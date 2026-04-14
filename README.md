# Multi-Agente — Cursos Médicos

Sistema multi-agente de atención al cliente para empresa de cursos médicos.
**Stack:** LangGraph + FastAPI + Pinecone + Redis  
**Canales:** WhatsApp (Botmaker) + Widget web embebible (WordPress)  
**CRM:** Zoho (Leads, Contacts, Sales Orders, Cobranzas)

---

## Arquitectura

```
                    ┌─────────────────────────────────────────┐
  WhatsApp          │           FastAPI Backend                │
  (Botmaker) ──────▶│  /webhook/botmaker                      │
                    │          │                               │
  Widget Web ───────│  /widget/chat                           │
  (WordPress)       │          │                               │
                    │          ▼                               │
                    │   ┌─────────────┐                        │
                    │   │  Supervisor │  (LangGraph)           │
                    │   │  Clasificador│                        │
                    │   └──────┬──────┘                        │
                    │     ┌────┴────┬──────────┐               │
                    │     ▼         ▼           ▼               │
                    │  Ventas   Cobranzas  Post-Venta           │
                    │  (RAG)    (Zoho)     (Zoho)               │
                    │     │         │           │               │
                    │     └────┬────┴───────────┘               │
                    │          ▼                               │
                    │   ┌─────────────┐  ┌──────────────┐     │
                    │   │   Pinecone  │  │    Redis      │     │
                    │   │  (cursos)   │  │  (historial)  │     │
                    │   └─────────────┘  └──────────────┘     │
                    └─────────────────────────────────────────┘
                              │ Integraciones
                    ┌─────────┴─────────────────────┐
                    │  Zoho CRM  │  MercadoPago      │
                    │  Rebill    │  Slack (alertas)  │
                    └───────────────────────────────┘
```

## Estructura de carpetas

```
multi-agente/
├── main.py                     # FastAPI entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── railway.toml                # Deploy en Railway
├── .env.example
├── config/
│   ├── settings.py             # Pydantic Settings (env vars)
│   └── constants.py            # Enums, constantes
├── agents/
│   ├── router.py               # Supervisor LangGraph (clasificador de intent)
│   ├── sales/                  # Agente ventas — RAG + cierre + Zoho
│   ├── collections/            # Agente cobranzas
│   └── post_sales/             # Agente post-venta
├── rag/
│   ├── indexer.py              # Vectoriza cursos → Pinecone
│   ├── retriever.py            # Búsqueda semántica
│   └── data/
│       ├── courses_ar.json     # Cursos Argentina
│       ├── courses_mx.json     # Cursos México
│       └── courses_*.json      # Otros países
├── integrations/
│   ├── botmaker.py             # Envío mensajes + handoff WhatsApp
│   ├── notifications.py        # Slack + email
│   ├── zoho/                   # Auth, Leads, Contacts, Sales Orders, Cobranzas
│   └── payments/               # MercadoPago + Rebill
├── channels/
│   ├── whatsapp.py             # Procesador mensajes WhatsApp
│   └── widget.py               # Procesador mensajes widget
├── api/
│   ├── webhooks.py             # /webhook/botmaker, /webhook/mercadopago, /webhook/rebill
│   ├── widget.py               # /widget/chat, /widget/chat/stream, /widget/history
│   └── admin.py                # /admin/reindex, /admin/status
├── memory/
│   └── conversation_store.py   # Redis — historial de conversaciones
├── models/
│   ├── conversation.py         # Conversation, ConversationState
│   ├── message.py              # Message, MessageRole
│   └── course.py               # Course, CourseSearchResult
├── widget/
│   ├── static/
│   │   ├── chat.js             # Widget JS embebible
│   │   └── chat.css            # Estilos del widget
│   └── wordpress_embed.html    # Snippet para pegar en WordPress
└── scripts/
    ├── index_courses.py        # Indexar cursos en Pinecone
    └── seed_test_data.py       # Limpiar datos de test
```

---

## Setup inicial

### 1. Variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

Variables obligatorias para funcionar:
```
OPENAI_API_KEY
PINECONE_API_KEY
PINECONE_INDEX_NAME
REDIS_URL
ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET / ZOHO_REFRESH_TOKEN
BOTMAKER_API_KEY
MP_ACCESS_TOKEN   (o REBILL_API_KEY)
```

