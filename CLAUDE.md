# MSK Multi-Agente — contexto operativo

Sistema multi-agente para MSK Latam (cursos médicos online, LATAM). Bot IA +
consola humana. Stack: FastAPI + LangGraph + Next.js 15. Deploy: DigitalOcean
droplet, Docker Compose, nginx.

## Arquitectura

```
┌─ Next.js 15 (frontend/) ────────────┐        ┌─ chat.js embebible ──┐
│  /inbox /prompts /users /templates   │        │  (msklatam.com,       │
│  /redis /dashboard /test-agent       │        │   msklatam.tech)      │
│  /agents /channels /analytics        │        └─┬─────────────────────┘
│  /settings /courses /login           │          │
└─┬────────────────────────────────────┘          │
  │ /api/*                                        │ /widget/*
  ▼                                               ▼
┌─ FastAPI (api/) ─────────────────────────────────────────────────────┐
│  /api/auth/*                   auth.py                                │
│  /api/inbox/*                  inbox_api.py  (13 endpoints REST)      │
│  /api/admin/*                  admin.py, admin_prompts.py,            │
│                                redis_admin.py, reports.py, etc.       │
│  /api/templates/*              templates.py (HSM)                     │
│  /widget/*                     widget.py (chat embebible público)     │
│  /webhook/*                    webhooks.py (Meta, MP, Rebill, Zoho)   │
│  /customer/*                   customer_auth.py (LMS)                 │
└───┬────────────────┬────────────────┬─────────────────────────────────┘
    │                │                │
    ▼                ▼                ▼
┌ Redis ──┐   ┌ Postgres ──┐   ┌ Integraciones ─────────────────────┐
│ Pub/Sub │   │ (Supabase) │   │ OpenAI (gpt-4o + mini + Whisper +  │
│ Cache   │   │ conv + msg │   │ TTS), Pinecone (RAG), Zoho CRM,    │
│ Session │   │ profiles   │   │ WhatsApp Meta Cloud API, Botmaker, │
│ Queues  │   │ audit_log  │   │ MercadoPago, Rebill, Cloudflare R2,│
│ Scheduler│  │            │   │ Sentry, Slack                       │
└─────────┘   └────────────┘   └────────────────────────────────────┘
```

## Convenciones de routing

**Única fuente de verdad**: el frontend Next.js consume todo bajo `/api/*`.
El cliente HTTP (`frontend/lib/api.ts`) antepone `/api` a cualquier path que
le pases — no hay casos especiales.

| Namespace | Quién lo consume | Ejemplo |
|---|---|---|
| `/api/*` | UI de la consola (Next.js) | `/api/inbox/conversations`, `/api/auth/login` |
| `/widget/*` | `chat.js` embebible en sitios externos | `/widget/chat`, `/widget/history/{id}` |
| `/webhook/*` | Integraciones (Meta/Botmaker/MP/Rebill/Zoho) | `/webhook/whatsapp`, `/webhook/mercadopago` |
| `/customer/*` | LMS externo | `/customer/login` |
| `/widget.js` | Bundle JS del widget público | — |
| `/health` | Uptime probe | — |

Agregar un endpoint nuevo del admin → va bajo `/api/admin/<cosa>` con prefix
en el router FastAPI correspondiente.

## Roles

Tres roles jerárquicos (hereda hacia arriba):

1. **`agente`** — solo ve Inbox. Filtrado server-side: ve sus conversaciones
   asignadas + las sin asignar dentro de sus `profiles.queues`
   (ej. `ventas_AR`, `cobranzas_MX`). No puede bulk ops.
2. **`supervisor`** — todo lo del agente + Analytics, Cursos, Plantillas HSM,
   Dashboard (Live/Histórico/Autónomo), Test Agent, Equipo (solo edita colas).
3. **`admin`** — todo + Agentes IA, Prompts, Canales, Redis, CRUD completo del
   Equipo. Único rol que crea/borra usuarios.

Enforcement:
- Backend: `Depends(require_role(...))` o `require_role_or_admin(...)` en cada
  endpoint sensible. En `list_conversations` el scope por rol se aplica en SQL.
- Frontend: `<RoleGate min="...">` en cada página + `rail.tsx` filtra items del
  nav.

## Deploy

