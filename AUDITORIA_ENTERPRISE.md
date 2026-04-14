# Auditoría Enterprise — MSK Latam Multi-Agente
**Fecha inicio:** 2026-04-13 | **Última actualización:** 2026-04-13
**Alcance:** Arquitectura, UX/UI, Meta/WhatsApp, Seguridad, Escalabilidad, Auditoría Gemini
**North Star:** Agente IA 100% autónomo que reabre conversaciones con plantillas HSM y cierra ventas 24/7

---

## 0. Visión — Sales Closer Autónomo

El objetivo final es un sistema que:
1. **Detecte oportunidades** en conversaciones abandonadas o leads fríos
2. **Reabra conversaciones** usando plantillas HSM aprobadas por Meta (fuera de la ventana de 24h)
3. **Ejecute secuencias de follow-up** automáticas (día 1, 3, 7, 15, 30)
4. **Negocie y cierre ventas** autónomamente usando contexto de Zoho CRM + historial
5. **Escale a humano** solo cuando sea necesario (objeciones complejas, pagos fallidos)
6. **Genere links de pago** (MercadoPago/Rebill) y trackee conversiones
7. **Reporte métricas** de funnel completo: contactados → respondidos → interesados → pagados

**Estado actual:** El sistema tiene los agentes IA, canales WhatsApp, CRM, pagos, pero le falta el "cerebro" autónomo que orqueste todo sin intervención humana.

---

## 1. Diagnóstico General

### Lo que funciona bien
- 3 agentes IA (ventas, soporte, clasificador) con LangGraph
- 3 canales WhatsApp (Meta directo, Twilio, Botmaker)
- Widget web con streaming SSE
- Inbox humano con Kanban, labels, asignación
- Integración Zoho CRM bidireccional (contactos, cursadas, historial)
- Pagos MercadoPago + Rebill con monitoreo automático
- Flujos visuales con Drawflow
- RAG con Pinecone (catálogo de cursos)
- Auth con Supabase (login, roles, permisos)
- Circuit breakers en APIs externas
- Rate limiting global (60/min) + auth (5/min)

### Riesgos principales
- ~~Credenciales hardcodeadas en `deploy_all.py`~~ → RESUELTO: movido a `.env`
- ~~`asyncio.sleep` bloqueante en tareas de monitoreo de pagos~~ → RESUELTO: reemplazado con Redis TTL
- ~~Redis: conexiones nuevas por request (sin pool)~~ → RESUELTO: singleton via `get_conversation_store()`
- Sin tests automatizados
- Media en filesystem local (no cloud storage)
- ~~Business hours configurados pero no enforced en el flujo~~ → RESUELTO: enforcement en widget + WhatsApp

---

## 2. Estado por Área — Checklist

### 2.1 Seguridad

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Auth en endpoints admin/inbox | ✅ DONE | `api/auth.py` con `require_role()`, Supabase JWT |
| 2 | Rate limiting | ✅ DONE | SlowAPI: 60/min global, 5/min auth (`main.py`) |
| 3 | Credenciales hardcodeadas en deploy | ✅ DONE | Movido a `.env`, `deploy_all.py` lee de env vars |
| 4 | `.env` en `.gitignore` | ✅ DONE | `.gitignore` incluye `.env` |
| 5 | Webhook signature verification | 🔧 PARCIAL | Meta webhook verifica firma, pero es bypassable |
| 6 | CORS configurado | ✅ DONE | `allowed_origins` en settings, no wildcard |
| 7 | Security headers (CSP, HSTS, X-Frame) | ✅ DONE | Middleware en main.py |
| 8 | Docker non-root user | ✅ DONE | Dockerfile: `useradd appuser`, corre como appuser |
| 9 | Docker multi-stage build | ✅ DONE | Builder stage + production stage |
| 10 | Healthcheck en Docker | ✅ DONE | Healthcheck en Dockerfile |
| 11 | Redis con password | ❌ PENDIENTE | Redis sin `requirepass` en compose |

