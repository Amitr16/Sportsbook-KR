"""
Multi-tenant routing system for sportsbook operators
"""

from flask import Blueprint, request, jsonify, session, render_template_string, redirect, send_from_directory
import sqlite3
import os
from functools import wraps

multitenant_bp = Blueprint('multitenant', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def require_admin_auth(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'operator_id' not in session:
            # If it's an API request, return JSON error
            if request.path.startswith('/api/') or request.headers.get('Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'error': 'Authentication required'
                }), 401
            # Otherwise redirect to login
            subdomain = kwargs.get('subdomain', '')
            return redirect(f'/admin/{subdomain}')
        return f(*args, **kwargs)
    return decorated_function

def get_current_operator():
    """Get current operator info from session"""
    if 'operator_id' not in session:
        return None
    
    conn = get_db_connection()
    operator = conn.execute("""
        SELECT id, login, sportsbook_name, subdomain, email, is_active, total_revenue, commission_rate
        FROM sportsbook_operators 
        WHERE id = ?
    """, (session['operator_id'],)).fetchone()
    conn.close()
    
    return dict(operator) if operator else None

def validate_subdomain(subdomain):
    """Validate if subdomain exists and is active"""
    conn = get_db_connection()
    operator = conn.execute(
        "SELECT id, sportsbook_name, is_active FROM sportsbook_operators WHERE subdomain = ?", 
        (subdomain,)
    ).fetchone()
    conn.close()
    
    if not operator:
        return None, "Sportsbook not found"
    
    if not operator['is_active']:
        return None, "This sportsbook is currently disabled"
    
    return dict(operator), None

# Sportsbook customer interface routes - cleaner URL structure
@multitenant_bp.route('/<subdomain>')
@multitenant_bp.route('/<subdomain>/')
def sportsbook_home_clean(subdomain):
    """Serve the customer betting interface for a specific sportsbook - clean URLs"""
    from src.routes.branding import get_operator_branding, generate_custom_css, generate_custom_js
    
    # Get operator branding
    branding = get_operator_branding(subdomain)
    if not branding:
        return "Sportsbook not found or inactive", 404
    
    # Serve the main betting interface with operator branding
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    try:
        html_path = os.path.join(static_folder, 'index.html')
        print(f"📁 Reading HTML file: {html_path}")
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✅ Successfully read HTML file, content length: {len(content)} characters")
        
        operator = branding['operator']
        
        # Replace basic branding
        content = content.replace('GoalServe Sports Betting Platform', f"{operator['name']} - Sports Betting")
        content = content.replace('GoalServe', operator['name'])
        
        # Inject custom CSS
        custom_css = generate_custom_css(branding)
        content = content.replace('</head>', f'{custom_css}</head>')
        
        # Inject custom JavaScript with operator context
        custom_js = generate_custom_js(branding)
        
        # Fix authentication redirects to maintain operator context
        auth_fix_js = f"""
        <script>
        // Override authentication redirects to maintain operator context
        window.OPERATOR_SUBDOMAIN = '{subdomain}';
        
        // Override the original auth functions
        window.showLogin = function() {{ window.location.href = '/{subdomain}/login'; }};
        window.showRegister = function() {{ window.location.href = '/{subdomain}/login'; }};
        
        // Fix the DOMContentLoaded authentication check
        document.addEventListener('DOMContentLoaded', function() {{
            const token = localStorage.getItem('token');
            if (!token) {{ 
                window.location.href = '/{subdomain}/login'; 
                return; 
            }}
            // Continue with normal authentication flow...
        }}, true);
        </script>
        """
        
        content = content.replace('</body>', f'{auth_fix_js}{custom_js}</body>')
        
        return content
        
    except FileNotFoundError:
        print(f"❌ HTML file not found: {html_path}")
        return "Betting interface not found", 500
    except UnicodeDecodeError as e:
        print(f"❌ Unicode decoding error: {e}")
        print(f"❌ File path: {html_path}")
        return f"Error reading betting interface: {str(e)}", 500
    except Exception as e:
        print(f"❌ Unexpected error reading HTML file: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        return f"Error reading betting interface: {str(e)}", 500

# Customer login/register routes
@multitenant_bp.route('/<subdomain>/login')
def sportsbook_login(subdomain):
    """Serve operator-specific login page"""
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return f"Error: {error}", 404
    
    # Serve branded login page
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    try:
        # Create a simple branded login page
        login_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{operator['sportsbook_name']} - Login</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                    color: #ffffff;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0;
                }}
                .login-container {{
                    background: rgba(26, 26, 46, 0.95);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    padding: 2rem;
                    width: 100%;
                    max-width: 400px;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                }}
                .logo {{
                    text-align: center;
                    margin-bottom: 2rem;
                }}
                .logo h1 {{
                    color: #4ade80;
                    font-size: 1.5rem;
                    margin: 0;
                }}
                .form-group {{
                    margin-bottom: 1rem;
                }}
                .form-group label {{
                    display: block;
                    margin-bottom: 0.5rem;
                    color: #e5e7eb;
                }}
                .form-group input {{
                    width: 100%;
                    padding: 0.75rem;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    background: rgba(255, 255, 255, 0.1);
                    color: #ffffff;
                    font-size: 1rem;
                }}
                .form-group input:focus {{
                    outline: none;
                    border-color: #4ade80;
                }}
                .btn {{
                    width: 100%;
                    padding: 0.75rem;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                .btn-primary {{
                    background: #4ade80;
                    color: #000;
                }}
                .btn-primary:hover {{
                    background: #22c55e;
                }}
                .toggle-form {{
                    text-align: center;
                    margin-top: 1rem;
                }}
                .toggle-form a {{
                    color: #4ade80;
                    text-decoration: none;
                }}
                .toggle-form a:hover {{
                    text-decoration: underline;
                }}
                .hidden {{
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div class="login-container">
                <div class="logo">
                    <h1>{operator['sportsbook_name']}</h1>
                    <p>Sports Betting Platform</p>
                </div>
                
                <!-- Login Form -->
                <div id="loginForm">
                    <h2>Login</h2>
                    <form onsubmit="handleLogin(event)">
                        <div class="form-group">
                            <label>Username or Email</label>
                            <input type="text" id="loginUsername" required>
                        </div>
                        <div class="form-group">
                            <label>Password</label>
                            <input type="password" id="loginPassword" required>
                        </div>
                        <button type="submit" class="btn btn-primary">Login</button>
                    </form>
                    <div class="toggle-form">
                        <p>Don't have an account? <a href="#" onclick="showRegisterForm()">Register here</a></p>
                    </div>
                </div>
                
                <!-- Register Form -->
                <div id="registerForm" class="hidden">
                    <h2>Register</h2>
                    <form onsubmit="handleRegister(event)">
                        <div class="form-group">
                            <label>Username</label>
                            <input type="text" id="registerUsername" required>
                        </div>
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" id="registerEmail" required>
                        </div>
                        <div class="form-group">
                            <label>Password</label>
                            <input type="password" id="registerPassword" required>
                        </div>
                        <button type="submit" class="btn btn-primary">Create Account</button>
                    </form>
                    <div class="toggle-form">
                        <p>Already have an account? <a href="#" onclick="showLoginForm()">Login here</a></p>
                    </div>
                </div>
            </div>
            
            <script>
                const SUBDOMAIN = '{subdomain}';
                const OPERATOR_ID = {operator['id']};
                
                function showLoginForm() {{
                    document.getElementById('loginForm').classList.remove('hidden');
                    document.getElementById('registerForm').classList.add('hidden');
                }}
                
                function showRegisterForm() {{
                    document.getElementById('loginForm').classList.add('hidden');
                    document.getElementById('registerForm').classList.remove('hidden');
                }}
                
                async function handleLogin(event) {{
                    event.preventDefault();
                    
                    const username = document.getElementById('loginUsername').value;
                    const password = document.getElementById('loginPassword').value;
                    
                    try {{
                        const response = await fetch(`/api/auth/${{SUBDOMAIN}}/login`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{ username, password }})
                        }});
                        
                        const data = await response.json();
                        
                        if (data.success) {{
                            localStorage.setItem('token', data.token);
                            window.location.href = `/${{SUBDOMAIN}}`;
                        }} else {{
                            alert(data.error || 'Login failed');
                        }}
                    }} catch (error) {{
                        alert('Login failed: ' + error.message);
                    }}
                }}
                
                async function handleRegister(event) {{
                    event.preventDefault();
                    
                    const username = document.getElementById('registerUsername').value;
                    const email = document.getElementById('registerEmail').value;
                    const password = document.getElementById('registerPassword').value;
                    
                    try {{
                        const response = await fetch(`/api/auth/${{SUBDOMAIN}}/register`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{ username, email, password }})
                        }});
                        
                        const data = await response.json();
                        
                        if (data.success) {{
                            alert(data.message);
                            showLoginForm();
                        }} else {{
                            alert(data.error || 'Registration failed');
                        }}
                    }} catch (error) {{
                        alert('Registration failed: ' + error.message);
                    }}
                }}
            </script>
        </body>
        </html>
        """
        
        return login_html
        
    except Exception as e:
        return f"Error loading login page: {str(e)}", 500

# Admin interface routes
@multitenant_bp.route('/<subdomain>/admin')
def sportsbook_admin_clean(subdomain):
    """Serve operator-specific admin login page"""
    return redirect(f'/admin/{subdomain}')

# Legacy routes for backward compatibility
@multitenant_bp.route('/sportsbook/<subdomain>')
@multitenant_bp.route('/sportsbook/<subdomain>/')
def sportsbook_home_legacy(subdomain):
    """Legacy route - redirect to clean URL"""
    return redirect(f'/{subdomain}')

# Sportsbook customer interface routes - original
@multitenant_bp.route('/sportsbook/<subdomain>')
@multitenant_bp.route('/sportsbook/<subdomain>/')
def sportsbook_home(subdomain):
    """Serve the customer betting interface for a specific sportsbook"""
    from src.routes.branding import get_operator_branding, generate_custom_css, generate_custom_js
    
    # Get operator branding
    branding = get_operator_branding(subdomain)
    if not branding:
        return "Sportsbook not found or inactive", 404
    
    # Serve the main betting interface with operator branding
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    try:
        html_path = os.path.join(static_folder, 'index.html')
        print(f"📁 Reading HTML file: {html_path}")
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✅ Successfully read HTML file, content length: {len(content)} characters")
        
        operator = branding['operator']
        
        # Replace basic branding
        content = content.replace('GoalServe Sports Betting Platform', f"{operator['name']} - Sports Betting")
        content = content.replace('GoalServe', operator['name'])
        
        # Inject custom CSS
        custom_css = generate_custom_css(branding)
        content = content.replace('</head>', f'{custom_css}</head>')
        
        # Inject custom JavaScript
        custom_js = generate_custom_js(branding)
        content = content.replace('</body>', f'{custom_js}</body>')
        
        return content
        
    except FileNotFoundError:
        print(f"❌ HTML file not found: {html_path}")
        return "Betting interface not found", 500
    except UnicodeDecodeError as e:
        print(f"❌ Unicode decoding error: {e}")
        print(f"❌ File path: {html_path}")
        return f"Error reading betting interface: {str(e)}", 500
    except Exception as e:
        print(f"❌ Unexpected error reading HTML file: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        return f"Error reading betting interface: {str(e)}", 500

# Admin dashboard routes
@multitenant_bp.route('/admin/<subdomain>/dashboard')
@require_admin_auth
def admin_dashboard(subdomain):
    """Admin dashboard for specific sportsbook"""
    operator = get_current_operator()
    if not operator or operator['subdomain'] != subdomain:
        session.clear()
        return redirect(f'/admin/{subdomain}')
    
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, operator=operator)

@multitenant_bp.route('/api/admin/<subdomain>/stats')
@require_admin_auth
def get_admin_stats(subdomain):
    """Get admin statistics (tenant-filtered)"""
    try:
        operator = get_current_operator()
        if not operator or operator['subdomain'] != subdomain:
            return jsonify({'success': False, 'error': 'Invalid operator'}), 403
        
        operator_id = operator['id']
        conn = get_db_connection()
        
        # Get user count
        user_count = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE sportsbook_operator_id = ?", 
            (operator_id,)
        ).fetchone()['count']
        
        # Get total bets
        total_bets = conn.execute(
            "SELECT COUNT(*) as count FROM bets WHERE sportsbook_operator_id = ?", 
            (operator_id,)
        ).fetchone()['count']
        
        # Get pending bets
        pending_bets = conn.execute(
            "SELECT COUNT(*) as count FROM bets WHERE status = 'pending' AND sportsbook_operator_id = ?", 
            (operator_id,)
        ).fetchone()['count']
        
        # Get total revenue (sum of stakes from lost bets minus payouts from won bets)
        revenue_data = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'lost' THEN stake ELSE 0 END) as total_stakes_lost,
                SUM(CASE WHEN status = 'won' THEN actual_return ELSE 0 END) as total_payouts
            FROM bets 
            WHERE sportsbook_operator_id = ?
        """, (operator_id,)).fetchone()
        
        total_stakes_lost = revenue_data['total_stakes_lost'] or 0
        total_payouts = revenue_data['total_payouts'] or 0
        total_revenue = total_stakes_lost - total_payouts
        
        # Get today's stats
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        today_bets = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bets 
            WHERE DATE(created_at) = ? AND sportsbook_operator_id = ?
        """, (today, operator_id)).fetchone()['count']
        
        today_revenue = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'lost' THEN stake ELSE 0 END) as stakes_lost,
                SUM(CASE WHEN status = 'won' THEN actual_return ELSE 0 END) as payouts
            FROM bets 
            WHERE DATE(created_at) = ? AND sportsbook_operator_id = ?
        """, (today, operator_id)).fetchone()
        
        today_stakes_lost = today_revenue['stakes_lost'] or 0
        today_payouts = today_revenue['payouts'] or 0
        today_net_revenue = today_stakes_lost - today_payouts
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'user_count': user_count,
                'total_bets': total_bets,
                'pending_bets': pending_bets,
                'total_revenue': round(total_revenue, 2),
                'today_bets': today_bets,
                'today_revenue': round(today_net_revenue, 2)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@multitenant_bp.route('/api/admin/<subdomain>/users')
