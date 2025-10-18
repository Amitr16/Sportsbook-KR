"""
Web3 Wallet Sync Service
Synchronizes Web2 database operations with Web3 (Aptos) blockchain wallet operations
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def sync_web3_debit(user_id: int, amount: float, description: str = "debit") -> Optional[str]:
    """
    Debit (withdraw) from user's Web3 wallet after Web2 debit
    
    Args:
        user_id: User ID from database
        amount: Amount to debit (in USDT)
        description: Description of the transaction
    
    Returns:
        Optional[str]: Transaction hash if successful, None if failed/skipped
    """
    try:
        # Get user's web3 wallet credentials from database
        from src.db_compat import connection_ctx
        
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT web3_wallet_address, web3_wallet_key FROM users WHERE id = %s",
                    (user_id,)
                )
                user_wallet = cursor.fetchone()
        
        if not user_wallet or not user_wallet['web3_wallet_key']:
            logger.warning(f"User {user_id} has no Web3 wallet - skipping Web3 debit")
            return None
        
        # Debit from Web3 wallet via Crossmint (gasless transactions)
        from src.services.crossmint_aptos_service import get_crossmint_service
        crossmint_service = get_crossmint_service()
        tx_hash = crossmint_service.withdraw(
            user_address=user_wallet['web3_wallet_address'],
            amount=amount
        )
        
        if tx_hash:
            logger.info(f"Web3 debit successful for user {user_id}: -{amount} USDT (tx: {tx_hash}) - {description}")
        else:
            logger.warning(f"Web3 debit failed for user {user_id}: -{amount} USDT - {description}")
        
        return tx_hash
        
    except Exception as e:
        logger.error(f"Web3 debit error for user {user_id}: {e}")
        # Don't raise - allow Web2 transaction to complete even if Web3 fails
        return None


def sync_web3_credit(user_id: int, amount: float, description: str = "credit") -> Optional[str]:
    """
    Credit (deposit) to user's Web3 wallet after Web2 credit
    
    Args:
        user_id: User ID from database
        amount: Amount to credit (in USDT)
        description: Description of the transaction
    
    Returns:
        Optional[str]: Transaction hash if successful, None if failed/skipped
    """
    try:
        # Get user's web3 wallet address from database
        from src.db_compat import connection_ctx
        
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT web3_wallet_address, web3_wallet_key FROM users WHERE id = %s",
                    (user_id,)
                )
                user_wallet = cursor.fetchone()
        
        if not user_wallet or not user_wallet['web3_wallet_address']:
            logger.warning(f"User {user_id} has no Web3 wallet - skipping Web3 credit")
            return None
        
        # Credit to Web3 wallet via Crossmint (gasless transactions)
        from src.services.crossmint_aptos_service import get_crossmint_service
        crossmint_service = get_crossmint_service()
        tx_hash = crossmint_service.deposit(
            to_address=user_wallet['web3_wallet_address'],
            amount=amount
        )
        
        if tx_hash:
            logger.info(f"Web3 credit successful for user {user_id}: +{amount} USDT (tx: {tx_hash}) - {description}")
        else:
            logger.warning(f"Web3 credit failed for user {user_id}: +{amount} USDT - {description}")
        
        return tx_hash
        
    except Exception as e:
        logger.error(f"Web3 credit error for user {user_id}: {e}")
        # Don't raise - allow Web2 transaction to complete even if Web3 fails
        return None


def get_web3_balance(user_id: int) -> Optional[float]:
    """
    Get user's Web3 wallet balance from blockchain
    
    Args:
        user_id: User ID from database
    
    Returns:
        Optional[float]: Balance in USDT, None if failed/not found
    """
    try:
        from src.db_compat import connection_ctx
        
        with connection_ctx() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT web3_wallet_address FROM users WHERE id = %s",
                    (user_id,)
                )
                user_wallet = cursor.fetchone()
        
        if not user_wallet or not user_wallet['web3_wallet_address']:
            logger.warning(f"User {user_id} has no Web3 wallet")
            return None
        
        from src.services.crossmint_aptos_service import get_crossmint_service
        crossmint_service = get_crossmint_service()
        balance = crossmint_service.get_balance(user_wallet['web3_wallet_address'])
        
        return balance
        
    except Exception as e:
        logger.error(f"Web3 balance query error for user {user_id}: {e}")
        return None

