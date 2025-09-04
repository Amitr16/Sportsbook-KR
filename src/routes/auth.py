"""
Authentication routes for sports betting platform
"""

from flask import Blueprint, request, jsonify, g, redirect, make_response, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.betting import User
import jwt
import datetime
from functools import wraps
import logging
import os
import urllib.parse

import requests

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
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')
GOOGLE_AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URI = 'https://openidconnect.googleapis.com/v1/userinfo'


@auth_bp.route('/google/login', methods=['GET'])
def google_login():
    """Start Google OAuth login by redirecting to Google's consent screen"""
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'include_granted_scopes': 'true',
        'prompt': 'consent'
    }
    url = f"{GOOGLE_AUTH_URI}?{urllib.parse.urlencode(params)}"
    return redirect(url, code=302)


@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Handle Google's callback, exchange code for tokens, create/login user, return JWT and redirect to app"""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'Missing authorization code'}), 400

        # Exchange authorization code for tokens
        token_payload = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        token_resp = requests.post(GOOGLE_TOKEN_URI, data=token_payload, timeout=10)
        if not token_resp.ok:
            return jsonify({'success': False, 'error': 'Failed to exchange code for token'}), 400
        tokens = token_resp.json()
        id_token = tokens.get('id_token')
        access_token = tokens.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'No access token received'}), 400

        # Fetch user info
        userinfo_resp = requests.get(
            GOOGLE_USERINFO_URI,
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

        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Ensure unique username
            base_username = (name or email.split('@')[0]).replace(' ', '').lower()
            username = base_username
            suffix = 1
            while User.query.filter_by(username=username).first() is not None:
                suffix += 1
                username = f"{base_username}{suffix}"

            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(f"google:{sub}"),
                balance=1000.0
            )
            db.session.add(user)
            db.session.commit()

        # Update last_login
        user.last_login = datetime.datetime.utcnow()
        db.session.commit()

        # Issue our JWT
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        app_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

        # Redirect back to frontend root with token in hash and also set a short-lived cookie so JS can pick it up
        redirect_url = f"/#token={urllib.parse.quote(app_token)}"
        resp = make_response(redirect(redirect_url, code=302))
        # Not HttpOnly so that client JS can read and migrate it into localStorage, then clear
        resp.set_cookie('app_token', app_token, max_age=600, samesite='Lax', secure=False, httponly=False)
        return resp

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return jsonify({'success': False, 'error': 'OAuth process failed'}), 500

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

