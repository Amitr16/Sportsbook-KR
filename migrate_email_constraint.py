#!/usr/bin/env python3
"""
Migration script to change email uniqueness constraint from global to per-tenant.
This allows the same email to have separate accounts for different tenants.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('env.local')

def migrate_email_constraint():
    """Update email constraint to be unique per tenant instead of globally unique"""
    
    # Parse DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:admin@localhost:5432/goalserve_sportsbook')
    
    # Parse the URL to extract connection parameters
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    
    db_params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'dbname': parsed.path.lstrip('/') or 'goalserve_sportsbook',
        'user': parsed.username or 'postgres',
        'password': parsed.password or 'admin'
    }
    
    try:
        import psycopg
        print("🔌 Connecting to database...")
        
        with psycopg.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                print("📋 Starting email constraint migration...")
                
                # Step 1: Find and drop the existing unique constraint on email
                print("1️⃣ Finding and dropping existing unique constraint on email...")
                try:
                    # First, find the constraint name
                    cursor.execute("""
                        SELECT constraint_name 
                        FROM information_schema.table_constraints 
                        WHERE table_name = 'users' 
                        AND constraint_type = 'UNIQUE' 
                        AND constraint_name LIKE '%email%';
                    """)
                    constraints = cursor.fetchall()
                    
                    if constraints:
                        for constraint in constraints:
                            constraint_name = constraint[0]
                            print(f"   Found constraint: {constraint_name}")
                            cursor.execute(f"ALTER TABLE users DROP CONSTRAINT {constraint_name};")
                            print(f"✅ Dropped constraint: {constraint_name}")
                    else:
                        print("⚠️ No email unique constraint found")
                except Exception as e:
                    print(f"⚠️ Could not drop email constraint: {e}")
                    # Continue anyway, the constraint might not exist
                
                # Step 2: Add new composite unique constraint on (email, sportsbook_operator_id)
                print("2️⃣ Adding composite unique constraint on (email, sportsbook_operator_id)...")
                try:
                    cursor.execute("""
                        ALTER TABLE users 
                        ADD CONSTRAINT users_email_operator_unique 
                        UNIQUE (email, sportsbook_operator_id);
                    """)
                    print("✅ Added composite unique constraint")
                except Exception as e:
                    print(f"❌ Failed to add composite constraint: {e}")
                    raise
                
                # Step 3: Update any existing users with NULL sportsbook_operator_id to have a default
                print("3️⃣ Updating users with NULL sportsbook_operator_id...")
                try:
                    # Get the first operator ID as default
                    cursor.execute("SELECT id FROM sportsbook_operators ORDER BY id LIMIT 1;")
                    default_operator = cursor.fetchone()
                    
                    if default_operator:
                        default_operator_id = default_operator[0]
                        cursor.execute("""
                            UPDATE users 
                            SET sportsbook_operator_id = %s 
                            WHERE sportsbook_operator_id IS NULL;
                        """, (default_operator_id,))
                        print(f"✅ Updated users with NULL operator_id to use operator {default_operator_id}")
                    else:
                        print("⚠️ No operators found, skipping NULL operator_id update")
                except Exception as e:
                    print(f"⚠️ Could not update NULL operator_ids: {e}")
                
                # Step 4: Verify the migration
                print("4️⃣ Verifying migration...")
                cursor.execute("""
                    SELECT constraint_name, constraint_type 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'users' AND constraint_type = 'UNIQUE';
                """)
                constraints = cursor.fetchall()
                print("📋 Current unique constraints on users table:")
                for constraint in constraints:
                    print(f"   - {constraint[0]}: {constraint[1]}")
                
                # Check for any duplicate emails within the same operator
                cursor.execute("""
                    SELECT email, sportsbook_operator_id, COUNT(*) 
                    FROM users 
                    GROUP BY email, sportsbook_operator_id 
                    HAVING COUNT(*) > 1;
                """)
                duplicates = cursor.fetchall()
                if duplicates:
                    print("❌ Found duplicate emails within same operator:")
                    for dup in duplicates:
                        print(f"   - Email: {dup[0]}, Operator: {dup[1]}, Count: {dup[2]}")
                else:
                    print("✅ No duplicate emails found within same operators")
                
                print("🎉 Email constraint migration completed successfully!")
                print("📝 Users can now have separate accounts for different tenants with the same email")
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_email_constraint()
