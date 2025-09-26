from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os
from typing import Annotated

load_dotenv()


class Settings(BaseSettings):
    db_url: str = os.getenv("DB_URL")
    base_path: str = os.getenv("STORAGE_BASE_PATH")
