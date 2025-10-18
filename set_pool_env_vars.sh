#!/bin/bash
# Set database pool environment variables for Fly.io
# This allows the pool to shrink during quiet periods instead of growing forever

echo "Setting database pool environment variables..."

# Let pool go down to zero when idle (instead of keeping minimum 2)
fly secrets set DB_POOL_MIN=0

# Reap idle connections after 60 seconds (instead of 300)
fly secrets set DB_POOL_MAX_IDLE=60

# Optional: Churn older sockets every 10 minutes for connection health
fly secrets set DB_POOL_MAX_LIFETIME=600

echo "✅ Pool environment variables set!"
echo ""
echo "Expected behavior after deployment:"
echo "  - Pool will shrink to 0-3 connections during quiet periods"
echo "  - Idle sockets reaped after 60 seconds of no use"
echo "  - No more persistent connection creep"
echo ""
echo "Next steps:"
echo "  1. Deploy your app: fly deploy"
echo "  2. Monitor /health/dashboard for 1-2 hours"
echo "  3. Verify 'Pool Sockets (Open)' drops to 0-3 when idle"
echo "  4. Verify 'Leaked & Recovered' stays at 0"

