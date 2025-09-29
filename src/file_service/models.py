from ..shared.db import Base
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from utils import ConfigSchema
import uuid


class Tenant(Base):
    __tablename__ = "tenants"

    # primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(
        String(100)
    )  # Can be null as long as we have the code
    configuration: Mapped[dict] = mapped_column(ConfigSchema, nullable=False)

    def __repr__(self):
        return f"<Tenant(id={self.id}, code={self.code}, configuration={self.configuration})>"
