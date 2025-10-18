#!/usr/bin/env python3
"""
Complete Crossmint Wallet Functions
All operations using ONLY Crossmint API (no CLI needed!)

Functions:
1. create_wallet() - Create MPC wallet
2. deposit() - Deposit to wallet (admin-signed)
3. withdraw() - Withdraw from wallet (user-signed via MPC)
4. transfer() - Transfer between wallets (user-signed via MPC)
5. check_balance() - Query wallet balance
"""

import os
import requests
import json
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv("env.local", override=False)
load_dotenv("postgresql.env", override=False)

class CrossmintWalletService:
    """Complete Crossmint wallet service"""
    
    def __init__(self):
        self.api_key = os.getenv("CROSSMINT_API_KEY")
        self.project_id = os.getenv("CROSSMINT_PROJECT_ID")
        self.environment = os.getenv("CROSSMINT_ENVIRONMENT", "staging")
        self.admin_wallet_locator = os.getenv("CROSSMINT_ADMIN_WALLET_LOCATOR", "email:admin@kryzel.io")
        
        if self.environment == "production":
            self.base_url = "https://www.crossmint.com/api"
        else:
            self.base_url = "https://staging.crossmint.com/api"
        
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        if self.project_id:
            self.headers["X-PROJECT-ID"] = self.project_id
        
        # Contract configuration
        self.contract_address = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
        self.module_name = "custodial_usdt"
        self.aptos_node_url = "https://fullnode.testnet.aptoslabs.com/v1"
    
    def create_wallet(self, email: str, username: str) -> tuple[str, str]:
        """
        Create Crossmint MPC wallet
        
        Args:
            email: User's email
            username: User's username
        
        Returns:
            (wallet_address, wallet_id)
        """
        wallet_data = {
            "type": "aptos-mpc-wallet",
            "linkedUser": f"email:{email}",
            "metadata": {
                "username": username,
                "created_via": "crossmint_api"
            }
        }
        
        response = requests.post(
            f"{self.base_url}/v1-alpha2/wallets",
            headers=self.headers,
            json=wallet_data,
            timeout=30
        )
        
        print(f"Create Wallet Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            wallet_info = response.json()
            wallet_address = wallet_info.get("address")
            wallet_id = wallet_info.get("linkedUser", wallet_info.get("id"))
            
            print(f"SUCCESS - Wallet created: {wallet_address}")
            return wallet_address, wallet_id
        else:
            raise Exception(f"Crossmint API error: {response.status_code} - {response.text}")
    
    def deposit(self, to_address: str, amount_usdt: float) -> Optional[str]:
        """
        Deposit USDT to a wallet (admin signs via contract call)
        
        Args:
            to_address: Recipient wallet address
            amount_usdt: Amount in USDT
        
        Returns:
            Transaction hash or None
        """
        amount_u128 = str(int(amount_usdt * 1_000_000))
        
        # Build wallet locator
        if ":" in self.admin_wallet_locator:
            if not self.admin_wallet_locator.endswith(":aptos-mpc-wallet"):
                wallet_locator = f"{self.admin_wallet_locator}:aptos-mpc-wallet"
            else:
                wallet_locator = self.admin_wallet_locator
        else:
            wallet_locator = f"email:{self.admin_wallet_locator}:aptos-mpc-wallet"
        
        transaction_data = {
            "chain": "aptos",
            "params": {
                "type": "entry-function",
                "function": f"{self.contract_address}::{self.module_name}::deposit",
                "type_arguments": [],
                "arguments": [to_address, amount_u128]
            }
        }
        
        print(f"Deposit Request:")
        print(f"  URL: {self.base_url}/v1-alpha2/wallets/{wallet_locator}/transactions")
        print(f"  Payload: {json.dumps(transaction_data, indent=2)}")
        
        response = requests.post(
            f"{self.base_url}/v1-alpha2/wallets/{wallet_locator}/transactions",
            headers=self.headers,
            json=transaction_data,
            timeout=30
        )
        
        print(f"Deposit Response: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            tx_hash = result.get("transactionHash") or result.get("txHash") or result.get("hash")
            print(f"SUCCESS - Deposit TX: {tx_hash}")
            return tx_hash
        else:
            print(f"ERROR - Deposit failed: {response.text}")
            return None
    
    def withdraw(self, user_wallet_locator: str, amount_usdt: float) -> Optional[str]:
        """
        Withdraw USDT from user's wallet (user signs via MPC)
        
        Args:
            user_wallet_locator: User's wallet locator (email:user@example.com:aptos-mpc-wallet)
            amount_usdt: Amount in USDT
        
        Returns:
            Transaction hash or None
        """
        amount_u128 = str(int(amount_usdt * 1_000_000))
        
        # Ensure proper locator format
        if not user_wallet_locator.endswith(":aptos-mpc-wallet"):
            if ":" in user_wallet_locator:
                user_wallet_locator = f"{user_wallet_locator}:aptos-mpc-wallet"
            else:
                user_wallet_locator = f"email:{user_wallet_locator}:aptos-mpc-wallet"
        
        transaction_data = {
            "chain": "aptos",
            "params": {
                "type": "entry-function",
                "function": f"{self.contract_address}::{self.module_name}::withdraw",
                "type_arguments": [],
                "arguments": [amount_u128]  # Only amount - user is auto-detected from signer
            }
        }
        
        print(f"Withdraw Request:")
        print(f"  URL: {self.base_url}/v1-alpha2/wallets/{user_wallet_locator}/transactions")
        print(f"  Payload: {json.dumps(transaction_data, indent=2)}")
        
        response = requests.post(
            f"{self.base_url}/v1-alpha2/wallets/{user_wallet_locator}/transactions",
            headers=self.headers,
            json=transaction_data,
            timeout=30
        )
        
        print(f"Withdraw Response: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            tx_hash = result.get("transactionHash") or result.get("txHash") or result.get("hash")
            print(f"SUCCESS - Withdrawal TX: {tx_hash}")
            return tx_hash
        else:
            print(f"ERROR - Withdrawal failed: {response.text}")
            return None
    
    def transfer(self, from_wallet_locator: str, to_address: str, amount_usdt: float) -> Optional[str]:
        """
        Transfer USDT between wallets (from user signs via MPC)
        
        Args:
            from_wallet_locator: Sender's wallet locator
            to_address: Recipient's wallet address
            amount_usdt: Amount in USDT
        
        Returns:
            Transaction hash or None
        """
        amount_u128 = str(int(amount_usdt * 1_000_000))
        
        # Ensure proper locator format
        if not from_wallet_locator.endswith(":aptos-mpc-wallet"):
            if ":" in from_wallet_locator:
                from_wallet_locator = f"{from_wallet_locator}:aptos-mpc-wallet"
            else:
                from_wallet_locator = f"email:{from_wallet_locator}:aptos-mpc-wallet"
        
        transaction_data = {
            "chain": "aptos",
            "params": {
                "type": "entry-function",
                "function": f"{self.contract_address}::{self.module_name}::transfer",
                "type_arguments": [],
                "arguments": [to_address, amount_u128]
            }
        }
        
        print(f"Transfer Request:")
        print(f"  URL: {self.base_url}/v1-alpha2/wallets/{from_wallet_locator}/transactions")
        print(f"  Payload: {json.dumps(transaction_data, indent=2)}")
        
        response = requests.post(
            f"{self.base_url}/v1-alpha2/wallets/{from_wallet_locator}/transactions",
            headers=self.headers,
            json=transaction_data,
            timeout=30
        )
        
        print(f"Transfer Response: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            tx_hash = result.get("transactionHash") or result.get("txHash") or result.get("hash")
            print(f"SUCCESS - Transfer TX: {tx_hash}")
            return tx_hash
        else:
            print(f"ERROR - Transfer failed: {response.text}")
            return None
    
    def check_balance(self, wallet_address: str) -> Optional[float]:
        """
        Check wallet balance using Aptos REST API (no Crossmint needed!)
        
        Args:
            wallet_address: Wallet address to check
        
        Returns:
            Balance in USDT or None
        """
        payload = {
            "function": f"{self.contract_address}::{self.module_name}::balance_of",
            "type_arguments": [],
            "arguments": [wallet_address]
        }
        
        try:
            response = requests.post(
                f"{self.aptos_node_url}/view",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and result:
                    balance_u128 = int(result[0])
                    balance_usdt = balance_u128 / 1_000_000
                    print(f"SUCCESS - Balance: {balance_usdt} USDT")
                    return balance_usdt
                else:
                    print(f"WARNING - Unexpected balance format: {result}")
                    return 0.0
            else:
                print(f"ERROR - Balance check failed: {response.text}")
                return None
        
        except Exception as e:
            print(f"ERROR - Error checking balance: {e}")
            return None


# ================================================================================
# TEST FUNCTIONS
# ================================================================================

def test_all_operations():
    """Test all Crossmint wallet operations"""
    
    print("="*80)
    print("CROSSMINT WALLET OPERATIONS - COMPLETE TEST")
    print("="*80)
    
    service = CrossmintWalletService()
    
    # Test 1: Create Wallet
    print("\n[TEST 1] Create Wallet")
    print("-"*80)
    
    import time
    test_email = f"test_{int(time.time())}@kryzel.io"
    test_username = f"testuser_{int(time.time())}"
    
    try:
        wallet_address, wallet_id = service.create_wallet(test_email, test_username)
        print(f"SUCCESS - Wallet: {wallet_address}")
    except Exception as e:
        print(f"FAILED - {e}")
        return
    
    # Test 2: Check Balance (should be 0)
    print("\n[TEST 2] Check Balance (Initial)")
    print("-"*80)
    
    balance = service.check_balance(wallet_address)
    print(f"Initial balance: {balance} USDT")
    
    # Test 3: Deposit
    print("\n[TEST 3] Deposit Funds")
    print("-"*80)
    
    tx_hash = service.deposit(wallet_address, 50.0)
    if tx_hash:
        print(f"SUCCESS - TX: {tx_hash}")
    else:
        print("FAILED - Deposit returned None (check errors above)")
    
    # Test 4: Check Balance (should show deposit)
    print("\n[TEST 4] Check Balance (After Deposit)")
    print("-"*80)
    
    import time
    time.sleep(3)  # Wait for transaction
    balance = service.check_balance(wallet_address)
    print(f"Balance after deposit: {balance} USDT")
    
    # Test 5: Withdraw (if deposit worked)
    if tx_hash:
        print("\n[TEST 5] Withdraw Funds")
        print("-"*80)
        
        user_locator = f"email:{test_email}:aptos-mpc-wallet"
        tx_hash_withdraw = service.withdraw(user_locator, 10.0)
        
        if tx_hash_withdraw:
            print(f"SUCCESS - TX: {tx_hash_withdraw}")
        else:
            print("FAILED - Withdraw returned None (check errors above)")
    
    # Test 6: Transfer (create second wallet)
    print("\n[TEST 6] Transfer Between Wallets")
    print("-"*80)
    
    try:
        # Create second wallet
        wallet2_address, wallet2_id = service.create_wallet(
            f"recipient_{int(time.time())}@kryzel.io",
            f"recipient_{int(time.time())}"
        )
        print(f"Second wallet created: {wallet2_address}")
        
        # Transfer from first to second
        from_locator = f"email:{test_email}:aptos-mpc-wallet"
        tx_hash_transfer = service.transfer(from_locator, wallet2_address, 5.0)
        
        if tx_hash_transfer:
            print(f"SUCCESS - TX: {tx_hash_transfer}")
        else:
            print("FAILED - Transfer returned None (check errors above)")
    
    except Exception as e:
        print(f"FAILED - {e}")
    
    # Final balances
    print("\n[FINAL] Check All Balances")
    print("-"*80)
    
    balance1 = service.check_balance(wallet_address)
    print(f"Wallet 1: {balance1} USDT")
    
    if 'wallet2_address' in locals():
        balance2 = service.check_balance(wallet2_address)
        print(f"Wallet 2: {balance2} USDT")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    test_all_operations()

