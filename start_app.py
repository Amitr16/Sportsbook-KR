#!/usr/bin/env python3
"""
GoalServe Sports Betting Platform - Integrated Startup

This script starts your main Flask app with ALL services integrated:
- Flask web application
- WebSocket service  
- Bet settlement service
- Pre-match odds service
- Live odds cache service
- All services automatically start and integrate

You only need to run ONE command now!
"""

import os
import sys
from pathlib import Path

def main():
    print("🚀 Starting GoalServe Sports Betting Platform...")
    print("📋 Services that will start automatically:")
    print("   ✅ Flask Web Application")
    print("   ✅ WebSocket Service")
    print("   ✅ Bet Settlement Service") 
    print("   ✅ Pre-match Odds Service")
    print("   ✅ Live Odds Cache Service")
    print("   ✅ Live Odds System Integration")
    print()
    print("🎯 All services are now integrated into your main app!")
    print("💡 You only need to run: python run.py")
    print()
    
    # Check if we're in the right directory
    if not Path("run.py").exists():
        print("❌ Error: run.py not found in current directory")
        print("   Please run this from your project root directory")
        return False
    
    # Start the main app
    try:
        print("🚀 Starting main application...")
        os.system("python run.py")
        return True
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
        return True
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("✅ Application startup complete")
    else:
        print("❌ Application startup failed")
        sys.exit(1)
