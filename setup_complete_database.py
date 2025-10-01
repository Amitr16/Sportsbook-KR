#!/usr/bin/env python3
"""
Complete Database Setup - Creates all tables needed for the hybrid system
"""

import sqlite3
import os
from datetime import datetime

def setup_complete_database():
    """Set up the complete database with all required tables"""
    print("🗄️ Setting up Complete Database...")
    
    if os.path.exists('local_app.db'):
        backup_name = f'local_app_backup_{int(datetime.now().timestamp())}.db'
        os.rename('local_app.db', backup_name)
        print(f"📦 Backed up existing database to {backup_name}")
    
    try:
        conn = sqlite3.connect('local_app.db')
        cursor = conn.cursor()
        
        print("\n🏗️ Creating core tables...")
        
        # 1. Create sportsbook_operators table
        cursor.execute('''
            CREATE TABLE sportsbook_operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sportsbook_name VARCHAR(100) NOT NULL UNIQUE,
                login VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100) NOT NULL,
                subdomain VARCHAR(50) NOT NULL UNIQUE,
                total_revenue DECIMAL(10,2) DEFAULT 0.00,
                is_active BOOLEAN DEFAULT TRUE,
                web3_enabled BOOLEAN DEFAULT FALSE,
                total_usdt_minted DECIMAL(18,6) DEFAULT 0.000000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Created sportsbook_operators table")
        
        # 2. Create users table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                balance DECIMAL(10,2) DEFAULT 1000.00,
                usdt_balance DECIMAL(18,6) DEFAULT 0.000000,
                aptos_wallet_address VARCHAR(66),
                aptos_wallet_id VARCHAR(255),
                web3_enabled BOOLEAN DEFAULT FALSE,
                usdt_contract VARCHAR(100),
                sportsbook_operator_id INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id),
                UNIQUE(username, sportsbook_operator_id),
                UNIQUE(email, sportsbook_operator_id)
            )
        ''')
        print("✅ Created users table")
        
        # 3. Create operator_wallets table
        cursor.execute('''
            CREATE TABLE operator_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id INTEGER NOT NULL,
                wallet_type VARCHAR(50) NOT NULL,
                current_balance DECIMAL(10,2) NOT NULL DEFAULT 0.0,
                usdt_balance DECIMAL(18,6) DEFAULT 0.000000,
                aptos_wallet_address VARCHAR(66),
                aptos_wallet_id VARCHAR(255),
                usdt_contract VARCHAR(100),
                initial_balance DECIMAL(10,2) NOT NULL DEFAULT 0.0,
                leverage_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
                UNIQUE(operator_id, wallet_type)
            )
        ''')
        print("✅ Created operator_wallets table")
        
        # 4. Create bets table
        cursor.execute('''
            CREATE TABLE bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sportsbook_operator_id INTEGER,
                match_id VARCHAR(50) NOT NULL,
                match_name VARCHAR(200),
                selection VARCHAR(100) NOT NULL,
                bet_selection VARCHAR(100),
                sport_name VARCHAR(50),
                market VARCHAR(50),
                stake DECIMAL(10,2) NOT NULL,
                usdt_stake DECIMAL(18,6),
                odds DECIMAL(8,3) NOT NULL,
                potential_return DECIMAL(10,2) NOT NULL,
                usdt_potential_return DECIMAL(18,6),
                status VARCHAR(20) DEFAULT 'pending',
                bet_type VARCHAR(20) DEFAULT 'single',
                bet_timing VARCHAR(20) DEFAULT 'pregame',
                is_active BOOLEAN DEFAULT TRUE,
                actual_return DECIMAL(10,2),
                usdt_actual_return DECIMAL(18,6),
                aptos_bet_transaction_hash VARCHAR(66),
                aptos_settlement_transaction_hash VARCHAR(66),
                on_chain BOOLEAN DEFAULT FALSE,
                settled_at TIMESTAMP,
                combo_selections TEXT,
                event_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        ''')
        print("✅ Created bets table")
        
        # 5. Create transactions table
        cursor.execute('''
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bet_id INTEGER,
                amount DECIMAL(10,2) NOT NULL,
                usdt_amount DECIMAL(18,6),
                transaction_type VARCHAR(50) NOT NULL,
                description TEXT,
                balance_before DECIMAL(10,2),
                balance_after DECIMAL(10,2),
                aptos_transaction_hash VARCHAR(66),
                usdt_contract VARCHAR(100),
                web3_enabled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (bet_id) REFERENCES bets(id)
            )
        ''')
        print("✅ Created transactions table")
        
        # 6. Create matches table
        cursor.execute('''
            CREATE TABLE matches (
                id INTEGER PRIMARY KEY,
                home_team VARCHAR(100) NOT NULL,
                away_team VARCHAR(100) NOT NULL,
                match_date TIMESTAMP NOT NULL,
                league VARCHAR(100),
                status VARCHAR(20) DEFAULT 'upcoming',
                home_score INTEGER DEFAULT 0,
                away_score INTEGER DEFAULT 0,
                sportsbook_operator_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        ''')
        print("✅ Created matches table")
        
        # 7. Create odds table
        cursor.execute('''
            CREATE TABLE odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                market VARCHAR(50) NOT NULL,
                selection VARCHAR(100) NOT NULL,
                odds_value DECIMAL(8,3) NOT NULL,
                sportsbook_operator_id INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id),
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        ''')
        print("✅ Created odds table")
        
        # 8. Create revenue_calculations table
        cursor.execute('''
            CREATE TABLE revenue_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id INTEGER NOT NULL,
                calculation_date DATE NOT NULL,
                total_revenue DECIMAL(10,2) NOT NULL,
                total_bets_amount DECIMAL(10,2) DEFAULT 0,
                total_payouts DECIMAL(10,2) DEFAULT 0,
                bookmaker_own_share DECIMAL(10,2) DEFAULT 0,
                kryzel_fee_from_own DECIMAL(10,2) DEFAULT 0,
                bookmaker_net_own DECIMAL(10,2) DEFAULT 0,
                community_share_30 DECIMAL(10,2) DEFAULT 0,
                remaining_profit DECIMAL(10,2) DEFAULT 0,
                calculation_metadata TEXT DEFAULT 'false',
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id)
            )
        ''')
        print("✅ Created revenue_calculations table")
        
        print("\n🔗 Creating USDT tables...")
        
        # 9. Create usdt_transactions table
        cursor.execute('''
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
        print("✅ Created usdt_transactions table")
        
        # 10. Create usdt_revenue_distributions table
        cursor.execute('''
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
        print("✅ Created usdt_revenue_distributions table")
        
        print("\n📊 Creating indexes...")
        
        # Create indexes
        indexes = [
            "CREATE INDEX idx_users_operator ON users(sportsbook_operator_id)",
            "CREATE INDEX idx_users_username ON users(username)",
            "CREATE INDEX idx_bets_user ON bets(user_id)",
            "CREATE INDEX idx_bets_status ON bets(status)",
            "CREATE INDEX idx_transactions_user ON transactions(user_id)",
            "CREATE INDEX idx_usdt_tx_entity ON usdt_transactions(entity_type, entity_id)",
            "CREATE INDEX idx_usdt_tx_type ON usdt_transactions(transaction_type)",
            "CREATE INDEX idx_usdt_revenue_date ON usdt_revenue_distributions(operator_id, distribution_date)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            print(f"✅ Created index")
        
        print("\n🎯 Creating test data...")
        
        # Insert test operator
        cursor.execute('''
            INSERT INTO sportsbook_operators 
            (sportsbook_name, login, password_hash, email, subdomain, web3_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'Demo Sportsbook',
            'demo_admin',
            'pbkdf2:sha256:600000$demo$hash',  # password: demo123
            'demo@example.com',
            'demo-sportsbook',
            True
        ))
        
        operator_id = cursor.lastrowid
        print(f"✅ Created demo operator (ID: {operator_id})")
        
        # Create 4 operator wallets
        wallet_types = [
            ('bookmaker_capital', 10000.0, 10000.0),
            ('liquidity_pool', 40000.0, 40000.0),
            ('revenue', 0.0, 0.0),
            ('community', 0.0, 0.0)
        ]
        
        for wallet_type, usd_balance, usdt_balance in wallet_types:
            cursor.execute('''
                INSERT INTO operator_wallets 
                (operator_id, wallet_type, current_balance, usdt_balance, initial_balance)
                VALUES (?, ?, ?, ?, ?)
            ''', (operator_id, wallet_type, usd_balance, usdt_balance, usd_balance))
            print(f"✅ Created {wallet_type} wallet: ${usd_balance} USD, {usdt_balance} USDT")
        
        # Insert test match
        cursor.execute('''
            INSERT INTO matches 
            (id, home_team, away_team, match_date, league, status, sportsbook_operator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            1,
            'Test Team A',
            'Test Team B',
            datetime.now(),
            'Test League',
            'upcoming',
            operator_id
        ))
        print("✅ Created test match")
        
        # Insert test odds
        cursor.execute('''
            INSERT INTO odds 
            (match_id, market, selection, odds_value, sportsbook_operator_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'match_winner', 'Test Team A', 2.5, operator_id))
        
        cursor.execute('''
            INSERT INTO odds 
            (match_id, market, selection, odds_value, sportsbook_operator_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'match_winner', 'Test Team B', 1.8, operator_id))
        
        print("✅ Created test odds")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Complete database setup finished!")
        print("\n📋 What was created:")
        print("✅ All core tables (users, bets, transactions, etc.)")
        print("✅ All USDT hybrid tables")
        print("✅ All necessary indexes")
        print("✅ Demo operator with 4 wallets")
        print("✅ Test match and odds")
        
        print("\n🚀 Ready to test:")
        print("1. Start Flask: export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
        print("2. Register user: POST /api/auth/demo-sportsbook/register")
        print("3. Place bet: POST /api/demo-sportsbook/place_bet")
        
        return True
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_complete_database()
