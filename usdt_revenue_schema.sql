-- USDT Revenue Distribution Schema
-- Tracks daily revenue distributions in both USD and USDT

-- Table to track USDT revenue distributions
CREATE TABLE IF NOT EXISTS usdt_revenue_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    distribution_date DATE NOT NULL,
    
    -- Profit amounts
    total_profit_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    total_profit_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    
    -- Bookmaker share
    bookmaker_share_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    bookmaker_share_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    
    -- Community share
    community_share_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    community_share_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    
    -- Kryzel platform fee
    kryzel_fee_usd DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    kryzel_fee_usdt DECIMAL(18,6) NOT NULL DEFAULT 0.000000,
    
    -- Transaction tracking
    revenue_wallet_tx_hash VARCHAR(66), -- Aptos transaction hash for revenue wallet transfer
    community_wallet_tx_hash VARCHAR(66), -- Aptos transaction hash for community wallet transfer
    
    -- Status and metadata
    status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed
    error_message TEXT,
    usdt_contract VARCHAR(255), -- USDT contract address used
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    -- Foreign key
    FOREIGN KEY (operator_id) REFERENCES sportsbook_operators(id),
    
    -- Unique constraint to prevent duplicate distributions
    UNIQUE(operator_id, distribution_date)
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_usdt_revenue_operator_date 
ON usdt_revenue_distributions(operator_id, distribution_date);

CREATE INDEX IF NOT EXISTS idx_usdt_revenue_status 
ON usdt_revenue_distributions(status);

-- Table to track individual USDT transactions for revenue distribution
CREATE TABLE IF NOT EXISTS usdt_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Entity information
    entity_type VARCHAR(20) NOT NULL, -- 'user', 'operator'
    entity_id INTEGER NOT NULL,
    wallet_type VARCHAR(50), -- For operators: 'bookmaker_capital', 'liquidity_pool', 'revenue', 'community'
    
    -- Transaction details
    transaction_type VARCHAR(30) NOT NULL, -- 'mint', 'transfer', 'bet', 'settlement', 'revenue_distribution'
    from_wallet VARCHAR(66), -- Aptos wallet address (sender)
    to_wallet VARCHAR(66), -- Aptos wallet address (recipient)
    usdt_amount DECIMAL(18,6) NOT NULL,
    
    -- Blockchain tracking
    aptos_transaction_hash VARCHAR(66),
    usdt_contract VARCHAR(255) NOT NULL,
    block_height INTEGER,
    
    -- Status and metadata
    status VARCHAR(20) DEFAULT 'pending', -- pending, confirmed, failed
    error_message TEXT,
    description TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP
);

-- Indexes for USDT transactions
CREATE INDEX IF NOT EXISTS idx_usdt_tx_entity 
ON usdt_transactions(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_usdt_tx_type 
ON usdt_transactions(transaction_type);

CREATE INDEX IF NOT EXISTS idx_usdt_tx_hash 
ON usdt_transactions(aptos_transaction_hash);

CREATE INDEX IF NOT EXISTS idx_usdt_tx_status 
ON usdt_transactions(status);

-- View to get revenue distribution summary
CREATE VIEW IF NOT EXISTS revenue_distribution_summary AS
SELECT 
    urd.operator_id,
    so.sportsbook_name,
    urd.distribution_date,
    urd.total_profit_usd,
    urd.total_profit_usdt,
    urd.bookmaker_share_usd + urd.community_share_usd + urd.kryzel_fee_usd as total_distributed_usd,
    urd.bookmaker_share_usdt + urd.community_share_usdt + urd.kryzel_fee_usdt as total_distributed_usdt,
    urd.status,
    urd.created_at,
    urd.processed_at,
    CASE 
        WHEN urd.bookmaker_share_usdt > 0 THEN 'hybrid'
        ELSE 'traditional'
    END as distribution_type
FROM usdt_revenue_distributions urd
JOIN sportsbook_operators so ON urd.operator_id = so.id
ORDER BY urd.distribution_date DESC, urd.operator_id;

-- View to get wallet balance synchronization status
CREATE VIEW IF NOT EXISTS wallet_sync_status AS
SELECT 
    'user' as entity_type,
    u.id as entity_id,
    u.username as entity_name,
    u.sportsbook_operator_id as operator_id,
    u.balance as usd_balance,
    u.usdt_balance,
    u.web3_enabled,
    ABS(u.balance - COALESCE(u.usdt_balance, 0)) as balance_difference,
    CASE 
        WHEN ABS(u.balance - COALESCE(u.usdt_balance, 0)) < 0.01 THEN 'synchronized'
        ELSE 'out_of_sync'
    END as sync_status
FROM users u
WHERE u.web3_enabled = TRUE

UNION ALL

SELECT 
    'operator' as entity_type,
    ow.operator_id as entity_id,
    ow.wallet_type as entity_name,
    ow.operator_id,
    ow.current_balance as usd_balance,
    ow.usdt_balance,
    CASE WHEN ow.aptos_wallet_address IS NOT NULL THEN TRUE ELSE FALSE END as web3_enabled,
    ABS(ow.current_balance - COALESCE(ow.usdt_balance, 0)) as balance_difference,
    CASE 
        WHEN ABS(ow.current_balance - COALESCE(ow.usdt_balance, 0)) < 0.01 THEN 'synchronized'
        ELSE 'out_of_sync'
    END as sync_status
FROM operator_wallets ow
WHERE ow.aptos_wallet_address IS NOT NULL;

-- Trigger to update processed_at timestamp when status changes to 'completed'
CREATE TRIGGER IF NOT EXISTS update_usdt_revenue_processed_at
    AFTER UPDATE OF status ON usdt_revenue_distributions
    WHEN NEW.status = 'completed' AND OLD.status != 'completed'
BEGIN
    UPDATE usdt_revenue_distributions 
    SET processed_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;
