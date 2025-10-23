# Double Tracking Bug Fix

## Problem Discovered
After deploying the enhanced tracking system, health check showed:
```
"checked_out": 3
"total_active": 528         🔴 MASSIVELY INCORRECT!
"total_leaks": 487          🔴 FALSE LEAKS!
"tracking_discrepancy": -525 🔴 NEGATIVE!

Top "leaker":
public_leaderboard.py::get_db_connection
  acquired: 932
  released: 466
  leaks: 466  🔴
```

## Root Cause
**DOUBLE TRACKING!** Every connection was being tracked TWICE:

1. In `get_db_connection()` functions:
   ```python
   context, track_start = track_connection_acquired("file.py::get_db_connection")
   conn = connect(use_pool=True)  # ← This also tracks!
   ```

2. Inside `db_compat.connect()`:
   ```python
   context, track_start = track_connection_acquired(context)  # ← TRACKED AGAIN!
   ```

Result: Every `get_db_connection()` call resulted in **2 tracking acquisitions** but only **1 release**, creating false leaks.

## Solution
Remove manual tracking from `get_db_connection()` functions that call `db_compat.connect(use_pool=True)` since `connect()` now handles tracking automatically.

### Files to Fix:
1. ✅ `src/routes/public_leaderboard.py` - FIXED
2. `src/routes/rich_superadmin_interface1.py`
3. `src/routes/rich_admin_interface.py`
4. `src/routes/json_sports.py`
5. `src/routes/sportsbook_registration.py`
6. `src/routes/branding.py`
7. `src/routes/theme_customization.py`

### Change Pattern:
```python
# BEFORE (DOUBLE TRACKING):
def get_db_connection():
    from src.db_compat import connect
    from src.utils.connection_tracker import track_connection_acquired
    context, track_start = track_connection_acquired("file.py::get_db_connection")
    conn = connect(use_pool=True)  # This ALSO tracks!
    conn._tracking_context = context
    conn._tracking_start = track_start
    return conn

# AFTER (SINGLE TRACKING):
def get_db_connection():
    from src.db_compat import connect
    # connect() now handles tracking automatically with proper caller context
    return connect(use_pool=True)
```

### Files Using sqlite3.connect() - KEEP TRACKING:
These don't use `db_compat.connect()`, so they still need manual tracking:
- `src/routes/multitenant_routing.py` - Uses `sqlite3.connect()`
- `src/routes/comprehensive_superadmin.py` - Uses `sqlite3.connect()`
- `src/routes/sportsbook_registration1.py` - Uses `sqlite3.connect(DATABASE_PATH)`
- `src/routes/superadmin.py` - Uses `sqlite3.connect(DATABASE_PATH)`
- `src/routes/tenant_admin.py` - Uses `sqlite3.connect(DATABASE_PATH)`
- `src/routes/comprehensive_admin.py` - Uses `sqlite3.connect()`
- `src/routes/theme_customization1.py` - Custom logic

## Expected Result After Fix:
```
"checked_out": 2-4
"total_active": 2-4         ✅ Should match checked_out
"total_leaks": 0            ✅ No false leaks
"tracking_discrepancy": 0   ✅ All connections tracked
```

