# Database Configuration Module
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
