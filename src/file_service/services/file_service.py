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
    ensure_tenant_directory,
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
from shared.rate_limiter import check_upload_rate_limit
import aiofiles
import anyio
import hashlib
import time
from pathlib import Path
import zipfile


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


def _validate_file_content_vs_extension(file_path: str, expected_ext: str, detected_mime: str) -> str:
    """Validate that file content matches the extension using magic bytes"""
    try:
        # Read first 1KB to detect actual file type
        with open(file_path, 'rb') as f:
            sample = f.read(1024)
        
        # Check magic bytes for common file types
        actual_mime = detected_mime  # fallback to detected
        
        if sample.startswith(b'%PDF-'):
            actual_mime = 'application/pdf'
        elif sample.startswith(b'\x89PNG\r\n\x1a\n'):
            actual_mime = 'image/png'
        elif sample.startswith(b'\xff\xd8\xff'):
            actual_mime = 'image/jpeg'
        elif sample.startswith(b'GIF87a') or sample.startswith(b'GIF89a'):
            actual_mime = 'image/gif'
        elif sample.startswith(b'RIFF') and b'WEBP' in sample[:12]:
            actual_mime = 'image/webp'
        elif sample.startswith(b'PK\x03\x04') and b'word/' in sample[:100]:
            actual_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif sample.startswith(b'PK\x03\x04') and b'xl/' in sample[:100]:
            actual_mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif sample.startswith(b'PK\x03\x04') and b'ppt/' in sample[:100]:
            actual_mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        
        # Check if extension matches content
        if expected_ext == '.pdf' and not actual_mime.startswith('application/pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .pdf does not match actual file type ({actual_mime})"
            )
        elif expected_ext != '.pdf' and actual_mime.startswith('application/pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File appears to be PDF but has extension {expected_ext}"
            )
        
        return actual_mime
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.warning(f"Could not validate file content for {file_path}: {e}")
        return detected_mime


def _validate_zip_depth(file_path: str, max_depth: int) -> None:
    """
    Validate ZIP file depth against tenant configuration.
    Raises HTTPException if ZIP contains nested ZIPs beyond allowed depth.
    """
    if max_depth < 0:
        return  # No validation needed
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            for info in zip_file.infolist():
                # Check if this is a ZIP file (case insensitive)
                if info.filename.lower().endswith('.zip'):
                    # Found a nested ZIP
                    if max_depth == 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="ZIP files with nested ZIPs are not allowed (max_zip_depth=0)"
                        )
                    
                    # For depth > 0, extract and validate recursively
                    if max_depth > 0:
                        # Create a temporary file with a unique name
                        import tempfile
                        import uuid
                        
                        temp_dir = tempfile.gettempdir()
                        temp_filename = f"nested_zip_{uuid.uuid4().hex}.zip"
                        temp_path = os.path.join(temp_dir, temp_filename)
                        
                        try:
                            # Extract the nested ZIP
                            with zip_file.open(info.filename) as source:
                                with open(temp_path, 'wb') as target:
                                    target.write(source.read())
                            
                            # Recursively validate the nested ZIP
                            _validate_zip_depth(temp_path, max_depth - 1)
                        finally:
                            # Clean up temp file
                            try:
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            except Exception as cleanup_error:
                                logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")
                                
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ZIP file format"
        )
    except HTTPException:
        raise  # Re-raise our validation exceptions
    except Exception as e:
        logger.warning(f"Error validating ZIP depth for {file_path}: {e}")
        # Don't fail upload for unexpected errors, just log them
        # This ensures the system remains robust even if ZIP validation has issues
        pass


def _validate_against_config(
    *,
    tenant_config: Dict[str, Any],
    ext: str,
    mime: str,
    size_bytes: int,
    file_path: Optional[str] = None,
):
    """
    Validate file against tenant configuration.
    Checks size, extensions, MIME types, and ZIP depth.
    """
    # Check for empty files
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty files are not allowed"
        )
    
    # Size check (kbytes)
    max_kb = tenant_config.get("max_file_size_kbytes")
    if isinstance(max_kb, int) and max_kb > 0:
        if (size_bytes + 1023) // 1024 > max_kb:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed size of {max_kb}KB",
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
    
    # ZIP depth validation
    if ext == '.zip' and file_path:
        max_zip_depth = tenant_config.get("max_zip_depth", 0)
        if isinstance(max_zip_depth, int):
            _validate_zip_depth(file_path, max_zip_depth)


