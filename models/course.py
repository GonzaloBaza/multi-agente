from pydantic import BaseModel, Field


class Course(BaseModel):
    id: str
    nombre: str
    descripcion: str
    categoria: str
    duracion_horas: int | None = None
    modalidad: str | None = None  # online, presencial, mixto
    precio: float
    moneda: str = "ARS"
    pais: str = "AR"
    tiene_certificado: bool = True
    tipo_certificado: str | None = None  # universitario, aval_sociedades, etc.
    docentes: list[str] = Field(default_factory=list)
    fecha_inicio: str | None = None
    cuotas_disponibles: int | None = None
    precio_cuota: float | None = None
    url_inscripcion: str | None = None
    rebill_plan_id: str | None = None
    mp_product_id: str | None = None
    lms_course_id: str | None = None
    lms_platform: str | None = None  # moodle, blackboard, tropos
    tags: list[str] = Field(default_factory=list)

    @property
    def precio_formateado(self) -> str:
        return f"{self.moneda} {self.precio:,.0f}"

    def to_embedding_text(self) -> str:
        """Texto que se vectorizará en Pinecone."""
        parts = [
            f"Curso: {self.nombre}",
            f"Descripción: {self.descripcion}",
            f"Categoría: {self.categoria}",
            f"Certificado: {'Sí' if self.tiene_certificado else 'No'}",
        ]
        if self.tipo_certificado:
            parts.append(f"Tipo de certificado: {self.tipo_certificado}")
        if self.docentes:
            parts.append(f"Docentes: {', '.join(self.docentes)}")
        if self.duracion_horas:
            parts.append(f"Duración: {self.duracion_horas} horas")
        if self.modalidad:
            parts.append(f"Modalidad: {self.modalidad}")
        parts.append(f"Precio: {self.precio_formateado}")
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        return "\n".join(parts)

    def to_pinecone_metadata(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "precio": self.precio,
            "moneda": self.moneda,
            "pais": self.pais,
            "tiene_certificado": self.tiene_certificado,
            "tipo_certificado": self.tipo_certificado or "",
            "modalidad": self.modalidad or "",
            "lms_platform": self.lms_platform or "",
            "rebill_plan_id": self.rebill_plan_id or "",
            "mp_product_id": self.mp_product_id or "",
        }


class CourseSearchResult(BaseModel):
    course: Course
    score: float
    excerpt: str = ""
