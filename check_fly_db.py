#!/usr/bin/env python3
"""Check Fly.io database for tables and superadmin user"""

import os
import psycopg2

def check_database():
    """Check database tables and superadmin user"""
    try:
        # Connect to database
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        print("🔍 Checking Fly.io database...")
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check if users table exists and has data
        if any('users' in table[0].lower() for table in tables):
            print("\n👥 Users table found, checking for superadmin...")
            
            # Look for users table (case insensitive)
            users_table = None
            for table in tables:
                if 'users' in table[0].lower():
                    users_table = table[0]
                    break
            
            if users_table:
                cur.execute(f"SELECT COUNT(*) FROM {users_table}")
                user_count = cur.fetchone()[0]
                print(f"  - Total users: {user_count}")
                
                # Check for superadmin
                try:
                    cur.execute(f"SELECT * FROM {users_table} WHERE username = 'superadmin' OR email = 'superadmin' LIMIT 1")
                    superadmin = cur.fetchone()
                    if superadmin:
                        print("  ✅ Superadmin user found!")
                        print(f"     Data: {superadmin}")
                    else:
                        print("  ❌ Superadmin user NOT found")
                except Exception as e:
                    print(f"  ⚠️  Error checking superadmin: {e}")
        
        # Check if sportsbook_operators table exists
        if any('sportsbook_operators' in table[0].lower() for table in tables):
            print("\n🏪 Sportsbook operators table found, checking data...")
            try:
                cur.execute("SELECT COUNT(*) FROM sportsbook_operators")
                op_count = cur.fetchone()[0]
                print(f"  - Total operators: {op_count}")
                
                if op_count > 0:
                    cur.execute("SELECT * FROM sportsbook_operators LIMIT 3")
                    operators = cur.fetchall()
                    print("  - Sample operators:")
                    for op in operators:
                        print(f"    {op}")
            except Exception as e:
                print(f"  ⚠️  Error checking operators: {e}")
        
        conn.close()
        print("\n✅ Database check completed")
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")

if __name__ == "__main__":
    check_database()
