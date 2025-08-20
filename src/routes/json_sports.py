"""
JSON-based Sports API Routes - Uses pre-match JSON files as single source of truth
"""

import json
import os
import sqlite3
from pathlib import Path
from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

json_sports_bp = Blueprint('json_sports', __name__)

# Base path to the Sports Pre Match folder
BASE_SPORTS_PATH = Path(__file__).parent.parent.parent / "Sports Pre Match"

# Database path for checking disabled events
DATABASE_PATH = Path(__file__).parent.parent / "database" / "app.db"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def filter_disabled_events(events, sport_name):
    """Filter out disabled events from the events list"""
    try:
        conn = get_db_connection()
        
        # Get all disabled event keys from the event_key column
        disabled_events = conn.execute(
            'SELECT event_key FROM disabled_events WHERE is_disabled = 1'
        ).fetchall()
        
        disabled_keys = set(row['event_key'] for row in disabled_events)
        conn.close()
        
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
                if event['odds']:
                    filtered_events.append(event)
                    print(f"🔍 Keeping event {event_id} with {len(event['odds'])} markets")
                else:
                    print(f"🔍 Removing event {event_id} (no markets left)")
            else:
                # Event has no odds, include it anyway
                filtered_events.append(event)
                print(f"🔍 Keeping event {event_id} (no odds)")
        
        print(f"🔍 Filtered to {len(filtered_events)} events")
        return filtered_events
        
    except Exception as e:
        logger.error(f"Error filtering disabled events: {e}")
        print(f"🔍 Error filtering: {e}")
        return events  # Return all events if filtering fails

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
                
                # For cricket, we know it's always "Home/Away" market (match winner)
                market_name = "home/away"  # Cricket uses Home/Away for match winner
                logger.info(f"Processing cricket market: {market_name}")
                
                # Collect all odds from the single bookmaker
                all_cricket_odds = []
                for odd_type in match['odds']['type']:
                    if 'bookmaker' in odd_type and odd_type['bookmaker']:
                        bookmaker = odd_type['bookmaker']
                        # Handle single bookmaker object (not a list)
                        if isinstance(bookmaker, dict) and 'odd' in bookmaker:
                            for o in bookmaker['odd']:
                                value = o.get('value', '')
                                name = o.get('name', '').lower()
                                try:
                                    float_val = float(value)
                                    if float_val > 1.0:  # Valid odds
                                        all_cricket_odds.append(value)
                                except (ValueError, TypeError):
                                    continue
                
                if all_cricket_odds:
                    # Map to match_result market
                    frontend_key = 'match_result'
                    logger.info(f"Cricket market '{market_name}' mapped to '{frontend_key}' with {len(all_cricket_odds)} odds")
                    all_odds[frontend_key] = all_cricket_odds
                    
                    # Extract market ID from cricket's unique structure
                    if 'type' in match['odds'] and match['odds']['type']:
                        # Get the first type entry (usually the main market)
                        first_type = match['odds']['type'][0]
                        if 'bookmaker' in first_type and first_type['bookmaker']:
                            # Get the first bookmaker's first odd ID as the market ID
                            first_bookmaker = first_type['bookmaker'][0]
                            if 'odd' in first_bookmaker and first_bookmaker['odd']:
                                first_odd = first_bookmaker['odd'][0]
                                cricket_market_id = first_odd.get('id', '')
                                if cricket_market_id:
                                    all_odds[f"{frontend_key}_market_id"] = cricket_market_id
                                    logger.info(f"✅ Stored cricket market ID for {frontend_key}: {cricket_market_id}")
                                else:
                                    logger.warning(f"⚠️ No market ID found for cricket {frontend_key}")
                    
                    logger.info(f"✅ Added cricket odds for {frontend_key}: {all_cricket_odds}")
                else:
                    logger.warning(f"⚠️ No valid odds found for cricket market: {market_name}")
                    
                logger.info(f"Final cricket odds extracted: {all_odds}")
            else:
                # Standard format: odds[].bookmakers[].odd[]
                # First pass: look for "Match Winner" specifically for match_result
                match_winner_odds = None
                other_odds = []
                
                for odd in match['odds']:
                    market_name = odd.get('value', '').lower()
                    market_id = odd.get('id', '')  # Get the market ID
                    
                    # Extract odds from bookmakers
                    if 'bookmakers' in odd and odd['bookmakers']:
                        bookmaker = odd['bookmakers'][0]
                        if 'odds' in bookmaker:
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
                                frontend_key = map_market_to_frontend(market_name)
                                logger.info(f"Standard market '{market_name}' (ID: {market_id}) mapped to '{frontend_key}' with {len(odds_values)} odds")
                                
                                # Special handling for match_result: prioritize "Match Winner" or "3way result" over "Home/Away"
                                if frontend_key == 'match_result':
                                    # For baseball and other sports, be more strict about what constitutes match_result
                                    if market_name in ['match winner', '3way result', '3way result', '1x2', 'match result'] or '3way' in market_name.lower():
                                        match_winner_odds = odds_values
                                        logger.info(f"✅ Found primary Match Result odds: {odds_values} (ID: {market_id}, market: {market_name})")
                                    elif market_name in ['home/away', 'winner'] and len(odds_values) >= 2:
                                        # For baseball, convert 2-way home/away to 3-way 1X2 format
                                        # Add a draw option with calculated odds (typically around 3.0-4.0)
                                        if sport_name == 'baseball':
                                            # Baseball can have draws in extra innings, so add X option
                                            draw_odds = 3.5  # Default draw odds for baseball
                                            three_way_odds = odds_values + [str(draw_odds)]
                                            match_winner_odds = three_way_odds
                                            logger.info(f"✅ Converted baseball 2-way to 3-way odds: {three_way_odds} (ID: {market_id}, market: {market_name})")
                                        else:
                                            # For other sports, don't include home/away as fallback for match_result
                                            logger.warning(f"⚠️ Skipping unsuitable market '{market_name}' for match_result (ID: {market_id})")
                                    else:
                                        # Don't include other markets as fallback for match_result
                                        logger.warning(f"⚠️ Skipping unsuitable market '{market_name}' for match_result (ID: {market_id})")
                                elif frontend_key:
                                    all_odds[frontend_key] = odds_values
                                
                                # Store market ID mapping separately
                                if market_id:
                                    all_odds[f"{frontend_key}_market_id"] = market_id
                                    logger.info(f"✅ Stored market ID for {frontend_key}: {market_id}")
                                else:
                                    logger.warning(f"⚠️ No market ID found for {frontend_key}")
                
                # Use Match Winner or 3way result odds if available, otherwise use other suitable match_result odds
                if match_winner_odds:
                    all_odds['match_result'] = match_winner_odds
                    logger.info(f"✅ Using primary Match Result odds: {match_winner_odds}")
                else:
                    # For baseball, be strict about fallback markets - only use actual 1X2 markets
                    logger.warning(f"⚠️ No suitable Match Result market found - will not show match_result odds")
                    logger.info(f"ℹ️ Available markets: {[odd.get('value', '') for odd in match['odds']]}")
                
                # Process other markets that weren't handled in the special match_result logic
                for odd in match['odds']:
                    market_name = odd.get('value', '').lower()
                    
                    # Skip if this was already processed in the match_result logic above
                    if map_market_to_frontend(market_name) == 'match_result':
                        continue
                    
                    # Also check if the odds are directly in the match (not in bookmakers structure)
                    if isinstance(odd, dict) and 'value' in odd:
                        # Handle direct odds structure like first_half_winner: ['3.00', '2.00', '3.40']
                        odds_values = []
                        if isinstance(odd['value'], list):
                            for value in odd['value']:
                                try:
                                    float_val = float(value)
                                    if float_val > 1.0:  # Valid odds
                                        odds_values.append(str(value))
                                except (ValueError, TypeError):
                                    continue
                            
                            if odds_values:
                                # Map market names to frontend keys
                                frontend_key = map_market_to_frontend(market_name)
                                logger.info(f"Direct market '{market_name}' mapped to '{frontend_key}' with {len(odds_values)} odds")
                                if frontend_key:
                                    all_odds[frontend_key] = odds_values
        
        return all_odds
    except Exception as e:
        logger.error(f"Error extracting odds from match: {e}")
        return None

