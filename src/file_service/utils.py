from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from schemas import ConfigSchema
from pydantic import ValidationError


# Creating JSON schema Validator
class UserConfigJSON(TypeDecorator):
    impl = JSONB

    def process_bind_param(self, value, dialect):
        if value is not None:
            try:
                validated = ConfigSchema(**value)
            except ValidationError as e:
                raise ValidationError("Invalid user configuration JSON: {e}")
        return value
