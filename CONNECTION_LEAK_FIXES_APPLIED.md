# Database Connection Leak Fixes Applied

## Summary
Based on the comprehensive audit, this document tracks all fixes applied to eliminate connection leaks and pool creep.

---

## ✅ **Fixes Applied So Far**

### 1. **URGENT: Fixed Risky Functions** (COMPLETED)
These functions had early returns before `conn.close()` and were identified as the primary source of hourly connection creep.

#### `src/routes/theme_customization.py`:
- ✅ **`load_theme()`** - Converted to `connection_ctx()`, removed manual `conn.close()`
  - **Issue**: Early return at line 212 before `conn.close()` at line 254
  - **Fix**: Wrapped in `with connection_ctx()` - connection automatically released
  
- ✅ **`save_theme_for_operator()`** - Converted to `connection_ctx()`, removed manual `conn.commit()` and `conn.close()`
  - **Issue**: Multiple paths, transaction management, manual close
  - **Fix**: `connection_ctx()` handles transactions and cleanup automatically

#### `src/routes/theme_customization1.py`:
- ✅ **`load_theme()`** - Converted to `connection_ctx()`
  - **Issue**: Early return at line 223 before `conn.close()` at line 265
  - **Fix**: Wrapped in `with connection_ctx()` - connection automatically released

- ✅ **`save_theme_for_operator()`** - Converted to `connection_ctx()`
  - **Issue**: Early returns at lines 314-315 before `conn.close()` at line 379
  - **Fix**: `connection_ctx()` handles all cleanup paths

- ✅ **`get_theme_css()`** - Converted to `connection_ctx()`
  - **Issue**: Early return at line 400-401 before `conn.close()` at line 483
  - **Fix**: `connection_ctx()` ensures connection is released even on early returns

---

## 🔄 **Pending Fixes**

### 2. **Convert Remaining 11 Files from `get_db_connection()` to `connection_ctx()`**

These files still use manual connection handling and need conversion:

#### High Priority:
- `src/routes/branding.py` - Most frequently called route
- `src/routes/public_leaderboard.py`
- `src/routes/multitenant_routing.py`
- `src/routes/json_sports.py`
- `src/routes/sportsbook_registration.py`
- `src/routes/sportsbook_registration1.py`

#### Lower Priority (Admin-only):
- `src/routes/comprehensive_admin.py`
- `src/routes/comprehensive_superadmin.py`
- `src/routes/rich_admin_interface.py`
- `src/routes/rich_superadmin_interface1.py`
- `src/routes/superadmin.py`
- `src/routes/tenant_admin.py`

### 3. **Health UI Fix: Show `checked_out` Instead of `pool_size`**
- **File**: `src/routes/health_dashboard.py`
- **Change**: Update JavaScript to use `db.checked_out` for "Active Connections" card
- **Add**: Separate display for "Open Sockets (Pool)" using `db.pool_size`
- **Purpose**: Stop false "leak" panic - show actual in-use connections

### 4. **Pool Configuration: Let Pool Shrink**
- **Environment Variables to Set**:
  ```
  DB_POOL_MIN=0            # Let pool go down to zero when idle
  DB_POOL_MAX_IDLE=60      # Reap idle connections after 60 seconds
  DB_POOL_MAX_LIFETIME=600 # Optional: Churn sockets every 10 minutes
  ```
- **Effect**: Pool will visibly shrink during quiet periods instead of holding sockets forever

### 5. **Add `leaked_recovered` Metric to Health JSON**
- **File**: `src/routes/health.py`
- **Purpose**: Surface count of connections recovered by GC finalizer
- **Metric**: If > 0 over 5-10 min window, indicates manual paths still missing fixes

---

## 🎯 **Expected Results After All Fixes**

1. **"Active Connections" on health UI will accurately show `checked_out` (0 when idle)**
2. **"Open Sockets (Pool)" will show `pool_size` (will shrink to 0-3 during quiet periods)**
3. **Hourly +1-2 connection creep will STOP** (risky functions are now fixed)
4. **`leaked_recovered` metric will be 0** (no GC cleanup needed)

---

## 📋 **Fix Pattern Used**

### Before (Manual - Leak Prone):
```python
def some_route():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT ...")
        # Early return HERE = leak!
        if some_condition:
            return jsonify({...})
        ...
        return jsonify({...})
    except:
        return error
    finally:
        if conn:
            conn.close()  # Never reached if early return!
```

### After (Context Manager - Leak Proof):
```python
def some_route():
    from src.db_compat import connection_ctx
    try:
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3000ms'")
                cur.execute("SELECT ...")
                # Early return is SAFE - context manager cleans up!
                if some_condition:
                    return jsonify({...})
                ...
                return jsonify({...})
    except:
        return error
```

**Key Difference**: `connection_ctx()` guarantees cleanup on ALL exit paths (return, exception, break, etc.)

---

## 🔬 **Root Cause Analysis**

### What We Thought Was Happening:
- "Active connections" growing = connection leak

### What Was Actually Happening:
1. **Pool Size vs Checked Out Confusion**: 
   - Health UI showed `pool_size` (total open sockets) as "Active Connections"
   - Reality: `checked_out` was 0 (no leak)
   - Pool holds sockets open for reuse, doesn't shrink without config changes

2. **Real Leak (Small but Real)**:
   - Theme customization functions had early returns before `conn.close()`
   - Each call leaked a socket temporarily (until GC finalizer ran)
   - With traffic, this caused +1-2 connections/hour creep
   - GC safety net prevented runaway leak, but connections stayed in pool

3. **Pool Doesn't Shrink by Default**:
   - `DB_POOL_MIN=2` kept at least 2 sockets open always
   - `DB_POOL_MAX_IDLE=300` (5 min) was too long for sporadic traffic
   - Pool grew with bursts, never shrank back down

---

## ✅ **Next Steps**
1. Continue converting remaining 11 files to `connection_ctx()`
2. Update health UI to show accurate metrics
3. Set pool environment variables
4. Add `leaked_recovered` monitoring
5. Deploy and monitor - should see pool stabilize at 0-3 connections during quiet periods

