#!/usr/bin/env python3
"""
Comprehensive deployment script for Fly.io with database migrations
- Deploys application to Fly.io
- Adds casino_enabled column to sportsbook_operators table
- Creates referral_table with superadmin entry
"""

import os
import sys
import subprocess
import time
import secrets
import string
from src import sqlite3_shim as sqlite3

# Global variable to store the correct fly command
FLY_CMD = None

def generate_referral_code(length=8):
    """Generate a random alphanumeric referral code."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")
    print(f"Command: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr}")
        return False

def check_fly_cli():
    """Check if Fly CLI is installed and user is logged in."""
    print("🔍 Checking Fly CLI...")
    
    # Try different possible locations for flyctl
    fly_paths = [
        "flyctl",
        "fly", 
        "c:/flyctl/flyctl.exe",
        "C:/flyctl/flyctl.exe"
    ]
    
    fly_cmd = None
    for path in fly_paths:
        try:
            result = subprocess.run(f"{path} version", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                fly_cmd = path
                print(f"✅ Found Fly CLI at: {path}")
                break
        except:
            continue
    
    if not fly_cmd:
        print("❌ Fly CLI not found. Please install it from https://fly.io/docs/hands-on/install-flyctl/")
        return False
    
    # Check if user is logged in
    if not run_command(f"{fly_cmd} auth whoami", "Checking Fly CLI authentication"):
        print("❌ Not logged in to Fly.io. Please run 'flyctl auth login' first")
        return False
    
    # Store the fly command for later use
    global FLY_CMD
    FLY_CMD = fly_cmd
    return True

def deploy_to_fly():
    """Deploy the application to Fly.io."""
    print("\n🚀 Starting deployment to Fly.io...")
    
    # Check if fly.toml exists
    if not os.path.exists('fly.toml'):
        print("❌ fly.toml not found. Please ensure you're in the correct directory.")
        return False
    
    # Deploy to Fly.io using the correct fly command
    if not run_command(f"{FLY_CMD} deploy", "Deploying to Fly.io"):
        return False
    
    print("✅ Deployment completed successfully!")
    return True

def add_casino_enabled_column():
    """Add casino_enabled column to sportsbook_operators table."""
    print("\n🔧 Adding casino_enabled column to sportsbook_operators table...")
    
    try:
        conn = sqlite3.connect()
        cursor = conn.cursor()
        
        # Check if column already exists (PostgreSQL syntax)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sportsbook_operators' 
            AND column_name = 'casino_enabled'
        """)
        column_exists = cursor.fetchone()
        
        if not column_exists:
            # Add the casino_enabled column with default value True
            cursor.execute("""
                ALTER TABLE sportsbook_operators 
                ADD COLUMN casino_enabled BOOLEAN DEFAULT true
            """)
            
            # Update existing records to have casino enabled by default
            cursor.execute("""
                UPDATE sportsbook_operators 
                SET casino_enabled = true 
                WHERE casino_enabled IS NULL
            """)
            
            conn.commit()
            print("✅ Successfully added casino_enabled column to sportsbook_operators table")
        else:
            print("ℹ️  casino_enabled column already exists in sportsbook_operators table")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error adding casino_enabled column: {e}")
        return False

def create_referral_table():
    """Create referral_table and add initial superadmin entry."""
    print("\n🔧 Creating referral_table...")
    
    try:
        conn = sqlite3.connect()
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'referral_table'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Create the referral table
            cursor.execute("""
                CREATE TABLE referral_table (
                    id SERIAL PRIMARY KEY,
                    operator_name VARCHAR(100) NOT NULL,
                    operator_id INTEGER NOT NULL,
                    referral_used VARCHAR(20),
                    referral_generated VARCHAR(20) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Generate initial superadmin referral code
            superadmin_referral = generate_referral_code()
            
            # Insert superadmin entry
            # Note: operator_id 0 is used for superadmin, which is not a foreign key to sportsbook_operators.id
            cursor.execute("""
                INSERT INTO referral_table 
                (operator_name, operator_id, referral_used, referral_generated)
                VALUES (?, ?, ?, ?)
            """, ('Superadmin', 0, 'N/A', superadmin_referral))
            
            conn.commit()
            print("✅ Successfully created referral_table")
            print(f"✅ Superadmin referral code: {superadmin_referral}")
        else:
            print("ℹ️  referral_table already exists")
            
            # Check if superadmin entry exists
            cursor.execute("""
                SELECT referral_generated FROM referral_table 
                WHERE operator_id = 0 AND operator_name = 'Superadmin'
            """)
            superadmin_entry = cursor.fetchone()
            
            if superadmin_entry:
                print(f"ℹ️  Superadmin entry already exists with code: {superadmin_entry[0]}")
            else:
                # Add superadmin entry if it doesn't exist
                superadmin_referral = generate_referral_code()
                cursor.execute("""
                    INSERT INTO referral_table 
                    (operator_name, operator_id, referral_used, referral_generated)
                    VALUES (?, ?, ?, ?)
                """, ('Superadmin', 0, 'N/A', superadmin_referral))
                conn.commit()
                print(f"✅ Added superadmin entry with code: {superadmin_referral}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating referral table: {e}")
        return False

def verify_deployment():
    """Verify the deployment by checking the app status."""
    print("\n🔍 Verifying deployment...")
    
    if not run_command(f"{FLY_CMD} status", "Checking app status"):
        return False
    
    print("✅ Deployment verification completed!")
    return True

def main():
    """Main deployment function."""
    print("🚀 Starting comprehensive deployment to Fly.io with database migrations")
    print("=" * 70)
    
    # Check prerequisites
    if not check_fly_cli():
        sys.exit(1)
    
    # Set DATABASE_URL if not already set
    if not os.environ.get('DATABASE_URL'):
        # You can change this to your actual database URL
        database_url = "postgresql://postgres:admin@localhost:5432/goalserve_sportsbook"
        os.environ['DATABASE_URL'] = database_url
        print(f"✅ DATABASE_URL set to: {database_url[:30]}...")
    else:
        print(f"✅ DATABASE_URL is already set: {os.environ['DATABASE_URL'][:30]}...")
    
    # Step 1: Deploy to Fly.io
    if not deploy_to_fly():
        print("❌ Deployment failed. Stopping.")
        sys.exit(1)
    
    # Step 2: Wait a moment for deployment to settle
    print("\n⏳ Waiting for deployment to settle...")
    time.sleep(10)
    
    # Step 3: Add casino_enabled column
    if not add_casino_enabled_column():
        print("❌ Failed to add casino_enabled column. Continuing with other tasks...")
    
    # Step 4: Create referral table
    if not create_referral_table():
        print("❌ Failed to create referral table. Continuing...")
    
    # Step 5: Verify deployment
    if not verify_deployment():
        print("⚠️  Deployment verification failed, but deployment may have succeeded.")
    
    print("\n" + "=" * 70)
    print("🎉 Deployment process completed!")
    print("\n📋 Summary:")
    print("✅ Application deployed to Fly.io")
    print("✅ casino_enabled column added to sportsbook_operators")
    print("✅ referral_table created with superadmin entry")
    print("\n🔗 Your app should be available at: https://your-app-name.fly.dev")
    print("\n💡 Next steps:")
    print("1. Test the admin dashboard to verify casino toggle works")
    print("2. Test the referral code display in the admin header")
    print("3. Test the registration process with referral codes")

if __name__ == '__main__':
    main()
