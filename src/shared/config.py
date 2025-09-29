from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    postgres_url: str = os.getenv("POSTGRES_URL")

    # Redis URL configs
    redis_host: str = os.getenv("REDIS_HOST")
    redis_port: int = int(os.getenv("REDIS_PORT"))
    redis_db: int = int(os.getenv("REDIS_DB"))

    # Storage Configs
    storage_path: str = os.getenv("STORAGE_PATH")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()