"""
Simple rate limiting for API endpoints.
Uses Redis to track request counts per user/tenant.
"""

import time
from typing import Optional
from fastapi import HTTPException, status
from shared.cache import get_redis_client
from shared.utils import setup_logger

logger = setup_logger()


async def check_rate_limit(
    key: str, 
    max_requests: int = 100, 
    window_seconds: int = 3600,
    redis=None
) -> bool:
    """
    Check if request is within rate limit.
    
    Args:
        key: Unique identifier for rate limiting (e.g., tenant_id, user_id)
        max_requests: Maximum requests allowed in the time window
        window_seconds: Time window in seconds (default: 1 hour)
        redis: Redis client (optional, will get from shared if not provided)
    
    Returns:
        True if request is allowed, False if rate limited
    
    Raises:
        HTTPException: If rate limit is exceeded
    """
    if not redis:
        try:
            redis = await get_redis_client()
        except Exception as e:
            logger.warning(f"Rate limiter: Redis unavailable, allowing request: {e}")
            return True
    
    try:
        # Create rate limit key with current time window
        current_window = int(time.time() // window_seconds)
        rate_key = f"rate_limit:{key}:{current_window}"
        
        # Get current count
        current_count = await redis.get(rate_key)
        current_count = int(current_count) if current_count else 0
        
        # Check if limit exceeded
        if current_count >= max_requests:
            logger.warning(f"Rate limit exceeded for {key}: {current_count}/{max_requests}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds."
            )
        
        # Increment counter
        await redis.incr(rate_key)
        await redis.expire(rate_key, window_seconds * 2)  # Keep for 2 windows to handle edge cases
        
        return True
        
    except HTTPException:
        # Re-raise rate limit exceptions
        raise
    except Exception as e:
        logger.warning(f"Rate limiter error for {key}, allowing request: {e}")
        return True


async def check_upload_rate_limit(tenant_id: str, redis=None) -> bool:
    """
    Check upload rate limit for a tenant.
    More restrictive than general API rate limiting.
    """
    return await check_rate_limit(
        key=f"upload:{tenant_id}",
        max_requests=50,
        window_seconds=3600,
        redis=redis
    )


async def check_embedding_rate_limit(tenant_id: str, redis=None) -> bool:
    """
    Check embedding generation rate limit for a tenant.
    Very restrictive since embeddings are resource-intensive.
    """
    return await check_rate_limit(
        key=f"embedding:{tenant_id}",
        max_requests=10,
        window_seconds=3600,
        redis=redis
    )
