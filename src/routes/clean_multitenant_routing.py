"""
Clean multi-tenant routing system with improved URL structure
/<subdomain> - customer betting interface
/<subdomain>/login - customer login/register
/<subdomain>/admin - admin interface
"""

from flask import Blueprint, request, redirect, render_template_string, session, jsonify
from src.db_compat import connection_ctx
from src.auth.session_utils import clear_operator_session
from src.utils.rate_limiter import rate_limit_per_tenant
from src.utils.request_coalescing import singleflight_branding
import os
from functools import wraps
from urllib.parse import quote
import time

clean_multitenant_bp = Blueprint('clean_multitenant', __name__)

# Tenant metadata cache for multi-tenant scalability
# Subdomain → operator mapping rarely changes (only when new operators register)
_TENANT_CACHE = {}
_TENANT_CACHE_TTL = 3600  # 1 hour


def validate_subdomain(subdomain):
    """Validate subdomain and return operator info (with aggressive caching)"""
    # Check cache first (subdomain→operator mapping rarely changes)
    cache_key = f"tenant:{subdomain}"
    now = time.time()
    
    if cache_key in _TENANT_CACHE:
        cached_time, cached_data = _TENANT_CACHE[cache_key]
        if now - cached_time < _TENANT_CACHE_TTL:
            return cached_data  # Return (operator, None) or (None, error)
    
    # Cache miss - query DB
    from src.db_compat import connection_ctx
    
    with connection_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, sportsbook_name, login, password_hash, subdomain, is_active, email
                FROM sportsbook_operators 
                WHERE subdomain = %s
            """, (subdomain,))
            operator = cur.fetchone()
    
    if not operator:
        result = (None, "Sportsbook not found")
        _TENANT_CACHE[cache_key] = (now, result)  # Cache negative results too
        return result
    
    if not operator['is_active']:
        result = (None, "This sportsbook is currently disabled")
        _TENANT_CACHE[cache_key] = (now, result)
        return result
    
    result = (dict(operator), None)
    _TENANT_CACHE[cache_key] = (now, result)  # Cache successful result
    return result

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
        
        # CRITICAL: Do NOT do global string replaces - they corrupt JavaScript!
        # Instead, inject branding via safe config block
        
        # Inject API base into meta tag for robust initialization
        api_base = os.getenv('API_BASE_URL', request.host_url.rstrip('/'))
        content = content.replace('<meta name="api-base" content="">', 
                                f'<meta name="api-base" content="{api_base}">')
        
        # Inject custom CSS
        custom_css = generate_custom_css(branding)
        content = content.replace('</head>', f'{custom_css}</head>')
        
        # Inject branding config BEFORE any app scripts (safe injection)
        branding_config = f"""
    <script>
      // Safe branding injection - does not touch JS code
      window.__BRANDING__ = {{
        siteName: "{operator['name']}",
        siteTitle: "{operator['name']} - Sports Betting",
        logoText: "{subdomain}",
        subdomain: "{subdomain}"
      }};
      console.log('🎨 Operator branding initialized for:', window.__BRANDING__.siteName);
    </script>
