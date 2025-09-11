"""
Database models for sports betting platform
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import json

# Remove the separate db instance - we'll use the main Flask app's database
# db = SQLAlchemy()

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

# We'll define these models but they'll be bound to the main app's db instance
# The actual db.Model will be set when the models are imported and bound to the app

class User:
    __tablename__ = 'users'
    
    # These will be set by SQLAlchemy when the model is bound
    id = None
    username = None
    email = None
    password_hash = None
    balance = None
    created_at = None
    last_login = None
    is_active = None
    
    # Multi-tenant support
    sportsbook_operator_id = None  # Foreign key to sportsbook_operators
    
    # Relationships
    bets = None
    transactions = None
    
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

class Bet:
    __tablename__ = 'bets'
    
    id = None  # Will be set by SQLAlchemy
    user_id = None
    
    # Multi-tenant support
    sportsbook_operator_id = None  # Foreign key to sportsbook_operators
    
    # Simplified fields for frontend compatibility
    match_id = None  # Match identifier
    match_name = None  # e.g., "Team A vs Team B"
    selection = None  # e.g., "Team A", "Over 2.5"
    bet_selection = None  # Alias for selection
    
    # Sport information - stored at betting time for reliable settlement
    sport_name = None  # e.g., "baseball", "soccer", "tennis"
    
    # Market information - for admin liability calculation
    market = None  # Market ID for admin liability calculation
    
    # Bet details
    stake = None
    odds = None  # Odds at time of bet placement
    potential_return = None
    status = None  # Simplified status
    bet_type = None  # Simplified type (single/combo)
    bet_timing = None  # pregame/ingame
    
    # Admin control
    is_active = None  # Can be disabled by admin
    
    # Settlement
    actual_return = None
    settled_at = None
    
    # Combo bet fields
    combo_selections = None  # JSON string for combo bet selections
    
    # Event timing
    event_time = None  # UTC time when the event is scheduled
    
    # Metadata
    created_at = None
    updated_at = None
    
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
            'market': self.market,
            'stake': self.stake,
            'odds': self.odds,
            'potential_return': self.potential_return,
            'status': self.status,
            'bet_type': self.bet_type,
            'bet_timing': self.bet_timing,
            'is_active': self.is_active,
            'actual_return': self.actual_return,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
            'event_time': self.event_time.isoformat() if self.event_time else None,
            'combo_selections': self.combo_selections,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Transaction:
    __tablename__ = 'transactions'
    
    id = None  # Will be set by SQLAlchemy
    user_id = None
    
    # Multi-tenant support
    sportsbook_operator_id = None  # Foreign key to sportsbook_operators
    
    # Transaction details
    bet_id = None  # Reference to bet
    amount = None  # Positive for deposits/wins, negative for withdrawals/bets
    transaction_type = None  # 'deposit', 'withdrawal', 'bet', 'win', 'loss'
    description = None  # Human-readable description
    
    # Balance tracking
    balance_before = None  # User balance before transaction
    balance_after = None   # User balance after transaction
    
    # Metadata
    created_at = None
    updated_at = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sportsbook_operator_id': self.sportsbook_operator_id,
            'bet_id': self.bet_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BetSlip:
    __tablename__ = 'bet_slips'
    
    id = None  # Will be set by SQLAlchemy
    user_id = None
    
    # Multi-tenant support
    sportsbook_operator_id = None  # Foreign key to sportsbook_operators
    
    # Bet slip details
    selections = None  # JSON string of bet selections
    total_stake = None
    potential_return = None
    status = None  # 'pending', 'placed', 'cancelled'
    
    # Metadata
    created_at = None
    updated_at = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sportsbook_operator_id': self.sportsbook_operator_id,
            'selections': self.selections,
            'total_stake': self.total_stake,
            'potential_return': self.potential_return,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Event:
    __tablename__ = 'events'
    
    id = None  # Will be set by SQLAlchemy
    goalserve_id = None  # External ID from GoalServe
    sport = None  # Sport name
    league = None  # League name
    home_team = None  # Home team name
    away_team = None  # Away team name
    start_time = None  # Event start time
    status = None  # Event status
    
    def to_dict(self):
        return {
            'id': self.id,
            'goalserve_id': self.goalserve_id,
            'sport': self.sport,
            'league': self.league,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'status': self.status
        }

class Outcome:
    __tablename__ = 'outcomes'
    
    id = None  # Will be set by SQLAlchemy
    event_id = None  # Foreign key to events
    market_id = None  # Market identifier
    selection = None  # Outcome selection (e.g., "Home", "Away", "Draw")
    odds = None  # Current odds
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'market_id': self.market_id,
            'selection': self.selection,
            'odds': self.odds
        }

# Function to bind models to the main Flask app's database
def bind_models_to_db(db_instance):
    """Bind all models to the main Flask app's database instance"""
    global User, Bet, Transaction, BetSlip, Event, Outcome
    
    # Bind User model
    User = type('User', (db_instance.Model,), {
        '__tablename__': 'users',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'username': db_instance.Column(db_instance.String(80), unique=True, nullable=False),
        'email': db_instance.Column(db_instance.String(120), unique=True, nullable=False),
        'password_hash': db_instance.Column(db_instance.String(255), nullable=False),
        'balance': db_instance.Column(db_instance.Float, default=1000.0),
        'created_at': db_instance.Column(db_instance.DateTime, default=datetime.utcnow),
        'last_login': db_instance.Column(db_instance.DateTime),
        'is_active': db_instance.Column(db_instance.Boolean, default=True),
        'sportsbook_operator_id': db_instance.Column(db_instance.Integer, nullable=True),
        'bets': db_instance.relationship('Bet', backref='user', lazy=True, cascade='all, delete-orphan'),
        'transactions': db_instance.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    })
    
    # Bind Bet model
    Bet = type('Bet', (db_instance.Model,), {
        '__tablename__': 'bets',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'user_id': db_instance.Column(db_instance.Integer, db_instance.ForeignKey('users.id'), nullable=False),
        'sportsbook_operator_id': db_instance.Column(db_instance.Integer, nullable=True),
        'match_id': db_instance.Column(db_instance.String(50)),
        'match_name': db_instance.Column(db_instance.String(200)),
        'selection': db_instance.Column(db_instance.String(100)),
        'bet_selection': db_instance.Column(db_instance.String(100)),
        'sport_name': db_instance.Column(db_instance.String(200)),
        'market': db_instance.Column(db_instance.String(50)),
        'stake': db_instance.Column(db_instance.Float, nullable=False),
        'odds': db_instance.Column(db_instance.Float, nullable=False),
        'potential_return': db_instance.Column(db_instance.Float, nullable=False),
        'status': db_instance.Column(db_instance.String(20), default='pending'),
        'bet_type': db_instance.Column(db_instance.String(20), default='single'),
        'bet_timing': db_instance.Column(db_instance.String(100), default='pregame'),
        'is_active': db_instance.Column(db_instance.Boolean, default=True),
        'actual_return': db_instance.Column(db_instance.Float, default=0.0),
        'settled_at': db_instance.Column(db_instance.DateTime),
        'combo_selections': db_instance.Column(db_instance.Text),
        'created_at': db_instance.Column(db_instance.DateTime, default=datetime.utcnow),
        'updated_at': db_instance.Column(db_instance.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    })
    
    # Bind Transaction model
    Transaction = type('Transaction', (db_instance.Model,), {
        '__tablename__': 'transactions',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'user_id': db_instance.Column(db_instance.Integer, db_instance.ForeignKey('users.id'), nullable=False),
        'sportsbook_operator_id': db_instance.Column(db_instance.Integer, nullable=True),
        'bet_id': db_instance.Column(db_instance.Integer, db_instance.ForeignKey('bets.id'), nullable=True),
        'amount': db_instance.Column(db_instance.Float, nullable=False),
        'transaction_type': db_instance.Column(db_instance.String(50), nullable=False),
        'description': db_instance.Column(db_instance.String(200)),
        'balance_before': db_instance.Column(db_instance.Float, nullable=False),
        'balance_after': db_instance.Column(db_instance.Float, nullable=False),
        'created_at': db_instance.Column(db_instance.DateTime, default=datetime.now)
    })
    
    # Bind BetSlip model
    BetSlip = type('BetSlip', (db_instance.Model,), {
        '__tablename__': 'bet_slips',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'user_id': db_instance.Column(db_instance.Integer, db_instance.ForeignKey('users.id'), nullable=False),
        'sportsbook_operator_id': db_instance.Column(db_instance.Integer, nullable=True),
        'selections': db_instance.Column(db_instance.Text),
        'total_stake': db_instance.Column(db_instance.Float, default=0.0),
        'potential_return': db_instance.Column(db_instance.Float, default=0.0),
        'status': db_instance.Column(db_instance.String(20), default='pending'),
        'created_at': db_instance.Column(db_instance.DateTime, default=datetime.utcnow),
        'updated_at': db_instance.Column(db_instance.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    })
    
    # Bind Event model
    Event = type('Event', (db_instance.Model,), {
        '__tablename__': 'events',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'goalserve_id': db_instance.Column(db_instance.String(100), unique=True, nullable=False),
        'sport': db_instance.Column(db_instance.String(50)),
        'league': db_instance.Column(db_instance.String(100)),
        'home_team': db_instance.Column(db_instance.String(100)),
        'away_team': db_instance.Column(db_instance.String(100)),
        'start_time': db_instance.Column(db_instance.DateTime),
        'status': db_instance.Column(db_instance.String(20), default='scheduled')
    })
    
    # Bind Outcome model
    Outcome = type('Outcome', (db_instance.Model,), {
        '__tablename__': 'outcomes',
        'id': db_instance.Column(db_instance.Integer, primary_key=True),
        'event_id': db_instance.Column(db_instance.Integer, db_instance.ForeignKey('events.id'), nullable=False),
        'market_id': db_instance.Column(db_instance.String(50)),
        'selection': db_instance.Column(db_instance.String(100)),
        'odds': db_instance.Column(db_instance.Float)
    })