### 2.2 Arquitectura & Infraestructura

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Circuit breakers | ✅ DONE | `utils/circuit_breaker.py` wired en Zoho, Meta, OpenAI |
| 2 | Redis Pub/Sub cross-worker | ✅ DONE | `broadcast_event()` usa Redis Pub/Sub, listener distribuye local |
| 3 | Redis connection pooling | ✅ DONE | Singleton `get_conversation_store()` en webhooks.py |
| 4 | asyncio.sleep en monitoreo de pagos | ✅ DONE | Reemplazado con Redis `expire()` TTL |
| 5 | Background job runner (Celery/APScheduler) | ❌ PENDIENTE | No hay worker persistente para tareas programadas |
| 6 | Media storage cloud (S3/R2) | ❌ PENDIENTE | Media en filesystem local (`/app/media` con Docker volume) |
| 7 | PostgreSQL backup de Redis | ❌ PENDIENTE | Todo en Redis, sin persistencia relacional |
| 8 | Channel abstraction layer | ❌ PENDIENTE | Cada canal tiene su propia implementación |
| 9 | Audit logging | 🔧 PARCIAL | Endpoint `/inbox/audit-log` existe, logging básico |
| 10 | Tests automatizados | ❌ PENDIENTE | No hay suite de tests (solo `seed_test_data.py`) |
| 11 | Métricas/Prometheus | 🔧 PARCIAL | `/health` + `/inbox/metrics` (FRT), sin Prometheus |

### 2.3 Consola de Agente (Inbox)

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Texto plano send/receive | ✅ DONE | Textarea con auto-expand |
| 2 | Audio/notas de voz | ✅ DONE | Grabación WebAudio + envío, playback en inbox |
| 3 | Macros/respuestas rápidas | ✅ DONE | CRUD Redis-backed, UI manager, atajos `/` |
| 4 | Kanban board | ✅ DONE | 8 columnas con labels |
| 5 | Drag & drop en Kanban | ✅ DONE | SortableJS con reglas de validación, SLA indicators |
| 6 | Búsqueda de mensajes | ✅ DONE | `filterMessages()` con highlight y scroll |
| 7 | Filtros avanzados (país, agente, label, fecha) | ✅ DONE | Panel de filtros con `applyFilters()` |
| 8 | Plantillas HSM desde inbox | ✅ DONE | Selector de plantillas, preview, variables, envío |
| 9 | Adjuntar archivos (imágenes, docs) | ✅ DONE | File picker con `handleMediaUpload()` |
| 10 | Emoji picker | ✅ DONE | Picker por categorías con `toggleEmojiPicker()` |
| 11 | Typing indicator | ✅ DONE | Typing events via Redis + SSE broadcast |
| 12 | Notificaciones desktop + sonido | ✅ DONE | Notification API + Web Audio beep |
| 13 | Banner ventana 24h | ✅ DONE | Endpoint + banner con TTL tracking |
| 14 | Status de mensajes (✓ ✓✓) | ✅ DONE | Procesa webhook `statuses` de Meta, broadcast SSE |
| 15 | Indicadores SLA por conversación | ✅ DONE | SLA en Kanban cards (ok/warn/breach) |
| 16 | Collision prevention (typing lock) | ✅ DONE | Redis lock + banner "X está escribiendo" |
| 17 | Close/reopen conversaciones | ✅ DONE | Endpoints + estado CLOSED |
| 18 | Bulk operations (label, assign, close) | ✅ DONE | Backend + UI frontend (selección múltiple) |
| 19 | Asignación round-robin | ✅ DONE | Auto-assign al handoff, least-loaded agent |
| 20 | Preview multimedia en hilo | 🔧 PARCIAL | Audio funciona, imágenes/docs/video pendientes |

