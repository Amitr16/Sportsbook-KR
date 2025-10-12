#!/usr/bin/env python3
# CRITICAL: eventlet monkey patching MUST be the very first import
import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv

# Load env for local overrides (safe in dev; production ignores env.local via env_loader)
load_dotenv("env.local", override=False)
load_dotenv("postgresql.env", override=False)  # Load PostgreSQL and Crossmint credentials

# Run database migrations on startup
try:
    print("Running database migrations...")
    from add_trade_count_migration import add_trade_count_column
    add_trade_count_column()
except Exception as e:
    print(f"Migration warning: {e}")
    print("Continuing with application startup...")

from src.main import app, socketio

if __name__ == "__main__":
    # On Fly, the proxy expects the app to listen on PORT (default 8080)
    port = int(os.getenv("PORT", 5000))
    print(f"Starting Flask app on 0.0.0.0:{port}...")
    print(f"Environment PORT: {os.getenv('PORT', 'NOT_SET')}")
    print(f"Final port: {port}")
    
    # Disable auto-reload to prevent Windows threading issues
    socketio.run(
        app, 
        host="0.0.0.0", 
        port=port, 
        allow_unsafe_werkzeug=True,
        debug=False,  # Disable debug mode to prevent auto-reload
        use_reloader=False  # Explicitly disable reloader
    )
