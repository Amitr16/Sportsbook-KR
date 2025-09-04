#!/usr/bin/env python3
"""
Apply database schema via Fly.io proxy connection
This script connects to the local proxy (127.0.0.1:5433) and applies the schema
"""

import psycopg
import sys
import os

# Connection details for the proxy
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "fly-user", 
    "password": "IMunbjeQnX4aOdA13o5XdJje",
    "dbname": "fly-db",
    "sslmode": "require"
}

def apply_schema():
    """Apply the complete database schema"""
    
    # Read the schema file
    schema_file = "complete_database_schema.sql"
    if not os.path.exists(schema_file):
        print(f"❌ Schema file not found: {schema_file}")
        return False
    
    try:
        print(f"📖 Reading schema from: {schema_file}")
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        print(f"🔌 Connecting to database via proxy (127.0.0.1:5433)...")
        print(f"   User: {DB_CONFIG['user']}")
        print(f"   Database: {DB_CONFIG['dbname']}")
        
        # Connect and apply schema
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                print("✅ Connected successfully!")
                print("🚀 Applying schema...")
                
                # Execute the schema
                cur.execute(schema_sql)
                
                print("✅ Schema applied successfully!")
                
                # Verify tables were created
                print("🔍 Verifying tables...")
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
                
                tables = cur.fetchall()
                if tables:
                    print(f"📋 Found {len(tables)} tables:")
                    for table in tables:
                        print(f"   - {table[0]}")
                else:
                    print("⚠️  No tables found - schema may not have been applied correctly")
                
                return True
                
    except FileNotFoundError:
        print(f"❌ Schema file not found: {schema_file}")
        return False
    except psycopg.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Fly.io Database Schema Application Tool")
    print("=" * 50)
    
    success = apply_schema()
    
    if success:
        print("\n🎉 Schema application completed successfully!")
        print("Your app should now work without 'UndefinedTable' errors.")
    else:
        print("\n💥 Schema application failed!")
        sys.exit(1)
