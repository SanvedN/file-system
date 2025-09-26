"""
Integration tests for File Service
Tests: API endpoints, workflows, and inter-component integration
"""

import pytest
import pytest_asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.db import Base, get_db
from src.shared.cache import get_redis_client
from src.shared.config import Settings
from src.file_service.models import Tenant, File
from src.file_service.app import app


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
        code="integration-test",
        name="Integration Test Tenant",
        description="Tenant for integration testing",
        storage_quota_bytes=10485760,  # 10MB
        file_count_limit=100
    )
    async_session.add(tenant)
    await async_session.commit()
    await async_session.refresh(tenant)
    return tenant


# API Integration Tests
@pytest.mark.integration
class TestFileServiceAPI:
    """Test File Service API endpoints"""
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_tenant_crud_endpoints(self, test_client):
        """Test tenant CRUD operations via API"""
        
        # Create tenant
        tenant_data = {
            "code": "api-test-001",
            "name": "API Test Tenant",
            "description": "Created via API test",
            "storage_quota_bytes": 5242880,  # 5MB
            "file_count_limit": 50
        }
        
        response = test_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        
        created_tenant = response.json()
        assert created_tenant["code"] == "api-test-001"
        assert created_tenant["name"] == "API Test Tenant"
        assert created_tenant["is_active"] is True
        
        tenant_id = created_tenant["id"]
        
        # Get tenant
        response = test_client.get(f"/api/v1/tenants/{tenant_data['code']}")
        assert response.status_code == 200
        
        retrieved_tenant = response.json()
        assert retrieved_tenant["id"] == tenant_id
        assert retrieved_tenant["code"] == tenant_data["code"]
        
        # Update tenant
        update_data = {
            "name": "Updated API Test Tenant",
            "description": "Updated via API test",
            "is_active": False
        }
        
        response = test_client.put(f"/api/v1/tenants/{tenant_data['code']}", json=update_data)
        assert response.status_code == 200
        
        updated_tenant = response.json()
        assert updated_tenant["name"] == "Updated API Test Tenant"
        assert updated_tenant["is_active"] is False
        
        # Get tenant stats
        response = test_client.get(f"/api/v1/tenants/{tenant_data['code']}/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "total_files" in stats
        assert "total_storage_bytes" in stats
        assert stats["total_files"] == 0
        
        # Check quotas
        response = test_client.get(f"/api/v1/tenants/{tenant_data['code']}/quotas")
        assert response.status_code == 200
        
        quotas = response.json()
        assert "within_storage_quota" in quotas
        assert "within_file_limit" in quotas
        
        # Delete tenant
        response = test_client.delete(f"/api/v1/tenants/{tenant_data['code']}")
        assert response.status_code == 200
        
        # Verify deletion
        response = test_client.get(f"/api/v1/tenants/{tenant_data['code']}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_file_operations_endpoints(self, test_client, sample_tenant, temp_storage, async_session):
        """Test file operations via API"""
        
        # Create a test file for operations
        test_content = "This is integration test file content for API testing."
        test_file_path = f"{temp_storage}/api_test_file.txt"
        Path(test_file_path).write_text(test_content)
        
        # Create file record directly (simulating upload)
        file_record = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="api_test_file.txt",
            stored_filename="stored_api_test_file.txt",
            file_path=test_file_path,
            file_size=len(test_content.encode()),
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="api_test_hash"
        )
        
        async_session.add(file_record)
        await async_session.commit()
        await async_session.refresh(file_record)
        
        # Get file metadata
        response = test_client.get(f"/api/v1/files/{file_record.id}")
        assert response.status_code == 200
        
        file_data = response.json()
        assert file_data["original_filename"] == "api_test_file.txt"
        assert file_data["tenant_code"] == sample_tenant.code
        assert file_data["file_size"] == len(test_content.encode())
        
        # Get files by tenant
        response = test_client.get(f"/api/v1/files/tenant/{sample_tenant.code}")
        assert response.status_code == 200
        
        files_data = response.json()
        assert files_data["total"] == 1
        assert len(files_data["files"]) == 1
        assert files_data["files"][0]["id"] == str(file_record.id)
        
        # Search files
        search_data = {
            "tenant_code": sample_tenant.code,
            "filename_pattern": "api_test",
            "file_extension": ".txt"
        }
        
        response = test_client.post("/api/v1/files/search", json=search_data)
        assert response.status_code == 200
        
        search_results = response.json()
        assert search_results["total"] == 1
        assert len(search_results["files"]) == 1
        
        # Download file (simulated)
        with patch('src.file_service.routes.FileResponse') as mock_file_response:
            mock_file_response.return_value = "file_content"
            response = test_client.get(f"/api/v1/files/{file_record.id}/download")
            # Note: Actual file download would require proper file handling
            # This tests the endpoint structure
        
        # Delete file
        response = test_client.delete(f"/api/v1/files/{file_record.id}?permanent=true")
        assert response.status_code == 200
        
        # Verify file deletion
        response = test_client.get(f"/api/v1/files/{file_record.id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_bulk_operations_endpoints(self, test_client, sample_tenant, temp_storage, async_session):
        """Test bulk operations via API"""
        
        # Create multiple test files
        test_files = []
        for i in range(3):
            test_content = f"Bulk test file {i} content"
            test_file_path = f"{temp_storage}/bulk_test_{i}.txt"
            Path(test_file_path).write_text(test_content)
            
            file_record = File(
                tenant_id=sample_tenant.id,
                tenant_code=sample_tenant.code,
                original_filename=f"bulk_test_{i}.txt",
                stored_filename=f"stored_bulk_test_{i}.txt",
                file_path=test_file_path,
                file_size=len(test_content.encode()),
                mime_type="text/plain",
                file_extension=".txt",
                file_hash=f"bulk_hash_{i}"
            )
            
            async_session.add(file_record)
            test_files.append(file_record)
        
        await async_session.commit()
        
        # Refresh all file records
        for file_record in test_files:
            await async_session.refresh(file_record)
        
        # Bulk delete files
        file_ids = [str(f.id) for f in test_files]
        bulk_delete_data = {
            "tenant_code": sample_tenant.code,
            "file_ids": file_ids,
            "permanent": True
        }
        
        response = test_client.post("/api/v1/files/bulk-delete", json=bulk_delete_data)
        assert response.status_code == 200
        
        delete_result = response.json()
        assert delete_result["deleted_count"] == 3
        assert delete_result["failed_count"] == 0
        
        # Verify all files are deleted
        for file_id in file_ids:
            response = test_client.get(f"/api/v1/files/{file_id}")
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_file_validation_endpoints(self, test_client, sample_tenant, temp_storage, async_session):
        """Test file validation via API"""
        
        # Create a test file for validation
        test_content = "File validation test content"
        test_file_path = f"{temp_storage}/validation_test.txt"
        Path(test_file_path).write_text(test_content)
        
        file_record = File(
            tenant_id=sample_tenant.id,
            tenant_code=sample_tenant.code,
            original_filename="validation_test.txt",
            stored_filename="stored_validation_test.txt",
            file_path=test_file_path,
            file_size=len(test_content.encode()),
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="validation_hash"
        )
        
        async_session.add(file_record)
        await async_session.commit()
        await async_session.refresh(file_record)
        
        # Validate files
        validation_data = {
            "file_ids": [str(file_record.id)],
            "tenant_code": sample_tenant.code,
            "check_integrity": True,
            "check_virus": False
        }
        
        with patch('src.file_service.services.AsyncFileValidator') as mock_validator:
            mock_validator_instance = AsyncMock()
            mock_validator_instance.validate_file.return_value = {
                "is_valid": True,
                "file_size": len(test_content.encode()),
                "mime_type": "text/plain",
                "validation_errors": []
            }
            mock_validator.return_value = mock_validator_instance
            
            response = test_client.post("/api/v1/files/validate", json=validation_data)
            assert response.status_code == 200
            
            validation_results = response.json()
            assert len(validation_results) == 1
            assert validation_results[0]["is_valid"] is True
    
    def test_statistics_endpoints(self, test_client):
        """Test statistics endpoints"""
        
        # Global file statistics
        response = test_client.get("/api/v1/files/stats/global")
        assert response.status_code == 200
        
        global_stats = response.json()
        assert "total_files" in global_stats
        assert "total_storage_bytes" in global_stats
        assert "active_tenants" in global_stats
    
    @pytest.mark.asyncio
    async def test_tenant_storage_info(self, test_client, sample_tenant):
        """Test tenant storage information endpoint"""
        
        response = test_client.get(f"/api/v1/health/storage/{sample_tenant.code}")
        assert response.status_code == 200
        
        storage_info = response.json()
        assert "tenant_code" in storage_info
        assert "storage_path" in storage_info
        assert "available_space" in storage_info


# Error Handling Integration Tests
@pytest.mark.integration
class TestFileServiceErrorHandling:
    """Test error handling in File Service API"""
    
    def test_tenant_not_found(self, test_client):
        """Test tenant not found scenarios"""
        
        # Get non-existent tenant
        response = test_client.get("/api/v1/tenants/nonexistent-tenant")
        assert response.status_code == 404
        
        # Update non-existent tenant
        response = test_client.put("/api/v1/tenants/nonexistent-tenant", json={"name": "Test"})
        assert response.status_code == 404
        
        # Delete non-existent tenant
        response = test_client.delete("/api/v1/tenants/nonexistent-tenant")
        assert response.status_code == 404
    
    def test_file_not_found(self, test_client):
        """Test file not found scenarios"""
        
        # Get non-existent file
        response = test_client.get(f"/api/v1/files/{uuid4()}")
        assert response.status_code == 404
        
        # Download non-existent file
        response = test_client.get(f"/api/v1/files/{uuid4()}/download")
        assert response.status_code == 404
        
        # Delete non-existent file
        response = test_client.delete(f"/api/v1/files/{uuid4()}")
        assert response.status_code == 404
    
    def test_invalid_tenant_data(self, test_client):
        """Test invalid tenant creation data"""
        
        # Missing required fields
        response = test_client.post("/api/v1/tenants/", json={})
        assert response.status_code == 422
        
        # Invalid tenant code format
        invalid_data = {
            "code": "invalid code with spaces",
            "name": "Test Tenant"
        }
        response = test_client.post("/api/v1/tenants/", json=invalid_data)
        assert response.status_code == 422
        
        # Negative quota values
        invalid_data = {
            "code": "test-tenant",
            "name": "Test Tenant",
            "storage_quota_bytes": -1000
        }
        response = test_client.post("/api/v1/tenants/", json=invalid_data)
        assert response.status_code == 422
    
    def test_duplicate_tenant_code(self, test_client):
        """Test duplicate tenant code handling"""
        
        tenant_data = {
            "code": "duplicate-test",
            "name": "First Tenant"
        }
        
        # Create first tenant
        response = test_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        
        # Try to create duplicate
        response = test_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 409  # Conflict
    
    def test_invalid_search_parameters(self, test_client):
        """Test invalid search parameters"""
        
        # Invalid date format
        invalid_search = {
            "tenant_code": "test-tenant",
            "uploaded_after": "invalid-date-format"
        }
        
        response = test_client.post("/api/v1/files/search", json=invalid_search)
        assert response.status_code == 422
        
        # Invalid size range
        invalid_search = {
            "tenant_code": "test-tenant",
            "min_size": 1000,
            "max_size": 100  # max < min
        }
        
        response = test_client.post("/api/v1/files/search", json=invalid_search)
        assert response.status_code == 422


# Performance Integration Tests
@pytest.mark.integration
@pytest.mark.slow
class TestFileServicePerformance:
    """Test performance aspects of File Service"""
    
    @pytest.mark.asyncio
    async def test_large_tenant_list_performance(self, test_client, async_session):
        """Test performance with many tenants"""
        
        # Create multiple tenants
        tenants = []
        for i in range(50):  # Reduced for test performance
            tenant = Tenant(
                code=f"perf-tenant-{i:03d}",
                name=f"Performance Test Tenant {i}",
                description=f"Tenant {i} for performance testing"
            )
            tenants.append(tenant)
        
        async_session.add_all(tenants)
        await async_session.commit()
        
        # Test tenant listing performance
        response = test_client.get("/api/v1/tenants/?skip=0&limit=100")
        assert response.status_code == 200
        
        tenants_data = response.json()
        assert len(tenants_data) >= 50
    
    @pytest.mark.asyncio
    async def test_large_file_list_performance(self, test_client, sample_tenant, temp_storage, async_session):
        """Test performance with many files"""
        
        # Create multiple files
        files = []
        for i in range(100):  # Reduced for test performance
            test_content = f"Performance test file {i} content"
            test_file_path = f"{temp_storage}/perf_file_{i}.txt"
            Path(test_file_path).write_text(test_content)
            
            file_record = File(
                tenant_id=sample_tenant.id,
                tenant_code=sample_tenant.code,
                original_filename=f"perf_file_{i}.txt",
                stored_filename=f"stored_perf_file_{i}.txt",
                file_path=test_file_path,
                file_size=len(test_content.encode()),
                mime_type="text/plain",
                file_extension=".txt",
                file_hash=f"perf_hash_{i}"
            )
            files.append(file_record)
        
        async_session.add_all(files)
        await async_session.commit()
        
        # Test file listing performance
        response = test_client.get(f"/api/v1/files/tenant/{sample_tenant.code}?skip=0&limit=50")
        assert response.status_code == 200
        
        files_data = response.json()
        assert files_data["total"] == 100
        assert len(files_data["files"]) == 50
        
        # Test search performance
        search_data = {
            "tenant_code": sample_tenant.code,
            "filename_pattern": "perf_file"
        }
        
        response = test_client.post("/api/v1/files/search", json=search_data)
        assert response.status_code == 200
        
        search_results = response.json()
        assert search_results["total"] == 100


# Caching Integration Tests
@pytest.mark.integration
class TestFileServiceCaching:
    """Test caching behavior in File Service"""
    
    @pytest.mark.asyncio
    async def test_tenant_caching(self, test_client, mock_redis):
        """Test tenant data caching"""
        
        # Create tenant
        tenant_data = {
            "code": "cache-test-001",
            "name": "Cache Test Tenant"
        }
        
        response = test_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        
        # First get - should set cache
        response = test_client.get("/api/v1/tenants/cache-test-001")
        assert response.status_code == 200
        
        # Verify cache operations were called
        mock_redis.get.assert_called()
        mock_redis.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_file_list_caching(self, test_client, sample_tenant, mock_redis):
        """Test file list caching"""
        
        # Get file list - should attempt caching
        response = test_client.get(f"/api/v1/files/tenant/{sample_tenant.code}")
        assert response.status_code == 200
        
        # Verify cache operations
        mock_redis.get.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
