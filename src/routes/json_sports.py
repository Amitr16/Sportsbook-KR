"""
JSON-based Sports API Routes - Uses pre-match JSON files as single source of truth
"""

import json
import os
import re
from src import sqlite3_shim as sqlite3
from pathlib import Path
from flask import Blueprint, jsonify, request
import logging
from typing import List, Dict, Any

# Market type aliases for proper prioritization
THREE_WAY_ALIASES = {
    "3way result", "3-way result", "3 way result", "3Way Result",
    "match result", "full time result", "regular time result",
    "match winner", "1x2", "1 x 2"
}
TWO_WAY_ALIASES = {
    "home/away", "home away", "moneyline", "winner", "2way result", "2-way result", "2 way result"
}

def _norm(s: str) -> str:
    """Normalize market name for comparison"""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def _has_draw(outcomes: List[Dict[str, Any]]) -> bool:
    """Check if outcomes include a draw/tie option"""
    labels = {_norm(o.get("name") or o.get("label") or o.get("outcome") or "") for o in outcomes}
    return any(lbl in {"x", "draw", "tie"} or "draw" in lbl or "tie" in lbl for lbl in labels)

def extract_cricket_specific_markets(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the 4 specific cricket markets using the EXACT logic from your working Python script:
    - Match Result (Home/Away) - Market ID: "2" 
    - Most Run outs - Market ID: "23511"
    - Most Sixes - Market ID: "23512" 
    - Most Fours - Market ID: "23513"
    """
    cricket_markets = {}
    
    # Markets we care about - EXACTLY as in your working script
    TARGETS_BY_ID = {
        "2": "Home/Away",       # Match Result (2-way)
        "23512": "Most Sixes",
        "23513": "Most Fours",
        "23511": "Most Run Outs",
    }
    TARGETS_BY_VALUE = set(TARGETS_BY_ID.values())
    
    # Helper: get bet365 bookmaker - EXACTLY as in your working script
    def get_bet365(bookmaker_field):
        if isinstance(bookmaker_field, dict):
            return bookmaker_field if str(bookmaker_field.get("id")) == "16" else None
        if isinstance(bookmaker_field, list):
            for bm in bookmaker_field:
                if str(bm.get("id")) == "16":
                    return bm
        return None
    
    # Check if this is cricket format (has 'odds' with 'type' array)
    if 'odds' in match_data and isinstance(match_data['odds'], dict) and 'type' in match_data['odds']:
        odds = match_data['odds']
        types = odds.get('type', [])
        if isinstance(types, dict):
            types = [types]
        
        for odd_type in types:
            tid = str(odd_type.get("id"))
            tval = odd_type.get("value")
            
            # Check if this is one of our target markets - EXACTLY as in your working script
            if (tid in TARGETS_BY_ID) or (tval in TARGETS_BY_VALUE):
                bm = get_bet365(odd_type.get("bookmaker"))
                if not bm:
                    continue
                    
                market = TARGETS_BY_ID.get(tid) or tval
                market_key = market.lower().replace(' ', '_').replace('/', '_')  # Convert to key format
                
                # Use the EXACT sel_map logic from your working script
                sel_map = {}
                if "odd" in bm:
                    for o in bm["odd"]:
                        name = str(o.get("name")).lower()
                        if name == "home":
                            sel_map["home_odds"] = o.get("value")
                        elif name == "away":
                            sel_map["away_odds"] = o.get("value")
                        elif name == "draw":
                            sel_map["draw_odds"] = o.get("value")
                        else:
                            sel_map[f"{name}_odds"] = o.get("value")
                
                # Convert sel_map to odds array format that frontend expects
                odds_values = []
                if "home_odds" in sel_map:
                    odds_values.append(sel_map["home_odds"])
                if "away_odds" in sel_map:
                    odds_values.append(sel_map["away_odds"])
                if "draw_odds" in sel_map:
                    odds_values.append(sel_map["draw_odds"])
                
                # Store the market data with simple odds array (frontend expects this)
                cricket_markets[market_key] = {
                    "market_id": tid,
                    "market_name": tval,
                    "odds": odds_values
                }
    
    return cricket_markets

logger = logging.getLogger(__name__)

json_sports_bp = Blueprint('json_sports', __name__)

# Base path to the Sports Pre Match folder
BASE_SPORTS_PATH = Path(__file__).parent.parent.parent / "Sports Pre Match"

# Sports configuration
SPORTS_CONFIG = {
    'soccer': {'display_name': 'Soccer', 'icon': '⚽', 'has_draw': True},
    'basketball': {'display_name': 'Basketball', 'icon': '🏀', 'has_draw': True},
    'tennis': {'display_name': 'Tennis', 'icon': '🎾', 'has_draw': False},
    'hockey': {'display_name': 'Hockey', 'icon': '🏒', 'has_draw': False},
    'handball': {'display_name': 'Handball', 'icon': '🤾', 'has_draw': True},
    'volleyball': {'display_name': 'Volleyball', 'icon': '🏐', 'has_draw': False},
    'football': {'display_name': 'American Football', 'icon': '🏈', 'has_draw': False},
    'baseball': {'display_name': 'Baseball', 'icon': '⚾', 'has_draw': False},
    'cricket': {'display_name': 'Cricket', 'icon': '🏏', 'has_draw': True},
    'rugby': {'display_name': 'Rugby', 'icon': '🏉', 'has_draw': True},
    'rugbyleague': {'display_name': 'Rugby League', 'icon': '🏉', 'has_draw': True},
    'table_tennis': {'display_name': 'Table Tennis', 'icon': '🏓', 'has_draw': False},
    'boxing': {'display_name': 'Boxing', 'icon': '🥊', 'has_draw': False},
    'mma': {'display_name': 'MMA', 'icon': '🥋', 'has_draw': False},
    'darts': {'display_name': 'Darts', 'icon': '🎯', 'has_draw': False},
    'esports': {'display_name': 'Esports', 'icon': '🎮', 'has_draw': False},
    'futsal': {'display_name': 'Futsal', 'icon': '⚽', 'has_draw': True},
    'golf': {'display_name': 'Golf', 'icon': '⛳', 'has_draw': False}
}

def load_sport_json(sport_name):
    """Load JSON data for a specific sport"""
    try:
        json_file = BASE_SPORTS_PATH / sport_name / f"{sport_name}_odds.json"
        
        if not json_file.exists():
            logger.warning(f"JSON file not found for {sport_name}: {json_file}")
            return None
            
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"Successfully loaded JSON for {sport_name}")
        return data
        
    except Exception as e:
        logger.error(f"Error loading JSON for {sport_name}: {e}")
        return None

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim"""
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    return conn

def filter_disabled_events(events, sport_name):
    """Filter out disabled events from the events list"""
    try:
        # Don't let this endpoint starve auth/tenant: 2s max
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=2) as conn:
            # Set very short statement timeout for this endpoint
            with conn.cursor() as c:
                c.execute("SET LOCAL statement_timeout = '1500ms'")
            
            # Get all disabled event keys from the event_key column
            # Handle both boolean and integer types for is_disabled
            try:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT event_key FROM disabled_events WHERE is_disabled = true')
                    disabled_events = cursor.fetchall()
            except Exception as bool_error:
                try:
                    # Fallback to integer comparison
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT event_key FROM disabled_events WHERE is_disabled = 1')
                        disabled_events = cursor.fetchall()
                except Exception as int_error:
                    print(f"🔍 Warning: Could not query disabled_events table: {bool_error}, {int_error}")
                    disabled_events = []
            
            disabled_keys = set(row['event_key'] for row in disabled_events)
        
        print(f"🔍 Filtering {len(events)} events for sport: {sport_name}")
        print(f"🔍 Disabled keys: {disabled_keys}")
        
        if not disabled_keys:
            print(f"🔍 No disabled events found, returning all {len(events)} events")
            return events  # No disabled events, return all
        
        # Filter events
        filtered_events = []
        for event in events:
            event_id = event.get('id', '')
            print(f"🔍 Checking event {event_id}")
            
            # Check all possible market combinations for this event
            if 'odds' in event:
                original_markets = list(event['odds'].keys())
                print(f"🔍 Event {event_id} has markets: {original_markets}")
                
                # Check for disabled market IDs
                markets_to_remove = []
                for market_key in list(event['odds'].keys()):
                    # Skip market_id keys themselves
                    if market_key.endswith('_market_id'):
                        continue
                        
                    # Check if this market has a market_id stored
                    market_id_key = f"{market_key}_market_id"
                    if market_id_key in event['odds']:
                        market_id = event['odds'][market_id_key]
                        event_key = f"{event_id}_{market_id}"
                        if event_key in disabled_keys:
                            print(f"🔍 Removing disabled market: {event_key} (market: {market_key})")
                            markets_to_remove.append(market_key)
                            markets_to_remove.append(market_id_key)  # Also remove the market_id key
                
                # Remove the disabled markets
                for market_key in markets_to_remove:
                    event['odds'].pop(market_key, None)
                
                remaining_markets = list(event['odds'].keys())
                print(f"🔍 Event {event_id} remaining markets: {remaining_markets}")
                
                # Only include event if it still has odds after filtering
                if remaining_markets and not all(key.endswith('_market_id') for key in remaining_markets):
                    filtered_events.append(event)
                    print(f"🔍 Event {event_id} included with markets: {remaining_markets}")
                else:
                    print(f"🔍 Event {event_id} excluded - no valid markets remaining")
            else:
                # Event has no odds, include it anyway
                filtered_events.append(event)
                print(f"🔍 Event {event_id} included (no odds)")
        
        print(f"🔍 Filtered {len(events)} events down to {len(filtered_events)} events")
        return filtered_events
        
    except Exception as e:
        print(f"🔍 Error filtering disabled events: {e}")
        return events  # Return all events if filtering fails

