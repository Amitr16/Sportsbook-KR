#!/usr/bin/env python3
"""
Crossmint Aptos Service
Handles Aptos wallet creation, management, and transactions using Crossmint API
"""

import os
import json
import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrossmintAptosService:
    """
    Service for managing Aptos wallets and transactions via Crossmint
    """
    
    def __init__(self):
        """Initialize Crossmint Aptos service with API credentials"""
        load_dotenv()
        self.api_key = os.getenv('CROSSMINT_API_KEY')
        self.project_id = os.getenv('CROSSMINT_PROJECT_ID')
        self.environment = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')  # staging or production
        
        # Crossmint API endpoints
        if self.environment == 'production':
            self.base_url = "https://www.crossmint.com/api"
        else:
            self.base_url = "https://staging.crossmint.com/api"
            
        self.headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Initialized Crossmint Aptos Service - Environment: {self.environment}")
    
    def create_operator_wallet(self, operator_id: int, email: str, sportsbook_name: str) -> Dict:
        """
        Create custodial Aptos wallet for sportsbook operator
        
        Args:
            operator_id: Database ID of the operator
            email: Operator's email address
            sportsbook_name: Name of the sportsbook
            
        Returns:
            Dict containing wallet address and other details
        """
        try:
            logger.info(f"Creating Aptos wallet for operator {operator_id}: {sportsbook_name}")
            
            # Create MPC wallet via Crossmint for Aptos
            wallet_data = {
                "type": "aptos-mpc-wallet",
                "linkedUser": f"email:{email}",
                "metadata": {
                    "operator_id": operator_id,
                    "email": email,
                    "sportsbook_name": sportsbook_name,
                    "wallet_type": "operator",
                    "created_at": datetime.now().isoformat()
                }
            }
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets",
                headers=self.headers,
                json=wallet_data
            )
            
            if response.status_code == 201:
                wallet_info = response.json()
                
                result = {
                    'success': True,
                    'wallet_address': wallet_info.get('address'),
                    'wallet_id': wallet_info.get('id'),
                    'chain': 'aptos',
                    'type': 'aptos-mpc-wallet',
                    'operator_id': operator_id,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Created Aptos wallet for operator {operator_id}: {result['wallet_address']}")
                return result
                
            else:
                logger.error(f"❌ Failed to create operator wallet: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating operator wallet: {str(e)}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }
    
    def create_user_wallet(self, user_id: int, email: str, username: str, operator_id: int) -> Dict:
        """
        Create custodial Aptos wallet for betting user
        
        Args:
            user_id: Database ID of the user
            email: User's email address  
            username: User's username
            operator_id: ID of the sportsbook operator
            
        Returns:
            Dict containing wallet address and other details
        """
        try:
            logger.info(f"Creating Aptos wallet for user {user_id}: {username}")
            
            # Create MPC wallet via Crossmint for Aptos
            wallet_data = {
                "type": "aptos-mpc-wallet",
                "linkedUser": f"email:{email}",
                "metadata": {
                    "user_id": user_id,
                    "email": email,
                    "username": username,
                    "operator_id": operator_id,
                    "wallet_type": "user",
                    "created_at": datetime.now().isoformat()
                }
            }
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets",
                headers=self.headers,
                json=wallet_data
            )
            
            if response.status_code == 201:
                wallet_info = response.json()
                
                result = {
                    'success': True,
                    'wallet_address': wallet_info.get('address'),
                    'wallet_id': wallet_info.get('id'),
                    'chain': 'aptos',
                    'type': 'aptos-mpc-wallet',
                    'user_id': user_id,
                    'operator_id': operator_id,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Created Aptos wallet for user {user_id}: {result['wallet_address']}")
                return result
                
            else:
                logger.error(f"❌ Failed to create user wallet: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating user wallet: {str(e)}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }
    
    def get_wallet_balance(self, wallet_address: str, token_type: str = "APT") -> Dict:
        """
        Get wallet balance for specified token
        
        Args:
            wallet_address: Aptos wallet address
            token_type: Token type (APT for native Aptos coin)
            
        Returns:
            Dict containing balance information
        """
        try:
            logger.info(f"Getting balance for wallet {wallet_address}")
            
            response = requests.get(
                f"{self.base_url}/v1-alpha2/wallets/{wallet_address}/balances",
                headers=self.headers,
                params={'chain': 'aptos'}
            )
            
            if response.status_code == 200:
                balances = response.json()
                
                # Find the specific token balance
                for balance in balances.get('balances', []):
                    if balance.get('currency') == token_type:
                        return {
                            'success': True,
                            'balance': balance.get('amount', '0'),
                            'currency': token_type,
                            'wallet_address': wallet_address
                        }
                
                # If token not found, return 0 balance
                return {
                    'success': True,
                    'balance': '0',
                    'currency': token_type,
                    'wallet_address': wallet_address
                }
                
            else:
                logger.error(f"❌ Failed to get wallet balance: {response.status_code}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting wallet balance: {str(e)}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }
    
    def transfer_tokens(self, from_wallet: str, to_wallet: str, amount: str, token_type: str = "APT") -> Dict:
        """
        Transfer tokens between wallets
        
        Args:
            from_wallet: Source wallet address
            to_wallet: Destination wallet address  
            amount: Amount to transfer (in token's smallest unit)
            token_type: Token type to transfer
            
        Returns:
            Dict containing transaction details
        """
        try:
            logger.info(f"Transferring {amount} {token_type} from {from_wallet} to {to_wallet}")
            
            transfer_data = {
                "chain": "aptos",
                "from": from_wallet,
                "to": to_wallet,
                "amount": amount,
                "currency": token_type
            }
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets/transfers",
                headers=self.headers,
                json=transfer_data
            )
            
            if response.status_code == 200:
                transfer_info = response.json()
                
                result = {
                    'success': True,
                    'transaction_hash': transfer_info.get('txHash'),
                    'from_wallet': from_wallet,
                    'to_wallet': to_wallet,
                    'amount': amount,
                    'currency': token_type,
                    'status': transfer_info.get('status')
                }
                
                logger.info(f"✅ Transfer initiated: {result['transaction_hash']}")
                return result
                
            else:
                logger.error(f"❌ Failed to transfer tokens: {response.status_code}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Error transferring tokens: {str(e)}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }
    
    # Token minting and distribution features - TO BE IMPLEMENTED LATER
    # def create_revenue_token(self, operator_id: int, token_name: str, token_symbol: str, supply: int = 1000000) -> Dict:
    # def mint_tokens(self, token_address: str, to_wallet: str, amount: str) -> Dict:
    
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
