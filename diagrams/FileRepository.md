# File Repository Service - Python FastAPI Assignment

## Overview
Build a secure, multi-tenant file storage and management service using Python and FastAPI. This service will provide comprehensive file operations and multi-tenant configuration management.

## Database Schema

### 1. cf_filerepo_file
```sql
CREATE TABLE cf_filerepo_file (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id INT NOT NULL,
    file_name VARCHAR(256),
    file_path VARCHAR(512),
    media_type VARCHAR(256),
    file_size_bytes BIGINT,
    tag VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    modified_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cf_filerepo_file_tenant_id ON cf_filerepo_file(tenant_id);
CREATE INDEX idx_cf_filerepo_file_tag ON cf_filerepo_file(tag);
CREATE INDEX idx_cf_filerepo_file_created_at ON cf_filerepo_file(created_at);
```

### 2. cf_filerepo_tenant_config
```sql
CREATE TABLE cf_filerepo_tenant_config (
    tenant_id INT PRIMARY KEY,
    tenant_code VARCHAR(16) UNIQUE,
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    modified_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3. cf_filerepo_embeddings
```sql
CREATE TABLE cf_filerepo_embeddings (
    file_id VARCHAR(64) NOT NULL,
    page_id INT NOT NULL,
    embeddings VECTOR(1536),
    ocr TEXT,
    FOREIGN KEY (file_id) REFERENCES cf_filerepo_file(id) ON DELETE CASCADE,
    PRIMARY KEY (file_id, page_id)
);

