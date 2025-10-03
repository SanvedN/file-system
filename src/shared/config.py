from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    file_repo_db_name: str
    file_repo_db_username: str
    file_repo_db_password: str
    file_repo_db_host: str
    file_repo_db_port: int

    file_repo_redis_host: str
    file_repo_redis_port: int
    file_repo_redis_db_number: int

    file_repo_storage_base: str
    file_repo_temp_base: str

    file_repo_log_level: str
    file_repo_log_format: str

    file_repo_cors_origins: str
    file_repo_host: str
    file_repo_port: int

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
