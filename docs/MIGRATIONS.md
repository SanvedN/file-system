# Database Migrations with Alembic

This document describes the database migration system implemented using Alembic for the Multi-Tenant Async File Management and Extraction System.

## Overview

The system uses Alembic for database schema version control and migrations. This ensures:

- **Version Control**: All database schema changes are tracked
- **Reproducible Deployments**: Consistent database state across environments
- **Rollback Capability**: Ability to revert schema changes if needed
- **Team Collaboration**: Multiple developers can work on schema changes safely

## Architecture

### Components

1. **Alembic Configuration** (`alembic.ini`)

   - Main Alembic configuration file
   - Database connection settings
   - Migration script location

2. **Migration Environment** (`alembic/env.py`)

   - Async database support
   - Model imports for autogeneration
   - Custom migration logic

3. **Migration Manager** (`src/shared/migrations.py`)

   - High-level migration utilities
   - Integration with application code
   - Status checking and validation

4. **Migration Scripts** (`alembic/versions/`)
   - Individual migration files
   - Schema change definitions
   - Upgrade and downgrade logic

## Usage

### Development Commands

#### Check Migration Status

```bash
make migrate-status
```

#### Create New Migration

```bash
# Auto-generate migration from model changes
make migrate-create MESSAGE="Add new user table"

# Create empty migration for custom changes
make migrate-create MESSAGE="Custom data migration" EMPTY=true
```

#### Apply Migrations

```bash
# Upgrade to latest
make migrate-upgrade

# Upgrade to specific revision
make migrate-upgrade REVISION="0002"
```

#### Rollback Migrations

```bash
# Downgrade to specific revision
make migrate-downgrade REVISION="0001"

# Downgrade to base (removes all tables)
make migrate-downgrade REVISION="base"
```

#### View Migration History

```bash
make migrate-history
```

#### Initialize Database

```bash
make migrate-init
```

#### Reset Database (Development Only)

```bash
make migrate-reset
```

### Programmatic Usage

#### In Application Code

```python
from src.shared.migrations import (
    ensure_database_migrated,
    get_database_schema_version,
    check_database_migration_status
)

# Ensure database is migrated before starting
await ensure_database_migrated()

# Check current schema version
version = await get_database_schema_version()

# Get detailed status
status = await check_database_migration_status()
```

#### Migration Manager

```python
from src.shared.migrations import get_migration_manager

manager = await get_migration_manager()

# Create migration
revision = await manager.create_migration("Add new feature")

# Check status
status = await manager.check_migration_status()

# Upgrade database
success = await manager.upgrade_database("head")
```

## Migration Workflow

### 1. Development Workflow

1. **Make Model Changes**

   ```python
   # Modify models in src/*/models.py
   class NewTable(Base):
       __tablename__ = "new_table"
       # ... new fields
   ```

2. **Generate Migration**

   ```bash
   make migrate-create MESSAGE="Add new table"
   ```

3. **Review Generated Migration**

   ```python
   # Check alembic/versions/XXXX_add_new_table.py
   def upgrade() -> None:
       op.create_table('new_table', ...)

   def downgrade() -> None:
       op.drop_table('new_table')
   ```

4. **Apply Migration**

   ```bash
   make migrate-upgrade
   ```

5. **Test Migration**
   ```bash
   make test
   ```

### 2. Production Deployment

1. **Pre-deployment Check**

   ```bash
   make migrate-status
   ```

2. **Apply Migrations**

   ```bash
   make migrate-upgrade
   ```

3. **Verify Deployment**
   ```bash
   make migrate-status
   ```

## Database Schema

### Current Tables

#### Tenants Table

- **Purpose**: Multi-tenant isolation
- **Key Fields**: `id`, `code`, `name`, `storage_quota_bytes`, `file_count_limit`
- **Indexes**: `code` (unique), `is_active`, `created_at`

#### Files Table

- **Purpose**: File metadata and tracking
- **Key Fields**: `id`, `tenant_id`, `original_filename`, `file_path`, `file_size`
- **Indexes**: `tenant_id`, `tenant_code`, `file_hash`, `status`, `uploaded_at`
- **Foreign Keys**: `tenant_id` → `tenants.id` (CASCADE)

