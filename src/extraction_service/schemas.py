from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class GenerateEmbeddingsResponse(BaseModel):
    file_id: str
    pages_processed: int
    success: bool = True


class EmbeddingPage(BaseModel):
    page_id: int
    ocr: Optional[str] = None
    # Do not return vector by default for size reasons


class GetEmbeddingsResponse(BaseModel):
    file_id: str
    pages: List[EmbeddingPage]


class SearchEmbeddingsRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class SearchMatch(BaseModel):
    file_id: str
    page_id: int
    score: float
    ocr: Optional[str] = None


class SearchEmbeddingsResponse(BaseModel):
    matches: List[SearchMatch]


# Tenant-wide search


class TenantSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class TenantSearchMatch(BaseModel):
    file_id: str
    page_id: int
    score: float
    ocr: Optional[str] = None


class TenantSearchResponse(BaseModel):
    matches: List[TenantSearchMatch]