@require_admin_auth
def get_users(subdomain):
    """Get users list (tenant-filtered)"""
    try:
        operator = get_current_operator()
        if not operator or operator['subdomain'] != subdomain:
            return jsonify({'success': False, 'error': 'Invalid operator'}), 403
        
        operator_id = operator['id']
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        conn = get_db_connection()
        
        # Build query with search
        base_query = "FROM users WHERE sportsbook_operator_id = ?"
        params = [operator_id]
        
        if search:
            base_query += " AND (username LIKE ? OR email LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        # Get total count
        total_count = conn.execute(f"SELECT COUNT(*) as count {base_query}", params).fetchone()['count']
        
        # Get paginated results
        offset = (page - 1) * per_page
        users = conn.execute(f"""
            SELECT id, username, email, balance, created_at, last_login, is_active
            {base_query}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'users': [dict(user) for user in users],
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

@multitenant_bp.route('/api/admin/<subdomain>/bets')
@require_admin_auth
def get_bets(subdomain):
    """Get bets list (tenant-filtered)"""
    try:
        operator = get_current_operator()
        if not operator or operator['subdomain'] != subdomain:
            return jsonify({'success': False, 'error': 'Invalid operator'}), 403
        
        operator_id = operator['id']
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status', '').strip()
        
        conn = get_db_connection()
        
        # Build query with filters
        base_query = """
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.sportsbook_operator_id = ?
        """
        params = [operator_id]
        
        if status:
            base_query += " AND b.status = ?"
            params.append(status)
        
        # Get total count
        total_count = conn.execute(f"SELECT COUNT(*) as count {base_query}", params).fetchone()['count']
        
        # Get paginated results
        offset = (page - 1) * per_page
        bets = conn.execute(f"""
            SELECT 
                b.id, b.match_name, b.selection, b.stake, b.odds, 
                b.potential_return, b.status, b.created_at, b.settled_at,
                u.username
            {base_query}
            ORDER BY b.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'bets': [dict(bet) for bet in bets],
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

# Admin Dashboard HTML Template
ADMIN_DASHBOARD_TEMPLATE = """
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8fafc;
            color: #334155;
        }

        .header {
            background: white;
            border-bottom: 1px solid #e2e8f0;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
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
            background: linear-gradient(135deg, #4ade80, #22c55e);
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
        }

        .logout-btn:hover {
            background: #dc2626;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .page-title {
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: #1e293b;
        }

        .page-subtitle {
            color: #64748b;
            margin-bottom: 2rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }

        .stat-title {
            font-size: 0.875rem;
            font-weight: 500;
            color: #64748b;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #1e293b;
        }

        .stat-change {
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }

        .stat-change.positive {
            color: #059669;
        }

        .stat-change.negative {
            color: #dc2626;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }

        .section {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }

        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
        }

        .table th,
        .table td {
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid #e2e8f0;
        }

        .table th {
            font-weight: 600;
            color: #374151;
            background: #f8fafc;
        }

        .status-badge {
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .status-pending {
            background: #fef3c7;
            color: #92400e;
        }

        .status-won {
            background: #d1fae5;
            color: #065f46;
        }

        .status-lost {
            background: #fee2e2;
            color: #991b1b;
        }

        .loading {
            text-align: center;
            padding: 2rem;
            color: #64748b;
        }

        @media (max-width: 768px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <div class="logo-icon">⚽</div>
            <span>{{ operator.sportsbook_name }}</span>
        </div>
        <div class="user-info">
            <span>Welcome, {{ operator.login }}</span>
            <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
    </div>

    <div class="container">
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Overview of your sportsbook operations</p>

        <div class="stats-grid" id="statsGrid">
            <div class="loading">Loading statistics...</div>
        </div>

        <div class="content-grid">
            <div class="section">
                <h2 class="section-title">Recent Users</h2>
                <div id="recentUsers" class="loading">Loading users...</div>
            </div>

            <div class="section">
                <h2 class="section-title">Recent Bets</h2>
                <div id="recentBets" class="loading">Loading bets...</div>
            </div>
        </div>
    </div>

    <script>
        const subdomain = '{{ operator.subdomain }}';
        
        // Load dashboard data
        async function loadDashboard() {
            try {
                // Load stats
                const statsResponse = await fetch(`/api/admin/${subdomain}/stats`);
                const statsData = await statsResponse.json();
                
                if (statsData.success) {
                    displayStats(statsData.stats);
                }

                // Load recent users
                const usersResponse = await fetch(`/api/admin/${subdomain}/users?per_page=5`);
                const usersData = await usersResponse.json();
                
                if (usersData.success) {
                    displayRecentUsers(usersData.users);
                }

                // Load recent bets
                const betsResponse = await fetch(`/api/admin/${subdomain}/bets?per_page=5`);
                const betsData = await betsResponse.json();
                
                if (betsData.success) {
                    displayRecentBets(betsData.bets);
                }

            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }

        function displayStats(stats) {
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-title">Total Users</div>
                    <div class="stat-value">${stats.user_count}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Total Bets</div>
                    <div class="stat-value">${stats.total_bets}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Pending Bets</div>
                    <div class="stat-value">${stats.pending_bets}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Total Revenue</div>
                    <div class="stat-value">$${stats.total_revenue}</div>
                    <div class="stat-change">Today: $${stats.today_revenue}</div>
                </div>
            `;
        }

        function displayRecentUsers(users) {
            const container = document.getElementById('recentUsers');
            
            if (users.length === 0) {
                container.innerHTML = '<p>No users yet</p>';
                return;
            }

            const table = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Balance</th>
                            <th>Joined</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${users.map(user => `
                            <tr>
                                <td>${user.username}</td>
                                <td>$${user.balance}</td>
                                <td>${new Date(user.created_at).toLocaleDateString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = table;
        }

        function displayRecentBets(bets) {
            const container = document.getElementById('recentBets');
            
            if (bets.length === 0) {
                container.innerHTML = '<p>No bets yet</p>';
                return;
            }

            const table = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Stake</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bets.map(bet => `
                            <tr>
                                <td>${bet.username}</td>
                                <td>$${bet.stake}</td>
                                <td><span class="status-badge status-${bet.status}">${bet.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = table;
        }

        async function logout() {
            try {
                await fetch('/api/admin-logout', { method: 'POST' });
                window.location.href = `/admin/${subdomain}`;
            } catch (error) {
                console.error('Logout error:', error);
                window.location.href = `/admin/${subdomain}`;
            }
        }

        // Load dashboard on page load
        loadDashboard();
    </script>
</body>
</html>
"""

