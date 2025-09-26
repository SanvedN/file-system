from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionType(str, Enum):
    TEXT = "text"
    METADATA = "metadata"
    STRUCTURED_DATA = "structured_data"
    FULL = "full"


# Base schemas
class ExtractionResultBase(BaseModel):
    file_id: str
    tenant_id: str
    extraction_type: ExtractionType
    extractor_version: str = "1.0"


class ExtractionRequest(BaseModel):
    file_id: str
    extraction_type: ExtractionType = ExtractionType.FULL
    extraction_config: Optional[Dict[str, Any]] = None
    priority: int = Field(0, ge=0, le=10)  # 0 = lowest, 10 = highest
    max_retries: int = Field(3, ge=0, le=10)


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    file_id: str
    tenant_id: str
    extraction_type: ExtractionType
    extractor_version: str
    status: ExtractionStatus
    progress_percentage: int = Field(0, ge=0, le=100)
    
    # Results
    extracted_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    file_analysis: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Processing info
    processing_time_ms: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    
    # Error handling
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated: datetime
    
    # Quality metrics
    extraction_quality: Optional[Dict[str, Any]] = None
    validation_passed: bool = False


class ExtractionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    file_id: str
    extraction_type: ExtractionType
    status: ExtractionStatus
    progress_percentage: int
    confidence_score: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
    processing_time_ms: Optional[int]
    validation_passed: bool


class ExtractionUpdate(BaseModel):
    status: Optional[ExtractionStatus] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    extracted_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    file_analysis: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    processing_time_ms: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    extraction_quality: Optional[Dict[str, Any]] = None
    validation_passed: Optional[bool] = None


class ExtractionListResponse(BaseModel):
    extractions: List[ExtractionSummary]
    total_count: int
    page: int
    limit: int
    has_next: bool
    has_previous: bool


# Bulk operations
class BulkExtractionRequest(BaseModel):
    file_ids: List[str] = Field(..., min_items=1, max_items=50)
    extraction_type: ExtractionType = ExtractionType.FULL
    extraction_config: Optional[Dict[str, Any]] = None
    priority: int = Field(0, ge=0, le=10)
    max_retries: int = Field(3, ge=0, le=10)


class BulkExtractionResponse(BaseModel):
    created_extractions: List[str]  # extraction IDs
    failed_requests: List[Dict[str, str]]  # file_id -> error
    total_created: int
    total_failed: int


class RetryExtractionRequest(BaseModel):
    extraction_ids: List[str] = Field(..., min_items=1, max_items=20)
    force_retry: bool = False  # Retry even if max retries reached


# Search and filter schemas
class ExtractionSearchRequest(BaseModel):
    tenant_id: Optional[str] = None
    file_id: Optional[str] = None
    extraction_type: Optional[ExtractionType] = None
    status: Optional[ExtractionStatus] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    completed_after: Optional[datetime] = None
    completed_before: Optional[datetime] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    validation_passed: Optional[bool] = None
    has_errors: Optional[bool] = None
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
    sort_by: Optional[str] = Field("created_at", pattern=r'^(created_at|completed_at|confidence_score|processing_time_ms)$')
    sort_order: Optional[str] = Field("desc", pattern=r'^(asc|desc)$')


# Statistics schemas
class ExtractionStats(BaseModel):
    total_extractions: int
    extractions_by_status: Dict[str, int]
    extractions_by_type: Dict[str, int]
    average_processing_time_ms: Optional[float]
    average_confidence_score: Optional[float]
    success_rate: float
    total_processing_time_ms: int
    fastest_extraction_ms: Optional[int]
    slowest_extraction_ms: Optional[int]


class TenantExtractionStats(BaseModel):
    tenant_id: str
    total_extractions: int
    successful_extractions: int
    failed_extractions: int
    average_processing_time_ms: Optional[float]
    total_processing_time_ms: int
    last_extraction: Optional[datetime]
    most_common_type: Optional[str]


# Processing details
class ProcessingMetrics(BaseModel):
    cpu_usage_percent: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    disk_io_mb: Optional[float] = None
    processing_time_ms: Optional[int] = None
    queue_wait_time_ms: Optional[int] = None


class ExtractionProgress(BaseModel):
    extraction_id: str
    status: ExtractionStatus
    progress_percentage: int
    current_step: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    metrics: Optional[ProcessingMetrics] = None


# Quality and validation schemas
class QualityMetrics(BaseModel):
    text_extraction_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    structure_detection_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata_completeness: Optional[float] = Field(None, ge=0.0, le=1.0)
    overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    validation_checks: List[Dict[str, Any]] = []


class ValidationResult(BaseModel):
    is_valid: bool
    validation_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    issues: List[str] = []
    warnings: List[str] = []
    quality_metrics: Optional[QualityMetrics] = None


# Configuration schemas
class ExtractionConfig(BaseModel):
    enable_text_extraction: bool = True
    enable_metadata_extraction: bool = True
    enable_structure_detection: bool = True
    max_text_length: Optional[int] = Field(None, gt=0)
    language_detection: bool = True
    ocr_enabled: bool = False
    preserve_formatting: bool = True
    extract_images: bool = False
    custom_extractors: List[str] = []


# Error schemas
class ExtractionError(BaseModel):
    error_code: str
    error_message: str
    error_type: str  # system, validation, processing, timeout
    timestamp: datetime
    retry_possible: bool
    suggested_action: Optional[str] = None


# Health and monitoring
class ExtractorHealth(BaseModel):
    extractor_name: str
    status: str  # healthy, degraded, unhealthy
    last_check: datetime
    processing_queue_size: int
    average_processing_time_ms: Optional[float]
    error_rate: float
    success_rate: float


class ExtractionServiceHealth(BaseModel):
    status: str
    database_status: str
    redis_status: str
    extractors: List[ExtractorHealth]
    total_queue_size: int
    processing_capacity: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
