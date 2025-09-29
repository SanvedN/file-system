# Multi-tenant File Management and Extraction System

---

### About the Project

The solution is a multi-tenant file management and information extraction system. It provides secured file storage, processing, management and extraction services. The system uses asynchronous microservices to provide these services along with cache management using Redis to ensure high availablity and durability.

**Tech Stack**: FastAPI, PostgreSQL, SQLAlchemy, Redis, Alembic, uv (package management)

### Features

- **Multi-tenant Architecture**: Each tenant has their own isolated file management and storage
- **Proper file validation and checks**: Proper configurations set up for file validations like file type, maximum file size
- **Async Operations** - Full async/await support with FastAPI and SQLAlchemy
- **Redis Caching** - Proper caching for metadata and repeated queries
- **Storage Management** - Organized storage with format `storage_base_path/<tenant_code>/YYYY-MM/` to ensure proper data sorting and searching

---

## System Architecture

The system consists of three main microservices:

- **File Service** (Port 8001): Handles file upload, storage, and management
- **Extraction Service** (Port 8002): Processes files and extracts structured data
- **API Gateway** (Port 8000): Routes requests and provides unified API access

![image](diagrams\component-diag.png)

---

## How to setup the project

**Prerequisites**

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
```

2. Install dependencies (make sure you have uv installed)

```bash
uv pip install -r requirements.txt
```

3. Run all servers using uvicorn

```bash
uvicorn main:app --reload
```

## Running using Docker and Deployment

PENDING
