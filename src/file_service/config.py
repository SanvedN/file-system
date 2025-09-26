"""
File Service Configuration
Service-specific configuration and settings for the File Management Service
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class FileServiceSettings(BaseSettings):
    """File Service specific configuration settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Service Identity
    service_name: str = Field(default="file-service", description="Service identifier")
    service_version: str = Field(default="1.0.0", description="Service version")
    service_description: str = Field(
        default="Multi-Tenant File Management Service", 
        description="Service description"
    )
    
    # Server Configuration
    file_service_host: str = Field(default="0.0.0.0", env="FILE_SERVICE_HOST")
    file_service_port: int = Field(default=8001, env="FILE_SERVICE_PORT")
    
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
    
    # Storage Configuration
    storage_base_path: str = Field(
        default="/app/storage",
        env="STORAGE_BASE_PATH",
        description="Base path for file storage"
    )
    storage_create_directories: bool = Field(
        default=True,
        env="STORAGE_CREATE_DIRECTORIES",
        description="Automatically create storage directories"
    )
    storage_use_symlinks: bool = Field(
        default=False,
        env="STORAGE_USE_SYMLINKS",
        description="Use symlinks for file organization"
    )
    
    # File Upload Configuration
    max_file_size: int = Field(
        default=104857600,  # 100MB
        env="MAX_FILE_SIZE",
        description="Maximum file size in bytes"
    )
    max_files_per_tenant: int = Field(
        default=10000,
        env="MAX_FILES_PER_TENANT",
        description="Maximum files per tenant (default limit)"
    )
    allowed_extensions: str = Field(
        default=".txt,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.json,.csv,.xml,.jpg,.jpeg,.png,.gif,.mp4,.mp3",
        env="ALLOWED_EXTENSIONS",
        description="Comma-separated list of allowed file extensions"
    )
    blocked_extensions: str = Field(
        default=".exe,.bat,.cmd,.sh,.ps1,.scr,.com,.pif",
        env="BLOCKED_EXTENSIONS",
        description="Comma-separated list of blocked file extensions"
    )
    
    # File Validation Configuration
    max_zip_depth: int = Field(
        default=3,
        env="MAX_ZIP_DEPTH",
        description="Maximum nested zip file depth"
    )
    validate_file_content: bool = Field(
        default=True,
        env="VALIDATE_FILE_CONTENT",
        description="Enable file content validation"
    )
    scan_for_viruses: bool = Field(
        default=False,
        env="SCAN_FOR_VIRUSES",
        description="Enable virus scanning (requires antivirus integration)"
    )
    check_file_integrity: bool = Field(
        default=True,
        env="CHECK_FILE_INTEGRITY",
        description="Verify file integrity during upload"
    )
    
    # Tenant Configuration
    default_storage_quota_mb: Optional[int] = Field(
        default=1024,  # 1GB
        env="DEFAULT_STORAGE_QUOTA_MB",
        description="Default storage quota per tenant in MB"
    )
    default_file_count_limit: Optional[int] = Field(
        default=1000,
        env="DEFAULT_FILE_COUNT_LIMIT",
        description="Default file count limit per tenant"
    )
    enable_tenant_isolation: bool = Field(
        default=True,
        env="ENABLE_TENANT_ISOLATION",
        description="Enforce strict tenant data isolation"
    )
    
    # Caching Configuration
    cache_tenant_data: bool = Field(
        default=True,
        env="CACHE_TENANT_DATA",
        description="Cache tenant information in Redis"
    )
    cache_file_metadata: bool = Field(
        default=True,
        env="CACHE_FILE_METADATA",
        description="Cache file metadata in Redis"
    )
    cache_ttl_seconds: int = Field(
        default=3600,  # 1 hour
        env="CACHE_TTL_SECONDS",
        description="Default cache TTL in seconds"
    )
    cache_file_list_ttl: int = Field(
        default=300,  # 5 minutes
        env="CACHE_FILE_LIST_TTL",
        description="File list cache TTL in seconds"
    )
    
    # Performance Configuration
    upload_chunk_size: int = Field(
        default=8192,  # 8KB
        env="UPLOAD_CHUNK_SIZE",
        description="File upload chunk size in bytes"
    )
    download_chunk_size: int = Field(
        default=8192,  # 8KB
        env="DOWNLOAD_CHUNK_SIZE",
        description="File download chunk size in bytes"
    )
    max_concurrent_uploads: int = Field(
        default=10,
        env="MAX_CONCURRENT_UPLOADS",
        description="Maximum concurrent file uploads per tenant"
    )
    background_task_workers: int = Field(
        default=4,
        env="BACKGROUND_TASK_WORKERS",
        description="Number of background task workers"
    )
    
    # Security Configuration
    enable_authentication: bool = Field(
        default=True,
        env="ENABLE_AUTHENTICATION",
        description="Enable API authentication"
    )
    api_key_header: str = Field(
        default="X-API-Key",
        env="API_KEY_HEADER",
        description="API key header name"
    )
    require_https: bool = Field(
        default=False,
        env="REQUIRE_HTTPS",
        description="Require HTTPS for all requests"
    )
    cors_origins: str = Field(
        default="*",
        env="CORS_ORIGINS",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Monitoring Configuration
    enable_metrics: bool = Field(
        default=True,
        env="ENABLE_METRICS",
        description="Enable metrics collection"
    )
    metrics_port: int = Field(
        default=9001,
        env="METRICS_PORT",
        description="Metrics endpoint port"
    )
    health_check_interval: int = Field(
        default=30,
        env="HEALTH_CHECK_INTERVAL",
        description="Health check interval in seconds"
    )
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")
    log_max_size_mb: int = Field(default=100, env="LOG_MAX_SIZE_MB")
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    # Environment Configuration
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")
    
    # Feature Flags
    enable_file_versioning: bool = Field(
        default=False,
        env="ENABLE_FILE_VERSIONING",
        description="Enable file versioning support"
    )
    enable_file_preview: bool = Field(
        default=True,
        env="ENABLE_FILE_PREVIEW",
        description="Enable file preview generation"
    )
    enable_bulk_operations: bool = Field(
        default=True,
        env="ENABLE_BULK_OPERATIONS",
        description="Enable bulk file operations"
    )
    enable_file_search: bool = Field(
        default=True,
        env="ENABLE_FILE_SEARCH",
        description="Enable advanced file search"
    )
    
    # Integration Configuration
    extraction_service_url: str = Field(
        default="http://localhost:8002",
        env="EXTRACTION_SERVICE_URL",
        description="Extraction service base URL"
    )
    extraction_service_timeout: int = Field(
        default=300,  # 5 minutes
        env="EXTRACTION_SERVICE_TIMEOUT",
        description="Extraction service request timeout in seconds"
    )
    auto_request_extraction: bool = Field(
        default=True,
        env="AUTO_REQUEST_EXTRACTION",
        description="Automatically request extraction for uploaded files"
    )
    
    # Cleanup Configuration
    cleanup_temp_files: bool = Field(
        default=True,
        env="CLEANUP_TEMP_FILES",
        description="Automatically cleanup temporary files"
    )
    temp_file_retention_hours: int = Field(
        default=24,
        env="TEMP_FILE_RETENTION_HOURS",
        description="Temporary file retention in hours"
    )
    cleanup_deleted_files_days: int = Field(
        default=30,
        env="CLEANUP_DELETED_FILES_DAYS",
        description="Cleanup soft-deleted files after days"
    )
    
    @validator("allowed_extensions")
    def validate_allowed_extensions(cls, v):
        """Validate and normalize allowed extensions"""
        if not v:
            return []
        extensions = [ext.strip().lower() for ext in v.split(",")]
        # Ensure extensions start with dot
        return [ext if ext.startswith(".") else f".{ext}" for ext in extensions if ext]
    
    @validator("blocked_extensions")
    def validate_blocked_extensions(cls, v):
        """Validate and normalize blocked extensions"""
        if not v:
            return []
        extensions = [ext.strip().lower() for ext in v.split(",")]
        # Ensure extensions start with dot
        return [ext if ext.startswith(".") else f".{ext}" for ext in extensions if ext]
    
    @validator("cors_origins")
    def validate_cors_origins(cls, v):
        """Validate and normalize CORS origins"""
        if v == "*":
            return ["*"]
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get allowed extensions as a list"""
        return self.allowed_extensions if isinstance(self.allowed_extensions, list) else []
    
    @property
    def blocked_extensions_list(self) -> List[str]:
        """Get blocked extensions as a list"""
        return self.blocked_extensions if isinstance(self.blocked_extensions, list) else []
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        return self.cors_origins if isinstance(self.cors_origins, list) else []
    
    @property
    def storage_quota_bytes(self) -> Optional[int]:
        """Get default storage quota in bytes"""
        if self.default_storage_quota_mb is None:
            return None
        return self.default_storage_quota_mb * 1024 * 1024
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"
    
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


# Global settings instance
file_service_settings = FileServiceSettings()


def get_file_service_settings() -> FileServiceSettings:
    """Get file service settings instance"""
    return file_service_settings


# Configuration validation
def validate_file_service_config() -> bool:
    """Validate file service configuration"""
    try:
        settings = get_file_service_settings()
        
        # Check required paths exist
        if settings.storage_create_directories:
            os.makedirs(settings.storage_base_path, exist_ok=True)
        
        # Validate file size limits
        if settings.max_file_size <= 0:
            raise ValueError("max_file_size must be positive")
        
        # Validate extensions
        if not settings.allowed_extensions_list:
            raise ValueError("allowed_extensions cannot be empty")
        
        # Check for conflicts between allowed and blocked extensions
        allowed_set = set(settings.allowed_extensions_list)
        blocked_set = set(settings.blocked_extensions_list)
        conflicts = allowed_set.intersection(blocked_set)
        if conflicts:
            raise ValueError(f"Extensions cannot be both allowed and blocked: {conflicts}")
        
        return True
        
    except Exception as e:
        print(f"File service configuration validation failed: {e}")
        return False


# Export settings for convenience
__all__ = [
    "FileServiceSettings",
    "file_service_settings",
    "get_file_service_settings",
    "validate_file_service_config"
]
