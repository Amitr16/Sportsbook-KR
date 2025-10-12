"""
Check active PostgreSQL connections
"""
import psycopg

DATABASE_URL = "postgresql://postgres:admin@127.0.0.1:5432/goalserve_sportsbook"

try:
    conn = psycopg.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                pid,
                usename,
                application_name,
                client_addr,
                state,
                query_start,
                NOW() - query_start as duration,
                query
            FROM pg_stat_activity
            WHERE datname = 'goalserve_sportsbook'
            AND pid != pg_backend_pid()
            ORDER BY query_start DESC
        """)
        
        connections = cur.fetchall()
        
        print(f"\n{'='*80}")
        print(f"ACTIVE CONNECTIONS TO goalserve_sportsbook: {len(connections)}")
        print(f"{'='*80}\n")
        
        for i, conn_info in enumerate(connections, 1):
            print(f"Connection {i}:")
            print(f"  PID: {conn_info[0]}")
            print(f"  User: {conn_info[1]}")
            print(f"  App: {conn_info[2]}")
            print(f"  State: {conn_info[4]}")
            print(f"  Duration: {conn_info[6]}")
            print(f"  Query: {conn_info[7][:100] if conn_info[7] else 'None'}...")
            print()
    
    conn.close()
    print(f"✅ Total active connections: {len(connections)}")
    
except Exception as e:
    print(f"❌ Error checking connections: {e}")

