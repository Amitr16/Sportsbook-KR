"""
Simple migration script to add Web3 columns to users table
Run this on Fly.io: fly ssh console -C "python migrate_users_web3_columns.py"
"""
import os
import sys

try:
    import psycopg
    from psycopg import rows
except ImportError:
    print("ERROR: psycopg not available")
    sys.exit(1)

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

print("Connecting to database...")

try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=rows.dict_row) as cur:
            print("Connected successfully!")
            
            # Check if columns already exist
            print("\nChecking existing columns in users table...")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
            """)
            existing = cur.fetchall()
            
            if len(existing) >= 2:
                print(f"Columns already exist in users table:")
                for col in existing:
                    print(f"  - {col['column_name']}: {col['data_type']}")
                print("\nMigration already completed. Exiting.")
                sys.exit(0)
            
            # Add columns
            print("\nAdding web3_wallet_address and web3_wallet_key columns to users table...")
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS web3_wallet_address VARCHAR(255) UNIQUE,
                ADD COLUMN IF NOT EXISTS web3_wallet_key TEXT
            """)
            
            conn.commit()
            print("Migration SQL executed successfully!")
            
            # Verify
            print("\nVerifying columns were added...")
            cur.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
                ORDER BY column_name
            """)
            columns = cur.fetchall()
            
            if columns:
                print("\nColumns successfully added to users table:")
                for col in columns:
                    print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
            else:
                print("\nWARNING: Could not verify columns were added")
                sys.exit(1)
                
except Exception as e:
    print(f"\nERROR: Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nUsers table migration complete!")
