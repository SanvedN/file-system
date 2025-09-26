import pytest
import json
from unittest.mock import AsyncMock, patch
import redis.asyncio as redis

from ..cache import (
    RedisClient,
    redis_client,
    get_tenant_cache_key,
    get_file_cache_key,
    get_file_list_cache_key,
    get_extraction_cache_key
)


class TestRedisClient:
    """Test Redis client functionality"""

    @pytest.fixture
    def redis_client_instance(self):
        """Create Redis client instance for testing"""
        return RedisClient()

    @pytest.mark.asyncio
    async def test_redis_connect_success(self, redis_client_instance):
        """Test successful Redis connection"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            mock_redis.ping.return_value = True
            
            await redis_client_instance.connect()
            
            assert redis_client_instance.redis is not None
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_connect_failure(self, redis_client_instance):
        """Test Redis connection failure"""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
            
            with pytest.raises(redis.ConnectionError):
                await redis_client_instance.connect()

    @pytest.mark.asyncio
    async def test_redis_disconnect(self, redis_client_instance):
        """Test Redis disconnection"""
        mock_redis = AsyncMock()
        redis_client_instance.redis = mock_redis
        
        await redis_client_instance.disconnect()
        
        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_value_success(self, redis_client_instance):
        """Test getting value from cache"""
        mock_redis = AsyncMock()
        test_data = {"key": "value"}
        mock_redis.get.return_value = json.dumps(test_data)
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.get("test_key")
        
        assert result == test_data
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_value_not_found(self, redis_client_instance):
        """Test getting non-existent value from cache"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.get("test_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_value_error(self, redis_client_instance):
        """Test getting value with Redis error"""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis.RedisError("Redis error")
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.get("test_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_set_value_success(self, redis_client_instance):
        """Test setting value in cache"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        redis_client_instance.redis = mock_redis
        
        test_data = {"key": "value"}
        result = await redis_client_instance.set("test_key", test_data)
        
        assert result is True
        mock_redis.set.assert_called_once_with(
            "test_key", 
            json.dumps(test_data, default=str), 
            ex=None
        )

    @pytest.mark.asyncio
    async def test_set_value_with_expiration(self, redis_client_instance):
        """Test setting value with expiration"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        redis_client_instance.redis = mock_redis
        
        test_data = {"key": "value"}
        result = await redis_client_instance.set("test_key", test_data, expire=3600)
        
        assert result is True
        mock_redis.set.assert_called_once_with(
            "test_key", 
            json.dumps(test_data, default=str), 
            ex=3600
        )

    @pytest.mark.asyncio
    async def test_set_value_no_redis(self, redis_client_instance):
        """Test setting value when Redis is not connected"""
        redis_client_instance.redis = None
        
        result = await redis_client_instance.set("test_key", {"key": "value"})
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_value_success(self, redis_client_instance):
        """Test deleting value from cache"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.delete("test_key")
        
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_value_not_found(self, redis_client_instance):
        """Test deleting non-existent value"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 0
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.delete("test_key")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_value_true(self, redis_client_instance):
        """Test checking if key exists (true)"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.exists("test_key")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_value_false(self, redis_client_instance):
        """Test checking if key exists (false)"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.exists("test_key")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_increment_value(self, redis_client_instance):
        """Test incrementing a counter"""
        mock_redis = AsyncMock()
        mock_redis.incrby.return_value = 5
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.increment("counter", 2)
        
        assert result == 5
        mock_redis.incrby.assert_called_once_with("counter", 2)

    @pytest.mark.asyncio
    async def test_set_json_root_path(self, redis_client_instance):
        """Test setting JSON value at root path"""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        redis_client_instance.redis = mock_redis
        
        test_data = {"key": "value"}
        result = await redis_client_instance.set_json("test_key", "$", test_data)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_set_json_nested_path(self, redis_client_instance):
        """Test setting JSON value at nested path"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"existing": "data"})
        mock_redis.set.return_value = True
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.set_json("test_key", "$.new_field", "new_value")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_get_json_root_path(self, redis_client_instance):
        """Test getting JSON value at root path"""
        mock_redis = AsyncMock()
        test_data = {"key": "value"}
        mock_redis.get.return_value = json.dumps(test_data)
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.get_json("test_key", "$")
        
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_json_nested_path(self, redis_client_instance):
        """Test getting JSON value at nested path"""
        mock_redis = AsyncMock()
        test_data = {"nested": {"key": "value"}}
        mock_redis.get.return_value = json.dumps(test_data)
        redis_client_instance.redis = mock_redis
        
        result = await redis_client_instance.get_json("test_key", "$.nested.key")
        
        assert result == "value"


class TestCacheKeyGenerators:
    """Test cache key generation functions"""

    def test_get_tenant_cache_key(self):
        """Test tenant cache key generation"""
        key = get_tenant_cache_key("test_tenant")
        assert key == "tenant:test_tenant"

    def test_get_file_cache_key(self):
        """Test file cache key generation"""
        key = get_file_cache_key("test_tenant", "file_123")
        assert key == "file:test_tenant:file_123"

    def test_get_file_list_cache_key(self):
        """Test file list cache key generation"""
        key = get_file_list_cache_key("test_tenant", page=2, limit=20)
        assert key == "files:test_tenant:page:2:limit:20"

    def test_get_file_list_cache_key_defaults(self):
        """Test file list cache key with defaults"""
        key = get_file_list_cache_key("test_tenant")
        assert key == "files:test_tenant:page:1:limit:10"

    def test_get_extraction_cache_key(self):
        """Test extraction cache key generation"""
        key = get_extraction_cache_key("file_123")
        assert key == "extraction:file_123"
