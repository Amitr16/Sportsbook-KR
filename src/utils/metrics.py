"""
Prometheus metrics for monitoring system performance
"""

import time
import functools
import logging
import os
from typing import Dict, Any, Optional
from flask import request, g, current_app

logger = logging.getLogger(__name__)

# Prometheus metrics (will be initialized if prometheus_client is available)
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available - metrics disabled")

# Metrics registry
_metrics_registry = None

def get_metrics_registry():
    """Get or create Prometheus metrics registry"""
    global _metrics_registry
    if _metrics_registry is None and PROMETHEUS_AVAILABLE:
        _metrics_registry = CollectorRegistry()
    return _metrics_registry

# Core metrics
REQUEST_COUNT = None
REQUEST_DURATION = None
DB_POOL_USAGE = None
DB_POOL_WAITING = None
CACHE_HITS = None
CACHE_MISSES = None
ACTIVE_CONNECTIONS = None
CIRCUIT_BREAKER_STATE = None
TENANT_REQUEST_COUNT = None

def init_metrics():
    """Initialize Prometheus metrics"""
    global REQUEST_COUNT, REQUEST_DURATION, DB_POOL_USAGE, DB_POOL_WAITING
    global CACHE_HITS, CACHE_MISSES, ACTIVE_CONNECTIONS, CIRCUIT_BREAKER_STATE
    global TENANT_REQUEST_COUNT
    
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus not available - using no-op metrics")
        return
    
    registry = get_metrics_registry()
    
    # Request metrics
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status_code', 'tenant'],
        registry=registry
    )
    
    REQUEST_DURATION = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint', 'tenant'],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        registry=registry
    )
    
    # Database metrics
    DB_POOL_USAGE = Gauge(
        'db_pool_usage_percent',
        'Database pool usage percentage',
        ['process_type'],
        registry=registry
    )
    
    DB_POOL_WAITING = Gauge(
        'db_pool_waiting_connections',
        'Number of connections waiting for pool',
        ['process_type'],
        registry=registry
    )
    
    ACTIVE_CONNECTIONS = Gauge(
        'db_active_connections',
        'Number of active database connections',
        ['process_type'],
        registry=registry
    )
    
    # Cache metrics
    CACHE_HITS = Counter(
        'cache_hits_total',
        'Total cache hits',
        ['cache_type', 'tenant'],
        registry=registry
    )
    
    CACHE_MISSES = Counter(
        'cache_misses_total',
        'Total cache misses',
        ['cache_type', 'tenant'],
        registry=registry
    )
    
    # Circuit breaker metrics
    CIRCUIT_BREAKER_STATE = Gauge(
        'circuit_breaker_state',
        'Circuit breaker state (0=closed, 1=open)',
        ['breaker_name'],
        registry=registry
    )
    
    # Tenant-specific metrics
    TENANT_REQUEST_COUNT = Counter(
        'tenant_requests_total',
        'Total requests per tenant',
        ['tenant', 'endpoint_type'],
        registry=registry
    )
    
    logger.info("✅ Prometheus metrics initialized")

def record_request_metrics(f):
    """Decorator to record request metrics"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not PROMETHEUS_AVAILABLE:
            return f(*args, **kwargs)
        
        start_time = time.time()
        tenant = getattr(g, 'tenant', 'unknown')
        endpoint = request.endpoint or 'unknown'
        method = request.method
        
        try:
            response = f(*args, **kwargs)
            status_code = getattr(response, 'status_code', 200)
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                tenant=tenant
            ).inc()
            
            TENANT_REQUEST_COUNT.labels(
                tenant=tenant,
                endpoint_type='api' if endpoint.startswith('api') else 'page'
            ).inc()
            
            return response
            
        except Exception as e:
            # Record error metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=500,
                tenant=tenant
            ).inc()
            raise
            
        finally:
            # Record duration
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                tenant=tenant
            ).observe(duration)
    
    return decorated_function

def update_pool_metrics():
    """Update database pool metrics"""
    if not PROMETHEUS_AVAILABLE:
        return
    
    try:
        from src.db_compat import pool
        p = pool()
        process_type = os.getenv('PROCESS_TYPE', 'unknown')
        
        # Get metrics based on pool type
        if hasattr(p, 'get_stats'):
            # psycopg_pool API
            stats = p.get_stats()
            pool_size = stats.get('pool_size', 0)
            pool_available = stats.get('pool_available', 0)
            requests_waiting = stats.get('requests_waiting', 0)
            max_size = getattr(p, 'max_size', 20)
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
        elif hasattr(p, 'size'):
            # Standard ConnectionPool
            pool_size = p.size()
            max_size = p.max_size if hasattr(p, 'max_size') else 20
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
            requests_waiting = getattr(p, 'waiting', 0)
        else:
            # NullPool or other - skip metrics
            return
        
        # Set metrics
        DB_POOL_USAGE.labels(process_type=process_type).set(usage_pct)
        DB_POOL_WAITING.labels(process_type=process_type).set(requests_waiting)
        ACTIVE_CONNECTIONS.labels(process_type=process_type).set(pool_size)
        
    except Exception as e:
        logger.debug(f"Failed to update pool metrics: {e}")

def record_cache_hit(cache_type: str, tenant: str = 'unknown'):
    """Record cache hit"""
    if PROMETHEUS_AVAILABLE:
        CACHE_HITS.labels(cache_type=cache_type, tenant=tenant).inc()

def record_cache_miss(cache_type: str, tenant: str = 'unknown'):
    """Record cache miss"""
    if PROMETHEUS_AVAILABLE:
        CACHE_MISSES.labels(cache_type=cache_type, tenant=tenant).inc()

def update_circuit_breaker_state(breaker_name: str, is_open: bool):
    """Update circuit breaker state"""
    if PROMETHEUS_AVAILABLE:
        CIRCUIT_BREAKER_STATE.labels(breaker_name=breaker_name).set(1 if is_open else 0)

def get_metrics():
    """Get Prometheus metrics in text format"""
    if not PROMETHEUS_AVAILABLE:
        return "# Prometheus client not available\n"
    
    registry = get_metrics_registry()
    return generate_latest(registry).decode('utf-8')

# Initialize metrics on import
init_metrics()
