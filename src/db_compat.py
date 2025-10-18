
from __future__ import annotations

print("db_compat loaded from:", __file__)
import os, re, weakref, time, traceback
import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Mapping, Sequence, Optional
from functools import lru_cache

# Track connections recovered by GC finalizer (indicates leaks)
_leaked_recovery_count = 0
_leaked_recovery_lock = threading.Lock()

def get_leaked_recovery_count():
    """Get count of connections recovered by GC finalizer"""
    global _leaked_recovery_count
    with _leaked_recovery_lock:
        return _leaked_recovery_count

def reset_leaked_recovery_count():
    """Reset the leaked recovery counter (for testing/monitoring)"""
    global _leaked_recovery_count
    with _leaked_recovery_lock:
        _leaked_recovery_count = 0

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
        
        try:
            # Execute the query - try with prepare=False for PgBouncer compatibility
            try:
                self._cursor.execute(adapted_sql, adapted_params, prepare=False)
            except TypeError:
                # Fallback if prepare parameter is not supported
                self._cursor.execute(adapted_sql, adapted_params)
        except Exception as e:
            # If query fails and leaves transaction in INERROR, rollback immediately
            # so the caller's next statement doesn't see "current transaction is aborted..."
            try:
                from psycopg import pq
                ts = getattr(self._cursor.connection.info, "transaction_status", None)
                if ts == pq.TransactionStatus.INERROR:
                    try:
                        self._cursor.connection.rollback()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                raise
        
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
    """
    PostgreSQL connection wrapper with SQLite-compatible API and proper transaction handling.
    
    IMPORTANT: Automatically cleans up transaction state when returning connections to pool.
    This prevents "rolling back returned connection" warnings with PgBouncer by ensuring
    all connections are in IDLE state (not INTRANS) before being returned to the pool.
    """
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn
        self._pool = None
        self._closed = False
        self.row_factory = None
        # Leak tracking / auto-return-on-GC for pooled conns
        self._checked_out_at = time.time()
        # Capture a short stack to help find who checked this out
        self._checkout_stack = ''.join(traceback.format_stack(limit=6))
        self._finalizer = None  # set later after we know _pool
    
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
            
        # Track connection release if tracking info exists
        if hasattr(self, '_tracking_context') and hasattr(self, '_tracking_start'):
            try:
                from src.utils.connection_tracker import track_connection_released
                track_connection_released(self._tracking_context, self._tracking_start)
            except Exception:
                pass  # Don't let tracking errors break connection cleanup
            
        pool, raw = self._pool, self._conn
        # Detach first so later __del__/__exit__ cannot close a pooled conn
        self._pool = None
        self._conn = None
        self._closed = True
        try:
            if pool is not None:
                # CRITICAL FIX: Ensure transaction is committed/rolled back before returning to pool
                # This prevents "rolling back returned connection" warnings with PgBouncer
                try:
                    # Check if connection is in transaction state
                    if hasattr(raw, 'info') and hasattr(raw.info, 'transaction_status'):
                        from psycopg import pq
                        # If in INTRANS or INERROR state, we need to clean up
                        if raw.info.transaction_status in (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR):
                            # Rollback to clean state (safe for both read and write operations that weren't explicitly committed)
                            raw.rollback()
                except Exception as tx_error:
                    # If transaction cleanup fails, just log it and continue
                    import logging
                    logging.debug(f"Transaction cleanup before pool return: {tx_error}")
                
                pool.putconn(raw)
            else:
                raw.close()
        except Exception:
            try:
                raw.close()
            except Exception:
                pass
        finally:
            # Cancel finalizer if any
            try:
                if self._finalizer is not None:
                    self._finalizer.detach()
            except Exception:
                pass
    
    def __enter__(self):
        """Support for context manager protocol"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol"""
        try:
            # If an exception occurred in the with block, rollback
            if exc_type is not None:
                try:
                    self.rollback()
                except:
                    pass
            self.close()
        except:
            pass
    
    def _attach_pool_finalizer(self, pool_obj):
        """
        Attach a GC finalizer that will return the connection to the pool
        even if caller forgot to close it. Only used for pooled connections.
        """
        if self._finalizer is not None:
            return
        raw = self._conn
        def _return_to_pool(raw_ref=raw, pool_ref=pool_obj):
            global _leaked_recovery_count
            try:
                # Best-effort cleanup
                try:
                    if hasattr(raw_ref, 'info') and hasattr(raw_ref.info, 'transaction_status'):
                        from psycopg import pq
                        if raw_ref.info.transaction_status in (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR):
                            raw_ref.rollback()
                except Exception:
                    pass
                pool_ref.putconn(raw_ref)
                with _leaked_recovery_lock:
                    _leaked_recovery_count += 1
                logging.warning("🔁 GC finalizer returned leaked DB connection to pool (count: %d)", _leaked_recovery_count)
            except Exception as e:
                try:
                    raw_ref.close()
                except Exception:
                    pass
                with _leaked_recovery_lock:
                    _leaked_recovery_count += 1
                logging.warning(f"💥 GC finalizer closed leaked DB connection (pool put failed, count: {_leaked_recovery_count}): {e}")
        self._finalizer = weakref.finalize(self, _return_to_pool)
        self._finalizer.atexit = False  # Don't duplicate atexit logs
    
    def __del__(self):
        # As a secondary guard, log if a pooled connection lived too long
        try:
            held_ms = (time.time() - self._checked_out_at) * 1000.0
            if held_ms > 5_000 and not self._closed:
                logging.warning(
                    "🕳️ DB connection object garbage-collected after %.0fms without close(); "
                    "auto-returned by GC finalizer.\nCheckout stack:\n%s",
                    held_ms, self._checkout_stack
                )
        except Exception:
            pass
    
    def __getattr__(self, name: str): 
        return getattr(self._conn, name)

