-- Aptos Wallet Schema - Core wallet creation only
-- Focused on wallet addresses without token minting/distribution

-- Add Aptos wallet fields to sportsbook_operators table
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;

-- Add Aptos wallet fields to users table  
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;

-- Add Aptos transaction fields to bets table (for future on-chain betting)
ALTER TABLE bets ADD COLUMN IF NOT EXISTS aptos_transaction_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS on_chain BOOLEAN DEFAULT FALSE;
ALTER TABLE bets ADD COLUMN IF NOT EXISTS settlement_tx_hash VARCHAR(66);

-- Create table for Aptos transactions (basic transaction tracking)
CREATE TABLE IF NOT EXISTS aptos_transactions (
    id SERIAL PRIMARY KEY,
    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'wallet_creation', 'bet_placement', 'settlement', 'transfer'
    from_address VARCHAR(66),
    to_address VARCHAR(66),
    amount DECIMAL(18,8),
    token_type VARCHAR(10) DEFAULT 'APT', -- APT for native Aptos coin
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'confirmed', 'failed'
    block_number BIGINT,
    gas_used BIGINT,
    gas_price DECIMAL(18,8),
    operator_id INTEGER REFERENCES sportsbook_operators(id),
    user_id INTEGER REFERENCES users(id),
    bet_id INTEGER REFERENCES bets(id),
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_aptos_operators_wallet ON sportsbook_operators(aptos_wallet_address);
CREATE INDEX IF NOT EXISTS idx_aptos_users_wallet ON users(aptos_wallet_address);
CREATE INDEX IF NOT EXISTS idx_aptos_bets_tx_hash ON bets(aptos_transaction_hash);
CREATE INDEX IF NOT EXISTS idx_aptos_transactions_hash ON aptos_transactions(transaction_hash);
CREATE INDEX IF NOT EXISTS idx_aptos_transactions_status ON aptos_transactions(status);
CREATE INDEX IF NOT EXISTS idx_aptos_transactions_type ON aptos_transactions(transaction_type);

-- Create function to log Aptos transactions
CREATE OR REPLACE FUNCTION log_aptos_transaction(
    p_tx_hash VARCHAR(66),
    p_tx_type VARCHAR(50),
    p_from_address VARCHAR(66),
    p_to_address VARCHAR(66),
    p_amount DECIMAL(18,8),
    p_operator_id INTEGER DEFAULT NULL,
    p_user_id INTEGER DEFAULT NULL,
    p_bet_id INTEGER DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    transaction_id INTEGER;
BEGIN
    INSERT INTO aptos_transactions (
        transaction_hash, transaction_type, from_address, to_address,
        amount, operator_id, user_id, bet_id, created_at
    ) VALUES (
        p_tx_hash, p_tx_type, p_from_address, p_to_address,
        p_amount, p_operator_id, p_user_id, p_bet_id, NOW()
    )
    RETURNING id INTO transaction_id;
    
    RETURN transaction_id;
END;
$$ LANGUAGE plpgsql;

-- Create function to update transaction status
CREATE OR REPLACE FUNCTION update_aptos_transaction_status(
    p_tx_hash VARCHAR(66),
    p_status VARCHAR(20),
    p_block_number BIGINT DEFAULT NULL,
    p_gas_used BIGINT DEFAULT NULL,
    p_gas_price DECIMAL(18,8) DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE aptos_transactions 
    SET 
        status = p_status,
        block_number = COALESCE(p_block_number, block_number),
        gas_used = COALESCE(p_gas_used, gas_used),
        gas_price = COALESCE(p_gas_price, gas_price),
        confirmed_at = CASE WHEN p_status = 'confirmed' THEN NOW() ELSE confirmed_at END
    WHERE transaction_hash = p_tx_hash;
END;
$$ LANGUAGE plpgsql;

-- Insert initial migration record
INSERT INTO aptos_transactions (
    transaction_hash, transaction_type, status, created_at
) VALUES (
    'WALLET_SCHEMA_INIT_' || EXTRACT(EPOCH FROM NOW())::TEXT,
    'schema_migration',
    'confirmed',
    NOW()
) ON CONFLICT DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE aptos_transactions IS 'Records Aptos blockchain transactions for wallet operations';
COMMENT ON COLUMN sportsbook_operators.aptos_wallet_address IS 'Operator Aptos wallet address from Crossmint';
COMMENT ON COLUMN sportsbook_operators.aptos_wallet_id IS 'Crossmint wallet ID for operator';
COMMENT ON COLUMN users.aptos_wallet_address IS 'User Aptos wallet address from Crossmint';
COMMENT ON COLUMN users.aptos_wallet_id IS 'Crossmint wallet ID for user';
COMMENT ON COLUMN bets.aptos_transaction_hash IS 'Transaction hash for on-chain bets';
COMMENT ON COLUMN bets.on_chain IS 'Whether this bet was placed on Aptos blockchain';

-- Create view for Web3 enabled operators
CREATE OR REPLACE VIEW web3_operators AS
SELECT 
    id,
    sportsbook_name,
    subdomain,
    aptos_wallet_address,
    web3_enabled,
    created_at
FROM sportsbook_operators 
WHERE web3_enabled = TRUE AND aptos_wallet_address IS NOT NULL;

-- Create view for Web3 enabled users
CREATE OR REPLACE VIEW web3_users AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.aptos_wallet_address,
    u.web3_enabled,
    u.sportsbook_operator_id,
    so.sportsbook_name,
    u.created_at
FROM users u
JOIN sportsbook_operators so ON u.sportsbook_operator_id = so.id
WHERE u.web3_enabled = TRUE AND u.aptos_wallet_address IS NOT NULL;
