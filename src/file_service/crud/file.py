# src/file_service/crud/file.py
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from file_service.models import File  # adjust path
from uuid import UUID
from shared.utils import logger


class FileCRUD:
    model = File

    async def list_by_tenant(self, db: AsyncSession, tenant_id: UUID):
        q = select(self.model).where(self.model.tenant_id == tenant_id)
        r = await db.execute(q)
        return r.scalars().all()

    async def get_by_id(self, db: AsyncSession, tenant_id: UUID, file_id: str) -> Optional[File]:
        q = select(self.model).where(
            and_(self.model.tenant_id == tenant_id, self.model.file_id == file_id)
        )
        r = await db.execute(q)
        return r.scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        file_id: str,
        file_name: str,
        file_path: str,
        media_type: str,
        file_size_bytes: int,
        tag: Optional[str],
        file_metadata: Optional[Dict[str, Any]],
    ) -> File:
        obj = self.model(
            tenant_id=tenant_id,
            file_id=file_id,
            file_name=file_name,
            file_path=file_path,
            media_type=media_type,
            file_size_bytes=file_size_bytes,
            tag=tag,
            file_metadata=file_metadata,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update_mutable(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        file_id: str,
        file_name: Optional[str] = None,
        tag: Optional[str] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[File]:
        obj = await self.get_by_id(db, tenant_id, file_id)
        if not obj:
            return None
        if file_name is not None:
            obj.file_name = file_name
        if tag is not None:
            obj.tag = tag
        if file_metadata is not None:
            obj.file_metadata = file_metadata
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def delete(self, db: AsyncSession, *, tenant_id: UUID, file_id: str) -> Optional[File]:
        obj = await self.get_by_id(db, tenant_id, file_id)
        if not obj:
            return None
        await db.delete(obj)
        await db.commit()
        return obj

    async def delete_by_tenant(self, db: AsyncSession, tenant_id: UUID) -> List[Tuple[str, str]]:
        """
        Delete DB file rows for a tenant.
        Returns list of tuples (file_id, file_name) for disk cleanup.
        """
        files = await self.list_by_tenant(db, tenant_id)
        file_infos = [(f.file_id, f.file_name) for f in files]
        # delete rows
        q = delete(self.model).where(self.model.tenant_id == tenant_id)
        await db.execute(q)
        await db.commit()
        return file_infos

    async def search(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filters: Dict[str, Any],
        sort_field: Optional[str],
        sort_order: str = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[File], int]:
        q = select(self.model).where(self.model.tenant_id == tenant_id)

        # Filters
        file_name = filters.get("file_name")
        if file_name:
            q = q.where(self.model.file_name.ilike(f"%{file_name}%"))

        media_type = filters.get("media_type")
        if media_type:
            q = q.where(self.model.media_type == media_type)

        tag = filters.get("tag")
        if tag:
            q = q.where(self.model.tag == tag)

        file_size_min = filters.get("file_size_min")
        if file_size_min is not None:
            q = q.where(self.model.file_size_bytes >= int(file_size_min))

        file_size_max = filters.get("file_size_max")
        if file_size_max is not None:
            q = q.where(self.model.file_size_bytes <= int(file_size_max))

        created_after = filters.get("created_after")
        if created_after is not None:
            q = q.where(self.model.created_at >= created_after)

        created_before = filters.get("created_before")
        if created_before is not None:
            q = q.where(self.model.created_at <= created_before)

        metadata = filters.get("metadata")
        if metadata:
            # JSONB contains
            q = q.where(self.model.file_metadata.contains(metadata))

        # Count total
        count_q = select(func.count()).select_from(q.subquery())
        total_r = await db.execute(count_q)
        total = int(total_r.scalar() or 0)

        # Sort
        sort_field_map = {
            "created_at": self.model.created_at,
            "modified_at": self.model.modified_at,
            "file_size_bytes": self.model.file_size_bytes,
            "file_name": self.model.file_name,
        }
        if sort_field in sort_field_map:
            col = sort_field_map[sort_field]
            q = q.order_by(col.desc() if sort_order == "desc" else col.asc())

        # Pagination
        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        offset = (page - 1) * limit
        q = q.offset(offset).limit(limit)

        r = await db.execute(q)
        items = r.scalars().all()
        return items, total
