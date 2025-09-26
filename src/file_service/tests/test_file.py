"""
Comprehensive test suite for File Service
Tests: models, CRUD, services, routes, and edge cases
"""

import pytest
import pytest_asyncio
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import aiofiles
import json
from uuid import uuid4, UUID

from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.shared.db import Base, get_db
from src.shared.cache import get_redis_client
from src.shared.config import Settings
from src.file_service.models import Tenant, File
from src.file_service.schemas import (
    TenantCreate, TenantUpdate, FileUpload, FileUpdate,
    FileSearchRequest, BulkDeleteRequest, ValidationRequest
)
from src.file_service.crud import TenantCRUD, FileCRUD
from src.file_service.services import TenantService, FileService
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
    return mock_redis


@pytest_asyncio.fixture
async def test_settings():
    """Test configuration settings"""
    return Settings(
        storage_base_path="/tmp/test_storage",
        max_file_size=1024 * 1024,  # 1MB
        allowed_extensions=".txt,.pdf,.json,.csv",
        max_zip_depth=2,
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/1"
    )


@pytest_asyncio.fixture
async def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


# Model Tests
@pytest.mark.unit
class TestTenantModel:
    """Test Tenant model functionality"""
    
    def test_tenant_creation(self):
        """Test basic tenant creation"""
        tenant = Tenant(
            code="test123",
            name="Test Tenant",
            description="Test Description",
            is_active=True,
            storage_quota_bytes=1000000,
            file_count_limit=100
        )
        
        assert tenant.code == "test123"
        assert tenant.name == "Test Tenant"
        assert tenant.is_active is True
        assert tenant.storage_quota_bytes == 1000000
        assert tenant.file_count_limit == 100
    
    def test_tenant_validation(self):
        """Test tenant code validation"""
        # Valid codes
        valid_codes = ["abc123", "test-tenant", "tenant_01"]
        for code in valid_codes:
            tenant = Tenant(code=code, name="Test")
            assert tenant.code == code
    
    @pytest.mark.asyncio
    async def test_tenant_relationships(self, async_session):
        """Test tenant-file relationships"""
        tenant = Tenant(code="test123", name="Test Tenant")
        async_session.add(tenant)
        await async_session.flush()
        
        file1 = File(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            original_filename="test1.txt",
            stored_filename="stored1.txt",
            file_path="/path/to/file1.txt",
            file_size=1000
        )
        file2 = File(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            original_filename="test2.txt",
            stored_filename="stored2.txt",
            file_path="/path/to/file2.txt",
            file_size=2000
        )
        
        async_session.add_all([file1, file2])
        await async_session.commit()
        
        # Refresh tenant to load relationships
        await async_session.refresh(tenant)
        assert len(tenant.files) == 2


@pytest.mark.unit
class TestFileModel:
    """Test File model functionality"""
    
    def test_file_creation(self):
        """Test basic file creation"""
        file = File(
            tenant_id=uuid4(),
            tenant_code="test123",
            original_filename="test.txt",
            stored_filename="stored_test.txt",
            file_path="/path/to/stored_test.txt",
            file_size=1024,
            mime_type="text/plain",
            file_extension=".txt",
            file_hash="abcd1234"
        )
        
        assert file.original_filename == "test.txt"
        assert file.stored_filename == "stored_test.txt"
        assert file.file_size == 1024
        assert file.mime_type == "text/plain"
    
    def test_file_properties(self):
        """Test file model properties"""
        file = File(
            tenant_id=uuid4(),
            tenant_code="test123",
            original_filename="test.zip",
            stored_filename="stored_test.zip",
            file_path="/storage/test123/2024-01/stored_test.zip",
            file_size=1024,
            file_extension=".zip"
        )
        
        assert file.is_zip_file is True
        assert file.storage_directory == "/storage/test123/2024-01"
        assert "1.0 KB" in file.get_display_size()
    
    def test_file_status_properties(self):
        """Test file status properties"""
        file = File(
            tenant_id=uuid4(),
            tenant_code="test123",
            original_filename="test.txt",
            stored_filename="stored_test.txt",
            file_path="/path/to/file.txt",
            file_size=1024,
            is_deleted=False
        )
        
        assert file.is_deleted is False