def load_json_file(json_file):
    """Load JSON file with size-based optimizations"""
    try:
        # Check file size first
        file_size = os.path.getsize(json_file)
        
        # For extremely large files, return sample data to prevent crashes
        if file_size > 100 * 1024 * 1024:  # 100MB
            logger.warning(f"⚠️ File extremely large ({file_size / (1024*1024):.1f}MB) - returning sample data")
            return {
                'metadata': {'sport': 'unknown'},
                'odds_data': {
                    'scores': {
                        'sport': 'unknown',
                        'categories': []  # Empty to prevent processing
                    }
                },
                '_file_too_large': True,
                '_total_matches': 9999
            }
        
        # For moderately large files, try to load with limits
        logger.info(f"Attempting to load moderately large file: {file_size / (1024*1024):.1f}MB")
        
        # Read file in chunks to check structure
        with open(json_file, 'r', encoding='utf-8') as f:
            # Read first 10KB to check structure
            header = f.read(10 * 1024)
            if '"categories"' in header and '"matches"' in header:
                # File has the right structure, but limit processing
                f.seek(0)
                data = json.load(f)
                
                # If it has too many categories, truncate it
                if 'odds_data' in data and 'scores' in data['odds_data']:
                    scores = data['odds_data']['scores']
                    if 'categories' in scores and len(scores['categories']) > 20:
                        logger.warning(f"⚠️ Too many categories ({len(scores['categories'])}) - truncating to first 20")
                        scores['categories'] = scores['categories'][:20]
                
                return data
            else:
                logger.error("File structure not recognized")
                return None
                
    except Exception as e:
        logger.error(f"Error loading large JSON file: {e}")
        return None

