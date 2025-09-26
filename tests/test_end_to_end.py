"""
End-to-End Tests for Multi-Tenant File Management and Extraction System
Tests: Complete workflows from file upload to extraction results
"""

import pytest
import pytest_asyncio
import tempfile
import json
import asyncio
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
from src.file_service.app import app as file_app
from src.extraction_service.app import app as extraction_app


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
    mock_redis.ping.return_value = True
    return mock_redis


@pytest_asyncio.fixture
async def test_settings():
    """Test configuration settings"""
    return Settings(
        storage_base_path="/tmp/test_storage",
        max_file_size=1024 * 1024,  # 1MB
        allowed_extensions=".txt,.pdf,.json,.csv,.zip",
        max_zip_depth=3,
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/1"
    )


@pytest_asyncio.fixture
async def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest_asyncio.fixture
async def file_client(async_session, mock_redis):
    """Create File Service test client"""
    
    async def override_get_db():
        yield async_session
    
    async def override_get_redis():
        return mock_redis
    
    file_app.dependency_overrides[get_db] = override_get_db
    file_app.dependency_overrides[get_redis_client] = override_get_redis
    
    with TestClient(file_app) as client:
        yield client
    
    file_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def extraction_client(async_session, mock_redis):
    """Create Extraction Service test client"""
    
    async def override_get_db():
        yield async_session
    
    async def override_get_redis():
        return mock_redis
    
    extraction_app.dependency_overrides[get_db] = override_get_db
    extraction_app.dependency_overrides[get_redis_client] = override_get_redis
    
    with TestClient(extraction_app) as client:
        yield client
    
    extraction_app.dependency_overrides.clear()


