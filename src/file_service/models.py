from sqlalchemy import String, DateTime, Integer, Text, BigInteger, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from uuid import uuid4
import uuid

from ..shared.db import Base


class Tenant(Base):
    __tablename__ = "tenants"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Tenant information
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status and configuration
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    storage_quota_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)  # Storage quota in bytes
    file_count_limit: Mapped[Optional[int]] = mapped_column(Integer)  # Maximum number of files
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Settings (JSON-like storage)
    settings: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for tenant-specific settings
    
    # Relationships
    files: Mapped[List["File"]] = relationship("File", back_populates="tenant", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_tenant_code', 'code'),
        Index('idx_tenant_active', 'is_active'),
        Index('idx_tenant_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, code={self.code}, name={self.name})>"


class File(Base):
    __tablename__ = "files"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Tenant relationship
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # File information
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # Full path to stored file
    
    # File metadata
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256 hash
    
    # Status and processing
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False)  # uploaded, processing, completed, error
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Upload metadata
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255))
    upload_ip: Mapped[Optional[str]] = mapped_column(String(45))  # Support IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Processing metadata
    processing_status: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for processing details
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # File validation
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, passed, failed
    validation_details: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for validation results
    
    # Extraction relationship (will be defined in extraction service)
    extraction_results: Mapped[List["ExtractionResult"]] = relationship(
        "ExtractionResult", 
        back_populates="file",
        cascade="all, delete-orphan",
        foreign_keys="ExtractionResult.file_id"
    )
    
    # Tenant relationship
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="files")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_tenant_id', 'tenant_id'),
        Index('idx_file_tenant_code', 'tenant_code'),
        Index('idx_file_status', 'status'),
        Index('idx_file_uploaded_at', 'uploaded_at'),
        Index('idx_file_deleted', 'is_deleted'),
        Index('idx_file_hash', 'file_hash'),
        Index('idx_file_extension', 'file_extension'),
        Index('idx_file_size', 'file_size'),
        Index('idx_file_tenant_uploaded', 'tenant_id', 'uploaded_at'),
        Index('idx_file_tenant_status', 'tenant_id', 'status'),
    )
    
    def __repr__(self):
        return f"<File(id={self.id}, tenant_code={self.tenant_code}, filename={self.original_filename})>"
    
    @property
    def is_zip_file(self) -> bool:
        """Check if file is a zip file"""
        return self.file_extension.lower() == '.zip'
    
    @property
    def storage_directory(self) -> str:
        """Get the storage directory path"""
        import os
        return os.path.dirname(self.file_path)
    
    def get_display_size(self) -> str:
        """Get human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