CREATE INDEX idx_cf_filerepo_embeddings_file_id ON cf_filerepo_embeddings(file_id);
```

## REST API Endpoints

### File Operations
- `POST /v1/tenants/{tenant_id}/upload?tag=invoice` - Upload a single file for a specific tenant (Content-Type: multipart/form-data, tag parameter for file categorization)
- `GET /v1/tenants/{tenant_id}/download/{file_id}?inline=true` - Download a specific file (inline=true for inline display, false for attachment)
- `POST /v1/tenants/{tenant_id}/files/search` - Search and filter files for a tenant
- `GET /v1/tenants/{tenant_id}/files/{file_id}` - Get details of a specific file
- `POST /v1/tenants/{tenant_id}/files/{file_id}` - Update file metadata and tag
- `DELETE /v1/tenants/{tenant_id}/files/{file_id}` - Delete a specific file

### Tenant Management
- `GET /v1/tenants/{tenant_id}/config` - Get tenant-specific configuration
- `POST /v1/tenants/{tenant_id}/config` - Update tenant configuration
- `DELETE /v1/tenants/{tenant_id}` - Delete a tenant and all associated files

### Embeddings
- `POST /v1/tenants/{tenant_id}/embeddings/{file_id}` - Generate embeddings for a PDF file (splits PDF into pages, converts each page to image, performs OCR, and stores both OCR text and embeddings)
- `GET /v1/tenants/{tenant_id}/embeddings/{file_id}` - Retrieve embeddings for a specific file
- `POST /v1/tenants/{tenant_id}/embeddings/search/{file_id}` - Search for best matching pages based on query embeddings

### Health Check
- `GET /ping` - Health check endpoint

## File Update API Details

### POST /v1/tenants/{tenant_id}/files/{file_id}
**Request Body (JSON):**
```json
{
  "tag": "updated_invoice",
  "metadata": {
    "department": "finance",
    "priority": "high",
    "project_id": "PRJ-2024-001",
    "client_id": 456
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "File updated successfully",
  "file": {
    "id": "CF_FR_abc123",
    "file_name": "document.pdf",
    "tag": "updated_invoice",
    "metadata": {
      "department": "finance",
      "priority": "high",
      "project_id": "PRJ-2024-001",
      "client_id": "CLIENT-456"
    },
    "modified_at": "2024-03-15T15:45:00Z"
  }
}
```

## Data Validation Rules

### Tag Restrictions
- Maximum length: 64 characters
- Allowed characters: alphanumeric (a-z, A-Z, 0-9) and underscore (_)
- Cannot start with an underscore character
- Pattern: `^[a-zA-Z0-9][a-zA-Z0-9_]{0,63}$`

### Tenant Code Restrictions
- Must start with a capital letter
- Allowed characters: capital letters (A-Z) and numbers (0-9)
- Pattern: `^[A-Z][A-Z0-9]*$`

## File Search API Details

### POST /v1/tenants/{tenant_id}/files/search
**Request Body (JSON):**
```json
{
  "filters": {
    "file_name": "document.pdf",           // Exact or partial match
    "media_type": "application/pdf",       // Filter by MIME type
    "tag": "invoice",                      // Filter by file tag
    "file_size_min": 1024,                // Minimum file size in bytes
    "file_size_max": 10485760,            // Maximum file size in bytes (10MB)
    "created_after": "2024-01-01T00:00:00Z",  // ISO 8601 timestamp
    "created_before": "2024-12-31T23:59:59Z", // ISO 8601 timestamp
    "metadata": {                          // Filter by metadata fields
      "department": "finance",
      "priority": "high"
    }
  },
  "sort": {
    "field": "created_at",                 // Sort field: created_at, modified_at, file_size_bytes, file_name
    "order": "desc"                       // asc or desc
  },
  "pagination": {
    "page": 1,                            // Page number (1-based)
    "limit": 50                           // Results per page (max 100)
  },
}
```

**Response:**
```json
{
  "files": [
    {
      "id": "CF_FR_abc123",
      "file_name": "document.pdf",
      "media_type": "application/pdf",
      "file_size_bytes": 2048576,
      "tag": "invoice",
      "metadata": {
        "department": "finance",
        "priority": "high"
      },
      "created_at": "2024-03-15T10:30:00Z",
      "modified_at": "2024-03-15T10:30:00Z",
      "expired_at": "2024-09-15T10:30:00Z"
    },
    {
      ....
    },
    {
      ....
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_pages": 5,
    "total_files": 247
  }
}
```

## Configuration

### Required Environment Variables
- `FILE_REPO_DB_NAME` - Database name
- `FILE_REPO_DB_USERNAME` - Database username
- `FILE_REPO_DB_PASSWORD` - Database password

### Optional Environment Settings
- `FILE_REPO_HOST` - Server host (default: 0.0.0.0)
- `FILE_REPO_PORT` - Server port (default: 8000)
- `FILE_REPO_DB_HOST` - Database host
- `FILE_REPO_DB_PORT` - Database port (default: 5432)
- `FILE_REPO_STORAGE_BASE` - File storage base directory
- `FILE_REPO_TEMP_BASE` - Temporary storage directory
- `FILE_REPO_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `FILE_REPO_CORS_ORIGINS` - Comma-separated list of allowed CORS origins

### Configuration File (config.yaml)
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["*"]

database:
  host: "localhost"
  port: 5432

storage:
  base_path: "/app/storage"
  temp_path: "/app/temp"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Tenant Configuration JSON Schema
The tenant configuration stored in `cf_filerepo_tenant_config.config` JSONB field:

```json
{
  "max_file_size_kbytes": 2048,
  "allowed_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".txt", ".doc", ".docx"],
  "forbidden_extensions": [".zip"],
  "allowed_mime_types": [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
  ],
  "forbidden_mime_types": [
    "application/msword",
  ],
}
```

## Technical Requirements

### Framework & Libraries
- **FastAPI** - Main web framework
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migrations
- **PostgreSQL** - Primary database
- **Pydantic** - Data validation and serialization

### Core Features to Implement

1. **Multi-tenant Architecture**
   - Tenant isolation through tenant_id
   - Per-tenant configuration management
   - Secure file storage organization

2. **File Management**
   - File upload with metadata extraction
   - ZIP file handling: extract to temporary folder and validate all file extensions against allowed list
   - Organized storage by tenant and date (`{tenant_code}/{YYYY_MM}/{file_id}.ext`)
   - Media type detection and validation

3. **Security & Middleware**
   - Request validation and sanitization
   - Tenant context middleware
   - File access permissions
   - Input validation for null characters

4. **Advanced File Operations**
   - Tag-based file categorization
   - Custom metadata storage

### File Storage Structure
```
{STORAGE_BASE}/
├── {TENANT_CODE}/
│   └── {YYYY_MM}/
│       └── {FILE_ID}.{extension}
```

## Deliverables

1. **FastAPI Application** with all endpoints implemented
2. **Database Models** using SQLAlchemy
3. **Migration Scripts** using Alembic
4. **Configuration Management** with environment variables
5. **Basic Testing** with pytest and TestContainers for integration tests
6. **Docker Setup** for easy deployment
7. **API Documentation** (auto-generated with FastAPI)

## Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directories
RUN mkdir -p /app/storage /app/temp

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