# CRUD Tests
@pytest.mark.unit
class TestTenantCRUD:
    """Test TenantCRUD operations"""
    
    @pytest.mark.asyncio
    async def test_create_tenant(self, async_session, mock_redis):
        """Test tenant creation"""
        crud = TenantCRUD()
        tenant_data = TenantCreate(
            code="test123",
            name="Test Tenant",
            description="Test Description"
        )
        
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        assert tenant.code == "test123"
        assert tenant.name == "Test Tenant"
        assert tenant.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_tenant_by_code(self, async_session, mock_redis):
        """Test getting tenant by code"""
        crud = TenantCRUD()
        
        # Create tenant first
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        created_tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Get tenant by code
        retrieved_tenant = await crud.get_by_code(async_session, "test123", mock_redis)
        
        assert retrieved_tenant is not None
        assert retrieved_tenant.id == created_tenant.id
        assert retrieved_tenant.code == "test123"
    
    @pytest.mark.asyncio
    async def test_update_tenant(self, async_session, mock_redis):
        """Test tenant update"""
        crud = TenantCRUD()
        
        # Create tenant
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Update tenant
        update_data = TenantUpdate(name="Updated Tenant", is_active=False)
        updated_tenant = await crud.update(async_session, tenant.id, update_data, mock_redis)
        
        assert updated_tenant.name == "Updated Tenant"
        assert updated_tenant.is_active is False
    
    @pytest.mark.asyncio
    async def test_delete_tenant(self, async_session, mock_redis, temp_storage):
        """Test tenant deletion"""
        crud = TenantCRUD()
        
        with patch('src.file_service.crud.cleanup_tenant_storage') as mock_cleanup:
            mock_cleanup.return_value = True
            
            # Create tenant
            tenant_data = TenantCreate(code="test123", name="Test Tenant")
            tenant = await crud.create(async_session, tenant_data, mock_redis)
            
            # Delete tenant
            result = await crud.delete(async_session, tenant.id, mock_redis, temp_storage)
            
            assert result is True
            mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_tenant_stats(self, async_session, mock_redis):
        """Test getting tenant statistics"""
        crud = TenantCRUD()
        
        # Create tenant with files
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await crud.create(async_session, tenant_data, mock_redis)
        
        # Add files
        file1 = File(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            original_filename="test1.txt",
            stored_filename="stored1.txt",
            file_path="/path/to/file1.txt",
            file_size=1000
        )
        file2 = File(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            original_filename="test2.txt",
            stored_filename="stored2.txt",
            file_path="/path/to/file2.txt",
            file_size=2000
        )
        
        async_session.add_all([file1, file2])
        await async_session.commit()
        
        # Get stats
        stats = await crud.get_stats(async_session, tenant.id)
        
        assert stats["total_files"] == 2
        assert stats["total_storage_bytes"] == 3000


@pytest.mark.unit
class TestFileCRUD:
    """Test FileCRUD operations"""
    
    @pytest.mark.asyncio
    async def test_create_file(self, async_session, mock_redis):
        """Test file creation"""
        # Create tenant first
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # Create file
        file_crud = FileCRUD()
        file_data = {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "original_filename": "test.txt",
            "stored_filename": "stored_test.txt",
            "file_path": "/path/to/file.txt",
            "file_size": 1024,
            "mime_type": "text/plain",
            "file_extension": ".txt",
            "file_hash": "abcd1234"
        }
        
        file = await file_crud.create(async_session, file_data, mock_redis)
        
        assert file.original_filename == "test.txt"
        assert file.tenant_id == tenant.id
        assert file.file_size == 1024
    
    @pytest.mark.asyncio
    async def test_get_files_by_tenant(self, async_session, mock_redis):
        """Test getting files by tenant"""
        # Create tenant and files
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        file_crud = FileCRUD()
        for i in range(3):
            file_data = {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "original_filename": f"test{i}.txt",
                "stored_filename": f"stored{i}.txt",
                "file_path": f"/path/to/file{i}.txt",
                "file_size": 1024 * (i + 1)
            }
            await file_crud.create(async_session, file_data, mock_redis)
        
        # Get files
        files, total = await file_crud.get_by_tenant(
            async_session, mock_redis, tenant.code, skip=0, limit=10,
        )
        
        assert len(files) == 3
        assert total == 3
    
    @pytest.mark.asyncio
    async def test_search_files(self, async_session, mock_redis):
        """Test file search functionality"""
        # Create tenant and files
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        file_crud = FileCRUD()
        file_data = {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "original_filename": "important_document.pdf",
            "stored_filename": "stored_doc.pdf",
            "file_path": "/path/to/doc.pdf",
            "file_size": 2048,
            "mime_type": "application/pdf",
            "file_extension": ".pdf"
        }
        await file_crud.create(async_session, file_data, mock_redis)
        
        # Search files
        search_request = FileSearchRequest(
            tenant_code="test123",
            filename_pattern="important",
            file_extension=".pdf",
            min_size=1000,
            max_size=5000
        )
        
        files, total = await file_crud.search_files(async_session, search_request)
        
        assert len(files) == 1
        assert files[0].original_filename == "important_document.pdf"
    
    @pytest.mark.asyncio
    async def test_bulk_delete_files(self, async_session, mock_redis, temp_storage):
        """Test bulk file deletion"""
        # Create tenant and files
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        file_crud = FileCRUD()
        file_ids = []
        
        for i in range(3):
            file_data = {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "original_filename": f"test{i}.txt",
                "stored_filename": f"stored{i}.txt",
                "file_path": f"{temp_storage}/test{i}.txt",
                "file_size": 1024
            }
            file = await file_crud.create(async_session, file_data, mock_redis)
            file_ids.append(file.id)
            
            # Create actual files
            Path(f"{temp_storage}/test{i}.txt").touch()
        
        # Bulk delete
        with patch('src.file_service.crud.delete_file') as mock_delete:
            mock_delete.return_value = True
            
            request = BulkDeleteRequest(
                tenant_code="test123",
                file_ids=file_ids,
                permanent=True
            )
            
            result = await file_crud.bulk_delete(async_session, request, mock_redis)
            
            assert result["deleted_count"] == 3
            assert result["failed_count"] == 0


