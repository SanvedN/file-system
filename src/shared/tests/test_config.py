import pytest
import os
from unittest.mock import patch
from ..config import Settings


class TestSettings:
    """Test configuration settings"""

    def test_default_settings(self):
        """Test default configuration values"""
        settings = Settings()
        assert settings.file_service_port == 8001
        assert settings.extraction_service_port == 8002
        assert settings.api_gateway_port == 8000
        assert settings.max_file_size == 104857600  # 100MB
        assert settings.max_zip_depth == 3
        assert settings.log_level == "INFO"
        assert settings.debug is True

    def test_allowed_extensions_list(self):
        """Test allowed extensions parsing"""
        settings = Settings()
        extensions = settings.allowed_extensions_list
        assert ".txt" in extensions
        assert ".pdf" in extensions
        assert ".zip" in extensions
        assert len(extensions) > 5

    @patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost:5432/test_db',
        'REDIS_URL': 'redis://localhost:6379/1',
        'STORAGE_BASE_PATH': '/test/storage',
        'MAX_FILE_SIZE': '52428800',  # 50MB
        'FILE_SERVICE_PORT': '9001'
    })
    def test_environment_override(self):
        """Test environment variable overrides"""
        settings = Settings()
        assert settings.database_url == 'postgresql+asyncpg://test:test@localhost:5432/test_db'
        assert settings.redis_url == 'redis://localhost:6379/1'
        assert settings.storage_base_path == '/test/storage'
        assert settings.max_file_size == 52428800
        assert settings.file_service_port == 9001

    def test_custom_extensions(self):
        """Test custom allowed extensions"""
        with patch.dict(os.environ, {'ALLOWED_EXTENSIONS': '.doc,.docx,.txt'}):
            settings = Settings()
            extensions = settings.allowed_extensions_list
            assert extensions == ['.doc', '.docx', '.txt']
