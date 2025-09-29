"""
Database migration utilities and helpers
Provides functions for managing database migrations with Alembic
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.shared.db import get_async_engine
from src.shared.config import Settings


class MigrationManager:
    """Manages database migrations using Alembic"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.project_root = Path(__file__).parent.parent.parent
        self.alembic_ini_path = self.project_root / "alembic.ini"
        self.alembic_versions_path = self.project_root / "alembic" / "versions"
    
    def _run_alembic_command(self, command: str, *args: str) -> subprocess.CompletedProcess:
        """Run an Alembic command"""
        cmd = [sys.executable, "-m", "alembic", command] + list(args)
        
        env = os.environ.copy()
        env["DATABASE_URL"] = self.settings.database_url
        
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
    
    async def get_current_revision(self) -> Optional[str]:
        """Get the current database revision"""
        try:
            result = self._run_alembic_command("current")
            if result.stdout.strip():
                # Extract revision from output like "0001 (head)"
                return result.stdout.strip().split()[0]
            return None
        except subprocess.CalledProcessError:
            return None
    
    async def get_head_revision(self) -> Optional[str]:
        """Get the head revision"""
        try:
            result = self._run_alembic_command("heads")
            if result.stdout.strip():
                return result.stdout.strip()
            return None
        except subprocess.CalledProcessError:
            return None
    
    async def is_database_initialized(self) -> bool:
        """Check if the database has been initialized with migrations"""
        try:
            current = await self.get_current_revision()
            return current is not None
        except Exception:
            return False
    
    async def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get migration history"""
        try:
            result = self._run_alembic_command("history", "--verbose")
            migrations = []
            
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('Rev: '):
                    parts = line.split(' -> ')
                    if len(parts) >= 2:
                        revision = parts[0].strip()
                        description = parts[1].strip() if len(parts) > 1 else ""
                        migrations.append({
                            "revision": revision,
                            "description": description
                        })
            
            return migrations
        except subprocess.CalledProcessError:
            return []
    
    async def create_migration(
        self, 
        message: str, 
        autogenerate: bool = True,
        empty: bool = False
    ) -> str:
        """Create a new migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        revision_id = f"{timestamp}_{message.lower().replace(' ', '_')}"
        
        args = ["revision", "--rev-id", revision_id, "-m", message]
        
        if autogenerate and not empty:
            args.append("--autogenerate")
        elif empty:
            args.append("--empty")
        
        result = self._run_alembic_command(*args)
        
        # Extract the created revision file path
        for line in result.stdout.split('\n'):
            if 'Generating' in line and '.py' in line:
                return line.split()[-1]
        
        return revision_id
    
    async def upgrade_database(self, revision: str = "head") -> bool:
        """Upgrade database to a specific revision"""
        try:
            self._run_alembic_command("upgrade", revision)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Migration upgrade failed: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    async def downgrade_database(self, revision: str) -> bool:
        """Downgrade database to a specific revision"""
        try:
            self._run_alembic_command("downgrade", revision)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Migration downgrade failed: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    async def stamp_database(self, revision: str = "head") -> bool:
        """Stamp database with a revision without running migrations"""
        try:
            self._run_alembic_command("stamp", revision)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Migration stamp failed: {e}")
            return False
    
    async def check_migration_status(self) -> Dict[str, Any]:
        """Check the current migration status"""
        current = await self.get_current_revision()
        head = await self.get_head_revision()
        is_initialized = await self.is_database_initialized()
        
        return {
            "current_revision": current,
            "head_revision": head,
            "is_initialized": is_initialized,
            "is_up_to_date": current == head if current and head else False,
            "needs_migration": current != head if current and head else True
        }
    
    async def initialize_database(self) -> bool:
        """Initialize database with initial migration"""
        try:
            # Check if database is already initialized
            if await self.is_database_initialized():
                print("Database is already initialized")
                return True
            
            # Run initial migration
            success = await self.upgrade_database("head")
            if success:
                print("Database initialized successfully")
            return success
            
        except Exception as e:
            print(f"Database initialization failed: {e}")
            return False
    
    async def reset_database(self) -> bool:
        """Reset database by dropping all tables and re-running migrations"""
        try:
            # Downgrade to base
            await self.downgrade_database("base")
            
            # Upgrade to head
            success = await self.upgrade_database("head")
            if success:
                print("Database reset successfully")
            return success
            
        except Exception as e:
            print(f"Database reset failed: {e}")
            return False
    
    async def validate_migrations(self) -> bool:
        """Validate that all migrations can be applied"""
        try:
            # Get current revision
            current = await self.get_current_revision()
            if not current:
                return False
            
            # Try to upgrade to head
            result = self._run_alembic_command("check")
            return result.returncode == 0
            
        except subprocess.CalledProcessError:
            return False


# Global migration manager instance
migration_manager = MigrationManager()


async def get_migration_manager() -> MigrationManager:
    """Get the global migration manager instance"""
    return migration_manager


async def initialize_database_migrations() -> bool:
    """Initialize database with migrations"""
    manager = await get_migration_manager()
    return await manager.initialize_database()


async def upgrade_database_migrations(revision: str = "head") -> bool:
    """Upgrade database to latest or specific revision"""
    manager = await get_migration_manager()
    return await manager.upgrade_database(revision)


async def check_database_migration_status() -> Dict[str, Any]:
    """Check database migration status"""
    manager = await get_migration_manager()
    return await manager.check_migration_status()


async def create_database_migration(message: str, autogenerate: bool = True) -> str:
    """Create a new database migration"""
    manager = await get_migration_manager()
    return await manager.create_migration(message, autogenerate)


# Migration utilities for services
async def ensure_database_migrated() -> bool:
    """Ensure database is migrated to the latest version"""
    try:
        manager = await get_migration_manager()
        status = await manager.check_migration_status()
        
        if not status["is_initialized"]:
            print("Database not initialized, running initial migration...")
            return await manager.initialize_database()
        
        if status["needs_migration"]:
            print(f"Database needs migration from {status['current_revision']} to {status['head_revision']}")
            return await manager.upgrade_database("head")
        
        print("Database is up to date")
        return True
        
    except Exception as e:
        print(f"Migration check failed: {e}")
        return False


async def get_database_schema_version() -> Optional[str]:
    """Get the current database schema version"""
    try:
        manager = await get_migration_manager()
        return await manager.get_current_revision()
    except Exception:
        return None


# Export functions
__all__ = [
    "MigrationManager",
    "migration_manager",
    "get_migration_manager",
    "initialize_database_migrations",
    "upgrade_database_migrations",
    "check_database_migration_status",
    "create_database_migration",
    "ensure_database_migrated",
    "get_database_schema_version"
]
