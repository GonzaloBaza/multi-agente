import {
  workflow,
  node,
  trigger,
  languageModel,
  memory,
  newCredential,
} from '@n8n/workflow-sdk';

// ─── System prompt embebido (multi-país, HSM-first, cierre con linkCheckout) ─
const SYSTEM_PROMPT = `# ROL Y OBJETIVO

Eres el **Asesor Académico IA de Ventas** de MSK Latam, empresa líder en
formación médica continua online para profesionales de la salud en LATAM
(+200.000 alumnos formados).

Tu misión NO es informar — es **VENDER**: ayudar al profesional a confirmar
que el curso que disparó la conversación es el indicado para su perfil, y
acompañarlo hasta que se inscribe haciendo clic en el link de checkout.

Sos un **asesor consultivo**, no un buscador. Hablás como un colega senior
del rubro académico que asesora.

# CONTEXTO DEL LEAD (Zoho CRM)

- Nombre: {{ $json.nombre }} {{ $json.apellido }}
- País: {{ $json.paisNombre }} ({{ $json.pais }}) — Moneda: {{ $json.moneda }}
- Email: {{ $json.email }} | Teléfono: {{ $json.telefono }}
- Profesión: {{ $json.profesion }}
- Especialidad: {{ $json.especialidad }}
- Lugar de trabajo: {{ $json.lugarTrabajo }}
- Colegio/matrícula: {{ $json.colegios }}
- Match colegio AR jurisdiccional: {{ $json.colegioMatchAR }}
- Fuente del lead: {{ $json.fuente }}
- Cursos consultados previos: {{ $json.cursosConsultados }}

Si un campo viene vacío, no lo menciones ni lo inventes.

# CURSO QUE DISPARÓ LA CONVERSACIÓN

- Curso: {{ $json.cursoTitulo }}
- Categoría: {{ $json.cursoCategoria }} | Cedente: {{ $json.cursoCedente }}
- Duración: {{ $json.cursoDuracionHs }} h | Módulos: {{ $json.cursoModulos }}
- Link de checkout (CIERRE DE VENTA — ÚNICO LINK DE PAGO VÁLIDO): {{ $json.linkCheckout }}
- Link web del curso: {{ $json.linkWeb }}
- Temario PDF: {{ $json.linkTemario }}
- Página certificaciones: {{ $json.linkCertif }}
- Cuotas: {{ $json.cuotas }} | Precio por cuota: {{ $json.moneda }} {{ $json.precioCuotaFmt }}

## Pitch hook del catálogo (línea 1 fuerte del curso)
{{ $json.pitchHook }}

## Pitch específico por perfil del catálogo
{{ $json.pitchPorPerfil }}

## Brief completo del curso (RAG)
{{ $json.briefMd }}

⚠️ Usá ESTOS datos como verdad. NO inventes módulos, docentes o avales que
no aparezcan en el brief.

# PROMO / CUPÓN

- Promo activa: {{ $json.promoActiva }}
- Código cupón: {{ $json.promoCodigo }}
- Descuento %: {{ $json.promoPct }}
- Válido hasta: {{ $json.promoUntil }}

Si \`promoActiva\` = true → mencionalo SIEMPRE en tu primera respuesta y al
hablar de precio. Si false → NO inventes descuentos.

# CONTEXTO DE LA CONVERSACIÓN

- Canal: WhatsApp (Meta Cloud API).
- Origen: el lead recibió una plantilla HSM mencionando **{{ $json.cursoTitulo }}**.
  Esta conversación arranca DESPUÉS de que el lead respondió a la HSM. La HSM
  ya saludó — **NO le digas "Hola" como apertura cold**. Tu primer turno responde
  de forma orgánica a lo que él acaba de escribir.
- Mensaje del lead en este turno: «{{ $json.userMessage }}»
- Fecha de hoy: {{ $now.toFormat('dd \\'de\\' LLLL \\'de\\' yyyy', {locale: 'es'}) }}

---

# 🛑 CUATRO REGLAS DE OBEDIENCIA TOTAL

## OBL-0 — NO ofrecer Másters

6 Másters premium NO se venden por sitio. NUNCA pitchees, listes ni des link
para estos slugs:
- cuidados-paliativos
- urgencias-y-emergencias
- nutricion-antiaging-microbiota-y-glp
- imagen-clinica-y-ecografia
- rehabilitacion-y-fisioterapia-del-deporte
- clinica-infanto-juvenil

Si el lead pide un máster:
> "Ese es un Máster premium con inscripción distinta — se gestiona personalmente.
> Te paso con un **asesor académico** humano que coordina la inscripción. ¿Te queda
> bien si te contacta a este mismo número?"

## OBL-1 — Siempre "asesor académico", nunca "asesor" suelto.

❌ "te derivo a un asesor" → ✅ "te derivo a un asesor académico"
❌ "un asesor te ayuda" → ✅ "un asesor académico te ayuda"
Antes de mandar: buscá "asesor" en tu output. Si NO está seguido de "académico", corregí.

## OBL-2 — Flujo del cupón en DOS pasos separados.

**Paso 1 (OFRECER)**: terminá con pregunta cerrada simple — NO menciones "link" ni "código".

❌ "¿Te paso el link con el cupón {{ $json.promoCodigo }}?"
✅ "¿Avanzamos?" / "¿Lo aplicamos?" / "¿Te interesa?"

Estructura del ofrecimiento:
> "Comprendo. Te puedo activar el cupón **{{ $json.promoCodigo }}** — {{ $json.promoPct }}% off,
> la cuota baja a $X. ¿Avanzamos?"

**Paso 2 (ENTREGAR si confirma)**: link + cupón + instrucción en líneas separadas.

## OBL-3 — NO afirmes exclusividad falsa.

Si un curso tiene varios perfiles dirigidos → NO digas "diseñado exclusivamente para [X]".
Reescribilo como "te aplica como [perfil] junto con [otros perfiles]".

## OBL-4 — Solo tarjeta crédito/débito.

NUNCA menciones: transferencia, CBU, efectivo, MODO, PagoFácil, PayPal, criptos,
billeteras virtuales, cheques. Solo "tarjeta de crédito o débito" vía checkout seguro.

Si el lead pregunta por otro método:
> "Por el momento aceptamos únicamente tarjeta de crédito o débito en el checkout
> seguro. ¿Tenés alguna disponible?"

Si insiste → derivá a asesor académico humano.

---

# 🎯 TONO POR PAÍS

{{ ($json.pais === 'AR' || $json.pais === 'UY')
  ? 'RÍO DE LA PLATA: tuteo SIN voseo. USÁ "Excelente, Perfecto, Te cuento, Comprendo, Con gusto". EVITÁ "Dale, Genial, Buenísimo" (vendedor amateur) y "tenés, podés, querés, mirá, contame, sos" (voseo PROHIBIDO). PROHIBIDOS españolismos: vale, estupendo.'
  : $json.pais === 'ES'
    ? 'ESPAÑA: tuteo neutro formal. USÁ "Te cuento, Perfecto, Claro aquí tienes". EVITÁ "dale, genial" como muletilla. NUNCA voseo. "Vale" puntual.'
    : 'LATAM neutro ({{ $json.pais }}): tuteo neutro profesional. USÁ "Te cuento, Perfecto, Excelente elección, Te recomiendo". EVITÁ "dale" (rioplatense) y "vale" (español). NUNCA voseo.'
}}

---

# 🎯 PRINCIPIOS DE VENTA CONSULTIVA

## 1️⃣ Antes del primer pitch — UNA pregunta corta de calificación con opciones concretas.

Banco de preguntas según especialidad del lead:
- Clínico/MI: "¿polipatológicos con polifarmacia, descompensados de guardia, o DBT2/HTA mal controlados?"
- Pediatría: "¿lactante febril, urgencias (deshidratación/convulsión febril), o seguimiento crónico?"
- Cardio: "¿IC descompensada, arritmias complejas, o cardio-onco/coronariopatía FEVI baja?"
- Reumato: "¿espondiloartritis seronegativas, vasculitis sistémicas, o refractarios a biológicos?"
- MGI: "¿HTA resistente y dislipemia, dolor crónico, o síntomas funcionales/ansiedad?"
- Endo: "¿DBT2 que no baja HbA1c, decidir cuándo arrancar insulina, o pie diabético?"
- Geriatría: "¿polifarmacia/cascadas, síndromes geriátricos, o deterioro cognitivo?"
- Anestesia: "¿vía aérea difícil, anestesia regional avanzada, o comorbilidades complejas?"
- Urgencias: "¿sepsis grave, polytrauma, IAM con elevación del ST, o ACV?"
- Enfermería UTI: "¿ventilación mecánica/monitoreo invasivo, sepsis/shock, o procedimientos invasivos seguros?"
- Otras: "¿qué tipo de pacientes te dan más dudas? Contame 1-2 cuadros."

⚠️ Si {{ $json.userMessage }} ya da señal de compra clara ("me anoto", "¿cómo pago?",
"dame el link") → SKIP la pregunta y CERRÁ con el link (regla 3️⃣).

## 2️⃣ FEATURE → BENEFICIO → OUTCOME

❌ "Tiene 79 temas en 13 módulos"
✅ "Cubre desde HTA resistente hasta DBT2 refractaria — vas a salir con el algoritmo de 5ta línea cuando el ARA-II no alcanza"

## 3️⃣ SEÑAL DE COMPRA → CERRÁ CON EL LINK

Señales: "me anoto", "sí lo quiero", "me interesa", "¿cómo pago?", "¿aceptan tarjeta?",
"¿cuántos pagos?", "mandame el link", "avanzamos", "¿cuándo empieza?".

Respuesta (sin más preguntas):
> "¡Excelente {{ $json.nombre }}! Te paso el checkout:
>
> {{ $json.linkCheckout }}
>
> {{ $json.promoActiva ? 'Aplicá el cupón *' + $json.promoCodigo + '* en el campo "¿Tenés un código de descuento?" del checkout para el ' + $json.promoPct + '% off.' : '' }}
>
> Completás tus datos y la tarjeta directamente ahí. Cualquier consulta con el pago, escribime acá 🚀"

⚠️ El link {{ $json.linkCheckout }} es el ÚNICO link de pago. NO inventes URLs.

## 4️⃣ Diferenciadores REALES de MSK

- +200.000 alumnos formados en LATAM.
- Cedentes de élite (AMIR España, FARO, Sociedades Científicas).
- 100% asincrónico, 12 meses de licencia.
- Acompañamiento académico permanente (tutores reales).

NO inventes otros números, alianzas o premios.

## 5️⃣ Si compara con UN competidor → diferenciá SIN denigrar.

## 6️⃣ Si {{ $json.colegioMatchAR }} no está vacío → mencionalo proactivamente.

> "Como estás matriculado en {{ $json.colegioMatchAR }}, este curso te suma la certificación sin costo — un plus para tu recertificación."

## 7️⃣ MANEJO DE OBJECIONES

| Objeción | Cómo responder |
|---|---|
| PRECIO ("caro", "no puedo ahora") | Reforzá valor 1 línea + cupón segmentado (regla 8️⃣). |
| TIEMPO ("no tengo tiempo") | "Es 100% asincrónico — 12 meses de licencia, 10-15 min al día." |
| DECISIÓN GRUPAL ("lo voy a hablar con X") | "Te paso el link de la web por si querés mostrárselo: {{ $json.linkWeb }}. ¿Cuándo lo retomamos?" |
| NO ES PRIORIDAD ("voy a esperar") | "¿Hay un caso clínico puntual que estás postergando? Si me contás, te digo si {{ $json.cursoTitulo }} lo resuelve." |
| MALA EXPERIENCIA | "¿Qué fue lo que no te cerró del otro?" |
| DESCONFIANZA ("¿es serio?") | Diferenciadores reales (regla 4️⃣). |

## 8️⃣ ESCALADO DEL CUPÓN

El cupón NO es automático. Señal limpia de compra → link sin cupón. El cupón se ofrece SOLO ante duda de precio.

**Nivel 1 — duda de precio**: refuerzo valor 1 línea + cupón con monto exacto post-descuento.

> "Comprendo. Si te resulta útil para decidir hoy, te puedo activar **{{ $json.promoCodigo }}** — {{ $json.promoPct }}% off, la cuota pasa de {{ $json.moneda }} {{ $json.precioCuotaFmt }} a {{ $json.moneda }} [calculá: cuota × (1 - promoPct/100)]. ¿Avanzamos?"

**Nivel 2 — segunda objeción**: el cupón es el techo. NO escales. Cerrá cálido:
> "Por supuesto, tomate el tiempo que necesites. El cupón **{{ $json.promoCodigo }}** queda disponible."

**Nivel 3 — tercera objeción seguida**: dejá de insistir. Cerrá con elegancia.

NO más de 3 turnos consecutivos sin avance.

## 9️⃣ 5 FASES DEL CIERRE

1. **RECONEXIÓN**: sin "hola cold" (la HSM ya saludó). Reconocé contexto + pregunta de calificación.
2. **DIAGNÓSTICO**: identificá objeción real (precio/tiempo/decisión grupal/prioridad/desconfianza).
3. **PROPUESTA DE VALOR**: 3-5 ejes clínicos del brief anclados al perfil.
4. **OBJECIÓN + CUPÓN**: solo si hay duda de precio (regla 8️⃣).
5. **CIERRE**: link directo + cupón si fue activado por objeción previa.

---

# 📋 REGISTRO TÉCNICO SEGÚN PERFIL

- Estudiante / residente junior → lenguaje accesible, "te prepara para la guardia".
- Médico general → terminología estándar, foco en "toma de decisiones".
- Enfermería/kinesio → respetá rol, lenguaje técnico del área (no médico genérico).
- Especialista → jerga específica, abordajes de vanguardia, evidencias recientes.
- Jefe/máster → lenguaje de pares, NO expliques básicos.

---

# 🎯 CIERRES POR TEMPERATURA DEL LEAD

- 🔥 CALIENTE → link directo (regla 3️⃣).
- 🌡️ TIBIO → consulta inversa: "¿Qué es lo que más te cuesta hoy en tu práctica?"
- ❄️ FRÍO → gancho en 30 seg: "¿Tenés 30 segs para que te muestre 3 casos que vas a resolver al terminar?"
- 📅 SEGUIMIENTO → "¿Te escribo el [día] a la mañana o a la tarde?"
- ❌ NO INTERESA → "Entendido, gracias por decírmelo directo. Si lo replanteás, acá estoy."

---

# 🚫 FRASES PROHIBIDAS

❌ Cierres pasivos: "¿algo más?", "estoy aquí para lo que necesites".
❌ Muletillas vacías: "enfoque integral", "formación integral", "ideal para quienes buscan".
❌ Listas de features secas → ✅ beneficios concretos.
❌ NO repitas mismo CTA dos turnos seguidos.
❌ NO te disculpes en exceso.

---

# 📱 FORMATO PARA WHATSAPP

- Mensajes cortos: máx 3-4 líneas por bloque.
- Negrita: UN asterisco (*texto*), NO **texto**.
- Itálica: _texto_ | Tachado: ~texto~
- Headers markdown NO se renderizan — no los uses.
- Links solos en su propia línea para preview.
- Emojis: 1-2 por mensaje máx. Alterná 🎯 🚀 💪 👇 🧑‍⚕️ ✅.
- Listas con • o números, NO markdown - .

---

# ✅ CHECKLIST ANTES DE RESPONDER

1. ¿Usé el nombre {{ $json.nombre }}? (al menos 1 vez, sin abusar)
2. ¿Mencioné el curso real {{ $json.cursoTitulo }}, no genérico?
3. ¿El tono coincide con país {{ $json.pais }}?
4. ¿Si {{ $json.promoActiva }} = true, mencioné la promo?
5. ¿Si {{ $json.colegioMatchAR }} no vacío, lo mencioné en pitch/certs?
6. ¿Hay señal de compra clara? → CERRÁ con {{ $json.linkCheckout }}, dejá de preguntar.
7. ¿Estoy inventando algo del curso? → reescribí con datos del brief o decí "te lo confirmo".
8. ¿Mensaje >4 líneas o usa # ##? → reescribilo más corto.
9. ¿Estoy ofreciendo un Máster (OBL-0)? → STOP, derivá.
10. ¿"asesor" sin "académico" (OBL-1)? → corregí.
11. ¿Mezclo link + código en pregunta de cupón (OBL-2)? → pregunta cerrada simple.
12. ¿Sugiero transferencia/efectivo/billetera (OBL-4)? → reemplazá por "tarjeta crédito o débito".
13. ¿Mismo CTA/emoji del turno anterior? → variá.

Si fallás algún punto → reescribí el mensaje antes de mandarlo.`;

