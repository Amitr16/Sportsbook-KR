"""
Updated Sportsbook registration API endpoints with Wallet Integration
Includes 4-wallet system initialization during registration
"""

from flask import Blueprint, request, jsonify, session, render_template, Response
from werkzeug.security import generate_password_hash, check_password_hash
from src import sqlite3_shim as sqlite3
from src.auth.session_utils import clear_operator_session
import re
import os
from datetime import datetime, date
import json
import csv
import io
import uuid

# Import Hybrid Wallet service for Web3 wallet creation (4-wallet system)
try:
    from src.services.hybrid_wallet_service import HybridWalletService
    HYBRID_WALLET_AVAILABLE = True
    print("✅ Hybrid Wallet service loaded - Web3 features enabled")
except ImportError:
    HybridWalletService = None
    HYBRID_WALLET_AVAILABLE = False
    print("⚠️ Hybrid Wallet service not available - Web3 features disabled")

sportsbook_bp = Blueprint('sportsbook', __name__)

DATABASE_PATH = 'src/database/app.db'

def get_db_connection():
    """Get database connection - SQLite direct connection to avoid PostgreSQL issues"""
    import sqlite3 as direct_sqlite3
    import os
    
    # Use direct SQLite connection to avoid PostgreSQL connection pool issues
    database_url = os.getenv('DATABASE_URL', 'sqlite:///local_app.db')
    if database_url.startswith('sqlite:///'):
        db_path = database_url.replace('sqlite:///', '')
        conn = direct_sqlite3.connect(db_path)
        conn.row_factory = direct_sqlite3.Row
        return conn
    else:
        # Fallback to original shim for PostgreSQL
        conn = sqlite3.connect()
        return conn

