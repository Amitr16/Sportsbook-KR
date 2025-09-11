"""
Rich Super Admin Interface - Based on original admin_app.py but with global scope
Same rich interface as admin_app.py but shows data across all operators
"""

from flask import Blueprint, request, session, redirect, render_template_string, jsonify
from src import sqlite3_shim as sqlite3
import json
from datetime import datetime, timedelta
import os
from sqlalchemy import text

rich_superadmin_bp = Blueprint('rich_superadmin', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def update_operator_revenue(operator_id, conn):
    """Update the total_revenue field for an operator based on actual bet settlements"""
    try:
        # Calculate current total revenue from actual bet settlements
        revenue_query = """
        SELECT 
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = ?
        """
        
        result = conn.execute(revenue_query, (operator_id,)).fetchone()
        total_stakes_lost = float(result['total_stakes_lost'] or 0)
        total_net_payouts = float(result['total_net_payouts'] or 0)
        total_revenue = total_stakes_lost - total_net_payouts
        
        # Update the operator's total_revenue field
        conn.execute("""
            UPDATE sportsbook_operators 
            SET total_revenue = ? 
            WHERE id = ?
        """, (total_revenue, operator_id))
        
        print(f"✅ Updated operator {operator_id} total_revenue to: {total_revenue}")
        
    except Exception as e:
        print(f"❌ Error updating operator revenue: {e}")

def calculate_global_event_financials(event_id, market_id, sport_name):
    """Calculate max liability and max possible gain for a specific event+market combination across ALL operators"""
    try:
        conn = get_db_connection()
        
        # Get all pending bets for this specific event+market combination from ALL operators
        query = """
        SELECT b.bet_selection, b.stake, b.potential_return, b.odds
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
        WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
        AND op.is_active = TRUE
        """
        
        bets = conn.execute(query, (event_id, market_id, sport_name)).fetchall()
        conn.close()
        
        if not bets:
            return 0.0, 0.0  # No bets = no liability or gain
        
        # Group bets by selection (outcome)
        selections = {}
        total_stakes = 0
        
        for bet in bets:
            selection = bet['bet_selection']
            stake = float(bet['stake'])
            potential_return = float(bet['potential_return'])
            
            if selection not in selections:
                selections[selection] = {'total_stake': 0, 'total_payout': 0}
            
            selections[selection]['total_stake'] += stake
            selections[selection]['total_payout'] += potential_return
            total_stakes += stake
        
        # Calculate profit/loss for each possible outcome
        outcomes = []
        for selection, data in selections.items():
            # If this selection wins: pay out winners, keep losing stakes
            payout = data['total_payout']
            profit_loss = total_stakes - payout
            outcomes.append(profit_loss)
        
        # Max liability = worst case (most negative outcome)
        max_liability = abs(min(outcomes)) if outcomes else 0.0
        
        # Max possible gain = best case (most positive outcome)  
        max_possible_gain = max(outcomes) if outcomes else 0.0
        
        return max_liability, max_possible_gain
        
    except Exception as e:
        print(f"Error calculating global financials: {e}")
        return 0.0, 0.0

def check_superadmin_auth(f):
    """Decorator to check if user is authenticated as super admin"""
    def decorated_function(*args, **kwargs):
        from src.auth.session_utils import is_superadmin_logged_in
        if not is_superadmin_logged_in():
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@rich_superadmin_bp.route('/superadmin/rich-dashboard')
@check_superadmin_auth
def rich_superadmin_dashboard():
    """Rich super admin dashboard with same interface as original admin_app.py"""
    from flask import make_response
    response = make_response(render_template_string(RICH_SUPERADMIN_TEMPLATE))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@rich_superadmin_bp.route('/test-toggle-status', methods=['POST'])
def test_toggle_status():
    """Test endpoint for toggle status without authentication"""
    try:
        # Test the toggle logic with a dummy event
        event_id = "test_event_123"
        sport_name = "test_sport"
        event_name = "Test Event"
        market_name = "test_market"
        
        conn = get_db_connection()
        
        # Test the INSERT statement that was causing the boolean error
        conn.execute("""
            INSERT INTO disabled_events (event_key, sport, event_name, market, is_disabled)
            VALUES (?, ?, ?, ?, TRUE)
            ON CONFLICT (event_key) DO UPDATE SET
                sport = EXCLUDED.sport,
                event_name = EXCLUDED.event_name,
                market = EXCLUDED.market,
                is_disabled = EXCLUDED.is_disabled
        """, (event_id, sport_name, event_name, market_name))
        
        # Clean up - remove the test record
        conn.execute("DELETE FROM disabled_events WHERE event_key = ?", (event_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Database constraint fix test passed - ON CONFLICT working correctly'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-betting-events', methods=['GET', 'POST'])
@check_superadmin_auth
def get_global_betting_events():
    """Get global betting events across all operators with global liability calculations"""
    try:
        # Handle both GET and POST methods
        if request.method == 'GET':
            # GET method - get parameters from query string
            show_bets_only = request.args.get('show_only_with_bets', 'false').lower() == 'true'
            sport_filter = request.args.get('sport', '')
            market_filter = request.args.get('market', '')
            search_term = request.args.get('search', '')
        else:
            # POST method - get parameters from JSON body
            data = request.get_json() or {}
            show_bets_only = data.get('show_bets_only', True)
            sport_filter = data.get('sport', '')
            market_filter = data.get('market', '')
            search_term = data.get('search', '')

        print(f"🔍 DEBUG: Global betting events - show_bets_only = {show_bets_only}")
        print(f"🔍 DEBUG: Method = {request.method}")

        conn = get_db_connection()
        
        # First, query the database to find which event_market combinations have bets across all operators
        if show_bets_only:
            # Get events with bets from database first
            bet_events_query = """
                SELECT DISTINCT b.match_id, b.sport_name, b.market, COUNT(*) as bet_count
        FROM bets b
                JOIN users u ON b.user_id = u.id 
                JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
                WHERE op.is_active = TRUE
                GROUP BY b.match_id, b.sport_name, b.market
                HAVING COUNT(*) > 0
                ORDER BY bet_count DESC
            """
            bet_events_result = conn.execute(bet_events_query).fetchall()
            
            # Create a set of events to load
            events_to_load = set()
            for row in bet_events_result:
                match_id = str(row['match_id'])
                sport_name = str(row['sport_name'])
                market_id = str(row['market'])
                events_to_load.add((match_id, sport_name, market_id))
        
        # Load sports and events data directly from JSON files
        import os
        import json
        
        # Path to Sports Pre Match directory
        sports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Sports Pre Match')
        
        if not os.path.exists(sports_dir):
            return jsonify({'error': 'Sports directory not found'})
        
        all_events = []
        all_sports = set()
        all_markets = set()
        
        # Load sports data
        sport_folders = [f for f in os.listdir(sports_dir) if os.path.isdir(os.path.join(sports_dir, f))]
        
        for sport_folder in sport_folders:
            sport_path = os.path.join(sports_dir, sport_folder)
            sport_display_name = sport_folder.title()
            
            # Apply sport filter if specified
            if sport_filter and sport_display_name.lower() != sport_filter.lower():
                continue
            
            # Load events for this sport
            events_file = os.path.join(sport_path, f'{sport_folder}_odds.json')
            
            if os.path.exists(events_file):
                try:
                    with open(events_file, 'r', encoding='utf-8') as f:
                        sport_data = json.load(f)
                    
                    # Extract events from the JSON structure
                    sport_events = []
                    if 'odds_data' in sport_data and 'scores' in sport_data['odds_data'] and 'categories' in sport_data['odds_data']['scores']:
                        for category in sport_data['odds_data']['scores']['categories']:
                            if 'matches' in category:
                                # Add category info to each match
                                for match in category['matches']:
                                    match['_category_name'] = category.get('name', 'Unknown Category')
                                sport_events.extend(category['matches'])
                    
                    # Process each event
                    for event in sport_events:
                        event_id = event.get('id', '')
                        
                        # Process markets/odds
                        if 'odds' in event:
                            for odd in event['odds']:
                                market_name = odd.get('value', '').lower()
                                market_id = odd.get('id', '')
                                
                                if not market_id:
                                    continue
                                
                                # If we're only showing events with bets, check if this event_market has bets
                                if show_bets_only:
                                    event_key = (str(event_id), str(sport_folder), str(market_id))
                                    if event_key not in events_to_load:
                                        continue  # Skip this event_market combination
                                
                                # Apply market filter if specified
                                if market_filter and market_name.lower() != market_filter.lower():
                                    continue
                                
                                # Apply search filter if specified
                                event_name = f"{event.get('localteam', {}).get('name', 'Unknown')} vs {event.get('awayteam', {}).get('name', 'Unknown')}"
                                if search_term and search_term.lower() not in event_name.lower() and search_term.lower() not in str(event_id).lower():
                                    continue
                                
                                # Add to sports and markets filters
                                all_sports.add(sport_display_name)
                                all_markets.add(market_name)
                                
                                # Create betting event entry
                                betting_event = {
                                    'id': f"{event_id}_{market_id}",
                                    'unique_id': f"{event_id}_{market_id}",
                                    'event_id': f"{event_id}_{market_id}",
                                    'sport': sport_display_name,
                                    'event_name': event_name,
                                    'market': market_name,
                                    'market_display': market_name,
                                    'category': event.get('_category_name', 'Unknown Category'),
                                    'odds_data': [],  # We'll populate this if needed
                                    'is_active': True,
                                    'date': event.get('date', ''),
                                    'time': event.get('time', ''),
                                    'status': 'active' if event.get('status', 'Unknown').lower() != 'finished' else 'finished'
                                }
                                
                                # Check if this event is disabled by checking bets.is_active status
                                # If any bets for this event/market are inactive, mark the event as disabled
                                active_check = conn.execute("""
                                    SELECT COUNT(*) as active_count, COUNT(*) as total_count
                                    FROM bets b 
                                    JOIN users u ON b.user_id = u.id 
                                    JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
                                    WHERE op.is_active = TRUE AND b.match_id = ? AND b.sport_name = ? AND b.market = ? AND b.is_active = TRUE
                                """, (event_id, sport_folder, market_id)).fetchone()
                                
                                total_check = conn.execute("""
                                    SELECT COUNT(*) as total_count
                                    FROM bets b 
                                    JOIN users u ON b.user_id = u.id 
                                    JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
                                    WHERE op.is_active = TRUE AND b.match_id = ? AND b.sport_name = ? AND b.market = ?
                                """, (event_id, sport_folder, market_id)).fetchone()
                                
                                total_bets_for_event = total_check['total_count'] if total_check else 0
                                active_bets_for_event = active_check['active_count'] if active_check else 0
                                
                                # If there are bets but none are active, mark as disabled
                                if total_bets_for_event > 0 and active_bets_for_event == 0:
                                    betting_event['is_active'] = False
                                    betting_event['status'] = 'disabled'
                                else:
                                    betting_event['is_active'] = True
                                    betting_event['status'] = 'active'
                                
                                # Calculate global financials for this event (across all operators)
                                max_liability, max_possible_gain = calculate_global_event_financials(event_id, market_id, sport_folder)
                                betting_event['max_liability'] = max_liability
                                betting_event['max_possible_gain'] = max_possible_gain
                                
                                # Add fields expected by the dashboard
                                betting_event['name'] = event_name
                                betting_event['liability'] = max_liability
                                betting_event['revenue'] = max_possible_gain
                                
                                # Get total bets for this event across all operators
                                bet_count_result = conn.execute("""
                                    SELECT COUNT(*) as count
                                    FROM bets b 
                                    JOIN users u ON b.user_id = u.id 
                                    JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
                                    WHERE op.is_active = TRUE AND b.match_id = ? AND b.sport_name = ? AND b.market = ?
                                """, (event_id, sport_folder, market_id)).fetchone()
                                total_bets = bet_count_result['count'] if bet_count_result else 0
                                betting_event['total_bets'] = total_bets
                                
                                all_events.append(betting_event)
                                
                except Exception as e:
                    print(f"Error loading events for {sport_folder}: {e}")
                    continue
        
        conn.close()
        
        # Calculate global summary
        total_events = len(all_events)
        active_events = len([e for e in all_events if e['status'] == 'active'])
        max_liability = max([e['liability'] for e in all_events]) if all_events else 0
        max_gain = max([e['revenue'] for e in all_events]) if all_events else 0
        
        sports = list(all_sports)
        markets = list(all_markets)
        
        return jsonify({
            'success': True,
            'events': all_events,
            'pagination': {
            'page': 1,
                'per_page': len(all_events),
                'total': total_events,
                'pages': 1
            },
            'summary': {
                'total_events': total_events,  # Show total available events, not filtered count
                'active_events': active_events,  # Count from all events
                'total_liability': max_liability,
                'max_liability': max_liability,
                'max_possible_gain': max_gain
            },
            'filters': {
                'sports': sports,
                'markets': markets
            }
        })
        
    except Exception as e:
        print(f"Error fetching global betting events: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-betting-events/toggle-status', methods=['POST'])
@check_superadmin_auth
def toggle_global_event_status():
    """Toggle the status of a global betting event"""
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        new_status = data.get('status')
        
        if not event_id or not new_status:
            return jsonify({'success': False, 'error': 'Missing event_id or status'}), 400
            
        conn = get_db_connection()
        
        # Extract match_id and market from event_id format "6200217_2"
        if '_' in event_id:
            base_event_id, market = event_id.split('_', 1)
        else:
            base_event_id = event_id
            market = None
        
        # APPROACH 1: Update bets.is_active for backend processing
        if new_status == 'disabled':
            # Mark all bets for this event/market combination as inactive
            if market:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = FALSE 
                    WHERE match_id = ? AND market = ?
                """, (base_event_id, market))
            else:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = FALSE 
                    WHERE match_id = ?
                """, (base_event_id,))
        else:
            # Mark all bets for this event/market combination as active
            if market:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = TRUE 
                    WHERE match_id = ? AND market = ?
                """, (base_event_id, market))
            else:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = TRUE 
                    WHERE match_id = ?
                """, (base_event_id,))
        
        # APPROACH 2: Update disabled_events table for frontend filtering
        if new_status == 'disabled':
            # Disable event by adding to disabled_events table
            # Get event details for the table
            event_details = conn.execute("""
                SELECT sport_name, match_name, market 
                FROM bets 
                WHERE match_id = ? AND market = ? 
                LIMIT 1
            """, (base_event_id, market)).fetchone()
            
            if event_details:
                sport_name = event_details['sport_name']
                event_name = event_details['match_name'] or 'Unknown Event'  # Use match_name from bets table
                market_name = event_details['market'] or 'Unknown Market'
            else:
                sport_name = 'Unknown Sport'
                event_name = 'Unknown Event'
                market_name = 'Unknown Market'
            
            # Insert into disabled_events table
            conn.execute("""
                INSERT INTO disabled_events (event_key, sport, event_name, market, is_disabled)
                VALUES (?, ?, ?, ?, TRUE)
                ON CONFLICT (event_key) DO UPDATE SET
                    sport = EXCLUDED.sport,
                    event_name = EXCLUDED.event_name,
                    market = EXCLUDED.market,
                    is_disabled = EXCLUDED.is_disabled
            """, (event_id, sport_name, event_name, market_name))
            
        else:
            # Enable event by removing from disabled_events table
            conn.execute("DELETE FROM disabled_events WHERE event_key = ?", (event_id,))
        
        conn.commit()
        conn.close()
        
        # Return success if either bets were updated or disabled_events was updated
        if bets_result.rowcount > 0 or new_status == 'disabled':
            return jsonify({'success': True, 'message': f'Event status updated to {new_status}'})
        else:
            return jsonify({'success': False, 'error': 'Event not found'})
            
    except Exception as e:
        print(f"Error toggling global event status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-users')
@check_superadmin_auth
def get_global_users():
    """Get all users across all operators"""
    
    try:
        conn = get_db_connection()
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        # Get all users with operator information
        users_query = """
        SELECT u.id, u.username, u.email, u.balance, u.created_at, u.is_active,
               so.sportsbook_name as operator_name,
               (SELECT COUNT(*) FROM bets WHERE user_id = u.id) as total_bets,
               (SELECT COALESCE(SUM(stake), 0) FROM bets WHERE user_id = u.id AND status IN ('won', 'lost', 'void')) as total_staked,
               (SELECT COALESCE(SUM(potential_return), 0) FROM bets WHERE user_id = u.id AND status = 'won') as total_payout,
               (SELECT COALESCE(SUM(CASE WHEN status IN ('won', 'lost', 'void') THEN stake ELSE 0 END), 0) - 
                COALESCE(SUM(CASE WHEN status = 'won' THEN potential_return ELSE 0 END), 0) FROM bets WHERE user_id = u.id) as profit
        FROM users u
        LEFT JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
        ORDER BY u.created_at DESC
        LIMIT ? OFFSET ?
        """
        
        users = conn.execute(users_query, (per_page, offset)).fetchall()
        
        # Get total count
        total_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'users': [dict(user) for user in users],
            'total': total_count,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-users/reset', methods=['POST'])
@check_superadmin_auth
def reset_all_global_users():
    """Reset all users across all operators - superadmin only"""
    try:
        data = request.get_json()
        new_balance = float(data.get('new_balance', 0))
        
        if new_balance < 0:
            return jsonify({'success': False, 'error': 'Balance must be 0 or greater'}), 400
        
        conn = get_db_connection()
        
        # Cancel all pending bets and refund stakes
        bets_cancelled = conn.execute("""
            UPDATE bets 
            SET status = 'cancelled' 
            WHERE status = 'pending'
        """).rowcount
        
        # Reset all user balances
        users_reset = conn.execute("""
            UPDATE users 
            SET balance = ?
        """, (new_balance,)).rowcount
        
        # Update default balance for all operators
        import json
        
        # First get all operators and update their settings
        operators = conn.execute("SELECT id, settings FROM sportsbook_operators").fetchall()
        
        for operator in operators:
            try:
                settings = json.loads(operator['settings']) if operator['settings'] else {}
                settings['default_user_balance'] = new_balance
                
                conn.execute("""
                    UPDATE sportsbook_operators 
                    SET settings = ? 
                    WHERE id = ?
                """, (json.dumps(settings), operator['id']))
            except Exception as e:
                print(f"Error updating operator {operator['id']} settings: {e}")
                # If JSON parsing fails, create a new settings object
                conn.execute("""
                    UPDATE sportsbook_operators 
                    SET settings = ? 
                    WHERE id = ?
                """, (json.dumps({'default_user_balance': new_balance}), operator['id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully reset all users across all operators',
            'bets_cancelled': bets_cancelled,
            'users_reset': users_reset,
            'new_balance': new_balance
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/run-daily-revenue-calculator', methods=['POST'])
@check_superadmin_auth
def run_daily_revenue_calculator():
    """Run the daily revenue calculator script"""
    try:
        from datetime import datetime
        import json
        
        # Import the daily revenue calculator functions directly
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # Import the functions from the script
        from daily_revenue_calculator import (
            get_operator_wallet_balances, 
            get_previous_total_revenue,
            calculate_revenue_distribution,
            update_daily_revenue_calculations
        )
        
        # Call the main function from the script
        update_daily_revenue_calculations()
        
        # Get statistics after running
        conn = get_db_connection()
        try:
            # Count operators processed
            operators_query = """
            SELECT COUNT(*) as count
            FROM sportsbook_operators 
            WHERE is_active = TRUE
            """
            operators_processed = conn.execute(operators_query).fetchone()['count']
            
            # Count calculations created today
            calculations_query = """
            SELECT COUNT(*) as count
            FROM revenue_calculations 
            WHERE DATE(processed_at) = DATE('now')
            """
            calculations_created = conn.execute(calculations_query).fetchone()['count']
            
            return jsonify({
                'success': True,
                'message': 'Daily revenue calculator completed successfully',
                'operators_processed': operators_processed,
                'calculations_created': calculations_created
            })
            
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/run-update-operator-wallets', methods=['POST'])
@check_superadmin_auth
def run_update_operator_wallets():
    """Run the update operator wallets script"""
    try:
        from datetime import datetime
        import json
        
        # Import the update operator wallets functions directly
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # Import the functions from the script
        from update_operator_wallets import (
            get_unprocessed_revenue_calculations,
            get_current_wallet_balances,
            update_wallet_balance,
            process_revenue_calculation
        )
        
        conn = get_db_connection()
        
        try:
            # Get unprocessed revenue calculations
            calculations = get_unprocessed_revenue_calculations(conn)
            calculations_processed = len(calculations)
            
            wallets_updated = 0
            
            for calculation in calculations:
                # Process the revenue calculation
                process_revenue_calculation(calculation, conn)
                
                wallets_updated += 1
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Update operator wallets completed successfully',
                'calculations_processed': calculations_processed,
                'wallets_updated': wallets_updated
            })
            
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/revenue-script-status')
@check_superadmin_auth
def get_revenue_script_status():
    """Get the last run times for revenue scripts"""
    try:
        conn = get_db_connection()
        
        # Get last revenue calculation processed_at
        last_revenue_calc = conn.execute("""
            SELECT processed_at 
            FROM revenue_calculations 
            ORDER BY processed_at DESC 
            LIMIT 1
        """).fetchone()
        
        # Get last wallet update updated_at
        last_wallet_update = conn.execute("""
            SELECT updated_at 
            FROM operator_wallets 
            ORDER BY updated_at DESC 
            LIMIT 1
        """).fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'last_revenue_calculation': last_revenue_calc['processed_at'] if last_revenue_calc else None,
            'last_wallet_update': last_wallet_update['updated_at'] if last_wallet_update else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-overview')
@check_superadmin_auth
def get_global_overview():
    """Get global overview statistics"""
    try:
        conn = get_db_connection()
        
        # Get total operators
        total_operators = conn.execute("SELECT COUNT(*) as count FROM sportsbook_operators").fetchone()['count']
        
        # Get total users
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        
        # Get total bets
        total_bets = conn.execute("SELECT COUNT(*) as count FROM bets").fetchone()['count']
        
        # Get total revenue
        total_revenue = conn.execute("""
            SELECT COALESCE(SUM(total_revenue), 0) as total 
            FROM sportsbook_operators
        """).fetchone()['total']
        
        # Get active events (events with pending bets)
        active_events = conn.execute("""
            SELECT COUNT(DISTINCT match_id) as count 
            FROM bets 
            WHERE status = 'pending'
        """).fetchone()['count']
        
        # Get total liability (sum of all pending bet stakes)
        total_liability = conn.execute("""
            SELECT COALESCE(SUM(stake), 0) as total 
            FROM bets 
            WHERE status = 'pending'
        """).fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_operators': total_operators,
            'total_users': total_users,
            'total_bets': total_bets,
            'total_revenue': total_revenue,
            'active_events': active_events,
            'total_liability': total_liability
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/operators')
@check_superadmin_auth
def get_operators():
    """Get all sportsbook operators"""
    
    try:
        conn = get_db_connection()
        
        operators_query = """
        SELECT so.id, so.sportsbook_name, so.subdomain, so.login, so.email, 
               so.created_at, so.is_active,
               (SELECT COUNT(*) FROM users WHERE sportsbook_operator_id = so.id) as user_count,
               (SELECT COUNT(*) FROM bets b JOIN users u ON b.user_id = u.id WHERE u.sportsbook_operator_id = so.id) as bet_count,
               (SELECT COALESCE(SUM(stake), 0) - COALESCE(SUM(potential_return), 0) FROM bets b JOIN users u ON b.user_id = u.id WHERE u.sportsbook_operator_id = so.id AND b.status IN ('won', 'lost')) as revenue
        FROM sportsbook_operators so
        ORDER BY so.created_at DESC
        """
        
        operators = conn.execute(operators_query).fetchall()
        conn.close()
        
        return jsonify({
            'operators': [dict(op) for op in operators]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@rich_superadmin_bp.route('/superadmin/api/user/<int:user_id>/toggle', methods=['POST'])
@check_superadmin_auth
def toggle_global_user_status(user_id):
    """Toggle user status globally (super admin power)"""
    
    try:
        conn = get_db_connection()
        
        # Get user
        user = conn.execute("SELECT id, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Toggle status
        new_status = not user['is_active']
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"User {'enabled' if new_status else 'disabled'} globally",
            'new_status': new_status
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/operator/<int:operator_id>/toggle', methods=['POST'])
@check_superadmin_auth
def toggle_operator_status(operator_id):
    """Toggle operator status (enable/disable)"""
    
    try:
        conn = get_db_connection()
        
        # Get current operator status
        operator = conn.execute('SELECT * FROM sportsbook_operators WHERE id = ?', (operator_id,)).fetchone()
        if not operator:
            conn.close()
            return jsonify({'error': 'Operator not found'}), 404
        
        # Toggle status
        new_status = not operator['is_active']
        conn.execute('UPDATE sportsbook_operators SET is_active = ? WHERE id = ?', (new_status, operator_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'new_status': new_status})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-stats')
@check_superadmin_auth
def get_global_stats():
    """Get global statistics for the super admin dashboard (adapted from admin interface)"""
    db = None
    try:
        from src.db import SessionLocal, close_db
        db = SessionLocal()
        
        # Get total operators count
        operator_count = db.execute(
            text("SELECT COUNT(*) FROM sportsbook_operators WHERE is_active = TRUE")
        ).scalar_one()
        
        # Get total users count across all operators
        user_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM users u 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.is_active = TRUE
        """)).scalar_one()
        
        # Get total bets count across all operators
        bet_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE
        """)).scalar_one()
        
        # Get total revenue across all operators (from won bets)
        total_revenue = db.execute(text("""
            SELECT COALESCE(SUM(b.actual_return - b.stake), 0)
            FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE AND b.status = 'won'
        """)).scalar_one()
        total_revenue = float(total_revenue or 0)
        
        # Get active events count across all operators (events with pending bets)
        active_events = db.execute(text("""
            SELECT COUNT(DISTINCT b.match_id)
            FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE AND b.status = 'pending'
        """)).scalar_one()
        
        # Get total liability across all operators (sum of all pending bet potential returns)
        # This matches the calculation shown in the betting events table
        total_liability = db.execute(text("""
            SELECT COALESCE(SUM(b.potential_return), 0)
            FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE AND b.status = 'pending'
        """)).scalar_one()
        total_liability = float(total_liability or 0)
        
        return jsonify({
            'total_operators': operator_count,
            'total_users': user_count,
            'total_bets': bet_count,
            'total_revenue': total_revenue,
            'active_events': active_events,
            'total_liability': total_liability
        })
        
    except Exception as e:
        print(f"Error getting global stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if db:
            close_db(db)

@rich_superadmin_bp.route('/superadmin/api/global-reports/overview')
@check_superadmin_auth
def get_global_reports_overview():
    """Get comprehensive global reports overview across all operators"""
    
    try:
        conn = get_db_connection()
        
        # Total bets and revenue across all operators
        total_query = """
        SELECT 
            COUNT(*) as total_bets,
            SUM(b.stake) as total_stakes,
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_payouts,
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_revenue_from_losses,
            COUNT(CASE WHEN b.status = 'pending' THEN 1 END) as pending_bets,
            COUNT(CASE WHEN b.status = 'won' THEN 1 END) as won_bets,
            COUNT(CASE WHEN b.status = 'lost' THEN 1 END) as lost_bets
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
        WHERE op.is_active = TRUE
        """
        
        totals = conn.execute(total_query).fetchone()
        
        # Daily revenue for the last 30 days across all operators
        daily_query = """
        SELECT 
            b.created_at::date as bet_date,
            COUNT(*) as daily_bets,
            SUM(b.stake) as daily_stakes,
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as daily_revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
        WHERE op.is_active = TRUE AND b.created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY b.created_at::date
        ORDER BY bet_date DESC
        """
        
        daily_data = conn.execute(daily_query).fetchall()
        
        # Sport-wise performance across all operators
        sport_query = """
        SELECT 
            b.sport_name,
            COUNT(*) as bets_count,
            SUM(b.stake) as total_stakes,
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as sport_revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
        WHERE op.is_active = TRUE
        GROUP BY b.sport_name
        ORDER BY sport_revenue DESC
        """
        
        sport_data = conn.execute(sport_query).fetchall()
        
        conn.close()
        
        # Calculate metrics
        total_stakes = float(totals['total_stakes'] or 0)
        total_revenue_from_losses = float(totals['total_revenue_from_losses'] or 0)
        total_payouts = float(totals['total_payouts'] or 0)
        total_revenue = total_revenue_from_losses - total_payouts
        win_rate = (totals['won_bets'] / max(totals['total_bets'], 1)) * 100
        
        return jsonify({
            'overview': {
                'total_bets': totals['total_bets'] or 0,
                'total_stakes': total_stakes,
                'total_revenue': total_revenue,
                'win_rate': win_rate,
                'pending_bets': totals['pending_bets'] or 0,
                'won_bets': totals['won_bets'] or 0,
                'lost_bets': totals['lost_bets'] or 0
            },
            'daily_data': [dict(row) for row in daily_data],
            'sport_data': [dict(row) for row in sport_data]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-reports/generate', methods=['POST'])
@check_superadmin_auth
def generate_global_custom_report():
    """Generate custom global reports based on parameters across all operators"""
    
    try:
        data = request.get_json()
        report_type = data.get('report_type', 'revenue')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        sport_filter = data.get('sport_filter')
        group_by = data.get('group_by', 'day')
        
        conn = get_db_connection()
        
        # Build base query with global filtering (all active operators)
        base_where = "op.is_active = TRUE"
        params = []
        
        # Add date filters if provided
        if date_from:
            base_where += " AND b.created_at::date >= ?"
            params.append(date_from)
        if date_to:
            base_where += " AND b.created_at::date <= ?"
            params.append(date_to)
        if sport_filter:
            base_where += " AND b.sport_name = ?"
            params.append(sport_filter)
        
        # Generate report based on type
        if report_type == 'revenue':
            query = f"""
            SELECT 
                b.created_at::date as bet_date,
                b.sport_name,
                COUNT(*) as total_bets,
                SUM(b.stake) as total_stakes,
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as revenue
            FROM bets b
            JOIN users u ON b.user_id = u.id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE {base_where}
            GROUP BY b.created_at::date, b.sport_name
            ORDER BY bet_date DESC, revenue DESC
            """
            
        elif report_type == 'user-activity':
            query = f"""
            SELECT 
                u.username,
                u.email,
                COUNT(b.id) as total_bets,
                SUM(b.stake) as total_staked,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as payout,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END) - 
                SUM(b.stake) as user_profit,
                u.created_at as joined_date
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY total_bets DESC
            """
            params = []  # Reset params for user query
            
        elif report_type == 'betting-patterns':
            query = f"""
            SELECT 
                b.created_at::date as bet_date,
                b.sport_name,
                b.market as bet_type,
                COUNT(*) as count,
                SUM(b.stake) as total_amount,
                (COUNT(CASE WHEN b.status = 'won' THEN 1 END) * 100.0 / COUNT(*)) as win_rate
            FROM bets b
            JOIN users u ON b.user_id = u.id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE {base_where}
            GROUP BY b.created_at::date, b.sport_name, b.market
            ORDER BY bet_date DESC, count DESC
            """
            
        elif report_type == 'sport-performance':
            query = f"""
            SELECT 
                b.sport_name,
                COUNT(*) as total_bets,
                SUM(b.stake) as total_stakes,
                COUNT(CASE WHEN b.status = 'won' THEN 1 END) as won_bets,
                COUNT(CASE WHEN b.status = 'lost' THEN 1 END) as lost_bets,
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as sport_revenue,
                (COUNT(CASE WHEN b.status = 'won' THEN 1 END) * 100.0 / COUNT(*)) as win_rate
            FROM bets b
            JOIN users u ON b.user_id = u.id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE {base_where}
            GROUP BY b.sport_name
            ORDER BY sport_revenue DESC
            """
        
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Execute query
        result = conn.execute(query, params).fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        report_data = [dict(row) for row in result]
        
        return jsonify(report_data)
        
    except Exception as e:
        print(f"Error generating global custom report: {e}")
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-reports/available-sports')
@check_superadmin_auth
def get_global_available_sports_for_reports():
    """Get available sports for global report filtering across all operators"""
    
    try:
        conn = get_db_connection()
        
        # Get sports that have bets from all active operators
        sports_query = """
        SELECT DISTINCT b.sport_name
        FROM bets b
        JOIN users u ON b.user_id = u.id
        JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
        WHERE op.is_active = TRUE AND b.sport_name IS NOT NULL AND b.sport_name != ''
        ORDER BY b.sport_name
        """
        
        sports_result = conn.execute(sports_query).fetchall()
        conn.close()
        
        sports = [row['sport_name'] for row in sports_result]
        
        return jsonify({'sports': sports})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/global-reports/export', methods=['POST'])
@check_superadmin_auth
def export_global_custom_report():
    """Export global custom report to CSV across all operators"""
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        report_type = data.get('report_type', 'revenue')
        format_type = data.get('format', 'csv')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        sport_filter = data.get('sport_filter')
        
        print(f"DEBUG: Global export request - type: {report_type}, format: {format_type}, from: {date_from}, to: {date_to}, sport: {sport_filter}")
        
        conn = get_db_connection()
        
        # Build base query (similar to generate endpoint)
        base_where = "op.is_active = TRUE"
        params = []
        
        if date_from:
            base_where += " AND b.created_at::date >= ?"
            params.append(date_from)
        if date_to:
            base_where += " AND b.created_at::date <= ?"
            params.append(date_to)
        if sport_filter:
            base_where += " AND b.sport_name = ?"
            params.append(sport_filter)
        
        # Generate CSV data
        if report_type == 'revenue':
            query = f"""
            SELECT 
                b.created_at::date as bet_date,
                b.sport_name,
                COUNT(*) as total_bets,
                SUM(b.stake) as total_stakes,
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as revenue
            FROM bets b
            JOIN users u ON b.user_id = u.id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE {base_where}
            GROUP BY b.created_at::date, b.sport_name
            ORDER BY bet_date DESC, revenue DESC
            """
            headers = ['Date', 'Sport', 'Total Bets', 'Total Stakes', 'Revenue']
        
        elif report_type == 'user-activity':
            query = f"""
            SELECT 
                u.username,
                u.email,
                COUNT(b.id) as total_bets,
                SUM(b.stake) as total_staked,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as payout,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END) - 
                SUM(b.stake) as user_profit,
                u.created_at as joined_date
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id
            WHERE op.is_active = TRUE
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY total_bets DESC
            """
            headers = ['Username', 'Email', 'Total Bets', 'Total Staked', 'Payout', 'Profit', 'Join Date']
            params = []
        
        else:
            return jsonify({'error': 'Export not supported for this report type'}), 400
        
        # Execute query
        try:
            result = conn.execute(query, params).fetchall()
            print(f"DEBUG: Global query executed successfully, got {len(result)} rows")
        except Exception as query_error:
            print(f"DEBUG: Global query execution error: {query_error}")
            print(f"DEBUG: Query: {query}")
            print(f"DEBUG: Params: {params}")
            conn.close()
            raise query_error
        
        conn.close()
        
        # Generate CSV content
        csv_content = ','.join(headers) + '\n'
        for row in result:
            csv_row = []
            for i, value in enumerate(row):
                # Escape commas and quotes in CSV
                if ',' in str(value) or '"' in str(value):
                    value = f'"{str(value).replace(chr(34), chr(34) + chr(34))}"'
                csv_row.append(str(value))
            csv_content += ','.join(csv_row) + '\n'
        
        # Return CSV file
        from flask import Response
        response = Response(csv_content, mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename={report_type}_global_report.csv'
        return response
        
    except Exception as e:
        print(f"Error exporting global report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@rich_superadmin_bp.route('/superadmin/api/manual-settlement')
@check_superadmin_auth
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
        print(f"Error getting global manual settlement data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get settlement data'
        }), 500

@rich_superadmin_bp.route('/superadmin/api/manual-settle', methods=['POST'])
@check_superadmin_auth
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
            }), 400
        
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
            
            # Determine if bet is a winner
            if winning_selection == 'none':
                # If "None" is selected, all bets lose
                is_winner = False
            else:
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
        
        # Update total_revenue for all affected operators
        affected_operators = set(bet['sportsbook_operator_id'] for bet in pending_bets)
        for operator_id in affected_operators:
            update_operator_revenue(operator_id, conn)
        
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
        print(f"Error manually settling global bets: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

@rich_superadmin_bp.route('/api/superadmin/export-pending-bets')
@check_superadmin_auth
def export_pending_bets():
    """Export all pending bets to CSV"""
    try:
        import csv
        import io
        from datetime import datetime
        
        conn = get_db_connection()
        
        # Query pending bets with user information using SQLite3
        query = """
        SELECT 
            b.id,
            b.user_id,
            b.match_id,
            b.match_name,
            b.selection,
            b.bet_selection,
            b.stake,
            b.odds,
            b.combo_selections,
            b.created_at,
            b.updated_at,
            u.username,
            u.email
        FROM bets b
        LEFT JOIN users u ON b.user_id = u.id
        WHERE b.status = 'pending'
        ORDER BY b.created_at DESC
        """
        
        pending_bets = conn.execute(query).fetchall()
        conn.close()
        
        if not pending_bets:
            return jsonify({
                'success': False,
                'error': 'No pending bets found'
            }), 404
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'Bet ID',
            'User ID', 
            'Username',
            'Email',
            'Match ID',
            'Match Name',
            'Selection',
            'Bet Selection',
            'Stake',
            'Odds',
            'Combo Selections',
            'Created At',
            'Updated At'
        ]
        writer.writerow(headers)
        
        # Write data rows
        for bet in pending_bets:
            # Parse combo_selections if it's JSON
            combo_selections_str = ""
            if bet['combo_selections']:
                try:
                    combo_data = json.loads(bet['combo_selections'])
                    combo_selections_str = json.dumps(combo_data, indent=2)
                except:
                    combo_selections_str = str(bet['combo_selections'])
            
            row = [
                bet['id'],
                bet['user_id'],
                bet['username'] or 'N/A',
                bet['email'] or 'N/A',
                bet['match_id'] or 'N/A',
                bet['match_name'] or 'N/A',
                bet['selection'] or 'N/A',
                bet['bet_selection'] or 'N/A',
                bet['stake'] or 0,
                bet['odds'] or 0,
                combo_selections_str,
                bet['created_at'] or 'N/A',
                bet['updated_at'] or 'N/A'
            ]
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pending_bets_export_{timestamp}.csv"
        
        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'filename': filename,
            'count': len(pending_bets)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error exporting pending bets: {str(e)}'
        }), 500

@rich_superadmin_bp.route('/api/superadmin/process-csv-settlement', methods=['POST'])
@check_superadmin_auth
def process_csv_settlement():
    """Process CSV file with bet results and update settlements"""
    try:
        from werkzeug.utils import secure_filename
        import csv
        import io
        from datetime import datetime
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            return jsonify({'success': False, 'error': 'No CSV file uploaded'}), 400
        
        file = request.files['csv_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'success': False, 'error': 'File must be a CSV'}), 400
        
        # Read and parse CSV
        csv_content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # Validate CSV format
        if 'Bet ID' not in csv_reader.fieldnames or 'Result' not in csv_reader.fieldnames:
            return jsonify({'success': False, 'error': 'CSV must contain "Bet ID" and "Result" columns'}), 400
        
        # Valid result values
        valid_results = ['WON', 'LOST', 'Results Pending', 'No Results']
        
        # Process each row
        conn = get_db_connection()
        processed_count = 0
        won_count = 0
        lost_count = 0
        pending_count = 0
        no_results_count = 0
        errors = []
        
        try:
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because header is row 1
                bet_id = row.get('Bet ID', '').strip()
                result = row.get('Result', '').strip()
                
                # Validate bet ID
                if not bet_id or not bet_id.isdigit():
                    errors.append(f"Row {row_num}: Invalid Bet ID '{bet_id}'")
                    continue
                
                bet_id = int(bet_id)
                
                # Validate result
                if result not in valid_results:
                    errors.append(f"Row {row_num}: Invalid Result '{result}'. Must be one of: {', '.join(valid_results)}")
                    continue
                
                # Get the bet from database
                bet_query = """
                SELECT b.*, u.username, u.sportsbook_operator_id
                FROM bets b
                JOIN users u ON b.user_id = u.id
                WHERE b.id = ? AND b.status = 'pending'
                """
                
                bet = conn.execute(bet_query, (bet_id,)).fetchone()
                
                if not bet:
                    errors.append(f"Row {row_num}: Bet ID {bet_id} not found or already settled")
                    continue
                
                # Update bet status based on result
                new_status = 'settled'
                if result == 'Results Pending':
                    new_status = 'pending'
                elif result == 'No Results':
                    new_status = 'voided'
                
                # Update the bet
                update_query = """
                UPDATE bets 
                SET status = ?, updated_at = ?
                WHERE id = ?
                """
                
                conn.execute(update_query, (new_status, datetime.now(), bet_id))
                
                # Handle wallet updates for settled bets
                if new_status == 'settled':
                    if result == 'WON':
                        # Add winnings to user wallet
                        winnings = bet['potential_return'] - bet['stake']  # Net winnings
                        conn.execute("""
                        UPDATE users 
                        SET wallet_balance = wallet_balance + ?
                        WHERE id = ?
                        """, (winnings, bet['user_id']))
                        won_count += 1
                    elif result == 'LOST':
                        # No wallet update needed for lost bets (stake already deducted)
                        lost_count += 1
                elif new_status == 'voided':
                    # Refund stake for voided bets
                    conn.execute("""
                    UPDATE users 
                    SET wallet_balance = wallet_balance + ?
                    WHERE id = ?
                    """, (bet['stake'], bet['user_id']))
                    no_results_count += 1
                else:  # Results Pending
                    pending_count += 1
                
                processed_count += 1
            
            # Commit all changes
            conn.commit()
            
            # Prepare response
            response_data = {
                'success': True,
                'processed_count': processed_count,
                'won_count': won_count,
                'lost_count': lost_count,
                'pending_count': pending_count,
                'no_results_count': no_results_count
            }
            
            if errors:
                response_data['warnings'] = errors[:10]  # Limit to first 10 errors
                if len(errors) > 10:
                    response_data['warnings'].append(f"... and {len(errors) - 10} more errors")
            
            return jsonify(response_data)
            
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error processing CSV: {str(e)}'
        }), 500

# Rich Super Admin Template (same rich interface as original admin_app.py but global)
RICH_SUPERADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoalServe - Super Admin Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
            min-height: 100vh;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .header h1 {
            font-size: 1.5rem;
        }
        
        .header .admin-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .logout-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .nav-tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        
        .nav-tab {
            padding: 0.75rem 1.5rem;
            background: rgba(255, 255, 255, 0.9);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .nav-tab.active {
            background: #e67e22;
            color: white;
        }
        
        .nav-tab:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        .content-section {
            display: none;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .content-section.active {
            display: block;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .summary-card h3 {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            font-weight: 500;
        }
        
        .summary-card .value {
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .controls {
            margin-bottom: 20px;
        }
        
        .controls button {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .controls button:hover {
            background: #2980b9;
        }
        
        .report-builder-form {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #333;
        }
        
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .form-actions {
            display: flex;
            gap: 15px;
            margin-top: 25px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background: #229954;
        }
        
        .btn-secondary {
            background: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #7f8c8d;
        }
        
        .report-results {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-top: 20px;
        }
        
        .report-results h3 {
            margin: 0 0 20px 0;
            color: #2c3e50;
        }
        
        .positive {
            color: #27ae60;
            font-weight: 500;
        }
        
        .negative {
            color: #e74c3c;
            font-weight: 500;
        }
        
        .table-container {
            overflow-x: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        
        th {
            background: #f8f9fa;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }
        
        th:hover {
            background: #e9ecef;
        }
        
        .status-badge {
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .status-active {
            background: #d4edda;
            color: #155724;
        }
        
        .status-disabled {
            background: #f8d7da;
            color: #721c24;
        }
        
        .action-btn {
            padding: 0.25rem 0.75rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: 0.5rem;
            display: inline-block !important;
            visibility: visible !important;
        }
        
        .btn-enable {
            background: #28a745;
            color: white;
        }
        
        .btn-disable {
            background: #dc3545;
            color: white;
        }
        
        .loading {
            text-align: center;
            padding: 2rem;
            color: #666;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
        }
        
        .operator-name {
            font-weight: 600;
            color: #e67e22;
        }
        
        /* Table layout fixes */
        #global-users-table,
        #operators-table {
            table-layout: fixed;
            width: 100%;
        }
        
        #global-users-table th:last-child,
        #operators-table th:last-child {
            width: 120px;
            min-width: 120px;
        }
        
        #global-users-table td:last-child,
        #operators-table td:last-child {
            text-align: center;
            padding: 8px 4px;
        }

        /* Global Betting Events Management Styles */
        .section {
            display: none;
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .section.active {
            display: block;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }

        .summary-card h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
            font-weight: 600;
            opacity: 1;
            color: white;
        }

        .summary-card p {
            margin: 0;
            font-size: 24px;
            font-weight: bold;
        }

        .controls {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .controls select,
        .controls input[type="text"] {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }

        .controls label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }

        .controls input[type="checkbox"] {
            margin: 0;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: #28a745;
            color: white;
        }

        .btn-primary:hover {
            background: #218838;
        }

        .btn-danger {
            background: #dc3545;
            color: white;
        }

        .btn-danger:hover {
            background: #c82333;
        }

        .btn-success {
            background: #28a745;
            color: white;
        }

        .btn-success:hover {
            background: #218838;
        }

        .btn-sm {
            padding: 4px 8px;
            font-size: 12px;
        }

        .table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }

        th {
            background-color: #f8f9fa;
            font-weight: 600;
        }

        .status-badge {
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }

        .status-badge.active {
            background: #d4edda;
            color: #155724;
        }

        .status-badge.disabled {
            background: #f8d7da;
            color: #721c24;
        }

        .positive {
            color: #28a745;
        }

        .negative {
            color: #dc3545;
        }

        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        /* Pagination Styles */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            margin: 1.5rem 0;
            padding: 1rem;
        }
        
        .pagination button {
            padding: 0.5rem 1rem;
            border: 1px solid #ddd;
            background: white;
            color: #333;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }
        
        .pagination button:hover:not(:disabled) {
            background: #f8f9fa;
            border-color: #e67e22;
        }
        
        .pagination button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination button.active {
            background: #e67e22;
            color: white;
            border-color: #e67e22;
        }
        
        .pagination-info {
            margin: 0 1rem;
            color: #666;
            font-size: 0.9rem;
        }
        
        .pagination-controls {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .pagination-controls select {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9rem;
        }

        .error {
            text-align: center;
            color: #dc3545;
            font-weight: 500;
        }

        .no-data {
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        /* Hide welcome banners */
        .welcome-banner {
            display: none !important;
        }
        
        /* Hide any other welcome messages */
        .welcome-message,
        .welcome-header,
        [class*="welcome"] {
            display: none !important;
        }

        /* Export Status Styles */
        .export-status.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .export-status.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .export-status.info {
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }

        .upload-status.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        .upload-status.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        .upload-status.info {
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌟 GoalServe - Super Admin Dashboard</h1>
        <div class="admin-info">
            <span>Global Management</span>
            <a href="/superadmin/logout" class="logout-btn">Logout</a>
        </div>
    </div>
    
    <div class="container">
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showSection('global-overview')">🏠 Global Overview</button>
            <button class="nav-tab" onclick="showSection('global-betting-events')">📊 Global Betting Events</button>
            <button class="nav-tab" onclick="showSection('manual-settlement')">💰 Manual Settlement</button>
            <button class="nav-tab" onclick="showSection('global-user-management')">👥 Global User Management</button>
            <button class="nav-tab" onclick="showSection('global-reports')">📈 Global Reports</button>
            <button class="nav-tab" onclick="showSection('operator-management')">🏢 Operator Management</button>
            <button class="nav-tab" onclick="showSection('global-report-builder')">🔧 Global Report Builder</button>
        </div>
        
        <!-- Global Dashboard Overview -->
        <div id="global-overview" class="section active">
            <h2>Global Dashboard Overview</h2>
            <p>Comprehensive view of all sportsbook operators and their performance</p>
            
            <!-- Global Summary Cards -->
            <div class="summary-cards">
                <div class="summary-card">
                    <h3>Total Operators</h3>
                    <p id="global-total-operators">0</p>
                </div>
                <div class="summary-card">
                    <h3>Total Users</h3>
                    <p id="global-total-users">0</p>
                </div>
                <div class="summary-card">
                    <h3>Total Bets</h3>
                    <p id="global-total-bets">0</p>
                </div>
                <div class="summary-card">
                    <h3>Total Revenue</h3>
                    <p id="global-total-revenue">$0.00</p>
                </div>
                <div class="summary-card">
                    <h3>Active Events</h3>
                    <p id="global-active-events">0</p>
                </div>
                <div class="summary-card">
                    <h3>Total Liability</h3>
                    <p id="global-total-liability">$0.00</p>
                </div>
            </div>
            
            <!-- Revenue Management Section -->
            <div style="background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h3 style="color: #2c3e50; margin-bottom: 15px; border-bottom: 2px solid #e67e22; padding-bottom: 10px;">💰 Revenue Management</h3>
                <p style="color: #666; margin-bottom: 20px;">Run daily revenue calculations and update operator wallets</p>
                
                <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px;">
                    <button onclick="runDailyRevenueCalculator()" 
                            style="background: linear-gradient(135deg, #28a745, #20c997); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease;"
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(40, 167, 69, 0.3)'"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <span>📊</span>
                        <span>Run Daily Revenue Calculator</span>
                    </button>
                    
                    <button onclick="runUpdateOperatorWallets()" 
                            style="background: linear-gradient(135deg, #007bff, #0056b3); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease;"
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0, 123, 255, 0.3)'"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <span>💳</span>
                        <span>Update Operator Wallets</span>
                    </button>
                </div>
                
                <!-- Last Run Status -->
                <div style="background: #f8f9fa; border-radius: 6px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #e67e22;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                        <div>
                            <strong style="color: #2c3e50;">📊 Last Revenue Calculation:</strong>
                            <span id="last-revenue-calculation" style="color: #666; font-style: italic;">Loading...</span>
                        </div>
                        <div>
                            <strong style="color: #2c3e50;">💳 Last Wallet Update:</strong>
                            <span id="last-wallet-update" style="color: #666; font-style: italic;">Loading...</span>
                        </div>
                    </div>
                </div>
                
                <div id="revenue-script-status" style="margin-top: 15px; padding: 10px; border-radius: 4px; display: none;">
                    <!-- Status messages will appear here -->
                </div>
            </div>
        </div>
            
        <!-- Global Betting Events Management -->
        <div id="global-betting-events" class="section">
            <h2>Global Betting Events Management</h2>
            


            <!-- Controls -->
            <div class="controls">
                <select id="global-events-sport-filter">
                    <option value="">All Sports</option>
                </select>
                <select id="global-market-filter">
                    <option value="">All Markets</option>
                </select>
                <input type="text" id="global-event-search" placeholder="Search events...">
                <label>
                    <input type="checkbox" id="global-show-bets-only" checked>
                    Show Only Events with Bets (Faster)
                </label>
                <button onclick="refreshGlobalEvents()" class="btn btn-primary">
                    <i class="fas fa-sync-alt"></i> Refresh Events
                </button>
            </div>
            
                         <!-- Events Table -->
            <div class="table-container">
                <table id="global-events-table">
                    <thead>
                        <tr>
                             <th onclick="sortTable('global-events-table', 0)" style="cursor: pointer;">
                                 Event ID <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 1)" style="cursor: pointer;">
                                 Sport <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 2)" style="cursor: pointer;">
                                 Event Name <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 3)" style="cursor: pointer;">
                                 Market <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 4)" style="cursor: pointer;">
                                 Total Bets <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 5)" style="cursor: pointer;">
                                 Liability <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 6)" style="cursor: pointer;">
                                 Revenue <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-events-table', 7)" style="cursor: pointer;">
                                 Status <span class="sort-icon">↕</span>
                             </th>
                             <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="global-events-tbody">
                         <!-- Events will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Manual Settlement Section -->
        <div id="manual-settlement" class="section">
            <h2>Global Manual Bet Settlement</h2>
            <p style="margin-bottom: 1rem; color: #666;">Manually settle pending bets across all operators by setting match outcomes</p>
            
            <div class="summary-cards">
                <div class="summary-card">
                    <h3>Total Matches</h3>
                    <p id="total-matches">-</p>
                </div>
                <div class="summary-card">
                    <h3>Total Liability</h3>
                    <p id="total-liability">$0.00</p>
                </div>
                <div class="summary-card">
                    <h3>Pending Bets</h3>
                    <p id="pending-bets">-</p>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="loadSettlementData()">🔄 Refresh Settlement Data</button>
            
            <!-- Export Section -->
            <div class="export-section" style="background: #e8f5e8; border: 2px solid #28a745; border-radius: 12px; padding: 1.5rem; margin: 1rem 0;">
                <h4 style="color: #155724; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">📊 Export Pending Bets</h4>
                <p style="color: #155724; margin-bottom: 1rem; opacity: 0.8;">Download all pending bets as a CSV file for manual review and settlement.</p>
                <button id="exportPendingBetsBtn" class="btn btn-success" style="background: #28a745; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer;">
                    <span class="btn-text">📊 Export Pending Bets</span>
                    <span class="btn-loading" style="display: none;">⏳ Exporting...</span>
                </button>
                <div id="exportStatus" class="export-status" style="margin-top: 1rem; padding: 1rem; border-radius: 8px; font-weight: 500; display: none;"></div>
            </div>
            
            <!-- CSV Upload Section -->
            <div class="csv-upload-section" style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 12px; padding: 1.5rem; margin: 1rem 0;">
                <h4 style="color: #856404; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">📁 Upload Bet Results CSV</h4>
                <p style="color: #856404; margin-bottom: 1rem; opacity: 0.8;">Upload a CSV file with bet results to process settlements automatically.</p>
                
                <div style="margin-bottom: 1rem;">
                    <label for="csvFile" style="display: block; margin-bottom: 0.5rem; font-weight: 600; color: #856404;">Select CSV File:</label>
                    <input type="file" id="csvFile" accept=".csv" style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; background: white;">
                </div>
                
                <div style="margin-bottom: 1rem;">
                    <h5 style="color: #856404; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem;">Required CSV Format:</h5>
                    <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; color: #495057; white-space: pre-line;">Bet ID,Result
54,WON
53,LOST
52,Results Pending
51,No Results</div>
                    <p style="font-size: 0.8rem; color: #856404; margin-top: 0.5rem;">
                        <strong>Valid Results:</strong> WON, LOST, Results Pending, No Results
                    </p>
                </div>
                
                <button id="processSettlementBtn" class="btn btn-warning" style="background: #ffc107; color: #212529; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; margin-right: 0.5rem;">
                    <span class="btn-text">⚡ Process Settlement</span>
                    <span class="btn-loading" style="display: none;">⏳ Processing...</span>
                </button>
                
                <button id="downloadTemplateBtn" class="btn btn-secondary" style="background: #6c757d; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer;">
                    📋 Download Template
                </button>
                
                <div id="uploadStatus" class="upload-status" style="margin-top: 1rem; padding: 1rem; border-radius: 8px; font-weight: 500; display: none;"></div>
            </div>
            
            <div class="table-container">
                <table id="settlement-table">
                    <thead>
                        <tr>
                            <th>Bet ID</th>
                            <th>Match & Market</th>
                            <th>Operator</th>
                            <th>Bet Summary</th>
                            <th>Outcomes</th>
                            <th>Total Liability</th>
                            <th>Settlement</th>
                        </tr>
                    </thead>
                    <tbody id="settlement-tbody">
                        <tr><td colspan="7" class="loading">Loading settlement data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Global User Management Section -->
        <div id="global-user-management" class="content-section">
            <h2>Global User Management</h2>
            <p>Manage users across all sportsbook operators with global admin powers</p>
            
            <div class="controls">
                <button onclick="loadGlobalUsers()">🔄 Refresh Global Users</button>
                
                <div class="reset-users-controls" style="display: inline-block; margin-left: 20px;">
                    <input type="number" id="global-reset-balance-amount" placeholder="Enter balance amount" 
                           style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; margin-right: 10px; width: 150px;">
                    <button onclick="resetAllGlobalUsers()" style="background: #dc2626; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                        🔄 Reset All Users
                    </button>
                    <div style="font-size: 12px; color: #666; margin-top: 5px;">
                        ⚠️ This will cancel all pending bets (refund stakes), reset ALL user balances across ALL operators, and set default balance for new users
                    </div>
                </div>
            </div>
            
            <!-- Pagination Controls -->
            <div class="pagination-controls">
                <label for="global-users-per-page">Users per page:</label>
                <select id="global-users-per-page" onchange="changeGlobalUsersPerPage()">
                    <option value="10">10</option>
                    <option value="20" selected>20</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                </select>
                <span id="global-users-pagination-info" class="pagination-info">Loading...</span>
            </div>
            
            <div class="table-container">
                <table id="global-users-table">
                    <thead>
                        <tr>
                             <th onclick="sortTable('global-users-table', 0)" style="cursor: pointer;">
                                 ID <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 1)" style="cursor: pointer;">
                                 Username <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 2)" style="cursor: pointer;">
                                 Email <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 3)" style="cursor: pointer;">
                                 Operator <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 4)" style="cursor: pointer;">
                                 Balance <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 5)" style="cursor: pointer;">
                                 Bets <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 6)" style="cursor: pointer;">
                                 Staked <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 7)" style="cursor: pointer;">
                                 Payout <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 8)" style="cursor: pointer;">
                                 Profit <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 9)" style="cursor: pointer;">
                                 Joined <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('global-users-table', 10)" style="cursor: pointer;">
                                 Status <span class="sort-icon">↕</span>
                             </th>
                            <th style="min-width: 120px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="global-users-tbody">
                        <tr><td colspan="12" class="loading">Loading global users...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <!-- Pagination -->
            <div id="global-users-pagination" class="pagination" style="display: none;">
                <button onclick="goToGlobalUsersPage(1)" id="global-users-first-page">« First</button>
                <button onclick="goToGlobalUsersPage(currentGlobalUsersPage - 1)" id="global-users-prev-page">‹ Previous</button>
                <div id="global-users-page-numbers"></div>
                <button onclick="goToGlobalUsersPage(currentGlobalUsersPage + 1)" id="global-users-next-page">Next ›</button>
                <button onclick="goToGlobalUsersPage(totalGlobalUsersPages)" id="global-users-last-page">Last »</button>
            </div>
        </div>
        
        <!-- Operator Management Section -->
        <div id="operator-management" class="content-section">
            <h2>🏢 Operator Management</h2>
            <p>Manage all sportsbook operators - enable/disable entire sportsbooks</p>
            
            <div class="controls">
                <button onclick="loadOperators()">🔄 Refresh Operators</button>
            </div>
            
            <div class="table-container">
                <table id="operators-table">
                    <thead>
                        <tr>
                             <th onclick="sortTable('operators-table', 0)" style="cursor: pointer;">
                                 ID <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 1)" style="cursor: pointer;">
                                 Sportsbook Name <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 2)" style="cursor: pointer;">
                                 Subdomain <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 3)" style="cursor: pointer;">
                                 Admin Username <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 4)" style="cursor: pointer;">
                                 Admin Email <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 5)" style="cursor: pointer;">
                                 Users <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 6)" style="cursor: pointer;">
                                 Bets <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 7)" style="cursor: pointer;">
                                 Revenue <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 8)" style="cursor: pointer;">
                                 Created <span class="sort-icon">↕</span>
                             </th>
                             <th onclick="sortTable('operators-table', 9)" style="cursor: pointer;">
                                 Status <span class="sort-icon">↕</span>
                             </th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="operators-tbody">
                        <tr><td colspan="11" class="loading">Loading operators...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Global Reports Section -->
        <div id="global-reports" class="content-section">
            <h2>Global Reports & Analytics</h2>
            <p>Comprehensive reporting across all sportsbook operations</p>
            
            <div class="summary-cards">
                <div class="summary-card">
                    <h3>Total Bets</h3>
                    <div class="value" id="global-reports-total-bets">0</div>
                </div>
                <div class="summary-card">
                    <h3>Total Stakes</h3>
                    <div class="value" id="global-reports-total-stakes">$0.00</div>
                </div>
                <div class="summary-card">
                    <h3>Global Revenue</h3>
                    <div class="value" id="global-reports-total-revenue">$0.00</div>
                </div>
                <div class="summary-card">
                    <h3>Win Rate</h3>
                    <div class="value" id="global-reports-win-rate">0%</div>
                </div>
            </div>
            
            <div class="controls">
                <button onclick="loadGlobalReports()">🔄 Refresh Global Reports</button>
            </div>
            
            <div class="table-container">
                <table id="global-reports-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Sport</th>
                            <th>Total Bets</th>
                            <th>Total Stakes</th>
                            <th>Revenue</th>
                        </tr>
                    </thead>
                    <tbody id="global-reports-tbody">
                        <tr><td colspan="5" class="loading">Loading global reports...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Global Report Builder Section -->
        <div id="global-report-builder" class="content-section">
            <h2>🔧 Global Report Builder</h2>
            <p>Create custom reports across all sportsbooks</p>
            
            <div class="report-builder-form">
                <div class="form-group">
                    <label for="global-report-type">Report Type:</label>
                    <select id="global-report-type">
                        <option value="revenue">Revenue Report</option>
                        <option value="user-activity">User Activity Report</option>
                        <option value="betting-patterns">Betting Patterns Report</option>
                        <option value="sport-performance">Sport Performance Report</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="global-date-from">Date From:</label>
                    <input type="date" id="global-date-from">
                </div>
                
                <div class="form-group">
                    <label for="global-date-to">Date To:</label>
                    <input type="date" id="global-date-to">
                </div>
                
                <div class="form-group">
                    <label for="global-reports-sport-filter">Sport Filter:</label>
                    <select id="global-reports-sport-filter">
                        <option value="">All Sports</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="global-group-by">Group By:</label>
                    <select id="global-group-by">
                        <option value="day">Day</option>
                        <option value="week">Week</option>
                        <option value="month">Month</option>
                        <option value="sport">Sport</option>
                    </select>
                </div>
                
                <div class="form-actions">
                    <button onclick="generateGlobalReport()" class="btn btn-primary">📊 Generate Report</button>
                    <button onclick="exportGlobalReport()" class="btn btn-secondary">📥 Export CSV</button>
                </div>
            </div>
            
            <div class="report-results" id="global-report-results" style="display: none;">
                <h3>📋 Report Results</h3>
                <div class="table-container">
                    <table id="global-report-table">
                        <thead id="global-report-header">
                        </thead>
                        <tbody id="global-report-body">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Version: 2025-09-11-event-time-fix
        console.log('🚀 Loading Rich Superadmin Interface v2025-09-11-event-time-fix');
        
        function showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.section, .content-section').forEach(section => {
                section.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected section
            document.getElementById(sectionId).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
            
            // Load data for the section
            if (sectionId === 'global-overview') {
                loadGlobalStats();
            } else if (sectionId === 'global-betting-events') {
                loadGlobalBettingEvents();
            } else if (sectionId === 'global-user-management') {
                loadGlobalUsers();
            } else if (sectionId === 'global-reports') {
                loadGlobalReports();
            } else if (sectionId === 'operator-management') {
                loadOperators();
            } else if (sectionId === 'global-report-builder') {
                loadGlobalReportBuilder();
            }
        }
        
        async function loadGlobalBettingEvents() {
            try {
                // Get the checkbox value
                const showBetsOnly = document.getElementById('global-show-bets-only')?.checked || false;
                console.log('🔍 DEBUG: showBetsOnly checkbox value:', showBetsOnly);
                
                // Build the URL with query parameters
                const url = `/superadmin/api/global-betting-events?show_only_with_bets=${showBetsOnly}`;
                console.log('🔍 DEBUG: Calling URL:', url);
                
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('global-events-tbody').innerHTML = 
                        `<tr><td colspan="9" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                // Update summary cards
                if (document.getElementById('global-total-bets')) {
                    document.getElementById('global-total-bets').textContent = data.summary?.total_events || 0;
                }
                if (document.getElementById('global-active-events')) {
                    document.getElementById('global-active-events').textContent = data.summary?.active_events || 0;
                }
                if (document.getElementById('global-total-liability')) {
                    document.getElementById('global-total-liability').textContent = `$${data.summary?.total_liability || '0.00'}`;
                }
                
                // Update table
                const tbody = document.getElementById('global-events-tbody');
                if (data.events.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="9" class="loading">No events found</td></tr>`;
                } else {
                    tbody.innerHTML = data.events.map(event => `
                        <tr>
                            <td>${event.event_id}</td>
                            <td>${event.sport}</td>
                            <td>${event.event_name}</td>
                            <td>${event.market}</td>
                            <td>${event.total_bets || 0}</td>
                            <td class="liability">$${event.liability || '0.00'}</td>
                            <td class="revenue">$${event.revenue || '0.00'}</td>
                            <td><span class="status-badge status-${event.status}">${event.status}</span></td>
                            <td>
                                <button class="btn btn-sm btn-warning" onclick="toggleEventStatus('${event.event_id}', '${event.sport}', '${event.market}')">
                                    ${event.status === 'disabled' ? 'Enable' : 'Disable'}
                                </button>
                            </td>
                        </tr>
                    `).join('');
                }
                
            } catch (error) {
                document.getElementById('global-events-tbody').innerHTML = 
                    `<tr><td colspan="9" class="error">Error loading events: ${error.message}</td></tr>`;
            }
        }
        
        async function toggleEventStatus(eventId, sport, market) {
            try {
                console.log('🔍 toggleEventStatus called with:', { eventId, sport, market });
                
                // Show confirmation dialog
                const confirmed = confirm(`Are you sure you want to toggle the status for ${sport} event ${eventId} (${market})?`);
                if (!confirmed) return;
                
                // Call the API to toggle event status
                const response = await fetch('/superadmin/api/global-betting-events/toggle-status', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        event_id: eventId,
                        status: 'disabled' // For now, always disable. You can enhance this to toggle between enabled/disabled
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert('Event status updated successfully!');
                    // Refresh the table to show updated status
                    await loadGlobalBettingEvents();
                } else {
                    alert('Error updating event status: ' + (result.error || 'Unknown error'));
                }
                
            } catch (error) {
                console.error('Error toggling event status:', error);
                alert('Error toggling event status: ' + error.message);
            }
        }
        
        // Pagination variables for global users
        let currentGlobalUsersPage = 1;
        let totalGlobalUsersPages = 1;
        let globalUsersPerPage = 20;
        
        async function loadGlobalUsers(page = 1) {
            console.log('🔍 loadGlobalUsers function called');
            try {
                currentGlobalUsersPage = page;
                const perPage = parseInt(document.getElementById('global-users-per-page').value) || 20;
                globalUsersPerPage = perPage;
                
                console.log('🌐 Fetching from /superadmin/api/global-users');
                const response = await fetch(`/superadmin/api/global-users?page=${page}&per_page=${perPage}`);
                console.log('📡 Response status:', response.status);
                
                const data = await response.json();
                console.log('📊 API Response data:', data);
                
                if (data.error) {
                    document.getElementById('global-users-tbody').innerHTML = 
                        `<tr><td colspan="12" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                // Update pagination info
                totalGlobalUsersPages = Math.ceil(data.total / perPage);
                document.getElementById('global-users-pagination-info').textContent = 
                    `Showing ${((page - 1) * perPage) + 1}-${Math.min(page * perPage, data.total)} of ${data.total} users`;
                
                const tbody = document.getElementById('global-users-tbody');
                if (data.users.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="12" class="loading">No users found</td></tr>`;
                } else {
                    console.log('🎯 Rendering users table with', data.users.length, 'users');
                    const userRows = data.users.map(user => `
                        <tr>
                            <td>${user.id}</td>
                            <td>${user.username}</td>
                            <td>${user.email}</td>
                            <td><span class="operator-name">${user.operator_name || 'Default Sportsbook'}</span></td>
                            <td>$${user.balance}</td>
                            <td>${user.total_bets}</td>
                            <td>$${user.total_staked}</td>
                            <td>$${user.total_payout}</td>
                            <td>$${user.profit}</td>
                            <td>${new Date(user.created_at).toLocaleDateString()}</td>
                            <td><span class="status-badge status-${user.is_active ? 'active' : 'disabled'}">${user.is_active ? 'Active' : 'Disabled'}</span></td>
                            <td>
                                <button class="action-btn ${user.is_active ? 'btn-disable' : 'btn-enable'}" 
                                        onclick="toggleGlobalUserStatus(${user.id})">
                                    ${user.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    `).join('');
                    
                    console.log('🎯 User rows HTML:', userRows);
                    tbody.innerHTML = userRows;
                    
                    // Debug: Check if buttons are actually in the DOM
                    const actionButtons = tbody.querySelectorAll('.action-btn');
                    console.log('🔘 Found action buttons:', actionButtons.length);
                    actionButtons.forEach((btn, index) => {
                        console.log(`🔘 Button ${index}:`, btn.textContent, 'Classes:', btn.className);
                    });
                }
                
                // Update pagination controls
                updateGlobalUsersPagination();
                
            } catch (error) {
                document.getElementById('global-users-tbody').innerHTML = 
                    `<tr><td colspan="12" class="error">Error loading users: ${error.message}</td></tr>`;
            }
        }
        
        function updateGlobalUsersPagination() {
            const pagination = document.getElementById('global-users-pagination');
            const pageNumbers = document.getElementById('global-users-page-numbers');
            
            if (totalGlobalUsersPages <= 1) {
                pagination.style.display = 'none';
                return;
            }
            
            pagination.style.display = 'flex';
            
            // Update button states
            document.getElementById('global-users-first-page').disabled = currentGlobalUsersPage === 1;
            document.getElementById('global-users-prev-page').disabled = currentGlobalUsersPage === 1;
            document.getElementById('global-users-next-page').disabled = currentGlobalUsersPage === totalGlobalUsersPages;
            document.getElementById('global-users-last-page').disabled = currentGlobalUsersPage === totalGlobalUsersPages;
            
            // Generate page numbers
            let pageNumbersHtml = '';
            const startPage = Math.max(1, currentGlobalUsersPage - 2);
            const endPage = Math.min(totalGlobalUsersPages, currentGlobalUsersPage + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                pageNumbersHtml += `<button onclick="goToGlobalUsersPage(${i})" class="${i === currentGlobalUsersPage ? 'active' : ''}">${i}</button>`;
            }
            
            pageNumbers.innerHTML = pageNumbersHtml;
        }
        
        function goToGlobalUsersPage(page) {
            if (page >= 1 && page <= totalGlobalUsersPages) {
                loadGlobalUsers(page);
            }
        }
        
        function changeGlobalUsersPerPage() {
            currentGlobalUsersPage = 1;
            loadGlobalUsers(1);
        }
        
        async function loadGlobalOverview() {
            try {
                const response = await fetch('/superadmin/api/global-overview');
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('global-total-operators').textContent = data.total_operators || 0;
                    document.getElementById('global-total-users').textContent = data.total_users || 0;
                    document.getElementById('global-total-bets').textContent = data.total_bets || 0;
                    document.getElementById('global-total-revenue').textContent = `$${(data.total_revenue || 0).toFixed(2)}`;
                    document.getElementById('global-active-events').textContent = data.active_events || 0;
                    document.getElementById('global-total-liability').textContent = `$${(data.total_liability || 0).toFixed(2)}`;
                }
            } catch (error) {
                console.error('Error loading global overview:', error);
            }
        }
        
        async function loadRevenueScriptStatus() {
            try {
                const response = await fetch('/superadmin/api/revenue-script-status');
                const data = await response.json();
                
                if (data.success) {
                    const lastRevenueCalc = document.getElementById('last-revenue-calculation');
                    const lastWalletUpdate = document.getElementById('last-wallet-update');
                    
                    if (data.last_revenue_calculation) {
                        const date = new Date(data.last_revenue_calculation);
                        lastRevenueCalc.textContent = date.toLocaleString();
                        lastRevenueCalc.style.color = '#28a745';
                    } else {
                        lastRevenueCalc.textContent = 'Never run';
                        lastRevenueCalc.style.color = '#dc3545';
                    }
                    
                    if (data.last_wallet_update) {
                        const date = new Date(data.last_wallet_update);
                        lastWalletUpdate.textContent = date.toLocaleString();
                        lastWalletUpdate.style.color = '#28a745';
                    } else {
                        lastWalletUpdate.textContent = 'Never run';
                        lastWalletUpdate.style.color = '#dc3545';
                    }
                }
            } catch (error) {
                console.error('Error loading revenue script status:', error);
                document.getElementById('last-revenue-calculation').textContent = 'Error loading';
                document.getElementById('last-wallet-update').textContent = 'Error loading';
            }
        }
        
        async function runDailyRevenueCalculator() {
            const statusDiv = document.getElementById('revenue-script-status');
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<div style="color: #007bff; font-weight: 500;">🔄 Running Daily Revenue Calculator...</div>';
            
            try {
                const response = await fetch('/superadmin/api/run-daily-revenue-calculator', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.innerHTML = `
                        <div style="color: #28a745; font-weight: 500;">
                            ✅ Daily Revenue Calculator completed successfully!<br>
                            <small>Processed ${data.operators_processed} operators, ${data.calculations_created} revenue calculations created</small>
                        </div>
                    `;
                    // Refresh the status display
                    loadRevenueScriptStatus();
                } else {
                    statusDiv.innerHTML = `
                        <div style="color: #dc3545; font-weight: 500;">
                            ❌ Error running Daily Revenue Calculator: ${data.error}
                        </div>
                    `;
                }
            } catch (error) {
                statusDiv.innerHTML = `
                    <div style="color: #dc3545; font-weight: 500;">
                        ❌ Error running Daily Revenue Calculator: ${error.message}
                    </div>
                `;
            }
            
            // Hide status after 5 seconds
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 5000);
        }
        
        async function runUpdateOperatorWallets() {
            const statusDiv = document.getElementById('revenue-script-status');
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<div style="color: #007bff; font-weight: 500;">🔄 Updating Operator Wallets...</div>';
            
            try {
                const response = await fetch('/superadmin/api/run-update-operator-wallets', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.innerHTML = `
                        <div style="color: #28a745; font-weight: 500;">
                            ✅ Operator Wallets updated successfully!<br>
                            <small>Processed ${data.calculations_processed} revenue calculations, ${data.wallets_updated} wallets updated</small>
                        </div>
                    `;
                    // Refresh the status display
                    loadRevenueScriptStatus();
                } else {
                    statusDiv.innerHTML = `
                        <div style="color: #dc3545; font-weight: 500;">
                            ❌ Error updating Operator Wallets: ${data.error}
                        </div>
                    `;
                }
            } catch (error) {
                statusDiv.innerHTML = `
                    <div style="color: #dc3545; font-weight: 500;">
                        ❌ Error updating Operator Wallets: ${error.message}
                    </div>
                `;
            }
            
            // Hide status after 5 seconds
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 5000);
        }
        
        async function resetAllGlobalUsers() {
            const resetAmount = document.getElementById('global-reset-balance-amount').value;
            
            if (!resetAmount || resetAmount < 0) {
                alert('Please enter a valid balance amount (must be 0 or greater)');
                return;
            }
            
            if (!confirm(`⚠️ WARNING: This will:\n\n1. Cancel ALL pending bets (refund stakes) across ALL operators\n2. Reset ALL user balances to $${resetAmount} across ALL operators\n3. Set default balance for NEW users to $${resetAmount}\n4. This action cannot be undone!\n\nAre you sure you want to continue?`)) {
                return;
            }
            
            try {
                const response = await fetch('/superadmin/api/global-users/reset', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        new_balance: parseFloat(resetAmount)
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`✅ Successfully reset all users across all operators!\n\n- ${data.bets_cancelled} pending bets cancelled (refunded)\n- ${data.users_reset} user balances reset to $${resetAmount}\n- New users will now get $${resetAmount} by default`);
                    loadGlobalUsers(); // Reload the users table
                } else {
                    alert('❌ Error: ' + data.error);
                }
                
            } catch (error) {
                alert('❌ Error resetting users: ' + error.message);
            }
        }
        
        async function loadOperators() {
            try {
                const response = await fetch('/superadmin/api/operators');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('operators-tbody').innerHTML = 
                        `<tr><td colspan="11" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                const tbody = document.getElementById('operators-tbody');
                if (data.operators.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="11" class="loading">No operators found</td></tr>`;
                } else {
                    tbody.innerHTML = data.operators.map(op => `
                        <tr>
                            <td>${op.id}</td>
                            <td><span class="operator-name">${op.sportsbook_name}</span></td>
                            <td>${op.subdomain}</td>
                            <td>${op.login}</td>
                            <td>${op.email}</td>
                            <td>${op.user_count}</td>
                            <td>${op.bet_count}</td>
                            <td>$${op.revenue.toFixed(2)}</td>
                            <td>${new Date(op.created_at).toLocaleDateString()}</td>
                            <td><span class="status-badge status-${op.is_active ? 'active' : 'disabled'}">${op.is_active ? 'Active' : 'Disabled'}</span></td>
                            <td>
                                <button class="action-btn ${op.is_active ? 'btn-disable' : 'btn-enable'}" 
                                        onclick="toggleOperatorStatus(${op.id})">
                                    ${op.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    `).join('');
                }
                
            } catch (error) {
                document.getElementById('operators-tbody').innerHTML = 
                    `<tr><td colspan="11" class="error">Error loading operators: ${error.message}</td></tr>`;
            }
        }
        
        async function loadGlobalReports() {
            try {
                const response = await fetch('/superadmin/api/global-reports/overview');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('global-reports-tbody').innerHTML = 
                        `<tr><td colspan="5" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                // Update summary cards
                document.getElementById('global-reports-total-bets').textContent = data.overview.total_bets || 0;
                document.getElementById('global-reports-total-stakes').textContent = `$${(data.overview.total_stakes || 0).toFixed(2)}`;
                document.getElementById('global-reports-total-revenue').textContent = `$${(data.overview.total_revenue || 0).toFixed(2)}`;
                document.getElementById('global-reports-win-rate').textContent = `${(data.overview.win_rate || 0).toFixed(1)}%`;
                
                // Update table
                const tbody = document.getElementById('global-reports-tbody');
                if (data.daily_data && data.daily_data.length > 0) {
                    tbody.innerHTML = data.daily_data.map(row => `
                        <tr>
                            <td>${row.bet_date}</td>
                            <td>${row.sport_name || 'All Sports'}</td>
                            <td>${row.daily_bets || 0}</td>
                            <td>$${(row.daily_stakes || 0).toFixed(2)}</td>
                            <td class="${(row.daily_revenue || 0) >= 0 ? 'positive' : 'negative'}">$${(row.daily_revenue || 0).toFixed(2)}</td>
                        </tr>
                    `).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="5" class="loading">No report data available</td></tr>`;
                }
                
            } catch (error) {
                document.getElementById('global-reports-tbody').innerHTML = 
                    `<tr><td colspan="5" class="error">Error loading reports: ${error.message}</td></tr>`;
            }
        }
        
        async function loadGlobalReportBuilder() {
            try {
                // Load available sports for filtering
                const response = await fetch('/superadmin/api/global-reports/available-sports');
                const data = await response.json();
                
                if (data.sports) {
                    const sportSelect = document.getElementById('global-events-sport-filter');
                    sportSelect.innerHTML = '<option value="">All Sports</option>';
                    data.sports.forEach(sport => {
                        sportSelect.innerHTML += `<option value="${sport}">${sport}</option>`;
                    });
                }
                
                // Set default dates (last 30 days)
                const today = new Date();
                const thirtyDaysAgo = new Date(today.getTime() - (30 * 24 * 60 * 60 * 1000));
                
                document.getElementById('global-date-from').value = thirtyDaysAgo.toISOString().split('T')[0];
                document.getElementById('global-date-to').value = today.toISOString().split('T')[0];
                
            } catch (error) {
                console.error('Error loading report builder:', error);
            }
        }
        
        async function generateGlobalReport() {
            try {
                const reportType = document.getElementById('global-report-type').value;
                const dateFrom = document.getElementById('global-date-from').value;
                const dateTo = document.getElementById('global-date-to').value;
                const sportFilter = document.getElementById('global-sport-filter').value;
                const groupBy = document.getElementById('global-group-by').value;
                
                const requestData = {
                    report_type: reportType,
                    date_from: dateFrom,
                    date_to: dateTo,
                    sport_filter: sportFilter,
                    group_by: groupBy
                };
                
                const response = await fetch('/superadmin/api/global-reports/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });
                
                const data = await response.json();
                
                if (data.error) {
                    alert('Error generating report: ' + data.error);
                    return;
                }
                
                // Display report results
                displayGlobalReportResults(data, reportType);
                
            } catch (error) {
                alert('Error generating report: ' + error.message);
            }
        }
        
        function displayGlobalReportResults(data, reportType) {
            const resultsDiv = document.getElementById('global-report-results');
            const header = document.getElementById('global-report-header');
            const body = document.getElementById('global-report-body');
            
            // Show results section
            resultsDiv.style.display = 'block';
            
            // Set headers based on report type
            let headers = [];
            if (reportType === 'revenue') {
                headers = ['Date', 'Sport', 'Total Bets', 'Total Stakes', 'Revenue'];
            } else if (reportType === 'user-activity') {
                headers = ['Username', 'Email', 'Total Bets', 'Total Staked', 'Payout', 'Profit', 'Join Date'];
            } else if (reportType === 'betting-patterns') {
                headers = ['Date', 'Sport', 'Bet Type', 'Count', 'Total Amount', 'Win Rate'];
            } else if (reportType === 'sport-performance') {
                headers = ['Sport', 'Total Bets', 'Total Stakes', 'Won Bets', 'Lost Bets', 'Revenue', 'Win Rate'];
            }
            
            // Create header row
            header.innerHTML = `<tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
            
            // Create body rows
            if (data.length === 0) {
                body.innerHTML = `<tr><td colspan="${headers.length}" class="loading">No data available for selected criteria</td></tr>`;
            } else {
                body.innerHTML = data.map(row => {
                    const cells = headers.map(header => {
                        let value = '';
                        if (header === 'Date' && row.bet_date) {
                            value = row.bet_date;
                        } else if (header === 'Sport' && row.sport_name) {
                            value = row.sport_name;
                        } else if (header === 'Total Bets' && row.total_bets !== undefined) {
                            value = row.total_bets;
                        } else if (header === 'Total Stakes' && row.total_stakes !== undefined) {
                            value = `$${(row.total_stakes || 0).toFixed(2)}`;
                        } else if (header === 'Revenue' && row.revenue !== undefined) {
                            const revenueClass = (row.revenue || 0) >= 0 ? 'positive' : 'negative';
                            value = `<span class="${revenueClass}">$${(row.revenue || 0).toFixed(2)}</span>`;
                        } else if (header === 'Username' && row.username) {
                            value = row.username;
                        } else if (header === 'Email' && row.email) {
                            value = row.email;
                        } else if (header === 'Total Staked' && row.total_staked !== undefined) {
                            value = `$${(row.total_staked || 0).toFixed(2)}`;
                        } else if (header === 'Payout' && row.payout !== undefined) {
                            value = `$${(row.payout || 0).toFixed(2)}`;
                        } else if (header === 'Profit' && row.user_profit !== undefined) {
                            const profitClass = (row.user_profit || 0) >= 0 ? 'positive' : 'negative';
                            value = `<span class="${profitClass}">$${(row.user_profit || 0).toFixed(2)}</span>`;
                        } else if (header === 'Join Date' && row.joined_date) {
                            value = new Date(row.joined_date).toLocaleDateString();
                        } else if (header === 'Bet Type' && row.bet_type) {
                            value = row.bet_type;
                        } else if (header === 'Count' && row.count !== undefined) {
                            value = row.count;
                        } else if (header === 'Total Amount' && row.total_amount !== undefined) {
                            value = `$${(row.total_amount || 0).toFixed(2)}`;
                        } else if (header === 'Win Rate' && row.win_rate !== undefined) {
                            value = `${(row.win_rate || 0).toFixed(1)}%`;
                        } else if (header === 'Won Bets' && row.won_bets !== undefined) {
                            value = row.won_bets;
                        } else if (header === 'Lost Bets' && row.lost_bets !== undefined) {
                            value = row.lost_bets;
                        } else {
                            value = row[Object.keys(row).find(key => key.toLowerCase().includes(header.toLowerCase().replace(' ', '_')))] || '';
                        }
                        return `<td>${value}</td>`;
                    });
                    return `<tr>${cells.join('')}</tr>`;
                }).join('');
            }
        }
        
        async function exportGlobalReport() {
            try {
                const reportType = document.getElementById('global-report-type').value;
                const dateFrom = document.getElementById('global-date-from').value;
                const dateTo = document.getElementById('global-date-to').value;
                const sportFilter = document.getElementById('global-sport-filter').value;
                
                const requestData = {
                    report_type: reportType,
                    date_from: dateFrom,
                    date_to: dateTo,
                    sport_filter: sportFilter,
                    format: 'csv'
                };
                
                const response = await fetch('/superadmin/api/global-reports/export', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });
                
                if (response.ok) {
                    // Create download link
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${reportType}_global_report.csv`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    const errorData = await response.json();
                    alert('Error exporting report: ' + (errorData.error || 'Unknown error'));
                }
                
            } catch (error) {
                alert('Error exporting report: ' + error.message);
            }
        }
        
        async function toggleGlobalUserStatus(userId) {
            try {
                const response = await fetch(`/superadmin/api/user/${userId}/toggle`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    loadGlobalUsers(); // Reload the users table
                } else {
                    alert('Error: ' + data.error);
                }
                
            } catch (error) {
                alert('Error toggling user status: ' + error.message);
            }
        }
        
        async function toggleOperatorStatus(operatorId) {
            try {
                const response = await fetch(`/superadmin/api/operator/${operatorId}/toggle`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    loadOperators(); // Reload the operators table
                } else {
                    alert('Error: ' + data.error);
                }
                
            } catch (error) {
                alert('Error toggling operator status: ' + error.message);
            }
        }
        
        // Global Betting Events Management Functions
        function loadGlobalBettingEventsWithFilters() {
            const sportFilter = document.getElementById('global-events-sport-filter').value;
            const marketFilter = document.getElementById('global-market-filter').value;
            const searchTerm = document.getElementById('global-event-search').value;
            const showBetsOnly = document.getElementById('global-show-bets-only').checked;

                         // Show loading state
             document.getElementById('global-events-tbody').innerHTML = `<tr><td colspan="9" class="loading">Loading global events...</td></tr>`;

            fetch('/superadmin/api/global-betting-events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sport: sportFilter,
                    market: marketFilter,
                    search: searchTerm,
                    show_bets_only: showBetsOnly
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayGlobalEvents(data.events);
                    // Update total liability in summary card from table data
                    if (document.getElementById('global-total-liability')) {
                        document.getElementById('global-total-liability').textContent = '$' + (data.summary.total_liability || 0).toFixed(2);
                    }
                    loadGlobalSportsFilter(data.filters.sports);
                    loadGlobalMarketsFilter(data.filters.markets);
                } else {
                    document.getElementById('global-events-tbody').innerHTML = `<tr><td colspan="9" class="error">Error loading events: ${data.error}</td></tr>`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('global-events-tbody').innerHTML = `<tr><td colspan="9" class="error">Failed to load events</td></tr>`;
            });
        }

        function refreshGlobalEvents() {
            loadGlobalBettingEventsWithFilters();
        }

        // Table sorting function
        function sortTable(tableId, columnIndex) {
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            // Get current sort direction
            const header = table.querySelector(`th:nth-child(${columnIndex + 1})`);
            const currentDirection = header.getAttribute('data-sort-direction') || 'asc';
            const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
            
            // Update all headers to remove sort indicators
            table.querySelectorAll('th').forEach(th => {
                th.setAttribute('data-sort-direction', '');
                const icon = th.querySelector('.sort-icon');
                if (icon) icon.textContent = '↕';
            });
            
            // Update current header
            header.setAttribute('data-sort-direction', newDirection);
            const icon = header.querySelector('.sort-icon');
            if (icon) icon.textContent = newDirection === 'asc' ? '↑' : '↓';
            
            // Sort rows
            rows.sort((a, b) => {
                const aValue = a.cells[columnIndex].getAttribute('data-sort') || a.cells[columnIndex].textContent;
                const bValue = b.cells[columnIndex].getAttribute('data-sort') || b.cells[columnIndex].textContent;
                
                // Handle numeric values
                const aNum = parseFloat(aValue);
                const bNum = parseFloat(bValue);
                
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return newDirection === 'asc' ? aNum - bNum : bNum - aNum;
                }
                
                // Handle string values
                const aStr = String(aValue).toLowerCase();
                const bStr = String(bValue).toLowerCase();
                
                if (newDirection === 'asc') {
                    return aStr.localeCompare(bStr);
                } else {
                    return bStr.localeCompare(aStr);
                }
            });
            
            // Reorder rows in the table
            rows.forEach(row => tbody.appendChild(row));
        }

        function displayGlobalEvents(events) {
            const tbody = document.getElementById('global-events-tbody');
            tbody.innerHTML = '';

            if (events.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="no-data">No events found</td></tr>`;
                return;
            }

            events.forEach(event => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td data-sort="${event.event_id}">${event.event_id}</td>
                    <td data-sort="${event.sport}">${event.sport}</td>
                    <td data-sort="${event.event_name}">${event.event_name}</td>
                    <td data-sort="${event.market}">${event.market}</td>
                    <td data-sort="${event.total_bets}">${event.total_bets}</td>
                    <td data-sort="${event.liability}" class="${event.liability < 0 ? 'negative' : 'positive'}">$${Math.abs(event.liability).toFixed(2)}</td>
                    <td data-sort="${event.revenue}" class="${event.revenue < 0 ? 'negative' : 'positive'}">$${Math.abs(event.revenue).toFixed(2)}</td>
                    <td data-sort="${event.status}"><span class="status-badge ${event.status}">${event.status}</td>
                    <td>
                        <button onclick="toggleGlobalEventStatus('${event.event_id}', '${event.status}')" 
                                class="btn ${event.status === 'active' ? 'btn-danger' : 'btn-success'} btn-sm">
                            ${event.status === 'active' ? 'Disable' : 'Enable'}
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }

        function loadGlobalStats() {
            fetch('/superadmin/api/global-stats')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error loading global stats:', data.error);
                        return;
                    }
                    updateGlobalSummaryCards(data);
                })
                .catch(error => {
                    console.error('Error loading global stats:', error);
                });
        }

        function updateGlobalSummaryCards(stats) {
            // Update the summary cards with global stats
            if (document.getElementById('global-total-operators')) {
                document.getElementById('global-total-operators').textContent = stats.total_operators || 0;
            }
            if (document.getElementById('global-total-users')) {
                document.getElementById('global-total-users').textContent = stats.total_users || 0;
            }
            if (document.getElementById('global-total-bets')) {
                document.getElementById('global-total-bets').textContent = stats.total_bets || 0;
            }
            if (document.getElementById('global-total-revenue')) {
                document.getElementById('global-total-revenue').textContent = '$' + (stats.total_revenue || 0).toFixed(2);
            }
            if (document.getElementById('global-active-events')) {
                document.getElementById('global-active-events').textContent = stats.active_events || 0;
            }
            if (document.getElementById('global-total-liability')) {
                document.getElementById('global-total-liability').textContent = '$' + (stats.total_liability || 0).toFixed(2);
            }
        }

        function loadGlobalSportsFilter(sports) {
            const select = document.getElementById('global-events-sport-filter');
            select.innerHTML = '<option value="">All Sports</option>';
            sports.forEach(sport => {
                const option = document.createElement('option');
                option.value = sport;
                option.textContent = sport;
                select.appendChild(option);
            });
        }

        function loadGlobalMarketsFilter(markets) {
            const select = document.getElementById('global-market-filter');
            select.innerHTML = '<option value="">All Markets</option>';
            markets.forEach(market => {
                const option = document.createElement('option');
                option.value = market;
                option.textContent = market;
                select.appendChild(option);
            });
        }

        function toggleGlobalEventStatus(eventId, currentStatus) {
            const newStatus = currentStatus === 'active' ? 'disabled' : 'active';
            
            fetch('/superadmin/api/global-betting-events/toggle-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_id: eventId,
                    status: newStatus
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message
                    alert(data.message);
                    // Refresh the events to show updated status
                    loadGlobalBettingEvents();
                } else {
                    alert('Error updating event status: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to update event status');
            });
        }

        // Add event listeners for filters
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded, setting up event listeners...');
            
            // Load initial data for global overview
            loadGlobalOverview();
            loadRevenueScriptStatus();
            
            // Test the showSection function
            window.testShowSection = function(sectionId) {
                console.log('Testing showSection with:', sectionId);
                showSection(sectionId);
            };
            // Global betting events filters
            const globalSportFilter = document.getElementById('global-events-sport-filter');
            const globalMarketFilter = document.getElementById('global-market-filter');
            const globalEventSearch = document.getElementById('global-event-search');
            const globalShowBetsOnly = document.getElementById('global-show-bets-only');

            if (globalSportFilter) {
                globalSportFilter.addEventListener('change', loadGlobalBettingEvents);
            }
            if (globalMarketFilter) {
                globalMarketFilter.addEventListener('change', loadGlobalBettingEvents);
            }
            if (globalEventSearch) {
                globalEventSearch.addEventListener('input', debounce(loadGlobalBettingEvents, 500));
            }
            if (globalShowBetsOnly) {
                globalShowBetsOnly.addEventListener('change', loadGlobalBettingEvents);
            }

                    // Load initial global stats (since global overview is the default active tab)
        loadGlobalStats();
    });
    
    // Tab switching function
    function showSection(sectionId) {
        console.log('🔍 showSection called with:', sectionId);
        
        // Hide all sections
        const allSections = document.querySelectorAll('.section, .content-section');
        console.log('📋 Found sections:', allSections.length);
        allSections.forEach(section => {
            section.classList.remove('active');
            console.log('🚫 Hiding section:', section.id, 'Classes:', section.className);
        });
        
        // Remove active class from all tabs
        const allTabs = document.querySelectorAll('.nav-tab');
        console.log('📋 Found tabs:', allTabs.length);
        allTabs.forEach(tab => {
            tab.classList.remove('active');
        });
        
        // Show selected section
        const selectedSection = document.getElementById(sectionId);
        console.log('🎯 Looking for section with ID:', sectionId);
        if (selectedSection) {
            selectedSection.classList.add('active');
            console.log('✅ Showing section:', sectionId, 'Classes:', selectedSection.className);
            
            // Check if section is visible
            const computedStyle = window.getComputedStyle(selectedSection);
            console.log('🎨 Section display style:', computedStyle.display);
            console.log('🎨 Section visibility style:', computedStyle.visibility);
        } else {
            console.error('❌ Section not found:', sectionId);
            console.log('🔍 Available sections:', Array.from(allSections).map(s => s.id));
        }
        
        // Add active class to clicked tab
        if (event && event.target) {
            event.target.classList.add('active');
            console.log('✅ Activated tab:', event.target.textContent);
        }
        
        // Load data for specific sections
        console.log('🔄 Loading data for section:', sectionId);
        if (sectionId === 'global-overview') {
            console.log('🏠 Loading global overview...');
            loadGlobalOverview();
            loadRevenueScriptStatus();
        } else if (sectionId === 'global-betting-events') {
            console.log('📊 Loading global betting events...');
            loadGlobalBettingEvents();
        } else if (sectionId === 'manual-settlement') {
            console.log('💰 Loading manual settlement...');
            loadSettlementData();
        } else if (sectionId === 'global-user-management') {
            console.log('👥 Loading global users...');
            loadGlobalUsers();
        } else if (sectionId === 'global-reports') {
            console.log('📈 Loading global reports...');
            loadGlobalReports();
        } else if (sectionId === 'operator-management') {
            console.log('🏢 Loading operators...');
            loadOperators();
        } else if (sectionId === 'global-report-builder') {
            console.log('🔧 Loading report builder...');
            // Load report builder if needed
        }
    }
    
    // Make showSection globally accessible
    window.showSection = showSection;
    


        // Debounce function for search input
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
        
        // Console banner for debugging
        console.log('🎯 Rich Superadmin Interface loaded successfully');
        console.log('🔧 Debounce function:', debounce.toString());
        console.log('✅ showSection function:', typeof showSection);
        
        // Manual Settlement Functions
        async function loadSettlementData() {
            try {
                const response = await fetch('/superadmin/api/manual-settlement');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('settlement-tbody').innerHTML = 
                        `<tr><td colspan="7" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                if (!data.success) {
                    document.getElementById('settlement-tbody').innerHTML = 
                        `<tr><td colspan="7" class="error">Error: ${data.error || 'Failed to load data'}</td></tr>`;
                    return;
                }
                
                const settlementData = data.data;
                
                // Update summary cards
                document.getElementById('total-matches').textContent = settlementData.length;
                document.getElementById('total-liability').textContent = `$${settlementData.reduce((sum, item) => sum + item.total_liability, 0).toFixed(2)}`;
                document.getElementById('pending-bets').textContent = settlementData.reduce((sum, item) => sum + item.bets.length, 0);
                
                // Update table
                const tbody = document.getElementById('settlement-tbody');
                if (settlementData.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" class="loading">No pending bets to settle</td></tr>`;
                } else {
                    tbody.innerHTML = settlementData.map(item => `
                        <tr>
                            <td>
                                <div style="font-weight: 600; color: #007bff;">${item.bets.map(bet => bet.id).join(', ')}</div>
                                <div style="font-size: 0.8rem; color: #666;">Bet ID${item.bets.length > 1 ? 's' : ''}</div>
                            </td>
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
                                    <option value="none">None (No Winner)</option>
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
                document.getElementById('settlement-tbody').innerHTML = 
                    `<tr><td colspan="7" class="error">Error loading settlement data: ${error.message}</td></tr>`;
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
            let confirmationMessage;
            if (winningSelection === 'no_result') {
                confirmationMessage = `Are you sure you want to CANCEL ${matchName}?\n\nAction: No Result (Cancel & Refund)\n\nThis will:\n• Cancel all bets for this match\n• Refund all stakes to users\n• Mark bets as "voided"\n\nThis action cannot be undone.`;
            } else if (winningSelection === 'none') {
                confirmationMessage = `Are you sure you want to settle ${matchName}?\n\nResult: None (All bets lose)\n\nThis action cannot be undone.`;
            } else {
                confirmationMessage = `Are you sure you want to settle ${matchName}?\n\nWinning selection: ${winningSelection}\n\nThis action cannot be undone.`;
            }
                
            if (!confirm(confirmationMessage)) {
                return;
            }
            
            try {
                const response = await fetch('/superadmin/api/manual-settle', {
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
                    // Success - just refresh the data without showing another alert
                    // The confirmation dialog already confirmed the action
                    loadSettlementData();
                } else {
                    alert('Failed to settle bets: ' + (data.error || 'Unknown error'));
                }
                
            } catch (error) {
                alert('Error settling bets: ' + error.message);
            }
        }

        // Export Pending Bets Functionality
        document.addEventListener('DOMContentLoaded', function() {
            const exportBtn = document.getElementById('exportPendingBetsBtn');
            if (exportBtn) {
                exportBtn.addEventListener('click', async function() {
                    const btn = this;
                    const btnText = btn.querySelector('.btn-text');
                    const btnLoading = btn.querySelector('.btn-loading');
                    const statusDiv = document.getElementById('exportStatus');
                    
                    // Show loading state
                    btn.disabled = true;
                    btnText.style.display = 'none';
                    btnLoading.style.display = 'inline';
                    statusDiv.style.display = 'none';
                    
                    try {
                        const response = await fetch('/api/superadmin/export-pending-bets');
                        const result = await response.json();
                        
                        if (result.success) {
                            // Create and download CSV file
                            const blob = new Blob([result.csv_content], { type: 'text/csv' });
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = result.filename;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);
                            
                            // Show success message
                            statusDiv.className = 'export-status success';
                            statusDiv.innerHTML = `✅ Successfully exported ${result.count} pending bets to ${result.filename}`;
                            statusDiv.style.display = 'block';
                        } else {
                            // Show error message
                            statusDiv.className = 'export-status error';
                            statusDiv.innerHTML = `❌ Error: ${result.error}`;
                            statusDiv.style.display = 'block';
                        }
                    } catch (error) {
                        console.error('Export error:', error);
                        statusDiv.className = 'export-status error';
                        statusDiv.innerHTML = '❌ Network error occurred while exporting';
                        statusDiv.style.display = 'block';
                    } finally {
                        // Reset button state
                        btn.disabled = false;
                        btnText.style.display = 'inline';
                        btnLoading.style.display = 'none';
                    }
                });
            }
        });

        // CSV Upload Functionality
        document.addEventListener('DOMContentLoaded', function() {
            const processBtn = document.getElementById('processSettlementBtn');
            const downloadTemplateBtn = document.getElementById('downloadTemplateBtn');
            const csvFileInput = document.getElementById('csvFile');
            
            // Download Template functionality
            if (downloadTemplateBtn) {
                downloadTemplateBtn.addEventListener('click', function() {
                    const csvContent = 'Bet ID,Result\n54,WON\n53,LOST\n52,Results Pending\n51,No Results';
                    const blob = new Blob([csvContent], { type: 'text/csv' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'bet_settlement_template.csv';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                });
            }
            
            // Process Settlement functionality
            if (processBtn) {
                processBtn.addEventListener('click', async function() {
                    const file = csvFileInput.files[0];
                    if (!file) {
                        alert('Please select a CSV file first');
                        return;
                    }
                    
                    const btn = this;
                    const btnText = btn.querySelector('.btn-text');
                    const btnLoading = btn.querySelector('.btn-loading');
                    const statusDiv = document.getElementById('uploadStatus');
                    
                    // Show loading state
                    btn.disabled = true;
                    btnText.style.display = 'none';
                    btnLoading.style.display = 'inline';
                    statusDiv.style.display = 'none';
                    
                    try {
                        const formData = new FormData();
                        formData.append('csv_file', file);
                        
                        const response = await fetch('/api/superadmin/process-csv-settlement', {
                            method: 'POST',
                            body: formData
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            // Show success message
                            statusDiv.className = 'upload-status success';
                            statusDiv.innerHTML = `✅ Successfully processed ${result.processed_count} bets. ${result.won_count} won, ${result.lost_count} lost, ${result.pending_count} pending, ${result.no_results_count} no results.`;
                            statusDiv.style.display = 'block';
                            
                            // Reload settlement data to reflect changes
                            if (typeof loadSettlementData === 'function') {
                                loadSettlementData();
                            }
                        } else {
                            // Show error message
                            statusDiv.className = 'upload-status error';
                            statusDiv.innerHTML = `❌ Error: ${result.error}`;
                            statusDiv.style.display = 'block';
                        }
                    } catch (error) {
                        console.error('Upload error:', error);
                        statusDiv.className = 'upload-status error';
                        statusDiv.innerHTML = '❌ Network error occurred while processing CSV';
                        statusDiv.style.display = 'block';
                    } finally {
                        // Reset button state
                        btn.disabled = false;
                        btnText.style.display = 'inline';
                        btnLoading.style.display = 'none';
                    }
                });
            }
        });
    </script>
</body>
</html>
'''

