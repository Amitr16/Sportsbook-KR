#!/usr/bin/env python3
"""
Run the application locally for development
"""

import os
import sys
sys.path.insert(0, 'src')

# Set environment for local development
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

from src.main import app

def run_local():
    """Run the Flask application locally"""
    
    print("🚀 Starting local development server...")
    
    try:
        # Run the app (imported from main.py)
        print(f"✅ App loaded successfully")
        print(f"🌐 Server will start at: http://localhost:5000")
        print(f"📊 Database: SQLite (local_app.db)")
        print(f"🔧 Debug mode: True")
        print("\nPress Ctrl+C to stop the server")
        
        # Start the app
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=True
        )
        
    except Exception as e:
        print(f"❌ Error starting local server: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_local()
