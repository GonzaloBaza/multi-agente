# Entrega 1 — Inbox: paginación + filtro de fechas + export CSV — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el inbox pueda cargar conversaciones de a tandas (sin tope de 500), filtrar por rango de fechas, y exportar a CSV lo que matchea los filtros actuales (supervisor+).

**Architecture:** Backend — se extrae el armado del WHERE de `list_conversations` a un helper puro `_build_conversations_where` (testeable sin DB, mismo estilo que `_agent_queue_scope_sql`), reusado por un nuevo endpoint `GET /conversations.csv` que streamea CSV. Frontend — `useConversations` pasa de `useQuery` a `useInfiniteQuery` (paginación por `offset` que el backend ya soporta), se agregan inputs de fecha y los botones "Cargar más" y "Descargar CSV".

**Tech Stack:** FastAPI + asyncpg (Postgres/Supabase), Pydantic; Next.js 15 + React Query v5 (`@tanstack/react-query`); pytest (solo funciones puras, sin DB — ver `tests/conftest.py`).

---

## File Structure

- `api/inbox_api.py` (modify) — extraer `_build_conversations_where`; refactor `list_conversations`; agregar `CSV_HEADER`, `conversation_csv_row`, y el endpoint `export_conversations_csv`.
- `tests/test_conversations_where.py` (create) — unit tests del helper de WHERE.
- `tests/test_conversations_csv.py` (create) — unit tests de la fila CSV.
- `frontend/lib/api/inbox.ts` (modify) — `ConversationsParams` + `useConversations` a infinite query con `date_from`/`date_to`.
- `frontend/app/(app)/inbox/page.tsx` (modify) — estado de fechas, wiring de "Cargar más" + "Descargar CSV".
- `frontend/components/inbox/conversation-list.tsx` (modify) — props nuevas + UI (inputs de fecha, botón Cargar más, botón CSV con `RoleGate`).

Cada tarea deja el repo compilando/testeando y se commitea sola.

---

## Task 1: Backend — extraer `_build_conversations_where` (helper puro)

**Files:**
- Modify: `api/inbox_api.py` (función `list_conversations`, ~864-1042; helper nuevo antes de ella)
- Test: `tests/test_conversations_where.py` (create)

El objetivo es mover TODO el armado de `where_parts`/`params` (scope por rol + filtros + vistas) a una función pura que devuelve `(where_clause, params)`, sin tocar la lógica. `list_conversations` queda sólo con la query + el mapeo a `ConversationOut`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_conversations_where.py`:

```python
"""
Unit tests del armado de WHERE para el listado de conversaciones.

`_build_conversations_where` toma los filtros del inbox + el user logueado y
emite (where_clause, params). Es pura (no toca DB) — misma filosofía que
test_agent_queue_scope.py.
"""

from __future__ import annotations

from api.inbox_api import _build_conversations_where


def _call(**kw):
    base = dict(
        user=None, view=None, lifecycle=None, channel=None, queue=None,
        country=None, assigned_to=None, search=None, date_from=None, date_to=None,
    )
    base.update(kw)
    return _build_conversations_where(**base)


def test_admin_no_filters_hides_resolved():
    where, params = _call()
    assert "cm.status is null OR cm.status != 'resolved'" in where
    assert params == []


def test_agente_sin_id_ni_colas_no_ve_nada():
    where, params = _call(user={"role": "agente", "id": None, "queues": []})
    assert where == "WHERE FALSE"
    assert params == []


def test_channel_filter_param():
    where, params = _call(channel="widget")
    assert "c.channel = $1" in where
    assert params == ["widget"]


def test_date_range_params():
    where, params = _call(date_from="2026-06-01", date_to="2026-06-30")
    assert "c.updated_at >= $1::timestamptz" in where
    assert "c.updated_at <= $2::timestamptz" in where
    assert params == ["2026-06-01T00:00:00Z", "2026-06-30T23:59:59Z"]


def test_queue_and_lifecycle_share_param_numbering():
    where, params = _call(queue="sales", lifecycle="hot")
    assert "cm.queue = $1" in where
    assert "lifecycle_override, cm.lifecycle_auto, 'new') = $2" in where
    assert params == ["sales", "hot"]


