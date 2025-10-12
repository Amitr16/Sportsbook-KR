#!/usr/bin/env python3
"""
Quick redeploy script to fix casino asset routing issues
"""

import subprocess
import sys

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"Running: {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"WARNING: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("Quick redeploy to fix casino asset routing...")
    print("=" * 50)
    
    # Deploy to Fly.io
    if not run_command("flyctl deploy", "Deploying backend fixes to Fly.io"):
        print("ERROR: Deployment failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("SUCCESS: Backend fixes deployed!")
    print("\nThe casino chip assets should now load correctly.")
    print("Check your deployed app to verify the fix.")

if __name__ == "__main__":
    main()