def extract_1x2_odds(odd_list):
    """Extract 1X2 odds from odd list"""
    odds = {}
    
    try:
        for odd in odd_list:
            if isinstance(odd, dict):
                name = odd.get('name', '').lower()
                value = odd.get('value', '')
                
                # Validate odds value
                try:
                    float_value = float(value)
                    if float_value <= 1.0:  # Invalid odds
                        continue
                except (ValueError, TypeError):
                    continue
                    
                # Map odds names to standard format
                if name in ['home', '1', 'home win']:
                    odds['1'] = value
                elif name in ['away', '2', 'away win']:
                    odds['2'] = value
                elif name in ['draw', 'x', 'tie']:
                    odds['X'] = value
                    
    except Exception as e:
        logger.error(f"Error extracting 1X2 odds: {e}")
        
    # Only return if we have at least home and away odds
    if '1' in odds and '2' in odds:
        return odds
    else:
        return {}

def extract_match_odds(match_data):
    """Extract 1X2 odds from match data"""
    if not isinstance(match_data, dict):
        return {}
    
    odds_data = {}
    
    # Look for odds in the match data
    if 'odds' in match_data:
        odds_list = match_data['odds']
        if not isinstance(odds_list, list):
            odds_list = [odds_list]
        
        for odds_market in odds_list:
            if isinstance(odds_market, dict):
                # Check if this is a main market (1X2, match result, etc.)
                market_value = odds_market.get('value', '').lower()
                if any(market in market_value for market in ['match winner', '1x2', 'full time result', 'match result', '3way result', 'home/away']):
                    # Extract bookmaker odds
                    if 'bookmakers' in odds_market:
                        bookmakers = odds_market['bookmakers']
                        if not isinstance(bookmakers, list):
                            bookmakers = [bookmakers]
                        
                        for bookmaker in bookmakers:
                            if isinstance(bookmaker, dict) and 'odds' in bookmaker:
                                odd_list = bookmaker['odds']
                                if not isinstance(odd_list, list):
                                    odd_list = [odd_list]
                                
                                # Extract 1X2 odds
                                extracted_odds = extract_1x2_odds(odd_list)
                                if extracted_odds:
                                    odds_data[market_value.replace(' ', '_')] = extracted_odds
                                    return odds_data  # Return first valid odds found
    
    return odds_data

