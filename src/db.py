# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# PgBouncer-friendly engine configuration
ENGINE = create_engine(
    DATABASE_URL,
    poolclass=NullPool,      # Critical: no app-level pooling behind PgBouncer
    pool_pre_ping=True,      # Validates connection before use
    future=True,
)

# Session factory
SessionLocal = scoped_session(sessionmaker(
    bind=ENGINE,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
))

def get_db():
    """Get a database session - use only when you need a short-lived session"""
    return SessionLocal()

def close_db(db):
    """Close a database session"""
    if db:
        try:
            db.close()
        except Exception:
            pass
