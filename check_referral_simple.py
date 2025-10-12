#!/usr/bin/env python3
"""
Simple script to check referral_table content
"""

import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://postgres:admin@localhost:5432/goalserve_sportsbook'

# Now import the database module
from src import sqlite3_shim

def check_referral_table():
    """Check referral_table content and structure"""
    try:
        conn = sqlite3_shim.connect()
        cursor = conn.cursor()
        
        print("🔍 Checking referral_table structure and content...")
        print("=" * 60)
        
        # Check table structure
        print("\n📋 Table Structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'referral_table'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        if columns:
            print(f"{'Column Name':<20} {'Data Type':<15} {'Nullable':<10} {'Default'}")
            print("-" * 60)
            for col in columns:
                print(f"{col[0]:<20} {col[1]:<15} {col[2]:<10} {col[3] or 'None'}")
        else:
            print("❌ Table structure not found")
            return False
        
        # Check table content
        print(f"\n📊 Table Content:")
        cursor.execute("""
            SELECT id, operator_name, operator_id, referral_used, referral_generated, created_at
            FROM referral_table 
            ORDER BY id
        """)
        rows = cursor.fetchall()
        
        if rows:
            print(f"{'ID':<5} {'Operator Name':<20} {'Op ID':<8} {'Referral Used':<15} {'Referral Generated':<18} {'Created At'}")
            print("-" * 100)
            for row in rows:
                # Handle datetime object properly
                if row[5]:
                    if hasattr(row[5], 'strftime'):
                        created_at = row[5].strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        created_at = str(row[5])[:19]
                else:
                    created_at = 'N/A'
                print(f"{row[0]:<5} {row[1]:<20} {row[2]:<8} {row[3] or 'N/A':<15} {row[4]:<18} {created_at}")
        else:
            print("❌ No data found in referral_table")
        
        # Check for superadmin entry
        print(f"\n🔍 Superadmin Entry Check:")
        cursor.execute("""
            SELECT operator_name, operator_id, referral_generated 
            FROM referral_table 
            WHERE operator_id = 0
        """)
        superadmin = cursor.fetchone()
        
        if superadmin:
            print(f"✅ Superadmin entry found:")
            print(f"   Operator Name: {superadmin[0]}")
            print(f"   Operator ID: {superadmin[1]}")
            print(f"   Referral Code: {superadmin[2]}")
        else:
            print("❌ Superadmin entry not found")
        
        # Check for duplicate referral codes
        print(f"\n🔍 Duplicate Referral Codes Check:")
        cursor.execute("""
            SELECT referral_generated, COUNT(*) as count
            FROM referral_table 
            GROUP BY referral_generated 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print("❌ Duplicate referral codes found:")
            for dup in duplicates:
                print(f"   Code: {dup[0]} (appears {dup[1]} times)")
        else:
            print("✅ No duplicate referral codes found")
        
        # Check for operators with referral codes
        print(f"\n🔍 Operators with Referral Codes:")
        cursor.execute("""
            SELECT COUNT(*) as total_operators
            FROM referral_table 
            WHERE operator_id > 0
        """)
        operator_count = cursor.fetchone()[0]
        print(f"   Total operators with referral codes: {operator_count}")
        
        # Check referral chain
        print(f"\n🔗 Referral Chain Analysis:")
        cursor.execute("""
            SELECT 
                rt1.operator_name as referrer,
                rt1.referral_generated as referrer_code,
                rt2.operator_name as referred,
                rt2.operator_id as referred_id
            FROM referral_table rt1
            LEFT JOIN referral_table rt2 ON rt1.referral_generated = rt2.referral_used
            WHERE rt1.operator_id > 0
            ORDER BY rt1.id
        """)
        chain = cursor.fetchall()
        
        if chain:
            print(f"{'Referrer':<20} {'Referrer Code':<15} {'Referred':<20} {'Referred ID'}")
            print("-" * 70)
            for link in chain:
                referred = link[2] if link[2] else 'None'
                referred_id = link[3] if link[3] else 'N/A'
                print(f"{link[0]:<20} {link[1]:<15} {referred:<20} {referred_id}")
        else:
            print("   No referral chain data found")
        
        conn.close()
        print("\n✅ Referral table check completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error checking referral table: {e}")
        return False

if __name__ == "__main__":
    check_referral_table()
