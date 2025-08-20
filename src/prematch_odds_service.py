import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PrematchOddsService:
    def __init__(self, base_folder: str = "Sports Pre Match"):
        self.base_url = "http://www.goalserve.com/getfeed"
        self.access_token = "e1e6a26b1dfa4f52976f08ddd2a17244"
        self.base_folder = Path(base_folder)
        self.running = False
        self.fetch_thread = None
        
        # Sports configuration with their category codes
        self.sports_config = {
            'soccer': {
                'category': 'soccer_10',
                'display_name': 'Soccer',
                'icon': '⚽'
            },
            'basketball': {
                'category': 'basket_10',
                'display_name': 'Basketball',
                'icon': '🏀'
            },
            'tennis': {
                'category': 'tennis_10',
                'display_name': 'Tennis',
                'icon': '🎾'
            },
            'hockey': {
                'category': 'hockey_10',
                'display_name': 'Hockey',
                'icon': '🏒'
            },
            'handball': {
                'category': 'handball_10',
                'display_name': 'Handball',
                'icon': '🤾'
            },
            'volleyball': {
                'category': 'volleyball_10',
                'display_name': 'Volleyball',
                'icon': '🏐'
            },
            'football': {
                'category': 'football_10',
                'display_name': 'American Football',
                'icon': '🏈'
            },
            'baseball': {
                'category': 'baseball_10',
                'display_name': 'Baseball',
                'icon': '⚾'
            },
            'cricket': {
                'category': 'cricket_10',
                'display_name': 'Cricket',
                'icon': '🏏'
            },
            'rugby': {
                'category': 'rugby_10',
                'display_name': 'Rugby Union',
                'icon': '🏉'
            },
            'rugbyleague': {
                'category': 'rugbyleague_10',
                'display_name': 'Rugby League',
                'icon': '🏉'
            },
            'boxing': {
                'category': 'boxing_10',
                'display_name': 'Boxing',
                'icon': '🥊'
            },
            'esports': {
                'category': 'esports_10',
                'display_name': 'Esports',
                'icon': '🎮'
            },
            'futsal': {
                'category': 'futsal_10',
                'display_name': 'Futsal',
                'icon': '⚽'
            },
            'mma': {
                'category': 'mma_10',
                'display_name': 'MMA',
                'icon': '🥋'
            },
            'table_tennis': {
                'category': 'table_tennis_10',
                'display_name': 'Table Tennis',
                'icon': '🏓'
            },
            'golf': {
                'category': 'golf_10',
                'display_name': 'Golf',
                'icon': '⛳'
            },
            'darts': {
                'category': 'darts_10',
                'display_name': 'Darts',
                'icon': '🎯'
            }
        }
        
        # Request configuration
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GoalServe-PrematchOdds/1.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Timeout settings
        self.timeout = (10, 30)  # (connect_timeout, read_timeout)
        
        # Statistics
        self.stats = {
            'total_fetches': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'last_fetch_time': None,
            'last_error': None
        }
        
        # Ensure base folder exists
        self._ensure_folder_structure()
    
    def _ensure_folder_structure(self):
        """Ensure the base folder and sport subfolders exist"""
        try:
            # Create base folder
            self.base_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Base folder created/verified: {self.base_folder}")
            
            # Create subfolders for each sport
            for sport_name in self.sports_config.keys():
                sport_folder = self.base_folder / sport_name
                sport_folder.mkdir(exist_ok=True)
                logger.info(f"✅ Sport folder created/verified: {sport_folder}")
                
        except Exception as e:
            logger.error(f"❌ Error creating folder structure: {e}")
            raise
    
    def _get_dynamic_dates(self) -> tuple:
        """Get dynamic date range (yesterday to tomorrow)"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Format dates as DD.MM.YYYY
        date_start = yesterday.strftime('%d.%m.%Y')
        date_end = tomorrow.strftime('%d.%m.%Y')
        
        return date_start, date_end
    
    def _build_odds_url(self, sport_name: str, date_start: str, date_end: str) -> str:
        """Build the odds URL for a specific sport"""
        category = self.sports_config[sport_name]['category']
        
        # Cricket uses simpler URL without bm=16 and date parameters
        if sport_name == 'cricket':
            url = (f"{self.base_url}/{self.access_token}/getodds/soccer?"
                   f"cat={category}&json=1")
        else:
            # All other sports use the same URL structure with different categories
            url = (f"{self.base_url}/{self.access_token}/getodds/soccer?"
                   f"cat={category}&json=1&bm=16&"
                   f"date_start={date_start}&date_end={date_end}")
        
        return url
    
    def _fetch_odds(self, sport_name: str, url: str) -> Optional[Dict]:
        """Fetch odds with single attempt - no retry logic"""
        try:
            logger.info(f"🔄 Fetching {sport_name} odds (single attempt)")
            
            response = self.session.get(url, timeout=self.timeout)
            
            # Handle different HTTP status codes
            if response.status_code == 200:
                try:
                    # Handle UTF-8 BOM if present
                    text = response.text
                    if text.startswith('\ufeff'):
                        text = text[1:]  # Remove BOM
                    data = json.loads(text)
                    
                    # Check if the response contains an error
                    if isinstance(data, dict):
                        if 'status' in data and data['status'] != '200':
                            logger.warning(f"⚠️ API Error for {sport_name}: {data.get('status')} - {data.get('message', 'Unknown error')}")
                            return data
                        
                        if 'message' in data and any(error_keyword in data['message'].lower() for error_keyword in ['error', 'failed', 'timeout', 'too many requests', 'rate limit']):
                            logger.warning(f"⚠️ API Error for {sport_name}: {data['message']}")
                            return data
                    
                    logger.info(f"✅ Successfully fetched {sport_name} odds")
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error for {sport_name}: {e}")
                    return None
            
            elif response.status_code == 429:  # Too Many Requests
                logger.warning(f"⚠️ Rate limit (429) for {sport_name}")
                return {'status': '429', 'message': 'Too Many Requests'}
            
            elif response.status_code == 500:  # Server Error
                logger.warning(f"⚠️ Server error (500) for {sport_name}")
                return {'status': '500', 'message': 'Server Error'}
            
            else:
                logger.warning(f"⚠️ HTTP {response.status_code} for {sport_name}")
                return {'status': str(response.status_code), 'message': f'HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout for {sport_name}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error for {sport_name}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Unexpected error for {sport_name}: {e}")
            return None
        
        logger.error(f"❌ Failed to fetch {sport_name} odds")
        return None
    
    def _save_odds_to_file(self, sport_name: str, odds_data: Dict) -> bool:
        """Save odds data to JSON file (overwrites existing file)"""
        try:
            
            # IMMEDIATE BLOCK: Check for the exact empty response pattern from raw API
            # Raw API response structure: {"scores": {"sport": "tennis", "ts": "0", "categories": []}}
            if (isinstance(odds_data, dict) and 
                'scores' in odds_data and 
                isinstance(odds_data['scores'], dict)):
                
                scores_data = odds_data['scores']
                
                # Check for ts=0 (indicates no data available)
                if 'ts' in scores_data:
                    ts_value = scores_data['ts']
                    # Check for both string "0" and integer 0, and also handle None/empty cases
                    if (ts_value == "0" or ts_value == 0 or ts_value == "" or ts_value is None):
                        logger.warning(f"🚫 IMMEDIATE BLOCK for {sport_name} - Invalid timestamp detected: {ts_value}")
                        logger.info(f"📊 Blocked response: {sport_name} has invalid timestamp")
                        return False
                
                # Check for empty categories array
                if ('categories' in scores_data and 
                    (not scores_data['categories'] or 
                     (isinstance(scores_data['categories'], list) and 
                      len(scores_data['categories']) == 0))):
                    
                    logger.warning(f"🚫 IMMEDIATE BLOCK for {sport_name} - Empty categories array detected")
                    logger.info(f"📊 Blocked response structure: {sport_name} has 0 categories")
                    return False
                
                # ADDITIONAL CHECK: If we have both ts=0 AND empty categories, this is definitely invalid
                if ('ts' in scores_data and 
                    (scores_data['ts'] == "0" or scores_data['ts'] == 0) and
                    'categories' in scores_data and 
                    (not scores_data['categories'] or 
                     (isinstance(scores_data['categories'], list) and 
                      len(scores_data['categories']) == 0))):
                    
                    logger.warning(f"🚫 IMMEDIATE BLOCK for {sport_name} - Invalid response: ts=0 AND empty categories")
                    logger.info(f"📊 Blocked invalid response: {sport_name} has no data")
                    return False
            
            # Also check for the wrapped structure (in case it's already wrapped)
            if (isinstance(odds_data, dict) and 
                'odds_data' in odds_data and 
                isinstance(odds_data['odds_data'], dict) and
                'scores' in odds_data['odds_data'] and
                isinstance(odds_data['odds_data']['scores'], dict)):
                
                scores_data = odds_data['odds_data']['scores']
                
                # Check for ts=0 (indicates no data available)
                if 'ts' in scores_data:
                    ts_value = scores_data['ts']
                    # Check for both string "0" and integer 0, and also handle None/empty cases
                    if (ts_value == "0" or ts_value == 0 or ts_value == "" or ts_value is None):
                        logger.warning(f"🚫 IMMEDIATE BLOCK for {sport_name} - Invalid timestamp detected: {ts_value}")
                        logger.info(f"📊 Blocked response: {sport_name} has invalid timestamp")
                        return False
                
                # Check for empty categories array
                if ('categories' in scores_data and 
                    (not scores_data['categories'] or 
                     (isinstance(scores_data['categories'], list) and 
                      len(scores_data['categories']) == 0))):
                    
                    logger.warning(f"🚫 IMMEDIATE BLOCK for {sport_name} - Empty categories array detected")
                    logger.info(f"📊 Blocked response structure: {sport_name} has 0 categories")
                    return False
            
            # Check if odds_data contains an error
            if isinstance(odds_data, dict):
                # Check for common error indicators
                if 'status' in odds_data and odds_data['status'] != '200':
                    logger.warning(f"⚠️ Skipping save for {sport_name} - Error status: {odds_data.get('status')} - {odds_data.get('message', 'Unknown error')}")
                    return False
                
                # Check for error messages
                if 'message' in odds_data and any(error_keyword in odds_data['message'].lower() for error_keyword in ['error', 'failed', 'timeout', 'too many requests', 'rate limit']):
                    logger.warning(f"⚠️ Skipping save for {sport_name} - Error message: {odds_data['message']}")
                    return False
                
                # Check if odds_data is empty or contains no actual odds
                if not odds_data or (len(odds_data) == 1 and 'status' in odds_data):
                    logger.warning(f"⚠️ Skipping save for {sport_name} - No valid odds data")
                    return False
                
                # CRITICAL CHECK: Look for the specific empty response pattern you mentioned
                # Example: {"odds_data": {"scores": {"sport": "soccer", "ts": "0", "categories": []}}}
                if 'odds_data' in odds_data:
                    odds_content = odds_data['odds_data']
                    if isinstance(odds_content, dict):
                        # Check if it's the scores structure with empty categories
                        if 'scores' in odds_content:
                            scores_data = odds_content['scores']
                            if isinstance(scores_data, dict) and 'categories' in scores_data:
                                categories = scores_data['categories']
                                if not categories or (isinstance(categories, list) and len(categories) == 0):
                                    logger.warning(f"🚫 BLOCKING SAVE for {sport_name} - API returned empty categories array (no events/odds)")
                                    logger.info(f"📊 Empty response structure: {sport_name} has 0 categories")
                                    return False
                        
                        # Check if odds_data is essentially empty (no meaningful content)
                        if not odds_content or (len(odds_content) == 1 and 'scores' in odds_content):
                            logger.warning(f"⚠️ Skipping save for {sport_name} - No meaningful odds content in response")
                            return False
                        
                        # Additional check: look for any actual betting markets with odds
                        has_actual_odds = False
                        for key, value in odds_content.items():
                            if key == 'scores' and isinstance(value, dict):
                                # Check if scores has actual categories with events
                                if 'categories' in value and value['categories']:
                                    for category in value['categories']:
                                        if isinstance(category, dict) and 'events' in category:
                                            events = category['events']
                                            if events and len(events) > 0:
                                                # Check if any event has actual odds
                                                for event in events:
                                                    if isinstance(event, dict) and 'odds' in event:
                                                        odds = event['odds']
                                                        if odds and isinstance(odds, dict) and len(odds) > 0:
                                                            has_actual_odds = True
                                                            break
                                                if has_actual_odds:
                                                    break
                            elif isinstance(value, dict) and 'events' in value:
                                # Direct events structure
                                events = value['events']
                                if events and len(events) > 0:
                                    for event in events:
                                        if isinstance(event, dict) and 'odds' in event:
                                            odds = event['odds']
                                            if odds and isinstance(odds, dict) and len(odds) > 0:
                                                has_actual_odds = True
                                                break
                                    if has_actual_odds:
                                        break
                        
                        if not has_actual_odds:
                            logger.warning(f"⚠️ Skipping save for {sport_name} - No actual betting odds found in response structure")
                            logger.info(f"📊 Response structure for {sport_name}: {list(odds_content.keys())}")
                            return False
            
            # Log what we're about to save (for debugging)
            logger.info(f"✅ Validation passed for {sport_name} - Proceeding to save odds data")
            logger.info(f"📊 Response structure for {sport_name}: {list(odds_data.keys()) if isinstance(odds_data, dict) else 'Not a dict'}")
            if isinstance(odds_data, dict) and 'odds_data' in odds_data:
                logger.info(f"📊 Odds data structure: {list(odds_data['odds_data'].keys())}")
                if 'scores' in odds_data['odds_data']:
                    scores = odds_data['odds_data']['scores']
                    logger.info(f"📊 Scores structure: {list(scores.keys()) if isinstance(scores, dict) else 'Not a dict'}")
                    if isinstance(scores, dict) and 'ts' in scores:
                        logger.info(f"📊 Timestamp value: {scores['ts']}")
                    if isinstance(scores, dict) and 'categories' in scores:
                        logger.info(f"📊 Categories count: {len(scores['categories']) if isinstance(scores['categories'], list) else 'Not a list'}")
            
            # Create filename without timestamp - always overwrites the same file
            filename = f"{sport_name}_odds.json"
            filepath = self.base_folder / sport_name / filename
            
            # Add metadata to the data
            data_with_metadata = {
                'metadata': {
                    'sport': sport_name,
                    'display_name': self.sports_config[sport_name]['display_name'],
                    'icon': self.sports_config[sport_name]['icon'],
                    'fetch_timestamp': datetime.now().isoformat(),
                    'date_range': self._get_dynamic_dates()
                },
                'odds_data': odds_data
            }
            
            # Save to file (overwrites existing file)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_with_metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Updated {sport_name} odds file: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving {sport_name} odds: {e}")
            return False
    
    def _fetch_single_sport_odds(self, sport_name: str) -> bool:
        """Fetch odds for a single sport"""
        try:
            # Get dynamic dates
            date_start, date_end = self._get_dynamic_dates()
            
            # Build URL
            url = self._build_odds_url(sport_name, date_start, date_end)
            
            # Log the URL being used
            logger.info(f"🌐 URL for {sport_name}: {url}")
            
            # Fetch odds with single attempt
            odds_data = self._fetch_odds(sport_name, url)
            
            if odds_data:
                # Check if the data contains an error
                if isinstance(odds_data, dict):
                    if 'status' in odds_data and odds_data['status'] != '200':
                        logger.warning(f"⚠️ Skipping save for {sport_name} due to error status: {odds_data.get('status')}")
                        self.stats['failed_fetches'] += 1
                        return False
                    
                    if 'message' in odds_data and any(error_keyword in odds_data['message'].lower() for error_keyword in ['error', 'failed', 'timeout', 'too many requests', 'rate limit']):
                        logger.warning(f"⚠️ Skipping save for {sport_name} due to error message: {odds_data['message']}")
                        self.stats['failed_fetches'] += 1
                        return False
                
                # Save to file (this will also check for errors and skip saving if needed)
                success = self._save_odds_to_file(sport_name, odds_data)
                if success:
                    self.stats['successful_fetches'] += 1
                    return True
                else:
                    self.stats['failed_fetches'] += 1
                    return False
            else:
                self.stats['failed_fetches'] += 1
                return False
                
        except Exception as e:
            logger.error(f"❌ Error fetching {sport_name} odds: {e}")
            self.stats['failed_fetches'] += 1
            return False
    
    def _fetch_all_sports_odds(self):
        """Fetch odds for all sports"""
        logger.info("🚀 Starting pre-match odds fetch for all sports")
        
        date_start, date_end = self._get_dynamic_dates()
        logger.info(f"📅 Date range: {date_start} to {date_end}")
        
        successful_sports = []
        failed_sports = []
        
        for sport_name in self.sports_config.keys():
            try:
                success = self._fetch_single_sport_odds(sport_name)
                if success:
                    successful_sports.append(sport_name)
                else:
                    failed_sports.append(sport_name)
                    
                # Small delay between requests to be respectful
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error processing {sport_name}: {e}")
                failed_sports.append(sport_name)
        
        # Update statistics
        self.stats['total_fetches'] += len(self.sports_config)
        self.stats['last_fetch_time'] = datetime.now().isoformat()
        
        # Log summary
        logger.info(f"📊 Fetch Summary:")
        logger.info(f"   ✅ Successful: {len(successful_sports)} sports")
        logger.info(f"   ❌ Failed: {len(failed_sports)} sports")
        
        if successful_sports:
            logger.info(f"   ✅ Successful sports: {', '.join(successful_sports)}")
        
        if failed_sports:
            logger.info(f"   ❌ Failed sports: {', '.join(failed_sports)}")
    
    def _fetch_loop(self):
        """Main fetch loop that runs every 30 seconds"""
        logger.info("🔄 Starting pre-match odds fetch loop")
        
        while self.running:
            try:
                self._fetch_all_sports_odds()
                
                # Wait 30 seconds before next fetch
                logger.info("⏳ Waiting 30 seconds before next fetch...")
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Error in fetch loop: {e}")
                self.stats['last_error'] = str(e)
                
                # Wait 30 seconds before retry
                logger.info("⏳ Waiting 30 seconds before retry...")
                time.sleep(30)
    
    def start(self):
        """Start the pre-match odds service"""
        if not self.running:
            try:
                self.running = True
                self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
                self.fetch_thread.start()
                logger.info("✅ Pre-match odds service started successfully")
                return True
            except Exception as e:
                self.running = False
                logger.error(f"❌ Failed to start pre-match odds service: {e}")
                return False
        return True
    
    def stop(self):
        """Stop the pre-match odds service"""
        self.running = False
        if self.fetch_thread:
            self.fetch_thread.join()
        logger.info("🛑 Pre-match odds service stopped")
    
    def get_stats(self) -> Dict:
        """Get service statistics"""
        return {
            'service_running': self.running,
            'total_sports': len(self.sports_config),
            'stats': self.stats,
            'base_folder': str(self.base_folder),
            'sports_configured': list(self.sports_config.keys())
        }
    
    def get_recent_files(self, sport_name: str = None, limit: int = 5) -> List[Dict]:
        """Get recent odds files"""
        try:
            files = []
            
            if sport_name:
                # Get files for specific sport
                sport_folder = self.base_folder / sport_name
                if sport_folder.exists():
                    for file in sport_folder.glob("*.json"):
                        files.append({
                            'sport': sport_name,
                            'filename': file.name,
                            'path': str(file),
                            'size': file.stat().st_size,
                            'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                        })
            else:
                # Get files for all sports
                for sport_name in self.sports_config.keys():
                    sport_folder = self.base_folder / sport_name
                    if sport_folder.exists():
                        for file in sport_folder.glob("*.json"):
                            files.append({
                                'sport': sport_name,
                                'filename': file.name,
                                'path': str(file),
                                'size': file.stat().st_size,
                                'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                            })
            
            # Sort by modification time (newest first) and limit
            files.sort(key=lambda x: x['modified'], reverse=True)
            return files[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error getting recent files: {e}")
            return []


# Global service instance
prematch_odds_service = None

def get_prematch_odds_service():
    """Get or create the global pre-match odds service instance"""
    global prematch_odds_service
    if prematch_odds_service is None:
        prematch_odds_service = PrematchOddsService()
    return prematch_odds_service
