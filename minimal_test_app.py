#!/usr/bin/env python3
"""
Minimal Flask App - Test Hybrid System
"""

import os
import sys
import sqlite3
from flask import Flask, request, jsonify, render_template_string

# Set environment
os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
sys.path.insert(0, 'src')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-key'

# Simple HTML template
REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sportsbook Registration</title>
</head>
<body>
    <h1>Register Sportsbook</h1>
    <form id="registerForm">
        <div>
            <label>Sportsbook Name:</label>
            <input type="text" name="sportsbook_name" required>
        </div>
        <div>
            <label>Email:</label>
            <input type="email" name="email" required>
        </div>
        <div>
            <label>Login:</label>
            <input type="text" name="login" required>
        </div>
        <div>
            <label>Password:</label>
            <input type="password" name="password" required>
        </div>
        <div>
            <label>
                <input type="checkbox" name="enable_web3" value="true"> Enable Web3 & Aptos Wallets
            </label>
        </div>
        <button type="submit">Register</button>
    </form>
    
    <div id="result"></div>
    
    <script>
        document.getElementById('registerForm').onsubmit = async function(e) {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                sportsbook_name: formData.get('sportsbook_name'),
                email: formData.get('email'),
                login: formData.get('login'),
                password: formData.get('password'),
                enable_web3: formData.get('enable_web3') === 'true'
            };
            
            try {
                const response = await fetch('/api/register-sportsbook', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                document.getElementById('result').innerHTML = 
                    '<pre>' + JSON.stringify(result, null, 2) + '</pre>';
            } catch (error) {
                document.getElementById('result').innerHTML = 
                    '<div style="color: red;">Error: ' + error.message + '</div>';
            }
        };
    </script>
</body>
</html>
'''

@app.route('/register-sportsbook')
def register_form():
    """Serve registration form"""
    return render_template_string(REGISTER_HTML)

@app.route('/api/register-sportsbook', methods=['POST'])
def register_sportsbook():
    """Register sportsbook with hybrid wallets"""
    try:
        data = request.get_json()
        print(f"📝 Registration request: {data}")
        
        # Basic validation
        required_fields = ['sportsbook_name', 'email', 'login', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        enable_web3 = data.get('enable_web3', False)
        print(f"🌐 Web3 enabled: {enable_web3}")
        
        if enable_web3:
            # Test hybrid wallet creation
            try:
                from src.services.hybrid_wallet_service import HybridWalletService
                
                # Create database connection (same as working test)
                conn = sqlite3.connect('local_app.db')
                conn.row_factory = sqlite3.Row
                
                # Step 1: Create sportsbook operator record first
                import hashlib
                password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
                
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sportsbook_operators 
                    (sportsbook_name, email, login, password_hash, subdomain, web3_enabled, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    data['sportsbook_name'],
                    data['email'],
                    data['login'],
                    password_hash,
                    f"{data['login']}-sportsbook",
                    True,
                    True
                ))
                
                operator_id = cursor.lastrowid
                print(f"✅ Created operator: {operator_id}")
                
                # Step 2: Create 4 operator wallets (traditional)
                wallet_types = ['bookmaker_capital', 'liquidity_pool', 'revenue', 'community']
                initial_balances = [10000.0, 40000.0, 0.0, 0.0]
                
                for wallet_type, balance in zip(wallet_types, initial_balances):
                    cursor.execute("""
                        INSERT INTO operator_wallets 
                        (operator_id, wallet_type, current_balance, usdt_balance, created_at)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    """, (operator_id, wallet_type, balance, 0.0))
                
                print("✅ Created 4 traditional operator wallets")
                
                # Step 3: Prepare operator data for hybrid wallet creation
                operator_data = {
                    'operator_id': operator_id,
                    'email': data['email'],
                    'sportsbook_name': data['sportsbook_name'],
                    'enable_web3': True
                }
                
                print("🏢 Creating hybrid wallets...")
                service = HybridWalletService()
                result = service.create_operator_with_hybrid_wallets(operator_data, conn)
                
                conn.close()
                
                if result['success']:
                    return jsonify({
                        'success': True,
                        'message': 'Sportsbook registered successfully with Web3 wallets!',
                        'operator_id': operator_id,
                        'web3_enabled': True,
                        'wallets': result['wallets'],
                        'total_usdt_minted': result['total_usdt_minted']
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'Wallet creation failed: {result.get("message")}'
                    }), 500
                    
            except Exception as e:
                print(f"❌ Hybrid wallet error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'message': f'Web3 integration error: {str(e)}'
                }), 500
        else:
            # Web2 only registration
            return jsonify({
                'success': True,
                'message': 'Sportsbook registered successfully (Web2 only)',
                'operator_id': 999,
                'web3_enabled': False
            })
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'database': 'sqlite'})

if __name__ == '__main__':
    print("🚀 Starting Minimal Test App...")
    print("📊 Database: SQLite")
    print("🌐 URL: http://localhost:5000/register-sportsbook")
    print("🔍 Health: http://localhost:5000/health")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
