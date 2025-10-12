"""
Crossmint Aptos Service
Handles Aptos wallet creation, management, and transactions using Crossmint API
Replaces direct Aptos SDK with managed Web3 infrastructure
"""

import os
import json
import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CrossmintAptosService:
    """
    Service for managing Aptos wallets and transactions via Crossmint
    No private keys needed - Crossmint handles all blockchain complexity
    """
    
    def __init__(self):
        """Initialize Crossmint Aptos service with API credentials"""
        load_dotenv()  # Reload environment variables
        self.api_key = os.getenv('CROSSMINT_API_KEY')
        self.project_id = os.getenv('CROSSMINT_PROJECT_ID')
        self.environment = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')
        
        # Admin wallet for contract interactions (should be created via Crossmint)
        self.admin_wallet_address = os.getenv('CROSSMINT_ADMIN_WALLET_ADDRESS')
        self.admin_wallet_locator = os.getenv('CROSSMINT_ADMIN_WALLET_LOCATOR')  # email:admin@kryzel.io format
        
        # Crossmint API endpoints
        if self.environment == 'production':
            self.base_url = "https://www.crossmint.com/api"
        else:
            self.base_url = "https://staging.crossmint.com/api"
            
        self.headers = {
            'X-API-KEY': self.api_key,
            'X-PROJECT-ID': self.project_id,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Initialized Crossmint Aptos Service - Environment: {self.environment}")
        if self.admin_wallet_address:
            logger.info(f"Admin wallet configured: {self.admin_wallet_address}")
        else:
            logger.warning("⚠️ No admin wallet configured - deposits will be disabled")
    
    def create_wallet(self, user_id: int, email: str, username: str, operator_id: int = None) -> tuple[str, str]:
        """
        Create custodial Aptos wallet (replaces aptos_wallet_service.create_wallet)
        
        Args:
            user_id: Database ID of the user
            email: User's email address  
            username: User's username
            operator_id: ID of the sportsbook operator (optional)
            
        Returns:
            tuple[str, str]: (wallet_address, wallet_id) - no private key needed!
        """
        try:
            logger.info(f"Creating Aptos wallet via Crossmint for user {user_id}: {username}")
            
            # Create MPC wallet via Crossmint for Aptos
            wallet_data = {
                "type": "aptos-mpc-wallet",
                "linkedUser": f"email:{email}",
                "metadata": {
                    "user_id": user_id,
                    "email": email,
                    "username": username,
                    "operator_id": operator_id,
                    "wallet_type": "operator" if operator_id else "user",
                    "created_at": datetime.now().isoformat()
                }
            }
            
            logger.info(f"POST {self.base_url}/v1-alpha2/wallets")
            logger.info(f"Headers: {{'x-api-key': '***', 'Content-Type': 'application/json'}}")
            logger.info(f"Payload: {json.dumps(wallet_data, indent=2)}")
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets",
                headers=self.headers,
                json=wallet_data
            )
            
            logger.info(f"Response Status: {response.status_code}")
            logger.info(f"Response Body: {response.text}")
            
            if response.status_code in [200, 201]:
                wallet_info = response.json()
                wallet_address = wallet_info.get('address')
                # Crossmint doesn't return an 'id' field, use linkedUser as wallet_id
                wallet_id = wallet_info.get('linkedUser', wallet_info.get('id'))
                
                logger.info(f"✅ Created Aptos wallet via Crossmint: {wallet_address}")
                return wallet_address, wallet_id
                
            else:
                logger.error(f"❌ Failed to create wallet: {response.status_code} - {response.text}")
                raise Exception(f"Crossmint API Error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error creating wallet: {str(e)}")
            raise
    
    def deposit(self, to_address: str, amount: float) -> Optional[str]:
        """
        Deposit USDT to a wallet using the custodial_usdt contract via Crossmint
        Admin wallet calls the deposit function on the contract
        
        Args:
            to_address: Recipient's Aptos address
            amount: Amount in USDT
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        try:
            if not self.admin_wallet_locator:
                logger.error("❌ No admin wallet configured - cannot deposit")
                return None
            
            logger.info(f"💸 Depositing {amount} USDT to {to_address} via custodial_usdt contract")
            
            # Contract info from https://github.com/dianasuar/usdt.move
            contract_address = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
            
            # Convert amount to u128 (6 decimals)
            amount_u128 = str(int(amount * 1_000_000))
            
            # Use Crossmint Aptos transaction API
            # Endpoint format: POST /api/v1-alpha2/wallets/{locator}/transactions
            transaction_data = {
                "chain": "aptos",
                "params": {
                    "type": "entry-function",
                    "function": f"{contract_address}::custodial_usdt::deposit",
                    "type_arguments": [],
                    "arguments": [to_address, amount_u128]
                }
            }
            
            # Build the full locator with wallet type
            # Format should be: email:<email>:aptos-mpc-wallet
            if 'email:' in self.admin_wallet_locator:
                email = self.admin_wallet_locator.replace('email:', '')
                full_locator = f"email:{email}:aptos-mpc-wallet"
            else:
                full_locator = self.admin_wallet_locator
            
            logger.info(f"Calling Crossmint transaction API")
            logger.info(f"POST {self.base_url}/v1-alpha2/wallets/{full_locator}/transactions")
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets/{full_locator}/transactions",
                headers=self.headers,
                json=transaction_data
            )
            
            logger.info(f"Response: {response.status_code} - {response.text}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                tx_hash = result.get('transactionHash') or result.get('txHash') or result.get('hash')
                logger.info(f"✅ Deposit transaction submitted - tx: {tx_hash}")
                return tx_hash
            else:
                logger.error(f"❌ Deposit failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Deposit error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def withdraw(self, user_address: str, amount: float) -> Optional[str]:
        """
        Withdraw USDT from a wallet using the custodial_usdt contract
        User withdraws their own funds (or admin can withdraw for users)
        
        Args:
            user_address: User's Aptos address
            amount: Amount in USDT to withdraw
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        try:
            logger.info(f"💰 Withdrawing {amount} USDT from {user_address} via custodial_usdt contract")
            
            # Contract info from https://github.com/dianasuar/usdt.move
            contract_address = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
            
            # Convert amount to u128 (6 decimals)
            amount_u128 = int(amount * 1_000_000)
            
            # For custodial system, withdrawals should be handled by reducing the balance in the contract
            # Since we control all wallets, we can just call admin functions to adjust balances
            logger.warning(f"⚠️ Withdraw requires transaction signing - use Aptos CLI or admin_reset_one function")
            return None
                
        except Exception as e:
            logger.error(f"❌ Withdrawal error: {str(e)}")
            return None
    
    def get_balance(self, address: str) -> Optional[float]:
        """
        Get USDT balance from the deployed custodial_usdt contract
        
        Uses the custodial USDT contract deployed at:
        0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085
        
        Args:
            address: Aptos address to query
        
        Returns:
            Optional[float]: Balance in USDT from the smart contract
        """
        try:
            logger.info(f"Getting USDT balance for {address} from custodial_usdt contract")
            
            # Contract info from https://github.com/dianasuar/usdt.move
            contract_address = "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
            module_name = "custodial_usdt"
            function_name = "balance_of"
            
            # Call the view function via Aptos Node API
            aptos_node_url = "https://fullnode.testnet.aptoslabs.com/v1"
            
            payload = {
                "function": f"{contract_address}::{module_name}::{function_name}",
                "type_arguments": [],
                "arguments": [address]
            }
            
            response = requests.post(
                f"{aptos_node_url}/view",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                # The view function returns a u128 balance
                if result and len(result) > 0:
                    balance_u128 = int(result[0])
                    # Convert from u128 to float (assuming 6 decimals like USDT)
                    balance_usdt = balance_u128 / 1_000_000.0
                    
                    logger.info(f"💵 USDT Balance for {address}: ${balance_usdt:.2f}")
                    return balance_usdt
                else:
                    logger.info(f"💵 USDT Balance for {address}: $0.00 (not found)")
                    return 0.0
            else:
                logger.error(f"❌ Failed to get balance: {response.status_code} - {response.text}")
                return 0.0
                
        except Exception as e:
            logger.error(f"❌ Balance query error: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def get_transaction_status(self, transaction_hash: str) -> Dict:
        """
        Get status of a transaction
        
        Args:
            transaction_hash: Hash of the transaction to check
        
        Returns:
            Dict containing transaction status
        """
        try:
            response = requests.get(
                f"{self.base_url}/v1-alpha2/transactions/{transaction_hash}",
                headers=self.headers,
                params={'chain': 'aptos'}
            )
            
            if response.status_code == 200:
                tx_info = response.json()
                
                return {
                    'success': True,
                    'transaction_hash': transaction_hash,
                    'status': tx_info.get('status'),
                    'block_number': tx_info.get('blockNumber'),
                    'timestamp': tx_info.get('timestamp')
                }
                
            else:
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting transaction status: {str(e)}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }


# Global instance
_crossmint_service = None

def get_crossmint_service() -> CrossmintAptosService:
    """Get or create global Crossmint service instance"""
    global _crossmint_service
    if _crossmint_service is None:
        _crossmint_service = CrossmintAptosService()
    return _crossmint_service