**Servidor**: `root@68.183.156.122` · `/opt/multiagente/` · SSH por password
(`MSK!@L4t4m`).

**Containers** (`docker-compose.yml`):
- `multiagente-api-1` (FastAPI, puerto 8000 interno)
- `multiagente-ui-1` (Next.js, puerto 3000 interno)
- `multiagente-redis-1` (Redis 7, solo localhost)

**Flujo deploy**:
```bash
# local
git add . && git commit -m "..." && git push

# server
plink -batch -pw 'MSK!@L4t4m' root@68.183.156.122
cd /opt/multiagente && git pull
docker compose up -d --build api ui
# Si cambió deploy/nginx-agentes.msklatam.com.conf:
cp deploy/nginx-agentes.msklatam.com.conf /etc/nginx/sites-available/agentes.msklatam.com
nginx -t && systemctl reload nginx
```

**Verificación**:
```bash
curl -sf https://agentes.msklatam.com/health       # 200 {"status":"ok"}
curl -sf https://agentes.msklatam.com/widget.js    # 200 ~36KB
```

⚠️ `--build` es **obligatorio** en cada deploy. El `docker-compose.yml` no
monta el código como volumen — la imagen tiene el snapshot. Sin `--build` el
container sirve código viejo aunque el FS del host esté actualizado.

## DB (Supabase Postgres)

Tablas:
- `auth.users` — managed por Supabase Auth (email + password + JWT).
- `public.profiles` — 1:1 con `auth.users`. Campos: `id` (uuid FK a
  `auth.users.id`), `email`, `name`, `role` ∈ `{admin, supervisor, agente}`,
  `queues` (text[] — colas asignadas).
- `public.conversations` — creadas por el bot (widget / WhatsApp).
- `public.messages` — mensajes de cada conversación.
- `public.conversation_meta` — metadata operativa (assigned_agent_id, status,
  queue, bot_paused, lifecycle, tags, needs_human). 1:1 con conversations.
- `public.inbox_audit_log` — acciones humanas en la consola (asignar,
  clasificar, takeover).

Migraciones en `migrations/` (002-006). Al correr una nueva:
```bash
pscp -batch -pw 'MSK!@L4t4m' migrations/00X.sql root@68.183.156.122:/tmp/
plink -batch -pw 'MSK!@L4t4m' root@68.183.156.122 \
  "docker cp /tmp/00X.sql multiagente-api-1:/tmp/ && \
   docker exec multiagente-api-1 python -c \"
import asyncio, asyncpg, os
async def main():
    c = await asyncpg.connect(os.environ['DATABASE_URL'], statement_cache_size=0)
    await c.execute(open('/tmp/00X.sql').read())
    await c.close()
asyncio.run(main())
\""
```

⚠️ `statement_cache_size=0` es **obligatorio** porque Supabase usa pgbouncer en
transaction mode.

## Agentes IA

4 agentes LangGraph bajo `agents/`:
- **`sales`** — RAG de cursos (Pinecone por país), pitch + link de pago
  (MercadoPago/Rebill).
- **`closer`** — toma el handoff de Ventas cuando el lead está caliente.
- **`collections`** — cobranzas (lee `area_cobranzas` de Zoho), regenera
  links de pago, gestiones.
- **`post_sales`** — soporte LMS (acceso, certificados, tickets).

**Router** (`agents/router.py`): gpt-4o-mini clasifica intent, despacha al
agente correspondiente. Persiste `queue` efectivo en `conversation_meta`.

**Widget flow** (`agents/routing/widget_flow.py`): máquina de estados
hardcoded para el menú inicial del widget (pre-IA). Estados: `main_menu` →
`asesoria_menu` → `pending_email` → `done`. Vive en Redis `wflow:{sid}`.

**Prompts**: editables en vivo desde `/prompts` (UI). Se persisten en
`agents/<agente>/prompts.py`. El bot lee el archivo en cada turno (no se
cachea el módulo). ⚠️ `docker compose build` sin pushear a git sobrescribe.

## Preferencias del usuario (Gonzalo Baza)

- Español rioplatense informal.
- Verificación real (HTTP 200, screenshot) antes de decir "listo".
- Trabajar directo en `main`, nunca worktrees.
- No inventar features ni nombres de archivos.
- Cambios pequeños y verificables, no big-bang.
