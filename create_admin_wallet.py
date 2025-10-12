"""
Create an admin wallet via Crossmint for custodial USDT contract interactions
Run this once to set up the admin wallet
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('postgresql.env')

CROSSMINT_API_KEY = os.getenv('CROSSMINT_API_KEY')
CROSSMINT_PROJECT_ID = os.getenv('CROSSMINT_PROJECT_ID')
CROSSMINT_ENVIRONMENT = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')

if CROSSMINT_ENVIRONMENT == 'production':
    BASE_URL = "https://www.crossmint.com/api"
else:
    BASE_URL = "https://staging.crossmint.com/api"

headers = {
    'X-API-KEY': CROSSMINT_API_KEY,
    'X-PROJECT-ID': CROSSMINT_PROJECT_ID,
    'Content-Type': 'application/json'
}

print("Creating admin wallet for custodial USDT contract...")
print("=" * 60)

# Create admin wallet
wallet_data = {
    "type": "aptos-mpc-wallet",
    "linkedUser": "email:admin@kryzel.io",
    "metadata": {
        "purpose": "admin",
        "description": "Admin wallet for custodial USDT contract operations"
    }
}

response = requests.post(
    f"{BASE_URL}/v1-alpha2/wallets",
    headers=headers,
    json=wallet_data
)

print(f"\nResponse Status: {response.status_code}")
print(f"Response: {response.text}\n")

if response.status_code in [200, 201]:
    wallet_info = response.json()
    wallet_address = wallet_info.get('address')
    
    print("SUCCESS! Admin wallet created!")
    print("=" * 60)
    print(f"Admin Wallet Address: {wallet_address}")
    print(f"Admin Wallet Locator: email:admin@kryzel.io")
    print("\nAdd these to postgresql.env:")
    print(f"CROSSMINT_ADMIN_WALLET_ADDRESS={wallet_address}")
    print(f"CROSSMINT_ADMIN_WALLET_LOCATOR=email:admin@kryzel.io")
    print("\nView on Aptos Explorer:")
    print(f"https://explorer.aptoslabs.com/account/{wallet_address}?network=testnet")
    print("=" * 60)
else:
    print("ERROR: Failed to create admin wallet")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

