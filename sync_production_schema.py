#!/usr/bin/env python3
"""
Sync production database schema to match local database
This script adds missing columns to make production match local structure
"""

import os
import sys
sys.path.append('/app')

from src import sqlite3_shim as sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_production_schema():
    """Make production database match local schema"""
    conn = None
    try:
        conn = sqlite3.connect()
        cursor = conn.cursor()
        
        # Add missing columns to Partner_leader_backup
        missing_columns = [
            ("subdomain", "VARCHAR(255)"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_type in missing_columns:
            logger.info(f"🔧 Adding {column_name} column to Partner_leader_backup...")
            try:
                cursor.execute(f"ALTER TABLE Partner_leader_backup ADD COLUMN {column_name} {column_type}")
                logger.info(f"✅ Added {column_name} to Partner_leader_backup")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"✅ {column_name} already exists in Partner_leader_backup")
                else:
                    logger.error(f"❌ Failed to add {column_name} to Partner_leader_backup: {e}")
        
        # Add missing columns to User_leader_backup
        missing_user_columns = [
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_type in missing_user_columns:
            logger.info(f"🔧 Adding {column_name} column to User_leader_backup...")
            try:
                cursor.execute(f"ALTER TABLE User_leader_backup ADD COLUMN {column_name} {column_type}")
                logger.info(f"✅ Added {column_name} to User_leader_backup")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"✅ {column_name} already exists in User_leader_backup")
                else:
                    logger.error(f"❌ Failed to add {column_name} to User_leader_backup: {e}")
        
        conn.commit()
        logger.info("🎉 Production schema synced successfully!")
        
        # Verify the final structure
        logger.info("🔍 Verifying final table structures...")
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'user_leader_backup' ORDER BY ordinal_position")
        user_columns = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 User_leader_backup columns: {user_columns}")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'partner_leader_backup' ORDER BY ordinal_position")
        partner_columns = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 Partner_leader_backup columns: {partner_columns}")
        
    except Exception as e:
        logger.error(f"❌ Failed to sync production schema: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sync_production_schema()
