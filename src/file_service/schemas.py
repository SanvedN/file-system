from pydantic import BaseModel


class ConfigSchema(BaseModel):

    # this size is in KB - kilobytes
    max_file_size_kbytes: int

    allowed_extensions: list[str]
    forbidden_extensions: list[str]
    allowed_mime_types: list[str]
    forbidden_mime_types: list[str]
    max_zip_depth: int
