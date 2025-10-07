import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime


class ConfigSchema(BaseModel):
    max_file_size_kbytes: int
    allowed_extensions: Optional[list[str]] = Field(default_factory=list)
    allowed_mime_types: Optional[list[str]] = Field(default_factory=list)
    forbidden_extensions: Optional[list[str]] = Field(default_factory=list)
    forbidden_mime_types: Optional[list[str]] = Field(default_factory=list)
    max_zip_depth: int = 0


TENANT_CODE_REGEX = re.compile(r"^[A-Z][A-Z0-9]*$")


class TenantConfig(BaseModel):
    max_file_size_kbytes: Optional[int] = Field(
        None, gt=0, description="Maximum allowed file size in kilobytes"
    )
    allowed_extensions: Optional[List[str]] = Field(
        None,
        description="List of allowed file extensions (with leading dot, e.g. .pdf)",
    )
    forbidden_extensions: Optional[List[str]] = Field(
        None, description="Explicitly forbidden extensions"
    )
    allowed_mime_types: Optional[List[str]] = Field(
        None, description="Allowed MIME types"
    )
    forbidden_mime_types: Optional[List[str]] = Field(
        None, description="Forbidden MIME types"
    )
    max_zip_depth: Optional[int] = Field(
        0, ge=0, description="How many nested zips allowed (0 = not allowed)"
    )

    @field_validator("allowed_extensions", "forbidden_extensions", mode="before")
    @classmethod
    def ensure_extension_format(cls, v: List[str]):
        if v is None:
            return v
        return [cls._validate_extension(ext) for ext in v]

    @staticmethod
    def _validate_extension(v: str) -> str:
        if not v:
            raise ValueError("extensions must be non-empty strings")
        if not v.startswith("."):
            raise ValueError("extensions must start with a dot, e.g. .pdf")
        return v.lower()

    @field_validator("max_file_size_kbytes")
    @classmethod
    def positive_kbytes(cls, v):
        if v is not None and v <= 0:
            raise ValueError("max_file_size_kbytes must be greater than 0")
        return v

    @field_validator("allowed_mime_types", "forbidden_mime_types", mode="before")
    @classmethod
    def ensure_mime_format(cls, v: List[str]):
        if v is None:
            return v
        return [cls._validate_mime(mime) for mime in v]

    @staticmethod
    def _validate_mime(v: str) -> str:
        if not v or "/" not in v:
            raise ValueError("invalid mime type")
        return v.lower()


class TenantCreate(BaseModel):
    tenant_code: str = Field(
        ..., max_length=32, description="Tenant-provided unique code."
    )
    configuration: Optional[TenantConfig] = None

    @field_validator("tenant_code")
    @classmethod
    def validate_code(cls, v: str):
        if not TENANT_CODE_REGEX.match(v):
            raise ValueError(
                "tenant code must start with a capital letter and contain only A-Z0-9"
            )
        return v


class TenantUpdate(BaseModel):
    configuration: Optional[TenantConfig] = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(validate_by_name=True, from_attributes=True)
    tenant_id: UUID
    tenant_code: str
    configuration: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

# ---------------------- File Schemas ----------------------


TAG_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_]{0,63}$")


class FileUpdateRequest(BaseModel):
    tag: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, v: Optional[str]):
        if v is None:
            return v
        if not TAG_REGEX.match(v):
            raise ValueError(
                "tag must match ^[a-zA-Z0-9][a-zA-Z0-9_]{0,63}$ and cannot start with _"
            )
        return v


class FileResponse(BaseModel):
    model_config = ConfigDict(validate_by_name=True, from_attributes=True)
    id: str = Field(alias="file_id")
    file_name: str
    media_type: str
    file_size_bytes: int
    tag: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="file_metadata")
    created_at: datetime
    modified_at: datetime


class FileSearchFilters(BaseModel):
    file_name: Optional[str] = None
    media_type: Optional[str] = None
    tag: Optional[str] = None
    file_size_min: Optional[int] = None
    file_size_max: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class FileSearchSort(BaseModel):
    field: Optional[str] = Field(default="created_at")
    order: Optional[str] = Field(default="desc")


class FileSearchPagination(BaseModel):
    page: int = 1
    limit: int = 50


class FileSearchRequest(BaseModel):
    filters: FileSearchFilters = Field(default_factory=FileSearchFilters)
    sort: FileSearchSort = Field(default_factory=FileSearchSort)
    pagination: FileSearchPagination = Field(default_factory=FileSearchPagination)


class FileSearchResponse(BaseModel):
    files: List[FileResponse]
    pagination: Dict[str, Any]