def extract_odds_from_match(match, sport_name=''):
    """Extract all odds from a match including secondary markets"""
    try:
        # Extract team names - handle dictionary structure
        localteam = match.get('localteam', {})
        visitorteam = match.get('visitorteam', {})
        awayteam = match.get('awayteam', {})  # Basketball uses 'awayteam' instead of 'visitorteam'
        player_1 = match.get('player_1', {})
        player_2 = match.get('player_2', {})
        
        # Handle different formats
        if isinstance(localteam, dict):
            home_team = localteam.get('name', '')
        else:
            home_team = str(localteam) if localteam else ''
            
        # Try both visitorteam and awayteam - prioritize the one with actual data
        away_team = ''
        if isinstance(visitorteam, dict) and visitorteam.get('name'):
            away_team = visitorteam.get('name', '')
        elif isinstance(awayteam, dict) and awayteam.get('name'):
            away_team = awayteam.get('name', '')
        elif visitorteam and not isinstance(visitorteam, dict):
            away_team = str(visitorteam)
        elif awayteam and not isinstance(awayteam, dict):
            away_team = str(awayteam)
        
        # For tennis/table tennis/darts, use player_1 and player_2 if no team names found
        if not home_team and isinstance(player_1, dict):
            home_team = player_1.get('name', '')
        elif not home_team:
            home_team = str(player_1) if player_1 else ''
            
        if not away_team and isinstance(player_2, dict):
            away_team = player_2.get('name', '')
        elif not away_team:
            away_team = str(player_2) if player_2 else ''
        
        # Extract all odds from the match
        all_odds = {}
        
        if 'odds' in match:
            # Check if this is cricket format (has 'type' array)
            if isinstance(match['odds'], dict) and 'type' in match['odds']:
                # Cricket format: odds.type[].bookmaker[].odd[]
                logger.info(f"Processing cricket odds for match {match.get('id', 'unknown')}")
                logger.info(f"Cricket odds structure: {list(match['odds'].keys())}")
                
                # Extract the 4 specific cricket markets using our new function
                cricket_markets = extract_cricket_specific_markets(match)
                logger.info(f"Extracted cricket markets: {list(cricket_markets.keys())}")
                
                # Process each market
                for market_key, market_data in cricket_markets.items():
                    if market_data.get('odds'):
                        all_odds[market_key] = market_data['odds']
                        all_odds[f"{market_key}_market_id"] = market_data['market_id']
                        all_odds[f"{market_key}_market_name"] = market_data['market_name']
                        logger.info(f"✅ Added cricket market '{market_key}': {market_data['odds']} (ID: {market_data['market_id']})")
                    else:
                        logger.warning(f"⚠️ No valid odds found for cricket market: {market_key}")
                
                # Legacy support: also add match_result for backward compatibility
                if 'home_away' in cricket_markets:
                    all_odds['match_result'] = cricket_markets['home_away']['odds']
                    all_odds['match_result_market_id'] = cricket_markets['home_away']['market_id']
                    all_odds['home_away'] = cricket_markets['home_away']['odds']
                    all_odds['home_away_market_id'] = cricket_markets['home_away']['market_id']
                    logger.info(f"✅ Added home_away and legacy match_result for backward compatibility")
                
                logger.info(f"Final cricket odds extracted: {list(all_odds.keys())}")
            else:
                # Standard format: odds[].bookmakers[].odd[]
                # First pass: collect and prioritize markets properly
                chosen_3way = None
                chosen_3way_id = None
                chosen_2way = None
                chosen_2way_id = None
                other_odds = []
                
                for odd in match['odds']:
                    market_name = odd.get('value', '')  # Keep original case for logging
                    market_name_lower = market_name.lower()
                    market_id = odd.get('id', '')
                    
                    # Extract odds from bookmakers
                    if 'bookmakers' in odd and odd['bookmakers']:
                        bookmaker = odd['bookmakers'][0]
                        if 'odds' in bookmaker:
                            # Check if this is a 3-way market (has draw/tie)
                            extracted_odds = extract_1x2_odds(bookmaker['odds'])
                            if extracted_odds and len(extracted_odds) >= 2:
                                # Convert to list format for consistency
                                odds_values = []
                                if '1' in extracted_odds:
                                    odds_values.append(extracted_odds['1'])
                                if 'X' in extracted_odds:
                                    odds_values.append(extracted_odds['X'])
                                if '2' in extracted_odds:
                                    odds_values.append(extracted_odds['2'])
                                
                                if len(odds_values) >= 2:
                                    # Determine if this is 3-way (has draw) or 2-way (no draw)
                                    has_draw = 'X' in extracted_odds and extracted_odds['X'] != '0'
                                    is_3way = has_draw and len(odds_values) == 3
                                    
                                    # Special handling for baseball: prioritize Home/Away over 1st Inning markets
                                    if sport_name == 'baseball':
                                        if 'home/away' in market_name_lower and not is_3way:
                                            # For baseball, Home/Away is the primary market
                                            chosen_2way = odds_values
                                            chosen_2way_id = market_id
                                            logger.info(f"✅ Found baseball Home/Away odds: {odds_values} (ID: {market_id}, market: {market_name})")
                                        # Completely ignore 3-way markets for baseball - only use 2-way Home/Away
                                        else:
                                            logger.info(f"ℹ️ Skipping baseball market '{market_name}' (ID: {market_id}) - not Home/Away")
                                    else:
                                        # For other sports, use normal priority
                                        if is_3way and chosen_3way is None:
                                            # Prefer the FIRST valid 3-way market; never overwrite with 2-way later
                                            chosen_3way = odds_values
                                            chosen_3way_id = market_id
                                            logger.info(f"✅ Found 3-way Match Result odds: {odds_values} (ID: {market_id}, market: {market_name})")
                                            logger.info(f"Extracted odds structure: {extracted_odds}")
                                        elif not is_3way and chosen_2way is None and chosen_3way is None:
                                            # Only use 2-way if no 3-way market exists yet
                                            chosen_2way = odds_values
                                            chosen_2way_id = market_id
                                            logger.info(f"✅ Found 2-way Home/Away odds: {odds_values} (ID: {market_id}, market: {market_name})")
                                        else:
                                            logger.info(f"ℹ️ Skipping market '{market_name}' (ID: {market_id}) - already have {'3-way' if chosen_3way else '2-way'} market")
                            else:
                                # For non-match_result markets, use the old logic
                                odds_values = []
                                for o in bookmaker['odds']:
                                    value = o.get('value', '')
                                    try:
                                        float_val = float(value)
                                        if float_val > 1.0:  # Valid odds
                                            odds_values.append(value)
                                    except (ValueError, TypeError):
                                        continue
                                
                                if odds_values:
                                    # Map market names to frontend keys
                                    frontend_key = map_market_to_frontend(market_name_lower)
                                    logger.info(f"Standard market '{market_name}' (ID: {market_id}) mapped to '{frontend_key}' with {len(odds_values)} odds")
                                    
                                    if frontend_key and frontend_key != 'match_result':  # Don't overwrite match_result here
                                        all_odds[frontend_key] = odds_values
                                    
                                    # Store market ID mapping separately
                                    if market_id:
                                        all_odds[f"{frontend_key}_market_id"] = market_id
                                        logger.info(f"✅ Stored market ID for {frontend_key}: {market_id}")
                                    else:
                                        logger.warning(f"⚠️ No market ID found for {frontend_key}")
                
                # Now set the match_result based on priority (3-way > 2-way)
                if chosen_3way and sport_name != 'baseball':  # Never use 3-way for baseball
                    # Only set match_result for true 3-way markets (1,X,2)
                    all_odds['match_result'] = chosen_3way
                    all_odds['match_result_market_id'] = str(chosen_3way_id)
                    all_odds['has_draw'] = True
                    logger.info(f"✅ Using 3-way Match Result odds: {chosen_3way}")
                elif chosen_2way:
                    # For 2-way markets, publish as home_away only to avoid 1X2 UI confusion
                    all_odds['home_away'] = chosen_2way
                    all_odds['home_away_market_id'] = str(chosen_2way_id)
                    all_odds['has_draw'] = False
                    logger.info(f"✅ Using 2-way Home/Away odds: {chosen_2way}")
                    # Note: NOT setting match_result for 2-way to prevent UI confusion
                else:
                    logger.warning(f"⚠️ No suitable Match Result market found - will not show match_result odds")
                    logger.info(f"ℹ️ Available markets: {[odd.get('value', '') for odd in match['odds']]}")
                
                # Override has_draw for specific sports that don't have draws
                if sport_name in ['baseball', 'tennis', 'volleyball', 'football', 'table_tennis', 'boxing', 'mma', 'darts', 'esports']:
                    all_odds['has_draw'] = False
                    logger.info(f"✅ Override: {sport_name} has no draws, set has_draw = False")
        
        return all_odds
    except Exception as e:
        logger.error(f"Error extracting odds from match: {e}")
        return None

