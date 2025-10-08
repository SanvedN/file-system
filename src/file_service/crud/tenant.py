from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from file_service.models import Tenant
from shared.utils import logger


class TenantCRUD:
    model = Tenant

    async def get_by_id(self, db: AsyncSession, tenant_id: UUID) -> Optional[Tenant]:
        q = select(self.model).where(self.model.tenant_id == tenant_id)
        r = await db.execute(q)
        return r.scalars().first()

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Tenant]:
        q = select(self.model).where(self.model.tenant_code == code)
        r = await db.execute(q)
        return r.scalars().first()

    async def list(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[Tenant]:
        q = select(self.model).offset(skip).limit(limit)
        r = await db.execute(q)
        return r.scalars().all()

    async def create(
        self, db: AsyncSession, *, code: str, configuration: dict
    ) -> Tenant:
        obj = self.model(tenant_code=code, configuration=configuration)
        db.add(obj)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.exception("IntegrityError creating tenant: %s", e)
            raise
        await db.refresh(obj)
        return obj

    async def update_configuration(
        self, db: AsyncSession, tenant_id: UUID, configuration: dict
    ) -> Optional[Tenant]:
        q = select(self.model).where(self.model.tenant_id == tenant_id)
        r = await db.execute(q)
        obj = r.scalars().first()
        if not obj:
            return None
        obj.configuration = configuration
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def delete(self, db: AsyncSession, tenant_id: UUID) -> bool:
        q = select(self.model).where(self.model.tenant_id == tenant_id)
        r = await db.execute(q)
        obj = r.scalars().first()
        if not obj:
            return False
        await db.delete(obj)
        await db.commit()
        return True
