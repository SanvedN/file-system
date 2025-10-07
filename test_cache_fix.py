#!/usr/bin/env python3
"""
Simple test script to verify cache invalidation is working.
Run this after updating a file to see if the cache is properly invalidated.
"""

import asyncio
import json
from src.shared.cache import get_redis_client, redis_key_for_files_list, redis_key_for_file_detail

async def test_cache_status(tenant_id: str, file_id: str):
    """Check cache status for a tenant and file"""
    try:
        redis = await get_redis_client()
        
        # Check files list cache
        files_list_key = redis_key_for_files_list(tenant_id)
        files_list_cached = await redis.get(files_list_key)
        
        # Check file detail cache
        file_detail_key = redis_key_for_file_detail(tenant_id, file_id)
        file_detail_cached = await redis.get(file_detail_key)
        
        print(f"Cache Status for Tenant: {tenant_id}")
        print(f"Files List Cache: {'HIT' if files_list_cached else 'MISS'}")
        print(f"File Detail Cache: {'HIT' if file_detail_cached else 'MISS'}")
        
        if files_list_cached:
            files = json.loads(files_list_cached)
            print(f"Files in cache: {len(files)}")
            for f in files:
                if f.get('file_id') == file_id:
                    print(f"Updated file in cache: {f}")
                    break
        
    except Exception as e:
        print(f"Error checking cache: {e}")

if __name__ == "__main__":
    # Replace with your actual tenant_id and file_id
    tenant_id = "824d4dd1-a487-4cf5-bea9-c7fa1b0df823"
    file_id = "CF_FR_91256078d123"
    
    asyncio.run(test_cache_status(tenant_id, file_id))