def map_market_to_frontend(market_name):
    """Map JSON market names to frontend market keys"""
    market_mapping = {
        # Soccer markets (37 markets available)
        'match winner': 'match_result',
        '3Way Result': 'match_result',  # Handle capital W version from Goalserve
        'home/away': 'home_away',  # Soccer can have both 3-way and 2-way, prioritize 3-way
        'match_result': 'match_result',  # Direct mapping
        'goals over/under': 'goals_over_under',
        
        # Cricket markets - Only Match Result
        'home/away': 'home_away',  # Cricket has no draw, so use home_away not match_result
        'to qualify': 'to_qualify',
        'results/both teams to score': 'results_both_teams_score',
        'result/total goals': 'result_total_goals',
        'home team score a goal': 'home_team_score_goal',
        'away team score a goal': 'away_team_score_goal',
        'corners 1x2': 'corners_1x2',
        'corners over under': 'corners_over_under',
        
        # Basketball markets (12 markets available)
        '3way result': 'match_result',
        '3Way Result': 'match_result',  # Handle capital W version from Goalserve
        'over/under': 'over_under',
        'asian handicap': 'asian_handicap',
        'over/under 1st half': 'over_under_first_half',
        'asian handicap first half': 'asian_handicap_first_half',
        'odd/even (including ot)': 'odd_even_including_ot',
        'over/under 1st qtr': 'over_under_first_quarter',
        'asian handicap 1st qtr': 'asian_handicap_first_quarter',
        'home/away - 1st half': 'first_half_winner',
        'home/away - 1st qtr': 'first_quarter_winner',
        'highest scoring quarter': 'highest_scoring_quarter',
        
        # Tennis markets (12 markets available)
        'home/away': 'home_away',  # Tennis has no draw, so use home_away not match_result
        'correct score 1st half': 'correct_score_first_half',
        'over/under by games in match': 'games_over_under',
        'over/under (1st set)': 'over_under_first_set',
        'home/away (1st set)': 'first_set',
        'asian handicap (sets)': 'asian_handicap_sets',
        'asian handicap (games)': 'asian_handicap_games',
        'set betting': 'set_betting',
        'tie-break (1st set)': 'tie_break_first_set',
        'home/away (2nd set)': 'second_set',
        'win at least one set (player 1)': 'win_one_set_player1',
        'win at least one set (player 2)': 'win_one_set_player2',
        
        # Handball markets (1 market available)
        '3way result': 'match_result',
        '3Way Result': 'match_result',  # Handle capital W version from Goalserve
        
        # Volleyball markets (5 markets available)
        'home/away': 'home_away',  # Volleyball has no draw, so use home_away not match_result
        'correct score': 'correct_score',
        'odd/even (1st set)': 'odd_even_first_set',
        'over/under (1st set)': 'over_under_first_set',
        'home/away (1st set)': 'first_set',
        
        # Baseball markets (3 markets available)
        'match winner': 'match_result',  # Primary 1X2 market
        '3way result': 'match_result',   # Alternative name for 1X2
        '3Way Result': 'match_result',   # Handle capital W version from Goalserve
        '1x2': 'match_result',           # Direct 1X2 market
        'match result': 'match_result',  # Direct mapping
        'correct score': 'correct_score',
        'odd/even (including ot)': 'odd_even_including_ot',
        
        # Rugby League markets (9 markets available)
        '3way result': 'match_result',
        '3Way Result': 'match_result',  # Handle capital W version from Goalserve
        'over/under': 'over_under',
        'asian handicap': 'asian_handicap',
        'over/under 1st half': 'over_under_first_half',
        'ht/ft double': 'ht_ft_double',
        'handicap result': 'handicap_result',
        '1st half 3way result': 'first_half_3way_result',
        'asian handicap first half': 'asian_handicap_first_half',
        
        # Table Tennis markets (3 markets available)
        'home/away': 'home_away',  # Table Tennis has no draw, so use home_away not match_result
        'home/away (1st set)': 'first_set',
        'set betting': 'set_betting',
        
        # Darts markets (3 markets available)
        'home/away': 'home_away',  # Darts has no draw, so use home_away not match_result
        'asian handicap': 'asian_handicap',
        'over/under': 'over_under',
        
        # Futsal markets (2 markets available)
        '3way result': 'match_result',
        '3Way Result': 'match_result',  # Handle capital W version from Goalserve
        'over/under': 'over_under',
    }
    
    return market_mapping.get(market_name, None)

