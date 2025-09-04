#!/usr/bin/env python3
"""
Live Odds System Starter Script

This script starts both the PrematchOddsService and LiveOddsCacheService
and integrates them to provide immediate cache updates and UI notifications
when new odds data is successfully saved.
"""

import time
import logging
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main function to start and integrate the live odds system"""
    try:
        logger.info("🚀 Starting Live Odds System...")
        
        # Import services
        from src.prematch_odds_service import get_prematch_odds_service
        from src.live_odds_cache_service import get_live_odds_cache_service
        
        # Get service instances
        prematch_service = get_prematch_odds_service()
        cache_service = get_live_odds_cache_service()
        
        logger.info("✅ Service instances created")
        
        # Start the cache service first
        if not cache_service.start():
            logger.error("❌ Failed to start Live Odds Cache Service")
            return False
        
        logger.info("✅ Live Odds Cache Service started")
        
        # Start the prematch odds service
        if not prematch_service.start():
            logger.error("❌ Failed to start Prematch Odds Service")
            cache_service.stop()
            return False
        
        logger.info("✅ Prematch Odds Service started")
        
        # Integrate the services: when odds are updated, update the cache
        prematch_service.add_odds_updated_callback(cache_service.on_odds_updated)
        
        logger.info("✅ Services integrated successfully")
        logger.info("🎯 Live odds updates will now automatically update cache and trigger UI updates")
        
        # Display service information
        logger.info("📊 Service Information:")
        logger.info(f"   Prematch Service: {'Running' if prematch_service.running else 'Stopped'}")
        logger.info(f"   Cache Service: {'Running' if cache_service.running else 'Stopped'}")
        logger.info(f"   Odds Folder: {cache_service.odds_folder}")
        logger.info(f"   Cached Sports: {len(cache_service.cache_data)}")
        
        # Keep the services running
        logger.info("🔄 Services are now running. Press Ctrl+C to stop.")
        
        try:
            while True:
                time.sleep(10)  # Check every 10 seconds
                
                # Log status periodically
                if prematch_service.running and cache_service.running:
                    logger.info("✅ All services running normally")
                else:
                    logger.warning("⚠️ One or more services have stopped")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
            
    except Exception as e:
        logger.error(f"❌ Error starting Live Odds System: {e}")
        return False
    
    finally:
        # Cleanup
        try:
            if 'prematch_service' in locals():
                prematch_service.stop()
                logger.info("🛑 Prematch Odds Service stopped")
            
            if 'cache_service' in locals():
                cache_service.stop()
                logger.info("🛑 Live Odds Cache Service stopped")
                
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
    
    return True

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the main function
    success = main()
    
    if success:
        logger.info("✅ Live Odds System shutdown complete")
        sys.exit(0)
    else:
        logger.error("❌ Live Odds System failed to start properly")
        sys.exit(1)
