# Pool Setup - db_compat.py

## Current Implementation (Lines 294-334)

```python
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
                    # Web process: large pool for handling user requests
                    max_conn = int(os.getenv("DB_WEB_POOL_MAX", os.getenv("DB_MAX_CONN", "70")))
                    min_conn = int(os.getenv("DB_POOL_MIN", "5"))
                    conn_timeout = float(os.getenv("DB_CONN_TIMEOUT", "5"))
                    print(f"Initializing WEB pool")
                
                _POOL = ConnectionPool(
                    _dsn(),
                    min_size=min_conn,
                    max_size=max_conn,
                    timeout=conn_timeout,
                    max_lifetime=int(os.getenv("DB_POOL_MAX_LIFETIME", "900")),
                    max_idle=int(os.getenv("DB_POOL_MAX_IDLE", "300")),
                    kwargs={"row_factory": dict_row},
                )
                print(f"Created {process_type} pool: min={min_conn}, max={max_conn}, timeout={conn_timeout}s")
    return _POOL

@contextmanager
def connection_ctx(timeout=10):
    """Canonical context manager for DB access - use everywhere"""
    p = pool()  # existing global Pool factory
    raw = p.getconn(timeout=timeout)
    try:
        yield raw
    finally:
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
```

## Questions for Expert:

1. **Pool sizes**: Should I reduce web pool from 70 to 20?
2. **Connection leak detection**: Should I add timing/logging in `connection_ctx`?
3. **Rollback safety**: Is the current rollback pattern safe?
4. **Session state**: Any issues with PgBouncer transaction mode?
5. **Connection wrappers**: Are there any remaining wrapped connections that could cause "can't return to pool" errors?

