#!/usr/bin/env python3
"""
Database migration script to add trade_count column to Partner_leader_backup table
This script runs during application startup to ensure the column exists
"""

import os
import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv('env.local')

from src.db_compat import get_connection

def add_trade_count_column():
    """Add trade_count column to Partner_leader_backup table if it doesn't exist"""
    conn = None
    try:
        print("Adding trade_count column to Partner_leader_backup table...")
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'partner_leader_backup' AND column_name = 'trade_count'
        """)
        
        if cursor.fetchone():
            print("trade_count column already exists in Partner_leader_backup")
        else:
            # Add the column
            cursor.execute("""
                ALTER TABLE Partner_leader_backup 
                ADD COLUMN trade_count INTEGER DEFAULT 0
            """)
            print("Added trade_count column to Partner_leader_backup")
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_trade_count_column()
