"""
Updated Sportsbook registration API endpoints with Wallet Integration
Includes 4-wallet system initialization during registration
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
from datetime import datetime, date
import json

sportsbook_bp = Blueprint('sportsbook', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_subdomain(sportsbook_name, login):
    """Generate a unique subdomain from sportsbook name and login"""
    # Clean the sportsbook name and login
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', sportsbook_name.lower())
    clean_login = re.sub(r'[^a-zA-Z0-9]', '', login.lower())
    
    # Try different combinations - prioritize sportsbook name
    candidates = [
        clean_name[:15],  # "demosportshub" - prioritize sportsbook name
        clean_name[:10],
        clean_login,
        f"{clean_name[:8]}{clean_login[:3]}",
        f"{clean_login}{clean_name[:5]}",
    ]
    
    conn = get_db_connection()
    
    for candidate in candidates:
        if len(candidate) >= 3:
            # Check if subdomain is available
            existing = conn.execute(
                "SELECT id FROM sportsbook_operators WHERE subdomain = ?", 
                (candidate,)
            ).fetchone()
            
            if not existing:
                conn.close()
                return candidate
    
    # If all candidates are taken, append numbers
    base = clean_login[:8] if clean_login else clean_name[:8]
    counter = 1
    
    while counter < 1000:
        candidate = f"{base}{counter}"
        existing = conn.execute(
            "SELECT id FROM sportsbook_operators WHERE subdomain = ?", 
            (candidate,)
        ).fetchone()
        
        if not existing:
            conn.close()
            return candidate
        counter += 1
    
    conn.close()
    raise Exception("Unable to generate unique subdomain")

def create_operator_wallets(operator_id, conn):
    """
    Create the 4 wallets for a new operator
    Called during sportsbook registration
    """
    cursor = conn.cursor()
    
    # Wallet 1: Bookmaker's Capital - $10,000 default
    cursor.execute("""
        INSERT INTO operator_wallets 
        (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        operator_id, 'bookmaker_capital', 10000.0, 10000.0, 1.0, 
        datetime.utcnow(), datetime.utcnow()
    ))
    wallet1_id = cursor.lastrowid
    
    # Wallet 2: Liquidity Pool Allocation - $40,000 default (5x leverage)
    cursor.execute("""
        INSERT INTO operator_wallets 
        (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        operator_id, 'liquidity_pool', 40000.0, 40000.0, 5.0, 
        datetime.utcnow(), datetime.utcnow()
    ))
    wallet2_id = cursor.lastrowid
    
    # Wallet 3: Revenue Wallet - starts at $0
    cursor.execute("""
        INSERT INTO operator_wallets 
        (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        operator_id, 'revenue', 0.0, 0.0, 1.0, 
        datetime.utcnow(), datetime.utcnow()
    ))
    wallet3_id = cursor.lastrowid
    
    # Wallet 4: Bookmaker's Earnings - starts at $0
    cursor.execute("""
        INSERT INTO operator_wallets 
        (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        operator_id, 'bookmaker_earnings', 0.0, 0.0, 1.0, 
        datetime.utcnow(), datetime.utcnow()
    ))
    wallet4_id = cursor.lastrowid
    
    # Create initial daily balance records for wallets with non-zero balances
    today = date.today()
    
    # Wallet 1 initial balance record
    cursor.execute("""
        INSERT INTO wallet_daily_balances 
        (wallet_id, date, opening_balance, closing_balance, daily_pnl, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (wallet1_id, today, 10000.0, 10000.0, 0.0, datetime.utcnow()))
    
    # Wallet 2 initial balance record
    cursor.execute("""
        INSERT INTO wallet_daily_balances 
        (wallet_id, date, opening_balance, closing_balance, daily_pnl, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (wallet2_id, today, 40000.0, 40000.0, 0.0, datetime.utcnow()))
    
    # Wallet 3 initial balance record
    cursor.execute("""
        INSERT INTO wallet_daily_balances 
        (wallet_id, date, opening_balance, closing_balance, daily_pnl, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (wallet3_id, today, 0.0, 0.0, 0.0, datetime.utcnow()))
    
    # Wallet 4 initial balance record
    cursor.execute("""
        INSERT INTO wallet_daily_balances 
        (wallet_id, date, opening_balance, closing_balance, daily_pnl, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (wallet4_id, today, 0.0, 0.0, 0.0, datetime.utcnow()))
    
    # Create initial funding transactions
    cursor.execute("""
        INSERT INTO wallet_transactions 
        (wallet_id, transaction_type, amount, balance_before, balance_after, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        wallet1_id, 'initial_funding', 10000.0, 0.0, 10000.0, 
        'Initial bookmaker capital funding', datetime.utcnow()
    ))
    
    cursor.execute("""
        INSERT INTO wallet_transactions 
        (wallet_id, transaction_type, amount, balance_before, balance_after, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        wallet2_id, 'initial_funding', 40000.0, 0.0, 40000.0, 
        'Initial liquidity pool allocation (5x leverage)', datetime.utcnow()
    ))
    
    return {
        'wallet1_id': wallet1_id,
        'wallet2_id': wallet2_id,
        'wallet3_id': wallet3_id,
        'wallet4_id': wallet4_id
    }

@sportsbook_bp.route('/register-sportsbook', methods=['POST'])
def register_sportsbook():
    """Register a new sportsbook operator with wallet initialization"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['sportsbook_name', 'login', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        sportsbook_name = data['sportsbook_name'].strip()
        login = data['login'].strip()
        password = data['password']
        email = data.get('email', '').strip() if data.get('email') else None
        
        # Validate sportsbook name
        if len(sportsbook_name) < 3 or len(sportsbook_name) > 100:
            return jsonify({
                'success': False,
                'error': 'Sportsbook name must be between 3 and 100 characters'
            }), 400
        
        # Validate login
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', login):
            return jsonify({
                'success': False,
                'error': 'Login must be 3-50 characters, letters, numbers, and underscores only'
            }), 400
        
        # Validate password
        if len(password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Validate email if provided
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({
                'success': False,
                'error': 'Invalid email address'
            }), 400
        
        conn = get_db_connection()
        
        try:
            # Check if sportsbook name already exists
            existing_name = conn.execute(
                "SELECT id FROM sportsbook_operators WHERE sportsbook_name = ?", 
                (sportsbook_name,)
            ).fetchone()
            
            if existing_name:
                return jsonify({
                    'success': False,
                    'error': 'A sportsbook with this name already exists'
                }), 400
            
            # Check if login already exists
            existing_login = conn.execute(
                "SELECT id FROM sportsbook_operators WHERE login = ?", 
                (login,)
            ).fetchone()
            
            if existing_login:
                return jsonify({
                    'success': False,
                    'error': 'This login username is already taken'
                }), 400
            
            # Generate unique subdomain
            try:
                subdomain = generate_subdomain(sportsbook_name, login)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': 'Unable to generate unique subdomain. Please try a different name or login.'
                }), 400
            
            # Hash password
            password_hash = generate_password_hash(password)
            
            # Default settings
            default_settings = {
                'theme': 'default',
                'currency': 'USD',
                'timezone': 'UTC',
                'max_bet_amount': 10000,
                'min_bet_amount': 1
            }
            
            # Insert new sportsbook operator
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sportsbook_operators 
                (sportsbook_name, login, password_hash, email, subdomain, settings, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sportsbook_name,
                login,
                password_hash,
                email,
                subdomain,
                json.dumps(default_settings),
                datetime.utcnow(),
                datetime.utcnow()
            ))
            
            operator_id = cursor.lastrowid
            
            # Create the 4 wallets for the new operator
            wallet_ids = create_operator_wallets(operator_id, conn)
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Sportsbook registered successfully with wallet system initialized',
                'sportsbook_name': sportsbook_name,
                'login': login,
                'subdomain': subdomain,
                'operator_id': operator_id,
                'admin_url': f'/{subdomain}/admin',
                'sportsbook_url': f'/{subdomain}',
                'wallets': {
                    'bookmaker_capital': {
                        'id': wallet_ids['wallet1_id'],
                        'balance': 10000.0,
                        'description': 'Bookmaker\'s own capital'
                    },
                    'liquidity_pool': {
                        'id': wallet_ids['wallet2_id'],
                        'balance': 40000.0,
                        'leverage': '5x',
                        'description': 'Liquidity pool allocation'
                    },
                    'revenue': {
                        'id': wallet_ids['wallet3_id'],
                        'balance': 0.0,
                        'description': 'Daily revenue collection'
                    },
                    'bookmaker_earnings': {
                        'id': wallet_ids['wallet4_id'],
                        'balance': 0.0,
                        'description': 'Bookmaker\'s personal earnings'
                    }
                }
            }), 201
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Registration failed: {str(e)}'
        }), 500

