"""
Betting API routes for sports betting platform
"""

from flask import Blueprint, request, jsonify, g
from src.models.betting import db, User, Bet, Transaction
from src.routes.auth import token_required
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

def determine_sport_from_match_name(match_name):
    """Determine sport from match name patterns"""
    if not match_name:
        return 'soccer'  # Default fallback
    
    match_name_lower = match_name.lower()
    
    # Determine sport from match name patterns
    if any(team in match_name_lower for team in ['marines', 'hawks', 'dragons', 'tigers', 'eagles', 'buffaloes', 'giants', 'swallows', 'carp', 'baystars', 'lions', 'fighters', 'orix']):
        return 'baseball'
    elif any(team in match_name_lower for team in ['lakers', 'warriors', 'celtics', 'bulls', 'heat', 'knicks', 'nets', 'raptors', 'mavericks', 'rockets', 'spurs', 'thunder']):
        return 'bsktbl'
    elif any(team in match_name_lower for team in ['united', 'city', 'arsenal', 'chelsea', 'liverpool', 'barcelona', 'real madrid', 'bayern', 'psg', 'juventus', 'milan', 'inter', 'vasco', 'csa']):
        return 'soccer'
    elif any(team in match_name_lower for team in ['patriots', 'cowboys', 'packers', 'steelers', '49ers', 'chiefs', 'bills', 'ravens', 'eagles', 'giants', 'jets']):
        return 'football'
    else:
        # Default to soccer for unknown teams
        return 'soccer'

betting_bp = Blueprint('betting', __name__)

@betting_bp.route('/bet-slip', methods=['GET'])
@token_required
def get_bet_slip():
    """Get current user's bet slip"""
    try:
        user_id = g.current_user.id
        
        # Get active bet slip
        bet_slip = BetSlip.query.filter_by(
            user_id=user_id,
            status=BetStatus.PENDING
        ).first()
        
        if not bet_slip:
            return jsonify({
                'success': True,
                'bet_slip': None,
                'bets': [],
                'total_stake': 0,
                'potential_return': 0
            })
        
        return jsonify({
            'success': True,
            'bet_slip': bet_slip.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting bet slip: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get bet slip'
        }), 500

@betting_bp.route('/bet-slip/add', methods=['POST'])
@token_required
def add_to_bet_slip():
    """Add selection to bet slip"""
    try:
        user_id = g.current_user.id
        data = request.get_json()
        
        event_id = data.get('event_id')
        outcome_id = data.get('outcome_id')
        stake = float(data.get('stake', 10))
        
        # Validate inputs
        if not event_id or not outcome_id:
            return jsonify({
                'success': False,
                'error': 'Event ID and outcome ID are required'
            }), 400
        
        # Get event and outcome
        event = Event.query.filter_by(goalserve_id=event_id).first()
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        outcome = Outcome.query.get(outcome_id)
        if not outcome:
            return jsonify({
                'success': False,
                'error': 'Outcome not found'
            }), 404
        
        # Check if bet already exists for this event/outcome
        existing_bet = Bet.query.filter_by(
            user_id=user_id,
            event_id=event.id,
            outcome_id=outcome_id,
            status=BetStatus.PENDING
        ).first()
        
        if existing_bet:
            # Update existing bet
            existing_bet.stake = stake
            existing_bet.odds = outcome.odds
            existing_bet.potential_return = stake * outcome.odds
            existing_bet.updated_at = datetime.utcnow()
        else:
            # Create new bet
            bet = Bet(
                user_id=user_id,
                event_id=event.id,
                outcome_id=outcome_id,
                stake=stake,
                odds=outcome.odds,
                potential_return=stake * outcome.odds,
                match_name=f"{event.home_team.name} vs {event.away_team.name}",
                bet_selection=outcome.name
            )
            db.session.add(bet)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Added to bet slip'
        })
        
    except Exception as e:
        logger.error(f"Error adding to bet slip: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to add to bet slip'
        }), 500

