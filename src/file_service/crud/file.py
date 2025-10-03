# src/file_service/crud/file.py
from typing import List, Tuple
from sqlalchemy import select, delete
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

    async def delete_by_tenant(self, db: AsyncSession, tenant_id: UUID) -> List[Tuple[str, str]]:
        """
        Delete DB file rows for a tenant.
        Returns list of tuples (file_id, file_name) for disk cleanup.
        """
        files = await self.list_by_tenant(db, tenant_id)
        file_infos = [(f.id, f.file_name) for f in files]
        # delete rows
        q = delete(self.model).where(self.model.tenant_id == tenant_id)
        await db.execute(q)
        await db.commit()
        return file_infos