@sportsbook_bp.route('/operator-wallets/<int:operator_id>', methods=['GET'])
def get_operator_wallets(operator_id):
    """Get all wallets for an operator"""
    try:
        conn = get_db_connection()
        
        # Get operator info
        operator = conn.execute(
            "SELECT id, sportsbook_name, login FROM sportsbook_operators WHERE id = ?",
            (operator_id,)
        ).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Operator not found'
            }), 404
        
        # Get all wallets for the operator
        wallets = conn.execute("""
            SELECT id, wallet_type, current_balance, initial_balance, leverage_multiplier, 
                   is_active, created_at, updated_at
            FROM operator_wallets 
            WHERE operator_id = ? 
            ORDER BY 
                CASE wallet_type 
                    WHEN 'bookmaker_capital' THEN 1
                    WHEN 'liquidity_pool' THEN 2
                    WHEN 'revenue' THEN 3
                    WHEN 'bookmaker_earnings' THEN 4
                END
        """, (operator_id,)).fetchall()
        
        conn.close()
        
        wallet_data = []
        for wallet in wallets:
            wallet_data.append({
                'id': wallet['id'],
                'wallet_type': wallet['wallet_type'],
                'current_balance': wallet['current_balance'],
                'initial_balance': wallet['initial_balance'],
                'leverage_multiplier': wallet['leverage_multiplier'],
                'is_active': bool(wallet['is_active']),
                'created_at': wallet['created_at'],
                'updated_at': wallet['updated_at']
            })
        
        return jsonify({
            'success': True,
            'operator': {
                'id': operator['id'],
                'sportsbook_name': operator['sportsbook_name'],
                'login': operator['login']
            },
            'wallets': wallet_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get wallets: {str(e)}'
        }), 500

