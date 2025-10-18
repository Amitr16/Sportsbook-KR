#!/usr/bin/env python3
"""
Quick Crossmint Test - Uses your existing service
"""

from dotenv import load_dotenv
load_dotenv("env.local", override=False)
load_dotenv("postgresql.env", override=False)

import os

print("="*80)
print("CROSSMINT CONFIGURATION CHECK")
print("="*80)

# Check environment variables
env_vars = {
    "CROSSMINT_API_KEY": os.getenv("CROSSMINT_API_KEY"),
    "CROSSMINT_PROJECT_ID": os.getenv("CROSSMINT_PROJECT_ID"),
    "CROSSMINT_ENVIRONMENT": os.getenv("CROSSMINT_ENVIRONMENT", "staging"),
    "CROSSMINT_ADMIN_WALLET_LOCATOR": os.getenv("CROSSMINT_ADMIN_WALLET_LOCATOR"),
}

print("\nEnvironment Variables:")
for key, value in env_vars.items():
    if value:
        if "KEY" in key:
            print(f"  {key}: {value[:20]}...{value[-10:] if len(value) > 30 else ''}")
        else:
            print(f"  {key}: {value}")
    else:
        print(f"  {key}: NOT SET")

missing = [k for k, v in env_vars.items() if not v and k in ['CROSSMINT_API_KEY', 'CROSSMINT_PROJECT_ID']]

if missing:
    print("\n" + "="*80)
    print("MISSING REQUIRED VARIABLES")
    print("="*80)
    for var in missing:
        print(f"  - {var}")
    print("\nAdd these to env.local or postgresql.env")
    print("\nExample:")
    print("CROSSMINT_API_KEY=sk_staging_...")
    print("CROSSMINT_PROJECT_ID=your-project-id")
    exit(1)

# Test with existing service
print("\n" + "="*80)
print("TESTING CROSSMINT SERVICE")
print("="*80)

try:
    from src.services.crossmint_aptos_service import get_crossmint_service
    
    crossmint = get_crossmint_service()
    
    print("\nService initialized successfully!")
    print(f"  Base URL: {crossmint.base_url}")
    print(f"  Environment: {crossmint.environment}")
    print(f"  Admin Wallet: {crossmint.admin_wallet_address or 'Not set'}")
    
    # Test wallet creation
    print("\n" + "-"*80)
    print("Creating test wallet...")
    print("-"*80)
    
    import time
    test_email = f"test_{int(time.time())}@kryzel.io"
    
    wallet_address, wallet_id = crossmint.create_wallet(
        user_id=99999,
        email=test_email,
        username=f"test_{int(time.time())}",
        operator_id=None
    )
    
    print("\nSUCCESS! Wallet Created")
    print("="*80)
    print(f"Address: {wallet_address}")
    print(f"Wallet ID: {wallet_id}")
    print(f"Email: {test_email}")
    print("="*80)
    
    # Test balance check
    print("\nChecking balance...")
    balance = crossmint.get_balance(wallet_address)
    
    if balance is not None:
        print(f"\nBalance: {balance} USDT")
    else:
        print("\nBalance: Query returned None (wallet empty or contract not initialized)")
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)
    print("\nYour Crossmint integration is working correctly!")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

