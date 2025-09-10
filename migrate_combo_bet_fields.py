#!/usr/bin/env python3
"""
Migration script to fix combo bet field length constraints
"""

import os
import sys
from dotenv import load_dotenv
import psycopg

# Load environment variables
load_dotenv()

def migrate_combo_bet_fields():
    """Update bet table field lengths to support combo bets"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found")
        return False
    
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                print("🔧 Updating bet table field lengths...")
                
                # Update sport_name field length from 50 to 200
                cur.execute("""
                    ALTER TABLE bets 
                    ALTER COLUMN sport_name TYPE VARCHAR(200)
                """)
                print("✅ Updated sport_name field length to 200")
                
                # Update bet_timing field length from 20 to 100
                cur.execute("""
                    ALTER TABLE bets 
                    ALTER COLUMN bet_timing TYPE VARCHAR(100)
                """)
                print("✅ Updated bet_timing field length to 100")
                
                # Commit changes
                conn.commit()
                print("✅ Migration completed successfully!")
                return True
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_combo_bet_fields()
    sys.exit(0 if success else 1)