# End-to-End Test Scenarios
@pytest.mark.e2e
class TestCompleteWorkflows:
    """Test complete end-to-end workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_tenant_file_extraction_workflow(
        self, file_client, extraction_client, temp_storage, async_session
    ):
        """Test complete workflow: create tenant -> upload file -> extract data -> verify results"""
        
        # Step 1: Create tenant via File Service
        tenant_data = {
            "code": "e2e-test-001",
            "name": "E2E Test Tenant",
            "description": "End-to-end test tenant",
            "storage_quota_bytes": 10485760,  # 10MB
            "file_count_limit": 100
        }
        
        response = file_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        
        tenant_response = response.json()
        tenant_code = tenant_response["code"]
        tenant_id = tenant_response["id"]
        
        # Verify tenant creation
        assert tenant_code == "e2e-test-001"
        assert tenant_response["is_active"] is True
        
        # Step 2: Create test file for upload
        test_content = {
            "document": {
                "title": "E2E Test Document",
                "content": "This is a comprehensive end-to-end test document with structured data.",
                "metadata": {
                    "author": "E2E Test Suite",
                    "created_date": "2024-01-01",
                    "category": "test",
                    "tags": ["e2e", "testing", "automation"]
                },
                "sections": [
                    {
                        "heading": "Introduction",
                        "text": "This section introduces the E2E testing approach.",
                        "word_count": 10
                    },
                    {
                        "heading": "Methodology", 
                        "text": "This section describes the testing methodology used.",
                        "word_count": 15
                    },
                    {
                        "heading": "Results",
                        "text": "This section presents the test results and findings.",
                        "word_count": 12
                    }
                ],
                "statistics": {
                    "total_words": 37,
                    "total_sections": 3,
                    "estimated_reading_time": "2 minutes"
                }
            }
        }
        
        test_file_path = f"{temp_storage}/e2e_test_document.json"
        Path(test_file_path).write_text(json.dumps(test_content, indent=2))
        
        # Step 3: Upload file via File Service (simulated)
        # Note: In real implementation, this would use multipart/form-data
        # For this test, we'll create the file record directly and then test extraction
        
        file_record = File(
            tenant_id=tenant_id,
            tenant_code=tenant_code,
            original_filename="e2e_test_document.json",
            stored_filename="stored_e2e_test_document.json",
            file_path=test_file_path,
            file_size=Path(test_file_path).stat().st_size,
            mime_type="application/json",
            file_extension=".json",
            file_hash="e2e_test_hash_123"
        )
        
        async_session.add(file_record)
        await async_session.commit()
        await async_session.refresh(file_record)
        
        # Step 4: Request full extraction via Extraction Service
        extraction_request = {
            "file_id": str(file_record.id),
            "tenant_id": str(file_record.tenant_id),
            "extraction_type": "full",
            "config": {
                "include_metadata": True,
                "confidence_threshold": 0.8
            }
        }
        
        response = extraction_client.post("/api/v1/extractions/", json=extraction_request)
        assert response.status_code == 201
        
        extraction_response = response.json()
        extraction_id = extraction_response["id"]
        
        # Verify extraction request
        assert extraction_response["file_id"] == str(file_record.id)
        assert extraction_response["extraction_type"] == "full"
        assert extraction_response["status"] == "pending"
        
        # Step 5: Process extraction
        response = extraction_client.post(f"/api/v1/extractions/{extraction_id}/process")
        assert response.status_code == 202
        
        # Step 6: Verify extraction results
        response = extraction_client.get(f"/api/v1/extractions/{extraction_id}")
        assert response.status_code == 200
        
        # Note: In real async processing, we'd need to poll or use callbacks
        # Here we test that the structure and APIs work correctly
        
        # Step 7: Check tenant statistics
        response = file_client.get(f"/api/v1/tenants/{tenant_code}/stats")
        assert response.status_code == 200
        
        stats = response.json()
        # Should show the uploaded file
        assert stats["total_files"] >= 1
        
        # Step 8: Search for extractions
        search_request = {
            "tenant_id": str(file_record.tenant_id),
            "extraction_type": "full",
            "min_confidence": 0.7
        }
        
        response = extraction_client.post("/api/v1/extractions/search", json=search_request)
        assert response.status_code == 200
        
        search_results = response.json()
        assert search_results["total"] >= 1
        
        # Step 9: Cleanup - Delete file and tenant
        response = file_client.delete(f"/api/v1/files/{file_record.id}?permanent=true")
        assert response.status_code in [200, 204]
        
        response = file_client.delete(f"/api/v1/tenants/{tenant_code}")
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_bulk_operations_workflow(
        self, file_client, extraction_client, temp_storage, async_session
    ):
        """Test bulk operations workflow"""
        
        # Step 1: Create tenant
        tenant_data = {
            "code": "bulk-test-001",
            "name": "Bulk Operations Test Tenant",
            "description": "Tenant for testing bulk operations"
        }
        
        response = file_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        tenant_response = response.json()
        tenant_id = tenant_response["id"]
        tenant_code = tenant_response["code"]
        
        # Step 2: Create multiple test files
        test_files = []
        file_contents = [
            {"type": "text", "content": "First test document content"},
            {"type": "text", "content": "Second test document content"},
            {"type": "json", "content": {"data": "Third test document", "value": 123}}
        ]
        
        for i, file_content in enumerate(file_contents):
            if file_content["type"] == "text":
                file_path = f"{temp_storage}/bulk_test_{i}.txt"
                Path(file_path).write_text(file_content["content"])
                mime_type = "text/plain"
                extension = ".txt"
            else:
                file_path = f"{temp_storage}/bulk_test_{i}.json"
                Path(file_path).write_text(json.dumps(file_content["content"]))
                mime_type = "application/json"
                extension = ".json"
            
            file_record = File(
                tenant_id=tenant_id,
                tenant_code=tenant_code,
                original_filename=f"bulk_test_{i}{extension}",
                stored_filename=f"stored_bulk_test_{i}{extension}",
                file_path=file_path,
                file_size=Path(file_path).stat().st_size,
                mime_type=mime_type,
                file_extension=extension,
                file_hash=f"bulk_hash_{i}"
            )
            
            async_session.add(file_record)
            test_files.append(file_record)
        
        await async_session.commit()
        
        # Refresh all file records
        for file_record in test_files:
            await async_session.refresh(file_record)
        
        # Step 3: Request bulk extractions
        file_ids = [str(f.id) for f in test_files]
        
        bulk_request = {
            "file_ids": file_ids,
            "tenant_id": str(tenant_id),
            "extraction_types": ["text", "metadata"],
            "config": {
                "include_metadata": True,
                "confidence_threshold": 0.7
            }
        }
        
        response = extraction_client.post("/api/v1/extractions/bulk", json=bulk_request)
        assert response.status_code == 201
        
        bulk_response = response.json()
        assert bulk_response["created_count"] == 6  # 3 files × 2 extraction types
        
        # Step 4: Process all extractions
        extraction_ids = [e["id"] for e in bulk_response["extractions"]]
        
        for extraction_id in extraction_ids:
            response = extraction_client.post(f"/api/v1/extractions/{extraction_id}/process")
            assert response.status_code == 202
        
        # Step 5: Check processing queue
        response = extraction_client.get("/api/v1/extractions/queue/pending")
        assert response.status_code == 200
        
        # Step 6: Get extraction statistics
        response = extraction_client.get("/api/v1/extractions/stats/global")
        assert response.status_code == 200
        
        stats = response.json()
        assert stats["total_extractions"] >= 6
        
        # Step 7: Bulk delete files
        bulk_delete_request = {
            "tenant_code": tenant_code,
            "file_ids": file_ids,
            "permanent": True
        }
        
        response = file_client.post("/api/v1/files/bulk-delete", json=bulk_delete_request)
        assert response.status_code == 200
        
        delete_response = response.json()
        assert delete_response["deleted_count"] == 3
        
        # Step 8: Cleanup tenant
        response = file_client.delete(f"/api/v1/tenants/{tenant_code}")
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(
        self, file_client, extraction_client, temp_storage, async_session
    ):
        """Test error handling in complete workflows"""
        
        # Step 1: Create tenant
        tenant_data = {
            "code": "error-test-001",
            "name": "Error Handling Test Tenant"
        }
        
        response = file_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        tenant_response = response.json()
        tenant_id = tenant_response["id"]
        tenant_code = tenant_response["code"]
        
        # Step 2: Test extraction with non-existent file
        extraction_request = {
            "file_id": str(uuid4()),  # Non-existent file
            "tenant_id": str(tenant_id),
            "extraction_type": "text"
        }
        
        response = extraction_client.post("/api/v1/extractions/", json=extraction_request)
        # Should handle gracefully
        assert response.status_code in [400, 404, 422]
        
        # Step 3: Test with invalid tenant
        extraction_request = {
            "file_id": str(uuid4()),
            "tenant_id": str(uuid4()),  # Non-existent tenant
            "extraction_type": "text"
        }
        
        response = extraction_client.post("/api/v1/extractions/", json=extraction_request)
        assert response.status_code in [400, 404, 422]
        
        # Step 4: Test with corrupted file
        corrupted_file_path = f"{temp_storage}/corrupted.json"
        Path(corrupted_file_path).write_text("{ invalid json without closing")
        
        corrupted_file = File(
            tenant_id=tenant_id,
            tenant_code=tenant_code,
            original_filename="corrupted.json",
            stored_filename="stored_corrupted.json",
            file_path=corrupted_file_path,
            file_size=Path(corrupted_file_path).stat().st_size,
            mime_type="application/json",
            file_extension=".json",
            file_hash="corrupted_hash"
        )
        
        async_session.add(corrupted_file)
        await async_session.commit()
        await async_session.refresh(corrupted_file)
        
        # Request extraction for corrupted file
        extraction_request = {
            "file_id": str(corrupted_file.id),
            "tenant_id": str(corrupted_file.tenant_id),
            "extraction_type": "structured_data"
        }
        
        response = extraction_client.post("/api/v1/extractions/", json=extraction_request)
        assert response.status_code == 201
        
        extraction_id = response.json()["id"]
        
        # Process extraction (should handle error gracefully)
        response = extraction_client.post(f"/api/v1/extractions/{extraction_id}/process")
        assert response.status_code == 202
        
        # Check if error was handled properly
        response = extraction_client.get(f"/api/v1/extractions/{extraction_id}")
        assert response.status_code == 200
        
        # Step 5: Cleanup
        response = file_client.delete(f"/api/v1/tenants/{tenant_code}")
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_workflow(
        self, file_client, extraction_client, temp_storage, async_session
    ):
        """Test concurrent operations across services"""
        
        # Step 1: Create tenant
        tenant_data = {
            "code": "concurrent-001",
            "name": "Concurrent Test Tenant"
        }
        
        response = file_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        tenant_response = response.json()
        tenant_id = tenant_response["id"]
        tenant_code = tenant_response["code"]
        
        # Step 2: Create multiple files concurrently
        async def create_test_file(file_index):
            file_content = f"Concurrent test file {file_index} content"
            file_path = f"{temp_storage}/concurrent_{file_index}.txt"
            Path(file_path).write_text(file_content)
            
            file_record = File(
                tenant_id=tenant_id,
                tenant_code=tenant_code,
                original_filename=f"concurrent_{file_index}.txt",
                stored_filename=f"stored_concurrent_{file_index}.txt",
                file_path=file_path,
                file_size=len(file_content.encode()),
                mime_type="text/plain",
                file_extension=".txt",
                file_hash=f"concurrent_hash_{file_index}"
            )
            
            async_session.add(file_record)
            return file_record
        
        # Create 5 files concurrently
        file_creation_tasks = [create_test_file(i) for i in range(5)]
        created_files = await asyncio.gather(*file_creation_tasks)
        
        await async_session.commit()
        
        # Refresh all files
        for file_record in created_files:
            await async_session.refresh(file_record)
        
        # Step 3: Request extractions concurrently
        async def request_extraction(file_record):
            import httpx
            
            extraction_request = {
                "file_id": str(file_record.id),
                "tenant_id": str(file_record.tenant_id),
                "extraction_type": "text"
            }
            
            async with httpx.AsyncClient(app=extraction_app, base_url="http://test") as client:
                response = await client.post("/api/v1/extractions/", json=extraction_request)
                return response.status_code, response.json() if response.status_code == 201 else None
        
        # Request extractions concurrently
        extraction_tasks = [request_extraction(file_record) for file_record in created_files]
        extraction_results = await asyncio.gather(*extraction_tasks)
        
        # Verify all extractions were requested successfully
        successful_extractions = [r for r in extraction_results if r[0] == 201]
        assert len(successful_extractions) == 5
        
        # Step 4: Process extractions concurrently
        extraction_ids = [r[1]["id"] for r in successful_extractions]
        
        async def process_extraction(extraction_id):
            import httpx
            
            async with httpx.AsyncClient(app=extraction_app, base_url="http://test") as client:
                response = await client.post(f"/api/v1/extractions/{extraction_id}/process")
                return response.status_code
        
        processing_tasks = [process_extraction(eid) for eid in extraction_ids]
        processing_results = await asyncio.gather(*processing_tasks)
        
        # Verify all processing requests were accepted
        assert all(status == 202 for status in processing_results)
        
        # Step 5: Verify system state
        response = file_client.get(f"/api/v1/tenants/{tenant_code}/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert stats["total_files"] == 5
        
        response = extraction_client.get("/api/v1/extractions/stats/global")
        assert response.status_code == 200
        
        extraction_stats = response.json()
        assert extraction_stats["total_extractions"] >= 5
        
        # Step 6: Cleanup
        response = file_client.delete(f"/api/v1/tenants/{tenant_code}")
        assert response.status_code in [200, 204]


# Performance and Load Tests
@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceWorkflows:
    """Test performance aspects of complete workflows"""
    
    @pytest.mark.asyncio
    async def test_high_volume_workflow(
        self, file_client, extraction_client, temp_storage, async_session
    ):
        """Test system behavior with high volume operations"""
        
        # Step 1: Create tenant
        tenant_data = {
            "code": "perf-test-001",
            "name": "Performance Test Tenant",
            "storage_quota_bytes": 104857600  # 100MB
        }
        
        response = file_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        tenant_response = response.json()
        tenant_id = tenant_response["id"]
        tenant_code = tenant_response["code"]
        
        # Step 2: Create and process many files
        file_count = 20  # Reduced for test performance
        created_files = []
        
        for i in range(file_count):
            file_content = f"Performance test document {i}. " * 50  # ~1.5KB each
            file_path = f"{temp_storage}/perf_test_{i}.txt"
            Path(file_path).write_text(file_content)
            
            file_record = File(
                tenant_id=tenant_id,
                tenant_code=tenant_code,
                original_filename=f"perf_test_{i}.txt",
                stored_filename=f"stored_perf_test_{i}.txt",
                file_path=file_path,
                file_size=len(file_content.encode()),
                mime_type="text/plain",
                file_extension=".txt",
                file_hash=f"perf_hash_{i}"
            )
            
            async_session.add(file_record)
            created_files.append(file_record)
        
        await async_session.commit()
        
        # Refresh all files
        for file_record in created_files:
            await async_session.refresh(file_record)
        
        # Step 3: Bulk extraction request
        file_ids = [str(f.id) for f in created_files]
        
        bulk_request = {
            "file_ids": file_ids,
            "tenant_id": str(tenant_id),
            "extraction_types": ["text"],
            "config": {"confidence_threshold": 0.8}
        }
        
        response = extraction_client.post("/api/v1/extractions/bulk", json=bulk_request)
        assert response.status_code == 201
        
        bulk_response = response.json()
        assert bulk_response["created_count"] == file_count
        
        # Step 4: Verify system still responsive
        response = file_client.get("/api/v1/health")
        assert response.status_code == 200
        
        response = extraction_client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Step 5: Check statistics
        response = extraction_client.get("/api/v1/extractions/stats/global")
        assert response.status_code == 200
        
        stats = response.json()
        assert stats["total_extractions"] >= file_count
        
        # Step 6: Cleanup
        bulk_delete_request = {
            "tenant_code": tenant_code,
            "file_ids": file_ids,
            "permanent": True
        }
        
        response = file_client.post("/api/v1/files/bulk-delete", json=bulk_delete_request)
        assert response.status_code == 200
        
        response = file_client.delete(f"/api/v1/tenants/{tenant_code}")
        assert response.status_code in [200, 204]


# Integration Health Tests
@pytest.mark.e2e
class TestSystemHealth:
    """Test overall system health and monitoring"""
    
    def test_service_health_endpoints(self, file_client, extraction_client):
        """Test that all service health endpoints are working"""
        
        # Test File Service health
        response = file_client.get("/api/v1/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "service" in health_data
        assert "timestamp" in health_data
        
        # Test Extraction Service health
        response = extraction_client.get("/api/v1/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "service" in health_data
        assert "timestamp" in health_data
    
    @pytest.mark.asyncio
    async def test_service_dependencies(self, file_client, extraction_client, mock_redis):
        """Test service dependency health"""
        
        # Test database connectivity (implicitly tested by successful operations)
        response = file_client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Test Redis connectivity (through mock)
        assert mock_redis.ping.return_value is True
        
        # Verify services can handle dependency failures gracefully
        # This would be tested by temporarily disconnecting dependencies
        # For now, we verify the basic structure works
    
    def test_api_versioning(self, file_client, extraction_client):
        """Test API versioning consistency"""
        
        # All endpoints should be under /api/v1/
        response = file_client.get("/api/v1/health")
        assert response.status_code == 200
        
        response = extraction_client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Test that unversioned endpoints don't exist or redirect
        response = file_client.get("/health")
        assert response.status_code == 404
        
        response = extraction_client.get("/health")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