@betting_bp.route('/bet-slip/remove', methods=['POST'])
@token_required
def remove_from_bet_slip():
    """Remove selection from bet slip"""
    try:
        user_id = g.current_user.id
        data = request.get_json()
        
        bet_id = data.get('bet_id')
        
        if not bet_id:
            return jsonify({
                'success': False,
                'error': 'Bet ID is required'
            }), 400
        
        # Find and remove bet
        bet = Bet.query.filter_by(
            id=bet_id,
            user_id=user_id,
            status=BetStatus.PENDING
        ).first()
        
        if not bet:
            return jsonify({
                'success': False,
                'error': 'Bet not found'
            }), 404
        
        db.session.delete(bet)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Removed from bet slip'
        })
        
    except Exception as e:
        logger.error(f"Error removing from bet slip: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to remove from bet slip'
        }), 500

@betting_bp.route('/bet-slip/clear', methods=['POST'])
@token_required
def clear_bet_slip():
    """Clear all selections from bet slip"""
    try:
        user_id = g.current_user.id
        
        # Remove all pending bets for user
        Bet.query.filter_by(
            user_id=user_id,
            status=BetStatus.PENDING
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bet slip cleared'
        })
        
    except Exception as e:
        logger.error(f"Error clearing bet slip: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to clear bet slip'
        }), 500

@betting_bp.route('/place', methods=['POST'])
@token_required
def place_bet():
    """Place a single bet"""
    try:
        user = g.current_user
        data = request.get_json()
        
        # Extract bet data from request
        match_id = data.get('match_id')
        match_name = data.get('match_name', f"Match {match_id}")
        selection = data.get('selection')
        odds = float(data.get('odds', 1.0))
        stake = float(data.get('stake', 10))
        sport_name = data.get('sport_name')  # New field for sport
        bet_timing = data.get('bet_timing', 'pregame')  # Default to pregame
        market_id = data.get('market_id', 'unknown')  # Market ID for admin liability calculation
        
        # Log the received data for debugging
        logger.info(f"Received bet data: match_id={match_id}, match_name={match_name}, sport_name={sport_name}, bet_timing={bet_timing}, market_id={market_id}")
        
        # If sport_name is not provided, try to determine it from match_name
        if not sport_name:
            sport_name = determine_sport_from_match_name(match_name)
            logger.info(f"Determined sport_name from match_name: {sport_name}")
        
        # TODO: The frontend should send sport_name from the odds data metadata
        # The odds data contains: "metadata": {"sport": "soccer", "display_name": "Soccer", ...}
        # This is much more reliable than guessing from team names
        
        if not match_id or not selection:
            return jsonify({
                'success': False,
                'message': 'Match ID and selection are required'
            }), 400
        
        # Check if this specific bet event is blocked by admin
        # For now, we'll check if there's an existing bet with is_active=False
        # In a real implementation, you'd have a separate BetEvent table
        blocked_bet = Bet.query.filter_by(
            match_id=match_id,
            selection=selection
        ).filter(Bet.is_active == False).first()
        
        if blocked_bet:
            return jsonify({
                'success': False,
                'message': 'This betting option has been disabled by administrator'
            }), 403
        
        # Check user balance
        if user.balance < stake:
            return jsonify({
                'success': False,
                'message': 'Insufficient balance'
            }), 400
        
        # Create bet record (simplified for now)
        bet = Bet(
            user_id=user.id,
            match_id=match_id,
            selection=selection,
            odds=odds,
            stake=stake,
            potential_return=stake * odds,
            status='pending',
            match_name=match_name,
            bet_selection=selection,
            sport_name=sport_name,  # Store sport name for reliable settlement
            bet_timing=bet_timing,  # Store bet timing (pregame/ingame)
            market=market_id,  # Store market ID for admin liability calculation
            sportsbook_operator_id=user.sportsbook_operator_id,  # Set operator ID for multi-tenant support
            is_active=True  # Default to active
        )
        
        # Deduct balance
        user.balance -= stake
        
        # Save to database
        db.session.add(bet)
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            amount=-stake,
            transaction_type='bet',
            description=f'Bet placement - {selection}',
            balance_before=user.balance + stake,
            balance_after=user.balance
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bet placed successfully',
            'bet_id': bet.id,
            'new_balance': user.balance,
            'bet_timing': bet_timing
        })
        
    except Exception as e:
        logger.error(f"Error placing bet: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to place bet: {str(e)}'
        }), 500

