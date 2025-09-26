from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import List, Optional
import os

load_dotenv()


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "postgresql+asyncpg://file_system_user:password@localhost:5432/file_system_db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "file_system_db"
    db_user: str = "file_system_user"
    db_password: str = "password"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Storage Configuration
    storage_base_path: str = "/app/storage"
    max_file_size: int = 104857600  # 100MB
    allowed_extensions: str = ".txt,.pdf,.doc,.docx,.xls,.xlsx,.zip,.json,.csv,.xml"
    max_zip_depth: int = 3
    
    # Service Configuration
    file_service_host: str = "0.0.0.0"
    file_service_port: int = 8001
    extraction_service_host: str = "0.0.0.0"
    extraction_service_port: int = 8002
    api_gateway_host: str = "0.0.0.0"
    api_gateway_port: int = 8000
    
    # Security
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Convert comma-separated extensions to list"""
        return [ext.strip() for ext in self.allowed_extensions.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
