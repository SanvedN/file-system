from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import mimetypes

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from file_service.crud.file import FileCRUD
from file_service.crud.tenant import TenantCRUD
from file_service.utils import (
    generate_file_path,
    delete_file_path,
    sanitize_filename,
)
from shared.utils import setup_logger
from shared.cache import (
    cache_get_files_list,
    cache_set_files_list,
    cache_delete_files_list,
    cache_get_file_detail,
    cache_set_file_detail,
    cache_delete_file_detail,
)
import aiofiles
import anyio


logger = setup_logger()
file_crud = FileCRUD()
tenant_crud = TenantCRUD()


async def ensure_tenant(db: AsyncSession, tenant_id: UUID):
    tenant = await tenant_crud.get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _normalize_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _detect_mime(filename: str, fallback: Optional[str]) -> str:
    if fallback:
        return fallback
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _validate_against_config(
    *,
    tenant_config: Dict[str, Any],
    ext: str,
    mime: str,
    size_bytes: int,
):
    # Size check (kbytes)
    max_kb = tenant_config.get("max_file_size_kbytes")
    if isinstance(max_kb, int) and max_kb > 0:
        if (size_bytes + 1023) // 1024 > max_kb:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds maximum allowed size",
            )

    # Normalize lists
    allowed_exts = [e.lower() for e in tenant_config.get("allowed_extensions", []) or []]
    forbidden_exts = [e.lower() for e in tenant_config.get("forbidden_extensions", []) or []]
    allowed_mimes = [m.lower() for m in tenant_config.get("allowed_mime_types", []) or []]
    forbidden_mimes = [m.lower() for m in tenant_config.get("forbidden_mime_types", []) or []]

    # Extension checks
    if ext in forbidden_exts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension is forbidden")
    # Per instruction: reject if not present in allowed list
    if allowed_exts and ext not in allowed_exts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension not allowed")
    if not allowed_exts:
        # If not there in both forbidden and accepted lists, reject
        # i.e., when allowed list empty, treat as not accepted
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File extension not allowed")

    # MIME checks
    if mime.lower() in forbidden_mimes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MIME type is forbidden")
    if allowed_mimes and mime.lower() not in allowed_mimes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MIME type not allowed")
    if not allowed_mimes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MIME type not allowed")


