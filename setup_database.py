#!/usr/bin/env python3
"""
GoalServe Sports Betting Platform - Database Setup Script
This script creates and initializes the database with all necessary tables, indexes, and sample data.
"""

import os
import sys
import sqlite3
from pathlib import Path
import hashlib
import json
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def create_password_hash(password):
    """Create a simple password hash (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def setup_database():
    """Set up the complete database with all tables and sample data"""
    
    # Ensure database directory exists
    db_dir = Path("src/database")
    db_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = db_dir / "app.db"
    
    # Remove existing database if it exists
    if db_path.exists():
        print(f"⚠️  Removing existing database: {db_path}")
        db_path.unlink()
    
    print(f"🚀 Creating new database: {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode = WAL")
        
        # Set cache size for better performance
        cursor.execute("PRAGMA cache_size = 10000")
        
        # Set temp store to memory for better performance
        cursor.execute("PRAGMA temp_store = MEMORY")
        
        print("✅ Database configuration applied")
        
        # Create tables
        print("📋 Creating database tables...")
        
        # Sportsbook operators table
        cursor.execute("""
            CREATE TABLE sportsbook_operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sportsbook_name VARCHAR(100) NOT NULL UNIQUE,
                login VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(120),
                subdomain VARCHAR(50) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT true,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                total_revenue FLOAT DEFAULT 0.0,
                commission_rate FLOAT DEFAULT 0.05,
                settings TEXT
            )
        """)
        
        # Super admins table
        cursor.execute("""
            CREATE TABLE super_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(120) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                permissions TEXT
            )
        """)
        
        # Users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) NOT NULL UNIQUE,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                balance FLOAT DEFAULT 1000.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                is_active BOOLEAN DEFAULT 1,
                sportsbook_operator_id INTEGER,
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        """)
        
        # Bets table
        cursor.execute("""
            CREATE TABLE bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sportsbook_operator_id INTEGER,
                match_id VARCHAR(50),
                match_name VARCHAR(200),
                selection VARCHAR(100),
                bet_selection VARCHAR(100),
                sport_name VARCHAR(50),
                market VARCHAR(50),
                stake FLOAT NOT NULL,
                odds FLOAT NOT NULL,
                potential_return FLOAT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                bet_type VARCHAR(20) DEFAULT 'single',
                bet_timing VARCHAR(20) DEFAULT 'pregame',
                is_active BOOLEAN DEFAULT 1,
                actual_return FLOAT DEFAULT 0.0,
                settled_at DATETIME,
                combo_selections TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        """)
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bet_id INTEGER,
                sportsbook_operator_id INTEGER,
                amount FLOAT NOT NULL,
                transaction_type VARCHAR(20) NOT NULL,
                description VARCHAR(200),
                balance_before FLOAT NOT NULL,
                balance_after FLOAT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (bet_id) REFERENCES bets(id),
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        """)
        
        # Bet slips table
        cursor.execute("""
            CREATE TABLE bet_slips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sportsbook_operator_id INTEGER,
                total_stake FLOAT NOT NULL,
                total_odds FLOAT NOT NULL,
                potential_return FLOAT NOT NULL,
                bet_type VARCHAR(8),
                status VARCHAR(10),
                actual_return FLOAT,
                settled_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        """)
        
        # Association table for bet slips and bets
        cursor.execute("""
            CREATE TABLE bet_slip_bets (
                bet_slip_id INTEGER NOT NULL,
                bet_id INTEGER NOT NULL,
                PRIMARY KEY (bet_slip_id, bet_id),
                FOREIGN KEY (bet_slip_id) REFERENCES bet_slips(id),
                FOREIGN KEY (bet_id) REFERENCES bets(id)
            )
        """)
        
        # Sports table
        cursor.execute("""
            CREATE TABLE sports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sport_key VARCHAR(50) NOT NULL UNIQUE,
                sport_name VARCHAR(100) NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                icon VARCHAR(10),
                has_draw BOOLEAN DEFAULT 0,
                priority INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Matches table
        cursor.execute("""
            CREATE TABLE matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id VARCHAR(100) NOT NULL UNIQUE,
                sport_key VARCHAR(50) NOT NULL,
                match_name VARCHAR(200) NOT NULL,
                home_team VARCHAR(100),
                away_team VARCHAR(100),
                start_time DATETIME,
                status VARCHAR(20) DEFAULT 'scheduled',
                score_home INTEGER DEFAULT 0,
                score_away INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sport_key) REFERENCES sports(sport_key)
            )
        """)
        
        # Odds table
        cursor.execute("""
            CREATE TABLE odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id VARCHAR(100) NOT NULL,
                market_type VARCHAR(50) NOT NULL,
                selection VARCHAR(100) NOT NULL,
                odds_value FLOAT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
        """)
        
        # Themes table
        cursor.execute("""
            CREATE TABLE themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sportsbook_operator_id INTEGER NOT NULL,
                theme_name VARCHAR(100) NOT NULL,
                primary_color VARCHAR(7) DEFAULT '#007bff',
                secondary_color VARCHAR(7) DEFAULT '#6c757d',
                accent_color VARCHAR(7) DEFAULT '#28a745',
                background_color VARCHAR(7) DEFAULT '#ffffff',
                text_color VARCHAR(7) DEFAULT '#212529',
                font_family VARCHAR(100) DEFAULT 'Arial, sans-serif',
                logo_url VARCHAR(255),
                favicon_url VARCHAR(255),
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
            )
        """)
        
        print("✅ All tables created successfully")
        
        # Create indexes
        print("🔍 Creating database indexes...")
        
        # Multi-tenant indexes
        cursor.execute("CREATE INDEX idx_users_sportsbook_operator ON users(sportsbook_operator_id)")
        cursor.execute("CREATE INDEX idx_bets_sportsbook_operator ON bets(sportsbook_operator_id)")
        cursor.execute("CREATE INDEX idx_transactions_sportsbook_operator ON transactions(sportsbook_operator_id)")
        cursor.execute("CREATE INDEX idx_bet_slips_sportsbook_operator ON bet_slips(sportsbook_operator_id)")
        
        # Sportsbook operator indexes
        cursor.execute("CREATE INDEX idx_sportsbook_operators_subdomain ON sportsbook_operators(subdomain)")
        cursor.execute("CREATE INDEX idx_sportsbook_operators_login ON sportsbook_operators(login)")
        cursor.execute("CREATE INDEX idx_sportsbook_operators_email ON sportsbook_operators(email)")
        
        # User indexes
        cursor.execute("CREATE INDEX idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX idx_users_last_login ON users(last_login)")
        
        # Bet indexes
        cursor.execute("CREATE INDEX idx_bets_user_id ON bets(user_id)")
        cursor.execute("CREATE INDEX idx_bets_match_id ON bets(match_id)")
        cursor.execute("CREATE INDEX idx_bets_status ON bets(status)")
        cursor.execute("CREATE INDEX idx_bets_sport_name ON bets(sport_name)")
        cursor.execute("CREATE INDEX idx_bets_created_at ON bets(created_at)")
        
        # Transaction indexes
        cursor.execute("CREATE INDEX idx_transactions_user_id ON transactions(user_id)")
        cursor.execute("CREATE INDEX idx_transactions_bet_id ON transactions(bet_id)")
        cursor.execute("CREATE INDEX idx_transactions_type ON transactions(transaction_type)")
        cursor.execute("CREATE INDEX idx_transactions_created_at ON transactions(created_at)")
        
        # Match indexes
        cursor.execute("CREATE INDEX idx_matches_sport_key ON matches(sport_key)")
        cursor.execute("CREATE INDEX idx_matches_start_time ON matches(start_time)")
        cursor.execute("CREATE INDEX idx_matches_status ON matches(status)")
        
        # Odds indexes
        cursor.execute("CREATE INDEX idx_odds_match_id ON odds(match_id)")
        cursor.execute("CREATE INDEX idx_odds_market_type ON odds(market_type)")
        
        # Theme indexes
        cursor.execute("CREATE INDEX idx_themes_operator ON themes(sportsbook_operator_id)")
        
        print("✅ All indexes created successfully")
        
        # Insert sample data
        print("📊 Inserting sample data...")
        
        # Default super admin
        super_admin_password = "superadmin123"
        super_admin_hash = create_password_hash(super_admin_password)
        cursor.execute("""
            INSERT INTO super_admins (username, password_hash, email, permissions) 
            VALUES (?, ?, ?, ?)
        """, ('superadmin', super_admin_hash, 'admin@goalserve.com', '{"all": true}'))
        
        # Default sportsbook operator
        operator_password = "admin123"
        operator_hash = create_password_hash(operator_password)
        cursor.execute("""
            INSERT INTO sportsbook_operators (sportsbook_name, login, password_hash, subdomain, email, settings) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('Default Sportsbook', 'admin', operator_hash, 'default', 'admin@default.com', '{"theme": "default", "commission": 0.05}'))
        
        # Default sports
        sports_data = [
            ('soccer', 'Soccer', 'Soccer', '⚽', 1, 1),
            ('basketball', 'Basketball', 'Basketball', '🏀', 1, 2),
            ('tennis', 'Tennis', 'Tennis', '🎾', 0, 3),
            ('baseball', 'Baseball', 'Baseball', '⚾', 0, 4),
            ('hockey', 'Hockey', 'Hockey', '🏒', 0, 5),
            ('cricket', 'Cricket', 'Cricket', '🏏', 1, 6),
            ('football', 'American Football', 'American Football', '🏈', 0, 7),
            ('rugby', 'Rugby', 'Rugby', '🏉', 1, 8),
            ('volleyball', 'Volleyball', 'Volleyball', '🏐', 0, 9),
            ('handball', 'Handball', 'Handball', '🤾', 1, 10),
            ('table_tennis', 'Table Tennis', 'Table Tennis', '🏓', 0, 11),
            ('darts', 'Darts', 'Darts', '🎯', 0, 12),
            ('esports', 'Esports', 'Esports', '🎮', 0, 13),
            ('mma', 'MMA', 'Mixed Martial Arts', '🥊', 0, 14),
            ('boxing', 'Boxing', 'Boxing', '🥊', 0, 15),
            ('golf', 'Golf', 'Golf', '⛳', 0, 16),
            ('futsal', 'Futsal', 'Futsal', '⚽', 1, 17),
            ('rugbyleague', 'Rugby League', 'Rugby League', '🏉', 1, 18)
        ]
        
        cursor.executemany("""
            INSERT INTO sports (sport_key, sport_name, display_name, icon, has_draw, priority) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, sports_data)
        
        # Default theme
        cursor.execute("""
            INSERT INTO themes (sportsbook_operator_id, theme_name, primary_color, secondary_color, accent_color) 
            VALUES (?, ?, ?, ?, ?)
        """, (1, 'Default Theme', '#007bff', '#6c757d', '#28a745'))
        
        print("✅ Sample data inserted successfully")
        
        # Create views
        print("👁️  Creating database views...")
        
        # Active bets view
        cursor.execute("""
            CREATE VIEW active_bets_view AS
            SELECT 
                b.id,
                b.match_name,
                b.selection,
                b.stake,
                b.odds,
                b.potential_return,
                b.status,
                b.sport_name,
                u.username,
                u.email,
                so.sportsbook_name,
                b.created_at
            FROM bets b
            JOIN users u ON b.user_id = u.id
            LEFT JOIN sportsbook_operators so ON b.sportsbook_operator_id = so.id
            WHERE b.is_active = 1 AND b.status = 'pending'
        """)
        
        # Operator revenue view
        cursor.execute("""
            CREATE VIEW operator_revenue_view AS
            SELECT 
                so.id,
                so.sportsbook_name,
                so.subdomain,
                COUNT(DISTINCT u.id) as total_users,
                COUNT(b.id) as total_bets,
                SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END) as total_payouts,
                SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_winnings,
                so.total_revenue,
                so.commission_rate
            FROM sportsbook_operators so
            LEFT JOIN users u ON so.id = u.sportsbook_operator_id
            LEFT JOIN bets b ON so.id = b.sportsbook_operator_id
            GROUP BY so.id, so.sportsbook_name, so.subdomain
        """)
        
        print("✅ Database views created successfully")
        
        # Commit all changes
        conn.commit()
        
        print("\n🎉 Database setup completed successfully!")
        print(f"📁 Database location: {db_path}")
        print("\n🔑 Default Login Credentials:")
        print("   Super Admin:")
        print(f"     Username: superadmin")
        print(f"     Password: {super_admin_password}")
        print("     Email: admin@goalserve.com")
        print("\n   Default Sportsbook Operator:")
        print(f"     Username: admin")
        print(f"     Password: {operator_password}")
        print(f"     Subdomain: default")
        print(f"     Email: admin@default.com")
        print("\n⚠️  IMPORTANT: Change these passwords in production!")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        setup_database()
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)
