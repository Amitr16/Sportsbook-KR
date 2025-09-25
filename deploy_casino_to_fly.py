#!/usr/bin/env python3
"""
Deploy casino-integrated betting system to Fly.io
This script handles the complete deployment process including database migrations
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def run_command(command, description, check=True):
    """Run a command and handle errors"""
    print(f"Running: {description}...")
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"WARNING: {result.stderr}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed")
        print(f"Error: {e.stderr}")
        return False

def check_prerequisites():
    """Check if all prerequisites are met"""
    print("Checking prerequisites...")
    
    # Check if flyctl is installed
    if not run_command("flyctl version", "Checking flyctl installation", check=False):
        print("ERROR: flyctl is not installed. Please install it first:")
        print("   https://fly.io/docs/hands-on/install-flyctl/")
        return False
    
    # Check if we're in the right directory
    if not Path("fly.toml").exists():
        print("ERROR: fly.toml not found. Please run this from the project root directory.")
        return False
    
    # Note: Casino frontend will be built during Docker build process
    print("INFO: Casino frontend will be built during Docker build process")
    
    print("SUCCESS: All prerequisites met")
    return True

def check_fly_authentication():
    """Check if we're logged in to Fly.io"""
    print("Checking Fly.io authentication...")
    if not run_command("flyctl auth whoami", "Checking Fly.io authentication", check=False):
        print("ERROR: Not logged in to Fly.io. Please run: flyctl auth login")
        return False
    print("SUCCESS: Authenticated with Fly.io")
    return True

def create_casino_tables():
    """Create casino tables in production database"""
    print("Creating casino tables in production database...")
    
    # Try different SSH approaches
    commands = [
        "flyctl ssh console -C 'python create_casino_tables_fly.py'",
        "flyctl ssh console --command 'python create_casino_tables_fly.py'",
        "flyctl ssh console -C python create_casino_tables_fly.py"
    ]
    
    for i, cmd in enumerate(commands):
        print(f"Trying SSH method {i+1}...")
        if run_command(cmd, f"Creating casino tables (method {i+1})", check=False):
            print("SUCCESS: Casino tables created successfully")
            return True
        else:
            print(f"Method {i+1} failed, trying next...")
    
    print("ERROR: All SSH methods failed. You may need to create tables manually.")
    print("To create tables manually:")
    print("1. Run: flyctl ssh console")
    print("2. Once connected, run: python create_casino_tables_fly.py")
    return False

def update_requirements():
    """Update requirements.txt if needed"""
    print("Checking requirements.txt...")
    
    # Check if all casino dependencies are in requirements.txt
    with open("requirements.txt", "r") as f:
        requirements = f.read()
    
    casino_deps = ["psycopg2-binary", "python-dotenv"]
    missing_deps = []
    
    for dep in casino_deps:
        if dep not in requirements:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"WARNING: Adding missing dependencies: {missing_deps}")
        with open("requirements.txt", "a") as f:
            for dep in missing_deps:
                f.write(f"\n{dep}")
        print("SUCCESS: Requirements.txt updated")
    else:
        print("SUCCESS: All dependencies already present")

def build_casino_frontend():
    """Build the casino frontend (now handled in Docker)"""
    print("INFO: Casino frontend will be built during Docker build process")
    print("SUCCESS: Casino frontend build step skipped (handled in Docker)")
    return True

def deploy_to_fly():
    """Deploy the application to Fly.io"""
    print("Deploying to Fly.io...")
    if not run_command("flyctl deploy", "Deploying to Fly.io"):
        print("ERROR: Deployment failed")
        return False
    print("SUCCESS: Deployment completed successfully")
    return True

def verify_deployment():
    """Verify the deployment is working"""
    print("Verifying deployment...")
    
    # Wait a moment for the app to start
    print("Waiting for app to start...")
    time.sleep(10)
    
    # Check app status
    if not run_command("flyctl status", "Checking app status", check=False):
        print("WARNING: Could not check app status")
        return False
    
    # Check if app is running
    if not run_command("flyctl status --json", "Getting app status", check=False):
        print("WARNING: Could not get detailed status")
        return False
    
    print("SUCCESS: Deployment verification completed")
    return True

def main():
    """Main deployment function"""
    print("Starting casino-integrated deployment to Fly.io...")
    print("=" * 60)
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        print("ERROR: Prerequisites check failed")
        sys.exit(1)
    
    # Step 2: Check authentication
    if not check_fly_authentication():
        print("ERROR: Authentication check failed")
        sys.exit(1)
    
    # Step 3: Update requirements
    update_requirements()
    
    # Step 4: Build casino frontend
    if not build_casino_frontend():
        print("ERROR: Casino frontend build failed")
        sys.exit(1)
    
    # Step 5: Deploy to Fly.io first (so scripts are available)
    if not deploy_to_fly():
        print("ERROR: Deployment failed")
        sys.exit(1)
    
    # Step 6: Create casino tables (after deployment)
    if not create_casino_tables():
        print("ERROR: Casino table creation failed")
        sys.exit(1)
    
    # Step 7: Verify deployment
    if not verify_deployment():
        print("WARNING: Deployment verification had issues, but deployment may still be successful")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Casino-integrated deployment completed successfully!")
    print("\nNext steps:")
    print("1. Check the deployment status: flyctl status")
    print("2. View logs: flyctl logs")
    print("3. Open the app: flyctl open")
    print("4. Test casino functionality:")
    print("   - Navigate to your sportsbook")
    print("   - Click on the casino link")
    print("   - Test games: Blackjack, Slots, Baccarat, etc.")
    print("5. Check game history functionality")
    
    print("\nTroubleshooting:")
    print("- If casino assets don't load: Check multi-tenant routing")
    print("- If games don't work: Check database tables and API endpoints")
    print("- If wallet doesn't update: Check session handling and database queries")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
