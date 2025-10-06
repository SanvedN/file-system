from datetime import datetime, timezone
import pydantic
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from file_service.schemas import ConfigSchema
from pydantic import ValidationError
import yaml
import os
import shutil
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
    # Basic sanitization: strip path separators and nulls
    name = name.replace("\x00", "")
    name = os.path.basename(name)
    return name


def tenant_month_folder(tenant_code: str) -> str:
    now = datetime.now(timezone.utc)
    folder = f"{tenant_code}/{now.strftime('%Y-%m')}"
    base = settings.file_repo_storage_base
    return os.path.join(base, folder)


def generate_file_path(tenant_code: str, file_id: str, filename: str) -> str:
    filename = sanitize_filename(filename)
    _, ext = os.path.splitext(filename)
    folder = tenant_month_folder(tenant_code)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{file_id}{ext}")


def delete_tenant_folder(tenant_code: str) -> None:
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    if os.path.exists(path):
        shutil.rmtree(path)
        logger.info("Deleted tenant folder %s", path)
    else:
        logger.debug("Tenant folder %s does not exist", path)


def delete_file_path(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("Deleted file %s", path)
    except Exception:
        logger.exception("Error deleting file path %s", path)


def create_tenant_folder(tenant_code: str):
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    os.makedirs(path, exist_ok=True)  # Creates recursively if not exists


def delete_tenant_folder(tenant_code: str):
    path = os.path.join(settings.file_repo_storage_base, tenant_code)
    if os.path.exists(path) and os.path.isdir(path):
        shutil.rmtree(path)  # Deletes everything inside + the folder
