"""
Tenant-specific authentication routes for multi-tenant sports betting platform
"""

from flask import Blueprint, request, jsonify, g, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.multitenant_models import User, SportsbookOperator
from src.auth.session_utils import log_out_tenant
import logging
import json
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import select
from types import SimpleNamespace
logger = logging.getLogger(__name__)

tenant_auth_bp = Blueprint('tenant_auth', __name__)

def get_operator_by_subdomain(subdomain):
    """Get operator by subdomain using ORM"""
    try:
        operator = current_app.db.session.execute(
            select(SportsbookOperator).where(SportsbookOperator.subdomain == subdomain)
        ).scalar_one_or_none()
        
        if operator:
            return {
                'id': operator.id,
                'sportsbook_name': operator.sportsbook_name,
                'subdomain': operator.subdomain,
                'is_active': operator.is_active
            }
        return None
    except Exception as e:
        logger.error(f"Error getting operator by subdomain: {e}")
        return None

@tenant_auth_bp.route('/api/auth/<subdomain>/register', methods=['POST'])
def tenant_register(subdomain):
    """Register user for a specific sportsbook operator"""
    try:
        # Validate operator
        operator = get_operator_by_subdomain(subdomain)
        if not operator:
            return jsonify({
                'success': False,
                'error': 'Invalid sportsbook'
            }), 404
        
        if not operator['is_active']:
            return jsonify({
                'success': False,
                'error': 'This sportsbook is currently disabled'
            }), 403
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            # Handle form-encoded data
            data = request.form.to_dict()
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
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
        
        # Check if user already exists using ORM
        existing_user = current_app.db.session.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        ).scalar_one_or_none()
        
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
        
        # Create new user with operator association
        password_hash = generate_password_hash(password)
        
        # Get the default balance for this operator (from admin reset settings)
        try:
            from src.routes.rich_admin_interface import get_default_user_balance
            default_balance = get_default_user_balance(operator['id'])
        except Exception as e:
            print(f"⚠️ Warning: Could not get default balance for operator {operator['id']}: {e}")
            default_balance = 1000.0  # Fall back to default
        
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            balance=default_balance,
            sportsbook_operator_id=operator['id'],
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        current_app.db.session.add(new_user)
        current_app.db.session.commit()
        
        logger.info(f"New user registered for {operator['sportsbook_name']}: {username}")
        
        return jsonify({
            'success': True,
            'message': f'Welcome to {operator["sportsbook_name"]}! Account created successfully.',
            'user': {
                'id': new_user.id,
                'username': username,
                'email': email,
                'balance': default_balance,
                'sportsbook': operator['sportsbook_name']
            }
        })
        
    except Exception as e:
        logger.error(f"Registration error for {subdomain}: {e}")
        return jsonify({
            'success': False,
            'error': 'Registration failed'
        }), 500

@tenant_auth_bp.route('/api/auth/<subdomain>/login', methods=['POST'])
def tenant_login(subdomain):
    """Login user for a specific sportsbook operator"""
    try:
        # Validate operator
        operator = get_operator_by_subdomain(subdomain)
        if not operator:
            logger.error(f"Login failed: Invalid sportsbook subdomain '{subdomain}'")
            return jsonify({
                'success': False,
                'error': 'Invalid sportsbook'
            }), 404
        
        if not operator['is_active']:
            logger.error(f"Login failed: Sportsbook '{subdomain}' is disabled")
            return jsonify({
                'success': False,
                'error': 'This sportsbook is currently disabled'
            }), 403
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            # Handle form-encoded data
            data = request.form.to_dict()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        logger.info(f"Login attempt for subdomain '{subdomain}', username: '{username}'")
        
        if not username or not password:
            logger.error(f"Login failed: Missing username or password for subdomain '{subdomain}'")
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        # Find user by username or email AND operator using ORM
        user = current_app.db.session.execute(
            select(User).where(
                ((User.username == username) | (User.email == username)) & 
                (User.sportsbook_operator_id == operator['id'])
            )
        ).scalar_one_or_none()
        
        if not user:
            logger.error(f"Login failed: User '{username}' not found for operator '{subdomain}' (ID: {operator['id']})")
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        if not check_password_hash(user.password_hash, password):
            logger.error(f"Login failed: Invalid password for user '{username}' in operator '{subdomain}'")
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        if not user.is_active:
            logger.error(f"Login failed: User '{username}' account is deactivated in operator '{subdomain}'")
            return jsonify({
                'success': False,
                'error': 'Account is deactivated'
            }), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        current_app.db.session.commit()
        
        logger.info(f"User login successful for {operator['sportsbook_name']}: {username}")
        
        # Use the multi-user session manager
        from src.session_manager import get_session_manager
        session_mgr = get_session_manager()
        
        # Create a new session for this user
        session_id = session_mgr.create_session(
            user_id=user.id,
            operator_id=operator['id'],
            username=user.username,
            subdomain=subdomain
        )
        
        # Clear any existing superadmin session data to prevent conflicts
        from src.auth.session_utils import log_out_superadmin
        log_out_superadmin()
        
        # Store the session ID in Flask session for reference
        session['current_session_id'] = session_id
        
        # Set current user context for backward compatibility
        session['user_id'] = user.id
        session['username'] = user.username
        session['operator_id'] = operator['id']
        # Normalize operator_subdomain to prevent future mismatches
        session['operator_subdomain'] = (subdomain or "").strip().lower()
        session['sportsbook_name'] = operator['sportsbook_name']
        
        # Cache user data in session to avoid database queries
        session['user_data'] = build_session_user(user)
        
        session.permanent = True  # Make session persistent
        session.modified = True   # Force Flask to save the session
        
        # Debug: Log session data
        logger.info(f"Session data set for user {username}: {dict(session)}")
        
        return jsonify({
            'success': True,
            'message': f'Welcome back to {operator["sportsbook_name"]}!',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance,
                'sportsbook': operator['sportsbook_name']
            }
        })
        
    except Exception as e:
        logger.error(f"Login failed for subdomain '{subdomain}': {str(e)}")
        logger.exception("Full exception details:")
        return jsonify({
            'success': False,
            'error': f'Login failed: {str(e)}'
        }), 500

