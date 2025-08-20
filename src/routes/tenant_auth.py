"""
Tenant-aware authentication routes for multi-tenant sportsbook system
"""

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.betting import db, User
import jwt
import datetime
from functools import wraps
import logging
import sqlite3

logger = logging.getLogger(__name__)

tenant_auth_bp = Blueprint('tenant_auth', __name__)

DATABASE_PATH = 'src/database/app.db'
JWT_SECRET_KEY = 'your-secret-key-change-in-production'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_operator_by_subdomain(subdomain):
    """Get operator by subdomain"""
    conn = get_db_connection()
    operator = conn.execute("""
        SELECT id, sportsbook_name, subdomain, is_active
        FROM sportsbook_operators 
        WHERE subdomain = ?
    """, (subdomain,)).fetchone()
    conn.close()
    
    return dict(operator) if operator else None

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
        
        data = request.get_json()
        
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
        
        # Check if user already exists (globally unique usernames and emails)
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
        
        # Create new user with operator association
        password_hash = generate_password_hash(password)
        
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            balance=1000.0,  # Starting balance
            sportsbook_operator_id=operator['id']  # Associate with operator
        )
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"New user registered for {operator['sportsbook_name']}: {username}")
        
        return jsonify({
            'success': True,
            'message': f'Welcome to {operator["sportsbook_name"]}! Account created successfully.',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance,
                'sportsbook': operator['sportsbook_name']
            }
        })
        
    except Exception as e:
        logger.error(f"Registration error for {subdomain}: {e}")
        db.session.rollback()
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
            return jsonify({
                'success': False,
                'error': 'Invalid sportsbook'
            }), 404
        
        if not operator['is_active']:
            return jsonify({
                'success': False,
                'error': 'This sportsbook is currently disabled'
            }), 403
        
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        # Find user by username or email AND operator
        user = User.query.filter(
            ((User.username == username) | (User.email == username)) &
            (User.sportsbook_operator_id == operator['id'])
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
        
        # Generate JWT token with operator context
        token_payload = {
            'user_id': user.id,
            'username': user.username,
            'operator_id': operator['id'],
            'operator_subdomain': subdomain,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm='HS256')
        
        logger.info(f"User login for {operator['sportsbook_name']}: {username}")
        
        return jsonify({
            'success': True,
            'message': f'Welcome back to {operator["sportsbook_name"]}!',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance,
                'sportsbook': operator['sportsbook_name']
            }
        })
        
    except Exception as e:
        logger.error(f"Login error for {subdomain}: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

@tenant_auth_bp.route('/api/auth/<subdomain>/profile', methods=['GET'])
def get_user_profile(subdomain):
    """Get user profile for a specific operator"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'Authorization token required'
            }), 401
        
        try:
            token = auth_header.split(' ')[1]  # Bearer <token>
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        except (IndexError, jwt.InvalidTokenError):
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
        
        # Validate operator context
        if data.get('operator_subdomain') != subdomain:
            return jsonify({
                'success': False,
                'error': 'Invalid operator context'
            }), 403
        
        # Get user
        user = User.query.filter(
            (User.id == data['user_id']) &
            (User.sportsbook_operator_id == data['operator_id'])
        ).first()
        
        if not user:
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

