#!/usr/bin/env python3
"""
Fix Database Configuration - Add SQLite Support
"""

import os
import shutil

def backup_and_fix_database_config():
    """Backup and fix database configuration files"""
    
    print("🔧 Fixing database configuration for SQLite support...")
    
    # 1. Backup original files
    files_to_backup = [
        'src/database_config.py',
        'src/db_compat.py',
        'src/main.py'
    ]
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            print(f"📋 Backed up {file_path} to {backup_path}")
    
    # 2. Create SQLite-compatible database_config.py
    database_config_content = '''# Database Configuration Module
# Support both SQLite and PostgreSQL

import os
import sqlite3
from contextlib import contextmanager

def get_database_url():
    """Get database URL - support both SQLite and PostgreSQL"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        # Default to SQLite for local development
        database_url = "sqlite:///local_app.db"
        print("⚠️ DATABASE_URL not set, defaulting to SQLite")
    
    return database_url

def is_postgresql():
    """Check if using PostgreSQL"""
    database_url = get_database_url()
    return database_url.startswith(('postgresql://', 'postgres://'))

def is_sqlite():
    """Check if using SQLite"""
    database_url = get_database_url()
    return database_url.startswith('sqlite:///')

@contextmanager
def get_raw_database_connection():
    """Get a raw database connection - SQLite or PostgreSQL"""
    database_url = get_database_url()
    
    if is_sqlite():
        # SQLite connection
        db_path = database_url.replace('sqlite:///', '')
        print(f"🔌 Connecting to SQLite: {db_path}")
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
            
    elif is_postgresql():
        # PostgreSQL connection (original logic)
        print(f"🔌 Connecting to PostgreSQL")
        
        # Import PostgreSQL dependencies only when needed
        import psycopg2
        from src.db_compat import connect as db_compat_connect
        
        try:
            conn = db_compat_connect(database_url, autocommit=False, use_pool=True)
            try:
                yield conn
            finally:
                if hasattr(conn, '_pool') and conn._pool:
                    conn._pool.putconn(conn)
                else:
                    conn.close()
        except Exception as e:
            print(f"⚠️ db_compat failed: {e}, trying direct connection")
            conn = psycopg2.connect(database_url)
            try:
                yield conn
            finally:
                conn.close()
    else:
        raise Exception(f"Unsupported database URL: {database_url}")

def get_database_connection():
    """Legacy function - use get_raw_database_connection() context manager instead"""
    print("⚠️ get_database_connection() is deprecated, use get_raw_database_connection() context manager")
    return get_raw_database_connection()
'''
    
    with open('src/database_config.py', 'w') as f:
        f.write(database_config_content)
    print("✅ Updated src/database_config.py with SQLite support")
    
    # 3. Create a simple SQLite-first db_compat.py
    db_compat_content = '''# db_compat.py - SQLite First, PostgreSQL Fallback

import os
import sqlite3
from contextlib import contextmanager

print("db_compat loaded from:", __file__)

class CompatConnection:
    """SQLite connection wrapper for compatibility"""
    def __init__(self, conn):
        self._conn = conn
        self._pool = None
    
    def execute(self, sql, params=None):
        """Execute SQL with parameter adaptation"""
        if params is None:
            params = []
        
        # Simple SQLite parameter adaptation
        if isinstance(params, dict):
            # Convert named parameters
            cursor = self._conn.execute(sql, params)
        else:
            # Convert positional parameters
            cursor = self._conn.execute(sql, params)
        return cursor
    
    def executemany(self, sql, params_list):
        """Execute SQL multiple times"""
        return self._conn.executemany(sql, params_list)
    
    def fetchall(self):
        """Fetch all results"""
        return self._conn.fetchall()
    
    def fetchone(self):
        """Fetch one result"""
        return self._conn.fetchone()
    
    def commit(self):
        """Commit transaction"""
        return self._conn.commit()
    
    def rollback(self):
        """Rollback transaction"""
        return self._conn.rollback()
    
    def close(self):
        """Close connection"""
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

def connect(dsn=None, *, autocommit=False, use_pool=True):
    """Connect to database - SQLite first, PostgreSQL fallback"""
    if not dsn:
        dsn = os.getenv('DATABASE_URL', 'sqlite:///local_app.db')
    
    print(f"🔌 db_compat connecting to: {dsn[:20]}...")
    
    if dsn.startswith('sqlite:///'):
        # SQLite connection
        db_path = dsn.replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        if autocommit:
            conn.isolation_level = None
        return CompatConnection(conn)
    
    elif dsn.startswith(('postgresql://', 'postgres://')):
        # PostgreSQL connection - import only when needed
        try:
            import psycopg
            from psycopg.rows import dict_row
            
            # Normalize DSN
            if dsn.startswith('postgres://'):
                dsn = dsn.replace('postgres://', 'postgresql://', 1)
            
            conn = psycopg.connect(dsn, autocommit=autocommit, row_factory=dict_row)
            return CompatConnection(conn)
        except ImportError:
            print("⚠️ psycopg not available, falling back to psycopg2")
            import psycopg2
            import psycopg2.extras
            
            conn = psycopg2.connect(dsn)
            if autocommit:
                conn.autocommit = True
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return CompatConnection(conn)
    
    else:
        raise Exception(f"Unsupported database URL: {dsn}")

# Legacy functions for compatibility
def get_global_pool(dsn=None, **kwargs):
    """Legacy function - returns None for SQLite"""
    return None

def safe_close_global_pool():
    """Legacy function - no-op for SQLite"""
    pass
'''
    
    with open('src/db_compat.py', 'w') as f:
        f.write(db_compat_content)
    print("✅ Updated src/db_compat.py with SQLite-first approach")
    
    print("🎉 Database configuration fixed!")
    print("📋 Original files backed up with .backup extension")
    print("🚀 Now try: python3 simple_start.py")

if __name__ == "__main__":
    backup_and_fix_database_config()
