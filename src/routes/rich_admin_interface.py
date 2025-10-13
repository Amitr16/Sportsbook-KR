"""
Rich Admin Interface - Extracted from original admin_app.py with tenant filtering
"""

from flask import Blueprint, request, session, redirect, render_template_string, jsonify
from src import sqlite3_shim as sqlite3
import json
from datetime import datetime, timedelta
import os
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

rich_admin_bp = Blueprint('rich_admin', __name__)

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim"""
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    conn.row_factory = sqlite3.Row
    return conn

def require_admin_auth(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if this is an API call (URL contains /api/)
        is_api_call = '/api/' in request.path
        
        # Check for admin-specific session keys
        if 'admin_operator_id' not in session:
            if is_api_call:
                return jsonify({'error': 'Unauthorized'}), 401
            else:
                return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

def calculate_casino_revenue(operator_id, conn):
    """Calculate casino revenue from game_round table for a specific operator"""
    try:
        # Calculate casino revenue from game_round table
        casino_query = """
        SELECT 
            SUM(gr.stake) as total_stakes,
            SUM(gr.payout) as total_payouts
        FROM game_round gr
        JOIN users u ON gr.user_id = u.id::text
        WHERE u.sportsbook_operator_id = ?
        """
        
        result = conn.execute(casino_query, (operator_id,)).fetchone()
        
        total_stakes = float(result['total_stakes'] or 0)
        total_payouts = float(result['total_payouts'] or 0)
        
        # Casino revenue = Money kept from losing games - Money paid to winners
        casino_revenue = total_stakes - total_payouts
        
        return casino_revenue
        
    except Exception as e:
        print(f"Error calculating casino revenue for operator {operator_id}: {e}")
        return 0.0

def calculate_sportsbook_revenue(operator_id, conn):
    """Calculate sportsbook revenue from bets table for a specific operator"""
    try:
        # Calculate sportsbook revenue from settled bets
        sportsbook_query = """
        SELECT 
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = ?
        """
        
        result = conn.execute(sportsbook_query, (operator_id,)).fetchone()
        
        total_stakes_lost = float(result['total_stakes_lost'] or 0)
        total_net_payouts = float(result['total_net_payouts'] or 0)
        
        # Sportsbook revenue = Money kept from losing bets - Extra money paid to winners
        sportsbook_revenue = total_stakes_lost - total_net_payouts
        
        return sportsbook_revenue
        
    except Exception as e:
        print(f"Error calculating sportsbook revenue for operator {operator_id}: {e}")
        return 0.0

def update_operator_revenue(operator_id, conn):
    """Update the total_revenue field for an operator based on both sportsbook and casino revenue"""
    try:
        # Calculate sportsbook revenue
        sportsbook_revenue = calculate_sportsbook_revenue(operator_id, conn)
        
        # Calculate casino revenue
        casino_revenue = calculate_casino_revenue(operator_id, conn)
        
        # Combined total revenue
        total_revenue = sportsbook_revenue + casino_revenue
        
        # Update the operator's total_revenue field
        conn.execute("""
            UPDATE sportsbook_operators 
            SET total_revenue = ? 
            WHERE id = ?
        """, (total_revenue, operator_id))
        
        print(f"✅ Updated operator {operator_id} total_revenue to: {total_revenue}")
        print(f"   📊 Sportsbook: ${sportsbook_revenue:.2f}, 🎰 Casino: ${casino_revenue:.2f}")
        
    except Exception as e:
        print(f"❌ Error updating operator revenue: {e}")

def get_default_user_balance(operator_id):
    """Get the default balance for new users under this operator"""
    try:
        conn = get_db_connection()
        
        # Get operator settings
        operator_row = conn.execute(
            "SELECT settings FROM sportsbook_operators WHERE id = ?",
            (operator_id,)
        ).fetchone()
        
        conn.close()
        
        if operator_row and operator_row['settings']:
            import json
            settings = json.loads(operator_row['settings'])
            default_balance = settings.get('default_user_balance')
            if default_balance is not None:
                return float(default_balance)
        
        # Fall back to default $1000 if no setting found
        return 1000.0
        
    except Exception as e:
        print(f"⚠️ Warning: Could not get default user balance for operator {operator_id}: {e}")
        return 1000.0

def calculate_event_financials(event_id, market_id, sport_name, operator_id):
    """Calculate max liability and max possible gain for a specific event+market combination for a specific operator"""
    try:
        conn = get_db_connection()
        
        # Get all pending bets for this specific event+market combination from this operator's users
        query = """
        SELECT b.bet_selection, b.stake, b.potential_return, b.odds
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
        AND u.sportsbook_operator_id = ?
        """
        
        bets = conn.execute(query, (event_id, market_id, sport_name, operator_id)).fetchall()
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
        print(f"Error calculating financials: {e}")
        return 0.0, 0.0

def calculate_total_revenue(operator_id):
    """Calculate total revenue from both sportsbook and casino for a specific operator"""
    try:
        conn = get_db_connection()
        
        # Calculate sportsbook revenue
        sportsbook_revenue = calculate_sportsbook_revenue(operator_id, conn)
        
        # Calculate casino revenue
        casino_revenue = calculate_casino_revenue(operator_id, conn)
        
        # Combined total revenue
        total_revenue = sportsbook_revenue + casino_revenue
        
        conn.close()
        
        return total_revenue
        
    except Exception as e:
        print(f"Error calculating total revenue: {e}")
        return 0.0

def get_operator_from_session():
    """Get operator info from session - ADMIN ONLY"""
    print(f"🔍 DEBUG: Session data: {session}")
    print(f"🔍 DEBUG: admin_operator_id in session: {session.get('admin_operator_id')}")
    print(f"🔍 DEBUG: admin_subdomain in session: {session.get('admin_subdomain')}")
    
    # Only use admin-specific session keys to prevent superadmin interference
    operator_id = session.get('admin_operator_id')
    operator_subdomain = session.get('admin_subdomain')
    
    if not operator_id:
        print("❌ DEBUG: No admin_operator_id in session - admin not logged in")
        return None
    
    conn = get_db_connection()
    operator = conn.execute("""
        SELECT id, sportsbook_name, login, subdomain, email
        FROM sportsbook_operators 
        WHERE id = ?
    """, (operator_id,)).fetchone()
    conn.close()
    
    print(f"🔍 DEBUG: Operator found: {operator}")
    return dict(operator) if operator else None

def serve_rich_admin_template(subdomain):
    """Serve rich admin template for a specific subdomain"""
    # Check if admin is logged in using new session keys, fall back to old ones
    operator_id = session.get('operator_id') or session.get('admin_operator_id')
    operator_subdomain = session.get('operator_subdomain') or session.get('admin_subdomain')
    
    if not operator_id or operator_subdomain != subdomain:
        return redirect(f'/{subdomain}/admin/login')
    
    operator = get_operator_from_session()
    if not operator:
        return redirect(f'/{subdomain}/admin/login')
    
    # Render the rich admin template with operator branding
    return render_template_string(RICH_ADMIN_TEMPLATE, operator=operator)

@rich_admin_bp.route('/<subdomain>/admin')
@rich_admin_bp.route('/<subdomain>/admin/')
def rich_admin_dashboard(subdomain):
    """Rich admin dashboard with tenant filtering"""
    return serve_rich_admin_template(subdomain)

@rich_admin_bp.route('/<subdomain>/admin/api/betting-events')
def get_tenant_betting_events(subdomain):
    """Get betting events filtered by tenant with bet-level information"""
    print(f"🔍 DEBUG: get_tenant_betting_events called for subdomain: {subdomain}")
    
    # Get operator from session
    operator = get_operator_from_session()
    if not operator:
        print(f"🔍 DEBUG: No operator found in session")
        return jsonify({'error': 'Unauthorized'}), 401
    
    print(f"🔍 DEBUG: Operator found: {operator['id']} ({operator['subdomain']})")
    
    try:
        import os
        import json
        
        # Get database connection for checking disabled events and bet information
        print(f"🔍 DEBUG: Getting database connection...")
        conn = get_db_connection()
        print(f"🔍 DEBUG: Database connection established")
        
        # Path to Sports Pre Match directory - use absolute path from project root
        sports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Sports Pre Match')
        print(f"🔍 DEBUG: Sports directory path: {sports_dir}")
        
        all_events = []
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get filter and search parameters
        sport_filter = request.args.get('sport', '')
        market_filter = request.args.get('market', '')
        search_query = request.args.get('search', '').lower()
        sort_by = request.args.get('sort_by', 'event_id')
        sort_order = request.args.get('sort_order', 'asc')
        
        print(f"🔍 DEBUG: Query params - page: {page}, per_page: {per_page}, sort_by: {sort_by}, sort_order: {sort_order}")
        print(f"🔍 DEBUG: Filters - sport: {sport_filter}, market: {market_filter}, search: {search_query}")
        print(f"🔍 DEBUG: Always showing only events with bets")
        
        # Simple query: Get all pending bets grouped by event_id + market_id
        bet_events_query = """
            SELECT 
                b.match_id,
                b.sport_name,
                b.market,
                COUNT(*) as bet_count,
                SUM(b.stake) as total_stake,
                SUM(b.potential_return) as total_potential_return,
                SUM(b.potential_return) as total_liability,
                SUM(b.potential_return - b.stake) as total_revenue,
                SUM(CASE WHEN b.is_active = TRUE THEN 1 ELSE 0 END) as active_bet_count,
                COUNT(*) as total_bet_count
            FROM bets b
            JOIN users u ON b.user_id = u.id
            WHERE u.sportsbook_operator_id = ? AND b.status = 'pending'
            GROUP BY b.match_id, b.sport_name, b.market
            ORDER BY b.match_id, b.sport_name, b.market
        """
        
        print(f"🔍 DEBUG: Executing SQL query for operator {operator['id']}")
        bet_events_result = conn.execute(bet_events_query, (operator['id'],)).fetchall()
        print(f"🔍 DEBUG: Found {len(bet_events_result)} event_market combinations with pending bets")
        
        # If no pending bets, return empty but properly structured response
        if len(bet_events_result) == 0:
            print(f"🔍 DEBUG: No pending bets found for operator {operator['id']}, returning empty events list")
            conn.close()
            return jsonify({
                'success': True,
                'events': [],
                'pagination': {
                    'page': 1,
                    'per_page': 0,
                    'total': 0,
                    'pages': 1
                },
                'summary': {
                    'total_events': 0,
                    'active_events': 0,
                    'total_liability': 0.0,
                    'total_revenue': 0.0,
                    'max_liability': 0.0,
                    'max_possible_gain': 0.0
                },
                'filters': {
                    'sports': [],
                    'markets': []
                }
            })
        
        all_events = []
        all_sports = set()
        all_markets = set()
        
        # Process each bet combination directly from database
        for row in bet_events_result:
            match_id = str(row['match_id'])
            sport_name = str(row['sport_name'])
            market_id = str(row['market'])
            bet_count = row['bet_count']
            total_liability = float(row['total_liability'] or 0)
            total_revenue = float(row['total_revenue'] or 0)
            active_bet_count = row['active_bet_count']
            total_bet_count = row['total_bet_count']
            
            # Determine if event is active based on active bets
            is_event_active = active_bet_count > 0
            event_status = 'active' if is_event_active else 'disabled'
            
            # Apply sport filter if specified
            if sport_filter and sport_name.lower() != sport_filter.lower():
                continue
            
            # Apply market filter if specified
            if market_filter and market_id.lower() != market_filter.lower():
                continue
            
            # Apply search filter if specified
            if search_query and search_query.lower() not in match_id.lower():
                continue
            
            # Add to sports and markets filters
            all_sports.add(sport_name)
            all_markets.add(f"Market {market_id}")
            
            # Create betting event entry
            betting_event = {
                'id': f"{match_id}_{market_id}",
                'unique_id': f"{match_id}_{market_id}",
                'event_id': f"{match_id}_{market_id}",
                'sport': sport_name,
                'event_name': f"Event {match_id}",
                'market': f"Market {market_id}",
                'market_display': f"Market {market_id}",
                'category': 'Unknown Category',
                'odds_data': [],
                'is_active': is_event_active,
                'date': '',
                'time': '',
                'status': event_status,
                'total_bets': bet_count,
                'max_liability': total_liability,
                'max_possible_gain': total_revenue,
                'liability': total_liability,
                'revenue': total_revenue,
                'name': f"Event {match_id}"
            }
            
            all_events.append(betting_event)
        
        conn.close()
        
        # Calculate summary
        total_events = len(all_events)
        active_events = len([e for e in all_events if e['status'] == 'active'])
        total_liability = sum([e['liability'] for e in all_events])
        total_revenue = sum([e['revenue'] for e in all_events])
        
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
                'total_events': total_events,
                'active_events': active_events,
                'total_liability': total_liability,
                'total_revenue': total_revenue,
                'max_liability': total_liability,
                'max_possible_gain': total_revenue
            },
            'filters': {
                'sports': sorted(all_sports),
                'markets': sorted(all_markets)
            }
        })
        
    except Exception as e:
        print(f"Error in get_tenant_betting_events: {e}")
        return jsonify({'error': str(e)}), 500


    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/stats')
def get_tenant_stats(subdomain):
    """Get statistics for the tenant admin dashboard"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Get basic stats
        total_users = conn.execute("""
            SELECT COUNT(*) as count FROM users u 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ?
        """, (operator['id'],)).fetchone()['count']
        
        active_users = conn.execute("""
            SELECT COUNT(*) as count FROM users u 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ? AND u.is_active = TRUE
        """, (operator['id'],)).fetchone()['count']
        
        total_bets = conn.execute("""
            SELECT COUNT(*) as count FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ?
        """, (operator['id'],)).fetchone()['count']
        
        pending_bets = conn.execute("""
            SELECT COUNT(*) as count FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ? AND b.status = 'pending'
        """, (operator['id'],)).fetchone()['count']
        
        total_stake = conn.execute("""
            SELECT COALESCE(SUM(stake), 0) as total FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ?
        """, (operator['id'],)).fetchone()['total']
        
        total_liability = conn.execute("""
            SELECT COALESCE(SUM(potential_return), 0) as total FROM bets b 
            JOIN users u ON b.user_id = u.id 
            JOIN sportsbook_operators op ON u.sportsbook_operator_id = op.id 
            WHERE op.id = ? AND b.status = 'pending'
        """, (operator['id'],)).fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'total_users': total_users,
            'active_users': active_users,
            'total_bets': total_bets,
            'pending_bets': pending_bets,
            'total_stake': float(total_stake),
            'total_liability': float(total_liability),
            'active_events': 0  # Will be calculated separately
        })
        
    except Exception as e:
        print(f"Error getting tenant stats: {e}")
        return jsonify({'error': str(e)}), 500
        all_events = []
        all_sports = set()
        all_markets = set()
        
        print(f"🔍 DEBUG: Starting to process sports folders...")
        
        try:
            # Load sports data
            sport_folders = [f for f in os.listdir(sports_dir) if os.path.isdir(os.path.join(sports_dir, f))]
            print(f"🔍 DEBUG: Found sport folders: {sport_folders}")
            
            for sport_folder in sport_folders:
                sport_path = os.path.join(sports_dir, sport_folder)
                # Use the folder name as-is since it matches the database sport names
                sports_data[sport_folder] = {'display_name': sport_folder.title()}
                print(f"🔍 DEBUG: Processing sport folder: {sport_folder}")
                
                # Load events for this sport - files are named {sport}_odds.json
                events_file = os.path.join(sport_path, f'{sport_folder}_odds.json')
                print(f"🔍 DEBUG: Looking for events file: {events_file}")
                
                if os.path.exists(events_file):
                    print(f"🔍 DEBUG: Events file found, loading...")
                    try:
                        with open(events_file, 'r', encoding='utf-8') as f:
                            sport_data = json.load(f)
                        
                        print(f"🔍 DEBUG: JSON loaded, checking structure...")
                        print(f"🔍 DEBUG: Top level keys: {list(sport_data.keys())}")
                        
                        # Extract events from the JSON structure
                        sport_events = []
                        
                        # Handle different JSON structures for different sports
                        if 'odds_data' in sport_data and 'scores' in sport_data['odds_data']:
                            scores = sport_data['odds_data']['scores']
                            
                            # Check for categories (plural) - used by most sports
                            if 'categories' in scores:
                                print(f"🔍 DEBUG: Found odds_data.scores.categories structure")
                                for category in scores['categories']:
                                    if 'matches' in category:
                                        print(f"🔍 DEBUG: Category '{category.get('name', 'Unknown')}' has {len(category['matches'])} matches")
                                        # Add category info to each match for later use
                                        for match in category['matches']:
                                            match['_category_name'] = category.get('name', 'Unknown Category')
                                        sport_events.extend(category['matches'])
                            
                            # Check for category (singular) - used by cricket
                            elif 'category' in scores:
                                print(f"🔍 DEBUG: Found odds_data.scores.category structure (cricket)")
                                categories = scores['category']
                                if isinstance(categories, list):
                                    for category in categories:
                                        if 'matches' in category and 'match' in category['matches']:
                                            # Cricket has nested match structure
                                            match_data = category['matches']['match']
                                            if isinstance(match_data, dict):
                                                # Single match
                                                match_data['_category_name'] = category.get('name', 'Unknown Category')
                                                sport_events.append(match_data)
                                            elif isinstance(match_data, list):
                                                # Multiple matches
                                                for match in match_data:
                                                    match['_category_name'] = category.get('name', 'Unknown Category')
                                                sport_events.extend(match_data)
                                            print(f"🔍 DEBUG: Cricket category '{category.get('name', 'Unknown')}' has {len(sport_events)} matches")
                        else:
                            print(f"🔍 DEBUG: Unexpected JSON structure for {sport_folder}")
                            print(f"🔍 DEBUG: odds_data present: {'odds_data' in sport_data}")
                            if 'odds_data' in sport_data:
                                print(f"🔍 DEBUG: scores present: {'scores' in sport_data['odds_data']}")
                                if 'scores' in sport_data['odds_data']:
                                    scores = sport_data['odds_data']['scores']
                                    print(f"🔍 DEBUG: scores keys: {list(scores.keys())}")
                        
                        print(f"🔍 DEBUG: Loaded {len(sport_events)} events for {sport_folder}")
                        
                        # Process each event
                        for event in sport_events:
                            event_id = event.get('id', '')
                            # Use the folder name as-is since it matches the database sport names
                            sport_display_name = sport_folder
                            
                            # Process markets/odds
                            if 'odds' in event:
                                print(f"🔍 DEBUG: Processing odds for event {event_id}")
                                print(f"🔍 DEBUG: Odds structure: {list(event['odds'].keys())}")
                                
                                # Handle different odds structures for different sports
                                if sport_folder == 'cricket':
                                    # Cricket has odds.type[].bookmaker[].odd[] structure
                                    print(f"🔍 DEBUG: Processing cricket odds structure")
                                    if 'type' in event['odds']:
                                        for odd_type in event['odds']['type']:
                                            market_name = odd_type.get('value', '').lower()
                                            market_id = odd_type.get('id', '')
                                            
                                            if not market_id:
                                                print(f"🔍 DEBUG: No market ID found for {market_name} in cricket event {event_id}")
                                                continue
                                            
                                            # If we're only showing events with bets, check if this event_market has bets
                                            if show_only_with_bets:
                                                event_key = (str(event_id), str(sport_folder).lower(), str(market_id))
                                                if event_key not in events_to_load:
                                                    print(f"🔍 DEBUG: Skipping cricket event {event_id} market {market_id} - no bets found")
                                                    continue  # Skip this event_market combination
                                            
                                            # Extract odds values from bookmakers
                                            odds_values = []
                                            if 'bookmaker' in odd_type and odd_type['bookmaker']:
                                                for bookmaker in odd_type['bookmaker']:
                                                    if 'odd' in bookmaker:
                                                        for o in bookmaker['odd']:
                                                            value = o.get('value', '')
                                                            try:
                                                                float_val = float(value)
                                                                if float_val > 1.0:  # Valid odds
                                                                    odds_values.append(value)
                                                            except (ValueError, TypeError):
                                                                continue
                                            
                                            if not odds_values:
                                                print(f"🔍 DEBUG: No valid odds found for cricket market {market_name} in event {event_id}")
                                                continue
                                            
                                            # Process this cricket market
                                            # Create betting event entry
                                            betting_event = {
                                                'id': f"{event_id}_{market_id}",
                                                'unique_id': f"{event_id}_{market_id}",
                                                'event_id': f"{event_id}_{market_id}",
                                                'sport': sport_display_name,
                                                'event_name': f"{event.get('localteam', {}).get('name', 'Unknown')} vs {event.get('awayteam', {}).get('name', 'Unknown')}",
                                                'market': market_name,
                                                'market_display': market_name,
                                                'category': event.get('_category_name', 'Unknown Category'),
                                                'odds_data': odds_values,
                                                'is_active': True,
                                                'date': event.get('date', ''),
                                                'time': event.get('time', ''),
                                                'status': 'active' if event.get('status', 'Unknown').lower() != 'finished' else 'finished'
                                            }
                                            
                                            # Add market ID mapping for frontend
                                            betting_event['match_result'] = odds_values
                                            betting_event['match_result_market_id'] = market_id
                                            
                                            # Check if this event is disabled
                                            event_key = f"{event_id}_{market_id}"
                                            disabled_check = conn.execute(
                                                'SELECT * FROM disabled_events WHERE sport = ?', 
                                                (event_key,)
                                            ).fetchone()
                                            
                                            if disabled_check:
                                                betting_event['is_active'] = False
                                                betting_event['status'] = 'disabled'
                                            
                                            # Get bet-level information for this event_market combination
                                            if event_key in bet_info_map:
                                                bet_info = bet_info_map[event_key]
                                                betting_event['total_bets'] = bet_info['bet_count']
                                                betting_event['liability'] = round(bet_info['total_liability'], 2)
                                                betting_event['revenue'] = round(bet_info['total_revenue'], 2)
                                                betting_event['max_liability'] = round(bet_info['total_liability'], 2)
                                                betting_event['max_possible_gain'] = round(bet_info['total_revenue'], 2)
                                                print(f"🔍 DEBUG: Found bet info for {event_key}: {bet_info}")
                                            else:
                                                # Calculate financials if no bet info available
                                                max_liability, max_possible_gain = calculate_event_financials(event_id, market_id, sport_folder, operator['id'])
                                                max_liability = round(max_liability, 2)
                                                max_possible_gain = round(max_possible_gain, 2)
                                                betting_event['max_liability'] = max_liability
                                                betting_event['max_possible_gain'] = max_possible_gain
                                                betting_event['liability'] = max_liability
                                                betting_event['revenue'] = max_possible_gain
                                                betting_event['total_bets'] = 0
                                                print(f"🔍 DEBUG: No bet info found for {event_key}, calculated: liability={max_liability}, gain={max_possible_gain}")
                                            
                                            # Add fields expected by the dashboard
                                            betting_event['name'] = f"{event.get('localteam', {}).get('name', 'Unknown')} vs {event.get('awayteam', {}).get('name', 'Unknown')}"
                                            
                                            all_events.append(betting_event)
                                            print(f"🔍 DEBUG: Added event {betting_event['id']} with {betting_event['total_bets']} bets")
                                else:
                                    # Standard odds structure for other sports
                                    print(f"🔍 DEBUG: Processing standard odds structure for {sport_folder}")
                                    for odd in event['odds']:
                                        market_name = odd.get('value', '').lower()
                                        market_id = odd.get('id', '')
                                        
                                        if not market_id:
                                            print(f"🔍 DEBUG: No market ID found for {market_name} in event {event_id}")
                                            continue
                                        
                                        # If we're only showing events with bets, check if this event_market has bets
                                        if show_only_with_bets:
                                            event_key = (str(event_id), str(sport_folder).lower(), str(market_id))
                                            if event_key not in events_to_load:
                                                print(f"🔍 DEBUG: Skipping standard event {event_id} market {market_id} - no bets found")
                                                continue  # Skip this event_market combination
                                        
                                        # Extract odds values from bookmakers
                                        odds_values = []
                                        if 'bookmakers' in odd and odd['bookmakers']:
                                            bookmaker = odd['bookmakers'][0]
                                            if 'odds' in bookmaker:
                                                for o in bookmaker['odds']:
                                                    value = o.get('value', '')
                                                    try:
                                                        float_val = float(value)
                                                        if float_val > 1.0:  # Valid odds
                                                            odds_values.append(value)
                                                    except (ValueError, TypeError):
                                                        continue
                                        
                                        if not odds_values:
                                            print(f"🔍 DEBUG: No valid odds found for market {market_name} in event {event_id}")
                                            continue
                                        
                                        # Process this standard market
                                        # Create betting event entry
                                        betting_event = {
                                            'id': f"{event_id}_{market_id}",
                                            'unique_id': f"{event_id}_{market_id}",
                                            'event_id': f"{event_id}_{market_id}",
                                            'sport': sport_display_name,
                                            'event_name': f"{event.get('localteam', {}).get('name', 'Unknown')} vs {event.get('awayteam', {}).get('name', 'Unknown')}",
                                            'market': market_name,
                                            'market_display': market_name,
                                            'category': event.get('_category_name', 'Unknown Category'),
                                            'odds_data': odds_values,
                                            'is_active': True,
                                            'date': event.get('date', ''),
                                            'time': event.get('time', ''),
                                            'status': 'active' if event.get('status', 'Unknown').lower() != 'finished' else 'finished'
                                        }
                                        
                                        # Add market ID mapping for frontend
                                        # Map market names to frontend keys
                                        if market_name in ['match winner', '3way result', '1x2', 'match result'] or '3way' in market_name.lower():
                                            betting_event['match_result'] = odds_values
                                            betting_event['match_result_market_id'] = market_id
                                        elif market_name in ['home/away', 'winner']:
                                            betting_event['home_away'] = odds_values
                                            betting_event['home_away_market_id'] = market_id
                                        elif 'over/under' in market_name.lower() or 'total' in market_name.lower():
                                            betting_event['over_under'] = odds_values
                                            betting_event['over_under_market_id'] = market_id
                                        elif 'asian handicap' in market_name.lower():
                                            betting_event['asian_handicap'] = odds_values
                                            betting_event['asian_handicap_market_id'] = market_id
                                        else:
                                            # Default mapping
                                            betting_event[market_name.replace(' ', '_')] = odds_values
                                            betting_event[f"{market_name.replace(' ', '_')}_market_id"] = market_id
                                        
                                        # Check if this event is disabled
                                        event_key = f"{event_id}_{market_id}"
                                        disabled_check = conn.execute(
                                            'SELECT * FROM disabled_events WHERE sport = ?', 
                                            (event_key,)
                                        ).fetchone()
                                        
                                        if disabled_check:
                                            betting_event['is_active'] = False
                                            betting_event['status'] = 'disabled'
                                        
                                        # Get bet-level information for this event_market combination
                                        if event_key in bet_info_map:
                                            bet_info = bet_info_map[event_key]
                                            betting_event['total_bets'] = bet_info['bet_count']
                                            betting_event['liability'] = bet_info['total_liability']
                                            betting_event['revenue'] = bet_info['total_revenue']
                                            betting_event['max_liability'] = bet_info['total_liability']
                                            betting_event['max_possible_gain'] = bet_info['total_revenue']
                                            print(f"🔍 DEBUG: Found bet info for {event_key}: {bet_info}")
                                        else:
                                            # Calculate financials if no bet info available
                                            max_liability, max_possible_gain = calculate_event_financials(event_id, market_id, sport_folder, operator['id'])
                                            betting_event['max_liability'] = max_liability
                                            betting_event['max_possible_gain'] = max_possible_gain
                                            betting_event['liability'] = max_liability
                                            betting_event['revenue'] = max_possible_gain
                                            betting_event['total_bets'] = 0
                                            print(f"🔍 DEBUG: No bet info found for {event_key}, calculated: liability={max_liability}, gain={max_possible_gain}")
                                        
                                        # Add fields expected by the dashboard
                                        betting_event['name'] = f"{event.get('localteam', {}).get('name', 'Unknown')} vs {event.get('awayteam', {}).get('name', 'Unknown')}"
                                        
                                        all_events.append(betting_event)
                                        print(f"🔍 DEBUG: Added event {betting_event['id']} with {betting_event['total_bets']} bets")
                                    
                                    # Add to sports and markets filters
                                    all_sports.add(sport_display_name)
                                    all_markets.add(market_name)
                                    

                    except Exception as e:
                        print(f"🔍 DEBUG: Error loading events for {sport_folder}: {e}")
                        continue
        except Exception as e:
            print(f"🔍 DEBUG: Error processing sports directory: {e}")
            return jsonify({'error': f'Error processing sports directory: {e}'})


        
        # Apply filters after collecting all events
        filtered_events = all_events
        
        # Apply sport filter
        if sport_filter:
            filtered_events = [e for e in filtered_events if e['sport'].lower() == sport_filter.lower()]
        
        # Apply market filter
        if market_filter:
            filtered_events = [e for e in filtered_events if e['market'].lower() == market_filter.lower()]
        
        # Apply search filter
        if search_query:
            filtered_events = [e for e in filtered_events if search_query in e['event_name'].lower()]
        
        # Sort events
        reverse = sort_order.lower() == 'desc'
        if sort_by == 'event_id':
            filtered_events.sort(key=lambda x: int(x['event_id'].split('_')[0]) if x['event_id'].split('_')[0].isdigit() else 0, reverse=reverse)
        elif sort_by == 'sport':
            filtered_events.sort(key=lambda x: x['sport'], reverse=reverse)
        elif sort_by == 'event_name':
            filtered_events.sort(key=lambda x: x['event_name'], reverse=reverse)
        elif sort_by == 'market':
            filtered_events.sort(key=lambda x: x['market'], reverse=reverse)
        elif sort_by == 'max_liability':
            filtered_events.sort(key=lambda x: x.get('max_liability', 0), reverse=reverse)
        elif sort_by == 'max_possible_gain':
            filtered_events.sort(key=lambda x: x.get('max_possible_gain', 0), reverse=reverse)
        elif sort_by == 'status':
            filtered_events.sort(key=lambda x: x.get('is_active', True), reverse=reverse)
        
        # Apply pagination
        total_events = len(filtered_events)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_events = filtered_events[start_idx:end_idx]
        
        # Get unique sports and markets for filters (from all events, not filtered)
        unique_sports = list(all_sports)
        unique_markets = list(all_markets)
        
        # Calculate summary statistics (from filtered events)
        active_events = len([e for e in filtered_events if e.get('is_active', True)])
        total_liability = round(sum(e.get('max_liability', 0) for e in filtered_events), 2)
        total_revenue = round(calculate_total_revenue(operator['id']), 2)  # Calculate from settled bets for this operator
        
        # Debug logging
        print(f"🔍 DEBUG: Total events loaded: {len(all_events)}")
        print(f"🔍 DEBUG: Events after filtering: {len(filtered_events)}")
        print(f"🔍 DEBUG: Active events: {active_events}")
        print(f"🔍 DEBUG: Total liability: {total_liability}")
        print(f"🔍 DEBUG: Total revenue: {total_revenue}")
        
        conn.close()
        
        return jsonify({
            'events': paginated_events,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_events,
                'pages': (total_events + per_page - 1) // per_page
            },
            'summary': {
                'total_events': len(all_events),  # Show total available events, not filtered count
                'active_events': len([e for e in all_events if e.get('is_active', True)]),  # Count from all events
                'total_liability': total_liability,
                'total_revenue': total_revenue,
                'max_liability': total_liability,
                'max_possible_gain': total_revenue
            },
            'filters': {
                'sports': sorted(unique_sports),
                'markets': sorted(unique_markets)
            }
        })
        
    except Exception as e:
        print(f"Error in get_tenant_betting_events: {e}")
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/admin-check')
def admin_check(subdomain):
    """Check if admin is logged in and return operator info"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({
            'success': True,
            'logged_in': False,
            'operator': None
        })
    
    return jsonify({
        'success': True,
        'logged_in': True,
        'operator': {
            'id': operator['id'],
            'sportsbook_name': operator['sportsbook_name'],
            'subdomain': operator['subdomain'],
            'email': operator['email']
        }
    })

@rich_admin_bp.route('/<subdomain>/admin/api/users')
def get_tenant_users(subdomain):
    """Get users filtered by tenant"""
    print(f"🔍 DEBUG: get_tenant_users called for subdomain: {subdomain}")
    
    operator = get_operator_from_session()
    print(f"🔍 DEBUG: Operator from session: {operator}")
    
    if not operator:
        print("❌ DEBUG: No operator found in session")
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        print(f"🔍 DEBUG: Looking for users with sportsbook_operator_id = {operator['id']}")
        
        # Get users for this operator only
        users_query = """
        SELECT id, username, email, balance, created_at, is_active,
               (SELECT COUNT(*) FROM bets WHERE user_id = users.id) as total_bets,
               (SELECT COALESCE(SUM(stake), 0) FROM bets WHERE user_id = users.id AND status IN ('won', 'lost', 'void')) as total_staked,
               (SELECT COALESCE(SUM(actual_return), 0) FROM bets WHERE user_id = users.id AND status = 'won') as total_payout,
               (SELECT COALESCE(SUM(CASE WHEN status = 'won' THEN actual_return ELSE 0 END), 0) - 
                       COALESCE(SUM(CASE WHEN status IN ('won', 'lost', 'void') THEN stake ELSE 0 END), 0) FROM bets WHERE user_id = users.id) as profit
        FROM users 
        WHERE sportsbook_operator_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """
        
        users = conn.execute(users_query, (operator['id'], per_page, offset)).fetchall()
        print(f"🔍 DEBUG: Found {len(users)} users for operator {operator['id']}")
        
        # Get total count
        total_count = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE sportsbook_operator_id = ?", 
            (operator['id'],)
        ).fetchone()['count']
        
        print(f"🔍 DEBUG: Total user count: {total_count}")
        
        conn.close()
        
        # Round financial values to 2 decimal places
        processed_users = []
        for user in users:
            user_dict = dict(user)
            user_dict['balance'] = round(float(user_dict['balance'] or 0), 2)
            user_dict['total_staked'] = round(float(user_dict['total_staked'] or 0), 2)
            user_dict['total_payout'] = round(float(user_dict['total_payout'] or 0), 2)
            user_dict['profit'] = round(float(user_dict['profit'] or 0), 2)
            processed_users.append(user_dict)
        
        return jsonify({
            'users': processed_users,
            'total': total_count,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        print(f"❌ DEBUG: Error in get_tenant_users: {e}")
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/casino-users')
def get_casino_users(subdomain):
    """Get casino users filtered by tenant"""
    print(f"🔍 DEBUG: get_casino_users called for subdomain: {subdomain}")
    
    operator = get_operator_from_session()
    print(f"🔍 DEBUG: Operator from session: {operator}")
    
    if not operator:
        print("❌ DEBUG: No operator found in session")
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        print(f"🔍 DEBUG: Looking for casino users with sportsbook_operator_id = {operator['id']}")
        
        # Get users for this operator only with casino-specific stats
        users_query = """
        SELECT id, username, email, balance, created_at, is_active,
               (SELECT COUNT(*) FROM game_round WHERE user_id = users.id::text) as total_games,
               (SELECT COALESCE(SUM(stake), 0) FROM game_round WHERE user_id = users.id::text) as total_staked,
               (SELECT COALESCE(SUM(payout), 0) FROM game_round WHERE user_id = users.id::text) as total_payout,
               (SELECT COALESCE(SUM(payout - stake), 0) FROM game_round WHERE user_id = users.id::text) as profit
        FROM users 
        WHERE sportsbook_operator_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """
        
        users = conn.execute(users_query, (operator['id'], per_page, offset)).fetchall()
        print(f"🔍 DEBUG: Found {len(users)} casino users for operator {operator['id']}")
        
        # Get total count
        total_count = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE sportsbook_operator_id = ?",
            (operator['id'],)
        ).fetchone()['count']
        
        conn.close()
        
        # Round financial values to 2 decimal places
        processed_users = []
        for user in users:
            user_dict = dict(user)
            user_dict['balance'] = round(float(user_dict['balance'] or 0), 2)
            user_dict['total_staked'] = round(float(user_dict['total_staked'] or 0), 2)
            user_dict['total_payout'] = round(float(user_dict['total_payout'] or 0), 2)
            user_dict['profit'] = round(float(user_dict['profit'] or 0), 2)
            processed_users.append(user_dict)
        
        return jsonify({
            'users': processed_users,
            'total': total_count,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        print(f"❌ DEBUG: Error in get_casino_users: {e}")
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/user/<int:user_id>/toggle', methods=['POST'])
def toggle_user_status(subdomain, user_id):
    """Toggle user active status (tenant-filtered) - Affects both sportsbook and casino"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Verify user belongs to this operator
        user = conn.execute(
            "SELECT id, is_active FROM users WHERE id = ? AND sportsbook_operator_id = ?",
            (user_id, operator['id'])
        ).fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Toggle status
        new_status = not user['is_active']
        conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (new_status, user_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"User {'enabled' if new_status else 'disabled'} successfully (affects both sportsbook and casino)",
            'new_status': new_status
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/users/reset', methods=['POST'])
def reset_all_users(subdomain):
    """Reset all users for a tenant: cancel pending bets and reset balances"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        new_balance = float(data.get('new_balance', 0))
        
        if new_balance < 0:
            return jsonify({'error': 'Balance amount must be 0 or greater'}), 400
        
        conn = get_db_connection()
        
        # First, get all pending bets to cancel them
        pending_bets = conn.execute(
            "SELECT b.id, b.user_id, b.stake, b.match_name FROM bets b WHERE b.user_id IN (SELECT id FROM users WHERE sportsbook_operator_id = ?) AND b.status = 'pending'",
            (operator['id'],)
        ).fetchall()
        
        bets_cancelled = len(pending_bets)
        
        if pending_bets:
            # Update all pending bets to voided status and refund stakes
            for bet in pending_bets:
                # Update bet status to voided (cancelled)
                conn.execute(
                    "UPDATE bets SET status = 'voided', settled_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (bet['id'],)
                )
                
                # Create refund transaction for this bet
                conn.execute(
                    "INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at) VALUES (?, ?, ?, 'refund', ?, ?, ?, CURRENT_TIMESTAMP)",
                    (bet['user_id'], bet['id'], bet['stake'], f'Bet cancelled - {bet["match_name"]} (Admin Reset)', bet['stake'], bet['stake'] * 2)
                )
        
        # Reset all user balances for this operator
        users_reset = conn.execute(
            "UPDATE users SET balance = ? WHERE sportsbook_operator_id = ?",
            (new_balance, operator['id'])
        ).rowcount
        
        # Store the reset amount in operator settings for future new users
        try:
            # Get current operator settings
            operator_row = conn.execute(
                "SELECT settings FROM sportsbook_operators WHERE id = ?",
                (operator['id'],)
            ).fetchone()
            
            # Parse existing settings or create new ones
            if operator_row and operator_row['settings']:
                import json
                settings = json.loads(operator_row['settings'])
            else:
                settings = {}
            
            # Update the default user balance setting
            settings['default_user_balance'] = new_balance
            
            # Save updated settings back to database
            conn.execute(
                "UPDATE sportsbook_operators SET settings = ? WHERE id = ?",
                (json.dumps(settings), operator['id'])
            )
            
            print(f"💾 Updated operator {operator['id']} settings: default_user_balance = {new_balance}")
            
        except Exception as settings_error:
            print(f"⚠️ Warning: Could not update operator settings: {settings_error}")
        
        # Clear session cache for all affected users to force fresh data fetch
        try:
            from flask import session
            # Force session to refresh user data on next request
            if 'user_data' in session:
                del session['user_data']
                print(f"🗑️ Cleared session cache for current admin user")
        except Exception as cache_error:
            print(f"⚠️ Warning: Could not clear session cache: {cache_error}")
        
        # Also trigger WebSocket balance updates for all affected users
        try:
            from src.websocket_service import broadcast_balance_update
            if 'broadcast_balance_update' in globals():
                # Get all user IDs for this operator
                user_ids = [row['id'] for row in conn.execute(
                    "SELECT id FROM users WHERE sportsbook_operator_id = ?", 
                    (operator['id'],)
                ).fetchall()]
                
                # Broadcast balance update to all affected users
                for user_id in user_ids:
                    broadcast_balance_update(user_id, new_balance)
                print(f"📡 WebSocket balance updates sent to {len(user_ids)} users")
        except Exception as ws_error:
            print(f"⚠️ Warning: Could not send WebSocket updates: {ws_error}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Reset completed for operator {operator['id']}: {bets_cancelled} bets cancelled, {users_reset} users reset")
        
        return jsonify({
            'success': True,
            'message': f'Successfully reset {users_reset} users and cancelled {bets_cancelled} pending bets',
            'bets_cancelled': bets_cancelled,
            'users_reset': users_reset,
            'new_balance': new_balance
        })
        
    except Exception as e:
        print(f"❌ Error resetting users: {e}")
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/betting-events/<event_key>/toggle', methods=['POST'])
def toggle_event_status(subdomain, event_key):
    """Toggle event active status (tenant-filtered) - using bets.is_active approach"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json() or {}
        new_status = data.get('status')
        
        # If no status provided, determine current status and toggle
        if not new_status:
            conn = get_db_connection()
            # Check current status by looking at active bets
            active_bets = conn.execute("""
                SELECT COUNT(*) as active_count
                FROM bets b
                JOIN users u ON b.user_id = u.id
                WHERE u.sportsbook_operator_id = ? 
                AND b.match_id = ? AND b.market = ? 
                AND b.is_active = TRUE AND b.status = 'pending'
            """, (operator['id'], event_key.split('_')[0], event_key.split('_')[1] if '_' in event_key else '')).fetchone()
            
            new_status = 'disabled' if active_bets['active_count'] > 0 else 'active'
            conn.close()
        
        conn = get_db_connection()
        
        # Extract match_id and market from event_key format "6200217_2"
        if '_' in event_key:
            base_event_id, market = event_key.split('_', 1)
        else:
            base_event_id = event_key
            market = None
        
        # Update bets.is_active for this operator's bets
        if new_status == 'disabled':
            # Mark all bets for this event/market combination as inactive
            if market:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = FALSE 
                    WHERE match_id = ? AND market = ?
                    AND user_id IN (
                        SELECT id FROM users 
                        WHERE sportsbook_operator_id = ?
                    )
                """, (base_event_id, market, operator['id']))
            else:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = FALSE 
                    WHERE match_id = ?
                    AND user_id IN (
                        SELECT id FROM users 
                        WHERE sportsbook_operator_id = ?
                    )
                """, (base_event_id, operator['id']))
        else:
            # Mark all bets for this event/market combination as active
            if market:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = TRUE 
                    WHERE match_id = ? AND market = ?
                    AND user_id IN (
                        SELECT id FROM users 
                        WHERE sportsbook_operator_id = ?
                    )
                """, (base_event_id, market, operator['id']))
            else:
                bets_result = conn.execute("""
                    UPDATE bets 
                    SET is_active = TRUE 
                    WHERE match_id = ?
                    AND user_id IN (
                        SELECT id FROM users 
                        WHERE sportsbook_operator_id = ?
                    )
                """, (base_event_id, operator['id']))
        
        conn.commit()
        conn.close()
        
        # Return success - the operation completed regardless of rowcount
        return jsonify({'success': True, 'message': f'Event status updated to {new_status}'})
                
    except Exception as e:
        print(f"Error toggling event status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/reports/overview')
@require_admin_auth
def get_reports_overview(subdomain):
    """Get comprehensive reports overview (tenant-filtered)"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Total bets and revenue for this operator's users
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
        WHERE u.sportsbook_operator_id = ?
        """
        
        totals = conn.execute(total_query, (operator['id'],)).fetchone()
        
        # Daily revenue for the last 30 days
        daily_query = """
        SELECT 
            DATE(b.created_at) as bet_date,
            COUNT(*) as daily_bets,
            SUM(b.stake) as daily_stakes,
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as daily_revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE u.sportsbook_operator_id = ? AND b.created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(b.created_at)
        ORDER BY bet_date DESC
        """
        
        daily_data = conn.execute(daily_query, (operator['id'],)).fetchall()
        
        # Sport-wise performance
        sport_query = """
        SELECT 
            b.sport_name,
            COUNT(*) as bets_count,
            SUM(b.stake) as total_stakes,
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as sport_revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE u.sportsbook_operator_id = ?
        GROUP BY b.sport_name
        ORDER BY sport_revenue DESC
        """
        
        sport_data = conn.execute(sport_query, (operator['id'],)).fetchall()
        
        conn.close()
        
        # Calculate metrics
        total_stakes = round(float(totals['total_stakes'] or 0), 2)
        total_revenue_from_losses = round(float(totals['total_revenue_from_losses'] or 0), 2)
        total_payouts = round(float(totals['total_payouts'] or 0), 2)
        total_revenue = round(total_revenue_from_losses - total_payouts, 2)
        win_rate = round((totals['won_bets'] / max(totals['total_bets'], 1)) * 100, 2)
        
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

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/reports/generate', methods=['POST'])
@require_admin_auth
def generate_custom_report(subdomain):
    """Generate custom reports based on parameters (tenant-filtered)"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        report_type = data.get('report_type', 'revenue')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        sport_filter = data.get('sport_filter')
        group_by = data.get('group_by', 'day')
        
        conn = get_db_connection()
        
        # Build base query with tenant filtering
        base_where = "u.sportsbook_operator_id = ?"
        params = [operator['id']]
        
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
            # Combined sportsbook and casino revenue analysis
            query = f"""
            WITH sportsbook_revenue AS (
                SELECT 
                    b.created_at::date as report_date,
                    b.sport_name as category,
                    'Sportsbook' as platform,
                    COUNT(*) as total_bets,
                    SUM(b.stake) as total_stakes,
                    SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
                    SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as revenue
                FROM bets b
                JOIN users u ON b.user_id = u.id
                WHERE {base_where}
                GROUP BY b.created_at::date, b.sport_name
            ),
            casino_revenue AS (
                SELECT 
                    gr.created_at::date as report_date,
                    gr.game_key as category,
                    'Casino' as platform,
                    COUNT(*) as total_bets,
                    SUM(gr.stake) as total_stakes,
                    SUM(gr.stake) - SUM(gr.payout) as revenue
                FROM game_round gr
                JOIN users u ON gr.user_id = u.id::text
                WHERE u.sportsbook_operator_id = ?
                {f"AND gr.created_at::date >= '{date_from}'" if date_from else ""}
                {f"AND gr.created_at::date <= '{date_to}'" if date_to else ""}
                GROUP BY gr.created_at::date, gr.game_key
            )
            SELECT * FROM sportsbook_revenue
            UNION ALL
            SELECT * FROM casino_revenue
            ORDER BY report_date DESC, revenue DESC
            """
            params = [operator['id']]  # Reset params for combined query
            
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
            WHERE u.sportsbook_operator_id = ?
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY total_bets DESC
            """
            params = [operator['id']]  # Reset params for user query
            
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
            WHERE {base_where}
            GROUP BY b.sport_name
            ORDER BY sport_revenue DESC
            """
            
        elif report_type == 'casino-performance':
            query = f"""
            SELECT 
                gr.game_key as game_name,
                COUNT(*) as total_games,
                SUM(gr.stake) as total_stakes,
                COUNT(CASE WHEN gr.payout > gr.stake THEN 1 END) as won_games,
                COUNT(CASE WHEN gr.payout <= gr.stake THEN 1 END) as lost_games,
                SUM(gr.stake) - SUM(gr.payout) as casino_revenue,
                (COUNT(CASE WHEN gr.payout > gr.stake THEN 1 END) * 100.0 / COUNT(*)) as win_rate
            FROM game_round gr
            JOIN users u ON gr.user_id = u.id::text
            WHERE u.sportsbook_operator_id = ?
            {f"AND gr.created_at::date >= '{date_from}'" if date_from else ""}
            {f"AND gr.created_at::date <= '{date_to}'" if date_to else ""}
            GROUP BY gr.game_key
            ORDER BY casino_revenue DESC
            """
            params = [operator['id']]  # Reset params for casino query
        
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Execute query
        try:
            result = conn.execute(query, params).fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            report_data = [dict(row) for row in result]
            
            return jsonify(report_data)
        except Exception as query_error:
            conn.close()
            print(f"Database query error: {query_error}")
            return jsonify({'error': f'Database query failed: {str(query_error)}'}), 500
        
    except Exception as e:
        print(f"Error generating custom report: {e}")
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/reports/available-sports')
@require_admin_auth
def get_available_sports_for_reports(subdomain):
    """Get available sports for report filtering (tenant-filtered)"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Get sports that have bets from this operator's users
        sports_query = """
        SELECT DISTINCT b.sport_name
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE u.sportsbook_operator_id = ?
        ORDER BY b.sport_name
        """
        
        sports_result = conn.execute(sports_query, (operator['id'],)).fetchall()
        conn.close()
        
        sports = [row['sport_name'] for row in sports_result]
        
        return jsonify({'sports': sports})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/casino-setting')
@require_admin_auth
def get_casino_setting(subdomain):
    """Get casino enabled setting for specific operator"""
    try:
        operator = get_operator_from_session()
        if not operator:
            return jsonify({'error': 'Unauthorized'}), 401
        
        conn = get_db_connection()
        
        # Get casino setting for this operator
        casino_setting = conn.execute("""
            SELECT casino_enabled FROM sportsbook_operators 
            WHERE id = ?
        """, (operator['id'],)).fetchone()
        
        conn.close()
        
        if casino_setting:
            return jsonify({
                'success': True,
                'casino_enabled': casino_setting['casino_enabled']
            })
        else:
            return jsonify({'error': 'Operator not found'}), 404
        
    except Exception as e:
        return jsonify({'error': 'Failed to get casino setting'}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/toggle-casino', methods=['POST'])
@require_admin_auth
def toggle_casino_setting(subdomain):
    """Toggle casino enabled setting for specific operator"""
    try:
        operator = get_operator_from_session()
        if not operator:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        casino_enabled = data.get('casino_enabled', True)
        
        conn = get_db_connection()
        
        # Update casino setting for this operator
        conn.execute("""
            UPDATE sportsbook_operators 
            SET casino_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (casino_enabled, operator['id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Casino {'enabled' if casino_enabled else 'disabled'} successfully",
            'casino_enabled': casino_enabled
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to toggle casino setting'}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/referral-code')
@require_admin_auth
def get_referral_code(subdomain):
    """Get the referral code for the current operator"""
    try:
        operator = get_operator_from_session()
        if not operator:
            print(f"❌ DEBUG: No operator found in session for subdomain {subdomain}")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        print(f"🔍 DEBUG: Getting referral code for operator ID: {operator['id']}")
        
        # Get referral code from referral_table
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT referral_generated FROM referral_table 
            WHERE operator_id = ?
        """, (operator['id'],))
        
        result = cursor.fetchone()
        conn.close()
        
        print(f"🔍 DEBUG: Referral code query result: {result}")
        
        if result:
            return jsonify({
                'success': True,
                'referral_code': result[0]
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Referral code not found'
            })
        
    except Exception as e:
        print(f"❌ DEBUG: Error getting referral code: {e}")
        return jsonify({'success': False, 'error': 'Failed to get referral code'}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/change-password', methods=['POST'])
@require_admin_auth
def change_admin_password(subdomain):
    """Change admin password"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'Current password and new password are required'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 6 characters long'
            }), 400
        
        conn = get_db_connection()
        
        # Get current operator with password hash
        operator_data = conn.execute("""
            SELECT id, login, password_hash 
            FROM sportsbook_operators 
            WHERE id = ?
        """, (operator['id'],)).fetchone()
        
        if not operator_data:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404
        
        # Verify current password
        if not check_password_hash(operator_data['password_hash'], current_password):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 400
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        conn.execute("""
            UPDATE sportsbook_operators 
            SET password_hash = ?, updated_at = ? 
            WHERE id = ?
        """, (new_password_hash, datetime.utcnow(), operator['id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        print(f"Error changing admin password: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/reports/export', methods=['POST'])
@require_admin_auth
def export_custom_report(subdomain):
    """Export custom report to CSV (tenant-filtered)"""
    operator = get_operator_from_session()
    if not operator:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        report_type = data.get('report_type', 'revenue')
        format_type = data.get('format', 'csv')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        sport_filter = data.get('sport_filter')
        
        print(f"DEBUG: Export request - type: {report_type}, format: {format_type}, from: {date_from}, to: {date_to}, sport: {sport_filter}")
        
        # For now, just return a simple CSV response
        # In a production system, you might want to use a proper CSV library
        conn = get_db_connection()
        
        # Build base query (similar to generate endpoint)
        base_where = "u.sportsbook_operator_id = ?"
        params = [operator['id']]
        
        if date_from:
            base_where += " AND DATE(b.created_at) >= ?"
            params.append(date_from)
        if date_to:
            base_where += " AND DATE(b.created_at) <= ?"
            params.append(date_to)
        if sport_filter:
            base_where += " AND b.sport_name = ?"
            params.append(sport_filter)
        
        # Generate CSV data
        if report_type == 'revenue':
            query = f"""
            SELECT 
                DATE(b.created_at) as bet_date,
                b.sport_name,
                COUNT(*) as total_bets,
                SUM(b.stake) as total_stakes,
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) - 
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as revenue
            FROM bets b
            JOIN users u ON b.user_id = u.id
            WHERE {base_where}
            GROUP BY DATE(b.created_at), b.sport_name
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
            WHERE u.sportsbook_operator_id = ?
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY total_bets DESC
            """
            headers = ['Username', 'Email', 'Total Bets', 'Total Staked', 'Payout', 'Profit', 'Join Date']
            params = [operator['id']]
        
        else:
            return jsonify({'error': 'Export not supported for this report type'}), 400
        
        # Execute query
        try:
            result = conn.execute(query, params).fetchall()
            print(f"DEBUG: Query executed successfully, got {len(result)} rows")
        except Exception as query_error:
            print(f"DEBUG: Query execution error: {query_error}")
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
        response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report.csv'
        return response
        
    except Exception as e:
        print(f"Error exporting report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/session-test')
def session_test(subdomain):
    """Test endpoint to debug session issues"""
    print(f"🔍 DEBUG: Session test called for subdomain: {subdomain}")
    print(f"🔍 DEBUG: Full session data: {dict(session)}")
    print(f"🔍 DEBUG: admin_id: {session.get('admin_operator_id')}")
    print(f"🔍 DEBUG: admin_subdomain: {session.get('admin_subdomain')}")
    print(f"🔍 DEBUG: admin_username: {session.get('admin_username')}")
    
    return jsonify({
        'session_data': dict(session),
        'admin_operator_id': session.get('admin_operator_id'),
        'admin_subdomain': session.get('admin_subdomain'),
        'admin_username': session.get('admin_username')
    })

@rich_admin_bp.route('/<subdomain>/admin/api/manual-settlement')
def get_manual_settlement_data(subdomain):
    """Get pending bets grouped by match for manual settlement"""
    try:
        # Check admin authentication
        if not session.get('admin_operator_id') or session.get('admin_subdomain') != subdomain:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        # Get operator ID from session
        operator_id = session.get('admin_operator_id')
        
        conn = get_db_connection()
        
        # Get all pending bets for this operator
        query = """
        SELECT b.*, u.username
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.status = 'pending' AND u.sportsbook_operator_id = ?
        ORDER BY b.created_at DESC
        """
        
        pending_bets = conn.execute(query, (operator_id,)).fetchall()
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
        print(f"Error getting manual settlement data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get settlement data'
        }), 500

    finally:

        if conn:

            conn.close()

@rich_admin_bp.route('/<subdomain>/admin/api/manual-settle', methods=['POST'])
def manual_settle_bets(subdomain):
    """Manually settle bets for a specific match and market"""
    try:
        # Check admin authentication
        if not session.get('admin_operator_id') or session.get('admin_subdomain') != subdomain:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        # Get operator ID from session
        operator_id = session.get('admin_operator_id')
        
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
        
        # Get all pending bets for this match and market from this operator
        query = """
        SELECT b.*, u.username
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.match_id = ? AND b.market = ? AND b.status = 'pending'
        AND u.sportsbook_operator_id = ?
        """
        
        pending_bets = conn.execute(query, (match_id, market, operator_id)).fetchall()
        
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
            # Determine if bet is a winner
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
        
        # Update operator's total_revenue after settlement
        update_operator_revenue(operator_id, conn)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Settled {settled_count} bets',
            'settled_count': settled_count,
            'won_count': won_count,
            'lost_count': lost_count,
            'total_payout': total_payout
        })
        
    except Exception as e:
        print(f"Error manually settling bets: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to settle bets'
        }), 500

