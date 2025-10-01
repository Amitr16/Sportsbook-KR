#!/usr/bin/env python3
"""
Frontend App - Web3 Sportsbook Registration
Fixed database connection issues for frontend testing
"""

import os
import sqlite3
import json
import requests
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

# Prevent any imports from src/ that cause PostgreSQL connection issues
os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'
os.environ['DISABLE_POSTGRES'] = '1'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'frontend-test-key'

# Load Crossmint credentials
load_dotenv('env.aptos')

# Crossmint configuration
CROSSMINT_API_KEY = os.getenv('CROSSMINT_API_KEY')
CROSSMINT_PROJECT_ID = os.getenv('CROSSMINT_PROJECT_ID')
CROSSMINT_ENVIRONMENT = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')
CROSSMINT_BASE_URL = f"https://{CROSSMINT_ENVIRONMENT}.crossmint.com/api"

CROSSMINT_HEADERS = {
    "X-API-KEY": CROSSMINT_API_KEY,
    "X-PROJECT-ID": CROSSMINT_PROJECT_ID,
    "Content-Type": "application/json"
}

# USDT Contract
USDT_CONTRACT_ADDRESS = "0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745"
USDT_CONTRACT_ID = f"{USDT_CONTRACT_ADDRESS}::simple_usdt::SimpleUSDT"

