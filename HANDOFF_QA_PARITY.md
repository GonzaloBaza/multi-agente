# Prompt de hand-off: paridad UI vieja → UI nueva + QA exhaustivo

**Pegá este prompt completo en una sesión nueva de Claude Code (con `/clear`).**
La sesión anterior dejó la app con bugs serios y funcionalidad faltante. Esta
sesión tiene que cerrar la deuda.

---

## Contexto del proyecto

Repo: `C:\Users\Gonzalo\Documents\GitHub\multi-agente` (rama `main`).
Sistema multi-agente para una empresa de cursos médicos (MSK Latam). Maneja
conversaciones de WhatsApp + widget web embebible. Bot IA + agentes humanos.

**Stack**:
- Backend: FastAPI + Python (`api/*.py`, `memory/*`, `integrations/*`)
- DB: Supabase Postgres + Redis para sesiones/estado
- Frontend nuevo (en migración): Next.js 15 App Router en `frontend/`
- UI vieja (a deprecar): HTML estático en `widget/*.html`, servido desde `main.py`
- Deploy: Docker Compose en DigitalOcean droplet

**Producción**:
- URL: https://agentes.msklatam.com
- SSH: `root@68.183.156.122` / password `MSK!@L4t4m`
- Path en server: `/opt/multiagente/`
- Cómo deployar: `git pull && docker compose build api ui && docker compose up -d api ui`
- Cómo correr migraciones: ver más abajo en sección "DB"

**Credenciales DB prod** (desde `/opt/multiagente/.env`):
- `DATABASE_URL` está en el .env del server. Para correr SQL ad-hoc:
  ```bash
  plink -batch -pw 'MSK!@L4t4m' root@68.183.156.122 \
    "docker run --rm -e PGPASSWORD='<pw del .env>' postgres:16-alpine \
     psql '<DATABASE_URL del .env con ?sslmode=require>' -c 'SELECT ...'"
  ```

**SSH desde Windows**: usar `plink -batch -pw 'MSK!@L4t4m' root@68.183.156.122 "<cmd>"`.
Las claves SSH del repo (`gbaza_key`, `gbaza.txt`) están encriptadas y no se
pueden desbloquear sin passphrase.

---

## Estado de la migración UI vieja → nueva

### UI vieja (en `widget/*.html`, servida desde rutas como `/inbox-ui`, `/admin/*-ui`):
- `inbox.html` — inbox completo (4900+ líneas, todo en un archivo)
- `users.html` — gestión de users
- `admin_prompts.html` — editor de prompts del bot
- `flows.html` — visual flow builder
- `templates.html` — templates HSM de WhatsApp
- `redis.html` — visor de Redis
- `dashboard.html` — métricas
- `test-agent.html` — sandbox de los agentes IA
- `login.html` — login

### UI nueva (en `frontend/app/(app)/`):
Páginas que existen pero **no se sabe si están completas ni protegidas por rol**:
- `/inbox` — inbox principal (lo único razonablemente completo)
- `/agents`
- `/analytics`
- `/channels`
- `/courses`
- `/prompts`
- `/settings`

**No existen** todavía: dashboard de métricas (`dashboard.html`), test agent
sandbox, flow builder, templates HSM, redis admin, retargeting panel.

---

## Roles del sistema (definidos en `api/auth.py`)

Tres roles, jerárquicos. Backend chequea con `require_role()` en cada endpoint;
la UI tiene que reflejarlo para no mostrar pantallas vacías o botones que
disparan 403.

### `agente` (default, más restrictivo)

**Inbox**:
- Solo ve conversaciones (a) asignadas a él, o (b) sin asignar en sus colas
  (`profile.queues`). Filtro hardcodeado en `widget/inbox.html:2497`.
- Solo ve sus colas asignadas en el filtro.
- Toma control de convs libres, manda mensajes, marca cerradas.
- **NO** puede asignar a otros, **NO** bulk ops, **NO** crear/editar snippets.

**Resto del rail**: nada de admin (Dashboard, Test AI, Flujos, Prompts,
Usuarios, Templates, Retargeting, Redis están todos detrás de `.admin-only`).

### `supervisor`

Hereda agente, **más**:
- Ve todas las conversaciones, no solo las suyas.
- Asigna a otros agentes.
- Bulk operations (`bulk_assign`, `bulk_close`, `bulk_label`).
- CRUD de snippets.
- Ve `/auth/users` y puede editar users existentes (NO crear ni borrar — eso
  es admin only en backend, ver `auth.py:183` y `:211`).
- Templates HSM, Dashboard, Test AI Agent, Retargeting.
- Endpoints `autonomous` (status, run-now, retry-now, toggle).

**NO** puede: crear/borrar users, editar prompts, editar flows, tocar Redis,
ver audit log de inbox, lifecycle stages.

### `admin`

