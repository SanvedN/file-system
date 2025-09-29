"""
Tests for database migration functionality
Tests: Migration management, status checking, and database operations
"""

import pytest
import pytest_asyncio
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.shared.migrations import (
    MigrationManager,
    get_migration_manager,
    initialize_database_migrations,
    upgrade_database_migrations,
    check_database_migration_status,
    create_database_migration,
    ensure_database_migrated,
    get_database_schema_version
)
from src.shared.config import Settings


@pytest_asyncio.fixture
async def test_settings():
    """Test configuration settings"""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        environment="testing"
    )


@pytest_asyncio.fixture
async def migration_manager(test_settings):
    """Create migration manager for testing"""
    return MigrationManager(test_settings)


@pytest.mark.unit
class TestMigrationManager:
    """Test MigrationManager functionality"""
    
    @pytest.mark.asyncio
    async def test_migration_manager_initialization(self, test_settings):
        """Test migration manager initialization"""
        manager = MigrationManager(test_settings)
        
        assert manager.settings == test_settings
        assert manager.project_root.exists()
        assert manager.alembic_ini_path.exists()
        assert manager.alembic_versions_path.exists()
    
    @pytest.mark.asyncio
    async def test_get_current_revision(self, migration_manager):
        """Test getting current revision"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(stdout="0001 (head)")
            
            revision = await migration_manager.get_current_revision()
            
            assert revision == "0001"
            mock_run.assert_called_once_with("current")
    
    @pytest.mark.asyncio
    async def test_get_current_revision_none(self, migration_manager):
        """Test getting current revision when none exists"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            
            revision = await migration_manager.get_current_revision()
            
            assert revision is None
    
    @pytest.mark.asyncio
    async def test_get_head_revision(self, migration_manager):
        """Test getting head revision"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(stdout="0001")
            
            revision = await migration_manager.get_head_revision()
            
            assert revision == "0001"
            mock_run.assert_called_once_with("heads")
    
    @pytest.mark.asyncio
    async def test_is_database_initialized_true(self, migration_manager):
        """Test database initialization check when initialized"""
        with patch.object(migration_manager, 'get_current_revision') as mock_get:
            mock_get.return_value = "0001"
            
            is_initialized = await migration_manager.is_database_initialized()
            
            assert is_initialized is True
    
    @pytest.mark.asyncio
    async def test_is_database_initialized_false(self, migration_manager):
        """Test database initialization check when not initialized"""
        with patch.object(migration_manager, 'get_current_revision') as mock_get:
            mock_get.return_value = None
            
            is_initialized = await migration_manager.is_database_initialized()
            
            assert is_initialized is False
    
    @pytest.mark.asyncio
    async def test_get_migration_history(self, migration_manager):
        """Test getting migration history"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_output = """
