# Diseño — Export CSV + Checkout enviado + Alerta de errores de envío

**Fecha**: 2026-06-26
**Autor**: Gonzalo Baza (+ Claude)
**Estado**: aprobado, pendiente de plan de implementación

## Contexto

Pedido operativo de MSK con 3 features independientes sobre el inbox/consola:

1. Descarga masiva de conversaciones a CSV desde el inbox, reusando los filtros existentes.
2. Marcar/filtrar conversaciones por "URL de checkout enviado" (en el inbox y en reportería).
3. Aviso de errores cuando el bot falla al enviar un mensaje (widget y WhatsApp).

Más un ajuste pedido en el camino: el inbox hoy muestra hasta 500 conversaciones; se quiere ver más vía paginación.

Se implementan como **3 entregas separadas, chicas y verificables** (orden: 1 → 2 → 3), nunca big-bang.

## Decisiones tomadas

- **CSV**: vive en el **Inbox** (la pantalla con filtros ventas/post-venta). Gating **supervisor+** (descarga masiva de datos de contacto, igual que las bulk ops). Respeta el scope por rol existente.
- **Checkout enviado**: detección **por contenido del mensaje** (`messages.content ILIKE '%msklatam.com/checkout%'`), exacta y sin depender del clasificador.
- **Reportería**: como Analytics hoy es **agregada** (no lista conversaciones), se agrega un **KPI "Checkout enviados" + % conversión**. El filtrado fila-por-fila vive en el Inbox (que además exporta CSV).
- **Errores de envío**: alerta a **Slack** reusando `utils/inbox_jobs.slack_notify()`. Sin retry (fuera de alcance).
- **Inbox limit**: **"Cargar más" / scroll infinito** usando el `offset` que el backend ya soporta (no un tope fijo más alto).

## Estado actual del código (hallazgos de exploración)

- `GET /api/v1/inbox/conversations` ([api/inbox_api.py:864](../../../api/inbox_api.py)) acepta `view, lifecycle, channel, queue, country, assigned_to, search, date_from, date_to, limit (Query(50, le=1000)), offset`. Scope por rol vía `_agent_queue_scope_sql`. No existe ningún export CSV hoy.
- Front inbox: `useConversations` ([frontend/lib/api/inbox.ts:231](../../../frontend/lib/api/inbox.ts)) pide `limit ?? 500` en un solo fetch (react-query). La UI no expone rango de fechas (aunque el backend lo soporta).
- `GET /api/v1/inbox/analytics` ([api/inbox_api.py:217](../../../api/inbox_api.py)) sólo filtra por `days`; devuelve agregados (KPIs, SLA, breakdowns por canal/queue/país/lifecycle, heatmap, leaderboard).
- El bot manda el link `https://msklatam.com/checkout/{slug}/?utm_source=bot` como **texto plano** dentro del mensaje del asistente. `messages` guarda el `content` completo (`role`, `content`, `metadata`, `created_at`, `conversation_id`).
- Paths de envío saliente: Botmaker (`channels/whatsapp.py` → `integrations/botmaker.py`), Meta Cloud API (`integrations/whatsapp_meta.py::_post`, loguea + circuit breaker + re-raise). Hoy los fallos se loguean con structlog y se re-lanzan; **no** se ven en UI, **no** van a Slack/Sentry, **no** hay status en `messages`.
- Helper Slack existente: `utils/inbox_jobs.slack_notify(text, blocks)` + `integrations/notifications.notify_slack()` usando `settings.slack_webhook_url` (env `SLACK_WEBHOOK_URL`).

---

## Entrega 1 — Inbox: paginación + filtro de fechas + export CSV

