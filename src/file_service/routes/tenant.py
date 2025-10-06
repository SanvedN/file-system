# src/file_service/routes/tenant.py
from fastapi import APIRouter, Depends, BackgroundTasks, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from file_service.schemas import TenantCreate, TenantResponse, TenantUpdate
from file_service.services.tenant_service import (
    create_tenant,
    get_tenant_by_code,
    update_tenant,
    delete_tenant,
)
from shared.db import get_db
from shared.cache import get_redis_client, get_redis
from shared.utils import logger
from file_service.crud.tenant import TenantCRUD

router = APIRouter(prefix="/v2/tenants", tags=["Tenants"])


@router.get("/ping", summary="Tenant service ping")
async def ping():
    return {"status": "ok"}


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def api_create_tenant(
    payload: TenantCreate, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    tenant = await create_tenant(db, redis, payload)
    return tenant


@router.get("/{code}", response_model=TenantResponse)
async def api_get_tenant(
    code: str, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
):
    tenant = await get_tenant_by_code(db, redis, code)
    return tenant


@router.patch("/{code}", response_model=TenantResponse)
async def api_update_tenant(
    code: str,
    payload: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    updated = await update_tenant(db, redis, code, payload)
    return updated


@router.delete("/{code}", status_code=status.HTTP_200_OK)
async def api_delete_tenant(
    code: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    result = await delete_tenant(db, redis, code, background=background_tasks)
    return result


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    crud = TenantCRUD()
    tenants = await crud.list(db, skip=skip, limit=limit)
    return tenants
