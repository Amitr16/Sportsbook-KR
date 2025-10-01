-- Hybrid Wallet Schema - Web2 + Web3 USDT Integration
-- Extends existing tables to support USDT balances alongside USD balances

-- ============================================================================
-- USERS TABLE EXTENSIONS
-- ============================================================================

-- Add USDT balance fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS usdt_balance DECIMAL(18,6) DEFAULT 0.000000;
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS usdt_contract VARCHAR(100);

-- ============================================================================
-- OPERATOR_WALLETS TABLE EXTENSIONS  
-- ============================================================================

-- Add USDT balance fields to operator_wallets table
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS usdt_balance DECIMAL(18,6) DEFAULT 0.000000;
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS usdt_contract VARCHAR(100);

-- ============================================================================
-- SPORTSBOOK_OPERATORS TABLE EXTENSIONS
-- ============================================================================

-- Add Web3 enablement to operators
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS total_usdt_minted DECIMAL(18,6) DEFAULT 0.000000;

-- ============================================================================
-- TRANSACTIONS TABLE EXTENSIONS
-- ============================================================================

-- Add USDT transaction tracking to existing transactions table
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS usdt_amount DECIMAL(18,6);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS aptos_transaction_hash VARCHAR(66);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS usdt_contract VARCHAR(100);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- BETS TABLE EXTENSIONS
-- ============================================================================

-- Add USDT betting fields to bets table
ALTER TABLE bets ADD COLUMN IF NOT EXISTS usdt_stake DECIMAL(18,6);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS usdt_potential_return DECIMAL(18,6);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS usdt_actual_return DECIMAL(18,6);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS aptos_bet_transaction_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS aptos_settlement_transaction_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS on_chain BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- NEW TABLES FOR USDT OPERATIONS
-- ============================================================================

-- Create table for USDT transaction history
CREATE TABLE IF NOT EXISTS usdt_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- 'user' or 'operator'
    entity_id INTEGER NOT NULL,
    wallet_type TEXT, -- For operators: 'bookmaker_capital', 'liquidity_pool', 'revenue', 'community'
    transaction_type TEXT NOT NULL, -- 'mint', 'transfer', 'burn', 'bet', 'settlement', 'revenue_distribution'
    from_wallet VARCHAR(66),
    to_wallet VARCHAR(66),
    usdt_amount DECIMAL(18,6) NOT NULL,
    aptos_transaction_hash VARCHAR(66),
    usdt_contract VARCHAR(100),
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'confirmed', 'failed'
    description TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP
);

-- Create table for daily USDT revenue distributions
CREATE TABLE IF NOT EXISTS usdt_revenue_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    
    -- USD amounts (from existing system)
    usd_total_revenue DECIMAL(10,2) DEFAULT 0,
    usd_bookmaker_share DECIMAL(10,2) DEFAULT 0,
    usd_liquidity_share DECIMAL(10,2) DEFAULT 0,
    usd_revenue_share DECIMAL(10,2) DEFAULT 0,
    usd_community_share DECIMAL(10,2) DEFAULT 0,
    
    -- USDT amounts (mirrored)
    usdt_total_revenue DECIMAL(18,6) DEFAULT 0,
    usdt_bookmaker_share DECIMAL(18,6) DEFAULT 0,
    usdt_liquidity_share DECIMAL(18,6) DEFAULT 0,
    usdt_revenue_share DECIMAL(18,6) DEFAULT 0,
    usdt_community_share DECIMAL(18,6) DEFAULT 0,
    
    -- Transaction hashes for on-chain operations
    bookmaker_tx_hash VARCHAR(66),
    liquidity_tx_hash VARCHAR(66),
    revenue_tx_hash VARCHAR(66),
    community_tx_hash VARCHAR(66),
    
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (operator_id, calculation_date),
    FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id)
);

