"""
Dedicated tests for Tenant management functionality
Tests: Tenant operations, quota management, and tenant-specific workflows
"""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.db import Base
from src.shared.config import Settings
from src.file_service.models import Tenant, File
from src.file_service.schemas import TenantCreate, TenantUpdate
from src.file_service.crud import TenantCRUD
from src.file_service.services import TenantService


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
        max_file_size=1024 * 1024,
        allowed_extensions=".txt,.pdf,.json,.csv",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/1"
    )


@pytest_asyncio.fixture
async def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


# Tenant Model Tests
@pytest.mark.unit
class TestTenantModel:
    """Test Tenant model functionality in detail"""
    
    def test_tenant_creation_with_all_fields(self):
        """Test tenant creation with all optional fields"""
        tenant = Tenant(
            code="comprehensive-test",
            name="Comprehensive Test Tenant",
            description="A tenant with all fields populated",
            is_active=True,
            storage_quota_bytes=104857600,  # 100MB
            file_count_limit=1000,
            created_by="test-user",
            settings='{"theme": "dark", "notifications": true}'
        )
        
        assert tenant.code == "comprehensive-test"
        assert tenant.name == "Comprehensive Test Tenant"
        assert tenant.description == "A tenant with all fields populated"
        assert tenant.is_active is True
        assert tenant.storage_quota_bytes == 104857600
        assert tenant.file_count_limit == 1000
        assert tenant.created_by == "test-user"
        assert tenant.settings == '{"theme": "dark", "notifications": true}'
        
        # Test auto-generated fields
        assert tenant.id is not None
        assert tenant.created_at is not None
        assert tenant.updated_at is not None
    
    def test_tenant_defaults(self):
        """Test tenant default values"""
        tenant = Tenant(
            code="default-test",
            name="Default Test Tenant"
        )
        
        assert tenant.is_active is True  # Default should be True
        assert tenant.storage_quota_bytes is None  # Default unlimited
        assert tenant.file_count_limit is None  # Default unlimited
        assert tenant.description is None
        assert tenant.created_by is None
        assert tenant.settings is None
    
    def test_tenant_code_validation_patterns(self):
        """Test various tenant code patterns"""
        valid_codes = [
            "simple",
            "test123",
            "test-tenant",
            "test_tenant",
            "a1b2c3",
            "tenant-with-multiple-hyphens",
            "tenant_with_multiple_underscores"
        ]
        
        for code in valid_codes:
            tenant = Tenant(code=code, name="Test")
            assert tenant.code == code
    
    @pytest.mark.asyncio
    async def test_tenant_file_relationship_cascade(self, async_session):
        """Test tenant-file relationship and cascade behavior"""
        
        # Create tenant
        tenant = Tenant(
            code="relationship-test",
            name="Relationship Test Tenant"
        )
        async_session.add(tenant)
        await async_session.flush()
        
        # Add multiple files
        files = []
        for i in range(5):
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=f"test_{i}.txt",
                stored_filename=f"stored_test_{i}.txt",
                file_path=f"/path/to/test_{i}.txt",
                file_size=1024 * (i + 1)
            )
            files.append(file)
        
        async_session.add_all(files)
        await async_session.commit()
        
        # Refresh tenant to load relationships
        await async_session.refresh(tenant)
        
        # Test relationship
        assert len(tenant.files) == 5
        assert all(f.tenant_id == tenant.id for f in tenant.files)
        
        # Test file access through relationship
        file_names = {f.original_filename for f in tenant.files}
        expected_names = {f"test_{i}.txt" for i in range(5)}
        assert file_names == expected_names


