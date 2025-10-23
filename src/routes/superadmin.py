"""
Super Admin routes and dashboard for global management
"""

from flask import Blueprint, request, jsonify, session, render_template_string, redirect
from werkzeug.security import check_password_hash, generate_password_hash
from src import sqlite3_shim as sqlite3
from src.auth.session_utils import log_out_superadmin
from datetime import datetime, timedelta
from functools import wraps
import json

superadmin_bp = Blueprint('superadmin', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection - now uses PostgreSQL via sqlite3_shim with tracking"""
    from src.utils.connection_tracker import track_connection_acquired
    
    # Track this connection acquisition
    context, track_start = track_connection_acquired("superadmin.py::get_db_connection")
    from src.db_compat import connect
    conn = connect(use_pool=True, _skip_tracking=True)  # Skip tracking since we track manually
    conn.row_factory = sqlite3.Row
    conn._tracking_context = context
    conn._tracking_start = track_start
    return conn

def require_superadmin_auth(f):
    """Decorator to require super admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from src.auth.session_utils import is_superadmin_logged_in
        if not is_superadmin_logged_in():
            # If it's an API request, return JSON error
            if request.path.startswith('/api/') or request.headers.get('Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'error': 'Super admin authentication required'
                }), 401
            # Otherwise redirect to login
            return redirect('/superadmin')
        return f(*args, **kwargs)
    return decorated_function

@superadmin_bp.route('/superadmin')
@superadmin_bp.route('/superadmin/')
def superadmin_login_page():
    """Super admin login page"""
    # Check if already logged in
    from src.auth.session_utils import is_superadmin_logged_in
    if is_superadmin_logged_in():
        return redirect('/superadmin/rich-dashboard')  # Redirect to rich dashboard
    
    return render_template_string(SUPERADMIN_LOGIN_TEMPLATE)

