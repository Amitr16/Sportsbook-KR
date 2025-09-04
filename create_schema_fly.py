#!/usr/bin/env python3
"""
Script to create the database schema on Fly.io PostgreSQL
Run this from within the Fly.io SSH console
"""

import os
import sys
import psycopg2
from psycopg2 import sql

def main():
    print("🚀 Starting database schema creation...")
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        sys.exit(1)
    
    print(f"📡 Connecting to database...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to database successfully")
        
        # Read the schema file
        schema_file = '/app/complete_database_schema.sql'
        if not os.path.exists(schema_file):
            print(f"❌ Schema file not found: {schema_file}")
            print("📁 Available files in /app/:")
            try:
                import subprocess
                result = subprocess.run(['ls', '-la', '/app/'], capture_output=True, text=True)
                print(result.stdout)
            except:
                print("Could not list directory contents")
            sys.exit(1)
        
        print(f"📖 Reading schema file: {schema_file}")
        
        with open(schema_file, 'r') as f:
            schema_content = f.read()
        
        # Split into individual statements
        statements = [stmt.strip() for stmt in schema_content.split(';') if stmt.strip()]
        
        print(f"📝 Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        for i, statement in enumerate(statements, 1):
            if not statement or statement.startswith('--'):
                continue
                
            try:
                print(f"🔧 Executing statement {i}/{len(statements)}...")
                cursor.execute(statement)
                print(f"✅ Statement {i} executed successfully")
            except Exception as e:
                print(f"❌ Error executing statement {i}: {e}")
                print(f"Statement: {statement[:100]}...")
                # Continue with other statements
                continue
        
        print("🎉 Database schema creation completed!")
        
        # Verify some key tables were created
        print("🔍 Verifying key tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
