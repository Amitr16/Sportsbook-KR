"""
Database migration: Add Web3 wallet columns to users table

Adds:
- web3_wallet_address: Aptos blockchain address
- web3_wallet_key: Encrypted private key for the wallet
"""

import logging
from src.db_compat import connection_ctx

logger = logging.getLogger(__name__)


def migrate_add_web3_wallet_columns():
    """Add web3_wallet_address and web3_wallet_key columns to users table"""
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                print("Starting migration: add_web3_wallet_columns")
                
                # Check if columns already exist
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
                """)
                existing_columns = [row['column_name'] for row in cursor.fetchall()]
                
                # Add web3_wallet_address if it doesn't exist
                if 'web3_wallet_address' not in existing_columns:
                    print("Adding column: web3_wallet_address")
                    cursor.execute("""
                        ALTER TABLE users 
                        ADD COLUMN web3_wallet_address VARCHAR(255) UNIQUE
                    """)
                    conn.commit()
                    print("Added web3_wallet_address column")
                else:
                    print("Column web3_wallet_address already exists")
                
                # Add web3_wallet_key if it doesn't exist
                if 'web3_wallet_key' not in existing_columns:
                    print("Adding column: web3_wallet_key")
                    cursor.execute("""
                        ALTER TABLE users 
                        ADD COLUMN web3_wallet_key TEXT
                    """)
                    conn.commit()
                    print("Added web3_wallet_key column")
                else:
                    print("Column web3_wallet_key already exists")
                
                print("Migration completed successfully")
                return True
                
    except Exception as e:
        print(f"Migration failed: {e}")
        return False


def rollback_web3_wallet_columns():
    """Rollback: Remove web3_wallet columns from users table"""
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                logger.info("🔄 Rolling back migration: add_web3_wallet_columns")
                
                cursor.execute("""
                    ALTER TABLE users 
                    DROP COLUMN IF EXISTS web3_wallet_address,
                    DROP COLUMN IF EXISTS web3_wallet_key
                """)
                conn.commit()
                
                logger.info("✅ Rollback completed successfully")
                return True
                
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return False


if __name__ == "__main__":
    # Run migration directly
    migrate_add_web3_wallet_columns()

