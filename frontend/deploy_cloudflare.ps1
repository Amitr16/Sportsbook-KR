# Cloudflare Pages Deployment Script
# This script deploys your frontend to Cloudflare Pages with minimal setup

Write-Host "🚀 Deploying GoalServe Sportsbook Frontend to Cloudflare Pages..." -ForegroundColor Green

# Check if Wrangler CLI is installed
if (!(Get-Command "wrangler" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Wrangler CLI not found. Installing..." -ForegroundColor Yellow
    npm install -g wrangler
}

# Login to Cloudflare (if not already logged in)
Write-Host "🔐 Checking Cloudflare authentication..." -ForegroundColor Blue
wrangler whoami

# Deploy to Cloudflare Pages
Write-Host "📦 Deploying to Cloudflare Pages..." -ForegroundColor Blue
wrangler pages deploy ../src/static --project-name=goalserve-sportsbook-frontend --commit-dirty=true

Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host "🌐 Your frontend will be available at: https://goalserve-sportsbook-frontend.pages.dev" -ForegroundColor Cyan
