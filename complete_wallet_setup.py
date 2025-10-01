#!/usr/bin/env python3
"""
Complete Wallet Integration Setup
Sets up the entire database with Aptos wallet support
"""

import os
import sqlite3
from datetime import datetime

def setup_complete_wallet_database():
    """Create complete database with both traditional and Aptos wallet support"""
    
    # Set database URL
    os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
    
    # Connect to SQLite
    conn = sqlite3.connect('local_app.db')
    cursor = conn.cursor()
    
    print("🔄 Setting up complete wallet database...")
    
    # 1. Create core sportsbook operators table
    print("📊 Creating sportsbook_operators table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sportsbook_operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sportsbook_name TEXT NOT NULL UNIQUE,
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT NOT NULL,
            subdomain TEXT NOT NULL UNIQUE,
            settings TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            total_revenue REAL DEFAULT 0.0,
            
            -- Aptos wallet fields
            aptos_wallet_address TEXT,
            aptos_wallet_id TEXT,
            web3_enabled BOOLEAN DEFAULT FALSE,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Create users table
    print("👥 Creating users table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 1000.0,
            sportsbook_operator_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            
            -- Aptos wallet fields
            aptos_wallet_address TEXT,
            aptos_wallet_id TEXT,
            web3_enabled BOOLEAN DEFAULT FALSE,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id),
            UNIQUE(username, sportsbook_operator_id),
            UNIQUE(email, sportsbook_operator_id)
        )
    """)
    
    # 3. Create operator wallets (4-wallet system)
    print("💰 Creating operator_wallets table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operator_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_id INTEGER NOT NULL,
            wallet_type TEXT NOT NULL,
            current_balance REAL DEFAULT 0.0,
            initial_balance REAL DEFAULT 0.0,
            leverage_multiplier REAL DEFAULT 1.0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
            UNIQUE(operator_id, wallet_type)
        )
    """)
    
    # 4. Create bets table
    print("🎯 Creating bets table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_id TEXT,
            selection TEXT NOT NULL,
            odds REAL NOT NULL,
            stake REAL NOT NULL,
            potential_return REAL NOT NULL,
            actual_return REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            match_name TEXT,
            bet_selection TEXT,
            sport_name TEXT,
            bet_timing TEXT,
            market TEXT,
            sportsbook_operator_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            event_time TIMESTAMP,
            placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP,
            
            -- Aptos blockchain fields
            aptos_transaction_hash TEXT,
            on_chain BOOLEAN DEFAULT FALSE,
            settlement_tx_hash TEXT,
            
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
        )
    """)
    
    # 5. Create transactions table
    print("💳 Creating transactions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bet_id INTEGER,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            description TEXT,
            balance_before REAL NOT NULL,
            balance_after REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (bet_id) REFERENCES bets(id)
        )
    """)
    
    # 6. Create Aptos transactions table
    print("🔗 Creating aptos_transactions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aptos_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_hash TEXT UNIQUE NOT NULL,
            transaction_type TEXT NOT NULL,
            from_address TEXT,
            to_address TEXT,
            amount REAL,
            token_type TEXT DEFAULT 'APT',
            status TEXT DEFAULT 'pending',
            block_number INTEGER,
            gas_used INTEGER,
            gas_price REAL,
            operator_id INTEGER,
            user_id INTEGER,
            bet_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            
            FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (bet_id) REFERENCES bets(id)
        )
    """)
    
    # 7. Create revenue calculations table
    print("📈 Creating revenue_calculations table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue_calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_id INTEGER NOT NULL,
            calculation_date DATE NOT NULL,
            total_revenue REAL DEFAULT 0.0,
            total_bets_amount REAL DEFAULT 0.0,
            total_payouts REAL DEFAULT 0.0,
            bookmaker_own_share REAL DEFAULT 0.0,
            kryzel_fee_from_own REAL DEFAULT 0.0,
            bookmaker_net_own REAL DEFAULT 0.0,
            remaining_profit REAL DEFAULT 0.0,
            bookmaker_share_60 REAL DEFAULT 0.0,
            community_share_30 REAL DEFAULT 0.0,
            kryzel_share_10 REAL DEFAULT 0.0,
            bookmaker_own_loss REAL DEFAULT 0.0,
            remaining_loss REAL DEFAULT 0.0,
            bookmaker_loss_70 REAL DEFAULT 0.0,
            community_loss_30 REAL DEFAULT 0.0,
            total_bookmaker_earnings REAL DEFAULT 0.0,
            calculation_metadata TEXT DEFAULT 'false',
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
            UNIQUE(operator_id, calculation_date)
        )
    """)
    
    # Create indexes for performance
    print("📊 Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_operator ON users(sportsbook_operator_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bets_user ON bets(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bets_operator ON bets(sportsbook_operator_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_aptos_tx_hash ON aptos_transactions(transaction_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_operator_wallets_operator ON operator_wallets(operator_id)")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("✅ Complete wallet database setup completed!")
    print("📊 Tables created:")
    print("   - sportsbook_operators (with Aptos wallet fields)")
    print("   - users (with Aptos wallet fields)")
    print("   - operator_wallets (4-wallet system)")
    print("   - bets (with on-chain support)")
    print("   - transactions (traditional)")
    print("   - aptos_transactions (blockchain)")
    print("   - revenue_calculations")

def create_test_data():
    """Create test operator and user data"""
    conn = sqlite3.connect('local_app.db')
    cursor = conn.cursor()
    
    print("\n🧪 Creating test data...")
    
    # Create test operator
    cursor.execute("""
        INSERT OR IGNORE INTO sportsbook_operators 
        (sportsbook_name, login, password_hash, email, subdomain, web3_enabled)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        'Test Sportsbook',
        'admin',
        'hashed_password_123',
        'admin@testsportsbook.com',
        'testsportsbook',
        True
    ))
    
    operator_id = cursor.lastrowid or 1
    
    # Create 4 wallets for operator
    wallets = [
        ('bookmaker_capital', 10000.0, 10000.0, 1.0),
        ('liquidity_pool', 40000.0, 40000.0, 5.0),
        ('revenue', 0.0, 0.0, 1.0),
        ('bookmaker_earnings', 0.0, 0.0, 1.0)
    ]
    
    for wallet_type, current_balance, initial_balance, leverage in wallets:
        cursor.execute("""
            INSERT OR IGNORE INTO operator_wallets
            (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
            VALUES (?, ?, ?, ?, ?)
        """, (operator_id, wallet_type, current_balance, initial_balance, leverage))
    
    # Create test user
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, email, password_hash, balance, sportsbook_operator_id, web3_enabled)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        'testuser',
        'user@test.com',
        'hashed_password_user',
        1000.0,
        operator_id,
        True
    ))
    
    conn.commit()
    conn.close()
    
    print("✅ Test data created:")
    print(f"   - Test Operator: testsportsbook (ID: {operator_id})")
    print("   - 4 operator wallets created")
    print("   - Test user: testuser")

if __name__ == "__main__":
    setup_complete_wallet_database()
    create_test_data()
    print("\n🎉 Complete wallet setup finished!")
    print("💡 Ready for Aptos integration testing!")
