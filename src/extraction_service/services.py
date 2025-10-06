from __future__ import annotations

import io
import os
from typing import Any, List, Tuple
import anyio
import os

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from extraction_service.crud import EmbeddingCRUD
from extraction_service.schemas import GenerateEmbeddingsResponse

from shared.cache import (
    cache_get,
    cache_set,
    cache_get_emb_pages,
    cache_set_emb_pages,
    cache_delete_emb_pages,
    cache_get_search,
    cache_set_search,
    redis_key_for_emb_search_tenant,
    redis_key_for_emb_search_file,
)

# OCR and PDF tools
import pytesseract
from PIL import Image
import fitz  # PyMuPDF

# Embeddings - pluggable; placeholder using sentence-transformers
from sentence_transformers import SentenceTransformer


embedder = SentenceTransformer("all-MiniLM-L6-v2")
crud = EmbeddingCRUD()


def _ensure_pdf(media_type: str):
    if media_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported for embeddings")


async def generate_embeddings_for_file(
    db: AsyncSession,
    *,
    file_id: str,
    file_path: str,
    media_type: str,
    redis=None,
) -> GenerateEmbeddingsResponse:
    _ensure_pdf(media_type)

    # Cache gate (idempotency)
    cache_key = f"embeddings:done:{file_id}"
    try:
        if redis:
            done = await cache_get(cache_key)
            if done:
                pages = await crud.get_by_file(db, file_id=file_id)
                return GenerateEmbeddingsResponse(file_id=file_id, pages_processed=len(pages), success=True)
    except Exception:
        pass

    # Convert PDF pages to images
    try:
        def _render_pages(path: str) -> List[Image.Image]:
            doc = fitz.open(path)
            imgs: List[Image.Image] = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                imgs.append(img)
            doc.close()
            return imgs

        images: List[Image.Image] = await anyio.to_thread.run_sync(lambda: _render_pages(file_path))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to process PDF")

    pages_processed = 0
    for idx, image in enumerate(images, start=1):
        # OCR
        ocr_text = await anyio.to_thread.run_sync(pytesseract.image_to_string, image)
        # Embedding
        vector = await anyio.to_thread.run_sync(lambda: embedder.encode(ocr_text).tolist())
        # Upsert
        await crud.upsert(db, file_id=file_id, page_id=idx, vector=vector, ocr=ocr_text)
        pages_processed += 1

    # Mark done in cache and invalidate pages/search caches
    try:
        if redis:
            await cache_set(cache_key, "1", ex=3600)
            await cache_delete_emb_pages(redis, file_id)
    except Exception:
        pass

    return GenerateEmbeddingsResponse(file_id=file_id, pages_processed=pages_processed, success=True)


async def get_embeddings_for_file(db: AsyncSession, *, file_id: str):
    return await crud.get_by_file(db, file_id=file_id)


async def search_embeddings_for_file(db: AsyncSession, *, file_id: str, query: str, top_k: int):
    qhash = str(abs(hash((query, top_k))))
    key = redis_key_for_emb_search_file(file_id, qhash, top_k)
    # No redis param here; kept simple; cache functions use global client in shared.cache when needed
    qvec = await anyio.to_thread.run_sync(lambda: embedder.encode(query).tolist())
    return await crud.search(db, file_id=file_id, query_vector=qvec, top_k=top_k)


async def search_embeddings_for_tenant(db: AsyncSession, *, tenant_id: str, query: str, top_k: int):
    qhash = str(abs(hash((query, top_k))))
    qvec = await anyio.to_thread.run_sync(lambda: embedder.encode(query).tolist())
    return await crud.search_tenant(db, tenant_id=tenant_id, query_vector=qvec, top_k=top_k)


