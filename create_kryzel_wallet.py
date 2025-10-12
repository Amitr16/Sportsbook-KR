#!/usr/bin/env python3
"""
Create Global Kryzel Wallet
Creates a global Kryzel wallet to receive 10% platform fees from all operators
"""

import os
import sys
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables (same as main app)
from src.config.env_loader import *  # noqa: F401 - just to execute the loader

from src import sqlite3_shim as sqlite3

def get_db_connection():
    """Get database connection using the same method as the main app"""
    conn = sqlite3.connect()
    conn.row_factory = sqlite3.Row
    return conn

def create_global_kryzel_wallet():
    """Create a global Kryzel wallet (operator_id = 0) to receive platform fees"""
    
    conn = get_db_connection()
    
    try:
        # Check if Kryzel wallet already exists
        existing = conn.execute("""
            SELECT id FROM operator_wallets 
            WHERE operator_id = 0 AND wallet_type = 'kryzel_platform_fee'
        """).fetchone()
        
        if existing:
            print("Global Kryzel wallet already exists (ID: {})".format(existing['id']))
            return existing['id']
        
        # Create global Kryzel wallet (operator_id = 0)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO operator_wallets 
            (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            0, 'kryzel_platform_fee', 0.0, 0.0, 1.0, 
            datetime.now(), datetime.now()
        ))
        
        kryzel_wallet_id = cursor.lastrowid
        conn.commit()
        
        print("Created global Kryzel wallet:")
        print(f"   - ID: {kryzel_wallet_id}")
        print(f"   - Operator ID: 0 (global)")
        print(f"   - Wallet Type: kryzel_platform_fee")
        print(f"   - Initial Balance: $0.00")
        
        return kryzel_wallet_id
        
    except Exception as e:
        print(f"Failed to create Kryzel wallet: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    print("Creating Global Kryzel Wallet...")
    print("=" * 50)
    
    try:
        wallet_id = create_global_kryzel_wallet()
        print(f"\nGlobal Kryzel wallet created successfully!")
        print(f"   This wallet will receive 10% platform fees from all operators.")
        
    except Exception as e:
        print(f"\nFailed to create Kryzel wallet: {e}")
        sys.exit(1)
