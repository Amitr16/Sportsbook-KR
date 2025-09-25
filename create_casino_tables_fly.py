#!/usr/bin/env python3
"""
Create casino tables in Fly.io production database
This script creates the necessary tables for casino functionality
"""

import os
import psycopg2
from dotenv import load_dotenv
import sys

def get_production_db_connection():
    """Get connection to production database"""
    try:
        # Get database URL from environment (set in Fly.io)
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("ERROR: DATABASE_URL not found in environment variables")
            print("Make sure DATABASE_URL is set in your Fly.io app environment")
            return None
            
        print(f"Connecting to production database...")
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"ERROR: Error connecting to database: {e}")
        return None

def create_casino_tables(conn):
    """Create casino-related tables"""
    cursor = conn.cursor()
    
    try:
        print("Creating casino tables...")
        
        # Create game_round table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_round (
                id SERIAL PRIMARY KEY,
                game_key VARCHAR(50) NOT NULL,
                user_id VARCHAR(100) NOT NULL,
                stake DECIMAL(10,2) NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'USD',
                payout DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                ref VARCHAR(100),
                result_json JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("SUCCESS: Created game_round table")
        
        # Create index for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_round_user_id 
            ON game_round(user_id);
        """)
        print("SUCCESS: Created index on game_round.user_id")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_round_created_at 
            ON game_round(created_at DESC);
        """)
        print("SUCCESS: Created index on game_round.created_at")
        
        # Create casino_sessions table for tracking active games
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS casino_sessions (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL,
                operator_id VARCHAR(100) NOT NULL,
                game_type VARCHAR(50) NOT NULL,
                session_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("SUCCESS: Created casino_sessions table")
        
        # Create index for casino_sessions
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_casino_sessions_user_id 
            ON casino_sessions(user_id);
        """)
        print("SUCCESS: Created index on casino_sessions.user_id")
        
        # Commit all changes
        conn.commit()
        print("SUCCESS: All casino tables created successfully!")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Error creating tables: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def verify_tables(conn):
    """Verify that tables were created correctly"""
    cursor = conn.cursor()
    
    try:
        print("Verifying table creation...")
        
        # Check game_round table
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'game_round'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print(f"SUCCESS: game_round table has {len(columns)} columns:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")
        
        # Check casino_sessions table
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'casino_sessions'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print(f"SUCCESS: casino_sessions table has {len(columns)} columns:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Error verifying tables: {e}")
        return False
    finally:
        cursor.close()

def main():
    """Main function"""
    print("Creating casino tables in Fly.io production database...")
    
    # Connect to database
    conn = get_production_db_connection()
    if not conn:
        print("ERROR: Failed to connect to database")
        sys.exit(1)
    
    try:
        # Create tables
        if not create_casino_tables(conn):
            print("ERROR: Failed to create tables")
            sys.exit(1)
        
        # Verify tables
        if not verify_tables(conn):
            print("ERROR: Failed to verify tables")
            sys.exit(1)
        
        print("\nSUCCESS: Casino tables setup completed successfully!")
        print("\nNext steps:")
        print("1. Deploy the updated Flask app: flyctl deploy")
        print("2. Test casino functionality in production")
        print("3. Check logs: flyctl logs")
        
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
