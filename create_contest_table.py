#!/usr/bin/env python3
"""
Create contest table to store contest end dates
"""

import os
import sys
sys.path.append('/app')

# Load environment variables
from dotenv import load_dotenv
load_dotenv('env.local')

from src import sqlite3_shim as sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_contest_table():
    """Create contest table to store contest end dates"""
    conn = None
    try:
        conn = sqlite3.connect()
        cursor = conn.cursor()
        
        # Create contest table
        logger.info("🔧 Creating contest table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contest_dates (
                id SERIAL PRIMARY KEY,
                contest_name VARCHAR(255) NOT NULL,
                contest_end_date TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        logger.info("✅ Contest table created successfully")
        
        conn.commit()
        logger.info("🎉 Contest table setup completed!")
        
    except Exception as e:
        logger.error(f"❌ Failed to create contest table: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_contest_table()
