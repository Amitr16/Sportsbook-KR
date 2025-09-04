#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load env for local overrides (safe in dev; production ignores env.local via env_loader)
load_dotenv("env.local", override=False)

from src.main import app, socketio

if __name__ == "__main__":
    # On Fly, the proxy expects the app to listen on PORT (default 8080)
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting Flask app on port {port}...")
    # Disable auto-reload to prevent Windows threading issues
    socketio.run(
        app, 
        host="0.0.0.0", 
        port=port, 
        allow_unsafe_werkzeug=True,
        debug=False,  # Disable debug mode to prevent auto-reload
        use_reloader=False  # Explicitly disable reloader
    )