@betting_bp.route('/place-combo', methods=['POST'])
@token_required
def place_combo_bet():
    """Place a combo bet with multiple selections"""
    try:
        user = g.current_user
        data = request.get_json()
        
        # Extract combo bet data
        selections = data.get('selections', [])
        total_odds = float(data.get('total_odds', 1.0))
        total_stake = float(data.get('total_stake', 10))
        bet_type = data.get('bet_type', 'combo')
        sport_name = data.get('sport_name')  # Sport from odds data metadata
        bet_timing = data.get('bet_timing', 'pregame')  # Default to pregame
        
        # For combo bets, create concatenated timing string (timing1_timing2_timing3)
        if selections:
            timings = []
            for selection in selections:
                if isinstance(selection, dict):
                    timing = selection.get('bet_timing', 'pregame')
                    timings.append(timing)
                else:
                    timings.append('pregame')  # Default fallback
            
            # Create concatenated timing string
            bet_timing = '_'.join(timings)
            logger.info(f"Created combo bet_timing: {bet_timing} from timings: {timings}")
        else:
            bet_timing = 'pregame'  # Default fallback
        
        # Log the received data for debugging
        logger.info(f"Received combo bet data: selections={len(selections)}, sport_name={sport_name}, bet_timing={bet_timing}")
        
        # For combo bets, create concatenated sport string (sport1_sport2_sport3)
        if selections:
            sports = []
            for selection in selections:
                if isinstance(selection, dict):
                    sport = selection.get('sport_name', 'soccer')
                    sports.append(sport)
                else:
                    sports.append('soccer')  # Default fallback
            
            # Create concatenated sport string
            sport_name = '_'.join(sports)
            logger.info(f"Created combo sport_name: {sport_name} from sports: {sports}")
        else:
            sport_name = 'soccer'  # Default fallback
        
        if not selections or len(selections) < 2:
            return jsonify({
                'success': False,
                'message': 'At least 2 selections are required for a combo bet'
            }), 400
        
        if len(selections) > 5:
            return jsonify({
                'success': False,
                'message': 'Maximum 5 selections allowed for combo bets'
            }), 400
        
        # Check user balance
        if user.balance < total_stake:
            return jsonify({
                'success': False,
                'message': 'Insufficient balance'
            }), 400
        
        # Create combo bet record
        combo_bet = Bet(
            user_id=user.id,
            match_id=f"combo_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            match_name=f"Combo Bet ({len(selections)} selections)",
            selection=f"Combo: {len(selections)} selections",
            odds=total_odds,
            stake=total_stake,
            potential_return=total_stake * total_odds,
            status='pending',
            bet_selection=f"Combo: {len(selections)} selections",
            bet_type='combo',
            sport_name=sport_name,  # Store sport name for reliable settlement
            bet_timing=bet_timing,  # Store bet timing (pregame/ingame)
            market='combo',  # Set market for combo bets
            sportsbook_operator_id=user.sportsbook_operator_id,  # Set operator ID for multi-tenant support
            combo_selections=json.dumps(selections)  # Store selections as JSON string
        )
        
        # Deduct balance
        user.balance -= total_stake
        
        # Save to database
        db.session.add(combo_bet)
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            amount=-total_stake,
            transaction_type='combo_bet',
            description=f'Combo bet placement - {len(selections)} selections',
            balance_before=user.balance + total_stake,
            balance_after=user.balance
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Combo bet placed successfully',
            'bet_id': combo_bet.id,
            'new_balance': user.balance,
            'selections_count': len(selections),
            'total_odds': total_odds
        })
        
    except Exception as e:
        logger.error(f"Error placing combo bet: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to place combo bet: {str(e)}'
        }), 500

