# db_compat.py - SQLite First, PostgreSQL Fallback

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

def get_connection(dsn=None, **kwargs):
    """Legacy function - alias for connect()"""
    return connect(dsn, **kwargs)
