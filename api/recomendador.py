"""
Recomendador de cursos para el flujo de Televenta.

Endpoints:
    POST /api/v1/recomendador/cursos   → 4 cursos recomendados para un perfil

Lo consume el workflow de n8n "Recomendador TV", que corre una vez por día:
baja la vista de Zoho Analytics (alumnos con certificado emitido), y por cada
fila pega acá y después crea el lead en Zoho CRM.

Auth: `X-Admin-Key`, igual que el resto de los endpoints de máquina.

Reemplaza al Assistant de OpenAI que murió con el sunset de la Assistants API
(2026-08-26). Ver `integrations/msk_recomendador.py` para el porqué del diseño.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.admin import verify_admin_key
from integrations import msk_recomendador

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/recomendador", tags=["recomendador"])


class RecomendarRequest(BaseModel):
    # El país llega como nombre desde Analytics ("Argentina"), pero se acepta
    # también el ISO. Desconocido cae al catálogo de Colombia.
    pais: str | None = Field(None, description='Nombre del país o ISO-2. Ej: "Argentina" o "ar"')
    profesion: str = ""
    especialidad: str = ""
    temas_interes: str = ""
    # Analytics manda los cursos cursados en un solo string separado por ';'.
    cursos_realizados: str | list[str] | None = None
    n: int = Field(msk_recomendador.N_RECOMENDACIONES, ge=1, le=10)


class CursoRecomendado(BaseModel):
    slug: str
    title: str
    product_id: int | None = None
    categoria: str | None = None
    cedente: str | None = None
    duration_hours: int | None = None
    currency: str | None = None
    total_price: float | None = None
    motivo: str = ""


class RecomendarResponse(BaseModel):
    country: str
    cursos: list[CursoRecomendado]
    # Listos para mapear directo a los campos del lead en Zoho, sin que n8n
    # tenga que hacer joins ni expresiones.
    titulos: str
    product_codes: str
    # True si el LLM falló o devolvió menos de `n` válidos y hubo que completar
    # con el ranking por defecto. Sirve para alertar sin cortar el flujo.
    fallback: bool
    candidatos_evaluados: int = 0


@router.post("/cursos", response_model=RecomendarResponse)
async def recomendar(
    req: RecomendarRequest,
    key: str = Depends(verify_admin_key),
) -> RecomendarResponse:
    resultado = await msk_recomendador.recomendar_cursos(
        pais=req.pais,
        profesion=req.profesion,
        especialidad=req.especialidad,
        temas_interes=req.temas_interes,
        cursos_realizados=req.cursos_realizados,
        n=req.n,
    )

    cursos = [
        CursoRecomendado(
            slug=c["slug"],
            title=c["title"],
            product_id=c.get("product_id"),
            categoria=c.get("categoria"),
            cedente=c.get("cedente"),
            duration_hours=c.get("duration_hours"),
            currency=c.get("currency"),
            total_price=float(c["total_price"]) if c.get("total_price") is not None else None,
            motivo=c.get("motivo", ""),
        )
        for c in resultado["cursos"]
    ]

    if resultado.get("fallback"):
        logger.warning(
            "recomendador_fallback",
            pais=req.pais,
            country=resultado["country"],
            devueltos=len(cursos),
        )

    return RecomendarResponse(
        country=resultado["country"],
        cursos=cursos,
        titulos="; ".join(c.title for c in cursos),
        product_codes="; ".join(str(c.product_id) for c in cursos if c.product_id),
        fallback=bool(resultado.get("fallback")),
        candidatos_evaluados=resultado.get("candidatos_evaluados", 0),
    )
