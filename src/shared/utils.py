import asyncio
import aiofiles
import os
import zipfile
import magic
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import hashlib
import structlog
from .config import settings

logger = structlog.get_logger()


class FileValidationError(Exception):
    """Custom exception for file validation errors"""
    pass


class StorageError(Exception):
    """Custom exception for storage operation errors"""
    pass


async def validate_file_size(file_size: int) -> bool:
    """Validate file size against maximum allowed"""
    return file_size <= settings.max_file_size


async def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed extensions"""
    file_ext = Path(filename).suffix.lower()
    return file_ext in settings.allowed_extensions_list


async def get_file_mime_type(file_path: str) -> str:
    """Get MIME type of file using python-magic"""
    try:
        return magic.from_file(file_path, mime=True)
    except Exception as e:
        logger.error("Failed to get MIME type", file_path=file_path, error=str(e))
        return "application/octet-stream"


async def validate_zip_depth(file_path: str, max_depth: int = None) -> bool:
    """Validate zip file depth to prevent zip bombs"""
    if max_depth is None:
        max_depth = settings.max_zip_depth
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            for zip_info in zip_file.filelist:
                # Count directory separators to determine depth
                depth = zip_info.filename.count('/') + zip_info.filename.count('\\')
                if depth > max_depth:
                    return False
        return True
    except zipfile.BadZipFile:
        logger.error("Invalid zip file", file_path=file_path)
        return False
    except Exception as e:
        logger.error("Error validating zip depth", file_path=file_path, error=str(e))
        return False


async def generate_file_hash(file_path: str) -> str:
    """Generate SHA256 hash of file content"""
    hash_sha256 = hashlib.sha256()
    try:
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error("Failed to generate file hash", file_path=file_path, error=str(e))
        raise StorageError(f"Failed to generate file hash: {str(e)}")


def generate_storage_path(tenant_code: str, upload_date: datetime = None) -> str:
    """Generate storage path following the format: storage_base_path/<tenant_code>/YYYY-MM/"""
    if upload_date is None:
        upload_date = datetime.utcnow()
    
    year_month = upload_date.strftime("%Y-%m")
    return os.path.join(settings.storage_base_path, tenant_code, year_month)


async def ensure_directory_exists(directory_path: str) -> bool:
    """Ensure directory exists, create if it doesn't"""
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error("Failed to create directory", directory_path=directory_path, error=str(e))
        return False


async def save_uploaded_file(
    file_content: bytes, 
    file_path: str,
    chunk_size: int = 8192
) -> bool:
    """Save uploaded file content to disk asynchronously"""
    try:
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if not await ensure_directory_exists(directory):
            raise StorageError(f"Failed to create directory: {directory}")
        
        async with aiofiles.open(file_path, 'wb') as f:
            # Write in chunks for memory efficiency
            for i in range(0, len(file_content), chunk_size):
                chunk = file_content[i:i + chunk_size]
                await f.write(chunk)
        
        logger.info("File saved successfully", file_path=file_path)
        return True
    except Exception as e:
        logger.error("Failed to save file", file_path=file_path, error=str(e))
        raise StorageError(f"Failed to save file: {str(e)}")


async def delete_file(file_path: str) -> bool:
    """Delete file from disk"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("File deleted successfully", file_path=file_path)
            return True
        else:
            logger.warning("File not found for deletion", file_path=file_path)
            return False
    except Exception as e:
        logger.error("Failed to delete file", file_path=file_path, error=str(e))
        return False


async def get_file_stats(file_path: str) -> Optional[Dict[str, Any]]:
    """Get file statistics"""
    try:
        if not os.path.exists(file_path):
            return None
        
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "mode": stat.st_mode,
        }
    except Exception as e:
        logger.error("Failed to get file stats", file_path=file_path, error=str(e))
        return None


async def cleanup_empty_directories(base_path: str, tenant_code: str):
    """Clean up empty directories for a tenant"""
    try:
        tenant_path = os.path.join(base_path, tenant_code)
        if not os.path.exists(tenant_path):
            return
        
        # Walk through directories bottom-up to remove empty ones
        for root, dirs, files in os.walk(tenant_path, topdown=False):
            if not dirs and not files:
                try:
                    os.rmdir(root)
                    logger.info("Removed empty directory", directory=root)
                except OSError:
                    pass  # Directory not empty or permission error
    except Exception as e:
        logger.error("Failed to cleanup directories", tenant_code=tenant_code, error=str(e))


def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename using timestamp and hash"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_hash = hashlib.md5(original_filename.encode()).hexdigest()[:8]
    name, ext = os.path.splitext(original_filename)
    return f"{name}_{timestamp}_{file_hash}{ext}"


async def validate_tenant_code(tenant_code: str) -> bool:
    """Validate tenant code format"""
    # Tenant code should be alphanumeric and between 3-50 characters
    if not tenant_code or len(tenant_code) < 3 or len(tenant_code) > 50:
        return False
    return tenant_code.replace("_", "").replace("-", "").isalnum()


class AsyncFileValidator:
    """Async file validator with comprehensive checks"""
    
    @staticmethod
    async def validate_file(
        filename: str,
        file_size: int,
        file_content: Optional[bytes] = None,
        temp_file_path: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive file validation
        Returns (is_valid, error_messages)
        """
        errors = []
        
        # Validate file size
        if not await validate_file_size(file_size):
            errors.append(f"File size {file_size} exceeds maximum allowed {settings.max_file_size}")
        
        # Validate file extension
        if not await validate_file_extension(filename):
            errors.append(f"File extension not allowed. Allowed: {settings.allowed_extensions}")
        
        # If we have file content or path, do additional validation
        if temp_file_path and os.path.exists(temp_file_path):
            # Validate MIME type
            mime_type = await get_file_mime_type(temp_file_path)
            logger.info("File MIME type detected", filename=filename, mime_type=mime_type)
            
            # If it's a zip file, validate depth
            if filename.lower().endswith('.zip'):
                if not await validate_zip_depth(temp_file_path):
                    errors.append(f"Zip file exceeds maximum depth of {settings.max_zip_depth}")
        
        return len(errors) == 0, errors
