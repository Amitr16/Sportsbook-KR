#!/usr/bin/env python3
"""
GoalServe Sports Betting Platform - Future-Proof Edition
Application Entry Point

Features:
- Automatic sport discovery
- Dynamic odds parsing
- Future-proof data handling
- Real GoalServe integration
- Pre-match odds service
"""

import os
import sys
import threading
import signal
from dotenv import load_dotenv

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables from .env file (optional)
load_dotenv()

# Import the Flask application
from main import app
from prematch_odds_service import get_prematch_odds_service

# Global variable to store the pre-match odds service
prematch_odds_service = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n🛑 Shutting down services...")
    if prematch_odds_service:
        prematch_odds_service.stop()
    print("✅ Services stopped gracefully")
    sys.exit(0)

def start_prematch_odds_service():
    """Start the pre-match odds service in a separate thread"""
    global prematch_odds_service
    try:
        prematch_odds_service = get_prematch_odds_service()
        prematch_odds_service.start()
        print("✅ Pre-match odds service started successfully")
    except Exception as e:
        print(f"❌ Failed to start pre-match odds service: {e}")

if __name__ == '__main__':
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration from environment variables
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"""
🚀 GoalServe Sports Betting Platform - Future-Proof Edition

📍 Server: http://{host}:{port}
🔧 Debug Mode: {debug}
🎯 Environment: {os.getenv('FLASK_ENV', 'development')}

🔮 Future-Proof Features:
✅ Automatic Sport Discovery
✅ Dynamic Odds Parsing  
✅ Real GoalServe Integration
✅ Auto Bet Settlement
✅ Complete Bet History
✅ Modern UI/UX Design
✅ Mobile Responsive
✅ Pre-Match Odds Service

🌟 No API Key Required - Ready to Use!
    """)
    
    # Start the pre-match odds service in a separate thread
    print("🔄 Starting pre-match odds service...")
    prematch_thread = threading.Thread(target=start_prematch_odds_service, daemon=True)
    prematch_thread.start()
    
    # Start the Flask development server
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )

