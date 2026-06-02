// ─────────────────────────────────────────────────────────────────────────────
// NORMALIZAR FICHA — BOT VENTAS (n8n)
//
// Mapea el payload del módulo Leads de Zoho CRM a las variables que consume
// el system prompt del AI Agent de ventas.
//
// Input esperado: el array `[ { data: [ { ...lead Zoho... } ] } ]` que llega
// al webhook desde el workflow disparador (HSM → Lead → este flow).
//
// Tolera tanto la forma envuelta (data[0]) como un objeto Zoho plano.
// ─────────────────────────────────────────────────────────────────────────────

const entrada = $input.first().json;
const zohoData = (entrada.data && entrada.data[0]) ? entrada.data[0] : entrada;

// ── País: Zoho lo guarda como string ("Argentina") → mapear a ISO-2 ─────────
const paisIso2 = (() => {
  const p = String(zohoData.Pais || "").toLowerCase().trim();
  if (!p) return "AR"; // fallback
  const map = {
    "argentina": "AR", "ar": "AR",
    "bolivia": "BO", "bo": "BO",
    "chile": "CL", "cl": "CL",
    "colombia": "CO", "co": "CO",
    "costa rica": "CR", "cr": "CR",
    "ecuador": "EC", "ec": "EC",
    "españa": "ES", "espana": "ES", "es": "ES",
    "guatemala": "GT", "gt": "GT",
    "honduras": "HN", "hn": "HN",
    "méxico": "MX", "mexico": "MX", "mx": "MX",
    "nicaragua": "NI", "ni": "NI",
    "panamá": "PA", "panama": "PA", "pa": "PA",
    "perú": "PE", "peru": "PE", "pe": "PE",
    "paraguay": "PY", "py": "PY",
    "el salvador": "SV", "sv": "SV",
    "uruguay": "UY", "uy": "UY",
    "venezuela": "VE", "ve": "VE",
  };
  return map[p] || "INT";
})();

// ── Moneda y formato locale ─────────────────────────────────────────────────
const monedaMap = {
  AR: "ARS", BO: "BOB", CL: "CLP", CO: "COP", CR: "CRC",
  EC: "USD", ES: "EUR", GT: "GTQ", HN: "HNL", MX: "MXN",
  NI: "NIO", PA: "USD", PE: "PEN", PY: "PYG", SV: "USD",
  UY: "UYU", VE: "USD", INT: "USD",
};
const localeMap = {
  AR: "es-AR", BO: "es-BO", CL: "es-CL", CO: "es-CO", CR: "es-CR",
  EC: "es-EC", ES: "es-ES", GT: "es-GT", HN: "es-HN", MX: "es-MX",
  NI: "es-NI", PA: "es-PA", PE: "es-PE", PY: "es-PY", SV: "es-SV",
  UY: "es-UY", VE: "es-VE", INT: "en-US",
};
const moneda = monedaMap[paisIso2] || "USD";
const locale = localeMap[paisIso2] || "es-AR";

// ── Resolver mensaje del usuario (igual lógica que el flow original) ────────
const resolveUserMessage = () => {
  try { const u = $('Unificar Mensajes').first().json;  if (u && u.body && u.body.userMessage) return u.body.userMessage; } catch (e) {}
  try { const e1 = $('Edit Fields1').first().json;       if (e1 && e1.texto_ocr) return e1.texto_ocr; } catch (e) {}
  try { const ef = $('Edit Fields').first().json;        if (ef && ef.body && ef.body.userMessage) return ef.body.userMessage; } catch (e) {}
  try { const wh = $('cobranzas-inbound-v1').first().json; if (wh && wh.body && wh.body.userMessage) return wh.body.userMessage; } catch (e) {}
  return "";
};

// ── Helpers ─────────────────────────────────────────────────────────────────
const safeStr = (v, fallback = "") => (v === null || v === undefined ? fallback : String(v));
const safeNum = (v, fallback = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};
const formatMonto = (n) => {
  if (!Number.isFinite(n) || n <= 0) return "";
  return n.toLocaleString(locale);
};

