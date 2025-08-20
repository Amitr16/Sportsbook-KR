"""
Working GoalServe API Client with Correct Data Structure Parsing
"""

import requests
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
from io import BytesIO
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedGoalServeClient:
    def __init__(self):
        self.base_url = "http://www.goalserve.com/getfeed"
        self.access_token = "e1e6a26b1dfa4f52976f08ddd2a17244"
        
        # Cache configuration
        self.cache = {}
        self.cache_duration = 300  # 5 minutes cache
        self.cache_lock = threading.Lock()
        
        # Request configuration for faster responses
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GoalServe-Client/1.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Timeout settings
        self.timeout = (5, 15)  # (connect_timeout, read_timeout)
        
        # Sports configuration with working endpoints
        self.sports_config = {
            'soccer': {
                'endpoint': 'soccernew/home',
                'events_endpoint': 'soccernew/home',
                'icon': '⚽',
                'display_name': 'Soccer',
                'has_draw': True,
                'priority': 1
            },
            'basketball': {
                'endpoint': 'bsktbl/home',
                'events_endpoint': 'bsktbl/home', 
                'icon': '🏀',
                'display_name': 'Basketball',
                'has_draw': True,
                'priority': 2
            },
            'tennis': {
                'endpoint': 'tennis_scores/home',
                'events_endpoint': 'tennis_scores/home',
                'icon': '🎾', 
                'display_name': 'Tennis',
                'has_draw': False,
                'priority': 3
            },
            'baseball': {
                'endpoint': 'baseball/home',
                'events_endpoint': 'baseball/home',
                'icon': '⚾',
                'display_name': 'Baseball', 
                'has_draw': False,
                'priority': 4
            },
            'hockey': {
                'endpoint': 'hockey/home',
                'events_endpoint': 'hockey/home',
                'icon': '🏒',
                'display_name': 'Hockey',
                'has_draw': False,
                'priority': 5
            },
            'cricket': {
                'endpoint': 'soccer?cat=cricket_10',
                'events_endpoint': 'soccer?cat=cricket_10',
                'icon': '🏏',
                'display_name': 'Cricket',
                'has_draw': True,
                'priority': 6
            },
            'football': {
                'endpoint': 'soccer?cat=football_10',
                'events_endpoint': 'soccer?cat=football_10',
                'icon': '🏈',
                'display_name': 'American Football',
                'has_draw': False,
                'priority': 7
            },
            'rugby': {
                'endpoint': 'rugby/home',
                'events_endpoint': 'rugby/home',
                'icon': '🏉',
                'display_name': 'Rugby',
                'has_draw': True,
                'priority': 8
            },
            'rugbyleague': {
                'endpoint': 'rugby/home',
                'events_endpoint': 'rugby/home',
                'icon': '🏉',
                'display_name': 'Rugby League',
                'has_draw': True,
                'priority': 9
            },
            'boxing': {
                'endpoint': 'boxing/home',
                'events_endpoint': 'boxing/home',
                'icon': '🥊',
                'display_name': 'Boxing',
                'has_draw': False,
                'priority': 10
            },
            'mma': {
                'endpoint': 'mma/home',
                'events_endpoint': 'mma/home',
                'icon': '🥋',
                'display_name': 'MMA',
                'has_draw': False,
                'priority': 11
            },
            'volleyball': {
                'endpoint': 'volleyball/home',
                'events_endpoint': 'volleyball/home',
                'icon': '🏐',
                'display_name': 'Volleyball',
                'has_draw': False,
                'priority': 12
            },
            'handball': {
                'endpoint': 'handball/home',
                'events_endpoint': 'handball/home',
                'icon': '🤾',
                'display_name': 'Handball',
                'has_draw': True,
                'priority': 13
            },
            'table_tennis': {
                'endpoint': 'table_tennis/home',
                'events_endpoint': 'table_tennis/home',
                'icon': '🏓',
                'display_name': 'Table Tennis',
                'has_draw': False,
                'priority': 14
            },
            'darts': {
                'endpoint': 'darts/home',
                'events_endpoint': 'darts/home',
                'icon': '🎯',
                'display_name': 'Darts',
                'has_draw': False,
                'priority': 15
            },
            'esports': {
                'endpoint': 'esports/home',
                'events_endpoint': 'esports/home',
                'icon': '🎮',
                'display_name': 'Esports',
                'has_draw': False,
                'priority': 16
            },
            'futsal': {
                'endpoint': 'futsal/home',
                'events_endpoint': 'futsal/home',
                'icon': '⚽',
                'display_name': 'Futsal',
                'has_draw': True,
                'priority': 17
            },
            'golf': {
                'endpoint': 'golf/home',
                'events_endpoint': 'golf/home',
                'icon': '⛳',
                'display_name': 'Golf',
                'has_draw': False,
                'priority': 18
            }
        }

    def _get_cache_key(self, endpoint: str, params: Dict = None) -> str:
        """Generate cache key for request"""
        params_str = json.dumps(params or {}, sort_keys=True)
        return f"{endpoint}:{params_str}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        if not cache_entry:
            return False
        
        cache_time = cache_entry.get('timestamp', 0)
        cache_duration = cache_entry.get('duration', self.cache_duration)
        return time.time() - cache_time < cache_duration

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if valid"""
        with self.cache_lock:
            cache_entry = self.cache.get(cache_key)
            if self._is_cache_valid(cache_entry):
                logger.info(f"Cache hit for {cache_key}")
                return cache_entry['data']
        return None

    def _set_cache(self, cache_key: str, data: Any, duration: int = None) -> None:
        """Set data in cache with optional custom duration"""
        if duration is None:
            duration = self.cache_duration
            
        with self.cache_lock:
            self.cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'duration': duration
            }

    def _make_request(self, endpoint: str, params: Dict = None, use_cache: bool = True) -> Optional[Dict]:
        """Make optimized API request with caching"""
        cache_key = self._get_cache_key(endpoint, params)
        
        # Check cache first
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Build URL
        url = f"{self.base_url}/{self.access_token}/{endpoint}"
        if not params:
            params = {}
        params['json'] = '1'  # Always request JSON format

        try:
            # Log the actual URL with parameters
            full_url = f"{url}?json=1"
            logger.info(f"Making API call to: {full_url}")
            start_time = time.time()
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            elapsed_time = time.time() - start_time
            logger.info(f"API call completed in {elapsed_time:.2f} seconds")
            
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}")
                return None

            # Parse response
            try:
                # Check if response is XML (common for GoalServe)
                content_type = response.headers.get('content-type', '').lower()
                if 'xml' in content_type or response.text.strip().startswith('<?xml'):
                    logger.info("Detected XML response, converting to JSON")
                    # Try to parse XML as JSON (sometimes GoalServe returns XML even with json=1)
                    # For now, let's try to parse it anyway
                    logger.warning("API returned XML despite json=1 parameter, attempting to parse anyway")
                
                # Handle UTF-8 BOM if present
                text = response.text
                if text.startswith('\ufeff'):
                    text = text[1:]  # Remove BOM
                
                data = json.loads(text)
                logger.info("Parsed JSON response successfully")
                
                # Cache the result
                if use_cache:
                    self._set_cache(cache_key, data)
                
                return data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    def get_available_sports(self) -> List[Dict]:
        """Get available sports by scanning Sports Pre Match folder"""
        logger.info("Getting available sports from Sports Pre Match folder...")
        
        # Check cache for sports list
        cache_key = "available_sports"
        cached_sports = self._get_from_cache(cache_key)
        if cached_sports:
            logger.info("Returning cached sports data")
            return cached_sports

        sports_data = []
        
        # Scan the Sports Pre Match folder for available sports
        import os
        from pathlib import Path
        
        # Try multiple possible paths for the Sports Pre Match folder
        possible_paths = [
            Path("Sports Pre Match"),  # Relative to current working directory
            Path("src/Sports Pre Match"),  # Relative to src directory
            Path(__file__).parent.parent / "Sports Pre Match",  # Relative to this file
            Path.cwd() / "Sports Pre Match",  # Relative to current working directory
            Path(__file__).parent.parent.parent / "Sports Pre Match"  # Go up one more level if needed
        ]
        
        logger.info(f"Current working directory: {Path.cwd()}")
        logger.info(f"This file location: {Path(__file__)}")
        logger.info(f"Parent directory: {Path(__file__).parent}")
        logger.info(f"Grandparent directory: {Path(__file__).parent.parent}")
        
        sports_folder = None
        for i, path in enumerate(possible_paths):
            logger.info(f"Trying path {i+1}: {path} (exists: {path.exists()})")
            if path.exists():
                sports_folder = path
                logger.info(f"Found Sports Pre Match folder at: {sports_folder}")
                break
        
        if not sports_folder:
            logger.error("Sports Pre Match folder not found in any of the expected locations")
            logger.error("Available paths tried:")
            for i, path in enumerate(possible_paths):
                logger.error(f"  {i+1}: {path} (exists: {path.exists()})")
            # Fallback to configured sports
            for sport_name, config in self.sports_config.items():
                sports_data.append({
                    'name': sport_name,
                    'display_name': config.get('display_name', sport_name.title()),
                    'icon': config.get('icon', '🏆'),
                    'event_count': 0
                })
            logger.info(f"Fallback: returning {len(sports_data)} configured sports")
            return sports_data
        
        logger.info(f"Scanning folder: {sports_folder}")
        logger.info(f"Contents of sports folder: {[item.name for item in sports_folder.iterdir()]}")
        
        # Clear any existing cache to ensure fresh data
        self.cache.clear()
        
        for sport_folder in sports_folder.iterdir():
            if sport_folder.is_dir():
                sport_name = sport_folder.name
                json_file = sport_folder / f"{sport_name}_odds.json"
                logger.info(f"Checking sport: {sport_name}, JSON file: {json_file} (exists: {json_file.exists()})")
                
                if json_file.exists():
                    try:
                        # Get sport config from our configuration
                        sport_config = self.sports_config.get(sport_name, {})
                        logger.info(f"Sport config for {sport_name}: {sport_config}")
                        
                        # Count events in the JSON file
                        event_count = self._count_events_in_json(json_file)
                        logger.info(f"Event count for {sport_name}: {event_count}")
                        
                        sports_data.append({
                            'name': sport_name,
                            'display_name': sport_config.get('display_name', sport_name.title()),
                            'icon': sport_config.get('icon', '🏆'),
                            'event_count': event_count
                        })
                        
                        logger.info(f"Loaded {sport_name}: {event_count} events from JSON")
                        
                    except Exception as e:
                        logger.error(f"Failed to load {sport_name}: {e}")
                        # Add with 0 events as fallback
                        sports_data.append({
                            'name': sport_name,
                            'display_name': sport_name.title(),
                            'icon': '🏆',
                            'event_count': 0
                        })
                else:
                    # If no _odds.json, but it's a directory, add it to sports_data
                    # This handles cases where a sport folder exists but has no odds data
                    logger.info(f"Sport folder {sport_name} exists but no odds.json found, adding with 0 events")
                    sports_data.append({
                        'name': sport_name,
                        'display_name': sport_name.title(),
                        'icon': '🏆',
                        'event_count': 0
                    })
        
        # Sort by priority if available
        sports_data.sort(key=lambda x: next(
            (config['priority'] for name, config in self.sports_config.items() 
             if name == x['name']), 999
        ))

        # Cache the result
        self._set_cache(cache_key, sports_data)
        
        logger.info(f"Final result: Loaded {len(sports_data)} sports from JSON files")
        logger.info(f"Sports loaded: {[s['name'] for s in sports_data]}")
        
        return sports_data
    
    def _count_events_in_json(self, json_file: Path) -> int:
        """Count events in a JSON file"""
        try:
            import json
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if 'odds_data' in data and 'scores' in data['odds_data']:
                scores = data['odds_data']['scores']
                
                # Check for cricket format (scores.category[])
                if 'category' in scores and isinstance(scores['category'], list):
                    total_events = 0
                    for category in scores['category']:
                        if 'matches' in category:
                            matches = category['matches']
                            if 'match' in matches:
                                # Cricket format: single match object
                                if isinstance(matches['match'], list):
                                    total_events += len(matches['match'])
                                else:
                                    total_events += 1
                    return total_events
                
                # Check for standard format (scores.categories[])
                elif 'categories' in scores and isinstance(scores['categories'], list):
                    total_events = 0
                    for category in scores['categories']:
                        if 'matches' in category:
                            matches = category['matches']
                            if 'match' in matches:
                                if isinstance(matches['match'], list):
                                    total_events += len(matches['match'])
                                else:
                                    total_events += 1
                            else:
                                # Some sports have matches directly in category
                                total_events += 1
                    return total_events
            
            return 0
            
        except Exception as e:
            logger.error(f"Error counting events in {json_file}: {e}")
            return 0

    def _get_sport_event_count(self, sport_name: str, config: Dict) -> int:
        """Get event count for a specific sport (only active matches)"""
        try:
            data = self._make_request(config['endpoint'], use_cache=True)
            if not data:
                return 0
            
            # Extract matches from the data using correct structure
            matches = self._extract_matches_from_goalserve_data(data)
            
            # Parse matches and count only active (non-completed, non-cancelled) ones
            active_count = 0
            for match in matches:
                try:
                    event = self._parse_single_event(match, sport_name, config)
                    if event and not event.get('is_completed', False) and not event.get('is_cancelled', False):
                        active_count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse match for count: {e}")
                    continue
            
            return active_count
            
        except Exception as e:
            logger.error(f"Error getting event count for {sport_name}: {e}")
            return 0

    def _extract_matches_from_goalserve_data(self, data: Dict) -> List[Dict]:
        """Extract matches from GoalServe API response data using correct structure"""
        matches = []
        
        try:
            if not isinstance(data, dict):
                return matches
            
            logger.info(f"Extracting matches from GoalServe data with keys: {list(data.keys())}")
            
            # GoalServe structure: { "scores": { "category": [...] } }
            if 'scores' in data and isinstance(data['scores'], dict):
                scores = data['scores']
                
                if 'category' in scores:
                    categories = scores['category']
                    
                    # Handle both single category (dict) and multiple categories (list)
                    if isinstance(categories, dict):
                        categories = [categories]
                    
                    if isinstance(categories, list):
                        logger.info(f"Found {len(categories)} categories")
                        
                        for category in categories:
                            if isinstance(category, dict):
                                category_name = category.get('@name', 'Unknown League')
                                
                                # Handle different sports data structures
                                # Soccer: category -> matches -> match
                                # Basketball/Tennis: category -> match (direct)
                                if 'matches' in category:
                                    # Soccer structure
                                    matches_container = category['matches']
                                    if isinstance(matches_container, dict) and 'match' in matches_container:
                                        category_matches = matches_container['match']
                                        self._process_matches(category_matches, category_name, matches)
                                elif 'match' in category:
                                    # Basketball/Tennis structure
                                    category_matches = category['match']
                                    self._process_matches(category_matches, category_name, matches)
            
            logger.info(f"Total matches extracted: {len(matches)}")
            
        except Exception as e:
            logger.error(f"Error extracting matches: {e}")
        
        return matches

    def _process_matches(self, category_matches, category_name: str, matches: List[Dict]):
        """Helper method to process matches from a category"""
        if isinstance(category_matches, dict):
            # Single match
            category_matches['@category_name'] = category_name
            matches.append(category_matches)
        elif isinstance(category_matches, list):
            # Multiple matches
            for match in category_matches:
                match['@category_name'] = category_name
            matches.extend(category_matches)
        
        match_count = len(category_matches) if isinstance(category_matches, list) else 1
        logger.info(f"Category '{category_name}': {match_count} matches")

    def get_sport_events(self, sport_name: str, date_filter: str = 'all', limit: int = 50) -> List[Dict]:
        """Get sport events from JSON files"""
        logger.info(f"Getting events for {sport_name} from JSON file (limit: {limit})")
        
        # Check cache first
        cache_key = f"events_{sport_name}_{date_filter}_{limit}"
        cached_events = self._get_from_cache(cache_key)
        if cached_events is not None:
            logger.info(f"Cache hit for {sport_name} events")
            return cached_events
        
        # Get sport configuration
        config = self.sports_config.get(sport_name, {})
        if not config:
            logger.warning(f"No configuration found for sport: {sport_name}")
            return []
        
        try:
            # Load events from JSON file using the same path resolution logic
            from pathlib import Path
            
            # Try multiple possible paths for the Sports Pre Match folder
            possible_paths = [
                Path("Sports Pre Match"),  # Relative to current working directory
                Path("src/Sports Pre Match"),  # Relative to src directory
                Path(__file__).parent.parent / "Sports Pre Match",  # Relative to this file
                Path.cwd() / "Sports Pre Match"  # Relative to current working directory
            ]
            
            json_file = None
            for base_path in possible_paths:
                if base_path.exists():
                    json_file = base_path / sport_name / f"{sport_name}_odds.json"
                    if json_file.exists():
                        break
            
            if not json_file or not json_file.exists():
                logger.warning(f"JSON file not found for {sport_name} in any expected location")
                return []

            import json
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract events from the JSON data
            events = self._extract_events_from_json(data, sport_name, config, limit)
            
            # Cache the result for 2 minutes (faster than the 5-minute default)
            self._set_cache(cache_key, events, duration=120)
            
            logger.info(f"Loaded {len(events)} events for {sport_name} from JSON and cached")
            return events

        except Exception as e:
            logger.error(f"Error getting events for {sport_name}: {e}")
            return []
    
    def _extract_events_from_json(self, data: Dict, sport_name: str, config: Dict, limit: int) -> List[Dict]:
        """Extract events from JSON data"""
        events = []
        
        try:
            if 'odds_data' in data and 'scores' in data['odds_data']:
                scores = data['odds_data']['scores']
                
                # Handle cricket format (scores.category[])
                if 'category' in scores and isinstance(scores['category'], list):
                    for category in scores['category']:
                        if 'matches' in category:
                            matches = category['matches']
                            if 'match' in matches:
                                match_list = matches['match']
                                if isinstance(match_list, list):
                                    for match in match_list:
                                        if len(events) >= limit:
                                            break
                                        event = self._parse_single_event(match, sport_name, config)
                                        if event:
                                            events.append(event)
                                elif isinstance(match_list, dict):
                                    if len(events) >= limit:
                                        break
                                    event = self._parse_single_event(match_list, sport_name, config)
                                    if event:
                                        events.append(event)
                
                # Handle standard format (scores.categories.category[])
                elif 'categories' in scores and isinstance(scores['categories'], list):
                    for category in scores['categories']:
                        if 'matches' in category:
                            matches = category['matches']
                            if 'match' in matches:
                                match_list = matches['match']
                                if isinstance(match_list, list):
                                    for match in match_list:
                                        if len(events) >= limit:
                                            break
                                        event = self._parse_single_event(match, sport_name, config)
                                        if event:
                                            events.append(event)
                                elif isinstance(match_list, dict):
                                    if len(events) >= limit:
                                        break
                                    event = self._parse_single_event(match_list, sport_name, config)
                                    if event:
                                        events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"Error extracting events from JSON: {e}")
            return []
    
    def _merge_odds_data(self, event: Dict, odds_match: Dict) -> Dict:
        """Merge odds data from odds feed into event data"""
        try:
            if 'odds' in odds_match:
                odds_data = odds_match['odds']
                if isinstance(odds_data, dict):
                    # Extract odds from the complex GoalServe structure
                    odds_1 = None
                    odds_x = None
                    odds_2 = None
                    
                    # Look for match winner odds in the type array (using exact logic from working script)
                    if 'type' in odds_data:
                        types = odds_data['type']
                        if isinstance(types, list):
                            for type_data in types:
                                if isinstance(type_data, dict):
                                    market_name = type_data.get('value', '')
                                    bookmakers = type_data.get('bookmaker', [])
                                    
                                    if isinstance(bookmakers, list):
                                        # Look for bet365 specifically (exact logic from working script)
                                        for bookmaker in bookmakers:
                                            bookie_name = bookmaker.get('name', '').lower()
                                            if bookie_name == 'bet365':
                                                odds_list = bookmaker.get('odd', [])
                                                if isinstance(odds_list, list):
                                                    for odd in odds_list:
                                                        name = odd.get('name', '')
                                                        value = odd.get('value', '')
                                                        # Only extract Home/Away odds for match winner
                                                        if market_name == 'Home/Away':
                                                            if name == 'Home':
                                                                odds_1 = float(value) if value else None
                                                            elif name == 'Away':
                                                                odds_2 = float(value) if value else None
                                                        elif market_name == '1X2':
                                                            if name == '1':
                                                                odds_1 = float(value) if value else None
                                                            elif name == 'X':
                                                                odds_x = float(value) if value else None
                                                            elif name == '2':
                                                                odds_2 = float(value) if value else None
                                                break  # Found bet365, stop looking
                    
                    # Update event with real odds
                    if odds_1 or odds_2 or odds_x:
                        event['odds_1'] = odds_1
                        event['odds_x'] = odds_x
                        event['odds_2'] = odds_2
                        logger.debug(f"Merged real odds for {event.get('home_team', '')} vs {event.get('away_team', '')}: 1={odds_1}, X={odds_x}, 2={odds_2}")
            
            return event
            
        except Exception as e:
            logger.error(f"Error merging odds data: {e}")
            return event

    def _parse_single_event(self, match: Dict, sport_name: str, config: Dict) -> Optional[Dict]:
        """Parse a single event from match data using GoalServe format"""
        try:
            # Extract team/player names based on sport structure
            home_team = 'Unknown Home'
            away_team = 'Unknown Away'
            
            if sport_name == 'tennis':
                # Tennis structure: player array with @name attributes (exact logic from working script)
                players = match.get('player', [])
                if not isinstance(players, list) or len(players) != 2:
                    logger.debug(f"Skipping match with {len(players) if isinstance(players, list) else 'non-list'} players")
                    return None
                
                home_team = players[0].get('@name', 'Unknown Home')  # Use '@name' as per tennis structure
                away_team = players[1].get('@name', 'Unknown Away')  # Use '@name' as per tennis structure
            else:
                # Soccer/Basketball structure: localteam/awayteam or localteam/visitorteam
                # Try both @name and name attributes for different sports
                home_team = (match.get('localteam', {}).get('@name') or 
                           match.get('localteam', {}).get('name', 'Unknown Home'))
                away_team = (match.get('awayteam', {}).get('@name') or 
                           match.get('awayteam', {}).get('name', 'Unknown Away'))
                
                # Fallback for soccer structure (visitorteam)
                if away_team == 'Unknown Away':
                    away_team = (match.get('visitorteam', {}).get('@name') or 
                               match.get('visitorteam', {}).get('name', 'Unknown Away'))
            
            if not home_team or not away_team or home_team == 'Unknown Home' or away_team == 'Unknown Away':
                logger.warning(f"Could not extract team names from match")
                return None

            # Extract time and status using @ attributes
            time_str = match.get('@time', '') or match.get('@status', '') or 'TBD'
            date_str = match.get('@date', '') or match.get('@formatted_date', '') or datetime.now().strftime('%b %d')
            status = match.get('@status', time_str)
            
            # Detect if match is live based on status (filter for "Not Started" like working script)
            is_live = False
            is_completed = False
            is_cancelled = False
            
            # Only process "Not Started" matches (like working script)
            if status != "Not Started":
                logger.debug(f"Skipping match with status: {status}")
                return None
            
            if status and status.isdigit():
                status_code = int(status)
                # Status codes like "22", "63" indicate live matches (minute of the game)
                is_live = status_code > 0 and status_code <= 90
                # Status codes like "90" might indicate completed matches (end of regulation)
                is_completed = status_code > 90
            elif status and 'timer' in match:
                # If there's a timer, it's likely live
                is_live = bool(match.get('@timer', ''))
            elif status == "FT":
                # Full Time indicates completed matches
                is_completed = True
            elif status == "90":
                # Minute 90 could be live or completed - check if there's a timer
                if match.get('@timer', ''):
                    is_live = True
                else:
                    is_completed = True
            elif status == "HT":
                # Half Time indicates live match
                is_live = True
            elif status in ["Cancl.", "Postp.", "WO"]:
                # Cancelled, Postponed, or Walk Over matches
                is_cancelled = True
            elif ":" in status:
                # Time format like "14:30" indicates scheduled match (not live, not completed)
                is_live = False
                is_completed = False
            
            # Extract scores based on sport
            home_score = '?'
            away_score = '?'
            
            if sport_name == 'tennis':
                # Tennis: extract scores from player arrays
                players = match.get('player', [])
                if isinstance(players, list) and len(players) >= 2:
                    home_score = players[0].get('@totalscore', '?')
                    away_score = players[1].get('@totalscore', '?')
            else:
                # Soccer/Basketball: extract from team objects
                # Try both @goals/@totalscore and goals/totalscore for different sports
                home_score = (match.get('localteam', {}).get('@goals') or 
                            match.get('localteam', {}).get('@totalscore') or
                            match.get('localteam', {}).get('goals') or
                            match.get('localteam', {}).get('totalscore', '?'))
                away_score = (match.get('awayteam', {}).get('@goals') or 
                            match.get('awayteam', {}).get('@totalscore') or
                            match.get('awayteam', {}).get('goals') or
                            match.get('awayteam', {}).get('totalscore', '?'))
                
                # Fallback for soccer structure (visitorteam)
                if away_score == '?':
                    away_score = (match.get('visitorteam', {}).get('@goals') or 
                                match.get('visitorteam', {}).get('@totalscore') or
                                match.get('visitorteam', {}).get('goals') or
                                match.get('visitorteam', {}).get('totalscore', '?'))
            
            # Extract venue
            venue = match.get('@venue', '')
            
            # Extract match ID
            match_id = match.get('@id', f"{sport_name}_{hash(f'{home_team}_{away_team}_{time_str}')}")
            
            # Generate realistic odds based on sport
            odds = self._generate_odds_for_sport(sport_name, config)
            
            # Extract league from category context
            league = match.get('@category_name', '') or match.get('category', {}).get('@name', '') or "Unknown League"

            # Extract odds if available
            odds_1 = None
            odds_x = None
            odds_2 = None
            
            # Look for odds in the match data (now using real GoalServe odds)
            if 'odds' in match:
                odds_data = match['odds']
                if isinstance(odds_data, dict):
                    # Extract odds from the complex GoalServe structure
                    odds_1 = None
                    odds_x = None
                    odds_2 = None
                    
                    # Look for match winner odds in the type array
                    if 'type' in odds_data:
                        types = odds_data['type']
                        if isinstance(types, list):
                            for type_data in types:
                                if isinstance(type_data, dict):
                                    # Look for "Home/Away" or "1X2" type odds
                                    value = type_data.get('value', '')
                                    if 'Home/Away' in value or '1X2' in value:
                                        if 'bookmaker' in type_data:
                                            bookmakers = type_data['bookmaker']
                                            if isinstance(bookmakers, list) and bookmakers:
                                                # Use the first bookmaker's odds
                                                first_bookmaker = bookmakers[0]
                                                if 'odd' in first_bookmaker:
                                                    odds_list = first_bookmaker['odd']
                                                    if isinstance(odds_list, list):
                                                        for odd in odds_list:
                                                            name = odd.get('name', '')
                                                            value = odd.get('value', '')
                                                            if name == 'Home' or name == '1':
                                                                odds_1 = float(value) if value else None
                                                            elif name == 'Away' or name == '2':
                                                                odds_2 = float(value) if value else None
                                                            elif name == 'X' or name == 'Draw':
                                                                odds_x = float(value) if value else None
                    
                    # If we found odds, use them
                    if odds_1 or odds_2 or odds_x:
                        logger.debug(f"Found real odds for {match.get('@home', '')} vs {match.get('@away', '')}: 1={odds_1}, X={odds_x}, 2={odds_2}")
            
            # For now, since soccer odds endpoint is not working, we'll set these to None
            # This can be updated when soccer odds become available
            
            # Create event object
            event = {
                'id': match.get('@id', ''),
                'home_team': home_team,
                'away_team': away_team,
                'time': time_str,
                'date': date_str,
                'status': status,
                'home_score': home_score,
                'away_score': away_score,
                'venue': match.get('@venue', ''),
                'league': match.get('@category_name', ''),
                'is_live': is_live,
                'is_completed': is_completed,
                'is_cancelled': is_cancelled,
                'odds_1': odds_1,
                'odds_x': odds_x,
                'odds_2': odds_2,
                'sport': sport_name
            }
            
            logger.info(f"Successfully parsed event: {home_team} vs {away_team} at {time_str}")
            
            return event
            
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None

    def _generate_odds_for_sport(self, sport_name: str, config: Dict) -> Dict:
        """Return actual odds from GoalServe API, or empty if none available"""
        # Only return actual odds from GoalServe, no random generation
        return {}

    def get_prematch_odds(self, sport_name: str) -> Dict:
        """Load pre-match odds from JSON files"""
        try:
            # Load odds from JSON file using the same path resolution logic
            from pathlib import Path
            
            # Try multiple possible paths for the Sports Pre Match folder
            possible_paths = [
                Path("Sports Pre Match"),  # Relative to current working directory
                Path("src/Sports Pre Match"),  # Relative to src directory
                Path(__file__).parent.parent / "Sports Pre Match",  # Relative to this file
                Path.cwd() / "Sports Pre Match"  # Relative to current working directory
            ]
            
            json_file = None
            for base_path in possible_paths:
                if base_path.exists():
                    json_file = base_path / sport_name / f"{sport_name}_odds.json"
                    if json_file.exists():
                        break
            
            if not json_file or not json_file.exists():
                logger.warning(f"JSON file not found for {sport_name} in any expected location")
                return {}

            import json
            with open(json_file, 'r', encoding='utf-8') as f:
                odds_data = json.load(f)
            
            logger.info(f"Successfully loaded odds for {sport_name} from JSON")
            return odds_data
            
        except Exception as e:
            logger.error(f"Error loading odds for {sport_name}: {e}")
            return {}

    def get_live_odds(self, sport_name: str) -> List[Dict]:
        """Get live odds for a specific sport using GoalServe's inplay-mapping endpoint"""
        logger.info(f"Fetching live odds for {sport_name}")
        
        if sport_name not in self.sports_config:
            logger.warning(f"Unknown sport: {sport_name}")
            return []
        
        config = self.sports_config[sport_name]
        
        # Map sport names to GoalServe inplay-mapping endpoints
        inplay_endpoints = {
            'soccer': 'soccernew/inplay-mapping',
            'basketball': 'basketball/inplay-mapping', 
            'tennis': 'tennis_scores/inplay-mapping',
            'baseball': 'baseball/inplay-mapping',
            'hockey': 'hockey/inplay-mapping'
        }
        
        endpoint = inplay_endpoints.get(sport_name)
        if not endpoint:
            logger.warning(f"No inplay-mapping endpoint found for {sport_name}")
            return []
        
        try:
            # Fetch inplay-mapping data
            mapping_data = self._make_request(endpoint, use_cache=False)  # Don't cache live data
            
            if not mapping_data:
                logger.warning(f"No inplay-mapping data received for {sport_name}")
                return []
            
            # Get current live matches from the regular feed
            live_matches = self._get_live_matches_from_regular_feed(sport_name)
            
            # Combine mapping data with live match data to create live odds
            live_odds = self._create_live_odds_from_mapping(mapping_data, live_matches, sport_name, config)
            
            logger.info(f"Successfully fetched live odds for {len(live_odds)} matches")
            return live_odds
            
        except Exception as e:
            logger.error(f"Error fetching live odds for {sport_name}: {e}")
            return []

    def _get_live_matches_from_regular_feed(self, sport_name: str) -> List[Dict]:
        """Get live matches from the regular GoalServe feed"""
        try:
            config = self.sports_config[sport_name]
            data = self._make_request(config['endpoint'], use_cache=False)
            
            if not data:
                return []
            
            matches = self._extract_matches_from_goalserve_data(data)
            live_matches = []
            
            for match in matches:
                status = match.get('@status', '')
                if self._is_match_live(status, match):
                    live_matches.append(match)
            
            return live_matches
            
        except Exception as e:
            logger.error(f"Error getting live matches: {e}")
            return []

    def _create_live_odds_from_mapping(self, mapping_data: Dict, live_matches: List[Dict], sport_name: str, config: Dict) -> List[Dict]:
        """Create live odds by combining mapping data with live match data"""
        live_odds = []
        
        try:
            # Extract mapping information
            mappings = mapping_data.get('mappings', {}).get('match', [])
            if not isinstance(mappings, list):
                mappings = [mappings] if mappings else []
            
            # Create a lookup for live matches
            live_matches_lookup = {}
            for match in live_matches:
                match_id = match.get('@id', '')
                home_team = match.get('localteam', {}).get('@name', '')
                away_team = match.get('visitorteam', {}).get('@name', '')
                key = f"{home_team}_{away_team}"
                live_matches_lookup[key] = match
            
            # First, try to match mappings with live matches
            matched_mappings = set()
            for mapping in mappings:
                try:
                    inplay_team1 = mapping.get('@inplay_team1_id', '')
                    inplay_team2 = mapping.get('@inplay_team2_id', '')
                    
                    # Find corresponding live match with improved matching
                    live_match = None
                    for key, match in live_matches_lookup.items():
                        home_team = match.get('localteam', {}).get('@name', '')
                        away_team = match.get('visitorteam', {}).get('@name', '')
                        
                        # Try multiple matching strategies
                        match_found = False
                        
                        # Strategy 1: Exact match
                        if (inplay_team1.lower() == home_team.lower() and 
                            inplay_team2.lower() == away_team.lower()):
                            match_found = True
                        
                        # Strategy 2: Partial match (one team name contains the other)
                        elif (inplay_team1.lower() in home_team.lower() or 
                              home_team.lower() in inplay_team1.lower() or
                              inplay_team2.lower() in away_team.lower() or
                              away_team.lower() in inplay_team2.lower()):
                            match_found = True
                        
                        # Strategy 3: Word-based matching (for cases like "Congo" vs "Congo Republic")
                        elif (any(word in home_team.lower() for word in inplay_team1.lower().split()) or
                              any(word in away_team.lower() for word in inplay_team2.lower().split())):
                            match_found = True
                        
                        if match_found:
                            live_match = match
                            break
                    
                    if live_match:
                        # Generate live odds for this match
                        live_odds_data = self._generate_dynamic_live_odds(live_match, sport_name)
                        
                        live_odds.append({
                            'match_id': live_match.get('@id', ''),
                            'pregame_match_id': mapping.get('@pregame_match_id', ''),
                            'inplay_match_id': mapping.get('@inplay_match_id', ''),
                            'home_team': live_match.get('localteam', {}).get('@name', ''),
                            'away_team': live_match.get('visitorteam', {}).get('@name', ''),
                            'home_score': live_match.get('localteam', {}).get('@goals', '0'),
                            'away_score': live_match.get('visitorteam', {}).get('@goals', '0'),
                            'status': live_match.get('@status', ''),
                            'time': live_match.get('@time', ''),
                            'venue': live_match.get('@venue', ''),
                            'league': live_match.get('@category_name', ''),
                            'live_odds': live_odds_data,
                            'sport': sport_name,
                            'team1_kit_color': mapping.get('team1_kit_color', {}).get('@value', ''),
                            'team2_kit_color': mapping.get('team2_kit_color', {}).get('@value', '')
                        })
                        matched_mappings.add(live_match.get('@id', ''))
                        
                except Exception as e:
                    logger.warning(f"Failed to process mapping: {e}")
                    continue
            
            # Now generate live odds for ALL live matches that weren't matched
            for match in live_matches:
                match_id = match.get('@id', '')
                if match_id not in matched_mappings:
                    # Generate live odds for this match
                    live_odds_data = self._generate_dynamic_live_odds(match, sport_name)
                    
                    live_odds.append({
                        'match_id': match.get('@id', ''),
                        'pregame_match_id': '',
                        'inplay_match_id': '',
                        'home_team': match.get('localteam', {}).get('@name', ''),
                        'away_team': match.get('visitorteam', {}).get('@name', ''),
                        'home_score': match.get('localteam', {}).get('@goals', '0'),
                        'away_score': match.get('visitorteam', {}).get('@goals', '0'),
                        'status': match.get('@status', ''),
                        'time': match.get('@time', ''),
                        'venue': match.get('@venue', ''),
                        'league': match.get('@category_name', ''),
                        'live_odds': live_odds_data,
                        'sport': sport_name,
                        'team1_kit_color': '',
                        'team2_kit_color': ''
                    })
            
            logger.info(f"Created live odds for {len(live_odds)} matches")
            
        except Exception as e:
            logger.error(f"Error creating live odds from mapping: {e}")
        
        return live_odds

    def _generate_dynamic_live_odds(self, match: Dict, sport_name: str) -> Dict:
        """Fetch actual live odds from GoalServe inplay endpoint"""
        try:
            # Get the inplay match ID from the match data
            inplay_match_id = match.get('@id', '')
            if not inplay_match_id:
                return {}
            
            # Fetch live odds from the inplay endpoint
            inplay_data = self._make_request(f'soccernew/inplay/{inplay_match_id}', use_cache=False)
            if not inplay_data or 'scores' not in inplay_data:
                return {}
            
            # Extract odds from the inplay data
            match_data = inplay_data['scores'].get('match', {})
            if not match_data:
                return {}
            
            # Look for odds in the match data
            odds = self._extract_live_odds_from_match(match_data, sport_name)
            return odds
            
        except Exception as e:
            logger.warning(f"Failed to fetch live odds for match {match.get('@id', '')}: {e}")
            return {}

    def _is_match_live(self, status: str, match: Dict) -> bool:
        """Check if a match is currently live based on status and timer"""
        if not status:
            return False
        
        # Check for live status indicators
        if status.isdigit():
            status_code = int(status)
            return status_code > 0 and status_code <= 90
        elif status in ["HT", "1H", "2H"]:
            return True
        elif status == "90" and match.get('@timer', ''):
            return True
        elif ":" in status and not status.startswith("FT"):
            # Time format like "14:30" - check if it's current time
            return False  # Scheduled match, not live
        
        return False

    def _extract_live_odds_from_match(self, match: Dict, sport_name: str) -> Dict:
        """Extract live odds from match data"""
        live_odds = {}
        
        try:
            # Look for odds data in the match structure
            # GoalServe might include odds in different formats
            odds_sources = [
                match.get('odds', {}),
                match.get('betting', {}),
                match.get('markets', {}),
                match.get('live_odds', {})
            ]
            
            for odds_source in odds_sources:
                if isinstance(odds_source, dict) and odds_source:
                    # Extract different types of odds
                    live_odds.update(self._parse_odds_markets(odds_source, sport_name))
            
            # Only return actual odds from GoalServe, no random generation
            return live_odds
            
        except Exception as e:
            logger.warning(f"Error extracting live odds: {e}")
            return {}

    def _parse_odds_markets(self, odds_data: Dict, sport_name: str) -> Dict:
        """Parse different types of odds markets from GoalServe data"""
        markets = {}
        
        try:
            # Common odds market types
            market_types = {
                '1x2': ['1', 'x', '2'],
                'match_winner': ['home', 'draw', 'away'],
                'total_goals': ['over', 'under'],
                'both_teams_score': ['yes', 'no'],
                'double_chance': ['1x', '12', 'x2']
            }
            
            for market_type, selections in market_types.items():
                if market_type in odds_data:
                    market_odds = odds_data[market_type]
                    if isinstance(market_odds, dict):
                        markets[market_type] = market_odds
                    elif isinstance(market_odds, list):
                        markets[market_type] = dict(zip(selections, market_odds))
            
        except Exception as e:
            logger.warning(f"Error parsing odds markets: {e}")
        
        return markets

    def _generate_live_odds_based_on_score(self, match: Dict, sport_name: str) -> Dict:
        """Return actual odds from GoalServe API, or empty if none available"""
        # Only return actual odds from GoalServe, no random generation
        return {}

    def clear_cache(self):
        """Clear all cached data"""
        with self.cache_lock:
            self.cache.clear()
            logger.info("Cache cleared")
    


    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        with self.cache_lock:
            total_entries = len(self.cache)
            valid_entries = sum(1 for entry in self.cache.values() if self._is_cache_valid(entry))
            
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'cache_duration': self.cache_duration
        }

