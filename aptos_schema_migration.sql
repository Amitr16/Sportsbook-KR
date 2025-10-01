-- Aptos Web3 Migration Schema
-- Based on WEB2_TO_WEB3_MIGRATION_GUIDE.md requirements

-- Add Aptos wallet fields to sportsbook_operators table
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS revenue_token_address VARCHAR(66);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS revenue_token_symbol VARCHAR(10);
ALTER TABLE sportsbook_operators ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;

-- Add Aptos wallet fields to users table  
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_address VARCHAR(66);
ALTER TABLE users ADD COLUMN IF NOT EXISTS aptos_wallet_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS web3_enabled BOOLEAN DEFAULT FALSE;

-- Add Aptos transaction fields to bets table
ALTER TABLE bets ADD COLUMN IF NOT EXISTS aptos_transaction_hash VARCHAR(66);
ALTER TABLE bets ADD COLUMN IF NOT EXISTS on_chain BOOLEAN DEFAULT FALSE;
ALTER TABLE bets ADD COLUMN IF NOT EXISTS settlement_tx_hash VARCHAR(66);

-- Add token tracking to operator_wallets table
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS aptos_token_balance DECIMAL(18,8) DEFAULT 0;
ALTER TABLE operator_wallets ADD COLUMN IF NOT EXISTS token_contract_address VARCHAR(66);

-- Add token distribution tracking to revenue_calculations table
ALTER TABLE revenue_calculations ADD COLUMN IF NOT EXISTS community_tokens_distributed DECIMAL(18,8) DEFAULT 0;
ALTER TABLE revenue_calculations ADD COLUMN IF NOT EXISTS token_distribution_tx_hash VARCHAR(66);

-- Create new table for Aptos token holders
CREATE TABLE IF NOT EXISTS aptos_token_holders (
    id SERIAL PRIMARY KEY,
    operator_id INTEGER REFERENCES sportsbook_operators(id),
    user_id INTEGER REFERENCES users(id),
    wallet_address VARCHAR(66) NOT NULL,
    token_contract_address VARCHAR(66) NOT NULL,
    token_balance DECIMAL(18,8) DEFAULT 0,
    total_earned DECIMAL(18,8) DEFAULT 0,
    last_distribution_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create new table for Aptos transactions
CREATE TABLE IF NOT EXISTS aptos_transactions (
    id SERIAL PRIMARY KEY,
    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'wallet_creation', 'token_mint', 'bet_placement', 'settlement', 'token_transfer'
    from_address VARCHAR(66),
    to_address VARCHAR(66),
    amount DECIMAL(18,8),
    token_address VARCHAR(66),
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

-- Create new table for token distributions
CREATE TABLE IF NOT EXISTS token_distributions (
    id SERIAL PRIMARY KEY,
    operator_id INTEGER REFERENCES sportsbook_operators(id),
    revenue_calculation_id INTEGER REFERENCES revenue_calculations(id),
    distribution_date DATE NOT NULL,
    total_amount_distributed DECIMAL(18,8) NOT NULL,
    token_contract_address VARCHAR(66) NOT NULL,
    transaction_hash VARCHAR(66),
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    recipients_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Create new table for individual token distribution records
CREATE TABLE IF NOT EXISTS token_distribution_details (
    id SERIAL PRIMARY KEY,
    distribution_id INTEGER REFERENCES token_distributions(id),
    user_id INTEGER REFERENCES users(id),
    wallet_address VARCHAR(66) NOT NULL,
    amount DECIMAL(18,8) NOT NULL,
    transaction_hash VARCHAR(66),
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_aptos_operators_wallet ON sportsbook_operators(aptos_wallet_address);
CREATE INDEX IF NOT EXISTS idx_aptos_users_wallet ON users(aptos_wallet_address);
CREATE INDEX IF NOT EXISTS idx_aptos_bets_tx_hash ON bets(aptos_transaction_hash);
CREATE INDEX IF NOT EXISTS idx_aptos_transactions_hash ON aptos_transactions(transaction_hash);
CREATE INDEX IF NOT EXISTS idx_aptos_transactions_status ON aptos_transactions(status);
CREATE INDEX IF NOT EXISTS idx_token_holders_operator ON aptos_token_holders(operator_id);
CREATE INDEX IF NOT EXISTS idx_token_distributions_date ON token_distributions(distribution_date);

-- Create function to update token holder balances
CREATE OR REPLACE FUNCTION update_token_holder_balance(
    p_operator_id INTEGER,
    p_user_id INTEGER,
    p_wallet_address VARCHAR(66),
    p_token_address VARCHAR(66),
    p_amount DECIMAL(18,8)
) RETURNS VOID AS $$
BEGIN
    INSERT INTO aptos_token_holders (
        operator_id, user_id, wallet_address, token_contract_address, 
        token_balance, total_earned, updated_at
    ) VALUES (
        p_operator_id, p_user_id, p_wallet_address, p_token_address,
        p_amount, p_amount, NOW()
    )
    ON CONFLICT (operator_id, user_id, token_contract_address) 
    DO UPDATE SET
        token_balance = aptos_token_holders.token_balance + p_amount,
        total_earned = aptos_token_holders.total_earned + p_amount,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update token balances when distributions are completed
CREATE OR REPLACE FUNCTION trigger_update_token_balances() RETURNS TRIGGER AS $$
BEGIN
    -- Update token holder records when a distribution detail is completed
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        PERFORM update_token_holder_balance(
            (SELECT d.operator_id FROM token_distributions d WHERE d.id = NEW.distribution_id),
            NEW.user_id,
            NEW.wallet_address,
            (SELECT d.token_contract_address FROM token_distributions d WHERE d.id = NEW.distribution_id),
            NEW.amount
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER token_distribution_update_trigger
    AFTER UPDATE ON token_distribution_details
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_token_balances();

-- Insert initial migration record
INSERT INTO aptos_transactions (
    transaction_hash, transaction_type, status, created_at
) VALUES (
    'MIGRATION_INIT_' || EXTRACT(EPOCH FROM NOW())::TEXT,
    'schema_migration',
    'completed',
    NOW()
) ON CONFLICT DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE aptos_token_holders IS 'Tracks token balances for revenue sharing participants';
COMMENT ON TABLE aptos_transactions IS 'Records all Aptos blockchain transactions';
COMMENT ON TABLE token_distributions IS 'Tracks batch token distribution events';
COMMENT ON TABLE token_distribution_details IS 'Individual token distribution records';

COMMENT ON COLUMN sportsbook_operators.aptos_wallet_address IS 'Operator Aptos wallet address from Crossmint';
COMMENT ON COLUMN sportsbook_operators.revenue_token_address IS 'Address of operator revenue sharing token contract';
COMMENT ON COLUMN users.aptos_wallet_address IS 'User Aptos wallet address from Crossmint';
COMMENT ON COLUMN bets.aptos_transaction_hash IS 'Transaction hash for on-chain bets';
COMMENT ON COLUMN bets.on_chain IS 'Whether this bet was placed on Aptos blockchain';