# Global connection pool - SIMPLIFIED SINGLETON PATTERN
import threading
import atexit

_POOL = None
_POOL_LOCK = threading.Lock()

def _dsn():
    """Get DATABASE_URL from environment (points at PgBouncer host)"""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # Normalize postgres:// to postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    elif url.startswith('postgresql+psycopg2://'):
        url = url.replace('postgresql+psycopg2://', 'postgresql://', 1)
    return url

def pool() -> ConnectionPool:
    """Get or create the global connection pool (size varies by process type)"""
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                from psycopg.rows import dict_row
                
                # Determine process type and set appropriate pool size
                process_type = os.getenv("PROCESS_TYPE", "web")  # web, worker_odds, worker_settlement
                
                if process_type == "worker_odds":
                    # Odds worker: small pool (only needs a few connections)
                    max_conn = int(os.getenv("DB_WORKER_POOL_MAX", "5"))
                    min_conn = 1
                    conn_timeout = 10.0
                    print(f"Initializing ODDS WORKER pool")
                elif process_type == "worker_settlement":
                    # Settlement worker: small pool
                    max_conn = int(os.getenv("DB_WORKER_POOL_MAX", "5"))
                    min_conn = 1
                    conn_timeout = 10.0
                    print(f"Initializing SETTLEMENT WORKER pool")
                else:
                    # Web process: conservative pool size (scale horizontally via replicas)
                    max_conn = int(os.getenv("DB_WEB_POOL_MAX", "20"))
                    min_conn = int(os.getenv("DB_POOL_MIN", "2"))
                    conn_timeout = float(os.getenv("DB_CONN_TIMEOUT", "5"))
                    print(f"Initializing WEB pool")
                
                stmt_timeout    = os.getenv("DB_STATEMENT_TIMEOUT", "3000")   # "3000" or "3s"
                idle_tx_timeout = os.getenv("DB_IDLE_IN_TRANSACTION_TIMEOUT", "5000")
                connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "4"))    # seconds
                prepare_thresh  = os.getenv("DB_PREPARE_THRESHOLD", "0")

                conn_kwargs = {
                    "row_factory": dict_row,
                    "connect_timeout": connect_timeout,
                    # TCP keepalives (critical on Fly to avoid idle disconnects)
                    "keepalives": 1,
                    "keepalives_idle": int(os.getenv("DB_KEEPALIVES_IDLE", "30")),
                    "keepalives_interval": int(os.getenv("DB_KEEPALIVES_INTERVAL", "10")),
                    "keepalives_count": int(os.getenv("DB_KEEPALIVES_COUNT", "3")),
                    # No `options` here — PgBouncer may reject startup options
                }

                _POOL = ConnectionPool(
                    _dsn(),
                    min_size=min_conn,
                    max_size=max_conn,
                    timeout=conn_timeout,  # wait-for-connection timeout
                    max_lifetime=int(os.getenv("DB_POOL_MAX_LIFETIME", "900")),
                    max_idle=int(os.getenv("DB_POOL_MAX_IDLE", "300")),
                    kwargs=conn_kwargs,
                )
                print(f"Created {process_type} pool: min={min_conn}, max={max_conn}, timeout={conn_timeout}s")
    return _POOL