@sportsbook_bp.route('/wallet-balance/<int:wallet_id>', methods=['GET'])
def get_wallet_balance(wallet_id):
    """Get current balance and recent transactions for a wallet"""
    try:
        conn = get_db_connection()
        
        # Get wallet info
        wallet = conn.execute("""
            SELECT w.*, o.sportsbook_name, o.login
            FROM operator_wallets w
            JOIN sportsbook_operators o ON w.operator_id = o.id
            WHERE w.id = ?
        """, (wallet_id,)).fetchone()
        
        if not wallet:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Wallet not found'
            }), 404
        
        # Get recent transactions (last 10)
        transactions = conn.execute("""
            SELECT transaction_type, amount, balance_before, balance_after, 
                   description, reference_id, created_at
            FROM wallet_transactions 
            WHERE wallet_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        """, (wallet_id,)).fetchall()
        
        conn.close()
        
        transaction_data = []
        for tx in transactions:
            transaction_data.append({
                'transaction_type': tx['transaction_type'],
                'amount': tx['amount'],
                'balance_before': tx['balance_before'],
                'balance_after': tx['balance_after'],
                'description': tx['description'],
                'reference_id': tx['reference_id'],
                'created_at': tx['created_at']
            })
        
        return jsonify({
            'success': True,
            'wallet': {
                'id': wallet['id'],
                'operator_id': wallet['operator_id'],
                'operator_name': wallet['sportsbook_name'],
                'operator_login': wallet['login'],
                'wallet_type': wallet['wallet_type'],
                'current_balance': wallet['current_balance'],
                'initial_balance': wallet['initial_balance'],
                'leverage_multiplier': wallet['leverage_multiplier'],
                'is_active': bool(wallet['is_active']),
                'created_at': wallet['created_at'],
                'updated_at': wallet['updated_at']
            },
            'recent_transactions': transaction_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get wallet balance: {str(e)}'
        }), 500

# Keep existing login/logout/check functions unchanged
@sportsbook_bp.route('/admin-login', methods=['POST'])
def admin_login():
    """Login endpoint for sportsbook operators"""
    try:
        data = request.get_json()
        
        login = data.get('login', '').strip()
        password = data.get('password', '')
        subdomain = data.get('subdomain', '').strip()
        
        if not login or not password:
            return jsonify({
                'success': False,
                'error': 'Login and password are required'
            }), 400
        
        conn = get_db_connection()
        
        # Find operator by login and subdomain
        if subdomain:
            operator = conn.execute("""
                SELECT id, login, password_hash, sportsbook_name, subdomain, is_active, last_login
                FROM sportsbook_operators 
                WHERE login = ? AND subdomain = ?
            """, (login, subdomain)).fetchone()
        else:
            operator = conn.execute("""
                SELECT id, login, password_hash, sportsbook_name, subdomain, is_active, last_login
                FROM sportsbook_operators 
                WHERE login = ?
            """, (login,)).fetchone()
        
        if not operator:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Invalid login credentials'
            }), 401
        
        if not operator['is_active']:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Your sportsbook account has been disabled. Please contact support.'
            }), 401
        
        # Verify password
        if not check_password_hash(operator['password_hash'], password):
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Invalid login credentials'
            }), 401
        
        # Update last login
        conn.execute("""
            UPDATE sportsbook_operators 
            SET last_login = ? 
            WHERE id = ?
        """, (datetime.utcnow(), operator['id']))
        conn.commit()
        conn.close()
        
        # Store in session
        session['operator_id'] = operator['id']
        session['operator_login'] = operator['login']
        session['operator_subdomain'] = operator['subdomain']
        session['operator_name'] = operator['sportsbook_name']
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'operator': {
                'id': operator['id'],
                'login': operator['login'],
                'sportsbook_name': operator['sportsbook_name'],
                'subdomain': operator['subdomain']
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Login failed: {str(e)}'
        }), 500

@sportsbook_bp.route('/admin-logout', methods=['POST'])
def admin_logout():
    """Logout endpoint for sportsbook operators"""
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200

@sportsbook_bp.route('/admin-check', methods=['GET'])
def admin_check():
    """Check if admin is logged in"""
    if 'operator_id' in session:
        return jsonify({
            'success': True,
            'logged_in': True,
            'operator': {
                'id': session['operator_id'],
                'login': session['operator_login'],
                'sportsbook_name': session['operator_name'],
                'subdomain': session['operator_subdomain']
            }
        }), 200
    else:
        return jsonify({
            'success': True,
            'logged_in': False
        }), 200

def require_admin_auth(f):
    """Decorator to require admin authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'operator_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