### 2.4 Widget Web

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Chat texto con streaming SSE | ✅ DONE | `chat.js` con SSE word-by-word |
| 2 | Saludo personalizado con contexto | ✅ DONE | Nombre, email, cursos del usuario |
| 3 | Audio playback | ✅ DONE | `appendMessage()` con audio/img/video |
| 4 | Historial de conversación | ✅ DONE | `/widget/history/{session_id}` con media |
| 5 | Business hours enforcement | ✅ DONE | Enforced en widget.py y whatsapp_meta.py |
| 6 | Botón de satisfacción/rating | ❌ PENDIENTE | No implementado |
| 7 | Transferencia a WhatsApp | ❌ PENDIENTE | No hay handoff widget→WhatsApp |

### 2.5 WhatsApp/Meta

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Texto entrante/saliente | ✅ DONE | Todos los proveedores |
| 2 | Botones interactivos | ✅ DONE | Meta Cloud API |
| 3 | Listas interactivas | 🔧 PARCIAL | Solo Meta |
| 4 | Plantillas HSM — envío | ✅ DONE | `api/templates.py` + WhatsAppMetaClient |
| 5 | Plantillas HSM — listar aprobadas | ✅ DONE | `GET /templates/hsm` con cache 5min |
| 6 | Media entrante (descarga de Meta) | ✅ DONE | `download_media()` en whatsapp_meta.py |
| 7 | Media saliente (imagen/audio/doc) | 🔧 PARCIAL | Audio funciona, faltan imagen y docs desde inbox |
| 8 | Status tracking (sent/delivered/read) | ✅ DONE | `_handle_wa_status()` procesa webhooks de Meta |
| 9 | Ventana 24h tracking | ✅ DONE | `wa_window:{phone}` con TTL 86400s |
| 10 | Ventana 24h enforcement | ✅ DONE | Endpoint + banner en inbox |
| 11 | Retargeting automático con HSM | ✅ DONE | Backend: config CRUD, run trigger, stats, cycle engine |
| 12 | Secuencias de follow-up | ✅ DONE | Day-based sequences (1,3,7,15,30) con HSM templates |

### 2.6 Zoho CRM

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Búsqueda de contactos | ✅ DONE | Por email, teléfono |
| 2 | Creación de leads | ✅ DONE | Desde widget y WhatsApp |
| 3 | Panel CRM en inbox | ✅ DONE | Sub-tabs con datos de contacto |
| 4 | Historial de cursadas | ✅ DONE | Lookups a módulos custom |
| 5 | Sync bidireccional | ✅ DONE | Eventos y notas |
| 6 | Webhook Zoho → plataforma | ✅ DONE | `/webhooks/zoho` procesa eventos |

### 2.7 Pagos

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | MercadoPago links de pago | ✅ DONE | Generación + webhook |
| 2 | Rebill suscripciones | ✅ DONE | Checkout links + webhook |
| 3 | Monitoreo automático de pagos | ✅ DONE | Background task (pero con asyncio.sleep) |
| 4 | Cobranzas panel en inbox | ✅ DONE | Sub-tab de cobranzas |

### 2.8 Agentes IA

| # | Item | Estado | Detalle |
|---|------|--------|---------|
| 1 | Agente de ventas | ✅ DONE | LangGraph con tools |
| 2 | Agente de soporte | ✅ DONE | RAG + knowledge base |
| 3 | Clasificador/router | ✅ DONE | Ruteo inteligente por intención |
| 4 | Flujos visuales (Drawflow) | ✅ DONE | Builder + runner |
| 5 | RAG con Pinecone | ✅ DONE | Metadata normalizada por país |
| 6 | Prompt management | ✅ DONE | Editable desde admin |
| 7 | Context summaries para clasificador | ❌ PENDIENTE | No hay resumen largo plazo (baja prioridad) |
| 8 | **Agente Sales Closer autónomo** | ✅ DONE | LangGraph agent con 5 fases de cierre + retargeting engine |

---

## 3. Hallazgos de Auditoría Gemini — Detalle Técnico