Acceso total. Lo extra sobre supervisor:
- Crear/borrar users.
- Editar prompts del bot.
- CRUD + activar/desactivar flows.
- Redis admin (incluyendo `flush_conversations` y `nuclear_reset`).
- Audit log de la inbox.
- Crear/borrar lifecycle stages.

**Inconsistencias conocidas del modelo viejo (decidir si se replican o se corrigen)**:
1. `flows.html:302` redirige al inbox si no es admin, pero el backend
   `list_flows` permite supervisor. La UI bloquea más que el backend.
2. `admin_prompts.html:338` mismo patrón, también redirige.

---

## Bugs conocidos / pendientes en el frontend nuevo

1. **Sin chequeos de rol del lado del cliente**: cualquier user logueado ve el
   rail completo y puede entrar a cualquier página. El backend devuelve 403,
   pero la UX es mala. Hace falta:
   - Hook `useRole()` o helper en `lib/auth.tsx`.
   - Componente `<RoleGate roles={["admin","supervisor"]}>` o similar.
   - Ocultar items del rail (`components/layout/rail.tsx`) según rol.
   - Filtrar conversaciones del lado cliente para `agente` (si el backend no
     lo hace ya — verificar).

2. **Inbox del agente NO filtra**: el endpoint `/api/inbox/conversations` hoy
   devuelve TODAS las convs sin importar el rol. La UI vieja filtraba en JS,
   pero la nueva no tiene ese filtro. Decidir: filtrar en backend (mejor,
   fuente de verdad) o en cliente (peor, pero menos cambios).

3. **Bulk actions en lib/api/inbox.ts**: existen `useBulkAssign` y
   `useBulkResolve` — verificar que el backend las acepte y que la UI las
   exponga solo para supervisor/admin.

4. **Páginas que faltan**: armar checklist de qué de la UI vieja se quiere en
   la nueva. Mínimo recomendado:
   - `/users` (gestión de users — ya hay `/agents` pero verificar que cubra
     create/edit/delete según rol).
   - `/prompts` — verificar que sea admin-only.
   - `/templates` — para templates HSM, no existe en frontend nuevo.
   - `/dashboard` — métricas, no existe.
   - `/redis` — admin, no existe.
   - `/flows` — flow builder, no existe.
   - `/test-agent` — sandbox, no existe.

5. **El token vive en localStorage** — vulnerable a XSS si una dependencia se
   compromete. Idealmente migrar a httpOnly cookie (requiere cambios en
   `/auth/login` para devolver `Set-Cookie`).

6. **No hay `middleware.ts` en Next**: el HTML de la app se sirve igual a
   visitantes anónimos. Hoy tiene un guard de cliente en `(app)/layout.tsx`
   que hace redirect, pero el HTML se descarga primero. No es vulnerable
   (los datos vienen via API protegida) pero es defense-in-depth faltante.

7. **Verificar: `/api/inbox/stream` SSE** — la sesión anterior cambió la auth
   de `?key=admin_key` a `?token=<session>`. Confirmar que el frontend lo
   está usando bien y que el SSE conecta para users logueados (no solo
   admin).

---

## Bugs/deuda conocidos en el backend

1. **`APP_ENV=development` en prod** (`/opt/multiagente/.env`). Cambiar a
   `production` y verificar qué se rompe (varios chequeos están detrás de
   `is_production`).

2. **`api/lifecycle.py` existe pero el router está comentado** en
   `main.py:42`. Decidir: activarlo o borrar el archivo.

3. **El backend no filtra conversaciones por rol/queue del agente** en
   `/api/inbox/conversations`. Revisar `api/inbox_api.py` y agregar filtro
   server-side basado en `user["role"]` y `user["queues"]`.

4. **`verify_admin_or_session`** se usa solo en `/api/inbox/*`. Otros
   endpoints como `/admin/courses/*`, `/admin/prompts/*`, `/admin/templates/*`
   siguen usando `verify_admin_key` estricto. Si la UI nueva los va a
   consumir desde el browser logueado, hay que migrarlos.

5. **`api/templates.py:395`** importa `require_role` localmente — verificar
   por qué no en el top y limpiar.

6. **Tests**: hay un scaffold mínimo en `tests/` con pytest. NO hay tests de
   integración reales. Después de cualquier cambio grande, agregar tests.

---

## DB (Postgres / Supabase)

**Tablas relevantes** (ver migrations):
- `auth.users` (Supabase) — la fuente de verdad de auth.
- `public.profiles` — info extra (role, queues, name). PK debe coincidir con
  `auth.users.id` (migración 005 ya re-sincronizó esto).
- `public.conversations` — convs.
- `public.conversation_meta` — metadata operativa (assigned_to, queue,
  status, lifecycle, tags, bot_paused, needs_human). Antes tenía
  `snoozed_until`/`snoozed_at`, removidos en migración 006.
