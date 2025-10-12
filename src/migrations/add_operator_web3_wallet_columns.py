"""
Migration: Add Web3 wallet columns to operator_wallets table
"""

import os
import sys
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.db_compat import connection_ctx

def migrate_add_operator_web3_wallet_columns():
    """Add web3_wallet_address and web3_wallet_key columns to operator_wallets table"""
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                # Check if columns already exist
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'operator_wallets' 
                    AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
                """)
                
                existing_columns = [row['column_name'] for row in cursor.fetchall()]
                
                # Add web3_wallet_address column if it doesn't exist
                if 'web3_wallet_address' not in existing_columns:
                    cursor.execute("""
                        ALTER TABLE operator_wallets 
                        ADD COLUMN web3_wallet_address VARCHAR(255)
                    """)
                    print("Added web3_wallet_address column to operator_wallets table")
                else:
                    print("web3_wallet_address column already exists")
                
                # Add web3_wallet_key column if it doesn't exist
                if 'web3_wallet_key' not in existing_columns:
                    cursor.execute("""
                        ALTER TABLE operator_wallets 
                        ADD COLUMN web3_wallet_key TEXT
                    """)
                    print("Added web3_wallet_key column to operator_wallets table")
                else:
                    print("web3_wallet_key column already exists")
                
                conn.commit()
                print("Migration completed successfully")
                
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

def rollback_operator_web3_wallet_columns():
    """Remove web3_wallet_address and web3_wallet_key columns from operator_wallets table"""
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                # Remove web3_wallet_key column
                cursor.execute("""
                    ALTER TABLE operator_wallets 
                    DROP COLUMN IF EXISTS web3_wallet_key
                """)
                print("Removed web3_wallet_key column from operator_wallets table")
                
                # Remove web3_wallet_address column
                cursor.execute("""
                    ALTER TABLE operator_wallets 
                    DROP COLUMN IF EXISTS web3_wallet_address
                """)
                print("Removed web3_wallet_address column from operator_wallets table")
                
                conn.commit()
                print("Rollback completed successfully")
                
    except Exception as e:
        print(f"Rollback failed: {e}")
        raise

if __name__ == "__main__":
    print("Adding Web3 wallet columns to operator_wallets table...")
    migrate_add_operator_web3_wallet_columns()
