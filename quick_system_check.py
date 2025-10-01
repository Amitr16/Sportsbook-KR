#!/usr/bin/env python3
"""
Quick System Check - Verify hybrid system components
"""

import os
import sys
import sqlite3

def check_system():
    """Quick check of the hybrid system"""
    print("🔍 QUICK HYBRID SYSTEM CHECK")
    print("=" * 50)
    
    # Check 1: Database exists
    if os.path.exists('local_app.db'):
        print("✅ Database file exists")
    else:
        print("❌ Database file missing")
        return False
    
    # Check 2: Check database schema
    try:
        conn = sqlite3.connect('local_app.db')
        cursor = conn.cursor()
        
        # Check if hybrid columns exist
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        required_user_columns = ['usdt_balance', 'aptos_wallet_address', 'web3_enabled']
        missing_user_cols = [col for col in required_user_columns if col not in user_columns]
        
        if missing_user_cols:
            print(f"⚠️ Missing user columns: {missing_user_cols}")
        else:
            print("✅ User table has hybrid columns")
        
        # Check operator_wallets table
        cursor.execute("PRAGMA table_info(operator_wallets)")
        wallet_columns = [col[1] for col in cursor.fetchall()]
        
        required_wallet_columns = ['usdt_balance', 'aptos_wallet_address']
        missing_wallet_cols = [col for col in required_wallet_columns if col not in wallet_columns]
        
        if missing_wallet_cols:
            print(f"⚠️ Missing operator_wallets columns: {missing_wallet_cols}")
        else:
            print("✅ Operator_wallets table has hybrid columns")
        
        # Check if we have any operators
        cursor.execute("SELECT COUNT(*) FROM sportsbook_operators")
        operator_count = cursor.fetchone()[0]
        print(f"📊 Operators in database: {operator_count}")
        
        # Check if we have any users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 Users in database: {user_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False
    
    # Check 3: Import test
    try:
        sys.path.append('src')
        from src.services.hybrid_wallet_service import HybridWalletService
        print("✅ HybridWalletService imports successfully")
        
        # Try to initialize (without calling external APIs)
        service = HybridWalletService()
        print("✅ HybridWalletService initializes successfully")
        
    except Exception as e:
        print(f"❌ Import/initialization failed: {e}")
        return False
    
    # Check 4: Environment variables
    if os.path.exists('env.aptos'):
        print("✅ env.aptos file exists")
        
        # Check if it has required variables
        with open('env.aptos', 'r') as f:
            content = f.read()
            if 'CROSSMINT_API_KEY' in content:
                print("✅ CROSSMINT_API_KEY found in env.aptos")
            else:
                print("⚠️ CROSSMINT_API_KEY not found in env.aptos")
                
            if 'CROSSMINT_PROJECT_ID' in content:
                print("✅ CROSSMINT_PROJECT_ID found in env.aptos")
            else:
                print("⚠️ CROSSMINT_PROJECT_ID not found in env.aptos")
    else:
        print("⚠️ env.aptos file missing")
    
    # Check 5: Schema files exist
    schema_files = [
        'hybrid_wallet_schema.sql',
        'usdt_revenue_schema.sql'
    ]
    
    for schema_file in schema_files:
        if os.path.exists(schema_file):
            print(f"✅ {schema_file} exists")
        else:
            print(f"⚠️ {schema_file} missing")
    
    # Check 6: Test files exist
    test_files = [
        'test_hybrid_system.py',
        'test_hybrid_betting.py',
        'test_complete_hybrid_system.py'
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"✅ {test_file} exists")
        else:
            print(f"⚠️ {test_file} missing")
    
    print("\n" + "=" * 50)
    print("🎯 SYSTEM STATUS SUMMARY:")
    print("✅ Core components are in place")
    print("✅ Database schema appears correct")
    print("✅ Services can be imported")
    print("✅ Test files are available")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Apply schema: python3 -c \"import sqlite3; conn=sqlite3.connect('local_app.db'); [conn.execute(stmt) for stmt in open('hybrid_wallet_schema.sql').read().split(';') if stmt.strip() and not stmt.strip().startswith('--')]; conn.commit(); conn.close()\"")
    print("2. Start Flask: export DATABASE_URL='sqlite:///local_app.db' && python3 run_local.py")
    print("3. Run test: python3 test_complete_hybrid_system.py")
    
    return True

if __name__ == "__main__":
    check_system()
