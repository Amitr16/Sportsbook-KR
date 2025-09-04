#!/bin/bash

# Database migration script
# This script runs database migrations inside the backend container

set -e

echo "🔄 Running database migrations..."

# Check if services are running
if ! docker compose ps | grep -q "backend"; then
    echo "❌ Backend service is not running. Start it first with: ./scripts/dev.sh"
    exit 1
fi

# Run migrations
echo "📊 Executing database migrations..."
docker compose exec backend python -m alembic upgrade head

echo "✅ Database migrations completed successfully!"
echo ""
echo "📚 Database is now up to date with the latest schema."
echo ""
