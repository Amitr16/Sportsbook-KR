"""
Cache management for public odds snapshot
Provides fast access to odds data without authentication
"""

import json
import time
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try Redis first, fallback to in-memory
try:
    from redis import Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    USE_REDIS = True
    logger.info("✅ Redis cache enabled")
except ImportError:
    USE_REDIS = False
    logger.warning("⚠️ Redis not available, using in-memory cache")

# Cache configuration
SNAPSHOT_KEY = "odds:snapshot:v1"
SNAPSHOT_TTL = 20  # seconds (tune 10-30s)

# Fallback in-memory cache
_memory_cache = {}
_memory_cache_timestamps = {}

def get_snapshot_from_cache() -> Optional[Dict[str, Any]]:
    """Get snapshot from cache (Redis or memory)"""
    try:
        if USE_REDIS:
            raw = redis.get(SNAPSHOT_KEY)
            if raw:
                return json.loads(raw)
        else:
            # Check in-memory cache
            if SNAPSHOT_KEY in _memory_cache:
                timestamp = _memory_cache_timestamps.get(SNAPSHOT_KEY, 0)
                if time.time() - timestamp < SNAPSHOT_TTL:
                    return _memory_cache[SNAPSHOT_KEY]
    except Exception as e:
        logger.error(f"❌ Cache read error: {e}")
    
    return None

def save_snapshot_to_cache(data: Dict[str, Any]):
    """Save snapshot to cache (Redis or memory)"""
    try:
        if USE_REDIS:
            redis.setex(SNAPSHOT_KEY, SNAPSHOT_TTL, json.dumps(data))
        else:
            # Save to in-memory cache
            _memory_cache[SNAPSHOT_KEY] = data
            _memory_cache_timestamps[SNAPSHOT_KEY] = time.time()
        
        logger.info(f"💾 Snapshot cached successfully (TTL: {SNAPSHOT_TTL}s)")
    except Exception as e:
        logger.error(f"❌ Cache write error: {e}")

def redact_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive data from snapshot for public access"""
    try:
        if not snapshot or 'data' not in snapshot:
            return snapshot
        
        redacted = {
            "ts": snapshot.get("ts"),
            "cached_at": datetime.now().isoformat(),
            "data": {}
        }
        
        # Process each sport's data
        for sport, sport_data in snapshot.get("data", {}).items():
            if isinstance(sport_data, list):
                # Limit to first 400 events per sport to bound payload
                redacted["data"][sport] = sport_data[:400]
            else:
                redacted["data"][sport] = sport_data
        
        return redacted
    except Exception as e:
        logger.error(f"❌ Error redacting snapshot: {e}")
        return snapshot

def get_cache_status() -> Dict[str, Any]:
    """Get cache status and statistics"""
    try:
        if USE_REDIS:
            ttl = redis.ttl(SNAPSHOT_KEY)
            exists = redis.exists(SNAPSHOT_KEY)
            return {
                "type": "redis",
                "exists": bool(exists),
                "ttl": ttl if ttl > 0 else None,
                "url": REDIS_URL
            }
        else:
            if SNAPSHOT_KEY in _memory_cache:
                timestamp = _memory_cache_timestamps.get(SNAPSHOT_KEY, 0)
                age = time.time() - timestamp
                ttl = max(0, SNAPSHOT_TTL - age)
                return {
                    "type": "memory",
                    "exists": True,
                    "ttl": ttl if ttl > 0 else None,
                    "age": age
                }
            else:
                return {
                    "type": "memory",
                    "exists": False,
                    "ttl": None,
                    "age": None
                }
    except Exception as e:
        logger.error(f"❌ Error getting cache status: {e}")
        return {"type": "error", "error": str(e)}
