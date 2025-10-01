#!/usr/bin/env python3
"""
Crossmint USDT Aptos Service - 4 Wallet System
Handles USDT wallet creation and management on Aptos via Crossmint API
"""

import os
import requests
import logging
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CrossmintUSDTService:
    """
    Service for managing USDT wallets on Aptos via Crossmint
    Creates 4 separate wallets per operator to mirror the traditional system
    """
    
    def __init__(self):
        load_dotenv('env.aptos')
        self.api_key = os.getenv('CROSSMINT_API_KEY')
        self.project_id = os.getenv('CROSSMINT_PROJECT_ID')
        self.environment = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')
        self.base_url = f"https://{self.environment}.crossmint.com/api"
        
        # Our deployed USDT contract address on Aptos testnet
        self.usdt_contract = "0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT"
        
        self.headers = {
            "X-API-KEY": self.api_key,
            "X-PROJECT-ID": self.project_id,
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Crossmint USDT Service - Environment: {self.environment}")

    def create_operator_wallets_complete(self, operator_id: int, email: str, sportsbook_name: str) -> Dict:
        """
        Create 4 separate Aptos USDT wallets for the complete 4-wallet system
        
        Args:
            operator_id: Unique operator identifier
            email: Operator's email address  
            sportsbook_name: Name of the sportsbook
            
        Returns:
            Dict containing all 4 wallet addresses and details
        """
        try:
            logger.info(f"Creating 4 Aptos USDT wallets for operator {operator_id}: {sportsbook_name}")
            
            wallet_types = [
                {
                    'type': 'bookmaker_capital', 
                    'description': 'Bookmaker Capital USDT Wallet',
                    'initial_usdt': 10000.0
                },
                {
                    'type': 'liquidity_pool', 
                    'description': 'Liquidity Pool USDT Wallet',
                    'initial_usdt': 40000.0
                }, 
                {
                    'type': 'revenue', 
                    'description': 'Revenue USDT Wallet',
                    'initial_usdt': 0.0
                },
                {
                    'type': 'community', 
                    'description': 'Community USDT Wallet',
                    'initial_usdt': 0.0
                }
            ]
            
            created_wallets = {}
            
            for wallet_config in wallet_types:
                wallet_type = wallet_config['type']
                description = wallet_config['description']
                initial_usdt = wallet_config['initial_usdt']
                
                logger.info(f"Creating {wallet_type} wallet for operator {operator_id}")
                
                wallet_data = {
                    "type": "aptos-mpc-wallet",
                    "linkedUser": f"email:{email}",
                    "metadata": {
                        "operator_id": operator_id,
                        "email": email,
                        "sportsbook_name": sportsbook_name,
                        "wallet_type": wallet_type,
                        "description": description,
                        "token_type": "USDT",
                        "initial_usdt_balance": initial_usdt,
                        "usdt_contract": self.usdt_contract,
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
                    created_wallets[wallet_type] = {
                        'wallet_address': wallet_info.get('address'),
                        'wallet_id': wallet_info.get('id'),
                        'wallet_type': wallet_type,
                        'description': description,
                        'chain': 'aptos',
                        'token_type': 'USDT',
                        'initial_usdt_balance': initial_usdt,
                        'usdt_contract': self.usdt_contract
                    }
                    logger.info(f"✅ Created {wallet_type} wallet: {wallet_info.get('address')} (Initial: {initial_usdt} USDT)")
                else:
                    logger.error(f"❌ Failed to create {wallet_type} wallet: {response.status_code} - {response.text}")
                    return {
                        'success': False, 
                        'error': f'Failed to create {wallet_type} wallet', 
                        'message': response.text
                    }
            
            result = {
                'success': True,
                'operator_id': operator_id,
                'wallets': created_wallets,
                'total_wallets': len(created_wallets),
                'total_initial_usdt': sum(w['initial_usdt_balance'] for w in created_wallets.values()),
                'usdt_contract': self.usdt_contract,
                'created_at': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Successfully created {len(created_wallets)} Aptos USDT wallets for operator {operator_id}")
            logger.info(f"💰 Total initial USDT allocated: {result['total_initial_usdt']} USDT")
            return result
            
        except Exception as e:
            logger.error(f"❌ Exception creating operator wallets: {e}")
            return {
                'success': False,
                'error': 'Exception', 
                'message': str(e)
            }

    def create_user_wallet(self, user_id: int, email: str, username: str, operator_id: int, initial_usdt: float = 1000.0) -> Dict:
        """
        Create a single Aptos USDT wallet for a user
        
        Args:
            user_id: Unique user identifier
            email: User's email address
            username: User's username
            operator_id: Associated operator ID
            initial_usdt: Initial USDT balance (default 1000.0)
            
        Returns:
            Dict containing wallet address and details
        """
        try:
            logger.info(f"Creating Aptos USDT wallet for user {user_id}: {username}")
            
            wallet_data = {
                "type": "aptos-mpc-wallet",
                "linkedUser": f"email:{email}",
                "metadata": {
                    "user_id": user_id,
                    "email": email,
                    "username": username,
                    "operator_id": operator_id,
                    "wallet_type": "user",
                    "token_type": "USDT",
                    "initial_usdt_balance": initial_usdt,
                    "usdt_contract": self.usdt_contract,
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
                    'token_type': 'USDT',
                    'initial_usdt_balance': initial_usdt,
                    'usdt_contract': self.usdt_contract,
                    'user_id': user_id,
                    'operator_id': operator_id,
                    'created_at': datetime.now().isoformat()
                }
                
                logger.info(f"✅ Created USDT wallet for user {user_id}: {result['wallet_address']} ({initial_usdt} USDT)")
                return result
                
            else:
                logger.error(f"❌ Failed to create user wallet: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception creating user wallet: {e}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }

    def get_usdt_balance(self, wallet_address: str) -> Dict:
        """
        Get USDT balance for a specific wallet
        
        Args:
            wallet_address: Aptos wallet address
            
        Returns:
            Dict containing balance information
        """
        try:
            logger.info(f"Getting USDT balance for wallet {wallet_address}")
            
            # Get USDT balance using Crossmint's balance API
            response = requests.get(
                f"{self.base_url}/v1-alpha2/wallets/{wallet_address}/balances",
                headers=self.headers,
                params={"tokens": self.usdt_contract}
            )
            
            if response.status_code == 200:
                balance_data = response.json()
                
                result = {
                    'success': True,
                    'wallet_address': wallet_address,
                    'usdt_balance': balance_data.get('balance', 0),
                    'usdt_contract': self.usdt_contract,
                    'chain': 'aptos'
                }
                
                logger.info(f"✅ USDT balance for {wallet_address}: {result['usdt_balance']}")
                return result
                
            else:
                logger.error(f"❌ Failed to get balance: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception getting balance: {e}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }

    def transfer_usdt(self, from_wallet: str, to_wallet: str, amount: float, description: str = "") -> Dict:
        """
        Transfer USDT between wallets
        
        Args:
            from_wallet: Source wallet address
            to_wallet: Destination wallet address  
            amount: Amount of USDT to transfer
            description: Transaction description
            
        Returns:
            Dict containing transaction details
        """
        try:
            logger.info(f"Transferring {amount} USDT from {from_wallet} to {to_wallet}")
            
            # Convert to smallest USDT units (assuming 6 decimals like standard USDT)
            usdt_amount = str(int(amount * (10**6)))
            
            transfer_data = {
                "from": from_wallet,
                "to": to_wallet,
                "amount": usdt_amount,
                "token": self.usdt_contract,
                "description": description or f"USDT transfer: {amount}"
            }
            
            response = requests.post(
                f"{self.base_url}/v1-alpha2/wallets/transfer",
                headers=self.headers,
                json=transfer_data
            )
            
            if response.status_code == 200:
                transfer_info = response.json()
                
                result = {
                    'success': True,
                    'transaction_hash': transfer_info.get('transactionHash'),
                    'from_wallet': from_wallet,
                    'to_wallet': to_wallet,
                    'amount': amount,
                    'usdt_amount': usdt_amount,
                    'token_type': 'USDT',
                    'chain': 'aptos',
                    'description': description
                }
                
                logger.info(f"✅ USDT transfer successful: {result['transaction_hash']}")
                return result
                
            else:
                logger.error(f"❌ Failed to transfer USDT: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'message': response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception transferring USDT: {e}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }

    def get_usdt_contract_info(self) -> Dict:
        """
        Get USDT contract information
        
        Returns:
            Dict containing contract details
        """
        return {
            'contract_address': self.usdt_contract,
            'token_name': 'Tether USD',
            'token_symbol': 'USDT',
            'decimals': 6,
            'chain': 'aptos',
            'network': 'testnet',
            'explorer_url': f'https://explorer.aptoslabs.com/account/{self.usdt_contract.split("::")[0]}?network=testnet'
        }

    def format_usdt_amount(self, amount: float) -> str:
        """
        Format USDT amount to smallest units (6 decimals)
        
        Args:
            amount: USDT amount in human-readable format
            
        Returns:
            String representation in smallest units
        """
        return str(int(amount * (10**6)))

    def parse_usdt_amount(self, raw_amount: str) -> float:
        """
        Parse USDT amount from smallest units to human-readable format
        
        Args:
            raw_amount: Amount in smallest units
            
        Returns:
            Float amount in USDT
        """
        return float(raw_amount) / (10**6)

    def validate_aptos_address(self, address: str) -> bool:
        """
        Validate Aptos wallet address format
        
        Args:
            address: Aptos address to validate
            
        Returns:
            Boolean indicating if address is valid
        """
        if not address:
            return False
        
        # Aptos addresses are 32 bytes (64 hex chars) with 0x prefix
        if not address.startswith('0x'):
            return False
        
        # Remove 0x prefix and check length
        hex_part = address[2:]
        if len(hex_part) != 64:
            return False
        
        # Check if all characters are valid hex
        try:
            int(hex_part, 16)
            return True
        except ValueError:
            return False