def test_search_uses_single_param_three_times():
    where, params = _call(search="juan")
    assert where.count("$1") == 3  # name, email, last_message comparten $1
    assert params == ["%juan%"]    # se envuelve en %...%


def test_mine_view_without_user_is_false():
    where, params = _call(view="mine", user=None)
    assert "FALSE" in where
    assert params == []
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_conversations_where.py -v`
Expected: FAIL con `ImportError: cannot import name '_build_conversations_where'`.

- [ ] **Step 3: Implementar el helper**

En `api/inbox_api.py`, agregar ESTA función justo antes de `@router.get("/conversations", ...)` (o sea antes de `list_conversations`, ~línea 862). Copia exactamente la lógica actual de `list_conversations` (líneas 888-1007), sin la parte de `pool`/`params.append(limit)`/`params.append(offset)`:

```python
def _build_conversations_where(
    *,
    user: dict | None,
    view: str | None,
    lifecycle: str | None,
    channel: str | None,
    queue: str | None,
    country: str | None,
    assigned_to: str | None,
    search: str | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, list]:
    """Arma el WHERE (scope por rol + filtros + vista) del listado de
    conversaciones. Devuelve (where_clause, params): where_clause incluye el
    prefijo 'WHERE ' (o '' si no hay condiciones) con placeholders $1..$N;
    params son los valores posicionales. Si el agente no tiene visibilidad,
    devuelve ('WHERE FALSE', []) para que la query no traiga filas.

    Pura (no toca DB) — reusada por list_conversations y export_conversations_csv.
    """
    where_parts: list[str] = []
    params: list = []
    idx = 1

    if user and user.get("role") == "agente":
        agent_id = user.get("id")
        queue_scope = _agent_queue_scope_sql(user.get("queues") or [])
        scope_parts = []
        if agent_id:
            scope_parts.append(f"cm.assigned_agent_id = ${idx}::uuid")
            params.append(agent_id)
            idx += 1
        if queue_scope:
            scope_parts.append(f"(cm.assigned_agent_id IS NULL AND {queue_scope})")
        if scope_parts:
            where_parts.append("(" + " OR ".join(scope_parts) + ")")
        else:
            return "WHERE FALSE", []

    if date_from:
        where_parts.append(f"c.updated_at >= ${idx}::timestamptz")
        params.append(date_from + "T00:00:00Z")
        idx += 1
    if date_to:
        where_parts.append(f"c.updated_at <= ${idx}::timestamptz")
        params.append(date_to + "T23:59:59Z")
        idx += 1
    if channel:
        where_parts.append(f"c.channel = ${idx}")
        params.append(channel)
        idx += 1
    if assigned_to:
        where_parts.append(f"cm.assigned_agent_id = ${idx}::uuid")
        params.append(assigned_to)
        idx += 1
    if queue:
        where_parts.append(f"cm.queue = ${idx}")
        params.append(queue)
        idx += 1
    if country:
        if country.upper() == "MP":
            primary_list = ",".join(f"'{c}'" for c in sorted(PRIMARY_COUNTRIES))
            where_parts.append(
                f"upper(coalesce(c.user_profile->>'country', 'AR')) NOT IN ({primary_list})"
            )
        else:
            where_parts.append(
                f"upper(coalesce(c.user_profile->>'country', 'AR')) = upper(${idx})"
            )
            params.append(country)
            idx += 1
    if lifecycle:
        where_parts.append(f"coalesce(cm.lifecycle_override, cm.lifecycle_auto, 'new') = ${idx}")
        params.append(lifecycle)
        idx += 1
    if search:
        where_parts.append(
            f"(c.user_profile->>'name' ilike ${idx} OR c.user_profile->>'email' ilike ${idx} OR lm.content ilike ${idx})"
        )
        params.append(f"%{search}%")
        idx += 1

    if view == "unread":
        if user and user.get("id"):
            where_parts.append(
                f"""(cm.bot_paused = true AND EXISTS (
                    SELECT 1 FROM public.messages m2
                    LEFT JOIN public.inbox_read_state rs2
                        ON rs2.conversation_id = m2.conversation_id
                        AND rs2.user_id = ${idx}::uuid
                    WHERE m2.conversation_id = c.id
                      AND m2.role = 'user'
                      AND (rs2.last_read_at IS NULL OR m2.created_at > rs2.last_read_at)
                ))"""
            )
            params.append(user["id"])
            idx += 1
        else:
            where_parts.append("FALSE")
    elif view == "mine":
        if user and user.get("id"):
            where_parts.append(f"cm.assigned_agent_id = ${idx}::uuid")
            params.append(user["id"])
            idx += 1
        else:
            where_parts.append("FALSE")
    elif view == "queue":
        where_parts.append("cm.assigned_agent_id is null AND cm.needs_human = true")
    elif view == "human-attn":
        where_parts.append("(cm.bot_paused = true OR cm.assigned_agent_id is not null)")
    elif view == "with-bot":
        where_parts.append("(cm.bot_paused = false AND coalesce(cm.needs_human,false) = false)")
    elif view == "resolved":
        where_parts.append("cm.status = 'resolved'")
    elif view in (None, "all"):
        where_parts.append("(cm.status is null OR cm.status != 'resolved')")

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    return where, params
```

- [ ] **Step 4: Refactor `list_conversations` para usar el helper**

Reemplazar el bloque de `list_conversations` que va desde la línea existente `pool = await postgres_store.get_pool()` (~886) hasta el cierre del armado de `where` y los `params.append(limit)/append(offset)` (~1011) por lo siguiente. **Importante**: el rango reemplazado ARRANCA en la línea `pool = ...` que ya existe, así no queda duplicada:

```python
    pool = await postgres_store.get_pool()

    user = (auth or {}).get("user") if (auth or {}).get("auth") == "session" else None
    where, params = _build_conversations_where(
        user=user, view=view, lifecycle=lifecycle, channel=channel, queue=queue,
        country=country, assigned_to=assigned_to, search=search,
        date_from=date_from, date_to=date_to,
    )

    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params.append(limit)
    params.append(offset)
