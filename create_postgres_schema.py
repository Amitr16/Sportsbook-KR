#!/usr/bin/env python3
"""
Script to create PostgreSQL schema on Fly.io
"""
import os
import sys
sys.path.insert(0, '/app/src')
from db_compat import get_connection

def create_schema():
    print('🔍 Reading PostgreSQL schema...')
    try:
        with open('/app/complete_database_schema.sql', 'r') as f:
            schema_sql = f.read()
        print(f'✅ Schema file read: {len(schema_sql)} characters')
    except Exception as e:
        print(f'❌ Error reading schema file: {e}')
        return False

    print('🚀 Creating PostgreSQL tables...')
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Split SQL by semicolons and execute each statement
                statements = schema_sql.split(';')
                executed = 0
                skipped = 0
                
                for i, statement in enumerate(statements):
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        try:
                            cur.execute(statement)
                            executed += 1
                            print(f'✅ Statement {i+1} executed')
                        except Exception as e:
                            skipped += 1
                            print(f'⚠️  Statement {i+1} skipped: {e}')
                
                conn.commit()
                print(f'🎉 PostgreSQL schema creation completed!')
                print(f'   Executed: {executed} statements')
                print(f'   Skipped: {skipped} statements')
                return True
                
    except Exception as e:
        print(f'❌ Error creating schema: {e}')
        return False

if __name__ == "__main__":
    success = create_schema()
    sys.exit(0 if success else 1)
