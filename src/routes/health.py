"""
BULLETPROOF health check endpoint - completely DB-free
"""

from flask import Blueprint, jsonify, Response
import time
import os

health_bp = Blueprint("health", __name__)

@health_bp.get("/health")
@health_bp.get("/healthz")  # Kubernetes-style endpoint
def health():
    """
    BULLETPROOF health check - NO DB, NO Redis, NO external dependencies
    
    Returns 200 even during DB outages to prevent VM flapping.
    This endpoint must NEVER import modules that initialize pools.
    """
    return jsonify({
        "ok": True, 
        "status": "healthy",
        "timestamp": time.time(),
        "version": os.getenv("APP_VERSION", "unknown")
    }), 200

@health_bp.get("/metrics")
def metrics():
    """
    Prometheus metrics endpoint
    """
    try:
        from src.utils.metrics import get_metrics
        metrics_data = get_metrics()
        return Response(metrics_data, mimetype='text/plain; version=0.0.4; charset=utf-8')
    except Exception as e:
        return Response(f"# Error getting metrics: {e}\n", mimetype='text/plain'), 500

@health_bp.get("/health/detailed")
def detailed_health():
    """
    Detailed health check with system metrics (may hit DB)
    """
    health_data = {
        "ok": True,
        "status": "healthy",
        "timestamp": time.time(),
        "version": os.getenv("APP_VERSION", "unknown"),
        "checks": {}
    }
    
    # Check database pool (optional - may fail)
    try:
        from src.db_compat import pool, is_db_circuit_breaker_open
        p = pool()
        
        # Get stats based on pool type (compatible with all pool types)
        if hasattr(p, 'get_stats'):
            # psycopg_pool API
            stats = p.get_stats()
            pool_size = stats.get('pool_size', 0)
            max_size = getattr(p, 'max_size', 20)
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
        elif hasattr(p, 'size'):
            # Standard ConnectionPool
            pool_size = p.size() if callable(p.size) else p.size
            max_size = p.max_size if hasattr(p, 'max_size') else 20
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
        else:
            # NullPool or other - no metrics
            pool_size = 0
            max_size = 0
            usage_pct = 0
        
        # Get per-route connection tracking
        try:
            from src.utils.connection_tracker import get_top_connection_users, get_connection_stats
            top_users = get_top_connection_users(limit=10)
            all_stats = get_connection_stats()
        except Exception:
            top_users = []
            all_stats = {}
        
        health_data["checks"]["database_pool"] = {
            "status": "healthy",
            "usage_percent": round(usage_pct, 1),
            "active_connections": pool_size,
            "max_connections": max_size,
            "circuit_breaker_open": is_db_circuit_breaker_open(),
            "top_connection_users": top_users,
            "connection_count": len(all_stats)
        }
    except Exception as e:
        health_data["checks"]["database_pool"] = {
            "status": "degraded",
            "error": str(e),
            "note": "Pool metrics unavailable (safe to ignore in development)"
        }
    
    # Check Redis (optional - may fail)
    try:
        import redis
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            redis_client = redis.from_url(redis_url)
            redis_client.ping()
            health_data["checks"]["redis"] = {"status": "healthy"}
            
            # Get session stats if available
            try:
                from src.utils.redis_session import get_session_stats
                session_stats = get_session_stats()
                health_data["checks"]["redis_sessions"] = session_stats
            except Exception as e:
                health_data["checks"]["redis_sessions"] = {"status": "error", "error": str(e)}
        else:
            health_data["checks"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        health_data["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Overall health based on critical checks
    # Only mark as unhealthy if ALL checks fail (more lenient)
    critical_failures = [
        check for check, data in health_data["checks"].items()
        if data.get("status") == "unhealthy"
    ]
    
    degraded_checks = [
        check for check, data in health_data["checks"].items()
        if data.get("status") == "degraded"
    ]
    
    if critical_failures:
        health_data["ok"] = False
        health_data["status"] = "unhealthy"
        health_data["critical_failures"] = critical_failures
    elif degraded_checks:
        health_data["status"] = "degraded"
        health_data["degraded_checks"] = degraded_checks
    
    # Always return 200 unless ALL checks are unhealthy (more lenient for development)
    status_code = 503 if len(critical_failures) == len(health_data["checks"]) else 200
    return jsonify(health_data), status_code