# Tenant CRUD Tests
@pytest.mark.unit
class TestTenantCRUD:
    """Test Tenant CRUD operations in detail"""
    
    @pytest.mark.asyncio
    async def test_create_tenant_with_validation(self, async_session, mock_redis):
        """Test tenant creation with various validation scenarios"""
        crud = TenantCRUD()
        
        # Valid tenant creation
        tenant_data = TenantCreate(
            code="crud-test-001",
            name="CRUD Test Tenant",
            description="Testing CRUD operations",
            storage_quota_bytes=52428800,  # 50MB
            file_count_limit=500
        )
        
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        assert tenant.code == "crud-test-001"
        assert tenant.name == "CRUD Test Tenant"
        assert tenant.storage_quota_bytes == 52428800
        assert tenant.file_count_limit == 500
        assert tenant.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_tenant_with_caching(self, async_session, mock_redis):
        """Test tenant retrieval with caching behavior"""
        crud = TenantCRUD()
        
        # Create tenant
        tenant_data = TenantCreate(
            code="cache-test-001",
            name="Cache Test Tenant"
        )
        created_tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # First retrieval - should cache result
        retrieved_tenant = await crud.get_by_code(async_session, "cache-test-001", mock_redis)
        
        assert retrieved_tenant is not None
        assert retrieved_tenant.id == created_tenant.id
        
        # Verify cache operations
        mock_redis.get.assert_called()
        mock_redis.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_tenant_partial(self, async_session, mock_redis):
        """Test partial tenant updates"""
        crud = TenantCRUD()
        
        # Create tenant
        tenant_data = TenantCreate(
            code="update-test-001",
            name="Original Name",
            description="Original Description",
            storage_quota_bytes=10485760,
            file_count_limit=100
        )
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Update only name
        update_data = TenantUpdate(name="Updated Name")
        updated_tenant = await crud.update(async_session, tenant.id, update_data, mock_redis)
        
        assert updated_tenant.name == "Updated Name"
        assert updated_tenant.description == "Original Description"  # Unchanged
        assert updated_tenant.storage_quota_bytes == 10485760  # Unchanged
        
        # Update only quota
        update_data = TenantUpdate(storage_quota_bytes=20971520)  # 20MB
        updated_tenant = await crud.update(async_session, tenant.id, update_data, mock_redis)
        
        assert updated_tenant.storage_quota_bytes == 20971520
        assert updated_tenant.name == "Updated Name"  # Still updated from before
    
    @pytest.mark.asyncio
    async def test_tenant_statistics_calculation(self, async_session, mock_redis):
        """Test tenant statistics calculation with various scenarios"""
        crud = TenantCRUD()
        
        # Create tenant
        tenant_data = TenantCreate(
            code="stats-test-001",
            name="Statistics Test Tenant"
        )
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add files with different sizes and statuses
        files_data = [
            {"name": "small.txt", "size": 1024, "is_deleted": False},
            {"name": "medium.txt", "size": 5120, "is_deleted": False},
            {"name": "large.txt", "size": 10240, "is_deleted": False},
            {"name": "deleted.txt", "size": 2048, "is_deleted": True},  # Should not count
        ]
        
        for file_data in files_data:
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=file_data["name"],
                stored_filename=f"stored_{file_data['name']}",
                file_path=f"/path/to/{file_data['name']}",
                file_size=file_data["size"],
                is_deleted=file_data["is_deleted"]
            )
            async_session.add(file)
        
        await async_session.commit()
        
        # Get statistics
        stats = await crud.get_stats(async_session, tenant.id)
        
        assert stats["total_files"] == 3  # Excluding deleted file
        assert stats["total_storage_bytes"] == 16384  # 1024 + 5120 + 10240
        assert stats["average_file_size"] == 5461.33  # Approximately
        assert "largest_file_size" in stats
        assert "smallest_file_size" in stats
    
    @pytest.mark.asyncio
    async def test_delete_tenant_with_cleanup(self, async_session, mock_redis, temp_storage):
        """Test tenant deletion with proper cleanup"""
        crud = TenantCRUD()
        
        # Create tenant
        tenant_data = TenantCreate(
            code="delete-test-001",
            name="Delete Test Tenant"
        )
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add some files
        for i in range(3):
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=f"file_{i}.txt",
                stored_filename=f"stored_file_{i}.txt",
                file_path=f"{temp_storage}/file_{i}.txt",
                file_size=1024
            )
            async_session.add(file)
        
        await async_session.commit()
        
        # Mock storage cleanup
        with patch('src.file_service.crud.cleanup_tenant_storage') as mock_cleanup:
            mock_cleanup.return_value = True
            
            # Delete tenant
            result = await crud.delete(async_session, tenant.id, mock_redis, temp_storage)
            
            assert result is True
            mock_cleanup.assert_called_once_with(temp_storage, tenant.code)
        
        # Verify tenant is deleted
        deleted_tenant = await crud.get_by_id(async_session, tenant.id)
        assert deleted_tenant is None