"""
        
        # Inject custom JavaScript
        custom_js = generate_custom_js(branding)
        content = content.replace('</body>', f'{branding_config}{custom_js}</body>')
        
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

@clean_multitenant_bp.route('/api/<subdomain>/casino-enabled')
def get_casino_enabled(subdomain):
    """Check if casino is enabled for this operator"""
    try:
        operator, error = validate_subdomain(subdomain)
        if not operator:
            return jsonify({'error': error}), 404
        
        # Use safe connection pattern
        from src.db_compat import connection_ctx
        with connection_ctx() as conn:
            with conn.cursor() as cur:
                # Get casino setting for this operator
                cur.execute("""
                    SELECT casino_enabled FROM sportsbook_operators 
                    WHERE id = %s
                """, (operator['id'],))
                casino_setting = cur.fetchone()
        
        if casino_setting:
            return jsonify({
                'success': True,
                'casino_enabled': casino_setting['casino_enabled']
            })
        else:
            return jsonify({'error': 'Operator not found'}), 404
        
    except Exception as e:
        return jsonify({'error': 'Failed to get casino setting'}), 500

# Casino interface - tenant-specific
@clean_multitenant_bp.route('/<subdomain>/casino')
def sportsbook_casino(subdomain):
    """Serve the casino interface for a specific sportsbook"""
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return f"Error: {error}", 404
    
    # Serve the casino frontend
    casino_frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'casino-suite-pro', 'frontend', 'dist', 'index.html')
    
    if not os.path.exists(casino_frontend_path):
        return "Casino frontend not found", 404
    
    try:
        with open(casino_frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the casino title with sportsbook branding
        content = content.replace('KRYZEL CASINO', f"{operator['sportsbook_name']} CASINO")
        
        # Fix asset paths to be tenant-specific
        content = content.replace('/casino/assets/', f'/{subdomain}/casino/assets/')
        content = content.replace('./assets/', f'/{subdomain}/casino/assets/')
        content = content.replace('./css/', f'/{subdomain}/casino/css/')
        content = content.replace('src="./assets/', f'src="./{subdomain}/casino/assets/')
        content = content.replace('href="./assets/', f'href="./{subdomain}/casino/assets/')
        content = content.replace('href="./css/', f'href="./{subdomain}/casino/css/')
        
        return content
        
    except Exception as e:
        return f"Error serving casino: {str(e)}", 500

# Casino static assets - tenant-specific
@clean_multitenant_bp.route('/<subdomain>/casino/assets/<path:filename>')
def casino_assets(subdomain, filename):
    """Serve casino static assets (CSS, JS, images)"""
    print(f"🔍 DEBUG: casino_assets called - subdomain: {subdomain}, filename: {filename}")
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        print(f"❌ DEBUG: Subdomain validation failed - {error}")
        return f"Error: {error}", 404
    
    # Serve casino assets - use absolute path from project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    casino_assets_path = os.path.join(project_root, 'casino-suite-pro', 'frontend', 'dist', 'assets', filename)
    print(f"🔍 DEBUG: Looking for asset at: {casino_assets_path}")
    print(f"🔍 DEBUG: Project root: {project_root}")
    
    if not os.path.exists(casino_assets_path):
        print(f"❌ DEBUG: Asset not found at: {casino_assets_path}")
        return "Asset not found", 404
    
    try:
        from flask import send_file, Response
        import mimetypes
        
        # Set correct MIME type for SVG files
        if filename.endswith('.svg'):
            mimetype = 'image/svg+xml'
        else:
            mimetype = mimetypes.guess_type(filename)[0]
        
        print(f"✅ DEBUG: Serving asset with mimetype: {mimetype}")
        response = send_file(casino_assets_path, mimetype=mimetype)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return f"Error serving asset: {str(e)}", 500

# Casino CSS files - tenant-specific
@clean_multitenant_bp.route('/<subdomain>/casino/css/<path:filename>')
def casino_css(subdomain, filename):
    """Serve casino CSS files"""
    print(f"🔍 DEBUG: casino_css called - subdomain: {subdomain}, filename: {filename}")
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        print(f"❌ DEBUG: Subdomain validation failed - {error}")
        return f"Error: {error}", 404
    
    # Serve casino CSS files - use absolute path from project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    casino_css_path = os.path.join(project_root, 'casino-suite-pro', 'frontend', 'dist', 'css', filename)
    print(f"🔍 DEBUG: Looking for CSS at: {casino_css_path}")
    print(f"🔍 DEBUG: Project root: {project_root}")
    
    if not os.path.exists(casino_css_path):
        print(f"❌ DEBUG: CSS not found at: {casino_css_path}")
        return "CSS file not found", 404
    
    try:
        from flask import send_file
        import mimetypes
        
        mimetype = 'text/css'
        print(f"✅ DEBUG: Serving CSS with mimetype: {mimetype}")
        response = send_file(casino_css_path, mimetype=mimetype)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return f"Error serving CSS: {str(e)}", 500

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
    
    # Read the theme customizer HTML file and customize it for this operator
    import os
    html_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'theme-customizer.html')
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Customize the theme customizer for this specific operator
        # SAFE: Only replace specific title strings, not JavaScript identifiers
        html_content = html_content.replace('GoalServe Platform', f"{operator['sportsbook_name']} Platform")
        html_content = html_content.replace('Your Sportsbook', operator['sportsbook_name'])
        
        # Update API endpoints to be subdomain-specific
        html_content = html_content.replace('/api/load-theme/', f'/api/load-theme/{subdomain}')
        html_content = html_content.replace('/api/save-theme/', f'/api/save-theme/{subdomain}')
        html_content = html_content.replace('/api/theme-css/', f'/api/theme-css/{subdomain}')
        
        # Add subdomain context to JavaScript
        subdomain_js = f"""
        <script>
        // Set subdomain context for theme customizer
        window.OPERATOR_SUBDOMAIN = '{subdomain}';
        window.OPERATOR_NAME = '{operator['sportsbook_name']}';
        
        // Override API calls to use subdomain-specific endpoints
        const originalFetch = window.fetch;
        window.fetch = function(url, options) {{
            if (url.startsWith('/api/save-theme/') && !url.includes('{subdomain}')) {{
                url = `/api/save-theme/{subdomain}`;
            }}
            if (url.startsWith('/api/load-theme/') && !url.includes('{subdomain}')) {{
                url = `/api/load-theme/{subdomain}`;
            }}
            return originalFetch(url, options);
        }};
        </script>
        """
        
        html_content = html_content.replace('</head>', f'{subdomain_js}</head>')
        
        return html_content, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        print(f"Error serving theme customizer: {e}")
        return "Theme customizer not available", 500

# Theme API endpoints for specific operator
@clean_multitenant_bp.route('/<subdomain>/api/save-theme', methods=['POST'])
def save_theme_for_operator(subdomain):
    """Save theme customization for specific operator"""
    from flask import request, jsonify, session
    
    # Check if admin is authenticated for this subdomain
    if not (session.get('operator_id') and session.get('operator_subdomain') == subdomain):
        return jsonify({'error': 'Unauthorized'}), 401
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return jsonify({'error': error}), 404
    
    try:
        print(f"🔍 Starting theme save process for operator: {subdomain}")
        
        # Get theme data from request
        theme_data = request.get_json()
        print(f"🔍 Received theme data: {theme_data}")
        
        if not theme_data:
            return jsonify({'error': 'No theme data provided'}), 400
        
        operator_id = operator['id']
        
        print("🔍 Getting database connection...")
        with connection_ctx() as conn:
            print("✅ Database connection successful")
            
            # Create sportsbook_themes table if it doesn't exist
            print("🔍 Creating sportsbook_themes table if it doesn't exist...")
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sportsbook_themes (
                        id SERIAL PRIMARY KEY,
                        sportsbook_operator_id INTEGER NOT NULL,
                        primary_color TEXT DEFAULT '#1e40af',
                        secondary_color TEXT DEFAULT '#3b82f6',
                        accent_color TEXT DEFAULT '#f59e0b',
                        background_color TEXT DEFAULT '#ffffff',
                        text_color TEXT DEFAULT '#1f2937',
                        font_family TEXT DEFAULT 'Inter, sans-serif',
                        layout_style TEXT DEFAULT 'modern',
                        button_style TEXT DEFAULT 'rounded',
                        card_style TEXT DEFAULT 'shadow',
                        logo_type TEXT DEFAULT 'default',
                        logo_url TEXT,
                        sportsbook_name TEXT DEFAULT 'Your Sportsbook',
                        custom_css TEXT,
                        banner_image_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators (id)
                    )
                ''')
            print("✅ Table creation/check successful")
            
            # Table already has all required columns, no need to add them
            print("✅ Table schema is already correct - all columns exist")
            
            # Check if theme customization already exists for this operator
            print(f"🔍 Checking for existing theme for operator_id: {operator_id}")
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM sportsbook_themes WHERE sportsbook_operator_id = %s', (operator_id,))
                existing = cursor.fetchone()
            print(f"🔍 Existing theme found: {existing is not None}")
        
        if existing:
            # Update existing theme
            cursor.execute('''
                UPDATE sportsbook_themes SET
                    primary_color = ?,
                    secondary_color = ?,
                    accent_color = ?,
                    background_color = ?,
                    text_color = ?,
                    font_family = ?,
                    layout_style = ?,
                    button_style = ?,
                    card_style = ?,
                    logo_type = ?,
                    logo_url = ?,
                    sportsbook_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE sportsbook_operator_id = ?
            ''', (
                theme_data.get('primaryColor', '#1e40af'),
                theme_data.get('secondaryColor', '#3b82f6'),
                theme_data.get('accentColor', '#f59e0b'),
                theme_data.get('backgroundColor', '#ffffff'),
                theme_data.get('textColor', '#1f2937'),
                theme_data.get('fontFamily', 'Inter, sans-serif'),
                theme_data.get('layoutStyle', 'modern'),
                theme_data.get('buttonStyle', 'rounded'),
                theme_data.get('cardStyle', 'shadow'),
                theme_data.get('logoType', 'default'),
                theme_data.get('logoUrl', ''),
                theme_data.get('sportsbookName', 'Your Sportsbook'),
                operator_id
            ))
        else:
            # Create new theme customization
            cursor.execute('''
                INSERT INTO sportsbook_themes 
                (sportsbook_operator_id, primary_color, secondary_color, accent_color, 
                 background_color, text_color, font_family, layout_style, button_style, 
                 card_style, logo_type, logo_url, sportsbook_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                operator_id,
                theme_data.get('primaryColor', '#1e40af'),
                theme_data.get('secondaryColor', '#3b82f6'),
                theme_data.get('accentColor', '#f59e0b'),
                theme_data.get('backgroundColor', '#ffffff'),
                theme_data.get('textColor', '#1f2937'),
                theme_data.get('fontFamily', 'Inter, sans-serif'),
                theme_data.get('layoutStyle', 'modern'),
                theme_data.get('buttonStyle', 'rounded'),
                theme_data.get('cardStyle', 'shadow'),
                theme_data.get('logoType', 'default'),
                theme_data.get('logoUrl', ''),
                theme_data.get('sportsbookName', 'Your Sportsbook')
            ))
        
        conn.commit()
        conn.close()
        
        # Invalidate cache after theme update (Phase 2: Redis + in-process)
        try:
            from src.utils.redis_cache import invalidate_tenant_cache
            invalidate_tenant_cache(subdomain)
            print(f"🗑️ Invalidated cache for {subdomain} after theme update")
        except Exception as cache_error:
            print(f"⚠️ Cache invalidation failed (non-critical): {cache_error}")
        
        print(f"✅ Theme saved successfully for operator: {subdomain}")
        return jsonify({'success': True, 'message': 'Theme saved successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error saving theme for operator {subdomain}: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to save theme: {str(e)}'}), 500

@clean_multitenant_bp.route('/<subdomain>/api/load-theme', methods=['GET'])
def load_theme_for_operator(subdomain):
    """Load theme customization for specific operator"""
    from flask import jsonify, session
    
    # Check if admin is authenticated for this subdomain
    if not (session.get('operator_id') and session.get('operator_subdomain') == subdomain):
        return jsonify({'error': 'Unauthorized'}), 401
    
    operator, error = validate_subdomain(subdomain)
    if not operator:
        return jsonify({'error': error}), 404
    
    try:
        print(f"🔍 Loading theme for operator: {subdomain}")
        
        # Get theme customization for this operator
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        primary_color, secondary_color, accent_color, 
                        background_color, text_color, font_family,
                        layout_style, button_style, card_style,
                        logo_type, logo_url, sportsbook_name
                    FROM sportsbook_themes 
                    WHERE sportsbook_operator_id = %s
                ''', (operator['id'],))
                
                theme = cursor.fetchone()
        
        if theme:
            print(f"✅ Found saved theme for operator: {subdomain}")
            return jsonify({
                'primaryColor': theme[0] or '#1e40af',
                'secondaryColor': theme[1] or '#3b82f6',
                'accentColor': theme[2] or '#f59e0b',
                'backgroundColor': theme[3] or '#ffffff',
                'textColor': theme[4] or '#1f2937',
                'fontFamily': theme[5] or 'Inter, sans-serif',
                'layoutStyle': theme[6] or 'modern',
                'buttonStyle': theme[7] or 'rounded',
                'cardStyle': theme[8] or 'shadow',
                'logoType': theme[9] or 'default',
                'logoUrl': theme[10] or '',
                'sportsbookName': theme[11] or 'Your Sportsbook'
            })
        else:
            print(f"ℹ️ No saved theme found for operator: {subdomain}, returning defaults")
            return jsonify({
                'primaryColor': '#1e40af',
                'secondaryColor': '#3b82f6',
                'accentColor': '#f59e0b',
                'backgroundColor': '#ffffff',
                'textColor': '#1f2937',
                'fontFamily': 'Inter, sans-serif',
                'layoutStyle': 'modern',
                'buttonStyle': 'rounded',
                'cardStyle': 'shadow',
                'logoType': 'default',
                'logoUrl': '',
                'sportsbookName': 'Your Sportsbook'
            })
        
    except Exception as e:
        print(f"Error loading theme for operator {subdomain}: {e}")
        return jsonify({'error': 'Failed to load theme'}), 500

@clean_multitenant_bp.route('/<subdomain>/api/public/load-theme', methods=['GET'])
@rate_limit_per_tenant(max_tokens=100, refill_rate=2.0, window_seconds=60, endpoint_type="public")
@singleflight_branding
def load_public_theme_for_operator(subdomain):
    """
    TRULY DB-FREE public theme endpoint - NEVER touches database
    Always returns 200 with cached data or defaults (never blocks on pool)
    """
    from flask import jsonify, current_app
    from src.utils.redis_cache import redis_cache_get
    import os
    import hashlib
    
    # Cache key for branding data
    cache_key = f"branding:{subdomain}"
    lock_key = f"lock:branding:{subdomain}"
    
    # Try to get cached branding data (stale is OK)
    cached_branding = redis_cache_get(cache_key)
    
    if cached_branding:
        # Serve cached value with proper headers
        theme_data = _extract_theme_from_branding(cached_branding)
        response = jsonify(theme_data)
        
        # Generate ETag from theme content
        etag = hashlib.md5(str(theme_data).encode()).hexdigest()
        response.headers['ETag'] = f'"{etag}"'
        response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=60'
        
        # Record cache hit
        try:
            from src.utils.metrics import record_cache_hit
            record_cache_hit('branding', subdomain)
        except Exception:
            pass
        
        return response, 200
    
    # Cache miss - check singleflight lock
    import redis
    redis_client = redis.from_url(os.getenv('REDIS_URL')) if os.getenv('REDIS_URL') else None
    
    if redis_client:
        try:
            # Try to acquire lock (30 second expiry)
            lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=30)
            if not lock_acquired:
                # Someone else is fetching, serve defaults immediately
                current_app.logger.info(f"🔄 Singleflight: serving defaults while {subdomain} refreshes")
                defaults = _get_default_theme_data()
                response = jsonify(defaults)
                response.headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=30'
                return response, 200
        except Exception as e:
            current_app.logger.warning(f"Redis singleflight failed: {e}")
    
    # We got the lock or Redis unavailable - serve defaults and trigger background refresh
    defaults = _get_default_theme_data()
    
    # Trigger background refresh (non-blocking, in separate thread)
    try:
        import threading
        threading.Thread(
            target=_background_refresh_branding_safe,
            args=(subdomain, cache_key, lock_key),
            daemon=True
        ).start()
    except Exception as e:
        current_app.logger.warning(f"Background refresh failed: {e}")
    
    # Record cache miss
    try:
        from src.utils.metrics import record_cache_miss
        record_cache_miss('branding', subdomain)
    except Exception:
        pass
    
    response = jsonify(defaults)
    response.headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=30'
    return response, 200

def _get_default_theme_data():
    """Get default theme data - never hits DB"""
    return {
        'primaryColor': '#10B981',
        'secondaryColor': '#1F2937',
        'backgroundColor': '#111827',
        'textColor': '#F9FAFB',
        'accentColor': '#3B82F6',
        'buttonStyle': 'rounded',
        'cardStyle': 'shadow',
        'logoType': 'default',
        'logoUrl': '',
        'sportsbookName': 'Your Sportsbook'
    }

def _extract_theme_from_branding(branding_data):
    """Extract theme data from branding cache - never hits DB"""
    if not branding_data or not isinstance(branding_data, dict):
        return _get_default_theme_data()
    
    theme_data = branding_data.get('theme', {})
    operator_data = branding_data.get('operator', {})
    
    return {
        'primaryColor': theme_data.get('primary_color') or '#10B981',
        'secondaryColor': theme_data.get('secondary_color') or '#1F2937',
        'backgroundColor': theme_data.get('background_color') or '#111827',
        'textColor': theme_data.get('text_color') or '#F9FAFB',
        'accentColor': theme_data.get('accent_color') or '#3B82F6',
        'buttonStyle': theme_data.get('button_style') or 'rounded',
        'cardStyle': theme_data.get('card_style') or 'shadow',
        'logoType': theme_data.get('logo_type') or 'default',
        'logoUrl': theme_data.get('logo_url') or '',
        'sportsbookName': operator_data.get('name') or 'Your Sportsbook'
    }

def _background_refresh_branding_safe(subdomain, cache_key, lock_key):
    """Background refresh of branding cache with circuit breaker protection"""
    try:
        # Check circuit breaker before hitting DB
        from src.db_compat import is_db_circuit_breaker_open
        if is_db_circuit_breaker_open():
            import logging
            logging.warning(f"Circuit breaker open - skipping DB refresh for {subdomain}")
            return
        
        # This will hit DB but in background thread with timeout protection
        from src.routes.branding import get_operator_branding
        fresh_branding = get_operator_branding(subdomain)
        
        # Update cache
        from src.utils.redis_cache import redis_cache_set
        redis_cache_set(cache_key, fresh_branding, ttl=3600)
        
        import logging
        logging.info(f"✅ Background refresh completed for {subdomain}")
        
    except Exception as e:
        import logging
        logging.warning(f"Background branding refresh failed for {subdomain}: {e}")
    finally:
        # Always release lock
        try:
            import redis
            redis_client = redis.from_url(os.getenv('REDIS_URL')) if os.getenv('REDIS_URL') else None
            if redis_client:
                redis_client.delete(lock_key)
        except Exception as e:
            import logging
            logging.warning(f"Failed to release lock for {subdomain}: {e}")


@clean_multitenant_bp.route('/api/theme-css/<subdomain>', methods=['GET'])
def get_theme_css(subdomain):
    """Serve theme CSS for specific operator - bulletproof against DB failures"""
    from flask import Response, make_response
    
    # Initialize default theme values
    primary_color = '#22C55E'
    secondary_color = '#3b82f6'
    accent_color = '#22C55E'
    background_color = '#1A1A1A'
    text_color = '#FFFFFF'
    font_family = 'Inter, sans-serif'
    layout_style = 'modern'
    button_style = 'rounded'
    card_style = 'shadow'
    
    try:
        print(f"🔍 Serving theme CSS for operator: {subdomain}")
        
        # Validate subdomain first
        operator, error = validate_subdomain(subdomain)
        if not operator:
            print(f"❌ Operator not found: {error}")
            # Still return valid CSS with defaults
            css_content = f"""/* Theme CSS for {subdomain} - operator not found, using defaults */