- `public.inbox_audit_log` — auditoría de acciones (asignar, clasificar,
  takeover, etc).
- `public.snippets` — respuestas rápidas.

**Migraciones aplicadas hasta ahora** (en `migrations/`):
- 002: conversation_meta inicial
- 003: inbox_audit_log
- 004: drop tabla `agents`, unificar todo en `profiles`
- 005: re-sync `profiles.id ← auth.users.id` + FKs faltantes
- 006: drop columnas snooze

**Verificar**:
- `select count(*) from auth.users;` vs `select count(*) from public.profiles;`
  → deben coincidir.
- Cada `profile.role` ∈ `{'agente','supervisor','admin'}`.
- `profile.queues` jsonb array de strings (puede estar vacío para admin/super).

---

## Tu trabajo en esta sesión

**Sé autónomo**. No me preguntes a cada paso. Hacé el QA, identificá los bugs,
arreglálos, deployá, verificá. Si encontrás algo serio, anotalo y seguí.

### Checklist obligatorio (no termines hasta cerrar todo esto)

#### 1. Auditoría de paridad UI vieja vs nueva
- Para cada `widget/*.html`, listar qué hace y dónde está (o si NO está) en
  el frontend nuevo.
- Reportá las gaps en una tabla markdown.

#### 2. Implementar role-based access control en el frontend nuevo
- `useRole()` hook + componente `<RoleGate>` (o equivalente).
- Aplicarlo en `components/layout/rail.tsx` (ocultar items según rol).
- Aplicarlo en cada página de `(app)/` que requiera rol específico.
- Para el `agente`, filtrar conversaciones server-side (modificar
  `api/inbox_api.py` `list_conversations`).

#### 3. Cerrar las páginas faltantes
Mínimo: `/users` (con CRUD según rol). El resto (templates, dashboard,
redis, flows, test-agent), si el alcance es grande, listalas como TODO en
un commit separado y avisame qué priorizar — pero al menos creá los stubs
con `<RoleGate>` y un mensaje "Próximamente".

#### 4. QA funcional end-to-end (en prod, desde el browser)
Para CADA rol (`agente`, `supervisor`, `admin`):
- Crear un usuario de cada rol (o usar uno existente — listar `profiles` primero).
- Loguearse como ese rol.
- Verificar que ve solo lo que le corresponde en el rail.
- Verificar que las páginas que NO debería ver (a) no están en el rail, (b) si
  navega manual a la URL, lo redirige o muestra "sin permisos".
- Verificar que las acciones que no debería poder hacer (botones, bulks) no
  están visibles, y si las llama por API directo → 403.
- Verificar que el inbox del `agente` filtra correctamente.

#### 5. Verificar el backend
- Correr los tests existentes: `cd tests && pytest`.
- Si falla algo del scaffold, arreglarlo.
- Agregar 1 test de integración por cada role check nuevo (mockear sesión).

#### 6. Verificar la DB
- Listar `profiles` con sus roles.
- Confirmar que `profile.id == auth.users.id` para todos.
- Confirmar que no hay convs huérfanas (sin `conversation_meta`).
- Verificar que las migraciones 002-006 estén aplicadas.

#### 7. Deploy + smoke test
- Commit + push + pull en prod + rebuild + restart.
- Smoke test de cada endpoint protegido por rol.
- Smoke test del SSE.

#### 8. Reporte final
Al terminar, escribime un mensaje con:
- ✅ qué funcionalidades de la UI vieja están ahora en la nueva.
- ⏳ qué quedó pendiente (con justificación de por qué se difirió).
- 🐛 qué bugs encontraste y arreglaste.
- 🔒 qué findings de seguridad encontraste (si alguno).
- 📋 qué tests agregaste.
- 🌐 cómo verificar manualmente en prod (URLs, qué clickear).

### Reglas

- **No deshabilites tests para que pasen**. Si un test falla, arreglá la causa.
- **No saltees el `git pull` en prod antes de buildar**. Si hay cambios remotos
  que no tenés, vas a sobreescribir.
- **No commitees secrets ni el .env**. El `.env.example` es el template.
- **Si encontrás un bug grave (auth, data leak, RCE)**, paralo todo, arreglalo
  primero, después seguí.
- **Mantené commits chicos y específicos**. Un commit por feature/fix.
- **No uses `git push --force`**.
- **No uses `git commit --amend`** si ya está pusheado.

### Si te trabás

Buscá en estos archivos:
- `HANDOFF_NEW_SESSION.md`, `SESSION_HANDOFF.md`, `PROJECT_CONTEXT.md`
- `CLAUDE.md` si existe
- `frontend/README.md`, `README.md`

---

**Empezá ya. Primer paso: leé `frontend/app/(app)/inbox/page.tsx` y
`api/auth.py` para confirmar el modelo, después armá la auditoría de paridad.**