```

Y en el `sql` de abajo, reemplazar las dos líneas finales:

```python
        ORDER BY c.updated_at DESC
        LIMIT ${idx - 1} OFFSET ${idx}
```

por:

```python
        ORDER BY c.updated_at DESC, c.id
        LIMIT ${limit_idx} OFFSET ${offset_idx}
```

(El `, c.id` agrega orden estable para que la paginación por offset no saltee filas con el mismo `updated_at`. No debe quedar un `ORDER BY` duplicado.)

Dejar intacto el resto (`async with pool.acquire()`, unread_map, presence_map, el `for r in rows` → `ConversationOut`). Borrar la línea vieja `pool = await postgres_store.get_pool()` duplicada al inicio si quedó (debe haber UNA sola, la de arriba).

- [ ] **Step 5: Correr tests + smoke de imports**

Run: `python -m pytest tests/test_conversations_where.py tests/test_imports_smoke.py -v`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add api/inbox_api.py tests/test_conversations_where.py
git commit -m "refactor(inbox): extraer _build_conversations_where (puro, testeable) + orden estable"
```

---

## Task 2: Backend — helpers puros de CSV (`CSV_HEADER`, `conversation_csv_row`)

**Files:**
- Modify: `api/inbox_api.py` (agregar constantes/función cerca de los schemas, ~línea 102)
- Test: `tests/test_conversations_csv.py` (create)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_conversations_csv.py`:

```python
"""Unit tests del mapeo de una conversación a fila CSV (pura, sin DB)."""

from __future__ import annotations

from api.inbox_api import CSV_HEADER, conversation_csv_row


def _sample(**kw):
    base = dict(
        id="abc-123",
        created="2026-06-01T10:00:00+00:00",
        last_activity="2026-06-02T11:30:00+00:00",
        channel="widget",
        name="Juan Pérez",
        email="juan@example.com",
        phone="+5491122334455",
        country="AR",
        queue="sales",
        lifecycle="hot",
        status="open",
        needs_human=True,
        bot_paused=False,
        message_count=7,
        last_message="hola\nquiero info",
    )
    base.update(kw)
    return base


