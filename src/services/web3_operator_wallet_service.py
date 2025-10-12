"""
Web3 Operator Wallet Service
Manages Web3 wallet addresses for operators and handles parallel Web3 operations
"""

import logging
from typing import Dict, List, Optional, Tuple
from src.db_compat import connection_ctx
from src.services.crossmint_aptos_service import get_crossmint_service

logger = logging.getLogger(__name__)

def get_operator_web3_wallets(operator_id: int) -> Dict[str, str]:
    """
    Get Web3 wallet addresses for an operator's 4 wallets.
    Returns dict with wallet_type -> wallet_address mapping.
    """
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT wallet_type, web3_wallet_address 
                    FROM operator_wallets 
                    WHERE operator_id = %s AND web3_wallet_address IS NOT NULL
                """, (operator_id,))
                
                wallets = cursor.fetchall()
                return {wallet['wallet_type']: wallet['web3_wallet_address'] for wallet in wallets}
    except Exception as e:
        logger.error(f"Failed to get Web3 wallets for operator {operator_id}: {e}")
        return {}

def store_operator_web3_wallet(operator_id: int, wallet_type: str, web3_address: str, web3_key: str) -> bool:
    """
    Store Web3 wallet address and key for an operator wallet.
    """
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE operator_wallets 
                    SET web3_wallet_address = %s, web3_wallet_key = %s
                    WHERE operator_id = %s AND wallet_type = %s
                """, (web3_address, web3_key, operator_id, wallet_type))
                
                conn.commit()
                logger.info(f"✅ Stored Web3 wallet for operator {operator_id}, {wallet_type}: {web3_address}")
                return True
    except Exception as e:
        logger.error(f"Failed to store Web3 wallet for operator {operator_id}, {wallet_type}: {e}")
        return False

def sync_web3_operator_wallet_debit(operator_id: int, wallet_type: str, amount: float, description: str) -> Optional[str]:
    """
    Debit (withdraw) from a Web3 operator wallet.
    """
    try:
        wallets = get_operator_web3_wallets(operator_id)
        if wallet_type not in wallets:
            logger.warning(f"No Web3 wallet found for operator {operator_id}, type {wallet_type}")
            return None
            
        wallet_address = wallets[wallet_type]
        
        # Perform Web3 withdrawal via Crossmint (gasless transactions)
        crossmint_service = get_crossmint_service()
        tx_hash = crossmint_service.withdraw(user_address=wallet_address, amount=amount)
        
        if tx_hash:
            logger.info(f"✅ Web3 debit: {amount} USDT from {wallet_type} (operator {operator_id}) - tx: {tx_hash}")
            return tx_hash
        else:
            logger.warning(f"⚠️ Web3 debit failed for {wallet_type} (operator {operator_id})")
            return None
            
    except Exception as e:
        logger.error(f"Web3 debit failed for operator {operator_id}, {wallet_type}: {e}")
        return None

def sync_web3_operator_wallet_credit(operator_id: int, wallet_type: str, amount: float, description: str) -> Optional[str]:
    """
    Credit (deposit) to a Web3 operator wallet.
    """
    try:
        wallets = get_operator_web3_wallets(operator_id)
        if wallet_type not in wallets:
            logger.warning(f"No Web3 wallet found for operator {operator_id}, type {wallet_type}")
            return None
            
        wallet_address = wallets[wallet_type]
        
        # Perform Web3 deposit via Crossmint (gasless transactions)
        crossmint_service = get_crossmint_service()
        tx_hash = crossmint_service.deposit(to_address=wallet_address, amount=amount)
        
        if tx_hash:
            logger.info(f"✅ Web3 credit: {amount} USDT to {wallet_type} (operator {operator_id}) - tx: {tx_hash}")
            return tx_hash
        else:
            logger.warning(f"⚠️ Web3 credit failed for {wallet_type} (operator {operator_id})")
            return None
            
    except Exception as e:
        logger.error(f"Web3 credit failed for operator {operator_id}, {wallet_type}: {e}")
        return None

def create_web3_revenue_calculation(operator_id: int, calculation_date: str, bookmaker_share: float, community_share: float) -> bool:
    """
    Create a Web3 revenue calculation record (parallel to Web2 revenue_calculations).
    For now, we'll store this in the same table with a 'web3_' prefix in metadata.
    """
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO revenue_calculations 
                    (operator_id, calculation_date, bookmaker_own_share, community_share_30, 
                     kryzel_fee_from_own, remaining_profit, calculation_metadata, processed_at)
                    VALUES (%s, %s, %s, %s, 0, 0, 'web3_false', NOW())
                """, (operator_id, calculation_date, bookmaker_share, community_share))
                
                conn.commit()
                logger.info(f"✅ Created Web3 revenue calculation for operator {operator_id}")
                return True
    except Exception as e:
        logger.error(f"Failed to create Web3 revenue calculation for operator {operator_id}: {e}")
        return False

def get_unprocessed_web3_revenue_calculations() -> List[Dict]:
    """
    Get all Web3 revenue calculation entries that haven't been processed yet.
    """
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        rc.id,
                        rc.operator_id,
                        rc.calculation_date,
                        rc.bookmaker_own_share,
                        rc.community_share_30,
                        so.sportsbook_name
                    FROM revenue_calculations rc
                    JOIN sportsbook_operators so ON rc.operator_id = so.id
                    WHERE rc.calculation_metadata = 'web3_false'
                    ORDER BY rc.calculation_date ASC, rc.processed_at ASC
                """)
                
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get unprocessed Web3 revenue calculations: {e}")
        return []

def mark_web3_revenue_calculation_processed(calc_id: int) -> bool:
    """
    Mark a Web3 revenue calculation as processed.
    """
    try:
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE revenue_calculations 
                    SET calculation_metadata = 'web3_true'
                    WHERE id = %s
                """, (calc_id,))
                
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"Failed to mark Web3 revenue calculation {calc_id} as processed: {e}")
        return False
