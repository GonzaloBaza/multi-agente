"""Customer auth — usuarios del sitio web (clientes, no agentes)."""

import json
import uuid

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/customer", tags=["customer"])

SESSION_TTL = 86400 * 7  # 7 días

# Hardcoded demo data for specific users
DEMO_COURSES = {
    "gbaza2612@gmail.com": ["Cardiología Superior", "Pediatría Emergencias"],
}


class CustomerLogin(BaseModel):
    email: str
    password: str


class CustomerSignup(BaseModel):
    email: str
    password: str
    name: str
    phone: str | None = None
    country: str | None = None


@router.post("/login")
async def customer_login(req: CustomerLogin):
    """Login para clientes del sitio web."""
    from integrations.supabase_client import sign_in_with_password

    try:
        await sign_in_with_password(req.email, req.password)
    except ValueError:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    # Get or create customer profile
    from integrations.supabase_client import get_customer_profile

    try:
        profile = await get_customer_profile(req.email)
    except Exception:
        profile = None

    if not profile:
        profile = {"email": req.email, "name": req.email.split("@")[0], "courses": []}

    # Inject demo courses for known test users
    courses = profile.get("courses") or DEMO_COURSES.get(req.email, [])

    token = str(uuid.uuid4())
    customer_info = {
        "email": req.email,
        "name": profile.get("name", req.email.split("@")[0]),
        "courses": courses,
    }

    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        await store._redis.setex(f"customer_session:{token}", SESSION_TTL, json.dumps(customer_info))
    except Exception as e:
        logger.warning("redis_session_save_failed", error=str(e))
        # Still return token even if Redis is unavailable — session won't persist across restarts

    logger.info("customer_login", email=req.email)
    return {"token": token, "customer": customer_info}


@router.post("/signup")
async def customer_signup(req: CustomerSignup):
    """Registro de nuevo cliente."""
    from integrations.supabase_client import (
        admin_create_auth_user,
        create_customer_profile,
        get_customer_profile,
    )

    # Check if already has a customers row
    existing_profile = None
    try:
        existing_profile = await get_customer_profile(req.email)
    except Exception:
        pass

    if existing_profile:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email. Iniciá sesión.")

    # Try to create Supabase Auth user
    auth_already_exists = False
    try:
        result = await admin_create_auth_user(req.email, req.password, req.name)
        err = result.get("error") or result.get("msg", "")
        err_str = str(err).lower() if err else ""
        if err and ("already" in err_str or "registered" in err_str or "exists" in err_str):
            # Auth user exists but no customers row — create profile and continue
            auth_already_exists = True
        elif err:
            detail = result.get("msg") or (
                result.get("error", {}).get("message") if isinstance(result.get("error"), dict) else str(err)
            )
            raise HTTPException(status_code=400, detail=str(detail))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al crear usuario: {str(e)}")

    # Create customer profile row
    try:
        await create_customer_profile(
            email=req.email,
            name=req.name,
            phone=req.phone,
            country=req.country,
        )
    except Exception as e:
        logger.warning("customer_profile_create_failed", error=str(e))

    # Auto-login
    token = str(uuid.uuid4())
    courses = DEMO_COURSES.get(req.email, [])
    customer_info = {"email": req.email, "name": req.name, "courses": courses}

    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        await store._redis.setex(f"customer_session:{token}", SESSION_TTL, json.dumps(customer_info))
    except Exception as e:
        logger.warning("redis_session_save_failed", error=str(e))

    logger.info("customer_signup", email=req.email, auth_reused=auth_already_exists)
    return {"token": token, "customer": customer_info}


@router.get("/me")
async def customer_me(x_customer_token: str | None = Header(None)):
    """Verifica sesión de cliente."""
    if not x_customer_token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        data = await store._redis.get(f"customer_session:{x_customer_token}")
        if not data:
            raise HTTPException(status_code=401, detail="Sesión expirada")
        return json.loads(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