### 2. Desarrollo local con Docker

```bash
docker-compose up
```

La API corre en `http://localhost:8000`

### 3. Sin Docker

```bash
pip install -r requirements.txt
# Asegurate de tener Redis corriendo: redis-server
uvicorn main:app --reload
```

---

## Indexar cursos en Pinecone

Primero indexar antes de que el agente de ventas pueda responder:

```bash
# Todos los países
python scripts/index_courses.py

# Solo Argentina
python scripts/index_courses.py --country AR

# Archivo específico
python scripts/index_courses.py --file mi_catalogo.json --country MX
```

**Formato del JSON de cursos** (ver `rag/data/courses_ar.json`):
```json
[
  {
    "id": "ar-001",
    "nombre": "Nombre del curso",
    "descripcion": "Descripción detallada...",
    "categoria": "Cardiología",
    "duracion_horas": 80,
    "modalidad": "online",
    "precio": 85000,
    "moneda": "ARS",
    "pais": "AR",
    "tiene_certificado": true,
    "tipo_certificado": "Aval SAC",
    "docentes": ["Dr. Juan Pérez"],
    "fecha_inicio": "2026-05-05",
    "cuotas_disponibles": 6,
    "precio_cuota": 14167,
    "rebill_plan_id": "plan_ar_001",
    "lms_course_id": "101",
    "lms_platform": "moodle",
    "tags": ["cardiología", "ECG"]
  }
]
```

---

## Configurar Botmaker

En la consola de Botmaker, configurar el webhook saliente:
```
URL: https://TU_DOMINIO/webhook/botmaker
Method: POST
Trigger: Cuando el usuario escribe un mensaje
```

---

## Embed en WordPress

Pegá en `footer.php` (antes de `</body>`) o con un plugin de header/footer:

```html
<script
  src="https://TU_DOMINIO/widget.js"
  data-country="AR"
  data-title="Asesor de Cursos"
  data-color="#1a73e8"
  defer
></script>
```

Ver más opciones en `widget/wordpress_embed.html`.

---

## Deploy en Railway

```bash
# Instalar Railway CLI
npm install -g @railway/cli

railway login
railway init
railway up
```

Configurar en Railway:
1. Agregar servicio **Redis** (desde Railway plugins)
2. Variables de entorno en el dashboard
3. El `railway.toml` ya configura el health check y restart policy

---

## Endpoints principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/webhook/botmaker` | Mensajes entrantes de WhatsApp |
| POST | `/webhook/mercadopago` | IPN de MercadoPago |
| POST | `/webhook/rebill` | Eventos de Rebill |
| POST | `/widget/chat` | Chat del widget web |
| GET  | `/widget/chat/stream` | Chat con SSE streaming |
| GET  | `/widget/history/{id}` | Historial de sesión |
| POST | `/admin/reindex` | Re-indexar cursos (requiere X-Admin-Key) |
| GET  | `/admin/status` | Estado del sistema |
| GET  | `/health` | Health check |
| GET  | `/docs` | Swagger (solo en dev) |

---

## Agentes

### Agente de Ventas
- Busca cursos por semántica (RAG sobre Pinecone por país)
- Responde dudas de precio, certificado, modalidad, docentes
- Genera links de pago (MercadoPago pago único / Rebill cuotas)
- Crea Lead y Sales Order en Zoho

### Agente de Cobranzas
- Consulta estado de pagos del alumno en Zoho
- Envía recordatorios y registra gestiones
- Regenera links de pago vencidos
- Ofrece planes de regularización
- Escala disputas → handoff humano

### Agente de Post-Venta
- Verifica inscripción y estado del alumno en Zoho
- Gestiona problemas de acceso al campus
- Procesa solicitudes de certificados
- Registra tickets de soporte técnico
- Toma encuestas NPS y registra en Zoho

### Supervisor / Router
- Clasifica el intent con GPT-4o-mini (económico, rápido)
- Detecta keywords de handoff para transferencia inmediata
- Transfiere la conversación tanto en Botmaker como notifica a Slack
