"""Initial migration - Create all tables

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all initial tables"""
    
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('storage_quota_bytes', sa.BigInteger(), nullable=True),
        sa.Column('file_count_limit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('settings', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # Create indexes for tenants table
    op.create_index('ix_tenants_code', 'tenants', ['code'], unique=True)
    op.create_index('ix_tenants_is_active', 'tenants', ['is_active'])
    op.create_index('ix_tenants_created_at', 'tenants', ['created_at'])
    
    # Create files table
    op.create_table('files',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('tenant_code', sa.String(length=50), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_extension', sa.String(length=10), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='uploaded'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('uploaded_by', sa.String(length=255), nullable=True),
        sa.Column('upload_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('validation_status', sa.String(length=20), nullable=True),
        sa.Column('validation_details', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for files table
    op.create_index('ix_files_tenant_id', 'files', ['tenant_id'])
    op.create_index('ix_files_tenant_code', 'files', ['tenant_code'])
    op.create_index('ix_files_original_filename', 'files', ['original_filename'])
    op.create_index('ix_files_stored_filename', 'files', ['stored_filename'])
    op.create_index('ix_files_file_hash', 'files', ['file_hash'])
    op.create_index('ix_files_status', 'files', ['status'])
    op.create_index('ix_files_is_deleted', 'files', ['is_deleted'])
    op.create_index('ix_files_uploaded_at', 'files', ['uploaded_at'])
    op.create_index('ix_files_mime_type', 'files', ['mime_type'])
    op.create_index('ix_files_file_extension', 'files', ['file_extension'])
    op.create_index('ix_files_validation_status', 'files', ['validation_status'])
    op.create_index('ix_files_tenant_status', 'files', ['tenant_id', 'status'])
    op.create_index('ix_files_tenant_deleted', 'files', ['tenant_id', 'is_deleted'])
    
    # Create extraction_results table
    op.create_table('extraction_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('extraction_type', sa.String(length=50), nullable=False),
        sa.Column('extractor_version', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('structured_data', sa.Text(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('file_analysis', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('memory_usage_mb', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('extraction_config', sa.Text(), nullable=True),
        sa.Column('extraction_quality', sa.Text(), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for extraction_results table
    op.create_index('ix_extraction_results_file_id', 'extraction_results', ['file_id'])
    op.create_index('ix_extraction_results_tenant_id', 'extraction_results', ['tenant_id'])
    op.create_index('ix_extraction_results_status', 'extraction_results', ['status'])
    op.create_index('ix_extraction_results_extraction_type', 'extraction_results', ['extraction_type'])
    op.create_index('ix_extraction_results_created_at', 'extraction_results', ['created_at'])
    op.create_index('ix_extraction_results_started_at', 'extraction_results', ['started_at'])
    op.create_index('ix_extraction_results_completed_at', 'extraction_results', ['completed_at'])
    op.create_index('ix_extraction_results_confidence_score', 'extraction_results', ['confidence_score'])
    op.create_index('ix_extraction_results_retry_count', 'extraction_results', ['retry_count'])
    op.create_index('ix_extraction_results_tenant_status', 'extraction_results', ['tenant_id', 'status'])
    op.create_index('ix_extraction_results_file_status', 'extraction_results', ['file_id', 'status'])


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('extraction_results')
    op.drop_table('files')
    op.drop_table('tenants')
