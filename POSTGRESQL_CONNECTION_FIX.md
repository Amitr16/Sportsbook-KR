# PostgreSQL Connection Rollback Fix

## Problem
On Fly.io with PgBouncer, database connections were being returned to the pool in INTRANS (in transaction) state, causing warnings:
```
WARNING:psycopg.pool:rolling back returned connection: <psycopg.Connection [INTRANS] ...>
```

## Root Cause
When PostgreSQL connections execute queries (even SELECT queries), they start implicit transactions. If connections are closed without calling `commit()` or `rollback()`, they remain in INTRANS state and PgBouncer has to roll them back.

## Solution Implemented
Modified `src/db_compat.py` to automatically clean up transaction state before returning connections to the pool:

### Changes Made:
1. **CompatConnection.close()** - Now checks transaction status and rolls back if needed
2. **CompatPool.putconn()** - Additional safety check for transaction cleanup
3. **CompatConnection.__exit__()** - Proper rollback on exceptions in context managers

### Key Code Changes:
```python
# In CompatConnection.close()
if hasattr(raw, 'info') and hasattr(raw.info, 'transaction_status'):
    from psycopg import pq
    if raw.info.transaction_status in (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR):
        raw.rollback()  # Clean up transaction state
```

## Result
- Eliminates "rolling back returned connection" warnings
- Connections are returned to pool in IDLE state (clean)
- No impact on application functionality
- Better connection pool health

## Files Modified:
- `src/db_compat.py` - Main connection handling logic

## Deployment Status:
✅ Code fix implemented locally
⏳ Ready for deployment to Fly.io (pending flyctl authentication issues)