Rev: 0001 -> Initial migration (head)
Rev: 0002 -> Add new table
            """
            mock_run.return_value = MagicMock(stdout=mock_output)
            
            history = await migration_manager.get_migration_history()
            
            assert len(history) == 2
            assert history[0]["revision"] == "0001"
            assert "Initial migration" in history[0]["description"]
            assert history[1]["revision"] == "0002"
            assert "Add new table" in history[1]["description"]
    
    @pytest.mark.asyncio
    async def test_create_migration_autogenerate(self, migration_manager):
        """Test creating migration with autogenerate"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(stdout="Generating /path/to/migration.py")
            
            result = await migration_manager.create_migration("Test migration")
            
            assert "migration.py" in result
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "revision" in args
            assert "--autogenerate" in args
            assert "Test migration" in args
    
    @pytest.mark.asyncio
    async def test_create_migration_empty(self, migration_manager):
        """Test creating empty migration"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(stdout="Generating /path/to/migration.py")
            
            result = await migration_manager.create_migration("Empty migration", empty=True)
            
            assert "migration.py" in result
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "--empty" in args
            assert "--autogenerate" not in args
    
    @pytest.mark.asyncio
    async def test_upgrade_database_success(self, migration_manager):
        """Test successful database upgrade"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            success = await migration_manager.upgrade_database("head")
            
            assert success is True
            mock_run.assert_called_once_with("upgrade", "head")
    
    @pytest.mark.asyncio
    async def test_upgrade_database_failure(self, migration_manager):
        """Test failed database upgrade"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "alembic", stderr="Error")
            
            success = await migration_manager.upgrade_database("head")
            
            assert success is False
    
    @pytest.mark.asyncio
    async def test_downgrade_database_success(self, migration_manager):
        """Test successful database downgrade"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            success = await migration_manager.downgrade_database("0001")
            
            assert success is True
            mock_run.assert_called_once_with("downgrade", "0001")
    
    @pytest.mark.asyncio
    async def test_stamp_database_success(self, migration_manager):
        """Test successful database stamping"""
        with patch.object(migration_manager, '_run_alembic_command') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            success = await migration_manager.stamp_database("head")
            
            assert success is True
            mock_run.assert_called_once_with("stamp", "head")
    
    @pytest.mark.asyncio
    async def test_check_migration_status(self, migration_manager):
        """Test migration status checking"""
        with patch.object(migration_manager, 'get_current_revision') as mock_current, \
             patch.object(migration_manager, 'get_head_revision') as mock_head, \
             patch.object(migration_manager, 'is_database_initialized') as mock_init:
            
            mock_current.return_value = "0001"
            mock_head.return_value = "0001"
            mock_init.return_value = True
            
            status = await migration_manager.check_migration_status()
            
            assert status["current_revision"] == "0001"
            assert status["head_revision"] == "0001"
            assert status["is_initialized"] is True
            assert status["is_up_to_date"] is True
            assert status["needs_migration"] is False
    
    @pytest.mark.asyncio
    async def test_check_migration_status_needs_update(self, migration_manager):
        """Test migration status when update is needed"""
        with patch.object(migration_manager, 'get_current_revision') as mock_current, \
             patch.object(migration_manager, 'get_head_revision') as mock_head, \
             patch.object(migration_manager, 'is_database_initialized') as mock_init:
            
            mock_current.return_value = "0001"
            mock_head.return_value = "0002"
            mock_init.return_value = True
            
            status = await migration_manager.check_migration_status()
            
            assert status["is_up_to_date"] is False
            assert status["needs_migration"] is True
    
    @pytest.mark.asyncio
    async def test_initialize_database_success(self, migration_manager):
        """Test successful database initialization"""
        with patch.object(migration_manager, 'is_database_initialized') as mock_init, \
             patch.object(migration_manager, 'upgrade_database') as mock_upgrade:
            
            mock_init.return_value = False
            mock_upgrade.return_value = True
            
            success = await migration_manager.initialize_database()
            
            assert success is True
            mock_upgrade.assert_called_once_with("head")
    
    @pytest.mark.asyncio
    async def test_initialize_database_already_initialized(self, migration_manager):
        """Test database initialization when already initialized"""
        with patch.object(migration_manager, 'is_database_initialized') as mock_init, \
             patch.object(migration_manager, 'upgrade_database') as mock_upgrade:
            
            mock_init.return_value = True
            
            success = await migration_manager.initialize_database()
            
            assert success is True
            mock_upgrade.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reset_database_success(self, migration_manager):
        """Test successful database reset"""
        with patch.object(migration_manager, 'downgrade_database') as mock_downgrade, \
             patch.object(migration_manager, 'upgrade_database') as mock_upgrade:
            
            mock_downgrade.return_value = True
            mock_upgrade.return_value = True
            
            success = await migration_manager.reset_database()
            
            assert success is True
            mock_downgrade.assert_called_once_with("base")
            mock_upgrade.assert_called_once_with("head")
    
    @pytest.mark.asyncio
    async def test_validate_migrations_success(self, migration_manager):
        """Test successful migration validation"""
        with patch.object(migration_manager, 'get_current_revision') as mock_current, \
             patch.object(migration_manager, '_run_alembic_command') as mock_run:
            
            mock_current.return_value = "0001"
            mock_run.return_value = MagicMock(returncode=0)
            
            is_valid = await migration_manager.validate_migrations()
            
            assert is_valid is True
            mock_run.assert_called_once_with("check")