@superadmin_bp.route('/api/superadmin/login', methods=['POST'])
def superadmin_login():
    """Super admin login endpoint"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        conn = get_db_connection()
        
        # Find super admin by username
        superadmin = conn.execute("""
            SELECT id, username, password_hash, email, is_active, last_login
            FROM super_admins 
            WHERE username = ?
        """, (username,)).fetchone()
        
        if not superadmin:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Invalid login credentials'
            }), 401
        
        if not superadmin['is_active']:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Your account has been disabled'
            }), 401
        
        # Verify password
        if not check_password_hash(superadmin['password_hash'], password):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Invalid login credentials'
            }), 401
        
        # Update last login
        conn.execute("""
            UPDATE super_admins 
            SET last_login = ? 
            WHERE id = ?
        """, (datetime.utcnow(), superadmin['id']))
        conn.commit()
        conn.close()
        
        # Store in session with namespaced key
        from src.auth.session_utils import log_in_superadmin
        log_in_superadmin({
            'id': superadmin['id'],
            'username': superadmin['username'],
            'email': superadmin['email']
        })
        
        return jsonify({
            'success': True,
            'message': 'Login successful'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Login failed: {str(e)}'
        }), 500

@superadmin_bp.route('/api/superadmin/logout', methods=['POST'])
def superadmin_logout():
    """Super admin logout endpoint"""
    log_out_superadmin()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200

@superadmin_bp.route('/superadmin/logout')
def superadmin_logout_redirect():
    """Super admin logout redirect endpoint"""
    log_out_superadmin()
    return redirect('/superadmin')

@superadmin_bp.route('/superadmin/dashboard')
@require_superadmin_auth
def superadmin_dashboard():
    """Super admin dashboard"""
    return render_template_string(SUPERADMIN_DASHBOARD_TEMPLATE)

@superadmin_bp.route('/api/superadmin/stats')
@require_superadmin_auth
def get_global_stats():
    """Get global statistics across all operators"""
    try:
        conn = get_db_connection()
        
        # Get total operators
        total_operators = conn.execute(
            "SELECT COUNT(*) as count FROM sportsbook_operators"
        ).fetchone()['count']
        
        # Get active operators
        active_operators = conn.execute(
            "SELECT COUNT(*) as count FROM sportsbook_operators WHERE is_active = TRUE"
        ).fetchone()['count']
        
        # Get total users across all operators
        total_users = conn.execute(
            "SELECT COUNT(*) as count FROM users"
        ).fetchone()['count']
        
        # Get total bets across all operators
        total_bets = conn.execute(
            "SELECT COUNT(*) as count FROM bets"
        ).fetchone()['count']
        
        # Get pending bets across all operators
        pending_bets = conn.execute(
            "SELECT COUNT(*) as count FROM bets WHERE status = 'pending'"
        ).fetchone()['count']
        
        # Get global revenue (sum of stakes from lost bets minus payouts from won bets)
        revenue_data = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'lost' THEN stake ELSE 0 END) as total_stakes_lost,
                SUM(CASE WHEN status = 'won' THEN actual_return ELSE 0 END) as total_payouts
            FROM bets
        """).fetchone()
        
        total_stakes_lost = revenue_data['total_stakes_lost'] or 0
        total_payouts = revenue_data['total_payouts'] or 0
        global_revenue = total_stakes_lost - total_payouts
        
        # Get today's stats
        today = datetime.now().strftime('%Y-%m-%d')
        today_bets = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bets 
            WHERE DATE(created_at) = ?
        """, (today,)).fetchone()['count']
        
        today_revenue = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'lost' THEN stake ELSE 0 END) as stakes_lost,
                SUM(CASE WHEN status = 'won' THEN actual_return ELSE 0 END) as payouts
            FROM bets 
            WHERE DATE(created_at) = ?
        """, (today,)).fetchone()
        
        today_stakes_lost = today_revenue['stakes_lost'] or 0
        today_payouts = today_revenue['payouts'] or 0
        today_net_revenue = today_stakes_lost - today_payouts
        
        # Get new operators this month
        current_month = datetime.now().strftime('%Y-%m')
        new_operators_this_month = conn.execute("""
            SELECT COUNT(*) as count 
            FROM sportsbook_operators 
            WHERE strftime('%Y-%m', created_at) = ?
        """, (current_month,)).fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_operators': total_operators,
                'active_operators': active_operators,
                'total_users': total_users,
                'total_bets': total_bets,
                'pending_bets': pending_bets,
                'global_revenue': round(global_revenue, 2),
                'today_bets': today_bets,
                'today_revenue': round(today_net_revenue, 2),
                'new_operators_this_month': new_operators_this_month
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/global-users')
@require_superadmin_auth
def get_global_users():
    """Get list of all users across all operators"""
    try:
        conn = get_db_connection()
        
        users = conn.execute("""
            SELECT 
                u.id, u.username, u.email, u.balance, u.is_active, u.created_at,
                so.sportsbook_name as operator_name,
                COUNT(b.id) as total_bets,
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost', 'void') THEN b.stake ELSE 0 END), 0) as total_staked,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as total_payout,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) - 
                COALESCE(SUM(CASE WHEN b.status IN ('won', 'lost', 'void') THEN b.stake ELSE 0 END), 0) as profit
            FROM users u
            LEFT JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
            LEFT JOIN bets b ON u.id = b.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """).fetchall()
        
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
            'success': True,
            'users': processed_users
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/global-reports/overview')
@require_superadmin_auth
def get_global_reports_overview():
    """Get global reports overview across all operators"""
    try:
        conn = get_db_connection()
        
        # Get overall statistics
        stats = conn.execute("""
            SELECT 
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT b.id) as total_bets,
                COALESCE(SUM(b.stake), 0) as total_staked,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as total_payouts,
                COALESCE(SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END), 0) as total_stakes_lost,
                COUNT(DISTINCT so.id) as total_operators
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id
            CROSS JOIN sportsbook_operators so
        """).fetchone()
        
        # Get daily stats for last 7 days
        daily_stats = conn.execute("""
            SELECT 
                DATE(b.created_at) as date,
                COUNT(b.id) as bet_count,
                COALESCE(SUM(b.stake), 0) as total_stake,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as payouts
            FROM bets b
            WHERE b.created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(b.created_at)
            ORDER BY date DESC
        """).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'overview': dict(stats),
            'daily_stats': [dict(day) for day in daily_stats]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/operators')
