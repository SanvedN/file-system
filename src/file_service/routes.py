from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import structlog

from .services import TenantService, FileService
from .schemas import (
    TenantCreate, TenantUpdate, TenantResponse, TenantStats,
    FileResponse as FileResponseModel, FileListResponse, FileSearchRequest,
    BulkDeleteRequest, BulkDeleteResponse, ValidationRequest,
    FileValidationResult, HealthResponse, StorageInfo, ErrorResponse
)
from ..shared.db import get_db
from ..shared.cache import redis_client

logger = structlog.get_logger()

# Create routers
tenant_router = APIRouter(prefix="/tenants", tags=["tenants"])
file_router = APIRouter(prefix="/files", tags=["files"])
health_router = APIRouter(prefix="/health", tags=["health"])


# Tenant Management Routes
@tenant_router.post("/", response_model=TenantResponse, status_code=201)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new tenant"""
    try:
        return await TenantService.create_tenant(db, tenant_data)
    except Exception as e:
        logger.error("Failed to create tenant", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create tenant")


@tenant_router.get("/{tenant_code}", response_model=TenantResponse)
async def get_tenant(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get tenant by code"""
    tenant = await TenantService.get_tenant(db, tenant_code)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@tenant_router.put("/{tenant_code}", response_model=TenantResponse)
async def update_tenant(
    tenant_code: str,
    tenant_data: TenantUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update tenant"""
    tenant = await TenantService.update_tenant(db, tenant_code, tenant_data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@tenant_router.delete("/{tenant_code}", status_code=204)
async def delete_tenant(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete tenant and all associated data"""
    success = await TenantService.delete_tenant(db, tenant_code)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")


@tenant_router.get("/{tenant_code}/stats", response_model=TenantStats)
async def get_tenant_stats(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get tenant statistics"""
    stats = await TenantService.get_tenant_stats(db, tenant_code)
    if not stats:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return stats


@tenant_router.get("/{tenant_code}/quotas")
async def check_tenant_quotas(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Check tenant quota usage"""
    quotas = await TenantService.check_tenant_quotas(db, tenant_code)
    if "error" in quotas:
        raise HTTPException(status_code=404, detail=quotas["error"])
    return quotas


# File Management Routes
@file_router.post("/upload", response_model=FileResponseModel, status_code=201)
async def upload_file(
    tenant_code: str,
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Upload a file for a tenant"""
    # Get client IP and user agent from request
    upload_ip = None
    user_agent = None
    if request:
        upload_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    return await FileService.upload_file(
        db=db,
        file=file,
        tenant_code=tenant_code,
        uploaded_by=uploaded_by,
        upload_ip=upload_ip,
        user_agent=user_agent
    )


@file_router.get("/{file_id}", response_model=FileResponseModel)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get file metadata by ID"""
    file_data = await FileService.get_file(db, file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
    return file_data


@file_router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Download a file"""
    file_path, original_filename = await FileService.download_file(db, file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type='application/octet-stream'
    )


@file_router.get("/tenant/{tenant_code}", response_model=FileListResponse)
async def get_files_by_tenant(
    tenant_code: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """Get files for a tenant with pagination"""
    return await FileService.get_files_by_tenant(
        db=db,
        tenant_code=tenant_code,
        page=page,
        limit=limit,
        include_deleted=include_deleted
    )


@file_router.post("/search", response_model=FileListResponse)
async def search_files(
    search_params: FileSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Search files with advanced filtering"""
    return await FileService.search_files(db, search_params)


@file_router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    permanent: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """Delete a file (soft delete by default)"""
    success = await FileService.delete_file(db, file_id, permanent)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {"message": "File deleted successfully", "permanent": permanent}


@file_router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_files(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete files"""
    return await FileService.bulk_delete_files(db, request)


@file_router.post("/validate")
async def validate_files(
    request: ValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate multiple files"""
    results = await FileService.validate_files(db, request.file_ids)
    return results


# Statistics and Info Routes
@file_router.get("/stats/global")
async def get_global_file_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get global file statistics"""
    from .crud import FileCRUD
    stats = await FileCRUD.get_file_stats(db)
    return stats


@file_router.get("/stats/tenant/{tenant_code}")
async def get_tenant_file_stats(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get file statistics for a specific tenant"""
    from .crud import FileCRUD
    stats = await FileCRUD.get_file_stats(db, tenant_code)
    return stats


# Health and Storage Info Routes
@health_router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_status = "healthy"  # This would check actual DB connection
        
        # Check Redis connection
        redis_status = "healthy"
        try:
            await redis_client.redis.ping() if redis_client.redis else None
        except:
            redis_status = "unhealthy"
        
        # Check storage
        storage_status = "healthy"  # This would check storage availability
        
        overall_status = "healthy" if all([
            db_status == "healthy",
            redis_status == "healthy", 
            storage_status == "healthy"
        ]) else "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            database_status=db_status,
            redis_status=redis_status,
            storage_status=storage_status
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            database_status="unknown",
            redis_status="unknown",
            storage_status="unknown"
        )


@health_router.get("/storage/{tenant_code}", response_model=StorageInfo)
async def get_storage_info(
    tenant_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get storage information for a tenant"""
    try:
        # Get tenant stats
        stats = await TenantService.get_tenant_stats(db, tenant_code)
        if not stats:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get storage path
        from ..shared.utils import generate_storage_path
        storage_path = generate_storage_path(tenant_code)
        
        # Calculate available space (this would be implemented with actual filesystem checks)
        available_space = None  # In production, use shutil.disk_usage()
        usage_percentage = stats.storage_usage_percentage
        
        return StorageInfo(
            tenant_code=tenant_code,
            storage_path=storage_path,
            total_files=stats.file_count,
            total_size_bytes=stats.total_storage_bytes,
            available_space_bytes=available_space,
            quota_bytes=stats.storage_quota_bytes,
            usage_percentage=usage_percentage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get storage info", error=str(e), tenant_code=tenant_code)
        raise HTTPException(status_code=500, detail="Failed to get storage info")


# Error handlers
@tenant_router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return ErrorResponse(
        error="Validation Error",
        detail=str(exc),
        error_code="VALIDATION_ERROR"
    )


@file_router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return ErrorResponse(
        error="Validation Error", 
        detail=str(exc),
        error_code="VALIDATION_ERROR"
    )


# Combine all routers
def get_file_service_router() -> APIRouter:
    """Get the complete file service router"""
    main_router = APIRouter()
    main_router.include_router(tenant_router)
    main_router.include_router(file_router)
    main_router.include_router(health_router)
    return main_router
