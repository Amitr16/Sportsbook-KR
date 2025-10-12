"""
Aptos Web3 Wallet Service
Handles wallet creation, deposits, withdrawals, and balance queries
for custodial USDT on Aptos blockchain
"""

import os
import logging
from typing import Optional, Tuple
from aptos_sdk.account import Account
from aptos_sdk.client import RestClient
from aptos_sdk.transactions import EntryFunction, TransactionArgument, TransactionPayload
from aptos_sdk.bcs import Serializer

logger = logging.getLogger(__name__)


class AptosWalletService:
    """Service for managing Aptos custodial USDT wallets"""
    
    def __init__(self):
        """Initialize Aptos client and configuration"""
        # Aptos configuration from environment
        self.node_url = os.getenv("APTOS_NODE_URL", "https://fullnode.testnet.aptoslabs.com/v1")
        self.module_address = os.getenv(
            "APTOS_MODULE_ADDRESS", 
            "0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085"
        )
        self.admin_private_key = os.getenv("APTOS_ADMIN_PRIVATE_KEY")
        
        # Initialize REST client
        self.client = RestClient(self.node_url)
        
        # Initialize admin account if private key is provided
        self.admin_account = None
        if self.admin_private_key:
            try:
                self.admin_account = Account.load_key(self.admin_private_key)
                logger.info(f"✅ Aptos admin account loaded: {self.admin_account.address()}")
            except Exception as e:
                logger.error(f"❌ Failed to load Aptos admin account: {e}")
        else:
            logger.warning("⚠️ APTOS_ADMIN_PRIVATE_KEY not set - admin functions will not work")
    
    def create_wallet(self) -> Tuple[str, str]:
        """
        Create a new Aptos wallet
        
        Returns:
            Tuple[str, str]: (address, private_key)
        """
        try:
            # Generate new account
            account = Account.generate()
            
            address = str(account.address())
            private_key = account.private_key.hex()
            
            logger.info(f"✅ Created new Aptos wallet: {address}")
            return address, private_key
            
        except Exception as e:
            logger.error(f"❌ Failed to create Aptos wallet: {e}")
            raise
    
    def deposit(self, to_address: str, amount: float) -> Optional[str]:
        """
        Deposit USDT to a user's wallet (admin function)
        
        Args:
            to_address: Recipient's Aptos address
            amount: Amount in USDT (will be converted to u128)
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        if not self.admin_account:
            logger.error("❌ Admin account not initialized - cannot deposit")
            return None
        
        try:
            # Convert amount to u128 (assuming 2 decimal places for USDT)
            # For example: 100.50 USDT = 10050 in u128
            amount_u128 = int(amount * 100)
            
            logger.info(f"💸 Depositing {amount} USDT ({amount_u128} units) to {to_address}")
            
            # Build transaction payload
            payload = EntryFunction.natural(
                module=f"{self.module_address}::custodial_usdt",
                function="deposit",
                ty_args=[],
                args=[
                    TransactionArgument(to_address, Serializer.struct),
                    TransactionArgument(amount_u128, Serializer.u128),
                ]
            )
            
            # Submit transaction
            signed_transaction = self.client.create_bcs_signed_transaction(
                self.admin_account, TransactionPayload(payload)
            )
            tx_hash = self.client.submit_bcs_transaction(signed_transaction)
            
            # Wait for transaction
            self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"✅ Deposit successful - tx: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Deposit failed for {to_address}: {e}")
            return None
    
    def withdraw(self, user_address: str, amount: float) -> Optional[str]:
        """
        Withdraw USDT from a user's wallet (admin function - Kryzel pays gas)
        
        Args:
            user_address: User's Aptos address (no private key needed)
            amount: Amount in USDT to withdraw
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        if not self.admin_account:
            logger.error("❌ Admin account not initialized - cannot withdraw")
            return None
        
        try:
            amount_u128 = int(amount * 100)
            
            logger.info(f"💰 Admin withdrawing {amount} USDT from user {user_address} (Kryzel pays gas)")
            
            # Build transaction payload - admin calls withdraw_for_user
            payload = EntryFunction.natural(
                module=f"{self.module_address}::custodial_usdt",
                function="withdraw_for_user",
                ty_args=[],
                args=[
                    TransactionArgument(user_address, Serializer.struct),
                    TransactionArgument(amount_u128, Serializer.u128),
                ]
            )
            
            # Submit transaction using admin account (Kryzel pays gas)
            signed_transaction = self.client.create_bcs_signed_transaction(
                self.admin_account, TransactionPayload(payload)
            )
            tx_hash = self.client.submit_bcs_transaction(signed_transaction)
            
            # Wait for transaction
            self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"✅ Withdrawal successful - tx: {tx_hash} (gas paid by Kryzel)")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Withdrawal failed for {user_address}: {e}")
            return None
    
    def transfer(self, from_private_key: str, to_address: str, amount: float) -> Optional[str]:
        """
        Transfer USDT between wallets
        
        Args:
            from_private_key: Sender's private key (hex string)
            to_address: Recipient's Aptos address
            amount: Amount in USDT to transfer
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        try:
            # Load sender account
            sender_account = Account.load_key(from_private_key)
            amount_u128 = int(amount * 100)
            
            logger.info(f"🔄 Transferring {amount} USDT from {sender_account.address()} to {to_address}")
            
            # Build transaction payload
            payload = EntryFunction.natural(
                module=f"{self.module_address}::custodial_usdt",
                function="transfer",
                ty_args=[],
                args=[
                    TransactionArgument(to_address, Serializer.struct),
                    TransactionArgument(amount_u128, Serializer.u128),
                ]
            )
            
            # Submit transaction
            signed_transaction = self.client.create_bcs_signed_transaction(
                sender_account, TransactionPayload(payload)
            )
            tx_hash = self.client.submit_bcs_transaction(signed_transaction)
            
            # Wait for transaction
            self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"✅ Transfer successful - tx: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Transfer failed: {e}")
            return None
    
    def get_balance(self, address: str) -> Optional[float]:
        """
        Get USDT balance for an address
        
        Args:
            address: Aptos address to query
        
        Returns:
            Optional[float]: Balance in USDT, None if query fails
        """
        try:
            # Call balance_of view function
            result = self.client.view_function(
                module=f"{self.module_address}::custodial_usdt",
                function="balance_of",
                type_arguments=[],
                arguments=[address]
            )
            
            if result and len(result) > 0:
                # Convert u128 back to USDT (divide by 100)
                balance_u128 = int(result[0])
                balance = balance_u128 / 100.0
                logger.info(f"💵 Balance for {address}: {balance} USDT")
                return balance
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Failed to get balance for {address}: {e}")
            return None
    
    def admin_reset_one(self, user_address: str, new_amount: float) -> Optional[str]:
        """
        Admin function to reset a single user's balance
        
        Args:
            user_address: User's Aptos address
            new_amount: New balance in USDT
        
        Returns:
            Optional[str]: Transaction hash if successful, None otherwise
        """
        if not self.admin_account:
            logger.error("❌ Admin account not initialized - cannot reset balance")
            return None
        
        try:
            amount_u128 = int(new_amount * 100)
            
            logger.info(f"🧹 Admin resetting {user_address} balance to {new_amount} USDT")
            
            # Build transaction payload
            payload = EntryFunction.natural(
                module=f"{self.module_address}::custodial_usdt",
                function="admin_reset_one",
                ty_args=[],
                args=[
                    TransactionArgument(user_address, Serializer.struct),
                    TransactionArgument(amount_u128, Serializer.u128),
                ]
            )
            
            # Submit transaction
            signed_transaction = self.client.create_bcs_signed_transaction(
                self.admin_account, TransactionPayload(payload)
            )
            tx_hash = self.client.submit_bcs_transaction(signed_transaction)
            
            # Wait for transaction
            self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"✅ Balance reset successful - tx: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Balance reset failed for {user_address}: {e}")
            return None


# Global instance
_aptos_service = None


def get_aptos_service() -> AptosWalletService:
    """Get or create global Aptos wallet service instance"""
    global _aptos_service
    if _aptos_service is None:
        _aptos_service = AptosWalletService()
    return _aptos_service

