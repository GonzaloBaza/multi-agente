"""
Indexa los cursos JSON en Pinecone.
Uso: python scripts/index_courses.py
"""
import json
import asyncio
from pathlib import Path
from pinecone import Pinecone, ServerlessSpec
from openai import AsyncOpenAI
from models.course import Course
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

BATCH_SIZE = 50


class CourseIndexer:
    def __init__(self):
        settings = get_settings()
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.openai_embedding_model
        self._index = None

    def _get_index(self):
        if self._index is None:
            self._index = self.pc.Index(self.index_name)
        return self._index

    def ensure_index_exists(self, dimension: int = 1536):
        existing = [i.name for i in self.pc.list_indexes()]
        if self.index_name not in existing:
            logger.info("creating_pinecone_index", name=self.index_name)
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        else:
            logger.info("index_exists", name=self.index_name)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def index_courses(self, courses: list[Course], namespace: str) -> int:
        """Vectoriza e indexa una lista de cursos en el namespace dado."""
        self.ensure_index_exists()
        index = self._get_index()
        total = 0

        for i in range(0, len(courses), BATCH_SIZE):
            batch = courses[i : i + BATCH_SIZE]
            texts = [c.to_embedding_text() for c in batch]
            embeddings = await self.embed_texts(texts)

            vectors = [
                {
                    "id": f"{namespace}_{c.id}",
                    "values": emb,
                    "metadata": {**c.to_pinecone_metadata(), "text": texts[j]},
                }
                for j, (c, emb) in enumerate(zip(batch, embeddings))
            ]

            index.upsert(vectors=vectors, namespace=namespace)
            total += len(vectors)
            logger.info("indexed_batch", namespace=namespace, count=len(vectors), total=total)

        return total

    async def index_from_file(self, json_path: Path, country_code: str) -> int:
        """Lee un JSON de cursos y lo indexa en el namespace del país."""
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        courses = [Course(**c) for c in raw]
        namespace = f"cursos_{country_code.lower()}"
        logger.info("indexing_file", path=str(json_path), country=country_code, count=len(courses))
        return await self.index_courses(courses, namespace)

    async def index_all_countries(self, data_dir: Path | None = None) -> dict[str, int]:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"

        results = {}
        for json_file in data_dir.glob("courses_*.json"):
            country_code = json_file.stem.split("_")[-1].upper()
            count = await self.index_from_file(json_file, country_code)
            results[country_code] = count

        return results
