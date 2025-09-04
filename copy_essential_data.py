#!/usr/bin/env python3
"""Copy essential data from local PostgreSQL to Fly.io database"""

import os
import psycopg2
import hashlib
import argparse

def hash_password(password):
    """Hash password using the same method as the app"""
    return hashlib.sha256(password.encode()).hexdigest()

def copy_essential_data():
    """Copy only essential data: superadmin, sportsbook operators, initial tenant"""
    
    # Local database connection
    local_conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="goalserve_sportsbook",
        user="postgres",
        password="admin"
    )
    
    # Fly.io database connection
    fly_conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    
    local_cur = local_conn.cursor()
    fly_cur = fly_conn.cursor()
    
    print("🚀 Starting essential data migration...")
    print("=" * 50)
    
    try:
        # 1. Copy sportsbook_operators
        print("📋 Copying sportsbook operators...")
        local_cur.execute("SELECT * FROM sportsbook_operators")
        operators = local_cur.fetchall()
        
        if operators:
            # Get column names
            local_cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'sportsbook_operators' ORDER BY ordinal_position")
            columns = [col[0] for col in local_cur.fetchall()]
            print(f"  - Found {len(operators)} operators")
            print(f"  - Columns: {', '.join(columns)}")
            
            # Insert into Fly.io
            for operator in operators:
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO sportsbook_operators ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT (subdomain) DO NOTHING"
                fly_cur.execute(insert_sql, operator)
            
            print(f"  ✅ Inserted {len(operators)} operators")
        else:
            print("  ⚠️  No operators found locally")
        
        # 2. Copy users (including superadmin)
        print("\n👥 Copying users (including superadmin)...")
        local_cur.execute("SELECT * FROM users")
        users = local_cur.fetchall()
        
        if users:
            # Get column names
            local_cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position")
            columns = [col[0] for col in local_cur.fetchall()]
            print(f"  - Found {len(users)} users")
            print(f"  - Columns: {', '.join(columns)}")
            
            # Insert into Fly.io
            for user in users:
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT (username) DO NOTHING"
                fly_cur.execute(insert_sql, user)
            
            print(f"  ✅ Inserted {len(users)} users")
            
            # Verify superadmin exists
            fly_cur.execute("SELECT username, email FROM users WHERE username = 'superadmin'")
            superadmin = fly_cur.fetchone()
            if superadmin:
                print(f"  ✅ Superadmin user confirmed: {superadmin}")
            else:
                print("  ❌ Superadmin user not found after migration")
        else:
            print("  ⚠️  No users found locally")
        
        # 3. Copy operator_branding if it exists
        print("\n🎨 Copying operator branding...")
        try:
            local_cur.execute("SELECT * FROM operator_branding")
            branding = local_cur.fetchall()
            
            if branding:
                # Get column names
                local_cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'operator_branding' ORDER BY ordinal_position")
                columns = [col[0] for col in local_cur.fetchall()]
                print(f"  - Found {len(branding)} branding records")
                
                # Insert into Fly.io
                for brand in branding:
                    placeholders = ', '.join(['%s'] * len(columns))
                    insert_sql = f"INSERT INTO operator_branding ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                    fly_cur.execute(insert_sql, brand)
                
                print(f"  ✅ Inserted {len(branding)} branding records")
            else:
                print("  ⚠️  No branding records found locally")
        except Exception as e:
            print(f"  ℹ️  Operator branding table not found or empty: {e}")
        
        # 4. Ensure Megabook tenant exists
        print("\n🏷️  Ensuring Megabook tenant exists...")
        try:
            fly_cur.execute("""
                INSERT INTO sportsbook_operators (name, subdomain, is_active) 
                VALUES ('Megabook', 'megabook', TRUE) 
                ON CONFLICT (subdomain) DO UPDATE 
                SET name = EXCLUDED.name, is_active = TRUE
            """)
            print("  ✅ Megabook tenant ensured")
        except Exception as e:
            print(f"  ⚠️  Could not ensure Megabook tenant: {e}")
        
        # Commit all changes
        fly_conn.commit()
        print("\n✅ Essential data migration completed successfully!")
        
        # Final verification
        print("\n🔍 Final verification:")
        fly_cur.execute("SELECT COUNT(*) FROM sportsbook_operators")
        op_count = fly_cur.fetchone()[0]
        print(f"  - Sportsbook operators: {op_count}")
        
        fly_cur.execute("SELECT COUNT(*) FROM users")
        user_count = fly_cur.fetchone()[0]
        print(f"  - Users: {user_count}")
        
        fly_cur.execute("SELECT username FROM users WHERE username = 'superadmin'")
        superadmin = fly_cur.fetchone()
        if superadmin:
            print(f"  - Superadmin: ✅ Found ({superadmin[0]})")
        else:
            print("  - Superadmin: ❌ Not found")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        fly_conn.rollback()
        raise
    finally:
        local_cur.close()
        fly_cur.close()
        local_conn.close()
        fly_conn.close()

if __name__ == "__main__":
    copy_essential_data()
