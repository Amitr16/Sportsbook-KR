"""
Authentication routes for sports betting platform
"""

from flask import Blueprint, request, jsonify, g, redirect, make_response, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.betting import User
import jwt
import datetime
from functools import wraps
import logging
import os
import urllib.parse

import requests

# Make sure .env / env.local are loaded on import (no circulars here; env_loader has no app deps)
import src.config.env_loader  # noqa: F401

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

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
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/google/callback"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "userinfo_uri": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    }


@auth_bp.route('/google/login', methods=['GET'])
def google_login():
    """Start Google OAuth login by redirecting to Google's consent screen"""
    cfg = _google_oauth_cfg()
    
    # Get redirect URI from query parameter or use default
    redirect_uri = request.args.get('redirect_uri', cfg["redirect_uri"])
    
    # Hard guard to avoid "client_id=None"
    if not cfg["client_id"] or not cfg["client_secret"]:
        current_app.logger.error("Google OAuth env missing: GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET")
        # For XHR/API, return JSON; for browser nav you can redirect to a friendly error/login
        if request.headers.get("Accept", "").find("application/json") >= 0 or request.path.startswith("/api"):
            return jsonify({"success": False, "error": "Google OAuth not configured"}), 500
        return redirect('/login', code=302)
    
    # Store the tenant context in session for redirect after OAuth
    referrer = request.headers.get('Referer', '')
    if '/megabook' in referrer or '/megabook/' in referrer:
        session['original_tenant'] = 'megabook'
    elif '/kr00' in referrer or '/kr00/' in referrer:
        session['original_tenant'] = 'kr00'
    else:
        # Try to extract tenant from referrer
        import re
        tenant_match = re.search(r'/([^/]+)/', referrer)
        if tenant_match:
            session['original_tenant'] = tenant_match.group(1)
        else:
            session['original_tenant'] = 'megabook'  # Default
    
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
    """Handle Google's callback, exchange code for tokens, create/login user, return JWT and redirect to app"""
    try:
        cfg = _google_oauth_cfg()
        
        code = request.args.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'Missing authorization code'}), 400

        # Get redirect URI from query parameter or use default
        redirect_uri = request.args.get('redirect_uri', cfg["redirect_uri"])
        
        if not cfg["client_id"] or not cfg["client_secret"]:
            current_app.logger.error("Google OAuth env missing on callback")
            return jsonify({'success': False, 'error': 'Google OAuth not configured'}), 500
        
        # Exchange authorization code for tokens
        token_payload = {
            'code': code,
            'client_id': cfg["client_id"],
            'client_secret': cfg["client_secret"],
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        token_resp = requests.post(cfg["token_uri"], data=token_payload, timeout=10)
        if not token_resp.ok:
            return jsonify({'success': False, 'error': 'Failed to exchange code for token'}), 400
        tokens = token_resp.json()
        id_token = tokens.get('id_token')
        access_token = tokens.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'No access token received'}), 400

        # Fetch user info
        userinfo_resp = requests.get(
            cfg["userinfo_uri"],
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if not userinfo_resp.ok:
            return jsonify({'success': False, 'error': 'Failed to fetch user info'}), 400
        userinfo = userinfo_resp.json()

        email = userinfo.get('email')
        name = userinfo.get('name') or (userinfo.get('given_name') or 'user')
        sub = userinfo.get('sub')  # Google user ID
        if not email:
            return jsonify({'success': False, 'error': 'Email not available from Google'}), 400

        # Find or create user using raw SQL (compatible with existing database)
        from src.db_compat import connect
        conn = connect()
        
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            # Ensure unique username
            base_username = (name or email.split('@')[0]).replace(' ', '').lower()[:15]
            username = base_username
            suffix = 1
            while conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone():
                suffix += 1
                username = f"{base_username}{suffix}"

            # Create new user
            conn.execute("""
                INSERT INTO users (username, email, password_hash, balance, is_active, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, email, generate_password_hash(f"google:{sub}"), 1000.0, 1, 
                  datetime.datetime.utcnow(), datetime.datetime.utcnow()))
            conn.commit()
            
            # Get the created user
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        else:
            # Update last_login
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                        (datetime.datetime.utcnow(), user['id']))
            conn.commit()

        conn.close()

        # Set session data for the user
        from flask import session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['email'] = user['email']
        session['balance'] = user['balance']
        session['role'] = 'user'
        
        # Set operator context for tenant compatibility
        session_tenant = session.get('original_tenant', 'megabook')
        if session_tenant == 'megabook':
            # Get the megabook operator ID from database
            from src.db_compat import connect
            conn = connect()
            operator = conn.execute("SELECT id FROM sportsbook_operators WHERE subdomain = 'megabook'").fetchone()
            if operator:
                session['operator_id'] = operator['id']
                session['operator_name'] = 'megabook'
            conn.close()
        
        session.permanent = True

        # Determine redirect URL based on referrer or default
        referrer = request.headers.get('Referer', '')
        logger.info(f"Google OAuth callback - Referrer: {referrer}")
        
        # Check if we have a redirect_uri parameter from the login request
        redirect_uri_param = request.args.get('redirect_uri', '')
        logger.info(f"Google OAuth callback - Redirect URI param: {redirect_uri_param}")
        
        # Check session for the original tenant context
        session_tenant = session.get('original_tenant', '')
        logger.info(f"Google OAuth callback - Session tenant: {session_tenant}")
        
        if '/kr00' in referrer or '/kr00/' in referrer or session_tenant == 'kr00':
            redirect_url = '/kr00'
        elif '/megabook' in referrer or '/megabook/' in referrer or session_tenant == 'megabook':
            redirect_url = '/megabook'
        elif redirect_uri_param and 'megabook' in redirect_uri_param:
            redirect_url = '/megabook'
        elif redirect_uri_param and 'kr00' in redirect_uri_param:
            redirect_url = '/kr00'
        else:
            # Default to megabook since that's what we're testing
            redirect_url = '/megabook'

        logger.info(f"Google OAuth callback - Redirecting to: {redirect_url}")
        
        # Redirect back to the betting page
        return redirect(redirect_url, code=302)

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return jsonify({'success': False, 'error': 'OAuth process failed'}), 500

@auth_bp.route('/me', methods=['GET'])
def get_user_profile():
    """Get current user profile from session"""
    from flask import session
    from src.db_compat import connect
    
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        conn = connect()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'balance': user['balance'],
            'last_login': user['last_login'].isoformat() if user['last_login'] else None
        })
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
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
        
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            balance=1000.0  # Starting balance
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

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
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

