# Wrapper Function Double Tracking Bug

## The Issue You Discovered
```
"db_compat.py::get_connection" - acquired: 37, released: 0  🔴
"sqlite3_shim.py::connect" - acquired: 4, released: 0  🔴
```

**Great catch!** This was NOT a counting bug - it was a **REAL LEAK** caused by double tracking in wrapper functions.

## Root Cause

### Problem 1: `db_compat.py::get_connection()`
```python
# Line 850-852 in db_compat.py
def get_connection(*args, **kwargs) -> CompatConnection:
    """Get a connection from the pool - convenience function for health checks"""
    return connect(*args, **kwargs)  # ← Calls connect() which tracks!
```

When code calls `get_connection()`:
1. Tracking system captures context as `"db_compat.py::get_connection"` 
2. Then it calls `connect()` which I added tracking to
3. `connect()` tracks AGAIN with a different context
4. Result: **2 acquisitions, 1 release** = LEAK!

### Problem 2: `sqlite3_shim.py::connect()`
```python
# Lines 18-27 in sqlite3_shim.py
def connect(dsn=None, *args, **kwargs):
    """Ignore legacy sqlite file paths and always use the Postgres DSN."""
    url = _resolve_dsn()
    return db_compat.connect(url, *args, **kwargs)  # ← Calls db_compat.connect() which tracks!
```

Same issue:
1. Tracking captures `"sqlite3_shim.py::connect"`
2. Then calls `db_compat.connect()` which tracks again
3. Result: **2 acquisitions, 1 release** = LEAK!

## The Solution

**Remove automatic tracking from `db_compat.connect()`**

The tracking should ONLY happen at the point where the connection request originates (in `get_db_connection()` functions), NOT in wrapper/helper functions.

### Changes Made:

1. ✅ **Removed tracking from `db_compat.connect()`**
   - Now it's just a simple connection factory
   - No automatic tracking = no double tracking from wrappers

2. ✅ **Re-added tracking to `get_db_connection()` functions**
   - These are the actual entry points where code requests connections
   - They track acquisition and attach `_tracking_context` + `_tracking_start`
   - When `conn.close()` is called, `CompatConnection.close()` calls `track_connection_released()`

### Files Updated:
1. `src/db_compat.py` - Removed automatic tracking from `connect()`
2. `src/routes/public_leaderboard.py` - Re-added tracking to `get_db_connection()`
3. `src/routes/rich_superadmin_interface1.py` - Re-added tracking to `get_db_connection()`
4. `src/routes/rich_admin_interface.py` - Re-added tracking to `get_db_connection()`
5. `src/routes/json_sports.py` - Re-added tracking to `get_db_connection()`
6. `src/routes/sportsbook_registration.py` - Re-added tracking to `get_db_connection()`
7. `src/routes/branding.py` - Re-added tracking to `get_db_connection()`
8. `src/routes/theme_customization.py` - Re-added tracking to `get_db_connection()`

## Expected Result After Fix:

```
✅ No more double tracking
✅ Wrapper functions won't create false leaks
✅ Each connection acquisition = 1 tracking acquisition
✅ Each connection release = 1 tracking release
✅ acquired == released (no leaks!)
```

## Key Insight

**Your question was CRITICAL!** You noticed that `db_compat.py::get_connection` and `sqlite3_shim.py::connect` weren't releasing anything, which led us to discover:

1. These are wrapper functions that call `db_compat.connect()`
2. When `connect()` had automatic tracking, it created double tracking
3. The "0 releases" wasn't a counting bug - it was showing that those specific contexts never released because they were just passing through to another function

This is why code review and questioning anomalies is so important! 🎯