# Tenant Service Tests
@pytest.mark.unit
class TestTenantService:
    """Test Tenant service business logic"""
    
    @pytest.mark.asyncio
    async def test_create_tenant_with_storage_setup(self, async_session, mock_redis, temp_storage, test_settings):
        """Test tenant creation with storage directory setup"""
        
        with patch('src.file_service.services.ensure_directory_exists') as mock_ensure_dir:
            mock_ensure_dir.return_value = True
            
            service = TenantService()
            tenant_data = TenantCreate(
                code="service-test-001",
                name="Service Test Tenant",
                storage_quota_bytes=10485760,
                file_count_limit=100
            )
            
            tenant = await service.create_tenant(
                async_session, tenant_data, mock_redis, test_settings
            )
            
            assert tenant.code == "service-test-001"
            assert tenant.storage_quota_bytes == 10485760
            
            # Verify storage directory creation was attempted
            mock_ensure_dir.assert_called()
    
    @pytest.mark.asyncio
    async def test_quota_enforcement_scenarios(self, async_session, mock_redis):
        """Test various quota enforcement scenarios"""
        service = TenantService()
        
        # Create tenant with specific quotas
        tenant_data = TenantCreate(
            code="quota-test-001",
            name="Quota Test Tenant",
            storage_quota_bytes=5120,  # 5KB
            file_count_limit=3
        )
        
        # Create tenant through service
        crud = TenantCRUD()
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add files approaching limits
        files_data = [
            {"name": "file1.txt", "size": 1024},
            {"name": "file2.txt", "size": 2048},
            {"name": "file3.txt", "size": 1024},  # Total: 4096 bytes, 3 files
        ]
        
        for file_data in files_data:
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=file_data["name"],
                stored_filename=f"stored_{file_data['name']}",
                file_path=f"/path/to/{file_data['name']}",
                file_size=file_data["size"]
            )
            async_session.add(file)
        
        await async_session.commit()
        
        # Check quotas - should be within limits
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is True
        assert quota_check["within_file_limit"] is True
        assert quota_check["storage_usage_percentage"] == 80.0  # 4096/5120
        assert quota_check["file_usage_percentage"] == 100.0  # 3/3
        
        # Add another file to exceed storage quota
        exceeding_file = File(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            original_filename="exceeding.txt",
            stored_filename="stored_exceeding.txt",
            file_path="/path/to/exceeding.txt",
            file_size=2048  # Would exceed 5KB limit
        )
        async_session.add(exceeding_file)
        await async_session.commit()
        
        # Check quotas again
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is False
        assert quota_check["within_file_limit"] is False  # Now 4 files > 3 limit
        assert quota_check["storage_usage_percentage"] > 100.0
    
    @pytest.mark.asyncio
    async def test_tenant_with_unlimited_quotas(self, async_session, mock_redis):
        """Test tenant behavior with unlimited quotas"""
        service = TenantService()
        
        # Create tenant with no quotas (unlimited)
        tenant_data = TenantCreate(
            code="unlimited-test-001",
            name="Unlimited Test Tenant"
            # No storage_quota_bytes or file_count_limit
        )
        
        crud = TenantCRUD()
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add many files with large sizes
        for i in range(10):
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=f"large_file_{i}.txt",
                stored_filename=f"stored_large_file_{i}.txt",
                file_path=f"/path/to/large_file_{i}.txt",
                file_size=1048576  # 1MB each
            )
            async_session.add(file)
        
        await async_session.commit()
        
        # Check quotas - should always be within limits for unlimited tenant
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is True
        assert quota_check["within_file_limit"] is True
        assert quota_check["storage_usage_percentage"] == 0.0  # Unlimited
        assert quota_check["file_usage_percentage"] == 0.0  # Unlimited
    
    @pytest.mark.asyncio
    async def test_tenant_stats_with_complex_scenarios(self, async_session, mock_redis):
        """Test tenant statistics with complex file scenarios"""
        service = TenantService()
        
        # Create tenant
        tenant_data = TenantCreate(
            code="complex-stats-001",
            name="Complex Stats Test Tenant"
        )
        
        crud = TenantCRUD()
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add files with various characteristics
        current_time = datetime.now(timezone.utc)
        
        complex_files = [
            {
                "name": "recent_small.txt", 
                "size": 512, 
                "status": "uploaded",
                "deleted": False,
                "mime_type": "text/plain"
            },
            {
                "name": "old_large.pdf", 
                "size": 2097152,  # 2MB
                "status": "completed",
                "deleted": False,
                "mime_type": "application/pdf"
            },
            {
                "name": "processing.doc", 
                "size": 1048576,  # 1MB
                "status": "processing",
                "deleted": False,
                "mime_type": "application/msword"
            },
            {
                "name": "deleted_file.txt", 
                "size": 1024, 
                "status": "uploaded",
                "deleted": True,
                "mime_type": "text/plain"
            },
            {
                "name": "error_file.json", 
                "size": 256, 
                "status": "error",
                "deleted": False,
                "mime_type": "application/json"
            }
        ]
        
        for file_data in complex_files:
            file = File(
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                original_filename=file_data["name"],
                stored_filename=f"stored_{file_data['name']}",
                file_path=f"/path/to/{file_data['name']}",
                file_size=file_data["size"],
                status=file_data["status"],
                is_deleted=file_data["deleted"],
                mime_type=file_data["mime_type"],
                uploaded_at=current_time
            )
            async_session.add(file)
        
        await async_session.commit()
        
        # Get comprehensive stats
        stats = await service.get_tenant_stats(async_session, tenant.id)
        
        # Verify stats calculations
        assert stats["total_files"] == 4  # Excluding deleted file
        assert stats["total_storage_bytes"] == 3146240  # Sum of non-deleted files
        assert stats["files_by_status"]["uploaded"] == 1
        assert stats["files_by_status"]["completed"] == 1
        assert stats["files_by_status"]["processing"] == 1
        assert stats["files_by_status"]["error"] == 1
        
        # Verify file type distribution
        expected_types = {
            "text/plain": 1,
            "application/pdf": 1,
            "application/msword": 1,
            "application/json": 1
        }
        
        for mime_type, count in expected_types.items():
            assert stats["files_by_type"][mime_type] == count


