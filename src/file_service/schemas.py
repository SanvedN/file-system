from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums for validation
class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


# Base schemas
class TenantBase(BaseModel):
    code: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    storage_quota_bytes: Optional[int] = Field(None, ge=0)
    file_count_limit: Optional[int] = Field(None, ge=0)
    settings: Optional[Dict[str, Any]] = None


class TenantCreate(TenantBase):
    created_by: Optional[str] = None
    
    @validator('code')
    def validate_code(cls, v):
        # Additional validation for tenant code
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Tenant code must contain only alphanumeric characters, underscores, and hyphens')
        return v.lower()


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    storage_quota_bytes: Optional[int] = Field(None, ge=0)
    file_count_limit: Optional[int] = Field(None, ge=0)
    settings: Optional[Dict[str, Any]] = None


class TenantResponse(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    file_count: Optional[int] = 0
    total_storage_used: Optional[int] = 0


class TenantStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    tenant_id: str
    tenant_code: str
    file_count: int
    total_storage_bytes: int
    storage_quota_bytes: Optional[int]
    file_count_limit: Optional[int]
    storage_usage_percentage: Optional[float]
    file_count_usage_percentage: Optional[float]
    last_upload: Optional[datetime]


# File schemas
class FileBase(BaseModel):
    original_filename: str = Field(..., min_length=1, max_length=255)
    tenant_code: str = Field(..., min_length=3, max_length=50)


class FileUpload(BaseModel):
    tenant_code: str = Field(..., min_length=3, max_length=50)
    uploaded_by: Optional[str] = None
    upload_ip: Optional[str] = None
    user_agent: Optional[str] = None


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    tenant_id: str
    tenant_code: str
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int
    mime_type: str
    file_extension: str
    file_hash: Optional[str]
    status: FileStatus
    is_deleted: bool
    uploaded_at: datetime
    processed_at: Optional[datetime]
    deleted_at: Optional[datetime]
    last_accessed: Optional[datetime]
    uploaded_by: Optional[str]
    upload_ip: Optional[str]
    validation_status: ValidationStatus
    validation_details: Optional[Dict[str, Any]] = None
    processing_status: Optional[Dict[str, Any]] = None
    error_message: Optional[str]
    retry_count: int
    
    # Computed fields
    display_size: Optional[str] = None
    is_zip_file: Optional[bool] = None


class FileMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    original_filename: str
    file_size: int
    mime_type: str
    file_extension: str
    uploaded_at: datetime
    status: FileStatus
    validation_status: ValidationStatus
    display_size: str


class FileListResponse(BaseModel):
    files: List[FileMetadata]
    total_count: int
    page: int
    limit: int
    has_next: bool
    has_previous: bool


class FileUpdate(BaseModel):
    original_filename: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[FileStatus] = None
    validation_status: Optional[ValidationStatus] = None
    validation_details: Optional[Dict[str, Any]] = None
    processing_status: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class FileStatsResponse(BaseModel):
    total_files: int
    total_size_bytes: int
    files_by_status: Dict[str, int]
    files_by_extension: Dict[str, int]
    average_file_size: float
    largest_file_size: int
    smallest_file_size: int
    upload_trend: List[Dict[str, Any]]  # Upload statistics over time


# Bulk operations
class BulkDeleteRequest(BaseModel):
    file_ids: List[str] = Field(..., min_items=1, max_items=100)
    permanent: bool = False


class BulkDeleteResponse(BaseModel):
    deleted_files: List[str]
    failed_deletions: List[Dict[str, str]]
    total_deleted: int
    total_failed: int


# Search and filter schemas
class FileSearchRequest(BaseModel):
    tenant_code: Optional[str] = None
    filename_pattern: Optional[str] = None
    file_extension: Optional[str] = None
    status: Optional[FileStatus] = None
    validation_status: Optional[ValidationStatus] = None
    uploaded_after: Optional[datetime] = None
    uploaded_before: Optional[datetime] = None
    min_size: Optional[int] = Field(None, ge=0)
    max_size: Optional[int] = Field(None, ge=0)
    uploaded_by: Optional[str] = None
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
    sort_by: Optional[str] = Field("uploaded_at", pattern=r'^(uploaded_at|file_size|original_filename)$')
    sort_order: Optional[str] = Field("desc", pattern=r'^(asc|desc)$')


# Validation schemas
class FileValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    file_info: Optional[Dict[str, Any]] = None


class ValidationRequest(BaseModel):
    file_ids: List[str] = Field(..., min_items=1, max_items=50)
    validation_type: str = Field("full", pattern=r'^(quick|full|deep)$')


# Error response schemas
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Health check schemas
class HealthResponse(BaseModel):
    status: str
    database_status: str
    redis_status: str
    storage_status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Storage info schemas
class StorageInfo(BaseModel):
    tenant_code: str
    storage_path: str
    total_files: int
    total_size_bytes: int
    available_space_bytes: Optional[int]
    quota_bytes: Optional[int]
    usage_percentage: Optional[float]
