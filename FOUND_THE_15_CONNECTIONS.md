# FOUND IT! The Source of 15 Untracked Connections

## The Problem
```
checked_out: 15              ← Pool says 15 connections
total_active: 0              ← Tracking says 0 active  
tracking_discrepancy: 15     ← 15 UNTRACKED! 🔴
```

## Root Cause: Flask-SQLAlchemy's Own Connection Pool!

### Discovery
Flask-SQLAlchemy was initialized WITHOUT explicit pool configuration:
```python
# src/main.py
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # ← Uses DEFAULT pool settings!
```

### The Issue
**SQLAlchemy's default pool configuration:**
- `pool_size = 5` (5 persistent connections)
- `max_overflow = 10` (up to 10 additional connections)
- **Total: Up to 15 connections!** 🎯

These connections:
- Are managed by SQLAlchemy's own pooling mechanism
- Bypass our `db_compat.py` pool
- Don't go through `connection_ctx()` or `get_db_connection()`
- **Are completely untracked by our system!**

### Why This Matters
We have **TWO separate connection pools**:
1. ✅ **Our `db_compat` pool** - Fully tracked, min=1, max=50
2. 🔴 **SQLAlchemy's pool** - Untracked, default=5+10 overflow

Result: The 15 "untracked" connections are SQLAlchemy's pool!

## The Fixes

### Fix 1: Configure SQLAlchemy to Use NullPool
```python
# src/main.py - ADDED
from sqlalchemy.pool import NullPool
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': NullPool,      # ← No pooling, create connections on-demand
    'pool_pre_ping': True,      # ← Validate connections before use
    'connect_args': {
        'connect_timeout': 10,
    }
}
```

**Effect:** SQLAlchemy will no longer maintain its own pool. It will create connections on-demand and close them immediately.

### Fix 2: Add Fallback Tracking to `db_compat.connect()`
```python
# src/db_compat.py - MODIFIED
def connect(...):
    # ...
    # Check if caller already set up tracking
    if not hasattr(conn, '_tracking_context'):
        # Caller didn't track - add tracking with detailed caller info
        context = f"UNTRACKED:{filename}::{function_name}:L{line_number}"
        context, track_start = track_connection_acquired(context)
        conn._tracking_context = context
        conn._tracking_start = track_start
```

**Effect:** Any connection that bypasses normal tracking will be labeled as "UNTRACKED" with caller details.

## Expected Result After Deploy

### Before:
```
checked_out: 15
total_active: 0
tracking_discrepancy: 15  🔴
```

### After:
```
checked_out: 2-5
total_active: 2-5
tracking_discrepancy: 0  ✅
```

## Benefits

1. ✅ **Single connection pool** - Only `db_compat` pool in use
2. ✅ **All connections tracked** - No more mysterious untracked connections
3. ✅ **Better visibility** - Any remaining untracked will show as "UNTRACKED:..." 
4. ✅ **Reduced overhead** - One pool instead of two
5. ✅ **True leak detection** - Discrepancy = 0 means perfect tracking

## Testing Plan

After deployment:
1. Wait 30 minutes for pools to stabilize
2. Check `/health/detailed`
3. Verify `tracking_discrepancy` is near 0 (allow ±1-2 for transient requests)
4. Look for any routes starting with `"UNTRACKED:"` - these need fixing
5. Monitor for 12 hours to ensure stability

## Confidence Level

**95% confident** this is the root cause because:
- SQLAlchemy's default pool = 5 + 10 overflow = 15 connections ✅
- Our discrepancy = exactly 15 ✅
- SQLAlchemy connections don't go through our tracking ✅
- Timeline matches (stable at 15 for 12 hours = pool size holding steady) ✅