@tenant_auth_bp.route('/api/auth/<subdomain>/profile', methods=['GET'])
def get_user_profile(subdomain):
    """Get user profile for a specific operator"""
    try:
        # Check authentication using Flask session
        from flask import session
        
        # Debug: Log session data
        logger.info(f"Profile check for subdomain '{subdomain}': session data = {dict(session)}")
        
        # Check if user is authenticated for this operator (normalized comparison)
        want_subdomain = (subdomain or "").strip().lower()
        have_subdomain = (session.get('operator_subdomain') or "").strip().lower()
        
        if not session.get('user_id') or have_subdomain != want_subdomain:
            logger.warning(f"Authentication failed for subdomain '{subdomain}': user_id={session.get('user_id')}, operator_subdomain={session.get('operator_subdomain')}, want='{want_subdomain}', have='{have_subdomain}'")
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Get user from session data
        user_id = session['user_id']
        operator_id = session['operator_id']
        
        # Log session structure for debugging
        logger.info(f"Session structure: {dict(session)}")
        
        # Get user details from database using ORM
        user = current_app.db.session.get(User, user_id)
        
        if not user or user.sportsbook_operator_id != operator_id:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get operator info
        operator = get_operator_by_subdomain(subdomain)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'sportsbook': operator['sportsbook_name'] if operator else 'Unknown'
            }
        })
        
    except Exception as e:
        logger.error(f"Profile error for {subdomain}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get profile'
        }), 500


@tenant_auth_bp.route('/api/auth/<subdomain>/logout', methods=['POST'])
def tenant_logout(subdomain):
    """Logout user and clear session data"""
    try:
        from flask import session
        from src.session_manager import get_session_manager
        
        session_mgr = get_session_manager()
        
        # Remove the user's session from the session manager
        if session.get('current_session_id'):
            session_mgr.remove_session(session['current_session_id'])
        
        # Clear only tenant session data, leaving superadmin intact
        log_out_tenant(subdomain)
        
        logger.info(f"User logged out from subdomain '{subdomain}'")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout error for {subdomain}: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500


@tenant_auth_bp.route('/<subdomain>/logout')
def tenant_logout_redirect(subdomain):
    """Logout user and redirect to login page"""
    try:
        from flask import session, redirect, url_for
        from src.session_manager import get_session_manager
        
        session_mgr = get_session_manager()
        
        # Remove the user's session from the session manager
        if session.get('current_session_id'):
            session_mgr.remove_session(session['current_session_id'])
        
        # Clear only tenant session data, leaving superadmin intact
        log_out_tenant(subdomain)
        
        logger.info(f"User logged out from subdomain '{subdomain}' and redirected to login")
        
        # Redirect to the login page for this subdomain
        return redirect(f'/{subdomain}/login')
        
    except Exception as e:
        logger.error(f"Logout redirect error for {subdomain}: {e}")
        # Fallback redirect
        return redirect(f'/{subdomain}/login')


@tenant_auth_bp.route('/api/auth/debug/sessions', methods=['GET'])
def debug_sessions():
    """Debug endpoint to see all active sessions"""
    try:
        from src.session_manager import get_session_manager
        
        session_mgr = get_session_manager()
        active_sessions = session_mgr.get_active_sessions_count()
        
        return jsonify({
            'success': True,
            'active_sessions': active_sessions,
            'message': f'Currently {active_sessions} active sessions'
        })
        
    except Exception as e:
        logger.error(f"Debug sessions error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get session info'
        }), 500

@tenant_auth_bp.route('/api/auth/debug/current-session', methods=['GET'])
def debug_current_session():
    """Debug endpoint to check current Flask session"""
    try:
        from flask import session
        
        return jsonify({
            'success': True,
            'session_data': dict(session),
            'has_user_id': bool(session.get('user_id')),
            'has_operator_id': bool(session.get('operator_id')),
            'has_user_data': bool(session.get('user_data')),
            'user_id': session.get('user_id'),
            'operator_id': session.get('operator_id'),
            'operator_subdomain': session.get('operator_subdomain'),
            'is_permanent': session.permanent
        })
        
    except Exception as e:
        logger.error(f"Debug current session error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get current session info'
        }), 500


