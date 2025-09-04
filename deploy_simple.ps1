# Simple GoalServe Deployment Script
# This script deploys to Fly.io using your existing PostgreSQL database

Write-Host "Deploying GoalServe Sports Betting Platform..." -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green

# Step 1: Create app if it doesn't exist
Write-Host "Step 1: Creating Fly.io app..." -ForegroundColor Cyan
try {
    flyctl apps create goalserve-sportsbook-backend
    Write-Host "SUCCESS: App created successfully" -ForegroundColor Green
} catch {
    Write-Host "INFO: App already exists or error occurred" -ForegroundColor Yellow
}

# Step 2: Set environment variables for your existing PostgreSQL
Write-Host "Step 2: Setting environment variables..." -ForegroundColor Cyan

# You need to replace 'your_password' with your actual PostgreSQL password
$databaseUrl = "postgresql://postgres:admin@localhost:5432/goalserve_sportsbook"

flyctl secrets set DATABASE_URL="$databaseUrl" --app goalserve-sportsbook-backend
flyctl secrets set FLASK_ENV="production" --app goalserve-sportsbook-backend
flyctl secrets set FLASK_DEBUG="false" --app goalserve-sportsbook-backend
flyctl secrets set HOST="0.0.0.0" --app goalserve-sportsbook-backend
flyctl secrets set PORT="8080" --app goalserve-sportsbook-backend

Write-Host "SUCCESS: Environment variables set" -ForegroundColor Green

# Step 3: Deploy the application
Write-Host "Step 3: Deploying application..." -ForegroundColor Cyan
flyctl deploy --app goalserve-sportsbook-backend

Write-Host "SUCCESS: Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Your app should now be available at:" -ForegroundColor White
Write-Host "https://goalserve-sportsbook-backend.fly.dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Update the DATABASE_URL in this script with your actual PostgreSQL password!" -ForegroundColor Yellow
