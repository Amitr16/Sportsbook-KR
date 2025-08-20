-- Wallet Revenue Architecture Database Migration
-- Creates the 4-wallet system tables

-- Create operator_wallets table
CREATE TABLE IF NOT EXISTS operator_wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    wallet_type VARCHAR(50) NOT NULL,
    current_balance REAL NOT NULL DEFAULT 0.0,
    initial_balance REAL NOT NULL DEFAULT 0.0,
    leverage_multiplier REAL NOT NULL DEFAULT 1.0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES sportsbook_operators (id),
    UNIQUE(operator_id, wallet_type)
);

-- Create wallet_daily_balances table
CREATE TABLE IF NOT EXISTS wallet_daily_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    date DATE NOT NULL,
    opening_balance REAL NOT NULL,
    closing_balance REAL NOT NULL,
    daily_pnl REAL NOT NULL DEFAULT 0.0,
    total_revenue REAL NOT NULL DEFAULT 0.0,
    total_bets_amount REAL NOT NULL DEFAULT 0.0,
    total_payouts REAL NOT NULL DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES operator_wallets (id),
    UNIQUE(wallet_id, date)
);

-- Create wallet_transactions table
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    amount REAL NOT NULL,
    balance_before REAL NOT NULL,
    balance_after REAL NOT NULL,
    description VARCHAR(500),
    reference_id VARCHAR(100),
    metadata TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES operator_wallets (id)
);

-- Create revenue_calculations table
CREATE TABLE IF NOT EXISTS revenue_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    total_revenue REAL NOT NULL DEFAULT 0.0,
    total_bets_amount REAL NOT NULL DEFAULT 0.0,
    total_payouts REAL NOT NULL DEFAULT 0.0,
    
    -- Revenue distribution (when profit)
    bookmaker_own_share REAL NOT NULL DEFAULT 0.0,
    kryzel_fee_from_own REAL NOT NULL DEFAULT 0.0,
    bookmaker_net_own REAL NOT NULL DEFAULT 0.0,
    remaining_profit REAL NOT NULL DEFAULT 0.0,
    bookmaker_share_60 REAL NOT NULL DEFAULT 0.0,
    community_share_30 REAL NOT NULL DEFAULT 0.0,
    kryzel_share_10 REAL NOT NULL DEFAULT 0.0,
    
    -- Loss distribution (when loss)
    bookmaker_own_loss REAL NOT NULL DEFAULT 0.0,
    remaining_loss REAL NOT NULL DEFAULT 0.0,
    bookmaker_loss_70 REAL NOT NULL DEFAULT 0.0,
    community_loss_30 REAL NOT NULL DEFAULT 0.0,
    
    -- Final amounts
    total_bookmaker_earnings REAL NOT NULL DEFAULT 0.0,
    
    calculation_metadata TEXT,
    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES sportsbook_operators (id),
    UNIQUE(operator_id, calculation_date)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_operator_wallets_operator_id ON operator_wallets(operator_id);
CREATE INDEX IF NOT EXISTS idx_operator_wallets_type ON operator_wallets(wallet_type);
CREATE INDEX IF NOT EXISTS idx_wallet_daily_balances_wallet_id ON wallet_daily_balances(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_daily_balances_date ON wallet_daily_balances(date);
CREATE INDEX IF NOT EXISTS idx_wallet_transactions_wallet_id ON wallet_transactions(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_transactions_type ON wallet_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_revenue_calculations_operator_id ON revenue_calculations(operator_id);
CREATE INDEX IF NOT EXISTS idx_revenue_calculations_date ON revenue_calculations(calculation_date);

-- Insert initial wallets for existing operators (if any)
-- This will create the 4 wallets for any existing operators
INSERT OR IGNORE INTO operator_wallets (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
SELECT 
    id as operator_id,
    'bookmaker_capital' as wallet_type,
    10000.0 as current_balance,
    10000.0 as initial_balance,
    1.0 as leverage_multiplier
FROM sportsbook_operators;

INSERT OR IGNORE INTO operator_wallets (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
SELECT 
    id as operator_id,
    'liquidity_pool' as wallet_type,
    40000.0 as current_balance,
    40000.0 as initial_balance,
    5.0 as leverage_multiplier
FROM sportsbook_operators;

INSERT OR IGNORE INTO operator_wallets (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
SELECT 
    id as operator_id,
    'revenue' as wallet_type,
    0.0 as current_balance,
    0.0 as initial_balance,
    1.0 as leverage_multiplier
FROM sportsbook_operators;

INSERT OR IGNORE INTO operator_wallets (operator_id, wallet_type, current_balance, initial_balance, leverage_multiplier)
SELECT 
    id as operator_id,
    'bookmaker_earnings' as wallet_type,
    0.0 as current_balance,
    0.0 as initial_balance,
    1.0 as leverage_multiplier
FROM sportsbook_operators;