@betting_bp.route('/bets', methods=['GET'])
@token_required
def get_user_bets():
    """Get user's betting history"""
    try:
        user_id = g.current_user.id
        
        # Get query parameters
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Build query
        query = Bet.query.filter_by(user_id=user_id)
        
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        # Include all bets (including pending ones)
        # No filter to exclude pending bets
        
        # Order by creation date (newest first)
        query = query.order_by(Bet.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        bets = []
        for bet in pagination.items:
            bet_dict = bet.to_dict()
            
            # Add formatted local time
            if bet.created_at:
                # Format the time in a readable format
                bet_dict['created_at_local'] = bet.created_at.strftime('%b %d, %Y at %I:%M %p')
            
            bets.append(bet_dict)
        
        return jsonify({
            'success': True,
            'bets': bets,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user bets: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get bets'
        }), 500

@betting_bp.route('/stats', methods=['GET'])
@token_required
def get_user_stats():
    """Get user's betting statistics"""
    try:
        user_id = g.current_user.id
        
        # Get all settled bets
        all_bets = Bet.query.filter_by(user_id=user_id).filter(
            Bet.status != BetStatus.PENDING
        ).all()
        
        if not all_bets:
            return jsonify({
                'success': True,
                'stats': {
                    'total_bets': 0,
                    'win_rate': 0,
                    'total_staked': 0,
                    'total_returned': 0,
                    'profit_loss': 0
                }
            })
        
        # Calculate statistics
        total_bets = len(all_bets)
        won_bets = len([b for b in all_bets if b.status == BetStatus.WON])
        total_staked = sum(bet.stake for bet in all_bets)
        total_returned = sum(bet.actual_return for bet in all_bets)
        
        win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
        profit_loss = total_returned - total_staked
        
        return jsonify({
            'success': True,
            'stats': {
                'total_bets': total_bets,
                'win_rate': round(win_rate, 1),
                'total_staked': round(total_staked, 2),
                'total_returned': round(total_returned, 2),
                'profit_loss': round(profit_loss, 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get stats'
        }), 500

@betting_bp.route('/settle', methods=['POST'])
def settle_bets():
    """Settle bets based on event results (admin endpoint)"""
    try:
        # Get all pending bets for finished events
        pending_bets = db.session.query(Bet).join(Event).filter(
            Bet.status == BetStatus.PENDING,
            Event.status == 'finished'
        ).all()
        
        settled_count = 0
        
        for bet in pending_bets:
            event = bet.event
            outcome = bet.outcome
            market = outcome.market
            
            # Determine bet result based on market type and event result
            is_winner = determine_bet_result(bet, event, outcome, market)
            
            if is_winner:
                bet.status = BetStatus.WON
                bet.actual_return = bet.potential_return
                
                # Credit user account
                user = bet.user
                user.balance += bet.actual_return
                
                # Create transaction
                transaction = Transaction(
                    user_id=user.id,
                    bet_id=bet.id,
                    amount=bet.actual_return,
                    transaction_type='win',
                    description=f'Bet win - {bet.match_name}',
                    balance_before=user.balance - bet.actual_return,
                    balance_after=user.balance
                )
                db.session.add(transaction)
                
            else:
                bet.status = BetStatus.LOST
                bet.actual_return = 0
            
            bet.settled_at = datetime.utcnow()
            settled_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Settled {settled_count} bets',
            'settled_count': settled_count
        })
        
    except Exception as e:
        logger.error(f"Error settling bets: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

def determine_bet_result(bet, event, outcome, market):
    """Determine if a bet is a winner based on event result"""
    try:
        market_type = market.market_type.lower()
        outcome_name = outcome.name.lower()
        
        home_score = event.home_score or 0
        away_score = event.away_score or 0
        
        # Match result markets
        if 'result' in market_type or '3way' in market_type:
            if outcome_name in ['1', 'home'] and home_score > away_score:
                return True
            elif outcome_name in ['x', 'draw'] and home_score == away_score:
                return True
            elif outcome_name in ['2', 'away'] and away_score > home_score:
                return True
        
        # Money line (no draw)
        elif 'money' in market_type or 'line' in market_type:
            if outcome_name in ['1', 'home'] and home_score > away_score:
                return True
            elif outcome_name in ['2', 'away'] and away_score > home_score:
                return True
        
        # Over/Under markets
        elif 'over' in market_type or 'under' in market_type or 'total' in market_type:
            total_goals = home_score + away_score
            
            # Extract line from market name (e.g., "Over/Under 2.5")
            import re
            line_match = re.search(r'(\d+\.?\d*)', market.name)
            if line_match:
                line = float(line_match.group(1))
                
                if 'over' in outcome_name and total_goals > line:
                    return True
                elif 'under' in outcome_name and total_goals < line:
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error determining bet result: {e}")
        return False

@betting_bp.route('/cash-out/<int:bet_id>', methods=['POST'])
@token_required
def cash_out_bet(bet_id):
    """Cash out a bet early"""
    try:
        user = g.current_user
        
        bet = Bet.query.filter_by(
            id=bet_id,
            user_id=user.id,
            status=BetStatus.PENDING
        ).first()
        
        if not bet:
            return jsonify({
                'success': False,
                'error': 'Bet not found or already settled'
            }), 404
        
        # Calculate cash out value (simplified - usually 80-90% of current value)
        cash_out_value = bet.potential_return * 0.85
        
        # Update bet status
        bet.status = BetStatus.CASHED_OUT
        bet.actual_return = cash_out_value
        bet.settled_at = datetime.utcnow()
        
        # Credit user account
        user.balance += cash_out_value
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            bet_id=bet.id,
            amount=cash_out_value,
            transaction_type='cash_out',
            description=f'Cash out - {bet.match_name}',
            balance_before=user.balance - cash_out_value,
            balance_after=user.balance
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bet cashed out successfully',
            'cash_out_value': cash_out_value,
            'new_balance': user.balance
        })
        
    except Exception as e:
        logger.error(f"Error cashing out bet: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to cash out bet'
        }), 500



