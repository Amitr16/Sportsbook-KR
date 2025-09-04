"""
Public snapshot routes
Provides public access to cached odds data without authentication
"""

from flask import Blueprint, jsonify, request
import logging
import time
from threading import Thread

from ..cache import get_snapshot_from_cache, save_snapshot_to_cache, redact_snapshot, get_cache_status
from ..services.snapshot_builder import build_full_snapshot

logger = logging.getLogger(__name__)

bp = Blueprint("snapshot_public", __name__, url_prefix="/api")

# Simple rate limiting (in-memory)
_rate_limits = {}

def rate_limit_simple(key: str, per_min: int = 10) -> bool:
    """Simple in-memory rate limiting"""
    client_ip = request.remote_addr
    rate_key = f"{key}:{client_ip}"
    current_time = time.time()
    
    # Clean old entries
    if rate_key in _rate_limits:
        _rate_limits[rate_key] = [
            req_time for req_time in _rate_limits[rate_key] 
            if current_time - req_time < 60  # 1 minute window
        ]
    else:
        _rate_limits[rate_key] = []
    
    # Check rate limit
    if len(_rate_limits[rate_key]) >= per_min:
        return False
    
    # Add current request
    _rate_limits[rate_key].append(current_time)
    return True

@bp.route("/public/snapshot", methods=["GET"])
def public_snapshot():
    """Get public odds snapshot (no auth required)"""
    try:
        # Rate limiting
        if not rate_limit_simple("public_snapshot", per_min=10):
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        logger.info("📡 Public snapshot requested")
        
        # Try cache first
        snap = get_snapshot_from_cache()
        
        if not snap:
            logger.info("💾 Cache miss, building fresh snapshot")
            snap = build_full_snapshot()
            if snap:
                save_snapshot_to_cache(snap)
        else:
            logger.info("⚡ Cache hit, serving from cache")
        
        if not snap:
            return jsonify({
                "error": "Unable to build snapshot",
                "ts": time.time()
            }), 500
        
        # Redact sensitive data for public access
        redacted = redact_snapshot(snap)
        
        response = jsonify({
            "type": "snapshot",
            **redacted
        })
        
        # Add caching headers for CDN optimization
        response.headers['Cache-Control'] = 'public, max-age=5, stale-while-revalidate=15'
        response.headers['Vary'] = 'Accept'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error serving public snapshot: {e}")
        return jsonify({"error": "Internal server error"}), 500

@bp.route("/cache/warmup", methods=["POST"])
def cache_warmup():
    """Trigger background cache warmup (no auth required, rate limited)"""
    try:
        # Rate limiting
        if not rate_limit_simple("warmup", per_min=4):
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        logger.info("🔥 Cache warmup requested")
        
        # Trigger background refresh
        def _warmup_job():
            try:
                logger.info("🔄 Starting background cache warmup...")
                snap = build_full_snapshot()
                if snap:
                    save_snapshot_to_cache(snap)
                    logger.info("✅ Background cache warmup completed")
                else:
                    logger.warning("⚠️ Background cache warmup failed - no snapshot built")
            except Exception as e:
                logger.error(f"❌ Background cache warmup error: {e}")
        
        # Start background thread
        Thread(target=_warmup_job, daemon=True).start()
        
        return jsonify({"ok": True, "message": "Cache warmup started"})
        
    except Exception as e:
        logger.error(f"❌ Error starting cache warmup: {e}")
        return jsonify({"error": "Internal server error"}), 500

@bp.route("/cache/status", methods=["GET"])
def cache_status():
    """Get cache status information"""
    try:
        # Rate limiting
        if not rate_limit_simple("cache_status", per_min=20):
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        status = get_cache_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"❌ Error getting cache status: {e}")
        return jsonify({"error": "Internal server error"}), 500
