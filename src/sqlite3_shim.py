"""
Production-safe shim: routes legacy 'sqlite' imports to Postgres via db_compat.
Refuses to use a filesystem path in production.
"""

import os
from . import db_compat

def _resolve_dsn():
    url = (os.getenv("DATABASE_URL")
           or os.getenv("POSTGRES_URL")
           or os.getenv("SQLALCHEMY_DATABASE_URI"))
    if url and url.startswith("postgres://"):
        # psycopg/SQLAlchemy prefer postgresql://
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def connect(dsn=None, *args, **kwargs):
    """
    Ignore legacy sqlite file paths and always use the Postgres DSN.
    """
    url = _resolve_dsn()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Refusing to fall back to sqlite file paths in production."
        )
    return db_compat.connect(url, *args, **kwargs)

# Add other common sqlite3 functions that might be imported
def connect_db(database=None, *args, **kwargs):
    """Alternative connect function that some code might use"""
    return connect(database, *args, **kwargs)

def get_db_connection(*args, **kwargs):
    """Another common pattern"""
    return connect(*args, **kwargs)

# Add Row class for compatibility
class Row:
    """Placeholder for sqlite3.Row compatibility"""
    pass

# Monkey patch the connection to handle row_factory
def _patch_connection(conn):
    """Add row_factory property to connection for compatibility"""
    if not hasattr(conn, 'row_factory'):
        conn.row_factory = Row
    return conn

# Update connect function to patch connections
_original_connect = connect
def connect(dsn=None, *args, **kwargs):
    """Connect and patch for compatibility"""
    conn = _original_connect(dsn, *args, **kwargs)
    return _patch_connection(conn)
