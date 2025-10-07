from __future__ import annotations

from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from shared.base import Base
from pgvector.sqlalchemy import Vector


class Embedding(Base):
    __tablename__ = "cf_filerepo_embeddings"

    file_id: Mapped[str] = mapped_column(String(64), ForeignKey("cf_filerepo_file.file_id", ondelete="CASCADE"), primary_key=True)
    page_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    embeddings: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    ocr: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


