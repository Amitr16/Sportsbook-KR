"""
Live Odds Cache Service - Manages in-memory cache of live odds and triggers UI updates
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LiveOddsCacheService:
    def __init__(self):
        self.cache_data = {}  # In-memory cache: {sport_name: {event_id: event_data}}
        self.cache_timestamps = {}  # Track when each sport's cache was last updated
        self.ui_update_callbacks = []  # Callbacks to trigger frontend updates
        self.running = False
        self.base_path = Path("Sports Pre Match")
        
        # Memory limits
        self.max_events_per_sport = int(os.getenv('MAX_EVENTS_PER_SPORT', '2000'))
        self.cache_ttl_sec = int(os.getenv('CACHE_TTL_SEC', '180'))
        
        # Initialize cache from existing JSON files
        self._initialize_cache_from_files()
    
    def clear_cache(self):
        """Clear the entire cache"""
        self.cache_data = {}
        self.cache_timestamps = {}
        logger.info("🧹 Cache cleared")
    
    def reinitialize_cache(self):
        """Reinitialize the cache from JSON files with current filtering"""
        try:
            logger.info("🔄 Reinitializing cache with current filtering...")
            self.cache_data = {}
            self.cache_timestamps = {}
            self._initialize_cache_from_files()
            logger.info("✅ Cache reinitialized successfully")
        except Exception as e:
            logger.error(f"❌ Error reinitializing cache: {e}")
    
    def start(self) -> bool:
        """Start the live odds cache service"""
        try:
            self.running = True
            # Disable cache warmup on startup to save memory
            if not os.getenv('DISABLE_CACHE_WARMUP', 'true').lower() == 'true':
                self.reinitialize_cache()
                logger.info("✅ Live Odds Cache Service started with fresh cache")
            else:
                logger.info("✅ Live Odds Cache Service started (cache warmup disabled for memory)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start Live Odds Cache Service: {e}")
            return False
    
    def stop(self):
        """Stop the live odds cache service"""
        self.running = False
        logger.info("🛑 Live Odds Cache Service stopped")
    
    def _initialize_cache_from_files(self):
        """Initialize the in-memory cache from existing JSON files"""
        try:
            if not self.base_path.exists():
                logger.warning(f"⚠️ Base path does not exist: {self.base_path}")
                return
            
            for sport_folder in self.base_path.iterdir():
                if sport_folder.is_dir():
                    sport_name = sport_folder.name
                    json_file = sport_folder / f"{sport_name}_odds.json"
                    
                    if json_file.exists():
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            
                            # Parse the data and populate cache
                            self._parse_and_cache_sport_data(sport_name, data)
                            logger.info(f"✅ Initialized cache for {sport_name} from {json_file}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error loading {sport_name} JSON: {e}")
            
            logger.info(f"✅ Cache initialization complete. Sports loaded: {list(self.cache_data.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error initializing cache from files: {e}")
    
    def _parse_and_cache_sport_data(self, sport_name: str, data: Dict):
        """Parse JSON data and populate the cache for a specific sport"""
        try:
            if 'odds_data' in data and 'scores' in data['odds_data']:
                scores = data['odds_data']['scores']
                if 'categories' in scores:
                    for category in scores['categories']:
                        if 'matches' in category:
                            for match in category['matches']:
                                # Filter out live/finished matches - only show pre-match odds
                                status = match.get('status', 'Not Started')  # Default to 'Not Started' if no status
                                skip_statuses = ['FT', 'HT', 'LIVE', 'Live', 'live', 'Finished', 'Final', 'Ended', 'Completed', 
                                               '1st Quarter', '2nd Quarter', '3rd Quarter', '4th Quarter', 
                                               'Set 1', 'Set 2', 'Set 3', 'Overtime', 'In Progress', 'in progress']
                                
                                # Debug logging for status filtering
                                logger.info(f"🔍 Checking {sport_name} match {match.get('id', 'unknown')} status: '{status}'")
                                
                                # Case-insensitive filtering
                                if any(skip_status.lower() in status.lower() for skip_status in skip_statuses):
                                    logger.info(f"⏭️ Skipping {sport_name} match {match.get('id', 'unknown')} with status: {status}")
                                    continue  # Skip this match
                                else:
                                    logger.info(f"✅ Accepting {sport_name} match {match.get('id', 'unknown')} with status: {status}")
                                
                                # Convert match to event format
                                event = self._parse_match_to_event(match, sport_name)
                                if event:
                                    event_id = event.get('id')
                                    if event_id:
                                        if sport_name not in self.cache_data:
                                            self.cache_data[sport_name] = {}
                                        self.cache_data[sport_name][event_id] = event
            
            # Update timestamp
            self.cache_timestamps[sport_name] = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error parsing {sport_name} data: {e}")
    
    def _parse_match_to_event(self, match: Dict, sport_name: str) -> Optional[Dict]:
        """Parse a match from JSON into the event format expected by the API"""
        try:
            # Extract basic match information
            event = {
                'id': match.get('id', ''),
                'sport': sport_name,
                'status': match.get('status', 'Not Started'),
                'time': match.get('time', ''),
                'date': match.get('formatted_date', '') or match.get('date', ''),
                'formatted_date': match.get('formatted_date', ''),
                'league': match.get('category', {}).get('name', '') if isinstance(match.get('category'), dict) else str(match.get('category', '')),
            }
            
            # Extract team names based on sport
            if sport_name in ['soccer', 'handball', 'hockey', 'futsal', 'cricket']:
                # These sports use localteam/visitorteam
                localteam = match.get('localteam', {})
                visitorteam = match.get('visitorteam', {})
                
                if isinstance(localteam, dict):
                    event['home_team'] = localteam.get('name', '')
                else:
                    event['home_team'] = str(localteam) if localteam else ''
                
                if isinstance(visitorteam, dict):
                    event['away_team'] = visitorteam.get('name', '')
                else:
                    event['away_team'] = str(visitorteam) if visitorteam else ''
                    
            elif sport_name == 'basketball':
                # Basketball uses home_team/away_team
                event['home_team'] = match.get('home_team', '')
                event['away_team'] = match.get('away_team', '')
                
            elif sport_name in ['tennis', 'table_tennis', 'darts']:
                # Individual sports use player_1/player_2
                player_1 = match.get('player_1', {})
                player_2 = match.get('player_2', {})
                
                if isinstance(player_1, dict):
                    event['home_team'] = player_1.get('name', '')
                else:
                    event['home_team'] = str(player_1) if player_1 else ''
                
                if isinstance(player_2, dict):
                    event['away_team'] = player_2.get('name', '')
                else:
                    event['away_team'] = str(player_2) if player_2 else ''
            
            else:
                # Default fallback
                event['home_team'] = match.get('home_team', '') or match.get('localteam', '')
                event['away_team'] = match.get('away_team', '') or match.get('visitorteam', '')
            
            # Extract odds using the working odds extraction logic
            from src.routes.json_sports import extract_odds_from_match
            odds = extract_odds_from_match(match, sport_name)
            if odds:
                event['odds'] = odds
            else:
                event['odds'] = {}
            
            return event
            
        except Exception as e:
            logger.error(f"❌ Error parsing match to event: {e}")
            return None
    
    def on_odds_updated(self, sport_name: str, odds_data: Dict):
        """Callback triggered when odds are updated by PrematchOddsService"""
        try:
            logger.info(f"🎯 Live odds update received for {sport_name}")
            logger.info(f"📊 Data received: {len(odds_data) if isinstance(odds_data, dict) else 'not dict'}")
            
            # Parse and update the cache
            self._parse_and_cache_sport_data(sport_name, odds_data)
            
            # Log cache status after update
            if sport_name in self.cache_data:
                logger.info(f"📈 Cache updated for {sport_name}: {len(self.cache_data[sport_name])} events")
                # Log first few events to see their status
                for i, (event_id, event) in enumerate(list(self.cache_data[sport_name].items())[:3]):
                    logger.info(f"   Event {i+1}: {event.get('home_team', '?')} vs {event.get('away_team', '?')} - Status: {event.get('status', '?')}")
            
            # Trigger UI update callbacks
            self._trigger_ui_updates(sport_name)
            
            logger.info(f"✅ Cache updated and UI update triggered for {sport_name}")
            
        except Exception as e:
            logger.error(f"❌ Error processing odds update for {sport_name}: {e}")
    

    
    def _trigger_ui_updates(self, sport_name: str):
        """Trigger frontend UI updates for a specific sport"""
        try:
            # Call local callbacks
            for callback in self.ui_update_callbacks:
                try:
                    callback(sport_name)
                except Exception as e:
                    logger.error(f"❌ Error in UI update callback: {e}")
            
            logger.info(f"✅ UI update callbacks triggered for {sport_name}")
                
        except Exception as e:
            logger.error(f"❌ Error triggering UI updates: {e}")
    
    def get_sport_events(self, sport_name: str, date_filter: str = 'all', limit: int = 50) -> List[Dict]:
        """Get events for a specific sport from the cache"""
        try:
            if sport_name not in self.cache_data:
                return []
            
            events = list(self.cache_data[sport_name].values())
            
            # Apply date filter if needed
            if date_filter != 'all':
                # Simple date filtering - could be enhanced
                pass
            
            # Apply limit
            if limit > 0:
                events = events[:limit]
            
            return events
            
        except Exception as e:
            logger.error(f"❌ Error getting events for {sport_name}: {e}")
            return []
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache"""
        try:
            total_events = sum(len(events) for events in self.cache_data.values())
            return {
                'running': self.running,
                'sports_cached': list(self.cache_data.keys()),
                'total_events': total_events,
                'cache_timestamps': {sport: ts.isoformat() for sport, ts in self.cache_timestamps.items()}
            }
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {'error': str(e)}

# Global instance
_live_odds_cache_service = None

def get_live_odds_cache_service() -> LiveOddsCacheService:
    """Get the global instance of LiveOddsCacheService"""
    global _live_odds_cache_service
    if _live_odds_cache_service is None:
        _live_odds_cache_service = LiveOddsCacheService()
    return _live_odds_cache_service
