"""
Per-tenant rate limiting with Redis token buckets
"""

import time
import logging
import redis
import os
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, jsonify, g, current_app

logger = logging.getLogger(__name__)

class TokenBucketRateLimiter:
    """Redis-based token bucket rate limiter per tenant"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()  # Test connection
            except Exception as e:
                logger.warning(f"Redis rate limiter unavailable: {e}")
    
    def _get_tenant_key(self, tenant: str, endpoint: str) -> str:
        """Generate Redis key for tenant + endpoint rate limiting"""
        return f"rate_limit:{tenant}:{endpoint}"
    
    def is_allowed(self, tenant: str, endpoint: str, 
                   max_tokens: int = 60, 
                   refill_rate: float = 1.0, 
                   window_seconds: int = 60) -> Dict[str, Any]:
        """
        Check if request is allowed for tenant + endpoint
        
        Args:
            tenant: Tenant identifier
            endpoint: API endpoint identifier
            max_tokens: Maximum tokens in bucket
            refill_rate: Tokens per second refill rate
            window_seconds: Time window for rate limiting
            
        Returns:
            Dict with 'allowed', 'remaining', 'reset_time'
        """
        if not self.redis_client:
            # No Redis = allow all requests
            return {
                'allowed': True,
                'remaining': max_tokens,
                'reset_time': int(time.time()) + window_seconds,
                'reason': 'no_redis'
            }
        
        try:
            key = self._get_tenant_key(tenant, endpoint)
            now = time.time()
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Get current bucket state
            pipe.hmget(key, 'tokens', 'last_refill')
            results = pipe.execute()
            
            current_tokens = float(results[0][0] or max_tokens)
            last_refill = float(results[0][1] or now)
            
            # Calculate tokens to add based on time elapsed
            time_elapsed = now - last_refill
            tokens_to_add = time_elapsed * refill_rate
            new_tokens = min(max_tokens, current_tokens + tokens_to_add)
            
            # Check if we have enough tokens
            if new_tokens >= 1.0:
                # Consume one token
                new_tokens -= 1.0
                allowed = True
            else:
                allowed = False
            
            # Update bucket state
            pipe.hmset(key, {
                'tokens': new_tokens,
                'last_refill': now
            })
            pipe.expire(key, window_seconds)
            pipe.execute()
            
            remaining_tokens = int(new_tokens)
            reset_time = int(now + window_seconds)
            
            return {
                'allowed': allowed,
                'remaining': remaining_tokens,
                'reset_time': reset_time,
                'reason': 'rate_limited' if not allowed else 'ok'
            }
            
        except Exception as e:
            logger.error(f"Rate limiter error for {tenant}:{endpoint}: {e}")
            # Fail open - allow request if Redis fails
            return {
                'allowed': True,
                'remaining': max_tokens,
                'reset_time': int(time.time()) + window_seconds,
                'reason': 'redis_error'
            }

# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> TokenBucketRateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        redis_url = os.getenv('REDIS_URL')
        _rate_limiter = TokenBucketRateLimiter(redis_url)
    return _rate_limiter

def rate_limit_per_tenant(max_tokens: int = 60, 
                         refill_rate: float = 1.0,
                         window_seconds: int = 60,
                         endpoint_type: str = "api"):
    """
    Decorator for per-tenant rate limiting
    
    Args:
        max_tokens: Maximum requests per window
        refill_rate: Requests per second refill rate
        window_seconds: Time window in seconds
        endpoint_type: Type of endpoint for rate limiting
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get tenant from request context
            tenant = getattr(g, 'tenant', 'unknown')
            
            # Get endpoint identifier
            endpoint = f"{endpoint_type}:{request.endpoint or 'unknown'}"
            
            # Check rate limit
            rate_limiter = get_rate_limiter()
            result = rate_limiter.is_allowed(
                tenant=tenant,
                endpoint=endpoint,
                max_tokens=max_tokens,
                refill_rate=refill_rate,
                window_seconds=window_seconds
            )
            
            if not result['allowed']:
                # Rate limited - return cached/stale data or 429
                logger.warning(f"🚨 Rate limited: {tenant} on {endpoint}")
                
                # For public endpoints, try to serve cached data
                if endpoint_type == "public":
                    try:
                        # Try to serve stale cached data instead of 429
                        cached_data = _get_cached_fallback_data(tenant, endpoint)
                        if cached_data:
                            response = jsonify(cached_data)
                            response.headers['X-Rate-Limited'] = 'true'
                            response.headers['X-Rate-Limit-Remaining'] = '0'
                            response.headers['X-Rate-Limit-Reset'] = str(result['reset_time'])
                            response.headers['Cache-Control'] = 'public, max-age=30, stale-while-revalidate=60'
                            return response, 200
                    except Exception as e:
                        logger.debug(f"Cache fallback failed: {e}")
                
                # Return 429 with rate limit headers
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests for tenant {tenant}',
                    'retry_after': result['reset_time'] - int(time.time())
                })
                response.headers['X-Rate-Limit-Remaining'] = str(result['remaining'])
                response.headers['X-Rate-Limit-Reset'] = str(result['reset_time'])
                response.headers['Retry-After'] = str(result['reset_time'] - int(time.time()))
                return response, 429
            
            # Add rate limit headers to successful response
            def add_rate_limit_headers(response):
                response.headers['X-Rate-Limit-Remaining'] = str(result['remaining'])
                response.headers['X-Rate-Limit-Reset'] = str(result['reset_time'])
                return response
            
            # Execute the original function
            original_response = f(*args, **kwargs)
            
            # Add headers if it's a Flask response
            if hasattr(original_response, 'headers'):
                return add_rate_limit_headers(original_response)
            
            return original_response
            
        return decorated_function
    return decorator

def _get_cached_fallback_data(tenant: str, endpoint: str) -> Optional[Dict]:
    """Get cached fallback data for rate-limited requests"""
    try:
        from src.utils.redis_cache import redis_cache_get
        
        # Try different cache keys based on endpoint
        if 'load-theme' in endpoint:
            cache_key = f"branding:{tenant}"
            cached_branding = redis_cache_get(cache_key)
            if cached_branding:
                from src.routes.clean_multitenant_routing import _extract_theme_from_branding
                return _extract_theme_from_branding(cached_branding)
        
        return None
        
    except Exception as e:
        logger.debug(f"Cache fallback failed: {e}")
        return None

def check_rate_limit_for_tenant(tenant: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Check rate limit for specific tenant and endpoint"""
    rate_limiter = get_rate_limiter()
    return rate_limiter.is_allowed(tenant, endpoint, **kwargs)