-- Create table for wallet synchronization status
CREATE TABLE IF NOT EXISTS wallet_sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- 'user' or 'operator'
    entity_id INTEGER NOT NULL,
    wallet_type TEXT, -- For operators: wallet type, for users: 'main'
    usd_balance DECIMAL(10,2),
    usdt_balance DECIMAL(18,6),
    is_synchronized BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- USDT transactions indexes
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_entity ON usdt_transactions (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_type ON usdt_transactions (transaction_type);
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_hash ON usdt_transactions (aptos_transaction_hash);
CREATE INDEX IF NOT EXISTS idx_usdt_transactions_status ON usdt_transactions (status);

-- Revenue distributions indexes
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_operator ON usdt_revenue_distributions (operator_id);
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_date ON usdt_revenue_distributions (calculation_date);
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_status ON usdt_revenue_distributions (status);

-- Wallet sync indexes
CREATE INDEX IF NOT EXISTS idx_wallet_sync_entity ON wallet_sync_status (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_wallet_sync_status ON wallet_sync_status (is_synchronized);

-- Users Web3 indexes
CREATE INDEX IF NOT EXISTS idx_users_web3_enabled ON users (web3_enabled);
CREATE INDEX IF NOT EXISTS idx_users_aptos_wallet ON users (aptos_wallet_address);

-- Operator wallets Web3 indexes
CREATE INDEX IF NOT EXISTS idx_operator_wallets_aptos ON operator_wallets (aptos_wallet_address);

-- ============================================================================
-- VIEWS FOR EASY QUERYING
-- ============================================================================

-- View for user wallet status
CREATE VIEW IF NOT EXISTS user_wallet_status AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.balance as usd_balance,
    u.usdt_balance,
    u.aptos_wallet_address,
    u.web3_enabled,
    CASE 
        WHEN u.web3_enabled = 1 AND ABS(u.balance - u.usdt_balance) < 0.01 THEN 'synchronized'
        WHEN u.web3_enabled = 1 AND ABS(u.balance - u.usdt_balance) >= 0.01 THEN 'out_of_sync'
        WHEN u.web3_enabled = 0 THEN 'web2_only'
        ELSE 'unknown'
    END as sync_status,
    u.sportsbook_operator_id
FROM users u;

-- View for operator wallet status
CREATE VIEW IF NOT EXISTS operator_wallet_status AS
SELECT 
    ow.id,
    ow.operator_id,
    so.sportsbook_name,
    ow.wallet_type,
    ow.current_balance as usd_balance,
    ow.usdt_balance,
    ow.aptos_wallet_address,
    CASE 
        WHEN so.web3_enabled = 1 AND ABS(ow.current_balance - ow.usdt_balance) < 0.01 THEN 'synchronized'
        WHEN so.web3_enabled = 1 AND ABS(ow.current_balance - ow.usdt_balance) >= 0.01 THEN 'out_of_sync'
        WHEN so.web3_enabled = 0 THEN 'web2_only'
        ELSE 'unknown'
    END as sync_status
FROM operator_wallets ow
JOIN sportsbook_operators so ON ow.operator_id = so.id;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

-- Add comments to document the hybrid system
COMMENT ON COLUMN users.usdt_balance IS 'USDT balance on Aptos blockchain (6 decimals)';
COMMENT ON COLUMN users.aptos_wallet_address IS 'Aptos wallet address created via Crossmint';
COMMENT ON COLUMN users.aptos_wallet_id IS 'Crossmint wallet ID for API operations';

COMMENT ON COLUMN operator_wallets.usdt_balance IS 'USDT balance on Aptos blockchain (6 decimals)';
COMMENT ON COLUMN operator_wallets.aptos_wallet_address IS 'Aptos wallet address for this operator wallet';

COMMENT ON TABLE usdt_transactions IS 'Complete history of all USDT operations on Aptos blockchain';
COMMENT ON TABLE usdt_revenue_distributions IS 'Daily revenue distribution in both USD and USDT';
COMMENT ON TABLE wallet_sync_status IS 'Tracks synchronization between USD and USDT balances';

-- ============================================================================
-- INITIAL DATA SETUP
-- ============================================================================

-- Set the USDT contract address for all existing records
UPDATE users SET usdt_contract = '0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT' WHERE usdt_contract IS NULL;
UPDATE operator_wallets SET usdt_contract = '0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT' WHERE usdt_contract IS NULL;
UPDATE transactions SET usdt_contract = '0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT' WHERE usdt_contract IS NULL;