:root {{
    --primary-color: {primary_color};
    --secondary-color: {secondary_color};
    --accent-color: {accent_color};
    --background-color: {background_color};
    --text-color: {text_color};
    --font-family: {font_family};
}}

body {{
    font-family: var(--font-family);
    background: var(--background-color);
    color: var(--text-color);
}}

.header, .sidebar, .content-area {{
    background: var(--background-color);
}}

.logo-icon, .sport-item.active, .refresh-btn, .view-btn.active {{
    background: var(--primary-color);
    color: white;
}}

.status-indicator.connected {{
    background: rgba(34, 197, 94, 0.2);
    border-color: var(--primary-color);
    color: var(--primary-color);
}}
"""
            resp = make_response(css_content, 200)
            resp.headers["Content-Type"] = "text/css; charset=utf-8"
            return resp
        
        # Try to get database connection with bulletproof error handling
        try:
            with connection_ctx() as conn:
                cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '1500ms'")
            
            # Get theme customization for this operator
            cursor.execute('''
                SELECT 
                    primary_color, secondary_color, accent_color, 
                    background_color, text_color, font_family,
                    layout_style, button_style, card_style
                FROM sportsbook_themes 
                WHERE sportsbook_operator_id = ?
            ''', (operator['id'],))
            
            theme = cursor.fetchone()
            conn.close()
            
            if theme:
                print(f"✅ Found saved theme for operator: {subdomain}")
                primary_color = theme[0] or primary_color
                secondary_color = theme[1] or secondary_color
                accent_color = theme[2] or accent_color
                background_color = theme[3] or background_color
                text_color = theme[4] or text_color
                font_family = theme[5] or font_family
                layout_style = theme[6] or layout_style
                button_style = theme[7] or button_style
                card_style = theme[8] or card_style
            else:
                print(f"ℹ️ No saved theme found for operator: {subdomain}, using defaults")
                
        except Exception as db_error:
            print(f"⚠️ Database connection failed for theme CSS, using defaults: {db_error}")
            # Continue with default values - don't fail the request
        
        # Generate CSS with theme values (always succeeds)
        css_content = f"""/* Theme CSS for {subdomain} */
