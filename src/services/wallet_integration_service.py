#!/usr/bin/env python3
"""
Complete Wallet Integration Service
Handles both traditional and Aptos wallet operations seamlessly
"""

import os
import sqlite3
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv('env.aptos')

from src.services.crossmint_aptos_service import CrossmintAptosService

logger = logging.getLogger(__name__)

class WalletIntegrationService:
    """
    Unified service that handles both traditional wallet operations 
    and Aptos blockchain wallet operations
    """
    
    def __init__(self, db_path: str = 'local_app.db'):
        self.db_path = db_path
        self.crossmint = CrossmintAptosService()
        logger.info("Wallet Integration Service initialized")
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =============================================================================
    # OPERATOR WALLET MANAGEMENT
    # =============================================================================
    
    def create_operator_complete(self, operator_data: Dict) -> Dict:
        """
        Create operator with both traditional 4-wallet system AND Aptos wallet
        
        Args:
            operator_data: {
                'sportsbook_name': str,
                'login': str, 
                'password_hash': str,
                'email': str,
                'subdomain': str,
                'enable_web3': bool (optional)
            }
            
        Returns:
            Complete operator creation result including Aptos wallet
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            logger.info(f"Creating complete operator: {operator_data['sportsbook_name']}")
            
            # 1. Create traditional operator record
            cursor.execute("""
                INSERT INTO sportsbook_operators 
                (sportsbook_name, login, password_hash, email, subdomain, web3_enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                operator_data['sportsbook_name'],
                operator_data['login'],
                operator_data['password_hash'],
                operator_data['email'],
                operator_data['subdomain'],
                operator_data.get('enable_web3', True)  # Default to Web3 enabled
            ))
            
            operator_id = cursor.lastrowid
            logger.info(f"Created operator record: ID {operator_id}")
            
            # 2. Create traditional 4-wallet system
            traditional_wallets = self._create_traditional_wallets(operator_id, cursor)
            logger.info(f"Created {len(traditional_wallets)} traditional wallets")
            
            # 3. Create Aptos wallet if Web3 enabled
            aptos_wallet = None
            if operator_data.get('enable_web3', True):
                aptos_wallet = self._create_operator_aptos_wallet(
                    operator_id, 
                    operator_data['email'], 
                    operator_data['sportsbook_name'],
                    cursor
                )
            
            conn.commit()
            
            result = {
                'success': True,
                'operator_id': operator_id,
                'traditional_wallets': traditional_wallets,
                'aptos_wallet': aptos_wallet,
                'web3_enabled': operator_data.get('enable_web3', True)
            }
            
            logger.info(f"✅ Complete operator creation successful: {operator_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error creating complete operator: {e}")
            conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            conn.close()
    
    def _create_traditional_wallets(self, operator_id: int, cursor) -> list:
        """Create the traditional 4-wallet system"""
        wallets = [
            ('bookmaker_capital', 10000.0, 10000.0, 1.0),
            ('liquidity_pool', 40000.0, 40000.0, 5.0),
            ('revenue', 0.0, 0.0, 1.0),
            ('bookmaker_earnings', 0.0, 0.0, 1.0)
        ]
        
        created_wallets = []
        for wallet_type, current_balance, initial_balance, leverage in wallets:
            cursor.execute("""
                INSERT INTO operator_wallets
                (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
                VALUES (?, ?, ?, ?, ?)
            """, (operator_id, wallet_type, current_balance, initial_balance, leverage))
            
            created_wallets.append({
                'wallet_type': wallet_type,
                'current_balance': current_balance,
                'initial_balance': initial_balance,
                'leverage_multiplier': leverage
            })
        
        return created_wallets
    
    def _create_operator_aptos_wallet(self, operator_id: int, email: str, sportsbook_name: str, cursor) -> Optional[Dict]:
        """Create Aptos wallet for operator"""
        try:
            logger.info(f"Creating Aptos wallet for operator {operator_id}")
            
            wallet_result = self.crossmint.create_operator_wallet(
                operator_id=operator_id,
                email=email,
                sportsbook_name=sportsbook_name
            )
            
            if wallet_result['success']:
                # Update operator with Aptos wallet details
                cursor.execute("""
                    UPDATE sportsbook_operators 
                    SET aptos_wallet_address = ?, aptos_wallet_id = ?
                    WHERE id = ?
                """, (
                    wallet_result['wallet_address'],
                    wallet_result['wallet_id'],
                    operator_id
                ))
                
                # Log wallet creation transaction
                cursor.execute("""
                    INSERT INTO aptos_transactions
                    (transaction_hash, transaction_type, to_address, operator_id, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    f"wallet_creation_{operator_id}_{datetime.now().timestamp()}",
                    'wallet_creation',
                    wallet_result['wallet_address'],
                    operator_id,
                    'confirmed'
                ))
                
                logger.info(f"✅ Aptos wallet created: {wallet_result['wallet_address']}")
                return wallet_result
            else:
                logger.warning(f"⚠️ Aptos wallet creation failed: {wallet_result.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating Aptos wallet: {e}")
            return None
    
    # =============================================================================
    # USER WALLET MANAGEMENT
    # =============================================================================
    
    def create_user_complete(self, user_data: Dict, operator_id: int) -> Dict:
        """
        Create user with traditional balance AND optional Aptos wallet
        
        Args:
            user_data: {
                'username': str,
                'email': str,
                'password_hash': str,
                'initial_balance': float (optional),
                'enable_web3': bool (optional)
            }
            operator_id: ID of the sportsbook operator
            
        Returns:
            Complete user creation result
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            logger.info(f"Creating complete user: {user_data['username']}")
            
            # 1. Create traditional user record
            cursor.execute("""
                INSERT INTO users
                (username, email, password_hash, balance, sportsbook_operator_id, web3_enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_data['username'],
                user_data['email'],
                user_data['password_hash'],
                user_data.get('initial_balance', 1000.0),
                operator_id,
                user_data.get('enable_web3', False)
            ))
            
            user_id = cursor.lastrowid
            logger.info(f"Created user record: ID {user_id}")
            
            # 2. Create initial balance transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, amount, transaction_type, description, balance_before, balance_after)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                user_data.get('initial_balance', 1000.0),
                'initial_deposit',
                'Initial account balance',
                0.0,
                user_data.get('initial_balance', 1000.0)
            ))
            
            # 3. Create Aptos wallet if Web3 enabled
            aptos_wallet = None
            if user_data.get('enable_web3', False):
                aptos_wallet = self._create_user_aptos_wallet(
                    user_id,
                    user_data['email'],
                    user_data['username'],
                    operator_id,
                    cursor
                )
            
            conn.commit()
            
            result = {
                'success': True,
                'user_id': user_id,
                'username': user_data['username'],
                'traditional_balance': user_data.get('initial_balance', 1000.0),
                'aptos_wallet': aptos_wallet,
                'web3_enabled': user_data.get('enable_web3', False)
            }
            
            logger.info(f"✅ Complete user creation successful: {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error creating complete user: {e}")
            conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            conn.close()
    
    def _create_user_aptos_wallet(self, user_id: int, email: str, username: str, operator_id: int, cursor) -> Optional[Dict]:
        """Create Aptos wallet for user"""
        try:
            logger.info(f"Creating Aptos wallet for user {user_id}")
            
            wallet_result = self.crossmint.create_user_wallet(
                user_id=user_id,
                email=email,
                username=username,
                operator_id=operator_id
            )
            
            if wallet_result['success']:
                # Update user with Aptos wallet details
                cursor.execute("""
                    UPDATE users 
                    SET aptos_wallet_address = ?, aptos_wallet_id = ?
                    WHERE id = ?
                """, (
                    wallet_result['wallet_address'],
                    wallet_result['wallet_id'],
                    user_id
                ))
                
                # Log wallet creation transaction
                cursor.execute("""
                    INSERT INTO aptos_transactions
                    (transaction_hash, transaction_type, to_address, user_id, operator_id, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    f"user_wallet_creation_{user_id}_{datetime.now().timestamp()}",
                    'wallet_creation',
                    wallet_result['wallet_address'],
                    user_id,
                    operator_id,
                    'confirmed'
                ))
                
                logger.info(f"✅ User Aptos wallet created: {wallet_result['wallet_address']}")
                return wallet_result
            else:
                logger.warning(f"⚠️ User Aptos wallet creation failed: {wallet_result.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating user Aptos wallet: {e}")
            return None
    
    # =============================================================================
    # WALLET OPERATIONS
    # =============================================================================
    
    def get_complete_operator_info(self, operator_id: int) -> Dict:
        """Get complete operator information including all wallets"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Get operator details
            cursor.execute("""
                SELECT * FROM sportsbook_operators WHERE id = ?
            """, (operator_id,))
            operator = cursor.fetchone()
            
            if not operator:
                return {'success': False, 'error': 'Operator not found'}
            
            # Get traditional wallets
            cursor.execute("""
                SELECT * FROM operator_wallets WHERE operator_id = ?
            """, (operator_id,))
            traditional_wallets = [dict(row) for row in cursor.fetchall()]
            
            # Get Aptos wallet balance if Web3 enabled
            aptos_balance = None
            if operator['web3_enabled'] and operator['aptos_wallet_address']:
                balance_result = self.crossmint.get_wallet_balance(
                    operator['aptos_wallet_address'], 
                    "APT"
                )
                if balance_result['success']:
                    aptos_balance = balance_result['balance']
            
            return {
                'success': True,
                'operator': dict(operator),
                'traditional_wallets': traditional_wallets,
                'aptos_balance': aptos_balance,
                'total_traditional_balance': sum(w['current_balance'] for w in traditional_wallets)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting operator info: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def get_complete_user_info(self, user_id: int) -> Dict:
        """Get complete user information including all balances"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Get user details
            cursor.execute("""
                SELECT u.*, so.sportsbook_name 
                FROM users u
                JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
                WHERE u.id = ?
            """, (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Get transaction history
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            transactions = [dict(row) for row in cursor.fetchall()]
            
            # Get Aptos wallet balance if Web3 enabled
            aptos_balance = None
            if user['web3_enabled'] and user['aptos_wallet_address']:
                balance_result = self.crossmint.get_wallet_balance(
                    user['aptos_wallet_address'], 
                    "APT"
                )
                if balance_result['success']:
                    aptos_balance = balance_result['balance']
            
            return {
                'success': True,
                'user': dict(user),
                'traditional_balance': user['balance'],
                'aptos_balance': aptos_balance,
                'recent_transactions': transactions
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting user info: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    # =============================================================================
    # BETTING OPERATIONS
    # =============================================================================
    
    def place_bet_complete(self, bet_data: Dict) -> Dict:
        """
        Place bet with support for both traditional and on-chain betting
        
        Args:
            bet_data: {
                'user_id': int,
                'match_id': str,
                'selection': str,
                'odds': float,
                'stake': float,
                'bet_type': str ('traditional' or 'aptos'),
                ... other bet fields
            }
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            logger.info(f"Placing bet for user {bet_data['user_id']}")
            
            # Get user info
            user_info = self.get_complete_user_info(bet_data['user_id'])
            if not user_info['success']:
                return user_info
            
            user = user_info['user']
            stake = bet_data['stake']
            
            # Check if this is on-chain betting
            is_on_chain = (bet_data.get('bet_type') == 'aptos' and 
                          user['web3_enabled'] and 
                          user['aptos_wallet_address'])
            
            if is_on_chain:
                return self._place_aptos_bet(bet_data, user, cursor, conn)
            else:
                return self._place_traditional_bet(bet_data, user, cursor, conn)
                
        except Exception as e:
            logger.error(f"❌ Error placing bet: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def _place_traditional_bet(self, bet_data: Dict, user: Dict, cursor, conn) -> Dict:
        """Place traditional off-chain bet"""
        stake = bet_data['stake']
        
        # Check traditional balance
        if user['balance'] < stake:
            return {'success': False, 'error': 'Insufficient traditional balance'}
        
        # Deduct from traditional balance
        new_balance = user['balance'] - stake
        cursor.execute("""
            UPDATE users SET balance = ? WHERE id = ?
        """, (new_balance, user['id']))
        
        # Create bet record
        cursor.execute("""
            INSERT INTO bets
            (user_id, match_id, selection, odds, stake, potential_return, 
             match_name, sport_name, sportsbook_operator_id, on_chain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user['id'],
            bet_data['match_id'],
            bet_data['selection'],
            bet_data['odds'],
            stake,
            stake * bet_data['odds'],
            bet_data.get('match_name', ''),
            bet_data.get('sport_name', ''),
            user['sportsbook_operator_id'],
            False  # Traditional bet
        ))
        
        bet_id = cursor.lastrowid
        
        # Create transaction record
        cursor.execute("""
            INSERT INTO transactions
            (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user['id'],
            bet_id,
            -stake,
            'bet',
            f"Bet placed - {bet_data['selection']}",
            user['balance'],
            new_balance
        ))
        
        conn.commit()
        
        return {
            'success': True,
            'bet_id': bet_id,
            'bet_type': 'traditional',
            'remaining_balance': new_balance,
            'potential_return': stake * bet_data['odds']
        }
    
    def _place_aptos_bet(self, bet_data: Dict, user: Dict, cursor, conn) -> Dict:
        """Place on-chain Aptos bet"""
        # For now, implement as traditional bet but with on_chain flag
        # In full implementation, this would interact with Aptos smart contracts
        
        stake = bet_data['stake']
        
        # Check traditional balance (for now)
        if user['balance'] < stake:
            return {'success': False, 'error': 'Insufficient balance for Aptos bet'}
        
        # Deduct from traditional balance
        new_balance = user['balance'] - stake
        cursor.execute("""
            UPDATE users SET balance = ? WHERE id = ?
        """, (new_balance, user['id']))
        
        # Create bet record with on-chain flag
        cursor.execute("""
            INSERT INTO bets
            (user_id, match_id, selection, odds, stake, potential_return, 
             match_name, sport_name, sportsbook_operator_id, on_chain, aptos_transaction_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user['id'],
            bet_data['match_id'],
            bet_data['selection'],
            bet_data['odds'],
            stake,
            stake * bet_data['odds'],
            bet_data.get('match_name', ''),
            bet_data.get('sport_name', ''),
            user['sportsbook_operator_id'],
            True,  # On-chain bet
            f"aptos_bet_{user['id']}_{datetime.now().timestamp()}"  # Mock transaction hash
        ))
        
        bet_id = cursor.lastrowid
        
        # Create transaction record
        cursor.execute("""
            INSERT INTO transactions
            (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user['id'],
            bet_id,
            -stake,
            'aptos_bet',
            f"Aptos bet placed - {bet_data['selection']}",
            user['balance'],
            new_balance
        ))
        
        conn.commit()
        
        return {
            'success': True,
            'bet_id': bet_id,
            'bet_type': 'aptos',
            'remaining_balance': new_balance,
            'potential_return': stake * bet_data['odds'],
            'on_chain': True
        }
