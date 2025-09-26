# Multi-Tenant Async File Management and Extraction System

A production-ready, multi-tenant asynchronous file management and extraction system built with FastAPI, SQLAlchemy, and Redis. This system provides secure file storage, processing, and extraction capabilities with full async operations and microservices architecture.

## 🏗️ Architecture

The system consists of three main microservices:

- **File Service** (Port 8001): Handles file upload, storage, and management
- **Extraction Service** (Port 8002): Processes files and extracts structured data
- **API Gateway** (Port 8000): Routes requests and provides unified API access

### Key Features

✅ **Multi-tenant Architecture** - Complete tenant isolation with quota management  
✅ **Async Operations** - Full async/await support with FastAPI and SQLAlchemy  
✅ **Redis Caching** - High-performance caching for metadata and repeated queries  
✅ **File Validation** - Comprehensive validation including size, type, and zip depth  
✅ **Storage Management** - Organized storage with format: `storage_base_path/<tenant_code>/YYYY-MM/`  
✅ **Production Ready** - Docker containers, Kubernetes manifests, health checks  
✅ **Comprehensive Testing** - Unit, integration, and async test coverage  
✅ **Monitoring & Logging** - Structured logging with health check endpoints

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Local Development

1. **Clone and setup**

```bash
git clone <repository-url>
cd file_system
cp env.example .env
# Edit .env with your configuration
```

2. **Install dependencies**

```bash
make install
```

3. **Start services with Docker Compose**

```bash
make docker-up
```

4. **Run database migrations**

```bash
make migrate
```

5. **Access the services**

- File Service API: http://localhost:8001/docs
- Extraction Service API: http://localhost:8002/docs
- API Gateway: http://localhost:8000/docs

### Production Deployment

#### Docker Compose

```bash
# Production deployment
make deploy-docker

# Scale services
docker-compose up --scale file-service=3 --scale extraction-service=2
```

#### Kubernetes

```bash
# Deploy to Kubernetes
make deploy-k8s

# Check status
make k8s-status
```

## 📊 API Documentation

### File Service Endpoints

#### Tenant Management

- `POST /api/v1/tenants/` - Create tenant
- `GET /api/v1/tenants/{tenant_code}` - Get tenant details
- `PUT /api/v1/tenants/{tenant_code}` - Update tenant
- `DELETE /api/v1/tenants/{tenant_code}` - Delete tenant
- `GET /api/v1/tenants/{tenant_code}/stats` - Get tenant statistics

#### File Management

- `POST /api/v1/files/upload` - Upload file
- `GET /api/v1/files/{file_id}` - Get file metadata
- `GET /api/v1/files/{file_id}/download` - Download file
- `DELETE /api/v1/files/{file_id}` - Delete file
- `GET /api/v1/files/tenant/{tenant_code}` - List files for tenant
- `POST /api/v1/files/search` - Advanced file search
- `POST /api/v1/files/bulk-delete` - Bulk delete files

### Extraction Service Endpoints

#### Extraction Management

- `POST /api/v1/extractions/` - Request extraction
- `GET /api/v1/extractions/{extraction_id}` - Get extraction result
- `POST /api/v1/extractions/search` - Search extractions
- `GET /api/v1/extractions/file/{file_id}` - Get extractions for file
- `POST /api/v1/extractions/bulk` - Bulk extraction request
- `POST /api/v1/extractions/retry` - Retry failed extractions

#### Processing & Statistics

- `GET /api/v1/extractions/queue/pending` - Get pending extractions
- `GET /api/v1/extractions/stats/global` - Global extraction statistics
- `POST /api/v1/extractions/admin/cleanup` - Cleanup old extractions

## 🗄️ Database Schema

### Tenants Table

```sql
- id (UUID, Primary Key)
- code (String, Unique, Index)
- name (String)
- description (Text, Optional)
- is_active (Boolean)
- storage_quota_bytes (BigInteger, Optional)
- file_count_limit (Integer, Optional)
- created_at (DateTime)
- updated_at (DateTime)
```

### Files Table

```sql
- id (UUID, Primary Key)
- tenant_id (UUID, Foreign Key)
- tenant_code (String, Index)
- original_filename (String)
- stored_filename (String)
- file_path (String)
- file_size (BigInteger)
- mime_type (String)
- file_extension (String)
- file_hash (String, SHA256)
- status (String: uploaded, processing, completed, error)
- validation_status (String: pending, passed, failed)
- uploaded_at (DateTime)
- processed_at (DateTime, Optional)
```

### Extraction Results Table

