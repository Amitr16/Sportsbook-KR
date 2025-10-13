"""
Authentication routes for sports betting platform
"""

from flask import Blueprint, request, jsonify, g, redirect, make_response, current_app, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.betting import User
import jwt
import datetime
from functools import wraps
import logging
import os
import urllib.parse

import requests
from requests.exceptions import Timeout, ConnectionError

# Make sure .env / env.local are loaded on import (no circulars here; env_loader has no app deps)
import src.config.env_loader  # noqa: F401

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

def _google_callback_url() -> str:
    # Use the redirect URI from environment to match Google Console
    return _google_oauth_cfg()["redirect_uri"]

# JWT Secret Key (in production, use environment variable)
JWT_SECRET_KEY = 'your-secret-key-change-in-production'

def token_required(f):
    """Decorator to require JWT token for protected routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                pass
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token is missing'
            }), 401
        
        try:
            # Decode token
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            current_user = current_app.db.session.query(User).get(data['user_id'])
            
            if not current_user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid token'
                }), 401
            
            # Check if user is blocked by admin
            if not current_user.is_active:
                return jsonify({
                    'success': False,
                    'error': 'Account has been disabled by administrator'
                }), 403
            
            g.current_user = current_user
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Token has expired'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated


# -----------------------------
# Google OAuth configuration
# -----------------------------
def _google_oauth_cfg():
    """Read Google OAuth config at call time to avoid import-time None values."""
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/auth/google/callback"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "userinfo_uri": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    }


@auth_bp.route('/google/login', methods=['GET'])
def google_login():
    """Start Google OAuth login by redirecting to Google's consent screen"""
    cfg = _google_oauth_cfg()
    
    # Always use our canonical callback; ignore client-provided redirect_uri
    redirect_uri = _google_callback_url()
    logger.info(f"Google OAuth login - Using redirect_uri: {redirect_uri}")
    
    # Hard guard to avoid "client_id=None"
    if not cfg["client_id"] or not cfg["client_secret"]:
        current_app.logger.error("Google OAuth env missing: GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET")
        # For XHR/API, return JSON; for browser nav you can redirect to a friendly error/login
        if request.headers.get("Accept", "").find("application/json") >= 0 or request.path.startswith("/api"):
            return jsonify({"success": False, "error": "Google OAuth not configured"}), 500
        return redirect('/login', code=302)
    
    # Store the tenant context in session for redirect after OAuth
    referrer = request.headers.get('Referer', '')
    
    # Extract tenant from various sources
    import re
    tenant = None
    
    # 1. First try to get tenant from explicit parameter
    tenant = request.args.get('tenant')
    if tenant:
        logger.info(f"Google OAuth login - Tenant from parameter: {tenant}")
    
    # 2. If no tenant parameter, try to extract from referrer
    if not tenant and referrer:
        tenant_match = re.search(r'/([^/?]+)(?:/|$|\?)', referrer)
        if tenant_match:
            potential_tenant = tenant_match.group(1)
            # Filter out common non-tenant paths
            if potential_tenant not in ['auth', 'api', 'static', 'favicon.ico', 'login', 'logout', 'register', 'localhost:5000']:
                tenant = potential_tenant
                logger.info(f"Google OAuth login - Tenant from referrer: {tenant}")
    
    # 3. If no tenant found in referrer, try to get it from the redirect_uri parameter
    if not tenant:
        redirect_uri = request.args.get('redirect_uri', '')
        if redirect_uri:
            # Extract tenant from redirect_uri like http://localhost:5000/{tenant}/...
            tenant_match = re.search(r'/([^/?]+)(?:/|$|\?)', redirect_uri)
            if tenant_match:
                potential_tenant = tenant_match.group(1)
                if potential_tenant not in ['auth', 'api', 'static', 'favicon.ico', 'login', 'logout', 'register', 'localhost:5000']:
                    tenant = potential_tenant
                    logger.info(f"Google OAuth login - Tenant from redirect_uri: {tenant}")
    
    # Validate that it's a known tenant by checking if it exists in database
    if tenant:
        try:
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=3) as conn:
                # Set very short statement timeout for this endpoint
                with conn.cursor() as c:
                    c.execute("SET LOCAL statement_timeout = '1500ms'")
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM sportsbook_operators WHERE subdomain = %s", (tenant,))
                    if cursor.fetchone():
                        session['original_tenant'] = tenant
                        session.permanent = True
                        session.modified = True
                        logger.info(f"Google OAuth login - Valid tenant found: {tenant}")
                    else:
                        logger.error(f"Google OAuth login - Unknown tenant '{tenant}', cannot proceed")
                        return jsonify({'success': False, 'error': f'Unknown tenant: {tenant}'}), 400
        except Exception as e:
            current_app.logger.error(f"Auth DB acquire failed fast: {e}")
            resp = make_response(jsonify({"error": "temporarily overloaded"}), 429)
            resp.headers["Retry-After"] = "2"
            return resp
    else:
        logger.error("Google OAuth login - No tenant found in referrer URL or redirect_uri")
        return jsonify({'success': False, 'error': 'No tenant found in URL'}), 400
    
    logger.info(f"Google OAuth login - Storing tenant: {session.get('original_tenant')}")
    
    params = {
        'client_id': cfg["client_id"],
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': cfg["scope"],
        'access_type': 'offline',
        'include_granted_scopes': 'true',
        'prompt': 'consent'
    }
    url = f'{cfg["auth_uri"]}?{urllib.parse.urlencode(params)}'
    return redirect(url, code=302)