def test_header_has_expected_columns():
    assert CSV_HEADER[0] == "id"
    assert "area" in CSV_HEADER
    assert "ultimo_mensaje" in CSV_HEADER
    assert len(CSV_HEADER) == 16


def test_row_length_matches_header():
    row = conversation_csv_row(_sample())
    assert len(row) == len(CSV_HEADER)


def test_area_label_maps_queue():
    assert conversation_csv_row(_sample(queue="sales"))[CSV_HEADER.index("area")] == "Ventas"
    assert conversation_csv_row(_sample(queue="post-sales"))[CSV_HEADER.index("area")] == "Post-venta"
    assert conversation_csv_row(_sample(queue="billing"))[CSV_HEADER.index("area")] == "Cobranzas"


def test_booleans_are_si_no():
    row = conversation_csv_row(_sample(needs_human=True, bot_paused=False))
    assert row[CSV_HEADER.index("needs_human")] == "Sí"
    assert row[CSV_HEADER.index("bot_paused")] == "No"


def test_last_message_newlines_flattened():
    row = conversation_csv_row(_sample(last_message="hola\nquiero info"))
    assert "\n" not in row[CSV_HEADER.index("ultimo_mensaje")]
    assert row[CSV_HEADER.index("ultimo_mensaje")] == "hola quiero info"


def test_message_count_is_string():
    row = conversation_csv_row(_sample(message_count=7))
    assert row[CSV_HEADER.index("mensajes")] == "7"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_conversations_csv.py -v`
Expected: FAIL con `ImportError: cannot import name 'CSV_HEADER'`.

- [ ] **Step 3: Implementar los helpers**

En `api/inbox_api.py`, después de la clase `MessageOut` (~línea 102), agregar:

```python
# ─── Export CSV (helpers puros) ──────────────────────────────────────────────

CSV_HEADER = [
    "id", "creada", "ultima_actividad", "canal", "nombre", "email", "telefono",
    "pais", "area", "lifecycle", "estado", "asignada_a", "needs_human",
    "bot_paused", "mensajes", "ultimo_mensaje",
]

_AREA_LABEL = {
    "sales": "Ventas",
    "billing": "Cobranzas",
    "post-sales": "Post-venta",
    "support": "Soporte",
}


def conversation_csv_row(c: dict, agent_name: str = "") -> list[str]:
    """Mapea una conversación normalizada (dict) a una fila CSV alineada con
    CSV_HEADER. Pura — el endpoint arma el dict desde la fila de Postgres."""
    return [
        c["id"],
        c.get("created") or "",
        c.get("last_activity") or "",
        c.get("channel") or "",
        c.get("name") or "",
        c.get("email") or "",
        c.get("phone") or "",
        c.get("country") or "",
        _AREA_LABEL.get(c.get("queue") or "sales", c.get("queue") or ""),
        c.get("lifecycle") or "",
        c.get("status") or "",
        agent_name or "",
        "Sí" if c.get("needs_human") else "No",
        "Sí" if c.get("bot_paused") else "No",
        str(c.get("message_count") or 0),
        (c.get("last_message") or "").replace("\n", " ").replace("\r", " ").strip(),
    ]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_conversations_csv.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/inbox_api.py tests/test_conversations_csv.py
