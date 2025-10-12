# Deployment Checklist - Pool Exhaustion Fixes

## Pre-Deployment

- [x] All 7 fixes implemented
- [x] No linting errors
- [x] Environment variables updated
- [x] Fly.toml updated with process separation
- [x] Health check endpoint added
- [x] Graceful degradation in branding
- [x] Cache pre-warming added
- [x] Retry utility created

## Deployment Commands

### 1. Deploy to Fly.io
```bash
fly deploy
```

### 2. Scale Processes
```bash
# Scale web process
fly scale count web 1

# Scale background workers
fly scale count worker_odds 1
fly scale count worker_settlement 1
```

### 3. Verify Health Check
```bash
curl https://sportsbook.kryzel.io/health
# Expected: {"ok": true, "status": "healthy"}
```

## Post-Deployment Verification

### 4. Check Logs
```bash
fly logs

# Look for:
# ✅ "🔥 Pre-warmed X/Y branding caches"
# ✅ "✅ Warmed cache for: [subdomain]"
# ❌ NO "PoolTimeout: couldn't get a connection"
```

### 5. Test Multi-Tenant Load
```bash
# Test multiple subdomains simultaneously
curl https://sportsbook.kryzel.io/supersports
curl https://sportsbook.kryzel.io/sportsking
curl https://sportsbook.kryzel.io/sportsplaces

# All should return 200, no 500s
```

### 6. Verify Branding Endpoints
```bash
# Test public theme endpoint
curl https://sportsbook.kryzel.io/supersports/api/public/load-theme

# Should return theme data, not 500
```

### 7. Monitor for 24 Hours
```bash
# Watch for any pool timeouts
fly logs | grep -i "pooltimeout"

# Should see very few or none
```

## Rollback Plan (if needed)

```bash
# If issues arise, rollback to previous deployment
fly releases list
fly rollback [PREVIOUS_VERSION]
```

## Success Criteria

- ✅ No `PoolTimeout` errors in logs
- ✅ All tenant pages load (200 status)
- ✅ Health checks passing
- ✅ Branding/theme endpoints return data (even under load)
- ✅ No VM restarts due to failed health checks
- ✅ Cache warming completes on boot

## If You Still See Timeouts

1. **Increase pool size:**
   ```bash
   fly secrets set DB_MAX_CONN=40
   fly deploy
   ```

2. **Check PgBouncer settings:**
   - Ensure `pool_mode = transaction`
   - Ensure `default_pool_size >= 50`

3. **Check Postgres max_connections:**
   ```sql
   SHOW max_connections;
   -- Should be >= 100
   ```

4. **Add retry to more endpoints:**
   - Use `ro_connection_with_retry` from `src/utils/db_retry.py`
   - Only for read-only public endpoints

## Notes

- Background workers now have separate pools - they won't starve web traffic
- Branding will serve stale cache on DB issues - better than 500s
- Health check is lightweight - won't fail on DB hiccups
- Cache pre-warming reduces stampeding herd on boot

## Contact

If issues persist after all fixes:
1. Check Fly.io dashboard for resource utilization
2. Review PgBouncer logs
3. Consider horizontal scaling (more web instances)