@contextmanager
def connection_ctx(timeout=10):
    """
    Canonical context manager for DB access - use everywhere
    Includes connection leak detection (warns if held > 300ms)
    """
    import time
    from src.utils.connection_tracker import track_connection_acquired, track_connection_released
    
    p = pool()  # existing global Pool factory
    start_time = time.time()
    
    # Track connection acquisition
    context, track_start = track_connection_acquired()
    
    raw = p.getconn(timeout=timeout)
    
    # CRITICAL: Clean aborted transactions BEFORE opening cursor
    try:
        from psycopg import pq
        ts = getattr(raw.info, "transaction_status", None)
        if ts in (pq.TransactionStatus.INERROR, pq.TransactionStatus.INTRANS):
            raw.rollback()  # Use connection method, not cursor execute
    except Exception:
        # Blind rollback attempt if inspection fails
        try:
            raw.rollback()
        except Exception:
            pass
    
    # Fast-fail liveness check + apply timeouts
    try:
        with raw.cursor() as _c:
            _c.execute("SELECT 1")
            # Apply timeouts *after* connect (safe with PgBouncer)
            # Accept both ms ("3000") and duration ("3s")
            st  = os.getenv("DB_STATEMENT_TIMEOUT", "3000")
            itx = os.getenv("DB_IDLE_IN_TRANSACTION_TIMEOUT", "5000")
            try:
                _c.execute(f"SET statement_timeout = {st}")
            except Exception as e:
                # If SET fails, rollback and continue (some pool modes don't allow it)
                try:
                    raw.rollback()
                except Exception:
                    pass
            try:
                _c.execute(f"SET idle_in_transaction_session_timeout = {itx}")
            except Exception as e:
                # If SET fails, rollback and continue
                try:
                    raw.rollback()
                except Exception:
                    pass
            # Prepare threshold (psycopg3 honors server GUC; safe to ignore if blocked)
            pt = os.getenv("DB_PREPARE_THRESHOLD", "0")
            try:
                _c.execute(f"SET prepare_threshold = {pt}")
            except Exception as e:
                # If SET fails, rollback and continue
                try:
                    raw.rollback()
                except Exception:
                    pass
    except Exception:
        # Replace bad connection transparently
        try:
            p.putconn(raw, close=True)
        except Exception:
            pass
        raw = p.getconn(timeout=timeout)
        # Retry the setup on the fresh connection
        try:
            with raw.cursor() as _c:
                _c.execute("SELECT 1")
        except Exception:
            pass
    
    # Wrap raw connection in CompatConnection for auto-rollback on errors
    compat_conn = CompatConnection(raw)
    # DON'T set _pool - connection_ctx will handle putconn in finally block
    # Setting _pool causes double-return attempts
    
    try:
        yield compat_conn
    finally:
        # Track connection release
        track_connection_released(context, track_start)
        
        # Calculate how long connection was held
        hold_time_ms = (time.time() - start_time) * 1000
        
        # Warn if connection held too long (potential leak or slow query)
        if hold_time_ms > 300:  # 300ms threshold
            import traceback
            logging.warning(
                f"⚠️ Connection held for {hold_time_ms:.0f}ms (>{300}ms threshold). "
                f"Potential leak or slow query. Stack:\n{''.join(traceback.format_stack()[-3:-1])}"
            )
        
        try:
            try:
                raw.rollback()
            except Exception:
                pass
            p.putconn(raw)
        except Exception as e:
            logging.warning("putconn failed (%s); closing connection", e)
            try:
                p.putconn(raw, close=True)
            except Exception:
                pass

