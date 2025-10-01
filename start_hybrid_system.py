#!/usr/bin/env python3
"""
Start Hybrid System - Complete setup and launch
"""

import os
import sys
import subprocess

def start_hybrid_system():
    """Complete setup and start of the hybrid system"""
    
    print("🚀 STARTING HYBRID SPORTSBOOK SYSTEM")
    print("=" * 50)
    
    # Step 1: Set environment
    print("\n1️⃣ Setting up environment...")
    os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    print("✅ Environment configured")
    
    # Step 2: Setup database
    print("\n2️⃣ Setting up complete database...")
    try:
        from setup_complete_database import setup_complete_database
        setup_complete_database()
        print("✅ Database setup completed")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    
    # Step 3: Start Flask app
    print("\n3️⃣ Starting Flask application...")
    print("🌐 Application will be available at: http://localhost:5000")
    print("📋 Test endpoints:")
    print("   • Register operator: POST /register-sportsbook")
    print("   • Register user: POST /api/auth/demo-sportsbook/register")
    print("   • Login user: POST /api/auth/demo-sportsbook/login")
    print("   • Place bet: POST /api/demo-sportsbook/place_bet")
    
    print("\n🎯 READY TO TEST HYBRID SYSTEM!")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Import and run the app
        sys.path.insert(0, 'src')
        from src.main import app
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Disable reloader to avoid issues
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    start_hybrid_system()