```sql
- id (UUID, Primary Key)
- file_id (UUID, Foreign Key)
- tenant_id (UUID)
- extraction_type (String: text, metadata, structured_data, full)
- status (String: pending, processing, completed, failed)
- extracted_text (Text, Optional)
- structured_data (JSON, Optional)
- metadata (JSON, Optional)
- confidence_score (Float)
- processing_time_ms (Integer)
- created_at (DateTime)
- completed_at (DateTime, Optional)
```

## ⚙️ Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/file_system_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=file_system_db
DB_USER=file_system_user
DB_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# Storage
STORAGE_BASE_PATH=/app/storage
MAX_FILE_SIZE=104857600  # 100MB
ALLOWED_EXTENSIONS=.txt,.pdf,.doc,.docx,.xls,.xlsx,.zip,.json,.csv,.xml
MAX_ZIP_DEPTH=3

# Services
FILE_SERVICE_HOST=0.0.0.0
FILE_SERVICE_PORT=8001
EXTRACTION_SERVICE_HOST=0.0.0.0
EXTRACTION_SERVICE_PORT=8002

# Security
SECRET_KEY=your-super-secret-key
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test types
make test-unit
make test-integration
make test-async

# Run linting
make lint

# Format code
make format
```

## 📦 Development Commands

```bash
# Setup development environment
make dev-setup

# Start development services
make dev-start

# Stop services
make dev-stop

# View logs
make logs

# Clean up
make clean

# Build Docker images
make docker-build

# Database operations
make db-shell         # Connect to database
make redis-shell      # Connect to Redis
make db-reset         # Reset database
```

## 🔧 Maintenance

### Database Migrations

```bash
# Run migrations
make migrate

# Create new migration
make migration name="add_new_feature"

# Reset database
make db-reset
```

### Monitoring & Health Checks

```bash
# Check service health
curl http://localhost:8001/api/v1/health  # File Service
curl http://localhost:8002/api/v1/health  # Extraction Service

# View metrics
make metrics

# View service logs
make logs service=file-service
make logs service=extraction-service
```

### Backup & Recovery

```bash
# Backup database
make backup

# Restore from backup
make restore backup=backup_file.sql

# Cleanup old extractions
curl -X POST "http://localhost:8002/api/v1/extractions/admin/cleanup?days_old=30"
```

## 🏗️ Extending the System

### Adding New Extractors

1. Create extractor class in `src/extraction_service/extractors/`
2. Register in `ExtractionService.__init__()`
3. Add new extraction type to schemas
4. Write tests for the new extractor

### Adding New File Types

1. Update `ALLOWED_EXTENSIONS` in configuration
2. Add validation logic in `AsyncFileValidator`
3. Implement extraction logic for new type
4. Update tests

### Scaling Considerations

- **File Service**: Stateless, can be scaled horizontally
- **Extraction Service**: CPU-intensive, scale based on processing needs
- **Database**: Use read replicas for better performance
- **Storage**: Consider distributed storage solutions (S3, GCS, etc.)

## 🛠️ Troubleshooting

### Common Issues

1. **File upload fails**

   - Check file size limits
   - Verify allowed extensions
   - Check storage permissions

2. **Extraction timeout**

   - Increase processing timeout
   - Check file format compatibility
   - Monitor resource usage

3. **Database connection issues**

   - Verify connection string
   - Check network connectivity
   - Review connection pool settings

4. **Redis connection problems**
   - Check Redis server status
   - Verify authentication
   - Review network configuration

### Performance Optimization

- Enable Redis caching for repeated queries
- Use connection pooling for database
- Implement file streaming for large uploads
- Add CDN for file downloads
- Monitor and optimize SQL queries

## 📋 Project Structure

```
file_system/
├── src/
│   ├── shared/           # Shared components
│   │   ├── config.py     # Configuration management
│   │   ├── db.py         # Database setup
│   │   ├── cache.py      # Redis caching
│   │   └── utils.py      # Common utilities
│   ├── file_service/     # File management service
│   │   ├── models.py     # Database models
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── crud.py       # Database operations
│   │   ├── services.py   # Business logic
│   │   ├── routes.py     # API endpoints
│   │   └── app.py        # FastAPI application
│   └── extraction_service/  # File extraction service
│       ├── models.py     # Database models
│       ├── schemas.py    # Pydantic schemas
│       ├── crud.py       # Database operations
│       ├── services.py   # Extraction logic
│       ├── routes.py     # API endpoints
│       └── app.py        # FastAPI application
├── tests/                # Test suite
├── k8s/                  # Kubernetes manifests
├── scripts/              # Utility scripts
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile           # Multi-stage Docker build
├── requirements.txt     # Python dependencies
└── Makefile            # Development automation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
