import os
import tempfile
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .crud import TenantCRUD, FileCRUD
from .models import Tenant, File
from .schemas import (
    TenantCreate, TenantUpdate, TenantResponse, TenantStats,
    FileUpload, FileResponse, FileSearchRequest, FileListResponse,
    BulkDeleteRequest, BulkDeleteResponse, FileValidationResult
)
from ..shared.utils import (
    AsyncFileValidator, generate_storage_path, generate_unique_filename,
    save_uploaded_file, delete_file, get_file_mime_type, generate_file_hash,
    StorageError, FileValidationError
)
from ..shared.config import settings
from ..shared.cache import redis_client
import structlog

logger = structlog.get_logger()


class TenantService:
    """Business logic for tenant management"""
    
    @staticmethod
    async def create_tenant(db: AsyncSession, tenant_data: TenantCreate) -> TenantResponse:
        """Create a new tenant with validation"""
        try:
            # Check if tenant code already exists
            existing_tenant = await TenantCRUD.get_by_code(db, tenant_data.code)
            if existing_tenant:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tenant with code '{tenant_data.code}' already exists"
                )
            
            # Create tenant
            tenant = await TenantCRUD.create(db, tenant_data)
            
            # Create storage directory
            storage_path = generate_storage_path(tenant.code)
            os.makedirs(storage_path, exist_ok=True)
            
            # Convert to response model
            return TenantResponse(
                id=tenant.id,
                code=tenant.code,
                name=tenant.name,
                description=tenant.description,
                is_active=tenant.is_active,
                storage_quota_bytes=tenant.storage_quota_bytes,
                file_count_limit=tenant.file_count_limit,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
                created_by=tenant.created_by,
                settings=tenant.settings
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to create tenant", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to create tenant")

    @staticmethod
    async def get_tenant(db: AsyncSession, tenant_code: str) -> Optional[TenantResponse]:
        """Get tenant by code"""
        tenant = await TenantCRUD.get_by_code(db, tenant_code)
        if not tenant:
            return None
        
        return TenantResponse(
            id=tenant.id,
            code=tenant.code,
            name=tenant.name,
            description=tenant.description,
            is_active=tenant.is_active,
            storage_quota_bytes=tenant.storage_quota_bytes,
            file_count_limit=tenant.file_count_limit,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            settings=tenant.settings
        )

    @staticmethod
    async def update_tenant(
        db: AsyncSession, 
        tenant_code: str, 
        tenant_data: TenantUpdate
    ) -> Optional[TenantResponse]:
        """Update tenant"""
        tenant = await TenantCRUD.get_by_code(db, tenant_code)
        if not tenant:
            return None
        
        updated_tenant = await TenantCRUD.update(db, tenant.id, tenant_data)
        if not updated_tenant:
            return None
        
        return TenantResponse(
            id=updated_tenant.id,
            code=updated_tenant.code,
            name=updated_tenant.name,
            description=updated_tenant.description,
            is_active=updated_tenant.is_active,
            storage_quota_bytes=updated_tenant.storage_quota_bytes,
            file_count_limit=updated_tenant.file_count_limit,
            created_at=updated_tenant.created_at,
            updated_at=updated_tenant.updated_at,
            created_by=updated_tenant.created_by,
            settings=updated_tenant.settings
        )

    @staticmethod
    async def delete_tenant(db: AsyncSession, tenant_code: str) -> bool:
        """Delete tenant and all associated data"""
        tenant = await TenantCRUD.get_by_code(db, tenant_code)
        if not tenant:
            return False
        
        return await TenantCRUD.delete(db, tenant.id)

    @staticmethod
    async def get_tenant_stats(db: AsyncSession, tenant_code: str) -> Optional[TenantStats]:
        """Get tenant statistics"""
        tenant = await TenantCRUD.get_by_code(db, tenant_code)
        if not tenant:
            return None
        
        stats_data = await TenantCRUD.get_stats(db, tenant.id)
        if not stats_data:
            return None
        
        return TenantStats(**stats_data)

    @staticmethod
    async def check_tenant_quotas(db: AsyncSession, tenant_code: str) -> Dict[str, Any]:
        """Check if tenant is within quotas"""
        tenant = await TenantCRUD.get_by_code(db, tenant_code)
        if not tenant:
            return {"error": "Tenant not found"}
        
        stats_data = await TenantCRUD.get_stats(db, tenant.id)
        if not stats_data:
            return {"error": "Failed to get stats"}
        
        quota_status = {
            "within_storage_quota": True,
            "within_file_count_quota": True,
            "storage_usage_percentage": stats_data.get("storage_usage_percentage", 0),
            "file_count_usage_percentage": stats_data.get("file_count_usage_percentage", 0)
        }
        
        if tenant.storage_quota_bytes and stats_data["total_storage_bytes"] > tenant.storage_quota_bytes:
            quota_status["within_storage_quota"] = False
        
        if tenant.file_count_limit and stats_data["file_count"] > tenant.file_count_limit:
            quota_status["within_file_count_quota"] = False
        
        return quota_status


