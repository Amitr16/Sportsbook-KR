
from __future__ import annotations

print("db_compat loaded from:", __file__)
import os, re
from typing import Any, Iterable, Mapping, Sequence, Optional
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Compile regex patterns once and cache them
_QMARK = re.compile(r"\?")
_NAMED = re.compile(r"(?<!:):([a-zA-Z_]\w*)")
_BOOL_1 = re.compile(r"(\b=\s*)1\b", re.IGNORECASE)
_BOOL_0 = re.compile(r"(\b=\s*)0\b", re.IGNORECASE)

# Cache for SQL adaptations
@lru_cache(maxsize=1000)
def adapt_sql(sql: str) -> str:
    """Cache SQL adaptations to avoid repeated regex processing"""
    s = _QMARK.sub("%s", sql)
    s = _NAMED.sub(lambda m: f"%({m.group(1)})s", s)
    s = _BOOL_1.sub(r"\1TRUE", s)
    s = _BOOL_0.sub(r"\1FALSE", s)
    return s

def force_gc_collect():
    """Force garbage collection to free memory"""
    import gc
    gc.collect()

def adapt_params(params: Any) -> Any:
    """Convert SQLite-style parameters to PostgreSQL-compatible ones"""
    if params is None:
        return None
    
    # Fast path for common cases
    if isinstance(params, (list, tuple)):
        if not params:  # Empty sequence
            return params
        # Only convert 0/1 to boolean if they're likely meant to be booleans
        # For now, let's be conservative and not convert anything automatically
        # The application code should handle boolean conversion explicitly
        return params
    
    if isinstance(params, dict):
        if not params:  # Empty dict
            return params
        # Same conservative approach for dicts
        return params
    
    # Single value - be conservative
    return params

class HybridRow(dict):
    """Optimized row object that supports both dict and tuple access"""
    def __init__(self, d: Mapping[str, Any]):
        super().__init__(d)
        self._values_list = None
    
    def __getitem__(self, key):
        if isinstance(key, int):
            if self._values_list is None:
                self._values_list = list(self.values())
            try:
                return self._values_list[key]
            except IndexError:
                raise IndexError(f"row index {key} out of range")
        return super().__getitem__(key)
    
    def __len__(self):
        return super().__len__()
    
    def __iter__(self):
        return iter(self.values())

class CompatCursor:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self._lastrowid = None  # Store last inserted ID
        self._stored_result = None # Store the result of RETURNING queries
    
    def __enter__(self):
        """Support for context manager protocol"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol"""
        # Close the cursor when exiting context
        try:
            self.close()
        except:
            pass
    
    def execute(self, sql: str, params: Any = None):
        # Convert SQLite placeholders to PostgreSQL
        adapted_sql = adapt_sql(sql)
        adapted_params = adapt_params(params) if params else None
        
        # Execute the query - try with prepare=False for PgBouncer compatibility
        try:
            self._cursor.execute(adapted_sql, adapted_params, prepare=False)
        except TypeError:
            # Fallback if prepare parameter is not supported
            self._cursor.execute(adapted_sql, adapted_params)
        
        # Check if this is an INSERT with RETURNING
        if adapted_sql.strip().upper().startswith('INSERT') and 'RETURNING' in adapted_sql.upper():
            # If INSERT has RETURNING, we need to get the ID but not consume the result
            # Store the cursor position so we can restore it
            try:
                # Get the result without consuming it
                result = self._cursor.fetchone()
                if result:
                    # Try to get 'id' column, fallback to first column
                    if isinstance(result, dict):
                        self._lastrowid = result.get('id', result.get(list(result.keys())[0]))
                    else:
                        self._lastrowid = result[0]
                    
                    # Restore the result so it can be fetched again
                    # We need to re-execute the query to restore the result
                    # This is a limitation of psycopg - we can't "unfetch"
                    # So we'll store the result and return it on the next fetchone()
                    self._stored_result = result
                else:
                    self._lastrowid = None
                    self._stored_result = None
            except Exception as e:
                self._lastrowid = None
                self._stored_result = None
        elif adapted_sql.strip().upper().startswith('INSERT'):
            # For INSERT without RETURNING, try to get last inserted ID
            try:
                # Try to get the last inserted ID from the sequence
                self._cursor.execute("SELECT LASTVAL()")
                result = self._cursor.fetchone()
                if result:
                    if isinstance(result, dict):
                        self._lastrowid = result.get('lastval', result.get(list(result.keys())[0]))
                    else:
                        self._lastrowid = result[0]
                else:
                    self._lastrowid = None
            except Exception as e:
                self._lastrowid = None
        
        return self
    
    def executemany(self, sql: str, seq: Iterable[Any]):
        adapted_sql = adapt_sql(sql)
        adapted_params = [adapt_params(params) for params in seq]
        return self._cursor.executemany(adapted_sql, adapted_params)
    
    def fetchone(self):
        # If we have a stored result from RETURNING, return it
        if hasattr(self, '_stored_result') and self._stored_result is not None:
            result = self._stored_result
            self._stored_result = None  # Clear it after use
            return HybridRow(result) if result else None
        
        # Otherwise, fetch from the cursor normally
        result = self._cursor.fetchone()
        return HybridRow(result) if result else None
    
    def fetchall(self):
        results = self._cursor.fetchall()
        return [HybridRow(result) for result in results]
    
    def fetchmany(self, size: int = None):
        results = self._cursor.fetchmany(size)
        return [HybridRow(result) for result in results]
    
    @property
    def lastrowid(self):
        """Emulate SQLite's lastrowid for PostgreSQL compatibility"""
        return self._lastrowid
    
    def __getattr__(self, name: str):
        return getattr(self._cursor, name)