# Circuit breaker state
_circuit_breaker_state = {
    'tripped': False,
    'last_check': 0,
    'failure_count': 0,
    'success_count': 0
}

def is_db_circuit_breaker_open():
    """Check if DB circuit breaker is open (pool >85% usage or timeout errors)"""
    try:
        p = pool()
        
        # Different pool types have different attributes
        # psycopg_pool.ConnectionPool uses different API than NullPool
        if hasattr(p, 'get_stats'):
            # psycopg_pool API
            stats = p.get_stats()
            pool_size = stats.get('pool_size', 0)
            pool_available = stats.get('pool_available', 0)
            requests_waiting = stats.get('requests_waiting', 0)
            max_size = getattr(p, 'max_size', 20)
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
            waiting_connections = requests_waiting
        elif hasattr(p, 'size'):
            # Standard ConnectionPool attributes
            pool_size = p.size()
            max_size = p.max_size if hasattr(p, 'max_size') else 20
            usage_pct = (pool_size / max_size) * 100 if max_size > 0 else 0
            waiting_connections = getattr(p, 'waiting', 0)
        else:
            # NullPool or other pool types - always allow through
            return False
        
        # Circuit breaker opens at 85% usage OR if we have waiting connections
        if usage_pct > 85 or waiting_connections > 5:
            _circuit_breaker_state['tripped'] = True
            _circuit_breaker_state['failure_count'] += 1
            logging.warning(f"🚨 DB Circuit Breaker OPEN: {usage_pct:.0f}% usage, {waiting_connections} waiting")
            return True
        else:
            _circuit_breaker_state['tripped'] = False
            _circuit_breaker_state['success_count'] += 1
            return False
    except Exception as e:
        logging.debug(f"Circuit breaker check failed (safe to ignore): {e}")
        return False  # Fail open for circuit breaker checks

def should_bypass_db_for_reads():
    """Check if we should bypass DB for non-critical reads"""
    return is_db_circuit_breaker_open()

def circuit_breaker_context(operation_type="read"):
    """Context manager for circuit breaker protection"""
    from contextlib import contextmanager
    
    @contextmanager
    def _circuit_context():
        if should_bypass_db_for_reads() and operation_type in ["read", "cache_miss"]:
            logging.info(f"🚨 Circuit breaker: bypassing {operation_type} operation")
            yield False  # Indicates DB operation should be skipped
        else:
            yield True  # Indicates DB operation should proceed
    
    return _circuit_context()