:root {{
    --primary-color: {primary_color};
    --secondary-color: {secondary_color};
    --accent-color: {accent_color};
    --background-color: {background_color};
    --text-color: {text_color};
    --font-family: {font_family};
}}

body {{
    font-family: var(--font-family);
    background: var(--background-color);
    color: var(--text-color);
}}

.header {{
    background: var(--background-color);
}}

.sidebar {{
    background: var(--background-color);
}}

.content-area {{
    background: var(--background-color);
}}

.logo-icon {{
    background: var(--primary-color);
}}

.sport-item.active {{
    background: var(--primary-color);
    color: white;
}}

.status-indicator.connected {{
    background: rgba(34, 197, 94, 0.2);
    border-color: var(--primary-color);
    color: var(--primary-color);
}}

.refresh-btn {{
    background: var(--primary-color);
    color: white;
}}

.view-btn.active {{
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
}}

/* Layout Styles */
.layout-{layout_style} {{
    --layout-spacing: {16 if layout_style == 'modern' else 12 if layout_style == 'classic' else 8 if layout_style == 'compact' else 20 if layout_style == 'wide' else 6}px;
    --layout-radius: {8 if layout_style == 'modern' else 4 if layout_style == 'classic' else 6 if layout_style == 'compact' else 12 if layout_style == 'wide' else 2}px;
}}

