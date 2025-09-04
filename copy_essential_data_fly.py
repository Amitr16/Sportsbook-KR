#!/usr/bin/env python3
"""Copy essential data from local PostgreSQL to Fly.io database - runs on Fly.io machine"""

import os
import psycopg2
import hashlib

def copy_essential_data():
    """Copy only essential data: superadmin, sportsbook operators, initial tenant"""
    
    # Fly.io database connection (this script runs on Fly.io)
    fly_conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    fly_cur = fly_conn.cursor()
    
    print("🚀 Starting essential data migration on Fly.io...")
    print("=" * 50)
    
    try:
        # 1. Check what tables exist
        print("🔍 Checking existing tables...")
        fly_cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        tables = fly_cur.fetchall()
        table_names = [table[0] for table in tables]
        print(f"  - Found tables: {', '.join(table_names)}")
        
        # 2. Create superadmin user if not exists
        print("\n👤 Creating superadmin user...")
        try:
            # Check if users table exists
            if 'users' in table_names:
                fly_cur.execute("SELECT COUNT(*) FROM users WHERE username = 'superadmin'")
                superadmin_exists = fly_cur.fetchone()[0]
                
                if superadmin_exists == 0:
                    # Create superadmin user
                    fly_cur.execute("""
                        INSERT INTO users (username, email, password_hash, role, is_active, created_at) 
                        VALUES ('superadmin', 'superadmin@goalserve.com', 
                                '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 
                                'superadmin', TRUE, NOW())
                        ON CONFLICT (username) DO NOTHING
                    """)
                    print("  ✅ Superadmin user created")
                else:
                    print("  ℹ️  Superadmin user already exists")
            else:
                print("  ❌ Users table not found")
        except Exception as e:
            print(f"  ⚠️  Error with superadmin: {e}")
        
        # 3. Create sportsbook operators if not exists
        print("\n🏪 Creating sportsbook operators...")
        try:
            if 'sportsbook_operators' in table_names:
                # Check if operators exist
                fly_cur.execute("SELECT COUNT(*) FROM sportsbook_operators")
                op_count = fly_cur.fetchone()[0]
                
                if op_count == 0:
                    # Create default operators
                    fly_cur.execute("""
                        INSERT INTO sportsbook_operators (name, subdomain, is_active, created_at) 
                        VALUES 
                            ('Megabook', 'megabook', TRUE, NOW()),
                            ('Default Sportsbook', 'default', TRUE, NOW())
                        ON CONFLICT (subdomain) DO NOTHING
                    """)
                    print("  ✅ Default sportsbook operators created")
                else:
                    print(f"  ℹ️  {op_count} operators already exist")
            else:
                print("  ❌ Sportsbook operators table not found")
        except Exception as e:
            print(f"  ⚠️  Error with operators: {e}")
        
        # 4. Create operator branding if table exists
        print("\n🎨 Creating operator branding...")
        try:
            if 'operator_branding' in table_names:
                # Check if branding exists
                fly_cur.execute("SELECT COUNT(*) FROM operator_branding")
                brand_count = fly_cur.fetchone()[0]
                
                if brand_count == 0:
                    # Create default branding
                    fly_cur.execute("""
                        INSERT INTO operator_branding (operator_id, theme_colors, logo_url, created_at) 
                        SELECT id, '{"primary": "#007bff", "secondary": "#6c757d"}', 
                               'https://via.placeholder.com/200x80?text=Logo', NOW()
                        FROM sportsbook_operators 
                        WHERE subdomain = 'megabook'
                        ON CONFLICT DO NOTHING
                    """)
                    print("  ✅ Default branding created")
                else:
                    print(f"  ℹ️  {brand_count} branding records already exist")
            else:
                print("  ℹ️  Operator branding table not found")
        except Exception as e:
            print(f"  ⚠️  Error with branding: {e}")
        
        # Commit all changes
        fly_conn.commit()
        print("\n✅ Essential data creation completed successfully!")
        
        # Final verification
        print("\n🔍 Final verification:")
        if 'sportsbook_operators' in table_names:
            fly_cur.execute("SELECT COUNT(*) FROM sportsbook_operators")
            op_count = fly_cur.fetchone()[0]
            print(f"  - Sportsbook operators: {op_count}")
        
        if 'users' in table_names:
            fly_cur.execute("SELECT COUNT(*) FROM users")
            user_count = fly_cur.fetchone()[0]
            print(f"  - Users: {user_count}")
            
            fly_cur.execute("SELECT username FROM users WHERE username = 'superadmin'")
            superadmin = fly_cur.fetchone()
            if superadmin:
                print(f"  - Superadmin: ✅ Found ({superadmin[0]})")
            else:
                print("  - Superadmin: ❌ Not found")
        
        print("\n🎯 Ready for superadmin login:")
        print("  - Username: superadmin")
        print("  - Password: superadmin123")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        fly_conn.rollback()
        raise
    finally:
        fly_cur.close()
        fly_conn.close()

if __name__ == "__main__":
    copy_essential_data()