class CompatConnection:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn
        self._pool = None
        self._closed = False
        self.row_factory = None
    
    def cursor(self):
        """Return a cursor with lastrowid emulation"""
        raw_cursor = self._conn.cursor()
        return CompatCursor(raw_cursor)
    
    def execute(self, sql: str, params: Any = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
    
    def executemany(self, sql: str, seq: Iterable[Any]):
        cur = self.cursor()
        cur.executemany(sql, seq)
        return cur
    
    def commit(self): 
        return self._conn.commit()
    
    def rollback(self): 
        return self._conn.rollback()
    
    def close(self):
        if self._closed:
            return
        pool, raw = self._pool, self._conn
        # Detach first so later __del__/__exit__ cannot close a pooled conn
        self._pool = None
        self._conn = None
        self._closed = True
        try:
            if pool is not None:
                pool.putconn(raw)
            else:
                raw.close()
        except Exception:
            try:
                raw.close()
            except Exception:
                pass
    
    def __enter__(self):
        """Support for context manager protocol"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol"""
        try:
            self.close()
        except:
            pass
    
    def __getattr__(self, name: str): 
        return getattr(self._conn, name)

# Global connection pool for better performance
_global_pool = None
_pool_reference_count = 0

def _normalize_dsn(dsn: str) -> str:
    """Convert SQLAlchemy-style URLs to standard PostgreSQL URLs for psycopg"""
    # Convert postgresql+psycopg2:// to postgresql:// (psycopg doesn't understand the +psycopg2 part)
    if dsn.startswith('postgresql+psycopg2://'):
        dsn = dsn.replace('postgresql+psycopg2://', 'postgresql://', 1)
    # Convert postgres:// to postgresql:// (legacy format)
    elif dsn.startswith('postgres://'):
        dsn = dsn.replace('postgres://', 'postgresql://', 1)
    return dsn

def _pool_is_closed(p):
    try:
        return bool(getattr(p, "closed", False))
    except Exception:
        return True

def get_global_pool(dsn: str = None, **kwargs) -> 'CompatPool':
    """Get or create global connection pool with PgBouncer-optimized settings"""
    global _global_pool
    if not dsn:
        # Use the optimized DATABASE_URL from database_config
        from src.database_config import get_database_url
        dsn = get_database_url()
    
    # Normalize the DSN for psycopg compatibility
    normalized_dsn = _normalize_dsn(dsn)
    
    # Always create new pool if DSN changes, pool doesn't exist, or pool is closed
    if (_global_pool is None or 
        _global_pool._dsn != normalized_dsn or 
        _pool_is_closed(_global_pool._pool)):
        if _global_pool:
            _global_pool.close()  # Close old pool
        
        # Check if we're in local development (no DATABASE_URL or localhost)
        is_local = (not os.getenv('DATABASE_URL') or 
                   'localhost' in normalized_dsn or 
                   '127.0.0.1' in normalized_dsn)
        
        if is_local:
            # Very lenient settings for local development
            pool_kwargs = {
                'min_size': 0,
                'max_size': 50,  # Much larger pool for local development
                'timeout': 120,  # Longer timeout for local development
                **kwargs
            }
        else:
            # Conservative settings for production (PgBouncer)
            pool_kwargs = {
                'min_size': 0,
                'max_size': 20,      # Conservative pool size for PgBouncer
                'timeout': 30,
                **kwargs
            }
        
        _global_pool = CompatPool(normalized_dsn, **pool_kwargs)
        _global_pool._dsn = normalized_dsn  # Store normalized DSN for comparison
    
    return _global_pool

def _reset_global_pool():
    """Reset global pool for testing purposes"""
    global _global_pool
    if _global_pool:
        _global_pool.close()
        _global_pool = None

def safe_close_global_pool():
    """Safely close the global pool only if no connections are in use"""
    global _global_pool, _pool_reference_count
    if _global_pool and _pool_reference_count <= 0:
        _global_pool.close()
        _global_pool = None
        print("DEBUG: Safely closed global connection pool")
    elif _global_pool:
        print(f"DEBUG: Pool still has {_pool_reference_count} active references, not closing")
    else:
        print("DEBUG: No pool to close")

def connect(dsn: Optional[str] = None, *, autocommit: bool = False, use_pool: bool = True) -> CompatConnection:
    """Connect with optional connection pooling for better performance"""
    if not dsn:
        # Use the optimized DATABASE_URL from database_config
        from src.database_config import get_database_url
        dsn = get_database_url()
    
    # Normalize the DSN for psycopg compatibility
    normalized_dsn = _normalize_dsn(dsn)
    
    # Log connection attempt (redact credentials, show host)
    import re
    host_match = re.search(r'@([^:/]+)', normalized_dsn)
    host = host_match.group(1) if host_match else 'unknown'
    print(f"🔌 db_compat connecting via host: {host}")
    
    if use_pool:
        global _global_pool
        try:
            pool = get_global_pool(normalized_dsn)  # Use conservative PgBouncer settings
            # Check if pool is closed before getting connection
            if _pool_is_closed(pool._pool):
                print("⚠️ Pool is closed, recreating...")
                # Force recreation of pool
                _global_pool = None
                pool = get_global_pool(normalized_dsn)
            raw = pool.getconn()
            conn = CompatConnection(raw)
            # Store pool reference for later return
            conn._pool = pool
            return conn
        except Exception as e:
            if "PoolClosed" in str(e):
                print(f"⚠️ Pool closed, recreating pool...")
                # Force pool recreation
                if _global_pool:
                    try:
                        _global_pool.close()
                    except:
                        pass
                    _global_pool = None
                # Try again with new pool
                pool = get_global_pool(normalized_dsn)
                raw = pool.getconn()
                conn = CompatConnection(raw)
                conn._pool = pool
                return conn
            else:
                raise
    else:
        raw = psycopg.connect(normalized_dsn, row_factory=dict_row)
        raw.autocommit = autocommit
        return CompatConnection(raw)

class CompatPool:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 20, timeout: int = 60):
        self._pool = ConnectionPool(
            conninfo=dsn, 
            min_size=0,  # Start with 0 connections to prevent immediate connection attempts
            max_size=max_size, 
            timeout=timeout,  # Connection timeout in seconds
            kwargs={"row_factory": dict_row}
        )
    
    def getconn(self) -> CompatConnection:
        if _pool_is_closed(self._pool):
            new = _make_pool()
            globals()["_GLOBAL_POOL"] = new
            return new.getconn()
        raw = self._pool.getconn()
        cc = CompatConnection(raw)
        cc._pool = self
        return cc
    
    def putconn(self, conn: CompatConnection):
        try:
            raw = conn if not isinstance(conn, CompatConnection) else getattr(conn, "_conn", None)
            if raw is None or getattr(raw, "closed", False):
                return
            if _pool_is_closed(self._pool):
                try:
                    raw.close()
                finally:
                    return
            self._pool.putconn(raw)
        except Exception as e:
            # Log error and force close connection
            import logging
            logging.error(f"Error returning connection to pool: {e}")
            try:
                if hasattr(conn, 'close'):
                    conn.close()
            except:
                pass
    
    def get_pool_stats(self):
        """Get pool statistics for monitoring"""
        try:
            return {
                'min_size': self._pool.min_size,
                'max_size': self._pool.max_size,
                'size': self._pool.size,
                'free_size': self._pool.free_size,
                'checked_in': self._pool.checked_in,
                'checked_out': self._pool.checked_out
            }
        except Exception as e:
            # psycopg_pool has different attributes, use what's available
            try:
                return {
                    'min_size': getattr(self._pool, 'min_size', 'unknown'),
                    'max_size': getattr(self._pool, 'max_size', 'unknown'),
                    'size': getattr(self._pool, 'size', 'unknown'),
                    'free_size': getattr(self._pool, 'free_size', 'unknown'),
                    'checked_in': getattr(self._pool, 'checked_in', 'unknown'),
                    'checked_out': getattr(self._pool, 'checked_out', 'unknown')
                }
            except:
                return {'error': str(e), 'pool_type': 'psycopg_pool'}
    
    def close(self): 
        self._pool.close()

def pool_connect(dsn: Optional[str] = None, **kw) -> CompatPool:
    if not dsn:
        # Use the optimized DATABASE_URL from database_config
        from src.database_config import get_database_url
        dsn = get_database_url()
    return CompatPool(dsn, **kw)

# Convenience function for the health endpoint
def get_connection(*args, **kwargs) -> CompatConnection:
    """Get a connection from the pool - convenience function for health checks"""
    return connect(*args, **kwargs)

@lru_cache(maxsize=100)
def get_table_columns(conn: CompatConnection, table: str) -> list[str]:
    """Cached table column lookup"""
    cur = conn.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %(t)s
        ORDER BY ordinal_position
    """, {"t": table})
    return [r['column_name'] for r in cur.fetchall()]
