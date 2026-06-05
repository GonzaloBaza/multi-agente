# Roadmap "Level Dios" — Bot de Ventas MSK

Ideas de mejora del agente de ventas, ordenadas por impacto en conversión.
Tipo: **[prompt]** = se hace en `prompts_v2.py` · **[infra]** = requiere backend/scheduler/integración.

## 🥇 Mayor impacto en plata
1. **Follow-up proactivo automático** [infra] — cadencias: nudge si recibió link y no pagó (3h/24h), re-engage al lead frío (3d). El mayor agujero de conversión hoy (el bot es 100% reactivo). Usar el scheduler existente.
2. **Memoria entre sesiones** [infra] — retomar con contexto del historial Zoho del lead (cursos previos, pagos, área) en vez de stateless 3 días.
3. **Framing / anclaje de precio** [prompt] — "menos que un café por día", "el costo de una consulta", costo diario de la cuota. El número crudo intimida.
4. **Respuestas en audio (TTS)** [infra] — si el lead manda audio, responder en audio (el stack tiene TTS). 3× cercanía en WhatsApp LATAM.

## 🥈 Más humano, menos robot
5. **Handoff inteligente** [infra+prompt] — lead premium/frustrado/trabado tras 3 intentos → pasar a humano con resumen de contexto. Saber cuándo NO ser bot.
6. **Biblioteca de objeciones avanzadas** [prompt] — "ya hice uno parecido", "lo apruebo con el jefe", "después del examen", "mi colega lo hizo y no le sirvió".
7. **Urgencia + prueba social REAL** [prompt] — cupos, vencimiento de promo, cohorte que arranca, "X colegas de tu provincia se anotaron". Solo con datos verdaderos.

## 🥉 Meta-juego
8. **Loop de auto-mejora medido contra ventas reales** [infra] — medir qué aperturas/cierres/timing de cupón convierten (cruzar con deals Zoho) y ajustar con datos. El v1-vs-v2 es el embrión.
9. **Cross-sell / bundles** [prompt] — combos (cardio + urgencias con descuento). Sube ticket promedio.

**Orden sugerido:** 1 → 3 → 4 → 2 → 5. Las 3, 6, 7, 9 son prompt (rápidas); 1, 2, 4, 8 son infra.
