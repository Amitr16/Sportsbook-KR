# GoalServe Sports Betting Platform - Deployment Script (PowerShell)
# This script automates the deployment to Fly.io and Cloudflare Pages

param(
    [switch]$SkipChecks,
    [switch]$Help
)

if ($Help) {
    Write-Host "🚀 GoalServe Sports Betting Platform - Deployment Script" -ForegroundColor Green
    Write-Host "Usage: .\deploy.ps1 [-SkipChecks] [-Help]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -SkipChecks    Skip pre-deployment checks" -ForegroundColor White
    Write-Host "  -Help          Show this help message" -ForegroundColor White
    exit 0
}

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "🚀 GoalServe Sports Betting Platform - Deployment Script" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

# Check if Fly.io CLI is installed
function Test-FlyCLI {
    try {
        # Try to find flyctl in PATH first
        $null = Get-Command flyctl -ErrorAction Stop
        Write-Status "Fly.io CLI (flyctl) found in PATH"
        return $true
    }
    catch {
        # Try to find flyctl in the .fly directory
        $flyctlPath = "$env:USERPROFILE\.fly\bin\flyctl.exe"
        if (Test-Path $flyctlPath) {
            Write-Status "Fly.io CLI (flyctl) found in .fly directory"
            $script:flyCommand = $flyctlPath
            return $true
        }
        else {
            Write-Error "Fly.io CLI (flyctl) not found. Please install it first:"
            Write-Host "Run: iwr https://fly.io/install.ps1 -useb | iex" -ForegroundColor Yellow
            return $false
        }
    }
}

# Check if logged into Fly.io
function Test-FlyAuth {
    try {
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        $null = & $flyCmd auth whoami 2>$null
        Write-Status "Authenticated with Fly.io"
        return $true
    }
    catch {
        Write-Error "Not logged into Fly.io. Please run: flyctl auth login"
        return $false
    }
}

# Create PostgreSQL database
function New-PostgreSQLDatabase {
    Write-Host "🗄️  Setting up PostgreSQL database..." -ForegroundColor Cyan
    
    try {
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        $postgresList = & $flyCmd postgres list 2>$null
        if ($postgresList -notmatch "goalserve-postgres") {
            Write-Status "Creating PostgreSQL database..."
            & $flyCmd postgres create goalserve-postgres --region iad
        }
        else {
            Write-Status "PostgreSQL database already exists"
        }
    }
    catch {
        Write-Error "Failed to create PostgreSQL database: $_"
        throw
    }
}

# Create and configure the app
function New-FlyApp {
    Write-Host "🌐 Setting up Fly.io app..." -ForegroundColor Cyan
    
    try {
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        $appsList = & $flyCmd apps list 2>$null
        if ($appsList -notmatch "goalserve-sportsbook-backend") {
            Write-Status "Creating Fly.io app..."
            & $flyCmd apps create goalserve-sportsbook-backend
        }
        else {
            Write-Status "Fly.io app already exists"
        }
        
        # Attach PostgreSQL
        Write-Status "Attaching PostgreSQL to app..."
        & $flyCmd postgres attach goalserve-postgres --app goalserve-sportsbook-backend --yes
    }
    catch {
        Write-Error "Failed to setup Fly.io app: $_"
        throw
    }
}

# Set environment variables
function Set-FlySecrets {
    Write-Host "🔐 Setting environment variables..." -ForegroundColor Cyan
    
    try {
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        # Generate secure keys
        $secretKey = -join ((33..126) | Get-Random -Count 32 | ForEach-Object {[char]$_})
        $jwtSecretKey = -join ((33..126) | Get-Random -Count 32 | ForEach-Object {[char]$_})
        
        # Set secrets
        & $flyCmd secrets set SECRET_KEY="$secretKey" --app goalserve-sportsbook-backend
        & $flyCmd secrets set JWT_SECRET_KEY="$jwtSecretKey" --app goalserve-sportsbook-backend
        & $flyCmd secrets set FLASK_ENV="production" --app goalserve-sportsbook-backend
        & $flyCmd secrets set FLASK_DEBUG="false" --app goalserve-sportsbook-backend
        & $flyCmd secrets set HOST="0.0.0.0" --app goalserve-sportsbook-backend
        & $flyCmd secrets set PORT="8080" --app goalserve-sportsbook-backend
        
        Write-Warning "Please set the following secrets manually:"
        Write-Host "  - GOOGLE_CLIENT_ID" -ForegroundColor Yellow
        Write-Host "  - GOOGLE_CLIENT_SECRET" -ForegroundColor Yellow
        Write-Host "  - GOALSERVE_API_KEY" -ForegroundColor Yellow
        Write-Host "  - CORS_ORIGINS (after frontend deployment)" -ForegroundColor Yellow
    }
    catch {
        Write-Error "Failed to set secrets: $_"
        throw
    }
}

