"""
Bet settlement service for automatically settling bets based on match results
"""

from __future__ import annotations  # avoids runtime eval of type hints
from flask import current_app
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

# Import models at module level for consistent access
from src.models.betting import Bet, User, Transaction
import logging
import time
import threading
from datetime import datetime, timedelta
import json
from src.goalserve_client import OptimizedGoalServeClient

logger = logging.getLogger(__name__)

# Define final statuses for all sports
FINAL_STATUSES = {
    "final", "finished", "ended", "ft", "full time", "game over", 
    "after extra time", "aet", "penalties", "pen", "90", "120",
    "complete", "completed", "result", "results", "final result"
}

def norm(x): 
    """Normalize text for comparison"""
    if x is None:
        return ""
    return str(x).lower().strip()

def event_key(event):
    """Create composite key for event matching"""
    # Adjust keys to your feed shape
    league = norm(event.get("league") or event.get("competition") or event.get("category"))
    home = norm(event.get("home", {}).get("name") if isinstance(event.get("home"), dict) else event.get("home"))
    away = norm(event.get("away", {}).get("name") if isinstance(event.get("away"), dict) else event.get("away"))
    # Use kickoff date (not full timestamp) to avoid TZ hiccups
    date = str(event.get("time") or event.get("date") or "")[:10]
    return (league, home, away, date)

def bet_key(bet):
    """Create composite key for bet matching"""
    # Extract team names from match_name (e.g., "Team A vs Team B")
    match_name = bet.match_name or ""
    if " vs " in match_name:
        home_team, away_team = match_name.split(" vs ", 1)
    else:
        home_team, away_team = match_name, ""
    
    # Use sport_name instead of league, and created_at instead of kickoff
    sport = getattr(bet, "sport_name", None) or getattr(bet, "sport", None) or "unknown"
    return (norm(sport), norm(home_team), norm(away_team), str(bet.created_at)[:10] if bet.created_at else "")

def _to_int(x):
    """Convert value to integer safely"""
    try:
        return int(x)
    except (TypeError, ValueError):
        return None

def get_team_score(event: dict, side: str) -> int | None:
    """
    Extract team score from event object with multiple fallback strategies
    side: 'home' | 'away'
    Supports any of:
      event['home_score'] / ['away_score']               # normalized
      event['home']['@totalscore'] / ['away']['@totalscore']
      event['localteam']['@totalscore'] / ['awayteam']['@totalscore']  # legacy Goalserve XML mapping
    """
    # 1) normalized flat fields (most reliable)
    v = event.get(f'{side}_score')
    if v is not None:
        return _to_int(v)

    # 2) normalized nested dicts
    node = event.get(side) or {}
    v = node.get('@totalscore')
    if v is not None:
        return _to_int(v)

    # 3) legacy goalserve mapping names
    legacy_key = 'localteam' if side == 'home' else 'awayteam'
    node = event.get(legacy_key) or {}
    v = node.get('@totalscore')
    if v is not None:
        return _to_int(v)

    # 4) try other common score fields
    for key in ("runs", "r", "goals", "score", "points", "goals_scored"):
        v = node.get(key)
        if v is not None:
            return _to_int(v)
    
    # 5) fallback: top-level score string like "3-2"
    sc = event.get("score") or event.get("result") or event.get("ft_score")
    if isinstance(sc, str) and "-" in sc:
        try:
            h, a = [int(x.strip()) for x in sc.split("-", 1)]
            return h if side == "home" else a
        except (ValueError, TypeError): 
            pass

    return None

def determine_outcome(event: dict) -> str | None:
    """Determine match outcome from scores"""
    hs = get_team_score(event, 'home')
    as_ = get_team_score(event, 'away')
    if hs is None or as_ is None:
        return None
    if hs > as_:
        return 'HOME'
    if hs < as_:
        return 'AWAY'
    return 'DRAW'

def get_score(ev, side):
    """Legacy function - now delegates to get_team_score"""
    return get_team_score(ev, side)

def robust_goalserve_parse(response_text, content_type=""):
    """
    Robust parsing for Goalserve responses that might be JSON or XML
    Handles cases where ?json=1 returns XML anyway
    """
    try:
        # Try JSON first if content type suggests it
        if "json" in content_type.lower() or response_text.strip().startswith("{"):
            return json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Fallback to XML parsing
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response_text)
        
        # Convert XML to dict-like structure for compatibility
        def xml_to_dict(element):
            result = {}
            for child in element:
                if len(child) == 0:
                    result[child.tag] = child.text or ""
                else:
                    result[child.tag] = xml_to_dict(child)
            return result
        
        return xml_to_dict(root)
    except ET.ParseError:
        logger.warning("Failed to parse Goalserve response as either JSON or XML")
        return None



