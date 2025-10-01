#!/usr/bin/env python3
"""
Manual Test Guide - Step by step testing of hybrid system
"""

import sqlite3
import os
import json

def show_test_guide():
    """Show step-by-step manual testing guide"""
    
    print("🧪 HYBRID SYSTEM MANUAL TEST GUIDE")
    print("=" * 60)
    
    print("\n📋 PREREQUISITES:")
    print("1. Flask app running: export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
    print("2. Database schema applied: python3 apply_hybrid_schema.py")
    print("3. Crossmint API keys in env.aptos file")
    
    print("\n🔄 TEST FLOW:")
    
    print("\n" + "="*50)
    print("STEP 1: REGISTER OPERATOR WITH 4 USDT WALLETS")
    print("="*50)
    
    print("""
POST http://localhost:5000/register-sportsbook
Content-Type: application/json

{
    "sportsbook_name": "Test Sportsbook",
    "login": "test_admin",
    "password": "password123",
    "email": "test@example.com",
    "enable_web3": true
}

✅ EXPECTED RESULT:
- 4 Aptos wallets created via Crossmint
- USDT minted to bookmaker_capital (10,000) and liquidity_pool (40,000)
- Response includes aptos_wallets with addresses and USDT balances
""")

    print("\n" + "="*50)
    print("STEP 2: REGISTER USER WITH USDT WALLET")
    print("="*50)
    
    print("""
POST http://localhost:5000/api/auth/test-sportsbook/register
Content-Type: application/json

{
    "username": "test_user",
    "email": "user@example.com", 
    "password": "password123",
    "enable_web3": true
}

✅ EXPECTED RESULT:
- 1 Aptos wallet created via Crossmint
- 1,000 USDT minted to user wallet
- Response includes aptos_wallet address and usdt_balance: 1000
""")

    print("\n" + "="*50)
    print("STEP 3: LOGIN USER")
    print("="*50)
    
    print("""
POST http://localhost:5000/api/auth/test-sportsbook/login
Content-Type: application/json

{
    "username": "test_user",
    "password": "password123"
}

✅ EXPECTED RESULT:
- Login successful
- Session created for betting
""")

    print("\n" + "="*50)
    print("STEP 4: PLACE BET (USDT DEDUCTION)")
    print("="*50)
    
    print("""
First create a test match in database, then:

POST http://localhost:5000/api/test-sportsbook/place_bet
Content-Type: application/json

{
    "match_id": 1,
    "market": "match_winner",
    "selection": "Team A",
    "stake": 100,
    "odds": 2.5
}

✅ EXPECTED RESULT:
- USD balance: 1000 → 900
- USDT balance: 1000 → 900  
- USDT transferred from user wallet to operator revenue wallet
- Response shows both usd_balance and usdt_balance
""")

    print("\n" + "="*50)
    print("STEP 5: SETTLE BET (USDT PAYOUT)")
    print("="*50)
    
    print("""
POST http://localhost:5000/api/test-sportsbook/manual_settle_bets
Content-Type: application/json

{
    "match_id": 1,
    "market": "match_winner", 
    "winning_selection": "Team A"
}

✅ EXPECTED RESULT:
- USD balance: 900 → 1150 (won 250)
- USDT balance: 900 → 1150
- USDT transferred from operator revenue wallet to user wallet
- Bet status changed to 'won'
""")

    print("\n" + "="*50)
    print("STEP 6: REVENUE DISTRIBUTION")
    print("="*50)
    
    print("""
Run: python3 hybrid_revenue_calculator.py

✅ EXPECTED RESULT:
- Calculates daily profit/loss
- Distributes USD and USDT to operator wallets
- Updates bookmaker_capital and community wallets
- Creates usdt_revenue_distributions record
""")

    print("\n" + "="*50)
    print("VERIFICATION QUERIES")
    print("="*50)
    
    print("""
Check balances in database:

-- User balances
SELECT username, balance, usdt_balance, web3_enabled, aptos_wallet_address 
FROM users WHERE username = 'test_user';

-- Operator wallet balances  
SELECT wallet_type, current_balance, usdt_balance, aptos_wallet_address
FROM operator_wallets 
WHERE operator_id = (SELECT id FROM sportsbook_operators WHERE sportsbook_name = 'Test Sportsbook');

-- USDT transactions
SELECT * FROM usdt_transactions ORDER BY created_at DESC LIMIT 10;

-- Revenue distributions
SELECT * FROM usdt_revenue_distributions ORDER BY distribution_date DESC LIMIT 5;
""")

def check_database_status():
    """Check current database status"""
    
    print("\n🔍 CURRENT DATABASE STATUS:")
    print("=" * 40)
    
    if not os.path.exists('local_app.db'):
        print("❌ Database file not found")
        return
    
    try:
        conn = sqlite3.connect('local_app.db')
        cursor = conn.cursor()
        
        # Check operators
        cursor.execute("SELECT COUNT(*) FROM sportsbook_operators")
        operator_count = cursor.fetchone()[0]
        print(f"📊 Operators: {operator_count}")
        
        if operator_count > 0:
            cursor.execute("SELECT sportsbook_name, web3_enabled FROM sportsbook_operators LIMIT 3")
            operators = cursor.fetchall()
            for op in operators:
                print(f"  - {op[0]} (Web3: {op[1]})")
        
        # Check users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 Users: {user_count}")
        
        if user_count > 0:
            cursor.execute("SELECT username, balance, usdt_balance, web3_enabled FROM users LIMIT 3")
            users = cursor.fetchall()
            for user in users:
                print(f"  - {user[0]}: ${user[1]} USD, {user[2] or 0} USDT (Web3: {user[3]})")
        
        # Check operator wallets
        cursor.execute("SELECT COUNT(*) FROM operator_wallets")
        wallet_count = cursor.fetchone()[0]
        print(f"🏦 Operator Wallets: {wallet_count}")
        
        if wallet_count > 0:
            cursor.execute("""
                SELECT ow.wallet_type, ow.current_balance, ow.usdt_balance, 
                       CASE WHEN ow.aptos_wallet_address IS NOT NULL THEN 'Yes' ELSE 'No' END
                FROM operator_wallets ow LIMIT 5
            """)
            wallets = cursor.fetchall()
            for wallet in wallets:
                print(f"  - {wallet[0]}: ${wallet[1] or 0} USD, {wallet[2] or 0} USDT (Aptos: {wallet[3]})")
        
        # Check bets
        cursor.execute("SELECT COUNT(*) FROM bets")
        bet_count = cursor.fetchone()[0]
        print(f"🎲 Bets: {bet_count}")
        
        # Check USDT transactions
        cursor.execute("SELECT COUNT(*) FROM usdt_transactions")
        usdt_tx_count = cursor.fetchone()[0]
        print(f"💱 USDT Transactions: {usdt_tx_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")

def show_curl_commands():
    """Show curl commands for easy testing"""
    
    print("\n🌐 CURL COMMANDS FOR TESTING:")
    print("=" * 40)
    
    print("""
# 1. Register Operator
curl -X POST http://localhost:5000/register-sportsbook \\
  -H "Content-Type: application/json" \\
  -d '{
    "sportsbook_name": "Test Sportsbook",
    "login": "test_admin", 
    "password": "password123",
    "email": "test@example.com",
    "enable_web3": true
  }'

# 2. Register User  
curl -X POST http://localhost:5000/api/auth/test-sportsbook/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "test_user",
    "email": "user@example.com",
    "password": "password123", 
    "enable_web3": true
  }'

# 3. Login User
curl -X POST http://localhost:5000/api/auth/test-sportsbook/login \\
  -H "Content-Type: application/json" \\
  -c cookies.txt \\
  -d '{
    "username": "test_user",
    "password": "password123"
  }'

# 4. Place Bet (after creating test match)
curl -X POST http://localhost:5000/api/test-sportsbook/place_bet \\
  -H "Content-Type: application/json" \\
  -b cookies.txt \\
  -d '{
    "match_id": 1,
    "market": "match_winner",
    "selection": "Team A", 
    "stake": 100,
    "odds": 2.5
  }'
""")

if __name__ == "__main__":
    show_test_guide()
    check_database_status()
    show_curl_commands()
    
    print("\n🎯 QUICK START:")
    print("1. python3 apply_hybrid_schema.py")
    print("2. export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
    print("3. Follow the curl commands above")
    print("4. Check database with the SQL queries provided")
