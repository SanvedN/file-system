import pytest
import asyncio
import tempfile
import os
import zipfile
from datetime import datetime
from unittest.mock import patch, AsyncMock

from ..utils import (
    validate_file_size,
    validate_file_extension,
    validate_zip_depth,
    generate_file_hash,
    generate_storage_path,
    ensure_directory_exists,
    save_uploaded_file,
    delete_file,
    get_file_stats,
    generate_unique_filename,
    validate_tenant_code,
    AsyncFileValidator,
    FileValidationError,
    StorageError
)
from ..config import settings


class TestFileValidation:
    """Test file validation functions"""

    @pytest.mark.asyncio
    async def test_validate_file_size_valid(self):
        """Test valid file size"""
        result = await validate_file_size(1024)  # 1KB
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_file_size_invalid(self):
        """Test invalid file size"""
        result = await validate_file_size(settings.max_file_size + 1)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_file_extension_valid(self):
        """Test valid file extension"""
        result = await validate_file_extension("test.pdf")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_file_extension_invalid(self):
        """Test invalid file extension"""
        result = await validate_file_extension("test.exe")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_file_extension_case_insensitive(self):
        """Test case insensitive extension validation"""
        result = await validate_file_extension("test.PDF")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_zip_depth_valid(self):
        """Test valid zip depth"""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            with zipfile.ZipFile(tmp_zip.name, 'w') as zf:
                zf.writestr('test.txt', 'content')
                zf.writestr('folder/test.txt', 'content')
            
            result = await validate_zip_depth(tmp_zip.name, max_depth=5)
            assert result is True
            
            os.unlink(tmp_zip.name)

    @pytest.mark.asyncio
    async def test_validate_zip_depth_invalid(self):
        """Test invalid zip depth"""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            with zipfile.ZipFile(tmp_zip.name, 'w') as zf:
                # Create deep nested structure
                zf.writestr('a/b/c/d/e/f/test.txt', 'content')
            
            result = await validate_zip_depth(tmp_zip.name, max_depth=3)
            assert result is False
            
            os.unlink(tmp_zip.name)


class TestFileOperations:
    """Test file operation functions"""

    @pytest.mark.asyncio
    async def test_generate_file_hash(self):
        """Test file hash generation"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file.flush()
            
            hash_result = await generate_file_hash(tmp_file.name)
            assert len(hash_result) == 64  # SHA256 hex length
            assert isinstance(hash_result, str)
            
            os.unlink(tmp_file.name)

    @pytest.mark.asyncio
    async def test_generate_file_hash_error(self):
        """Test file hash generation with non-existent file"""
        with pytest.raises(StorageError):
            await generate_file_hash('/non/existent/file.txt')

    def test_generate_storage_path(self):
        """Test storage path generation"""
        tenant_code = "test_tenant"
        test_date = datetime(2023, 5, 15)
        
        path = generate_storage_path(tenant_code, test_date)
        assert path.endswith("test_tenant/2023-05")
        assert settings.storage_base_path in path

    def test_generate_storage_path_current_date(self):
        """Test storage path generation with current date"""
        tenant_code = "test_tenant"
        path = generate_storage_path(tenant_code)
        assert tenant_code in path
        assert settings.storage_base_path in path

    @pytest.mark.asyncio
    async def test_ensure_directory_exists(self):
        """Test directory creation"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_path = os.path.join(tmp_dir, "new_directory")
            result = await ensure_directory_exists(test_path)
            assert result is True
            assert os.path.exists(test_path)

    @pytest.mark.asyncio
    async def test_save_uploaded_file(self):
        """Test file saving"""
        content = b"test file content"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "test_file.txt")
            result = await save_uploaded_file(content, file_path)
            
            assert result is True
            assert os.path.exists(file_path)
            
            with open(file_path, 'rb') as f:
                assert f.read() == content

    @pytest.mark.asyncio
    async def test_delete_file_existing(self):
        """Test deleting existing file"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b'content')
            tmp_file.flush()
            
            result = await delete_file(tmp_file.name)
            assert result is True
            assert not os.path.exists(tmp_file.name)

    @pytest.mark.asyncio
    async def test_delete_file_non_existing(self):
        """Test deleting non-existing file"""
        result = await delete_file('/non/existent/file.txt')
        assert result is False

    @pytest.mark.asyncio
    async def test_get_file_stats(self):
        """Test getting file statistics"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file.flush()
            
            stats = await get_file_stats(tmp_file.name)
            assert stats is not None
            assert stats['size'] == 12  # length of 'test content'
            assert 'created' in stats
            assert 'modified' in stats
            
            os.unlink(tmp_file.name)

    @pytest.mark.asyncio
    async def test_get_file_stats_non_existing(self):
        """Test getting stats for non-existing file"""
        stats = await get_file_stats('/non/existent/file.txt')
        assert stats is None


class TestUtilityFunctions:
    """Test utility functions"""

    def test_generate_unique_filename(self):
        """Test unique filename generation"""
        original = "test_file.txt"
        unique1 = generate_unique_filename(original)
        unique2 = generate_unique_filename(original)
        
        assert unique1 != unique2
        assert unique1.endswith('.txt')
        assert 'test_file' in unique1

    @pytest.mark.asyncio
    async def test_validate_tenant_code_valid(self):
        """Test valid tenant code"""
        assert await validate_tenant_code("valid_tenant") is True
        assert await validate_tenant_code("tenant123") is True
        assert await validate_tenant_code("test-tenant") is True

    @pytest.mark.asyncio
    async def test_validate_tenant_code_invalid(self):
        """Test invalid tenant code"""
        assert await validate_tenant_code("a") is False  # too short
        assert await validate_tenant_code("a" * 51) is False  # too long
        assert await validate_tenant_code("tenant@123") is False  # invalid chars
        assert await validate_tenant_code("") is False  # empty


class TestAsyncFileValidator:
    """Test AsyncFileValidator class"""

    @pytest.mark.asyncio
    async def test_validate_file_valid(self):
        """Test valid file validation"""
        is_valid, errors = await AsyncFileValidator.validate_file(
            filename="test.pdf",
            file_size=1024
        )
        assert is_valid is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_file_invalid_size(self):
        """Test file validation with invalid size"""
        is_valid, errors = await AsyncFileValidator.validate_file(
            filename="test.pdf",
            file_size=settings.max_file_size + 1
        )
        assert is_valid is False
        assert len(errors) > 0
        assert "exceeds maximum allowed" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension"""
        is_valid, errors = await AsyncFileValidator.validate_file(
            filename="test.exe",
            file_size=1024
        )
        assert is_valid is False
        assert len(errors) > 0
        assert "File extension not allowed" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_zip_file(self):
        """Test zip file validation"""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            with zipfile.ZipFile(tmp_zip.name, 'w') as zf:
                zf.writestr('test.txt', 'content')
            
            is_valid, errors = await AsyncFileValidator.validate_file(
                filename="test.zip",
                file_size=1024,
                temp_file_path=tmp_zip.name
            )
            assert is_valid is True
            assert len(errors) == 0
            
            os.unlink(tmp_zip.name)