def map_market_to_frontend(market_name):
    """Map JSON market names to frontend market keys"""
    market_mapping = {
        # Soccer markets (37 markets available)
        'match winner': 'match_result',
        'home/away': 'match_result',
        'match_result': 'match_result',  # Direct mapping
        'goals over/under': 'goals_over_under',
        
        # Cricket markets - Only Match Result
        'home/away': 'match_result',  # Cricket uses Home/Away for match winner,
        'to qualify': 'to_qualify',
        'results/both teams to score': 'results_both_teams_score',
        'result/total goals': 'result_total_goals',
        'home team score a goal': 'home_team_score_goal',
        'away team score a goal': 'away_team_score_goal',
        'corners 1x2': 'corners_1x2',
        'corners over under': 'corners_over_under',
        
        # Basketball markets (12 markets available)
        '3way result': 'match_result',
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
        'home/away': 'match_result',
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
        
        # Volleyball markets (5 markets available)
        'home/away': 'match_result',
        'correct score': 'correct_score',
        'odd/even (1st set)': 'odd_even_first_set',
        'over/under (1st set)': 'over_under_first_set',
        'home/away (1st set)': 'first_set',
        
        # Baseball markets (3 markets available)
        'match winner': 'match_result',  # Primary 1X2 market
        '3way result': 'match_result',   # Alternative name for 1X2
        '1x2': 'match_result',           # Direct 1X2 market
        'match result': 'match_result',  # Direct mapping
        'correct score': 'correct_score',
        'odd/even (including ot)': 'odd_even_including_ot',
        
        # Rugby League markets (9 markets available)
        '3way result': 'match_result',
        'over/under': 'over_under',
        'asian handicap': 'asian_handicap',
        'over/under 1st half': 'over_under_first_half',
        'ht/ft double': 'ht_ft_double',
        'handicap result': 'handicap_result',
        '1st half 3way result': 'first_half_3way_result',
        'asian handicap first half': 'asian_handicap_first_half',
        
        # Table Tennis markets (3 markets available)
        'home/away': 'match_result',
        'home/away (1st set)': 'first_set',
        'set betting': 'set_betting',
        
        # Darts markets (3 markets available)
        'home/away': 'match_result',
        'asian handicap': 'asian_handicap',
        'over/under': 'over_under',
        
        # Futsal markets (2 markets available)
        '3way result': 'match_result',
        'over/under': 'over_under',
    }
    
    return market_mapping.get(market_name, None)