def create_aptos_wallet(email, metadata):
    """Create Aptos wallet via Crossmint"""
    try:
        wallet_data = {
            "type": "aptos-mpc-wallet",
            "linkedUser": f"email:{email}",
            "metadata": metadata
        }
        
        print(f"🌐 Creating Aptos wallet for {email}")
        
        response = requests.post(
            f"{CROSSMINT_BASE_URL}/v1-alpha2/wallets",
            headers=CROSSMINT_HEADERS,
            json=wallet_data,
            timeout=30
        )
        
        print(f"📡 Crossmint API Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            wallet_info = response.json()
            return {
                'success': True,
                'wallet_address': wallet_info.get('address'),
                'wallet_id': wallet_info.get('id')
            }
        else:
            return {
                'success': False,
                'message': f"API Error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f"Network Error: {str(e)}"
        }

def mint_usdt(wallet_address, amount):
    """Simulate USDT minting"""
    try:
        print(f"🪙 Minting {amount} USDT to {wallet_address}")
        
        # Simulate transaction hash
        transaction_hash = f"0x{'0' * 55}{hash(wallet_address + str(amount)) % 1000000000:09d}"
        
        print(f"✅ Simulated USDT mint: {amount} USDT")
        
        return {
            'success': True,
            'transaction_hash': transaction_hash,
            'wallet_address': wallet_address,
            'amount': amount
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

# Enhanced HTML template with better styling
REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Web3 Sportsbook Registration</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container { 
            max-width: 800px; margin: 0 auto; 
            background: white; border-radius: 15px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; padding: 30px; text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .form-container { padding: 40px; }
        .form-group { margin: 20px 0; }
        label { 
            display: block; margin-bottom: 8px; font-weight: 600; 
            color: #333; font-size: 1.1em;
        }
        input[type="text"], input[type="email"], input[type="password"] { 
            width: 100%; padding: 15px; border: 2px solid #e1e5e9; 
            border-radius: 8px; font-size: 1em; transition: border-color 0.3s;
        }
        input:focus { 
            outline: none; border-color: #4facfe; 
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }
        .checkbox-group { 
            display: flex; align-items: center; gap: 10px;
            padding: 15px; background: #f8f9fa; border-radius: 8px;
            border: 2px solid #e1e5e9;
        }
        .checkbox-group input[type="checkbox"] { 
            width: 20px; height: 20px; margin: 0;
        }
        .checkbox-group label { 
            margin: 0; font-weight: 500; color: #495057;
        }
        .submit-btn { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 15px 30px; border: none; 
            border-radius: 8px; font-size: 1.1em; font-weight: 600;
            cursor: pointer; width: 100%; transition: transform 0.2s;
        }
        .submit-btn:hover { transform: translateY(-2px); }
        .submit-btn:disabled { 
            background: #6c757d; cursor: not-allowed; transform: none;
        }
        .result { margin-top: 30px; padding: 20px; border-radius: 8px; }
        .success { 
            background: #d4edda; border: 2px solid #c3e6cb; color: #155724;
        }
        .error { 
            background: #f8d7da; border: 2px solid #f5c6cb; color: #721c24;
        }
        .loading { 
            background: #fff3cd; border: 2px solid #ffeaa7; color: #856404;
        }
        .wallet-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px; margin-top: 20px;
        }
        .wallet-card { 
            background: #f8f9fa; padding: 15px; border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        .wallet-card h4 { 
            color: #495057; margin-bottom: 10px; text-transform: capitalize;
        }
        .wallet-address { 
            font-family: 'Courier New', monospace; font-size: 0.9em;
            background: white; padding: 8px; border-radius: 4px;
            border: 1px solid #dee2e6; word-break: break-all;
        }
        .stats { 
            display: flex; justify-content: space-between; margin: 20px 0;
            padding: 15px; background: #e9ecef; border-radius: 8px;
        }
        .stat { text-align: center; }
        .stat-value { font-size: 1.5em; font-weight: bold; color: #495057; }
        .stat-label { font-size: 0.9em; color: #6c757d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Web3 Sportsbook</h1>
            <p>Register your sportsbook with Aptos blockchain integration</p>
        </div>
        
        <div class="form-container">
            <form id="registerForm">
                <div class="form-group">
                    <label>🏢 Sportsbook Name:</label>
                    <input type="text" name="sportsbook_name" required 
                           placeholder="My Awesome Sportsbook">
                </div>
                
                <div class="form-group">
                    <label>📧 Email Address:</label>
                    <input type="email" name="email" required 
                           placeholder="admin@mysportsbook.com">
                </div>
                
                <div class="form-group">
                    <label>👤 Admin Login:</label>
                    <input type="text" name="login" required 
                           placeholder="admin">
                </div>
                
                <div class="form-group">
                    <label>🔒 Password:</label>
                    <input type="password" name="password" required 
                           placeholder="Minimum 8 characters">
                </div>
                
                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" name="enable_web3" value="true" checked id="web3Check">
                        <label for="web3Check">
                            🌐 Enable Web3 & Aptos Integration
                            <br><small>Creates 4 operator wallets with USDT on Aptos testnet</small>
                        </label>
                    </div>
                </div>
                
                <button type="submit" class="submit-btn" id="submitBtn">
                    🎯 Register Sportsbook
                </button>
            </form>
            
            <div id="result"></div>
        </div>
    </div>
    
    <script>
        document.getElementById('registerForm').onsubmit = async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('result');
            const submitBtn = document.getElementById('submitBtn');
            
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Creating Sportsbook...';
            resultDiv.innerHTML = `
                <div class="result loading">
                    <h3>⏳ Processing Registration</h3>
                    <p>Creating sportsbook operator and Aptos wallets...</p>
                </div>
            `;
            
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
                
                if (result.success) {
                    let html = '<div class="result success">';
                    html += '<h3>✅ Registration Successful!</h3>';
                    
                    html += '<div class="stats">';
                    html += '<div class="stat"><div class="stat-value">' + result.operator_id + '</div><div class="stat-label">Operator ID</div></div>';
                    html += '<div class="stat"><div class="stat-value">' + (result.web3_enabled ? 'Yes' : 'No') + '</div><div class="stat-label">Web3 Enabled</div></div>';
                    if (result.total_usdt_minted) {
                        html += '<div class="stat"><div class="stat-value">' + result.total_usdt_minted.toLocaleString() + '</div><div class="stat-label">USDT Minted</div></div>';
                    }
                    html += '</div>';
                    
                    if (result.wallets) {
                        html += '<h4>🏦 Aptos Wallets Created:</h4>';
                        html += '<div class="wallet-grid">';
                        
                        for (const [walletType, walletInfo] of Object.entries(result.wallets)) {
                            html += '<div class="wallet-card">';
                            html += '<h4>' + walletType.replace('_', ' ') + '</h4>';
                            html += '<div><strong>USDT Balance:</strong> ' + walletInfo.usdt_balance.toLocaleString() + '</div>';
                            html += '<div><strong>Address:</strong></div>';
                            html += '<div class="wallet-address">' + walletInfo.address + '</div>';
                            html += '</div>';
                        }
                        
                        html += '</div>';
                    }
                    
                    html += '</div>';
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <h3>❌ Registration Failed</h3>
                            <p>${result.message}</p>
                        </div>
                    `;
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="result error">
                        <h3>❌ Network Error</h3>
                        <p>Failed to connect to server: ${error.message}</p>
                    </div>
                `;
            } finally {
                // Reset button
                submitBtn.disabled = false;
                submitBtn.textContent = '🎯 Register Sportsbook';
            }
        };
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    """Redirect to registration"""
    return '''
    <script>window.location.href = "/register-sportsbook";</script>
    <a href="/register-sportsbook">Go to Registration</a>
    '''

@app.route('/register-sportsbook')
def register_form():
    """Serve registration form"""
    return render_template_string(REGISTER_HTML)

@app.route('/api/register-sportsbook', methods=['POST'])
def register_sportsbook():
    """Register sportsbook with hybrid wallets - NO EXTERNAL IMPORTS"""
    try:
        data = request.get_json()
        print(f"📝 Registration request: {data}")
        
        # Basic validation
        required_fields = ['sportsbook_name', 'email', 'login', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        if len(data['password']) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long'}), 400
        
        enable_web3 = data.get('enable_web3', False)
        print(f"🌐 Web3 enabled: {enable_web3}")
        
        # Create DIRECT SQLite connection (no imports from src/)
        conn = sqlite3.connect('local_app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Step 1: Create sportsbook operator record
            password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
            subdomain = f"{data['login']}-{hash(data['email']) % 10000}"
            
            cursor.execute("""
                INSERT INTO sportsbook_operators 
                (sportsbook_name, email, login, password_hash, subdomain, web3_enabled, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                data['sportsbook_name'],
                data['email'],
                data['login'],
                password_hash,
                subdomain,
                enable_web3,
                True
            ))
            
            operator_id = cursor.lastrowid
            print(f"✅ Created operator: {operator_id}")
            
            # Step 2: Create 4 operator wallets
            wallet_configs = [
                {'type': 'bookmaker_capital', 'usd_balance': 10000.0, 'usdt_amount': 10000.0},
                {'type': 'liquidity_pool', 'usd_balance': 40000.0, 'usdt_amount': 40000.0},
                {'type': 'revenue', 'usd_balance': 0.0, 'usdt_amount': 0.0},
                {'type': 'community', 'usd_balance': 0.0, 'usdt_amount': 0.0}
            ]
            
            created_wallets = {}
            total_usdt_minted = 0.0
            
            for wallet_config in wallet_configs:
                wallet_type = wallet_config['type']
                usd_balance = wallet_config['usd_balance']
                usdt_amount = wallet_config['usdt_amount']
                
                # Create traditional wallet record
                cursor.execute("""
                    INSERT INTO operator_wallets 
                    (operator_id, wallet_type, current_balance, usdt_balance, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (operator_id, wallet_type, usd_balance, 0.0))
                
                if enable_web3:
                    print(f"🌐 Creating {wallet_type} wallet...")
                    
                    # Create Aptos wallet
                    wallet_result = create_aptos_wallet(
                        data['email'],
                        {
                            "operator_id": operator_id,
                            "email": data['email'],
                            "sportsbook_name": data['sportsbook_name'],
                            "wallet_type": wallet_type,
                            "token_type": "USDT",
                            "created_at": datetime.now().isoformat()
                        }
                    )
                    
                    if wallet_result['success']:
                        aptos_wallet_address = wallet_result['wallet_address']
                        aptos_wallet_id = wallet_result['wallet_id']
                        
                        print(f"✅ Created wallet: {aptos_wallet_address}")
                        
                        # Mint USDT if amount > 0
                        if usdt_amount > 0:
                            mint_result = mint_usdt(aptos_wallet_address, usdt_amount)
                            if mint_result['success']:
                                total_usdt_minted += usdt_amount
                                print(f"✅ Minted {usdt_amount} USDT")
                        
                        # Update operator_wallets table with Aptos info
                        cursor.execute("""
                            UPDATE operator_wallets 
                            SET aptos_wallet_address = ?, aptos_wallet_id = ?, 
                                usdt_balance = ?, usdt_contract = ?
                            WHERE operator_id = ? AND wallet_type = ?
                        """, (
                            aptos_wallet_address, aptos_wallet_id,
                            usdt_amount, USDT_CONTRACT_ID,
                            operator_id, wallet_type
                        ))
                        
                        created_wallets[wallet_type] = {
                            'address': aptos_wallet_address,
                            'wallet_id': aptos_wallet_id,
                            'usdt_balance': usdt_amount,
                            'usd_balance': usd_balance,
                            'chain': 'aptos'
                        }
                    else:
                        print(f"❌ Failed to create {wallet_type} wallet: {wallet_result['message']}")
                        # Continue with other wallets even if one fails
            
            conn.commit()
            print(f"✅ Registration complete! Operator ID: {operator_id}")
            
            response_data = {
                'success': True,
                'message': f'Sportsbook "{data["sportsbook_name"]}" registered successfully!',
                'operator_id': operator_id,
                'web3_enabled': enable_web3,
                'subdomain': subdomain
            }
            
            if enable_web3:
                response_data.update({
                    'wallets': created_wallets,
                    'total_usdt_minted': total_usdt_minted,
                    'total_wallets': len(created_wallets),
                    'usdt_contract': USDT_CONTRACT_ID
                })
            
            return jsonify(response_data)
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Registration failed: {str(e)}'
        }), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'database': 'sqlite',
        'web3': 'enabled' if CROSSMINT_API_KEY else 'disabled',
        'usdt_contract': USDT_CONTRACT_ID
    })

if __name__ == '__main__':
    print("🚀 Starting Frontend App...")
    print("📊 Database: SQLite (isolated)")
    print(f"🔑 Crossmint: {'✅ Configured' if CROSSMINT_API_KEY else '❌ Missing API Key'}")
    print("🌐 Frontend URL: http://localhost:5000")
    print("🔍 Health Check: http://localhost:5000/health")
    print("📋 Registration: http://localhost:5000/register-sportsbook")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