# Service Tests
@pytest.mark.unit
class TestTenantService:
    """Test TenantService business logic"""
    
    @pytest.mark.asyncio
    async def test_create_tenant(self, async_session, mock_redis, temp_storage, test_settings):
        """Test tenant creation with storage setup"""
        with patch('src.file_service.services.ensure_directory_exists') as mock_ensure_dir:
            mock_ensure_dir.return_value = True
            
            service = TenantService()
            tenant_data = TenantCreate(
                code="test123",
                name="Test Tenant",
                storage_quota_bytes=1000000
            )
            
            tenant = await service.create_tenant(
                async_session, tenant_data, mock_redis, test_settings
            )
            
            assert tenant.code == "test123"
            assert tenant.storage_quota_bytes == 1000000
            mock_ensure_dir.assert_called()
    
    @pytest.mark.asyncio
    async def test_check_tenant_quotas(self, async_session, mock_redis):
        """Test tenant quota checking"""
        # Create tenant with limits
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(
            code="test123",
            name="Test Tenant",
            storage_quota_bytes=5000,
            file_count_limit=2
        )
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # Add files to approach limits
        file_crud = FileCRUD()
        for i in range(2):
            file_data = {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "original_filename": f"test{i}.txt",
                "stored_filename": f"stored{i}.txt",
                "file_path": f"/path/to/file{i}.txt",
                "file_size": 2000  # Total: 4000 bytes
            }
            await file_crud.create(async_session, file_data, mock_redis)
        
        service = TenantService()
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        
        assert quota_check["within_storage_quota"] is True
        assert quota_check["within_file_limit"] is True
        assert quota_check["storage_usage_percentage"] == 80.0  # 4000/5000


@pytest.mark.unit
class TestFileService:
    """Test FileService business logic"""
    
    @pytest.mark.asyncio
    async def test_upload_file(self, async_session, mock_redis, temp_storage, test_settings):
        """Test file upload process"""
        # Create tenant
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # Create test file content
        test_content = b"This is test file content"
        
        # Mock file upload
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=test_content)
        
        with patch('src.file_service.services.save_uploaded_file') as mock_save, \
             patch('src.file_service.services.get_file_mime_type') as mock_mime, \
             patch('src.file_service.services.generate_file_hash') as mock_hash, \
             patch('src.file_service.services.generate_storage_path') as mock_path, \
             patch('src.file_service.services.generate_unique_filename') as mock_filename:
            
            mock_save.return_value = True
            mock_mime.return_value = "text/plain"
            mock_hash.return_value = "abcd1234"
            mock_path.return_value = f"{temp_storage}/test123/2024-01"
            mock_filename.return_value = "stored_test.txt"
            
            service = FileService()
            file_upload_data = FileUpload(
                tenant_code="test123",
                description="Test file upload"
            )
            
            uploaded_file = await service.upload_file(
                async_session, mock_file, file_upload_data, mock_redis, test_settings
            )
            
            assert uploaded_file.original_filename == "test.txt"
            assert uploaded_file.tenant_code == "test123"
            assert uploaded_file.file_size == len(test_content)
    
    @pytest.mark.asyncio
    async def test_validate_files(self, async_session, mock_redis, test_settings):
        """Test file validation"""
        # Create tenant and file
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="test123", name="Test Tenant")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        file_crud = FileCRUD()
        file_data = {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "original_filename": "test.txt",
            "stored_filename": "stored_test.txt",
            "file_path": "/path/to/file.txt",
            "file_size": 1024
        }
        file = await file_crud.create(async_session, file_data, mock_redis)
        
        with patch('src.file_service.services.AsyncFileValidator') as mock_validator:
            mock_validator_instance = AsyncMock()
            mock_validator_instance.validate_file.return_value = {
                "is_valid": True,
                "file_size": 1024,
                "mime_type": "text/plain",
                "validation_errors": []
            }
            mock_validator.return_value = mock_validator_instance
            
            service = FileService()
            validation_request = ValidationRequest(
                file_ids=[file.id],
                tenant_code="test123"
            )
            
            results = await service.validate_files(
                async_session, validation_request, mock_redis, test_settings
            )
            
            assert len(results) == 1
            assert results[0]["is_valid"] is True


