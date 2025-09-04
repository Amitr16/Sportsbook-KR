#!/usr/bin/env python3
"""
Simple schema application script for Fly Postgres cluster
"""

import psycopg
import os
from pathlib import Path

# Database connection details from your Fly Postgres cluster
DB_CONFIG = {
    'host': 'pgbouncer.w76geopwz96rplk4.flympg.net',
    'port': 5432,
    'user': 'fly-user',
    'password': 'IMunbjeQnX4aOdA13o5XdJje',
    'dbname': 'fly-db',
    'sslmode': 'require'
}

def main():
    print("🚀 Starting schema application...")
    
    # Check if schema file exists
    schema_file = Path("complete_database_schema.sql")
    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        return
    
    print(f"📖 Reading schema file: {schema_file}")
    
    try:
        # Read the schema file
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        print(f"📝 Schema file loaded ({len(schema_sql)} characters)")
        
        # Connect to database
        print("🔌 Connecting to database...")
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = False
        
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
                    return
        
        # Commit all changes
        conn.commit()
        print("💾 All schema changes committed successfully!")
        conn.close()
        
        print("🎉 SUCCESS: Database schema has been applied!")
        
    except Exception as e:
        print(f"❌ Schema application failed: {e}")

if __name__ == "__main__":
    main()
