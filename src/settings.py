#!/usr/bin/env python3
"""
Settings module for local vs Fly.io deployment
Uses Pydantic for environment variable management
"""

from pydantic import BaseSettings, Field
from typing import List
import os

class Settings(BaseSettings):
    """Application settings with environment switching"""
    
    # Environment detection
    ENV: str = Field(default="development", env="FLASK_ENV")
    IS_PRODUCTION: bool = Field(default=False, env="IS_PRODUCTION")
    IS_LOCAL: bool = Field(default=True, env="IS_LOCAL")
    
    # Server configuration
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")  # Use Fly's $PORT in prod, 8000 locally
    
    # Database configuration
    DATABASE_URL: str = Field(
        default="",  # No default - must be provided via environment
        env="DATABASE_URL"
    )
    DATABASE_TYPE: str = Field(default="postgresql", env="DATABASE_TYPE")
    
    # Redis configuration
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # CORS configuration
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://goalserve-sportsbook-backend.fly.dev",
            "https://goalserve-sportsbook.fly.dev"
        ],
        env="CORS_ORIGINS"
    )
    
    # Socket.IO configuration
    SOCKET_ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://goalserve-sportsbook-backend.fly.dev",
            "https://goalserve-sportsbook.fly.dev"
        ],
        env="SOCKET_ALLOWED_ORIGINS"
    )
    SOCKETIO_PATH: str = Field(default="/socket.io/", env="SOCKETIO_PATH")
    
    # Goalserve API configuration
    GOALSERVE_API_KEY: str = Field(default="demo-key", env="GOALSERVE_API_KEY")
    GOALSERVE_BASE_URL: str = Field(
        default="https://www.goalserve.com/getfeed",
        env="GOALSERVE_BASE_URL"
    )
    
    # Mock feed configuration (for local development)
    USE_MOCK_FEED: bool = Field(default=False, env="USE_MOCK_FEED")
    MOCK_FEED_DIR: str = Field(default="mock_feeds", env="MOCK_FEED_DIR")
    
    # Bet settlement configuration
    SETTLEMENT_CHECK_INTERVAL: int = Field(default=30, env="SETTLEMENT_CHECK_INTERVAL")
    
    # Flask secret key
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        env="SECRET_KEY"
    )
    
    # Debug mode
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENV == "production" or self.IS_PRODUCTION
    
    @property
    def is_local(self) -> bool:
        """Check if running locally"""
        return not self.is_production
    
    def get_database_config(self):
        """Get database configuration based on environment"""
        if self.is_local:
            return {
                'url': self.DATABASE_URL,
                'type': 'postgresql',
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            }
        else:
            return {
                'url': self.DATABASE_URL,
                'type': 'postgresql',
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            }
    
    def print_config(self):
        """Print current configuration for debugging"""
        print(f"=== Configuration ===")
        print(f"Environment: {self.ENV}")
        print(f"Is Local: {self.is_local}")
        print(f"Host: {self.HOST}")
        print(f"Port: {self.PORT}")
        print(f"Database Type: {self.DATABASE_TYPE}")
        print(f"Database URL: {self.DATABASE_URL[:50]}..." if len(self.DATABASE_URL) > 50 else f"Database URL: {self.DATABASE_URL}")
        print(f"Redis URL: {self.REDIS_URL}")
        print(f"Debug Mode: {self.DEBUG}")
        print(f"CORS Origins: {self.CORS_ORIGINS}")
        print(f"Socket Origins: {self.SOCKET_ALLOWED_ORIGINS}")
        print(f"Use Mock Feed: {self.USE_MOCK_FEED}")
        print(f"===================")

# Create settings instance
settings = Settings()