def extract_single_event(match, sport_config, category_name='', sport_name=''):
    """Extract a single event with odds"""
    try:
        import time
        start_time = time.time()
        max_processing_time = 2  # 2 seconds max per event
        
        logger.info(f"Extracting event for sport: {sport_name}, match ID: {match.get('id', 'unknown')}")
        
        # Extract team names - handle dictionary structure
        localteam = match.get('localteam', {})
        visitorteam = match.get('visitorteam', {})
        awayteam = match.get('awayteam', {})  # Basketball uses 'awayteam' instead of 'visitorteam'
        
        # Handle different formats
        if isinstance(localteam, dict):
            home_team = localteam.get('name', '')
        else:
            home_team = str(localteam) if localteam else ''
            
        # Try both visitorteam and awayteam - prioritize the one with actual data
        away_team = ''
        if isinstance(visitorteam, dict) and visitorteam.get('name'):
            away_team = visitorteam.get('name', '')
        elif isinstance(awayteam, dict) and awayteam.get('name'):
            away_team = awayteam.get('name', '')
        elif visitorteam and not isinstance(visitorteam, dict):
            away_team = str(visitorteam)
        elif awayteam and not isinstance(awayteam, dict):
            away_team = str(awayteam)
        
        # Fallback for tennis/other sports
        if not home_team:
            player_1 = match.get('player_1', {})
            if isinstance(player_1, dict):
                home_team = player_1.get('name', '')
            else:
                home_team = str(player_1) if player_1 else ''
                
        if not away_team:
            player_2 = match.get('player_2', {})
            if isinstance(player_2, dict):
                away_team = player_2.get('name', '')
            else:
                away_team = str(player_2) if player_2 else ''
        
        logger.info(f"Teams extracted - Home: {home_team}, Away: {away_team}")
        
        # Validate that we have both teams
        if not home_team or not away_team:
            logger.warning(f"Missing team names for {sport_name} match {match.get('id', 'unknown')}")
            return None
        
        # Check timeout before processing odds
        if time.time() - start_time > max_processing_time:
            logger.warning(f"⚠️ Timeout processing {sport_name} match {match.get('id', 'unknown')}")
            return None
        
        # Extract all odds including secondary markets
        all_odds = extract_odds_from_match(match, sport_name)
        
        # Check timeout after odds extraction
        if time.time() - start_time > max_processing_time:
            logger.warning(f"⚠️ Timeout after odds extraction for {sport_name} match {match.get('id', 'unknown')}")
            return None
        
        logger.info(f"Odds extracted for {sport_name}: {all_odds}")
        
        # Format odds for frontend
        formatted_odds = {}
        if all_odds:
            # Handle match_result (1X2) odds specifically - only for true 3-way markets
            if 'match_result' in all_odds:
                match_result_odds = all_odds['match_result']
                if len(match_result_odds) >= 3:
                    # For 1X2 markets, show all 3 values: Home, Draw, Away
                    formatted_odds['match_result'] = match_result_odds
                    logger.info(f"✅ Formatted 1X2 odds: {match_result_odds}")
                else:
                    logger.warning(f"⚠️ Expected 3 odds for 3-way match_result, got: {match_result_odds}")
            
            # Handle home_away (2-way) odds separately
            if 'home_away' in all_odds:
                home_away_odds = all_odds['home_away']
                if len(home_away_odds) >= 2:
                    formatted_odds['home_away'] = home_away_odds
                    logger.info(f"✅ Formatted home_away odds: {home_away_odds}")
                else:
                    logger.warning(f"⚠️ Expected 2 odds for home_away, got: {home_away_odds}")
            
            # Handle other markets
            for market_key, odds_values in all_odds.items():
                if market_key not in ['match_result', 'home_away'] and odds_values:
                    formatted_odds[market_key] = odds_values
        
        logger.info(f"Formatted odds for {sport_name}: {formatted_odds}")
        
        # Use category name as league, or fallback to 'Unknown League'
        league_name = category_name if category_name else 'Unknown League'
        
        # Handle status field - convert time-based statuses to meaningful text
        raw_status = match.get('status', '')
        if not raw_status:
            status = 'Not Started'
        elif ':' in raw_status:  # Time-based status (e.g., "18:45")
            status = 'Not Started'
        elif raw_status in ['FT', 'HT', 'LIVE', 'Finished', 'Final', 'Ended', 'Completed']:
            status = raw_status
        else:
            status = raw_status
        
        event = {
            'id': match.get('id', ''),
            'home_team': home_team,
            'away_team': away_team,
            'date': match.get('formatted_date', '') or match.get('date', ''),
            'time': match.get('time', ''),
            'league': league_name,
            'status': status,
            'odds': formatted_odds,
            'sport': sport_name  # Include sport information for betting
        }
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Successfully extracted {sport_name} event: {event['id']} - {home_team} vs {away_team} in {processing_time:.3f}s")
        
        # Debug: Log market IDs in the event
        logger.info(f"Event {event['id']} odds structure: {formatted_odds}")
        for market_key, odds_data in formatted_odds.items():
            if f"{market_key}_market_id" in formatted_odds:
                logger.info(f"✅ Market {market_key} has ID: {formatted_odds[f'{market_key}_market_id']}")
            else:
                logger.warning(f"⚠️ Market {market_key} has no ID")      
        return event
        
    except Exception as e:
        logger.error(f"Error extracting event: {e}")
        return None

