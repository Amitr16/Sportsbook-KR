#!/usr/bin/env python3
"""
Pure Python Aptos Helper - NO CLI REQUIRED!
Uses Aptos REST API directly for balance queries

Based on: https://aptos.dev/nodes/aptos-api-spec
"""

import requests
import json

# Contract configuration  
MODULE_ADDRESS = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
MODULE_NAME = "custodial_usdt"
APTOS_NODE_URL = "https://fullnode.testnet.aptoslabs.com/v1"

def balance_of(wallet_address: str) -> float:
    """
    Check wallet balance using Aptos REST API (NO CLI needed!)
    
    Args:
        wallet_address: Aptos wallet address
    
    Returns:
        Balance in USDT (converted from u128)
    """
    # Use Aptos REST API view function endpoint
    # POST /view with function payload
    
    payload = {
        "function": f"{MODULE_ADDRESS}::{MODULE_NAME}::balance_of",
        "type_arguments": [],
        "arguments": [wallet_address]
    }
    
    try:
        response = requests.post(
            f"{APTOS_NODE_URL}/view",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"Request to: {APTOS_NODE_URL}/view")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        print(f"Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Result: {result}")
            
            # Result format: [balance_u128]
            if isinstance(result, list) and result:
                balance_u128 = int(result[0])
                balance_usdt = balance_u128 / 1_000_000
                return balance_usdt
            else:
                print(f"Unexpected result format: {result}")
                return 0.0
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("="*80)
    print("PURE PYTHON APTOS BALANCE CHECK (NO CLI!)")
    print("="*80)
    
    # Test with the Kryzel wallets we created
    test_wallets = {
        "Kryzel Admin": "0xbdbaee3d225a06cc8d0ead1ce8c5a45b74586377242c097dd393126715d56ae9",
        "Kryzel Platform Fee": "0x8ca156d418a273d194464b7851aca384f4e867ba1c0794065e58cf0bc0257bc9",
        "Test Wallet (just created)": "0xc0351e9716f653bc2220d760d14965e8ded384dd1e56da785171d1db5301ef15"
    }
    
    print("\nChecking balances...")
    print("-"*80)
    
    for name, address in test_wallets.items():
        print(f"\n{name}:")
        print(f"  Address: {address}")
        
        balance = balance_of(address)
        
        if balance is not None:
            print(f"  Balance: {balance} USDT")
        else:
            print(f"  Balance: Query failed")
    
    print("\n" + "="*80)
    print("BALANCE CHECK COMPLETE")
    print("="*80)
    print("\nNOTE: Deposits still require Aptos CLI")
    print("The Kryzel repo uses 'aptos move run' for deposits")
    print("This is because Crossmint doesn't support custom contract calls on testnet")

