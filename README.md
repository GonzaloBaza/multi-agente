# MSK Multi-Agente

Sistema multi-agente de atención al cliente para **MSK Latam** (cursos
médicos online, LATAM). Bot IA con 4 agentes especializados + consola
humana para agentes, supervisores y admins.

**Producción**: [agentes.msklatam.com](https://agentes.msklatam.com)

## Stack

- **Backend**: FastAPI + LangGraph + OpenAI + Pinecone (RAG) + Redis +
  Supabase Postgres.
- **Frontend**: Next.js 15 (App Router) + React 19 + TanStack Query +
  Tailwind.
- **Deploy**: Docker Compose en DigitalOcean, nginx con SSL (Let's Encrypt).
- **Canales**: WhatsApp Meta Cloud API (principal), Botmaker, Twilio,
  widget web embebible.
- **Integraciones**: Zoho CRM, MercadoPago, Rebill, Cloudflare R2 (media),
  Sentry, Slack.

## Estructura

```
multi-agente/
├── main.py                       FastAPI entry point
├── config/                       Pydantic Settings + constantes
├── api/                          Routers FastAPI
│   ├── auth.py                   /api/auth/*     login/users/sessions
│   ├── inbox_api.py              /api/inbox/*    REST del inbox nuevo
│   ├── inbox.py                  helpers internos (broadcast_event, SSE)
│   ├── admin.py                  /api/admin/{status,channels-status}
│   ├── admin_prompts.py          /api/admin/prompts/*
│   ├── admin_courses.py          /api/admin/courses/*
│   ├── widget_config.py          /api/admin/widget-config/*
│   ├── redis_admin.py            /api/admin/redis/*
│   ├── reports.py                /api/admin/reports/*
│   ├── autonomous.py             /api/admin/autonomous/*
│   ├── test_agent.py             /api/admin/test-agent
│   ├── templates.py              /api/templates/*  (HSM)
│   ├── widget.py                 /widget/*       chat embebible público
│   ├── customer_auth.py          /customer/*     LMS externo
│   └── webhooks.py               /webhook/*      Meta, MP, Rebill, Zoho
├── agents/                       Agentes LangGraph
│   ├── router.py                 Clasificador de intent
│   ├── sales/                    RAG + cierre (MP / Rebill)
│   ├── closer/                   Cierre autónomo de leads calientes
│   ├── collections/              Cobranzas (Zoho)
│   ├── post_sales/               Soporte LMS + certificados
│   └── routing/
│       ├── widget_flow.py        Máquina de estados del menú inicial
│       ├── router_prompt.py      System prompt del clasificador
│       └── greeting_prompt.py    Saludo personalizado del widget
├── channels/                     Processors por canal
│   ├── widget.py                 Mensajes entrantes del widget web
│   ├── whatsapp_meta.py          WhatsApp Meta Cloud API (principal)
│   ├── whatsapp.py               Botmaker
│   └── twilio_whatsapp.py        Twilio (sandbox)
├── integrations/                 Clientes externos
│   ├── whatsapp_meta.py          Cliente Meta Cloud API
│   ├── botmaker.py               Cliente Botmaker
│   ├── twilio_whatsapp.py        Cliente Twilio
│   ├── zoho/                     CRM (contacts, leads, cobranzas, SO)
│   ├── payments/                 MercadoPago, Rebill
│   ├── supabase_client.py        Auth + profiles
│   ├── storage.py                Cloudflare R2 (uploads)
│   ├── stt.py                    OpenAI Whisper
│   ├── tts.py                    OpenAI TTS
│   ├── courses_cache.py          Cache cursos (Redis + WP)
│   ├── msk_courses.py            Sync desde WordPress CMS
│   └── notifications.py          Slack alerts
├── memory/                       Persistencia
│   ├── conversation_store.py     Redis (cache 7d)
│   ├── postgres_store.py         Asyncpg pool + CRUD
│   └── conversation_meta.py      CRUD conversation_meta
├── models/                       Pydantic models
├── utils/                        Helpers (scheduler, audit, circuit
│                                 breaker, SSE events, inbox cron)
├── frontend/                     Next.js 15 console
│   └── (ver frontend/README.md)
├── widget/
│   └── static/
│       ├── chat.js               Widget embebible (msklatam.com/tech)
│       └── chat.css
├── migrations/                   SQL (002-006 aplicadas)
├── scripts/                      Tooling interno (backfills, debug)
├── tests/                        Pytest (smoke + unit)
├── deploy/
│   └── nginx-agentes.msklatam.com.conf
├── Dockerfile                    Backend multi-stage
├── frontend/Dockerfile           Frontend standalone
├── docker-compose.yml
└── CLAUDE.md                     Contexto operativo (agentes, DB, deploy)
```

## Setup local

### Variables de entorno

```bash
cp .env.example .env
# Editar con tus credenciales
```

Críticas para arrancar: `OPENAI_API_KEY`, `DATABASE_URL`, `REDIS_URL`,
`REDIS_PASSWORD`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `APP_SECRET_KEY`.

### Con Docker

```bash
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000 (si tenés Next.js en el compose)

### Sin Docker

Backend:
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

## Deploy producción

```bash
# local
git add . && git commit -m "..." && git push

# server
plink -batch -pw 'MSK!@L4t4m' root@68.183.156.122
cd /opt/multiagente && git pull
docker compose up -d --build api ui
```

Ver [CLAUDE.md](./CLAUDE.md) para detalle de nginx, migraciones DB, agentes
IA y convenciones internas.

## Widget embebible

Pegar en sitios externos (`msklatam.com`, `msklatam.tech`):

```html
<script
  src="https://agentes.msklatam.com/widget.js"
  data-country="AR"
  data-title="Asesor de Cursos"
  data-color="#1a73e8"
  defer
></script>
```

Config avanzada (avatar, saludo, posición, quick replies): editar desde la
consola en **Canales → Apariencia del widget** (admin-only).

## Endpoints

Ver [CLAUDE.md](./CLAUDE.md) § "Convenciones de routing".

## Tests

```bash
cd tests && pytest -v
```

Smoke tests de imports + unit tests de `_agent_queue_scope_sql`,
`CircuitBreaker`, health endpoint. No hay integration tests — las
dependencias externas (Pinecone, Zoho, OpenAI, WhatsApp) son costosas de
mockear.

## Licencia

Propietario — MSK Latam. No distribuir.
