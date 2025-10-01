#!/usr/bin/env python3
"""
Aptos Registration Enhancement
Extends operator and user registration to include Aptos wallet creation via Crossmint
"""

import os
import json
import logging
from datetime import datetime
from flask import jsonify
from werkzeug.security import generate_password_hash

# Import our Crossmint Aptos service
from src.services.crossmint_aptos_service import CrossmintAptosService

logger = logging.getLogger(__name__)

def create_operator_with_aptos_wallet(operator_data, conn):
    """
    Create operator with traditional 4-wallet system + Aptos wallet
    
    Args:
        operator_data: Dict containing operator registration data
        conn: Database connection
        
    Returns:
        Dict containing operator details including Aptos wallet
    """
    try:
        logger.info(f"Creating operator with Aptos wallet: {operator_data['sportsbook_name']}")
        
        # First create traditional operator record (existing logic)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sportsbook_operators 
            (sportsbook_name, login, password_hash, email, subdomain, settings, 
             web3_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            operator_data['sportsbook_name'],
            operator_data['login'],
            operator_data['password_hash'],
            operator_data['email'],
            operator_data['subdomain'],
            operator_data['settings'],
            True,  # Enable Web3 for new operators
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        operator_id = cursor.lastrowid
        logger.info(f"Created operator record with ID: {operator_id}")
        
        # Create Aptos wallet via Crossmint
        crossmint = CrossmintAptosService()
        wallet_result = crossmint.create_operator_wallet(
            operator_id=operator_id,
            email=operator_data['email'],
            sportsbook_name=operator_data['sportsbook_name']
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
            
            logger.info(f"✅ Operator {operator_id} Aptos wallet created: {wallet_result['wallet_address']}")
            
            return {
                'success': True,
                'operator_id': operator_id,
                'aptos_wallet_address': wallet_result['wallet_address'],
                'aptos_wallet_id': wallet_result['wallet_id'],
                'web3_enabled': True
            }
        else:
            # Log error but don't fail registration - operator can use traditional system
            logger.warning(f"⚠️ Aptos wallet creation failed for operator {operator_id}: {wallet_result.get('message')}")
            
            return {
                'success': True,
                'operator_id': operator_id,
                'aptos_wallet_address': None,
                'aptos_wallet_id': None,
                'web3_enabled': False,
                'warning': 'Operator created but Aptos wallet creation failed'
            }
            
    except Exception as e:
        logger.error(f"❌ Error creating operator with Aptos wallet: {str(e)}")
        raise

def create_user_with_aptos_wallet(user_data, operator_id, conn):
    """
    Create user with traditional balance + optional Aptos wallet
    
    Args:
        user_data: Dict containing user registration data
        operator_id: ID of the sportsbook operator
        conn: Database connection
        
    Returns:
        Dict containing user details including Aptos wallet if created
    """
    try:
        logger.info(f"Creating user with Aptos wallet: {user_data['username']}")
        
        # First create traditional user record (existing logic)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users 
            (username, email, password_hash, balance, sportsbook_operator_id, 
             web3_enabled, is_active, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data['username'],
            user_data['email'],
            user_data['password_hash'],
            user_data.get('initial_balance', 1000.0),
            operator_id,
            user_data.get('create_aptos_wallet', False),  # Optional Web3 enablement
            True,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        user_id = cursor.lastrowid
        logger.info(f"Created user record with ID: {user_id}")
        
        # Create Aptos wallet if requested
        if user_data.get('create_aptos_wallet', False):
            crossmint = CrossmintAptosService()
            wallet_result = crossmint.create_user_wallet(
                user_id=user_id,
                email=user_data['email'],
                username=user_data['username'],
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
                
                logger.info(f"✅ User {user_id} Aptos wallet created: {wallet_result['wallet_address']}")
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'aptos_wallet_address': wallet_result['wallet_address'],
                    'aptos_wallet_id': wallet_result['wallet_id'],
                    'web3_enabled': True
                }
            else:
                # Log error but don't fail registration
                logger.warning(f"⚠️ Aptos wallet creation failed for user {user_id}: {wallet_result.get('message')}")
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'aptos_wallet_address': None,
                    'aptos_wallet_id': None,
                    'web3_enabled': False,
                    'warning': 'User created but Aptos wallet creation failed'
                }
        else:
            # User opted out of Web3 - traditional account only
            return {
                'success': True,
                'user_id': user_id,
                'aptos_wallet_address': None,
                'aptos_wallet_id': None,
                'web3_enabled': False
            }
            
    except Exception as e:
        logger.error(f"❌ Error creating user with Aptos wallet: {str(e)}")
        raise

def get_aptos_wallet_balance(wallet_address: str):
    """
    Get Aptos wallet balance via Crossmint
    
    Args:
        wallet_address: Aptos wallet address
        
    Returns:
        Dict containing balance information
    """
    try:
        crossmint = CrossmintAptosService()
        return crossmint.get_wallet_balance(wallet_address, "APT")
    except Exception as e:
        logger.error(f"❌ Error getting Aptos wallet balance: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def transfer_aptos_tokens(from_wallet: str, to_wallet: str, amount: str):
    """
    Transfer APT tokens between wallets
    
    Args:
        from_wallet: Source wallet address
        to_wallet: Destination wallet address
        amount: Amount to transfer in APT
        
    Returns:
        Dict containing transfer result
    """
    try:
        crossmint = CrossmintAptosService()
        return crossmint.transfer_tokens(from_wallet, to_wallet, amount, "APT")
    except Exception as e:
        logger.error(f"❌ Error transferring Aptos tokens: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
