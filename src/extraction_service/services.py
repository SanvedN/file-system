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
from shared.rate_limiter import check_embedding_rate_limit

# OCR and PDF tools
import pytesseract
from PIL import Image
import fitz  # PyMuPDF

# Embeddings - pluggable; placeholder using sentence-transformers
from sentence_transformers import SentenceTransformer

from shared.utils import logger


embedder = SentenceTransformer("all-MiniLM-L6-v2")
crud = EmbeddingCRUD()


def _ensure_pdf(media_type: str):
    if media_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported for embeddings")


def _validate_pdf_content(file_path: str) -> None:
    """Validate that file is actually a valid PDF by content"""
    try:
        # Check PDF magic bytes
        with open(file_path, 'rb') as f:
            header = f.read(8)
            if not header.startswith(b'%PDF-'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File does not appear to be a valid PDF (missing PDF signature)"
                )
        
        # Try to open with PyMuPDF to validate structure
        doc = fitz.open(file_path)
        
        # Check if PDF is password protected
        if doc.is_encrypted:
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password-protected PDFs are not supported"
            )
        
        # Check if PDF has pages
        if doc.page_count == 0:
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF file contains no pages"
            )
        
        # Check if PDF is too large (more than 100 pages)
        if doc.page_count > 100:
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF file is too large (more than 100 pages). Please split into smaller files."
            )
        
        doc.close()
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PDF file: {str(e)}"
        )


async def generate_embeddings_for_file(
    db: AsyncSession,
    *,
    file_id: str,
    file_path: str,
    media_type: str,
    tenant_id: str = None,
    redis=None,
) -> GenerateEmbeddingsResponse:
    _ensure_pdf(media_type)
    
    # Check rate limit for embedding generation
    if tenant_id:
        await check_embedding_rate_limit(tenant_id, redis)
    
    # Validate PDF content before processing
    _validate_pdf_content(file_path)

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
        try:
            # OCR with error handling
            ocr_text = await anyio.to_thread.run_sync(pytesseract.image_to_string, image)
            
            # Skip pages with no text (blank pages)
            if not ocr_text or not ocr_text.strip():
                logger.info(f"Skipping blank page {idx} for file {file_id}")
                continue
            
            # Embedding
            vector = await anyio.to_thread.run_sync(lambda: embedder.encode(ocr_text).tolist())
            
            # Upsert
            await crud.upsert(db, file_id=file_id, page_id=idx, vector=vector, ocr=ocr_text)
            pages_processed += 1
            
        except Exception as e:
            logger.warning(f"Failed to process page {idx} for file {file_id}: {e}")
            # Continue with other pages instead of failing completely
            continue

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
    qvec = await anyio.to_thread.run_sync(lambda: embedder.encode(query).tolist())
    return await crud.search(db, file_id=file_id, query_vector=qvec, top_k=top_k)


async def search_embeddings_for_tenant(db: AsyncSession, *, tenant_id: str, query: str, top_k: int):
    qhash = str(abs(hash((query, top_k))))
    qvec = await anyio.to_thread.run_sync(lambda: embedder.encode(query).tolist())
    return await crud.search_tenant(db, tenant_id=tenant_id, query_vector=qvec, top_k=top_k)