// ── Datos del lead ──────────────────────────────────────────────────────────
const nombre   = safeStr(zohoData.First_Name) || safeStr(zohoData.Full_Name).split(" ")[0] || "Doc";
const apellido = safeStr(zohoData.Last_Name);
const fullName = safeStr(zohoData.Full_Name) || `${nombre} ${apellido}`.trim();
const email    = safeStr(zohoData.Email);
const telefono = safeStr(zohoData.Phone);
const profesion = safeStr(zohoData.Profesion);
const especialidad = safeStr(zohoData.Especialidad);
const lugarTrabajo = safeStr(zohoData.Lugar_de_trabajo);
const cargo    = safeStr(zohoData.Tipo_de_vendedor); // no siempre aplica
const fuente   = safeStr(zohoData.Lead_Source);

// Colegio / matrícula AR (5 jurisdiccionales que el prompt usa)
const colegios = Array.isArray(zohoData.Colegio_Sociedad_o_Federaci_n)
  ? zohoData.Colegio_Sociedad_o_Federaci_n.map(x => safeStr(x?.name || x))
  : [];
const colegioMatchAR = (() => {
  const lower = colegios.join(" ").toLowerCase();
  if (lower.includes("misiones")) return "COLEMEMI (Colegio de Médicos de Misiones)";
  if (lower.includes("catamarca")) return "COLMEDCAT (Colegio de Médicos de Catamarca)";
  if (lower.includes("la pampa")) return "CSMLP (Consejo Superior Médico de La Pampa)";
  if (lower.includes("santa cruz")) return "CMSC (Consejo Médico de Santa Cruz)";
  if (lower.includes("santa fe") && lower.includes("1")) return "CMSF1 (Colegio de Médicos de Santa Fe 1ra)";
  return "";
})();

// ── Datos del curso (vienen pre-armados desde Zoho) ─────────────────────────
const cursoTitulo = safeStr(zohoData.curso_nombre_plantilla) || safeStr(zohoData.Programa?.name) || "el curso";
const cursoSlug   = (() => {
  const url = safeStr(zohoData.Link_web);
  const m = url.match(/curso\/([^/?#]+)/i);
  return m ? m[1] : "";
})();
const linkCheckout = safeStr(zohoData.Link_checkout);
const linkTemario  = safeStr(zohoData.Link_temario);
const linkWeb      = safeStr(zohoData.Link_web);
const linkCertif   = safeStr(zohoData.Certificaciones);

// Precio (Zoho a veces lo trae, a veces no)
const precioCuota = safeNum(zohoData.Precio_cuota);
const cuotas      = safeNum(zohoData.Cuotas);
const descuentoPct = safeNum(zohoData.Descuento);
const cuponZoho    = safeStr(zohoData.Cup_n_de_descuento) || safeStr(zohoData.CUPON_DESCUENTO) || safeStr(zohoData.cupon_bot);
const cuponValidoHasta = safeStr(zohoData.valido_hasta);

// ── Promo activa AR (Hot Sale) — solo si el lead es AR y no trae cupón propio
const promoArActiva = paisIso2 === "AR" && !cuponZoho;
const promoCodigo = promoArActiva ? "HOY30" : (cuponZoho || "");
const promoPct    = promoArActiva ? 30 : descuentoPct;
const promoUntil  = promoArActiva ? "17 de mayo 2026" : cuponValidoHasta;

// ── Output ──────────────────────────────────────────────────────────────────
return {
  // identificadores
  leadId: safeStr(zohoData.id),
  owner: safeStr(zohoData.Owner?.name),

  // contacto
  nombre,
  apellido,
  fullName,
  email,
  telefono,

  // geo + tono
  pais: paisIso2,
  paisNombre: safeStr(zohoData.Pais),
  ciudad: safeStr(zohoData.City),
  provincia: safeStr(zohoData.State),
  moneda,
  locale,

  // perfil profesional
  profesion,
  especialidad,
  lugarTrabajo,
  cargo,
  colegios,
  colegioMatchAR,

  // curso de interés
  cursoTitulo,
  cursoSlug,
  linkCheckout,
  linkTemario,
  linkWeb,
  linkCertif,
  precioCuota,
  precioCuotaFmt: formatMonto(precioCuota),
  cuotas,

  // promo / cupón
  promoActiva: !!(promoArActiva || cuponZoho),
  promoCodigo,
  promoPct,
  promoUntil,

  // contexto adicional
  fuente,
  leadStatus: safeStr(zohoData.Lead_Status),
  scoringVenta: safeNum(zohoData.Scoring_venta),
  cursosConsultados: safeStr(zohoData.Cursos_consultados),

  // mensaje del usuario (turno actual)
  userMessage: resolveUserMessage(),

  // metadata
  ficha_inicializada: true,
  fichaTimestamp: Date.now(),
};
