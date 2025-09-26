import redis.asyncio as redis
import json
from typing import Any, Optional, Union
from .config import settings
import structlog

logger = structlog.get_logger()


class RedisClient:
    """Async Redis client for caching operations"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )
            # Test connection
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if not self.redis:
                return None
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional expiration"""
        try:
            if not self.redis:
                return False
            json_value = json.dumps(value, default=str)
            result = await self.redis.set(key, json_value, ex=expire)
            return bool(result)
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if not self.redis:
                return False
            result = await self.redis.delete(key)
            return bool(result)
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if not self.redis:
                return False
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error("Redis exists error", key=key, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        try:
            if not self.redis:
                return None
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error("Redis increment error", key=key, error=str(e))
            return None
    
    async def set_json(self, key: str, path: str, value: Any) -> bool:
        """Set JSON value at path"""
        try:
            if not self.redis:
                return False
            # For basic Redis, we'll simulate JSON path operations
            # In production, consider using RedisJSON module
            current = await self.get(key) or {}
            if path == "$":
                current = value
            else:
                # Simple path implementation for common cases
                keys = path.strip("$.").split(".")
                target = current
                for k in keys[:-1]:
                    target = target.setdefault(k, {})
                target[keys[-1]] = value
            
            return await self.set(key, current)
        except Exception as e:
            logger.error("Redis set_json error", key=key, path=path, error=str(e))
            return False
    
    async def get_json(self, key: str, path: str = "$") -> Optional[Any]:
        """Get JSON value at path"""
        try:
            if not self.redis:
                return None
            current = await self.get(key)
            if not current or path == "$":
                return current
            
            # Simple path implementation
            keys = path.strip("$.").split(".")
            target = current
            for k in keys:
                if isinstance(target, dict) and k in target:
                    target = target[k]
                else:
                    return None
            return target
        except Exception as e:
            logger.error("Redis get_json error", key=key, path=path, error=str(e))
            return None


# Global Redis client instance
redis_client = RedisClient()


# Cache key generators
def get_tenant_cache_key(tenant_code: str) -> str:
    """Generate cache key for tenant"""
    return f"tenant:{tenant_code}"


def get_file_cache_key(tenant_code: str, file_id: str) -> str:
    """Generate cache key for file metadata"""
    return f"file:{tenant_code}:{file_id}"


def get_file_list_cache_key(tenant_code: str, page: int = 1, limit: int = 10) -> str:
    """Generate cache key for file list"""
    return f"files:{tenant_code}:page:{page}:limit:{limit}"


def get_extraction_cache_key(file_id: str) -> str:
    """Generate cache key for extraction result"""
    return f"extraction:{file_id}"
