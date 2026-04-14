"""
Procesador de mensajes del widget web embebible.
El widget usa HTTP polling o SSE (Server-Sent Events).
"""
from models.message import Message, MessageRole
from memory.conversation_store import get_conversation_store
from agents.router import route_message
from integrations.notifications import notify_handoff
from config.constants import Channel, ConversationStatus, MAX_HISTORY_MESSAGES
import structlog

logger = structlog.get_logger(__name__)


async def process_widget_message(
    session_id: str,
    message_text: str,
    country: str = "AR",
    user_name: str = "",
    user_email: str = "",
    user_courses: str = "",
) -> dict:
    """
    Procesa un mensaje del widget web.

    Returns:
        {response: str, agent_used: str, handoff_requested: bool, session_id: str}
    """
    store = await get_conversation_store()
    conversation, is_new = await store.get_or_create(
        channel=Channel.WIDGET,
        external_id=session_id,
        country=country,
    )

    # Verificar si un agente humano tomó el control (bot desactivado)
    bot_disabled = await store._redis.get(f"bot_disabled:{session_id}")
    if bot_disabled:
        # Guardar el mensaje del usuario igual, pero no responder con IA
        user_msg_only = Message(role=MessageRole.USER, content=message_text)
        await store.append_message(conversation, user_msg_only)

        # Notificar al inbox via SSE
        try:
            from api.inbox import broadcast_event
            import datetime
            broadcast_event({
                "type": "new_message",
                "session_id": session_id,
                "role": "user",
                "content": message_text,
                "sender_name": user_name or "Usuario",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

        return {
            "response": "",
            "agent_used": "humano",
            "handoff_requested": False,
            "session_id": session_id,
            "bot_disabled": True,
        }

    # Si la conversación fue handed off, informar al usuario
    if conversation.status == ConversationStatus.HANDED_OFF:
        return {
            "response": "Tu consulta fue derivada a un asesor. Te contactaremos a la brevedad.",
            "agent_used": "humano",
            "handoff_requested": True,
            "session_id": session_id,
        }

    # Actualizar perfil si se tienen datos
    if user_name and not conversation.user_profile.name:
        conversation.user_profile.name = user_name
    if user_email and not conversation.user_profile.email:
        conversation.user_profile.email = user_email

    # ── Enriquecer contexto con datos del cliente logueado ──
    # Si tenemos email, buscamos sus datos en la tabla customers y/o Zoho
    user_context_lines = []
    if user_email:
        # 1. Datos de customers (Supabase)
        try:
            from integrations.supabase_client import get_customer_profile
            profile = await get_customer_profile(user_email)
            if profile:
                if profile.get("name"):
                    user_context_lines.append(f"Nombre del cliente: {profile['name']}")
                if profile.get("phone"):
                    user_context_lines.append(f"Teléfono: {profile['phone']}")
                courses = profile.get("courses") or []
                if courses:
                    user_context_lines.append(f"Cursos inscriptos: {', '.join(courses)}")
                if profile.get("profession"):
                    user_context_lines.append(f"Profesión: {profile['profession']}")
                if profile.get("specialty"):
                    user_context_lines.append(f"Especialidad: {profile['specialty']}")
                if profile.get("interests"):
                    user_context_lines.append(f"Intereses: {profile['interests']}")
        except Exception as e:
            logger.debug("customer_profile_lookup_failed", error=str(e))
        # Also use courses passed directly from widget (faster, no DB call)
        if user_courses and not any("Cursos inscriptos" in l for l in user_context_lines):
            user_context_lines.append(f"Cursos inscriptos: {user_courses}")

        # 2. Cache Zoho (si ya fue buscado antes)
        try:
            import json as _json
            cached_zoho = await store._redis.get(f"zoho_cache:{session_id}")
            if cached_zoho:
                zoho_data = _json.loads(cached_zoho)
                if zoho_data.get("found") and zoho_data.get("record"):
                    r = zoho_data["record"]
                    if r.get("curso_de_interes"):
                        user_context_lines.append(f"Curso de interés (CRM): {r['curso_de_interes']}")
                    if r.get("estado_pago"):
                        user_context_lines.append(f"Estado de pago (CRM): {r['estado_pago']}")
        except Exception:
            pass

        # 3. Perfil Zoho completo (profesión, especialidad, intereses, cursadas) — cacheado por email
        try:
            import json as _json
            cursadas_key = f"zoho_cursadas:{user_email}"
            cached_cursadas = await store._redis.get(cursadas_key)

            if cached_cursadas is None:
                # Buscar en Zoho por primera vez — traer perfil completo
                from integrations.zoho.contacts import ZohoContacts
                zc = ZohoContacts()
                contact = await zc.search_by_email_with_full_profile(user_email)
                cursadas_list = []
                if contact:
                    # Agregar campos de perfil profesional al contexto
                    def _lst(v):
                        if isinstance(v, list):
                            return ", ".join(str(x) for x in v if x and str(x) != "null")
                        return str(v) if v else ""

                    profesion_zoho = contact.get("Profesi_n", "") or contact.get("Profesi\u00f3n", "") or contact.get("Profesion", "")
                    especialidad_zoho = contact.get("Especialidad", "")
                    esp_interes = _lst(contact.get("Especialidad_interes"))
                    intereses_ad = _lst(contact.get("Intereses_adicionales"))
                    contenido = _lst(contact.get("Contenido_Interes"))

                    if profesion_zoho and not any("Profesión" in l for l in user_context_lines):
                        user_context_lines.append(f"Profesión: {profesion_zoho}")
                    if especialidad_zoho and not any("Especialidad:" in l for l in user_context_lines):
                        user_context_lines.append(f"Especialidad: {especialidad_zoho}")
                    if esp_interes:
                        user_context_lines.append(f"Especialidades de interés: {esp_interes}")
                    if intereses_ad:
                        user_context_lines.append(f"Intereses adicionales: {intereses_ad}")
                    if contenido:
                        user_context_lines.append(f"Contenido de interés: {contenido}")

                    # Parsear cursadas — campos pueden ser string o lookup {name, id}
                    def _curso_name(entry):
                        for fld in ("Curso", "Nombre_de_curso", "Nombre_del_curso"):
                            v = entry.get(fld)
                            if isinstance(v, dict):
                                return v.get("name", "")
                            if isinstance(v, str) and v.strip():
                                return v.strip()
                        return ""

                    raw = contact.get("Formulario_de_cursada") or []
                    for item in raw:
                        nombre = _curso_name(item)
                        if nombre:
                            cursadas_list.append({
                                "curso": nombre,
                                "finalizo": item.get("Finalizo"),
                                "estado_ov": item.get("Estado_de_OV", ""),
                                "fecha_fin": item.get("Fecha_finalizaci_n") or item.get("Fecha_finalización", ""),
                                "fecha_enrol": item.get("Enrollamiento", ""),
                            })
                # Cachear 24hs
                await store._redis.setex(cursadas_key, 86400, _json.dumps(cursadas_list))
            else:
                cursadas_list = _json.loads(cached_cursadas)

            if cursadas_list:
                # Armar texto de TODOS los cursos del alumno (cualquier estado)
                todos = [c["curso"] for c in cursadas_list]
                user_context_lines.append(
                    f"Cursos del alumno ({len(todos)} total): {', '.join(todos)}"
                )
                user_context_lines.append(
                    f"IMPORTANTE — No recomiendes estos cursos (ya los tiene): {', '.join(todos)}"
                )
        except Exception as e:
            logger.debug("zoho_cursadas_lookup_failed", error=str(e))

    # ── Saludo personalizado al abrir el widget ───────────────────────────────
    if message_text == "__widget_init__":
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            from config.settings import get_settings

            # Armar contexto del cliente para el saludo
            ctx = "\n".join(user_context_lines) if user_context_lines else ""
            system = (
                "Sos el asistente de MSK Latam, una plataforma de capacitación médica. "
                "El cliente acaba de abrir el chat. Tu tarea es generar un saludo breve "
                "(2-3 oraciones), cálido y personalizado usando su información. "
                "Si sabés su nombre, usá solo el primero. "
                "Si tenés sus cursos finalizados, podés mencionarlos brevemente. "
                "Al final, invitalo a que te consulte sobre nuevos cursos según su perfil. "
                "No listes todos sus datos. Respondé solo el saludo, sin explicaciones."
            )
            if ctx:
                system += f"\n\nDatos del cliente:\n{ctx}"

            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=get_settings().openai_api_key,
                temperature=0.7,
                max_tokens=120,
            )
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="Generá el saludo personalizado."),
            ])
            greeting_text = resp.content.strip()
        except Exception as e:
            logger.warning("widget_init_greeting_failed", error=str(e))
            nombre = user_name.split()[0] if user_name else ""
            greeting_text = (
                f"¡Hola{' ' + nombre if nombre else ''}! 👋 "
                "Soy tu asesor de MSK Latam. "
                "Estoy aquí para recomendarte cursos médicos según tu perfil. ¿En qué te puedo ayudar?"
            )

        # Guardar solo la respuesta del bot (no el __widget_init__)
        bot_msg = Message(
            role=MessageRole.ASSISTANT,
            content=greeting_text,
            metadata={"agent": "bienvenida"},
        )
        await store.append_message(conversation, bot_msg)

        # Notificar inbox
        try:
            from api.inbox import broadcast_event
            import datetime
            broadcast_event({
                "type": "new_message",
                "session_id": session_id,
                "role": "assistant",
                "content": greeting_text,
                "sender_name": "bienvenida",
                "timestamp": bot_msg.timestamp.isoformat(),
            })
        except Exception:
            pass

        return {
            "response": greeting_text,
            "agent_used": "bienvenida",
            "handoff_requested": False,
            "session_id": session_id,
        }

    # Guardar mensaje del usuario
    user_msg = Message(role=MessageRole.USER, content=message_text)
    await store.append_message(conversation, user_msg)

    # Historial para el LLM
    history = conversation.get_history_for_llm(MAX_HISTORY_MESSAGES)
    history_without_last = history[:-1] if history else []

    # Prepend context as a system-style message if we have user data
    if user_context_lines:
        context_block = (
            "[CONTEXTO DEL CLIENTE IDENTIFICADO]\n"
            + "\n".join(user_context_lines)
            + "\n\nUsá estos datos para personalizar la respuesta:\n"
            + "- Saluda al cliente por su nombre si es el primer mensaje.\n"
            + "- Si el cliente pregunta por cursos o recomendaciones, sugerí cursos NUEVOS "
            + "basándote en su profesión, especialidad e intereses, pero NUNCA recomiendes "
            + "cursos que ya tiene (los marcados como 'No recomiendes').\n"
            + "- No repitas literalmente estos datos, usálos de forma natural en la conversación."
        )
        history_without_last = [{"role": "system", "content": context_block}] + history_without_last

    logger.info(
        "widget_message_received",
        session_id=session_id,
        country=country,
        is_new=is_new,
    )

    # Procesar con el supervisor
    result = await route_message(
        user_message=message_text,
        history=history_without_last,
        country=country,
        channel="widget",
        conversation_id=conversation.id,
        phone=conversation.user_profile.phone or "",
        skip_flow=bool(user_email),   # usuario logueado → respuesta natural, sin flujo
    )

    # Si el agente de cobranzas obtuvo la ficha via email, guardarla en Redis
    if (result.get("agent_used") == "cobranzas"
            and user_email
            and not result.get("handoff_requested")):
        try:
            from integrations.zoho.area_cobranzas import ZohoAreaCobranzas
            import json as _json
            zoho = ZohoAreaCobranzas()
            ficha = await zoho.search_by_email(user_email)
            if ficha and ficha.get("cobranzaId"):
                redis = store._redis
                key = f"datos_deudor:{user_email}"
                await redis.setex(key, 7200, _json.dumps(ficha))
        except Exception:
            pass

    response_text = result["response"]
    handoff = result["handoff_requested"]
    handoff_reason = result["handoff_reason"]

    # Guardar respuesta del bot
    bot_msg = Message(
        role=MessageRole.ASSISTANT,
        content=response_text,
        metadata={"agent": result["agent_used"]},
    )
    await store.append_message(conversation, bot_msg)

    # Notificar al inbox via SSE (usuario + respuesta bot)
    try:
        from api.inbox import broadcast_event
        import datetime
        broadcast_event({
            "type": "new_message",
            "session_id": session_id,
            "role": "user",
            "content": message_text,
            "sender_name": user_name or "Usuario",
            "timestamp": user_msg.timestamp.isoformat(),
        })
        if response_text:
            broadcast_event({
                "type": "new_message",
                "session_id": session_id,
                "role": "assistant",
                "content": response_text,
                "sender_name": result["agent_used"],
                "timestamp": bot_msg.timestamp.isoformat(),
            })
    except Exception:
        pass

    # Auto-clasificar lead
    try:
        from agents.classifier import classify_conversation
        msgs = [{"role": m.role.value, "content": m.content} for m in conversation.messages[-10:]]
        await classify_conversation(msgs, session_id)
    except Exception:
        pass

    if handoff:
        await notify_handoff(
            channel="Widget Web",
            external_id=session_id,
            user_name=user_name or session_id,
            reason=handoff_reason,
            agent=result["agent_used"],
        )
        conversation.status = ConversationStatus.HANDED_OFF
        await store.save(conversation)
        # Auto-assign via round-robin
        try:
            from api.inbox import auto_assign_round_robin
            await auto_assign_round_robin(session_id)
        except Exception:
            pass

    return {
        "response": response_text,
        "agent_used": result["agent_used"],
        "handoff_requested": handoff,
        "session_id": session_id,
    }
