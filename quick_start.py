#!/usr/bin/env python3
"""
Quick Start - Simple setup and launch
"""

import os
import sys
import sqlite3
from datetime import datetime

def quick_setup():
    """Quick database setup and app start"""
    
    print("🚀 QUICK HYBRID SYSTEM SETUP")
    print("=" * 40)
    
    # Set environment
    os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
    
    print("\n📊 Creating database...")
    
    # Remove old database
    if os.path.exists('local_app.db'):
        os.remove('local_app.db')
        print("✅ Removed old database")
    
    # Create new database with essential tables
    conn = sqlite3.connect('local_app.db')
    cursor = conn.cursor()
    
    # Create sportsbook_operators
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create users
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
            sportsbook_operator_id INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
        )
    ''')
    
    # Create operator_wallets
    cursor.execute('''
        CREATE TABLE operator_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_id INTEGER NOT NULL,
            wallet_type VARCHAR(50) NOT NULL,
            current_balance DECIMAL(10,2) NOT NULL DEFAULT 0.0,
            usdt_balance DECIMAL(18,6) DEFAULT 0.000000,
            aptos_wallet_address VARCHAR(66),
            aptos_wallet_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
            UNIQUE(operator_id, wallet_type)
        )
    ''')
    
    # Create bets
    cursor.execute('''
        CREATE TABLE bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sportsbook_operator_id INTEGER,
            match_id VARCHAR(50) NOT NULL,
            match_name VARCHAR(200),
            selection VARCHAR(100) NOT NULL,
            sport_name VARCHAR(50),
            market VARCHAR(50),
            stake DECIMAL(10,2) NOT NULL,
            usdt_stake DECIMAL(18,6),
            odds DECIMAL(8,3) NOT NULL,
            potential_return DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            actual_return DECIMAL(10,2),
            usdt_actual_return DECIMAL(18,6),
            on_chain BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create transactions
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
            web3_enabled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create matches
    cursor.execute('''
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            home_team VARCHAR(100) NOT NULL,
            away_team VARCHAR(100) NOT NULL,
            match_date TIMESTAMP NOT NULL,
            league VARCHAR(100),
            status VARCHAR(20) DEFAULT 'upcoming',
            sportsbook_operator_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create odds
    cursor.execute('''
        CREATE TABLE odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            market VARCHAR(50) NOT NULL,
            selection VARCHAR(100) NOT NULL,
            odds_value DECIMAL(8,3) NOT NULL,
            sportsbook_operator_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create USDT tables
    cursor.execute('''
        CREATE TABLE usdt_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type VARCHAR(20) NOT NULL,
            entity_id INTEGER NOT NULL,
            transaction_type VARCHAR(30) NOT NULL,
            usdt_amount DECIMAL(18,6) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    print("✅ Created all tables")
    
    # Insert demo data
    cursor.execute('''
        INSERT INTO sportsbook_operators 
        (sportsbook_name, login, password_hash, email, subdomain, web3_enabled)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        'Demo Sportsbook',
        'demo',
        'pbkdf2:sha256:600000$demo$hash',
        'demo@example.com',
        'demo-sportsbook',
        1
    ))
    
    operator_id = cursor.lastrowid
    
    # Create operator wallets
    wallets = [
        ('bookmaker_capital', 10000.0, 10000.0),
        ('liquidity_pool', 40000.0, 40000.0),
        ('revenue', 0.0, 0.0),
        ('community', 0.0, 0.0)
    ]
    
    for wallet_type, usd, usdt in wallets:
        cursor.execute('''
            INSERT INTO operator_wallets 
            (operator_id, wallet_type, current_balance, usdt_balance)
            VALUES (?, ?, ?, ?)
        ''', (operator_id, wallet_type, usd, usdt))
    
    # Insert test match
    cursor.execute('''
        INSERT INTO matches 
        (id, home_team, away_team, match_date, league, sportsbook_operator_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (1, 'Team A', 'Team B', datetime.now(), 'Test League', operator_id))
    
    # Insert test odds
    cursor.execute('''
        INSERT INTO odds 
        (match_id, market, selection, odds_value, sportsbook_operator_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (1, 'match_winner', 'Team A', 2.5, operator_id))
    
    conn.commit()
    conn.close()
    
    print("✅ Database setup complete!")
    print("\n🎯 READY TO TEST:")
    print("1. Start Flask: export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
    print("2. Test registration: POST /register-sportsbook")
    print("3. Test user reg: POST /api/auth/demo-sportsbook/register")
    
    return True

if __name__ == "__main__":
    quick_setup()
