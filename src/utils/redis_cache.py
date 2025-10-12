"""
Redis-based distributed cache for multi-tenant scalability
Shared across all web instances for consistent caching
"""

import os
import json
import datetime, decimal, uuid
import redis
import logging
from typing import Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)

# Global Redis client
_redis_client = None

def get_redis_client():
    """Get or create Redis client (lazy initialization)"""
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL')
        
        if not redis_url:
            logger.warning("⚠️ REDIS_URL not set - falling back to in-process cache")
            return None
        
        try:
            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,  # Automatically decode bytes to strings
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            _redis_client.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            _redis_client = None
    
    return _redis_client

def redis_cache_get(key: str) -> Optional[Any]:
    """
    Get value from Redis cache
    Returns None if not found or Redis unavailable
    """
    try:
        client = get_redis_client()
        if not client:
            return None
        
        value = client.get(key)
        if value:
            # Deserialize JSON
            return json.loads(value)
        return None
        
    except Exception as e:
        logger.warning(f"Redis GET error for key {key}: {e}")
        return None

def _safe_json_default(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        # Always ISO 8601 in UTC if tz-aware
        if isinstance(o, datetime.datetime) and o.tzinfo:
            return o.astimezone(datetime.timezone.utc).isoformat()
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, uuid.UUID):
        return str(o)
    # Fallback: string repr to avoid hard failures
    return str(o)

def redis_cache_set(key: str, value: Any, ttl: int = 3600):
    """
    Set value in Redis cache with TTL
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Time to live in seconds (default 1 hour)
    """
    try:
        client = get_redis_client()
        if not client:
            return False
        
        # Serialize to JSON (tolerant of datetime/Decimal/UUID)
        serialized = json.dumps(value, default=_safe_json_default, ensure_ascii=False)
        client.setex(key, ttl, serialized)
        return True
        
    except Exception as e:
        logger.warning(f"Redis SET error for key {key}: {e}")
        return False

def redis_cache_delete(key: str):
    """Delete key from Redis cache (for invalidation)"""
    try:
        client = get_redis_client()
        if not client:
            return False
        
        client.delete(key)
        return True
        
    except Exception as e:
        logger.warning(f"Redis DELETE error for key {key}: {e}")
        return False

def redis_cache_delete_pattern(pattern: str):
    """
    Delete all keys matching a pattern (for bulk invalidation)
    
    Args:
        pattern: Redis key pattern (e.g., "branding:*")
    """
    try:
        client = get_redis_client()
        if not client:
            return 0
        
        # Use SCAN for safe pattern deletion
        deleted = 0
        for key in client.scan_iter(match=pattern, count=100):
            client.delete(key)
            deleted += 1
        
        logger.info(f"🗑️ Deleted {deleted} Redis keys matching pattern: {pattern}")
        return deleted
        
    except Exception as e:
        logger.warning(f"Redis DELETE PATTERN error for {pattern}: {e}")
        return 0

def cached(key_prefix: str, ttl: int = 3600):
    """
    Decorator for function result caching in Redis
    
    Usage:
        @cached("tenant", ttl=3600)
        def get_tenant_data(subdomain):
            # ... query DB ...
            return data
    
    The cache key will be: key_prefix:function_arg
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and first argument
            if args:
                cache_key = f"{key_prefix}:{args[0]}"
            else:
                cache_key = f"{key_prefix}:{func.__name__}"
            
            # Try Redis cache first
            cached_value = redis_cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"✅ Redis cache HIT: {cache_key}")
                return cached_value
            
            # Cache miss - call function
            logger.debug(f"❌ Redis cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            
            # Store in Redis (non-blocking - don't fail if Redis is down)
            if result is not None:
                redis_cache_set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# Helper functions for common cache operations
def invalidate_tenant_cache(subdomain: str):
    """Invalidate all cache for a specific tenant"""
    redis_cache_delete(f"tenant:{subdomain}")
    redis_cache_delete(f"branding:{subdomain}")
    logger.info(f"🗑️ Invalidated cache for tenant: {subdomain}")

def invalidate_all_branding_cache():
    """Invalidate all branding cache (e.g., after global settings change)"""
    deleted = redis_cache_delete_pattern("branding:*")
    logger.info(f"🗑️ Invalidated {deleted} branding cache entries")