@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Google redirects here. Create/login user, set session, then redirect to app."""
    import datetime
    import logging
    logger = logging.getLogger(__name__)

    logger.info("🔔 Google OAuth callback hit!")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request args: {dict(request.args)}")

    try:
        logger.info("🔧 Loading Google OAuth config...")
        cfg = _google_oauth_cfg()
        logger.info(f"✅ OAuth config loaded: client_id exists={bool(cfg.get('client_id'))}, token_uri={cfg.get('token_uri')}")

        # 1) Validate code
        code = request.args.get('code')
        if not code:
            logger.error("❌ Missing authorization code")
            return jsonify({'success': False, 'error': 'Missing authorization code'}), 400

        # Must exactly match what we used at /google/login
        logger.info("🔧 Getting callback URL...")
        redirect_uri = _google_callback_url()
        logger.info(f"✅ Callback URL: {redirect_uri}")
        
        if not cfg["client_id"] or not cfg["client_secret"]:
            logger.error("❌ Google OAuth env missing on callback")
            return jsonify({'success': False, 'error': 'Google OAuth not configured'}), 500

        # 2) Exchange code → tokens
        logger.info("🔄 Exchanging code for tokens...")
        logger.info(f"🔄 Making POST to: {cfg['token_uri']}")
        try:
            token_resp = requests.post(
                cfg["token_uri"],
                data={
                    'code': code,
                    'client_id': cfg["client_id"],
                    'client_secret': cfg["client_secret"],
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code'
                },
                timeout=5  # Reduced timeout to fail faster
            )
            logger.info(f"✅ Token exchange response: {token_resp.status_code}")
        except requests.exceptions.Timeout:
            logger.error("❌ Token exchange timed out after 5 seconds")
            return jsonify({'success': False, 'error': 'Token exchange timed out'}), 408
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Token exchange failed with error: {e}")
            return jsonify({'success': False, 'error': f'Token exchange failed: {e}'}), 500
        if not token_resp.ok:
            logger.error("Token exchange failed: %s", token_resp.text[:500])
            return jsonify({'success': False, 'error': 'Token exchange failed'}), 400

        tokens = token_resp.json()
        access_token = tokens.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Missing access token'}), 400

        # 3) Get Google user info (add timeouts + one retry)
        logger.info("🔄 Getting Google user info...")
        def _userinfo():
            return requests.get(
                cfg["userinfo_uri"],
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=(3, 6),  # 3s connect, 6s read
            )
        try:
            userinfo_resp = _userinfo()
        except (Timeout, ConnectionError):
            logger.warning("⚠️ Userinfo request timed out, retrying once...")
            userinfo_resp = _userinfo()

        userinfo_resp.raise_for_status()
        logger.info(f"✅ Userinfo response: {userinfo_resp.status_code}")
        userinfo = userinfo_resp.json()
        email = userinfo.get('email')
        name = userinfo.get('name') or (userinfo.get('given_name') or 'user')
        sub = userinfo.get('sub')  # Google user ID

        if not email:
            return jsonify({'success': False, 'error': 'Email not available from Google'}), 400

        # 4) Get operator_id from tenant stored in session
        tenant = session.get('original_tenant')
        if not tenant:
            logger.error("❌ No tenant found in session, cannot proceed with OAuth")
            return jsonify({'success': False, 'error': 'No tenant context found'}), 400
        logger.info(f"🔍 Google OAuth callback - Tenant: {tenant}")
        
        # Get operator_id from subdomain
        operator_id = None
        if tenant:
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=3) as conn:
                # Set very short statement timeout for this endpoint
                with conn.cursor() as c:
                    c.execute("SET LOCAL statement_timeout = '1500ms'")
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM sportsbook_operators WHERE subdomain = %s", (tenant,))
                    operator_result = cursor.fetchone()
                    if operator_result:
                        operator_id = operator_result['id']
                        logger.info(f"🔍 Found operator_id: {operator_id} for tenant: {tenant}")
                    else:
                        logger.warning(f"⚠️ No operator found for tenant: {tenant}")
        
        # 5) Find or create user; update last_login
        from src.db_compat import connection_ctx
        try:
            with connection_ctx(timeout=3) as conn:
                # Set very short statement timeout for this endpoint
                with conn.cursor() as c:
                    c.execute("SET LOCAL statement_timeout = '1500ms'")
                logger.info(f"🔍 Looking for existing user with email: {email} and operator_id: {operator_id}")
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, username, email, balance, sportsbook_operator_id FROM users WHERE email = %s AND sportsbook_operator_id = %s",
                        (email, operator_id)
                    )
                    user = cursor.fetchone()
        except Exception as e:
            current_app.logger.error(f"Auth DB acquire failed fast: {e}")
            resp = make_response(jsonify({"error": "temporarily overloaded"}), 429)
            resp.headers["Retry-After"] = "2"
            return resp
        
        # Check if user exists for this specific operator
        if user and user.get('sportsbook_operator_id') != operator_id:
            logger.info(f"🔍 User {email} exists for operator {user.get('sportsbook_operator_id')} but logging into operator {operator_id}")
            logger.info(f"🔍 Creating separate account for this tenant...")
            # Don't update existing user, we'll create a new one below
            user = None
        
        if not user:
            logger.info(f"🔍 No existing user found, creating new user for email: {email}")
            
            # Generate cool random username (same as frontend)
            import random
            
            # List of cool username prefixes
            prefixes = [
                'Thunder', 'Lightning', 'Storm', 'Fire', 'Ice', 'Shadow', 'Mystic', 'Cosmic',
                'Quantum', 'Nebula', 'Stellar', 'Solar', 'Lunar', 'Galactic', 'Atomic', 'Neon',
                'Cyber', 'Digital', 'Virtual', 'Matrix', 'Code', 'Pixel', 'Byte', 'Data',
                'Alpha', 'Beta', 'Gamma', 'Delta', 'Omega', 'Nova', 'Super', 'Ultra',
                'Mega', 'Giga', 'Tera', 'Peta', 'Exa', 'Zetta', 'Yotta', 'Infinity'
            ]
            
            # List of cool suffixes
            suffixes = [
                'Master', 'Lord', 'King', 'Queen', 'Prince', 'Princess', 'Duke', 'Duchess',
                'Warrior', 'Knight', 'Mage', 'Wizard', 'Sorcerer', 'Warlock', 'Priest', 'Monk',
                'Hunter', 'Ranger', 'Rogue', 'Assassin', 'Ninja', 'Samurai', 'Viking', 'Berserker',
                'Phoenix', 'Dragon', 'Tiger', 'Lion', 'Eagle', 'Falcon', 'Wolf', 'Bear',
                'Storm', 'Thunder', 'Lightning', 'Fire', 'Ice', 'Shadow', 'Mystic', 'Cosmic',
                'Pro', 'Elite', 'Legend', 'Myth', 'Epic', 'Hero', 'Champion', 'Winner'
            ]
            
            # Generate random username (no numbers)
            prefix = random.choice(prefixes)
            suffix = random.choice(suffixes)
            username = f"{prefix}{suffix}"
            
            # Check if username is available, try with different suffix if taken
            attempts = 0
            with conn.cursor() as cursor:
                while cursor.execute("SELECT 1 FROM users WHERE username = %s AND sportsbook_operator_id = %s", (username, operator_id)).fetchone() and attempts < 10:
                    suffix = random.choice(suffixes)
                    username = f"{prefix}{suffix}"
                    attempts += 1
            
            # If still not available after 10 attempts, fall back to simple approach
            if attempts >= 10:
                logger.warning(f"⚠️ Could not generate unique cool username, falling back to simple approach")
                base = (name or email.split("@")[0]).replace(" ", "").lower()[:15]
                username, n = base, 1
                
                # Check for username conflicts within this operator
                with conn.cursor() as cursor:
                    while cursor.execute("SELECT 1 FROM users WHERE username = %s AND sportsbook_operator_id = %s", (username, operator_id)).fetchone():
                        n += 1
                        username = f"{base}{n}"
            
            logger.info(f"🔍 Generated cool username: {username} for email: {email}")
            
            try:
                # Get default balance for this operator
                try:
                    from src.routes.rich_admin_interface import get_default_user_balance
                    default_balance = get_default_user_balance(operator_id)
                except Exception as e:
                    logger.warning(f"⚠️ Could not get default balance for operator {operator_id}: {e}")
                    default_balance = 1000.0  # Fall back to default
                    
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (username, email, password_hash, balance, is_active, created_at, last_login, sportsbook_operator_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (username, email, generate_password_hash(f"google:{sub}"), default_balance, True,
                         datetime.datetime.utcnow(), datetime.datetime.utcnow(), operator_id),
                    )
                    conn.commit()
                    logger.info(f"✅ Successfully created new user with operator_id: {operator_id}")
                    
                    # Verify user was created and fetch the complete user data
                    cursor.execute(
                        "SELECT id, username, email, balance, sportsbook_operator_id FROM users WHERE email = %s AND sportsbook_operator_id = %s", 
                        (email, operator_id)
                    )
                    user = cursor.fetchone()
                if user:
                    logger.info(f"✅ Verified user creation: {user}")
                else:
                    logger.error(f"❌ User creation failed - user not found after insert")
                    return jsonify({'success': False, 'error': 'User creation failed'}), 500
                    
            except Exception as insert_error:
                logger.error(f"❌ User creation failed: {insert_error}")
                conn.rollback()
                return jsonify({'success': False, 'error': f'User creation failed: {str(insert_error)}'}), 500
        else:
            logger.info(f"✅ Found existing user: {user}")
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET last_login = %s WHERE id = %s",
                             (datetime.datetime.utcnow(), user["id"]))
                conn.commit()
                logger.info(f"✅ Updated existing user last_login")

        # 6) Set session
        logger.info("=" * 50)
        logger.info(f"🔍 Setting session for user: {user}")
        logger.info(f"🔍 Session before setting: {dict(session)}")
        
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['email'] = user['email']
        session['balance'] = user['balance']
        session['role'] = 'user'
        if operator_id:
            session['operator_id'] = operator_id
        session.permanent = True
        session.modified = True
        
        logger.info(f"✅ Session set - user_id: {session.get('user_id')}, operator_id: {session.get('operator_id')}")
        logger.info(f"✅ Session data after setting: {dict(session)}")
        logger.info(f"✅ Session permanent: {session.permanent}")
        logger.info(f"✅ Session modified: {session.modified}")
        logger.info("=" * 50)

        # 6) Set operator context (tenant) - already set above
        # No need for additional operator lookup since we already have operator_id

        # 7) Persist the session with the redirect response
        session.permanent = True
        session.modified = True

        # 8) Compute redirect target based on the tenant from session
        referrer = request.headers.get('Referer', '') or ''
        session_tenant = session.get('original_tenant')
        logger.info("Google OAuth callback - Referrer: %s", referrer)
        logger.info("Google OAuth callback - Session tenant: %s", session_tenant)

        # Use the tenant from session to determine redirect URL
        # This ensures we redirect back to the correct tenant subdomain
        redirect_url = f'/{session_tenant}'
        
        logger.info("Google OAuth callback - Redirecting to: %s", redirect_url)
        
        # Flask's built-in sessions automatically save to response
        resp = redirect(redirect_url, code=303)  # 303 is safer after POST/redirect flows
        return resp

    except Exception as e:
        current_app.logger.exception("Google OAuth callback error")
        return jsonify({'success': False, 'error': 'OAuth process failed'}), 500

# Note: Alias route will be registered in main.py to avoid import-time app context issues

@auth_bp.route('/me', methods=['GET'])
def get_user_profile():
    """Get current user profile from session"""
    from flask import session, request
    from src.db_compat import connection_ctx
    
    try:
        logger.info("=" * 50)
        logger.info("🔍 /api/auth/me endpoint hit")
        logger.info(f"🔍 Request URL: {request.url}")
        logger.info(f"🔍 Request method: {request.method}")
        logger.info(f"🔍 Request headers: {dict(request.headers)}")
        logger.info(f"🔍 Session data: {dict(session)}")
        logger.info(f"🔍 Session ID: {session.get('_id', 'No session ID')}")
        logger.info(f"🔍 Session permanent: {session.permanent}")
        logger.info(f"🔍 Session modified: {session.modified}")
        
        user_id = session.get('user_id')
        logger.info(f"🔍 User ID from session: {user_id}")
        
        if not user_id:
            logger.warning("❌ No user_id in session - user not authenticated")
            logger.warning("❌ Available session keys: " + str(list(session.keys())))
            return jsonify({'error': 'Not authenticated'}), 401
        
        logger.info(f"🔍 Querying database for user_id: {user_id}")
        with connection_ctx(timeout=5) as conn:
            # Set very short statement timeout for this endpoint
            with conn.cursor() as c:
                c.execute("SET LOCAL statement_timeout = '2000ms'")
            logger.info(f"🔍 Database connection established")
            with conn.cursor() as cursor:
                logger.info(f"🔍 Database cursor created")
                cursor.execute("SELECT id, username, email, balance, last_login FROM users WHERE id = %s", (user_id,))
                logger.info(f"🔍 Database query executed")
                user = cursor.fetchone()
                logger.info(f"🔍 Database fetch completed")
        
        logger.info(f"🔍 Database query result: {user}")
        
        if not user:
            logger.warning(f"❌ User not found in database for user_id: {user_id}")
            return jsonify({'error': 'User not found'}), 404
        
        user_data = {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'balance': float(user[3]) if user[3] else 0.0,
            'last_login': user[4].isoformat() if user[4] else None
        }
        
        logger.info(f"✅ Returning user data: {user_data}")
        logger.info("=" * 50)
        return jsonify(user_data)
        
    except Exception as e:
        logger.error(f"❌ Error getting user profile: {e}")
        logger.exception("Full traceback:")
        logger.info("=" * 50)
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Validate input
        if not username or not email or not password:
            return jsonify({
                'success': False,
                'error': 'Username, email, and password are required'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 6 characters long'
            }), 400
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                return jsonify({
                    'success': False,
                    'error': 'Username already exists'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': 'Email already exists'
                }), 400
        
        # Create new user
        password_hash = generate_password_hash(password)
        
        # Get default balance (for global registration, use default operator or fallback)
        try:
            from src.routes.rich_admin_interface import get_default_user_balance
            # For global registration, try to get balance from operator 1 (default) or use fallback
            default_balance = get_default_user_balance(1) if hasattr(current_app, 'db') else 1000.0
        except Exception as e:
            logger.warning(f"⚠️ Could not get default balance for global registration: {e}")
            default_balance = 1000.0  # Fall back to default
        
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            balance=default_balance  # Configurable starting balance
        )
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"New user registered: {username}")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance
            }
        })
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Registration failed'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account is deactivated'
            }), 401
        
        # Update last login
        user.last_login = datetime.datetime.utcnow()
        db.session.commit()
        
        # Generate JWT token
        token_payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)  # Token expires in 7 days
        }
        
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm='HS256')
        
        logger.info(f"User logged in: {username}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """Get current user profile"""
    try:
        user = g.current_user
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Profile error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get profile'
        }), 500

@auth_bp.route('/me-jwt', methods=['GET'])
@token_required
def get_current_user_jwt():
    """Get current user data (alias for /profile)"""
    try:
        # ✅ Read through the SAME SQLAlchemy session used by writes
        user = current_app.db.session.get(User, g.current_user.id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'balance': float(user.balance or 0),
            'last_login': user.last_login.isoformat() if user.last_login else None
        })
        
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get user data'
        }), 500

@auth_bp.route('/debug/session', methods=['GET'])
def debug_session():
    """Debug endpoint to check session data"""
    from flask import session, g, request
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 DEBUG SESSION ENDPOINT")
    logger.info(f"🔍 Session data: {dict(session)}")
    logger.info(f"🔍 g.current_user: {getattr(g, 'current_user', 'Not set')}")
    logger.info(f"🔍 Request cookies: {dict(request.cookies)}")
    logger.info(f"🔍 Request headers: {dict(request.headers)}")
    
    return jsonify({
        'session_data': dict(session),
        'g_current_user': str(getattr(g, 'current_user', 'Not set')),
        'user_id': session.get('user_id'),
        'operator_id': session.get('operator_id'),
        'user_data': session.get('user_data'),
        'original_tenant': session.get('original_tenant'),
        'request_cookies': dict(request.cookies),
        'session_permanent': session.permanent,
        'session_modified': session.modified
    })

@auth_bp.route('/debug/set-tenant', methods=['POST'])
def debug_set_tenant():
    """Debug endpoint to manually set tenant in session"""
    from flask import session, make_response
    import logging
    logger = logging.getLogger(__name__)
    
    data = request.get_json()
    tenant = data.get('tenant', 'supersports')
    
    # Try to set session data
    session['original_tenant'] = tenant
    session['test_key'] = 'test_value'
    session.permanent = True
    session.modified = True
    
    logger.info(f"🔍 DEBUG: Set tenant to {tenant} in session")
    logger.info(f"🔍 DEBUG: Session data: {dict(session)}")
    logger.info(f"🔍 DEBUG: Session permanent: {session.permanent}")
    logger.info(f"🔍 DEBUG: Session modified: {session.modified}")
    
    # Create response and ensure session is saved
    response = make_response(jsonify({
        'success': True,
        'tenant': tenant,
        'session_data': dict(session),
        'session_permanent': session.permanent,
        'session_modified': session.modified
    }))
    
    return response

@auth_bp.route('/debug/test-session', methods=['GET'])
def debug_test_session():
    """Test if session is working at all"""
    from flask import session, make_response
    import logging
    logger = logging.getLogger(__name__)
    
    # Try to read and write to session
    current_value = session.get('test_counter', 0)
    session['test_counter'] = current_value + 1
    session['test_timestamp'] = str(datetime.datetime.now())
    session.permanent = True
    session.modified = True
    
    logger.info(f"🔍 DEBUG: Test session - counter: {current_value + 1}")
    logger.info(f"🔍 DEBUG: Session data: {dict(session)}")
    
    response = make_response(jsonify({
        'success': True,
        'counter': current_value + 1,
        'session_data': dict(session),
        'session_permanent': session.permanent,
        'session_modified': session.modified
    }))
    
    return response

@auth_bp.route('/debug/simple-session', methods=['GET'])
def debug_simple_session():
    """Very simple session test"""
    from flask import session
    import logging
    logger = logging.getLogger(__name__)
    
    # Just try to set a simple value
    session['simple_test'] = 'hello_world'
    
    logger.info(f"🔍 SIMPLE SESSION TEST: {dict(session)}")
    
    return jsonify({
        'session_data': dict(session),
        'simple_test': session.get('simple_test', 'NOT_FOUND')
    })

@auth_bp.route('/debug/fix-user-data', methods=['POST'])
def fix_user_data():
    """Simple fix to add sportsbook_operator_id to user_data"""
    from flask import session
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        # Get existing user_data or create new
        user_data = session.get('user_data', {})
        
        # Add sportsbook_operator_id if missing
        if 'sportsbook_operator_id' not in user_data:
            user_data['sportsbook_operator_id'] = session.get('operator_id')
            session['user_data'] = user_data
            logger.info(f"✅ Added sportsbook_operator_id to user_data: {user_data}")
        
        return jsonify({
            'success': True,
            'message': 'User data fixed',
            'user_data': user_data
        })
        
    except Exception as e:
        logger.error(f"Error fixing user data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/debug/refresh-user', methods=['POST'])
def refresh_user_data():
    """Force refresh user data to include sportsbook_operator_id"""
    from flask import session
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        # Clear cached user data
        if 'user_data' in session:
            del session['user_data']
        
        # Manually build user data with sportsbook_operator_id from session
        fresh_user_data = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'email': session.get('email'),
            'balance': session.get('balance', 1000.0),
            'is_active': True,
            'sportsbook_operator_id': session.get('operator_id'),
            'created_at': None,
            'last_login': None
        }
        
        session['user_data'] = fresh_user_data
        
        logger.info(f"✅ Refreshed user data: {fresh_user_data}")
        
        return jsonify({
            'success': True,
            'message': 'User data refreshed',
            'user_data': fresh_user_data
        })
        
    except Exception as e:
        logger.error(f"Error refreshing user data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    """Update user profile"""
    try:
        user = g.current_user
        data = request.get_json()
        
        # Update allowed fields
        if 'email' in data:
            email = data['email'].strip()
            if email != user.email:
                # Check if email already exists
                existing_user = User.query.filter_by(email=email).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({
                        'success': False,
                        'error': 'Email already exists'
                    }), 400
                user.email = email
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update profile'
        }), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password():
    """Change user password"""
    try:
        user = g.current_user
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
        
        # Verify current password
        if not check_password_hash(user.password_hash, current_password):
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 400
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        logger.info(f"Password changed for user: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        logger.error(f"Password change error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to change password'
        }), 500

@auth_bp.route('/refresh-token', methods=['POST'])
@token_required
def refresh_token():
    """Refresh JWT token"""
    try:
        user = g.current_user
        
        # Generate new token
        token_payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh token'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """Logout user (client-side token removal)"""
    try:
        user = g.current_user
        logger.info(f"User logged out: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@auth_bp.route('/update-username', methods=['POST'])
def update_username():
    """Update user's username"""
    try:
        # Get user from session instead of token
        user_id = session.get('user_id')
        operator_id = session.get('operator_id')
        
        if not user_id or not operator_id:
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        data = request.get_json()
        new_username = data.get('username', '').strip()
        
        if not new_username:
            return jsonify({
                'success': False,
                'error': 'Username is required'
            }), 400
        
        if len(new_username) < 3 or len(new_username) > 20:
            return jsonify({
                'success': False,
                'error': 'Username must be between 3 and 20 characters'
            }), 400
        
        # Check if username contains only valid characters
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
            return jsonify({
                'success': False,
                'error': 'Username can only contain letters, numbers, and underscores'
            }), 400
        
        # Check if username is already taken by another user in the same operator
        from src.db_compat import get_connection
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM users 
                WHERE username = %s AND sportsbook_operator_id = %s AND id != %s
            """, (new_username, operator_id, user_id))
            
            if cursor.fetchone():
                cursor.close()
                return jsonify({
                    'success': False,
                    'error': 'Username is already taken'
                }), 400
            
            # Update username
            cursor.execute("""
                UPDATE users 
                SET username = %s 
                WHERE id = %s AND sportsbook_operator_id = %s
            """, (new_username, user_id, operator_id))
            
            conn.commit()
            cursor.close()
        finally:
            if conn:
                conn.close()
        
        # Update session
        session['username'] = new_username
        
        logger.info(f"Username updated for user {user_id}: {new_username}")
        
        return jsonify({
            'success': True,
            'message': 'Username updated successfully',
            'username': new_username
        })
        
    except Exception as e:
        logger.error(f"Username update error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update username'
        }), 500

@auth_bp.route('/generate-username', methods=['POST'])
@token_required
def generate_username():
    """Generate a random username for the user"""
    try:
        user = g.current_user
        
        # Generate random username
        import random
        import string
        
        # List of cool username prefixes
        prefixes = [
            'Thunder', 'Lightning', 'Storm', 'Fire', 'Ice', 'Shadow', 'Mystic', 'Cosmic',
            'Quantum', 'Nebula', 'Stellar', 'Solar', 'Lunar', 'Galactic', 'Atomic', 'Neon',
            'Cyber', 'Digital', 'Virtual', 'Matrix', 'Code', 'Pixel', 'Byte', 'Data',
            'Alpha', 'Beta', 'Gamma', 'Delta', 'Omega', 'Nova', 'Super', 'Ultra',
            'Mega', 'Giga', 'Tera', 'Peta', 'Exa', 'Zetta', 'Yotta', 'Infinity'
        ]
        
        # List of cool suffixes
        suffixes = [
            'Master', 'Lord', 'King', 'Queen', 'Prince', 'Princess', 'Duke', 'Duchess',
            'Warrior', 'Knight', 'Mage', 'Wizard', 'Sorcerer', 'Warlock', 'Priest', 'Monk',
            'Hunter', 'Ranger', 'Rogue', 'Assassin', 'Ninja', 'Samurai', 'Viking', 'Berserker',
            'Phoenix', 'Dragon', 'Tiger', 'Lion', 'Eagle', 'Falcon', 'Wolf', 'Bear',
            'Storm', 'Thunder', 'Lightning', 'Fire', 'Ice', 'Shadow', 'Mystic', 'Cosmic',
            'Pro', 'Elite', 'Legend', 'Myth', 'Epic', 'Hero', 'Champion', 'Winner'
        ]
        
        # Generate random username
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        number = random.randint(1, 9999)
        
        username = f"{prefix}{suffix}{number}"
        
        # Check if username is available
        from src.db_compat import get_connection
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM users 
                WHERE username = %s AND sportsbook_operator_id = %s
            """, (username, user.sportsbook_operator_id))
            
            # If username is taken, try with different number
            attempts = 0
            while cursor.fetchone() and attempts < 10:
                number = random.randint(1, 9999)
                username = f"{prefix}{suffix}{number}"
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE username = %s AND sportsbook_operator_id = %s
                """, (username, user.sportsbook_operator_id))
                attempts += 1
            
            cursor.close()
        finally:
            if conn:
                conn.close()
        
        logger.info(f"Generated username for user {user.id}: {username}")
        
        return jsonify({
            'success': True,
            'username': username
        })
        
    except Exception as e:
        logger.error(f"Username generation error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate username'
        }), 500

