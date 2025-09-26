from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import json

from .models import Tenant, File
from .schemas import (
    TenantCreate, TenantUpdate, FileUpload, FileUpdate, 
    FileSearchRequest, ValidationStatus, FileStatus
)
from ..shared.cache import redis_client, get_tenant_cache_key, get_file_cache_key, get_file_list_cache_key
from ..shared.utils import validate_tenant_code, cleanup_empty_directories
from ..shared.config import settings
import structlog

logger = structlog.get_logger()


class TenantCRUD:
    """CRUD operations for Tenant model"""
    
    @staticmethod
    async def create(db: AsyncSession, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant"""
        try:
            # Validate tenant code
            if not await validate_tenant_code(tenant_data.code):
                raise ValueError(f"Invalid tenant code: {tenant_data.code}")
            
            # Create tenant object
            tenant = Tenant(
                code=tenant_data.code.lower(),
                name=tenant_data.name,
                description=tenant_data.description,
                is_active=tenant_data.is_active,
                storage_quota_bytes=tenant_data.storage_quota_bytes,
                file_count_limit=tenant_data.file_count_limit,
                created_by=tenant_data.created_by,
                settings=json.dumps(tenant_data.settings) if tenant_data.settings else None
            )
            
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
            
            # Cache the tenant
            await redis_client.set(
                get_tenant_cache_key(tenant.code),
                {
                    "id": tenant.id,
                    "code": tenant.code,
                    "name": tenant.name,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat()
                },
                expire=3600  # 1 hour
            )
            
            logger.info("Tenant created", tenant_id=tenant.id, tenant_code=tenant.code)
            return tenant
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to create tenant", error=str(e), tenant_code=tenant_data.code)
            raise

    @staticmethod
    async def get_by_id(db: AsyncSession, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        try:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get tenant by ID", error=str(e), tenant_id=tenant_id)
            return None

    @staticmethod
    async def get_by_code(db: AsyncSession, tenant_code: str) -> Optional[Tenant]:
        """Get tenant by code with caching"""
        try:
            # Try cache first
            cached_tenant = await redis_client.get(get_tenant_cache_key(tenant_code))
            if cached_tenant:
                # Verify tenant still exists in DB
                result = await db.execute(
                    select(Tenant).where(Tenant.code == tenant_code.lower())
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    return tenant
                else:
                    # Remove stale cache entry
                    await redis_client.delete(get_tenant_cache_key(tenant_code))
            
            # Fetch from database
            result = await db.execute(
                select(Tenant).where(Tenant.code == tenant_code.lower())
            )
            tenant = result.scalar_one_or_none()
            
            if tenant:
                # Cache the result
                await redis_client.set(
                    get_tenant_cache_key(tenant_code),
                    {
                        "id": tenant.id,
                        "code": tenant.code,
                        "name": tenant.name,
                        "is_active": tenant.is_active,
                        "created_at": tenant.created_at.isoformat()
                    },
                    expire=3600
                )
            
            return tenant
            
        except Exception as e:
            logger.error("Failed to get tenant by code", error=str(e), tenant_code=tenant_code)
            return None

    @staticmethod
    async def get_all(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = True
    ) -> List[Tenant]:
        """Get all tenants with pagination"""
        try:
            query = select(Tenant)
            if active_only:
                query = query.where(Tenant.is_active == True)
            
            query = query.offset(skip).limit(limit).order_by(Tenant.created_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get tenants", error=str(e))
            return []

    @staticmethod
    async def update(db: AsyncSession, tenant_id: str, tenant_data: TenantUpdate) -> Optional[Tenant]:
        """Update tenant"""
        try:
            # Get existing tenant
            tenant = await TenantCRUD.get_by_id(db, tenant_id)
            if not tenant:
                return None
            
            # Update fields
            update_data = tenant_data.model_dump(exclude_unset=True)
            if update_data.get('settings'):
                update_data['settings'] = json.dumps(update_data['settings'])
            
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(**update_data)
                .returning(Tenant)
            )
            
            result = await db.execute(stmt)
            updated_tenant = result.scalar_one_or_none()
            await db.commit()
            
            if updated_tenant:
                # Update cache
                await redis_client.delete(get_tenant_cache_key(updated_tenant.code))
                logger.info("Tenant updated", tenant_id=tenant_id)
            
            return updated_tenant
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to update tenant", error=str(e), tenant_id=tenant_id)
            return None

    @staticmethod
    async def delete(db: AsyncSession, tenant_id: str) -> bool:
        """Delete tenant and cleanup associated data"""
        try:
            # Get tenant first
            tenant = await TenantCRUD.get_by_id(db, tenant_id)
            if not tenant:
                return False
            
            # Delete all associated files first
            await db.execute(delete(File).where(File.tenant_id == tenant_id))
            
            # Delete tenant
            await db.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await db.commit()
            
            # Cleanup cache
            await redis_client.delete(get_tenant_cache_key(tenant.code))
            
            # Cleanup storage directories
            await cleanup_empty_directories(settings.storage_base_path, tenant.code)
            
            logger.info("Tenant deleted", tenant_id=tenant_id, tenant_code=tenant.code)
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to delete tenant", error=str(e), tenant_id=tenant_id)
            return False

    @staticmethod
    async def get_stats(db: AsyncSession, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant statistics"""
        try:
            # Get file count and total size
            file_stats = await db.execute(
                select(
                    func.count(File.id).label('file_count'),
                    func.coalesce(func.sum(File.file_size), 0).label('total_size'),
                    func.max(File.uploaded_at).label('last_upload')
                ).where(
                    and_(File.tenant_id == tenant_id, File.is_deleted == False)
                )
            )
            stats = file_stats.first()
            
            # Get tenant details
            tenant = await TenantCRUD.get_by_id(db, tenant_id)
            if not tenant:
                return None
            
            # Calculate usage percentages
            storage_usage_pct = None
            if tenant.storage_quota_bytes:
                storage_usage_pct = (stats.total_size / tenant.storage_quota_bytes) * 100
            
            file_count_usage_pct = None
            if tenant.file_count_limit:
                file_count_usage_pct = (stats.file_count / tenant.file_count_limit) * 100
            
            return {
                "tenant_id": tenant_id,
                "tenant_code": tenant.code,
                "file_count": stats.file_count,
                "total_storage_bytes": stats.total_size,
                "storage_quota_bytes": tenant.storage_quota_bytes,
                "file_count_limit": tenant.file_count_limit,
                "storage_usage_percentage": storage_usage_pct,
                "file_count_usage_percentage": file_count_usage_pct,
                "last_upload": stats.last_upload
            }
            
        except Exception as e:
            logger.error("Failed to get tenant stats", error=str(e), tenant_id=tenant_id)
            return None


class FileCRUD:
    """CRUD operations for File model"""
    
    @staticmethod
    async def create(db: AsyncSession, file_data: Dict[str, Any]) -> File:
        """Create a new file record"""
        try:
            file_obj = File(**file_data)
            db.add(file_obj)
            await db.commit()
            await db.refresh(file_obj)
            
            # Cache file metadata
            await redis_client.set(
                get_file_cache_key(file_obj.tenant_code, file_obj.id),
                {
                    "id": file_obj.id,
                    "original_filename": file_obj.original_filename,
                    "file_size": file_obj.file_size,
                    "mime_type": file_obj.mime_type,
                    "status": file_obj.status,
                    "uploaded_at": file_obj.uploaded_at.isoformat()
                },
                expire=1800  # 30 minutes
            )
            
            # Invalidate file list cache
            cache_pattern = f"files:{file_obj.tenant_code}:*"
            # In production, you might want to use SCAN to find and delete matching keys
            
            logger.info("File record created", file_id=file_obj.id, tenant_code=file_obj.tenant_code)
            return file_obj
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to create file record", error=str(e))
            raise

    @staticmethod
    async def get_by_id(db: AsyncSession, file_id: str) -> Optional[File]:
        """Get file by ID"""
        try:
            result = await db.execute(
                select(File)
                .options(selectinload(File.tenant))
                .where(File.id == file_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get file by ID", error=str(e), file_id=file_id)
            return None

    @staticmethod
    async def get_by_tenant(
        db: AsyncSession,
        tenant_code: str,
        skip: int = 0,
        limit: int = 10,
        include_deleted: bool = False
    ) -> Tuple[List[File], int]:
        """Get files by tenant with pagination"""
        try:
            # Try cache first for first page
            if skip == 0 and not include_deleted:
                cache_key = get_file_list_cache_key(tenant_code, 1, limit)
                cached_result = await redis_client.get(cache_key)
                if cached_result:
                    return cached_result["files"], cached_result["total_count"]
            
            # Build query
            query = select(File).where(File.tenant_code == tenant_code.lower())
            if not include_deleted:
                query = query.where(File.is_deleted == False)
            
            # Get total count
            count_query = select(func.count(File.id)).where(File.tenant_code == tenant_code.lower())
            if not include_deleted:
                count_query = count_query.where(File.is_deleted == False)
            
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()
            
            # Get files
            query = query.offset(skip).limit(limit).order_by(File.uploaded_at.desc())
            result = await db.execute(query)
            files = result.scalars().all()
            
            # Cache first page
            if skip == 0 and not include_deleted:
                cache_key = get_file_list_cache_key(tenant_code, 1, limit)
                cache_data = {
                    "files": [
                        {
                            "id": f.id,
                            "original_filename": f.original_filename,
                            "file_size": f.file_size,
                            "mime_type": f.mime_type,
                            "status": f.status,
                            "uploaded_at": f.uploaded_at.isoformat()
                        }
                        for f in files
                    ],
                    "total_count": total_count
                }
                await redis_client.set(cache_key, cache_data, expire=600)  # 10 minutes
            
            return files, total_count
            
        except Exception as e:
            logger.error("Failed to get files by tenant", error=str(e), tenant_code=tenant_code)
            return [], 0

    @staticmethod
    async def search_files(db: AsyncSession, search_params: FileSearchRequest) -> Tuple[List[File], int]:
        """Search files with advanced filtering"""
        try:
            # Build base query
            query = select(File)
            count_query = select(func.count(File.id))
            
            conditions = []
            
            # Tenant filter
            if search_params.tenant_code:
                conditions.append(File.tenant_code == search_params.tenant_code.lower())
            
            # Filename pattern
            if search_params.filename_pattern:
                conditions.append(File.original_filename.ilike(f"%{search_params.filename_pattern}%"))
            
            # File extension
            if search_params.file_extension:
                conditions.append(File.file_extension == search_params.file_extension.lower())
            
            # Status
            if search_params.status:
                conditions.append(File.status == search_params.status)
            
            # Validation status
            if search_params.validation_status:
                conditions.append(File.validation_status == search_params.validation_status)
            
            # Date range
            if search_params.uploaded_after:
                conditions.append(File.uploaded_at >= search_params.uploaded_after)
            if search_params.uploaded_before:
                conditions.append(File.uploaded_at <= search_params.uploaded_before)
            
            # Size range
            if search_params.min_size:
                conditions.append(File.file_size >= search_params.min_size)
            if search_params.max_size:
                conditions.append(File.file_size <= search_params.max_size)
            
            # Uploaded by
            if search_params.uploaded_by:
                conditions.append(File.uploaded_by == search_params.uploaded_by)
            
            # Apply conditions
            if conditions:
                where_clause = and_(*conditions)
                query = query.where(where_clause)
                count_query = count_query.where(where_clause)
            
            # Get total count
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply sorting
            sort_column = getattr(File, search_params.sort_by, File.uploaded_at)
            if search_params.sort_order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))
            
            # Apply pagination
            skip = (search_params.page - 1) * search_params.limit
            query = query.offset(skip).limit(search_params.limit)
            
            # Execute query
            result = await db.execute(query)
            files = result.scalars().all()
            
            return files, total_count
            
        except Exception as e:
            logger.error("Failed to search files", error=str(e))
            return [], 0

    @staticmethod
    async def update(db: AsyncSession, file_id: str, file_data: FileUpdate) -> Optional[File]:
        """Update file metadata"""
        try:
            # Get existing file
            file_obj = await FileCRUD.get_by_id(db, file_id)
            if not file_obj:
                return None
            
            # Update fields
            update_data = file_data.model_dump(exclude_unset=True)
            
            # Handle JSON fields
            if 'validation_details' in update_data and update_data['validation_details']:
                update_data['validation_details'] = json.dumps(update_data['validation_details'])
            if 'processing_status' in update_data and update_data['processing_status']:
                update_data['processing_status'] = json.dumps(update_data['processing_status'])
            
            stmt = (
                update(File)
                .where(File.id == file_id)
                .values(**update_data)
                .returning(File)
            )
            
            result = await db.execute(stmt)
            updated_file = result.scalar_one_or_none()
            await db.commit()
            
            if updated_file:
                # Update cache
                await redis_client.delete(get_file_cache_key(updated_file.tenant_code, file_id))
                logger.info("File updated", file_id=file_id)
            
            return updated_file
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to update file", error=str(e), file_id=file_id)
            return None

    @staticmethod
    async def delete(db: AsyncSession, file_id: str, permanent: bool = False) -> bool:
        """Delete or soft delete file"""
        try:
            file_obj = await FileCRUD.get_by_id(db, file_id)
            if not file_obj:
                return False
            
            if permanent:
                # Permanent deletion
                await db.execute(delete(File).where(File.id == file_id))
            else:
                # Soft deletion
                await db.execute(
                    update(File)
                    .where(File.id == file_id)
                    .values(is_deleted=True, deleted_at=datetime.utcnow())
                )
            
            await db.commit()
            
            # Clear cache
            await redis_client.delete(get_file_cache_key(file_obj.tenant_code, file_id))
            
            logger.info("File deleted", file_id=file_id, permanent=permanent)
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to delete file", error=str(e), file_id=file_id)
            return False

    @staticmethod
    async def bulk_delete(
        db: AsyncSession, 
        file_ids: List[str], 
        permanent: bool = False
    ) -> Tuple[List[str], List[str]]:
        """Bulk delete files"""
        try:
            successful_deletes = []
            failed_deletes = []
            
            for file_id in file_ids:
                if await FileCRUD.delete(db, file_id, permanent):
                    successful_deletes.append(file_id)
                else:
                    failed_deletes.append(file_id)
            
            return successful_deletes, failed_deletes
            
        except Exception as e:
            logger.error("Failed bulk delete", error=str(e))
            return [], file_ids

    @staticmethod
    async def get_file_stats(db: AsyncSession, tenant_code: Optional[str] = None) -> Dict[str, Any]:
        """Get file statistics"""
        try:
            # Base query
            query = select(
                func.count(File.id).label('total_files'),
                func.coalesce(func.sum(File.file_size), 0).label('total_size'),
                func.avg(File.file_size).label('avg_size'),
                func.max(File.file_size).label('max_size'),
                func.min(File.file_size).label('min_size')
            )
            
            if tenant_code:
                query = query.where(File.tenant_code == tenant_code.lower())
            
            query = query.where(File.is_deleted == False)
            
            result = await db.execute(query)
            stats = result.first()
            
            # Get status breakdown
            status_query = select(
                File.status,
                func.count(File.id).label('count')
            ).where(File.is_deleted == False)
            
            if tenant_code:
                status_query = status_query.where(File.tenant_code == tenant_code.lower())
            
            status_query = status_query.group_by(File.status)
            status_result = await db.execute(status_query)
            status_breakdown = {row.status: row.count for row in status_result}
            
            # Get extension breakdown
            ext_query = select(
                File.file_extension,
                func.count(File.id).label('count')
            ).where(File.is_deleted == False)
            
            if tenant_code:
                ext_query = ext_query.where(File.tenant_code == tenant_code.lower())
            
            ext_query = ext_query.group_by(File.file_extension).limit(10)
            ext_result = await db.execute(ext_query)
            extension_breakdown = {row.file_extension: row.count for row in ext_result}
            
            return {
                "total_files": stats.total_files,
                "total_size_bytes": stats.total_size,
                "average_file_size": float(stats.avg_size or 0),
                "largest_file_size": stats.max_size or 0,
                "smallest_file_size": stats.min_size or 0,
                "files_by_status": status_breakdown,
                "files_by_extension": extension_breakdown
            }
            
        except Exception as e:
            logger.error("Failed to get file stats", error=str(e))
            return {}
