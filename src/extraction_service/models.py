from sqlalchemy import String, DateTime, Integer, Text, BigInteger, Boolean, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..shared.db import Base


class ExtractionResult(Base):
    __tablename__ = "extraction_results"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # File relationship
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # Extraction metadata
    extraction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # text, metadata, structured_data, etc.
    extractor_version: Mapped[str] = mapped_column(String(20), default="1.0")
    
    # Processing status
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    
    # Extraction results
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    structured_data: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    metadata: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    
    # File analysis
    file_analysis: Mapped[Optional[str]] = mapped_column(Text)  # JSON string with file analysis
    confidence_score: Mapped[Optional[float]] = mapped_column()  # Extraction confidence (0.0 - 1.0)
    
    # Processing details
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    memory_usage_mb: Mapped[Optional[float]] = mapped_column()
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Processing configuration
    extraction_config: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for extraction parameters
    
    # Quality metrics
    extraction_quality: Mapped[Optional[str]] = mapped_column(Text)  # JSON string with quality metrics
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="extraction_results")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_file_id', 'file_id'),
        Index('idx_extraction_tenant_id', 'tenant_id'),
        Index('idx_extraction_status', 'status'),
        Index('idx_extraction_type', 'extraction_type'),
        Index('idx_extraction_created', 'created_at'),
        Index('idx_extraction_completed', 'completed_at'),
        Index('idx_extraction_tenant_status', 'tenant_id', 'status'),
        Index('idx_extraction_file_status', 'file_id', 'status'),
    )
    
    def __repr__(self):
        return f"<ExtractionResult(id={self.id}, file_id={self.file_id}, status={self.status})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if extraction is completed"""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Check if extraction failed"""
        return self.status == "failed"
    
    @property
    def is_processing(self) -> bool:
        """Check if extraction is currently processing"""
        return self.status == "processing"
    
    @property
    def can_retry(self) -> bool:
        """Check if extraction can be retried"""
        return self.retry_count < self.max_retries and self.status == "failed"
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get processing duration in seconds"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    def get_processing_summary(self) -> dict:
        """Get a summary of processing metrics"""
        return {
            "status": self.status,
            "progress": self.progress_percentage,
            "duration_seconds": self.duration_seconds,
            "memory_usage_mb": self.memory_usage_mb,
            "processing_time_ms": self.processing_time_ms,
            "confidence_score": self.confidence_score,
            "retry_count": self.retry_count,
            "validation_passed": self.validation_passed
        }
