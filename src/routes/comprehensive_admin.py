"""
Comprehensive Admin Interface - Tenant Filtered
Exact same features as admin_app.py but filtered for specific operator
"""

from flask import Blueprint, render_template_string, jsonify, request, session, redirect, url_for
from src import sqlite3_shim as sqlite3
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)

comprehensive_admin_bp = Blueprint('comprehensive_admin', __name__)

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim"""
    conn = sqlite3.connect()  # No path needed - shim uses DATABASE_URL
    return conn

def admin_required(f):
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

def get_operator_by_subdomain(subdomain):
    """Get operator by subdomain"""
    conn = get_db_connection()
    operator = conn.execute("""
        SELECT id, sportsbook_name, subdomain, is_active, login
        FROM sportsbook_operators 
        WHERE subdomain = ?
    """, (subdomain,)).fetchone()
    conn.close()
    return dict(operator) if operator else None

@comprehensive_admin_bp.route('/admin/<subdomain>/dashboard')
@admin_required
def admin_dashboard(subdomain):
    """Comprehensive admin dashboard for specific operator"""
    try:
        # Get operator info
        operator = get_operator_by_subdomain(subdomain)
        if not operator:
            return "Operator not found", 404
        
        # Verify admin belongs to this operator
        if session.get('admin_operator_id') != operator['id']:
            return "Unauthorized", 403
        
        operator_id = operator['id']
        
        # Get comprehensive admin interface HTML
        html_template = get_comprehensive_admin_template()
        
        return render_template_string(html_template, 
                                    operator=operator,
                                    operator_id=operator_id)
        
    except Exception as e:
        logger.error(f"Admin dashboard error for {subdomain}: {e}")
        return "Dashboard error", 500

@comprehensive_admin_bp.route('/api/admin/<subdomain>/betting-events')
@admin_required
def get_betting_events(subdomain):
    """Get betting events for specific operator with proper filtering logic"""
    try:
        print(f"🔍 DEBUG: Starting get_betting_events for subdomain: {subdomain}")
        
        operator = get_operator_by_subdomain(subdomain)
        print(f"🔍 DEBUG: Operator found: {operator}")
        
        admin_operator_id = session.get('admin_operator_id') or session.get('admin_id') or session.get('operator_id')
        print(f"🔍 DEBUG: Admin operator ID: {admin_operator_id}")
        
        if not operator or admin_operator_id != operator['id']:
            print(f"🔍 DEBUG: Authorization failed - operator: {operator}, admin_id: {admin_operator_id}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        operator_id = operator['id']
        show_only_with_bets = request.args.get('show_only_with_bets', 'false').lower() == 'true'
        
        print(f"🔍 DEBUG: show_only_with_bets = {show_only_with_bets}")
        print(f"🔍 DEBUG: Operator ID: {operator_id}")
        
        print("🔍 DEBUG: Getting database connection...")
        conn = get_db_connection()
        print("🔍 DEBUG: Database connection successful")
        
        # Step 1: Get ALL pending bets for this operator from database - AGGREGATED by event+market
        base_query = """
            SELECT 
                b.match_id,
                b.sport_name, 
                b.market, 
                b.match_name,
                COUNT(*) as bet_count
            FROM bets b
            JOIN users u ON b.user_id = u.id 
            WHERE u.sportsbook_operator_id = ? AND b.status = 'pending'
            GROUP BY b.match_id, b.sport_name, b.market, b.match_name
            ORDER BY b.match_id DESC
        """
        
        print(f"🔍 DEBUG: Executing base query with operator_id: {operator_id}")
        print(f"🔍 DEBUG: SQL Query: {base_query}")
        
        try:
            bet_events_result = conn.execute(base_query, (operator_id,)).fetchall()
            print(f"🔍 DEBUG: Query executed successfully")
            print(f"🔍 DEBUG: Found {len(bet_events_result)} pending bets for operator {operator_id}")
        except Exception as e:
            print(f"🔍 DEBUG: Error executing base query: {e}")
            raise e
        
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
                    SUM(b.potential_return) as total_potential_returns
                FROM bets b
                JOIN users u ON b.user_id = u.id
                WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
                AND u.sportsbook_operator_id = ?
            """
            
            totals = conn.execute(totals_query, (bet['match_id'], bet['market'], bet['sport_name'], operator_id)).fetchone()
            
            if totals:
                event_total_stakes = float(totals['total_stakes'] or 0)
                event_total_potential_returns = float(totals['total_potential_returns'] or 0)
                
                # Get detailed bet selections for liability calculation
                selections_query = """
                    SELECT b.bet_selection, SUM(b.stake) as total_stake, SUM(b.potential_return) as total_payout
                    FROM bets b
                    JOIN users u ON b.user_id = u.id
                    WHERE b.match_id = ? AND b.market = ? AND b.sport_name = ? AND b.status = 'pending'
                    AND u.sportsbook_operator_id = ?
                    GROUP BY b.bet_selection
                """
                
                selections = conn.execute(selections_query, (bet['match_id'], bet['market'], bet['sport_name'], operator_id)).fetchall()
                
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
                    'event_name': bet['match_name'],
                    'market': bet['market'],
                    'total_bets': bet['bet_count'],
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
        
        total_events = len(all_events)
        active_events = len([e for e in all_events if e['status'] == 'active'])
        
        # Calculate total liability and max possible gain (sum of individual event liabilities)
        total_liability = sum(e.get('max_liability', 0) for e in all_events)
        total_max_possible_gain = sum(e.get('max_possible_gain', 0) for e in all_events)
        
        print(f"🔍 DEBUG: Final result - total_events: {total_events}, active_events: {active_events}")
        print(f"🔍 DEBUG: Total liability: {total_liability}, Total max_possible_gain: {total_max_possible_gain}")
        print(f"🔍 DEBUG: all_events: {all_events}")
        
        return jsonify({
            'success': True,
            'events': all_events,
            'total_events': total_events,
            'active_events': active_events,
            'total_liability': total_liability,
            'total_max_possible_gain': total_max_possible_gain
        })
        
    except Exception as e:
        logger.error(f"Betting events error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to get events'}), 500

    finally:

        if conn:

            conn.close()

@comprehensive_admin_bp.route('/api/admin/<subdomain>/users')
@admin_required
def get_users(subdomain):
    """Get users for specific operator"""
    try:
        operator = get_operator_by_subdomain(subdomain)
        # Check for admin-specific session keys only to prevent superadmin interference
        admin_operator_id = session.get('admin_operator_id')
        if not operator or not admin_operator_id or admin_operator_id != operator['id']:
            return jsonify({'error': 'Unauthorized - admin session required'}), 403
        
        operator_id = operator['id']
        conn = get_db_connection()
        
        # Get users for this operator only
        users_query = """
        SELECT u.id, u.username, u.email, u.balance, u.is_active, u.created_at, u.last_login,
               COUNT(b.id) as total_bets,
               COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost', 'void') THEN b.stake ELSE 0 END), 0) as total_staked,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as total_payout,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) - 
               COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost', 'void') THEN b.stake ELSE 0 END), 0) as cumulative_profit
        FROM users u
        LEFT JOIN bets b ON u.id = b.user_id
        WHERE u.sportsbook_operator_id = ?
        GROUP BY u.id, u.username, u.email, u.balance, u.is_active, u.created_at, u.last_login
        ORDER BY u.created_at DESC
        """
        
        users = conn.execute(users_query, (operator_id,)).fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'balance': round(float(user['balance']), 2),
                'total_bets': user['total_bets'],
                'total_staked': round(float(user['total_staked']), 2),
                'total_payout': round(float(user['total_payout']), 2),
                'cumulative_profit': round(float(user['cumulative_profit']), 2),
                'joined': user['created_at'][:10] if user['created_at'] else '',
                'status': 'Active' if user['is_active'] else 'Disabled',
                'is_active': user['is_active']
            })
        
        return jsonify({
            'success': True,
            'users': users_list
        })
        
    except Exception as e:
        logger.error(f"Users error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to get users'}), 500

    finally:

        if conn:

            conn.close()

@comprehensive_admin_bp.route('/api/admin/<subdomain>/toggle-user', methods=['POST'])
@admin_required
def toggle_user_status(subdomain):
    """Enable/disable user for specific operator"""
    try:
        operator = get_operator_by_subdomain(subdomain)
        if not operator or session.get('admin_operator_id') != operator['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        conn = get_db_connection()
        
        # Verify user belongs to this operator
        user = conn.execute("""
            SELECT id, is_active FROM users 
            WHERE id = ? AND sportsbook_operator_id = ?
        """, (user_id, operator['id'])).fetchone()
        
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
            'message': f"User {'enabled' if new_status else 'disabled'} successfully",
            'new_status': new_status
        })
        
    except Exception as e:
        logger.error(f"Toggle user error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to toggle user status'}), 500

    finally:

        if conn:

            conn.close()

@comprehensive_admin_bp.route('/api/admin/<subdomain>/reports')
@admin_required
def get_reports(subdomain):
    """Get comprehensive reports for specific operator"""
    try:
        operator = get_operator_by_subdomain(subdomain)
        if not operator or session.get('admin_operator_id') != operator['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        operator_id = operator['id']
        conn = get_db_connection()
        
        # Get comprehensive betting statistics for this operator
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
        WHERE u.sportsbook_operator_id = ?
        """
        
        stats = conn.execute(stats_query, (operator_id,)).fetchone()
        
        # Get sport performance
        sport_query = """
        SELECT b.sport_name,
               COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.potential_return - b.stake 
                               WHEN b.status = 'lost' THEN -b.stake ELSE 0 END), 0) as revenue
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE u.sportsbook_operator_id = ?
        GROUP BY b.sport_name
        ORDER BY revenue DESC
        """
        
        sports = conn.execute(sport_query, (operator_id,)).fetchall()
        
        # Get top users
        top_users_query = """
        SELECT u.username, COUNT(b.id) as bet_count
        FROM users u
        LEFT JOIN bets b ON u.id = b.user_id
        WHERE u.sportsbook_operator_id = ?
        GROUP BY u.id, u.username
        HAVING bet_count > 0
        ORDER BY bet_count DESC
        LIMIT 10
        """
        
        top_users = conn.execute(top_users_query, (operator_id,)).fetchall()
        
        conn.close()
        
        # Calculate win rate
        total_bets = stats['total_bets'] or 0
        won_bets = stats['won_bets'] or 0
        win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_bets': total_bets,
                'total_stakes': round(float(stats['total_stakes'] or 0), 2),
                'total_revenue': round(float(stats['total_revenue'] or 0), 2),
                'win_rate': round(win_rate, 1),
                'pending_bets': stats['pending_bets'] or 0,
                'won_bets': won_bets,
                'lost_bets': stats['lost_bets'] or 0
            },
            'sport_performance': [{'sport': s['sport_name'], 'revenue': round(float(s['revenue']), 2)} for s in sports],
            'top_users': [{'username': u['username'], 'bets': u['bet_count']} for u in top_users]
        })
        
    except Exception as e:
        logger.error(f"Reports error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to get reports'}), 500

    finally:

        if conn:

            conn.close()

@comprehensive_admin_bp.route('/api/admin/<subdomain>/casino-setting')
@admin_required
def get_casino_setting(subdomain):
    """Get casino enabled setting for specific operator"""
    try:
        operator = get_operator_by_subdomain(subdomain)
        if not operator or session.get('admin_operator_id') != operator['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
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
        logger.error(f"Casino setting error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to get casino setting'}), 500

    finally:

        if conn:

            conn.close()

@comprehensive_admin_bp.route('/api/admin/<subdomain>/toggle-casino', methods=['POST'])
@admin_required
def toggle_casino_setting(subdomain):
    """Toggle casino enabled setting for specific operator"""
    try:
        operator = get_operator_by_subdomain(subdomain)
        if not operator or session.get('admin_operator_id') != operator['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
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
        logger.error(f"Toggle casino error for {subdomain}: {e}")
        return jsonify({'error': 'Failed to toggle casino setting'}), 500

    finally:

        if conn:

            conn.close()

def get_comprehensive_admin_template():
    """Get the comprehensive admin HTML template"""
    return """
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>{{ operator.sportsbook_name }} - Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .header { background: rgba(0,0,0,0.1); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; color: white; }
        .header h1 { font-size: 1.5rem; }
        .logout-btn { background: #e74c3c; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; }
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 1rem; }
        .tabs { display: flex; gap: 1rem; margin-bottom: 2rem; }
        .tab { background: rgba(255,255,255,0.1); color: white; border: none; padding: 1rem 2rem; border-radius: 10px; cursor: pointer; transition: all 0.3s; }
        .tab.active { background: rgba(255,255,255,0.2); transform: translateY(-2px); }
        .tab-content { background: white; border-radius: 15px; padding: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.1); display: none; }
        .tab-content.active { display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 1.5rem; border-radius: 10px; text-align: center; }
        .stat-number { font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }
        .stat-label { opacity: 0.9; }
        .data-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        .data-table th, .data-table td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
        .data-table th { background: #f8f9fa; font-weight: 600; }
        .data-table th[onclick] { cursor: pointer; user-select: none; }
        .data-table th[onclick]:hover { background: #e9ecef; }
        .sort-icon { margin-left: 0.5rem; font-weight: bold; color: #6c757d; }
        .data-table th[data-sort-direction="asc"] .sort-icon { color: #28a745; }
        .data-table th[data-sort-direction="desc"] .sort-icon { color: #dc3545; }
        .data-table { table-layout: fixed; }
        .data-table thead { 
            display: table-header-group !important; 
            visibility: visible !important; 
            opacity: 1 !important;
            position: relative !important;
            z-index: 1000 !important;
        }
        .data-table th { 
            display: table-cell !important; 
            visibility: visible !important; 
            opacity: 1 !important;
            position: relative !important;
        }
        #events-table-headers { 
            display: table-header-group !important; 
            visibility: visible !important; 
            opacity: 1 !important;
        }
        #events-table-headers th { 
            display: table-cell !important; 
            visibility: visible !important; 
            opacity: 1 !important;
        }
        .btn { padding: 0.5rem 1rem; border: none; border-radius: 5px; cursor: pointer; font-size: 0.9rem; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-primary { background: #3498db; color: white; }
        .status-active { background: #27ae60; color: white; padding: 0.25rem 0.5rem; border-radius: 3px; font-size: 0.8rem; }
        .status-disabled { background: #e74c3c; color: white; padding: 0.25rem 0.5rem; border-radius: 3px; font-size: 0.8rem; }
        .loading { text-align: center; padding: 2rem; color: #666; }
        .reports-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 2rem; }
        .report-card { background: #f8f9fa; padding: 1.5rem; border-radius: 10px; border-left: 4px solid #667eea; }
        .report-title { font-weight: 600; margin-bottom: 1rem; color: #333; }
        
        /* Casino Slider Styles */
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
        
        #casinoToggle:checked + .casino-slider {
            background: #28a745; /* Green when enabled */
        }
        
        #casinoToggle:not(:checked) + .casino-slider {
            background: #dc3545; /* Red when disabled */
        }
        
        #casinoToggle:checked + .casino-slider:before {
            transform: translateX(30px);
        }
        
        .casino-slider-button {
            display: none; /* This is just for semantic purposes */
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
            <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('trading-events', event)">📊 Trading Events</button>
            <button class="tab" onclick="showTab('user-management', event)">👥 User Management</button>
            <button class="tab" onclick="showTab('reports', event)">📈 Reports</button>
            <button class="tab" onclick="showTab('report-builder', event)">🔧 Report Builder</button>
        </div>

        <!-- Trading Events Tab -->
        <div id="trading-events" class="tab-content active">
            <h2>Trading Events Management</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-events">-</div>
                    <div class="stat-label">Total Events</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="active-events">-</div>
                    <div class="stat-label">Active Events</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-liability">$0.00</div>
                    <div class="stat-label">Total Liability</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-revenue-events">$0.00</div>
                    <div class="stat-label">Total Revenue</div>
                </div>
            </div>
            
            <!-- Casino Control Section -->
            <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; border-left: 4px solid #667eea;">
                <h3 style="margin-bottom: 1rem; color: #333;">🎰 Casino Settings</h3>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <label for="casinoToggle" style="font-weight: 600; color: #555;">Enable Casino for Users:</label>
                    <div style="position: relative; display: inline-block;">
                        <input type="checkbox" id="casinoToggle" style="display: none;" onchange="toggleCasino()">
                        <label for="casinoToggle" class="casino-slider">
                            <span class="casino-slider-button"></span>
                        </label>
                    </div>
                    <span id="casinoStatus" style="font-weight: 600; color: #28a745;">Enabled</span>
                </div>
                <p style="margin-top: 0.5rem; color: #666; font-size: 0.9rem;">
                    When disabled, users under this operator will not see the casino button on the sports betting page.
                </p>
            </div>
            
            <button class="btn btn-primary" onclick="refreshEvents()">🔄 Refresh Events</button>
            
            <!-- Events Table - Using the working pattern from superadmin -->
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
                                Total Liability <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 6)" style="cursor: pointer;">
                                Revenue <span class="sort-icon">↕</span>
                            </th>
                            <th onclick="sortTable('events-table', 7)" style="cursor: pointer;">
                                Status <span class="sort-icon">↕</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody id="events-table-body">
                        <!-- Events will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- User Management Tab -->
        <div id="user-management" class="tab-content">
            <h2>User Management</h2>
            <button class="btn btn-primary" onclick="refreshUsers()">🔄 Refresh Users</button>
            
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Balance</th>
                        <th>Total Bets</th>
                        <th>Total Staked</th>
                        <th>Payout</th>
                        <th>Profit</th>
                        <th>Joined</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="users-table">
                    <tr><td colspan="11" class="loading">Loading users...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Reports Tab -->
        <div id="reports" class="tab-content">
            <h2>Reports & Analytics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-bets-report">-</div>
                    <div class="stat-label">Total Bets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-stakes-report">$0</div>
                    <div class="stat-label">Total Stakes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-revenue-report">$0</div>
                    <div class="stat-label">Total Revenue</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="win-rate-report">0%</div>
                    <div class="stat-label">Win Rate</div>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="refreshReports()">🔄 Refresh Reports</button>
            
            <div class="reports-grid">
                <div class="report-card">
                    <div class="report-title">📊 Trading Overview</div>
                    <div id="trading-overview">Loading...</div>
                </div>
                <div class="report-card">
                    <div class="report-title">🏆 Sport Performance</div>
                    <div id="sport-performance">Loading...</div>
                </div>
                <div class="report-card">
                    <div class="report-title">👑 Top Users</div>
                    <div id="top-users">Loading...</div>
                </div>
            </div>
        </div>

        <!-- Report Builder Tab -->
        <div id="report-builder" class="tab-content">
            <h2>🔧 Report Builder</h2>
            <p>Generate custom reports for {{ operator.sportsbook_name }}</p>
            <div style="margin-top: 2rem;">
                <h3>📋 Available Reports</h3>
                <ul style="margin-top: 1rem; line-height: 2;">
                    <li><strong>Betting Summary:</strong> Daily betting activity by sport</li>
                    <li><strong>User Activity:</strong> User statistics and betting behavior</li>
                    <li><strong>Financial Overview:</strong> Daily revenue and financial metrics</li>
                    <li><strong>Sport Performance:</strong> Revenue and performance by sport</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        // Simple variable assignment - using the working pattern from superadmin
        var operatorId = {{ operator_id }};
        var subdomain = '{{ operator.subdomain }}';
        
        console.log('Operator ID:', operatorId);
        console.log('Subdomain:', subdomain);
        
        function showTab(tabName, event) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            if (event && event.target) {
                event.target.classList.add('active');
            }
            
            // Load data for the tab
            if (tabName === 'betting-events') loadBettingEvents();
            if (tabName === 'user-management') loadUsers();
            if (tabName === 'reports') loadReports();
        }
        
        // Simple function to load betting events - using the working pattern from superadmin
        function loadBettingEvents() {
            console.log('Loading betting events...');
            
            // Show loading state
            document.getElementById('events-table-body').innerHTML = '<tr><td colspan="8" class="loading">Loading events...</td></tr>';
            
            fetch('/api/admin/' + subdomain + '/betting-events')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        displayEvents(data.events);
                        // Update summary stats
                        if (document.getElementById('total-events')) {
                            document.getElementById('total-events').textContent = data.total_events || 0;
                        }
                        if (document.getElementById('active-events')) {
                            document.getElementById('active-events').textContent = data.active_events || 0;
                        }
                        if (document.getElementById('total-liability')) {
                            document.getElementById('total-liability').textContent = '$' + (data.total_liability || 0).toFixed(2);
                        }
                        if (document.getElementById('total-revenue-events')) {
                            document.getElementById('total-revenue-events').textContent = '$' + (data.total_max_possible_gain || 0).toFixed(2);
                        }
                    } else {
                        document.getElementById('events-table-body').innerHTML = '<tr><td colspan="8" class="error">Error loading events: ' + data.error + '</td></tr>';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('events-table-body').innerHTML = '<tr><td colspan="8" class="error">Failed to load events</td></tr>';
                });
        }
        
        // Simple function to display events - using the working pattern from superadmin
        function displayEvents(events) {
            const tbody = document.getElementById('events-table-body');
            tbody.innerHTML = '';

            if (events.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="no-data">No events found</td></tr>';
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
                    <td data-sort="${event.max_liability}">$${Math.abs(event.max_liability || 0).toFixed(2)}</td>
                    <td data-sort="${event.max_possible_gain}">$${Math.abs(event.max_possible_gain || 0).toFixed(2)}</td>
                    <td data-sort="${event.status}"><span class="status-active">${event.status}</span></td>
                `;
                tbody.appendChild(row);
            });
        }
        
        function loadUsers() {
            fetch('/api/admin/' + subdomain + '/users')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('users-table');
                        if (data.users.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="11" style="text-align: center; color: #666;">No users found</td></tr>';
                        } else {
                            tbody.innerHTML = data.users.map(user => `
                                <tr>
                                    <td>${user.id}</td>
                                    <td>${user.username}</td>
                                    <td>${user.email}</td>
                                    <td>$${user.balance.toFixed(2)}</td>
                                    <td>${user.total_bets}</td>
                                    <td>$${user.total_staked.toFixed(2)}</td>
                                    <td>$${user.total_payout.toFixed(2)}</td>
                                    <td>$${user.cumulative_profit.toFixed(2)}</td>
                                    <td>${user.joined}</td>
                                    <td><span class="status-${user.is_active ? 'active' : 'disabled'}">${user.status}</span></td>
                                    <td>
                                        <button class="btn ${user.is_active ? 'btn-danger' : 'btn-success'}" 
                                                onclick="toggleUser(${user.id}, ${user.is_active})">
                                            ${user.is_active ? 'Disable' : 'Enable'}
                                        </button>
                                    </td>
                                </tr>
                            `).join('');
                        }
                    }
                })
                .catch(err => console.error('Error loading users:', err));
        }
        
        function loadReports() {
            fetch('/api/admin/' + subdomain + '/reports')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const stats = data.stats;
                        document.getElementById('total-bets-report').textContent = stats.total_bets;
                        document.getElementById('total-stakes-report').textContent = `$${stats.total_stakes.toFixed(2)}`;
                        document.getElementById('total-revenue-report').textContent = `$${stats.total_revenue.toFixed(2)}`;
                        document.getElementById('win-rate-report').textContent = `${stats.win_rate}%`;
                        
                        // Betting Overview
                        document.getElementById('betting-overview').innerHTML = `
                            <div>Pending Bets: <strong>${stats.pending_bets}</strong></div>
                            <div>Won Bets: <strong>${stats.won_bets}</strong></div>
                            <div>Lost Bets: <strong>${stats.lost_bets}</strong></div>
                        `;
                        
                        // Sport Performance
                        document.getElementById('sport-performance').innerHTML = 
                            data.sport_performance.map(sport => 
                                `<div>${sport.sport}: <strong>$${sport.revenue.toFixed(2)}</strong></div>`
                            ).join('') || '<div>No data available</div>';
                        
                        // Top Users
                        document.getElementById('top-users').innerHTML = 
                            data.top_users.map(user => 
                                `<div>${user.username}: <strong>${user.bets} bets</strong></div>`
                            ).join('') || '<div>No data available</div>';
                    }
                })
                .catch(err => console.error('Error loading reports:', err));
        }
        
        function toggleUser(userId, isActive) {
            fetch('/api/admin/' + subdomain + '/toggle-user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadUsers(); // Refresh the users table
                    alert(data.message);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error toggling user:', err);
                alert('Failed to toggle user status');
            });
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
        
        function refreshEvents() { loadBettingEvents(); }
        function refreshUsers() { loadUsers(); }
        function refreshReports() { loadReports(); }
        
        function logout() {
            if (confirm('Are you sure you want to logout?')) {
                window.location.href = '/admin/logout';
            }
        }
        
        // Casino toggle functionality
        function toggleCasino() {
            const checkbox = document.getElementById('casinoToggle');
            const status = document.getElementById('casinoStatus');
            const isEnabled = checkbox.checked;
            
            // Update status text
            status.textContent = isEnabled ? 'Enabled' : 'Disabled';
            status.style.color = isEnabled ? '#28a745' : '#dc3545';
            
            // Send API request to update casino setting
            fetch('/api/admin/' + subdomain + '/toggle-casino', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ casino_enabled: isEnabled })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    console.log('Casino setting updated:', data.message);
                } else {
                    console.error('Error updating casino setting:', data.error);
                    // Revert the toggle if there was an error
                    checkbox.checked = !isEnabled;
                    status.textContent = !isEnabled ? 'Enabled' : 'Disabled';
                    status.style.color = !isEnabled ? '#28a745' : '#dc3545';
                    alert('Error updating casino setting: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error updating casino setting:', err);
                // Revert the toggle if there was an error
                checkbox.checked = !isEnabled;
                status.textContent = !isEnabled ? 'Enabled' : 'Disabled';
                status.style.color = !isEnabled ? '#28a745' : '#dc3545';
                alert('Failed to update casino setting');
            });
        }
        
        // Load casino setting on page load
        function loadCasinoSetting() {
            fetch('/api/admin/' + subdomain + '/casino-setting')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const checkbox = document.getElementById('casinoToggle');
                        const status = document.getElementById('casinoStatus');
                        checkbox.checked = data.casino_enabled;
                        status.textContent = data.casino_enabled ? 'Enabled' : 'Disabled';
                        status.style.color = data.casino_enabled ? '#28a745' : '#dc3545';
                    }
                })
                .catch(err => console.error('Error loading casino setting:', err));
        }
        
        // Load initial data
        loadBettingEvents();
        loadCasinoSetting();
    </script>
</body>
</html>
    """

