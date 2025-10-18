#!/usr/bin/env python3
"""
Aptos Contract Helper - Based on Kryzel-User-Wallet-Creation-Deposit-Funds
Uses Aptos CLI directly for contract interactions (deposits, withdrawals, balance)
"""

import os
import shlex
import subprocess
import json
from typing import Dict, Optional

# Contract configuration
MODULE_ADDRESS = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
MODULE_NAME = "custodial_usdt"
APTOS_PROFILE = os.getenv("APTOS_ADMIN_PROFILE", "contract_admin")
APTOS_REST_URL = "https://fullnode.testnet.aptoslabs.com"

def _run_aptos_command(args: list) -> str:
    """Run Aptos CLI command and return output"""
    cmd = ["aptos"] + args
    print(f"Running: {' '.join(shlex.quote(x) for x in cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise RuntimeError(f"Aptos CLI error: {error_msg}")
        
        return result.stdout
    
    except subprocess.TimeoutExpired:
        raise RuntimeError("Aptos CLI command timed out after 30 seconds")
    except FileNotFoundError:
        raise RuntimeError("Aptos CLI not found. Install it: https://aptos.dev/cli-tools/aptos-cli-tool/install-aptos-cli")

def _function_id(function_name: str) -> str:
    """Build full function ID"""
    return f"{MODULE_ADDRESS}::{MODULE_NAME}::{function_name}"

def deposit(to_address: str, amount_usdt: float) -> Dict:
    """
    Deposit USDT to a wallet using the custodial_usdt contract
    
    Args:
        to_address: Recipient's Aptos wallet address
        amount_usdt: Amount in USDT (will be converted to u128 with 6 decimals)
    
    Returns:
        Dict with transaction result
    """
    # Convert to u128 (6 decimals)
    amount_u128 = int(amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("deposit"),
        "--args", f"address:{to_address}", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

def withdraw(amount_usdt: float) -> Dict:
    """
    Withdraw USDT from caller's wallet (uses profile's wallet)
    
    Args:
        amount_usdt: Amount in USDT
    
    Returns:
        Dict with transaction result
    """
    amount_u128 = int(amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("withdraw"),
        "--args", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

def transfer(to_address: str, amount_usdt: float) -> Dict:
    """
    Transfer USDT from caller's wallet to another address
    
    Args:
        to_address: Recipient's Aptos wallet address
        amount_usdt: Amount in USDT
    
    Returns:
        Dict with transaction result
    """
    amount_u128 = int(amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("transfer"),
        "--args", f"address:{to_address}", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

def balance_of(address: str) -> float:
    """
    Check balance of any Aptos wallet address
    
    Args:
        address: Aptos wallet address
    
    Returns:
        Balance in USDT (converted from u128)
    """
    output = _run_aptos_command([
        "move", "view",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("balance_of"),
        "--args", f"address:{address}"
    ])
    
    result = json.loads(output)
    raw_balance = result.get("Result")
    
    if isinstance(raw_balance, list) and raw_balance:
        balance_u128 = int(raw_balance[0])
        return balance_u128 / 1_000_000  # Convert to USDT
    
    return 0.0

def admin_reset_one(address: str, new_amount_usdt: float) -> Dict:
    """
    Admin function: Reset a single user's balance
    
    Args:
        address: User's Aptos wallet address
        new_amount_usdt: New balance in USDT
    
    Returns:
        Dict with transaction result
    """
    amount_u128 = int(new_amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("admin_reset_one"),
        "--args", f"address:{address}", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

def admin_reset_all(new_amount_usdt: float) -> Dict:
    """
    Admin function: Reset all users' balances
    
    Args:
        new_amount_usdt: New balance for all users in USDT
    
    Returns:
        Dict with transaction result
    """
    amount_u128 = int(new_amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("admin_reset_all"),
        "--args", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

def admin_reset_top_k(k: int, new_amount_usdt: float) -> Dict:
    """
    Admin function: Reset top K holders' balances
    
    Args:
        k: Number of top holders to reset
        new_amount_usdt: New balance in USDT
    
    Returns:
        Dict with transaction result
    """
    amount_u128 = int(new_amount_usdt * 1_000_000)
    
    output = _run_aptos_command([
        "move", "run",
        "--profile", APTOS_PROFILE,
        "--url", APTOS_REST_URL,
        "--function-id", _function_id("admin_reset_top_k"),
        "--args", f"u64:{k}", f"u128:{amount_u128}",
        "--assume-yes"
    ])
    
    return json.loads(output)

# Test if Aptos CLI is available
def check_aptos_cli():
    """Check if Aptos CLI is installed"""
    try:
        result = subprocess.run(["aptos", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Aptos CLI found: {version}")
            return True
        else:
            print("❌ Aptos CLI not working properly")
            return False
    except FileNotFoundError:
        print("❌ Aptos CLI not installed")
        print("Install from: https://aptos.dev/cli-tools/aptos-cli-tool/install-aptos-cli")
        return False
    except Exception as e:
        print(f"❌ Error checking Aptos CLI: {e}")
        return False

if __name__ == "__main__":
    print("="*80)
    print("APTOS CONTRACT HELPER - TEST")
    print("="*80)
    
    # Check CLI
    if not check_aptos_cli():
        exit(1)
    
    print(f"\nConfiguration:")
    print(f"  Module Address: {MODULE_ADDRESS}")
    print(f"  Module Name: {MODULE_NAME}")
    print(f"  Profile: {APTOS_PROFILE}")
    print(f"  REST URL: {APTOS_REST_URL}")
    print("\nReady to use!")

