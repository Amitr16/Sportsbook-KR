#!/bin/bash

# Development environment startup script
# This script sets up and starts the local development environment

set -e

echo "🚀 Starting GoalServe Sports Betting Platform - Local Development"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if .env file exists, if not copy from example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from env.example..."
    cp env.example .env
    echo "✅ .env file created. You may want to customize it."
fi

# Create mock feeds directory if it doesn't exist
if [ ! -d mock_feeds ]; then
    echo "📁 Creating mock_feeds directory..."
    mkdir -p mock_feeds
    echo "✅ mock_feeds directory created."
fi

# Build and start services
echo "🔨 Building and starting services..."
docker compose up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
if docker compose ps | grep -q "healthy"; then
    echo "✅ All services are healthy!"
else
    echo "⚠️ Some services may not be fully ready yet."
fi

echo ""
echo "🎉 Local development environment is ready!"
echo ""
echo "📍 Services:"
echo "   - Backend API: http://127.0.0.1:8000"
echo "   - Database: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs: docker compose logs -f"
echo "   - Stop services: docker compose down"
echo "   - Restart: docker compose restart"
echo "   - Rebuild: docker compose up --build"
echo ""
echo "📚 Next steps:"
echo "   1. Open http://127.0.0.1:8000 in your browser"
echo "   2. If you have a frontend dev server at :5000, update it to point to :8000"
echo "   3. Check the logs if something isn't working: docker compose logs -f"
echo ""