# Rich Admin Template (extracted from original admin_app.py)
    finally:

        if conn:

            conn.close()

RICH_ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ operator.sportsbook_name }} - Admin Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            position: relative;
        }
        
        .referral-code-section {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(255, 255, 255, 0.1);
            padding: 0.5rem 1rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .referral-label {
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .referral-code {
            font-family: 'Courier New', monospace;
            font-weight: bold;
            font-size: 0.9rem;
            color: #fff;
            background: rgba(0, 0, 0, 0.2);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            cursor: pointer;
            user-select: all;
            transition: background 0.2s ease;
        }
        
        .referral-code:hover {
            background: rgba(0, 0, 0, 0.3);
        }
        
        .copy-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #fff;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: background 0.2s ease;
        }
        
        .copy-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .settings-btn {
            background: none;
            border: none;
            font-size: 1.2rem;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 50%;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2.5rem;
            height: 2.5rem;
        }
        
        .settings-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: rotate(90deg);
        }
        
        .settings-dropdown {
            position: fixed;
            top: 80px;
            right: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            padding: 1rem;
            min-width: 280px;
            z-index: 1000;
            display: none;
            border: 1px solid #e9ecef;
        }
        
        .settings-dropdown.show {
            display: block;
        }
        
        .settings-dropdown h3 {
            margin: 0 0 1rem 0;
            color: #2c3e50;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .settings-dropdown .form-group {
            margin-bottom: 1rem;
        }
        
        .settings-dropdown .form-group label {
            display: block;
            margin-bottom: 0.25rem;
            font-weight: 600;
            color: #495057;
            font-size: 0.85rem;
        }
        
        .settings-dropdown .form-group input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        
        .settings-dropdown .form-group input:focus {
            outline: none;
            border-color: #4CAF50;
            box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
        }
        
        .settings-dropdown .form-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .settings-dropdown .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            flex: 1;
        }
        
        .settings-dropdown .btn-primary {
            background: #4CAF50;
            color: white;
        }
        
        .settings-dropdown .btn-primary:hover {
            background: #45a049;
        }
        
        .settings-dropdown .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .settings-dropdown .btn-secondary:hover {
            background: #5a6268;
        }
        
        .settings-dropdown .message {
            padding: 0.75rem;
            border-radius: 4px;
            margin-top: 0.75rem;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .settings-dropdown .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .settings-dropdown .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        /* Responsive adjustments for settings dropdown */
        @media (max-width: 768px) {
            .settings-dropdown {
                top: 70px;
                right: 10px;
                left: 10px;
                min-width: auto;
                width: auto;
            }
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
            background: #4CAF50;
            color: white;
        }
        
        .nav-tab:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        /* Hide Reports tab */
        .nav-tab[onclick*="reports"] {
            display: none;
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
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }
        
        .summary-card h3 {
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
            opacity: 0.9;
        }
        
        .summary-card .value {
            font-size: 1.8rem;
            font-weight: bold;
        }
        
        /* Casino Control Styles */
        .casino-control-section {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            border-left: 4px solid #667eea;
        }
        
        .casino-control-section h3 {
            margin-bottom: 1rem;
            color: #333;
            font-size: 1.2rem;
        }
        
        .casino-control-row {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.5rem;
        }
        
        .casino-label {
            font-weight: 600;
            color: #555;
        }
        
        .casino-toggle-container {
            position: relative;
            display: inline-block;
        }
        
        .casino-toggle-input {
            display: none;
        }
        
        .casino-slider {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 30px;
            background: #dc3545; /* Red by default (disabled state) */
            border-radius: 30px;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        
        .casino-slider:before {
            content: '';
            position: absolute;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: white;
            top: 2px;
            left: 2px;
            transition: transform 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .casino-toggle-input:checked + .casino-slider {
            background: #28a745; /* Green when enabled */
        }
        
        .casino-toggle-input:not(:checked) + .casino-slider {
            background: #dc3545; /* Red when disabled */
        }
        
        .casino-toggle-input:checked + .casino-slider:before {
            transform: translateX(30px);
        }
        
        .casino-slider-button {
            display: none;
        }
        
        .casino-status {
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }
        
        .casino-status.enabled {
            color: #28a745;
        }
        
        .casino-status.disabled {
            color: #dc3545;
        }
        
        .casino-description {
            margin-top: 0.5rem;
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 0;
        }
        
        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .controls select, .controls input, .controls button {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9rem;
        }
        
        .controls button {
            background: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: 600;
        }
        
        .controls button:hover {
            background: #45a049;
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
        
        /* Report Builder Styles */
        .report-builder-form {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            border: 1px solid #e9ecef;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        
        .form-group label {
            font-weight: 600;
            color: #495057;
            font-size: 0.9rem;
        }
        
        .form-group select,
        .form-group input {
            padding: 0.75rem;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 0.9rem;
            background: white;
            transition: border-color 0.2s ease;
        }
        
        .form-group select:focus,
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .date-inputs {
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        
        .date-inputs input {
            flex: 1;
        }
        
        .generate-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
            margin-top: 1rem;
        }
        
        .generate-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        .form-section {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid #e9ecef;
        }
        
        .form-section h3 {
            color: #495057;
            margin-bottom: 1.5rem;
            font-size: 1.2rem;
            border-bottom: 2px solid #667eea;
            padding-bottom: 0.75rem;
        }
        
        .form-section h2 {
            color: #2c3e50;
            margin-bottom: 2rem;
            font-size: 1.8rem;
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .form-help-text {
            font-size: 0.85rem;
            color: #6c757d;
            margin-top: 0.25rem;
            font-style: italic;
        }
        
        .form-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, #dee2e6, transparent);
            margin: 2rem 0;
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
            border-color: #667eea;
        }
        
        .pagination button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination button.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
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
        
    </style>
</head>
<body>
    <div class="header">
        <h1>🏆 {{ operator.sportsbook_name }} - Admin Dashboard</h1>
        <div class="admin-info">
            <div class="referral-code-section">
                <span class="referral-label">Referral Code:</span>
                <span id="referralCodeDisplay" class="referral-code" onclick="copyReferralCode()" title="Click to copy">Loading...</span>
                <button class="copy-btn" onclick="copyReferralCode()" title="Copy referral code">📋</button>
            </div>
            <span>Welcome, {{ operator.login }}</span>
            <button class="settings-btn" onclick="toggleSettingsDropdown()" title="Settings">⚙️</button>
            <a href="/{{ operator.subdomain }}/admin/logout" class="logout-btn">Logout</a>
        </div>
        
        <!-- Settings Dropdown -->
        <div id="settings-dropdown" class="settings-dropdown">
            <h3>🔐 Change Password</h3>
            
            <form id="password-change-form" class="settings-form">
                <div class="form-group">
                    <label for="current-password">Current Password:</label>
                    <input type="password" id="current-password" name="current_password" required>
                </div>
                
                <div class="form-group">
                    <label for="new-password">New Password:</label>
                    <input type="password" id="new-password" name="new_password" required minlength="6">
                </div>
                
                <div class="form-group">
                    <label for="confirm-password">Confirm New Password:</label>
                    <input type="password" id="confirm-password" name="confirm_password" required>
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">Change Password</button>
                    <button type="button" class="btn btn-secondary" onclick="clearPasswordForm()">Clear</button>
                </div>
            </form>
            
            <div id="password-change-message" class="message" style="display: none;"></div>
        </div>
    </div>
    
    <div class="container">
                    <div class="nav-tabs">
                <button class="nav-tab active" onclick="showSection('betting-events')">📊 Events</button>

                <button class="nav-tab" onclick="showSection('user-management')">👥 User Management</button>
                <button class="nav-tab" onclick="showSection('report-builder')">🔧 Report Builder</button>
                <button class="nav-tab" onclick="openThemeCustomizer()">🎨 Theme Customizer</button>
            </div>
        
        <!-- Trading Events Section -->
        <div id="trading-events" class="content-section active">
            <h2>Trading Events Management</h2>
            <div class="summary-cards">
                <div class="summary-card">
                    <h3>Total Events</h3>
                    <div class="value" id="total-events">0</div>
                </div>
                <div class="summary-card">
                    <h3>Active Events</h3>
                    <div class="value" id="active-events">0</div>
                </div>
                <div class="summary-card">
                    <h3>Total Liability</h3>
                    <div class="value" id="total-liability">$0.00</div>
                </div>
            </div>
            
            <!-- Casino Control Section -->
            <div class="casino-control-section">
                <h3>🎰 Casino Settings</h3>
                <div class="casino-control-row">
                    <label for="casinoToggle" class="casino-label">Enable Casino for Users:</label>
                    <div class="casino-toggle-container">
                        <input type="checkbox" id="casinoToggle" class="casino-toggle-input" onchange="toggleCasino()">
                        <label for="casinoToggle" class="casino-slider">
                            <span class="casino-slider-button"></span>
                        </label>
                    </div>
                    <span id="casinoStatus" class="casino-status enabled">Enabled</span>
                </div>
                <p class="casino-description">
                    When disabled, users under this operator will not see the casino button on the sports betting page.
                </p>
            </div>
            
            <div class="controls">
                <select id="sport-filter">
                    <option value="">All Sports</option>
                </select>
                <select id="market-filter">
                    <option value="">All Markets</option>
                </select>
                <input type="text" id="search-events" placeholder="Search events...">
                <button onclick="loadBettingEvents()">🔄 Refresh Events</button>
            </div>
            
            <div class="table-container">
                <table id="events-table">
                    <thead>
                        <tr>
                            <th onclick="sortTable('events-table', 0)" style="cursor: pointer;">
                                Event ID <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 1)" style="cursor: pointer;">
                                Sport <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 2)" style="cursor: pointer;">
                                Event Name <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 3)" style="cursor: pointer;">
                                Market <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 4)" style="cursor: pointer;">
                                Total Bets <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 5)" style="cursor: pointer;">
                                Liability <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 6)" style="cursor: pointer;">
                                Status <span class="sort-icon">↕</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody id="events-tbody">
                        <tr><td colspan="7" class="loading">Loading events...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        

        
        <!-- User Management Section -->
        <div id="user-management" class="content-section">
            <h2>User Management</h2>
            <p>Manage users across your sportsbook and casino operations</p>
            
            <!-- Sub-tabs for Sportsbook and Casino -->
            <div class="sub-tabs" style="margin-bottom: 1.5rem; border-bottom: 2px solid #e2e8f0;">
                <button class="sub-tab active" onclick="switchUserTab('sportsbook')" id="sportsbook-tab" style="padding: 0.75rem 1.5rem; background: transparent; border: none; border-bottom: 3px solid #4ade80; color: #1e293b; font-weight: 600; cursor: pointer; margin-right: 1rem;">
                    ⚽ Sportsbook
                </button>
                <button class="sub-tab" onclick="switchUserTab('casino')" id="casino-tab" style="padding: 0.75rem 1.5rem; background: transparent; border: none; border-bottom: 3px solid transparent; color: #64748b; font-weight: 600; cursor: pointer;">
                    🎰 Casino
                </button>
            </div>
            
            <!-- Sportsbook Users Table -->
            <div id="sportsbook-users" class="user-tab-content">
                <div class="controls">
                    <button onclick="loadUsers()">🔄 Refresh Users</button>
                </div>
                
                <!-- Pagination Controls -->
                <div class="pagination-controls">
                    <label for="users-per-page">Users per page:</label>
                    <select id="users-per-page" onchange="changeUsersPerPage()">
                        <option value="10">10</option>
                        <option value="20" selected>20</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                    </select>
                    <span id="users-pagination-info" class="pagination-info">Loading...</span>
                </div>
                
                <div class="table-container">
                    <table id="users-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('users-table', 0)" style="cursor: pointer;">
                                    ID <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 1)" style="cursor: pointer;">
                                    Username <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 2)" style="cursor: pointer;">
                                    Email <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 3)" style="cursor: pointer;">
                                    Balance <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 4)" style="cursor: pointer;">
                                    Bets <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 5)" style="cursor: pointer;">
                                    Staked <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 6)" style="cursor: pointer;">
                                    Payout <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 7)" style="cursor: pointer;">
                                    Profit <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 8)" style="cursor: pointer;">
                                    Joined <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('users-table', 9)" style="cursor: pointer;">
                                    Status <span class="sort-icon">↕</span>
                                </th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="users-tbody">
                            <tr><td colspan="11" class="loading">Loading users...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Pagination -->
                <div id="users-pagination" class="pagination" style="display: none;">
                    <button onclick="goToUsersPage(1)" id="users-first-page">« First</button>
                    <button onclick="goToUsersPage(currentUsersPage - 1)" id="users-prev-page">‹ Previous</button>
                    <div id="users-page-numbers"></div>
                    <button onclick="goToUsersPage(currentUsersPage + 1)" id="users-next-page">Next ›</button>
                    <button onclick="goToUsersPage(totalUsersPages)" id="users-last-page">Last »</button>
                </div>
            </div>
            
            <!-- Casino Users Table -->
            <div id="casino-users" class="user-tab-content" style="display: none;">
                <div class="controls">
                    <button onclick="loadCasinoUsers()">🔄 Refresh Casino Users</button>
                </div>
                
                <!-- Pagination Controls for Casino -->
                <div class="pagination-controls">
                    <label for="casino-users-per-page">Users per page:</label>
                    <select id="casino-users-per-page" onchange="changeCasinoUsersPerPage()">
                        <option value="10">10</option>
                        <option value="20" selected>20</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                    </select>
                    <span id="casino-users-pagination-info" class="pagination-info">Loading...</span>
                </div>
                
                <div class="table-container">
                    <table id="casino-users-table">
                        <thead>
                            <tr>
                                <th onclick="sortTable('casino-users-table', 0)" style="cursor: pointer;">
                                    ID <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 1)" style="cursor: pointer;">
                                    Username <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 2)" style="cursor: pointer;">
                                    Email <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 3)" style="cursor: pointer;">
                                    Balance <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 4)" style="cursor: pointer;">
                                    Games <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 5)" style="cursor: pointer;">
                                    Staked <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 6)" style="cursor: pointer;">
                                    Payout <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 7)" style="cursor: pointer;">
                                    Profit <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 8)" style="cursor: pointer;">
                                    Joined <span class="sort-icon">↕</span>
                                </th>
                                <th onclick="sortTable('casino-users-table', 9)" style="cursor: pointer;">
                                    Status <span class="sort-icon">↕</span>
                                </th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="casino-users-tbody">
                            <tr><td colspan="11" class="loading">Loading casino users...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Pagination for Casino -->
                <div id="casino-users-pagination" class="pagination" style="display: none;">
                    <button onclick="goToCasinoUsersPage(1)" id="casino-users-first-page">« First</button>
                    <button onclick="goToCasinoUsersPage(currentCasinoUsersPage - 1)" id="casino-users-prev-page">‹ Previous</button>
                    <div id="casino-users-page-numbers"></div>
                    <button onclick="goToCasinoUsersPage(currentCasinoUsersPage + 1)" id="casino-users-next-page">Next ›</button>
                    <button onclick="goToCasinoUsersPage(totalCasinoUsersPages)" id="casino-users-last-page">Last »</button>
                </div>
            </div>
        </div>
        

        
        <!-- Report Builder Section -->
        <div id="report-builder" class="content-section">
            <h2>Custom Report Builder</h2>
            
            <div class="form-section">
                <h3>📊 Report Configuration</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Report Type:</label>
                        <select id="report-type">
                            <option value="revenue">Revenue Analysis (Sportsbook + Casino)</option>
                            <option value="user-activity">User Activity</option>
                            <option value="trading-patterns">Trading Patterns</option>
                            <option value="sport-performance">Sport Performance</option>
                            <option value="casino-performance">Casino Performance</option>
                        </select>
                        <div class="form-help-text">Choose the type of analysis you want to generate</div>
                    </div>
                    <div class="form-group">
                        <label>Group By:</label>
                        <select id="group-by">
                            <option value="day">Day</option>
                            <option value="week">Week</option>
                            <option value="month">Month</option>
                            <option value="sport">Sport</option>
                            <option value="user">User</option>
                        </select>
                        <div class="form-help-text">Select how to group the data in your report</div>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Date Range:</label>
                        <div class="date-inputs">
                            <input type="date" id="start-date" placeholder="Start Date">
                            <input type="date" id="end-date" placeholder="End Date">
                        </div>
                        <div class="form-help-text">Select the time period for your report</div>
                    </div>
                </div>
                
                <div class="form-divider"></div>
                
                <button class="generate-btn" onclick="generateCustomReport()">
                    📊 Generate Report
                </button>
            </div>
            
            <div id="custom-report-results" class="form-section" style="display: none;">
                <h3>📈 Custom Report Results</h3>
                <div class="table-container">
                    <table id="custom-report-table">
                        <thead id="custom-report-thead"></thead>
                        <tbody id="custom-report-tbody"></tbody>
                    </table>
                </div>
                <button class="generate-btn" onclick="exportCustomReport()" style="margin-top: 1rem;">
                    📊 Export Custom Report
                </button>
            </div>
        </div>
        
    </div>
    
    <script>
        const SUBDOMAIN = '{{ operator.subdomain }}';
        
        // Global variables for pagination and filtering
        let currentPage = 1;
        let perPage = 20;
        let currentSortBy = 'event_id';
        let currentSortOrder = 'asc';
        let currentSportFilter = '';
        let currentMarketFilter = '';
        let currentSearchQuery = '';
        let showOnlyWithBets = true;
        
        // Loading functions
        function showLoading(section) {
            const loadingEl = document.getElementById(`${section}-loading`);
            if (loadingEl) loadingEl.style.display = 'block';
        }
        
        function hideLoading(section) {
            const loadingEl = document.getElementById(`${section}-loading`);
            if (loadingEl) loadingEl.style.display = 'none';
        }
        
        // Pagination function
        function updatePagination(totalItems) {
            const totalPages = Math.ceil(totalItems / perPage);
            const paginationEl = document.getElementById('pagination');
            if (!paginationEl) return;
            
            if (totalPages <= 1) {
                paginationEl.innerHTML = '';
                return;
            }
            
            let paginationHTML = '';
            for (let i = 1; i <= totalPages; i++) {
                paginationHTML += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
            }
            paginationEl.innerHTML = paginationHTML;
        }
        
        function goToPage(page) {
            currentPage = page;
            loadBettingEvents();
        }
        
        // Filter functions
        function applyFilters() {
            currentPage = 1; // Reset to first page when filtering
            currentSportFilter = document.getElementById('sport-filter')?.value || '';
            currentMarketFilter = document.getElementById('market-filter')?.value || '';
            currentSearchQuery = document.getElementById('search-events')?.value || '';
            loadBettingEvents();
        }
        
        function updateFilterOptions(filters) {
            // Update sport filter
            const sportSelect = document.getElementById('sport-filter');
            const currentSport = sportSelect?.value || '';
            if (sportSelect) {
                sportSelect.innerHTML = '<option value="">All Sports</option>';
                if (filters?.sports) {
                    filters.sports.forEach(sport => {
                        const option = document.createElement('option');
                        option.value = sport;
                        option.textContent = sport;
                        if (sport === currentSport) option.selected = true;
                        sportSelect.appendChild(option);
                    });
                }
            }
            
            // Update market filter
            const marketSelect = document.getElementById('market-filter');
            const currentMarket = marketSelect?.value || '';
            if (marketSelect) {
                marketSelect.innerHTML = '<option value="">All Markets</option>';
                if (filters?.markets) {
                    filters.markets.forEach(market => {
                        const option = document.createElement('option');
                        option.value = market;
                        option.textContent = market;
                        if (market === currentMarket) option.selected = true;
                        marketSelect.appendChild(option);
                    });
                }
            }
        }
        
        // Casino toggle functionality
        function toggleCasino() {
            const checkbox = document.getElementById('casinoToggle');
            const status = document.getElementById('casinoStatus');
            const isEnabled = checkbox.checked;
            
            // Update status text and class
            status.textContent = isEnabled ? 'Enabled' : 'Disabled';
            status.className = `casino-status ${isEnabled ? 'enabled' : 'disabled'}`;
            
            // Send API request to update casino setting
            fetch('/api/admin/' + SUBDOMAIN + '/toggle-casino', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ casino_enabled: isEnabled })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    console.log('Casino setting updated:', data.message);
                    
                    // Show or hide Casino tab based on new setting
                    const casinoTab = document.getElementById('casino-tab');
                    if (casinoTab) {
                        if (isEnabled) {
                            casinoTab.style.display = 'inline-block';
                        } else {
                            casinoTab.style.display = 'none';
                            // If casino is disabled and we're on casino tab, switch to sportsbook
                            if (casinoTab.classList.contains('active')) {
                                switchUserTab('sportsbook');
                            }
                        }
                    }
                } else {
                    console.error('Error updating casino setting:', data.error);
                    // Revert the toggle if there was an error
                    checkbox.checked = !isEnabled;
                    status.textContent = !isEnabled ? 'Enabled' : 'Disabled';
                    status.className = `casino-status ${!isEnabled ? 'enabled' : 'disabled'}`;
                    alert('Error updating casino setting: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error updating casino setting:', err);
                // Revert the toggle if there was an error
                checkbox.checked = !isEnabled;
                status.textContent = !isEnabled ? 'Enabled' : 'Disabled';
                status.className = `casino-status ${!isEnabled ? 'enabled' : 'disabled'}`;
                alert('Failed to update casino setting');
            });
        }
        
        // Load casino setting on page load
        function loadCasinoSetting() {
            fetch('/api/admin/' + SUBDOMAIN + '/casino-setting')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const checkbox = document.getElementById('casinoToggle');
                        const status = document.getElementById('casinoStatus');
                        const casinoTab = document.getElementById('casino-tab');
                        
                        checkbox.checked = data.casino_enabled;
                        status.textContent = data.casino_enabled ? 'Enabled' : 'Disabled';
                        status.className = `casino-status ${data.casino_enabled ? 'enabled' : 'disabled'}`;
                        
                        // Show or hide Casino tab based on casino setting
                        if (casinoTab) {
                            if (data.casino_enabled) {
                                casinoTab.style.display = 'inline-block';
                            } else {
                                casinoTab.style.display = 'none';
                                // If casino is disabled and we're on casino tab, switch to sportsbook
                                if (casinoTab.classList.contains('active')) {
                                    switchUserTab('sportsbook');
                                }
                            }
                        }
                    }
                })
                .catch(err => console.error('Error loading casino setting:', err));
        }
        
        // Load referral code on page load
        function loadReferralCode() {
            fetch('/' + SUBDOMAIN + '/admin/api/referral-code')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('referralCodeDisplay').textContent = data.referral_code;
                    } else {
                        document.getElementById('referralCodeDisplay').textContent = 'Not found';
                    }
                })
                .catch(err => {
                    console.error('Error loading referral code:', err);
                    document.getElementById('referralCodeDisplay').textContent = 'Error';
                });
        }
        
        // Copy referral code to clipboard
        function copyReferralCode() {
            const referralCode = document.getElementById('referralCodeDisplay').textContent;
            if (referralCode && referralCode !== 'Loading...' && referralCode !== 'Not found' && referralCode !== 'Error') {
                navigator.clipboard.writeText(referralCode).then(() => {
                    // Show temporary success message
                    const originalText = document.getElementById('referralCodeDisplay').textContent;
                    document.getElementById('referralCodeDisplay').textContent = 'Copied!';
                    document.getElementById('referralCodeDisplay').style.background = 'rgba(0, 255, 0, 0.3)';
                    
                    setTimeout(() => {
                        document.getElementById('referralCodeDisplay').textContent = originalText;
                        document.getElementById('referralCodeDisplay').style.background = 'rgba(0, 0, 0, 0.2)';
                    }, 1000);
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                    alert('Failed to copy referral code');
                });
            }
        }
        
        // Initialize page when DOM is loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Load betting events on page load
            loadBettingEvents();
            // Load casino setting on page load
            loadCasinoSetting();
            // Load referral code on page load
            loadReferralCode();
            
            // Add event listeners for filters
            const sportFilter = document.getElementById('sport-filter');
            const marketFilter = document.getElementById('market-filter');
            const searchInput = document.getElementById('search-events');
            const refreshBtn = document.getElementById('refresh-events');
            
            if (sportFilter) sportFilter.addEventListener('change', applyFilters);
            if (marketFilter) marketFilter.addEventListener('change', applyFilters);
            if (searchInput) searchInput.addEventListener('input', applyFilters);
            if (refreshBtn) refreshBtn.addEventListener('click', loadBettingEvents);
        });
        
        async function loadBettingEvents() {
            try {
                showLoading('betting-events');
                
                // Build query parameters
                const params = new URLSearchParams();
                if (currentPage > 1) params.append('page', currentPage);
                if (perPage !== 20) params.append('per_page', perPage);
                if (currentSortBy !== 'event_id') params.append('sort_by', currentSortBy);
                if (currentSortOrder !== 'asc') params.append('sort_order', currentSortOrder);
                if (currentSportFilter) params.append('sport', currentSportFilter);
                if (currentMarketFilter) params.append('market', currentMarketFilter);
                if (currentSearchQuery) params.append('search', currentSearchQuery);
                
                // Use the correct API endpoint for rich admin interface
                const response = await fetch(`/${SUBDOMAIN}/admin/api/betting-events?${params.toString()}`);
                const data = await response.json();
                
                if (data.success) {
                    // Update summary cards
                    document.getElementById('total-events').textContent = data.summary?.total_events || 0;
                    document.getElementById('active-events').textContent = data.summary?.active_events || 0;
                    
                    // Update total liability from summary
                    const totalLiability = data.summary?.total_liability || 0;
                    document.getElementById('total-liability').textContent = '$' + totalLiability.toFixed(2);
                    
                    // Update events table
                    const tbody = document.getElementById('events-tbody');
                    if (data.events && data.events.length > 0) {
                        const eventRows = data.events.map(event => `
                            <tr>
                                <td>${event.event_id || 'N/A'}</td>
                                <td>${event.sport || 'N/A'}</td>
                                <td>${event.event_name || 'N/A'}</td>
                                <td>${event.market || 'N/A'}</td>
                                <td>${event.total_bets || 0}</td>
                                <td>$${(event.max_liability || 0).toFixed(2)}</td>
                                <td><span class="status-${event.status === 'active' ? 'active' : 'disabled'}">${event.status || 'N/A'}</span></td>
                            </tr>
                        `).join('');
                        tbody.innerHTML = eventRows;
                    } else {
                        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #666; padding: 2rem; font-style: italic;">📊 No pending events at the moment</td></tr>';
                    }
                    
                    // Update pagination
                    updatePagination(data.summary?.total_events || 0);
                    
                    // Update filter options
                    if (data.filters) {
                        updateFilterOptions(data.filters);
                    }
                } else {
                    console.error('Failed to load betting events:', data.error);
                    document.getElementById('events-tbody').innerHTML = '<tr><td colspan="7" style="text-align: center; color: #dc3545; padding: 2rem;">⚠️ Unable to load events. Please try refreshing the page.</td></tr>';
                }
            } catch (error) {
                console.error('Error loading betting events:', error);
                document.getElementById('events-tbody').innerHTML = '<tr><td colspan="7" style="text-align: center; color: #dc3545; padding: 2rem;">⚠️ Unable to load events. Please try refreshing the page.</td></tr>';
            } finally {
                hideLoading('betting-events');
            }
        }
        
        async function toggleEvent(eventId) {
            try {
                const response = await fetch(`/${SUBDOMAIN}/admin/api/betting-events/${eventId}/toggle`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    loadBettingEvents(); // Reload the events table
                } else {
                    alert('Error: ' + data.error);
                }
                
            } catch (error) {
                alert('Error toggling event status: ' + error.message);
            }
        }
        

        
        // Pagination variables
        let currentUsersPage = 1;
        let totalUsersPages = 1;
        let usersPerPage = 20;
        
        async function loadUsers(page = 1) {
            try {
                currentUsersPage = page;
                const perPage = parseInt(document.getElementById('users-per-page').value) || 20;
                usersPerPage = perPage;
                
                const response = await fetch(`/${SUBDOMAIN}/admin/api/users?page=${page}&per_page=${perPage}`);
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('users-tbody').innerHTML = 
                        `<tr><td colspan="11" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                // Update pagination info
                totalUsersPages = Math.ceil(data.total / perPage);
                document.getElementById('users-pagination-info').textContent = 
                    `Showing ${((page - 1) * perPage) + 1}-${Math.min(page * perPage, data.total)} of ${data.total} users`;
                
                const tbody = document.getElementById('users-tbody');
                if (data.users.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="11" class="loading">No users found</td></tr>';
                } else {
                    tbody.innerHTML = data.users.map(user => `
                        <tr>
                            <td data-sort="${user.id}">${user.id}</td>
                            <td data-sort="${user.username}">${user.username}</td>
                            <td data-sort="${user.email}">${user.email}</td>
                            <td data-sort="${user.balance}">$${user.balance}</td>
                            <td data-sort="${user.total_bets}">${user.total_bets}</td>
                            <td data-sort="${user.total_staked}">$${user.total_staked}</td>
                            <td data-sort="${user.total_payout}">$${user.total_payout}</td>
                            <td data-sort="${user.profit}">$${user.profit}</td>
                            <td data-sort="${new Date(user.created_at).getTime()}">${new Date(user.created_at).toLocaleDateString()}</td>
                            <td data-sort="${user.is_active ? 'active' : 'disabled'}"><span class="status-badge status-${user.is_active ? 'active' : 'disabled'}">${user.is_active ? 'Active' : 'Disabled'}</span></td>
                            <td>
                                <button class="action-btn ${user.is_active ? 'btn-disable' : 'btn-enable'}" 
                                        onclick="toggleUserStatus(${user.id})">
                                    ${user.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    `).join('');
                }
                
                // Update pagination controls
                updateUsersPagination();
                
            } catch (error) {
                document.getElementById('users-tbody').innerHTML = 
                    `<tr><td colspan="11" class="error">Error loading users: ${error.message}</td></tr>`;
            }
        }
        
        function updateUsersPagination() {
            const pagination = document.getElementById('users-pagination');
            const pageNumbers = document.getElementById('users-page-numbers');
            
            if (totalUsersPages <= 1) {
                pagination.style.display = 'none';
                return;
            }
            
            pagination.style.display = 'flex';
            
            // Update button states
            document.getElementById('users-first-page').disabled = currentUsersPage === 1;
            document.getElementById('users-prev-page').disabled = currentUsersPage === 1;
            document.getElementById('users-next-page').disabled = currentUsersPage === totalUsersPages;
            document.getElementById('users-last-page').disabled = currentUsersPage === totalUsersPages;
            
            // Generate page numbers
            let pageNumbersHtml = '';
            const startPage = Math.max(1, currentUsersPage - 2);
            const endPage = Math.min(totalUsersPages, currentUsersPage + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                pageNumbersHtml += `<button onclick="goToUsersPage(${i})" class="${i === currentUsersPage ? 'active' : ''}">${i}</button>`;
            }
            
            pageNumbers.innerHTML = pageNumbersHtml;
        }
        
        function goToUsersPage(page) {
            if (page >= 1 && page <= totalUsersPages) {
                loadUsers(page);
            }
        }
        
        function changeUsersPerPage() {
            currentUsersPage = 1;
            loadUsers(1);
        }
        
        async function toggleUserStatus(userId) {
            try {
                const response = await fetch(`/${SUBDOMAIN}/admin/api/user/${userId}/toggle`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    // Reload both tables since disabling affects both sportsbook and casino
                    loadUsers();
                    loadCasinoUsers();
                    alert(data.message || 'User status updated successfully');
                } else {
                    alert('Error: ' + data.error);
                }
                
            } catch (error) {
                alert('Error toggling user status: ' + error.message);
            }
        }
        
        // Sub-tab switching function
        function switchUserTab(tabName) {
            // Hide all tab contents
            document.getElementById('sportsbook-users').style.display = 'none';
            document.getElementById('casino-users').style.display = 'none';
            
            // Remove active class from all tabs
            document.getElementById('sportsbook-tab').classList.remove('active');
            document.getElementById('casino-tab').classList.remove('active');
            document.getElementById('sportsbook-tab').style.borderBottomColor = 'transparent';
            document.getElementById('casino-tab').style.borderBottomColor = 'transparent';
            document.getElementById('sportsbook-tab').style.color = '#64748b';
            document.getElementById('casino-tab').style.color = '#64748b';
            
            // Show selected tab and update styles
            if (tabName === 'sportsbook') {
                document.getElementById('sportsbook-users').style.display = 'block';
                document.getElementById('sportsbook-tab').classList.add('active');
                document.getElementById('sportsbook-tab').style.borderBottomColor = '#4ade80';
                document.getElementById('sportsbook-tab').style.color = '#1e293b';
            } else if (tabName === 'casino') {
                document.getElementById('casino-users').style.display = 'block';
                document.getElementById('casino-tab').classList.add('active');
                document.getElementById('casino-tab').style.borderBottomColor = '#4ade80';
                document.getElementById('casino-tab').style.color = '#1e293b';
                loadCasinoUsers(); // Load casino users when switching to casino tab
            }
        }
        
        // Casino Users Pagination Variables
        let currentCasinoUsersPage = 1;
        let totalCasinoUsersPages = 1;
        let totalCasinoUsers = 0;
        
        // Load Casino Users Function
        async function loadCasinoUsers(page = 1) {
            try {
                currentCasinoUsersPage = page;
                const perPage = parseInt(document.getElementById('casino-users-per-page').value);
                
                const response = await fetch(`/${SUBDOMAIN}/admin/api/casino-users?page=${page}&per_page=${perPage}`);
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('casino-users-tbody').innerHTML = 
                        `<tr><td colspan="11" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                totalCasinoUsers = data.total;
                totalCasinoUsersPages = Math.ceil(data.total / perPage);
                
                // Update pagination info
                document.getElementById('casino-users-pagination-info').textContent = 
                    `Showing ${((page - 1) * perPage) + 1}-${Math.min(page * perPage, data.total)} of ${data.total} users`;
                
                // Display casino users
                const tbody = document.getElementById('casino-users-tbody');
                if (data.users.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="11" class="loading">No casino users found</td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.users.map(user => {
                    const statusClass = user.is_active ? 'active' : 'inactive';
                    const statusText = user.is_active ? 'Active' : 'Disabled';
                    const profit = user.profit || 0;
                    const profitClass = profit >= 0 ? 'positive' : 'negative';
                    
                    return `
                        <tr>
                            <td data-sort="${user.id}">${user.id}</td>
                            <td data-sort="${user.username}">${user.username}</td>
                            <td data-sort="${user.email}">${user.email}</td>
                            <td data-sort="${user.balance}">$${user.balance.toFixed(2)}</td>
                            <td data-sort="${user.total_games}">${user.total_games || 0}</td>
                            <td data-sort="${user.total_staked}">$${(user.total_staked || 0).toFixed(2)}</td>
                            <td data-sort="${user.total_payout}">$${(user.total_payout || 0).toFixed(2)}</td>
                            <td data-sort="${profit}" class="${profitClass}">$${profit.toFixed(2)}</td>
                            <td data-sort="${user.created_at}">${new Date(user.created_at).toLocaleDateString()}</td>
                            <td data-sort="${user.is_active}"><span class="badge ${statusClass}">${statusText}</span></td>
                            <td>
                                <button class="btn-sm ${user.is_active ? 'btn-danger' : 'btn-success'}" 
                                        onclick="toggleUserStatus(${user.id})">
                                    ${user.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
                
                // Update pagination controls
                updateCasinoUsersPagination();
                
            } catch (error) {
                document.getElementById('casino-users-tbody').innerHTML = 
                    `<tr><td colspan="11" class="error">Error loading casino users: ${error.message}</td></tr>`;
            }
        }
        
        function updateCasinoUsersPagination() {
            const pagination = document.getElementById('casino-users-pagination');
            const pageNumbers = document.getElementById('casino-users-page-numbers');
            
            if (totalCasinoUsersPages <= 1) {
                pagination.style.display = 'none';
                return;
            }
            
            pagination.style.display = 'flex';
            
            // Update button states
            document.getElementById('casino-users-first-page').disabled = currentCasinoUsersPage === 1;
            document.getElementById('casino-users-prev-page').disabled = currentCasinoUsersPage === 1;
            document.getElementById('casino-users-next-page').disabled = currentCasinoUsersPage === totalCasinoUsersPages;
            document.getElementById('casino-users-last-page').disabled = currentCasinoUsersPage === totalCasinoUsersPages;
            
            // Generate page numbers
            let pageNumbersHtml = '';
            const startPage = Math.max(1, currentCasinoUsersPage - 2);
            const endPage = Math.min(totalCasinoUsersPages, currentCasinoUsersPage + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                pageNumbersHtml += `<button onclick="goToCasinoUsersPage(${i})" class="${i === currentCasinoUsersPage ? 'active' : ''}">${i}</button>`;
            }
            
            pageNumbers.innerHTML = pageNumbersHtml;
        }
        
        function goToCasinoUsersPage(page) {
            if (page >= 1 && page <= totalCasinoUsersPages) {
                loadCasinoUsers(page);
            }
        }
        
        function changeCasinoUsersPerPage() {
            currentCasinoUsersPage = 1;
            loadCasinoUsers(1);
        }
        
        
        function openThemeCustomizer() {
            // Open theme customizer in new tab for this specific operator
            window.open(`/${SUBDOMAIN}/admin/theme-customizer`, '_blank');
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
        
        async function loadReportBuilder() {
            try {
                // Report builder is now ready - no need to load sports filter
                console.log('Report builder loaded successfully');
            } catch (error) {
                console.error('Error loading report builder:', error);
            }
        }
        
        async function generateCustomReport() {
            try {
                const reportType = document.getElementById('report-type').value;
                const startDate = document.getElementById('start-date').value;
                const endDate = document.getElementById('end-date').value;
                const groupBy = document.getElementById('group-by').value;
                
                // Show loading state
                const resultsDiv = document.getElementById('custom-report-results');
                resultsDiv.style.display = 'block';
                
                const tbody = document.getElementById('custom-report-tbody');
                const thead = document.getElementById('custom-report-thead');
                
                tbody.innerHTML = '<tr><td colspan="5" class="loading">Generating report...</td></tr>';
                
                // Generate report data
                const response = await fetch(`/${SUBDOMAIN}/admin/api/reports/generate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        report_type: reportType,
                        date_from: startDate || null,
                        date_to: endDate || null,
                        group_by: groupBy
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    tbody.innerHTML = `<tr><td colspan="5" class="error">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                // Update table headers based on report type
                const headers = getReportHeaders(reportType, groupBy);
                thead.innerHTML = `<tr>${headers.map((h, index) => `<th onclick="sortTable('custom-report-table', ${index})" style="cursor: pointer;">${h} <span class="sort-icon">↕</span></th>`).join('')}</tr>`;
                
                // Update table body with report data
                if (data.length > 0) {
                    tbody.innerHTML = data.map(row => {
                        const cells = getReportCells(row, reportType, groupBy);
                        const sortValues = getReportSortValues(row, reportType, groupBy);
                        return `<tr>${cells.map((cell, index) => `<td data-sort="${sortValues[index]}">${cell}</td>`).join('')}</tr>`;
                    }).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="' + headers.length + '" class="loading">No data found for the selected criteria</td></tr>';
                }
                
            } catch (error) {
                console.error('Error generating custom report:', error);
                const tbody = document.getElementById('custom-report-tbody');
                tbody.innerHTML = `<tr><td colspan="5" class="error">Error generating report: ${error.message}</td></tr>`;
            }
        }
        
        function getReportHeaders(reportType, groupBy) {
            const headerMap = {
                'revenue': ['Date', 'Category', 'Platform', 'Total Bets', 'Total Stakes', 'Revenue', 'Profit Margin'],
                'user-activity': ['Username', 'Email', 'Total Bets', 'Total Staked', 'Payout', 'Profit', 'Join Date'],
                'betting-patterns': ['Date', 'Sport', 'Bet Type', 'Count', 'Total Amount', 'Win Rate'],
                'sport-performance': ['Sport', 'Total Bets', 'Total Stakes', 'Won Bets', 'Lost Bets', 'Revenue', 'Win Rate'],
                'casino-performance': ['Game', 'Total Games', 'Total Stakes', 'Won Games', 'Lost Games', 'Revenue', 'Win Rate']
            };
            
            return headerMap[reportType] || ['Data', 'Value'];
        }
        
        function getReportCells(row, reportType, groupBy) {
            switch (reportType) {
                case 'revenue':
                    return [
                        row.bet_date || row.report_date || 'N/A',
                        row.category || row.sport_name || 'N/A',
                        row.platform || 'N/A',
                        row.total_bets || 0,
                        `$${(row.total_stakes || 0).toFixed(2)}`,
                        `$${(row.revenue || 0).toFixed(2)}`,
                        `${((row.revenue || 0) / Math.max(row.total_stakes || 1, 1) * 100).toFixed(1)}%`
                    ];
                case 'user-activity':
                    return [
                        row.username || 'N/A',
                        row.email || 'N/A',
                        row.total_bets || 0,
                        `$${(row.total_staked || 0).toFixed(2)}`,
                        `$${(row.payout || 0).toFixed(2)}`,
                        `$${(row.user_profit || 0).toFixed(2)}`,
                        new Date(row.joined_date || Date.now()).toLocaleDateString()
                    ];
                case 'betting-patterns':
                    return [
                        row.bet_date || 'N/A',
                        row.sport_name || 'N/A',
                        row.bet_type || 'N/A',
                        row.count || 0,
                        `$${(row.total_amount || 0).toFixed(2)}`,
                        `${(row.win_rate || 0).toFixed(1)}%`
                    ];
                case 'sport-performance':
                    return [
                        row.sport_name || 'N/A',
                        row.total_bets || 0,
                        `$${(row.total_stakes || 0).toFixed(2)}`,
                        row.won_bets || 0,
                        row.lost_bets || 0,
                        `$${(row.sport_revenue || 0).toFixed(2)}`,
                        `${(row.win_rate || 0).toFixed(1)}%`
                    ];
                case 'casino-performance':
                    return [
                        row.game_name || 'N/A',
                        row.total_games || 0,
                        `$${(row.total_stakes || 0).toFixed(2)}`,
                        row.won_games || 0,
                        row.lost_games || 0,
                        `$${(row.casino_revenue || 0).toFixed(2)}`,
                        `${(row.win_rate || 0).toFixed(1)}%`
                    ];
                default:
                    return Object.values(row);
            }
        }

        function getReportSortValues(row, reportType, groupBy) {
            switch (reportType) {
                case 'revenue':
                    return [
                        new Date(row.bet_date || row.report_date || Date.now()).getTime(),
                        row.category || row.sport_name || '',
                        row.platform || '',
                        row.total_bets || 0,
                        row.total_stakes || 0,
                        row.revenue || 0,
                        (row.revenue || 0) / Math.max(row.total_stakes || 1, 1) * 100
                    ];
                case 'user-activity':
                    return [
                        row.username || '',
                        row.email || '',
                        row.total_bets || 0,
                        row.total_staked || 0,
                        row.payout || 0,
                        row.user_profit || 0,
                        new Date(row.joined_date || Date.now()).getTime()
                    ];
                case 'betting-patterns':
                    return [
                        new Date(row.bet_date || Date.now()).getTime(),
                        row.sport_name || '',
                        row.bet_type || '',
                        row.count || 0,
                        row.total_amount || 0,
                        row.win_rate || 0
                    ];
                case 'sport-performance':
                    return [
                        row.sport_name || '',
                        row.total_bets || 0,
                        row.total_stakes || 0,
                        row.won_bets || 0,
                        row.lost_bets || 0,
                        row.sport_revenue || 0,
                        row.win_rate || 0
                    ];
                case 'casino-performance':
                    return [
                        row.game_name || '',
                        row.total_games || 0,
                        row.total_stakes || 0,
                        row.won_games || 0,
                        row.lost_games || 0,
                        row.casino_revenue || 0,
                        row.win_rate || 0
                    ];
                default:
                    return Object.values(row);
            }
        }
        
        async function exportCustomReport() {
            try {
                const reportType = document.getElementById('report-type').value;
                const startDate = document.getElementById('start-date').value;
                const endDate = document.getElementById('end-date').value;
                const sportFilter = document.getElementById('sport-filter-report').value;
                const format = 'csv'; // Default to CSV for now
                
                const response = await fetch(`/${SUBDOMAIN}/admin/api/reports/export`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        report_type: reportType,
                        format: format,
                        date_from: startDate || null,
                        date_to: endDate || null,
                        sport_filter: sportFilter || null
                    })
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    
                    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
                    a.download = `${reportType}_${timestamp}.${format}`;
                    
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    throw new Error('Failed to export report');
                }
                
            } catch (error) {
                console.error('Error exporting custom report:', error);
                alert('Failed to export report. Please try again.');
            }
        }
        
        function showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.content-section').forEach(section => {
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
            
            // Load data for specific sections
            if (sectionId === 'betting-events') {
                loadBettingEvents();
            } else if (sectionId === 'report-builder') {
                loadReportBuilder();
            } else if (sectionId === 'user-management') {
                loadUsers();
            }
        }
        
        // Settings Dropdown Functions
        function toggleSettingsDropdown() {
            const dropdown = document.getElementById('settings-dropdown');
            dropdown.classList.toggle('show');
        }
        
        function clearPasswordForm() {
            document.getElementById('password-change-form').reset();
            hideMessage();
        }
        
        function showMessage(message, type) {
            const messageDiv = document.getElementById('password-change-message');
            messageDiv.textContent = message;
            messageDiv.className = `message ${type}`;
            messageDiv.style.display = 'block';
            
            // Auto-hide success messages after 5 seconds
            if (type === 'success') {
                setTimeout(() => {
                    hideMessage();
                }, 5000);
            }
        }
        
        function hideMessage() {
            const messageDiv = document.getElementById('password-change-message');
            messageDiv.style.display = 'none';
        }
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(event) {
            const dropdown = document.getElementById('settings-dropdown');
            const settingsBtn = document.querySelector('.settings-btn');
            
            if (!dropdown.contains(event.target) && !settingsBtn.contains(event.target)) {
                dropdown.classList.remove('show');
            }
        });
        
        // Handle password change form submission
        document.addEventListener('DOMContentLoaded', function() {
            const passwordForm = document.getElementById('password-change-form');
            if (passwordForm) {
                passwordForm.addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    const currentPassword = document.getElementById('current-password').value;
                    const newPassword = document.getElementById('new-password').value;
                    const confirmPassword = document.getElementById('confirm-password').value;
                    
                    // Validate passwords
                    if (newPassword !== confirmPassword) {
                        showMessage('New passwords do not match', 'error');
                        return;
                    }
                    
                    if (newPassword.length < 6) {
                        showMessage('New password must be at least 6 characters long', 'error');
                        return;
                    }
                    
                    try {
                        const response = await fetch(`/${SUBDOMAIN}/admin/api/change-password`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                current_password: currentPassword,
                                new_password: newPassword
                            })
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            showMessage('Password changed successfully!', 'success');
                            clearPasswordForm();
                            // Close dropdown after successful password change
                            setTimeout(() => {
                                document.getElementById('settings-dropdown').classList.remove('show');
                            }, 2000);
                        } else {
                            showMessage(data.error || 'Failed to change password', 'error');
                        }
                    } catch (error) {
                        console.error('Error changing password:', error);
                        showMessage('An error occurred while changing password', 'error');
                    }
                });
            }
        });
    </script>
</body>
</html>
'''