def build_session_user(user):
    """Build session user DTO from ORM User object - pure data transfer, no ORM mapping"""
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'balance': float(user.balance or 0),
        'is_active': getattr(user, 'is_active', True),
        'sportsbook_operator_id': getattr(user, 'sportsbook_operator_id', None),
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': user.last_login.isoformat() if user.last_login else None
    }


def ensure_user_data_complete(user_data):
    """Ensure user_data has all required attributes for betting routes"""
    required_attrs = {
        'id': user_data.get('id'),
        'username': user_data.get('username', 'Unknown'),
        'email': user_data.get('email', ''),
        'balance': float(user_data.get('balance', 0)),
        'is_active': user_data.get('is_active', True),
        'sportsbook_operator_id': user_data.get('sportsbook_operator_id'),
        'created_at': user_data.get('created_at'),
        'last_login': user_data.get('last_login')
    }
    return required_attrs

@tenant_auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user_profile():
    """Get current user profile from session (compatibility endpoint)"""
    try:
        from flask import session
        
        # Check if user is authenticated
        if not session.get('user_id') or not session.get('operator_id'):
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Check if we have cached user data, but ensure balance is always fresh
        cached = session.get('user_data')
        if cached and cached.get('id'):
            # Use cached data but ALWAYS fetch fresh balance from database
            # This keeps odds cache and other data intact
            pass  # Continue to database fetch for fresh balance
        
        # 2) Get user details from database using the SAME SQLAlchemy session
        user_id = session['user_id']
        operator_id = session['operator_id']
        
        # ✅ Use ONLY the ORM session - no raw database fallbacks, no db_compat
        user = current_app.db.session.get(User, user_id)
        
        if not user or user.sportsbook_operator_id != operator_id:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # 3) Use the build_session_user function for consistency
        user_data = build_session_user(user)
        
        # Cache non-sensitive user data (username, email, etc.) but NEVER balance
        # Balance must always be fetched fresh from database
        safe_cache_data = {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'is_active': user_data.get('is_active'),
            'sportsbook_operator_id': user_data.get('sportsbook_operator_id'),  # Fixed: use correct field name
            'operator_subdomain': user_data.get('operator_subdomain')
            # Balance is intentionally NOT cached - always fresh
        }
        session['user_data'] = safe_cache_data
        
        # Return in the format expected by the frontend
        # Always return fresh user_data (never cached balance)
        response = jsonify(user_data)
        
        # Add cache control headers to prevent caching of balance data
        response.headers['Cache-Control'] = 'no-store, private, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Get current user profile error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get profile'
        }), 500

@tenant_auth_bp.route('/api/auth/force-refresh', methods=['POST'])
def force_refresh_user_data():
    """Force refresh user data by clearing session cache"""
    try:
        from flask import session
        
        # Check if user is authenticated
        if not session.get('user_id') or not session.get('operator_id'):
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Clear cached user data to force fresh fetch
        if 'user_data' in session:
            del session['user_data']
            print(f"🗑️ Force refreshed user data for user {session['user_id']}")
        
        # Update cache timestamp to invalidate any other caches
        session['balance_cache_timestamp'] = int(time.time())
        
        return jsonify({
            'success': True,
            'message': 'User data cache cleared successfully'
        })
        
    except Exception as e:
        logger.error(f"Force refresh error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to force refresh'
        }), 500


def session_required(f):
    """Decorator to require Flask session for protected routes"""
    from functools import wraps
    from flask import session, jsonify, g
    
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if user is authenticated via session
        if not session.get('user_id') or not session.get('operator_id'):
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Check if we already have user data cached in session
        if 'user_data' in session:
            user_data = session['user_data']
            # ✅ Ensure all required attributes are present before creating SimpleNamespace
            complete_user_data = ensure_user_data_complete(user_data)
            g.current_user = SimpleNamespace(**complete_user_data)
            return f(*args, **kwargs)
        
        # Only query database if user data not cached - use ORM session
        try:
            from flask import current_app
            user = current_app.db.session.get(User, session['user_id'])
            
            if not user or user.sportsbook_operator_id != session['operator_id']:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
            
            # Check if user is blocked by admin
            if not getattr(user, 'is_active', True):
                return jsonify({
                    'success': False,
                    'error': 'Account has been disabled by administrator'
                }), 403
            
            # Cache user data in session for future requests using the clean DTO
            session['user_data'] = build_session_user(user)
            
            # ✅ Ensure all required attributes are present before creating SimpleNamespace
            complete_user_data = ensure_user_data_complete(session['user_data'])
            g.current_user = SimpleNamespace(**complete_user_data)
                
        except Exception as e:
            logger.error(f"Session authentication error: {e}")
            return jsonify({
                'success': False,
                'error': 'Authentication failed'
            }), 500
        
        return f(*args, **kwargs)
    
    return decorated

