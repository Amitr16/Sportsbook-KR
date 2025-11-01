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
    """Get operator by subdomain using tracked connection"""
    try:
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("SELECT * FROM sportsbook_operators WHERE subdomain = %s LIMIT 1", (subdomain,))
                operator_row = cursor.fetchone()
                operator = operator_row if operator_row else None
        
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
        
        # Check if user already exists for this specific operator using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("""
                    SELECT * FROM users 
                    WHERE (username = %s OR email = %s) 
                    AND sportsbook_operator_id = %s 
                    LIMIT 1
                """, (username, email, operator['id']))
                existing_user_row = cursor.fetchone()
                existing_user = existing_user_row if existing_user_row else None
        
        if existing_user:
            if existing_user.username == username:
                return jsonify({
                    'success': False,
                    'error': 'Username already exists for this sportsbook'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': 'Email already exists for this sportsbook'
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
        
        # Create Web3 wallet for the user via Crossmint
        web3_wallet_address = None
        web3_wallet_key = None
        try:
            from src.services.crossmint_aptos_service import get_crossmint_service
            crossmint_service = get_crossmint_service()
            web3_wallet_address, web3_wallet_key = crossmint_service.create_wallet(
                user_id=0,  # Will be updated after user creation
                email=email,
                username=username,
                operator_id=operator['id']
            )
            logger.info(f"✅ Created Web3 wallet for {username}: {web3_wallet_address}")
        except Exception as wallet_error:
            logger.warning(f"⚠️ Failed to create Web3 wallet for {username}: {wallet_error}")
            # Continue registration even if Web3 wallet creation fails
        
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            balance=default_balance,
            sportsbook_operator_id=operator['id'],
            is_active=True,
            created_at=datetime.utcnow(),
            web3_wallet_address=web3_wallet_address,
            web3_wallet_key=web3_wallet_key
        )
        
        # Create user using tracked connection
        with connection_ctx(timeout=5) as conn:
            with conn.transaction():
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, balance, sportsbook_operator_id, is_active, created_at, web3_wallet_address, web3_wallet_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (username, email, password_hash, default_balance, operator['id'], True, datetime.utcnow(), web3_wallet_address, web3_wallet_key))
                user_id = cursor.fetchone()['id']
        
        new_user = {'id': user_id, 'username': username, 'email': email, 'balance': default_balance}
        
        logger.info(f"New user registered for {operator['sportsbook_name']}: {username}")
        
        # Credit initial balance to Web3 wallet via custodial USDT contract
        if web3_wallet_address and default_balance > 0:
            try:
                from src.services.crossmint_aptos_service import get_crossmint_service
                crossmint_service = get_crossmint_service()
                tx_hash = crossmint_service.deposit(web3_wallet_address, default_balance)
                if tx_hash:
                    logger.info(f"✅ Credited {default_balance} USDT to Web3 wallet - tx: {tx_hash}")
                else:
                    logger.warning(f"⚠️ Failed to credit initial balance to Web3 wallet - admin wallet may not be configured")
            except Exception as deposit_error:
                logger.warning(f"⚠️ Failed to deposit initial balance to Web3 wallet: {deposit_error}")
        
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
        
        # Find user by username or email AND operator using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                cursor.execute("""
                    SELECT * FROM users 
                    WHERE (username = %s OR email = %s) 
                    AND sportsbook_operator_id = %s 
                    LIMIT 1
                """, (username, username, operator['id']))
                user_row = cursor.fetchone()
                user = user_row if user_row else None
        
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
        
        # Update last login using tracked connection
        with connection_ctx(timeout=3) as conn:
            with conn.transaction():
                cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (datetime.utcnow(), user['id']))
        
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
        
        # Get user details from database using tracked connection
        from src.db_compat import connection_ctx
        with connection_ctx(timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '2000ms'")
                cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
                user_row = cursor.fetchone()
                user = user_row if user_row else None
        
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
        
        logger.info(f"🚪 Logout initiated for subdomain '{subdomain}'")
        logger.info(f"🔍 Session before logout: {dict(session)}")
        
        session_mgr = get_session_manager()
        
        # Remove the user's session from the session manager
        if session.get('current_session_id'):
            session_mgr.remove_session(session['current_session_id'])
        
        # Clear only tenant session data, leaving superadmin intact
        log_out_tenant(subdomain)
        
        # CRITICAL: Clear ALL user and operator session data
        # Save superadmin session if it exists
        superadmin_session = session.get('sid:_superadmin')
        
        # Clear the ENTIRE session (nuclear option)
        session.clear()
        
        # Restore superadmin session if it existed
        if superadmin_session:
            session['sid:_superadmin'] = superadmin_session
        
        # Mark session as permanent and modified to force save
        session.permanent = True
        session.modified = True
        
        logger.info(f"🔍 Session after logout: {dict(session)}")
        logger.info(f"✅ User logged out from subdomain '{subdomain}' and redirected to main page")
        
        # Create redirect response with cache-busting headers
        response = redirect(f'/{subdomain}')
        
        # Add cache-busting headers to force browser to not cache the logout
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # Clear the session cookie explicitly
        response.set_cookie('session', '', expires=0, max_age=0)
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Logout redirect error for {subdomain}: {e}")
        # Fallback redirect to main page
        return redirect(f'/{subdomain}')


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
    from flask import session
    
    # Get sportsbook_operator_id from user, fallback to session
    sportsbook_operator_id = getattr(user, 'sportsbook_operator_id', None)
    if not sportsbook_operator_id:
        sportsbook_operator_id = session.get('operator_id')
    
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'balance': float(user.balance or 0),
        'is_active': getattr(user, 'is_active', True),
        'sportsbook_operator_id': sportsbook_operator_id,
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
        from flask import session, request
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("=" * 50)
        logger.info("🔍 tenant_auth /api/auth/me endpoint hit")
        logger.info(f"🔍 Request URL: {request.url}")
        logger.info(f"🔍 Session data: {dict(session)}")
        
        # Check if user is authenticated (user_id only - operator is context, not identity)
        # Check both possible session formats: user_id directly or user_data.id
        user_id = session.get('user_id') or (session.get('user_data', {}).get('id') if session.get('user_data') else None)
        if not user_id:
            logger.warning("❌ No user_id in session - user not authenticated")
            logger.warning(f"❌ Available session keys: {list(session.keys())}")
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
        # user_id already extracted above
        operator_id = session.get('operator_id')  # Optional - may be missing after OAuth
        
        logger.info(f"🔍 Looking up user_id: {user_id}, operator_id: {operator_id}")
        
        # ✅ Use db_compat for consistency with OAuth callback
        try:
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=5) as conn:
                # Set very short statement timeout for this endpoint
                with conn.cursor() as c:
                    c.execute("SET LOCAL statement_timeout = '2000ms'")
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, username, email, balance, is_active, created_at, last_login, sportsbook_operator_id FROM users WHERE id = %s", (user_id,))
                    user = cursor.fetchone()
            logger.info(f"🔍 Database query result: {user}")
        except Exception as e:
            logger.error(f"❌ Database query failed: {e}")
            return jsonify({
                'success': False,
                'error': 'Database error'
            }), 500
        
        if not user:
            logger.warning(f"❌ User not found in database for user_id: {user_id}")
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        # Only check operator_id if it exists in session
        # Note: user is now a dict from db_compat with dict_row
        if operator_id and user.get('sportsbook_operator_id') != operator_id:
            return jsonify({
                'success': False,
                'error': 'User not found for this operator'
            }), 404
        
        # 3) Build user data from raw database result
        logger.info(f"✅ User found: {user}")
        user_data = {
            'id': user['id'],
            'username': user['username'], 
            'email': user['email'],
            'balance': float(user['balance']) if user['balance'] else 0.0,
            'is_active': bool(user['is_active']) if user['is_active'] is not None else True,
            'created_at': user['created_at'].isoformat() if user['created_at'] else None,
            'last_login': user['last_login'].isoformat() if user['last_login'] else None,
            'sportsbook_operator_id': user['sportsbook_operator_id'] if user['sportsbook_operator_id'] else None
        }
        logger.info(f"✅ User data built: {user_data}")
        
        # Cache non-sensitive user data (username, email, etc.) but NEVER balance
        # Balance must always be fetched fresh from database
        safe_cache_data = {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'is_active': user_data.get('is_active'),
            'created_at': user_data.get('created_at'),
            'last_login': user_data.get('last_login')
            # Balance is intentionally NOT cached - always fresh
        }
        session['user_data'] = safe_cache_data
        
        # Return in the format expected by the frontend
        # Always return fresh user_data (never cached balance)
        # Convert datetime objects to strings for JSON serialization
        def safe_isoformat(dt):
            if dt is None:
                return None
            try:
                return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
            except Exception:
                return str(dt)
        
        response_data = {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'balance': user_data.get('balance'),
            'is_active': user_data.get('is_active'),
            'created_at': safe_isoformat(user_data.get('created_at')),
            'last_login': safe_isoformat(user_data.get('last_login')),
            'sportsbook_operator_id': user_data.get('sportsbook_operator_id'),
            'operator_required': operator_id is None
        }
        response = jsonify(response_data)
        
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

@tenant_auth_bp.route('/api/auth/admin/me', methods=['GET'])
def get_admin_profile():
    """Get admin profile from session"""
    try:
        from flask import session
        
        # Superadmin (global)
        if session.get('admin_id') and session.get('is_superadmin'):
            return jsonify({
                'success': True,
                'authenticated': True,
                'role': 'superadmin',
                'admin_id': session['admin_id'],
                'operator_id': None
            }), 200
        
        # Tenant admin
        if session.get('admin_id') and session.get('operator_id'):
            return jsonify({
                'success': True,
                'authenticated': True,
                'role': 'admin',
                'admin_id': session['admin_id'],
                'operator_id': session['operator_id'],
                'operator_name': session.get('operator_name')
            }), 200
        
        return jsonify({
            'success': False,
            'error': 'Admin authentication required'
        }), 401
        
    except Exception as e:
        logger.error(f"Get admin profile error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get admin profile'
        }), 500

@tenant_auth_bp.route('/api/debug/session', methods=['GET'])
def debug_session():
    """Debug endpoint to check session data"""
    from flask import session, g
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 DEBUG SESSION ENDPOINT")
    logger.info(f"🔍 Session data: {dict(session)}")
    logger.info(f"🔍 g.current_user: {getattr(g, 'current_user', 'Not set')}")
    
    return jsonify({
        'session_data': dict(session),
        'g_current_user': str(getattr(g, 'current_user', 'Not set')),
        'user_id': session.get('user_id'),
        'operator_id': session.get('operator_id'),
        'user_data': session.get('user_data')
    })

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
        # Debug logging for session validation
        logger.info(f"🔍 SESSION DEBUG: user_id={session.get('user_id')}, operator_id={session.get('operator_id')}")
        logger.info(f"🔍 SESSION DEBUG: session keys={list(session.keys())}")
        
        # Check if user is authenticated via session
        if not session.get('user_id') or not session.get('operator_id'):
            logger.warning(f"❌ SESSION FAILED: Missing user_id or operator_id")
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Check if we already have user data cached in session
        if 'user_data' in session:
            user_data = session['user_data']
            
            # Check if user is disabled from cached data
            if not user_data.get('is_active', True):
                logger.warning(f"❌ CACHED USER DISABLED: user_id={session.get('user_id')}")
                return jsonify({
                    'success': False,
                    'error': 'Account has been disabled by administrator'
                }), 403
            
            # Re-validate is_active status from database to prevent stale cache issues
            # This ensures disabled users can't continue using cached data
            try:
                from flask import current_app
                from src.db_compat import connection_ctx
                with connection_ctx(timeout=2) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = '1000ms'")
                        cursor.execute("SELECT is_active FROM users WHERE id = %s LIMIT 1", (session['user_id'],))
                        result = cursor.fetchone()
                        if result:
                            db_is_active = result[0] if isinstance(result, tuple) else result['is_active']
                            if not db_is_active:
                                logger.warning(f"❌ DB VALIDATION FAILED - USER DISABLED: user_id={session.get('user_id')}")
                                # Clear the stale cache
                                session.pop('user_data', None)
                                return jsonify({
                                    'success': False,
                                    'error': 'Account has been disabled by administrator'
                                }), 403
            except Exception as validation_error:
                logger.warning(f"Could not validate is_active status: {validation_error}")
                # Continue with cached data if validation fails
            
            # Fix: Ensure sportsbook_operator_id is present
            if 'sportsbook_operator_id' not in user_data and session.get('operator_id'):
                user_data['sportsbook_operator_id'] = session.get('operator_id')
                session['user_data'] = user_data
                logger.info(f"✅ Fixed user_data: added sportsbook_operator_id = {session.get('operator_id')}")
            
            # ✅ Ensure all required attributes are present before creating SimpleNamespace
            complete_user_data = ensure_user_data_complete(user_data)
            g.current_user = SimpleNamespace(**complete_user_data)
            return f(*args, **kwargs)
        
        # Only query database if user data not cached - use ORM session
        try:
            from flask import current_app
            # Get user using tracked connection
            from src.db_compat import connection_ctx
            with connection_ctx(timeout=3) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '2000ms'")
                    cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (session['user_id'],))
                    user_row = cursor.fetchone()
                    user = user_row if user_row else None
            
            # Debug logging
            logger.info(f"🔍 session_required - user: {user}")
            logger.info(f"🔍 session_required - user.sportsbook_operator_id: {getattr(user, 'sportsbook_operator_id', None) if user else None}")
            logger.info(f"🔍 session_required - session['operator_id']: {session.get('operator_id')}")
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
            
            # Only check operator_id if both exist and don't match
            session_operator_id = session.get('operator_id')
            user_operator_id = getattr(user, 'sportsbook_operator_id', None)
            
            if session_operator_id and user_operator_id and user_operator_id != session_operator_id:
                logger.warning(f"⚠️ Operator mismatch: user has {user_operator_id}, session has {session_operator_id}")
                return jsonify({
                    'success': False,
                    'error': 'User not found for this operator'
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