def extract_single_event(match, sport_config, category_name='', sport_name=''):
    """Extract a single event with odds"""
    try:
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
        
        # Extract all odds including secondary markets
        all_odds = extract_odds_from_match(match, sport_name)
        logger.info(f"Odds extracted for {sport_name}: {all_odds}")
        
        # Format odds for frontend
        formatted_odds = {}
        if all_odds:
            # Handle match_result (1X2) odds specifically
            if 'match_result' in all_odds:
                match_result_odds = all_odds['match_result']
                if len(match_result_odds) >= 3:
                    # For 1X2 markets, show all 3 values: Home, Draw, Away
                    formatted_odds['match_result'] = match_result_odds
                    logger.info(f"✅ Formatted 1X2 odds: {match_result_odds}")
                elif len(match_result_odds) >= 2:
                    # Fallback for 2-way markets
                    formatted_odds['match_result'] = match_result_odds
                    logger.warning(f"⚠️ Only 2 odds found for match_result: {match_result_odds}")
                else:
                    logger.warning(f"⚠️ Insufficient odds for match_result: {match_result_odds}")
            
            # Handle other markets
            for market_key, odds_values in all_odds.items():
                if market_key != 'match_result' and odds_values:
                    formatted_odds[market_key] = odds_values
        
        logger.info(f"Formatted odds for {sport_name}: {formatted_odds}")
        
        # Use category name as league, or fallback to 'Unknown League'
        league_name = category_name if category_name else 'Unknown League'
        
        event = {
            'id': match.get('id', ''),
            'home_team': home_team,
            'away_team': away_team,
            'date': match.get('date', ''),
            'time': match.get('time', ''),
            'league': league_name,
            'status': match.get('status', 'Not Started'),
            'odds': formatted_odds,
            'sport': sport_name  # Include sport information for betting
        }
        
        logger.info(f"✅ Successfully extracted {sport_name} event: {event['id']} - {home_team} vs {away_team}")
        
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
        # Check if this is cricket format (odds_data.scores.category structure)
        if 'odds_data' in json_data and 'scores' in json_data['odds_data'] and 'category' in json_data['odds_data']['scores']:
            # Cricket format: odds_data.scores.category[].matches.match
            scores = json_data['odds_data']['scores']
            categories = scores['category']
            if not isinstance(categories, list):
                categories = [categories]
                
            for category in categories:
                if 'matches' not in category:
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
        # Check if this is cricket standard format (with bm=16 parameter)
        elif 'odds_data' in json_data and 'scores' in json_data['odds_data'] and 'categories' in json_data['odds_data']['scores']:
            # Cricket standard format: odds_data.scores.categories.category[].matches.match[]
            scores = json_data['odds_data']['scores']
            categories = scores['categories']
            if not isinstance(categories, list):
                categories = [categories]
                
            for category in categories:
                if 'matches' not in category:
                    continue
                    
                matches = category['matches']
                if not isinstance(matches, list):
                    matches = [matches]
                    
                for match in matches:
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
                if 'matches' not in category:
                    continue
                    
                matches = category['matches']
                if not isinstance(matches, list):
                    matches = [matches]
                    
                for match in matches:
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
                    
    except Exception as e:
        logger.error(f"Error extracting events from JSON: {e}")
        
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
            
        events = extract_events_from_json(json_data, sport_config, sport_name)
        
        # Filter out disabled events
        filtered_events = filter_disabled_events(events, sport_name)
        
        logger.info(f"✅ Returning {len(filtered_events)} active events (filtered from {len(events)} total) for {sport_name}")
        
        # Add caching headers for better performance
        response = jsonify(filtered_events)
        response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutes cache
        response.headers['ETag'] = f'"{hash(str(filtered_events))}"'  # ETag for caching
        return response
        
    except Exception as e:
        logger.error(f"Error fetching events for {sport_name}: {e}")
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

