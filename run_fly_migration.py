"""
Run database migration on Fly.io production database
"""
import os
import psycopg

# Fly.io production database URL
# Get this from: fly secrets list
FLY_DATABASE_URL = input("Enter your Fly.io DATABASE_URL (from 'fly secrets list'): ").strip()

if not FLY_DATABASE_URL:
    print("ERROR: DATABASE_URL is required")
    exit(1)

print("\nConnecting to Fly.io production database...")

try:
    with psycopg.connect(FLY_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            print("Connected successfully!")
            
            # Check if columns already exist
            print("\nChecking existing columns...")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'operator_wallets' 
                AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
            """)
            existing = cur.fetchall()
            
            if existing:
                print(f"Columns already exist: {existing}")
                print("Migration may have already been run.")
            else:
                print("Columns do not exist. Running migration...")
            
            # Add columns
            print("\nAdding web3_wallet_address and web3_wallet_key columns...")
            cur.execute("""
                ALTER TABLE operator_wallets 
                ADD COLUMN IF NOT EXISTS web3_wallet_address VARCHAR(255) UNIQUE,
                ADD COLUMN IF NOT EXISTS web3_wallet_key TEXT
            """)
            
            conn.commit()
            print("Migration completed successfully!")
            
            # Verify
            print("\nVerifying columns were added...")
            cur.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'operator_wallets' 
                AND column_name IN ('web3_wallet_address', 'web3_wallet_key')
            """)
            columns = cur.fetchall()
            
            if columns:
                print("\nColumns successfully added:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
            else:
                print("\nWARNING: Could not verify columns were added")
                
except Exception as e:
    print(f"\nERROR: Migration failed: {e}")
    exit(1)

print("\nMigration complete! You can now test operator registration on Fly.io.")

