#!/usr/bin/env python3
"""
Worker module for bet settlement service
Runs in a separate container for local development
"""

import os
import sys
import time
import signal
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.settings import settings
from src.bet_settlement_service import BetSettlementService

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n🛑 Shutting down worker...")
    if bet_settlement_service:
        bet_settlement_service.stop()
    print("✅ Worker stopped gracefully")
    sys.exit(0)

def main():
    """Main worker function"""
    print("👷 Starting GoalServe Sports Betting Platform - Settlement Worker")
    print(f"📍 Environment: {settings.ENV}")
    print(f"📍 Database: {settings.DATABASE_TYPE}")
    print(f"📍 Redis: {settings.REDIS_URL}")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize bet settlement service
    global bet_settlement_service
    try:
        bet_settlement_service = BetSettlementService()
        bet_settlement_service.start()
        print("✅ Bet settlement service started successfully")
        
        # Keep the worker running
        print("🔄 Worker is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"❌ Error starting settlement service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
