from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json

from .models import ExtractionResult
from .schemas import (
    ExtractionRequest, ExtractionUpdate, ExtractionSearchRequest,
    ExtractionStatus, ExtractionType
)
from ..shared.cache import redis_client, get_extraction_cache_key
from ..shared.config import settings
import structlog

logger = structlog.get_logger()


class ExtractionCRUD:
    """CRUD operations for ExtractionResult model"""
    
    @staticmethod
    async def create(db: AsyncSession, extraction_data: Dict[str, Any]) -> ExtractionResult:
        """Create a new extraction result record"""
        try:
            extraction_obj = ExtractionResult(**extraction_data)
            db.add(extraction_obj)
            await db.commit()
            await db.refresh(extraction_obj)
            
            # Cache extraction metadata
            await redis_client.set(
                get_extraction_cache_key(extraction_obj.file_id),
                {
                    "id": extraction_obj.id,
                    "file_id": extraction_obj.file_id,
                    "status": extraction_obj.status,
                    "extraction_type": extraction_obj.extraction_type,
                    "progress_percentage": extraction_obj.progress_percentage,
                    "created_at": extraction_obj.created_at.isoformat()
                },
                expire=1800  # 30 minutes
            )
            
            logger.info("Extraction record created", extraction_id=extraction_obj.id, file_id=extraction_obj.file_id)
            return extraction_obj
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to create extraction record", error=str(e))
            raise

    @staticmethod
    async def get_by_id(db: AsyncSession, extraction_id: str) -> Optional[ExtractionResult]:
        """Get extraction by ID"""
        try:
            result = await db.execute(
                select(ExtractionResult)
                .options(selectinload(ExtractionResult.file))
                .where(ExtractionResult.id == extraction_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get extraction by ID", error=str(e), extraction_id=extraction_id)
            return None

    @staticmethod
    async def get_by_file_id(
        db: AsyncSession, 
        file_id: str,
        extraction_type: Optional[ExtractionType] = None
    ) -> List[ExtractionResult]:
        """Get extractions by file ID"""
        try:
            query = select(ExtractionResult).where(ExtractionResult.file_id == file_id)
            
            if extraction_type:
                query = query.where(ExtractionResult.extraction_type == extraction_type)
            
            query = query.order_by(ExtractionResult.created_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get extractions by file ID", error=str(e), file_id=file_id)
            return []

    @staticmethod
    async def get_by_tenant(
        db: AsyncSession,
        tenant_id: str,
        skip: int = 0,
        limit: int = 10,
        status: Optional[ExtractionStatus] = None
    ) -> Tuple[List[ExtractionResult], int]:
        """Get extractions by tenant with pagination"""
        try:
            # Build query
            query = select(ExtractionResult).where(ExtractionResult.tenant_id == tenant_id)
            
            if status:
                query = query.where(ExtractionResult.status == status)
            
            # Get total count
            count_query = select(func.count(ExtractionResult.id)).where(ExtractionResult.tenant_id == tenant_id)
            if status:
                count_query = count_query.where(ExtractionResult.status == status)
            
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()
            
            # Get extractions
            query = query.offset(skip).limit(limit).order_by(ExtractionResult.created_at.desc())
            result = await db.execute(query)
            extractions = result.scalars().all()
            
            return extractions, total_count
            
        except Exception as e:
            logger.error("Failed to get extractions by tenant", error=str(e), tenant_id=tenant_id)
            return [], 0

    @staticmethod
    async def search_extractions(
        db: AsyncSession, 
        search_params: ExtractionSearchRequest
    ) -> Tuple[List[ExtractionResult], int]:
        """Search extractions with advanced filtering"""
        try:
            # Build base query
            query = select(ExtractionResult)
            count_query = select(func.count(ExtractionResult.id))
            
            conditions = []
            
            # Tenant filter
            if search_params.tenant_id:
                conditions.append(ExtractionResult.tenant_id == search_params.tenant_id)
            
            # File filter
            if search_params.file_id:
                conditions.append(ExtractionResult.file_id == search_params.file_id)
            
            # Extraction type
            if search_params.extraction_type:
                conditions.append(ExtractionResult.extraction_type == search_params.extraction_type)
            
            # Status
            if search_params.status:
                conditions.append(ExtractionResult.status == search_params.status)
            
            # Date ranges
            if search_params.created_after:
                conditions.append(ExtractionResult.created_at >= search_params.created_after)
            if search_params.created_before:
                conditions.append(ExtractionResult.created_at <= search_params.created_before)
            
            if search_params.completed_after:
                conditions.append(ExtractionResult.completed_at >= search_params.completed_after)
            if search_params.completed_before:
                conditions.append(ExtractionResult.completed_at <= search_params.completed_before)
            
            # Confidence filter
            if search_params.min_confidence is not None:
                conditions.append(ExtractionResult.confidence_score >= search_params.min_confidence)
            
            # Validation filter
            if search_params.validation_passed is not None:
                conditions.append(ExtractionResult.validation_passed == search_params.validation_passed)
            
            # Error filter
            if search_params.has_errors is not None:
                if search_params.has_errors:
                    conditions.append(ExtractionResult.error_message.isnot(None))
                else:
                    conditions.append(ExtractionResult.error_message.is_(None))
            
            # Apply conditions
            if conditions:
                where_clause = and_(*conditions)
                query = query.where(where_clause)
                count_query = count_query.where(where_clause)
            
            # Get total count
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply sorting
            sort_column = getattr(ExtractionResult, search_params.sort_by, ExtractionResult.created_at)
            if search_params.sort_order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))
            
            # Apply pagination
            skip = (search_params.page - 1) * search_params.limit
            query = query.offset(skip).limit(search_params.limit)
            
            # Execute query
            result = await db.execute(query)
            extractions = result.scalars().all()
            
            return extractions, total_count
            
        except Exception as e:
            logger.error("Failed to search extractions", error=str(e))
            return [], 0

    @staticmethod
    async def update(
        db: AsyncSession, 
        extraction_id: str, 
        extraction_data: ExtractionUpdate
    ) -> Optional[ExtractionResult]:
        """Update extraction result"""
        try:
            # Get existing extraction
            extraction_obj = await ExtractionCRUD.get_by_id(db, extraction_id)
            if not extraction_obj:
                return None
            
            # Update fields
            update_data = extraction_data.model_dump(exclude_unset=True)
            
            # Handle JSON fields
            json_fields = ['structured_data', 'metadata', 'file_analysis', 'extraction_quality']
            for field in json_fields:
                if field in update_data and update_data[field] is not None:
                    update_data[field] = json.dumps(update_data[field])
            
            # Update timestamps based on status
            if update_data.get('status'):
                if update_data['status'] == ExtractionStatus.PROCESSING and not extraction_obj.started_at:
                    update_data['started_at'] = datetime.utcnow()
                elif update_data['status'] in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED]:
                    if not extraction_obj.completed_at:
                        update_data['completed_at'] = datetime.utcnow()
                    
                    # Calculate processing time
                    if extraction_obj.started_at:
                        processing_time = (datetime.utcnow() - extraction_obj.started_at).total_seconds() * 1000
                        update_data['processing_time_ms'] = int(processing_time)
            
            stmt = (
                update(ExtractionResult)
                .where(ExtractionResult.id == extraction_id)
                .values(**update_data)
                .returning(ExtractionResult)
            )
            
            result = await db.execute(stmt)
            updated_extraction = result.scalar_one_or_none()
            await db.commit()
            
            if updated_extraction:
                # Update cache
                await redis_client.delete(get_extraction_cache_key(updated_extraction.file_id))
                logger.info("Extraction updated", extraction_id=extraction_id)
            
            return updated_extraction
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to update extraction", error=str(e), extraction_id=extraction_id)
            return None

    @staticmethod
    async def delete(db: AsyncSession, extraction_id: str) -> bool:
        """Delete extraction result"""
        try:
            extraction_obj = await ExtractionCRUD.get_by_id(db, extraction_id)
            if not extraction_obj:
                return False
            
            await db.execute(delete(ExtractionResult).where(ExtractionResult.id == extraction_id))
            await db.commit()
            
            # Clear cache
            await redis_client.delete(get_extraction_cache_key(extraction_obj.file_id))
            
            logger.info("Extraction deleted", extraction_id=extraction_id)
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to delete extraction", error=str(e), extraction_id=extraction_id)
            return False

    @staticmethod
    async def get_pending_extractions(
        db: AsyncSession, 
        limit: int = 10,
        extraction_type: Optional[ExtractionType] = None
    ) -> List[ExtractionResult]:
        """Get pending extractions for processing"""
        try:
            query = select(ExtractionResult).where(ExtractionResult.status == ExtractionStatus.PENDING)
            
            if extraction_type:
                query = query.where(ExtractionResult.extraction_type == extraction_type)
            
            # Order by priority (if we add priority field) and creation time
            query = query.order_by(ExtractionResult.created_at.asc()).limit(limit)
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get pending extractions", error=str(e))
            return []

    @staticmethod
    async def get_failed_extractions_for_retry(
        db: AsyncSession,
        limit: int = 10
    ) -> List[ExtractionResult]:
        """Get failed extractions that can be retried"""
        try:
            query = select(ExtractionResult).where(
                and_(
                    ExtractionResult.status == ExtractionStatus.FAILED,
                    ExtractionResult.retry_count < ExtractionResult.max_retries
                )
            ).order_by(ExtractionResult.created_at.asc()).limit(limit)
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get failed extractions for retry", error=str(e))
            return []

    @staticmethod
    async def increment_retry_count(db: AsyncSession, extraction_id: str) -> bool:
        """Increment retry count for an extraction"""
        try:
            stmt = (
                update(ExtractionResult)
                .where(ExtractionResult.id == extraction_id)
                .values(retry_count=ExtractionResult.retry_count + 1)
            )
            
            await db.execute(stmt)
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to increment retry count", error=str(e), extraction_id=extraction_id)
            return False

    @staticmethod
    async def get_extraction_stats(
        db: AsyncSession, 
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get extraction statistics"""
        try:
            # Base query
            query = select(
                func.count(ExtractionResult.id).label('total_extractions'),
                func.avg(ExtractionResult.processing_time_ms).label('avg_processing_time'),
                func.avg(ExtractionResult.confidence_score).label('avg_confidence'),
                func.sum(ExtractionResult.processing_time_ms).label('total_processing_time'),
                func.min(ExtractionResult.processing_time_ms).label('min_processing_time'),
                func.max(ExtractionResult.processing_time_ms).label('max_processing_time')
            )
            
            if tenant_id:
                query = query.where(ExtractionResult.tenant_id == tenant_id)
            
            result = await db.execute(query)
            stats = result.first()
            
            # Get status breakdown
            status_query = select(
                ExtractionResult.status,
                func.count(ExtractionResult.id).label('count')
            )
            
            if tenant_id:
                status_query = status_query.where(ExtractionResult.tenant_id == tenant_id)
            
            status_query = status_query.group_by(ExtractionResult.status)
            status_result = await db.execute(status_query)
            status_breakdown = {row.status: row.count for row in status_result}
            
            # Get type breakdown
            type_query = select(
                ExtractionResult.extraction_type,
                func.count(ExtractionResult.id).label('count')
            )
            
            if tenant_id:
                type_query = type_query.where(ExtractionResult.tenant_id == tenant_id)
            
            type_query = type_query.group_by(ExtractionResult.extraction_type)
            type_result = await db.execute(type_query)
            type_breakdown = {row.extraction_type: row.count for row in type_result}
            
            # Calculate success rate
            total = stats.total_extractions or 0
            successful = status_breakdown.get(ExtractionStatus.COMPLETED, 0)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            return {
                "total_extractions": total,
                "extractions_by_status": status_breakdown,
                "extractions_by_type": type_breakdown,
                "average_processing_time_ms": float(stats.avg_processing_time or 0),
                "average_confidence_score": float(stats.avg_confidence or 0),
                "success_rate": success_rate,
                "total_processing_time_ms": int(stats.total_processing_time or 0),
                "fastest_extraction_ms": stats.min_processing_time,
                "slowest_extraction_ms": stats.max_processing_time
            }
            
        except Exception as e:
            logger.error("Failed to get extraction stats", error=str(e))
            return {}

    @staticmethod
    async def cleanup_old_extractions(
        db: AsyncSession,
        days_old: int = 30,
        keep_successful: bool = True
    ) -> int:
        """Cleanup old extraction records"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            query = delete(ExtractionResult).where(ExtractionResult.created_at < cutoff_date)
            
            if keep_successful:
                query = query.where(ExtractionResult.status != ExtractionStatus.COMPLETED)
            
            result = await db.execute(query)
            await db.commit()
            
            deleted_count = result.rowcount
            logger.info("Cleaned up old extractions", deleted_count=deleted_count, days_old=days_old)
            
            return deleted_count
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to cleanup old extractions", error=str(e))
            return 0
