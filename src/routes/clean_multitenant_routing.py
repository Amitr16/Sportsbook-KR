"""
Clean multi-tenant routing system with improved URL structure
/<subdomain> - customer betting interface
/<subdomain>/login - customer login/register
/<subdomain>/admin - admin interface
"""

from flask import Blueprint, request, redirect, render_template_string, session
from src import sqlite3_shim as sqlite3
from src.db_compat import connect
from src.auth.session_utils import clear_operator_session
import os
from functools import wraps
from urllib.parse import quote

clean_multitenant_bp = Blueprint('clean_multitenant', __name__)

def get_db_connection():
    """Get database connection with retry mechanism"""
    import time
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            return connect()
        except Exception as e:
            if "PoolClosed" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ Pool closed, retrying connection (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                print(f"❌ Failed to get database connection after {max_retries} attempts: {e}")
                raise

def validate_subdomain(subdomain):
    """Validate subdomain and return operator info"""
    conn = get_db_connection()
    
    operator = conn.execute("""
        SELECT id, sportsbook_name, login, password_hash, subdomain, is_active, email
        FROM sportsbook_operators 
        WHERE subdomain = ?
    """, (subdomain,)).fetchone()
    
    conn.close()
    
    if not operator:
        return None, "Sportsbook not found"
    
    if not operator['is_active']:
        return None, "This sportsbook is currently disabled"
    
    return dict(operator), None

# Customer betting interface - clean URL (works for both authenticated and non-authenticated users)
@clean_multitenant_bp.route('/<subdomain>')
@clean_multitenant_bp.route('/<subdomain>/')
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
        
        # Note: Removed hardcoded login redirects to allow public betting page to work
        # The public betting page handles authentication via bootstrapAuth() function
        
        # Inject custom CSS
        custom_css = generate_custom_css(branding)
        content = content.replace('</head>', f'{custom_css}</head>')
        
        # Authentication is now handled by the frontend bootstrapAuth function
        # No server-side JavaScript injection needed
        auth_fix_js = ""
        
        # Inject custom JavaScript
        custom_js = generate_custom_js(branding)
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

# Customer login/register page
@clean_multitenant_bp.route('/<subdomain>/login')
def sportsbook_login(subdomain):
    """Serve operator-specific login/register page"""
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return f"Error: {error}", 404
    
    # Create a branded login/register page
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
                text-align: center;
            }}
            .logo {{
                font-size: 2rem;
                font-weight: bold;
                margin-bottom: 1rem;
                color: #4ade80;
            }}
            .form-group {{
                margin-bottom: 1rem;
                text-align: left;
            }}
            label {{
                display: block;
                margin-bottom: 0.5rem;
                color: #e2e8f0;
            }}
            input {{
                width: 100%;
                padding: 0.75rem;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                font-size: 1rem;
            }}
            input:focus {{
                outline: none;
                border-color: #4ade80;
                box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.1);
            }}
            button {{
                width: 100%;
                padding: 0.75rem;
                background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
                color: #000000;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(74, 222, 128, 0.3);
            }}
            .error {{
                color: #ef4444;
                margin-top: 0.5rem;
                font-size: 0.875rem;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">{operator['sportsbook_name']}</div>
            <h2>Login</h2>
            <form id="loginForm">
                <div class="form-group">
                    <label for="loginUsername">Username</label>
                    <input type="text" id="loginUsername" required>
                </div>
                <div class="form-group">
                    <label for="loginPassword">Password</label>
                    <input type="password" id="loginPassword" required>
                </div>
                <button type="submit">Login</button>
                <div id="errorMessage" class="error" style="display: none;"></div>
            </form>
        </div>
        
        <script>
            document.getElementById('loginForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
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
                        window.location.href = `/${{SUBDOMAIN}}`;
                    }} else {{
                        document.getElementById('errorMessage').textContent = data.error || 'Login failed';
                        document.getElementById('errorMessage').style.display = 'block';
                    }}
                }} catch (error) {{
                    document.getElementById('errorMessage').textContent = 'Network error. Please try again.';
                    document.getElementById('errorMessage').style.display = 'block';
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return login_html

# Admin interface route
@clean_multitenant_bp.route('/<subdomain>/admin')
def sportsbook_admin(subdomain):
    """Serve rich admin interface directly at /<subdomain>/admin"""
    # Check if admin is authenticated using the correct session keys
    from flask import session
    if not (session.get('operator_id') and session.get('operator_subdomain') == subdomain):
        return redirect(f'/{subdomain}/admin/login')
    
    # Serve the rich admin interface directly
    from src.routes.rich_admin_interface import serve_rich_admin_template
    return serve_rich_admin_template(subdomain)

# Theme customizer for specific operator
@clean_multitenant_bp.route('/<subdomain>/admin/theme-customizer')
def sportsbook_theme_customizer(subdomain):
    """Serve theme customizer for specific operator"""
    from flask import session
    
    # Check if admin is authenticated for this subdomain
    if not (session.get('operator_id') and session.get('operator_subdomain') == subdomain):
        return redirect(f'/{subdomain}/admin/login')
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return f"Error: {error}", 404
    
    # Create theme customizer HTML
    theme_customizer_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{operator['sportsbook_name']} - Theme Customizer</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                color: #ffffff;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 2rem;
            }}
            .logo {{
                font-size: 2rem;
                font-weight: bold;
                color: #4ade80;
                margin-bottom: 0.5rem;
            }}
            .theme-form {{
                background: rgba(26, 26, 46, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 2rem;
                margin-bottom: 2rem;
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
                box-sizing: border-box;
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">{operator['sportsbook_name']}</div>
                <h1>Theme Customizer</h1>
            </div>
            
            <div class="theme-form">
                <h2>Customize Your Sportsbook</h2>
                <form id="themeForm">
                    <div class="form-group">
                        <label for="primaryColor">Primary Color</label>
                        <input type="color" id="primaryColor" value="#4ade80">
                    </div>
                    <div class="form-group">
                        <label for="secondaryColor">Secondary Color</label>
                        <input type="color" id="secondaryColor" value="#22c55e">
                    </div>
                    <div class="form-group">
                        <label for="logoText">Logo Text</label>
                        <input type="text" id="logoText" value="{operator['sportsbook_name']}">
                    </div>
                    <button type="submit" class="btn btn-primary">Save Theme</button>
                </form>
            </div>
        </div>
        
        <script>
            document.getElementById('themeForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                const themeData = {{
                    primaryColor: document.getElementById('primaryColor').value,
                    secondaryColor: document.getElementById('secondaryColor').value,
                    logoText: document.getElementById('logoText').value
                }};
                
                try {{
                    const response = await fetch(`/${{SUBDOMAIN}}/admin/api/theme-save`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(themeData)
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        alert('Theme saved successfully!');
                    }} else {{
                        alert('Error saving theme: ' + data.error);
                    }}
                }} catch (error) {{
                    alert('Network error. Please try again.');
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return theme_customizer_html

# Admin login page
@clean_multitenant_bp.route('/<subdomain>/admin/login')
def sportsbook_admin_login(subdomain):
    """Serve admin login page"""
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return f"Error: {error}", 404
    
    # Simple admin login page
    admin_login_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{operator['sportsbook_name']} - Admin Login</title>
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
                text-align: center;
            }}
            .logo {{
                font-size: 2rem;
                font-weight: bold;
                margin-bottom: 1rem;
                color: #4ade80;
            }}
            .form-group {{
                margin-bottom: 1rem;
                text-align: left;
            }}
            label {{
                display: block;
                margin-bottom: 0.5rem;
                color: #e2e8f0;
            }}
            input {{
                width: 100%;
                padding: 0.75rem;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                font-size: 1rem;
            }}
            input:focus {{
                outline: none;
                border-color: #4ade80;
                box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.1);
            }}
            button {{
                width: 100%;
                padding: 0.75rem;
                background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
                color: #000000;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(74, 222, 128, 0.3);
            }}
            .error {{
                color: #ef4444;
                margin-top: 0.5rem;
                font-size: 0.875rem;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">{operator['sportsbook_name']}</div>
            <h2>Admin Login</h2>
            <form id="adminLoginForm">
                <div class="form-group">
                    <label for="adminUsername">Username</label>
                    <input type="text" id="adminUsername" required>
                </div>
                <div class="form-group">
                    <label for="adminPassword">Password</label>
                    <input type="password" id="adminPassword" required>
                </div>
                <button type="submit">Login</button>
                <div id="errorMessage" class="error" style="display: none;"></div>
            </form>
        </div>
        
        <script>
            document.getElementById('adminLoginForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                const username = document.getElementById('adminUsername').value;
                const password = document.getElementById('adminPassword').value;
                
                try {{
                    const response = await fetch(`/{subdomain}/admin/api/login`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{ username, password }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        window.location.href = `/{subdomain}/admin`;
                    }} else {{
                        document.getElementById('errorMessage').textContent = data.error || 'Login failed';
                        document.getElementById('errorMessage').style.display = 'block';
                    }}
                }} catch (error) {{
                    document.getElementById('errorMessage').textContent = 'Network error. Please try again.';
                    document.getElementById('errorMessage').style.display = 'block';
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return admin_login_html

# Admin login API
@clean_multitenant_bp.route('/<subdomain>/admin/api/login', methods=['POST'])
def admin_login_api(subdomain):
    """Handle admin login"""
    from flask import request, session, jsonify
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return jsonify({'success': False, 'error': 'Operator not found'}), 404
    
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        # Check admin credentials using password hash
        from werkzeug.security import check_password_hash
        if username == operator['login'] and check_password_hash(operator['password_hash'], password):
            # Clear any existing session to avoid conflicts
            session.clear()
            
            # Set admin session with correct keys for /api/auth/me
            session['admin_id'] = f"{operator['id']}:{username}"
            session['operator_id'] = operator['id']
            session['operator_name'] = subdomain
            session['role'] = 'admin'
            
            # Legacy keys for backward compatibility
            session['operator_subdomain'] = subdomain
            session['admin_operator_id'] = operator['id']
            session['admin_subdomain'] = subdomain
            
            session.permanent = True  # Make session persistent
            
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': 'Login failed'}), 500

# Admin logout route
@clean_multitenant_bp.route('/<subdomain>/admin/logout')
def admin_logout(subdomain):
    """Handle admin logout"""
    from flask import session, redirect
    
    # Clear admin session
    session.pop('operator_id', None)
    session.pop('operator_subdomain', None)
    session.pop('admin_operator_id', None)
    session.pop('admin_subdomain', None)
    
    # Redirect to admin login page for this subdomain
    return redirect(f'/{subdomain}/admin/login')