@pytest.mark.unit
class TestMigrationFunctions:
    """Test migration utility functions"""
    
    @pytest.mark.asyncio
    async def test_get_migration_manager(self):
        """Test getting migration manager instance"""
        manager = await get_migration_manager()
        
        assert isinstance(manager, MigrationManager)
    
    @pytest.mark.asyncio
    async def test_initialize_database_migrations(self):
        """Test initialize database migrations function"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.initialize_database.return_value = True
            
            success = await initialize_database_migrations()
            
            assert success is True
            mock_manager.initialize_database.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upgrade_database_migrations(self):
        """Test upgrade database migrations function"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.upgrade_database.return_value = True
            
            success = await upgrade_database_migrations("head")
            
            assert success is True
            mock_manager.upgrade_database.assert_called_once_with("head")
    
    @pytest.mark.asyncio
    async def test_check_database_migration_status(self):
        """Test check database migration status function"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            expected_status = {
                "current_revision": "0001",
                "head_revision": "0001",
                "is_initialized": True,
                "is_up_to_date": True,
                "needs_migration": False
            }
            mock_manager.check_migration_status.return_value = expected_status
            
            status = await check_database_migration_status()
            
            assert status == expected_status
            mock_manager.check_migration_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_database_migration(self):
        """Test create database migration function"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.create_migration.return_value = "0001_test_migration.py"
            
            result = await create_database_migration("Test migration")
            
            assert result == "0001_test_migration.py"
            mock_manager.create_migration.assert_called_once_with("Test migration", True)
    
    @pytest.mark.asyncio
    async def test_ensure_database_migrated_initialized(self):
        """Test ensure database migrated when already initialized"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.check_migration_status.return_value = {
                "is_initialized": True,
                "needs_migration": False,
                "current_revision": "0001",
                "head_revision": "0001"
            }
            
            success = await ensure_database_migrated()
            
            assert success is True
            mock_manager.check_migration_status.assert_called_once()
            mock_manager.initialize_database.assert_not_called()
            mock_manager.upgrade_database.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ensure_database_migrated_not_initialized(self):
        """Test ensure database migrated when not initialized"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.check_migration_status.return_value = {
                "is_initialized": False,
                "needs_migration": True,
                "current_revision": None,
                "head_revision": "0001"
            }
            mock_manager.initialize_database.return_value = True
            
            success = await ensure_database_migrated()
            
            assert success is True
            mock_manager.initialize_database.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_database_migrated_needs_update(self):
        """Test ensure database migrated when update is needed"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.check_migration_status.return_value = {
                "is_initialized": True,
                "needs_migration": True,
                "current_revision": "0001",
                "head_revision": "0002"
            }
            mock_manager.upgrade_database.return_value = True
            
            success = await ensure_database_migrated()
            
            assert success is True
            mock_manager.upgrade_database.assert_called_once_with("head")
    
    @pytest.mark.asyncio
    async def test_get_database_schema_version(self):
        """Test get database schema version function"""
        with patch('src.shared.migrations.migration_manager') as mock_manager:
            mock_manager.get_current_revision.return_value = "0001"
            
            version = await get_database_schema_version()
            
            assert version == "0001"
            mock_manager.get_current_revision.assert_called_once()


@pytest.mark.integration
class TestMigrationIntegration:
    """Test migration integration with database"""
    
    @pytest.mark.asyncio
    async def test_migration_with_real_database(self, test_settings):
        """Test migration with real database connection"""
        # This test would require a real database connection
        # For now, we'll mock the database operations
        
        with patch('src.shared.migrations.MigrationManager._run_alembic_command') as mock_run:
            # Mock successful migration commands
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            manager = MigrationManager(test_settings)
            
            # Test initialization
            success = await manager.initialize_database()
            assert success is True
            
            # Test status check
            with patch.object(manager, 'get_current_revision') as mock_current, \
                 patch.object(manager, 'get_head_revision') as mock_head, \
                 patch.object(manager, 'is_database_initialized') as mock_init:
                
                mock_current.return_value = "0001"
                mock_head.return_value = "0001"
                mock_init.return_value = True
                
                status = await manager.check_migration_status()
                assert status["is_up_to_date"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