async def upload_file(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    tenant_code: str,
    tenant_config: Dict[str, Any],
    file: UploadFile,
    tag: Optional[str],
    metadata: Optional[Dict[str, Any]],
    redis=None,
) -> Dict[str, Any]:
    # Generate file id and destination path
    file_id = f"CF_FR_{uuid.uuid4().hex[:12]}"
    safe_name = sanitize_filename(file.filename or "file")
    dst_path = generate_file_path(tenant_code, file_id, safe_name)

    # Prepare validation inputs
    ext = _normalize_extension(safe_name)
    media_type = _detect_mime(safe_name, file.content_type)

    # Persist to disk with size check
    size = 0
    await anyio.to_thread.run_sync(os.makedirs, os.path.dirname(dst_path), True)
    async with aiofiles.open(dst_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            await out.write(chunk)

            # Early size validation
            try:
                _validate_against_config(
                    tenant_config=tenant_config, ext=ext, mime=media_type, size_bytes=size
                )
            except HTTPException:
                # cleanup partial
                try:
                    await out.flush()
                finally:
                    delete_file_path(dst_path)
                raise

    # Final validation (covers very small files or exact threshold)
    _validate_against_config(
        tenant_config=tenant_config, ext=ext, mime=media_type, size_bytes=size
    )

    rec = await file_crud.create(
        db,
        tenant_id=tenant_id,
        file_id=file_id,
        file_name=safe_name,
        file_path=dst_path,
        media_type=media_type,
        file_size_bytes=size,
        tag=tag,
        file_metadata=metadata,
    )

    # Invalidate caches for tenant list and this file detail
    try:
        if redis:
            await cache_delete_files_list(redis, str(tenant_id))
            await cache_delete_file_detail(redis, str(tenant_id), file_id)
    except Exception:
        logger.exception("Failed to invalidate caches after upload")

    return {
        "id": rec.file_id,
        "file_name": rec.file_name,
        "media_type": rec.media_type,
        "file_size_bytes": rec.file_size_bytes,
        "tag": rec.tag,
        "metadata": rec.file_metadata,
        "created_at": rec.created_at,
        "modified_at": rec.modified_at,
    }


async def get_file(db: AsyncSession, *, tenant_id: UUID, file_id: str, redis=None):
    # Try cache
    if redis:
        cached = await cache_get_file_detail(redis, str(tenant_id), file_id)
        if cached:
            return cached
    rec = await file_crud.get_by_id(db, tenant_id, file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if redis:
        try:
            await cache_set_file_detail(
                redis,
                str(tenant_id),
                file_id,
                {
                    "file_id": rec.file_id,
                    "file_name": rec.file_name,
                    "media_type": rec.media_type,
                    "file_size_bytes": rec.file_size_bytes,
                    "tag": rec.tag,
                    "file_metadata": rec.file_metadata,
                    "created_at": rec.created_at.isoformat() if rec.created_at else None,
                    "modified_at": rec.modified_at.isoformat() if rec.modified_at else None,
                    "file_path": rec.file_path,
                },
            )
        except Exception:
            logger.exception("Failed to cache file detail %s", file_id)
    return rec


async def update_file(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    file_id: str,
    tag: Optional[str],
    metadata: Optional[Dict[str, Any]],
    redis=None,
):
    rec = await file_crud.update_mutable(
        db, tenant_id=tenant_id, file_id=file_id, tag=tag, file_metadata=metadata
    )
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    # Invalidate caches
    try:
        if redis:
            await cache_delete_file_detail(redis, str(tenant_id), file_id)
            await cache_delete_files_list(redis, str(tenant_id))
    except Exception:
        logger.exception("Failed to invalidate caches after update")
    return rec


async def delete_file(db: AsyncSession, *, tenant_id: UUID, file_id: str, redis=None):
    rec = await file_crud.delete(db, tenant_id=tenant_id, file_id=file_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    # Remove from disk
    await anyio.to_thread.run_sync(delete_file_path, rec.file_path)
    # Invalidate caches
    if redis:
        try:
            await cache_delete_file_detail(redis, str(tenant_id), file_id)
            await cache_delete_files_list(redis, str(tenant_id))
        except Exception:
            logger.exception("Failed to invalidate caches for delete %s", file_id)
    return True


async def search_files(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    filters: Dict[str, Any],
    sort_field: Optional[str],
    sort_order: str,
    page: int,
    limit: int,
):
    items, total = await file_crud.search(
        db,
        tenant_id=tenant_id,
        filters=filters,
        sort_field=sort_field,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )
    return items, total


async def list_files(db: AsyncSession, *, tenant_id: UUID, redis=None):
    if redis:
        try:
            cached = await cache_get_files_list(redis, str(tenant_id))
            if cached is not None:
                return cached
        except Exception:
            logger.exception("Redis error reading files list")
    items = await file_crud.list_by_tenant(db, tenant_id)
    files = [
        {
            "file_id": it.file_id,
            "file_name": it.file_name,
            "media_type": it.media_type,
            "file_size_bytes": it.file_size_bytes,
            "tag": it.tag,
            "file_metadata": it.file_metadata,
            "created_at": it.created_at.isoformat() if it.created_at else None,
            "modified_at": it.modified_at.isoformat() if it.modified_at else None,
        }
        for it in items
    ]
    if redis:
        try:
            await cache_set_files_list(redis, str(tenant_id), files)
        except Exception:
            logger.exception("Redis error setting files list")
    return files