class FileService:
    """Business logic for file management"""
    
    @staticmethod
    async def upload_file(
        db: AsyncSession,
        file: UploadFile,
        tenant_code: str,
        uploaded_by: Optional[str] = None,
        upload_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> FileResponse:
        """Upload and process a file"""
        try:
            # Validate tenant exists and is active
            tenant = await TenantCRUD.get_by_code(db, tenant_code)
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            if not tenant.is_active:
                raise HTTPException(status_code=400, detail="Tenant is not active")
            
            # Check quotas
            quota_status = await TenantService.check_tenant_quotas(db, tenant_code)
            if not quota_status.get("within_file_count_quota", True):
                raise HTTPException(status_code=413, detail="File count quota exceeded")
            
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Check storage quota
            if tenant.storage_quota_bytes:
                stats_data = await TenantCRUD.get_stats(db, tenant.id)
                if stats_data and (stats_data["total_storage_bytes"] + file_size) > tenant.storage_quota_bytes:
                    raise HTTPException(status_code=413, detail="Storage quota exceeded")
            
            # Create temporary file for validation
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Validate file
                is_valid, validation_errors = await AsyncFileValidator.validate_file(
                    filename=file.filename,
                    file_size=file_size,
                    temp_file_path=tmp_file_path
                )
                
                if not is_valid:
                    raise FileValidationError(f"File validation failed: {', '.join(validation_errors)}")
                
                # Generate unique filename and storage path
                unique_filename = generate_unique_filename(file.filename)
                storage_dir = generate_storage_path(tenant_code)
                file_path = os.path.join(storage_dir, unique_filename)
                
                # Save file to storage
                await save_uploaded_file(file_content, file_path)
                
                # Get file metadata
                file_extension = Path(file.filename).suffix.lower()
                mime_type = await get_file_mime_type(file_path)
                file_hash = await generate_file_hash(file_path)
                
                # Create file record
                file_data = {
                    "tenant_id": tenant.id,
                    "tenant_code": tenant_code.lower(),
                    "original_filename": file.filename,
                    "stored_filename": unique_filename,
                    "file_path": file_path,
                    "file_size": file_size,
                    "mime_type": mime_type,
                    "file_extension": file_extension,
                    "file_hash": file_hash,
                    "status": "uploaded",
                    "validation_status": "passed",
                    "validation_details": None,
                    "uploaded_by": uploaded_by,
                    "upload_ip": upload_ip,
                    "user_agent": user_agent
                }
                
                file_obj = await FileCRUD.create(db, file_data)
                
                logger.info(
                    "File uploaded successfully",
                    file_id=file_obj.id,
                    tenant_code=tenant_code,
                    filename=file.filename,
                    size=file_size
                )
                
                return FileResponse(
                    id=file_obj.id,
                    tenant_id=file_obj.tenant_id,
                    tenant_code=file_obj.tenant_code,
                    original_filename=file_obj.original_filename,
                    stored_filename=file_obj.stored_filename,
                    file_path=file_obj.file_path,
                    file_size=file_obj.file_size,
                    mime_type=file_obj.mime_type,
                    file_extension=file_obj.file_extension,
                    file_hash=file_obj.file_hash,
                    status=file_obj.status,
                    is_deleted=file_obj.is_deleted,
                    uploaded_at=file_obj.uploaded_at,
                    processed_at=file_obj.processed_at,
                    deleted_at=file_obj.deleted_at,
                    last_accessed=file_obj.last_accessed,
                    uploaded_by=file_obj.uploaded_by,
                    upload_ip=file_obj.upload_ip,
                    validation_status=file_obj.validation_status,
                    validation_details=file_obj.validation_details,
                    processing_status=file_obj.processing_status,
                    error_message=file_obj.error_message,
                    retry_count=file_obj.retry_count,
                    display_size=file_obj.get_display_size(),
                    is_zip_file=file_obj.is_zip_file
                )
                
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except HTTPException:
            raise
        except FileValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except StorageError as e:
            raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
        except Exception as e:
            logger.error("Failed to upload file", error=str(e), tenant_code=tenant_code)
            raise HTTPException(status_code=500, detail="Failed to upload file")

    @staticmethod
    async def get_file(db: AsyncSession, file_id: str) -> Optional[FileResponse]:
        """Get file by ID"""
        file_obj = await FileCRUD.get_by_id(db, file_id)
        if not file_obj:
            return None
        
        # Update last accessed
        await FileCRUD.update(db, file_id, {"last_accessed": datetime.utcnow()})
        
        return FileResponse(
            id=file_obj.id,
            tenant_id=file_obj.tenant_id,
            tenant_code=file_obj.tenant_code,
            original_filename=file_obj.original_filename,
            stored_filename=file_obj.stored_filename,
            file_path=file_obj.file_path,
            file_size=file_obj.file_size,
            mime_type=file_obj.mime_type,
            file_extension=file_obj.file_extension,
            file_hash=file_obj.file_hash,
            status=file_obj.status,
            is_deleted=file_obj.is_deleted,
            uploaded_at=file_obj.uploaded_at,
            processed_at=file_obj.processed_at,
            deleted_at=file_obj.deleted_at,
            last_accessed=file_obj.last_accessed,
            uploaded_by=file_obj.uploaded_by,
            upload_ip=file_obj.upload_ip,
            validation_status=file_obj.validation_status,
            validation_details=file_obj.validation_details,
            processing_status=file_obj.processing_status,
            error_message=file_obj.error_message,
            retry_count=file_obj.retry_count,
            display_size=file_obj.get_display_size(),
            is_zip_file=file_obj.is_zip_file
        )

    @staticmethod
    async def get_files_by_tenant(
        db: AsyncSession,
        tenant_code: str,
        page: int = 1,
        limit: int = 10,
        include_deleted: bool = False
    ) -> FileListResponse:
        """Get files for a tenant with pagination"""
        skip = (page - 1) * limit
        files, total_count = await FileCRUD.get_by_tenant(db, tenant_code, skip, limit, include_deleted)
        
        file_metadata = [
            {
                "id": f.id,
                "original_filename": f.original_filename,
                "file_size": f.file_size,
                "mime_type": f.mime_type,
                "file_extension": f.file_extension,
                "uploaded_at": f.uploaded_at,
                "status": f.status,
                "validation_status": f.validation_status,
                "display_size": f.get_display_size()
            }
            for f in files
        ]
        
        return FileListResponse(
            files=file_metadata,
            total_count=total_count,
            page=page,
            limit=limit,
            has_next=(skip + limit) < total_count,
            has_previous=page > 1
        )

    @staticmethod
    async def search_files(db: AsyncSession, search_params: FileSearchRequest) -> FileListResponse:
        """Search files with advanced filtering"""
        files, total_count = await FileCRUD.search_files(db, search_params)
        
        file_metadata = [
            {
                "id": f.id,
                "original_filename": f.original_filename,
                "file_size": f.file_size,
                "mime_type": f.mime_type,
                "file_extension": f.file_extension,
                "uploaded_at": f.uploaded_at,
                "status": f.status,
                "validation_status": f.validation_status,
                "display_size": f.get_display_size()
            }
            for f in files
        ]
        
        return FileListResponse(
            files=file_metadata,
            total_count=total_count,
            page=search_params.page,
            limit=search_params.limit,
            has_next=((search_params.page - 1) * search_params.limit + search_params.limit) < total_count,
            has_previous=search_params.page > 1
        )

    @staticmethod
    async def delete_file(db: AsyncSession, file_id: str, permanent: bool = False) -> bool:
        """Delete a file"""
        file_obj = await FileCRUD.get_by_id(db, file_id)
        if not file_obj:
            return False
        
        # Delete from database
        success = await FileCRUD.delete(db, file_id, permanent)
        
        # If permanent deletion or soft delete is successful, delete physical file
        if success and (permanent or not file_obj.is_deleted):
            try:
                await delete_file(file_obj.file_path)
            except Exception as e:
                logger.error("Failed to delete physical file", error=str(e), file_path=file_obj.file_path)
        
        return success

    @staticmethod
    async def bulk_delete_files(
        db: AsyncSession, 
        request: BulkDeleteRequest
    ) -> BulkDeleteResponse:
        """Bulk delete files"""
        successful_deletes = []
        failed_deletions = []
        
        for file_id in request.file_ids:
            try:
                if await FileService.delete_file(db, file_id, request.permanent):
                    successful_deletes.append(file_id)
                else:
                    failed_deletions.append({"file_id": file_id, "error": "File not found or already deleted"})
            except Exception as e:
                failed_deletions.append({"file_id": file_id, "error": str(e)})
        
        return BulkDeleteResponse(
            deleted_files=successful_deletes,
            failed_deletions=failed_deletions,
            total_deleted=len(successful_deletes),
            total_failed=len(failed_deletions)
        )

    @staticmethod
    async def download_file(db: AsyncSession, file_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Get file path and filename for download"""
        file_obj = await FileCRUD.get_by_id(db, file_id)
        if not file_obj or file_obj.is_deleted:
            return None, None
        
        # Update last accessed
        await FileCRUD.update(db, file_id, {"last_accessed": datetime.utcnow()})
        
        return file_obj.file_path, file_obj.original_filename

    @staticmethod
    async def validate_files(db: AsyncSession, file_ids: List[str]) -> Dict[str, FileValidationResult]:
        """Validate multiple files"""
        results = {}
        
        for file_id in file_ids:
            try:
                file_obj = await FileCRUD.get_by_id(db, file_id)
                if not file_obj:
                    results[file_id] = FileValidationResult(
                        is_valid=False,
                        errors=["File not found"],
                        warnings=[],
                        file_info=None
                    )
                    continue
                
                # Re-validate the file
                is_valid, validation_errors = await AsyncFileValidator.validate_file(
                    filename=file_obj.original_filename,
                    file_size=file_obj.file_size,
                    temp_file_path=file_obj.file_path
                )
                
                results[file_id] = FileValidationResult(
                    is_valid=is_valid,
                    errors=validation_errors,
                    warnings=[],
                    file_info={
                        "filename": file_obj.original_filename,
                        "size": file_obj.file_size,
                        "mime_type": file_obj.mime_type,
                        "extension": file_obj.file_extension
                    }
                )
                
            except Exception as e:
                results[file_id] = FileValidationResult(
                    is_valid=False,
                    errors=[f"Validation error: {str(e)}"],
                    warnings=[],
                    file_info=None
                )
        
        return results
