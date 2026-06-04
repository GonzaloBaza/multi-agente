# Diseño — Agente de Ventas v2 (prompt podado + modelo configurable)

Fecha: 2026-06-04
Autor: Gonzalo Baza + Claude
Estado: aprobado para implementar

## Problema

El agente de ventas en producción (`agents/sales`, vía `api/sales_whatsapp.py`)
no respeta reglas que SÍ están en el prompt. Casos reales observados (4-jun-2026):

- COLMED III se lista como certificación **jurisdiccional** cuando el prompt dice
  que es **NACIONAL** ([prompts.py:1068](../../../agents/sales/prompts.py)).
- No hace *probe* de especialidad/dolor cuando el user da solo profesión — pitchea directo.
- No retruca objeciones de precio ("ahora no").
- No adapta al perfil (ofreció curso de médicos a un estudiante de paramédico).
- Mensajes largos y genéricos, CTA repetida.

**Causa raíz:** el system prompt pesa ~118 KB (~30k tokens) y `agent.py` le inyecta
catálogo + brief + headers encima. Con gpt-4o, el modelo descarta reglas enterradas.
Las reglas correctas YA existen; el problema es cumplimiento.

## Objetivo

Construir un **agente de ventas v2 en paralelo**, aislado de producción, para testear:
1. Un **prompt podado** (lossless: cero reglas perdidas, solo se comprime).
2. Un **modelo mejor** de instruction-following (gpt-4.1 ahora; Claude paso 2).

Sin tocar el flujo v1 que está vendiendo hoy.

## Decisiones (de la fase de brainstorming)

| Tema | Decisión |
|---|---|
| Aislamiento | Endpoint nuevo dedicado `/api/v1/sales/whatsapp/webhook-v2` |
| Modelo | `SALES_V2_MODEL` env, default `gpt-4.1`. Claude = paso 2 |
| Podado | Lossless (no se cae ninguna regla) + inventario de reglas como red de seguridad |
| Zoho en tests | Escribe igual que prod pero **marcado como TEST** (filtrable/borrable) |
| Estructura | Enfoque C (híbrido): nuevo prompt+agente+endpoint, reusa infra v1 importándola |
| Reúso | Orquestación *thin* en v2 → **prod intacto** (cero ediciones a v1) |

## Arquitectura

**Archivos nuevos:**
- `agents/sales/prompts_v2.py` → `build_sales_prompt_v2(...)` — prompt podado.
- `agents/sales/agent_v2.py` → `build_sales_agent_v2(...)` — usa prompt_v2 + modelo env.
- `api/sales_whatsapp_v2.py` → router `/api/v1/sales/whatsapp/webhook-v2`.
- `docs/sales_v2/rules_inventory.md` → inventario de reglas + mapeo de cobertura.

**Se importa de v1 (sin editar):**
- `api/sales_whatsapp.py`: `_bucket_*`, `_debounce_wait`, `_ensure_lead_id`,
  `_ctwa_backfill_contact`, `_build_user_profile`, `_country_from_phone`, dedup.
- `agents/sales/agent.py`: priority header, `_format_course_context`, catálogo, master warning.
- `agents/sales/tools.py`: `SALES_TOOLS`.
- `ZohoLeads`, `channel_configs`.

**Lógica nueva:** una orquestación *thin* `_process_message_and_respond_v2` (~40-60 líneas)
que secuencia los helpers importados pero llama `build_sales_agent_v2` y aplica el
marcador TEST en Zoho. El endpoint v1 (`/webhook`) NO se edita.

**Registro:** router v2 agregado en `main.py` (1 línea).

## Podado lossless (3 pasos)

1. **Inventario** (`docs/sales_v2/rules_inventory.md`): extraer cada regla distinta de
   `prompts.py` + fragmentos de `agent.py` a un checklist con ID (R-001, R-002, ...).
2. **Escribir `prompts_v2.py`**: cubrir TODOS los IDs, comprimiendo — deduplicar reglas
   repetidas, consolidar ejemplos (5→1-2), prosa→bullets imperativos, reglas críticas
   arriba. Misma parametrización (country/channel/campaign/CTWA) y mismas inyecciones
   dinámicas (importadas de `agent.py`). Solo se poda el cuerpo estático.
3. **Validar cobertura**: cada ID mapeado a su sección en v2. Checklist 100% = lossless.

Meta de tamaño: ~8-12 KB (de 118 KB) sin perder reglas.

**Fuera de alcance (YAGNI):** certs determinísticas (opción #2) — follow-up. En v2 las
reglas de certs siguen en el prompt podado.

## Modelo

`build_sales_agent_v2` lee `SALES_V2_MODEL` (default `gpt-4.1`). OpenAI tiene prompt
caching automático (~50% en el prefijo). Claude (paso 2) requiere `langchain-anthropic`
+ `ANTHROPIC_API_KEY` + cache manual (~90%).

## Zoho en modo TEST

Los leads creados/actualizados por v2 se marcan como test para filtrar y borrar:
- `Description` con prefijo `[QA-V2]`.
- `Ad_Account` / marcador reconocible (definir en impl).
El back-fill de contacto (importado de v1) funciona igual.

## Testing y comparación v1 vs v2

- Reusar el harness existente (script Python → endpoint + fetch a Zoho), parametrizado
  por endpoint (`/webhook` vs `/webhook-v2`).
- Correr las mismas N conversaciones CTWA contra ambos.
- **Scorecard** mapeado al inventario: COLMED3 nacional, probe de especialidad, manejo de
  objeción, adaptación por perfil, largo/genericidad de mensajes.
- Output: transcripts lado a lado + checklist de cumplimiento de reglas v1 vs v2.

## Error handling

- v2 hereda el manejo de errores de los helpers importados (try/except, fallbacks).
- Si `build_sales_agent_v2` o el modelo fallan → respuesta de fallback, log de warning.
- Marcador TEST garantiza que ningún lead de prueba se confunda con uno real.

## Criterio de éxito

v2 cumple las reglas que v1 viola (verificado con el scorecard sobre el harness),
manteniendo latencia aceptable para WhatsApp realtime, sin impacto en producción v1.
