# Connection Leak Fixes - Deployment Plan

## ✅ **Phase 1: URGENT Fixes (COMPLETED)**
**Status**: ✅ Done
**Files Fixed**: 
- `src/routes/theme_customization.py` (2 functions)
- `src/routes/theme_customization1.py` (3 functions)

**Impact**: Stops hourly +1-2 connection creep from risky functions

---

## 🚀 **Phase 2: Quick Wins (Deploy These Now)**

### Fix 2A: Update Health UI (5 min)
**File**: `src/routes/health_dashboard.py`

**Change 1** - Line ~380 (JavaScript):
```javascript
// BEFORE:
document.getElementById('dbActive').textContent = db.pool_size;

// AFTER:
document.getElementById('dbActive').textContent = db.checked_out;
```

**Change 2** - Add new metric display in HTML (after line ~320):
```html
<div class="metric">
    <span class="metric-label">Pool Sockets (Total Open)</span>
    <span class="metric-value" id="dbPoolSize">-</span>
</div>
```

**Change 3** - Add to JavaScript (after line ~385):
```javascript
document.getElementById('dbPoolSize').textContent = db.pool_size;
```

**Result**: Dashboard shows accurate "in-use" vs "open sockets" counts

---

### Fix 2B: Pool Environment Variables (2 min)
**Platform**: Fly.io

**Commands**:
```bash
fly secrets set DB_POOL_MIN=0
fly secrets set DB_POOL_MAX_IDLE=60
fly secrets set DB_POOL_MAX_LIFETIME=600
```

**Result**: Pool will shrink during quiet periods instead of growing forever

---

### Fix 2C: Add Leaked Recovery Metric (10 min)
**File**: `src/routes/health.py`

**In `/health/detailed` endpoint**, add after line ~150:
```python
# Get leaked connection recovery count from GC finalizer
try:
    from src.db_compat import get_leaked_recovery_count
    leaked_recovered = get_leaked_recovery_count()
except:
    leaked_recovered = 0

health_data["checks"]["database_pool"]["leaked_recovered"] = leaked_recovered
```

**File**: `src/db_compat.py`

**Add this global counter near the top**:
```python
_leaked_recovery_count = 0
_leaked_recovery_lock = threading.Lock()

def get_leaked_recovery_count():
    """Get count of connections recovered by GC finalizer"""
    global _leaked_recovery_count
    with _leaked_recovery_lock:
        return _leaked_recovery_count
```

**Update GC finalizer** (find `def _finalizer(conn):` around line ~130):
```python
def _finalizer(conn):
    """Safety net: return leaked connection to pool via GC"""
    global _leaked_recovery_count
    try:
        if conn and not conn.closed:
            with _leaked_recovery_lock:
                _leaked_recovery_count += 1  # INCREMENT COUNTER
            logger.warning("⚠️ GC finalizer returned leaked DB connection to pool (count: %d)", _leaked_recovery_count)
            conn.close()
    except Exception as e:
        logger.error(f"Error in connection finalizer: {e}")
```

**Result**: Health endpoint shows how many connections were leaked (should be 0 after all fixes)

---

## 🔧 **Phase 3: Remaining File Conversions (Can Do Later)**

These 11 files still use `get_db_connection()`. They're **lower risk** than the theme files we fixed, but should still be converted for consistency:

### High Priority (Public Routes):
1. `src/routes/branding.py` - Most called route
2. `src/routes/public_leaderboard.py`
3. `src/routes/multitenant_routing.py`
4. `src/routes/json_sports.py`
5. `src/routes/sportsbook_registration.py`
6. `src/routes/sportsbook_registration1.py`

### Low Priority (Admin-Only):
7. `src/routes/comprehensive_admin.py`
8. `src/routes/comprehensive_superadmin.py`
9. `src/routes/rich_admin_interface.py`
10. `src/routes/rich_superadmin_interface1.py`
11. `src/routes/superadmin.py`
12. `src/routes/tenant_admin.py`

**Pattern to use**: Same as theme files - replace `get_db_connection()` with `connection_ctx()`

---

## 📊 **Expected Timeline**

| Phase | Duration | Impact |
|-------|----------|--------|
| Phase 1 (DONE) | ✅ Complete | Stops risky function leaks |
| Phase 2A (UI) | 5 min | Accurate dashboard |
| Phase 2B (Env) | 2 min | Pool shrinks properly |
| Phase 2C (Metric) | 10 min | Leak monitoring |
| **DEPLOY & TEST** | 1 hour | Verify fixes work |
| Phase 3 | 2-4 hours | Convert remaining files |

---

## ✅ **Success Criteria**

After Phase 1 + Phase 2 deployment:
1. ✅ Health UI "Active Connections" shows 0 when idle (not 8-15)
2. ✅ "Pool Sockets" drops to 0-3 after 60 seconds of idle time
3. ✅ No hourly connection creep over 8 hours
4. ✅ `leaked_recovered` metric stays at 0

---

## 🚨 **Critical: What to Monitor**

### First 24 Hours After Deployment:
1. **Dashboard Metrics**:
   - Active Connections (should be 0 when idle)
   - Pool Sockets (should shrink to 0-3 when idle)
   - Leaked Recovered (should stay 0)

2. **Connection Tracker Table**:
   - All routes should show "Active Now: 0" when idle
   - No persistent non-zero values

3. **Application Logs**:
   - No "GC finalizer returned leaked DB connection" warnings
   - If you see these warnings, it means there are still unfixed manual connection paths

### If Issues Persist:
- Check `leaked_recovered` metric - if > 0, there are still manual paths leaking
- Review connection tracker to identify which routes/functions
- Apply Phase 3 fixes to those specific files

---

## 📝 **Rollback Plan**

If issues occur after deployment:

1. **Revert env variables**:
   ```bash
   fly secrets unset DB_POOL_MIN
   fly secrets unset DB_POOL_MAX_IDLE
   fly secrets unset DB_POOL_MAX_LIFETIME
   ```

2. **Revert theme files from git**:
   ```bash
   git checkout HEAD -- src/routes/theme_customization.py
   git checkout HEAD -- src/routes/theme_customization1.py
   ```

3. **Redeploy**

---

## 🎯 **Next Steps**

1. **Review** this plan and `CONNECTION_LEAK_FIXES_APPLIED.md`
2. **Apply** Phase 2A, 2B, 2C fixes (15 minutes total)
3. **Deploy** to Fly.io
4. **Monitor** for 24 hours using success criteria
5. **Apply** Phase 3 conversions if needed (likely not urgent after Phase 1+2)

