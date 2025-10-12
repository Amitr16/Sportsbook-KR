"""
Check admin wallet status and balance
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv('postgresql.env')

CROSSMINT_API_KEY = os.getenv('CROSSMINT_API_KEY')
CROSSMINT_PROJECT_ID = os.getenv('CROSSMINT_PROJECT_ID')
CROSSMINT_ENVIRONMENT = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')
ADMIN_WALLET_ADDRESS = os.getenv('CROSSMINT_ADMIN_WALLET_ADDRESS')

BASE_URL = "https://staging.crossmint.com/api" if CROSSMINT_ENVIRONMENT != 'production' else "https://www.crossmint.com/api"
APTOS_NODE_URL = "https://fullnode.testnet.aptoslabs.com/v1"

HEADERS = {
    'X-API-KEY': CROSSMINT_API_KEY,
    'X-PROJECT-ID': CROSSMINT_PROJECT_ID,
    'Content-Type': 'application/json'
}

print("=" * 70)
print("ADMIN WALLET STATUS CHECK")
print("=" * 70)

print(f"\nAdmin Wallet Address: {ADMIN_WALLET_ADDRESS}")

# Check 1: Query wallet via Crossmint
print("\n[1] Querying wallet via Crossmint API...")
locator = "email:admin@kryzel.io:aptos-mpc-wallet"
response = requests.get(
    f"{BASE_URL}/v1-alpha2/wallets/{locator}",
    headers=HEADERS
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    wallet_info = response.json()
    print(f"Response: {wallet_info}")
else:
    print(f"Error: {response.text}")

# Check 2: Query APT balance via Aptos node
print("\n[2] Checking APT balance on Aptos blockchain...")
apt_balance = 0.0
response = requests.get(
    f"{APTOS_NODE_URL}/accounts/{ADMIN_WALLET_ADDRESS}/resource/0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>"
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    coin_store = response.json()
    apt_balance = int(coin_store['data']['coin']['value']) / 100_000_000  # APT has 8 decimals
    print(f"APT Balance: {apt_balance} APT")
    
    if apt_balance == 0:
        print("\nWARNING: Admin wallet has 0 APT!")
        print("The wallet needs APT for gas fees to execute transactions.")
        print(f"\nFund it here: https://aptoslabs.com/testnet-faucet")
        print(f"Address: {ADMIN_WALLET_ADDRESS}")
elif response.status_code == 404:
    print("ERROR: Wallet not initialized on blockchain yet (no APT balance)")
    print("The wallet needs to be funded with APT for gas fees.")
    print(f"\nFund it here: https://aptoslabs.com/testnet-faucet")
    print(f"Address: {ADMIN_WALLET_ADDRESS}")
else:
    print(f"Error: {response.text}")

# Check 3: Query USDT balance from custodial contract
print("\n[3] Checking USDT balance in custodial contract...")
CONTRACT_ADDRESS = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
payload = {
    "function": f"{CONTRACT_ADDRESS}::custodial_usdt::balance_of",
    "type_arguments": [],
    "arguments": [ADMIN_WALLET_ADDRESS]
}
response = requests.post(f"{APTOS_NODE_URL}/view", json=payload)
if response.status_code == 200:
    balance_u128 = int(response.json()[0])
    usdt_balance = balance_u128 / 1_000_000.0
    print(f"USDT Balance: ${usdt_balance:.2f}")
else:
    print(f"Error: {response.status_code} - {response.text}")

print("\n" + "=" * 70)
print("NEXT STEPS:")
print("=" * 70)
if response.status_code == 200 and apt_balance > 0:
    print("Admin wallet is ready for transactions!")
else:
    print("1. Fund admin wallet with APT from faucet:")
    print(f"   https://aptoslabs.com/testnet-faucet")
    print(f"   Address: {ADMIN_WALLET_ADDRESS}")
    print("2. Wait 1-2 minutes for faucet transaction to confirm")
    print("3. Run test again: python test_quick_deposit_balance.py")
print("=" * 70)

