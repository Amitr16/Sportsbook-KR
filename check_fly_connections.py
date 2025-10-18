#!/usr/bin/env python3
"""
Query Fly.io PostgreSQL to see active connections
"""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv("env.local", override=False)
load_dotenv("postgresql.env", override=False)

def check_active_connections():
    """Check active database connections on Fly.io"""
    try:
        import psycopg
        
        # Get DATABASE_URL from environment
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            print("ERROR: DATABASE_URL not set")
            return
        
        print(f"Connecting to: {db_url[:30]}...")
        
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Query 1: Total active connections by state
                print("\n" + "="*80)
                print("ACTIVE CONNECTIONS BY STATE:")
                print("="*80)
                cur.execute("""
                    SELECT 
                        state,
                        COUNT(*) as count
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY state
                    ORDER BY count DESC;
                """)
                for row in cur.fetchall():
                    print(f"  {row[0]:20s} : {row[1]}")
                
                # Query 2: Detailed active connections
                print("\n" + "="*80)
                print("DETAILED ACTIVE CONNECTIONS:")
                print("="*80)
                cur.execute("""
                    SELECT 
                        pid,
                        usename,
                        application_name,
                        client_addr,
                        state,
                        query_start,
                        state_change,
                        wait_event_type,
                        wait_event,
                        LEFT(query, 60) as query_preview
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND pid != pg_backend_pid()  -- Exclude this query
                    ORDER BY state_change DESC
                    LIMIT 20;
                """)
                
                rows = cur.fetchall()
                if rows:
                    for row in rows:
                        print(f"\nPID: {row[0]}")
                        print(f"  User: {row[1]}")
                        print(f"  App: {row[2] or 'N/A'}")
                        print(f"  Client: {row[3] or 'N/A'}")
                        print(f"  State: {row[4]}")
                        print(f"  Query Start: {row[5]}")
                        print(f"  State Change: {row[6]}")
                        print(f"  Wait Event: {row[7] or 'N/A'} / {row[8] or 'N/A'}")
                        print(f"  Query: {row[9] or 'N/A'}")
                else:
                    print("  No other active connections found")
                
                # Query 3: Connection pool statistics
                print("\n" + "="*80)
                print("CONNECTION SUMMARY:")
                print("="*80)
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_connections,
                        COUNT(*) FILTER (WHERE state = 'active') as active,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle,
                        COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                        COUNT(*) FILTER (WHERE wait_event_type IS NOT NULL) as waiting
                    FROM pg_stat_activity
                    WHERE datname = current_database();
                """)
                
                row = cur.fetchone()
                print(f"  Total Connections: {row[0]}")
                print(f"  Active:            {row[1]}")
                print(f"  Idle:              {row[2]}")
                print(f"  Idle in Trans:     {row[3]}")
                print(f"  Waiting:           {row[4]}")
                
                # Query 4: Long-running queries
                print("\n" + "="*80)
                print("LONG-RUNNING QUERIES (>5 seconds):")
                print("="*80)
                cur.execute("""
                    SELECT 
                        pid,
                        NOW() - query_start as duration,
                        state,
                        LEFT(query, 100) as query
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND state != 'idle'
                      AND query_start < NOW() - INTERVAL '5 seconds'
                    ORDER BY duration DESC;
                """)
                
                rows = cur.fetchall()
                if rows:
                    for row in rows:
                        print(f"\nPID: {row[0]}")
                        print(f"  Duration: {row[1]}")
                        print(f"  State: {row[2]}")
                        print(f"  Query: {row[3]}")
                else:
                    print("  No long-running queries")
                
                print("\n" + "="*80)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_active_connections()

