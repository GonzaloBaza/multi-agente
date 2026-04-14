---
name: Stack y arquitectura del proyecto
description: Visión general del sistema multi-agente (stack, canales, agentes, integraciones)
type: project
originSessionId: afc9a303-de9b-483e-b191-c75bf4d36177
---
**multi-agente** = sistema de atención al cliente para MSK Latam (cursos médicos, venta B2C).

**Stack**: FastAPI + LangGraph + Pinecone (RAG de cursos por país) + Redis (conversación + sesiones + pubsub) + Supabase (auth admin/clientes).

**Agentes LangGraph** (bajo `agents/`):
- `router.py` — supervisor clasificador (gpt-4o-mini), decide intent y mantiene continuidad de flujo
- `sales/` — ReAct con RAG + generación de links MP/Rebill + creación de leads Zoho
- `collections/` — cobranzas, payment status, regeneración de links, gestiones
- `post_sales/` — soporte: LMS, certificados, tickets
- `closer/` — **NUEVO (Sprint 11)**: cierra leads abandonados 24/7 autónomamente

**Canales** (`channels/` + `integrations/`):
- Meta WhatsApp Cloud API (principal, `/webhook/whatsapp`)
- Botmaker (handoff humano, HSM templates)
- Twilio (implementado, no en producción)
- Widget web embebible WordPress (`/widget/chat`)

**Integraciones**: Zoho CRM (leads/contacts/sales orders/cobranzas), MercadoPago + Rebill (pagos + IPN), Slack (alertas handoff), Pinecone (RAG).

**Admin (`widget/*.html`)**: Kanban inbox con SLA/bulk ops, Drawflow visual builder, editor de prompts en Redis, CRUD HSM templates, redis debugger, retargeting engine.

**Estado** (según `AUDITORIA_ENTERPRISE.md`): ~85% enterprise-ready. Sprint 10 (inbox) y 11 (closer) completados. Pendientes: tests automatizados, media en S3/R2 (hoy filesystem), Postgres backup de Redis, job runner real (hoy asyncio).

**Why:** Referencia para no releer todo el repo cada vez. Conocer los 4 agentes y la división de canales acelera cualquier tarea de debugging o feature.

**How to apply:** Cuando Gonzalo mencione "el closer", "cobranzas", "ventas", o "retargeting", ubicar el código en las carpetas correspondientes. Para cambios de LLM/prompts, editar en `/admin/prompts` (Redis) antes que en el código.
