from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from src.file_service.utils import UserConfigJSON
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "cf_filerepo_tenant_config"

    # primary key
    tenant_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    tenant_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    configuration: Mapped[dict] = mapped_column(UserConfigJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<Tenant(id={self.id}, code={self.code}, configuration={self.configuration}, "
            f"created_at={self.created_at}, updated_at={self.updated_at})>"
        )
