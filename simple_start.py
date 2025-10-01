#!/usr/bin/env python3
"""
Simple Start - Bypass complex database setup
"""

import os
import sys

# Force SQLite usage
os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

# Disable complex services that are causing issues
os.environ['DISABLE_PREMATCH_ODDS'] = '1'
os.environ['DISABLE_BET_SETTLEMENT'] = '1'
os.environ['DISABLE_LIVE_ODDS'] = '1'

print("🚀 Starting Simple Flask App...")
print("📊 Database: SQLite (local_app.db)")
print("🔧 Complex services disabled for testing")

try:
    # Import and run the app
    sys.path.insert(0, 'src')
    from src.main import app
    
    print("✅ App loaded successfully")
    print("🌐 Server starting at: http://localhost:5000")
    print("📋 Test URL: http://localhost:5000/register-sportsbook")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,  # Disable debug to reduce noise
        use_reloader=False  # Disable reloader to avoid issues
    )
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
