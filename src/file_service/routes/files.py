from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File as UploadFileField, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.cache import get_redis
from file_service.crud.tenant import TenantCRUD
from file_service.schemas import (
    FileResponse as FileResponseSchema,
    FileSearchRequest,
    FileSearchResponse,
    FileUpdateRequest,
)
from file_service.services.file_service import (
    upload_file,
    get_file,
    update_file,
    delete_file,
    search_files,
)


router = APIRouter(prefix="/v2/tenants", tags=["Files"])


@router.post("/{tenant_id}/upload", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
async def upload(
    tenant_id: UUID,
    tag: Optional[str] = None,
    file: UploadFile = UploadFileField(...),
    db: AsyncSession = Depends(get_db),
):
    tenant = await TenantCRUD().get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    data = await upload_file(
        db,
        tenant_id=tenant.tenant_id,
        tenant_code=tenant.tenant_code,
        tenant_config=tenant.configuration,
        file=file,
        tag=tag,
        metadata=None,
    )
    # Map into schema fields
    return {
        "file_id": data["id"],
        "file_name": data["file_name"],
        "media_type": data["media_type"],
        "file_size_bytes": data["file_size_bytes"],
        "tag": data["tag"],
        "file_metadata": data["metadata"],
        "created_at": data["created_at"],
        "modified_at": data["modified_at"],
    }


@router.get("/{tenant_id}/download/{file_id}")
async def download(
    tenant_id: UUID,
    file_id: str,
    inline: bool = True,
    db: AsyncSession = Depends(get_db),
):
    rec = await get_file(db, tenant_id=tenant_id, file_id=file_id)
    disposition = "inline" if inline else "attachment"
    return FileResponse(rec.file_path, media_type=rec.media_type, filename=rec.file_name, headers={"Content-Disposition": f"{disposition}; filename=\"{rec.file_name}\""})


@router.post("/{tenant_id}/files/search", response_model=FileSearchResponse)
async def search(tenant_id: UUID, body: FileSearchRequest, db: AsyncSession = Depends(get_db)):
    items, total = await search_files(
        db,
        tenant_id=tenant_id,
        filters=body.filters.model_dump(exclude_none=True),
        sort_field=body.sort.field,
        sort_order=body.sort.order,
        page=body.pagination.page,
        limit=body.pagination.limit,
    )
    files = [
        {
            "file_id": it.file_id,
            "file_name": it.file_name,
            "media_type": it.media_type,
            "file_size_bytes": it.file_size_bytes,
            "tag": it.tag,
            "file_metadata": it.file_metadata,
            "created_at": it.created_at,
            "modified_at": it.modified_at,
        }
        for it in items
    ]
    total_pages = (total + body.pagination.limit - 1) // body.pagination.limit if body.pagination.limit else 1
    return {
        "files": files,
        "pagination": {
            "page": body.pagination.page,
            "limit": body.pagination.limit,
            "total_pages": total_pages,
            "total_files": total,
        },
    }


@router.get("/{tenant_id}/files/{file_id}", response_model=FileResponseSchema)
async def get_file_details(tenant_id: UUID, file_id: str, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    rec = await get_file(db, tenant_id=tenant_id, file_id=file_id, redis=redis)
    return {
        "file_id": rec.file_id,
        "file_name": rec.file_name,
        "media_type": rec.media_type,
        "file_size_bytes": rec.file_size_bytes,
        "tag": rec.tag,
        "file_metadata": rec.file_metadata,
        "created_at": rec.created_at,
        "modified_at": rec.modified_at,
    }


@router.post("/{tenant_id}/files/{file_id}", response_model=FileResponseSchema)
async def update_file_details(
    tenant_id: UUID,
    file_id: str,
    body: FileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    rec = await update_file(
        db,
        tenant_id=tenant_id,
        file_id=file_id,
        tag=body.tag,
        metadata=body.metadata,
        redis=redis,
    )
    return {
        "file_id": rec.file_id,
        "file_name": rec.file_name,
        "media_type": rec.media_type,
        "file_size_bytes": rec.file_size_bytes,
        "tag": rec.tag,
        "file_metadata": rec.file_metadata,
        "created_at": rec.created_at,
        "modified_at": rec.modified_at,
    }


@router.delete("/{tenant_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_route(tenant_id: UUID, file_id: str, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await delete_file(db, tenant_id=tenant_id, file_id=file_id, redis=redis)
    return None


@router.get("/{tenant_id}/files")
async def list_files_route(tenant_id: UUID, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    from file_service.services.file_service import list_files as list_files_service

    files = await list_files_service(db, tenant_id=tenant_id, redis=redis)
    return {"files": files}