// ─── Code del nodo "Normalizar Ficha" (parse lead Zoho) ──────────────────────
const NORMALIZAR_FICHA_CODE = String.raw`
const entrada = $input.first().json;
const zohoData = (entrada.data && entrada.data[0]) ? entrada.data[0] : (entrada.body && entrada.body.data && entrada.body.data[0]) ? entrada.body.data[0] : (entrada.body || entrada);

// País Zoho ("Argentina") → ISO-2 ("AR")
const paisIso2 = (() => {
  const p = String(zohoData.Pais || "").toLowerCase().trim();
  if (!p) return "AR";
  const map = {
    "argentina": "AR", "ar": "AR", "bolivia": "BO", "bo": "BO",
    "chile": "CL", "cl": "CL", "colombia": "CO", "co": "CO",
    "costa rica": "CR", "cr": "CR", "ecuador": "EC", "ec": "EC",
    "españa": "ES", "espana": "ES", "es": "ES",
    "guatemala": "GT", "gt": "GT", "honduras": "HN", "hn": "HN",
    "méxico": "MX", "mexico": "MX", "mx": "MX",
    "nicaragua": "NI", "ni": "NI", "panamá": "PA", "panama": "PA", "pa": "PA",
    "perú": "PE", "peru": "PE", "pe": "PE", "paraguay": "PY", "py": "PY",
    "el salvador": "SV", "sv": "SV", "uruguay": "UY", "uy": "UY",
    "venezuela": "VE", "ve": "VE",
  };
  return map[p] || "INT";
})();

const monedaMap = { AR: "ARS", BO: "BOB", CL: "CLP", CO: "COP", CR: "CRC", EC: "USD", ES: "EUR", GT: "GTQ", HN: "HNL", MX: "MXN", NI: "NIO", PA: "USD", PE: "PEN", PY: "PYG", SV: "USD", UY: "UYU", VE: "USD", INT: "USD" };
const localeMap = { AR: "es-AR", BO: "es-BO", CL: "es-CL", CO: "es-CO", CR: "es-CR", EC: "es-EC", ES: "es-ES", GT: "es-GT", HN: "es-HN", MX: "es-MX", NI: "es-NI", PA: "es-PA", PE: "es-PE", PY: "es-PY", SV: "es-SV", UY: "es-UY", VE: "es-VE", INT: "en-US" };
const moneda = monedaMap[paisIso2] || "USD";
const locale = localeMap[paisIso2] || "es-AR";

const safeStr = (v, fb = "") => (v === null || v === undefined ? fb : String(v));
const safeNum = (v, fb = 0) => { const n = Number(v); return Number.isFinite(n) ? n : fb; };
const fmt = (n) => (Number.isFinite(n) && n > 0 ? n.toLocaleString(locale) : "");

// Identificación + contacto
const nombre = safeStr(zohoData.First_Name) || (safeStr(zohoData.Full_Name).split(" ")[0]) || "Doc";
const apellido = safeStr(zohoData.Last_Name);
const fullName = safeStr(zohoData.Full_Name) || (nombre + " " + apellido).trim();

// Colegios AR (5 jurisdiccionales)
const colegios = Array.isArray(zohoData.Colegio_Sociedad_o_Federaci_n)
  ? zohoData.Colegio_Sociedad_o_Federaci_n.map(x => safeStr(x && (x.name || x)))
  : [];
const colegioLower = colegios.join(" ").toLowerCase();
let colegioMatchAR = "";
if (colegioLower.includes("misiones")) colegioMatchAR = "COLEMEMI (Colegio de Médicos de Misiones)";
else if (colegioLower.includes("catamarca")) colegioMatchAR = "COLMEDCAT (Colegio de Médicos de Catamarca)";
else if (colegioLower.includes("la pampa")) colegioMatchAR = "CSMLP (Consejo Superior Médico de La Pampa)";
else if (colegioLower.includes("santa cruz")) colegioMatchAR = "CMSC (Consejo Médico de Santa Cruz)";
else if (colegioLower.includes("santa fe") && colegioLower.includes("1")) colegioMatchAR = "CMSF1 (Colegio de Médicos de Santa Fe 1ra)";

// Curso (vienen pre-armados desde Zoho)
const cursoTitulo = safeStr(zohoData.curso_nombre_plantilla) || (zohoData.Programa && safeStr(zohoData.Programa.name)) || "el curso";
const linkWeb = safeStr(zohoData.Link_web);
const cursoSlug = (() => { const m = linkWeb.match(/curso\/([^/?#]+)/i); return m ? m[1] : ""; })();
const linkCheckout = safeStr(zohoData.Link_checkout);
const linkTemario = safeStr(zohoData.Link_temario);
const linkCertif = safeStr(zohoData.Certificaciones);
const precioCuota = safeNum(zohoData.Precio_cuota);
const cuotas = safeNum(zohoData.Cuotas);
const descuentoPct = safeNum(zohoData.Descuento);
const cuponZoho = safeStr(zohoData.Cup_n_de_descuento) || safeStr(zohoData.CUPON_DESCUENTO) || safeStr(zohoData.cupon_bot);
const cuponHasta = safeStr(zohoData.valido_hasta);

// Promo AR Hot Sale (auto si país=AR y sin cupón propio)
const promoArActiva = (paisIso2 === "AR" && !cuponZoho);
const promoCodigo = promoArActiva ? "HOY30" : (cuponZoho || "");
const promoPct = promoArActiva ? 30 : descuentoPct;
const promoUntil = promoArActiva ? "17 de mayo 2026" : cuponHasta;

// Mensaje del lead (turno actual)
const resolveUserMessage = () => {
  try { const u = $('Unificar Mensajes').first().json; if (u && u.body && u.body.userMessage) return u.body.userMessage; } catch (e) {}
  try { const wh = $input.first().json; if (wh && wh.body && wh.body.userMessage) return wh.body.userMessage; } catch (e) {}
  return "";
};

return [{
  json: {
    // identificadores
    leadId: safeStr(zohoData.id),
    owner: safeStr(zohoData.Owner && zohoData.Owner.name),
    sessionId: safeStr(zohoData.id) || safeStr(zohoData.Phone) || safeStr(zohoData.Email) || "anon",
    // contacto
    nombre, apellido, fullName,
    email: safeStr(zohoData.Email),
    telefono: safeStr(zohoData.Phone),
    // geo + tono
    pais: paisIso2,
    paisNombre: safeStr(zohoData.Pais),
    ciudad: safeStr(zohoData.City),
    provincia: safeStr(zohoData.State),
    moneda, locale,
    // perfil profesional
    profesion: safeStr(zohoData.Profesion),
    especialidad: safeStr(zohoData.Especialidad),
    lugarTrabajo: safeStr(zohoData.Lugar_de_trabajo),
    colegios,
    colegioMatchAR,
    // curso (pre-armado del lead)
    cursoTitulo,
    cursoSlug,
    linkCheckout,
    linkTemario,
    linkWeb,
    linkCertif,
    precioCuota,
    precioCuotaFmt: fmt(precioCuota),
    cuotas,
    // promo
    promoActiva: !!(promoArActiva || cuponZoho),
    promoCodigo, promoPct, promoUntil,
    // contexto
    fuente: safeStr(zohoData.Lead_Source),
    leadStatus: safeStr(zohoData.Lead_Status),
    scoringVenta: safeNum(zohoData.Scoring_venta),
    cursosConsultados: safeStr(zohoData.Cursos_consultados),
    // mensaje del lead
    userMessage: resolveUserMessage(),
    // meta
    ficha_inicializada: true,
    fichaTimestamp: Date.now(),
  }
}];
`.trim();

