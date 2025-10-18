# Database Connection Leak Audit Files

## Overview
This folder contains all Python files that interact with the database. The main issue is **persistent, untracked database connections that don't drop to zero and keep increasing over time**.

## The Problem

### Symptoms:
- Active DB connections slowly grow from 3 to 8-15 over 8 hours
- Connection tracker shows "Active Now: 0" for all routes
- Connections are persistent and don't go down to 0
- They just keep increasing

### Root Causes Identified:

1. **Legacy `get_db_connection()` Pattern** (CRITICAL)
   - Files use `connect(use_pool=True)` which requires manual `conn.close()`
   - `track_connection_acquired()` is called when getting connection
   - BUT `track_connection_released()` is NOT called before `conn.close()`
   - Result: Connection tracking thinks connection is still active even after close

2. **SQLAlchemy ORM Calls** (FIXED in betting.py, bet_settlement_service.py, auth.py, tenant_auth.py)
   - Direct `current_app.db.session.query()` calls bypass connection tracking
   - `db.session.get()`, `db.session.add()`, `db.session.commit()` not tracked
   - Background workers using SQLAlchemy ORM outside Flask request context

3. **Health Endpoint SQLAlchemy Engines** (NEEDS FIX)
   - `/health/detailed` creates SQLAlchemy engines via `create_engine()`
   - These engines are never disposed
   - Each health check creates new untracked connections

## Files in This Audit

### CRITICAL - Need Immediate Fixes:

#### Routes with `get_db_connection()` Pattern:
1. **branding.py** - Most frequently called, missing tracking release
2. **public_leaderboard.py** - Missing `track_connection_released()` before `conn.close()`
3. **multitenant_routing.py** - Missing `track_connection_released()` before `conn.close()`
4. **theme_customization.py** - Missing tracking in `get_db_connection()` and release
5. **theme_customization1.py** - Backup file, same issues
6. **sportsbook_registration.py** - Missing tracking release
7. **sportsbook_registration1.py** - Backup file, same issues
8. **json_sports.py** - Missing tracking in `get_db_connection()`

#### Admin/Superadmin Routes (Lower Priority - Admin Only):
9. **comprehensive_admin.py** - Admin-only, potential leaks
10. **comprehensive_superadmin.py** - Superadmin-only, potential leaks
11. **rich_admin_interface.py** - Admin-only, potential leaks
12. **rich_superadmin_interface1.py** - Superadmin-only, potential leaks
13. **superadmin.py** - Superadmin-only, potential leaks
14. **tenant_admin.py** - Tenant admin, potential leaks

#### Health Monitoring:
15. **health.py** - Creates SQLAlchemy engines, never disposes them

### ALREADY FIXED:
16. **betting.py** - ✅ All SQLAlchemy ORM calls replaced with `connection_ctx()`
17. **bet_settlement_service.py** - ✅ All SQLAlchemy ORM calls replaced with `connection_ctx()`
18. **auth.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`
19. **tenant_auth.py** - ✅ SQLAlchemy ORM calls replaced with `connection_ctx()`

### ALREADY CORRECT (Using connection_ctx properly):
20. **web3_operator_wallet_service.py** - ✅ Uses `connection_ctx()` correctly
21. **web3_sync_service.py** - ✅ Uses `connection_ctx()` correctly
22. **web3_reset_service.py** - ✅ Uses `connection_ctx()` correctly

### Core Infrastructure:
23. **db_compat.py** - Database compatibility layer and connection pooling
24. **main.py** - Flask app initialization, imports tracking
25. **connection_tracker.py** - Connection tracking utility
26. **sqlalchemy_tracking.py** - SQLAlchemy connection tracking
27. **sqlalchemy_session_tracker.py** - SQLAlchemy session tracking
28. **sqlalchemy_monkey_patch.py** - Monkey patches SQLAlchemy to auto-track

## Required Fixes

### Fix Pattern for `get_db_connection()` Files:

#### Step 1: Add tracking to `get_db_connection()` function:
```python
def get_db_connection():
    """Get database connection from pool - caller MUST call conn.close()"""
    from src.db_compat import connect
    from src.utils.connection_tracker import track_connection_acquired
    
    # Track this connection acquisition
    context, track_start = track_connection_acquired("filename.py::get_db_connection")
    conn = connect(use_pool=True)
    conn._tracking_context = context
    conn._tracking_start = track_start
    return conn
```

#### Step 2: Add tracking release before EVERY `conn.close()`:
```python
finally:
    if conn:
        # Release tracking before closing connection
        if hasattr(conn, '_tracking_context') and hasattr(conn, '_tracking_start'):
            from src.utils.connection_tracker import track_connection_released
            track_connection_released(conn._tracking_context, conn._tracking_start)
        conn.close()
```

### Fix Pattern for Health Endpoints:

In `health.py`, replace SQLAlchemy engine creation with proper disposal:
```python
# BEFORE:
engine = create_engine(DATABASE_URL)
# ... use engine ...

# AFTER:
engine = create_engine(DATABASE_URL)
try:
    # ... use engine ...
finally:
    engine.dispose()  # CRITICAL: Dispose engine to close connections
```

## Testing After Fixes

1. Deploy fixes
2. Monitor `/health/dashboard`
3. Check:
   - Active connections should drop to 3 (base connections)
   - Connection tracker should show actual route usage
   - After 8 hours, connections should NOT increase beyond expected load

## Priority Order

1. **URGENT**: Fix `branding.py` (most frequently called)
2. **HIGH**: Fix `public_leaderboard.py`, `multitenant_routing.py`, `json_sports.py`
3. **HIGH**: Fix `health.py` SQLAlchemy engine disposal
4. **MEDIUM**: Fix `theme_customization.py`, `sportsbook_registration.py`
5. **LOW**: Fix admin-only routes (low traffic)

## Notes

- DO NOT use `replace_all` for indentation-sensitive code
- Fix files one at a time to avoid syntax errors
- Test after each fix
- The pattern is simple but MUST be applied correctly to every `conn.close()` call

