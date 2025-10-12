"""
Request coalescing (singleflight) at web tier to prevent thundering herd
"""

import asyncio
import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from concurrent.futures import Future
import functools

logger = logging.getLogger(__name__)

class SingleflightCoalescer:
    """Per-process request coalescing to prevent duplicate work"""
    
    def __init__(self):
        self._inflight: Dict[str, Future] = {}
        self._lock = threading.Lock()
    
    def coalesce(self, key: str, func: Callable, *args, **kwargs):
        """
        Coalesce multiple requests for the same key into a single execution
        
        Args:
            key: Unique identifier for the request
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result from function execution
        """
        with self._lock:
            # Check if request is already in flight
            if key in self._inflight:
                future = self._inflight[key]
                logger.debug(f"🔄 Coalescing request for key: {key}")
                return future.result()
            
            # Create new future for this request
            future = Future()
            self._inflight[key] = future
            
        try:
            # Execute the function
            result = func(*args, **kwargs)
            future.set_result(result)
            return result
            
        except Exception as e:
            future.set_exception(e)
            raise
            
        finally:
            # Clean up
            with self._lock:
                self._inflight.pop(key, None)

# Global coalescer instance
_coalescer = SingleflightCoalescer()

def singleflight(key_func: Optional[Callable] = None):
    """
    Decorator for request coalescing
    
    Args:
        key_func: Function to generate coalescing key from request args
                 If None, uses first argument as key
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate coalescing key
            if key_func:
                coalesce_key = key_func(*args, **kwargs)
            else:
                # Use first argument as key (typically tenant/subdomain)
                coalesce_key = str(args[0]) if args else "default"
            
            # Add function name to key for uniqueness
            full_key = f"{f.__name__}:{coalesce_key}"
            
            return _coalescer.coalesce(full_key, f, *args, **kwargs)
            
        return decorated_function
    return decorator

def coalesce_branding_requests(tenant: str, endpoint: str = "load-theme"):
    """Coalesce branding/theme requests for same tenant"""
    return f"branding:{tenant}:{endpoint}"

def coalesce_odds_requests(sport: str, market: str = "default"):
    """Coalesce odds requests for same sport/market"""
    return f"odds:{sport}:{market}"

# Example usage decorators
def singleflight_branding(f):
    """Singleflight decorator for branding requests"""
    return singleflight(lambda subdomain, **kwargs: coalesce_branding_requests(subdomain))(f)

def singleflight_odds(f):
    """Singleflight decorator for odds requests"""
    return singleflight(lambda sport, **kwargs: coalesce_odds_requests(sport))(f)

# Async version for future use
class AsyncSingleflightCoalescer:
    """Async version of request coalescing"""
    
    def __init__(self):
        self._inflight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
    
    async def coalesce(self, key: str, coro):
        """Coalesce async requests"""
        async with self._lock:
            if key in self._inflight:
                future = self._inflight[key]
                logger.debug(f"🔄 Coalescing async request for key: {key}")
                return await future
            
            future = asyncio.Future()
            self._inflight[key] = future
            
        try:
            result = await coro
            future.set_result(result)
            return result
            
        except Exception as e:
            future.set_exception(e)
            raise
            
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

# Global async coalescer
_async_coalescer = AsyncSingleflightCoalescer()

def async_singleflight(key_func: Optional[Callable] = None):
    """Async decorator for request coalescing"""
    def decorator(f):
        @functools.wraps(f)
        async def decorated_function(*args, **kwargs):
            if key_func:
                coalesce_key = key_func(*args, **kwargs)
            else:
                coalesce_key = str(args[0]) if args else "default"
            
            full_key = f"async:{f.__name__}:{coalesce_key}"
            
            return await _async_coalescer.coalesce(full_key, f(*args, **kwargs))
            
        return decorated_function
    return decorator