### 3.1 Credenciales hardcodeadas (CRÍTICO)
**Archivo:** `deploy_all.py` líneas 8-10
```python
HOST = "<server-ip-redacted>"
USER = "root"
PASS = "<password-redacted>"
```
**Riesgo:** Cualquier persona con acceso al repo tiene acceso root al servidor de producción.
**Fix:** Mover a `.env` o usar SSH key authentication. Rotar password del servidor.

### 3.2 asyncio.sleep bloqueante (ALTO)
**Archivo:** `api/webhooks.py`
- Línea 97: `await asyncio.sleep(15 * 60)` — 15 minutos
- Línea 149: `await asyncio.sleep(75 * 60)` — 75 minutos
- Línea 152: `await asyncio.sleep(80700)` — ~22 horas

**Riesgo:** Cada tarea de monitoreo de pago mantiene una coroutine abierta durante horas. Con muchos pagos concurrentes, el event loop se degrada.
**Fix:** Reemplazar con APScheduler o Redis-based delayed jobs.

### 3.3 Redis connection leaks (MEDIO)
**Archivos afectados:**
- `api/admin.py` — `aioredis.from_url()` en cada request
- `api/inbox.py` — `aioredis.from_url()` en `start_pubsub_listener()`
- `api/webhooks.py` — múltiples `aioredis.from_url()`

**Riesgo:** Conexiones que nunca se cierran, file descriptor exhaustion bajo carga.
**Fix:** Pool global de conexiones en `memory/conversation_store.py`, inyectar en todos los módulos.

### 3.4 Sin tests (ALTO)
No existe suite de tests. Solo `seed_test_data.py` para datos de prueba.
**Fix:** Crear `tests/` con pytest, fixtures para Redis mock, tests de integración para router y agentes.

---

## 4. Sprints Completados

### Sprint 1 — Fundación (completado)
- ✅ Arquitectura multi-agente con LangGraph
- ✅ 3 canales WhatsApp funcionando
- ✅ Widget web con streaming
- ✅ Inbox humano básico
- ✅ Integración Zoho CRM

### Sprint 2 — Inbox Avanzado (completado)
- ✅ Kanban board con labels
- ✅ Asignación de agentes
- ✅ Takeover/release de conversaciones
- ✅ SSE real-time updates

### Sprint 3 — CRM & Pagos (completado)
- ✅ Panel CRM en inbox con sub-tabs
- ✅ MercadoPago + Rebill integración
- ✅ Cobranzas panel
- ✅ Zoho bidireccional

### Sprint 4 — Flujos & RAG (completado)
- ✅ Drawflow visual builder
- ✅ Flow runner con estados
- ✅ Pinecone RAG con metadata normalizada
- ✅ Prompt management

### Sprint 5 — Auth & Admin (completado)
- ✅ Supabase auth (login, roles, permisos)
- ✅ Redis admin tool
- ✅ Rate limiting
- ✅ Circuit breakers

### Sprint 6 — Enterprise Fixes (completado)
- ✅ Message duplication fix (Redis Pub/Sub refactor)
- ✅ Audio playback en inbox y widget
- ✅ Quick replies CRUD
- ✅ Bulk operations backend
- ✅ Close/reopen conversations
- ✅ Business hours config (sin enforcement)
- ✅ Filtros y búsqueda de mensajes
- ✅ Media en historial widget

### Sprint 7 — Seguridad & Estabilidad (completado)
- ✅ Deploy credentials movidos a `.env`
- ✅ Redis connection pool (singleton `get_conversation_store()`)
- ✅ `asyncio.sleep` reemplazado por Redis TTL expire
- ✅ Docker multi-stage build + non-root user + healthcheck
- ✅ Security headers ya existentes