# Integration Tests
@pytest.mark.integration
class TestFileServiceIntegration:
    """Integration tests for File Service components"""
    
    @pytest.mark.asyncio
    async def test_tenant_file_lifecycle(self, async_session, mock_redis, temp_storage, test_settings):
        """Test complete tenant and file lifecycle"""
        # Create tenant
        tenant_service = TenantService()
        tenant_data = TenantCreate(
            code="lifecycle123",
            name="Lifecycle Test Tenant",
            storage_quota_bytes=10000,
            file_count_limit=5
        )
        
        with patch('src.file_service.services.ensure_directory_exists') as mock_ensure_dir:
            mock_ensure_dir.return_value = True
            tenant = await tenant_service.create_tenant(
                async_session, tenant_data, mock_redis, test_settings
            )
        
        # Upload file
        file_service = FileService()
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "lifecycle_test.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"Lifecycle test content")
        
        with patch('src.file_service.services.save_uploaded_file') as mock_save, \
             patch('src.file_service.services.get_file_mime_type') as mock_mime, \
             patch('src.file_service.services.generate_file_hash') as mock_hash, \
             patch('src.file_service.services.generate_storage_path') as mock_path, \
             patch('src.file_service.services.generate_unique_filename') as mock_filename:
            
            mock_save.return_value = True
            mock_mime.return_value = "text/plain"
            mock_hash.return_value = "lifecycle1234"
            mock_path.return_value = f"{temp_storage}/lifecycle123/2024-01"
            mock_filename.return_value = "stored_lifecycle.txt"
            
            upload_data = FileUpload(tenant_code="lifecycle123")
            uploaded_file = await file_service.upload_file(
                async_session, mock_file, upload_data, mock_redis, test_settings
            )
        
        # Check tenant stats
        stats = await tenant_service.get_tenant_stats(async_session, tenant.id)
        assert stats["total_files"] == 1
        
        # Check quotas
        quota_info = await tenant_service.check_tenant_quotas(async_session, tenant.id)
        assert quota_info["within_storage_quota"] is True
        assert quota_info["within_file_limit"] is True
        
        # Delete file
        with patch('src.file_service.services.delete_file') as mock_delete:
            mock_delete.return_value = True
            result = await file_service.delete_file(
                async_session, uploaded_file.id, mock_redis, permanent=True
            )
            assert result is True
        
        # Delete tenant
        with patch('src.file_service.services.cleanup_tenant_storage') as mock_cleanup:
            mock_cleanup.return_value = True
            result = await tenant_service.delete_tenant(
                async_session, tenant.id, mock_redis, temp_storage
            )
            assert result is True