@require_superadmin_auth
def get_operators():
    """Get list of all sportsbook operators"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        conn = get_db_connection()
        
        # Build query with search
        base_query = "FROM sportsbook_operators"
        params = []
        
        if search:
            base_query += " WHERE (sportsbook_name LIKE ? OR login LIKE ? OR email LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        # Get total count
        total_count = conn.execute(f"SELECT COUNT(*) as count {base_query}", params).fetchone()['count']
        
        # Get paginated results with revenue data
        offset = (page - 1) * per_page
        operators = conn.execute(f"""
            SELECT 
                so.id, so.sportsbook_name, so.login, so.email, so.subdomain,
                so.is_active, so.created_at, so.last_login, so.total_revenue,
                COUNT(u.id) as user_count,
                COUNT(b.id) as bet_count,
                COALESCE(SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as calculated_revenue
            {base_query}
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN bets b ON so.id = b.sportsbook_operator_id
            GROUP BY so.id
            ORDER BY so.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'operators': [dict(operator) for operator in operators],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/operators/<int:operator_id>/toggle', methods=['POST'])
@require_superadmin_auth
def toggle_operator_status(operator_id):
    """Enable or disable a sportsbook operator"""
    try:
        conn = get_db_connection()
        
        # Get current status
        operator = conn.execute(
            "SELECT is_active, sportsbook_name FROM sportsbook_operators WHERE id = ?", 
            (operator_id,)
        ).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404
        
        # Toggle status
        new_status = not operator['is_active']
        conn.execute(
            "UPDATE sportsbook_operators SET is_active = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.utcnow(), operator_id)
        )
        conn.commit()
        conn.close()
        
        action = "enabled" if new_status else "disabled"
        return jsonify({
            'success': True,
            'message': f'Operator "{operator["sportsbook_name"]}" has been {action}',
            'is_active': new_status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/operators/<int:operator_id>/reset-password', methods=['POST'])
@require_superadmin_auth
def reset_operator_password(operator_id):
    """Reset password for a sportsbook operator"""
    try:
        data = request.get_json()
        new_password = data.get('new_password', '').strip()
        
        if not new_password or len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        conn = get_db_connection()
        
        # Check if operator exists
        operator = conn.execute(
            "SELECT sportsbook_name FROM sportsbook_operators WHERE id = ?", 
            (operator_id,)
        ).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404
        
        # Update password
        password_hash = generate_password_hash(new_password)
        conn.execute(
            "UPDATE sportsbook_operators SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, datetime.utcnow(), operator_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Password reset for operator "{operator["sportsbook_name"]}"'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/api/superadmin/export-pending-bets')
@require_superadmin_auth
def export_pending_bets():
    """Export all pending bets to CSV"""
    try:
        from src.models.betting import Bet, User
        from src import db
        import csv
        import io
        from datetime import datetime
        
        # Query pending bets with user information
        pending_bets = db.session.query(Bet, User).join(
            User, Bet.user_id == User.id
        ).filter(
            Bet.status == 'pending'
        ).order_by(Bet.created_at.desc()).all()
        
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
        for bet, user in pending_bets:
            # Parse combo_selections if it's JSON
            combo_selections_str = ""
            if bet.combo_selections:
                try:
                    combo_data = json.loads(bet.combo_selections)
                    combo_selections_str = json.dumps(combo_data, indent=2)
                except:
                    combo_selections_str = str(bet.combo_selections)
            
            row = [
                bet.id,
                bet.user_id,
                user.username or 'N/A',
                user.email or 'N/A',
                bet.match_id or 'N/A',
                bet.match_name or 'N/A',
                bet.selection or 'N/A',
                bet.bet_selection or 'N/A',
                bet.stake or 0,
                bet.odds or 0,
                combo_selections_str,
                bet.created_at.isoformat() if bet.created_at else 'N/A',
                bet.updated_at.isoformat() if bet.updated_at else 'N/A'
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

@superadmin_bp.route('/api/superadmin/revenue-by-operator')
@require_superadmin_auth
def get_revenue_by_operator():
    """Get revenue breakdown by operator"""
    try:
        conn = get_db_connection()
        
        revenue_data = conn.execute("""
            SELECT 
                so.sportsbook_name,
                so.subdomain,
                COUNT(b.id) as total_bets,
                COALESCE(SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END), 0) as total_stakes_lost,
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as total_payouts,
                COALESCE(SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END), 0) as net_revenue
            FROM sportsbook_operators so
            LEFT JOIN bets b ON so.id = b.sportsbook_operator_id
            WHERE so.is_active = TRUE
            GROUP BY so.id
            ORDER BY net_revenue DESC
        """).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'revenue_data': [dict(row) for row in revenue_data]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@superadmin_bp.route('/superadmin/rich-dashboard')
@require_superadmin_auth
def rich_dashboard():
    """Rich dashboard with manual settlement functionality"""
    return render_template_string(RICH_DASHBOARD_TEMPLATE)

# Super Admin Login Template
SUPERADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Super Admin Login - GoalServe</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        }

        .logo {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #f59e0b, #d97706);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
        }

        .logo-text {
            font-size: 24px;
            font-weight: bold;
            color: #f59e0b;
        }

        .login-title {
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #ffffff;
        }

        .login-subtitle {
            text-align: center;
            color: #94a3b8;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            font-weight: 600;
            color: #e2e8f0;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .form-input {
            width: 100%;
            padding: 15px 20px;
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            font-size: 16px;
            background: rgba(255, 255, 255, 0.05);
            color: #ffffff;
            transition: all 0.3s ease;
        }

        .form-input:focus {
            outline: none;
            border-color: #f59e0b;
            box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1);
            background: rgba(255, 255, 255, 0.1);
        }

        .form-input::placeholder {
            color: #64748b;
        }

        .login-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 20px;
        }

        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(245, 158, 11, 0.3);
        }

        .login-btn:active {
            transform: translateY(0);
        }

        .login-btn:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }

        .alert {
            padding: 15px 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-weight: 500;
            display: none;
        }

        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .footer {
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: #64748b;
            font-size: 12px;
        }

        @media (max-width: 768px) {
            .login-container {
                padding: 30px 20px;
                margin: 10px;
            }

            .login-title {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <div class="logo-text">GoalServe</div>
        </div>
        
        <h1 class="login-title">Super Admin</h1>
        <p class="login-subtitle">Global platform management</p>

        <div id="alert" class="alert"></div>

        <form id="loginForm">
            <div class="form-group">
                <label for="username" class="form-label">Username</label>
                <input 
                    type="text" 
                    id="username" 
                    name="username" 
                    class="form-input" 
                    placeholder="Enter your username"
                    required
                >
            </div>

            <div class="form-group">
                <label for="password" class="form-label">Password</label>
                <input 
                    type="password" 
                    id="password" 
                    name="password" 
                    class="form-input" 
                    placeholder="Enter your password"
                    required
                >
            </div>

            <button type="submit" class="login-btn" id="loginBtn">
                <span id="btnText">Sign In</span>
                <span id="btnLoading" class="loading" style="display: none;"></span>
            </button>
        </form>

        <div class="footer">
            <p>GoalServe Super Admin Panel</p>
        </div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const loginBtn = document.getElementById('loginBtn');
            const btnText = document.getElementById('btnText');
            const btnLoading = document.getElementById('btnLoading');
            const alert = document.getElementById('alert');
            
            // Show loading state
            loginBtn.disabled = true;
            btnText.style.display = 'none';
            btnLoading.style.display = 'inline-block';
            alert.style.display = 'none';
            
            // Get form data
            const formData = new FormData(this);
            const data = {
                username: formData.get('username'),
                password: formData.get('password')
            };
            
            try {
                const response = await fetch('/api/superadmin/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    // Success - redirect to rich dashboard
                    window.location.href = '/superadmin/rich-dashboard';
                } else {
                    // Error
                    alert.className = 'alert alert-error';
                    alert.textContent = result.error || 'Login failed. Please try again.';
                    alert.style.display = 'block';
                }
                
            } catch (error) {
                console.error('Login error:', error);
                alert.className = 'alert alert-error';
                alert.textContent = 'Network error. Please check your connection and try again.';
                alert.style.display = 'block';
            }
            
            // Reset button state
            loginBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
        });
    </script>
