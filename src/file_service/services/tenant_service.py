from datetime import datetime
import json
import asyncio
from copy import deepcopy
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, BackgroundTasks
from uuid import UUID
from file_service.schemas import TenantCreate, TenantResponse, TenantUpdate
from file_service.crud.tenant import TenantCRUD
from file_service.crud.file import FileCRUD
from shared.cache import cache_set_tenant, cache_get_tenant, cache_delete_tenant
from shared.utils import logger
from file_service.utils import (
    delete_tenant_folder,
    create_tenant_folder,
    generate_file_path,
    delete_file_path,
    get_default_tenant_configs_from_config,
)
from shared.config import settings

crud = TenantCRUD()
file_crud = FileCRUD()


async def get_tenant_by_code(db: AsyncSession, redis, code: str):
    # Try cache
    if redis:
        try:
            cached = await cache_get_tenant(redis, code)
            if cached is not None:
                return TenantResponse(
                    tenant_id=UUID(cached["tenant_id"]),
                    tenant_code=cached["tenant_code"],
                    configuration=cached["configuration"],
                    created_at=datetime.fromisoformat(cached["created_at"]),
                    updated_at=datetime.fromisoformat(cached["updated_at"])
                )
        except Exception:
            logger.exception("Redis read failed for tenant %s", code)

    tenant = await crud.get_by_code(db, code)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # cache full tenant
    if redis:
        try:
            await cache_set_tenant(redis, tenant.tenant_code, tenant)
        except Exception:
            logger.exception("Failed to set tenant cache for %s", tenant.tenant_code)

    return tenant


def normalize_config(config: dict) -> dict:
    config = dict(config)  # shallow copy
    if "zip_nesting_limit" in config:
        config["max_zip_depth"] = config.pop("zip_nesting_limit")
    return config


async def create_tenant(db: AsyncSession, redis, data: TenantCreate):
    # ensure uniqueness
    existing = await crud.get_by_code(db, data.tenant_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with code '{data.tenant_code}' already exists",
        )

    if data.configuration is None or data.configuration.model_dump() == {}:
        raw_config = get_default_tenant_configs_from_config()
    else:
        raw_config = data.configuration.model_dump()
    normalized_config = normalize_config(raw_config)

    tenant = await crud.create(
        db,
        code=data.tenant_code,
        configuration=normalized_config,
    )

    try:
        create_tenant_folder(tenant.tenant_code)
    except Exception:
        logger.exception("Failed to create folder for tenant %s", tenant.tenant_code)

    if redis:
        try:
            await cache_set_tenant(
                redis, tenant.tenant_code, tenant
            )
        except Exception:
            logger.exception("Failed to cache tenant %s", tenant.tenant_code)

    return tenant


async def update_tenant(db: AsyncSession, redis, code: str, data: TenantUpdate):
    tenant = await crud.get_by_code(db, code)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Prevent code change (TenantUpdate has no code field,just in case)
    if hasattr(data, "code") and data.code is not None and data.code != tenant.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant code is immutable and cannot be changed",
        )

    existing_config = tenant.configuration or {}

    # If configuration is provided, extract only explicitly set fields (partial update)
    if data.configuration is not None:
        update_config = data.configuration.model_dump(exclude_unset=True)
        merged_config = deepcopy(existing_config)
        merged_config.update(update_config)  # shallow merge, replace keys provided
    else:
        merged_config = existing_config

    normalized_config = normalize_config(merged_config)

    updated = await crud.update_configuration(db, tenant.tenant_id, normalized_config)

    if redis:
        try:
            await cache_set_tenant(
                redis, tenant.tenant_code, tenant
            )
        except Exception:
            logger.exception("Failed to update tenant cache %s", tenant.tenant_code)

    return updated


async def _delete_files_from_disk(file_infos):
    for file_id, file_name, tenant_code in file_infos:
        try:
            path = generate_file_path(tenant_code, file_id, file_name)
            delete_file_path(path)
        except Exception:
            logger.exception(
                "Failed to delete file %s for tenant %s", file_id, tenant_code
            )


async def _delete_files_for_tenant(db: AsyncSession, tenant_id: UUID, tenant_code: str):
    file_infos = []
    try:
        infos = await file_crud.list_by_tenant(db, tenant_id)
        file_infos = [(f.id, f.file_name, tenant_code) for f in infos]
        await file_crud.delete_by_tenant(db, tenant_id)
    except Exception:
        logger.exception("Failed to delete files for tenant %s in DB", tenant_id)
    await _delete_files_from_disk(file_infos)


async def delete_tenant(
    db: AsyncSession, redis, code: str, background: Optional[BackgroundTasks] = None
):
    tenant = await crud.get_by_code(db, code)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    tenant_id = tenant.tenant_id
    tenant_code = tenant.tenant_code

    ok = await crud.delete(db, tenant_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant",
        )

    # ✅ Delete tenant cache
    if redis:
        try:
            await cache_delete_tenant(redis, tenant_code)
        except Exception:
            logger.exception("Failed to delete tenant cache %s", tenant_code)

    # ✅ Background task to clean up files and tenant folder
    async def background_cleanup():
        try:
            await _delete_files_for_tenant(db, tenant_id, tenant_code)
        except Exception:
            logger.exception(
                "Background: failed to delete files for tenant %s", tenant_code
            )

        try:
            await asyncio.to_thread(delete_tenant_folder, tenant_code)
        except Exception:
            logger.exception(
                "Background: failed to delete tenant folder %s", tenant_code
            )

    if background:
        background.add_task(background_cleanup)
        return {"detail": "Tenant deleted. Background cleanup started."}
    else:
        await background_cleanup()
        return {"detail": "Tenant deleted and cleaned up."}
