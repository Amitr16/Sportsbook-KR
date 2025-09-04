"""
Snapshot builder service
Builds a full odds snapshot from all sports data
"""

import logging
from typing import Dict, Any
from datetime import datetime
import os
from pathlib import Path
import json

logger = logging.getLogger(__name__)

def build_full_snapshot() -> Dict[str, Any]:
    """Build a complete odds snapshot from all available sports data"""
    try:
        logger.info("🔄 Building full odds snapshot...")
        
        snapshot = {
            "ts": datetime.now().isoformat(),
            "type": "snapshot",
            "data": {}
        }
        
        # Find the Sports Pre Match folder
        sports_folders = [
            Path("Sports Pre Match"),
            Path("src/Sports Pre Match"),
            Path(__file__).parent.parent.parent / "Sports Pre Match",
            Path.cwd() / "Sports Pre Match"
        ]
        
        sports_folder = None
        for folder in sports_folders:
            if folder.exists() and folder.is_dir():
                sports_folder = folder
                break
        
        if not sports_folder:
            logger.warning("⚠️ Sports Pre Match folder not found, returning empty snapshot")
            return snapshot
        
        logger.info(f"📁 Using sports folder: {sports_folder}")
        
        # Scan all sport directories
        sports_processed = 0
        for sport_dir in sports_folder.iterdir():
            if not sport_dir.is_dir():
                continue
                
            sport_name = sport_dir.name
            
            # Look for the main odds file
            odds_file = sport_dir / f"{sport_name}_odds.json"
            if not odds_file.exists():
                continue
            
            try:
                # Read the odds data
                with open(odds_file, 'r', encoding='utf-8') as f:
                    sport_data = json.load(f)
                
                # Extract the actual odds data
                if isinstance(sport_data, dict) and 'odds_data' in sport_data:
                    odds_data = sport_data['odds_data']
                else:
                    odds_data = sport_data
                
                # Add to snapshot
                snapshot["data"][sport_name] = odds_data
                sports_processed += 1
                
                logger.debug(f"✅ Added {sport_name} to snapshot")
                
            except Exception as e:
                logger.error(f"❌ Error reading {sport_name} odds: {e}")
                continue
        
        logger.info(f"✅ Built snapshot with {sports_processed} sports")
        return snapshot
        
    except Exception as e:
        logger.error(f"❌ Error building snapshot: {e}")
        return {
            "ts": datetime.now().isoformat(),
            "type": "snapshot",
            "data": {},
            "error": str(e)
        }

def build_sport_snapshot(sport_name: str) -> Dict[str, Any]:
    """Build a snapshot for a specific sport"""
    try:
        logger.info(f"🔄 Building snapshot for {sport_name}...")
        
        # Find the Sports Pre Match folder
        sports_folders = [
            Path("Sports Pre Match"),
            Path("src/Sports Pre Match"),
            Path(__file__).parent.parent.parent / "Sports Pre Match",
            Path.cwd() / "Sports Pre Match"
        ]
        
        sports_folder = None
        for folder in sports_folders:
            if folder.exists() and folder.is_dir():
                sports_folder = folder
                break
        
        if not sports_folder:
            logger.warning(f"⚠️ Sports Pre Match folder not found for {sport_name}")
            return None
        
        sport_dir = sports_folder / sport_name
        if not sport_dir.exists():
            logger.warning(f"⚠️ Sport directory not found: {sport_dir}")
            return None
        
        # Look for the main odds file
        odds_file = sport_dir / f"{sport_name}_odds.json"
        if not odds_file.exists():
            logger.warning(f"⚠️ Odds file not found: {odds_file}")
            return None
        
        # Read the odds data
        with open(odds_file, 'r', encoding='utf-8') as f:
            sport_data = json.load(f)
        
        # Extract the actual odds data
        if isinstance(sport_data, dict) and 'odds_data' in sport_data:
            return sport_data['odds_data']
        else:
            return sport_data
            
    except Exception as e:
        logger.error(f"❌ Error building {sport_name} snapshot: {e}")
        return None
