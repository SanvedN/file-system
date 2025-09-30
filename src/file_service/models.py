import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.file_service.utils import (
    UserConfigJSON,
    get_default_tenant_configs_from_config,
)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "cf_filerepo_tenant_config"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    configuration: Mapped[dict] = mapped_column(
        UserConfigJSON, nullable=False, default=get_default_tenant_configs_from_config()
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    files: Mapped[list["File"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )

    _immutable_fields = {"tenant_id", "tenant_code", "created_at"}

    def __setattr__(self, key, value):
        if key in self._immutable_fields and hasattr(self, key):
            raise AttributeError(f"'{key}' is immutable and cannot be modified.")
        super().__setattr__(key, value)

    def __repr__(self):
        return (
            f"<Tenant(tenant_id={self.tenant_id}, tenant_code={self.tenant_code}, "
            f"configuration={self.configuration}, created_at={self.created_at}, "
            f"updated_at={self.updated_at})>"
        )


class File(Base):
    __tablename__ = "cf_filerepo_file"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cf_filerepo_tenant_config.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tag: Mapped[str | None] = mapped_column(String(64))
    file_metadata: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="files", lazy="joined")

    __table_args__ = (
        Index("idx_cf_filerepo_file_tenant_id", "tenant_id"),
        Index("idx_cf_filerepo_file_tag", "tag"),
        Index("idx_cf_filerepo_file_created_at", "created_at"),
    )

    _mutable_fields = {"file_name", "tag", "file_metadata"}

    def __setattr__(self, key, value):
        # Allow only _mutable_fields to be updated if attribute already set
        if hasattr(self, key):
            if key not in self._mutable_fields and key not in {"modified_at"}:
                raise AttributeError(f"'{key}' is immutable and cannot be modified.")
        super().__setattr__(key, value)

    def __repr__(self):
        return (
            f"<File(id={self.id}, tenant_id={self.tenant_id}, "
            f"file_name={self.file_name}, file_path={self.file_path}, "
            f"media_type={self.media_type}, file_size_bytes={self.file_size_bytes}, "
            f"tag={self.tag}, created_at={self.created_at}, modified_at={self.modified_at})>"
        )