def extract_events_from_json(json_data, sport_config, sport_name=''):
    """Extract events with odds from JSON data"""
    events = []
    
    try:
        # Add safety limit to prevent processing too many events
        # Baseball has very large JSON files, so limit it more aggressively
        if sport_name == 'baseball':
            max_events = 50  # Limit baseball to 50 events to prevent hanging
        else:
            max_events = 1000  # Other sports can have more events
        
        events_processed = 0
        
        # Check if this is cricket format (odds_data.scores.category structure)
        if 'odds_data' in json_data and 'scores' in json_data['odds_data'] and 'category' in json_data['odds_data']['scores']:
            # Cricket format: odds_data.scores.category[].matches.match
            scores = json_data['odds_data']['scores']
            categories = scores['category']
            if not isinstance(categories, list):
                categories = [categories]
                
            for category in categories:
                if 'matches' not in category or events_processed >= max_events:
                    continue
                    
                matches = category['matches']
                # Cricket has single match object, not array
                if isinstance(matches, dict) and 'match' in matches:
                    match = matches['match']
                    if isinstance(match, dict):
                        # Only process matches that haven't started and have odds
                        status = match.get('status', '')
                        
                        # Skip finished/live matches - be more inclusive for pre-match
                        skip_statuses = ['FT', 'HT', 'LIVE', 'Finished', 'Final', 'Ended', 'Completed', 
                                       '1st Quarter', '2nd Quarter', '3rd Quarter', '4th Quarter', 
                                       'Set 1', 'Set 2', 'Set 3', 'Overtime']
                        
                        if status in skip_statuses:
                            continue
                            
                        # Pass category name as league information
                        category_name = category.get('name', '')
                        event = extract_single_event(match, sport_config, category_name, sport_name)
                        if event:  # Only add if event has valid odds
                            events.append(event)
                            events_processed += 1
                            if events_processed >= max_events:
                                logger.warning(f"⚠️ Reached max events limit ({max_events}) for {sport_name}")
                                break
        # Check if this is cricket standard format (with bm=16 parameter)
        elif 'odds_data' in json_data and 'scores' in json_data['odds_data'] and 'categories' in json_data['odds_data']['scores']:
            # Cricket standard format: odds_data.scores.categories.category[].matches.match[]
            scores = json_data['odds_data']['scores']
            categories = scores['categories']
            if not isinstance(categories, list):
                categories = [categories]
                
            for category in categories:
                if 'matches' not in category or events_processed >= max_events:
                    continue
                    
                matches = category['matches']
                if not isinstance(matches, list):
                    matches = [matches]
                    
                for match in matches:
                    if isinstance(match, dict) and events_processed < max_events:
                        # Only process matches that haven't started and have odds
                        status = match.get('status', '')
                        
                        # Skip finished/live matches - be more inclusive for pre-match
                        skip_statuses = ['FT', 'HT', 'LIVE', 'Finished', 'Final', 'Ended', 'Completed', 
                                       '1st Quarter', '2nd Quarter', '3rd Quarter', '4th Quarter', 
                                       'Set 1', 'Set 2', 'Set 3', 'Overtime']
                        
                        if status in skip_statuses:
                            continue
                            
                        # Pass category name as league information
                        category_name = category.get('name', '')
                        event = extract_single_event(match, sport_config, category_name, sport_name)
                        if event:  # Only add if event has valid odds
                            events.append(event)
                            events_processed += 1
                            if events_processed >= max_events:
                                logger.warning(f"⚠️ Reached max events limit ({max_events}) for {sport_name}")
                                break
                    if events_processed >= max_events:
                        break
                if events_processed >= max_events:
                    break
        else:
            # Standard format: odds_data.scores.categories.category[].matches.match[]
            if not json_data or 'odds_data' not in json_data:
                return events
                
            odds_data = json_data['odds_data']
            if 'scores' not in odds_data:
                return events
                
            scores = odds_data['scores']
            if 'categories' not in scores:
                return events
                
            categories = scores['categories']
            if not isinstance(categories, list):
                categories = [categories]
                
            for category in categories:
                if 'matches' not in category or events_processed >= max_events:
                    continue
                    
                matches = category['matches']
                if not isinstance(matches, list):
                    matches = [matches]
                    
                for match in matches:
                    if isinstance(match, dict) and events_processed < max_events:
                        # Only process matches that haven't started and have odds
                        status = match.get('status', '')
                        
                        # Skip finished/live matches - be more inclusive for pre-match
                        skip_statuses = ['FT', 'HT', 'LIVE', 'Finished', 'Final', 'Ended', 'Completed', 
                                       '1st Quarter', '2nd Quarter', '3rd Quarter', '4th Quarter', 
                                       'Set 1', 'Set 2', 'Set 3', 'Overtime']
                        
                        if status in skip_statuses:
                            continue
                            
                        # Pass category name as league information
                        category_name = category.get('name', '')
                        event = extract_single_event(match, sport_config, category_name, sport_name)
                        if event:  # Only add if event has valid odds
                            events.append(event)
                            events_processed += 1
                            if events_processed >= max_events:
                                logger.warning(f"⚠️ Reached max events limit ({max_events}) for {sport_name}")
                                break
                    if events_processed >= max_events:
                        break
                if events_processed >= max_events:
                    break
                    
    except Exception as e:
        logger.error(f"Error extracting events from JSON: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
    logger.info(f"Extracted {len(events)} events from {sport_name} JSON (processed {events_processed} matches)")
    return events

@json_sports_bp.route('/sports', methods=['GET'])
def get_sports():
    """Get all available sports with event counts from JSON files"""
    try:
        logger.info("=== JSON SPORTS API CALLED ===")
        
        sports_counts = {}
        
        for sport_name, config in SPORTS_CONFIG.items():
            logger.info(f"Processing sport: {sport_name}")
            json_data = load_sport_json(sport_name)
            if json_data:
                events = extract_events_from_json(json_data, config)
                event_count = len(events)
                logger.info(f"Sport {sport_name}: extracted {event_count} events")
                if event_count > 0:  # Only include sports with events
                    sports_counts[sport_name] = {
                        'count': event_count,
                        'display_name': config['display_name'],
                        'icon': config['icon'],
                        'has_draw': config['has_draw']
                    }
                    logger.info(f"✅ {config['display_name']}: {event_count} events")
                else:
                    logger.info(f"⚪ {config['display_name']}: No events with odds")
            else:
                logger.warning(f"❌ {config['display_name']}: JSON file not found")
                
        logger.info(f"=== RETURNING {len(sports_counts)} SPORTS WITH EVENTS ===")
        logger.info(f"Sports found: {list(sports_counts.keys())}")
        return jsonify(sports_counts)
        
    except Exception as e:
        logger.error(f"Error fetching sports from JSON: {e}")
        return jsonify({}), 500

@json_sports_bp.route('/events/<sport_name>', methods=['GET'])
def get_sport_events(sport_name):
    """Get events for a specific sport from JSON files"""
    try:
        logger.info(f"=== JSON EVENTS API CALLED FOR {sport_name.upper()} ===")
        
        if sport_name not in SPORTS_CONFIG:
            logger.error(f"Unknown sport: {sport_name}")
            return jsonify([]), 404
            
        sport_config = SPORTS_CONFIG[sport_name]
        json_data = load_sport_json(sport_name)
        
        if not json_data:
            logger.error(f"No JSON data found for {sport_name}")
            return jsonify([]), 404
        
        # Add timeout protection for large files like baseball
        import time
        start_time = time.time()
        # Baseball needs a shorter timeout due to large JSON files
        if sport_name == 'baseball':
            max_processing_time = 15  # 15 seconds max for baseball
        else:
            max_processing_time = 30  # 30 seconds max for other sports
        
        logger.info(f"Starting to extract events for {sport_name}...")
        events = extract_events_from_json(json_data, sport_config, sport_name)
        
        # Check if processing took too long
        processing_time = time.time() - start_time
        if processing_time > max_processing_time:
            logger.warning(f"⚠️ Processing {sport_name} took {processing_time:.2f}s (over {max_processing_time}s limit)")
        
        # Filter out disabled events
        filtered_events = filter_disabled_events(events, sport_name)
        
        logger.info(f"✅ Returning {len(filtered_events)} active events (filtered from {len(events)} total) for {sport_name} in {processing_time:.2f}s")
        
        # Add caching headers for better performance
        response = jsonify(filtered_events)
        response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutes cache
        response.headers['ETag'] = f'"{hash(str(filtered_events))}"'  # ETag for caching
        return response
        
    except Exception as e:
        logger.error(f"Error fetching events for {sport_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify([]), 500

@json_sports_bp.route('/health', methods=['GET'])
def health_check():
    """Check JSON files availability"""
    try:
        total_sports = len(SPORTS_CONFIG)
        available_sports = 0
        total_events = 0
        
        for sport_name, config in SPORTS_CONFIG.items():
            json_data = load_sport_json(sport_name)
            if json_data:
                available_sports += 1
                events = extract_events_from_json(json_data, config)
                total_events += len(events)
                
        return jsonify({
            'status': 'healthy',
            'data_source': 'JSON files',
            'base_path': str(BASE_SPORTS_PATH),
            'total_sports_configured': total_sports,
            'available_sports': available_sports,
            'total_events_with_odds': total_events
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

