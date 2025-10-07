"""empty message

Revision ID: 58f79584900e
Revises: 
Create Date: 2025-09-30 16:56:44.895372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '58f79584900e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # cf_filerepo_tenant_config
    op.create_table(
        "cf_filerepo_tenant_config",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("configuration", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # cf_filerepo_file
    op.create_table(
        "cf_filerepo_file",
        sa.Column("file_id", sa.String(length=35), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cf_filerepo_tenant_config.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False, unique=True),
        sa.Column("media_type", sa.String(length=256), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=True),
        sa.Column("file_metadata", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )
    op.create_index("idx_cf_filerepo_file_tenant_id", "cf_filerepo_file", ["tenant_id"]) 
    op.create_index("idx_cf_filerepo_file_tag", "cf_filerepo_file", ["tag"]) 
    op.create_index("idx_cf_filerepo_file_created_at", "cf_filerepo_file", ["created_at"]) 

    # cf_filerepo_embeddings
    op.create_table(
        "cf_filerepo_embeddings",
        sa.Column("file_id", sa.String(length=64), sa.ForeignKey("cf_filerepo_file.file_id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("page_id", sa.Integer, primary_key=True, nullable=False),
        sa.Column("embeddings", Vector(1536), nullable=False),
        sa.Column("ocr", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop embeddings
    op.drop_table("cf_filerepo_embeddings")

    # Drop file indexes and table
    op.drop_index("idx_cf_filerepo_file_created_at", table_name="cf_filerepo_file")
    op.drop_index("idx_cf_filerepo_file_tag", table_name="cf_filerepo_file")
    op.drop_index("idx_cf_filerepo_file_tenant_id", table_name="cf_filerepo_file")
    op.drop_table("cf_filerepo_file")

    # Drop tenant table
    op.drop_table("cf_filerepo_tenant_config")

    # Optionally drop extension (comment out if shared)
    op.execute("DROP EXTENSION IF EXISTS vector")