# Async Tests
@pytest.mark.asyncio
class TestAsyncOperations:
    """Test async-specific functionality"""
    
    @pytest.mark.asyncio
    async def test_concurrent_file_uploads(self, async_session, mock_redis, temp_storage, test_settings):
        """Test concurrent file uploads"""
        # Create tenant
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="concurrent123", name="Concurrent Test")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        file_service = FileService()
        
        async def upload_file(filename: str):
            mock_file = MagicMock(spec=UploadFile)
            mock_file.filename = filename
            mock_file.content_type = "text/plain"
            mock_file.read = AsyncMock(return_value=f"Content of {filename}".encode())
            
            with patch('src.file_service.services.save_uploaded_file') as mock_save, \
                 patch('src.file_service.services.get_file_mime_type') as mock_mime, \
                 patch('src.file_service.services.generate_file_hash') as mock_hash, \
                 patch('src.file_service.services.generate_storage_path') as mock_path, \
                 patch('src.file_service.services.generate_unique_filename') as mock_filename:
                
                mock_save.return_value = True
                mock_mime.return_value = "text/plain"
                mock_hash.return_value = f"hash_{filename}"
                mock_path.return_value = f"{temp_storage}/concurrent123/2024-01"
                mock_filename.return_value = f"stored_{filename}"
                
                upload_data = FileUpload(tenant_code="concurrent123")
                return await file_service.upload_file(
                    async_session, mock_file, upload_data, mock_redis, test_settings
                )
        
        # Upload multiple files concurrently
        import asyncio
        tasks = [upload_file(f"file{i}.txt") for i in range(5)]
        uploaded_files = await asyncio.gather(*tasks)
        
        assert len(uploaded_files) == 5
        assert all(f.tenant_code == "concurrent123" for f in uploaded_files)
    
    @pytest.mark.asyncio
    async def test_async_cache_operations(self, async_session, mock_redis):
        """Test async Redis cache operations"""
        tenant_crud = TenantCRUD()
        
        # Test cache miss then hit
        mock_redis.get.return_value = None  # Cache miss
        
        tenant_data = TenantCreate(code="cache123", name="Cache Test")
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # First call should hit database
        result1 = await tenant_crud.get_by_code(async_session, "cache123", mock_redis)
        assert result1.code == "cache123"
        
        # Mock cache hit
        mock_redis.get.return_value = json.dumps({
            "id": str(tenant.id),
            "code": "cache123",
            "name": "Cache Test",
            "is_active": True
        }).encode()
        
        # Second call should hit cache
        result2 = await tenant_crud.get_by_code(async_session, "cache123", mock_redis)
        assert result2 is not None  # Cache implementation would return cached data


# Edge Case Tests
@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_duplicate_tenant_code(self, async_session, mock_redis):
        """Test handling of duplicate tenant codes"""
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(code="duplicate123", name="First Tenant")
        
        # Create first tenant
        await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # Try to create duplicate
        with pytest.raises(Exception):  # Should raise integrity error
            await tenant_crud.create(async_session, tenant_data, mock_redis)
    
    @pytest.mark.asyncio
    async def test_file_size_validation(self, test_settings):
        """Test file size validation"""
        from src.shared.utils import validate_file_size, FileValidationError
        
        # Valid size
        validate_file_size(1024, test_settings)
        
        # Invalid size
        with pytest.raises(FileValidationError):
            validate_file_size(test_settings.max_file_size + 1, test_settings)
    
    @pytest.mark.asyncio
    async def test_invalid_file_extension(self, test_settings):
        """Test file extension validation"""
        from src.shared.utils import validate_file_extension, FileValidationError
        
        # Valid extension
        validate_file_extension("test.txt", test_settings)
        
        # Invalid extension
        with pytest.raises(FileValidationError):
            validate_file_extension("test.exe", test_settings)
    
    @pytest.mark.asyncio
    async def test_storage_quota_exceeded(self, async_session, mock_redis):
        """Test storage quota validation"""
        # Create tenant with small quota
        tenant_crud = TenantCRUD()
        tenant_data = TenantCreate(
            code="quota123",
            name="Quota Test",
            storage_quota_bytes=1000
        )
        tenant = await tenant_crud.create(async_session, tenant_data, mock_redis)
        
        # Add file that exceeds quota
        file_crud = FileCRUD()
        file_data = {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "original_filename": "large_file.txt",
            "stored_filename": "stored_large.txt",
            "file_path": "/path/to/large.txt",
            "file_size": 1500  # Exceeds 1000 byte quota
        }
        await file_crud.create(async_session, file_data, mock_redis)
        
        # Check quota status
        service = TenantService()
        quota_check = await service.check_tenant_quotas(async_session, tenant.id)
        assert quota_check["within_storage_quota"] is False
    
    @pytest.mark.asyncio
    async def test_nonexistent_file_operations(self, async_session, mock_redis):
        """Test operations on nonexistent files"""
        file_crud = FileCRUD()
        
        # Try to get nonexistent file
        file = await file_crud.get_by_id(async_session, uuid4())
        assert file is None
        
        # Try to delete nonexistent file
        result = await file_crud.delete(
            async_session, uuid4(), mock_redis, permanent=True
        )
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
