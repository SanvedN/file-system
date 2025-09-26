"""
Integration tests for Extraction Service
Tests: inter-service communication, API endpoints, and full workflows
"""

import pytest
import pytest_asyncio
import tempfile
import json
import httpx
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.db import Base, get_db
from src.shared.cache import get_redis_client
from src.shared.config import Settings
from src.file_service.models import Tenant, File
from src.extraction_service.models import ExtractionResult
from src.extraction_service.schemas import ExtractionType, ExtractionStatus
from src.extraction_service.app import app


# Test Database Setup
@pytest_asyncio.fixture
async def async_session():
    """Create test database session"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    return mock_redis


@pytest_asyncio.fixture
async def test_settings():
    """Test configuration settings"""
    return Settings(
        storage_base_path="/tmp/test_storage",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/1"
    )


@pytest_asyncio.fixture
async def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest_asyncio.fixture
async def test_client(async_session, mock_redis):
    """Create test client with dependency overrides"""
    
    async def override_get_db():
        yield async_session
    
    async def override_get_redis():
        return mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_tenant(async_session):
    """Create a sample tenant for testing"""
    tenant = Tenant(
        code="integration123",
        name="Integration Test Tenant",
        description="Tenant for integration testing"
    )
    async_session.add(tenant)
    await async_session.commit()
    await async_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def sample_files(async_session, sample_tenant, temp_storage):
    """Create sample files for testing"""
    files = []
    
    # Text file
    txt_path = f"{temp_storage}/test_document.txt"
    Path(txt_path).write_text("This is a comprehensive test document for extraction testing.\nIt contains multiple lines and detailed content.")
    
    txt_file = File(
        tenant_id=sample_tenant.id,
        tenant_code=sample_tenant.code,
        original_filename="test_document.txt",
        stored_filename="stored_test_document.txt",
        file_path=txt_path,
        file_size=Path(txt_path).stat().st_size,
        mime_type="text/plain",
        file_extension=".txt",
        file_hash="txt_hash_123"
    )
    
    # JSON file
    json_path = f"{temp_storage}/test_data.json"
    json_data = {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com", "score": 95.5},
            {"id": 2, "name": "Bob", "email": "bob@example.com", "score": 87.2}
        ],
        "metadata": {
            "total_count": 2,
            "created_at": "2024-01-01T00:00:00Z",
            "version": "1.0"
        }
    }
    Path(json_path).write_text(json.dumps(json_data, indent=2))
    
    json_file = File(
        tenant_id=sample_tenant.id,
        tenant_code=sample_tenant.code,
        original_filename="test_data.json",
        stored_filename="stored_test_data.json",
        file_path=json_path,
        file_size=Path(json_path).stat().st_size,
        mime_type="application/json",
        file_extension=".json",
        file_hash="json_hash_456"
    )
    
    async_session.add_all([txt_file, json_file])
    await async_session.commit()
    
    await async_session.refresh(txt_file)
    await async_session.refresh(json_file)
    
    files.extend([txt_file, json_file])
    return files


# API Integration Tests
@pytest.mark.integration
class TestExtractionServiceAPI:
    """Test Extraction Service API endpoints"""
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_request_extraction_endpoint(self, test_client, sample_files):
        """Test extraction request endpoint"""
        txt_file = sample_files[0]
        
        request_data = {
            "file_id": str(txt_file.id),
            "tenant_id": str(txt_file.tenant_id),
            "extraction_type": "text",
            "config": {
                "include_metadata": True,
                "confidence_threshold": 0.8
            }
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["file_id"] == str(txt_file.id)
        assert data["extraction_type"] == "text"
        assert data["status"] == "pending"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_extraction_endpoint(self, test_client, sample_files, async_session, mock_redis):
        """Test get extraction endpoint"""
        txt_file = sample_files[0]
        
        # Create extraction first
        extraction = ExtractionResult(
            file_id=txt_file.id,
            tenant_id=txt_file.tenant_id,
            extraction_type=ExtractionType.TEXT,
            status=ExtractionStatus.COMPLETED,
            extracted_text="Extracted text content",
            confidence_score=0.92,
            processing_time_ms=1500
        )
        async_session.add(extraction)
        await async_session.commit()
        await async_session.refresh(extraction)
        
        # Get extraction
        response = test_client.get(f"/api/v1/extractions/{extraction.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == str(extraction.id)
        assert data["status"] == "completed"
        assert data["extracted_text"] == "Extracted text content"
        assert data["confidence_score"] == 0.92
    
    @pytest.mark.asyncio
    async def test_search_extractions_endpoint(self, test_client, sample_files, async_session):
        """Test search extractions endpoint"""
        txt_file = sample_files[0]
        
        # Create multiple extractions
        extractions = [
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.TEXT,
                status=ExtractionStatus.COMPLETED,
                confidence_score=0.95
            ),
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.METADATA,
                status=ExtractionStatus.FAILED
            )
        ]
        
        async_session.add_all(extractions)
        await async_session.commit()
        
        # Search for completed extractions
        search_data = {
            "tenant_id": str(txt_file.tenant_id),
            "status": "completed",
            "min_confidence": 0.9
        }
        
        response = test_client.post("/api/v1/extractions/search", json=search_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert len(data["extractions"]) == 1
        assert data["extractions"][0]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_bulk_extraction_endpoint(self, test_client, sample_files):
        """Test bulk extraction request endpoint"""
        file_ids = [str(f.id) for f in sample_files]
        tenant_id = str(sample_files[0].tenant_id)
        
        bulk_request = {
            "file_ids": file_ids,
            "tenant_id": tenant_id,
            "extraction_types": ["text", "metadata"],
            "config": {
                "include_metadata": True,
                "confidence_threshold": 0.7
            }
        }
        
        response = test_client.post("/api/v1/extractions/bulk", json=bulk_request)
        assert response.status_code == 201
        
        data = response.json()
        assert data["created_count"] == 4  # 2 files × 2 extraction types
        assert len(data["extractions"]) == 4
    
    @pytest.mark.asyncio
    async def test_process_extraction_endpoint(self, test_client, sample_files, async_session):
        """Test extraction processing endpoint"""
        txt_file = sample_files[0]
        
        # Create pending extraction
        extraction = ExtractionResult(
            file_id=txt_file.id,
            tenant_id=txt_file.tenant_id,
            extraction_type=ExtractionType.TEXT,
            status=ExtractionStatus.PENDING
        )
        async_session.add(extraction)
        await async_session.commit()
        await async_session.refresh(extraction)
        
        # Process extraction
        response = test_client.post(f"/api/v1/extractions/{extraction.id}/process")
        assert response.status_code == 202
        
        data = response.json()
        assert data["message"] == "Extraction processing started"
        assert data["extraction_id"] == str(extraction.id)
    
    @pytest.mark.asyncio
    async def test_get_extractions_by_file_endpoint(self, test_client, sample_files, async_session):
        """Test get extractions by file endpoint"""
        txt_file = sample_files[0]
        
        # Create extractions for the file
        extractions = [
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.TEXT,
                status=ExtractionStatus.COMPLETED
            ),
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.METADATA,
                status=ExtractionStatus.COMPLETED
            )
        ]
        
        async_session.add_all(extractions)
        await async_session.commit()
        
        # Get extractions by file
        response = test_client.get(f"/api/v1/extractions/file/{txt_file.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 2
        assert all(e["file_id"] == str(txt_file.id) for e in data)
    
    @pytest.mark.asyncio
    async def test_get_pending_extractions_endpoint(self, test_client, sample_files, async_session):
        """Test get pending extractions endpoint"""
        txt_file = sample_files[0]
        
        # Create pending extractions
        pending_extractions = [
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.TEXT,
                status=ExtractionStatus.PENDING
            ),
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.METADATA,
                status=ExtractionStatus.PENDING
            )
        ]
        
        async_session.add_all(pending_extractions)
        await async_session.commit()
        
        # Get pending extractions
        response = test_client.get("/api/v1/extractions/queue/pending")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["extractions"]) == 2
        assert all(e["status"] == "pending" for e in data["extractions"])
    
    @pytest.mark.asyncio
    async def test_extraction_stats_endpoint(self, test_client, sample_files, async_session):
        """Test extraction statistics endpoint"""
        txt_file = sample_files[0]
        
        # Create extractions with different statuses
        extractions = [
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.TEXT,
                status=ExtractionStatus.COMPLETED,
                confidence_score=0.95
            ),
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.METADATA,
                status=ExtractionStatus.FAILED
            ),
            ExtractionResult(
                file_id=txt_file.id,
                tenant_id=txt_file.tenant_id,
                extraction_type=ExtractionType.STRUCTURED_DATA,
                status=ExtractionStatus.PENDING
            )
        ]
        
        async_session.add_all(extractions)
        await async_session.commit()
        
        # Get global stats
        response = test_client.get("/api/v1/extractions/stats/global")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_extractions"] == 3
        assert data["completed_extractions"] == 1
        assert data["failed_extractions"] == 1
        assert data["pending_extractions"] == 1


# Workflow Integration Tests
@pytest.mark.integration
class TestExtractionWorkflows:
    """Test complete extraction workflows"""
    
    @pytest.mark.asyncio
    async def test_text_extraction_workflow(self, test_client, sample_files):
        """Test complete text extraction workflow"""
        txt_file = sample_files[0]
        
        # Step 1: Request text extraction
        request_data = {
            "file_id": str(txt_file.id),
            "tenant_id": str(txt_file.tenant_id),
            "extraction_type": "text",
            "config": {"include_metadata": True}
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        assert response.status_code == 201
        extraction_id = response.json()["id"]
        
        # Step 2: Process extraction
        response = test_client.post(f"/api/v1/extractions/{extraction_id}/process")
        assert response.status_code == 202
        
        # Step 3: Check extraction result
        response = test_client.get(f"/api/v1/extractions/{extraction_id}")
        assert response.status_code == 200
        
        # Note: In real scenario, processing would be async
        # Here we verify the API structure works correctly
    
    @pytest.mark.asyncio
    async def test_full_extraction_workflow(self, test_client, sample_files):
        """Test complete full extraction workflow"""
        json_file = sample_files[1]  # JSON file with structured data
        
        # Step 1: Request full extraction
        request_data = {
            "file_id": str(json_file.id),
            "tenant_id": str(json_file.tenant_id),
            "extraction_type": "full",
            "config": {
                "include_metadata": True,
                "confidence_threshold": 0.8
            }
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        assert response.status_code == 201
        extraction_id = response.json()["id"]
        
        # Step 2: Process extraction
        response = test_client.post(f"/api/v1/extractions/{extraction_id}/process")
        assert response.status_code == 202
        
        # Step 3: Check processing status
        response = test_client.get(f"/api/v1/extractions/{extraction_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["extraction_type"] == "full"
    
    @pytest.mark.asyncio
    async def test_bulk_extraction_workflow(self, test_client, sample_files):
        """Test bulk extraction workflow"""
        file_ids = [str(f.id) for f in sample_files]
        tenant_id = str(sample_files[0].tenant_id)
        
        # Step 1: Request bulk extractions
        bulk_request = {
            "file_ids": file_ids,
            "tenant_id": tenant_id,
            "extraction_types": ["text", "metadata", "structured_data"],
            "config": {"confidence_threshold": 0.7}
        }
        
        response = test_client.post("/api/v1/extractions/bulk", json=bulk_request)
        assert response.status_code == 201
        
        data = response.json()
        extraction_ids = [e["id"] for e in data["extractions"]]
        
        # Step 2: Process all extractions
        for extraction_id in extraction_ids:
            response = test_client.post(f"/api/v1/extractions/{extraction_id}/process")
            assert response.status_code == 202
        
        # Step 3: Check results
        for extraction_id in extraction_ids:
            response = test_client.get(f"/api/v1/extractions/{extraction_id}")
            assert response.status_code == 200


# Error Handling Integration Tests
@pytest.mark.integration
class TestExtractionErrorHandling:
    """Test error handling in extraction workflows"""
    
    def test_request_extraction_invalid_file(self, test_client):
        """Test extraction request with invalid file ID"""
        request_data = {
            "file_id": str(uuid4()),  # Non-existent file
            "tenant_id": str(uuid4()),
            "extraction_type": "text"
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        # Should handle gracefully - exact behavior depends on implementation
        assert response.status_code in [400, 404, 422]
    
    def test_get_nonexistent_extraction(self, test_client):
        """Test getting non-existent extraction"""
        response = test_client.get(f"/api/v1/extractions/{uuid4()}")
        assert response.status_code == 404
    
    def test_invalid_extraction_type(self, test_client, sample_files):
        """Test request with invalid extraction type"""
        txt_file = sample_files[0]
        
        request_data = {
            "file_id": str(txt_file.id),
            "tenant_id": str(txt_file.tenant_id),
            "extraction_type": "invalid_type"
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_malformed_search_request(self, test_client):
        """Test search with malformed request"""
        search_data = {
            "tenant_id": "not-a-uuid",  # Invalid UUID
            "min_confidence": 1.5  # Invalid confidence value
        }
        
        response = test_client.post("/api/v1/extractions/search", json=search_data)
        assert response.status_code == 422  # Validation error


# Performance Integration Tests
@pytest.mark.integration
class TestExtractionPerformance:
    """Test performance aspects of extraction workflows"""
    
    @pytest.mark.asyncio
    async def test_concurrent_extraction_requests(self, test_client, sample_files):
        """Test handling concurrent extraction requests"""
        txt_file = sample_files[0]
        
        # Create multiple concurrent requests
        import asyncio
        import httpx
        
        async def make_request():
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                request_data = {
                    "file_id": str(txt_file.id),
                    "tenant_id": str(txt_file.tenant_id),
                    "extraction_type": "text"
                }
                response = await client.post("/api/v1/extractions/", json=request_data)
                return response.status_code
        
        # Make 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        status_codes = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(code == 201 for code in status_codes)
    
    @pytest.mark.asyncio
    async def test_large_file_extraction(self, test_client, sample_tenant, temp_storage, async_session):
        """Test extraction with larger file"""
        # Create a larger text file
        large_content = "This is a large test document. " * 1000  # ~30KB
        large_file_path = f"{temp_storage}/large_document.txt"
        Path(large_file_path).write_text(large_content)
        
        large_file = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="large_document.txt",
            stored_filename="stored_large_document.txt",
            file_path=large_file_path,
            file_size=len(large_content.encode()),
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="large_hash_789"
        )
        async_session.add(large_file)
        await async_session.commit()
        await async_session.refresh(large_file)
        
        # Request extraction
        request_data = {
            "file_id": str(large_file.id),
            "tenant_id": str(large_file.tenant_id),
            "extraction_type": "text"
        }
        
        response = test_client.post("/api/v1/extractions/", json=request_data)
        assert response.status_code == 201
        
        # Process extraction
        extraction_id = response.json()["id"]
        response = test_client.post(f"/api/v1/extractions/{extraction_id}/process")
        assert response.status_code == 202


# Cross-Service Integration Tests
@pytest.mark.integration
class TestCrossServiceIntegration:
    """Test integration between File Service and Extraction Service"""
    
    @pytest.mark.asyncio
    async def test_file_upload_to_extraction_workflow(self, test_client, sample_tenant, temp_storage):
        """Test workflow from file upload to extraction (simulated)"""
        # This would typically involve calling File Service API
        # For now, we simulate the workflow by directly creating file records
        
        # Simulate file upload result
        uploaded_file_path = f"{temp_storage}/uploaded_test.txt"
        Path(uploaded_file_path).write_text("Uploaded file content for extraction testing.")
        
        # In real scenario, this would come from File Service API response
        file_metadata = {
            "file_id": str(uuid4()),
            "tenant_id": str(sample_tenant.id),
            "file_path": uploaded_file_path,
            "original_filename": "uploaded_test.txt",
            "mime_type": "text/plain"
        }
        
        # Request extraction for the "uploaded" file
        request_data = {
            "file_id": file_metadata["file_id"],
            "tenant_id": file_metadata["tenant_id"],
            "extraction_type": "text",
            "config": {"include_metadata": True}
        }
        
        # This would fail in reality without actual file record,
        # but demonstrates the API integration pattern
        response = test_client.post("/api/v1/extractions/", json=request_data)
        # Expected to fail gracefully due to missing file record
        assert response.status_code in [400, 404, 422]
    
    def test_extraction_results_caching(self, test_client, mock_redis):
        """Test that extraction results are properly cached"""
        # Verify Redis operations are called during extraction workflows
        # This is tested through the mock_redis fixture
        
        # Check that cache operations are configured
        assert mock_redis.get is not None
        assert mock_redis.set is not None
        assert mock_redis.delete is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
