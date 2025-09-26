"""
Extraction Service Configuration
Service-specific configuration and settings for the File Extraction Service
"""

import os
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class ExtractionServiceSettings(BaseSettings):
    """Extraction Service specific configuration settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Service Identity
    service_name: str = Field(default="extraction-service", description="Service identifier")
    service_version: str = Field(default="1.0.0", description="Service version")
    service_description: str = Field(
        default="Multi-Tenant File Extraction Service",
        description="Service description"
    )
    
    # Server Configuration
    extraction_service_host: str = Field(default="0.0.0.0", env="EXTRACTION_SERVICE_HOST")
    extraction_service_port: int = Field(default=8002, env="EXTRACTION_SERVICE_PORT")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost/file_system_db",
        env="DATABASE_URL",
        description="Async PostgreSQL connection string"
    )
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL",
        description="Redis connection string"
    )
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    redis_socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    # Extraction Configuration
    supported_file_types: str = Field(
        default=".txt,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.json,.csv,.xml,.html,.md,.rtf",
        env="SUPPORTED_FILE_TYPES",
        description="Comma-separated list of supported file types for extraction"
    )
    max_extraction_file_size: int = Field(
        default=52428800,  # 50MB
        env="MAX_EXTRACTION_FILE_SIZE",
        description="Maximum file size for extraction in bytes"
    )
    extraction_timeout: int = Field(
        default=300,  # 5 minutes
        env="EXTRACTION_TIMEOUT",
        description="Extraction timeout in seconds"
    )
    max_concurrent_extractions: int = Field(
        default=5,
        env="MAX_CONCURRENT_EXTRACTIONS",
        description="Maximum concurrent extractions per tenant"
    )
    
    # Text Extraction Configuration
    text_extraction_enabled: bool = Field(
        default=True,
        env="TEXT_EXTRACTION_ENABLED",
        description="Enable text extraction"
    )
    max_text_length: int = Field(
        default=1048576,  # 1MB
        env="MAX_TEXT_LENGTH",
        description="Maximum extracted text length in characters"
    )
    text_encoding: str = Field(
        default="utf-8",
        env="TEXT_ENCODING",
        description="Default text encoding for extraction"
    )
    preserve_formatting: bool = Field(
        default=True,
        env="PRESERVE_FORMATTING",
        description="Preserve text formatting during extraction"
    )
    
    # Metadata Extraction Configuration
    metadata_extraction_enabled: bool = Field(
        default=True,
        env="METADATA_EXTRACTION_ENABLED",
        description="Enable metadata extraction"
    )
    extract_file_properties: bool = Field(
        default=True,
        env="EXTRACT_FILE_PROPERTIES",
        description="Extract file system properties"
    )
    extract_format_metadata: bool = Field(
        default=True,
        env="EXTRACT_FORMAT_METADATA",
        description="Extract format-specific metadata"
    )
    extract_exif_data: bool = Field(
        default=True,
        env="EXTRACT_EXIF_DATA",
        description="Extract EXIF data from images"
    )
    
    # Structured Data Extraction Configuration
    structured_data_enabled: bool = Field(
        default=True,
        env="STRUCTURED_DATA_ENABLED",
        description="Enable structured data extraction"
    )
    max_json_depth: int = Field(
        default=20,
        env="MAX_JSON_DEPTH",
        description="Maximum JSON nesting depth for extraction"
    )
    max_csv_rows: int = Field(
        default=100000,
        env="MAX_CSV_ROWS",
        description="Maximum CSV rows to process"
    )
    csv_sample_size: int = Field(
        default=1000,
        env="CSV_SAMPLE_SIZE",
        description="CSV sample size for type inference"
    )
    auto_detect_delimiters: bool = Field(
        default=True,
        env="AUTO_DETECT_DELIMITERS",
        description="Auto-detect CSV delimiters"
    )
    
    # PDF Extraction Configuration
    pdf_extraction_enabled: bool = Field(
        default=True,
        env="PDF_EXTRACTION_ENABLED",
        description="Enable PDF text extraction"
    )
    pdf_extract_images: bool = Field(
        default=False,
        env="PDF_EXTRACT_IMAGES",
        description="Extract images from PDFs"
    )
    pdf_extract_tables: bool = Field(
        default=True,
        env="PDF_EXTRACT_TABLES",
        description="Extract tables from PDFs"
    )
    pdf_max_pages: int = Field(
        default=1000,
        env="PDF_MAX_PAGES",
        description="Maximum PDF pages to process"
    )
    
    # Office Document Configuration
    office_extraction_enabled: bool = Field(
        default=True,
        env="OFFICE_EXTRACTION_ENABLED",
        description="Enable Office document extraction"
    )
    extract_office_metadata: bool = Field(
        default=True,
        env="EXTRACT_OFFICE_METADATA",
        description="Extract Office document metadata"
    )
    extract_office_comments: bool = Field(
        default=True,
        env="EXTRACT_OFFICE_COMMENTS",
        description="Extract comments from Office documents"
    )
    extract_office_formulas: bool = Field(
        default=True,
        env="EXTRACT_OFFICE_FORMULAS",
        description="Extract formulas from spreadsheets"
    )
    
    # Quality and Confidence Configuration
    min_confidence_threshold: float = Field(
        default=0.5,
        env="MIN_CONFIDENCE_THRESHOLD",
        description="Minimum confidence threshold for extractions"
    )
    enable_quality_scoring: bool = Field(
        default=True,
        env="ENABLE_QUALITY_SCORING",
        description="Enable extraction quality scoring"
    )
    confidence_calculation_method: str = Field(
        default="weighted",
        env="CONFIDENCE_CALCULATION_METHOD",
        description="Confidence calculation method (simple, weighted, ml)"
    )
    
    # Retry Configuration
    max_retry_attempts: int = Field(
        default=3,
        env="MAX_RETRY_ATTEMPTS",
        description="Maximum retry attempts for failed extractions"
    )
    retry_delay_seconds: int = Field(
        default=60,
        env="RETRY_DELAY_SECONDS",
        description="Delay between retry attempts in seconds"
    )
    exponential_backoff: bool = Field(
        default=True,
        env="EXPONENTIAL_BACKOFF",
        description="Use exponential backoff for retries"
    )
    
    # Caching Configuration
    cache_extraction_results: bool = Field(
        default=True,
        env="CACHE_EXTRACTION_RESULTS",
        description="Cache extraction results in Redis"
    )
    extraction_cache_ttl: int = Field(
        default=86400,  # 24 hours
        env="EXTRACTION_CACHE_TTL",
        description="Extraction result cache TTL in seconds"
    )
    cache_file_analysis: bool = Field(
        default=True,
        env="CACHE_FILE_ANALYSIS",
        description="Cache file analysis results"
    )
    
    # Performance Configuration
    extraction_workers: int = Field(
        default=4,
        env="EXTRACTION_WORKERS",
        description="Number of extraction worker processes"
    )
    worker_memory_limit_mb: int = Field(
        default=1024,  # 1GB
        env="WORKER_MEMORY_LIMIT_MB",
        description="Memory limit per worker in MB"
    )
    worker_timeout_seconds: int = Field(
        default=600,  # 10 minutes
        env="WORKER_TIMEOUT_SECONDS",
        description="Worker timeout in seconds"
    )
    batch_processing_enabled: bool = Field(
        default=True,
        env="BATCH_PROCESSING_ENABLED",
        description="Enable batch processing for multiple files"
    )
    batch_size: int = Field(
        default=10,
        env="BATCH_SIZE",
        description="Batch size for bulk processing"
    )
    
    # Queue Configuration
    extraction_queue_name: str = Field(
        default="extraction_queue",
        env="EXTRACTION_QUEUE_NAME",
        description="Redis queue name for extractions"
    )
    priority_queue_enabled: bool = Field(
        default=True,
        env="PRIORITY_QUEUE_ENABLED",
        description="Enable priority queue for extractions"
    )
    queue_monitoring_enabled: bool = Field(
        default=True,
        env="QUEUE_MONITORING_ENABLED",
        description="Enable queue monitoring and metrics"
    )
    
    # Storage Configuration
    temp_extraction_path: str = Field(
        default="/tmp/extractions",
        env="TEMP_EXTRACTION_PATH",
        description="Temporary path for extraction processing"
    )
    cleanup_temp_files: bool = Field(
        default=True,
        env="CLEANUP_TEMP_FILES",
        description="Automatically cleanup temporary files"
    )
    temp_file_retention_hours: int = Field(
        default=2,
        env="TEMP_FILE_RETENTION_HOURS",
        description="Temporary file retention in hours"
    )
    
    # Security Configuration
    enable_file_scanning: bool = Field(
        default=True,
        env="ENABLE_FILE_SCANNING",
        description="Enable file scanning before extraction"
    )
    max_file_scan_time: int = Field(
        default=30,
        env="MAX_FILE_SCAN_TIME",
        description="Maximum file scan time in seconds"
    )
    blocked_file_patterns: str = Field(
        default="*.exe,*.bat,*.cmd,*.scr,*.com,*.pif",
        env="BLOCKED_FILE_PATTERNS",
        description="Comma-separated patterns of blocked files"
    )
    
    # Monitoring Configuration
    enable_metrics: bool = Field(
        default=True,
        env="ENABLE_METRICS",
        description="Enable metrics collection"
    )
    metrics_port: int = Field(
        default=9002,
        env="METRICS_PORT",
        description="Metrics endpoint port"
    )
    health_check_interval: int = Field(
        default=30,
        env="HEALTH_CHECK_INTERVAL",
        description="Health check interval in seconds"
    )
    track_processing_metrics: bool = Field(
        default=True,
        env="TRACK_PROCESSING_METRICS",
        description="Track detailed processing metrics"
    )
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")
    log_max_size_mb: int = Field(default=100, env="LOG_MAX_SIZE_MB")
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    log_extraction_details: bool = Field(
        default=True,
        env="LOG_EXTRACTION_DETAILS",
        description="Log detailed extraction information"
    )
    
    # Environment Configuration
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")
    
    # Feature Flags
    enable_experimental_extractors: bool = Field(
        default=False,
        env="ENABLE_EXPERIMENTAL_EXTRACTORS",
        description="Enable experimental extraction features"
    )
    enable_ml_enhancement: bool = Field(
        default=False,
        env="ENABLE_ML_ENHANCEMENT",
        description="Enable ML-based extraction enhancement"
    )
    enable_async_callbacks: bool = Field(
        default=True,
        env="ENABLE_ASYNC_CALLBACKS",
        description="Enable async callbacks for extraction completion"
    )
    
    # Integration Configuration
    file_service_url: str = Field(
        default="http://localhost:8001",
        env="FILE_SERVICE_URL",
        description="File service base URL"
    )
    file_service_timeout: int = Field(
        default=30,
        env="FILE_SERVICE_TIMEOUT",
        description="File service request timeout in seconds"
    )
    webhook_endpoints: str = Field(
        default="",
        env="WEBHOOK_ENDPOINTS",
        description="Comma-separated webhook endpoints for notifications"
    )
    
    # Cleanup Configuration
    cleanup_old_extractions_days: int = Field(
        default=90,
        env="CLEANUP_OLD_EXTRACTIONS_DAYS",
        description="Cleanup old extractions after days"
    )
    cleanup_failed_extractions_days: int = Field(
        default=7,
        env="CLEANUP_FAILED_EXTRACTIONS_DAYS",
        description="Cleanup failed extractions after days"
    )
    archive_successful_extractions: bool = Field(
        default=False,
        env="ARCHIVE_SUCCESSFUL_EXTRACTIONS",
        description="Archive successful extractions instead of deleting"
    )
    
    @validator("supported_file_types")
    def validate_supported_file_types(cls, v):
        """Validate and normalize supported file types"""
        if not v:
            return []
        types = [ext.strip().lower() for ext in v.split(",")]
        return [ext if ext.startswith(".") else f".{ext}" for ext in types if ext]
    
    @validator("blocked_file_patterns")
    def validate_blocked_file_patterns(cls, v):
        """Validate and normalize blocked file patterns"""
        if not v:
            return []
        return [pattern.strip() for pattern in v.split(",") if pattern.strip()]
    
    @validator("webhook_endpoints")
    def validate_webhook_endpoints(cls, v):
        """Validate and normalize webhook endpoints"""
        if not v:
            return []
        return [url.strip() for url in v.split(",") if url.strip()]
    
    @validator("confidence_calculation_method")
    def validate_confidence_method(cls, v):
        """Validate confidence calculation method"""
        allowed_methods = ["simple", "weighted", "ml"]
        if v not in allowed_methods:
            raise ValueError(f"confidence_calculation_method must be one of {allowed_methods}")
        return v
    
    @property
    def supported_file_types_list(self) -> List[str]:
        """Get supported file types as a list"""
        return self.supported_file_types if isinstance(self.supported_file_types, list) else []
    
    @property
    def blocked_file_patterns_list(self) -> List[str]:
        """Get blocked file patterns as a list"""
        return self.blocked_file_patterns if isinstance(self.blocked_file_patterns, list) else []
    
    @property
    def webhook_endpoints_list(self) -> List[str]:
        """Get webhook endpoints as a list"""
        return self.webhook_endpoints if isinstance(self.webhook_endpoints, list) else []
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"
    
    @property
    def worker_memory_limit_bytes(self) -> int:
        """Get worker memory limit in bytes"""
        return self.worker_memory_limit_mb * 1024 * 1024
    
    @property
    def database_config(self) -> dict:
        """Get database configuration dictionary"""
        return {
            "url": self.database_url,
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "pool_recycle": self.db_pool_recycle,
        }
    
    @property
    def redis_config(self) -> dict:
        """Get Redis configuration dictionary"""
        return {
            "url": self.redis_url,
            "pool_size": self.redis_pool_size,
            "socket_timeout": self.redis_socket_timeout,
            "socket_connect_timeout": self.redis_socket_connect_timeout,
        }
    
    @property
    def extractor_config(self) -> Dict[str, Any]:
        """Get extractor configuration dictionary"""
        return {
            "text": {
                "enabled": self.text_extraction_enabled,
                "max_length": self.max_text_length,
                "encoding": self.text_encoding,
                "preserve_formatting": self.preserve_formatting,
            },
            "metadata": {
                "enabled": self.metadata_extraction_enabled,
                "file_properties": self.extract_file_properties,
                "format_metadata": self.extract_format_metadata,
                "exif_data": self.extract_exif_data,
            },
            "structured": {
                "enabled": self.structured_data_enabled,
                "max_json_depth": self.max_json_depth,
                "max_csv_rows": self.max_csv_rows,
                "csv_sample_size": self.csv_sample_size,
                "auto_detect_delimiters": self.auto_detect_delimiters,
            },
            "pdf": {
                "enabled": self.pdf_extraction_enabled,
                "extract_images": self.pdf_extract_images,
                "extract_tables": self.pdf_extract_tables,
                "max_pages": self.pdf_max_pages,
            },
            "office": {
                "enabled": self.office_extraction_enabled,
                "extract_metadata": self.extract_office_metadata,
                "extract_comments": self.extract_office_comments,
                "extract_formulas": self.extract_office_formulas,
            }
        }


# Global settings instance
extraction_service_settings = ExtractionServiceSettings()


def get_extraction_service_settings() -> ExtractionServiceSettings:
    """Get extraction service settings instance"""
    return extraction_service_settings


# Configuration validation
def validate_extraction_service_config() -> bool:
    """Validate extraction service configuration"""
    try:
        settings = get_extraction_service_settings()
        
        # Check required paths exist
        os.makedirs(settings.temp_extraction_path, exist_ok=True)
        
        # Validate timeout settings
        if settings.extraction_timeout <= 0:
            raise ValueError("extraction_timeout must be positive")
        
        if settings.worker_timeout_seconds <= 0:
            raise ValueError("worker_timeout_seconds must be positive")
        
        # Validate worker settings
        if settings.extraction_workers <= 0:
            raise ValueError("extraction_workers must be positive")
        
        if settings.worker_memory_limit_mb <= 0:
            raise ValueError("worker_memory_limit_mb must be positive")
        
        # Validate file types
        if not settings.supported_file_types_list:
            raise ValueError("supported_file_types cannot be empty")
        
        # Validate confidence settings
        if not (0.0 <= settings.min_confidence_threshold <= 1.0):
            raise ValueError("min_confidence_threshold must be between 0.0 and 1.0")
        
        return True
        
    except Exception as e:
        print(f"Extraction service configuration validation failed: {e}")
        return False


# Export settings for convenience
__all__ = [
    "ExtractionServiceSettings",
    "extraction_service_settings",
    "get_extraction_service_settings",
    "validate_extraction_service_config"
]
