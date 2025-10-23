# Casino API Connection Leak - Summary & Fix

## Root Cause Found ✅

**Location:** `src/routes/casino_api.py` (1691 lines)

**Issue:** 12 endpoints use `get_tracked_connection()` but many lack `finally` blocks to ensure `conn.close()` is called when errors occur.

## Evidence from Health Check:
```
"UNTRACKED:db_compat.py::get_connection:L861"
  acquired: 108
  released: 0   ← 108 connections NEVER closed!
```

This traces to `casino_api.py` → `get_tracked_connection()` → `get_connection()` → `connect()`

## Fixes Applied So Far:

### 1. `/user-info` endpoint (Line 473) ✅ FIXED
- Added `conn = None` before try
- Added `finally` block with `conn.close()`

### 2. `/balance` endpoint (Line 548) ✅ FIXED  
- Moved `conn = None` outside inner try block
- Already had `finally` block but `conn` was out of scope

## Remaining Endpoints That Need Fixing:

3. `/slots/bet` - Line 609 (needs finally)
4. Slots game round storage - Line 682 (needs finally)  
5. `/play/slots-20` - Line 759 (needs finally)
6. `/play/roulette/history` - Line 867 (needs finally)
7. `/play/blackjack` - Line 962 (needs finally)
8. `/play/roulette` - Line 1380 (needs finally)
9. `/play/crash` - Line 1495 (needs finally)
10. `/play/crash/history` - Line 1591 (needs finally)
11. `/game-history` - Line 1686 (needs finally)

## Quick Fix Options:

### Option A: Add Finally Blocks (Surgical - Recommended)
For each endpoint, wrap in:
```python
conn = None
try:
    conn = get_tracked_connection()
    # ... existing code ...
finally:
    if conn:
        try:
            conn.close()
        except:
            pass
```

### Option B: Convert to connection_ctx() (Cleaner Long-term)
Replace all `get_tracked_connection()` with `connection_ctx()`:
```python
from src.db_compat import connection_ctx
with connection_ctx(timeout=5) as conn:
    # ... existing code ...
# Auto-closes, no finally needed!
```

## Recommendation

**For Now:** Apply Option A to all 9 remaining endpoints (surgical fix)

**For Later:** Refactor casino_api.py to use `connection_ctx()` throughout

## Expected Result After Fix:

```
"casino_api.py::get_tracked_connection"
  acquired: ~120
  released: ~120  ✅ All released!
  leaks: 0  ✅
```

Tracking discrepancy should drop from `-101` to near `0`.

