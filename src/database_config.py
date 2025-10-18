# Database Configuration Module
# PostgreSQL ONLY - No SQLite support
# Using db_compat for SQLite-style compatibility with optimized connection pooling

import os
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from src.db_compat import connect as db_compat_connect, pool
from contextlib import contextmanager

def get_database_url():
    """Get PostgreSQL database URL with PgBouncer-optimized parameters"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL environment variable is required for PostgreSQL connection")
    
    # Convert legacy postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    
    # Accept postgresql:// and postgresql+psycopg2://
    import re
    if not re.match(r"^postgresql(\+psycopg2)?://", database_url):
        raise Exception(f"Unsupported DATABASE_URL scheme: {database_url}")
    
    # Parse existing parameters to avoid conflicts
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    parsed = urlparse(database_url)
    query_params = parse_qs(parsed.query)
    
    # Only add sslmode if not already present
    if 'sslmode' not in query_params:
        # Use 'disable' for local development, 'require' for production
        if 'localhost' in database_url or '127.0.0.1' in database_url:
            query_params['sslmode'] = ['disable']
        else:
            query_params['sslmode'] = ['require']
    
    # Add other PgBouncer-optimized parameters if not present
    defaults = {
        'connect_timeout': '10',
        'keepalives': '1',
        'keepalives_idle': '30',
        'keepalives_interval': '10',
        'keepalives_count': '5',
        'application_name': 'goalserve'
    }
    
    for key, value in defaults.items():
        if key not in query_params:
            query_params[key] = [value]
    
    # Rebuild the URL
    new_query = urlencode(query_params, doseq=True)
    optimized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    return optimized_url

def get_database_path():
    """Get the PostgreSQL connection string"""
    return get_database_url()

def is_postgresql():
    """Check if the application is using PostgreSQL (always True now)"""
    return True

@contextmanager
def get_raw_database_connection():
    """Get a raw PostgreSQL database connection with SQLite compatibility and automatic pooling"""
    database_url = get_database_url()
    
    print(f"DEBUG: Using db_compat with connection pooling: {database_url}")
    
    # Use db_compat with connection pooling for better performance
    try:
        conn = db_compat_connect(database_url, autocommit=False, use_pool=True)
        print("DEBUG: Successfully connected via db_compat with pooling")
        try:
            yield conn
        finally:
            # Ensure connection is properly returned to pool
            try:
                if hasattr(conn, '_pool') and conn._pool:
                    conn._pool.putconn(conn)
                else:
                    conn.close()
            except Exception as e:
                print(f"DEBUG: Error returning connection to pool: {e}")
                # Force close connection if pool return fails
                try:
                    conn.close()
                except:
                    pass
    except Exception as e:
        print(f"DEBUG: db_compat connection failed: {e}")
        print("DEBUG: Falling back to direct psycopg2 connection")
        
        # Fallback to direct connection if db_compat fails
        if database_url.startswith('postgresql://'):
            conn = psycopg2.connect(
                database_url,
                connect_timeout=10,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            try:
                yield conn
            finally:
                conn.close()
        else:
            raise Exception("Invalid PostgreSQL connection string format")

def get_database_connection():
    """Legacy function - use get_raw_database_connection() context manager instead"""
    return get_raw_database_connection()

def create_database_engine():
    """Create PostgreSQL engine with NullPool (no connection holding between calls)"""
    database_url = get_database_url()
    
    # Use NullPool to avoid holding connections - app should use db_compat pool instead
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        echo=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
    
    return engine

def get_database_session():
    """Get database session"""
    engine = create_database_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def test_database_connection():
    """Test DB using db_compat pool (no ad-hoc SQLAlchemy pools)"""
    try:
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {e}"

def get_connection_pool_status():
    """Report psycopg_pool stats (the real pool your app uses)"""
    try:
        from src.db_compat import pool
        p = pool()
        if hasattr(p, "get_stats"):
            s = p.get_stats()  # psycopg_pool
            # Normalize across versions
            size = s.get("pool_size", 0)
            avail = s.get("pool_available", s.get("pool_free", 0))
            checked_out = max(size - avail, 0)
            return {
                "pool_size": size,
                "available": avail,
                "checked_out": checked_out,
                "waiting": s.get("requests_waiting", 0),
                "max_size": getattr(p, "max_size", None),
                "min_size": getattr(p, "min_size", None),
            }
        return {"note": "pool stats unavailable for this pool type"}
    except Exception as e:
        return {"error": str(e)}

def get_flask_database_config():
    """Get Flask SQLAlchemy configuration for PostgreSQL"""
    return {
        'SQLALCHEMY_DATABASE_URI': get_database_url(),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': 20,
            'max_overflow': 30,
            'pool_pre_ping': True,
            'pool_recycle': 600,
            'pool_timeout': 30
        }
    }

def close_all_connections():
    """Close all database connections and pools (useful for cleanup)"""
    # REMOVED: safe_close_global_pool() - pools should only close on process exit
    # The pool will be automatically closed when the process exits