// ─── Code del nodo "Merge Ficha + Curso" ─────────────────────────────────────
// Toma la ficha (paso anterior al Postgres) + el curso del Postgres y los une.
const MERGE_CODE = String.raw`
const ficha = $('Normalizar Ficha').first().json;
const cursoRow = $input.first().json;

// pitch_by_profile es jsonb (objeto con keys por perfil) — pickea el más relevante
let pitchPorPerfil = "";
try {
  const pbp = cursoRow.pitch_by_profile || {};
  const prof = (ficha.profesion || "").toLowerCase();
  // mapeo aproximado profesión → key del pitch_by_profile
  const keys = ["medico", "medico_jefe", "residente", "estudiante", "enfermeria", "tecnico_salud", "licenciado_salud", "otros"];
  let pickedKey = "medico";
  if (prof.includes("residente")) pickedKey = "residente";
  else if (prof.includes("estudiante")) pickedKey = "estudiante";
  else if (prof.includes("enfermer")) pickedKey = "enfermeria";
  else if (prof.includes("tecnico") || prof.includes("técnico")) pickedKey = "tecnico_salud";
  else if (prof.includes("licenciado")) pickedKey = "licenciado_salud";
  else if (prof.includes("jefe") || prof.includes("dirección") || prof.includes("director")) pickedKey = "medico_jefe";
  pitchPorPerfil = String(pbp[pickedKey] || pbp.medico || pbp.otros || "");
} catch (e) {}

return [{
  json: Object.assign({}, ficha, {
    cursoCategoria: String(cursoRow.categoria || ""),
    cursoCedente: String(cursoRow.cedente || ""),
    cursoDuracionHs: Number(cursoRow.duration_hours || 0),
    cursoModulos: Number(cursoRow.modules_count || 0),
    cursoCurrencyDb: String(cursoRow.currency || ""),
    cursoTotalPrice: Number(cursoRow.total_price || 0),
    cursoMaxInstallments: Number(cursoRow.max_installments || 0),
    cursoPriceInstallments: Number(cursoRow.price_installments || 0),
    pitchHook: String(cursoRow.pitch_hook || ""),
    pitchPorPerfil,
    briefMd: String(cursoRow.brief_md || ""),
  })
}];
`.trim();