def generate_subdomain(sportsbook_name, login):
    """Generate a unique subdomain from sportsbook name only"""
    # Clean the sportsbook name only
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', sportsbook_name.lower())
    
    # Try different variations of sportsbook name only
    candidates = [
        clean_name,  # Full cleaned name
        clean_name[:15],  # Truncated to 15 chars
        clean_name[:10],  # Truncated to 10 chars
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
    
    # If all candidates are taken, append numbers to sportsbook name
    base = clean_name[:8]
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
    
    # First, ensure the operator_wallets table exists
    # Check if we're using PostgreSQL by trying to detect the connection type
    is_postgres = False
    try:
        # Try to get server version - this will work for PostgreSQL
        cursor.execute("SELECT version()")
        version_result = cursor.fetchone()
        is_postgres = "PostgreSQL" in str(version_result[0]) if version_result else False
    except:
        # If that fails, check connection attributes
        is_postgres = hasattr(conn, 'server_version')
    
    print(f"DEBUG: Wallet creation - is_postgres: {is_postgres}")
    
    if is_postgres:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_wallets (
                id SERIAL PRIMARY KEY,
                operator_id INTEGER NOT NULL,
                wallet_type VARCHAR(50) NOT NULL,
                current_balance REAL NOT NULL DEFAULT 0.0,
                initial_balance REAL NOT NULL DEFAULT 0.0,
                leverage_multiplier REAL NOT NULL DEFAULT 1.0,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES sportsbook_operators (id),
                UNIQUE(operator_id, wallet_type)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id INTEGER NOT NULL,
                wallet_type VARCHAR(50) NOT NULL,
                current_balance REAL NOT NULL DEFAULT 0.0,
                initial_balance REAL NOT NULL DEFAULT 0.0,
                leverage_multiplier REAL NOT NULL DEFAULT 1.0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES sportsbook_operators (id),
                UNIQUE(operator_id, wallet_type)
            )
        """)
    
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
    
    # Wallet 4: Community - starts at $0
    cursor.execute("""
        INSERT INTO operator_wallets 
        (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        operator_id, 'community', 0.0, 0.0, 1.0, 
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

@sportsbook_bp.route('/register-sportsbook', methods=['GET'])
def register_sportsbook_form():
    """Serve the sportsbook registration form"""
    try:
        # Serve the registration HTML file
        static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
        html_path = os.path.join(static_folder, 'register-sportsbook.html')
        
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content
        
    except FileNotFoundError:
        return "Registration form not found", 404
    except Exception as e:
        return f"Error loading registration form: {str(e)}", 500

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
            
            # Create 4 hybrid wallets (USD + USDT) if Web3 is enabled
            aptos_wallets = None
            enable_web3 = data.get('enable_web3', True)  # Default to enabled
            
            if enable_web3 and email:
                try:
                    from src.services.hybrid_wallet_service import HybridWalletService
                    
                    hybrid_service = HybridWalletService()
                    
                    # Prepare operator data for hybrid wallet creation
                    operator_data = {
                        'operator_id': operator_id,
                        'email': email,
                        'sportsbook_name': sportsbook_name,
                        'enable_web3': enable_web3
                    }
                    
                    # Create hybrid wallets (this will handle both USD and USDT)
                    hybrid_result = hybrid_service.create_operator_with_hybrid_wallets(
                        operator_data=operator_data,
                        conn=conn
                    )
                    
                    if hybrid_result['success']:
                        aptos_wallets = {
                            'total_wallets': hybrid_result['total_wallets'],
                            'total_usdt': hybrid_result['total_usdt_minted'],
                            'wallets': {
                                wallet_type: {
                                    'address': wallet_info['address'],
                                    'wallet_id': wallet_info['wallet_id'],
                                    'usdt_balance': wallet_info['usdt_balance'],
                                    'chain': 'aptos',
                                    'token': 'USDT'
                                }
                                for wallet_type, wallet_info in hybrid_result['wallets'].items()
                            }
                        }
                        print(f"✅ Created {hybrid_result['total_wallets']} hybrid wallets for operator {operator_id}")
                        print(f"💰 Total USDT minted: {hybrid_result['total_usdt_minted']} USDT")
                    else:
                        print(f"⚠️ Hybrid wallet creation failed: {hybrid_result.get('message')}")
                        
                except Exception as e:
                    print(f"⚠️ Error creating hybrid wallets: {e}")
            
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
                'aptos_wallets': aptos_wallets,
                'web3_enabled': enable_web3 and aptos_wallets is not None,
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
                    'community': {
                        'id': wallet_ids['wallet4_id'],
                        'balance': 0.0,
                        'description': 'Community share of profits'
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
    clear_operator_session()
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

# Bulk Registration Functions
def generate_subdomain_bulk(sportsbook_name, login):
    """Generate a unique subdomain from sportsbook name and login"""
    # Clean the name for subdomain
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', sportsbook_name.lower())
    clean_login = re.sub(r'[^a-zA-Z0-9]', '', login.lower())
    
    # Combine and truncate if too long
    base_subdomain = f"{clean_name}{clean_login}"[:20]
    
    # Check if subdomain exists and add random suffix if needed
    conn = get_db_connection()
    try:
        counter = 1
        subdomain = base_subdomain
        while True:
            existing = conn.execute(
                "SELECT id FROM sportsbook_operators WHERE subdomain = ?", 
                (subdomain,)
            ).fetchone()
            
            if not existing:
                break
                
            subdomain = f"{base_subdomain}{counter}"
            counter += 1
            
            if counter > 999:  # Prevent infinite loop
                subdomain = f"{base_subdomain}{uuid.uuid4().hex[:8]}"
                break
                
        return subdomain
    finally:
        conn.close()


@sportsbook_bp.route('/bulk-register', methods=['POST'])
def bulk_register():
    """Process CSV file and create multiple sportsbook operators"""
    try:
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No CSV file uploaded'
            }), 400
        
        file = request.files['csv_file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({
                'success': False,
                'error': 'File must be a CSV file'
            }), 400
        
        # Read and parse CSV
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            rows = list(csv_input)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Error reading CSV file: {str(e)}'
            }), 400
        
        if not rows:
            return jsonify({
                'success': False,
                'error': 'CSV file is empty'
            }), 400
        
        # Debug: Log the actual columns found
        actual_columns = list(rows[0].keys()) if rows else []
        print(f"DEBUG: CSV columns found: {actual_columns}")
        print(f"DEBUG: First row data: {rows[0] if rows else 'No rows'}")
        
        # Normalize column names (remove BOM, trim whitespace and convert to lowercase for comparison)
        normalized_columns = {}
        for col in actual_columns:
            # Remove BOM character if present
            clean_col = col.lstrip('\ufeff').strip()
            normalized_columns[clean_col.lower()] = col
        print(f"DEBUG: Normalized columns: {list(normalized_columns.keys())}")
        
        # Check for BOM or hidden characters
        for col in actual_columns:
            print(f"DEBUG: Column '{col}' - repr: {repr(col)}")
        
        # Validate required columns (case insensitive)
        required_columns = ['sportsbook_name', 'login', 'password', 'email']
        missing_columns = []
        for req_col in required_columns:
            if req_col.lower() not in normalized_columns:
                missing_columns.append(req_col)
        
        if missing_columns:
            return jsonify({
                'success': False,
                'error': f'Missing required columns: {", ".join(missing_columns)}. Found columns: {", ".join(actual_columns)}'
            }), 400
        
        # Process each row
        results = {
            'successful': [],
            'failed': [],
            'total_processed': len(rows)
        }
        
        conn = get_db_connection()
        print(f"DEBUG: Database connection type: {type(conn)}")
        print(f"DEBUG: Database connection: {conn}")
        
        try:
            for i, row in enumerate(rows, 1):
                # Start a new transaction for each row
                # Check if we're using PostgreSQL or SQLite
                is_postgres = hasattr(conn, 'server_version')
                if is_postgres:
                    conn.execute("BEGIN")
                else:
                    conn.execute("BEGIN TRANSACTION")
                try:
                    # Extract and validate data using normalized column names
                    sportsbook_name = row[normalized_columns['sportsbook_name']].strip()
                    login = row[normalized_columns['login']].strip()
                    password = row[normalized_columns['password']].strip()
                    email = row[normalized_columns['email']].strip() if row[normalized_columns['email']] else None
                    
                    # Use default values
                    commission_rate = 0.05
                    initial_balance = 100000.0
                    
                    # Validate required fields
                    if not sportsbook_name or not login or not password:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    # Validate sportsbook name
                    if len(sportsbook_name) < 3 or len(sportsbook_name) > 100:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Sportsbook name must be between 3 and 100 characters'
                        })
                        continue
                    
                    # Validate login
                    if not re.match(r'^[a-zA-Z0-9_]{3,50}$', login):
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Login must be 3-50 characters, letters, numbers, and underscores only'
                        })
                        continue
                    
                    # Validate password
                    if len(password) < 8:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Password must be at least 8 characters long'
                        })
                        continue
                    
                    # Validate email if provided
                    if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Invalid email address'
                        })
                        continue
                    
                    # Check if sportsbook name already exists
                    existing_name = conn.execute(
                        "SELECT id FROM sportsbook_operators WHERE sportsbook_name = ?", 
                        (sportsbook_name,)
                    ).fetchone()
                    
                    if existing_name:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Sportsbook name already exists'
                        })
                        continue
                    
                    # Check if login already exists
                    existing_login = conn.execute(
                        "SELECT id FROM sportsbook_operators WHERE login = ?", 
                        (login,)
                    ).fetchone()
                    
                    if existing_login:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': 'Login username already exists'
                        })
                        continue
                    
                    # Generate unique subdomain
                    try:
                        subdomain = generate_subdomain_bulk(sportsbook_name, login)
                    except Exception as e:
                        results['failed'].append({
                            'row': i,
                            'sportsbook_name': sportsbook_name,
                            'error': f'Unable to generate subdomain: {str(e)}'
                        })
                        continue
                    
                    # Hash password
                    password_hash = generate_password_hash(password)
                    
                    # Default settings
                    default_settings = {
                        'theme': 'default',
                        'currency': 'USD',
                        'timezone': 'UTC',
                        'max_bet_amount': 10000,
                        'min_bet_amount': 1,
                        'default_user_balance': 1000.0,
                        'commission_rate': commission_rate
                    }
                    
                    # Insert new sportsbook operator
                    cursor = conn.cursor()
                    print(f"DEBUG: About to insert operator: {sportsbook_name}")
                    cursor.execute("""
                        INSERT INTO sportsbook_operators 
                        (sportsbook_name, login, password_hash, email, subdomain, settings, 
                         commission_rate, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sportsbook_name,
                        login,
                        password_hash,
                        email,
                        subdomain,
                        json.dumps(default_settings),
                        commission_rate,
                        datetime.utcnow(),
                        datetime.utcnow()
                    ))
                    print(f"DEBUG: Insert executed for {sportsbook_name}")
                    
                    operator_id = cursor.lastrowid
                    print(f"DEBUG: Created operator {sportsbook_name} with ID: {operator_id}")
                    
                    # Create the 4 wallets for the new operator (same as single registration)
                    wallet_ids = None
                    try:
                        wallet_ids = create_operator_wallets(operator_id, conn)
                        # Update bookmaker capital wallet with initial balance
                        if wallet_ids:
                            cursor.execute("""
                                UPDATE operator_wallets 
                                SET current_balance = ? 
                                WHERE id = ? AND wallet_type = 'bookmaker_capital'
                            """, (initial_balance, wallet_ids['bookmaker_capital']))
                        print(f"DEBUG: Successfully created wallets for {sportsbook_name}")
                    except Exception as wallet_error:
                        print(f"ERROR: Could not create wallets for {sportsbook_name}: {wallet_error}")
                        # Don't fail the entire operation - operator creation should still succeed
                        wallet_ids = None
                    
                    # Commit the transaction for this row
                    conn.commit()
                    print(f"DEBUG: Committed transaction for {sportsbook_name} (ID: {operator_id})")
                    
                    # Verify the record was actually inserted
                    verify_cursor = conn.cursor()
                    verify_cursor.execute("SELECT id, sportsbook_name FROM sportsbook_operators WHERE id = ?", (operator_id,))
                    verify_result = verify_cursor.fetchone()
                    print(f"DEBUG: Verification query result: {verify_result}")
                    
                    # Format wallet information like single registration
                    wallet_info = None
                    if wallet_ids:
                        wallet_info = {
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
                    
                    results['successful'].append({
                        'row': i,
                        'sportsbook_name': sportsbook_name,
                        'login': login,
                        'email': email,
                        'subdomain': subdomain,
                        'operator_id': operator_id,
                        'admin_url': f'/{subdomain}/admin',
                        'sportsbook_url': f'/{subdomain}',
                        'wallets': wallet_info
                    })
                    
                except Exception as e:
                    # Rollback the transaction for this row
                    conn.rollback()
                    results['failed'].append({
                        'row': i,
                        'sportsbook_name': row.get('sportsbook_name', 'Unknown'),
                        'error': f'Processing error: {str(e)}'
                    })
                    continue
            
            # All transactions are handled per row above
            
            return jsonify({
                'success': True,
                'message': f'Bulk registration completed. {len(results["successful"])} successful, {len(results["failed"])} failed.',
                'results': results
            })
            
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500

@sportsbook_bp.route('/bulk-register/template')
def download_template():
    """Download CSV template for bulk registration"""
    template_data = [
        {
            'sportsbook_name': 'Example Sportsbook',
            'login': 'admin_user',
            'password': 'password123',
            'email': 'admin@example.com'
        },
        {
            'sportsbook_name': 'Another Sportsbook',
            'login': 'admin_user2',
            'password': 'password456',
            'email': 'admin2@example.com'
        }
    ]
    
    # Create CSV response
    output = io.StringIO()
    fieldnames = ['sportsbook_name', 'login', 'password', 'email']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(template_data)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=bulk_registration_template.csv'}
    )

