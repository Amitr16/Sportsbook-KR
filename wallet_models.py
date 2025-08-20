"""
Wallet Revenue Architecture Database Models
Based on the 4-wallet system described in the PDF
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import json

# Assuming db is imported from the main models
# from src.models.multitenant_models import db

class WalletType(Enum):
    """Wallet types as defined in the architecture"""
    BOOKMAKER_CAPITAL = "bookmaker_capital"  # Wallet 1 - Bookie's own capital
    LIQUIDITY_POOL = "liquidity_pool"        # Wallet 2 - LP allocation
    REVENUE = "revenue"                      # Wallet 3 - All betting PnL flows here
    BOOKMAKER_EARNINGS = "bookmaker_earnings" # Wallet 4 - Bookie's personal earnings

class OperatorWallet(db.Model):
    """
    Four wallets per operator as per the architecture:
    - Wallet 1: Bookmaker's Capital ($10,000 default)
    - Wallet 2: Liquidity Pool Allocation ($40,000 default with 5x leverage)
    - Wallet 3: Revenue Wallet (All betting PnL flows here)
    - Wallet 4: Bookmaker's Revenue Wallet (Personal earnings)
    """
    __tablename__ = 'operator_wallets'
    
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=False)
    wallet_type = db.Column(db.Enum(WalletType), nullable=False)
    current_balance = db.Column(db.Float, default=0.0, nullable=False)
    initial_balance = db.Column(db.Float, default=0.0, nullable=False)
    leverage_multiplier = db.Column(db.Float, default=1.0)  # 5x for liquidity pool
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    daily_balances = db.relationship('WalletDailyBalance', backref='wallet', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('WalletTransaction', backref='wallet', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint: one wallet per type per operator
    __table_args__ = (
        db.UniqueConstraint('operator_id', 'wallet_type', name='unique_operator_wallet_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'operator_id': self.operator_id,
            'wallet_type': self.wallet_type.value,
            'current_balance': self.current_balance,
            'initial_balance': self.initial_balance,
            'leverage_multiplier': self.leverage_multiplier,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class WalletDailyBalance(db.Model):
    """
    Daily balance records for each wallet
    Creates a new record every day for tracking balance history
    """
    __tablename__ = 'wallet_daily_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('operator_wallets.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    opening_balance = db.Column(db.Float, nullable=False)
    closing_balance = db.Column(db.Float, nullable=False)
    daily_pnl = db.Column(db.Float, default=0.0)  # Profit/Loss for the day
    total_revenue = db.Column(db.Float, default=0.0)  # Total revenue generated
    total_bets_amount = db.Column(db.Float, default=0.0)  # Total betting volume
    total_payouts = db.Column(db.Float, default=0.0)  # Total payouts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one record per wallet per date
    __table_args__ = (
        db.UniqueConstraint('wallet_id', 'date', name='unique_wallet_daily_balance'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'wallet_id': self.wallet_id,
            'date': self.date.isoformat() if self.date else None,
            'opening_balance': self.opening_balance,
            'closing_balance': self.closing_balance,
            'daily_pnl': self.daily_pnl,
            'total_revenue': self.total_revenue,
            'total_bets_amount': self.total_bets_amount,
            'total_payouts': self.total_payouts,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class WalletTransaction(db.Model):
    """
    Transaction history for wallet operations
    Records all movements between wallets and revenue distributions
    """
    __tablename__ = 'wallet_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('operator_wallets.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'revenue_distribution', 'loss_allocation', 'initial_funding', etc.
    amount = db.Column(db.Float, nullable=False)  # Positive for credits, negative for debits
    balance_before = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500))
    reference_id = db.Column(db.String(100))  # Reference to bet, settlement, etc.
    metadata = db.Column(db.Text)  # JSON field for additional data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'wallet_id': self.wallet_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'description': self.description,
            'reference_id': self.reference_id,
            'metadata': json.loads(self.metadata) if self.metadata else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class RevenueCalculation(db.Model):
    """
    Daily revenue calculation records
    Stores the results of end-of-day revenue calculations
    """
    __tablename__ = 'revenue_calculations'
    
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=False)
    calculation_date = db.Column(db.Date, nullable=False)
    total_revenue = db.Column(db.Float, default=0.0)  # Total daily revenue (positive) or loss (negative)
    total_bets_amount = db.Column(db.Float, default=0.0)
    total_payouts = db.Column(db.Float, default=0.0)
    
    # Revenue distribution (when profit)
    bookmaker_own_share = db.Column(db.Float, default=0.0)  # 20% of profit
    kryzel_fee_from_own = db.Column(db.Float, default=0.0)  # 10% of bookmaker's own share
    bookmaker_net_own = db.Column(db.Float, default=0.0)   # 90% of bookmaker's own share
    
    remaining_profit = db.Column(db.Float, default=0.0)     # 80% of total profit
    bookmaker_share_60 = db.Column(db.Float, default=0.0)   # 60% of remaining to bookmaker
    community_share_30 = db.Column(db.Float, default=0.0)   # 30% of remaining to community
    kryzel_share_10 = db.Column(db.Float, default=0.0)      # 10% of remaining to Kryzel
    
    # Loss distribution (when loss)
    bookmaker_own_loss = db.Column(db.Float, default=0.0)   # 20% of loss from own capital
    remaining_loss = db.Column(db.Float, default=0.0)       # 80% of loss
    bookmaker_loss_70 = db.Column(db.Float, default=0.0)    # 70% of remaining loss
    community_loss_30 = db.Column(db.Float, default=0.0)    # 30% of remaining loss
    
    # Final amounts transferred to Wallet 4 (Bookmaker's earnings)
    total_bookmaker_earnings = db.Column(db.Float, default=0.0)
    
    calculation_metadata = db.Column(db.Text)  # JSON field for detailed calculation data
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one calculation per operator per date
    __table_args__ = (
        db.UniqueConstraint('operator_id', 'calculation_date', name='unique_operator_daily_calculation'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'operator_id': self.operator_id,
            'calculation_date': self.calculation_date.isoformat() if self.calculation_date else None,
            'total_revenue': self.total_revenue,
            'total_bets_amount': self.total_bets_amount,
            'total_payouts': self.total_payouts,
            'bookmaker_own_share': self.bookmaker_own_share,
            'kryzel_fee_from_own': self.kryzel_fee_from_own,
            'bookmaker_net_own': self.bookmaker_net_own,
            'remaining_profit': self.remaining_profit,
            'bookmaker_share_60': self.bookmaker_share_60,
            'community_share_30': self.community_share_30,
            'kryzel_share_10': self.kryzel_share_10,
            'bookmaker_own_loss': self.bookmaker_own_loss,
            'remaining_loss': self.remaining_loss,
            'bookmaker_loss_70': self.bookmaker_loss_70,
            'community_loss_30': self.community_loss_30,
            'total_bookmaker_earnings': self.total_bookmaker_earnings,
            'calculation_metadata': json.loads(self.calculation_metadata) if self.calculation_metadata else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

# Helper functions for wallet operations

def create_operator_wallets(operator_id, db_session):
    """
    Create the 4 wallets for a new operator
    Called during sportsbook registration
    """
    wallets = []
    
    # Wallet 1: Bookmaker's Capital - $10,000 default
    wallet1 = OperatorWallet(
        operator_id=operator_id,
        wallet_type=WalletType.BOOKMAKER_CAPITAL,
        current_balance=10000.0,
        initial_balance=10000.0,
        leverage_multiplier=1.0
    )
    wallets.append(wallet1)
    
    # Wallet 2: Liquidity Pool Allocation - $40,000 default (5x leverage)
    wallet2 = OperatorWallet(
        operator_id=operator_id,
        wallet_type=WalletType.LIQUIDITY_POOL,
        current_balance=40000.0,
        initial_balance=40000.0,
        leverage_multiplier=5.0
    )
    wallets.append(wallet2)
    
    # Wallet 3: Revenue Wallet - starts at $0
    wallet3 = OperatorWallet(
        operator_id=operator_id,
        wallet_type=WalletType.REVENUE,
        current_balance=0.0,
        initial_balance=0.0,
        leverage_multiplier=1.0
    )
    wallets.append(wallet3)
    
    # Wallet 4: Bookmaker's Earnings - starts at $0
    wallet4 = OperatorWallet(
        operator_id=operator_id,
        wallet_type=WalletType.BOOKMAKER_EARNINGS,
        current_balance=0.0,
        initial_balance=0.0,
        leverage_multiplier=1.0
    )
    wallets.append(wallet4)
    
    # Add all wallets to session
    for wallet in wallets:
        db_session.add(wallet)
    
    return wallets

def get_operator_wallets(operator_id):
    """Get all wallets for an operator"""
    return OperatorWallet.query.filter_by(operator_id=operator_id).all()

def get_wallet_by_type(operator_id, wallet_type):
    """Get a specific wallet by type for an operator"""
    return OperatorWallet.query.filter_by(
        operator_id=operator_id, 
        wallet_type=wallet_type
    ).first()

def record_wallet_transaction(wallet, transaction_type, amount, description, reference_id=None, metadata=None):
    """Record a wallet transaction"""
    balance_before = wallet.current_balance
    wallet.current_balance += amount
    balance_after = wallet.current_balance
    
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        description=description,
        reference_id=reference_id,
        metadata=json.dumps(metadata) if metadata else None
    )
    
    return transaction