### Backend
- **Export**: nuevo `GET /api/v1/inbox/conversations.csv` que **reusa la misma construcción de filtros + scope por rol** que `list_conversations` (refactor: extraer el armado del WHERE/scope a un helper compartido para no duplicar). Sin paginado; tope duro de seguridad (~50.000 filas) y, si se supera, se trunca con aviso en logs.
  - `StreamingResponse`, `media_type="text/csv"`, `Content-Disposition: attachment; filename="conversaciones_YYYYMMDD.csv"`.
  - UTF-8 **con BOM** (`﻿`) para que Excel respete acentos.
  - Generación con `csv` (stdlib) sobre un generador que streamea filas.
  - Gating: **supervisor+** (`require_role_or_admin("supervisor")` o equivalente).
  - **Columnas**: id, creada, ultima_actividad, canal, nombre, email, telefono, pais, area (Ventas/Cobranzas/Post-venta), lifecycle, estado, asignada_a (nombre del agente), needs_human, bot_paused, mensajes (#), ultimo_mensaje.
- **Paginación**: el endpoint ya soporta `offset`; no requiere cambio backend más allá de confirmar orden estable (`ORDER BY c.updated_at DESC, c.id` para evitar saltos entre páginas).

### Frontend (inbox)
- **Cargar más / scroll infinito**: migrar `useConversations` de `useQuery` a `useInfiniteQuery` (react-query), páginas de 500 vía `offset`. Botón "Cargar más" al pie de la lista (+ opcional IntersectionObserver para auto-cargar al acercarse al fondo). Mantener compatibilidad con el refresh/real-time actual (refetch de páginas ya cargadas).
- **Filtro de fechas**: agregar inputs desde/hasta en la barra de filtros del inbox → mapean a `date_from`/`date_to`.
- **Botón "Descargar CSV"** en la toolbar del inbox (junto a Refrescar, en `frontend/components/inbox/conversation-list.tsx`). Arma los mismos query params del estado de filtros actual y dispara la descarga por navegación directa al endpoint (la cookie de sesión viaja sola). Visible sólo para supervisor+.

### Verificación
- Descargar con varios sets de filtros (ventas vs post-venta, fechas, canal) y confirmar que las filas del CSV coinciden con lo que muestra el inbox.
- "Cargar más" trae la tanda siguiente sin duplicar ni saltear filas.
- Un usuario rol `agente` no ve el botón de export; el endpoint le responde 403 si lo invoca a mano.

---

## Entrega 2 — "Checkout enviado" (filtro + columna + KPI)

### Backend
- Helper SQL compartido `checkout_sent_exists(c.id)`:
  `EXISTS (SELECT 1 FROM public.messages m WHERE m.conversation_id = c.id AND m.role = 'assistant' AND m.content ILIKE '%msklatam.com/checkout%')`.
  Se expone como columna calculada `checkout_sent` (bool).
- `list_conversations` y `conversations.csv`:
  - Nuevo query param `checkout_sent` (`true`/`false`/omitido = todos) → agrega el `EXISTS`/`NOT EXISTS` al WHERE.
  - Agregar `checkout_sent` al `ConversationOut` y al CSV (columna "checkout_enviado" Sí/No).
- `analytics`: agregar al response `checkout_sent_count` (conversaciones con checkout enviado en la ventana `days`) y `checkout_conversion_pct` = (conversaciones con checkout enviado **y** etiqueta de clasificador `convertido`) / (checkout enviados) × 100. Se usa la etiqueta IA `convertido` (Redis `conv_label:{session_id}`, ya leída en batch por el endpoint `/pipeline`) por consistencia con cómo el resto del producto define "convertido".

### Frontend
- **Inbox**: toggle "Checkout enviado" (sí/no/todos) en la barra de filtros + badge en la fila/detalle cuando `checkout_sent` es true.
- **Analytics**: card KPI "Checkout enviados: N" + "% conversión".

### Verificación
- Conversación donde el bot mandó el link → aparece el badge y entra en el filtro "sí"; una sin link no.
- El número del KPI en analytics coincide con el conteo del filtro en el inbox para la misma ventana.

---

## Entrega 3 — Alerta a Slack si el bot falla al enviar

### Backend
- Función central `notify_send_failure(channel, conversation_id, destino, error)` (nuevo, p. ej. en `integrations/notifications.py` o `utils/inbox_jobs.py`) que arma el mensaje Slack: canal, link `https://agentes.msklatam.com/inbox?conv=<id>`, destinatario (teléfono/session), error resumido, hora. Reusa `slack_notify()`.
- **Anti-spam**: throttle con contador Redis (p. ej. máx 1 alerta por `conversation_id` cada 10 min y un tope global N/min) para no inundar Slack ante un fallo masivo.
- **Wire en los paths de salida**, capturando a nivel del handler de canal (donde hay contexto de conversación):
  - Botmaker — `channels/whatsapp.py` (envuelve `botmaker.send_message`).
  - Meta Cloud API — caller de `integrations/whatsapp_meta.py::_post` (o el handler que lo invoca).
  - Widget — el "envío" es in-process: alertar cuando el agente tira excepción y no devuelve respuesta al usuario.
- **Scope del fallo**: envío al canal con error/excepción (non-200, timeout, circuit-breaker abierto). Se mantiene el logging actual. No se agrega retry.

### Acción previa
- Confirmar que `SLACK_WEBHOOK_URL` esté seteado en el `.env` del server. Si no, el helper no-opea sin romper hasta que se cargue.

### Verificación
- Forzar un fallo de envío (p. ej. token/credencial inválida en un entorno de prueba o un mock) y confirmar que llega la alerta a Slack con el link a la conversación.
- El throttle evita más de 1 alerta por conv en la ventana definida.

---

## Fuera de alcance (YAGNI)

- Retry/reenvío automático de mensajes fallidos.
- Status persistente de "mensaje fallido" en la tabla `messages` + vista de fallidos en UI (sólo Slack por ahora).
- Filtrar TODO el dashboard de analytics por checkout-enviado (sólo KPI por ahora).
- Notificación in-app / Sentry para fallos de envío (se eligió sólo Slack).
