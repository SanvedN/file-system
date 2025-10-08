from datetime import datetime, timezone
from pathlib import Path
import pydantic
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from file_service.schemas import ConfigSchema
from pydantic import ValidationError
import yaml
import os
import shutil
import time
from datetime import datetime
from typing import Tuple
from shared.config import settings
from shared.utils import setup_logger

logger = setup_logger()


# Creating JSON schema Validator
class UserConfigJSON(TypeDecorator):
    impl = JSONB

    def process_bind_param(self, value, dialect):
        if value is not None:
            try:
                validated = ConfigSchema(**value)
            except pydantic.ValidationError as e:
                raise ValueError("Invalid user configuration JSON: {e}")
        return value


def get_default_tenant_configs_from_config(
    path: str = "./src/file_service/tenant_config.yaml",
) -> UserConfigJSON:
    try:
        with open(path, "r") as file:
            config: UserConfigJSON = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        raise FileNotFoundError(f"YAML config file not found at path: {path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file at {path}: {e}")


def generate_file_path(
    tenant_code: str, file_id: str, filename: str, dt: datetime | None = None
) -> str:
    ext = filename.rsplit(".", 1)[-1]
    date_str = (dt or datetime.now(timezone.utc)).strftime("%Y_%m")
    return f"{tenant_code}/{date_str}/{file_id}.{ext}"


def sanitize_filename(name: str) -> str:
    """
    Clean filename to prevent security issues.
    Removes dangerous characters and path traversal attempts.
    """
    if not name:
        return "unnamed_file"
    
    # Remove null bytes and dangerous characters
    name = name.replace("\x00", "")
    name = name.replace("..", "")  # Prevent path traversal
    name = name.replace("/", "_")  # Replace path separators
    name = name.replace("\\", "_")  # Replace Windows path separators
    
    # Get just the filename, not the full path
    name = os.path.basename(name)
    
    # Limit filename length
    if len(name) > 200:
        name = name[:200]
    
    # If empty after cleaning, give it a default name
    if not name or name == "." or name == "..":
        name = f"file_{int(time.time())}"
    
    return name


def tenant_month_folder(tenant_code: str) -> str:
    now = datetime.now(timezone.utc)
    folder = f"{tenant_code}/{now.strftime('%Y-%m')}"
    base = settings.file_repo_storage_base
    return os.path.join(base, folder)


def generate_file_path(tenant_code: str, file_id: str, filename: str) -> str:
    """
    Generate file path without creating directories.
    Directory creation should be handled separately.
    """
    filename = sanitize_filename(filename)
    _, ext = os.path.splitext(filename)
    folder = tenant_month_folder(tenant_code)
    return os.path.join(folder, f"{file_id}{ext}")


def ensure_tenant_directory(tenant_code: str) -> str:
    """
    Ensure tenant directory exists and return the path.
    """
    folder = tenant_month_folder(tenant_code)
    _ensure_directory_exists(folder)
    return folder


def _ensure_directory_exists(path: str) -> None:
    """
    Ensure directory exists with robust error handling for Windows.
    """
    if os.path.exists(path) and os.path.isdir(path):
        return  # Directory already exists
    
    try:
        os.makedirs(path, exist_ok=True)
    except (FileExistsError, OSError) as e:
        # On Windows, sometimes FileExistsError occurs even with exist_ok=True
        # Check if directory actually exists now
        if not (os.path.exists(path) and os.path.isdir(path)):
            # Directory still doesn't exist, this is a real error
            raise e
        # Directory exists now, which is what we wanted


def delete_tenant_folder(tenant_code: str) -> None:
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    if os.path.exists(path):
        shutil.rmtree(path)
        logger.info("Deleted tenant folder %s", path)
    else:
        logger.debug("Tenant folder %s does not exist", path)


def delete_file_path(path: str) -> None:
    try:
        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            logger.info("Deleted file: %s", file_path.as_posix())
        else:
            logger.warning("File not found or not a regular file: %s", file_path.as_posix())
    except Exception as e:
        logger.exception("Error deleting file path %s: %s", path, str(e))


def create_tenant_folder(tenant_code: str):
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    os.makedirs(path, exist_ok=True)  # Creates recursively if not exists


def delete_tenant_folder(tenant_code: str):
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    if os.path.exists(path) and os.path.isdir(path):
        shutil.rmtree(path)  # Deletes everything inside + the folder
