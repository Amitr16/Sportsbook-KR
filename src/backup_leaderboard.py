"""
Leaderboard backup utility for saving snapshots before reset operations
"""
from datetime import datetime
import uuid

def get_db_connection():
    """Get database connection - uses PostgreSQL via sqlite3_shim"""
    from src import sqlite3_shim as sqlite3
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    return conn

def create_backup_tables():
    """Create backup tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create User_leader_backup table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS User_leader_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT,
            staked REAL DEFAULT 0,
            payout REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reset_operation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create Partner_leader_backup table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Partner_leader_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sportsbook_name TEXT NOT NULL,
            subdomain TEXT,
            is_active BOOLEAN DEFAULT 1,
            user_count INTEGER DEFAULT 0,
            total_volume REAL DEFAULT 0,
            backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reset_operation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_backup_date ON User_leader_backup(backup_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_backup_username ON User_leader_backup(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_backup_date ON Partner_leader_backup(backup_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_backup_name ON Partner_leader_backup(sportsbook_name)")
    
    conn.commit()
    conn.close()

def backup_user_leaderboard(reset_operation_id=None):
    """Backup current user leaderboard data"""
    if not reset_operation_id:
        reset_operation_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current user leaderboard data (only settled bets)
    cursor.execute("""
        SELECT 
            u.username,
            u.email,
            COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as staked,
            COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) as payout,
            COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) - 
            COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as profit
        FROM users u
        LEFT JOIN bets b ON u.id = b.user_id
        GROUP BY u.id, u.username, u.email
        ORDER BY profit DESC
    """)
    
    users = cursor.fetchall()
    
    # Insert into backup table
    backup_time = datetime.now()
    for user in users:
        cursor.execute("""
            INSERT INTO User_leader_backup (username, email, staked, payout, profit, backup_date, reset_operation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user[0], user[1], user[2], user[3], user[4], backup_time, reset_operation_id))
    
    conn.commit()
    conn.close()
    
    return len(users), reset_operation_id

def backup_partner_leaderboard(reset_operation_id=None):
    """Backup current partner leaderboard data"""
    if not reset_operation_id:
        reset_operation_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current partner leaderboard data (only settled bets for volume)
    cursor.execute("""
        SELECT 
            so.sportsbook_name,
            so.subdomain,
            so.is_active,
            COUNT(DISTINCT u.id) as user_count,
            COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost') THEN b.stake ELSE 0 END), 0) as total_volume
        FROM sportsbook_operators so
        LEFT JOIN users u ON so.id = u.sportsbook_operator_id
        LEFT JOIN bets b ON u.id = b.user_id
        GROUP BY so.id, so.sportsbook_name, so.subdomain, so.is_active
        ORDER BY total_volume DESC
    """)
    
    partners = cursor.fetchall()
    
    # Insert into backup table
    backup_time = datetime.now()
    for partner in partners:
        cursor.execute("""
            INSERT INTO Partner_leader_backup (sportsbook_name, subdomain, is_active, user_count, total_volume, backup_date, reset_operation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (partner[0], partner[1], partner[2], partner[3], partner[4], backup_time, reset_operation_id))
    
    conn.commit()
    conn.close()
    
    return len(partners), reset_operation_id

def backup_all_leaderboards():
    """Backup both user and partner leaderboards with same operation ID"""
    reset_operation_id = str(uuid.uuid4())
    
    user_count, _ = backup_user_leaderboard(reset_operation_id)
    partner_count, _ = backup_partner_leaderboard(reset_operation_id)
    
    return {
        'reset_operation_id': reset_operation_id,
        'user_count': user_count,
        'partner_count': partner_count,
        'backup_time': datetime.now().isoformat()
    }

def get_latest_backup_date():
    """Get the date of the most recent backup"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT MAX(backup_date) as latest_date 
        FROM User_leader_backup
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result and result[0] else None
