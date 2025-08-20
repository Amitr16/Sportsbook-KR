import threading
import time
import json
from datetime import datetime, timedelta
from src.goalserve_client import OptimizedGoalServeClient
from src.models.betting import db, Bet, User, Transaction
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)

class BetSettlementService:
    def __init__(self, app=None):
        self.client = OptimizedGoalServeClient()
        self.app = app  # Store Flask app instance
        self.running = False
        self.settlement_thread = None
        self.check_interval = 30  # Check every 30 seconds for completed matches
        self.last_check_time = None
        self.total_checks = 0
        self.successful_settlements = 0
        self.failed_settlements = 0
        self.last_error = None
        self.start_time = None
        
    def start(self):
        """Start the automatic bet settlement service"""
        if not self.running:
            try:
                self.running = True
                self.start_time = datetime.utcnow()
                self.settlement_thread = threading.Thread(target=self._settlement_loop, daemon=True)
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
        """Stop the automatic bet settlement service"""
        self.running = False
        if self.settlement_thread:
            self.settlement_thread.join()
        logger.info("Automatic bet settlement service stopped")
    
    def _settlement_loop(self):
        """Main settlement loop that automatically settles bets when matches end"""
        logger.info("🔄 Settlement service loop started")
        
        while self.running:
            try:
                self.last_check_time = datetime.utcnow()
                self.total_checks += 1
                
                logger.info(f"🔍 Settlement check #{self.total_checks} - {self.last_check_time.strftime('%H:%M:%S')}")
                logger.info(f"📊 Current stats - Running: {self.running}, Checks: {self.total_checks}")
                
                # Check if we can access the database
                try:
                    if self.app:
                        with self.app.app_context():
                            pending_count = Bet.query.filter_by(status='pending').count()
                            logger.info(f"📋 Found {pending_count} pending bets in database")
                    else:
                        logger.warning("⚠️ No Flask app instance available for database access")
                except Exception as db_error:
                    logger.error(f"❌ Database access error: {db_error}")
                
                self.check_for_completed_matches()
                
                # Log periodic status
                if self.total_checks % 10 == 0:  # Every 10 checks (5 minutes)
                    logger.info(f"📊 Settlement Service Stats: {self.total_checks} checks, {self.successful_settlements} settlements, {self.failed_settlements} failures")
                
                logger.info(f"✅ Settlement check #{self.total_checks} completed successfully")
                
            except Exception as e:
                self.failed_settlements += 1
                self.last_error = str(e)
                logger.error(f"❌ CRITICAL ERROR in automatic settlement loop: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.exception("Full exception details:")
                
                # Don't let the service crash - continue running
                logger.info("🔄 Continuing settlement service despite error...")
            
            logger.info(f"⏰ Sleeping for {self.check_interval} seconds...")
            time.sleep(self.check_interval)
        
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
                logger.info(f"  Bet {i+1}: ID={bet.id}, Match={bet.match_name}, Sport={bet.sport_name}, Match_ID={bet.match_id}")
            
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
            if bet.sport_name:
                sports_to_check.add(bet.sport_name)
            else:
                # Fallback to match name analysis (for legacy bets)
                match_name = bet.match_name.lower()
                
                # Determine sport from match name patterns
                if any(team in match_name for team in ['marines', 'hawks', 'dragons', 'tigers', 'eagles', 'buffaloes', 'giants', 'swallows', 'carp', 'baystars', 'lions', 'fighters', 'orix']):
                    sports_to_check.add('baseball')
                elif any(team in match_name for team in ['lakers', 'warriors', 'celtics', 'bulls', 'heat', 'knicks', 'nets', 'raptors', 'mavericks', 'rockets', 'spurs', 'thunder']):
                    sports_to_check.add('bsktbl')
                elif any(team in match_name for team in ['united', 'city', 'arsenal', 'chelsea', 'liverpool', 'barcelona', 'real madrid', 'bayern', 'psg', 'juventus', 'milan', 'inter']):
                    sports_to_check.add('soccer')
                elif any(team in match_name for team in ['patriots', 'cowboys', 'packers', 'steelers', '49ers', 'chiefs', 'bills', 'ravens', 'eagles', 'giants', 'jets']):
                    sports_to_check.add('football')
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
            
            # Find the match in current events by match ID
            match_event = None
            for event in events:
                if event.get('id') == match_id:
                    match_event = event
                    break
            
            if not match_event:
                logger.info(f"Match with ID {match_id} not found in current events: {match_name}")
                # Try to find in historical data
                match_event = self._find_match_in_historical_data(match_id, match_name, bets[0].sport_name if bets else None)
                if not match_event:
                    logger.warning(f"Match with ID {match_id} not found in historical data either: {match_name}")
                    return
            
            # Check if match is completed
            is_completed = match_event.get('is_completed', False)
            is_cancelled = match_event.get('is_cancelled', False)
            
            # Also check status field for completion indicators
            status = match_event.get('status', '')
            if status in ['FT', '90', '120'] or (status.isdigit() and int(status) > 90):
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
            home_score = int(match_event.get('home_score', 0))
            away_score = int(match_event.get('away_score', 0))
            
            logger.info(f"🏁 Auto-settling bets for {match_event['home_team']} vs {match_event['away_team']} - Final Score: {home_score}-{away_score}")
            
            settled_count = 0
            won_count = 0
            lost_count = 0
            
            # Process each bet (already within Flask app context)
            for bet in bets:
                try:
                    # Re-query the bet in the current session to ensure it's persistent
                    bet = Bet.query.get(bet.id)
                    if not bet:
                        logger.warning(f"Bet {bet.id} not found in current session, skipping")
                        continue
                    
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
                            
                            # Update user balance
                            user = User.query.get(bet.user_id)
                            if user:
                                balance_before = user.balance
                                user.balance += bet.actual_return
                                balance_after = user.balance
                                
                                # Create transaction record
                                transaction = Transaction(
                                    user_id=bet.user_id,
                                    bet_id=bet.id,
                                    amount=bet.actual_return,
                                    transaction_type='win',
                                    description=f'💰 Won bet on {bet.match_name} - {bet.selection} (Score: {home_score}-{away_score})',
                                    balance_before=balance_before,
                                    balance_after=balance_after
                                )
                                
                                db.session.add(transaction)
                                won_count += 1
                                logger.info(f"✅ User {user.username} WON ${bet.actual_return} on bet {bet.id}")
                        else:
                            # Bet lost
                            bet.status = 'lost'
                            bet.actual_return = 0.0
                            lost_count += 1
                            logger.info(f"❌ User LOST bet {bet.id} on {bet.match_name}")
                        
                        bet.settled_at = datetime.utcnow()
                        settled_count += 1
                    
                except Exception as e:
                    logger.error(f"Error auto-settling bet {bet.id}: {e}")
                    db.session.rollback()
                    continue
            
            # Commit all settlements
            db.session.commit()
            logger.info(f"🎉 Auto-settlement complete: {settled_count} bets settled ({won_count} won, {lost_count} lost)")
                    
        except Exception as e:
            logger.error(f"Error auto-settling bets for match: {e}")
            db.session.rollback()
    
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
                                # Return stake to user
                                user = User.query.get(bet.user_id)
                                if user:
                                    balance_before = user.balance
                                    user.balance += bet.stake  # Return the stake
                                    balance_after = user.balance
                                    
                                    # Create transaction record
                                    transaction = Transaction(
                                        user_id=bet.user_id,
                                        bet_id=bet.id,
                                        amount=bet.stake,
                                        transaction_type='void',
                                        description=f'🔄 Voided bet on {bet.match_name} - {bet.selection} (Match cancelled)',
                                        balance_before=balance_before,
                                        balance_after=balance_after
                                    )
                                    
                                    db.session.add(transaction)
                                    logger.info(f"🔄 User {user.username} refunded ${bet.stake} for voided bet {bet.id}")
                                
                                bet.status = 'void'
                                bet.actual_return = bet.stake  # Return stake
                                bet.settled_at = datetime.utcnow()
                                voided_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error auto-voiding bet {bet.id}: {e}")
                            db.session.rollback()
                            continue
                
                # Commit all void transactions
                db.session.commit()
                logger.info(f"🔄 Auto-void complete: {voided_count} bets voided")
            else:
                logger.error("❌ No Flask app instance available for database access")
                return
                    
        except Exception as e:
            logger.error(f"Error auto-voiding bets for match: {e}")
            db.session.rollback()
    
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
            
            # Return stake to user
            user = User.query.get(bet.user_id)
            if user:
                balance_before = user.balance
                user.balance += bet.stake
                balance_after = user.balance
                
                # Create transaction record
                transaction = Transaction(
                    user_id=bet.user_id,
                    bet_id=bet.id,
                    amount=bet.stake,
                    transaction_type='combo_void',
                    description=f'🔄 Combo bet voided - match cancelled',
                    balance_before=balance_before,
                    balance_after=balance_after
                )
                
                db.session.add(transaction)
                logger.info(f"🔄 User {user.username} refunded ${bet.stake} for voided combo bet {bet.id}")
            
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
                    
                    # Update user balance
                    user = User.query.get(bet.user_id)
                    if user:
                        balance_before = user.balance
                        user.balance += bet.actual_return
                        balance_after = user.balance
                        
                        # Create transaction record
                        transaction = Transaction(
                            user_id=bet.user_id,
                            bet_id=bet.id,
                            amount=bet.actual_return,
                            transaction_type='combo_win',
                            description=f'🎯 Combo bet WON! {len(selections)} selections all correct',
                            balance_before=balance_before,
                            balance_after=balance_after
                        )
                        
                        db.session.add(transaction)
                        logger.info(f"🎯 User {user.username} WON combo bet {bet.id} - ${bet.actual_return}")
                else:
                    # Combo bet lost - at least one selection lost
                    bet.status = 'lost'
                    bet.actual_return = 0.0
                    logger.info(f"❌ Combo bet {bet.id} LOST - not all selections won")
                
                bet.settled_at = datetime.utcnow()
                bet.combo_selections = json.dumps(selections)  # Update with results
                
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
            
            # Determine match status for settlement
            is_completed = False
            is_cancelled = False
            
            if status == "FT" or status == "90" or status == "120":
                is_completed = True
            elif status.isdigit():
                status_code = int(status)
                if status_code > 90:  # Over 90 minutes indicates completed
                    is_completed = True
            elif status in ["Cancl.", "Postp.", "WO"]:
                is_cancelled = True
            
            # Extract scores
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
                home_score = int(home_score) if home_score != '?' else 0
                away_score = int(away_score) if away_score != '?' else 0
            except (ValueError, TypeError):
                home_score = 0
                away_score = 0
            
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
                'match_name': f"{home_team} vs {away_team}"
            }
            
            return event
            
        except Exception as e:
            logger.error(f"Error parsing match for settlement: {e}")
            return None 