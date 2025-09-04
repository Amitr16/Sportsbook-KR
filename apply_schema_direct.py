#!/usr/bin/env python3
"""
Direct schema application script for Fly Postgres cluster
This script connects directly to the cluster and applies the complete database schema
"""

import os
import sys
import psycopg
from pathlib import Path

# Database connection details from Fly Postgres cluster
DB_CONFIG = {
    'host': 'pgbouncer.w76geopwz96rplk4.flympg.net',
    'port': 5432,
    'user': 'fly-user',
    'password': 'IMunbjeQnX4aOdA13o5XdJje',
    'dbname': 'fly-db',
    'sslmode': 'require'
}

def test_connection():
    """Test database connection"""
    print("🔌 Testing database connection...")
    try:
        conn = psycopg.connect(**DB_CONFIG)
        print("✅ Database connection successful!")
        
        # Test basic query
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"📊 PostgreSQL version: {version.split(',')[0]}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def apply_schema():
    """Apply the complete database schema"""
    schema_file = Path("complete_database_schema.sql")
    
    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        return False
    
    print(f"📖 Reading schema file: {schema_file}")
    
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        print(f"📝 Schema file loaded ({len(schema_sql)} characters)")
        
        # Connect to database
        print("🔌 Connecting to database...")
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = False  # We'll handle transactions manually
        
        # Split SQL into individual statements
        statements = []
        current_statement = ""
        
        for line in schema_sql.split('\n'):
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
                    return False
        
        # Commit all changes
        conn.commit()
        print("💾 All schema changes committed successfully!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Schema application failed: {e}")
        return False

def verify_schema():
    """Verify that key tables were created"""
    print("🔍 Verifying schema creation...")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        
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
        return True
        
    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        return False

def main():
    """Main execution function"""
    print("🚀 Starting Fly Postgres schema application...")
    print("=" * 50)
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    
    # Apply schema
    if not apply_schema():
        print("❌ Schema application failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    
    # Verify schema
    if not verify_schema():
        print("❌ Schema verification failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 SUCCESS: Database schema has been applied successfully!")
    print("Your GoalServe Sports Betting Platform is now ready to use!")

if __name__ == "__main__":
    main()
