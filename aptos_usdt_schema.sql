-- Aptos USDT Wallet Schema - 4 Wallet System
-- Extends operator_wallets table to support USDT wallets on Aptos

-- Add Aptos USDT wallet fields to operator_wallets table
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS usdt_balance DECIMAL(18,6) DEFAULT 0;
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS usdt_contract VARCHAR(66);

-- Add Aptos USDT wallet fields to users table  
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS usdt_balance DECIMAL(18,6) DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS usdt_contract VARCHAR(66);

-- Add USDT transaction fields to bets table (for on-chain betting)
ALTER TABLE bets ADD COLUMN IF NOT EXISTS aptos_transaction_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS on_chain BOOLEAN DEFAULT FALSE;
ALTER TABLE bets ADD COLUMN IF NOT EXISTS settlement_tx_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS usdt_stake DECIMAL(18,6);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS usdt_payout DECIMAL(18,6);

-- Create table for USDT transactions (detailed transaction tracking)
CREATE TABLE IF NOT EXISTS usdt_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- 'operator' or 'user'
    entity_id INTEGER NOT NULL,
    wallet_type TEXT, -- 'bookmaker_capital', 'liquidity_pool', 'revenue', 'community' for operators
    transaction_type TEXT NOT NULL, -- 'wallet_creation', 'deposit', 'withdrawal', 'bet_placement', 'bet_settlement', 'revenue_distribution'
    aptos_transaction_hash VARCHAR(66),
    from_wallet VARCHAR(66),
    to_wallet VARCHAR(66),
    usdt_amount DECIMAL(18,6) NOT NULL,
    usdt_contract VARCHAR(66),
    status TEXT NOT NULL, -- 'pending', 'confirmed', 'failed'
    description TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create table for daily USDT revenue distribution
CREATE TABLE IF NOT EXISTS usdt_revenue_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    
    -- Traditional USD amounts (from existing system)
    usd_total_revenue DECIMAL(10,2) DEFAULT 0,
    usd_bookmaker_share DECIMAL(10,2) DEFAULT 0,
    usd_community_share DECIMAL(10,2) DEFAULT 0,
    usd_kryzel_fee DECIMAL(10,2) DEFAULT 0,
    
    -- USDT amounts (mirrored on-chain)
    usdt_total_revenue DECIMAL(18,6) DEFAULT 0,
    usdt_bookmaker_share DECIMAL(18,6) DEFAULT 0,
    usdt_community_share DECIMAL(18,6) DEFAULT 0,
    usdt_kryzel_fee DECIMAL(18,6) DEFAULT 0,
    
    -- Transaction hashes for on-chain operations
    bookmaker_tx_hash VARCHAR(66),
    community_tx_hash VARCHAR(66),
    kryzel_tx_hash VARCHAR(66),
    
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (operator_id, calculation_date),
    FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_entity ON usdt_transactions (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_wallet_type ON usdt_transactions (wallet_type);
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_tx_hash ON usdt_transactions (aptos_transaction_hash);
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_operator ON usdt_revenue_distributions (operator_id);
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_date ON usdt_revenue_distributions (calculation_date);

-- Add comments for documentation
COMMENT ON COLUMN operator_wallets.aptos_wallet_address IS 'Aptos blockchain wallet address for USDT operations';
COMMENT ON COLUMN operator_wallets.usdt_balance IS 'Current USDT balance in this wallet (6 decimal places)';
COMMENT ON COLUMN operator_wallets.usdt_contract IS 'USDT contract address on Aptos';

COMMENT ON TABLE usdt_transactions IS 'Tracks all USDT transactions on Aptos blockchain';
COMMENT ON TABLE usdt_revenue_distributions IS 'Daily revenue distribution in both USD and USDT';
