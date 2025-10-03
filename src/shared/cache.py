import json
import os
import redis.asyncio as redis
from redis.exceptions import RedisError
from urllib.parse import urlparse
from shared.config import settings

REDIS_URL = settings.file_repo_redis_url

_redis_client: redis.Redis = None


async def init_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL, decode_responses=True  # Optional: makes string handling easier
        )


async def get_redis_client() -> redis.Redis:
    if _redis_client is None:
        await init_redis()
    return _redis_client


async def cache_set(key: str, value: str, ex: int = None):
    try:
        client = await get_redis_client()
        await client.set(key, value, ex=ex)
    except RedisError as e:
        print(f"Redis SET error: {e}")


async def cache_get(key: str):
    try:
        client = await get_redis_client()
        return await client.get(key)
    except RedisError as e:
        print(f"Redis GET error: {e}")
        return None


async def cache_delete(key: str):
    try:
        client = await get_redis_client()
        await client.delete(key)
    except RedisError as e:
        print(f"Redis DELETE error: {e}")


# FastAPI dependency
async def get_redis():
    return await get_redis_client()


def redis_key_for_tenant(code: str) -> str:
    return f"tenant:cfg:{code}"


async def cache_set_tenant(
    redis: redis.Redis, code: str, cfg: dict, ttl_seconds: int = 3600
) -> None:
    await redis.set(redis_key_for_tenant(code), json.dumps(cfg), ex=ttl_seconds)


async def cache_get_tenant(redis: redis.Redis, code: str) -> dict | None:
    v = await redis.get(redis_key_for_tenant(code))
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


async def cache_delete_tenant(redis: redis.Redis, code: str) -> None:
    await redis.delete(redis_key_for_tenant(code))