/* Button Styles */
.btn-{button_style} {{
    border-radius: {25 if button_style == 'rounded' else 0 if button_style == 'sharp' else 4}px;
    {f'border: 1px solid rgba(255, 255, 255, 0.2);' if button_style == 'minimal' else ''}
}}

/* Card Styles */
.card-{card_style} {{
    {f'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);' if card_style == 'shadow' else ''}
    {f'border: 2px solid rgba(255, 255, 255, 0.1); box-shadow: none;' if card_style == 'border' else ''}
    {f'border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: none;' if card_style == 'minimal' else ''}
    {f'box-shadow: 0 0 20px rgba(34, 197, 94, 0.3);' if card_style == 'glow' else ''}
}}
"""
        
        print(f"✅ Theme CSS generated for operator: {subdomain}")
        resp = make_response(css_content, 200)
        resp.headers["Content-Type"] = "text/css; charset=utf-8"
        return resp
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating theme CSS for operator {subdomain}: {e}")
        # Always return valid CSS with headers to prevent write() before start_response
        resp = make_response("/* theme error; using defaults */", 200)
        resp.headers["Content-Type"] = "text/css; charset=utf-8"
        return resp

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
            # Clear any existing session to avoid tenant conflicts
            session.clear()
            
            # Set admin session with correct keys for /api/auth/me
            session['admin_id'] = f"{operator['id']}:{username}"
            session['operator_id'] = operator['id']
            session['operator_name'] = subdomain
            session['role'] = 'admin'
            
            # CRITICAL: Set the correct tenant context to match the URL subdomain
            session['original_tenant'] = subdomain
            session['operator_subdomain'] = subdomain
            session['admin_operator_id'] = operator['id']
            session['admin_subdomain'] = subdomain
            
            session.permanent = True  # Make session persistent
            
            print(f"✅ Admin login successful for subdomain: {subdomain}, operator_id: {operator['id']}")
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            print(f"❌ Admin login failed for subdomain: {subdomain}, username: {username}")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        print(f"❌ Admin login error for subdomain {subdomain}: {e}")
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
