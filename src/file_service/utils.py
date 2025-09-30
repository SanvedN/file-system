from datetime import datetime, timezone
import pydantic
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from src.file_service.schemas import ConfigSchema
from pydantic import ValidationError
import yaml


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