</body>
</html>
"""

# Super Admin Dashboard Template
SUPERADMIN_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Super Admin Dashboard - GoalServe</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f1f5f9;
            color: #334155;
        }

        .header {
            background: white;
            border-bottom: 1px solid #e2e8f0;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 1.25rem;
            font-weight: bold;
            color: #1e293b;
        }

        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #f59e0b, #d97706);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 16px;
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .logout-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s ease;
        }

        .logout-btn:hover {
            background: #dc2626;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .page-title {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #1e293b;
        }

        .page-subtitle {
            color: #64748b;
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }

        .stat-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid #e2e8f0;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }

        .stat-title {
            font-size: 0.875rem;
            font-weight: 600;
            color: #64748b;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }

        .stat-change {
            font-size: 0.875rem;
            font-weight: 500;
        }

        .stat-change.positive {
            color: #059669;
        }

        .stat-change.negative {
            color: #dc2626;
        }

        .content-sections {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }

        .section {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid #e2e8f0;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #1e293b;
        }

        .search-box {
            padding: 0.5rem 1rem;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 14px;
            width: 250px;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
        }

        .table th,
        .table td {
            text-align: left;
            padding: 1rem;
            border-bottom: 1px solid #e2e8f0;
        }

        .table th {
            font-weight: 600;
            color: #374151;
            background: #f8fafc;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .table td {
            color: #4b5563;
        }

        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .status-active {
            background: #d1fae5;
            color: #065f46;
        }

        .status-inactive {
            background: #fee2e2;
            color: #991b1b;
        }

        .action-btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            margin-right: 0.5rem;
            transition: all 0.3s ease;
        }

        .btn-toggle {
            background: #3b82f6;
            color: white;
        }

        .btn-toggle:hover {
            background: #2563eb;
        }

        .btn-reset {
            background: #f59e0b;
            color: white;
        }

        .btn-reset:hover {
            background: #d97706;
        }

        .loading {
            text-align: center;
            padding: 3rem;
            color: #64748b;
            font-size: 1.1rem;
        }

        .revenue-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            border-bottom: 1px solid #e2e8f0;
        }

        .revenue-item:last-child {
            border-bottom: none;
        }

        .revenue-name {
            font-weight: 600;
            color: #1e293b;
        }

        .revenue-amount {
            font-weight: 700;
            font-size: 1.1rem;
        }

        .revenue-positive {
            color: #059669;
        }

        .revenue-negative {
            color: #dc2626;
        }

        /* Manual Settlement Styles */
        .settlement-controls {
            padding: 1rem 0;
        }

        .export-section {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }

        .export-section h3 {
            color: #1e293b;
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .export-section p {
            color: #64748b;
            margin-bottom: 1.5rem;
            line-height: 1.5;
        }

        .export-status {
            margin-top: 1rem;
            padding: 1rem;
            border-radius: 8px;
            font-weight: 500;
        }

        .export-status.success {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            color: #059669;
        }

        .export-status.error {
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #dc2626;
        }

        .export-status.info {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #2563eb;
        }

        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .search-box {
                width: 100%;
                margin-top: 1rem;
            }
            
            .section-header {
                flex-direction: column;
                align-items: stretch;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <span>GoalServe Super Admin</span>
        </div>
        <div class="user-info">
            <span>Global Management</span>
            <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
    </div>

    <div class="container">
        <h1 class="page-title">Super Admin Dashboard</h1>
        <p class="page-subtitle">Global overview and management of all sportsbook operations</p>

        <div class="stats-grid" id="statsGrid">
            <div class="loading">Loading global statistics...</div>
        </div>

        <div class="content-sections">
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Sportsbook Operators</h2>
                    <input type="text" class="search-box" placeholder="Search operators..." id="operatorSearch">
                </div>
                <div id="operatorsTable" class="loading">Loading operators...</div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Revenue by Operator</h2>
                </div>
                <div id="revenueBreakdown" class="loading">Loading revenue data...</div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Manual Settlement</h2>
                </div>
                <div class="settlement-controls">
                    <div class="export-section">
                        <h3>Export Pending Bets</h3>
                        <p>Download all pending bets as a CSV file for manual review and settlement.</p>
                        <button id="exportPendingBetsBtn" class="btn btn-primary">
                            <span class="btn-text">📊 Export Pending Bets</span>
                            <span class="btn-loading" style="display: none;">⏳ Exporting...</span>
                        </button>
                        <div id="exportStatus" class="export-status" style="display: none;"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let operators = [];
        
        // Load dashboard data
        async function loadDashboard() {
            try {
                // Load global stats
                const statsResponse = await fetch('/api/superadmin/stats');
                const statsData = await statsResponse.json();
                
                if (statsData.success) {
                    displayStats(statsData.stats);
                }

                // Load operators
                const operatorsResponse = await fetch('/api/superadmin/operators');
                const operatorsData = await operatorsResponse.json();
                
                if (operatorsData.success) {
                    operators = operatorsData.operators;
                    displayOperators(operators);
                }

                // Load revenue breakdown
                const revenueResponse = await fetch('/api/superadmin/revenue-by-operator');
                const revenueData = await revenueResponse.json();
                
                if (revenueData.success) {
                    displayRevenueBreakdown(revenueData.revenue_data);
                }

            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }

        function displayStats(stats) {
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-title">Total Operators</div>
                    <div class="stat-value">${stats.total_operators}</div>
                    <div class="stat-change">Active: ${stats.active_operators}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Total Users</div>
                    <div class="stat-value">${stats.total_users}</div>
                    <div class="stat-change">Across all platforms</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Total Bets</div>
                    <div class="stat-value">${stats.total_bets}</div>
                    <div class="stat-change">Pending: ${stats.pending_bets}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Global Revenue</div>
                    <div class="stat-value">$${stats.global_revenue}</div>
                    <div class="stat-change ${stats.today_revenue >= 0 ? 'positive' : 'negative'}">Today: $${stats.today_revenue}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">New Operators</div>
                    <div class="stat-value">${stats.new_operators_this_month}</div>
                    <div class="stat-change">This month</div>
                </div>
            `;
        }

        function displayOperators(operatorsList) {
            const container = document.getElementById('operatorsTable');
            
            if (operatorsList.length === 0) {
                container.innerHTML = '<p>No operators found</p>';
                return;
            }

            const table = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>Sportsbook</th>
                            <th>Login</th>
                            <th>Users</th>
                            <th>Bets</th>
                            <th>Revenue</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${operatorsList.map(operator => `
                            <tr>
                                <td>
                                    <div>
                                        <strong>${operator.sportsbook_name}</strong><br>
                                        <small>/admin/${operator.subdomain}</small>
                                    </div>
                                </td>
                                <td>${operator.login}</td>
                                <td>${operator.user_count}</td>
                                <td>${operator.bet_count}</td>
                                <td class="${operator.calculated_revenue >= 0 ? 'revenue-positive' : 'revenue-negative'}">
                                    $${operator.calculated_revenue.toFixed(2)}
                                </td>
                                <td>
                                    <span class="status-badge ${operator.is_active ? 'status-active' : 'status-inactive'}">
                                        ${operator.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td>
                                    <button class="action-btn btn-toggle" onclick="toggleOperator(${operator.id})">
                                        ${operator.is_active ? 'Disable' : 'Enable'}
                                    </button>
                                    <button class="action-btn btn-reset" onclick="resetPassword(${operator.id})">
                                        Reset Password
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = table;
        }

        function displayRevenueBreakdown(revenueData) {
            const container = document.getElementById('revenueBreakdown');
            
            if (revenueData.length === 0) {
                container.innerHTML = '<p>No revenue data available</p>';
                return;
            }

            const items = revenueData.map(item => `
                <div class="revenue-item">
                    <div>
                        <div class="revenue-name">${item.sportsbook_name}</div>
                        <small>${item.total_bets} bets</small>
                    </div>
                    <div class="revenue-amount ${item.net_revenue >= 0 ? 'revenue-positive' : 'revenue-negative'}">
                        $${item.net_revenue.toFixed(2)}
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = items;
        }

        async function toggleOperator(operatorId) {
            try {
                const response = await fetch(`/api/superadmin/operators/${operatorId}/toggle`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Reload operators
                    const operatorsResponse = await fetch('/api/superadmin/operators');
                    const operatorsData = await operatorsResponse.json();
                    
                    if (operatorsData.success) {
                        operators = operatorsData.operators;
                        displayOperators(operators);
                    }
                    
                    alert(result.message);
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                console.error('Error toggling operator:', error);
                alert('Network error occurred');
            }
        }

        async function resetPassword(operatorId) {
            const newPassword = prompt('Enter new password (minimum 8 characters):');
            
            if (!newPassword || newPassword.length < 8) {
                alert('Password must be at least 8 characters long');
                return;
            }
            
            try {
                const response = await fetch(`/api/superadmin/operators/${operatorId}/reset-password`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ new_password: newPassword })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert(result.message);
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                console.error('Error resetting password:', error);
                alert('Network error occurred');
            }
        }

        // Search functionality
        document.getElementById('operatorSearch').addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const filteredOperators = operators.filter(operator => 
                operator.sportsbook_name.toLowerCase().includes(searchTerm) ||
                operator.login.toLowerCase().includes(searchTerm) ||
                (operator.email && operator.email.toLowerCase().includes(searchTerm))
            );
            displayOperators(filteredOperators);
        });

        async function logout() {
            try {
                await fetch('/api/superadmin/logout', { method: 'POST' });
                window.location.href = '/superadmin';
            } catch (error) {
                console.error('Logout error:', error);
                window.location.href = '/superadmin';
            }
        }

        // Export pending bets functionality
        document.getElementById('exportPendingBetsBtn').addEventListener('click', async function() {
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

        // Load dashboard on page load
        loadDashboard();
    </script>
</body>
</html>
"""