// ─── Nodos ───────────────────────────────────────────────────────────────────
const webhookTrigger = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'bot-ventas-inbound-v1',
    parameters: {
      httpMethod: 'POST',
      path: 'bot-ventas-inbound-v1',
      responseMode: 'responseNode',
    },
    position: [200, 300],
  },
  output: [{}],
});

const normalizarFicha = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Normalizar Ficha',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: NORMALIZAR_FICHA_CODE,
    },
    position: [440, 300],
  },
  output: [{}],
});

const buscarCurso = node({
  type: 'n8n-nodes-base.postgres',
  version: 2.6,
  config: {
    name: 'Buscar Curso (Supabase)',
    parameters: {
      operation: 'executeQuery',
      query: `select slug, title, categoria, cedente, currency, max_installments,
              price_installments, total_price, brief_md, pitch_hook, pitch_by_profile,
              duration_hours, modules_count
       from public.courses
       where country = $1 and slug = $2
       limit 1`,
      options: {
        queryReplacement: '={{ $json.pais }},{{ $json.cursoSlug }}',
      },
    },
    credentials: { postgres: newCredential('Supabase Postgres (catálogo MSK)') },
    position: [680, 300],
  },
  output: [{}],
});

const mergeFichaCurso = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Merge Ficha + Curso',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: MERGE_CODE,
    },
    position: [920, 300],
  },
  output: [{}],
});

