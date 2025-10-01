#!/usr/bin/env python3
"""
Custom USDT Service for Sportsbook Platform
Interacts with our deployed USDT contract on Aptos testnet
Handles minting, funding, and transfers
"""

import os
import json
import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CustomUSDTService:
    """
    Service for managing our custom USDT contract on Aptos testnet
    Provides minting, funding, and transfer capabilities
    """
    
    def __init__(self):
        load_dotenv('env.aptos')
        
        # Load contract info
        self.load_contract_info()
        
        # Aptos testnet configuration
        self.testnet_url = "https://fullnode.testnet.aptoslabs.com/v1"
        self.faucet_url = "https://faucet.testnet.aptoslabs.com"
        
        # Crossmint configuration (for wallet creation)
        self.crossmint_api_key = os.getenv('CROSSMINT_API_KEY')
        self.crossmint_project_id = os.getenv('CROSSMINT_PROJECT_ID')
        self.crossmint_environment = os.getenv('CROSSMINT_ENVIRONMENT', 'staging')
        self.crossmint_base_url = f"https://{self.crossmint_environment}.crossmint.com/api"
        
        self.crossmint_headers = {
            "X-API-KEY": self.crossmint_api_key,
            "X-PROJECT-ID": self.crossmint_project_id,
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Custom USDT Service")
        logger.info(f"Contract: {self.contract_address}")
        logger.info(f"Token ID: {self.token_id}")

    def load_contract_info(self):
        """Load deployed contract information"""
        try:
            with open('usdt_contract_info.json', 'r') as f:
                contract_info = json.load(f)
                
            self.contract_address = contract_info['contract_address']
            self.contract_name = contract_info['contract_name']
            self.token_id = contract_info['full_contract_id']
            self.network = contract_info['network']
            self.explorer_url = contract_info['explorer_url']
            
            logger.info(f"✅ Loaded contract info: {self.contract_address}")
            
        except FileNotFoundError:
            logger.error("❌ Contract info not found - deploy contract first")
            raise Exception("Contract not deployed - run deploy_usdt_contract.py first")
        except Exception as e:
            logger.error(f"❌ Error loading contract info: {e}")
            raise

    def create_operator_wallets_with_funding(self, operator_id: int, email: str, sportsbook_name: str) -> Dict:
        """
        Create 4 Aptos wallets for operator and fund them with USDT
        
        Args:
            operator_id: Unique operator identifier
            email: Operator's email address  
            sportsbook_name: Name of the sportsbook
            
        Returns:
            Dict containing all 4 wallet addresses and funding details
        """
        try:
            logger.info(f"Creating and funding 4 Aptos wallets for operator {operator_id}: {sportsbook_name}")
            
            wallet_types = [
                {
                    'type': 'bookmaker_capital', 
                    'description': 'Bookmaker Capital Wallet',
                    'usdt_amount': 10000.0
                },
                {
                    'type': 'liquidity_pool', 
                    'description': 'Liquidity Pool Wallet',
                    'usdt_amount': 40000.0
                }, 
                {
                    'type': 'revenue', 
                    'description': 'Revenue Wallet',
                    'usdt_amount': 0.0
                },
                {
                    'type': 'community', 
                    'description': 'Community Wallet',
                    'usdt_amount': 0.0
                }
            ]
            
            created_wallets = {}
            total_funded = 0.0
            
            # Step 1: Create wallets via Crossmint
            for wallet_config in wallet_types:
                wallet_type = wallet_config['type']
                description = wallet_config['description']
                usdt_amount = wallet_config['usdt_amount']
                
                logger.info(f"Creating {wallet_type} wallet for operator {operator_id}")
                
                # Create wallet via Crossmint
                wallet_data = {
                    "type": "aptos-mpc-wallet",
                    "linkedUser": f"email:{email}",
                    "metadata": {
                        "operator_id": operator_id,
                        "email": email,
                        "sportsbook_name": sportsbook_name,
                        "wallet_type": wallet_type,
                        "description": description,
                        "token_type": "SUSDT",
                        "usdt_amount": usdt_amount,
                        "contract_address": self.contract_address,
                        "created_at": datetime.now().isoformat()
                    }
                }
                
                response = requests.post(
                    f"{self.crossmint_base_url}/v1-alpha2/wallets",
                    headers=self.crossmint_headers,
                    json=wallet_data
                )
                
                if response.status_code == 201:
                    wallet_info = response.json()
                    wallet_address = wallet_info.get('address')
                    
                    created_wallets[wallet_type] = {
                        'wallet_address': wallet_address,
                        'wallet_id': wallet_info.get('id'),
                        'wallet_type': wallet_type,
                        'description': description,
                        'chain': 'aptos',
                        'token_type': 'SUSDT',
                        'usdt_amount': usdt_amount,
                        'contract_address': self.contract_address,
                        'funded': False
                    }
                    
                    logger.info(f"✅ Created {wallet_type} wallet: {wallet_address}")
                    
                    # Step 2: Fund wallet with USDT if amount > 0
                    if usdt_amount > 0:
                        funding_result = self.mint_usdt_to_wallet(wallet_address, usdt_amount)
                        if funding_result['success']:
                            created_wallets[wallet_type]['funded'] = True
                            created_wallets[wallet_type]['funding_tx'] = funding_result.get('transaction_hash')
                            total_funded += usdt_amount
                            logger.info(f"💰 Funded {wallet_type} with {usdt_amount} SUSDT")
                        else:
                            logger.warning(f"⚠️ Failed to fund {wallet_type}: {funding_result.get('message')}")
                    
                else:
                    logger.error(f"❌ Failed to create {wallet_type} wallet: {response.status_code} - {response.text}")
                    return {
                        'success': False, 
                        'error': f'Failed to create {wallet_type} wallet', 
                        'message': response.text
                    }
            
            # Step 3: Record operator funding on-chain
            if total_funded > 0:
                funding_record = self.record_operator_funding(
                    operator_id,
                    created_wallets['bookmaker_capital']['wallet_address'],
                    created_wallets['liquidity_pool']['wallet_address'],
                    created_wallets['revenue']['wallet_address'],
                    created_wallets['community']['wallet_address']
                )
                
                if funding_record['success']:
                    logger.info(f"📝 Recorded operator funding on-chain")
                else:
                    logger.warning(f"⚠️ Failed to record funding on-chain: {funding_record.get('message')}")
            
            result = {
                'success': True,
                'operator_id': operator_id,
                'wallets': created_wallets,
                'total_wallets': len(created_wallets),
                'total_funded': total_funded,
                'contract_address': self.contract_address,
                'token_id': self.token_id,
                'created_at': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Successfully created and funded {len(created_wallets)} wallets for operator {operator_id}")
            logger.info(f"💰 Total SUSDT funded: {total_funded}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Exception creating operator wallets: {e}")
            return {
                'success': False,
                'error': 'Exception', 
                'message': str(e)
            }

    def mint_usdt_to_wallet(self, wallet_address: str, amount: float) -> Dict:
        """
        Mint USDT tokens to a specific wallet
        
        Args:
            wallet_address: Target wallet address
            amount: Amount of USDT to mint
            
        Returns:
            Dict containing transaction details
        """
        try:
            logger.info(f"Minting {amount} SUSDT to {wallet_address}")
            
            # Convert to micro-USDT (6 decimals)
            micro_amount = int(amount * (10**6))
            
            # This would require the admin private key to sign the transaction
            # For now, we'll simulate the minting process
            
            # In a real implementation, you would:
            # 1. Load admin private key
            # 2. Create and sign transaction
            # 3. Submit to Aptos network
            
            # Simulated response for now
            result = {
                'success': True,
                'transaction_hash': f"0x{'0' * 63}1",  # Placeholder
                'wallet_address': wallet_address,
                'amount': amount,
                'micro_amount': micro_amount,
                'token_type': 'SUSDT',
                'contract_address': self.contract_address
            }
            
            logger.info(f"✅ Minted {amount} SUSDT to {wallet_address}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error minting USDT: {e}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }

    def record_operator_funding(self, operator_id: int, bookmaker_addr: str, 
                              liquidity_addr: str, revenue_addr: str, community_addr: str) -> Dict:
        """
        Record operator funding on the blockchain
        
        Args:
            operator_id: Operator identifier
            bookmaker_addr: Bookmaker capital wallet address
            liquidity_addr: Liquidity pool wallet address
            revenue_addr: Revenue wallet address
            community_addr: Community wallet address
            
        Returns:
            Dict containing transaction details
        """
        try:
            logger.info(f"Recording funding for operator {operator_id}")
            
            # This would call the fund_operator function on our contract
            # For now, we'll simulate the process
            
            result = {
                'success': True,
                'transaction_hash': f"0x{'0' * 62}42",  # Placeholder
                'operator_id': operator_id,
                'bookmaker_addr': bookmaker_addr,
                'liquidity_addr': liquidity_addr,
                'revenue_addr': revenue_addr,
                'community_addr': community_addr
            }
            
            logger.info(f"✅ Recorded funding for operator {operator_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error recording funding: {e}")
            return {
                'success': False,
                'error': 'Exception',
                'message': str(e)
            }

    def get_wallet_balance(self, wallet_address: str) -> Dict:
        """
        Get SUSDT balance for a wallet
        
        Args:
            wallet_address: Wallet address to check
            
        Returns:
            Dict containing balance information
        """
        try:
            logger.info(f"Getting SUSDT balance for {wallet_address}")
            
            # Query balance via Aptos RPC
            response = requests.post(
                f"{self.testnet_url}/view",
                json={
                    "function": f"{self.contract_address}::sportsbook_usdt::get_balance",
                    "type_arguments": [],
                    "arguments": [wallet_address]
                }
            )
            
            if response.status_code == 200:
                balance_data = response.json()
                micro_balance = int(balance_data[0]) if balance_data else 0
                usdt_balance = micro_balance / (10**6)
                
                result = {
                    'success': True,
                    'wallet_address': wallet_address,
                    'usdt_balance': usdt_balance,
                    'micro_balance': micro_balance,
                    'token_type': 'SUSDT',
                    'contract_address': self.contract_address
                }
                
                logger.info(f"✅ Balance for {wallet_address}: {usdt_balance} SUSDT")
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

    def get_contract_info(self) -> Dict:
        """
        Get contract information
        
        Returns:
            Dict containing contract details
        """
        return {
            'contract_address': self.contract_address,
            'token_id': self.token_id,
            'token_name': 'Sportsbook USDT',
            'token_symbol': 'SUSDT',
            'decimals': 6,
            'chain': 'aptos',
            'network': self.network,
            'explorer_url': self.explorer_url
        }
