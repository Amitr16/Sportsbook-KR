"""
Database models for sports betting platform
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import json

db = SQLAlchemy()

class BetStatus(Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    VOID = "void"
    CASHED_OUT = "cashed_out"

class BetType(Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    SYSTEM = "system"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Multi-tenant support
    sportsbook_operator_id = db.Column(db.Integer, nullable=True)  # Foreign key to sportsbook_operators
    
    # Relationships
    bets = db.relationship('Bet', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'balance': self.balance,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'sportsbook_operator_id': self.sportsbook_operator_id
        }

class Bet(db.Model):
    __tablename__ = 'bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Multi-tenant support
    sportsbook_operator_id = db.Column(db.Integer, nullable=True)  # Foreign key to sportsbook_operators
    
    # Simplified fields for frontend compatibility
    match_id = db.Column(db.String(50))  # Match identifier
    match_name = db.Column(db.String(200))  # e.g., "Team A vs Team B"
    selection = db.Column(db.String(100))  # e.g., "Team A", "Over 2.5"
    bet_selection = db.Column(db.String(100))  # Alias for selection
    
    # Sport information - stored at betting time for reliable settlement
    sport_name = db.Column(db.String(50))  # e.g., "baseball", "soccer", "tennis"
    
    # Market information - for admin liability calculation
    market = db.Column(db.String(50))  # Market ID for admin liability calculation
    
    # Bet details
    stake = db.Column(db.Float, nullable=False)
    odds = db.Column(db.Float, nullable=False)  # Odds at time of bet placement
    potential_return = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # Simplified status
    bet_type = db.Column(db.String(20), default='single')  # Simplified type (single/combo)
    bet_timing = db.Column(db.String(20), default='pregame')  # pregame/ingame
    
    # Admin control
    is_active = db.Column(db.Boolean, default=True)  # Can be disabled by admin
    
    # Settlement
    actual_return = db.Column(db.Float, default=0.0)
    settled_at = db.Column(db.DateTime)
    
    # Combo bet fields
    combo_selections = db.Column(db.Text)  # JSON string for combo bet selections
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'match_id': self.match_id,
            'match_name': self.match_name,
            'selection': self.selection,
            'bet_selection': self.bet_selection,
            'sport_name': self.sport_name,
            'stake': self.stake,
            'odds': self.odds,
            'potential_return': self.potential_return,
            'status': self.status,
            'bet_type': self.bet_type,
            'bet_timing': self.bet_timing,
            'is_active': self.is_active,
            'actual_return': self.actual_return,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'combo_selections': json.loads(self.combo_selections) if self.combo_selections else None
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bet_id = db.Column(db.Integer, db.ForeignKey('bets.id'), nullable=True)  # Null for deposits/withdrawals
    
    # Transaction details
    amount = db.Column(db.Float, nullable=False)  # Positive for credits, negative for debits
    transaction_type = db.Column(db.String(20), nullable=False)  # bet, win, deposit, withdrawal
    description = db.Column(db.String(200))
    balance_before = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'bet_id': self.bet_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

