"""
Updated database models for multi-tenant sports betting platform
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

class SportsbookOperator(db.Model):
    """Sportsbook operators (admins) who run their own betting sites"""
    __tablename__ = 'sportsbook_operators'
    
    id = db.Column(db.Integer, primary_key=True)
    sportsbook_name = db.Column(db.String(100), unique=True, nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120))
    subdomain = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    total_revenue = db.Column(db.Float, default=0.0)
    commission_rate = db.Column(db.Float, default=0.05)
    settings = db.Column(db.Text)  # JSON field for operator-specific settings
    
    # Relationships
    users = db.relationship('User', backref='sportsbook_operator', lazy=True)
    bets = db.relationship('Bet', backref='sportsbook_operator', lazy=True)
    transactions = db.relationship('Transaction', backref='sportsbook_operator', lazy=True)
    bet_slips = db.relationship('BetSlip', backref='sportsbook_operator', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sportsbook_name': self.sportsbook_name,
            'login': self.login,
            'email': self.email,
            'subdomain': self.subdomain,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'total_revenue': self.total_revenue,
            'commission_rate': self.commission_rate,
            'settings': json.loads(self.settings) if self.settings else {}
        }
    
    def get_settings(self):
        """Get operator settings as dictionary"""
        return json.loads(self.settings) if self.settings else {}
    
    def set_settings(self, settings_dict):
        """Set operator settings from dictionary"""
        self.settings = json.dumps(settings_dict)

class SuperAdmin(db.Model):
    """Super administrators with global access"""
    __tablename__ = 'super_admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    permissions = db.Column(db.Text)  # JSON field for granular permissions
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'permissions': json.loads(self.permissions) if self.permissions else {}
        }
    
    def get_permissions(self):
        """Get permissions as dictionary"""
        return json.loads(self.permissions) if self.permissions else {}
    
    def set_permissions(self, permissions_dict):
        """Set permissions from dictionary"""
        self.permissions = json.dumps(permissions_dict)

class User(db.Model):
    """Updated User model with multi-tenant support"""
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
    sportsbook_operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=True)
    
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
    """Updated Bet model with multi-tenant support"""
    __tablename__ = 'bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Multi-tenant support
    sportsbook_operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=True)
    
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
            'sportsbook_operator_id': self.sportsbook_operator_id,
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
    """Updated Transaction model with multi-tenant support"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bet_id = db.Column(db.Integer, db.ForeignKey('bets.id'), nullable=True)  # Null for deposits/withdrawals
    
    # Multi-tenant support
    sportsbook_operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=True)
    
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
            'sportsbook_operator_id': self.sportsbook_operator_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BetSlip(db.Model):
    """Updated BetSlip model with multi-tenant support"""
    __tablename__ = 'bet_slips'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Multi-tenant support
    sportsbook_operator_id = db.Column(db.Integer, db.ForeignKey('sportsbook_operators.id'), nullable=True)
    
    total_stake = db.Column(db.Float, nullable=False)
    total_odds = db.Column(db.Float, nullable=False)
    potential_return = db.Column(db.Float, nullable=False)
    bet_type = db.Column(db.String(8))  # single, multiple
    status = db.Column(db.String(10))  # pending, won, lost, void
    actual_return = db.Column(db.Float)
    settled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sportsbook_operator_id': self.sportsbook_operator_id,
            'total_stake': self.total_stake,
            'total_odds': self.total_odds,
            'potential_return': self.potential_return,
            'bet_type': self.bet_type,
            'status': self.status,
            'actual_return': self.actual_return,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Association table for bet slips and bets (many-to-many)
bet_slip_bets = db.Table('bet_slip_bets',
    db.Column('bet_slip_id', db.Integer, db.ForeignKey('bet_slips.id'), primary_key=True),
    db.Column('bet_id', db.Integer, db.ForeignKey('bets.id'), primary_key=True)
)

