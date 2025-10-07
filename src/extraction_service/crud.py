from __future__ import annotations

from typing import List, Optional, Sequence
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from extraction_service.models import Embedding


class EmbeddingCRUD:
    model = Embedding

    async def upsert(
        self, db: AsyncSession, *, file_id: str, page_id: int, vector: list[float], ocr: str | None
    ) -> Embedding:
        q = select(self.model).where(
            (self.model.file_id == file_id) & (self.model.page_id == page_id)
        )
        r = await db.execute(q)
        obj = r.scalars().first()
        if obj:
            obj.embeddings = vector
            obj.ocr = ocr
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
            return obj
        obj = self.model(file_id=file_id, page_id=page_id, embeddings=vector, ocr=ocr)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def get_by_file(self, db: AsyncSession, *, file_id: str) -> list[Embedding]:
        q = select(self.model).where(self.model.file_id == file_id).order_by(self.model.page_id.asc())
        r = await db.execute(q)
        return list(r.scalars().all())

    async def delete_by_file(self, db: AsyncSession, *, file_id: str) -> int:
        q = delete(self.model).where(self.model.file_id == file_id)
        r = await db.execute(q)
        await db.commit()
        return r.rowcount or 0

    async def search(self, db: AsyncSession, *, file_id: str, query_vector: list[float], top_k: int) -> Sequence[tuple[int, float, str | None]]:
        # Use pgvector <-> cosine distance
        # Pass vector as text literal and cast to vector to satisfy asyncpg binding
        qvec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
        sql = """
            SELECT page_id, 1 - (embeddings <=> CAST(:qvec AS vector)) AS score, ocr
            FROM cf_filerepo_embeddings
            WHERE file_id = :fid
            ORDER BY embeddings <=> CAST(:qvec AS vector) ASC
            LIMIT :k
        """
        r = await db.execute(
            text(sql),
            {"qvec": qvec_str, "fid": file_id, "k": top_k},
        )
        return r.all()


    async def search_tenant(
        self,
        db: AsyncSession,
        *,
        tenant_id: str,
        query_vector: list[float],
        top_k: int,
    ) -> Sequence[tuple[str, int, float, str | None, list[float]]]:
        # Join with cf_filerepo_file to filter by tenant
        qvec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
        sql = """
            SELECT e.file_id, e.page_id, 1 - (e.embeddings <=> CAST(:qvec AS vector)) AS score, e.ocr, e.embeddings
            FROM cf_filerepo_embeddings e
            INNER JOIN cf_filerepo_file f ON f.file_id = e.file_id
            WHERE f.tenant_id = CAST(:tid AS uuid)
            ORDER BY e.embeddings <=> CAST(:qvec AS vector) ASC
            LIMIT :k
        """
        r = await db.execute(
            text(sql),
            {"qvec": qvec_str, "tid": tenant_id, "k": top_k},
        )
        return r.all()


