#!/usr/bin/env python3
"""
Apply Hybrid Schema - Simple script to apply all hybrid wallet schemas
"""

import sqlite3
import os

def apply_hybrid_schema():
    """Apply the complete hybrid wallet schema"""
    print("📊 Applying Hybrid Wallet Schema...")
    
    try:
        conn = sqlite3.connect('local_app.db')
        
        # Read hybrid wallet schema
        if os.path.exists('hybrid_wallet_schema.sql'):
            print("📄 Reading hybrid_wallet_schema.sql...")
            with open('hybrid_wallet_schema.sql', 'r') as f:
                hybrid_schema = f.read()
        else:
            print("⚠️ hybrid_wallet_schema.sql not found")
            hybrid_schema = ""
        
        # Read USDT revenue schema
        if os.path.exists('usdt_revenue_schema.sql'):
            print("📄 Reading usdt_revenue_schema.sql...")
            with open('usdt_revenue_schema.sql', 'r') as f:
                revenue_schema = f.read()
        else:
            print("⚠️ usdt_revenue_schema.sql not found")
            revenue_schema = ""
        
        # Combine schemas
        all_schema = hybrid_schema + "\n" + revenue_schema
        
        # Split by semicolons and execute each statement
        statements = [stmt.strip() for stmt in all_schema.split(';') if stmt.strip()]
        
        executed_count = 0
        for stmt in statements:
            if stmt.startswith('--') or not stmt:
                continue
            
            try:
                conn.execute(stmt)
                executed_count += 1
                if 'CREATE TABLE' in stmt.upper():
                    table_name = stmt.split()[5] if len(stmt.split()) > 5 else "unknown"
                    print(f"✅ Created table: {table_name}")
                elif 'ALTER TABLE' in stmt.upper():
                    table_name = stmt.split()[2] if len(stmt.split()) > 2 else "unknown"
                    print(f"✅ Altered table: {table_name}")
                elif 'CREATE INDEX' in stmt.upper():
                    index_name = stmt.split()[4] if len(stmt.split()) > 4 else "unknown"
                    print(f"✅ Created index: {index_name}")
                elif 'CREATE VIEW' in stmt.upper():
                    view_name = stmt.split()[4] if len(stmt.split()) > 4 else "unknown"
                    print(f"✅ Created view: {view_name}")
                else:
                    print(f"✅ Executed statement")
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate column" in error_msg:
                    print(f"⚠️ Skipped (already exists): {stmt[:50]}...")
                else:
                    print(f"❌ Error: {e}")
                    print(f"   Statement: {stmt[:100]}...")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Schema application completed!")
        print(f"📊 Executed {executed_count} statements")
        
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
    apply_hybrid_schema()
