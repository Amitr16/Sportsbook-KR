#!/bin/bash

# GoalServe Sports Betting Platform - Deployment Script
# This script automates the deployment to Fly.io and Cloudflare Pages

set -e  # Exit on any error

echo "🚀 GoalServe Sports Betting Platform - Deployment Script"
echo "========================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Fly.io CLI is installed
check_fly_cli() {
    if ! command -v fly &> /dev/null; then
        print_error "Fly.io CLI not found. Please install it first:"
        echo "Windows: iwr https://fly.io/install.ps1 -useb | iex"
        echo "macOS/Linux: curl -L https://fly.io/install.sh | sh"
        exit 1
    fi
    print_status "Fly.io CLI found"
}

# Check if logged into Fly.io
check_fly_auth() {
    if ! fly auth whoami &> /dev/null; then
        print_error "Not logged into Fly.io. Please run: fly auth login"
        exit 1
    fi
    print_status "Authenticated with Fly.io"
}

# Create PostgreSQL database
create_postgres() {
    echo "🗄️  Setting up PostgreSQL database..."
    
    if ! fly postgres list | grep -q "goalserve-postgres"; then
        print_status "Creating PostgreSQL database..."
        fly postgres create goalserve-postgres --region iad
    else
        print_status "PostgreSQL database already exists"
    fi
}

# Create and configure the app
setup_app() {
    echo "🌐 Setting up Fly.io app..."
    
    if ! fly apps list | grep -q "goalserve-sportsbook-backend"; then
        print_status "Creating Fly.io app..."
        fly apps create goalserve-sportsbook-backend
    else
        print_status "Fly.io app already exists"
    fi
    
    # Attach PostgreSQL
    print_status "Attaching PostgreSQL to app..."
    fly postgres attach goalserve-postgres --app goalserve-sportsbook-backend --yes
}

# Set environment variables
set_secrets() {
    echo "🔐 Setting environment variables..."
    
    # Generate secure keys
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET_KEY=$(openssl rand -hex 32)
    
    # Set secrets
    fly secrets set SECRET_KEY="$SECRET_KEY" --app goalserve-sportsbook-backend
    fly secrets set JWT_SECRET_KEY="$JWT_SECRET_KEY" --app goalserve-sportsbook-backend
    fly secrets set FLASK_ENV="production" --app goalserve-sportsbook-backend
    fly secrets set FLASK_DEBUG="false" --app goalserve-sportsbook-backend
    fly secrets set HOST="0.0.0.0" --app goalserve-sportsbook-backend
    fly secrets set PORT="8080" --app goalserve-sportsbook-backend
    
    print_warning "Please set the following secrets manually:"
    echo "  - GOOGLE_CLIENT_ID"
    echo "  - GOOGLE_CLIENT_SECRET"
    echo "  - GOALSERVE_API_KEY"
    echo "  - CORS_ORIGINS (after frontend deployment)"
}

# Create volume
create_volume() {
    echo "💾 Creating persistent volume..."
    
    if ! fly volumes list | grep -q "goalserve_data"; then
        print_status "Creating volume..."
        fly volumes create goalserve_data --size 10 --region iad --app goalserve-sportsbook-backend
    else
        print_status "Volume already exists"
    fi
}

# Deploy the application
deploy_app() {
    echo "🚀 Deploying application..."
    
    print_status "Building and deploying..."
    fly deploy --app goalserve-sportsbook-backend
    
    print_status "Deployment complete!"
}

# Test deployment
test_deployment() {
    echo "🧪 Testing deployment..."
    
    # Wait for app to be ready
    sleep 10
    
    # Test health endpoint
    if curl -f "https://goalserve-sportsbook-backend.fly.dev/health" &> /dev/null; then
        print_status "Health check passed"
    else
        print_error "Health check failed"
        return 1
    fi
}

# Main deployment function
main() {
    echo "Starting deployment process..."
    
    check_fly_cli
    check_fly_auth
    create_postgres
    setup_app
    set_secrets
    create_volume
    deploy_app
    test_deployment
    
    echo ""
    print_status "Backend deployment completed successfully!"
    echo ""
    echo "🌐 Your backend is now available at:"
    echo "   https://goalserve-sportsbook-backend.fly.dev"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Set remaining secrets (Google OAuth, GoalServe API)"
    echo "   2. Deploy frontend to Cloudflare Pages"
    echo "   3. Update CORS_ORIGINS with your frontend URL"
    echo "   4. Test the complete application"
    echo ""
    echo "📖 See DEPLOYMENT_GUIDE.md for detailed instructions"
}

# Run main function
main "$@"
