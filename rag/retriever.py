"""
Retriever RAG: dado un query y país, devuelve los cursos más relevantes de Pinecone.
"""
from functools import lru_cache
from pinecone import Pinecone
from openai import AsyncOpenAI
from models.course import Course, CourseSearchResult
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

TOP_K = 5


class CourseRetriever:
    def __init__(self):
        settings = get_settings()
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = self._pc.Index(settings.pinecone_index_name)
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._embedding_model = settings.openai_embedding_model

    async def _embed(self, text: str) -> list[float]:
        response = await self._openai.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def search(
        self,
        query: str,
        country: str = "AR",
        top_k: int = TOP_K,
        filters: dict | None = None,
    ) -> list[CourseSearchResult]:
        namespace = f"cursos_{country.lower()}"
        embedding = await self._embed(query)

        query_kwargs: dict = {
            "vector": embedding,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": True,
        }
        if filters:
            query_kwargs["filter"] = filters

        response = self._index.query(**query_kwargs)

        results: list[CourseSearchResult] = []
        for match in response.matches:
            meta = match.metadata or {}
            try:
                course = Course(
                    id=meta.get("id", match.id),
                    nombre=meta.get("nombre", ""),
                    descripcion=meta.get("text", ""),
                    categoria=meta.get("categoria", ""),
                    precio=float(meta.get("precio", 0)),
                    moneda=meta.get("moneda", "ARS"),
                    pais=meta.get("pais", country),
                    tiene_certificado=bool(meta.get("tiene_certificado", True)),
                    tipo_certificado=meta.get("tipo_certificado") or None,
                    modalidad=meta.get("modalidad") or None,
                    lms_platform=meta.get("lms_platform") or None,
                    rebill_plan_id=meta.get("rebill_plan_id") or None,
                    mp_product_id=meta.get("mp_product_id") or None,
                )
                results.append(CourseSearchResult(course=course, score=match.score, excerpt=meta.get("text", "")))
            except Exception as e:
                logger.warning("course_parse_error", match_id=match.id, error=str(e))

        return results

    def format_for_llm(self, results: list[CourseSearchResult]) -> str:
        """Convierte resultados en texto estructurado para incluir en el prompt."""
        if not results:
            return "No encontré cursos que coincidan con tu búsqueda."

        lines = []
        for i, r in enumerate(results, 1):
            c = r.course
            lines.append(f"{i}. **{c.nombre}**")
            lines.append(f"   - Categoría: {c.categoria}")
            lines.append(f"   - Precio: {c.precio_formateado}")
            if c.cuotas_disponibles and c.precio_cuota:
                lines.append(f"   - Cuotas: {c.cuotas_disponibles}x {c.moneda} {c.precio_cuota:,.0f}")
            if c.duracion_horas:
                lines.append(f"   - Duración: {c.duracion_horas} hs")
            if c.modalidad:
                lines.append(f"   - Modalidad: {c.modalidad}")
            cert = c.tipo_certificado if c.tipo_certificado else ("Sí" if c.tiene_certificado else "No")
            lines.append(f"   - Certificado: {cert}")
            if c.fecha_inicio:
                lines.append(f"   - Próximo inicio: {c.fecha_inicio}")
            lines.append("")

        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_retriever() -> CourseRetriever:
    return CourseRetriever()
