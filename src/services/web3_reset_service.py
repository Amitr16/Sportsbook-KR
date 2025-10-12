"""
Web3 Wallet Reset Service

This service handles resetting all Web3 wallets to a specified balance amount.
It's used by the admin reset contest functionality.
"""

import logging
from typing import Optional, Dict, Any
from src.db_compat import connection_ctx

logger = logging.getLogger(__name__)


def reset_all_web3_wallets(new_balance: float) -> Dict[str, Any]:
    """
    Reset all Web3 wallets to the specified balance amount.
    
    Args:
        new_balance: The new balance amount to set for all wallets
        
    Returns:
        Dict containing reset statistics and any errors
    """
    logger.info(f"🔄 WEB3 RESET: Starting Web3 wallet reset to {new_balance} USDT")
    
    stats = {
        'wallets_reset': 0,
        'wallets_failed': 0,
        'errors': []
    }
    
    try:
        # Get all users with Web3 wallets
        with connection_ctx() as conn:
            cursor = conn.cursor()
            
            # Get all users that have Web3 wallet addresses
            cursor.execute("""
                SELECT id, username, web3_wallet_address, web3_wallet_key
                FROM users 
                WHERE web3_wallet_address IS NOT NULL 
                AND web3_wallet_key IS NOT NULL
            """)
            users_with_wallets = cursor.fetchall()
            
            logger.info(f"🔄 WEB3 RESET: Found {len(users_with_wallets)} users with Web3 wallets")
            
            if not users_with_wallets:
                logger.info("ℹ️ WEB3 RESET: No users with Web3 wallets found")
                return stats
            
            # Import the Crossmint service
            from src.services.crossmint_aptos_service import get_crossmint_service
            crossmint_service = get_crossmint_service()
            
            # Reset each wallet
            for user in users_with_wallets:
                user_id = user['id']
                username = user['username']
                wallet_address = user['web3_wallet_address']
                wallet_key = user['web3_wallet_key']
                
                try:
                    logger.info(f"🔄 WEB3 RESET: Resetting wallet for user {username} ({user_id})")
                    
                    # Get current balance to calculate difference
                    current_balance = crossmint_service.get_balance(wallet_address)
                    balance_diff = new_balance - current_balance
                    
                    logger.info(f"🔄 WEB3 RESET: User {username} current: {current_balance} USDT, target: {new_balance} USDT, diff: {balance_diff}")
                    
                    if abs(balance_diff) < 0.01:  # Skip if difference is negligible
                        logger.info(f"ℹ️ WEB3 RESET: User {username} already has correct balance, skipping")
                        stats['wallets_reset'] += 1
                        continue
                    
                    # Reset wallet to new balance
                    tx_hash = None
                    if balance_diff > 0:
                        # Need to deposit more USDT via Crossmint
                        from src.services.crossmint_aptos_service import get_crossmint_service
                        crossmint_service = get_crossmint_service()
                        tx_hash = crossmint_service.deposit(wallet_address, balance_diff)
                        logger.info(f"✅ WEB3 RESET: Deposited {balance_diff} USDT to {username} - tx: {tx_hash}")
                    else:
                        # Need to withdraw USDT via Crossmint (gasless transactions)
                        from src.services.crossmint_aptos_service import get_crossmint_service
                        crossmint_service = get_crossmint_service()
                        tx_hash = crossmint_service.withdraw(wallet_address, abs(balance_diff))
                        logger.info(f"✅ WEB3 RESET: Withdrew {abs(balance_diff)} USDT from {username} - tx: {tx_hash}")
                    
                    if tx_hash:
                        stats['wallets_reset'] += 1
                        logger.info(f"✅ WEB3 RESET: Successfully reset {username}'s wallet to {new_balance} USDT")
                    else:
                        stats['wallets_failed'] += 1
                        error_msg = f"Failed to reset wallet for {username}: No transaction hash returned"
                        logger.error(f"❌ WEB3 RESET: {error_msg}")
                        stats['errors'].append(error_msg)
                        
                except Exception as wallet_error:
                    stats['wallets_failed'] += 1
                    error_msg = f"Failed to reset wallet for {username}: {str(wallet_error)}"
                    logger.error(f"❌ WEB3 RESET: {error_msg}")
                    stats['errors'].append(error_msg)
                    continue
            
            logger.info(f"✅ WEB3 RESET: Completed! Reset {stats['wallets_reset']} wallets, {stats['wallets_failed']} failed")
            
    except Exception as e:
        error_msg = f"Web3 reset service error: {str(e)}"
        logger.error(f"❌ WEB3 RESET: {error_msg}")
        stats['errors'].append(error_msg)
    
    return stats


def reset_web3_wallet_for_user(user_id: int, new_balance: float) -> Dict[str, Any]:
    """
    Reset a specific user's Web3 wallet to the specified balance.
    
    Args:
        user_id: The user ID whose wallet to reset
        new_balance: The new balance amount to set
        
    Returns:
        Dict containing success status and transaction details
    """
    logger.info(f"🔄 WEB3 RESET: Resetting wallet for user {user_id} to {new_balance} USDT")
    
    try:
        with connection_ctx() as conn:
            cursor = conn.cursor()
            
            # Get user's Web3 wallet info
            cursor.execute("""
                SELECT id, username, web3_wallet_address, web3_wallet_key
                FROM users 
                WHERE id = %s AND web3_wallet_address IS NOT NULL AND web3_wallet_key IS NOT NULL
            """, (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return {
                    'success': False,
                    'error': f'User {user_id} has no Web3 wallet or wallet info missing'
                }
            
            # Import the Crossmint service
            from src.services.crossmint_aptos_service import get_crossmint_service
            crossmint_service = get_crossmint_service()
            
            # Get current balance and calculate difference
            current_balance = crossmint_service.get_balance(user['web3_wallet_address'])
            balance_diff = new_balance - current_balance
            
            logger.info(f"🔄 WEB3 RESET: User {user['username']} current: {current_balance} USDT, target: {new_balance} USDT, diff: {balance_diff}")
            
            if abs(balance_diff) < 0.01:  # Skip if difference is negligible
                return {
                    'success': True,
                    'message': f"User {user['username']} already has correct balance",
                    'tx_hash': None,
                    'balance_change': 0
                }
            
            # Reset wallet to new balance
            tx_hash = None
            if balance_diff > 0:
                # Need to deposit more USDT via Crossmint
                from src.services.crossmint_aptos_service import get_crossmint_service
                crossmint_service = get_crossmint_service()
                tx_hash = crossmint_service.deposit(user['web3_wallet_address'], balance_diff)
                logger.info(f"✅ WEB3 RESET: Deposited {balance_diff} USDT to {user['username']} - tx: {tx_hash}")
            else:
                # Need to withdraw USDT via Crossmint (gasless transactions)
                from src.services.crossmint_aptos_service import get_crossmint_service
                crossmint_service = get_crossmint_service()
                tx_hash = crossmint_service.withdraw(user['web3_wallet_address'], abs(balance_diff))
                logger.info(f"✅ WEB3 RESET: Withdrew {abs(balance_diff)} USDT from {user['username']} - tx: {tx_hash}")
            
            return {
                'success': True,
                'message': f"Successfully reset {user['username']}'s wallet to {new_balance} USDT",
                'tx_hash': tx_hash,
                'balance_change': balance_diff,
                'previous_balance': current_balance,
                'new_balance': new_balance
            }
            
    except Exception as e:
        error_msg = f"Failed to reset wallet for user {user_id}: {str(e)}"
        logger.error(f"❌ WEB3 RESET: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
