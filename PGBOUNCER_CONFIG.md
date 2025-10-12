# PgBouncer Configuration Recommendations

## Overview
This document provides recommended PgBouncer configuration settings for optimal connection pooling with the Flask application.

## Recommended Settings

### PgBouncer Configuration (`pgbouncer.ini`)

```ini
[databases]
* = host=YOUR_POSTGRES_HOST port=5432 dbname=YOUR_DATABASE

[pgbouncer]
# Connection pool mode - TRANSACTION is recommended for stateless web apps
pool_mode = transaction

# Maximum number of client connections to PgBouncer
# Should be higher than total app connections across all instances
max_client_conn = 500

# Maximum number of server connections per database
# Should match or slightly exceed DB_MAX_CONN * number_of_app_instances
default_pool_size = 50

# Maximum number of additional connections that can be established
reserve_pool_size = 10

# Maximum time to wait for a connection (seconds)
query_wait_timeout = 600

# Close server connections that have been idle for this long (seconds)
server_idle_timeout = 600

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
```

## PostgreSQL Configuration

Ensure your PostgreSQL server has sufficient connections:

```sql
-- Check current max_connections
SHOW max_connections;

-- Set max_connections (requires restart)
-- Should be >= PgBouncer default_pool_size + reserve_pool_size + buffer
ALTER SYSTEM SET max_connections = 100;

-- Apply changes (requires restart)
SELECT pg_reload_conf();
```

## Application Environment Variables

### Production (Fly.io) - Already configured in `fly.toml`:
```bash
DB_MAX_CONN=30           # Maximum connections in app pool
DB_CONN_TIMEOUT=5        # Connection acquisition timeout (seconds)
DB_POOL_MIN=4            # Minimum idle connections
DB_POOL_MAX=30           # Maximum total connections
DB_POOL_TIMEOUT=5        # Same as DB_CONN_TIMEOUT for consistency
DB_POOL_MAX_LIFETIME=1800 # Connection lifetime (30 minutes)
DB_POOL_MAX_IDLE=300     # Idle connection timeout (5 minutes)
```

### Local Development - Already configured in `postgresql.env`:
```bash
DB_MAX_CONN=30
DB_CONN_TIMEOUT=5
DB_POOL_MIN=1
DB_POOL_MAX=30
DB_POOL_TIMEOUT=5
DB_POOL_MAX_LIFETIME=1800
DB_POOL_MAX_IDLE=300
```

## Connection Math

For a proper setup:

1. **App Pool Size**: `DB_MAX_CONN = 30` per instance
2. **Total App Connections**: `30 × number_of_instances`
3. **PgBouncer Pool**: `default_pool_size = 50` (handles 1-2 app instances comfortably)
4. **PostgreSQL Max**: `max_connections = 100+` (handles PgBouncer + admin connections)

## Fly.io Specific Settings

If using Fly.io's managed Postgres with PgBouncer, set these secrets:

```bash
# Set PgBouncer configuration via Fly secrets
fly secrets set PGBOUNCER_POOL_MODE=transaction
fly secrets set PGBOUNCER_DEFAULT_POOL_SIZE=50
fly secrets set PGBOUNCER_RESERVE_POOL_SIZE=10
fly secrets set PGBOUNCER_MAX_CLIENT_CONN=500
fly secrets set PGBOUNCER_QUERY_WAIT_TIMEOUT=600
```

## Monitoring

### Check PgBouncer Status
```bash
# Connect to PgBouncer admin console
psql -p 6432 -U pgbouncer -h your-pgbouncer-host pgbouncer

# Show pools
SHOW POOLS;

# Show clients
SHOW CLIENTS;

# Show servers
SHOW SERVERS;

# Show stats
SHOW STATS;
```

### Application Logging
The app will log pool creation with:
```
✅ Created connection pool (max=30 connections, timeout=5s)
```

## Troubleshooting

### If you see `PoolTimeout` errors:
1. Increase `DB_MAX_CONN` (but not above PgBouncer limits)
2. Decrease `DB_CONN_TIMEOUT` to fail faster
3. Check for connection leaks (connections not properly closed)
4. Review PgBouncer's `SHOW POOLS` to see server-side capacity

### If you see "too many connections" on PostgreSQL:
1. Increase PostgreSQL `max_connections`
2. Reduce PgBouncer `default_pool_size`
3. Check for rogue connections: `SELECT * FROM pg_stat_activity;`

### If PgBouncer is slow:
1. Increase `default_pool_size`
2. Increase `reserve_pool_size`
3. Check network latency between PgBouncer and PostgreSQL

## Best Practices

1. **Use `pool_mode = transaction`** for stateless Flask apps
2. **Keep app pool smaller than PgBouncer capacity**
3. **Always use context managers** (`with connection_ctx() as conn:`)
4. **Never hold connections during sleep/wait**
5. **Set aggressive timeouts** (5s) to fail fast
6. **Monitor connection counts** regularly
7. **Test under load** to tune settings

## References

- [PgBouncer Documentation](https://www.pgbouncer.org/config.html)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [psycopg_pool Documentation](https://www.psycopg.org/psycopg3/docs/api/pool.html)

