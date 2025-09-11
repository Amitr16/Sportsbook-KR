#!/usr/bin/env python3
"""
Deploy the betting system to Fly.io
This script helps with the deployment process
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr}")
        return False

def check_flyctl():
    """Check if flyctl is installed"""
    try:
        subprocess.run("flyctl version", shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """Main deployment function"""
    print("🚀 Starting deployment to Fly.io...")
    
    # Check if flyctl is installed
    if not check_flyctl():
        print("❌ flyctl is not installed. Please install it first:")
        print("   https://fly.io/docs/hands-on/install-flyctl/")
        return False
    
    # Check if we're in the right directory
    if not Path("fly.toml").exists():
        print("❌ fly.toml not found. Please run this from the project root directory.")
        return False
    
    # Check if we're logged in to Fly.io
    if not run_command("flyctl auth whoami", "Checking Fly.io authentication"):
        print("❌ Not logged in to Fly.io. Please run: flyctl auth login")
        return False
    
    # Deploy to Fly.io
    if not run_command("flyctl deploy", "Deploying to Fly.io"):
        print("❌ Deployment failed")
        return False
    
    print("🎉 Deployment completed successfully!")
    print("\n📋 Next steps:")
    print("1. Check the deployment status: flyctl status")
    print("2. View logs: flyctl logs")
    print("3. Open the app: flyctl open")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