# Create volume
function New-FlyVolume {
    Write-Host "💾 Creating persistent volume..." -ForegroundColor Cyan
    
    try {
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        $volumesList = & $flyCmd volumes list 2>$null
        if ($volumesList -notmatch "goalserve_data") {
            Write-Status "Creating volume..."
            & $flyCmd volumes create goalserve_data --size 10 --region iad --app goalserve-sportsbook-backend
        }
        else {
            Write-Status "Volume already exists"
        }
    }
    catch {
        Write-Error "Failed to create volume: $_"
        throw
    }
}

# Deploy the application
function Deploy-FlyApp {
    Write-Host "🚀 Deploying application..." -ForegroundColor Cyan
    
    try {
        Write-Status "Building and deploying..."
        $flyCmd = if ($script:flyCommand) { $script:flyCommand } else { "flyctl" }
        & $flyCmd deploy --app goalserve-sportsbook-backend
        Write-Status "Deployment complete!"
    }
    catch {
        Write-Error "Failed to deploy application: $_"
        throw
    }
}

# Test deployment
function Test-FlyDeployment {
    Write-Host "🧪 Testing deployment..." -ForegroundColor Cyan
    
    try {
        # Wait for app to be ready
        Start-Sleep -Seconds 10
        
        # Test health endpoint
        $healthUrl = "https://goalserve-sportsbook-backend.fly.dev/health"
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -ErrorAction Stop
        
        if ($response.StatusCode -eq 200) {
            Write-Status "Health check passed"
        }
        else {
            Write-Error "Health check failed with status: $($response.StatusCode)"
            return $false
        }
    }
    catch {
        Write-Error "Health check failed: $_"
        return $false
    }
    
    return $true
}

# Main deployment function
function Start-Deployment {
    Write-Host "Starting deployment process..." -ForegroundColor Cyan
    
    if (-not $SkipChecks) {
        if (-not (Test-FlyCLI)) { exit 1 }
        if (-not (Test-FlyAuth)) { exit 1 }
    }
    
    New-PostgreSQLDatabase
    New-FlyApp
    New-FlyVolume
    Deploy-FlyApp
    Set-FlySecrets
    
    if (Test-FlyDeployment) {
        Write-Host ""
        Write-Status "Backend deployment completed successfully!"
        Write-Host ""
        Write-Host "🌐 Your backend is now available at:" -ForegroundColor White
        Write-Host "   https://goalserve-sportsbook-backend.fly.dev" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "📋 Next steps:" -ForegroundColor White
        Write-Host "   1. Set remaining secrets (Google OAuth, GoalServe API)" -ForegroundColor Yellow
        Write-Host "   2. Deploy frontend to Cloudflare Pages" -ForegroundColor Yellow
        Write-Host "   3. Update CORS_ORIGINS with your frontend URL" -ForegroundColor Yellow
        Write-Host "   4. Test the complete application" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📖 See DEPLOYMENT_GUIDE.md for detailed instructions" -ForegroundColor Cyan
    }
    else {
        Write-Error "Deployment test failed. Please check the logs: flyctl logs"
        exit 1
    }
}

# Run main deployment function
try {
    Start-Deployment
}
catch {
    Write-Error "Deployment failed: $_"
    Write-Host "Check the logs with: flyctl logs" -ForegroundColor Yellow
    exit 1
}
