from pydantic import BaseModel

class ConfigSchema(BaseModel):

    # this size is in KB - kilobytes
    max_size: int

    allowed_extensions: list[str]
    media_types: list[str]
    max_zip_depth: int