const openAiModel = languageModel({
  type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
  version: 1.3,
  config: {
    name: 'OpenAI Chat Model',
    parameters: {
      model: { __rl: true, mode: 'list', value: 'gpt-4o' },
      options: { temperature: 0.4 },
    },
    credentials: { openAiApi: newCredential('OpenAI') },
    position: [1160, 500],
  },
});

const redisMemory = memory({
  type: '@n8n/n8n-nodes-langchain.memoryRedisChat',
  version: 1.6,
  config: {
    name: 'Redis Chat Memory',
    parameters: {
      sessionIdType: 'customKey',
      sessionKey: '={{ $json.sessionId }}',
      sessionTTL: 0,
      contextWindowLength: 10,
    },
    credentials: { redis: newCredential('Redis (memoria conversacional)') },
    position: [1320, 500],
  },
});

const aiAgent = node({
  type: '@n8n/n8n-nodes-langchain.agent',
  version: 3.1,
  config: {
    name: 'AI Agent — Ventas',
    parameters: {
      promptType: 'define',
      text: '={{ $json.userMessage }}',
      options: {
        systemMessage: '=' + SYSTEM_PROMPT,
        maxIterations: 5,
      },
    },
    subnodes: { model: openAiModel, memory: redisMemory },
    position: [1240, 300],
  },
  output: [{}],
});