class BetSettlementService:
    def __init__(self, app=None):
        self.client = OptimizedGoalServeClient()
        self.app = app  # Store Flask app instance
        self.running = False
        self.settlement_thread = None
        self.check_interval = 300  # Check every 5 minutes for completed matches (reduced from 30min to avoid pool starvation)
        self.last_check_time = None
        self.total_checks = 0
        self.successful_settlements = 0
        self.failed_settlements = 0
        self.last_error = None
        self.start_time = None
        # cooperative stop signal
        import threading
        self._stop_event = threading.Event()
        
    def start(self):
        """Start the automatic bet settlement service"""
        if not self.running:
            try:
                self.running = True
                self.start_time = datetime.utcnow()
                # Daemon thread so process can exit without a blocking join at shutdown
                self.settlement_thread = threading.Thread(
                    target=self._settlement_loop,
                    name="bet-settlement",
                    daemon=True
                )
                self.settlement_thread.start()
                logger.info("✅ Automatic bet settlement service started successfully")
                return True
            except Exception as e:
                self.running = False
                self.last_error = str(e)
                logger.error(f"❌ Failed to start settlement service: {e}")
                return False
        return True
    
    def stop(self):
        """Cooperative, non-blocking stop (Eventlet-safe)."""
        self.running = False
        try:
            self._stop_event.set()
        except Exception:
            pass
        # Do NOT hard-join inside atexit; yield cooperatively instead.
        try:
            import eventlet
            # give the worker loop some chances to exit
            for _ in range(10):
                if not (self.settlement_thread and self.settlement_thread.is_alive()):
                    break
                eventlet.sleep(0.05)
        except Exception:
            # If eventlet not available here, just skip waiting
            pass
        self.settlement_thread = None
        logger.info("Automatic bet settlement service stopped")
    
    def _settlement_loop(self):
        """Main settlement loop that automatically settles bets when matches end"""
        import eventlet
        logger.info("🔄 Settlement service loop started")
        
        while self.running and not self._stop_event.is_set():
            try:
                self.last_check_time = datetime.utcnow()
                self.total_checks += 1
                
                logger.debug(f"🔍 Settlement check #{self.total_checks} - {self.last_check_time.strftime('%H:%M:%S')}")
                logger.info(f"📊 Current stats - Running: {self.running}, Checks: {self.total_checks}")
                
                # Check if we can access the database - NO CONNECTION HELD DURING SLEEP
                try:
                    if self.app:
                        with self.app.app_context():
                            # Use connection_ctx() with explicit transaction (no autocommit needed)
                            from src.db_compat import connection_ctx
                            with connection_ctx(timeout=5) as conn:
                                with conn.cursor() as c:
                                    c.execute("SET LOCAL statement_timeout = '2000ms'")
                                # Simple read query (no transaction needed for SELECT)
                                with conn.cursor() as cur:
                                    cur.execute("SELECT COUNT(*) FROM bets WHERE status = %s", ('pending',))
                                    pending_count = cur.fetchone()['count']
                            logger.info(f"📋 Found {pending_count} pending bets in database")
                    else:
                        logger.warning("⚠️ No Flask app instance available for database access")
                except Exception as db_error:
                    logger.error(f"❌ Database access error: {db_error}")
                
                self.check_for_completed_matches()
                
                # Log periodic status
                if self.total_checks % 10 == 0:  # Every 10 checks (5 minutes)
                    logger.info(f"📊 Settlement Service Stats: {self.total_checks} checks, {self.successful_settlements} settlements, {self.failed_settlements} failures")
                
                logger.debug(f"✅ Settlement check #{self.total_checks} completed successfully")
                
            except Exception as e:
                self.failed_settlements += 1
                self.last_error = str(e)
                logger.error(f"❌ CRITICAL ERROR in automatic settlement loop: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.exception("Full exception details:")
                
                # Don't let the service crash - continue running
                logger.info("🔄 Continuing settlement service despite error...")
            
            logger.info(f"⏰ Sleeping for {self.check_interval} seconds ({self.check_interval//60} minutes)...")
            # ALWAYS yield via eventlet to avoid hub conflicts
            import eventlet
            eventlet.sleep(self.check_interval)
        
        logger.info("🛑 Settlement service loop stopped")
    
    def _parse_combo_sport_timing(self, sport_string, timing_string):
        """Parse concatenated sport and timing strings for combo bets"""
        if not sport_string or not timing_string:
            return [], []
        
        # Split by underscore
        sports = sport_string.split('_')
        timings = timing_string.split('_')
        
        # Ensure same length (pad with last value if needed)
        while len(timings) < len(sports):
            timings.append(timings[-1] if timings else 'pregame')
        
        while len(sports) < len(timings):
            sports.append(sports[-1] if sports else 'soccer')
        
        return sports, timings
    
    def _get_sport_for_match_id(self, match_id, sport_match_mapping):
        """Get the sport for a specific match ID in a combo bet"""
        return sport_match_mapping.get(match_id, 'soccer')  # Default to soccer
    
    def _get_endpoints_for_match_id(self, match_id, sport_match_mapping):
        """Get specific endpoints to check for a match ID based on its sport"""
        sport = self._get_sport_for_match_id(match_id, sport_match_mapping)
        endpoints = [
            f"{sport}/home",  # Recent completed matches
            f"{sport}/d-1",   # Yesterday
            f"{sport}/d-2",   # Day before yesterday
            f"{sport}/d-3"    # 3 days ago
        ]
        return endpoints
    
    def _create_sport_match_mapping(self, combo_bet):
        """Create sport to match ID mapping for combo bets"""
        if not combo_bet.combo_selections:
            return {}
        
        try:
            selections = json.loads(combo_bet.combo_selections)
            sports, timings = self._parse_combo_sport_timing(combo_bet.sport_name, combo_bet.bet_timing)
            
            sport_match_mapping = {}
            for i, selection in enumerate(selections):
                match_id = selection.get('match_id')
                if match_id and i < len(sports):
                    sport_match_mapping[match_id] = sports[i]
            
            return sport_match_mapping
        except Exception as e:
            logger.error(f"Error creating sport match mapping for combo bet {combo_bet.id}: {e}")
            return {}
    
    def check_for_completed_matches(self):
        """Check for completed matches and automatically settle bets"""
        try:
            logger.info("🔍 Starting check_for_completed_matches...")
            
            # Get all pending bets within Flask app context
            if self.app:
                with self.app.app_context():
                    pending_bets = Bet.query.filter_by(status='pending').all()
            else:
                logger.error("❌ No Flask app instance available for database access")
                return
            
            if not pending_bets:
                logger.info("📭 No pending bets found, skipping settlement check")
                return
            
            logger.info(f"📋 Found {len(pending_bets)} pending bets for automatic settlement")
            
            # Log details of each pending bet
            for i, bet in enumerate(pending_bets):
                logger.debug(f"  Bet {i+1}: ID={bet.id}, Match={bet.match_name}, Sport={bet.sport_name}, Match_ID={bet.match_id}")
            
            # Collect all unique match IDs we need to check
            match_ids_to_check = set()
            
            for bet in pending_bets:
                if bet.combo_selections:
                    # For combo bets, extract individual match IDs
                    import json
                    selections = json.loads(bet.combo_selections)
                    for selection in selections:
                        match_id = selection.get('match_id')
                        if match_id and not match_id.startswith('combo_') and not match_id.startswith('match_'):
                            match_ids_to_check.add(match_id)
                else:
                    # For single bets, use the bet's match_id
                    if bet.match_id and not bet.match_id.startswith('combo_') and not bet.match_id.startswith('match_'):
                        match_ids_to_check.add(bet.match_id)
            
            if not match_ids_to_check:
                logger.info("No valid match IDs to check for settlement")
                return
            
            logger.info(f"Checking {len(match_ids_to_check)} unique match IDs for settlement")
            
            # Get historical events for multiple sports (last 7 days)
            # This is necessary because current events feed filters out completed matches
            historical_events = []
            
            # Define sports to check based on the pending bets
            sports_to_check = self._determine_sports_from_bets(pending_bets)
            logger.info(f"Checking historical data for sports: {sports_to_check}")
            
            for sport in sports_to_check:
                # Special handling for cricket - use the cricket/livescore feed
                if sport == 'cricket':
                    try:
                        logger.info("Checking cricket/livescore for historical data")
                        cricket_events = self._get_cricket_historical_events()
                        historical_events.extend(cricket_events)
                    except Exception as e:
                        logger.warning(f"Error fetching cricket data: {e}")
                    continue
                
                # First check the /home endpoint for each sport
                try:
                    # Use soccernew for soccer, otherwise use sport/home
                    if sport == 'soccer':
                        home_endpoint = 'soccernew/home'
                    else:
                        home_endpoint = f'{sport}/home'
                    
                    logger.info(f"Checking {home_endpoint} for historical data")
                    home_data = self.client._make_request(home_endpoint, use_cache=False)
                    if home_data:
                        matches = self.client._extract_matches_from_goalserve_data(home_data)
                        for match in matches:
                            # Parse match into event format for settlement (include completed matches)
                            event = self._parse_match_for_settlement(match, sport, home_endpoint)
                            if event:
                                historical_events.append(event)
                except Exception as e:
                    logger.warning(f"Error fetching home data for {sport}: {e}")
                
                # Then check the daily historical feeds for the last 7 days
                for days_ago in range(1, 8):  # Check last 7 days
                    try:
                        # Use soccernew for soccer, otherwise use sport/d-X
                        if sport == 'soccer':
                            endpoint = f'soccernew/d-{days_ago}'
                        else:
                            endpoint = f'{sport}/d-{days_ago}'
                        
                        historical_data = self.client._make_request(endpoint, use_cache=False)
                        if historical_data:
                            matches = self.client._extract_matches_from_goalserve_data(historical_data)
                            for match in matches:
                                # Parse match into event format for settlement (include completed matches)
                                event = self._parse_match_for_settlement(match, sport, endpoint)
                                if event:
                                    historical_events.append(event)
                    except Exception as e:
                        logger.warning(f"Error fetching historical data for {sport} d-{days_ago}: {e}")
                        continue
            
            logger.info(f"Found {len(historical_events)} historical events to check for settlement")
            
            # 1) After building the historical list - CRITICAL LOG
            if historical_events:
                sample_ids = [str(e.get("id", "NO_ID")) for e in historical_events[:5]]
                logger.info("🧾 Historical events sample (first 5 IDs): %s", sample_ids)
            else:
                logger.warning("⚠️ No historical events found for settlement")
            
            # Separate single bets and combo bets
            single_bets = []
            combo_bets = []
            
            for bet in pending_bets:
                if bet.combo_selections:
                    combo_bets.append(bet)
                else:
                    single_bets.append(bet)
            
            # Process single bets (existing logic)
            if single_bets:
                bets_by_match = {}
                for bet in single_bets:
                    match_key = bet.match_name
                    if match_key not in bets_by_match:
                        bets_by_match[match_key] = []
                    bets_by_match[match_key].append(bet)
                
                            # Process each match within the same app context
            for match_name, bets in bets_by_match.items():
                # 2) When checking each pending bet - CRITICAL LOG
                for bet in bets:
                    logger.info("🔎 Looking for event: bet_id=%s match_id=%s sport=%s",
                                bet.id, bet.match_id, bet.sport_name or "unknown")
                self._check_match_completion(match_name, bets, historical_events)
            
            # Process combo bets (new logic)
            if combo_bets:
                logger.info(f"Processing {len(combo_bets)} combo bets")
                for combo_bet in combo_bets:
                    self._check_combo_bet_completion(combo_bet, historical_events)
                
        except Exception as e:
            logger.error(f"Error checking for completed matches: {e}")
    
    def _determine_sports_from_bets(self, bets):
        """Determine which sports to check based on the pending bets - now uses stored sport_name"""
        sports_to_check = set()
        
        for bet in bets:
            # Use stored sport_name if available (most reliable)
            sport = getattr(bet, "sport_name", None) or getattr(bet, "sport", None)
            if sport:
                sports_to_check.add(sport)
            else:
                # Fallback to match name analysis (for legacy bets)
                match_name = getattr(bet, "match_name", "").lower()
                
                # Determine sport from match name patterns
                if any(team in match_name for team in ['marines', 'hawks', 'dragons', 'tigers', 'eagles', 'buffaloes', 'giants', 'swallows', 'carp', 'baystars', 'lions', 'fighters', 'orix']):
                    sports_to_check.add('baseball')
                elif any(team in match_name for team in ['lakers', 'warriors', 'celtics', 'bulls', 'heat', 'knicks', 'nets', 'raptors', 'mavericks', 'rockets', 'spurs', 'thunder']):
                    sports_to_check.add('bsktbl')
                elif any(team in match_name for team in ['united', 'city', 'arsenal', 'chelsea', 'liverpool', 'barcelona', 'real madrid', 'bayern', 'psg', 'juventus', 'milan', 'inter']):
                    sports_to_check.add('soccer')
                elif any(team in match_name for team in ['patriots', 'cowboys', 'packers', 'steelers', '49ers', 'chiefs', 'bills', 'ravens', 'eagles', 'giants', 'jets']):
                    sports_to_check.add('football')
                elif any(team in match_name for team in ['india', 'australia', 'england', 'pakistan', 'south africa', 'new zealand', 'west indies', 'sri lanka', 'bangladesh', 'afghanistan', 'ireland', 'zimbabwe']):
                    sports_to_check.add('cricket')
                else:
                    # Default to soccer for unknown teams
                    sports_to_check.add('soccer')
        
        # Only add soccer as fallback if no specific sport was identified
        if not sports_to_check:
            sports_to_check.add('soccer')
        
        return list(sports_to_check)
    
    def _check_combo_bet_completion(self, combo_bet, events):
        """Check completion for individual matches within a combo bet using sport-specific endpoints"""
        try:
            # Parse combo selections
            if not combo_bet.combo_selections:
                logger.warning(f"Combo bet {combo_bet.id} has no selections data")
                return
            
            selections = json.loads(combo_bet.combo_selections)
            logger.info(f"Checking combo bet {combo_bet.id} with {len(selections)} selections")
            
            # Create sport to match ID mapping for this combo bet
            sport_match_mapping = self._create_sport_match_mapping(combo_bet)
            logger.info(f"Sport mapping for combo bet {combo_bet.id}: {sport_match_mapping}")
            
            # Check each selection for completion
            for selection in selections:
                if selection.get('settled', False):
                    logger.debug(f"Selection already settled: {selection.get('match_name')}")
                    continue
                
                match_id = selection.get('match_id')
                if not match_id:
                    logger.warning(f"No match_id in selection: {selection}")
                    continue
                
                # Skip invalid match IDs (combo IDs, placeholder IDs)
                if match_id.startswith('combo_') or match_id.startswith('match_'):
                    logger.warning(f"Skipping invalid match_id in combo bet: {match_id}")
                    continue
                
                # Get the sport for this specific match ID
                sport = self._get_sport_for_match_id(match_id, sport_match_mapping)
                logger.info(f"Checking match {match_id} in {sport} data")
                
                # Find the match in current events or historical data
                match_event = None
                for event in events:
                    if event.get('id') == match_id:
                        match_event = event
                        break
                
                if not match_event:
                    logger.info(f"Match {match_id} not found in current events, checking {sport} historical data")
                    match_event = self._find_match_in_historical_data_for_combo(match_id, selection.get('match_name', ''), sport)
                
                if match_event and match_event.get('is_completed', False):
                    logger.info(f"🎯 Combo bet {combo_bet.id}: Match {match_id} completed in {sport}, settling selection")
                    self._settle_combo_bet(combo_bet, match_event, 
                                         match_event.get('home_score', 0), 
                                         match_event.get('away_score', 0))
                elif match_event and match_event.get('is_cancelled', False):
                    logger.info(f"❌ Combo bet {combo_bet.id}: Match {match_id} cancelled in {sport}, voiding selection")
                    self._void_combo_bet(combo_bet, match_event)
                    
        except Exception as e:
            logger.error(f"Error checking combo bet completion for bet {combo_bet.id}: {e}")
    
    def _check_match_completion(self, match_name, bets, events):
        """Check if a specific match is completed and automatically settle bets"""
        try:
            # Get the match ID from the first bet (all bets for same match should have same match_id)
            match_id = bets[0].match_id if bets else None
            
            if not match_id:
                logger.warning(f"No match_id found for bets on {match_name}")
                return
            
            # Find the match in current events by match ID - ROBUST MATCHING
            match_event = None
            
            # Build indexes once per fetch for efficient lookup
            by_id = {str(e.get("id")): e for e in events if e.get("id") is not None}
            by_composite = {event_key(e): e for e in events}
            
            # Try ID lookup first
            match_event = by_id.get(str(match_id))
            if not match_event and str(match_id).isdigit():
                match_event = by_id.get(str(int(match_id)))
            
            # If no ID match, try composite lookup (league+teams+date)
            if not match_event and bets:
                bet = bets[0]  # Use first bet for composite matching
                composite_key = bet_key(bet)
                match_event = by_composite.get(composite_key)
                if match_event:
                    logger.info("✅ Found match by composite key (league+teams+date) for bet_id=%s", bet.id)
            
            if not match_event:
                logger.info(f"Match with ID {match_id} not found in current events: {match_name}")
                # Try to find in historical data
                sport_name = getattr(bets[0], "sport_name", None) if bets else None
                match_event = self._find_match_in_historical_data(match_id, match_name, sport_name)
                if not match_event:
                    logger.warning(f"❌ Couldn't locate event for bet_id=%s (id=%s).", 
                                  bets[0].id if bets else "unknown", match_id)
                    return
            
            # Check if match is completed - ROBUST STATUS CHECKING
            is_completed = match_event.get('is_completed', False)
            is_cancelled = match_event.get('is_cancelled', False)
            
            # Also check status field for completion indicators
            status = match_event.get('status', '')
            normalized_status = norm(status)
            
            # Check if status indicates completion
            if normalized_status in FINAL_STATUSES:
                is_completed = True
            elif status in ['FT', '90', '120'] or (status.isdigit() and int(status) > 90):
                is_completed = True
            
            # 3) Before deciding settlement - CRITICAL LOG
            logger.info("📌 Event found for bet_id=%s: status=%s raw_status=%s id=%s",
                        bets[0].id if bets else "unknown", normalized_status, status, match_event.get('id'))
            
            # Check if status is final but not completed
            if normalized_status in FINAL_STATUSES and not is_completed:
                logger.info("🔄 Status indicates final but not marked completed, forcing completion")
                is_completed = True
            
            # Run settlement within Flask app context
            if self.app:
                with self.app.app_context():
                    if is_completed:
                        logger.info(f"🎯 MATCH COMPLETED: {match_name} - Auto-settling bets")
                        self._auto_settle_bets_for_match(match_event, bets)
                    elif is_cancelled or status in ['Cancl.', 'Postp.', 'WO']:
                        logger.info(f"❌ MATCH CANCELLED: {match_name} - Auto-voiding bets")
                        self._auto_void_bets_for_match(match_event, bets)
                    else:
                        logger.info(f"⏳ Present but not final (bet_id=%s, status=%s)", 
                                  bets[0].id if bets else "unknown", normalized_status)
            else:
                logger.error("❌ No Flask app instance available for database access")
                
        except Exception as e:
            logger.error(f"Error checking match completion for {match_name}: {e}")
    
    def _find_match_in_historical_data(self, match_id, match_name, sport_name=None):
        """Find a match in historical data feeds - optimized for specific match ID"""
        try:
            # Only search if we have a valid match_id (not combo IDs)
            if not match_id or match_id.startswith('combo_') or match_id.startswith('match_'):
                logger.debug(f"Skipping search for invalid match_id: {match_id}")
                return None
            
            logger.info(f"🔍 Searching for match {match_id} in historical data")
            
            # Use stored sport_name if available (most reliable)
            if sport_name:
                sports_to_check = [sport_name]
                logger.info(f"Using stored sport_name: {sport_name}")
            else:
                # Fallback to match name analysis (for legacy bets)
                sports_to_check = self._determine_sports_from_match_name(match_name)
                logger.info(f"Using match name analysis for {match_name}: {sports_to_check}")
            
            # Check historical feeds for each sport
            for sport in sports_to_check:
                # First check the /home endpoint
                home_endpoint = f'{sport}/home'
                logger.debug(f"Checking {home_endpoint} for match {match_id}")
                
                try:
                    home_data = self.client._make_request(home_endpoint, use_cache=False)
                    if home_data:
                        # Extract matches from home data
                        matches = self.client._extract_matches_from_goalserve_data(home_data)
                        
                        # Look for the specific match ID
                        for match in matches:
                            if match.get('@id') == str(match_id):
                                logger.info(f"✅ Found match {match_id} in {sport} home data")
                                # Parse the match into event format for settlement
                                event = self._parse_match_for_settlement(match, sport, home_endpoint)
                                if event:
                                    return event
                except Exception as e:
                    logger.warning(f"Error checking {home_endpoint} for match {match_id}: {e}")
                
                # Then check the daily historical feeds for the last 7 days
                for days_ago in range(1, 8):  # d-1 to d-7
                    endpoint = f'{sport}/d-{days_ago}'
                    logger.debug(f"Checking {endpoint} for match {match_id}")
                    
                    try:
                        historical_data = self.client._make_request(endpoint, use_cache=False)
                        if not historical_data:
                            continue
                        
                        # Extract matches from historical data
                        matches = self.client._extract_matches_from_goalserve_data(historical_data)
                        
                        # Look for the specific match ID
                        for match in matches:
                            if match.get('@id') == str(match_id):
                                logger.info(f"✅ Found match {match_id} in {sport} historical data {days_ago} days ago")
                                # Parse the match into event format for settlement
                                event = self._parse_match_for_settlement(match, sport, endpoint)
                                if event:
                                    return event
                    except Exception as e:
                        logger.warning(f"Error checking {endpoint} for match {match_id}: {e}")
                        continue
                
            logger.warning(f"❌ Match {match_id} not found in any historical feeds")
            return None
            
        except Exception as e:
            logger.error(f"Error searching historical data for match {match_id}: {e}")
            return None
    
    def _find_match_in_historical_data_for_combo(self, match_id, match_name, sport):
        """Find a match in historical data feeds for combo bets using sport-specific endpoints"""
        try:
            # Only search if we have a valid match_id (not combo IDs)
            if not match_id or match_id.startswith('combo_') or match_id.startswith('match_'):
                logger.debug(f"Skipping search for invalid match_id: {match_id}")
                return None
            
            logger.info(f"🔍 Searching for match {match_id} in {sport} historical data")
            
            # Check sport-specific endpoints
            endpoints = [
                f"{sport}/home",  # Recent completed matches
                f"{sport}/d-1",   # Yesterday
                f"{sport}/d-2",   # Day before yesterday
                f"{sport}/d-3"    # 3 days ago
            ]
            
            for endpoint in endpoints:
                logger.debug(f"Checking {endpoint} for match {match_id}")
                
                try:
                    data = self.client._make_request(endpoint, use_cache=False)
                    if not data:
                        continue
                    
                    # Extract matches from data
                    matches = self.client._extract_matches_from_goalserve_data(data)
                    
                    # Look for the specific match ID
                    for match in matches:
                        if match.get('@id') == str(match_id):
                            logger.info(f"✅ Found match {match_id} in {sport} {endpoint}")
                            # Parse the match into event format for settlement
                            event = self._parse_match_for_settlement(match, sport, endpoint)
                            if event:
                                return event
                except Exception as e:
                    logger.warning(f"Error checking {endpoint} for match {match_id}: {e}")
                    continue
            
            logger.warning(f"❌ Match {match_id} not found in {sport} historical feeds")
            return None
            
        except Exception as e:
            logger.error(f"Error searching {sport} historical data for match {match_id}: {e}")
            return None
    
    def _determine_sports_from_match_name(self, match_name):
        """Determine which sports to check based on match name"""
        match_name_lower = match_name.lower()
        sports_to_check = set()
        
        # Determine sport from match name patterns
        if any(team in match_name_lower for team in ['marines', 'hawks', 'dragons', 'tigers', 'eagles', 'buffaloes', 'giants', 'swallows', 'carp', 'baystars', 'lions', 'fighters', 'orix']):
            sports_to_check.add('baseball')
        elif any(team in match_name_lower for team in ['lakers', 'warriors', 'celtics', 'bulls', 'heat', 'knicks', 'nets', 'raptors', 'mavericks', 'rockets', 'spurs', 'thunder']):
            sports_to_check.add('bsktbl')
        elif any(team in match_name_lower for team in ['united', 'city', 'arsenal', 'chelsea', 'liverpool', 'barcelona', 'real madrid', 'bayern', 'psg', 'juventus', 'milan', 'inter']):
            sports_to_check.add('soccer')
        elif any(team in match_name_lower for team in ['patriots', 'cowboys', 'packers', 'steelers', '49ers', 'chiefs', 'bills', 'ravens', 'eagles', 'giants', 'jets']):
            sports_to_check.add('football')
        else:
            # Default to soccer for unknown teams
            sports_to_check.add('soccer')
        
        # Only add soccer as fallback if no specific sport was identified
        if not sports_to_check:
            sports_to_check.add('soccer')
        
        return list(sports_to_check)
    
    def _auto_settle_bets_for_match(self, match_event, bets):
        """Automatically settle bets for a completed match"""
        try:
            # DEBUG: Log the full match event structure
            logger.debug(f"🔍 DEBUG: Full match event structure: {match_event}")
            
            # ROBUST SCORE EXTRACTION WITH MULTIPLE FALLBACKS
            home_score = get_team_score(match_event, 'home')
            away_score = get_team_score(match_event, 'away')
            
            if home_score is None or away_score is None:
                logger.warning("⚠️ Couldn't parse scores for match %s; skipping settlement", match_event.get('id'))
                logger.warning("🔍 Event structure: %s", match_event)
                return
            
            logger.info(f"🏁 Auto-settling bets for {match_event.get('home_team', 'Unknown')} vs {match_event.get('away_team', 'Unknown')} - Final Score: {home_score}-{away_score}")
            
            settled_count = 0
            won_count = 0
            lost_count = 0
            
            # Process each bet (already within Flask app context)
            for bet in bets:
                try:
                    # Re-query the bet using tracked connection
                    from src.db_compat import connection_ctx
                    with connection_ctx(timeout=5) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                            cursor.execute("SELECT * FROM bets WHERE id = %s LIMIT 1", (bet.id,))
                            bet_row = cursor.fetchone()
                            if not bet_row:
                                logger.warning(f"Bet {bet.id} not found in database, skipping")
                                continue
                            bet = bet_row
                    
                    if bet.bet_type == 'combo':
                        # Handle combo bet settlement
                        self._settle_combo_bet(bet, match_event, home_score, away_score)
                        settled_count += 1
                    else:
                        # Handle single bet settlement
                        bet_won = self._determine_bet_outcome(bet, match_event, home_score, away_score)
                        
                        if bet_won:
                            # Bet won - credit user account
                            bet.status = 'won'
                            bet.actual_return = bet.potential_return
                            
                            # Update user balance using tracked connection
                            with connection_ctx(timeout=5) as conn:
                                with conn.transaction():
                                    # Get user current balance
                                    cursor.execute("SELECT balance FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                                    user_row = cursor.fetchone()
                                    if not user_row:
                                        logger.warning(f"User {bet.user_id} not found for bet {bet.id}")
                                        continue
                                    
                                    balance_before = user_row['balance'] or 0
                                    balance_after = balance_before + bet.actual_return
                                    
                                    # Update user balance
                                    cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet.user_id))
                                    
                                    # Update bet status
                                    cursor.execute("UPDATE bets SET status = %s, actual_return = %s WHERE id = %s", 
                                                 ('won', bet.actual_return, bet.id))
                                    
                                    # Create transaction record
                                    cursor.execute("""
                                        INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (bet.user_id, bet.id, bet.actual_return, 'win', 
                                         f'💰 Won bet on {bet.match_name} - {bet.selection} (Score: {home_score}-{away_score})', 
                                         balance_before, balance_after, datetime.now()))
                                    
                                    user = {'id': bet.user_id, 'balance': balance_after}
                                won_count += 1
                                logger.info("💰 Wallet updated u=%s Δ=%.2f new=%.2f bet=%s",
                                            user.id, bet.actual_return, user.balance, bet.id)
                                
                                # Sync Web3 wallet credit (non-blocking)
                                try:
                                    from src.services.web3_sync_service import sync_web3_credit
                                    sync_web3_credit(user.id, bet.actual_return, f"Bet win - {bet.match_name}")
                                except Exception as web3_error:
                                    logger.warning(f"Web3 sync failed for bet win: {web3_error}")
                                
                                # Emit WebSocket balance update event
                                try:
                                    from flask_socketio import emit
                                    emit('bet:settled', {
                                        'user_id': user.id,
                                        'bet_id': bet.id,
                                        'result': 'won',
                                        'payout': bet.actual_return,
                                        'new_balance': user.balance
                                    }, room=f'user_{user.id}')
                                    
                                    # Also emit balance update
                                    emit('balance:update', {
                                        'user_id': user.id,
                                        'balance': user.balance
                                    }, room=f'user_{user.id}')
                                except Exception as e:
                                    logger.warning(f"Failed to emit WebSocket events: {e}")
                        else:
                            # Bet lost
                            bet.status = 'lost'
                            bet.actual_return = 0.0
                            lost_count += 1
                            logger.info(f"❌ User LOST bet {bet.id} on {bet.match_name}")
                            
                            # Emit WebSocket balance update event for lost bet
                            try:
                                from flask_socketio import emit
                                # Get user balance using tracked connection
                                with connection_ctx(timeout=3) as conn:
                                    with conn.cursor() as cursor:
                                        cursor.execute("SELECT id, balance FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                                        user_row = cursor.fetchone()
                                        if user_row:
                                            emit('bet:settled', {
                                                'user_id': user_row['id'],
                                                'bet_id': bet.id,
                                                'result': 'lost',
                                                'payout': 0,
                                                'new_balance': user_row['balance']
                                            }, room=f'user_{bet.user_id}')
                            except Exception as e:
                                logger.warning(f"Failed to emit WebSocket events: {e}")
                        
                        bet.settled_at = datetime.utcnow()
                        settled_count += 1
                    
                except Exception as e:
                    logger.error(f"Error auto-settling bet {bet.id}: {e}")
                    # No rollback needed - connection_ctx handles transactions
                    continue
            
            # No commit needed - connection_ctx handles transactions
            pass
            
            # Update total_revenue for all affected operators
            self._update_operator_revenues(bets)
            
            logger.info(f"🎉 Auto-settlement complete: {settled_count} bets settled ({won_count} won, {lost_count} lost)")
                    
        except Exception as e:
            logger.error(f"Error auto-settling bets for match: {e}")
            # No rollback needed - connection_ctx handles transactions
    
    def _auto_void_bets_for_match(self, match_event, bets):
        """Automatically void bets for a cancelled match"""
        try:
            logger.info(f"🔄 Auto-voiding bets for cancelled match: {match_event['home_team']} vs {match_event['away_team']}")
            
            voided_count = 0
            
            # Run within Flask app context
            if self.app:
                with self.app.app_context():
                    for bet in bets:
                        try:
                            if bet.bet_type == 'combo':
                                # Handle combo bet voiding
                                self._void_combo_bet(bet, match_event)
                                voided_count += 1
                            else:
                                # Handle single bet voiding
                                # Return stake to user using tracked connection
                                from src.db_compat import connection_ctx
                                with connection_ctx(timeout=5) as conn:
                                    with conn.transaction():
                                        # Get user current balance
                                        cursor.execute("SELECT balance FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                                        user_row = cursor.fetchone()
                                        if user_row:
                                            balance_before = user_row['balance'] or 0
                                            balance_after = balance_before + bet.stake  # Return the stake
                                            
                                            # Update user balance
                                            cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet.user_id))
                                            
                                            # Update bet status
                                            cursor.execute("UPDATE bets SET status = %s WHERE id = %s", ('void', bet.id))
                                            
                                            # Create transaction record
                                            cursor.execute("""
                                                INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                            """, (bet.user_id, bet.id, bet.stake, 'void',
                                                 f'🔄 Voided bet on {bet.match_name} - {bet.selection} (Match cancelled)',
                                                 balance_before, balance_after, datetime.now()))
                                            
                                            user = {'id': bet.user_id, 'balance': balance_after}
                                    logger.info("💰 Wallet updated u=%s Δ=%.2f new=%.2f bet=%s (void)",
                                                user.id, bet.stake, user.balance, bet.id)
                                    
                                    # Emit WebSocket balance update event for voided bet
                                    try:
                                        from flask_socketio import emit
                                        emit('bet:settled', {
                                            'user_id': user.id,
                                            'bet_id': bet.id,
                                            'result': 'void',
                                            'payout': bet.stake,
                                            'new_balance': user.balance
                                        }, room=f'user_{user.id}')
                                        
                                        # Also emit balance update
                                        emit('balance:update', {
                                            'user_id': user.id,
                                            'balance': user.balance
                                        }, room=f'user_{user.id}')
                                    except Exception as e:
                                        logger.warning(f"Failed to emit WebSocket events: {e}")
                                
                                bet.status = 'void'
                                bet.actual_return = bet.stake  # Return stake
                                bet.settled_at = datetime.utcnow()
                                voided_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error auto-voiding bet {bet.id}: {e}")
                            # No rollback needed - connection_ctx handles transactions
                            continue
                
                # No commit needed - connection_ctx handles transactions
                pass
                logger.info(f"🔄 Auto-void complete: {voided_count} bets voided")
            else:
                logger.error("❌ No Flask app instance available for database access")
                return
                    
        except Exception as e:
            logger.error(f"Error auto-voiding bets for match: {e}")
            # No rollback needed - connection_ctx handles transactions
    
    def _void_combo_bet(self, bet, match_event):
        """Void a combo bet when one of its matches is cancelled"""
        try:
            import json
            
            # Parse combo selections
            if not bet.combo_selections:
                logger.warning(f"Combo bet {bet.id} has no selections data")
                return
            
            selections = json.loads(bet.combo_selections)
            current_match_id = match_event.get('id')
            
            # Find the current match in the combo selections
            current_selection = None
            for selection in selections:
                if selection.get('match_id') == current_match_id:
                    current_selection = selection
                    break
            
            if not current_selection:
                logger.info(f"Match {current_match_id} not found in combo bet {bet.id} selections")
                return
            
            # Mark this selection as voided
            current_selection['result'] = 'void'
            current_selection['settled'] = True
            current_selection['settled_at'] = datetime.utcnow().isoformat()
            current_selection['void_reason'] = 'match_cancelled'
            
            # If any selection is voided, the entire combo bet is voided
            bet.status = 'void'
            bet.actual_return = bet.stake  # Return full stake
            bet.settled_at = datetime.utcnow()
            bet.combo_selections = json.dumps(selections)
            
            # Return stake to user - EXPLICIT WALLET UPDATE
            # Get user and update balance using tracked connection
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=5) as conn:
                with conn.transaction():
                    # Get user current balance
                    cursor.execute("SELECT balance FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                    user_row = cursor.fetchone()
                    if user_row:
                        balance_before = user_row['balance'] or 0
                        balance_after = balance_before + bet.stake
                        
                        # Update user balance
                        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet.user_id))
                        
                        # Update bet status
                        cursor.execute("UPDATE bets SET status = %s, actual_return = %s, settled_at = %s, combo_selections = %s WHERE id = %s",
                                     ('void', bet.stake, bet.settled_at, bet.combo_selections, bet.id))
                        
                        # Create transaction record
                        cursor.execute("""
                            INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (bet.user_id, bet.id, bet.stake, 'combo_void',
                             '🔄 Combo bet voided - match cancelled',
                             balance_before, balance_after, datetime.now()))
                        
                        user = {'id': bet.user_id, 'balance': balance_after}
                logger.info("💰 Wallet updated u=%s Δ=%.2f new=%.2f bet=%s (combo void)",
                            user.id, bet.stake, user.balance, bet.id)
            
        except Exception as e:
            logger.error(f"Error voiding combo bet {bet.id}: {e}")
    
    def _settle_combo_bet(self, bet, match_event, home_score, away_score):
        """Settle a combo bet by checking if all selections are complete"""
        try:
            import json
            
            # Parse combo selections
            if not bet.combo_selections:
                logger.warning(f"Combo bet {bet.id} has no selections data")
                return
            
            selections = json.loads(bet.combo_selections)
            current_match_id = match_event.get('id')
            
            # Find the current match in the combo selections
            current_selection = None
            for selection in selections:
                if selection.get('match_id') == current_match_id:
                    current_selection = selection
                    break
            
            if not current_selection:
                logger.info(f"Match {current_match_id} not found in combo bet {bet.id} selections")
                return
            
            # Check if this selection won
            selection_won = self._determine_combo_selection_outcome(current_selection, match_event, home_score, away_score)
            
            # Update the selection result in the combo bet
            current_selection['result'] = 'won' if selection_won else 'lost'
            current_selection['settled'] = True
            current_selection['settled_at'] = datetime.utcnow().isoformat()
            
            # Check if all selections are now settled
            all_settled = all(selection.get('settled', False) for selection in selections)
            
            if all_settled:
                # All selections are settled - determine final combo bet outcome
                all_won = all(selection.get('result') == 'won' for selection in selections)
                
                if all_won:
                    # Combo bet won - all selections won
                    bet.status = 'won'
                    bet.actual_return = bet.potential_return
                    
                    # Update user balance using tracked connection
                    from src.db_compat import connection_ctx
                    with connection_ctx(timeout=5) as conn:
                        with conn.transaction():
                            # Get user current balance
                            cursor.execute("SELECT balance, username FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                            user_row = cursor.fetchone()
                            if user_row:
                                balance_before = user_row['balance'] or 0
                                balance_after = balance_before + bet.actual_return
                                
                                # Update user balance
                                cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet.user_id))
                                
                                # Update bet status
                                cursor.execute("UPDATE bets SET status = %s, actual_return = %s WHERE id = %s",
                                             ('won', bet.actual_return, bet.id))
                                
                                # Create transaction record
                                cursor.execute("""
                                    INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, (bet.user_id, bet.id, bet.actual_return, 'combo_win',
                                     f'🎯 Combo bet WON! {len(selections)} selections all correct',
                                     balance_before, balance_after, datetime.now()))
                                
                                user = {'id': bet.user_id, 'balance': balance_after, 'username': user_row['username']}
                        logger.info(f"🎯 User {user.username} WON combo bet {bet.id} - ${bet.actual_return}")
                else:
                    # Combo bet lost - at least one selection lost
                    bet.status = 'lost'
                    bet.actual_return = 0.0
                    logger.info(f"❌ Combo bet {bet.id} LOST - not all selections won")
                
                bet.settled_at = datetime.utcnow()
                bet.combo_selections = json.dumps(selections)  # Update with results
                
                # UPDATE WALLET BALANCE FOR COMBO BET (already done above)
                try:
                    # Balance already updated in the tracked connection block above
                    pass
                    
                    # Emit WebSocket balance update event (only if in app context)
                    try:
                        from flask import current_app
                        if current_app:
                            from src.main import socketio
                            socketio.emit('balance:update', {
                                'user_id': user.id,
                                'balance': user.balance
                            }, to=f'user_{user.id}', namespace='/')
                    except Exception as e:
                        logger.warning(f"Failed to emit WebSocket events: {e}")
                    
                    # No commit needed - connection_ctx handles transactions
                    pass
                    
                except Exception as e:
                    logger.error(f"Error updating wallet for combo bet {bet.id}: {e}")
                    # No rollback needed - connection_ctx handles transactions
                
                logger.info(f"🎯 Combo bet {bet.id} fully settled: {'WON' if all_won else 'LOST'}")
            else:
                # Not all selections settled yet - update the combo bet with current progress
                bet.combo_selections = json.dumps(selections)
                logger.info(f"🎯 Combo bet {bet.id} selection {current_match_id} settled: {'WON' if selection_won else 'LOST'}")
            
        except Exception as e:
            logger.error(f"Error settling combo bet {bet.id}: {e}")
    
    def _determine_combo_selection_outcome(self, selection, match_event, home_score, away_score):
        """Determine if a combo bet selection won"""
        try:
            # Use cricket-specific logic if this is a cricket match
            if match_event.get('sport') == 'cricket':
                winner = match_event.get('winner')
                if not winner:
                    return False
                
                selection_type = selection.get('selection', '').lower()
                
                # Map bet selections to winners
                if selection_type in ['1', 'home', match_event['home_team'].lower()]:
                    return winner == 'home'
                elif selection_type in ['2', 'away', match_event['away_team'].lower()]:
                    return winner == 'away'
                elif selection_type in ['x', 'draw', 'tie']:
                    return winner == 'draw'
                else:
                    return False
            
            selection_type = selection.get('selection', '')
            match_event_id = match_event.get('id')
            
            # For match result selections (1, X, 2)
            if selection_type in ['1', 'X', '2']:
                # Determine winner
                if home_score > away_score:
                    winner = '1'  # Home win
                elif home_score < away_score:
                    winner = '2'  # Away win
                else:
                    winner = 'X'  # Draw
                
                return selection_type == winner
            
            # For team selections (e.g., "Team A")
            elif selection_type:
                home_team = match_event.get('home_team', '')
                away_team = match_event.get('away_team', '')
                
                if selection_type == home_team:
                    return home_score > away_score
                elif selection_type == away_team:
                    return away_score > home_score
                else:
                    # Check if selection is a draw prediction
                    if 'draw' in selection_type.lower() or 'x' in selection_type.lower():
                        return home_score == away_score
            
            return False
            
        except Exception as e:
            logger.error(f"Error determining combo selection outcome: {e}")
            return False
    
    def _determine_bet_outcome(self, bet, match_event, home_score, away_score):
        """Determine if a bet won based on match result"""
        try:
            # Use cricket-specific logic if this is a cricket match
            if match_event.get('sport') == 'cricket':
                return self._determine_cricket_bet_outcome(bet, match_event)
            
            selection = bet.selection.lower()
            home_team = match_event['home_team'].lower()
            away_team = match_event['away_team'].lower()
            
            # Determine match result
            if home_score > away_score:
                match_result = 'home_win'
            elif away_score > home_score:
                match_result = 'away_win'
            else:
                match_result = 'draw'
            
            # Check bet selection against match result
            if selection == home_team or selection == '1':
                return match_result == 'home_win'
            elif selection == away_team or selection == '2':
                return match_result == 'away_win'
            elif selection == 'draw' or selection == 'x':
                return match_result == 'draw'
            else:
                # For other bet types (goals, etc.), we'd need more complex logic
                logger.warning(f"Unknown bet selection: {selection}")
                return False
                
        except Exception as e:
            logger.error(f"Error determining bet outcome: {e}")
            return False
    
    def force_settle_match(self, match_name):
        """Force settlement for a specific match (for testing)"""
        try:
            pending_bets = Bet.query.filter(
                and_(
                    Bet.status == 'pending',
                    Bet.match_name == match_name
                )
            ).all()
            
            if pending_bets:
                logger.info(f"🔧 Force settling {len(pending_bets)} bets for {match_name}")
                
                # Get historical events to check for completed matches
                historical_events = []
                for days_ago in range(1, 8):  # Check last 7 days
                    try:
                        endpoint = f'soccernew/d-{days_ago}'
                        historical_data = self.client._make_request(endpoint, use_cache=False)
                        if historical_data:
                            matches = self.client._extract_matches_from_goalserve_data(historical_data)
                            for match in matches:
                                # Parse match into event format for settlement (include completed matches)
                                event = self._parse_match_for_settlement(match, 'soccer', endpoint)
                                if event:
                                    historical_events.append(event)
                    except Exception as e:
                        logger.warning(f"Error fetching historical data for d-{days_ago}: {e}")
                        continue
                
                self._check_match_completion(match_name, pending_bets, historical_events)
            else:
                logger.info(f"No pending bets found for {match_name}")
                
        except Exception as e:
            logger.error(f"Error force settling match {match_name}: {e}")
    
    def get_settlement_stats(self):
        """Get comprehensive settlement service statistics"""
        try:
            stats = {
                'service_running': self.running,
                'check_interval': self.check_interval,
                'total_checks': self.total_checks,
                'successful_settlements': self.successful_settlements,
                'failed_settlements': self.failed_settlements,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'last_error': self.last_error,
                'uptime_seconds': (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0,
                'success_rate': (self.successful_settlements / max(self.total_checks, 1)) * 100 if self.total_checks > 0 else 0
            }
            
            # Add pending bets count
            try:
                from src.models.betting import Bet
                pending_count = Bet.query.filter_by(status='pending').count()
                stats['pending_bets'] = pending_count
            except Exception as e:
                stats['pending_bets'] = 'Error getting count'
                stats['pending_bets_error'] = str(e)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting settlement stats: {e}")
            return {
                'error': str(e),
                'service_running': self.running,
                'check_interval': self.check_interval
            }
    
    def _parse_match_for_settlement(self, match, sport_name, endpoint):
        """Parse a match for settlement purposes - includes completed matches"""
        try:
            # DEBUG: Log the raw match data for baseball matches
            if sport_name == 'baseball':
                logger.debug(f"🔍 DEBUG: Parsing baseball match from {endpoint}: {match.get('@id', 'unknown')} - {match.get('localteam', {}).get('@name', 'unknown')} vs {match.get('awayteam', {}).get('@name', 'unknown')}")
            
            # Extract team names
            home_team = (match.get('localteam', {}).get('@name') or 
                        match.get('localteam', {}).get('name', 'Unknown Home'))
            away_team = (match.get('awayteam', {}).get('@name') or 
                        match.get('awayteam', {}).get('name', 'Unknown Away'))
            
            # Fallback for soccer structure (visitorteam)
            if away_team == 'Unknown Away':
                away_team = (match.get('visitorteam', {}).get('@name') or 
                           match.get('visitorteam', {}).get('name', 'Unknown Away'))
            
            if not home_team or not away_team or home_team == 'Unknown Home' or away_team == 'Unknown Away':
                return None
            
            # Extract time and status
            time_str = match.get('@time', '') or match.get('@status', '') or 'TBD'
            date_str = match.get('@date', '') or match.get('@formatted_date', '') or datetime.now().strftime('%b %d')
            status = match.get('@status', time_str)
            
            # DEBUG: Log status for baseball matches
            if sport_name == 'baseball':
                logger.debug(f"🔍 DEBUG: Baseball match status: '{status}' from endpoint {endpoint}")
            
            # Determine match status for settlement - SPORT-SPECIFIC
            is_completed = False
            is_cancelled = False
            
            # Baseball-specific statuses
            if sport_name == 'baseball':
                if status.lower() in ["finished", "final", "game over", "complete", "completed"]:
                    is_completed = True
                    logger.info(f"✅ Baseball match marked as completed: {home_team} vs {away_team}")
                elif status in ["Cancl.", "Postp.", "WO", "Cancelled", "Postponed"]:
                    is_cancelled = True
            else:
                # Soccer/football statuses
                if status == "FT" or status == "90" or status == "120":
                    is_completed = True
                elif status.isdigit():
                    status_code = int(status)
                    if status_code > 90:  # Over 90 minutes indicates completed
                        is_completed = True
                elif status in ["Cancl.", "Postp.", "WO"]:
                    is_cancelled = True
            
            # Extract scores - ENHANCED for baseball
            home_score = None
            away_score = None
            
            if sport_name == 'baseball':
                # Try multiple possible score locations for baseball
                localteam = match.get('localteam', {})
                awayteam = match.get('awayteam', {})
                
                # DEBUG: Log the team data structures
                logger.debug(f"🔍 DEBUG: Baseball localteam structure: {localteam.get('@name', 'unknown')} - score: {localteam.get('@totalscore', 'unknown')}")
                logger.debug(f"🔍 DEBUG: Baseball awayteam structure: {awayteam.get('@name', 'unknown')} - score: {awayteam.get('@totalscore', 'unknown')}")
                
                # Try various score fields
                home_score = (localteam.get('@goals') or 
                             localteam.get('@totalscore') or
                             localteam.get('goals') or
                             localteam.get('totalscore') or
                             localteam.get('runs') or
                             localteam.get('score') or
                             localteam.get('points'))
                
                away_score = (awayteam.get('@goals') or 
                             awayteam.get('@totalscore') or
                             awayteam.get('goals') or
                             awayteam.get('totalscore') or
                             awayteam.get('runs') or
                             awayteam.get('score') or
                             awayteam.get('points'))
                
                logger.debug(f"🔍 DEBUG: Baseball scores extracted - home: '{home_score}', away: '{away_score}'")
            else:
                # Original logic for other sports
                home_score = (match.get('localteam', {}).get('@goals') or 
                             match.get('localteam', {}).get('@totalscore') or
                             match.get('localteam', {}).get('goals') or
                             match.get('localteam', {}).get('totalscore', '0'))
                away_score = (match.get('awayteam', {}).get('@goals') or 
                             match.get('awayteam', {}).get('@totalscore') or
                             match.get('awayteam', {}).get('goals') or
                             match.get('awayteam', {}).get('totalscore', '0'))
                
                # Fallback for soccer structure (visitorteam)
                if away_score == '0':
                    away_score = (match.get('visitorteam', {}).get('@goals') or 
                                match.get('visitorteam', {}).get('@totalscore') or
                                match.get('visitorteam', {}).get('goals') or
                                match.get('visitorteam', {}).get('totalscore', '0'))
            
            # Convert scores to integers
            try:
                home_score = int(home_score) if home_score and home_score != '?' else 0
                away_score = int(away_score) if away_score and away_score != '?' else 0
            except (ValueError, TypeError):
                home_score = 0
                away_score = 0
            
            # DEBUG: Log final scores for baseball
            if sport_name == 'baseball':
                logger.debug(f"🔍 DEBUG: Final baseball scores - home: {home_score}, away: {away_score}")
            
            # Extract match ID
            match_id = match.get('@id', f"{sport_name}_{hash(f'{home_team}_{away_team}_{time_str}')}")
            
            # Create event object
            event = {
                'id': match_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'status': status,
                'time': time_str,
                'date': date_str,
                'is_completed': is_completed,
                'is_cancelled': is_cancelled,
                'match_name': f"{home_team} vs {away_team}",
                'sport': sport_name,  # Add sport for score extraction
                'category': match.get('@category', '')  # Add category for debugging
            }
            
            return event
            
        except Exception as e:
            logger.error(f"Error parsing match for settlement: {e}")
            return None
    
    def _update_operator_revenues(self, bets):
        """Update total_revenue field for all operators affected by the settled bets"""
        try:
            # Get unique operator IDs from the settled bets
            affected_operators = set()
            for bet in bets:
                # Get the user's operator ID using tracked connection
                from src.db_compat import connection_ctx
                with connection_ctx(timeout=3) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT sportsbook_operator_id FROM users WHERE id = %s LIMIT 1", (bet.user_id,))
                        user_row = cursor.fetchone()
                        if user_row and user_row['sportsbook_operator_id']:
                            affected_operators.add(user_row['sportsbook_operator_id'])
            
            # Update revenue for each affected operator
            for operator_id in affected_operators:
                self._update_operator_revenue(operator_id)
                
        except Exception as e:
            logger.error(f"Error updating operator revenues: {e}")
    
    def _calculate_casino_revenue(self, operator_id):
        """Calculate casino revenue from game_round table for a specific operator"""
        try:
            casino_query = """
            SELECT 
                SUM(gr.stake) as total_stakes,
                SUM(gr.payout) as total_payouts
            FROM game_round gr
            JOIN users u ON gr.user_id = u.id::text
            WHERE u.sportsbook_operator_id = :operator_id
            """
            
            # Execute using tracked connection
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            SUM(gr.stake) as total_stakes,
                            SUM(gr.payout) as total_payouts
                        FROM game_round gr
                        JOIN users u ON gr.user_id = u.id::text
                        WHERE u.sportsbook_operator_id = %s
                    """, (operator_id,))
                    result = cursor.fetchone()
            
            total_stakes = float(result[0] or 0)
            total_payouts = float(result[1] or 0)
            
            # Casino revenue = Money kept from losing games - Money paid to winners
            casino_revenue = total_stakes - total_payouts
            
            return casino_revenue
            
        except Exception as e:
            logger.error(f"Error calculating casino revenue for operator {operator_id}: {e}")
            return 0.0

    def _calculate_sportsbook_revenue(self, operator_id):
        """Calculate sportsbook revenue from bets table for a specific operator"""
        try:
            sportsbook_query = """
            SELECT 
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
            FROM bets b
            JOIN users u ON b.user_id = u.id
            WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = :operator_id
            """
            
            # Execute using tracked connection
            with connection_ctx(timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
                            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
                        FROM bets b
                        JOIN users u ON b.user_id = u.id
                        WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = %s
                    """, (operator_id,))
                    result = cursor.fetchone()
            
            total_stakes_lost = float(result[0] or 0)
            total_net_payouts = float(result[1] or 0)
            
            # Sportsbook revenue = Money kept from losing bets - Extra money paid to winners
            sportsbook_revenue = total_stakes_lost - total_net_payouts
            
            return sportsbook_revenue
            
        except Exception as e:
            logger.error(f"Error calculating sportsbook revenue for operator {operator_id}: {e}")
            return 0.0

    def _update_operator_revenue(self, operator_id):
        """Update the total_revenue field for a specific operator based on both sportsbook and casino revenue"""
        try:
            from src.models.multitenant_models import SportsbookOperator
            
            # Calculate sportsbook revenue
            sportsbook_revenue = self._calculate_sportsbook_revenue(operator_id)
            
            # Calculate casino revenue
            casino_revenue = self._calculate_casino_revenue(operator_id)
            
            # Combined total revenue
            total_revenue = sportsbook_revenue + casino_revenue
            
            # Update the operator's total_revenue field using tracked connection
            with connection_ctx(timeout=5) as conn:
                with conn.transaction():
                    cursor.execute("UPDATE sportsbook_operators SET total_revenue = %s WHERE id = %s", (total_revenue, operator_id))
                    cursor.execute("SELECT id FROM sportsbook_operators WHERE id = %s LIMIT 1", (operator_id,))
                    operator_found = cursor.fetchone()
                    
                    if operator_found:
                        logger.info(f"✅ Updated operator {operator_id} total_revenue to: {total_revenue}")
                        logger.info(f"   📊 Sportsbook: ${sportsbook_revenue:.2f}, 🎰 Casino: ${casino_revenue:.2f}")
                    else:
                        logger.warning(f"Operator {operator_id} not found for revenue update")
                
        except Exception as e:
            logger.error(f"❌ Error updating operator {operator_id} revenue: {e}")
            # No rollback needed - connection_ctx handles transactions
    
    def _get_cricket_historical_events(self):
        """Get cricket historical events from the cricket/livescore feed"""
        try:
            logger.info("🏏 Fetching cricket historical events from cricket/livescore feed")
            
            # Use the special cricket feed URL
            cricket_url = f"{self.client.base_url}/{self.client.access_token}/cricket/livescore"
            
            response = self.client.session.get(cricket_url, timeout=self.client.timeout)
            response.raise_for_status()
            
            # Parse the XML response
            cricket_data = robust_goalserve_parse(response.text, response.headers.get('content-type', ''))
            if not cricket_data:
                logger.warning("Failed to parse cricket XML data")
                return []
            
            events = []
            
            # Extract matches from cricket data structure
            if 'scores' in cricket_data and 'category' in cricket_data['scores']:
                categories = cricket_data['scores']['category']
                if not isinstance(categories, list):
                    categories = [categories]
                
                for category in categories:
                    if 'match' in category:
                        matches = category['match']
                        if not isinstance(matches, list):
                            matches = [matches]
                        
                        for match in matches:
                            event = self._parse_cricket_match_for_settlement(match, category.get('@name', 'Unknown'))
                            if event:
                                events.append(event)
            
            logger.info(f"🏏 Found {len(events)} cricket events for settlement")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching cricket historical events: {e}")
            return []
    
    def _parse_cricket_match_for_settlement(self, match, category_name):
        """Parse a cricket match from the cricket/livescore feed for settlement"""
        try:
            # Extract basic match info
            match_id = match.get('@id', '')
            home_team = match.get('localteam', {}).get('@name', 'Unknown Home')
            away_team = match.get('visitorteam', {}).get('@name', 'Unknown Away')
            status = match.get('@status', '')
            match_type = match.get('@type', '')
            venue = match.get('@venue', '')
            
            # Determine if match is completed
            is_completed = status.lower() in ['finished', 'completed', 'result']
            is_cancelled = status.lower() in ['cancelled', 'postponed', 'abandoned']
            
            # Extract scores from cricket-specific structure
            home_score = self._extract_cricket_score(match.get('localteam', {}))
            away_score = self._extract_cricket_score(match.get('visitorteam', {}))
            
            # Determine winner based on cricket rules
            winner = self._determine_cricket_winner(match, home_score, away_score)
            
            # Create event object for settlement
            event = {
                'id': match_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'status': status,
                'is_completed': is_completed,
                'is_cancelled': is_cancelled,
                'match_name': f"{home_team} vs {away_team}",
                'sport': 'cricket',
                'category': category_name,
                'match_type': match_type,
                'venue': venue,
                'winner': winner,  # 'home', 'away', 'draw', or None
                'raw_match_data': match  # Store raw data for detailed analysis
            }
            
            logger.debug(f"🏏 Parsed cricket match: {home_team} vs {away_team} - Status: {status}, Winner: {winner}")
            return event
            
        except Exception as e:
            logger.error(f"Error parsing cricket match for settlement: {e}")
            return None
    
    def _extract_cricket_score(self, team_data):
        """Extract score from cricket team data"""
        try:
            # Try different score fields that might be present
            score_fields = ['@totalscore', '@goals', 'totalscore', 'goals', 'runs', 'score']
            
            for field in score_fields:
                score = team_data.get(field)
                if score and score != '?':
                    # Extract numeric part from score string (e.g., "607/7d" -> 607)
                    if isinstance(score, str) and '/' in score:
                        score = score.split('/')[0]
                    try:
                        return int(score)
                    except (ValueError, TypeError):
                        continue
            
            return 0
        except Exception as e:
            logger.debug(f"Error extracting cricket score: {e}")
            return 0
    
    def _determine_cricket_winner(self, match, home_score, away_score):
        """Determine winner of cricket match based on cricket rules"""
        try:
            status = match.get('@status', '').lower()
            
            # Check if match is finished
            if status not in ['finished', 'completed', 'result']:
                return None
            
            # Check for explicit winner in match data
            localteam = match.get('localteam', {})
            visitorteam = match.get('visitorteam', {})
            
            local_winner = localteam.get('@winner', '').lower()
            visitor_winner = visitorteam.get('@winner', '').lower()
            
            if local_winner == 'true':
                return 'home'
            elif visitor_winner == 'true':
                return 'away'
            
            # Check comment for winner info
            comment = match.get('comment', {})
            if isinstance(comment, dict):
                comment_text = comment.get('@post', '').lower()
                if home_score > away_score and 'won' in comment_text:
                    return 'home'
                elif away_score > home_score and 'won' in comment_text:
                    return 'away'
                elif 'draw' in comment_text or 'tie' in comment_text:
                    return 'draw'
            
            # Fallback to score comparison (though this might not be accurate for cricket)
            if home_score > away_score:
                return 'home'
            elif away_score > home_score:
                return 'away'
            else:
                return 'draw'
                
        except Exception as e:
            logger.error(f"Error determining cricket winner: {e}")
            return None
    
    def _determine_cricket_bet_outcome(self, bet, match_event):
        """Determine if a cricket bet won based on match result"""
        try:
            selection = bet.selection.lower()
            winner = match_event.get('winner')
            
            if not winner:
                logger.warning(f"Cricket match {match_event.get('id')} has no determined winner")
                return False
            
            # Map bet selections to winners
            if selection in ['1', 'home', match_event['home_team'].lower()]:
                return winner == 'home'
            elif selection in ['2', 'away', match_event['away_team'].lower()]:
                return winner == 'away'
            elif selection in ['x', 'draw', 'tie']:
                return winner == 'draw'
            else:
                logger.warning(f"Unknown cricket bet selection: {selection}")
                return False
                
        except Exception as e:
            logger.error(f"Error determining cricket bet outcome: {e}")
            return False 

if __name__ == "__main__":
    """Entry point for running the bet settlement service as a standalone worker"""
    logger.info("🚀 Starting Bet Settlement Service Worker...")
    
    try:
        # Create and start the service
        service = BetSettlementService()
        service.start()
        
        # Keep the service running
        logger.info("✅ Bet Settlement Service started successfully")
        
        # Wait for keyboard interrupt to stop
        try:
            import eventlet
            while service.running:
                eventlet.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal...")
            service.stop()
            logger.info("✅ Bet Settlement Service stopped")
            
    except Exception as e:
        logger.error(f"❌ Failed to start Bet Settlement Service: {e}")
        raise