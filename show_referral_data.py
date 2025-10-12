#!/usr/bin/env python3
"""
Simple script to show referral_table data
"""

import os
from src import sqlite3_shim

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://postgres:admin@localhost:5432/goalserve_sportsbook'

def show_referral_data():
    """Show all data from referral_table"""
    try:
        conn = sqlite3_shim.connect()
        cursor = conn.cursor()
        
        print("📊 Referral Table Data (SELECT * FROM referral_table):")
        print("=" * 80)
        
        # Get all data
        cursor.execute("SELECT * FROM referral_table ORDER BY id")
        rows = cursor.fetchall()
        
        if rows:
            # Get column names
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'referral_table'
                ORDER BY ordinal_position
            """)
            columns = [col[0] for col in cursor.fetchall()]
            
            # Print header
            header = " | ".join(f"{col:<15}" for col in columns)
            print(header)
            print("-" * len(header))
            
            # Print data
            for row in rows:
                # Format each row
                formatted_row = []
                for i, value in enumerate(row):
                    if value is None:
                        formatted_row.append("NULL")
                    elif hasattr(value, 'strftime'):  # datetime object
                        formatted_row.append(value.strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        formatted_row.append(str(value))
                
                row_str = " | ".join(f"{val:<15}" for val in formatted_row)
                print(row_str)
        else:
            print("❌ No data found in referral_table")
        
        conn.close()
        print(f"\n✅ Found {len(rows)} rows in referral_table")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_referral_data()
