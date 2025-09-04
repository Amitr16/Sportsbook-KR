#!/usr/bin/env python3
"""
Schema application via SSH to Fly app
This script will SSH into the Fly app and apply the schema from within the Fly network
"""

import subprocess
import sys
import os
from pathlib import Path

def run_ssh_command(command):
    """Run a command via SSH to the Fly app"""
    ssh_cmd = [
        "fly", "ssh", "console", 
        "--app", "goalserve-sportsbook-backend",
        "-C", command
    ]
    
    print(f"🔌 Running SSH command: {' '.join(ssh_cmd)}")
    
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print("✅ SSH command executed successfully")
            if result.stdout.strip():
                print("📤 Output:")
                print(result.stdout)
        else:
            print(f"❌ SSH command failed with return code {result.returncode}")
            if result.stderr.strip():
                print("📤 Error output:")
                print(result.stderr)
            if result.stdout.strip():
                print("📤 Standard output:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ SSH command timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ SSH command failed: {e}")
        return False

def main():
    """Main execution function"""
    print("🚀 Starting schema application via SSH to Fly app...")
    print("=" * 60)
    
    # Step 1: Test SSH connection
    print("🔌 Testing SSH connection to Fly app...")
    if not run_ssh_command("echo 'SSH connection test successful'"):
        print("❌ Cannot establish SSH connection to Fly app")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Step 2: Check if schema file exists on the remote app
    print("📁 Checking if schema file exists on remote app...")
    if not run_ssh_command("ls -la /app/complete_database_schema.sql"):
        print("❌ Schema file not found on remote app")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Step 3: Test database connection from within the app
    print("🔌 Testing database connection from within Fly app...")
    test_script = '''
import psycopg
import os

try:
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found in environment")
        exit(1)
    
    print(f"🔌 Connecting to database...")
    conn = psycopg.connect(db_url)
    print("✅ Database connection successful!")
    
    # Test basic query
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"📊 PostgreSQL version: {version.split(',')[0]}")
    
    conn.close()
    print("✅ Database test completed successfully!")
    
except Exception as e:
    print(f"❌ Database test failed: {e}")
    exit(1)
'''
    
    if not run_ssh_command(f"python3 -c \"{test_script}\""):
        print("❌ Database connection test failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Step 4: Apply the schema
    print("📖 Applying database schema...")
    schema_script = '''
import psycopg
import os
from pathlib import Path

try:
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found in environment")
        exit(1)
    
    # Read schema file
    schema_file = Path("/app/complete_database_schema.sql")
    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        exit(1)
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    print(f"📝 Schema file loaded ({len(schema_sql)} characters)")
    
    # Connect to database
    print("🔌 Connecting to database...")
    conn = psycopg.connect(db_url)
    conn.autocommit = False
    
    # Split SQL into individual statements
    statements = []
    current_statement = ""
    
    for line in schema_sql.split('\\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        current_statement += line + " "
        
        if line.endswith(';'):
            statements.append(current_statement.strip())
            current_statement = ""
    
    if current_statement.strip():
        statements.append(current_statement.strip())
    
    print(f"🔧 Found {len(statements)} SQL statements to execute")
    
    # Execute statements
    with conn.cursor() as cur:
        for i, statement in enumerate(statements, 1):
            try:
                print(f"⚡ Executing statement {i}/{len(statements)}...")
                cur.execute(statement)
                print(f"✅ Statement {i} executed successfully")
            except Exception as e:
                print(f"❌ Statement {i} failed: {e}")
                print(f"🔍 Failed SQL: {statement[:100]}...")
                conn.rollback()
                conn.close()
                exit(1)
    
    # Commit all changes
    conn.commit()
    print("💾 All schema changes committed successfully!")
    conn.close()
    
    print("✅ Schema application completed successfully!")
    
except Exception as e:
    print(f"❌ Schema application failed: {e}")
    exit(1)
'''
    
    if not run_ssh_command(f"python3 -c \"{schema_script}\""):
        print("❌ Schema application failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Step 5: Verify schema creation
    print("🔍 Verifying schema creation...")
    verify_script = '''
import psycopg
import os

try:
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found in environment")
        exit(1)
    
    conn = psycopg.connect(db_url)
    
    # Check for key tables
    key_tables = [
        'sportsbook_operators',
        'users',
        'sports',
        'betting_events',
        'wallets'
    ]
    
    with conn.cursor() as cur:
        for table in key_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table,))
            
            exists = cur.fetchone()[0]
            status = "✅" if exists else "❌"
            print(f"{status} Table '{table}': {'EXISTS' if exists else 'MISSING'}")
    
    conn.close()
    print("✅ Schema verification completed!")
    
except Exception as e:
    print(f"❌ Schema verification failed: {e}")
    exit(1)
'''
    
    if not run_ssh_command(f"python3 -c \"{verify_script}\""):
        print("❌ Schema verification failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS: Database schema has been applied successfully!")
    print("Your GoalServe Sports Betting Platform is now ready to use!")

if __name__ == "__main__":
    main()
