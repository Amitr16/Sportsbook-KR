#!/usr/bin/env python3
"""
Configuration file for local vs Fly.io deployment
"""

import os
from pathlib import Path

class Config:
    """Application configuration with environment switching"""
    
    # Environment detection
    ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = ENV == 'production'
    IS_LOCAL = not IS_PRODUCTION
    
    # Database configuration
    if IS_LOCAL:
        # Local development - use SQLite for simplicity
        DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///local_app.db')
        DATABASE_TYPE = 'sqlite'
    else:
        # Production (Fly.io) - use PostgreSQL
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is required for production")
        DATABASE_TYPE = 'postgresql'
    
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = IS_LOCAL
    
    # CORS configuration
    CORS_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "https://goalserve-sportsbook-backend.fly.dev",
        "https://goalserve-sportsbook.fly.dev"
    ]
    
    # Socket.IO configuration
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25
    
    # Goalserve API configuration
    GOALSERVE_API_KEY = os.getenv('GOALSERVE_API_KEY', 'demo-key')
    GOALSERVE_BASE_URL = os.getenv('GOALSERVE_BASE_URL', 'https://www.goalserve.com/getfeed')
    
    # Bet settlement configuration
    SETTLEMENT_CHECK_INTERVAL = 30  # seconds
    
    @classmethod
    def get_database_config(cls):
        """Get database configuration based on environment"""
        if cls.DATABASE_TYPE == 'sqlite':
            return {
                'url': cls.DATABASE_URL,
                'type': 'sqlite',
                'pool_size': 1,
                'max_overflow': 0,
                'pool_timeout': 30,
                'pool_recycle': 3600
            }
        else:
            return {
                'url': cls.DATABASE_URL,
                'type': 'postgresql',
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            }
    
    @classmethod
    def print_config(cls):
        """Print current configuration for debugging"""
        print(f"=== Configuration ===")
        print(f"Environment: {cls.ENV}")
        print(f"Is Local: {cls.IS_LOCAL}")
        print(f"Database Type: {cls.DATABASE_TYPE}")
        print(f"Database URL: {cls.DATABASE_URL[:50]}..." if len(str(cls.DATABASE_URL)) > 50 else f"Database URL: {cls.DATABASE_URL}")
        print(f"Debug Mode: {cls.DEBUG}")
        print(f"CORS Origins: {cls.CORS_ORIGINS}")
        print(f"===================")

# Create config instance
config = Config()
