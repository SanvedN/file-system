from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import structlog

from .services import ExtractionService
from .schemas import (
    ExtractionRequest, ExtractionResponse, ExtractionSearchRequest,
    ExtractionListResponse, BulkExtractionRequest, BulkExtractionResponse,
    RetryExtractionRequest, ExtractionStats, ExtractionServiceHealth,
    ExtractionStatus, ExtractionType
)
from ..shared.db import get_db
from ..shared.cache import redis_client

logger = structlog.get_logger()

# Create routers
extraction_router = APIRouter(prefix="/extractions", tags=["extractions"])
health_router = APIRouter(prefix="/health", tags=["health"])

# Initialize extraction service
extraction_service = ExtractionService()


# Extraction Management Routes
@extraction_router.post("/", response_model=ExtractionResponse, status_code=201)
async def request_extraction(
    request: ExtractionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request a new extraction"""
    return await extraction_service.request_extraction(db, request)


@extraction_router.get("/{extraction_id}", response_model=ExtractionResponse)
async def get_extraction(
    extraction_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get extraction by ID"""
    extraction = await extraction_service.get_extraction(db, extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return extraction


@extraction_router.post("/search", response_model=ExtractionListResponse)
async def search_extractions(
    search_params: ExtractionSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Search extractions with advanced filtering"""
    return await extraction_service.search_extractions(db, search_params)


@extraction_router.get("/file/{file_id}", response_model=List[ExtractionResponse])
async def get_extractions_by_file(
    file_id: str,
    extraction_type: Optional[ExtractionType] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all extractions for a specific file"""
    from .crud import ExtractionCRUD
    extractions = await ExtractionCRUD.get_by_file_id(db, file_id, extraction_type)
    
    extraction_responses = []
    for extraction in extractions:
        extraction_response = await extraction_service.get_extraction(db, extraction.id)
        if extraction_response:
            extraction_responses.append(extraction_response)
    
    return extraction_responses


@extraction_router.get("/tenant/{tenant_id}")
async def get_extractions_by_tenant(
    tenant_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[ExtractionStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get extractions for a tenant with pagination"""
    from .crud import ExtractionCRUD
    skip = (page - 1) * limit
    extractions, total_count = await ExtractionCRUD.get_by_tenant(
        db, tenant_id, skip, limit, status
    )
    
    extraction_summaries = []
    for extraction in extractions:
        extraction_summaries.append({
            "id": extraction.id,
            "file_id": extraction.file_id,
            "extraction_type": extraction.extraction_type,
            "status": extraction.status,
            "progress_percentage": extraction.progress_percentage,
            "confidence_score": extraction.confidence_score,
            "created_at": extraction.created_at,
            "completed_at": extraction.completed_at,
            "processing_time_ms": extraction.processing_time_ms,
            "validation_passed": extraction.validation_passed
        })
    
    return {
        "extractions": extraction_summaries,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "has_next": (skip + limit) < total_count,
        "has_previous": page > 1
    }


@extraction_router.post("/bulk", response_model=BulkExtractionResponse)
async def bulk_request_extractions(
    request: BulkExtractionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request multiple extractions"""
    return await extraction_service.bulk_request_extractions(db, request)


@extraction_router.post("/retry")
async def retry_extractions(
    request: RetryExtractionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Retry failed extractions"""
    return await extraction_service.retry_extractions(db, request)


@extraction_router.delete("/{extraction_id}")
async def delete_extraction(
    extraction_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete an extraction"""
    from .crud import ExtractionCRUD
    success = await ExtractionCRUD.delete(db, extraction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    return {"message": "Extraction deleted successfully"}


# Processing Routes
@extraction_router.post("/{extraction_id}/process")
async def process_extraction(
    extraction_id: str,
    file_path: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Process an extraction (typically called by internal services)"""
    # Add to background tasks for async processing
    background_tasks.add_task(
        extraction_service.process_extraction,
        db,
        extraction_id,
        file_path
    )
    
    return {"message": "Extraction processing started", "extraction_id": extraction_id}


@extraction_router.get("/queue/pending")
async def get_pending_extractions(
    limit: int = Query(10, ge=1, le=100),
    extraction_type: Optional[ExtractionType] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get pending extractions for processing"""
    from .crud import ExtractionCRUD
    pending_extractions = await ExtractionCRUD.get_pending_extractions(
        db, limit, extraction_type
    )
    
    return [
        {
            "id": extraction.id,
            "file_id": extraction.file_id,
            "tenant_id": extraction.tenant_id,
            "extraction_type": extraction.extraction_type,
            "created_at": extraction.created_at,
            "retry_count": extraction.retry_count
        }
        for extraction in pending_extractions
    ]


@extraction_router.get("/queue/failed")
async def get_failed_extractions_for_retry(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get failed extractions that can be retried"""
    from .crud import ExtractionCRUD
    failed_extractions = await ExtractionCRUD.get_failed_extractions_for_retry(db, limit)
    
    return [
        {
            "id": extraction.id,
            "file_id": extraction.file_id,
            "tenant_id": extraction.tenant_id,
            "extraction_type": extraction.extraction_type,
            "error_message": extraction.error_message,
            "retry_count": extraction.retry_count,
            "max_retries": extraction.max_retries,
            "created_at": extraction.created_at
        }
        for extraction in failed_extractions
    ]


# Statistics Routes
@extraction_router.get("/stats/global", response_model=ExtractionStats)
async def get_global_extraction_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get global extraction statistics"""
    return await extraction_service.get_extraction_stats(db)


@extraction_router.get("/stats/tenant/{tenant_id}", response_model=ExtractionStats)
async def get_tenant_extraction_stats(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get extraction statistics for a specific tenant"""
    return await extraction_service.get_extraction_stats(db, tenant_id)


# Health and Status Routes
@health_router.get("/", response_model=ExtractionServiceHealth)
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_status = "healthy"  # Would check actual DB connection
        
        # Check Redis connection
        redis_status = "healthy"
        try:
            await redis_client.redis.ping() if redis_client.redis else None
        except:
            redis_status = "unhealthy"
        
        # Mock extractor health checks
        extractors = [
            {
                "extractor_name": "text_extractor",
                "status": "healthy",
                "last_check": "2025-09-26T00:00:00Z",
                "processing_queue_size": 0,
                "average_processing_time_ms": 1500.0,
                "error_rate": 0.05,
                "success_rate": 0.95
            },
            {
                "extractor_name": "metadata_extractor",
                "status": "healthy",
                "last_check": "2025-09-26T00:00:00Z",
                "processing_queue_size": 0,
                "average_processing_time_ms": 500.0,
                "error_rate": 0.02,
                "success_rate": 0.98
            },
            {
                "extractor_name": "structured_data_extractor",
                "status": "healthy",
                "last_check": "2025-09-26T00:00:00Z",
                "processing_queue_size": 0,
                "average_processing_time_ms": 2000.0,
                "error_rate": 0.08,
                "success_rate": 0.92
            }
        ]
        
        overall_status = "healthy" if all([
            db_status == "healthy",
            redis_status == "healthy",
            all(ext["status"] == "healthy" for ext in extractors)
        ]) else "unhealthy"
        
        return ExtractionServiceHealth(
            status=overall_status,
            database_status=db_status,
            redis_status=redis_status,
            extractors=extractors,
            total_queue_size=sum(ext["processing_queue_size"] for ext in extractors),
            processing_capacity=100  # Mock capacity
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return ExtractionServiceHealth(
            status="unhealthy",
            database_status="unknown",
            redis_status="unknown",
            extractors=[],
            total_queue_size=0,
            processing_capacity=0
        )


# Admin/Maintenance Routes
@extraction_router.post("/admin/cleanup")
async def cleanup_old_extractions(
    days_old: int = Query(30, ge=1),
    keep_successful: bool = Query(True),
    db: AsyncSession = Depends(get_db)
):
    """Cleanup old extraction records"""
    from .crud import ExtractionCRUD
    deleted_count = await ExtractionCRUD.cleanup_old_extractions(
        db, days_old, keep_successful
    )
    
    return {
        "message": f"Cleaned up {deleted_count} old extractions",
        "deleted_count": deleted_count,
        "days_old": days_old,
        "kept_successful": keep_successful
    }


# Combine all routers
def get_extraction_service_router() -> APIRouter:
    """Get the complete extraction service router"""
    main_router = APIRouter()
    main_router.include_router(extraction_router)
    main_router.include_router(health_router)
    return main_router
