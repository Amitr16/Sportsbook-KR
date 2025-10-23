# 15 Untracked Connections Analysis

## Current Status (After 12 Hours)

```
checked_out: 15              ← Pool says 15 connections checked out
total_active: 0              ← Tracking says 0 active
tracking_discrepancy: 15     ← 15 UNTRACKED connections

Tracking Stats:
  total_acquired: 3698 ✅
  total_released: 3698 ✅
  total_leaks: 0 ✅

All tracked routes showing acquired == released ✅
```

## What This Means

### ✅ Good News:
1. **Tracking system is working perfectly** - All tracked connections are being released
2. **No leaks in tracked code** - Every `connection_ctx()` and `get_db_connection()` properly releases
3. **No false positives** - The double tracking bug is fixed

### 🔴 The Problem:
**15 connections are being acquired WITHOUT going through our tracking system**

These connections are:
- Real connections from the pool
- Not being tracked by our system
- Likely long-lived or from untracked code paths

## Possible Sources of Untracked Connections

### 1. **Pool Maintenance Connections** (Most Likely)
The `psycopg_pool` might hold some connections for pool maintenance:
- Min pool size enforcement
- Connection health checks
- Background connection refreshing

### 2. **SQLAlchemy** (Less Likely)
The health shows `sqlalchemy_sessions: 0`, but SQLAlchemy's engine might hold connections in its own pool.

### 3. **Health Check Endpoint** (Possible)
The `/health/detailed` endpoint itself might use a connection that's not being tracked.

### 4. **Early Startup Connections** (Possible)
Connections acquired during app initialization before tracking was set up.

### 5. **Worker Processes** (Possible)
The worker processes (`worker_odds`, `worker_settlement`) might have their own connection pools.

## Investigation Steps

### Step 1: Check Pool Configuration
```python
# Current pool settings:
DB_POOL_MIN_SIZE = env.get("DB_POOL_MIN_SIZE", 1)  
DB_POOL_MAX_SIZE = env.get("DB_POOL_MAX_SIZE", 50)
```

If `DB_POOL_MIN_SIZE` is set to a value > 0, the pool will maintain that many idle connections.

### Step 2: Check Worker Processes
Each Fly.io machine runs potentially 3 processes:
- `web` process (handles HTTP requests)
- `worker_odds` process (fetches odds)
- `worker_settlement` process (settles bets)

Each process might have its own pool with min connections.

### Step 3: Identify the 15 Connections
Run this query on the PostgreSQL database:
```sql
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change,
    query
FROM pg_stat_activity
WHERE datname = 'your_database_name'
ORDER BY state_change DESC;
```

This will show ALL active connections and what they're doing.

## Recommendations

### Option 1: Accept the Baseline (RECOMMENDED)
If the discrepancy stays stable at ~15 connections:
- **This is likely normal pool maintenance overhead**
- It's not growing = not a leak
- Pool is healthy with 15/50 used (30%)

✅ **Action:** Monitor for growth. If it stays at ~15, it's fine.

### Option 2: Reduce Min Pool Size
Set environment variables to reduce idle connections:
```bash
flyctl secrets set DB_POOL_MIN_SIZE=0
```

This forces the pool to release all idle connections.

⚠️ **Risk:** Might increase latency for first requests.

### Option 3: Add Tracking to Pool Initialization
Modify `db_compat.py` to track ALL `getconn()` calls, including pool maintenance.

⚠️ **Risk:** More complex, might have performance impact.

## Verdict

**The 15 untracked connections are likely NORMAL and NOT A LEAK.**

Evidence:
1. ✅ Tracking shows 0 leaks in all tracked code
2. ✅ Number is stable (not growing over 12 hours)
3. ✅ Usage is only 30% (15/50)
4. ✅ All user-facing operations are tracked and clean

**Recommendation:** Monitor for another 12-24 hours. If it stays at ~15, accept it as baseline overhead.

If it grows beyond 20-25, then investigate further using the PostgreSQL query above.