# Rich Dashboard Template with Manual Settlement
RICH_DASHBOARD_TEMPLATE = """
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .header {
            background: #ff6b35;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 1.8rem;
            font-weight: 700;
        }

        .nav-bar {
            background: rgba(255, 255, 255, 0.95);
            padding: 1rem 2rem;
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .nav-btn {
            background: #f8f9fa;
            border: 2px solid #e9ecef;
            color: #495057;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .nav-btn:hover {
            background: #e9ecef;
            border-color: #dee2e6;
        }

        .nav-btn.active {
            background: #ff6b35;
            color: white;
            border-color: #ff6b35;
        }

        .container {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 2rem;
        }

        .main-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }

        .card-title {
            font-size: 2rem;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }

        .card-subtitle {
            color: #7f8c8d;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 12px;
            text-align: center;
        }

        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .stat-label {
            font-size: 1rem;
            opacity: 0.9;
        }

        .action-section {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }

        .action-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 1rem;
        }

        .btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }

        .btn:hover {
            background: #218838;
            transform: translateY(-2px);
        }

        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
        }

        .export-section {
            background: #e8f5e8;
            border: 2px solid #28a745;
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1rem;
        }

        .export-title {
            color: #155724;
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .export-desc {
            color: #155724;
            margin-bottom: 1rem;
            opacity: 0.8;
        }

        .export-status {
            margin-top: 1rem;
            padding: 1rem;
            border-radius: 8px;
            font-weight: 500;
            display: none;
        }

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

        .bets-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }

        .bets-table th,
        .bets-table td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }

        .bets-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }

        .bets-table tr:hover {
            background: #f8f9fa;
        }

        .settlement-dropdown {
            padding: 0.5rem;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background: white;
        }

        .settle-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        }

        .settle-btn:hover {
            background: #0056b3;
        }

        .loading {
            text-align: center;
            padding: 2rem;
            color: #6c757d;
        }

        @media (max-width: 768px) {
            .container {
                padding: 0 1rem;
            }
            
            .nav-bar {
                padding: 1rem;
                flex-direction: column;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>GoalServe - Super Admin Dashboard</h1>
    </div>

    <div class="nav-bar">
        <a href="#" class="nav-btn">Global Overview</a>
        <a href="#" class="nav-btn">Global Betting Events</a>
        <a href="#" class="nav-btn active">Manual Settlement</a>
        <a href="#" class="nav-btn">Global User Management</a>
        <a href="#" class="nav-btn">Global Reports</a>
        <a href="#" class="nav-btn">Operator Management</a>
    </div>

    <div class="container">
        <div class="main-card">
            <h2 class="card-title">Global Manual Bet Settlement</h2>
            <p class="card-subtitle">Manually settle pending bets across all operators by setting match outcomes</p>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="totalMatches">-</div>
                    <div class="stat-label">Total Matches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="totalLiability">-</div>
                    <div class="stat-label">Total Liability</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="pendingBets">-</div>
                    <div class="stat-label">Pending Bets</div>
                </div>
            </div>

            <div class="action-section">
                <h3 class="action-title">Settlement Actions</h3>
                <button id="refreshBtn" class="btn">Refresh Settlement Data</button>
                
                <div class="export-section">
                    <h4 class="export-title">📊 Export Pending Bets</h4>
                    <p class="export-desc">Download all pending bets as a CSV file for manual review and settlement.</p>
                    <button id="exportPendingBetsBtn" class="btn">
                        <span class="btn-text">📊 Export Pending Bets</span>
                        <span class="btn-loading" style="display: none;">⏳ Exporting...</span>
                    </button>
                    <div id="exportStatus" class="export-status" style="display: none;"></div>
                </div>
            </div>

            <div id="betsTable" class="loading">Loading pending bets...</div>
        </div>
    </div>

    <script>
        // Load settlement data
        async function loadSettlementData() {
            try {
                // Load global stats
                const statsResponse = await fetch('/api/superadmin/stats');
                const statsData = await statsResponse.json();
                
                if (statsData.success) {
                    document.getElementById('totalMatches').textContent = statsData.total_matches || 0;
                    document.getElementById('totalLiability').textContent = `$${(statsData.total_liability || 0).toFixed(2)}`;
                    document.getElementById('pendingBets').textContent = statsData.pending_bets || 0;
                }
                
                // Load pending bets (mock data for now)
                loadPendingBets();
                
            } catch (error) {
                console.error('Error loading settlement data:', error);
            }
        }

        // Load pending bets
        function loadPendingBets() {
            const tableContainer = document.getElementById('betsTable');
            
            // Mock data - replace with actual API call
            const mockBets = [
                {
                    match: "Combo Bet (5 selections)",
                    operator: "Default Sportsbook",
                    stake: "$19.00",
                    outcome: "Combo: 5 selections",
                    liability: "$861.84"
                },
                {
                    match: "Combo Bet (4 selections)",
                    operator: "Default Sportsbook", 
                    stake: "$10.00",
                    outcome: "Combo: 4 selections",
                    liability: "$141.70"
                },
                {
                    match: "Combo Bet (2 selections)",
                    operator: "Default Sportsbook",
                    stake: "$10.00", 
                    outcome: "Combo: 2 selections",
                    liability: "$27.60"
                },
                {
                    match: "San Diego Padres vs Cincinnati Reds",
                    operator: "megabook",
                    stake: "$10.00",
                    outcome: "Cincinnati Reds", 
                    liability: "$22.50"
                }
            ];

            let tableHTML = `
                <table class="bets-table">
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
                    <tbody>
            `;

            mockBets.forEach(bet => {
                tableHTML += `
                    <tr>
                        <td>${bet.match}</td>
                        <td>${bet.operator}</td>
                        <td>1 bets<br>Total Stake: ${bet.stake}</td>
                        <td>${bet.outcome}</td>
                        <td>${bet.liability}</td>
                        <td>
                            <select class="settlement-dropdown">
                                <option>No Result (Cancel & Refund)</option>
                                <option>Won</option>
                                <option>Lost</option>
                            </select>
                            <br><br>
                            <button class="settle-btn">Settle</button>
                        </td>
                    </tr>
                `;
            });

            tableHTML += `
                    </tbody>
                </table>
            `;

            tableContainer.innerHTML = tableHTML;
        }

        // Export pending bets functionality
        document.getElementById('exportPendingBetsBtn').addEventListener('click', async function() {
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

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', function() {
            loadSettlementData();
        });

        // Load data on page load
        loadSettlementData();
    </script>
</body>
</html>
"""

