"""
Herramientas del agente de ventas:
- search_courses: RAG sobre Pinecone
- get_course_details: detalle de un curso específico
- create_payment_link: genera link MP o Rebill según el curso
- create_lead: crea lead en Zoho
- create_sales_order: crea orden de venta en Zoho
"""
from langchain_core.tools import tool
from rag.retriever import get_retriever
from integrations.payments.mercadopago import MercadoPagoClient
from integrations.payments.rebill import RebillClient
from integrations.zoho.leads import ZohoLeads
from integrations.zoho.contacts import ZohoContacts
from integrations.zoho.sales_orders import ZohoSalesOrders
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


@tool
async def search_courses(query: str, country: str = "AR", categoria: str = "") -> str:
    """
    Busca cursos médicos relevantes según la consulta del usuario.
    Retorna una lista formateada de los cursos más relevantes con precio y detalles.

    Args:
        query: Descripción de lo que busca el usuario (ej: 'cardiología para médicos generales')
        country: Código de país del usuario (AR, MX, CO, PE, CL, UY)
        categoria: Filtro opcional por categoría (ej: 'Pediatría', 'Cardiología')
    """
    retriever = get_retriever()
    filters = {}
    if categoria:
        filters["categoria"] = {"$eq": categoria}

    results = await retriever.search(query, country=country, filters=filters or None)
    return retriever.format_for_llm(results)


@tool
async def get_course_details(course_name: str, country: str = "AR") -> str:
    """
    Obtiene detalles completos de un curso específico por nombre.
    Usar cuando el usuario pregunta por un curso en particular.

    Args:
        course_name: Nombre o parte del nombre del curso
        country: Código de país del usuario
    """
    retriever = get_retriever()
    results = await retriever.search(course_name, country=country, top_k=1)
    if not results:
        return f"No encontré el curso '{course_name}' para el país {country}."

    c = results[0].course
    lines = [
        f"📚 {c.nombre}",
        f"",
        f"📋 Descripción: {c.descripcion}",
        f"🏷️ Categoría: {c.categoria}",
        f"💰 Precio: {c.precio_formateado}",
    ]
    if c.cuotas_disponibles and c.precio_cuota:
        lines.append(f"💳 Cuotas: {c.cuotas_disponibles} cuotas de {c.moneda} {c.precio_cuota:,.0f}")
    if c.duracion_horas:
        lines.append(f"⏱️ Duración: {c.duracion_horas} horas")
    if c.modalidad:
        lines.append(f"🖥️ Modalidad: {c.modalidad}")
    if c.tiene_certificado:
        cert = c.tipo_certificado or "Sí"
        lines.append(f"🎓 Certificado: {cert}")
    if c.docentes:
        lines.append(f"👨‍⚕️ Docentes: {', '.join(c.docentes)}")
    if c.fecha_inicio:
        lines.append(f"📅 Próximo inicio: {c.fecha_inicio}")
    if c.rebill_plan_id:
        lines.append(f"✅ Disponible en cuotas vía Rebill")
    lines.append(f"🆔 ID interno: {c.id}")

    return "\n".join(lines)


@tool
async def create_payment_link(
    course_id: str,
    course_name: str,
    price: float,
    currency: str,
    country: str,
    customer_email: str,
    customer_name: str,
    zoho_order_id: str = "",
    use_rebill: bool = False,
    rebill_plan_id: str = "",
) -> str:
    """
    Genera un link de pago para la inscripción al curso.
    Usa Rebill si el curso tiene plan de suscripción (cuotas), sino MercadoPago (pago único).

    Args:
        course_id: ID interno del curso
        course_name: Nombre del curso
        price: Precio total
        currency: Moneda (ARS, MXN, COP, etc.)
        country: País del usuario
        customer_email: Email del cliente
        customer_name: Nombre completo del cliente
        zoho_order_id: ID de la orden en Zoho (opcional, para referencia)
        use_rebill: Si True, genera link de suscripción Rebill (cuotas)
        rebill_plan_id: ID del plan en Rebill (requerido si use_rebill=True)
    """
    external_ref = zoho_order_id or f"{course_id}_{customer_email}"
    settings = get_settings()

    if use_rebill and rebill_plan_id:
        client = RebillClient()
        name_parts = customer_name.strip().split(" ", 1)
        result = await client.create_subscription_link(
            plan_id=rebill_plan_id,
            customer={
                "email": customer_email,
                "first_name": name_parts[0],
                "last_name": name_parts[1] if len(name_parts) > 1 else "",
                "phone": "",
            },
            external_reference=external_ref,
        )
        url = result.get("checkout_url", "")
        return f"Link de pago en cuotas generado:\n{url}\n\n_ID suscripción: {result.get('subscription_id', '')}_"
    else:
        client_mp = MercadoPagoClient()
        result = await client_mp.create_payment_link(
            title=course_name,
            price=price,
            currency=currency,
            payer_email=customer_email,
            external_reference=external_ref,
        )
        url = result.get("checkout_url", "")
        return f"Link de pago generado:\n{url}\n\n_Preference ID: {result.get('preference_id', '')}_"


@tool
async def create_or_update_lead(
    name: str,
    phone: str,
    email: str,
    country: str,
    course_name: str,
    channel: str = "WhatsApp",
    notes: str = "",
) -> str:
    """
    Crea o actualiza un Lead en Zoho CRM.
    Llamar cuando el usuario muestra interés o antes de generar el link de pago.

    Args:
        name: Nombre completo
        phone: Teléfono con código de país
        email: Email
        country: País (Argentina, México, etc.)
        course_name: Nombre del curso de interés
        channel: Canal de origen (WhatsApp, Widget Web)
        notes: Notas adicionales
    """
    leads = ZohoLeads()
    existing = await leads.search_by_phone(phone) if phone else None

    data = {
        "name": name,
        "phone": phone,
        "email": email,
        "country": country,
        "curso_de_interes": course_name,
        "canal_origen": channel,
        "notas": notes,
    }

    if existing:
        await leads.update(existing["id"], {
            "Curso_de_Interes": course_name,
            "Notas_Bot": notes,
        })
        return f"Lead actualizado en Zoho. ID: {existing['id']}"
    else:
        result = await leads.create(data)
        return f"Lead creado en Zoho. ID: {result['id']}"


@tool
async def create_sales_order(
    contact_id: str,
    course_name: str,
    price: float,
    currency: str,
    country: str,
    payment_link: str,
    payment_provider: str,
    notes: str = "",
) -> str:
    """
    Crea una Sales Order en Zoho CRM para registrar la inscripción y el link de pago.
    Llamar después de generar el link de pago.

    Args:
        contact_id: ID del contacto en Zoho
        course_name: Nombre del curso
        price: Precio
        currency: Moneda
        country: País
        payment_link: URL del link de pago generado
        payment_provider: 'MercadoPago' o 'Rebill'
        notes: Notas adicionales
    """
    orders = ZohoSalesOrders()
    result = await orders.create({
        "contact_id": contact_id,
        "curso_nombre": course_name,
        "precio": price,
        "moneda": currency,
        "payment_link": payment_link,
        "payment_provider": payment_provider,
        "pais": country,
        "notas": notes,
    })
    return f"Orden de venta creada en Zoho. ID: {result['id']}"
