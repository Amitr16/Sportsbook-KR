-- ========================================
-- GoalServe Sports Betting Platform
-- PostgreSQL Database Schema
-- ========================================

-- ========================================
-- Core Tables
-- ========================================

-- Sportsbook operators (admins) who run their own betting sites
CREATE TABLE sportsbook_operators (
    id SERIAL PRIMARY KEY,
    sportsbook_name VARCHAR(100) NOT NULL UNIQUE,
    login VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120),
    subdomain VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    total_revenue DECIMAL(10,2) DEFAULT 0.0,
    commission_rate DECIMAL(5,4) DEFAULT 0.05,
    settings TEXT -- JSON field for operator-specific settings
);

-- Super administrators with global access
CREATE TABLE super_admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    permissions TEXT -- JSON field for granular permissions
);

-- Users table with multi-tenant support
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) DEFAULT 1000.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    sportsbook_operator_id INTEGER,
    FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
);

-- Bets table with multi-tenant support
CREATE TABLE bets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    sportsbook_operator_id INTEGER,
    match_id VARCHAR(50),
    match_name VARCHAR(200),
    selection VARCHAR(100),
    bet_selection VARCHAR(100),
    sport_name VARCHAR(50),
    market VARCHAR(50),
    stake DECIMAL(10,2) NOT NULL,
    odds DECIMAL(8,2) NOT NULL,
    potential_return DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    bet_type VARCHAR(20) DEFAULT 'single',
    bet_timing VARCHAR(20) DEFAULT 'pregame',
    is_active BOOLEAN DEFAULT true,
    actual_return DECIMAL(10,2) DEFAULT 0.0,
    settled_at TIMESTAMP,
    combo_selections TEXT,
    event_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
);

-- Transactions table with multi-tenant support
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    bet_id INTEGER,
    sportsbook_operator_id INTEGER,
    amount DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    description VARCHAR(200),
    balance_before DECIMAL(10,2) NOT NULL,
    balance_after DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (bet_id) REFERENCES bets(id),
    FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
);

-- Bet slips table with multi-tenant support
CREATE TABLE bet_slips (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    sportsbook_operator_id INTEGER,
    total_stake DECIMAL(10,2) NOT NULL,
    total_odds DECIMAL(8,2) NOT NULL,
    potential_return DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
);

-- Events/Matches table
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(50) UNIQUE,
    sport_name VARCHAR(50),
    match_name VARCHAR(200),
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    start_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'scheduled',
    result VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outcomes table
CREATE TABLE outcomes (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(50),
    market VARCHAR(50),
    selection VARCHAR(100),
    odds DECIMAL(8,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sports table
CREATE TABLE sports (
    id SERIAL PRIMARY KEY,
    sport_key VARCHAR(20) UNIQUE,
    sport_name VARCHAR(50) NOT NULL,
    display_name VARCHAR(50),
    icon_url VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Themes table for operator customization
CREATE TABLE themes (
    id SERIAL PRIMARY KEY,
    sportsbook_operator_id INTEGER,
    theme_name VARCHAR(50) DEFAULT 'default',
    primary_color VARCHAR(7) DEFAULT '#007bff',
    secondary_color VARCHAR(7) DEFAULT '#6c757d',
    accent_color VARCHAR(7) DEFAULT '#28a745',
    logo_url VARCHAR(255),
    custom_css TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sportsbook_operator_id) REFERENCES sportsbook_operators(id)
);

-- ========================================
-- Indexes for Performance
-- ========================================

CREATE INDEX idx_bets_user_id ON bets(user_id);
CREATE INDEX idx_bets_operator_id ON bets(sportsbook_operator_id);
CREATE INDEX idx_bets_status ON bets(status);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_events_sport_name ON events(sport_name);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_outcomes_event_id ON outcomes(event_id);

-- ========================================
-- Sample Data
-- ========================================

-- Insert default super admin
INSERT INTO super_admins (username, password_hash, email, permissions) VALUES 
('admin', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'admin@goalserve.com', '["all"]');

-- Insert sample sportsbook operator
INSERT INTO sportsbook_operators (sportsbook_name, login, password_hash, email, subdomain, is_active) VALUES 
('Demo Sportsbook', 'demo', '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 'demo@goalserve.com', 'demo', true);

-- Insert sample sports
INSERT INTO sports (sport_key, sport_name, display_name, is_active) VALUES 
('soccer', 'Soccer', 'Soccer', true),
('basketball', 'Basketball', 'Basketball', true),
('tennis', 'Tennis', 'Tennis', true),
('hockey', 'Hockey', 'Hockey', true),
('baseball', 'Baseball', 'Baseball', true);

-- Insert default theme
INSERT INTO themes (sportsbook_operator_id, theme_name, primary_color, secondary_color, accent_color) VALUES 
(1, 'default', '#007bff', '#6c757d', '#28a745');

-- ========================================
-- Views for Common Queries
-- ========================================

-- View for bet summary with operator info
CREATE VIEW bet_summary AS
SELECT 
    b.id, b.user_id, b.match_name, b.stake, b.odds, b.status,
    u.username, so.sportsbook_name
FROM bets b
LEFT JOIN users u ON b.user_id = u.id
LEFT JOIN sportsbook_operators so ON b.sportsbook_operator_id = so.id;

-- View for operator revenue summary
CREATE VIEW operator_revenue AS
SELECT 
    so.id, so.sportsbook_name, so.subdomain,
    COUNT(b.id) as total_bets,
    SUM(b.stake) as total_stake,
    SUM(CASE WHEN b.status = 'won' THEN b.actual_return ELSE 0 END) as total_payouts
FROM sportsbook_operators so
LEFT JOIN bets b ON so.id = b.sportsbook_operator_id
GROUP BY so.id, so.sportsbook_name, so.subdomain;

-- ========================================
-- Functions and Triggers
-- ========================================

-- Function to update bet status
CREATE OR REPLACE FUNCTION update_bet_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('won', 'lost') AND OLD.status = 'pending' THEN
        -- Update user balance
        UPDATE users 
        SET balance = balance + NEW.actual_return 
        WHERE id = NEW.user_id;
        
        -- Insert transaction record
        INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after)
        SELECT 
            NEW.user_id, 
            NEW.id, 
            NEW.actual_return, 
            'bet_settlement', 
            'Bet settlement: ' || NEW.status,
            balance - NEW.actual_return,
            balance
        FROM users WHERE id = NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for bet status updates
CREATE TRIGGER bet_status_trigger
    AFTER UPDATE ON bets
    FOR EACH ROW
    EXECUTE FUNCTION update_bet_status();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at columns
CREATE TRIGGER update_sportsbook_operators_updated_at
    BEFORE UPDATE ON sportsbook_operators
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bets_updated_at
    BEFORE UPDATE ON bets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Grant Permissions
-- ========================================

-- Grant all permissions to the fly-user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "fly-user";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "fly-user";
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "fly-user";

-- ========================================
-- Schema Complete
-- ========================================

SELECT 'GoalServe Sports Betting Platform database schema created successfully!' as status;