#### Extraction Results Table

- **Purpose**: File extraction results and processing status
- **Key Fields**: `id`, `file_id`, `tenant_id`, `extraction_type`, `status`
- **Indexes**: `file_id`, `tenant_id`, `status`, `extraction_type`, `created_at`
- **Foreign Keys**: `file_id` → `files.id` (CASCADE), `tenant_id` → `tenants.id` (CASCADE)

## Migration Best Practices

### 1. Naming Conventions

- Use descriptive migration names
- Include the feature or change being made
- Use snake_case for migration names

### 2. Migration Content

- Always include both `upgrade()` and `downgrade()` functions
- Test migrations in both directions
- Use transactions for data migrations
- Avoid breaking changes in production

### 3. Data Migrations

```python
def upgrade() -> None:
    # Schema changes
    op.add_column('users', sa.Column('new_field', sa.String(255)))

    # Data migration
    connection = op.get_bind()
    connection.execute(
        text("UPDATE users SET new_field = 'default_value' WHERE new_field IS NULL")
    )

def downgrade() -> None:
    op.drop_column('users', 'new_field')
```

### 4. Index Management

```python
def upgrade() -> None:
    # Create index
    op.create_index('ix_table_field', 'table', ['field'])

    # Create unique index
    op.create_index('ix_table_unique_field', 'table', ['unique_field'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_table_field', 'table')
    op.drop_index('ix_table_unique_field', 'table')
```

## Environment-Specific Configuration

### Development

- Uses SQLite for testing
- Automatic migration on startup
- Reset capability for testing

### Production

- Uses PostgreSQL
- Manual migration control
- Backup before migrations
- Rollback procedures

### Docker/Kubernetes

- Migration jobs for initialization
- Health checks for migration status
- Automated migration on deployment

## Troubleshooting

### Common Issues

#### 1. Migration Conflicts

```bash
# Check current status
make migrate-status

# View migration history
make migrate-history

# Resolve conflicts manually
# Edit migration files as needed
```

#### 2. Failed Migrations

```bash
# Check migration validity
make migrate-validate

# Rollback to previous state
make migrate-downgrade REVISION="previous_revision"

# Fix issues and retry
make migrate-upgrade
```

#### 3. Database Connection Issues

```bash
# Check database connectivity
make db-shell

# Verify environment variables
echo $DATABASE_URL

# Test migration connection
make migrate-status
```

### Recovery Procedures

#### 1. Corrupted Migration State

```bash
# Reset migration state
make migrate-reset

# Re-apply all migrations
make migrate-upgrade
```

#### 2. Partial Migration Failure

```bash
# Check current state
make migrate-status

# Complete migration manually
make migrate-upgrade
```

## Monitoring and Alerting

### Migration Status Monitoring

- Daily migration status checks
- Alert on migration failures
- Track migration execution time
- Monitor database schema version

### Health Checks

```python
# Application health check includes migration status
async def health_check():
    status = await check_database_migration_status()
    return {
        "database_migrated": status["is_up_to_date"],
        "schema_version": status["current_revision"]
    }
```

## Security Considerations

### Migration Security

- Migrations run with database privileges
- Validate migration scripts before execution
- Use parameterized queries for data migrations
- Audit migration execution logs

### Access Control

- Limit migration execution to authorized users
- Use service accounts for automated migrations
- Rotate database credentials regularly
- Monitor migration execution

## Performance Considerations

### Large Table Migrations

- Use batch processing for large data migrations
- Add indexes after data migration
- Consider downtime for major schema changes
- Test migration performance on staging

### Concurrent Access

- Migrations are atomic by default
- Use `transaction_per_migration=True` for safety
- Consider application downtime for breaking changes
- Plan migration windows for production

## Integration with CI/CD

### Automated Testing

```yaml
# GitHub Actions example
- name: Run Migrations
  run: |
    make migrate-upgrade
    make test
    make migrate-downgrade REVISION="base"
```

### Deployment Pipeline

```yaml
# Deployment steps
1. Backup database
2. Run migrations
3. Deploy application
4. Verify deployment
5. Run health checks
```

This migration system provides a robust, production-ready solution for database schema management across all environments.