# Tenant Integration Tests
@pytest.mark.integration
class TestTenantIntegration:
    """Test tenant integration with other components"""
    
    @pytest.mark.asyncio
    async def test_tenant_lifecycle_with_file_operations(self, async_session, mock_redis, temp_storage, test_settings):
        """Test complete tenant lifecycle with file operations"""
        
        # Phase 1: Create tenant
        service = TenantService()
        
        with patch('src.file_service.services.ensure_directory_exists') as mock_ensure_dir:
            mock_ensure_dir.return_value = True
            
            tenant_data = TenantCreate(
                code="lifecycle-test-001",
                name="Lifecycle Test Tenant",
                storage_quota_bytes=10485760,  # 10MB
                file_count_limit=5
            )
            
            tenant = await service.create_tenant(
                async_session, tenant_data, mock_redis, test_settings
            )
        
        # Phase 2: Add files and monitor quotas
        from src.file_service.crud import FileCRUD
        file_crud = FileCRUD()
        
        for i in range(3):
            file_data = {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "original_filename": f"lifecycle_file_{i}.txt",
                "stored_filename": f"stored_lifecycle_file_{i}.txt",
                "file_path": f"{temp_storage}/lifecycle_file_{i}.txt",
                "file_size": 1048576 * (i + 1),  # 1MB, 2MB, 3MB
                "mime_type": "text/plain",
                "file_extension": ".txt"
            }
            
            await file_crud.create(async_session, file_data, mock_redis)
        
        # Phase 3: Check quota status
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is True  # 6MB < 10MB
        assert quota_check["within_file_limit"] is True  # 3 < 5
        
        # Phase 4: Get updated stats
        stats = await service.get_tenant_stats(async_session, tenant.id)
        
        assert stats["total_files"] == 3
        assert stats["total_storage_bytes"] == 6291456  # 6MB total
        
        # Phase 5: Update tenant
        update_data = TenantUpdate(
            storage_quota_bytes=5242880,  # Reduce to 5MB
            file_count_limit=2  # Reduce to 2 files
        )
        
        crud = TenantCRUD()
        updated_tenant = await crud.update(async_session, tenant.id, update_data, mock_redis)
        
        # Phase 6: Check quotas after update (should exceed limits)
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is False  # 6MB > 5MB
        assert quota_check["within_file_limit"] is False  # 3 > 2
        
        # Phase 7: Clean up - delete tenant
        with patch('src.file_service.services.cleanup_tenant_storage') as mock_cleanup:
            mock_cleanup.return_value = True
            
            result = await service.delete_tenant(
                async_session, tenant.id, mock_redis, temp_storage
            )
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
