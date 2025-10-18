"""
Betting API routes for sports betting platform
"""

from flask import Blueprint, request, jsonify, g, current_app, session
from src.models.multitenant_models import User, Bet, Transaction, BetSlip, BetStatus
from src.routes.tenant_auth import session_required
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

def _get_orm_user_for_bet(session, ns_user_id: int) -> User:
    """Load the mapped ORM row for the current user"""
    user = session.get(User, ns_user_id)
    if not user:
        raise ValueError(f"User {ns_user_id} not found")
    return user

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

@betting_bp.route('/user/balance', methods=['GET'])
@session_required
def get_user_balance():
    """Get current user balance for testing"""
    try:
        # For read-only operations, SimpleNamespace is fine
        user = g.current_user
        return jsonify({
            'success': True,
            'user_id': user.id,
            'username': user.username,
            'balance': float(user.balance or 0),
            'message': 'Balance retrieved successfully'
        })
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to get balance: {str(e)}'
        }), 500

@betting_bp.route('/bet-slip', methods=['GET'])
@session_required
def get_bet_slip():
    """Get current user's bet slip"""
    try:
        user_id = g.current_user.id
        
        # Get active bet slip using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("SELECT * FROM bet_slips WHERE user_id = %s AND status = %s LIMIT 1", 
                             (user_id, BetStatus.PENDING))
                bet_slip_row = cursor.fetchone()
                bet_slip = bet_slip_row if bet_slip_row else None
        
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
@session_required
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
        
        # Get event and outcome using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                
                # Get event
                cursor.execute("SELECT * FROM events WHERE goalserve_id = %s LIMIT 1", (event_id,))
                event_row = cursor.fetchone()
                if not event_row:
                    return jsonify({
                        'success': False,
                        'error': 'Event not found'
                    }), 404
                event = event_row
                
                # Get outcome
                cursor.execute("SELECT * FROM outcomes WHERE id = %s LIMIT 1", (outcome_id,))
                outcome_row = cursor.fetchone()
                if not outcome_row:
                    return jsonify({
                        'success': False,
                        'error': 'Outcome not found'
                    }), 404
                outcome = outcome_row
        
        # Check if bet already exists for this event/outcome using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("SELECT * FROM bets WHERE user_id = %s AND event_id = %s AND outcome_id = %s AND status = %s LIMIT 1",
                             (user_id, event['id'], outcome_id, BetStatus.PENDING))
                existing_bet_row = cursor.fetchone()
                existing_bet = existing_bet_row if existing_bet_row else None
        
        # Create or update bet using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.transaction():
                if existing_bet:
                    # Update existing bet
                    cursor.execute("""
                        UPDATE bets SET 
                            stake = %s, 
                            odds = %s, 
                            potential_return = %s, 
                            updated_at = %s 
                        WHERE id = %s
                    """, (stake, outcome['odds'], stake * outcome['odds'], datetime.now(), existing_bet['id']))
                    bet_id = existing_bet['id']
                else:
                    # Create new bet
                    cursor.execute("""
                        INSERT INTO bets (user_id, event_id, outcome_id, stake, odds, potential_return, match_name, bet_selection, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user_id, event['id'], outcome_id, stake, outcome['odds'], stake * outcome['odds'], 
                         f"{event['home_team_name']} vs {event['away_team_name']}", outcome['name'], BetStatus.PENDING, datetime.now()))
                    bet_id = cursor.fetchone()['id']
        
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
@session_required
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
        
        # Find and remove bet using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("SELECT * FROM bets WHERE id = %s AND user_id = %s AND status = %s LIMIT 1",
                             (bet_id, user_id, BetStatus.PENDING))
                bet_row = cursor.fetchone()
                bet = bet_row if bet_row else None
        
        if not bet:
            return jsonify({
                'success': False,
                'error': 'Bet not found'
            }), 404
        
        # Delete bet using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.transaction():
                cursor.execute("DELETE FROM bets WHERE id = %s", (bet_id,))
        
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
@session_required
def clear_bet_slip():
    """Clear all selections from bet slip"""
    try:
        user_id = g.current_user.id
        
        # Remove all pending bets for user using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.transaction():
                cursor.execute("DELETE FROM bets WHERE user_id = %s AND status = %s", (user_id, BetStatus.PENDING))
        
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
@session_required
def place_bet():
    """Place a single bet"""
    try:
        # IMPORTANT: g.current_user is a SimpleNamespace (NOT ORM)
        # Re-load a proper ORM User for persistence:
        db = current_app.db.session
        user = _get_orm_user_for_bet(db, g.current_user.id)
        
        # Verify operator match
        if user.sportsbook_operator_id != g.current_user.sportsbook_operator_id:
            return jsonify({
                'success': False,
                'message': 'Operator mismatch'
            }), 400
        
        data = request.get_json()
        
        # Extract bet data from request
        match_id = data.get('match_id')
        match_name = data.get('match_name', f"Match {match_id}")
        selection = data.get('selection')
        odds = float(data.get('odds', 1.0))
        stake = float(data.get('stake', 10))
        sport_name = data.get('sport_name')
        bet_timing = data.get('bet_timing', 'pregame')
        market_id = data.get('market_id', 'unknown')
        event_time = data.get('event_time')  # UTC time when the event is scheduled
        
        if not match_id or not selection:
            return jsonify({
                'success': False,
                'message': 'Match ID and selection are required'
            }), 400
        
        # Validate stake amount - must be positive integer
        if stake <= 0:
            return jsonify({
                'success': False,
                'message': 'Betting amount must be greater than zero'
            }), 400
        
        if not isinstance(stake, (int, float)) or stake != int(stake):
            return jsonify({
                'success': False,
                'message': 'Betting amount must be a whole number'
            }), 400
        
        # Check if this specific bet event is blocked by admin
        blocked_bet = db.query(Bet).filter_by(
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
        
        # Create bet record using IDs only, not relationship objects
        bet = Bet(
            user_id=user.id,  # Use ID, not the user object
            match_id=match_id,
            selection=selection,
            odds=odds,
            stake=stake,
            potential_return=stake * odds,
            status='pending',
            match_name=match_name,
            bet_selection=selection,
            sport_name=sport_name,
            bet_timing=bet_timing,
            market=market_id,
            sportsbook_operator_id=user.sportsbook_operator_id,  # Use ID, not the user object
            is_active=True,
            event_time=event_time  # UTC time when the event is scheduled
        )
        
        # Deduct balance on the ORM user object
        user.balance -= stake
        
        # Save to database
        db.add(bet)
        db.flush()  # Get bet.id without committing
        
        # Create transaction record using IDs only
        transaction = Transaction(
            user_id=user.id,  # Use ID, not the user object
            bet_id=bet.id,
            amount=-stake,
            transaction_type='bet',
            description=f'Bet placement - {selection}',
            balance_before=user.balance + stake,
            balance_after=user.balance
        )
        
        db.add(transaction)
        
        # Commit all changes atomically
        db.commit()
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user.id, stake, f"Bet placement - {selection}")
        except Exception as web3_error:
            logger.warning(f"Web3 sync failed for bet placement: {web3_error}")
        
        # DO NOT refresh g.current_user - it's a SimpleNamespace!
        # Instead, get the new balance from the ORM user object
        new_balance = float(user.balance)
        
        # Update session cache with the new balance using the clean DTO approach
        try:
            from src.routes.tenant_auth import build_session_user
            # Update the session cache with fresh user data
            updated_user_data = build_session_user(user)
            session['user_data'] = updated_user_data
            logger.info("Session cache updated successfully")
        except Exception as e:
            logger.warning(f"Failed to update session user data: {e}")
        
        # Emit socket events using primitives only
        try:
            from flask_socketio import emit
            emit('bet:placed', {
                'user_id': user.id,
                'bet_id': bet.id,
                'stake': stake,
                'new_balance': new_balance
            }, to=f'user_{user.id}', namespace='/')
            
            emit('balance:update', {
                'user_id': user.id,
                'balance': new_balance
            }, to=f'user_{user.id}', namespace='/')
            
            logger.info("Socket events emitted successfully")
        except Exception as e:
            logger.warning(f"Failed to emit socket events: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Bet placed successfully',
            'bet_id': bet.id,
            'new_balance': new_balance
        })
        
    except Exception as e:
        logger.error(f"Error placing bet: {e}")
        # No rollback needed - connection_ctx handles transactions automatically
        pass
        return jsonify({
            'success': False,
            'message': f'Failed to place bet: {str(e)}'
        }), 500

@betting_bp.route('/place-combo', methods=['POST'])
@session_required
def place_combo_bet():
    """Place a combo bet with multiple selections"""
    try:
        # IMPORTANT: g.current_user is a SimpleNamespace (NOT ORM)
        # Re-load a proper ORM User for persistence:
        db = current_app.db.session
        user = _get_orm_user_for_bet(db, g.current_user.id)
        
        # Verify operator match
        if user.sportsbook_operator_id != g.current_user.sportsbook_operator_id:
            return jsonify({
                'success': False,
                'message': 'Operator mismatch'
            }), 400
        
        data = request.get_json()
        
        # Extract combo bet data
        selections = data.get('selections', [])
        total_odds = float(data.get('total_odds', 1.0))
        total_stake = float(data.get('total_stake', 10))
        bet_type = data.get('bet_type', 'combo')
        sport_name = data.get('sport_name')  # Sport from odds data metadata
        bet_timing = data.get('bet_timing', 'pregame')  # Default to pregame
        event_time = data.get('event_time')  # UTC time when the event is scheduled
        
        # Validate total stake amount - must be positive integer
        if total_stake <= 0:
            return jsonify({
                'success': False,
                'message': 'Betting amount must be greater than zero'
            }), 400
        
        if not isinstance(total_stake, (int, float)) or total_stake != int(total_stake):
            return jsonify({
                'success': False,
                'message': 'Betting amount must be a whole number'
            }), 400
        
        # For combo bets, create concatenated timing string (timing1_timing2_timing3)
        if selections:
            timings = []
            for selection in selections:
                if isinstance(selection, dict):
                    timing = selection.get('bet_timing', 'pregame')
                    timings.append(timing)
                else:
                    timings.append('pregame')  # Default fallback
            
            # Create concatenated timing string, but limit length
            bet_timing = '_'.join(timings)
            if len(bet_timing) > 100:
                bet_timing = bet_timing[:97] + '...'  # Truncate if too long
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
            
            # Create concatenated sport string, but limit length
            sport_name = '_'.join(sports)
            if len(sport_name) > 200:
                sport_name = sport_name[:197] + '...'  # Truncate if too long
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
            match_id=f"combo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
            sportsbook_operator_id=getattr(user, 'sportsbook_operator_id', None),  # Safely get operator ID
            combo_selections=json.dumps(selections),  # Store selections as JSON string
            event_time=event_time  # UTC time when the event is scheduled
        )
        
        # Deduct balance
        user.balance -= total_stake
        
        # Save to database
        db.add(combo_bet)
        db.flush()  # Get combo_bet.id without committing
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            bet_id=combo_bet.id,  # Now we have the combo bet ID
            amount=-total_stake,
            transaction_type='combo_bet',
            description=f'Combo bet placement - {len(selections)} selections',
            balance_before=user.balance + total_stake,  # Balance before deduction
            balance_after=user.balance  # Balance after deduction
        )
        db.add(transaction)
        
        # Commit all changes atomically
        db.commit()
        
        # Sync Web3 wallet debit (non-blocking)
        try:
            from src.services.web3_sync_service import sync_web3_debit
            sync_web3_debit(user.id, total_stake, f"Combo bet placement - {len(selections)} selections")
        except Exception as web3_error:
            logger.warning(f"Web3 sync failed for combo bet placement: {web3_error}")
        
        # DO NOT refresh g.current_user - it's a SimpleNamespace!
        # Instead, get the new balance from the ORM user object
        new_balance = float(user.balance)
        
        # Update session cache with the new balance using the clean DTO approach
        try:
            from src.routes.tenant_auth import build_session_user
            # Update the session cache with fresh user data
            updated_user_data = build_session_user(user)
            session['user_data'] = updated_user_data
            logger.info("Session cache updated successfully")
        except Exception as e:
            logger.warning(f"Failed to update session user data: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Combo bet placed successfully',
            'bet_id': combo_bet.id,
            'new_balance': new_balance,
            'selections_count': len(selections),
            'total_odds': total_odds
        })
        
    except Exception as e:
        logger.error(f"Error placing combo bet: {e}")
        # Rollback the session if there was an error
        try:
            db.rollback()
        except:
            pass
        return jsonify({
            'success': False,
            'message': f'Failed to place combo bet: {str(e)}'
        }), 500

@betting_bp.route('/bets', methods=['GET'])
@session_required
def get_user_bets():
    """Get user's betting history with connection pool optimization"""
    try:
        user_id = g.current_user.id
        
        # Get query parameters
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Use raw connection for better performance and connection management
        from src.database_config import get_raw_database_connection
        
        with get_raw_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SET LOCAL statement_timeout = '1500ms'")
            
            # Build base query
            base_query = "FROM bets WHERE user_id = %s"
            params = [user_id]
            
            if status and status != 'all':
                base_query += " AND status = %s"
                params.append(status)
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total {base_query}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']
            
            # Calculate pagination
            offset = (page - 1) * per_page
            total_pages = (total_count + per_page - 1) // per_page
            
            # Get paginated results
            select_query = f"""
                SELECT id, match_name, selection, stake, odds, potential_return, 
                       status, created_at, settled_at, sport_name, bet_timing, combo_selections
                {base_query}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(select_query, params + [per_page, offset])
            
            bets = []
            for row in cursor.fetchall():
                bet_dict = dict(row)
                
                # Add UTC ISO-8601 timestamp (bulletproof for any user timezone)
                if bet_dict.get('created_at'):
                    from datetime import timezone
                    
                    def to_utc_iso(dt):
                        # dt may be naive or aware; normalize to UTC-aware, then ISO with Z
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        else:
                            dt = dt.astimezone(timezone.utc)
                        return dt.isoformat().replace("+00:00", "Z")
                    
                    bet_dict["created_at_iso"] = to_utc_iso(bet_dict['created_at'])
                    bet_dict["created_at"] = bet_dict["created_at_iso"]  # alias for compatibility
                
                bets.append(bet_dict)
        
        return jsonify({
            'success': True,
            'bets': bets,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user bets: {e}")
        logger.exception("Full exception details for bet history:")
        
        # Try to rollback any pending transactions
        # No rollback needed - connection_ctx handles transactions automatically
        pass
        
        return jsonify({
            'success': False,
            'error': 'Failed to get bets'
        }), 500

@betting_bp.route('/test-connection', methods=['GET'])
@session_required
def test_betting_connection():
    """Test endpoint to verify database connection and authentication"""
    try:
        user_id = g.current_user.id
        
        # Simple raw query instead of ORM to test connection
        from src.database_config import get_raw_database_connection
        with get_raw_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SET LOCAL statement_timeout = '1500ms'")
            cursor.execute("SELECT COUNT(*) as count FROM bets WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            bet_count = result['count'] if result else 0
        
        return jsonify({
            'success': True,
            'message': 'Connection test successful',
            'user_id': user_id,
            'user_name': g.current_user.username,
            'bet_count': bet_count
        })
        
    except Exception as e:
        logger.error(f"Error in connection test: {e}")
        logger.exception("Full exception details for connection test:")
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }), 500

@betting_bp.route('/stats', methods=['GET'])
@session_required
def get_user_stats():
    """Get user's betting statistics"""
    try:
        user_id = g.current_user.id
        
        # Get all settled bets using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("""
                    SELECT * FROM bets 
                    WHERE user_id = %s AND status != %s
                    ORDER BY created_at DESC
                """, (user_id, BetStatus.PENDING))
                all_bets = cursor.fetchall()
        
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
        # Get all pending bets for finished events using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=10) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                cursor.execute("""
                    SELECT b.*, e.status as event_status, e.home_score, e.away_score
                    FROM bets b
                    JOIN events e ON b.event_id = e.id
                    WHERE b.status = %s AND e.status = 'finished'
                """, (BetStatus.PENDING,))
                pending_bets = cursor.fetchall()
        
        settled_count = 0
        
        for bet in pending_bets:
            # Determine bet result (this would need the full event/outcome/market data)
            # For now, simplified - you may need to fetch additional data
            with connection_ctx(timeout=5) as conn:
                with conn.transaction():
                    # Get outcome and market info
                    cursor.execute("SELECT * FROM outcomes WHERE id = %s", (bet['outcome_id'],))
                    outcome = cursor.fetchone()
                    
                    if not outcome:
                        continue
                    
                    cursor.execute("SELECT * FROM markets WHERE id = %s", (outcome['market_id'],))
                    market = cursor.fetchone()
                    
                    cursor.execute("SELECT * FROM events WHERE id = %s", (bet['event_id'],))
                    event = cursor.fetchone()
                    
                    # Determine if bet won (simplified - you'll need proper logic)
                    is_winner = determine_bet_result(bet, event, outcome, market)
                    
                    if is_winner:
                        # Get user balance
                        cursor.execute("SELECT balance FROM users WHERE id = %s", (bet['user_id'],))
                        user = cursor.fetchone()
                        
                        if user:
                            balance_before = user['balance']
                            balance_after = balance_before + bet['potential_return']
                            
                            # Update user balance
                            cursor.execute("UPDATE users SET balance = %s WHERE id = %s", 
                                         (balance_after, bet['user_id']))
                            
                            # Update bet
                            cursor.execute("""UPDATE bets SET status = %s, actual_return = %s, settled_at = %s 
                                           WHERE id = %s""",
                                         (BetStatus.WON, bet['potential_return'], datetime.now(), bet['id']))
                            
                            # Create transaction
                            cursor.execute("""
                                INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (bet['user_id'], bet['id'], bet['potential_return'], 'win',
                                 f'Bet win - {bet["match_name"]}', balance_before, balance_after, datetime.now()))
                    else:
                        # Update bet as lost
                        cursor.execute("""UPDATE bets SET status = %s, actual_return = %s, settled_at = %s 
                                       WHERE id = %s""",
                                     (BetStatus.LOST, 0, datetime.now(), bet['id']))
                    
                    settled_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Settled {settled_count} bets',
            'settled_count': settled_count
        })
        
    except Exception as e:
        logger.error(f"Error settling bets: {e}")
        # No rollback needed - connection_ctx handles transactions
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
@session_required
def cash_out_bet(bet_id):
    """Cash out a bet early"""
    try:
        user = g.current_user
        
        # Get bet and cash out using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("""
                    SELECT * FROM bets 
                    WHERE id = %s AND user_id = %s AND status = %s
                    LIMIT 1
                """, (bet_id, user.id, BetStatus.PENDING))
                bet = cursor.fetchone()
                
                if not bet:
                    return jsonify({
                        'success': False,
                        'error': 'Bet not found or already settled'
                    }), 404
                
                # Calculate cash out value (simplified - usually 80-90% of current value)
                cash_out_value = bet['potential_return'] * 0.85
                
                # Get user balance
                cursor.execute("SELECT balance FROM users WHERE id = %s", (user.id,))
                user_data = cursor.fetchone()
                balance_before = user_data['balance']
                balance_after = balance_before + cash_out_value
                
                # Update bet status
                cursor.execute("""
                    UPDATE bets 
                    SET status = %s, actual_return = %s, settled_at = %s 
                    WHERE id = %s
                """, (BetStatus.CASHED_OUT, cash_out_value, datetime.now(), bet_id))
                
                # Credit user account
                cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, user.id))
                
                # Create transaction
                cursor.execute("""
                    INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (user.id, bet_id, cash_out_value, 'cash_out',
                     f'Cash out - {bet["match_name"]}', balance_before, balance_after, datetime.now()))
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bet cashed out successfully',
            'cash_out_value': cash_out_value,
            'new_balance': user.balance
        })
        
    except Exception as e:
        logger.error(f"Error cashing out bet: {e}")
        # No rollback needed - connection_ctx handles transactions
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
            # Get all pending bets using tracked connection
            with connection_ctx(timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                    cursor.execute("SELECT * FROM bets WHERE status = %s", (BetStatus.PENDING,))
                    pending_bets = cursor.fetchall()
            
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
                # No commit needed - connection_ctx handles transactions
                logger.info(f"Auto settled {settled_count} bets")
                
        except Exception as e:
            logger.error(f"Error in auto settlement check: {e}")
            # No rollback needed - connection_ctx handles transactions
    
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
            # Get event, outcome, and market data using tracked connection
            with connection_ctx(timeout=5) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM events WHERE id = %s", (bet['event_id'],))
                    event = cursor.fetchone()
                    
                    cursor.execute("SELECT * FROM outcomes WHERE id = %s", (bet['outcome_id'],))
                    outcome = cursor.fetchone()
                    
                    if outcome:
                        cursor.execute("SELECT * FROM markets WHERE id = %s", (outcome['market_id'],))
                        market = cursor.fetchone()
                    else:
                        market = None
            
            # Determine bet result
            is_winner = determine_bet_result(bet, event, outcome, market)
            
            if is_winner:
                # Update bet and user balance using tracked connection
                with connection_ctx(timeout=5) as conn:
                    with conn.transaction():
                        # Get user balance
                        cursor.execute("SELECT balance FROM users WHERE id = %s", (bet['user_id'],))
                        user_data = cursor.fetchone()
                        balance_before = user_data['balance']
                        balance_after = balance_before + bet['potential_return']
                        
                        # Update user balance
                        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet['user_id']))
                        
                        # Update bet
                        cursor.execute("""UPDATE bets SET status = %s, actual_return = %s, settled_at = %s WHERE id = %s""",
                                     (BetStatus.WON, bet['potential_return'], datetime.now(), bet['id']))
                        
                        # Create transaction
                        cursor.execute("""
                            INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (bet['user_id'], bet['id'], bet['potential_return'], 'win',
                             f'Auto settled win - {bet["match_name"]}', balance_before, balance_after, datetime.now()))
            else:
                # Update bet as lost
                with connection_ctx(timeout=5) as conn:
                    with conn.transaction():
                        cursor.execute("""UPDATE bets SET status = %s, actual_return = %s, settled_at = %s WHERE id = %s""",
                                     (BetStatus.LOST, 0, datetime.now(), bet['id']))
            
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
        
        # Get pending bets count using tracked connection
        with connection_ctx(timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM bets WHERE status = %s", (BetStatus.PENDING,))
                pending_count = cursor.fetchone()[0]
        
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
@session_required
def get_manual_settlement_data():
    """Get pending bets grouped by match for manual settlement"""
    try:
        # Get all pending bets using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("SELECT * FROM bets WHERE status = 'pending' ORDER BY match_id, market")
                pending_bets = cursor.fetchall()
        
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
@session_required
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
        
        # Get all pending bets for this match and market using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("""
                    SELECT * FROM bets 
                    WHERE match_id = %s AND market = %s AND status = 'pending'
                """, (match_id, market))
                pending_bets = cursor.fetchall()
        
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
            is_winner = (bet['selection'] == winning_selection)
            
            with connection_ctx(timeout=5) as conn:
                with conn.transaction():
                    if is_winner:
                        # Get user balance
                        cursor.execute("SELECT balance FROM users WHERE id = %s", (bet['user_id'],))
                        user_data = cursor.fetchone()
                        
                        if user_data:
                            balance_before = user_data['balance']
                            balance_after = balance_before + bet['potential_return']
                            
                            # Update user balance
                            cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (balance_after, bet['user_id']))
                            
                            # Update bet
                            cursor.execute("""
                                UPDATE bets SET status = 'won', actual_return = %s, settled_at = %s WHERE id = %s
                            """, (bet['potential_return'], datetime.now(), bet['id']))
                            
                            # Create transaction
                            cursor.execute("""
                                INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (bet['user_id'], bet['id'], bet['potential_return'], 'win',
                                 f'Bet win - {bet["match_name"]} ({bet["selection"]})', balance_before, balance_after, datetime.now()))
                            
                            won_count += 1
                            total_payout += bet['potential_return']
                    else:
                        # Update bet as lost
                        cursor.execute("""
                            UPDATE bets SET status = 'lost', actual_return = 0, settled_at = %s WHERE id = %s
                        """, (datetime.now(), bet['id']))
                        lost_count += 1
                    
                    settled_count += 1
        
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
        # No rollback needed - connection_ctx handles transactions
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

