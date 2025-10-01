#!/usr/bin/env python3
"""
Final Test App - Completely Isolated Hybrid System Test
"""

import os
import sys
import sqlite3
import json
import requests
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

# Set environment
os.environ['DATABASE_URL'] = 'sqlite:///local_app.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-key'

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
        
        response = requests.post(
            f"{CROSSMINT_BASE_URL}/v1-alpha2/wallets",
            headers=CROSSMINT_HEADERS,
            json=wallet_data
        )
        
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
            'message': str(e)
        }

def mint_usdt(wallet_address, amount):
    """Simulate USDT minting (using our custom contract)"""
    try:
        print(f"🪙 Minting {amount} USDT to {wallet_address}")
        
        # In a real implementation, this would call the Aptos contract
        # For now, we'll simulate it
        transaction_hash = f"0x{'0' * 63}{hash(wallet_address + str(amount)) % 10000000000:010d}"
        
        print(f"✅ Simulated USDT mint: {amount} USDT to {wallet_address}")
        
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

# Simple HTML template
REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Web3 Sportsbook Registration</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="email"], input[type="password"] { 
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; 
        }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .result { margin-top: 20px; padding: 15px; border-radius: 4px; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .wallet-info { background: #e2e3e5; padding: 10px; margin: 5px 0; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>🚀 Web3 Sportsbook Registration</h1>
    <p>Register your sportsbook with Aptos wallet integration</p>
    
    <form id="registerForm">
        <div class="form-group">
            <label>Sportsbook Name:</label>
            <input type="text" name="sportsbook_name" required placeholder="My Awesome Sportsbook">
        </div>
        <div class="form-group">
            <label>Email:</label>
            <input type="email" name="email" required placeholder="admin@mysportsbook.com">
        </div>
        <div class="form-group">
            <label>Login:</label>
            <input type="text" name="login" required placeholder="admin">
        </div>
        <div class="form-group">
            <label>Password:</label>
            <input type="password" name="password" required placeholder="Minimum 8 characters">
        </div>
        <div class="form-group">
            <label>
                <input type="checkbox" name="enable_web3" value="true" checked> 
                🌐 Enable Web3 & Aptos Wallets (4 operator wallets with USDT)
            </label>
        </div>
        <button type="submit">🎯 Register Sportsbook</button>
    </form>
    
    <div id="result"></div>
    
    <script>
        document.getElementById('registerForm').onsubmit = async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<div>⏳ Creating sportsbook and wallets...</div>';
            
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
                    html += '<p><strong>Operator ID:</strong> ' + result.operator_id + '</p>';
                    html += '<p><strong>Web3 Enabled:</strong> ' + (result.web3_enabled ? 'Yes' : 'No') + '</p>';
                    
                    if (result.wallets) {
                        html += '<h4>🏦 Aptos Wallets Created:</h4>';
                        html += '<p><strong>Total USDT Minted:</strong> ' + result.total_usdt_minted + '</p>';
                        
                        for (const [walletType, walletInfo] of Object.entries(result.wallets)) {
                            html += '<div class="wallet-info">';
                            html += '<strong>' + walletType + ':</strong><br>';
                            html += 'Address: ' + walletInfo.address + '<br>';
                            html += 'USDT Balance: ' + walletInfo.usdt_balance;
                            html += '</div>';
                        }
                    }
                    
                    html += '</div>';
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.innerHTML = '<div class="result error"><h3>❌ Registration Failed</h3><p>' + result.message + '</p></div>';
                }
            } catch (error) {
                resultDiv.innerHTML = '<div class="result error"><h3>❌ Network Error</h3><p>' + error.message + '</p></div>';
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
        
        if len(data['password']) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long'}), 400
        
        enable_web3 = data.get('enable_web3', False)
        print(f"🌐 Web3 enabled: {enable_web3}")
        
        # Create SQLite connection
        conn = sqlite3.connect('local_app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Step 1: Create sportsbook operator record
            password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
            
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
                enable_web3,
                True
            ))
            
            operator_id = cursor.lastrowid
            print(f"✅ Created operator: {operator_id}")
            
            # Step 2: Create 4 operator wallets (traditional)
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
                        
                        # Mint USDT if amount > 0
                        if usdt_amount > 0:
                            mint_result = mint_usdt(aptos_wallet_address, usdt_amount)
                            if mint_result['success']:
                                total_usdt_minted += usdt_amount
                        
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
                        
                        print(f"✅ Created {wallet_type} wallet: {aptos_wallet_address}")
                    else:
                        print(f"❌ Failed to create {wallet_type} wallet: {wallet_result['message']}")
            
            conn.commit()
            
            response_data = {
                'success': True,
                'message': 'Sportsbook registered successfully!',
                'operator_id': operator_id,
                'web3_enabled': enable_web3
            }
            
            if enable_web3:
                response_data.update({
                    'wallets': created_wallets,
                    'total_usdt_minted': total_usdt_minted,
                    'total_wallets': len(created_wallets)
                })
            
            return jsonify(response_data)
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'database': 'sqlite',
        'web3': 'enabled' if CROSSMINT_API_KEY else 'disabled'
    })

if __name__ == '__main__':
    print("🚀 Starting Final Test App...")
    print("📊 Database: SQLite")
    print(f"🔑 Crossmint: {'✅ Configured' if CROSSMINT_API_KEY else '❌ Missing API Key'}")
    print("🌐 URL: http://localhost:5000/register-sportsbook")
    print("🔍 Health: http://localhost:5000/health")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