### Sprint 8 — Ventana 24h & Business Hours (completado)
- ✅ Business hours enforcement en widget.py y whatsapp_meta.py
- ✅ `wa_window:{phone}` tracking con TTL 24h
- ✅ Banner de ventana 24h en inbox
- ✅ Status tracking (sent/delivered/read) via webhook Meta
- ✅ Endpoint `/conversations/{sid}/wa-window`

### Sprint 9 — Retargeting & Follow-up Engine (completado)
- ✅ Retargeting config CRUD (`GET/POST /retargeting/config`)
- ✅ Retargeting run trigger (`POST /retargeting/run`)
- ✅ Retargeting stats (`GET /retargeting/stats`)
- ✅ Ciclo de retargeting: escanea leads inactivos, envía HSM por día
- ✅ Secuencias day-based (1, 3, 7, 15, 30)
- ✅ Tracking por phone en Redis `retarget:{phone}`

### Sprint 10 — Inbox Enterprise (completado)
- ✅ Kanban drag & drop con SortableJS
- ✅ Reglas de validación en transiciones Kanban
- ✅ SLA indicators (ok/warn/breach) en cards
- ✅ Bulk operations UI (selección múltiple + etiquetar/asignar/cerrar)
- ✅ Desktop notifications + sonido (Web Audio API)
- ✅ Emoji picker
- ✅ File attachment desde inbox

---

## 5. Roadmap — Lo que falta

### Sprint 11 — Sales Closer MVP (EN PROGRESO)
- [ ] **Agente Sales Closer**: nuevo agente LangGraph que:
  - Evalúa contexto CRM (cursadas, interacciones, último contacto)
  - Decide cuándo y cómo contactar
  - Selecciona plantilla HSM óptima
  - Maneja objeciones de precio (descuentos, planes de pago)
  - Genera link de pago personalizado
  - Detecta señales de compra y cierra
  - Escala a humano solo si es necesario
- [ ] **Auto-scheduling**: el agente programa sus propios follow-ups via retargeting engine
- [ ] **Dashboard de retargeting**: UI para ver campañas activas, tasas de respuesta
- [ ] **Modo nocturno/fin de semana**: agente opera 24/7 usando business hours config

### Sprint 12 — Outbound & Scaling
- [ ] `POST /campaigns/create` — CSV + plantilla HSM + segmentación
- [ ] Scheduler de envío con rate limiting (Meta: 80msg/seg por WABA)
- [ ] Opt-out tracking (cumplimiento)
- [ ] Dashboard de campaña: enviados, entregados, leídos, respondidos
- [ ] Redis con password en compose
- [ ] Tests básicos: router, conversation_store, auth
- [ ] Scoring de leads con features de Zoho + historial
- [ ] Reportes automáticos: daily digest

---

## 6. Resumen Ejecutivo

| Área | Estado | Gap |
|------|--------|-----|
| Seguridad | ✅ Auth + headers + Docker hardened + creds en .env | BAJO |
| Consola agente | ✅ Texto+audio+emoji+HSM+bulk+D&D+SLA+notifs | BAJO |
| Real-time | ✅ SSE + Redis Pub/Sub + status tracking | BAJO |
| Kanban | ✅ D&D + reglas + SLA + filtros | COMPLETADO |
| WhatsApp/Meta | ✅ Texto+botones+audio+HSM+status+ventana24h | BAJO |
| Pagos | ✅ MP + Rebill + monitoreo | BAJO |
| CRM | ✅ Zoho bidireccional + panel inbox | BAJO |
| Retargeting | ✅ Engine backend completo | UI dashboard pendiente |
| Business Hours | ✅ Enforcement en widget + WhatsApp | COMPLETADO |
| Sales Closer IA | 🔴 No existe | **PRÓXIMO SPRINT** |
| Tests | 🔴 No existen | FUTURO |

### Próximo paso
**Sprint 11 — Agente Sales Closer MVP**: el agente LangGraph autónomo que cierra ventas 24/7.

**Lo que ya está listo:** ~85% de la infraestructura. Solo falta el "cerebro" autónomo.