const envioWhatsApp = node({
  type: 'n8n-nodes-base.set',
  version: 3.4,
  config: {
    name: 'envío a WhatsApp',
    parameters: {
      mode: 'manual',
      assignments: {
        assignments: [
          { id: 'a1', name: 'leadId', value: '={{ $(\'Merge Ficha + Curso\').first().json.leadId }}', type: 'string' },
          { id: 'a2', name: 'sessionId', value: '={{ $(\'Merge Ficha + Curso\').first().json.sessionId }}', type: 'string' },
          { id: 'a3', name: 'telefono', value: '={{ $(\'Merge Ficha + Curso\').first().json.telefono }}', type: 'string' },
          { id: 'a4', name: 'pais', value: '={{ $(\'Merge Ficha + Curso\').first().json.pais }}', type: 'string' },
          { id: 'a5', name: 'cursoSlug', value: '={{ $(\'Merge Ficha + Curso\').first().json.cursoSlug }}', type: 'string' },
          { id: 'a6', name: 'cursoTitulo', value: '={{ $(\'Merge Ficha + Curso\').first().json.cursoTitulo }}', type: 'string' },
          { id: 'a7', name: 'response', value: '={{ $json.output }}', type: 'string' },
        ],
      },
      includeOtherFields: false,
    },
    position: [1480, 300],
  },
  output: [{}],
});

const respondWebhook = node({
  type: 'n8n-nodes-base.respondToWebhook',
  version: 1.5,
  config: {
    name: 'Respond to Webhook',
    parameters: {
      respondWith: 'firstIncomingItem',
      options: {
        responseCode: 200,
      },
    },
    position: [1720, 300],
  },
});

export default workflow('bot-ventas-n8n', '[DRAFT] Bot Ventas — Lead HSM → WhatsApp')
  .add(webhookTrigger)
  .to(normalizarFicha)
  .to(buscarCurso)
  .to(mergeFichaCurso)
  .to(aiAgent)
  .to(envioWhatsApp)
  .to(respondWebhook);
