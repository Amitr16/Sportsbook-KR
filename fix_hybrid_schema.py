#!/usr/bin/env python3
"""
Fix Hybrid Schema - SQLite compatible version
"""

import sqlite3
import os

def apply_hybrid_schema_sqlite():
    """Apply hybrid schema with SQLite compatibility"""
    print("📊 Applying SQLite-Compatible Hybrid Schema...")
    
    try:
        conn = sqlite3.connect('local_app.db')
        cursor = conn.cursor()
        
        # Helper function to add column if it doesn't exist
        def add_column_if_not_exists(table, column, definition):
            try:
                cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
                print(f"✅ {table}.{column} already exists")
            except sqlite3.OperationalError:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    print(f"✅ Added {table}.{column}")
                except Exception as e:
                    print(f"❌ Failed to add {table}.{column}: {e}")
        
        # Helper function to create table if it doesn't exist
        def create_table_if_not_exists(table_name, create_sql):
            try:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if cursor.fetchone():
                    print(f"✅ Table {table_name} already exists")
                else:
                    cursor.execute(create_sql)
                    print(f"✅ Created table {table_name}")
            except Exception as e:
                print(f"❌ Failed to create table {table_name}: {e}")
        
        print("\n🔧 Adding columns to existing tables...")
        
        # Add columns to users table
        add_column_if_not_exists('users', 'usdt_balance', 'DECIMAL(18,6) DEFAULT 0.000000')
        add_column_if_not_exists('users', 'aptos_wallet_address', 'VARCHAR(66)')
        add_column_if_not_exists('users', 'aptos_wallet_id', 'VARCHAR(255)')
        add_column_if_not_exists('users', 'web3_enabled', 'BOOLEAN DEFAULT FALSE')
        add_column_if_not_exists('users', 'usdt_contract', 'VARCHAR(100)')
        
        # Add columns to operator_wallets table
        add_column_if_not_exists('operator_wallets', 'usdt_balance', 'DECIMAL(18,6) DEFAULT 0.000000')
        add_column_if_not_exists('operator_wallets', 'aptos_wallet_address', 'VARCHAR(66)')
        add_column_if_not_exists('operator_wallets', 'aptos_wallet_id', 'VARCHAR(255)')
        add_column_if_not_exists('operator_wallets', 'usdt_contract', 'VARCHAR(100)')
        
        # Add columns to sportsbook_operators table
        add_column_if_not_exists('sportsbook_operators', 'web3_enabled', 'BOOLEAN DEFAULT FALSE')
        add_column_if_not_exists('sportsbook_operators', 'total_usdt_minted', 'DECIMAL(18,6) DEFAULT 0.000000')
        
        # Add columns to transactions table
        add_column_if_not_exists('transactions', 'usdt_amount', 'DECIMAL(18,6)')
        add_column_if_not_exists('transactions', 'aptos_transaction_hash', 'VARCHAR(66)')
        add_column_if_not_exists('transactions', 'usdt_contract', 'VARCHAR(100)')
        add_column_if_not_exists('transactions', 'web3_enabled', 'BOOLEAN DEFAULT FALSE')
        
        # Add columns to bets table
        add_column_if_not_exists('bets', 'usdt_stake', 'DECIMAL(18,6)')
        add_column_if_not_exists('bets', 'usdt_potential_return', 'DECIMAL(18,6)')
        add_column_if_not_exists('bets', 'usdt_actual_return', 'DECIMAL(18,6)')
        add_column_if_not_exists('bets', 'aptos_bet_transaction_hash', 'VARCHAR(66)')
        add_column_if_not_exists('bets', 'aptos_settlement_transaction_hash', 'VARCHAR(66)')
        add_column_if_not_exists('bets', 'on_chain', 'BOOLEAN DEFAULT FALSE')
        
        print("\n🏗️ Creating new tables...")
        
        # Create usdt_transactions table
        create_table_if_not_exists('usdt_transactions', '''
            CREATE TABLE usdt_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type VARCHAR(20) NOT NULL,
                entity_id INTEGER NOT NULL,
                wallet_type VARCHAR(50),
                transaction_type VARCHAR(30) NOT NULL,
                from_wallet VARCHAR(66),
                to_wallet VARCHAR(66),
                usdt_amount DECIMAL(18,6) NOT NULL,
                aptos_transaction_hash VARCHAR(66),
                usdt_contract VARCHAR(255) NOT NULL,
                block_height INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP
            )
        ''')
        
        # Create usdt_revenue_distributions table
        create_table_if_not_exists('usdt_revenue_distributions', '''
            CREATE TABLE usdt_revenue_distributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id INTEGER NOT NULL,
                distribution_date DATE NOT NULL,
                total_profit_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                total_profit_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                bookmaker_share_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                bookmaker_share_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                community_share_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                community_share_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                kryzel_fee_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                kryzel_fee_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
                revenue_wallet_tx_hash VARCHAR(66),
                community_wallet_tx_hash VARCHAR(66),
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT,
                usdt_contract VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
                UNIQUE(operator_id, distribution_date)
            )
        ''')
        
        print("\n📊 Creating indexes...")
        
        # Create indexes (only if tables exist)
        indexes = [
            ("idx_usdt_tx_entity", "CREATE INDEX IF NOT EXISTS idx_usdt_tx_entity ON usdt_transactions(entity_type, entity_id)"),
            ("idx_usdt_tx_type", "CREATE INDEX IF NOT EXISTS idx_usdt_tx_type ON usdt_transactions(transaction_type)"),
            ("idx_usdt_tx_hash", "CREATE INDEX IF NOT EXISTS idx_usdt_tx_hash ON usdt_transactions(aptos_transaction_hash)"),
            ("idx_usdt_tx_status", "CREATE INDEX IF NOT EXISTS idx_usdt_tx_status ON usdt_transactions(status)"),
            ("idx_usdt_revenue_date", "CREATE INDEX IF NOT EXISTS idx_usdt_revenue_date ON usdt_revenue_distributions(operator_id, distribution_date)"),
            ("idx_usdt_revenue_status", "CREATE INDEX IF NOT EXISTS idx_usdt_revenue_status ON usdt_revenue_distributions(status)")
        ]
        
        for index_name, index_sql in indexes:
            try:
                cursor.execute(index_sql)
                print(f"✅ Created index: {index_name}")
            except Exception as e:
                print(f"⚠️ Index {index_name}: {e}")
        
        print("\n🔄 Setting default values...")
        
        # Set default USDT contract for existing records
        usdt_contract = "0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT"
        
        try:
            cursor.execute("UPDATE operator_wallets SET usdt_contract = ? WHERE usdt_contract IS NULL", (usdt_contract,))
            print("✅ Updated operator_wallets usdt_contract")
        except Exception as e:
            print(f"⚠️ operator_wallets update: {e}")
        
        try:
            cursor.execute("UPDATE transactions SET usdt_contract = ? WHERE usdt_contract IS NULL", (usdt_contract,))
            print("✅ Updated transactions usdt_contract")
        except Exception as e:
            print(f"⚠️ transactions update: {e}")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Schema application completed successfully!")
        
        # Verify schema
        print("\n🔍 Verifying schema...")
        conn = sqlite3.connect('local_app.db')
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        hybrid_user_cols = ['usdt_balance', 'aptos_wallet_address', 'web3_enabled']
        
        for col in hybrid_user_cols:
            if col in user_columns:
                print(f"✅ users.{col} exists")
            else:
                print(f"❌ users.{col} missing")
        
        # Check operator_wallets table
        cursor.execute("PRAGMA table_info(operator_wallets)")
        wallet_columns = [col[1] for col in cursor.fetchall()]
        hybrid_wallet_cols = ['usdt_balance', 'aptos_wallet_address']
        
        for col in hybrid_wallet_cols:
            if col in wallet_columns:
                print(f"✅ operator_wallets.{col} exists")
            else:
                print(f"❌ operator_wallets.{col} missing")
        
        # Check new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%usdt%'")
        usdt_tables = cursor.fetchall()
        
        if usdt_tables:
            print(f"✅ USDT tables created: {[table[0] for table in usdt_tables]}")
        else:
            print("⚠️ No USDT tables found")
        
        conn.close()
        
        print("\n🎉 Hybrid schema is ready!")
        return True
        
    except Exception as e:
        print(f"❌ Schema application failed: {e}")
        return False

if __name__ == "__main__":
    apply_hybrid_schema_sqlite()