# Auto Settlement System
import threading
import time
from src.goalserve_client import OptimizedGoalServeClient as GoalServeClient

class AutoSettlementWorker:
    """Background worker for automatic bet settlement"""
    
    def __init__(self, goalserve_client):
        self.goalserve_client = goalserve_client
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the auto settlement worker"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.thread.start()
            logger.info("Auto settlement worker started")
    
    def stop(self):
        """Stop the auto settlement worker"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Auto settlement worker stopped")
    
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                self._check_and_settle_bets()
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Auto settlement worker error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def _check_and_settle_bets(self):
        """Check for finished events and settle bets"""
        try:
            # Get all pending bets
            pending_bets = Bet.query.filter_by(status=BetStatus.PENDING).all()
            
            if not pending_bets:
                return
            
            settled_count = 0
            
            for bet in pending_bets:
                try:
                    # Get live scores for the event's sport
                    sport = bet.event.sport.key if bet.event.sport else 'soccer'
                    live_data = self.goalserve_client.get_live_scores(sport)
                    
                    # Check if event is finished
                    event_finished, final_score = self._check_event_status(bet.event, live_data)
                    
                    if event_finished:
                        # Update event with final score
                        if final_score:
                            bet.event.home_score = final_score.get('home_score', 0)
                            bet.event.away_score = final_score.get('away_score', 0)
                            bet.event.status = 'finished'
                        
                        # Settle the bet
                        self._settle_single_bet(bet)
                        settled_count += 1
                        
                except Exception as e:
                    logger.error(f"Error settling bet {bet.id}: {e}")
                    continue
            
            if settled_count > 0:
                db.session.commit()
                logger.info(f"Auto settled {settled_count} bets")
                
        except Exception as e:
            logger.error(f"Error in auto settlement check: {e}")
            db.session.rollback()
    
    def _check_event_status(self, event, live_data):
        """Check if an event is finished based on live data"""
        try:
            if not isinstance(live_data, dict) or 'scores' not in live_data:
                return False, None
            
            # Look for the event in live data
            for category_key, category_data in live_data['scores'].items():
                if not isinstance(category_data, dict) or 'matches' not in category_data:
                    continue
                
                matches = category_data['matches']
                if isinstance(matches, dict):
                    matches = matches.values()
                
                for match in matches:
                    if not isinstance(match, dict):
                        continue
                    
                    # Match by team names or event ID
                    match_home = match.get('localteam', {}).get('name', '') if isinstance(match.get('localteam'), dict) else str(match.get('localteam', ''))
                    match_away = match.get('visitorteam', {}).get('name', '') if isinstance(match.get('visitorteam'), dict) else str(match.get('visitorteam', ''))
                    
                    if (event.home_team.name.lower() in match_home.lower() and 
                        event.away_team.name.lower() in match_away.lower()) or \
                       (str(event.external_id) == str(match.get('id', ''))):
                        
                        status = match.get('status', '').lower()
                        
                        # Check if match is finished
                        if any(finished_status in status for finished_status in ['finished', 'ft', 'final', 'ended', 'completed']):
                            home_score = match.get('localteam', {}).get('goals', 0) if isinstance(match.get('localteam'), dict) else 0
                            away_score = match.get('visitorteam', {}).get('goals', 0) if isinstance(match.get('visitorteam'), dict) else 0
                            
                            try:
                                home_score = int(home_score) if home_score != '?' else 0
                                away_score = int(away_score) if away_score != '?' else 0
                            except (ValueError, TypeError):
                                home_score = away_score = 0
                            
                            return True, {
                                'home_score': home_score,
                                'away_score': away_score
                            }
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking event status: {e}")
            return False, None
    
    def _settle_single_bet(self, bet):
        """Settle a single bet"""
        try:
            event = bet.event
            outcome = bet.outcome
            market = outcome.market
            
            # Determine bet result
            is_winner = determine_bet_result(bet, event, outcome, market)
            
            if is_winner:
                bet.status = BetStatus.WON
                bet.actual_return = bet.potential_return
                
                # Credit user account
                user = bet.user
                user.balance += bet.actual_return
                
                # Create transaction
                transaction = Transaction(
                    user_id=user.id,
                    bet_id=bet.id,
                    amount=bet.actual_return,
                    transaction_type='win',
                    description=f'Auto settled win - {bet.match_name}',
                    balance_before=user.balance - bet.actual_return,
                    balance_after=user.balance
                )
                db.session.add(transaction)
                
            else:
                bet.status = BetStatus.LOST
                bet.actual_return = 0
            
            bet.settled_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error settling single bet: {e}")
            raise

# Initialize auto settlement worker
auto_settlement_worker = None

@betting_bp.route('/admin/start-auto-settlement', methods=['POST'])
def start_auto_settlement():
    """Start auto settlement worker (admin endpoint)"""
    global auto_settlement_worker
    
    try:
        if auto_settlement_worker is None:
            from src.goalserve_client import OptimizedGoalServeClient as GoalServeClient
            goalserve_client = GoalServeClient()
            auto_settlement_worker = AutoSettlementWorker(goalserve_client)
        
        auto_settlement_worker.start()
        
        return jsonify({
            'success': True,
            'message': 'Auto settlement worker started'
        })
        
    except Exception as e:
        logger.error(f"Error starting auto settlement: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to start auto settlement'
        }), 500

@betting_bp.route('/admin/stop-auto-settlement', methods=['POST'])
def stop_auto_settlement():
    """Stop auto settlement worker (admin endpoint)"""
    global auto_settlement_worker
    
    try:
        if auto_settlement_worker:
            auto_settlement_worker.stop()
        
        return jsonify({
            'success': True,
            'message': 'Auto settlement worker stopped'
        })
        
    except Exception as e:
        logger.error(f"Error stopping auto settlement: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to stop auto settlement'
        }), 500

@betting_bp.route('/admin/settlement-status', methods=['GET'])
def get_settlement_status():
    """Get auto settlement worker status"""
    global auto_settlement_worker
    
    try:
        is_running = auto_settlement_worker and auto_settlement_worker.running
        
        # Get pending bets count
        pending_count = Bet.query.filter_by(status=BetStatus.PENDING).count()
        
        return jsonify({
            'success': True,
            'auto_settlement_running': is_running,
            'pending_bets': pending_count
        })
        
    except Exception as e:
        logger.error(f"Error getting settlement status: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get settlement status'
        }), 500

@betting_bp.route('/manual-settlement', methods=['GET'])
@token_required
def get_manual_settlement_data():
    """Get pending bets grouped by match for manual settlement"""
    try:
        # Get all pending bets
        pending_bets = db.session.query(Bet).filter(
            Bet.status == 'pending'
        ).all()
        
        # Group bets by match_id and market
        grouped_bets = {}
        
        for bet in pending_bets:
            match_key = f"{bet.match_id}_{bet.market}"
            
            if match_key not in grouped_bets:
                grouped_bets[match_key] = {
                    'match_id': bet.match_id,
                    'match_name': bet.match_name,
                    'sport_name': bet.sport_name,
                    'market': bet.market,
                    'total_stake': 0,
                    'total_liability': 0,
                    'bets': [],
                    'outcomes': set()
                }
            
            # Add bet to group
            grouped_bets[match_key]['bets'].append({
                'id': bet.id,
                'user_id': bet.user_id,
                'username': bet.user.username if bet.user else 'Unknown',
                'selection': bet.selection,
                'stake': bet.stake,
                'odds': bet.odds,
                'potential_return': bet.potential_return,
                'created_at': bet.created_at.isoformat() if bet.created_at else None
            })
            
            # Update totals
            grouped_bets[match_key]['total_stake'] += bet.stake
            grouped_bets[match_key]['total_liability'] += bet.potential_return
            grouped_bets[match_key]['outcomes'].add(bet.selection)
        
        # Convert to list and sort by total liability (highest first)
        settlement_list = list(grouped_bets.values())
        settlement_list.sort(key=lambda x: x['total_liability'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': settlement_list
        })
        
    except Exception as e:
        logger.error(f"Error getting manual settlement data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get settlement data'
        }), 500

@betting_bp.route('/manual-settle', methods=['POST'])
@token_required
def manual_settle_bets():
    """Manually settle bets for a specific match and market"""
    try:
        data = request.get_json()
        match_id = data.get('match_id')
        market = data.get('market')
        winning_selection = data.get('winning_selection')
        
        if not all([match_id, market, winning_selection]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: match_id, market, winning_selection'
            }), 400
        
        # Get all pending bets for this match and market
        pending_bets = db.session.query(Bet).filter(
            Bet.match_id == match_id,
            Bet.market == market,
            Bet.status == 'pending'
        ).all()
        
        if not pending_bets:
            return jsonify({
                'success': False,
                'error': 'No pending bets found for this match and market'
            }), 404
        
        settled_count = 0
        won_count = 0
        lost_count = 0
        total_payout = 0
        
        for bet in pending_bets:
            # Determine if bet is a winner
            is_winner = (bet.selection == winning_selection)
            
            if is_winner:
                bet.status = 'won'
                bet.actual_return = bet.potential_return
                won_count += 1
                total_payout += bet.actual_return
                
                # Credit user account
                user = bet.user
                if user:
                    user.balance += bet.actual_return
                    
                    # Create transaction
                    transaction = Transaction(
                        user_id=user.id,
                        bet_id=bet.id,
                        amount=bet.actual_return,
                        transaction_type='win',
                        description=f'Bet win - {bet.match_name} ({bet.selection})',
                        balance_before=user.balance - bet.actual_return,
                        balance_after=user.balance
                    )
                    db.session.add(transaction)
            else:
                bet.status = 'lost'
                bet.actual_return = 0
                lost_count += 1
            
            bet.settled_at = datetime.utcnow()
            settled_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Settled {settled_count} bets',
            'settled_count': settled_count,
            'won_count': won_count,
            'lost_count': lost_count,
            'total_payout': total_payout
        })
        
    except Exception as e:
        logger.error(f"Error manually settling bets: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

