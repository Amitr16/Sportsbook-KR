-- ========================================
-- GoalServe Sports Betting Platform
-- Complete Database Schema
-- ========================================

-- ========================================
-- Core Tables
-- ========================================

-- Sportsbook operators (admins) who run their own betting sites
CREATE TABLE sportsbook_operators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sportsbook_name VARCHAR(100) NOT NULL UNIQUE,
    login VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120),
    subdomain VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    total_revenue FLOAT DEFAULT 0.0,
    commission_rate FLOAT DEFAULT 0.05,
    settings TEXT -- JSON field for operator-specific settings
);

-- Super administrators with global access
CREATE TABLE super_admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    permissions TEXT -- JSON field for granular permissions
);

-- Users table with multi-tenant support
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
);

-- Bets table with multi-tenant support
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
);

-- Transactions table with multi-tenant support
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
);

-- Bet slips table with multi-tenant support
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
);

-- Association table for bet slips and bets (many-to-many)
CREATE TABLE bet_slip_bets (
    bet_slip_id INTEGER NOT NULL,
    bet_id INTEGER NOT NULL,
    PRIMARY KEY (bet_slip_id, bet_id),
    FOREIGN KEY (bet_slip_id) REFERENCES bet_slips(id),
    FOREIGN KEY (bet_id) REFERENCES bets(id)
);

-- ========================================
-- Sports and Odds Tables
-- ========================================

-- Sports configuration table
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
);

-- Matches/Events table
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
);

-- Odds table for different markets
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
);

-- ========================================
-- Theme and Branding Tables
-- ========================================

-- Theme customization table
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
);

-- ========================================
-- Indexes for Performance
-- ========================================

-- Multi-tenant indexes
CREATE INDEX idx_users_sportsbook_operator ON users(sportsbook_operator_id);
CREATE INDEX idx_bets_sportsbook_operator ON bets(sportsbook_operator_id);
CREATE INDEX idx_transactions_sportsbook_operator ON transactions(sportsbook_operator_id);
CREATE INDEX idx_bet_slips_sportsbook_operator ON bet_slips(sportsbook_operator_id);

-- Sportsbook operator indexes
CREATE INDEX idx_sportsbook_operators_subdomain ON sportsbook_operators(subdomain);
CREATE INDEX idx_sportsbook_operators_login ON sportsbook_operators(login);
CREATE INDEX idx_sportsbook_operators_email ON sportsbook_operators(email);

-- User indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_last_login ON users(last_login);

-- Bet indexes
CREATE INDEX idx_bets_user_id ON bets(user_id);
CREATE INDEX idx_bets_match_id ON bets(match_id);
CREATE INDEX idx_bets_status ON bets(status);
CREATE INDEX idx_bets_sport_name ON bets(sport_name);
CREATE INDEX idx_bets_created_at ON bets(created_at);

-- Transaction indexes
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_bet_id ON transactions(bet_id);
CREATE INDEX idx_transactions_type ON transactions(transaction_type);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- Match indexes
CREATE INDEX idx_matches_sport_key ON matches(sport_key);
CREATE INDEX idx_matches_start_time ON matches(start_time);
CREATE INDEX idx_matches_status ON matches(status);

-- Odds indexes
CREATE INDEX idx_odds_match_id ON odds(match_id);
CREATE INDEX idx_odds_market_type ON odds(market_type);

-- Theme indexes
CREATE INDEX idx_themes_operator ON themes(sportsbook_operator_id);

-- ========================================
-- Sample Data
-- ========================================

-- Insert default super admin
INSERT INTO super_admins (username, password_hash, email, permissions) 
VALUES ('superadmin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4tbQJ3qKqG', 'admin@goalserve.com', '{"all": true}');

-- Insert default sportsbook operator
INSERT INTO sportsbook_operators (sportsbook_name, login, password_hash, subdomain, email, settings) 
VALUES ('Default Sportsbook', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4tbQJ3qKqG', 'default', 'admin@default.com', '{"theme": "default", "commission": 0.05}');

-- Insert default sports
INSERT INTO sports (sport_key, sport_name, display_name, icon, has_draw, priority) VALUES
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
('rugbyleague', 'Rugby League', 'Rugby League', '🏉', 1, 18);

-- Insert default theme for default sportsbook
INSERT INTO themes (sportsbook_operator_id, theme_name, primary_color, secondary_color, accent_color) 
VALUES (1, 'Default Theme', '#007bff', '#6c757d', '#28a745');

-- ========================================
-- Views for Common Queries
-- ========================================

-- View for active bets with user and operator info
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
WHERE b.is_active = 1 AND b.status = 'pending';

-- View for operator revenue summary
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
GROUP BY so.id, so.sportsbook_name, so.subdomain;

-- ========================================
-- Triggers for Data Integrity
-- ========================================

-- Trigger to update user balance after transaction
CREATE TRIGGER update_user_balance_after_transaction
AFTER INSERT ON transactions
BEGIN
    UPDATE users 
    SET balance = NEW.balance_after 
    WHERE id = NEW.user_id;
END;

-- Trigger to update operator revenue after bet settlement
CREATE TRIGGER update_operator_revenue_after_settlement
AFTER UPDATE ON bets
WHEN NEW.status IN ('won', 'lost') AND OLD.status = 'pending'
BEGIN
    UPDATE sportsbook_operators 
    SET total_revenue = total_revenue + 
        CASE 
            WHEN NEW.status = 'lost' THEN NEW.stake * (1 - commission_rate)
            WHEN NEW.status = 'won' THEN NEW.stake * (1 - commission_rate) - NEW.actual_return
        END
    WHERE id = NEW.sportsbook_operator_id;
END;

-- ========================================
-- Database Maintenance
-- ========================================

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Set cache size for better performance
PRAGMA cache_size = 10000;

-- Set temp store to memory for better performance
PRAGMA temp_store = MEMORY;