git commit -m "feat(inbox): helpers puros CSV_HEADER + conversation_csv_row"
```

---

## Task 3: Backend — endpoint `GET /conversations.csv` (supervisor+)

**Files:**
- Modify: `api/inbox_api.py` (nuevo endpoint después de `list_conversations`, ~línea 1118; nuevos imports arriba)

- [ ] **Step 1: Agregar imports**

Al tope de `api/inbox_api.py`, en la zona de imports stdlib (cerca de `import uuid`), agregar:

```python
import csv
import io
```

Y en el import de fastapi responses (agregar la línea si no está):

```python
from fastapi.responses import StreamingResponse
```

- [ ] **Step 2: Implementar el endpoint**

Insertar después del `return out` que cierra `list_conversations` (~línea 1117), antes de `@router.post("/conversations/{conv_id}/read")`:

```python
@router.get("/conversations.csv")
async def export_conversations_csv(
    view: str | None = None,
    lifecycle: str | None = None,
    channel: str | None = None,
    queue: str | None = None,
    country: str | None = None,
    assigned_to: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    auth: dict = Depends(require_role_or_admin("admin", "supervisor")),
):
    """Exporta a CSV las conversaciones que matchean los mismos filtros del
    inbox (sin paginar, tope duro de seguridad). Sólo supervisor+ — es bajada
    masiva de datos de contacto. Respeta el scope por rol vía el mismo helper
    que el listado."""
    EXPORT_CAP = 50000
    pool = await postgres_store.get_pool()
    user = (auth or {}).get("user") if (auth or {}).get("auth") == "session" else None
    where, params = _build_conversations_where(
        user=user, view=view, lifecycle=lifecycle, channel=channel, queue=queue,
        country=country, assigned_to=assigned_to, search=search,
        date_from=date_from, date_to=date_to,
    )
    cap_idx = len(params) + 1
    params.append(EXPORT_CAP)

    sql = f"""
        SELECT
            c.id, c.channel, c.external_id, c.user_profile, c.updated_at, c.created_at,
            lm.content    AS last_message,
            lm.created_at AS last_message_at,
            mc.cnt        AS message_count,
            cm.assigned_agent_id,
            cm.status,
            cm.queue,
            cm.bot_paused,
            cm.needs_human,
            coalesce(cm.lifecycle_override, cm.lifecycle_auto, 'new') as lifecycle
        FROM public.conversations c
        LEFT JOIN public.conversation_meta cm ON cm.conversation_id = c.id
        LEFT JOIN LATERAL (
            SELECT content, created_at FROM public.messages
            WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1
        ) lm ON true
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS cnt FROM public.messages WHERE conversation_id = c.id
        ) mc ON true
        {where}
        ORDER BY c.updated_at DESC, c.id
        LIMIT ${cap_idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        agent_ids = list({str(r["assigned_agent_id"]) for r in rows if r["assigned_agent_id"]})
        agent_names: dict[str, str] = {}
        if agent_ids:
            arows = await conn.fetch(
                "SELECT id::text AS id, name FROM public.profiles WHERE id = ANY($1::uuid[])",
                agent_ids,
            )
            agent_names = {a["id"]: (a["name"] or "") for a in arows}

    if len(rows) >= EXPORT_CAP:
        logger.warning("csv_export_truncated", cap=EXPORT_CAP, where=where)

    def _normalize(r) -> dict:
        profile = r["user_profile"] or {}
        if isinstance(profile, str):
            import json as _json
            try:
                profile = _json.loads(profile)
            except Exception:
                profile = {}
        phone = profile.get("phone") or (r["external_id"] if r["channel"] == "whatsapp" else "") or ""
        last_act = r["last_message_at"] or r["updated_at"]
        return {
            "id": str(r["id"]),
            "created": r["created_at"].isoformat() if r["created_at"] else "",
            "last_activity": last_act.isoformat() if last_act else "",
            "channel": r["channel"],
            "name": profile.get("name") or "",
            "email": profile.get("email") or "",
            "phone": phone,
            "country": _infer_country_from_phone(phone) or profile.get("country") or "AR",
            "queue": r["queue"] or "sales",
            "lifecycle": r["lifecycle"] or "new",
            "status": r["status"] or "open",
            "assigned_agent_id": str(r["assigned_agent_id"]) if r["assigned_agent_id"] else "",
            "needs_human": bool(r["needs_human"]),
            "bot_paused": bool(r["bot_paused"]),
            "message_count": r["message_count"] or 0,
            "last_message": r["last_message"] or "",
        }

    def _iter():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(CSV_HEADER)
        yield "﻿" + buf.getvalue()  # BOM para que Excel respete acentos
        buf.seek(0); buf.truncate(0)
        for r in rows:
            c = _normalize(r)
            writer.writerow(conversation_csv_row(c, agent_names.get(c["assigned_agent_id"], "")))
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    filename = f"conversaciones_{datetime.utcnow().date().isoformat()}.csv"
    return StreamingResponse(
        _iter(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 3: Smoke de imports + arranque local**

Run: `python -m pytest tests/test_imports_smoke.py -v`
Expected: PASS (el módulo importa sin romper).

- [ ] **Step 4: Verificación manual contra el server (post-deploy, ver Task 6)**

Diferida a Task 6 (requiere DB real). Comando de verificación con admin key:

```bash
curl -s -o /tmp/convs.csv -w "%{http_code}\n" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agentes.msklatam.com/api/v1/inbox/conversations.csv?queue=sales&date_from=2026-06-01"
head -3 /tmp/convs.csv   # primera línea = header con BOM
```
Expected: `200` y el CSV con header `id,creada,...` y filas de ventas desde el 1-jun.

- [ ] **Step 5: Commit**

```bash
git add api/inbox_api.py
git commit -m "feat(inbox): endpoint GET /conversations.csv (export filtrado, supervisor+)"
```

---

## Task 4: Frontend — `useConversations` a infinite query + filtro de fechas

**Files:**
- Modify: `frontend/lib/api/inbox.ts` (`ConversationsParams` ~211-219, `useConversations` ~221-244; agregar import `useInfiniteQuery`)

- [ ] **Step 1: Agregar `useInfiniteQuery` al import de react-query**

Buscar el import de `@tanstack/react-query` en el archivo y agregar `useInfiniteQuery` a la lista (junto a `useQuery`, `useMutation`, etc.). Si el import es `import { useQuery, useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";`, queda:

```ts
import { useQuery, useInfiniteQuery, useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
```

- [ ] **Step 2: Extender `ConversationsParams`**

Reemplazar el type (~211-219) por:

```ts
export type ConversationsParams = {
  view?: InboxView;
  lifecycle?: LifecycleStage | null;
  channel?: Channel | null;
  queue?: Queue | null;
  country?: string | null;
  search?: string;
  dateFrom?: string | null;
  dateTo?: string | null;
  limit?: number;
};
```

- [ ] **Step 3: Reescribir `useConversations` como infinite query**

Reemplazar la función `useConversations` entera (~221-244) por:

```ts
export function useConversations(params: ConversationsParams) {
  const PAGE = params.limit ?? 500;

  const buildQs = () => {
    const qs = new URLSearchParams();
    if (params.view && params.view !== "all") qs.set("view", params.view);
    if (params.lifecycle) qs.set("lifecycle", params.lifecycle);
    if (params.channel)   qs.set("channel", params.channel);
    if (params.queue)     qs.set("queue", params.queue);
    if (params.country)   qs.set("country", params.country);
    if (params.search)    qs.set("search", params.search);
    if (params.dateFrom)  qs.set("date_from", params.dateFrom);
    if (params.dateTo)    qs.set("date_to", params.dateTo);
    return qs;
  };

  const q = useInfiniteQuery({
    queryKey: ["inbox", "conversations", Object.fromEntries(buildQs())],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const qs = buildQs();
      qs.set("limit", String(PAGE));
      qs.set("offset", String(pageParam));
      const data = await api.get<ApiConversation[]>(`/inbox/conversations?${qs}`);
      return data.map(apiToListItem);
    },
    // Si la última página vino incompleta, no hay más; si vino llena, el
    // próximo offset es la cantidad total ya traída.
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length < PAGE ? undefined : allPages.length * PAGE,
    staleTime: 5_000,
    refetchInterval: 15_000, // polling de 15s para nuevas conversaciones
  });

  const items = (q.data?.pages ?? []).flat();
  return Object.assign(q, { items });
}
```

- [ ] **Step 4: Verificar tipos/build del front**

Run: `cd frontend && npm run build`
Expected: build OK (sin errores de tipo en `inbox.ts`). Si `apiToListItem`/`ApiConversation` no estuvieran en scope, ya lo estaban en la versión previa — no se tocan.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/inbox.ts
git commit -m "feat(inbox): useConversations con paginacion infinite + filtro de fechas"
```

---

## Task 5: Frontend — UI: filtro de fechas, "Cargar más" y "Descargar CSV"

**Files:**
- Modify: `frontend/app/(app)/inbox/page.tsx` (estado + wiring, ~96-126)
- Modify: `frontend/components/inbox/conversation-list.tsx` (Props ~24-69 + UI)

- [ ] **Step 1: Estado de fechas + consumo del infinite query en la página**

En `frontend/app/(app)/inbox/page.tsx`, después de `const [search, setSearch] = useState("");` (~101) agregar:

```tsx
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
```

Reemplazar (~125-126):

```tsx
  const convsQ = useConversations({ view, lifecycle, channel, queue, country, search });
  const items = convsQ.data ?? [];
```

por:

```tsx
  const convsQ = useConversations({
    view, lifecycle, channel, queue, country, search,
    dateFrom: dateFrom || null, dateTo: dateTo || null,
  });
  const items = convsQ.items;
```

(Si más abajo en el archivo hay otros usos de `convsQ.data` para la lista, cambiarlos a `convsQ.items`. `convsQ.isLoading` / `convsQ.isError` siguen existiendo.)

- [ ] **Step 2: Handler de descarga CSV en la página**

Agregar dentro de `InboxPageInner`, junto a los otros `useCallback` (~después de `handleClickConv`):

```tsx
  const downloadCsv = useCallback(() => {
    const qs = new URLSearchParams();
    if (view !== "all") qs.set("view", view);
    if (lifecycle) qs.set("lifecycle", lifecycle);
    if (channel)   qs.set("channel", channel);
    if (queue)     qs.set("queue", queue);
    if (country)   qs.set("country", country);
    if (search)    qs.set("search", search);
    if (dateFrom)  qs.set("date_from", dateFrom);
    if (dateTo)    qs.set("date_to", dateTo);
    // Navegación directa same-origin → manda la cookie msk_session y descarga.
    window.open(`/api/v1/inbox/conversations.csv?${qs.toString()}`, "_blank");
  }, [view, lifecycle, channel, queue, country, search, dateFrom, dateTo]);
```

- [ ] **Step 3: Pasar las props nuevas a `<ConversationList ... />`**

En el JSX donde se renderiza `<ConversationList ... />`, agregar estas props (junto a las de filtros existentes):

```tsx
            dateFrom={dateFrom}
            onDateFromChange={setDateFrom}
            dateTo={dateTo}
            onDateToChange={setDateTo}
            onExportCsv={downloadCsv}
            hasMore={!!convsQ.hasNextPage}
            loadingMore={convsQ.isFetchingNextPage}
            onLoadMore={() => convsQ.fetchNextPage()}
```

- [ ] **Step 4: Extender Props de `ConversationList`**

En `frontend/components/inbox/conversation-list.tsx`, agregar al `interface Props` (después de `search`/`onSearchChange`, ~55):

```tsx
  dateFrom: string;
  onDateFromChange: (v: string) => void;
  dateTo: string;
  onDateToChange: (v: string) => void;

  /** Export CSV (solo supervisor+ lo ve) */
  onExportCsv: () => void;

  /** Paginación incremental */
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
```

Y agregarlos a la desestructuración de props del componente (donde se hace `function ConversationList({ items, selectedId, ... }: Props)`), incluyendo `dateFrom, onDateFromChange, dateTo, onDateToChange, onExportCsv, hasMore, loadingMore, onLoadMore`.

- [ ] **Step 5: Importar `RoleGate` y `Download` + botón CSV en la toolbar**

En los imports de `conversation-list.tsx`:
- Agregar `Download` a la lista de `lucide-react` (línea 3).
- Cambiar `import { useRole } from "@/lib/auth";` por `import { useRole, RoleGate } from "@/lib/auth";` (si `useRole` no se usa más, se puede dejar igual; `RoleGate` es lo que sumamos).

En el header/toolbar, **justo al lado del botón de Refrescar** (el `<Button>` con `<RefreshCw />`), agregar:

```tsx
            <RoleGate min="supervisor">
              <Button
                variant="ghost"
                size="icon"
                title="Descargar CSV (conversaciones filtradas)"
                onClick={onExportCsv}
              >
                <Download className="h-4 w-4" />
              </Button>
            </RoleGate>
```

- [ ] **Step 6: Inputs de fecha en el panel de filtros**

Dentro del dropdown/sección de filtros avanzados (donde están los `CollapsibleSection` de lifecycle/channel/queue), agregar una sección:

```tsx
            <CollapsibleSection title="Fechas">
              <div className="flex flex-col gap-2 px-1 py-1">
                <label className="text-xs text-muted-foreground">
                  Desde
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => onDateFromChange(e.target.value)}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-muted-foreground">
                  Hasta
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => onDateToChange(e.target.value)}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
                  />
                </label>
              </div>
            </CollapsibleSection>
```

- [ ] **Step 7: Botón "Cargar más" al pie de la lista**

Al final del map de items (después del `.map(...)` que renderiza las filas, antes de cerrar el contenedor scrolleable de la lista), agregar:

```tsx
            {hasMore && (
              <button
                onClick={onLoadMore}
                disabled={loadingMore}
                className="w-full py-3 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                {loadingMore ? "Cargando…" : "Cargar más"}
              </button>
            )}
```

- [ ] **Step 8: Build del front**

Run: `cd frontend && npm run build`
Expected: build OK. Si TypeScript se queja de una prop faltante en `<ConversationList>`, completar la prop que falte (todas las nuevas de Step 4 deben pasarse en Step 3).

- [ ] **Step 9: Commit**

```bash
git add frontend/app/"(app)"/inbox/page.tsx frontend/components/inbox/conversation-list.tsx
git commit -m "feat(inbox): UI filtro de fechas + Cargar mas + boton Descargar CSV (supervisor+)"
```

---

## Task 6: Deploy + verificación real

**Files:** ninguno (deploy).

- [ ] **Step 1: Push**

```bash
git push origin main
```

- [ ] **Step 2: Build + recreate api + ui en el server (tmux)**

```bash
ssh -i ~/.ssh/msk_droplet -o ServerAliveInterval=30 root@129.212.145.193 \
  "cd /opt/multiagente && git pull --ff-only && rm -f /tmp/e1_done.flag && tmux kill-session -t e1 2>/dev/null; tmux new-session -d -s e1 'docker compose -p msk-multiagente build api ui > /tmp/e1.log 2>&1 && docker compose -p msk-multiagente up -d --force-recreate api ui >> /tmp/e1.log 2>&1 && echo DONE > /tmp/e1_done.flag'"
```
Esperar el flag (`until [ -f /tmp/e1_done.flag ]`).

- [ ] **Step 3: Verificación HTTP**

```bash
curl -sf https://agentes.msklatam.com/health    # 200 {"status":"ok"}
# CSV (con admin key del .env del server):
curl -s -o /tmp/c.csv -w "%{http_code}\n" -H "X-Admin-Key: <ADMIN_KEY>" \
  "https://agentes.msklatam.com/api/v1/inbox/conversations.csv?queue=sales"
head -2 /tmp/c.csv
```
Expected: health 200; CSV 200 con header `id,creada,ultima_actividad,...`.

- [ ] **Step 4: Verificación visual (Gonzalo)**

- En `/inbox`: aparece la sección "Fechas" en filtros; setear un rango filtra la lista.
- Botón "Descargar CSV" visible (supervisor/admin) → baja un .csv que abre bien en Excel con acentos.
- Con muchas conversaciones: aparece "Cargar más" al pie y trae la tanda siguiente sin duplicar.
- Un usuario rol `agente` NO ve el botón CSV.

---

## Notas de verificación / criterios de done (Entrega 1)

- `python -m pytest tests/test_conversations_where.py tests/test_conversations_csv.py tests/test_imports_smoke.py -v` → PASS.
- El listado del inbox sigue funcionando idéntico (mismos filtros, scope por rol intacto) — el refactor de Task 1 no cambia comportamiento observable salvo el `ORDER BY ... , c.id`.
- CSV respeta filtros + scope por rol (un agente sólo exporta lo que ve; el endpoint exige supervisor+ de todos modos).
- "Cargar más" pagina por offset sin saltear ni duplicar (orden estable por `updated_at, id`).