async def _check_concurrent_upload(redis, tenant_id: UUID, filename: str) -> str:
    """
    Check if same file is being uploaded concurrently.
    Returns a lock key if successful, raises exception if already uploading.
    """
    if not redis:
        return None
    
    # Create a unique key for this upload attempt
    upload_key = f"upload:lock:{tenant_id}:{hashlib.md5(filename.encode()).hexdigest()}"
    
    try:
        # Try to set lock with 30 second expiration
        result = await redis.set(upload_key, "1", ex=30, nx=True)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Same file is already being uploaded. Please wait and try again."
            )
        return upload_key
    except Exception as e:
        logger.warning(f"Could not check concurrent upload: {e}")
        return None


async def _release_upload_lock(redis, lock_key: str):
    """Release the upload lock"""
    if redis and lock_key:
        try:
            await redis.delete(lock_key)
        except Exception as e:
            logger.warning(f"Could not release upload lock: {e}")


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
    # Check rate limit for uploads
    await check_upload_rate_limit(str(tenant_id), redis)
    
    # Check for concurrent uploads of same file
    upload_lock = await _check_concurrent_upload(redis, tenant_id, file.filename or "file")
    
    try:
        # Generate file id and destination path
        file_id = f"CF_FR_{uuid.uuid4().hex[:12]}"
        safe_name = sanitize_filename(file.filename or "file")
        
        # Ensure directory exists first (thread-safe)
        await anyio.to_thread.run_sync(ensure_tenant_directory, tenant_code)
        
        # Generate file path (no directory creation)
        dst_path = generate_file_path(tenant_code, file_id, safe_name)

        # Prepare validation inputs
        ext = _normalize_extension(safe_name)
        media_type = _detect_mime(safe_name, file.content_type)

        # Persist to disk with size check
        size = 0
        # Directory is already created by generate_file_path function
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
                        tenant_config=tenant_config, ext=ext, mime=media_type, size_bytes=size, file_path=dst_path
                    )
                except HTTPException:
                    # cleanup partial
                    try:
                        await out.flush()
                    finally:
                        await anyio.to_thread.run_sync(delete_file_path, dst_path)
                    raise

        # Final validation (covers very small files or exact threshold)
        _validate_against_config(
            tenant_config=tenant_config, ext=ext, mime=media_type, size_bytes=size, file_path=dst_path
        )
        
        # Validate file content matches extension
        actual_mime = _validate_file_content_vs_extension(dst_path, ext, media_type)
        if actual_mime != media_type:
            media_type = actual_mime

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
    
    except Exception as e:
        # Clean up partial file if upload failed
        try:
            if 'dst_path' in locals() and os.path.exists(dst_path):
                os.remove(dst_path)
        except Exception:
            logger.warning(f"Could not clean up partial file {dst_path}")
        
        # Re-raise the original exception
        raise e
    
    finally:
        # Always release the upload lock
        await _release_upload_lock(redis, upload_lock)


async def get_file(db: AsyncSession, *, tenant_id: UUID, file_id: str, redis=None):
    """
    Get file details with cache and error handling.
    Always returns the database model object for consistency.
    """
    # Try cache first
    if redis:
        try:
            cached = await cache_get_file_detail(redis, str(tenant_id), file_id)
            if cached:
                # Cache hit - still fetch from DB to ensure consistency
                # This ensures we always return the model object
                pass
        except Exception as e:
            logger.warning(f"Cache read failed for file {file_id}: {e}")

    # Always fetch from DB to ensure we return the model object
    try:
        rec = await file_crud.get_by_id(db, tenant_id, file_id)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        # Cache result (don't fail if cache is down)
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
            except Exception as e:
                logger.warning(f"Cache write failed for file {file_id}: {e}")
        
        return rec
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Database error getting file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file information"
        )


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
            logger.info(f"Invalidated caches for file {file_id} after update")
    except Exception as e:
        logger.exception(f"Failed to invalidate caches after update: {e}")
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
            logger.info(f"Cache invalidated for deleted file {file_id} in tenant {tenant_id}")
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
                logger.info(f"Cache hit for files list for tenant {tenant_id}")
                return cached
        except Exception as e:
            logger.warning(f"Redis error reading files list: {e}")
    
    logger.info(f"Cache miss - fetching files from DB for tenant {tenant_id}")
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
            logger.info(f"Cached files list for tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"Redis error setting files list: {e}")
    return files


