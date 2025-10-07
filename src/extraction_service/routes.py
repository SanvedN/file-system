from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from extraction_service.schemas import (
    GenerateEmbeddingsResponse,
    GetEmbeddingsResponse,
    EmbeddingPage,
    SearchEmbeddingsRequest,
    SearchEmbeddingsResponse,
    SearchMatch,
    TenantSearchRequest,
    TenantSearchResponse,
    TenantSearchMatch,
)
from extraction_service.services import (
    generate_embeddings_for_file,
    get_embeddings_for_file,
    search_embeddings_for_file,
    search_embeddings_for_tenant,
)
from shared.db import get_db
from shared.cache import get_redis
from file_service.crud.file import FileCRUD


router = APIRouter(prefix="/v2/tenants", tags=["Embeddings"])


@router.post("/{tenant_id}/embeddings/search", response_model=TenantSearchResponse)
async def search_tenant(tenant_id: str, body: TenantSearchRequest, db: AsyncSession = Depends(get_db)):
    rows = await search_embeddings_for_tenant(db, tenant_id=tenant_id, query=body.query, top_k=body.top_k)
    return TenantSearchResponse(
        matches=[
            TenantSearchMatch(
                file_id=row[0],
                page_id=row[1],
                score=float(row[2]),
                ocr=row[3],
                embeddings=list(row[4]),
            )
            for row in rows
        ]
    )


@router.post("/{tenant_id}/embeddings/{file_id}", response_model=GenerateEmbeddingsResponse)
async def generate(tenant_id: str, file_id: str, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    # Fetch file info
    file = await FileCRUD().get_by_id(db, tenant_id=tenant_id, file_id=file_id)
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    # Validate and process
    return await generate_embeddings_for_file(
        db,
        file_id=file.file_id,
        file_path=file.file_path,
        media_type=file.media_type,
        redis=redis,
    )


@router.get("/{tenant_id}/embeddings/{file_id}", response_model=GetEmbeddingsResponse)
async def get_embeddings(tenant_id: str, file_id: str, db: AsyncSession = Depends(get_db)):
    pages = await get_embeddings_for_file(db, file_id=file_id)
    return GetEmbeddingsResponse(
        file_id=file_id,
        pages=[EmbeddingPage(page_id=p.page_id, ocr=p.ocr) for p in pages],
    )


@router.post("/{tenant_id}/embeddings/search/{file_id}", response_model=SearchEmbeddingsResponse)
async def search(tenant_id: str, file_id: str, body: SearchEmbeddingsRequest, db: AsyncSession = Depends(get_db)):
    rows = await search_embeddings_for_file(db, file_id=file_id, query=body.query, top_k=body.top_k)
    return SearchEmbeddingsResponse(
        matches=[
            SearchMatch(file_id=file_id, page_id=row[0], score=float(row[1]), ocr=row[2])
            for row in rows
        ]
    )


 


