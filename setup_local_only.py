#!/usr/bin/env python3
"""
Setup local SQLite database only - then use run.py
"""

import os
import sys
sys.path.insert(0, 'src')

# Set environment for local development
os.environ['FLASK_ENV'] = 'development'

from config import config
import sqlite3

def setup_local_database():
    """Setup local SQLite database with schema and sample data"""
    
    print("Setting up local development database...")
    config.print_config()
    
    if config.DATABASE_TYPE != 'sqlite':
        print("❌ This script is for local SQLite setup only")
        return False
    
    try:
        # Create SQLite database
        db_path = config.DATABASE_URL.replace('sqlite:///', '')
        print(f"Creating database at: {db_path}")
        
        # Create tables using the existing schema
        with open('postgresql_schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Convert PostgreSQL syntax to SQLite
        schema_sql = schema_sql.replace('SERIAL', 'INTEGER')
        schema_sql = schema_sql.replace('BIGSERIAL', 'INTEGER')
        schema_sql = schema_sql.replace('VARCHAR', 'TEXT')
        schema_sql = schema_sql.replace('TIMESTAMP WITH TIME ZONE', 'TIMESTAMP')
        schema_sql = schema_sql.replace('TIMESTAMP WITHOUT TIME ZONE', 'TIMESTAMP')
        schema_sql = schema_sql.replace('DECIMAL(10,2)', 'REAL')
        schema_sql = schema_sql.replace('BOOLEAN', 'INTEGER')
        
        # Remove PostgreSQL-specific statements
        schema_sql = '\n'.join([
            line for line in schema_sql.split('\n') 
            if not line.strip().startswith('--') and 
               not line.strip().startswith('CREATE INDEX') and
               not line.strip().startswith('ALTER TABLE') and
               not line.strip().startswith('GRANT') and
               not line.strip().startswith('REVOKE')
        ])
        
        # Create database and tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Split and execute schema statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        for stmt in statements:
            if stmt:
                try:
                    cursor.execute(stmt)
                    print(f"✅ Executed: {stmt[:50]}...")
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        print(f"⚠️ Warning: {e}")
                        print(f"Statement: {stmt}")
        
        # Insert sample data
        print("\nInserting sample data...")
        
        # Insert superadmin user
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, email, password_hash, role, balance, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, ('superadmin', 'admin@example.com', 'superadmin123', 'superadmin', 10000.0))
        
        # Insert test user
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, email, password_hash, role, balance, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, ('am1111', 'test@example.com', 'password123', 'user', 1000.0))
        
        # Insert sportsbook operator
        cursor.execute("""
            INSERT OR IGNORE INTO sportsbook_operators (name, domain, status, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ('Test Sportsbook', 'test.local', 'active'))
        
        # Insert sample events
        cursor.execute("""
            INSERT OR IGNORE INTO events (goalserve_id, home_team, away_team, sport, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, ('341136', 'Hiroshima Carp', 'Chunichi Dragons', 'baseball', 'scheduled'))
        
        # Insert sample outcomes
        cursor.execute("""
            INSERT OR IGNORE INTO outcomes (event_id, name, odds, market_type, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (1, 'Hiroshima Carp', 2.5, 'match_result'))
        
        cursor.execute("""
            INSERT OR IGNORE INTO outcomes (event_id, name, odds, market_type, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (1, 'Chunichi Dragons', 1.8, 'match_result'))
        
        conn.commit()
        conn.close()
        
        print("✅ Local database setup complete!")
        print(f"Database file: {db_path}")
        print("\nSample data:")
        print("- Superadmin: superadmin / superadmin123")
        print("- Test user: am1111 / password123")
        print("- Sample event: Hiroshima Carp vs Chunichi Dragons (Baseball)")
        print("\n🚀 Now you can run: python run.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up local database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_local_database()
