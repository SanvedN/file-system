from shared.cache import init_redis, cache_set, cache_get, cache_delete

import pytest


@pytest.mark.asyncio
async def test_cache_set_get_delete():
    await init_redis()

    key = "test-key"
    value = "test-value"

    # Set value
    await cache_set(key, value, ex=10)

    # Get value and assert
    retrieved = await cache_get(key)
    assert retrieved == value

    # Delete value
    await cache_delete(key)

    # Ensure value is gone
    retrieved = await cache_get(key)
    assert retrieved is None
