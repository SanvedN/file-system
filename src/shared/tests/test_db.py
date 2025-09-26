import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from unittest.mock import patch, AsyncMock

from ..db import Base, get_db, init_db, close_db, engine
from ..config import settings


class TestDatabase:
    """Test database functionality"""

    @pytest.fixture
    async def test_engine(self):
        """Create test database engine"""
        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield test_engine
        await test_engine.dispose()

    @pytest.mark.asyncio
    async def test_database_engine_creation(self):
        """Test database engine is created correctly"""
        assert engine is not None
        assert engine.url.drivername == "postgresql+asyncpg"

    @pytest.mark.asyncio
    async def test_get_db_session(self, test_engine):
        """Test database session dependency"""
        with patch('src.shared.db.engine', test_engine):
            with patch('src.shared.db.AsyncSessionLocal') as mock_session_local:
                mock_session = AsyncMock(spec=AsyncSession)
                mock_session_local.return_value.__aenter__.return_value = mock_session
                mock_session_local.return_value.__aexit__.return_value = None
                
                async for session in get_db():
                    assert session is not None
                    break
                
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_with_error(self, test_engine):
        """Test database session with error handling"""
        with patch('src.shared.db.engine', test_engine):
            with patch('src.shared.db.AsyncSessionLocal') as mock_session_local:
                mock_session = AsyncMock(spec=AsyncSession)
                mock_session.commit.side_effect = Exception("Database error")
                mock_session_local.return_value.__aenter__.return_value = mock_session
                mock_session_local.return_value.__aexit__.return_value = None
                
                with pytest.raises(Exception):
                    async for session in get_db():
                        break
                
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db(self, test_engine):
        """Test database initialization"""
        with patch('src.shared.db.engine', test_engine):
            # Mock the imports to avoid circular import issues
            with patch('src.shared.db.Tenant'), \
                 patch('src.shared.db.File'), \
                 patch('src.shared.db.ExtractionResult'):
                
                await init_db()
                # If no exception is raised, the test passes

    @pytest.mark.asyncio
    async def test_close_db(self):
        """Test database closure"""
        mock_engine = AsyncMock()
        with patch('src.shared.db.engine', mock_engine):
            await close_db()
            mock_engine.dispose.assert_called_once()


class TestBaseModel:
    """Test base database model"""

    def test_base_model_exists(self):
        """Test that Base model exists and is configured"""
        assert Base is not None
        assert hasattr(Base, 'metadata')
        assert hasattr(Base, 'registry')
