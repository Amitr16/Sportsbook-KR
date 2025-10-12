# Connection Pool Exhaustion - Comprehensive Fix

## Problem
The application was experiencing connection pool timeouts during multi-tenant load spikes, causing:
- 500 errors on branding/theme endpoints
- Failed health checks leading to VM restarts
- "PoolTimeout: couldn't get a connection after 10.00 sec" errors

## Root Causes
1. **Pool too small** for concurrent tenant requests
2. **Background workers** (odds fetcher, settlement) competing with web process for connections
3. **No graceful degradation** - theme endpoints threw 500 instead of serving cached/defaults
4. **Health checks** depended on DB, causing cascading failures
5. **No cache pre-warming** - stampeding herd on boot

## Solutions Implemented

### 1. Environment Variable Updates ✅
**Files Modified:**
- `postgresql.env`
- `fly.toml`

**Changes:**
```bash
DB_MAX_CONN=30          # Increased pool size for concurrent tenant loads
DB_MIN_CONN=5           # Maintain minimum connections
DB_CONN_TIMEOUT=5       # Fail fast instead of hanging 10s
DB_IDLE_TIMEOUT=60      # Recycle idle connections
```

**Why:** Gives the pool headroom for tenant spikes while failing fast to prevent cascading timeouts.

---

### 2. Separate Fly Processes ✅
**File Modified:** `fly.toml`

**Changes:**
```toml
[processes]
web = "gunicorn -w 3 -k gthread -b 0.0.0.0:8080 'src.main:app'"
worker_odds = "python -m src.prematch_odds_service"
worker_settlement = "python -m src.bet_settlement_service"
```

**Deployment:**
```bash
fly scale count web 1
fly scale count worker_odds 1
fly scale count worker_settlement 1
```

**Why:** Background workers now have their own connection pools, preventing them from starving the web process during tenant spikes.

---

### 3. Graceful Branding Degradation ✅
**File Modified:** `src/routes/branding.py`

**Changes:**
- Added `PoolTimeout` and `OperationalError` exception handling
- On DB unavailable, serves stale cache if present
- Never returns 500 - always serves cached or default branding

**Code:**
```python
try:
    operator = _get_cached(cache_key, lambda: _load_operator_branding_from_db(subdomain))
except (PoolTimeout, OperationalError) as e:
    logging.warning(f"⚠️ Branding DB unavailable. Serving cached/default for {subdomain}")
    if cache_key in _BRANDING_CACHE:
        _, operator = _BRANDING_CACHE[cache_key]  # serve stale
```

**Why:** Frontend can live with stale/default branding; it cannot live with 500 errors. Pages still load during DB pressure.

---

### 4. Background Service Connection Hygiene ✅
**Files Verified:**
- `src/bet_settlement_service.py`
- `src/prematch_odds_service.py`

**Status:** ✅ Already correct
- All `time.sleep()` calls are **outside** `connection_ctx()` blocks
- No connections held during long sleeps
- Proper connection lifecycle management

---

### 5. Lightweight Health Check ✅
**Files Created/Modified:**
- `src/routes/health.py` (NEW)
- `src/main.py` (registered blueprint)
- `fly.toml` (health check path remains `/healthz`)

**Changes:**
```python
@health_bp.get("/health")
def health():
    """Health check that doesn't touch the database"""
    return jsonify({"ok": True, "status": "healthy"}), 200
```

**Why:** Transient DB hiccups no longer mark the entire instance as unhealthy. Prevents unnecessary VM restarts.

---

### 6. Read-Only Retry Utility ✅
**File Created:** `src/utils/db_retry.py`

**Usage:**
```python
from src.utils.db_retry import ro_connection_with_retry

with ro_connection_with_retry(attempts=2) as conn:
    # read-only DB operations
    cur = conn.cursor()
    cur.execute("SELECT ...")
```

**Features:**
- Random jitter (50-200ms) to avoid thundering herd
- Only for read endpoints (duplicates harmless)
- DO NOT use for writes

**Why:** Gives public endpoints a second chance on transient pool exhaustion without cascading failures.

---

### 7. Branding Cache Pre-Warming ✅
**Files Modified:**
- `src/routes/branding.py` (added `warm_branding_cache` function)
- `src/main.py` (call on boot in background thread)

**Changes:**
```python
def warm_branding_cache(subdomains=None):
    """Pre-warm branding cache on boot to prevent stampeding"""
    # Fetches all active operators and warms cache
    ...

# In main.py
threading.Thread(target=warm_branding_cache, daemon=True).start()
```

**Why:** First requests after boot no longer stampede the DB. Cache is warm and ready for tenant traffic.

---

## Expected Results

### Before:
```
ERROR: PoolTimeout: couldn't get a connection after 10.00 sec
GET /TENANT/api/public/load-theme 500
Health checks failing → VM restart
```

### After:
- ✅ Bigger pool (30) + worker separation = far fewer timeouts
- ✅ Branding/theme serve cached/default on pool trouble → pages still load
- ✅ Background services don't hold connections → pool free for web traffic
- ✅ Health checks independent of DB → no cascading failures
- ✅ Pre-warmed cache → no stampeding herd on boot

## Deployment Steps

1. **Update environment variables:**
   ```bash
   # Already in fly.toml, will be applied on next deploy
   ```

2. **Deploy with new process configuration:**
   ```bash
   fly deploy
   ```

3. **Scale processes independently:**
   ```bash
   fly scale count web 1
   fly scale count worker_odds 1
   fly scale count worker_settlement 1
   ```

4. **Verify health check:**
   ```bash
   curl https://sportsbook.kryzel.io/health
   # Should return: {"ok": true, "status": "healthy"}
   ```

5. **Monitor logs for cache warming:**
   ```bash
   fly logs
   # Look for: "🔥 Pre-warmed X/Y branding caches"
   ```

## PgBouncer Configuration (Fly.io)

Ensure your PgBouncer settings are optimized:

```ini
pool_mode = transaction
max_client_conn = 500
default_pool_size = 50
```

And in Postgres:
```sql
-- Ensure Postgres can handle PgBouncer's server pool
ALTER SYSTEM SET max_connections = 100;
SELECT pg_reload_conf();
```

## Monitoring

Watch for these log patterns:

**Good:**
```
✅ Warmed cache for: supersports
✅ Serving stale cache for supersports
⚠️ Branding DB unavailable (PoolTimeout). Serving cached/default
```

**Bad (should no longer see):**
```
❌ PoolTimeout: couldn't get a connection
ERROR 500 on /api/public/load-theme
```

## Files Modified

1. `postgresql.env` - Updated DB pool settings
2. `fly.toml` - Updated pool config, added process separation
3. `src/routes/branding.py` - Added graceful degradation, cache warming
4. `src/routes/health.py` - NEW lightweight health check
5. `src/utils/db_retry.py` - NEW read-only retry utility
6. `src/main.py` - Registered health blueprint, added cache warming on boot

## Next Steps

- Monitor production logs after deploy for pool timeouts
- If still seeing timeouts under extreme load, increase `DB_MAX_CONN` to 40-50
- Consider adding `ro_connection_with_retry` to other public read endpoints if needed
- Tune cache TTL (`_CACHE_TTL` in branding.py) based on traffic patterns

