from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):

    # PgSQL URL configs
    file_repo_db_name: str = os.getenv("FILE_REPO_DB_NAME")
    file_repo_db_username: str = os.getenv("FILE_REPO_DB_USERNAME")
    file_repo_db_password: str = os.getenv("FILE_REPO_DB_PASSWORD")
    file_repo_db_host: str = os.getenv("FILE_REPO_DB_HOST")
    file_repo_db_port: int = int(os.getenv("FILE_REPO_DB_PORT"))

    # Redis URL configs
    file_repo_redis_host: str = os.getenv("FILE_REPO_REDIS_HOST")
    file_repo_redis_port: int = int(os.getenv("FILE_REPO_REDIS_PORT"))
    file_repo_redis_db_number: int = int(os.getenv("FILE_REPO_REDIS_DB_NUMBER"))

    # Storage Configs
    file_repo_storage_base: str = os.getenv("FILE_REPO_STORAGE_BASE")
    file_repo_temp_base: str = os.getenv("FILE_REPO_TEMP_BASE")

    # Logging Configs
    file_repo_log_level: str = os.getenv("FILE_REPO_LOG_LEVEL")
    file_repo_log_format: str = os.getenv("FILE_REPO_LOG_FORMAT")

    # FastAPI configs
    file_repo_cors_origins: str = os.getenv("FILE_REPO_CORS_ORIGINS")
    file_repo_host: str = os.getenv("FILE_REPO_HOST")
    file_repo_port: int = int(os.getenv("FILE_REPO_PORT"))

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def file_repo_redis_url(self) -> str:
        return f"redis://{self.file_repo_redis_host}:{self.file_repo_redis_port}/{self.file_repo_redis_db_number}"

    @property
    def file_repo_postgresql_url(self) -> str:
        return f"postgresql+asyncpg://{self.file_repo_db_username}:{self.file_repo_db_password}@{self.file_repo_db_host}:{self.file_repo_db_port}/{self.file_repo_db_name}"

    @property
    def file_repo_allowed_origins(self) -> list[str]:
        return [s.strip() for s in self.file_repo_cors_origins.split(",")]


settings = Settings()