def log_pool_metrics():
    """Log pool usage metrics for monitoring (Phase 2 + Prometheus)"""
    try:
        p = pool()
        
        # Get stats based on pool type
        if hasattr(p, 'get_stats'):
            # psycopg_pool API
            pool_stats = p.get_stats()
            stats = {
                'size': pool_stats.get('pool_size', 0),
                'available': pool_stats.get('pool_available', 0),
                'waiting': pool_stats.get('requests_waiting', 0),
            }
            max_size = getattr(p, 'max_size', 20)
        elif hasattr(p, 'size'):
            # Standard ConnectionPool
            stats = {
                'size': p.size(),
                'available': getattr(p, 'available', 0),
                'waiting': getattr(p, 'waiting', 0),
            }
            max_size = p.max_size if hasattr(p, 'max_size') else 20
        else:
            # NullPool or other - no metrics
            return {}
        
        # Calculate usage percentage
        usage_pct = (stats['size'] / max_size) * 100 if max_size > 0 else 0
        
        # Update Prometheus metrics
        try:
            from src.utils.metrics import update_pool_metrics
            update_pool_metrics()
        except Exception as e:
            logging.debug(f"Failed to update Prometheus metrics: {e}")
        
        # Update circuit breaker metrics
        try:
            from src.utils.metrics import update_circuit_breaker_state
            is_open = is_db_circuit_breaker_open()
            update_circuit_breaker_state('db_pool', is_open)
        except Exception as e:
            logging.debug(f"Failed to update circuit breaker metrics: {e}")
        
        # Log warning if pool is >80% utilized
        if usage_pct > 80:
            logging.warning(f"⚠️ Pool usage HIGH: {usage_pct:.0f}% ({stats['size']}/{max_size}) - {stats['waiting']} waiting")
        elif usage_pct > 50:
            logging.info(f"📊 Pool usage: {usage_pct:.0f}% ({stats['size']}/{max_size})")
        
        return stats
    except Exception as e:
        logging.error(f"Error getting pool metrics: {e}")
        return {}

def debug_pool(tag=""):
    """Debug helper to log pool stats"""
    try:
        p = pool()
        if hasattr(p, 'get_stats'):
            s = p.get_stats()
            print(f"DB_POOL[{tag}] size={s.get('pool_size', '?')} available={s.get('pool_available', '?')} requests_waiting={s.get('requests_waiting', 0)}")
    except Exception as e:
        print(f"DB_POOL[{tag}] stats unavailable: {e}")

# Clean up pool only on process exit
@atexit.register
def _close_pool_on_exit():
    """Close the global pool only when the process exits"""
    global _POOL
    if _POOL:
        try:
            _POOL.close()
            print("Closed connection pool on process exit")
        except Exception as e:
            print(f"Error closing pool on exit: {e}")

def connect(dsn: Optional[str] = None, *, autocommit: bool = False, use_pool: bool = True) -> CompatConnection:
    """
    Legacy helper - AVOID in new code. Use connection_ctx() instead.
    Only use if caller will putconn() correctly.
    """
    if use_pool:
        p = pool()
        raw = p.getconn()
        conn = CompatConnection(raw)
        conn._pool = p
        conn._attach_pool_finalizer(p)  # Ensure GC will putconn if caller forgets
        if autocommit:
            # Ensure no aborted transaction before toggling autocommit
            try:
                from psycopg import pq
                ts = getattr(raw.info, "transaction_status", None)
                if ts in (pq.TransactionStatus.INERROR, pq.TransactionStatus.INTRANS):
                    raw.rollback()
            except Exception:
                # blind rollback if inspection not available
                try:
                    raw.rollback()
                except Exception:
                    pass
            raw.autocommit = True
        return conn
    else:
        raw = psycopg.connect(_dsn(), row_factory=dict_row)
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
            
            # CRITICAL FIX: Clean up transaction state before returning to pool
            try:
                if hasattr(raw, 'info') and hasattr(raw.info, 'transaction_status'):
                    from psycopg import pq
                    # If in INTRANS or INERROR state, rollback to clean up
                    if raw.info.transaction_status in (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR):
                        raw.rollback()
            except Exception as tx_error:
                import logging
                logging.debug(f"Transaction cleanup in putconn: {tx_error}")
            
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
