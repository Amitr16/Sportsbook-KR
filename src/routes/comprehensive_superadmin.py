"""
Comprehensive Super Admin Interface - Global Level
Same features as admin but across ALL operators + additional super admin features
"""

from flask import Blueprint, render_template_string, jsonify, request, session, redirect
from src import sqlite3_shim as sqlite3
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import logging
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

comprehensive_superadmin_bp = Blueprint('comprehensive_superadmin', __name__)

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim"""
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    return conn

def superadmin_required(f):
    """Decorator to require super admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from src.auth.session_utils import is_superadmin_logged_in
        if not is_superadmin_logged_in():
            return redirect('/superadmin')
        return f(*args, **kwargs)
    return decorated_function

@comprehensive_superadmin_bp.route('/superadmin/comprehensive-dashboard')
@superadmin_required
def superadmin_comprehensive_dashboard():
    """Comprehensive super admin dashboard"""
    try:
        html_template = get_comprehensive_superadmin_template()
        return render_template_string(html_template)
        
    except Exception as e:
        logger.error(f"Super admin comprehensive dashboard error: {e}")
        return "Dashboard error", 500

@comprehensive_superadmin_bp.route('/api/superadmin/global-betting-events')
@superadmin_required
def get_global_betting_events():
    """Get betting events across ALL operators with show_only_with_bets filtering"""
    try:
        show_only_with_bets = request.args.get('show_only_with_bets', 'false').lower() == 'true'
        
        print(f"🔍 DEBUG: Global betting events - show_only_with_bets = {show_only_with_bets}")
        
        conn = get_db_connection()
        
        # Step 1: Get pending bets from ALL operators - AGGREGATED by event+market with LIMIT
        base_query = """
            SELECT 
                b.match_id,
                b.sport_name, 
                b.market, 
                COUNT(*) as bet_count
            FROM bets b
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
            WHERE b.status = 'pending' AND so.is_active = TRUE
            GROUP BY b.match_id, b.sport_name, b.market
            ORDER BY b.match_id DESC
            LIMIT 1000
        """
        
        bet_events_result = conn.execute(base_query).fetchall()
        print(f"🔍 DEBUG: Found {len(bet_events_result)} pending bets across all operators")
        
        if not bet_events_result:
            conn.close()
            return jsonify({
                'events': [],
                'summary': {
                    'total_events': 0,
                    'total_bets': 0,
                    'total_stakes': 0.0,
                    'total_potential_returns': 0.0
                }
            })
        
        # Step 2: If show_only_with_bets=true, filter by JSON file availability
        if show_only_with_bets:
            print("🔍 DEBUG: Filtering by JSON file availability...")
            
            # Get events that exist in JSON files
            available_events = set()
            sports_dir = os.path.join(os.getcwd(), 'Sports Pre Match')
            
            if os.path.exists(sports_dir):
                for sport_folder in os.listdir(sports_dir):
                    if os.path.isdir(os.path.join(sports_dir, sport_folder)):
                        events_file = os.path.join(sports_dir, sport_folder, f'{sport_folder}_odds.json')
                        if os.path.exists(events_file):
                            try:
                                with open(events_file, 'r', encoding='utf-8') as f:
                                    sport_data = json.load(f)
                                
                                # Extract available event-market combinations
                                if 'odds_data' in sport_data and 'scores' in sport_data['odds_data'] and 'categories' in sport_data['odds_data']['scores']:
                                    for category in sport_data['odds_data']['scores']['categories']:
                                        if 'matches' in category:
                                            for match in category['matches']:
                                                event_id = str(match.get('id', ''))
                                                if 'odds' in match:
                                                    for odd in match['odds']:
                                                        market_id = str(odd.get('id', ''))
                                                        if market_id:
                                                            available_events.add((event_id, sport_folder, market_id))
                                
                            except Exception as e:
                                print(f"Error loading {sport_folder} JSON: {e}")
                                continue
            
            print(f"🔍 DEBUG: Available events in JSON: {len(available_events)}")
            
            # Filter bets to only include available events
            filtered_bets = []
            for bet in bet_events_result:
                event_key = (str(bet['match_id']), str(bet['sport_name']), str(bet['market']))
                if event_key in available_events:
                    filtered_bets.append(bet)
            
            bet_events_result = filtered_bets
            print(f"🔍 DEBUG: After JSON filtering: {len(bet_events_result)} bets")
        
        # Step 3: Process and format the results
        all_events = []
        total_stakes = 0.0
        total_potential_returns = 0.0
        
        for bet in bet_events_result:
            # Get detailed bet selections and calculate totals for this event+market
            totals_query = """
                SELECT 
                    SUM(b.stake) as total_stakes,
                    SUM(b.potential_return) as total_potential_returns,
                    COUNT(DISTINCT so.sportsbook_name) as operator_count
                FROM bets b
                JOIN users u ON b.user_id = u.id
                JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
                WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
                AND so.is_active = TRUE
            """
            
            totals = conn.execute(totals_query, (bet['match_id'], bet['market'], bet['sport_name'])).fetchone()
            
            if totals:
                event_total_stakes = float(totals['total_stakes'] or 0)
                event_total_potential_returns = float(totals['total_potential_returns'] or 0)
                operator_count = int(totals['operator_count'] or 0)
                
                # Get detailed bet selections for liability calculation
                selections_query = """
                    SELECT b.bet_selection, SUM(b.stake) as total_stake, SUM(b.potential_return) as total_payout
                    FROM bets b
                    JOIN users u ON b.user_id = u.id
                    JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
                    WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
                    AND so.is_active = TRUE
                    GROUP BY b.bet_selection
                """
                
                selections = conn.execute(selections_query, (bet['match_id'], bet['market'], bet['sport_name'])).fetchall()
                
                if selections:
                    # Calculate profit/loss for each possible outcome
                    outcomes = []
                    
                    for selection_row in selections:
                        total_payout = float(selection_row['total_payout'])
                        # If this selection wins: pay out winners, keep losing stakes
                        profit_loss = event_total_stakes - total_payout
                        outcomes.append(profit_loss)
                    
                    max_liability = abs(min(outcomes)) if outcomes else 0.0
                    max_possible_gain = max(outcomes) if outcomes else 0.0
                else:
                    max_liability = 0.0
                    max_possible_gain = 0.0
                
                total_stakes += event_total_stakes
                total_potential_returns += event_total_potential_returns
                
                # Create betting event entry - AGGREGATED at event+market level
                betting_event = {
                    'event_id': bet['match_id'],
                    'sport': bet['sport_name'].title(),
                    'event_name': f"{bet['sport_name'].title()} - {bet['market']}",
                    'market': bet['market'],
                    'total_bets': bet['bet_count'],
                    'operator_count': operator_count,
                    'max_liability': max_liability,
                    'max_possible_gain': max_possible_gain,
                    'total_stakes': event_total_stakes,
                    'total_potential_returns': event_total_potential_returns,
                    'status': 'active'
                }
                
                all_events.append(betting_event)
        
        conn.close()
        
        # Calculate summary
        total_events = len(all_events)
        
        return jsonify({
            'success': True,
            'events': all_events,
            'total_events': total_events,
            'active_events': total_events,
            'total_liability': sum(e['max_liability'] for e in all_events),
            'max_possible_gain': sum(e['max_possible_gain'] for e in all_events),
            'summary': {
                'total_events': total_events,
                'total_bets': sum(event['total_bets'] for event in all_events),
                'total_stakes': total_stakes,
                'total_potential_returns': total_potential_returns
            }
        })
        
    except Exception as e:
        logger.error(f"Global betting events error: {e}")
        return jsonify({'error': 'Failed to get events'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/global-users')
@superadmin_required
def get_global_users():
    """Get users across ALL operators"""
    try:
        conn = get_db_connection()
        
        # Get users from ALL operators
        users_query = """
        SELECT u.id, u.username, u.email, u.balance, u.is_active, u.created_at, u.last_login,
               so.sportsbook_name, so.subdomain,
               COUNT(b.id) as total_bets,
               COALESCE(SUM(b.stake), 0) as total_staked,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return ELSE 0 END), 0) as total_payout,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return - b.stake 
                               WHEN b.status = 'lost' THEN -b.stake ELSE 0 END), 0) as cumulative_profit
        FROM users u
        JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
        LEFT JOIN bets b ON u.id = b.user_id
        GROUP BY u.id, u.username, u.email, u.balance, u.is_active, u.created_at, u.last_login, so.sportsbook_name, so.subdomain
        ORDER BY u.created_at DESC
        """
        
        users = conn.execute(users_query).fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'balance': float(user['balance']),
                'operator': user['sportsbook_name'],
                'subdomain': user['subdomain'],
                'total_bets': user['total_bets'],
                'total_staked': float(user['total_staked']),
                'total_payout': float(user['total_payout']),
                'cumulative_profit': float(user['cumulative_profit']),
                'joined': user['created_at'][:10] if user['created_at'] else '',
                'status': 'Active' if user['is_active'] else 'Disabled',
                'is_active': user['is_active']
            })
        
        return jsonify({
            'success': True,
            'users': users_list
        })
        
    except Exception as e:
        logger.error(f"Global users error: {e}")
        return jsonify({'error': 'Failed to get users'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/toggle-global-user', methods=['POST'])
@superadmin_required
def toggle_global_user_status():
    """Enable/disable user globally (super admin power)"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        conn = get_db_connection()
        
        # Get user info
        user = conn.execute("""
            SELECT u.id, u.is_active, u.username, so.sportsbook_name
            FROM users u
            JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
            WHERE u.id = ?
        """, (user_id,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Toggle user status
        new_status = not user['is_active']
        conn.execute("""
            UPDATE users SET is_active = ? WHERE id = ?
        """, (new_status, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"User {user['username']} from {user['sportsbook_name']} {'enabled' if new_status else 'disabled'} successfully",
            'new_status': new_status
        })
        
    except Exception as e:
        logger.error(f"Toggle global user error: {e}")
        return jsonify({'error': 'Failed to toggle user status'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/global-reports')
@superadmin_required
def get_global_reports():
    """Get comprehensive reports across ALL operators"""
    try:
        conn = get_db_connection()
        
        # Get comprehensive betting statistics across ALL operators
        stats_query = """
        SELECT 
            COUNT(b.id) as total_bets,
            COALESCE(SUM(b.stake), 0) as total_stakes,
            COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return - b.stake 
                             WHEN b.status = 'lost' THEN -b.stake ELSE 0 END), 0) as total_revenue,
            COUNT(CASE WHEN b.status = 'pending' THEN 1 END) as pending_bets,
            COUNT(CASE WHEN b.status = 'won' THEN 1 END) as won_bets,
            COUNT(CASE WHEN b.status = 'lost' THEN 1 END) as lost_bets
        FROM bets b
        JOIN users u ON b.user_id = u.id
        """
        
        stats = conn.execute(stats_query).fetchone()
        
        # Get sport performance globally
        sport_query = """
        SELECT b.sport_name,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return - b.stake 
                               WHEN b.status = 'lost' THEN -b.stake ELSE 0 END), 0) as revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        GROUP BY b.sport_name
        ORDER BY revenue DESC
        """
        
        sports = conn.execute(sport_query).fetchall()
        
        # Get top users globally
        top_users_query = """
        SELECT u.username, so.sportsbook_name, COUNT(b.id) as bet_count
        FROM users u
        JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
        LEFT JOIN bets b ON u.id = b.user_id
        GROUP BY u.id, u.username, so.sportsbook_name
        HAVING bet_count > 0
        ORDER BY bet_count DESC
        LIMIT 10
        """
        
        top_users = conn.execute(top_users_query).fetchall()
        
        conn.close()
        
        # Calculate win rate
        total_bets = stats['total_bets'] or 0
        won_bets = stats['won_bets'] or 0
        win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_bets': total_bets,
                'total_stakes': float(stats['total_stakes'] or 0),
                'total_revenue': float(stats['total_revenue'] or 0),
                'win_rate': round(win_rate, 1),
                'pending_bets': stats['pending_bets'] or 0,
                'won_bets': won_bets,
                'lost_bets': stats['lost_bets'] or 0
            },
            'sport_performance': [{'sport': s['sport_name'], 'revenue': float(s['revenue'])} for s in sports],
            'top_users': [{'username': u['username'], 'operator': u['sportsbook_name'], 'bets': u['bet_count']} for u in top_users]
        })
        
    except Exception as e:
        logger.error(f"Global reports error: {e}")
        return jsonify({'error': 'Failed to get reports'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/operators')
@superadmin_required
def get_operators():
    """Get all operators for management"""
    try:
        conn = get_db_connection()
        
        operators_query = """
        SELECT so.id, so.sportsbook_name, so.subdomain, so.admin_username, so.admin_email, 
               so.is_active, so.created_at,
               COUNT(DISTINCT u.id) as total_users,
               COUNT(DISTINCT b.id) as total_bets,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return - b.stake 
                               WHEN b.status = 'lost' THEN -b.stake ELSE 0 END), 0) as revenue
        FROM sportsbook_operators so
        LEFT JOIN users u ON so.id = u.sportsbook_operator_id
        LEFT JOIN bets b ON u.id = b.user_id
        GROUP BY so.id, so.sportsbook_name, so.subdomain, so.admin_username, so.admin_email, so.is_active, so.created_at
        ORDER BY so.created_at DESC
        """
        
        operators = conn.execute(operators_query).fetchall()
        conn.close()
        
        operators_list = []
        for op in operators:
            operators_list.append({
                'id': op['id'],
                'sportsbook_name': op['sportsbook_name'],
                'subdomain': op['subdomain'],
                'admin_username': op['admin_username'],
                'admin_email': op['admin_email'],
                'is_active': op['is_active'],
                'created_at': op['created_at'][:10] if op['created_at'] else '',
                'total_users': op['total_users'],
                'total_bets': op['total_bets'],
                'revenue': float(op['revenue'] or 0),
                'status': 'Active' if op['is_active'] else 'Disabled'
            })
        
        return jsonify({
            'success': True,
            'operators': operators_list
        })
        
    except Exception as e:
        logger.error(f"Operators error: {e}")
        return jsonify({'error': 'Failed to get operators'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/toggle-operator', methods=['POST'])
@superadmin_required
def toggle_operator_status():
    """Enable/disable operator (super admin power)"""
    try:
        data = request.get_json()
        operator_id = data.get('operator_id')
        
        conn = get_db_connection()
        
        # Get operator info
        operator = conn.execute("""
            SELECT id, is_active, sportsbook_name FROM sportsbook_operators WHERE id = ?
        """, (operator_id,)).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({'error': 'Operator not found'}), 404
        
        # Toggle operator status
        new_status = not operator['is_active']
        conn.execute("""
            UPDATE sportsbook_operators SET is_active = ? WHERE id = ?
        """, (new_status, operator_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Operator {operator['sportsbook_name']} {'enabled' if new_status else 'disabled'} successfully",
            'new_status': new_status
        })
        
    except Exception as e:
        logger.error(f"Toggle operator error: {e}")
        return jsonify({'error': 'Failed to toggle operator status'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/change-operator-password', methods=['POST'])
@superadmin_required
def change_operator_password():
    """Change operator admin password (super admin power)"""
    try:
        data = request.get_json()
        operator_id = data.get('operator_id')
        new_password = data.get('new_password')
        
        if not new_password or len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        conn = get_db_connection()
        
        # Get operator info
        operator = conn.execute("""
            SELECT id, sportsbook_name FROM sportsbook_operators WHERE id = ?
        """, (operator_id,)).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({'error': 'Operator not found'}), 404
        
        # Update password
        password_hash = generate_password_hash(new_password)
        conn.execute("""
            UPDATE sportsbook_operators SET admin_password_hash = ? WHERE id = ?
        """, (password_hash, operator_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Password changed for {operator['sportsbook_name']} successfully"
        })
        
    except Exception as e:
        logger.error(f"Change operator password error: {e}")
        return jsonify({'error': 'Failed to change password'}), 500

@comprehensive_superadmin_bp.route('/api/superadmin/manual-settlement')
@superadmin_required
def get_global_manual_settlement_data():
    """Get pending bets grouped by match for manual settlement across all operators"""
    try:
        conn = get_db_connection()
        
        # Get all pending bets from ALL operators
        query = """
        SELECT b.*, u.username, so.sportsbook_name as operator_name
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
        WHERE b.status = 'pending'
        ORDER BY b.created_at DESC
        """
        
        pending_bets = conn.execute(query).fetchall()
        conn.close()
        
        # Group bets by match_id and market
        grouped_bets = {}
        
        for bet in pending_bets:
            match_key = f"{bet['match_id']}_{bet['market']}"
            
            if match_key not in grouped_bets:
                grouped_bets[match_key] = {
                    'match_id': bet['match_id'],
                    'match_name': bet['match_name'],
                    'sport_name': bet['sport_name'],
                    'market': bet['market'],
                    'operator_name': bet['operator_name'],
                    'total_stake': 0,
                    'total_liability': 0,
                    'bets': [],
                    'outcomes': set()
                }
            
            # Add bet to group
            grouped_bets[match_key]['bets'].append({
                'id': bet['id'],
                'user_id': bet['user_id'],
                'username': bet['username'],
                'operator_name': bet['operator_name'],
                'selection': bet['selection'],
                'stake': bet['stake'],
                'odds': bet['odds'],
                'potential_return': bet['potential_return'],
                'created_at': bet['created_at']
            })
            
            # Update totals
            grouped_bets[match_key]['total_stake'] += bet['stake']
            grouped_bets[match_key]['total_liability'] += bet['potential_return']
            grouped_bets[match_key]['outcomes'].add(bet['selection'])
        
        # Convert to list and sort by total liability (highest first)
        settlement_list = list(grouped_bets.values())
        settlement_list.sort(key=lambda x: x['total_liability'], reverse=True)
        
        # Convert sets to lists for JSON serialization
        for item in settlement_list:
            item['outcomes'] = list(item['outcomes'])
        
        return jsonify({
            'success': True,
            'data': settlement_list
        })
        
    except Exception as e:
        logger.error(f"Error getting global manual settlement data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get settlement data'
        }), 500

@comprehensive_superadmin_bp.route('/api/superadmin/manual-settle', methods=['POST'])
@superadmin_required
def global_manual_settle_bets():
    """Manually settle bets for a specific match and market across all operators"""
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
        
        conn = get_db_connection()
        
        # Get all pending bets for this match and market from ALL operators
        query = """
        SELECT b.*, u.username, so.sportsbook_name as operator_name
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
        WHERE b.match_id = ? AND b.market = ? AND b.status = 'pending'
        """
        
        pending_bets = conn.execute(query, (match_id, market)).fetchall()
        
        if not pending_bets:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No pending bets found for this match and market'
            }), 404
        
        settled_count = 0
        won_count = 0
        lost_count = 0
        total_payout = 0
        
        for bet in pending_bets:
            # Handle "No Result" case - cancel bet and refund stake
            if winning_selection == 'no_result':
                # Update bet status to voided (cancelled)
                conn.execute("""
                    UPDATE bets 
                    SET status = 'voided', actual_return = ?, settled_at = ?
                    WHERE id = ?
                """, (bet['stake'], datetime.now(), bet['id']))
                
                # Refund the stake to user account
                conn.execute("""
                    UPDATE users 
                    SET balance = balance + ?
                    WHERE id = ?
                """, (bet['stake'], bet['user_id']))
                
                # Create transaction record for refund
                conn.execute("""
                    INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                    VALUES (?, ?, ?, 'refund', ?, ?, ?, ?)
                """, (
                    bet['user_id'], 
                    bet['id'], 
                    bet['stake'],
                    f'Bet cancelled - {bet["match_name"]} (No Result)',
                    bet['stake'],  # balance_before (simplified)
                    bet['stake'] * 2,  # balance_after (simplified)
                    datetime.now()
                ))
                
                settled_count += 1
                continue
            
            # Determine if bet is a winner (for normal settlement)
            is_winner = (bet['selection'] == winning_selection)
            
            if is_winner:
                # Update bet status to won
                conn.execute("""
                    UPDATE bets 
                    SET status = 'won', actual_return = ?, settled_at = ?
                    WHERE id = ?
                """, (bet['potential_return'], datetime.now(), bet['id']))
                
                won_count += 1
                total_payout += bet['potential_return']
                
                # Credit user account
                conn.execute("""
                    UPDATE bets 
                    SET status = 'won', actual_return = ?, settled_at = ?
                    WHERE id = ?
                """, (bet['potential_return'], datetime.now(), bet['id']))
                
                won_count += 1
                total_payout += bet['potential_return']
                
                # Credit user account
                conn.execute("""
                    UPDATE users 
                    SET balance = balance + ?
                    WHERE id = ?
                """, (bet['potential_return'], bet['user_id']))
                
                # Create transaction record
                conn.execute("""
                    INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at)
                    VALUES (?, ?, ?, 'win', ?, ?, ?, ?)
                """, (
                    bet['user_id'], 
                    bet['id'], 
                    bet['potential_return'],
                    f'Bet win - {bet["match_name"]} ({bet["selection"]})',
                    bet['potential_return'],  # balance_before (simplified)
                    bet['potential_return'] * 2,  # balance_after (simplified)
                    datetime.now()
                ))
                
            else:
                # Update bet status to lost
                conn.execute("""
                    UPDATE bets 
                    SET status = 'lost', actual_return = 0, settled_at = ?
                    WHERE id = ?
                """, (datetime.now(), bet['id']))
                
                lost_count += 1
            
            settled_count += 1
        
        conn.commit()
        conn.close()
        
        # Prepare success message based on settlement type
        if winning_selection == 'no_result':
            message = f'Cancelled {settled_count} bets across all operators - stakes refunded'
        else:
            message = f'Settled {settled_count} bets across all operators'
        
        return jsonify({
            'success': True,
            'message': message,
            'settled_count': settled_count,
            'won_count': won_count,
            'lost_count': lost_count,
            'total_payout': total_payout,
            'settlement_type': 'cancelled' if winning_selection == 'no_result' else 'normal'
        })
        
    except Exception as e:
        logger.error(f"Error manually settling global bets: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

def get_comprehensive_superadmin_template():
    """Get the comprehensive super admin HTML template"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoalServe - Super Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #f39c12 0%, #e74c3c 100%); min-height: 100vh; }
        .header { background: rgba(0,0,0,0.1); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; color: white; }
        .header h1 { font-size: 1.5rem; }
        .logout-btn { background: #c0392b; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; }
        .container { max-width: 1600px; margin: 2rem auto; padding: 0 1rem; }
        .tabs { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .tab { background: rgba(255,255,255,0.1); color: white; border: none; padding: 1rem 2rem; border-radius: 10px; cursor: pointer; transition: all 0.3s; }
        .tab.active { background: rgba(255,255,255,0.2); transform: translateY(-2px); }
        .tab-content { background: white; border-radius: 15px; padding: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.1); display: none; }
        .tab-content.active { display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card { background: linear-gradient(135deg, #f39c12, #e74c3c); color: white; padding: 1.5rem; border-radius: 10px; text-align: center; }
        .stat-number { font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }
        .stat-label { opacity: 0.9; }
        .data-table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }
        .data-table th, .data-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }
        .data-table th { background: #f8f9fa; font-weight: 600; }
        .btn { padding: 0.4rem 0.8rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem; margin: 0 0.2rem; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-primary { background: #3498db; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .status-active { background: #27ae60; color: white; padding: 0.25rem 0.5rem; border-radius: 3px; font-size: 0.8rem; }
        .status-disabled { background: #e74c3c; color: white; padding: 0.25rem 0.5rem; border-radius: 3px; font-size: 0.8rem; }
        .loading { text-align: center; padding: 2rem; color: #666; }
        .reports-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 2rem; }
        .report-card { background: #f8f9fa; padding: 1.5rem; border-radius: 10px; border-left: 4px solid #f39c12; }
        .report-title { font-weight: 600; margin-bottom: 1rem; color: #333; }
        .operator-card { background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #3498db; }
        .operator-name { font-weight: 600; color: #2c3e50; margin-bottom: 0.5rem; }
        .operator-stats { display: flex; gap: 1rem; font-size: 0.9rem; color: #666; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
        .modal-content { background: white; margin: 15% auto; padding: 2rem; width: 400px; border-radius: 10px; }
        .modal-header { font-weight: 600; margin-bottom: 1rem; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
        .form-group input { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌟 GoalServe - Super Admin Dashboard</h1>
        <div>
            <span>Global Management</span>
            <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('global-betting-events')">📊 Global Betting Events</button>
            <button class="tab" onclick="showTab('manual-settlement')">💰 Manual Settlement</button>
            <button class="tab" onclick="showTab('global-user-management')">👥 Global User Management</button>
            <button class="tab" onclick="showTab('global-reports')">📈 Global Reports</button>
            <button class="tab" onclick="showTab('operator-management')">🏢 Operator Management</button>
            <button class="tab" onclick="showTab('global-report-builder')">🔧 Global Report Builder</button>
        </div>

        <!-- Global Betting Events Tab -->
        <div id="global-betting-events" class="tab-content active">
            <h2>Global Betting Events Management</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="global-total-events">-</div>
                    <div class="stat-label">Total Events</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-active-events">-</div>
                    <div class="stat-label">Active Events</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-total-liability">$0.00</div>
                    <div class="stat-label">Global Liability</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-total-revenue-events">$0.00</div>
                    <div class="stat-label">Global Revenue</div>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="refreshGlobalEvents()">🔄 Refresh Global Events</button>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Event ID</th>
                        <th>Sport</th>
                        <th>Event Name</th>
                        <th>Market</th>
                        <th>Operator</th>
                        <th>Total Bets</th>
                        <th>Liability</th>
                        <th>Revenue</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="global-events-table">
                    <tr><td colspan="9" class="loading">Loading global events...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Manual Settlement Tab -->
        <div id="manual-settlement" class="tab-content">
            <h2>Global Manual Bet Settlement</h2>
            <p style="margin-bottom: 1rem; color: #666;">Manually settle pending bets across all operators by setting match outcomes</p>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-matches">-</div>
                    <div class="stat-label">Total Matches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-liability">$0.00</div>
                    <div class="stat-label">Total Liability</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="pending-bets">-</div>
                    <div class="stat-label">Pending Bets</div>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="loadSettlementData()">🔄 Refresh Settlement Data</button>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Match & Market</th>
                        <th>Operator</th>
                        <th>Bet Summary</th>
                        <th>Outcomes</th>
                        <th>Total Liability</th>
                        <th>Settlement</th>
                    </tr>
                </thead>
                <tbody id="settlement-table">
                    <tr><td colspan="6" class="loading">Loading settlement data...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Global User Management Tab -->
        <div id="global-user-management" class="tab-content">
            <h2>Global User Management</h2>
            <p style="margin-bottom: 1rem; color: #666;">Manage users across all sportsbook operators</p>
            <button class="btn btn-primary" onclick="refreshGlobalUsers()">🔄 Refresh Global Users</button>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Operator</th>
                        <th>Balance</th>
                        <th>Bets</th>
                        <th>Staked</th>
                        <th>Payout</th>
                        <th>Profit</th>
                        <th>Joined</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="global-users-table">
                    <tr><td colspan="12" class="loading">Loading global users...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Global Reports Tab -->
        <div id="global-reports" class="tab-content">
            <h2>Global Reports & Analytics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="global-total-bets-report">-</div>
                    <div class="stat-label">Global Total Bets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-total-stakes-report">$0</div>
                    <div class="stat-label">Global Total Stakes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-total-revenue-report">$0</div>
                    <div class="stat-label">Global Total Revenue</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="global-win-rate-report">0%</div>
                    <div class="stat-label">Global Win Rate</div>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="refreshGlobalReports()">🔄 Refresh Global Reports</button>
            
            <div class="reports-grid">
                <div class="report-card">
                    <div class="report-title">📊 Global Betting Overview</div>
                    <div id="global-betting-overview">Loading...</div>
                </div>
                <div class="report-card">
                    <div class="report-title">🏆 Global Sport Performance</div>
                    <div id="global-sport-performance">Loading...</div>
                </div>
                <div class="report-card">
                    <div class="report-title">👑 Global Top Users</div>
                    <div id="global-top-users">Loading...</div>
                </div>
            </div>
        </div>

        <!-- Operator Management Tab -->
        <div id="operator-management" class="tab-content">
            <h2>🏢 Operator Management</h2>
            <p style="margin-bottom: 1rem; color: #666;">Manage all sportsbook operators</p>
            <button class="btn btn-primary" onclick="refreshOperators()">🔄 Refresh Operators</button>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Sportsbook Name</th>
                        <th>Subdomain</th>
                        <th>Admin Username</th>
                        <th>Admin Email</th>
                        <th>Users</th>
                        <th>Bets</th>
                        <th>Revenue</th>
                        <th>Created</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="operators-table">
                    <tr><td colspan="11" class="loading">Loading operators...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Global Report Builder Tab -->
        <div id="global-report-builder" class="tab-content">
            <h2>🔧 Global Report Builder</h2>
            <p>Generate comprehensive reports across all sportsbook operators</p>
            <div style="margin-top: 2rem;">
                <h3>📋 Available Global Reports</h3>
                <ul style="margin-top: 1rem; line-height: 2;">
                    <li><strong>Global Betting Summary:</strong> Betting activity across all operators</li>
                    <li><strong>Operator Performance:</strong> Revenue and performance by operator</li>
                    <li><strong>Global User Activity:</strong> User statistics across all platforms</li>
                    <li><strong>Global Financial Overview:</strong> Comprehensive financial metrics</li>
                    <li><strong>Cross-Platform Analytics:</strong> Comparative analysis between operators</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Change Password Modal -->
    <div id="passwordModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">Change Operator Password</div>
            <div class="form-group">
                <label>New Password:</label>
                <input type="password" id="newPassword" placeholder="Enter new password (min 6 characters)">
            </div>
            <div style="text-align: right;">
                <button class="btn btn-primary" onclick="saveNewPassword()">Save</button>
                <button class="btn" onclick="closePasswordModal()">Cancel</button>
            </div>
        </div>
    </div>

    <script>
        let currentOperatorId = null;
        
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load data for the tab
            if (tabName === 'global-betting-events') loadGlobalBettingEvents();
            if (tabName === 'global-user-management') loadGlobalUsers();
            if (tabName === 'global-reports') loadGlobalReports();
            if (tabName === 'operator-management') loadOperators();
        }
        
        function loadGlobalBettingEvents() {
            fetch('/api/superadmin/global-betting-events')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('global-total-events').textContent = data.total_events;
                        document.getElementById('global-active-events').textContent = data.active_events;
                        
                        const tbody = document.getElementById('global-events-table');
                        if (data.events.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #666;">No events found</td></tr>';
                        } else {
                            tbody.innerHTML = data.events.map(event => `
                                <tr>
                                    <td>${event.event_id}</td>
                                    <td>${event.sport}</td>
                                    <td>${event.event_name}</td>
                                    <td>${event.market}</td>
                                    <td><strong>${event.operator}</strong></td>
                                    <td>${event.total_bets}</td>
                                    <td>$${event.max_liability.toFixed(2)}</td>
                                    <td>$${event.max_possible_gain.toFixed(2)}</td>
                                    <td><span class="status-active">${event.status}</span></td>
                                </tr>
                            `).join('');
                        }
                    }
                })
                .catch(err => console.error('Error loading global events:', err));
        }
        
        function loadGlobalUsers() {
            fetch('/api/superadmin/global-users')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('global-users-table');
                        if (data.users.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; color: #666;">No users found</td></tr>';
                        } else {
                            tbody.innerHTML = data.users.map(user => `
                                <tr>
                                    <td>${user.id}</td>
                                    <td>${user.username}</td>
                                    <td>${user.email}</td>
                                    <td><strong>${user.operator}</strong></td>
                                    <td>$${user.balance.toFixed(2)}</td>
                                    <td>${user.total_bets}</td>
                                    <td>$${user.total_staked.toFixed(2)}</td>
                                    <td>$${user.total_payout.toFixed(2)}</td>
                                    <td>$${user.cumulative_profit.toFixed(2)}</td>
                                    <td>${user.joined}</td>
                                    <td><span class="status-${user.is_active ? 'active' : 'disabled'}">${user.status}</span></td>
                                    <td>
                                        <button class="btn ${user.is_active ? 'btn-danger' : 'btn-success'}" 
                                                onclick="toggleGlobalUser(${user.id}, ${user.is_active})">
                                            ${user.is_active ? 'Disable' : 'Enable'}
                                        </button>
                                    </td>
                                </tr>
                            `).join('');
                        }
                    }
                })
                .catch(err => console.error('Error loading global users:', err));
        }
        
        function loadGlobalReports() {
            fetch('/api/superadmin/global-reports')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const stats = data.stats;
                        document.getElementById('global-total-bets-report').textContent = stats.total_bets;
                        document.getElementById('global-total-stakes-report').textContent = `$${stats.total_stakes.toFixed(2)}`;
                        document.getElementById('global-total-revenue-report').textContent = `$${stats.total_revenue.toFixed(2)}`;
                        document.getElementById('global-win-rate-report').textContent = `${stats.win_rate}%`;
                        
                        // Global Betting Overview
                        document.getElementById('global-betting-overview').innerHTML = `
                            <div>Pending Bets: <strong>${stats.pending_bets}</strong></div>
                            <div>Won Bets: <strong>${stats.won_bets}</strong></div>
                            <div>Lost Bets: <strong>${stats.lost_bets}</strong></div>
                        `;
                        
                        // Global Sport Performance
                        document.getElementById('global-sport-performance').innerHTML = 
                            data.sport_performance.map(sport => 
                                `<div>${sport.sport}: <strong>$${sport.revenue.toFixed(2)}</strong></div>`
                            ).join('') || '<div>No data available</div>';
                        
                        // Global Top Users
                        document.getElementById('global-top-users').innerHTML = 
                            data.top_users.map(user => 
                                `<div>${user.username} (${user.operator}): <strong>${user.bets} bets</strong></div>`
                            ).join('') || '<div>No data available</div>';
                    }
                })
                .catch(err => console.error('Error loading global reports:', err));
        }
        
        function loadOperators() {
            fetch('/api/superadmin/operators')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('operators-table');
                        if (data.operators.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="11" style="text-align: center; color: #666;">No operators found</td></tr>';
                        } else {
                            tbody.innerHTML = data.operators.map(op => `
                                <tr>
                                    <td>${op.id}</td>
                                    <td><strong>${op.sportsbook_name}</strong></td>
                                    <td>${op.subdomain}</td>
                                    <td>${op.admin_username}</td>
                                    <td>${op.admin_email}</td>
                                    <td>${op.total_users}</td>
                                    <td>${op.total_bets}</td>
                                    <td>$${op.revenue.toFixed(2)}</td>
                                    <td>${op.created_at}</td>
                                    <td><span class="status-${op.is_active ? 'active' : 'disabled'}">${op.status}</span></td>
                                    <td>
                                        <button class="btn ${op.is_active ? 'btn-danger' : 'btn-success'}" 
                                                onclick="toggleOperator(${op.id}, ${op.is_active})">
                                            ${op.is_active ? 'Disable' : 'Enable'}
                                        </button>
                                        <button class="btn btn-warning" onclick="changeOperatorPassword(${op.id})">
                                            Change Password
                                        </button>
                                    </td>
                                </tr>
                            `).join('');
                        }
                    }
                })
                .catch(err => console.error('Error loading operators:', err));
        }
        
        function toggleGlobalUser(userId, isActive) {
            fetch('/api/superadmin/toggle-global-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadGlobalUsers();
                    alert(data.message);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error toggling global user:', err);
                alert('Failed to toggle user status');
            });
        }
        
        function toggleOperator(operatorId, isActive) {
            if (confirm(`Are you sure you want to ${isActive ? 'disable' : 'enable'} this operator?`)) {
                fetch('/api/superadmin/toggle-operator', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ operator_id: operatorId })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        loadOperators();
                        alert(data.message);
                    } else {
                        alert('Error: ' + data.error);
                    }
                })
                .catch(err => {
                    console.error('Error toggling operator:', err);
                    alert('Failed to toggle operator status');
                });
            }
        }
        
        function changeOperatorPassword(operatorId) {
            currentOperatorId = operatorId;
            document.getElementById('passwordModal').style.display = 'block';
            document.getElementById('newPassword').value = '';
        }
        
        function closePasswordModal() {
            document.getElementById('passwordModal').style.display = 'none';
            currentOperatorId = null;
        }
        
        function saveNewPassword() {
            const newPassword = document.getElementById('newPassword').value;
            if (!newPassword || newPassword.length < 6) {
                alert('Password must be at least 6 characters');
                return;
            }
            
            fetch('/api/superadmin/change-operator-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    operator_id: currentOperatorId,
                    new_password: newPassword
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    closePasswordModal();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error changing password:', err);
                alert('Failed to change password');
            });
        }
        
        function refreshGlobalEvents() { loadGlobalBettingEvents(); }
        function refreshGlobalUsers() { loadGlobalUsers(); }
        function refreshGlobalReports() { loadGlobalReports(); }
        function refreshOperators() { loadOperators(); }
        
        // Manual Settlement Functions
        async function loadSettlementData() {
            try {
                const response = await fetch('/api/superadmin/manual-settlement');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('settlement-table').innerHTML = 
                        `<tr><td colspan="6" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                if (!data.success) {
                    document.getElementById('settlement-table').innerHTML = 
                        `<tr><td colspan="6" class="error">Error: ${data.error || 'Failed to load data'}</td></tr>`;
                    return;
                }
                
                const settlementData = data.data;
                
                // Update summary cards
                document.getElementById('total-matches').textContent = settlementData.length;
                document.getElementById('total-liability').textContent = `$${settlementData.reduce((sum, item) => sum + item.total_liability, 0).toFixed(2)}`;
                document.getElementById('pending-bets').textContent = settlementData.reduce((sum, item) => sum + item.bets.length, 0);
                
                // Update table
                const tbody = document.getElementById('settlement-table');
                if (settlementData.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="loading">No pending bets to settle</td></tr>';
                } else {
                    tbody.innerHTML = settlementData.map(item => `
                        <tr>
                            <td>
                                <div style="font-weight: 600;">${item.match_name}</div>
                                <div style="font-size: 0.9rem; color: #666;">${item.sport_name} • ${item.market}</div>
                            </td>
                            <td>${item.operator_name}</td>
                            <td>
                                <div style="font-weight: 600;">${item.bets.length} bets</div>
                                <div style="font-size: 0.9rem; color: #666;">Total Stake: $${item.total_stake.toFixed(2)}</div>
                            </td>
                            <td>${item.outcomes.join(', ')}</td>
                            <td class="liability">$${item.total_liability.toFixed(2)}</td>
                            <td>
                                <select class="outcome-select" id="outcome_${item.match_id}_${item.market}" style="margin-bottom: 0.5rem; width: 100%; padding: 0.3rem; border: 1px solid #ddd; border-radius: 4px;">
                                    <option value="no_result">No Result (Cancel & Refund)</option>
                                    ${item.outcomes.map(outcome => `<option value="${outcome}">${outcome}</option>`).join('')}
                                </select>
                                <button class="btn btn-warning" onclick="settleBets('${item.match_id}', '${item.market}', '${item.match_name}')" style="width: 100%;">
                                    Settle
                                </button>
                            </td>
                        </tr>
                    `).join('');
                }
                
            } catch (error) {
                document.getElementById('settlement-table').innerHTML = 
                    `<tr><td colspan="6" class="error">Error loading settlement data: ${error.message}</td></tr>`;
            }
        }
        
        async function settleBets(matchId, market, matchName) {
            const outcomeSelect = document.getElementById(`outcome_${matchId}_${market}`);
            const winningSelection = outcomeSelect.value;
            
            if (!winningSelection) {
                alert('Please select a winning outcome');
                return;
            }
            
            // Confirm settlement
            let confirmMessage;
            if (winningSelection === 'no_result') {
                confirmMessage = `Are you sure you want to CANCEL ${matchName}?\n\nAction: No Result (Cancel & Refund)\n\nThis will:\n• Cancel all bets for this match\n• Refund all stakes to users\n• Mark bets as "voided"\n\nThis action cannot be undone.`;
            } else {
                confirmMessage = `Are you sure you want to settle ${matchName}?\n\nWinning selection: ${winningSelection}\n\nThis action cannot be undone.`;
            }
            
            if (!confirm(confirmMessage)) {
                return;
            }
            
            try {
                const response = await fetch('/api/superadmin/manual-settle', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        match_id: matchId,
                        market: market,
                        winning_selection: winningSelection
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (data.settlement_type === 'cancelled') {
                        alert(`✅ Successfully cancelled ${data.settled_count} bets!\n\nAll stakes have been refunded to users.\n\nBets marked as "voided"`);
                    } else {
                        alert(`✅ Successfully settled ${data.settled_count} bets!\n\nWon: ${data.won_count}\nLost: ${data.lost_count}\nTotal Payout: $${data.total_payout.toFixed(2)}`);
                    }
                    // Refresh the settlement data
                    loadSettlementData();
                } else {
                    alert('Failed to settle bets: ' + (data.error || 'Unknown error'));
                }
                
            } catch (error) {
                alert('Error settling bets: ' + error.message);
            }
        }
        
        function logout() {
            if (confirm('Are you sure you want to logout?')) {
                window.location.href = '/superadmin/logout';
            }
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('passwordModal');
            if (event.target == modal) {
                closePasswordModal();
            }
        }
        
        // Load initial data
        loadGlobalBettingEvents();
    </script>
</body>
</html>
    """

