#!/bin/bash

# Cloudflare Pages Deployment Script
# This script deploys your frontend to Cloudflare Pages with minimal setup

echo "🚀 Deploying GoalServe Sportsbook Frontend to Cloudflare Pages..."

# Check if Wrangler CLI is installed
if ! command -v wrangler &> /dev/null; then
    echo "❌ Wrangler CLI not found. Installing..."
    npm install -g wrangler
fi

# Login to Cloudflare (if not already logged in)
echo "🔐 Checking Cloudflare authentication..."
wrangler whoami

# Deploy to Cloudflare Pages
echo "📦 Deploying to Cloudflare Pages..."
wrangler pages deploy ../src/static --project-name=goalserve-sportsbook-frontend --commit-dirty=true

echo "✅ Deployment complete!"
echo "🌐 Your frontend will be available at: https://goalserve-sportsbook-frontend.pages.dev"
