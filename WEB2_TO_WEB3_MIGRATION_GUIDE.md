# 🔄 Web2 to Web3 Migration Guide

This document provides a comprehensive guide for migrating the Kryzel Sports Betting Platform from Web2 to Web3, including all API flows, wallet management, and blockchain integration points.

## 📋 Table of Contents

1. [Operator Registration Flow](#1-operator-registration-flow)
2. [User Registration Flow](#2-user-registration-flow)
3. [Betting Flow & Wallet Management](#3-betting-flow--wallet-management)
4. [Bet Settlement System](#4-bet-settlement-system)
5. [Operator Wallet Management](#5-operator-wallet-management)
6. [Web3 Integration Points](#6-web3-integration-points)

---

## 1. Operator Registration Flow

### Overview
Operators register to create their own branded sportsbook with custom subdomain and admin access.
  
### API Flow

#### 1.1 Initial Registration Request
**Endpoint:** `POST /api/register-sportsbook`  
**File:** `src/routes/sportsbook_registration.py`  
**Function:** `register_sportsbook()`

```python
# Request Body
{
    
    "sportsbook_name": "Megabook Sports",
    "subdomain": "megabook",
    "admin_username": "admin",
    "admin_email": "admin@megabook.com",
    "admin_password": "secure_password",
    "theme_preferences": {
        "primary_color": "#1a73e8",
        "secondary_color": "#34a853"
    }
}
```

#### 1.2 Database Operations
**File:** `src/routes/sportsbook_registration.py`  
**Functions:**
- `create_operator()` - Creates sportsbook_operators record
- `create_admin_user()` - Creates admin user account
- `setup_operator_wallets()` - Initializes 4 wallet system

```python
# Database Tables Created:
# 1. sportsbook_operators
# 2. users (admin user)
# 3. operator_wallets (4 wallets: bookmaker_capital, liquidity_pool, revenue, community)
```

#### 1.3 Wallet Initialization
**File:** `src/routes/sportsbook_registration.py`  
**Function:** `setup_operator_wallets()`

```python
# Initial Wallet Balances:
wallets = [
    {"wallet_type": "bookmaker_capital", "current_balance": 10000.0},
    {"wallet_type": "liquidity_pool", "current_balance": 40000.0},
    {"wallet_type": "revenue", "current_balance": 0.0},
    {"wallet_type": "community", "current_balance": 0.0}
]
```

#### 1.4 Response
**Success Response:**
```json
{
    "success": true,
    "operator_id": 123,
    "subdomain": "megabook",
    "admin_url": "https://megabook.yourdomain.com/admin",
    "user_url": "https://megabook.yourdomain.com/login"
}
```

---

## 2. User Registration Flow

### Overview
End users register to place bets on the operator's sportsbook platform.

### API Flow

#### 2.1 User Registration Request
**Endpoint:** `POST /{subdomain}/api/register`  
**File:** `src/routes/tenant_auth.py`  
**Function:** `register_user()`

```python
# Request Body
{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "user_password",
    "initial_deposit": 100.0  # Optional initial wallet funding
}
```

#### 2.2 User Creation & Wallet Setup
**File:** `src/routes/tenant_auth.py`  
**Functions:**
- `create_user()` - Creates user record
- `create_user_wallet()` - Creates user wallet

```python
# Database Tables:
# 1. users (with sportsbook_operator_id)
# 2. user_wallets (user's betting wallet)
```

#### 2.3 Initial Wallet Funding
**File:** `src/routes/tenant_auth.py`  
**Function:** `fund_user_wallet()`

```python
# If initial_deposit provided:
# 1. Create user_wallets record
# 2. Set initial balance
# 3. Log transaction
```

#### 2.4 Response
**Success Response:**
```json
{
    "success": true,
    "user_id": 456,
    "username": "john_doe",
    "wallet_balance": 100.0,
    "login_url": "https://megabook.yourdomain.com/login"
}
```

---

## 3. Betting Flow & Wallet Management

### Overview
Users place bets, which immediately deduct from their wallet balance and create bet records.

### API Flow

#### 3.1 Place Bet Request
**Endpoint:** `POST /{subdomain}/api/place-bet`  
**File:** `src/routes/betting.py`  
**Function:** `place_bet()`

```python
# Request Body
{
    "event_id": "match_123",
    "selection": "home_win",
    "odds": 2.5,
    "stake": 50.0,
    "bet_type": "match_winner"
}
```

#### 3.2 Wallet Balance Check & Deduction
**File:** `src/routes/betting.py`  
**Functions:**
- `check_user_balance()` - Validates sufficient funds
- `deduct_user_balance()` - Deducts stake from user wallet
- `create_bet_record()` - Creates bet record

```python
# Wallet Operations:
# 1. Check user_wallets.current_balance >= stake
# 2. Deduct stake from user_wallets.current_balance
# 3. Create bet record with status='pending'
# 4. Calculate potential_return = stake * odds
```

#### 3.3 Bet Record Creation
**File:** `src/routes/betting.py`  
**Function:** `create_bet_record()`

```python
# Database Record:
bet_data = {
    "user_id": user_id,
    "sportsbook_operator_id": operator_id,
    "event_id": event_id,
    "selection": selection,
    "odds": odds,
    "stake": stake,
    "potential_return": stake * odds,
    "actual_return": 0.0,  # Set after settlement
    "status": "pending",
    "bet_type": bet_type,
    "placed_at": datetime.now()
}
```

#### 3.4 Response
**Success Response:**
```json
{
    "success": true,
    "bet_id": 789,
    "remaining_balance": 450.0,
    "bet_status": "pending",
    "potential_return": 125.0
}
```

---

## 4. Bet Settlement System

### Overview
Bets are settled either automatically (via AI detection) or manually (by admin), updating wallet balances accordingly.

### 4.1 Automatic Settlement

#### API Trigger
**File:** `src/bet_settlement_service.py`  
**Class:** `BetSettlementService`  
**Function:** `_auto_settle_bets_for_match()`

```python
# Triggered by:
# 1. Scheduled job (every 5 minutes)
# 2. Match result detection via Goalserve API
# 3. Manual trigger by admin
```

#### Settlement Process
**File:** `src/bet_settlement_service.py`  
**Functions:**
- `_detect_match_result()` - AI-powered result detection
- `_settle_bet()` - Updates bet status and user wallet
- `_update_operator_revenues()` - Updates operator revenue

```python
# Settlement Logic:
if match_result == "home_win" and bet.selection == "home_win":
    # Winning bet
    bet.status = "won"
    bet.actual_return = bet.potential_return
    user_wallet.balance += bet.actual_return
    operator_revenue -= (bet.actual_return - bet.stake)
    
elif match_result != bet.selection:
    # Losing bet
    bet.status = "lost"
    bet.actual_return = 0.0
    operator_revenue += bet.stake
    
else:
    # Void bet (refund)
    bet.status = "void"
    bet.actual_return = bet.stake
    user_wallet.balance += bet.stake
```

#### Wallet Updates
**File:** `src/bet_settlement_service.py`  
**Function:** `_update_operator_revenue()`

```python
# Operator Revenue Calculation:
total_revenue = (
    SUM(CASE WHEN status='lost' THEN stake ELSE 0 END) -  # Money from losing bets
    SUM(CASE WHEN status='won' THEN (actual_return - stake) ELSE 0 END)  # Payouts to winners
)
```

### 4.2 Manual Settlement

#### API Endpoint
**Endpoint:** `POST /admin/settle-bet`  
**File:** `src/routes/rich_admin_interface.py`  
**Function:** `manual_settle_bets()`

```python
# Request Body
{
    "bet_ids": [789, 790, 791],
    "settlement_type": "manual",
    "admin_notes": "Settled after manual review"
}
```

#### Manual Settlement Process
**File:** `src/routes/rich_admin_interface.py`  
**Functions:**
- `manual_settle_bets()` - Admin-triggered settlement
- `update_operator_revenue()` - Updates operator revenue after settlement

```python
# Manual Settlement Steps:
# 1. Validate admin permissions
# 2. Update bet status and actual_return
# 3. Update user wallet balance
# 4. Recalculate operator revenue
# 5. Update sportsbook_operators.total_revenue
```

---

## 5. Operator Wallet Management

### Overview
The `update_operator_wallets.py` script processes daily revenue calculations and updates the 4-wallet system.

### 5.1 Daily Revenue Calculator

#### Script Execution
**File:** `daily_revenue_calculator.py`  
**Function:** `calculate_daily_revenue()`

```python
# Daily Process:
# 1. Get current total_revenue from sportsbook_operators
# 2. Get previous total_revenue from revenue_calculations
# 3. Calculate today's_profit = current - previous
# 4. Apply revenue distribution logic
# 5. Insert record into revenue_calculations
```

#### Revenue Distribution Logic
**File:** `daily_revenue_calculator.py`  
**Function:** `calculate_revenue_distribution()`

```python
# Profit Days (profit > 0):
bookmaker_own_share = 90% * (profit * bookmaker_ratio) + 60% * (profit * liquidity_ratio)
kryzel_fee_from_own = 10% * profit
community_share_30 = 30% * (profit * liquidity_ratio)
remaining_profit = 0.0

# Loss Days (profit < 0):
bookmaker_own_share = 95% * (profit * bookmaker_ratio) + 65% * (profit * liquidity_ratio)
kryzel_fee_from_own = 0% * profit
community_share_30 = 35% * (profit * liquidity_ratio)
remaining_profit = 0.0
```

### 5.2 Wallet Updater Script

#### Script Execution
**File:** `update_operator_wallets.py`  
**Function:** `update_operator_wallets()`

```python
# Process:
# 1. Find unprocessed revenue_calculations (metadata='false')
# 2. Update operator_wallets based on revenue distribution
# 3. Handle surplus and deficit scenarios
# 4. Mark calculations as processed (metadata='true')
```

#### Wallet Update Logic
**File:** `update_operator_wallets.py`  
**Function:** `process_revenue_calculation()`

```python
# Bookmaker Capital Update:
new_bookmaker_capital = current_balance + bookmaker_own_share
if new_bookmaker_capital > 10000:
    surplus = new_bookmaker_capital - 10000
    bookmaker_capital = 10000
    revenue_wallet += surplus
else:
    bookmaker_capital = new_bookmaker_capital

# Liquidity Pool Update:
liquidity_pool += community_share_30
if liquidity_pool < 0:
    liquidity_pool = 0  # Cap at zero
```

### 5.3 Four Wallet System

#### Wallet Types
**File:** `src/routes/sportsbook_registration.py`  
**Function:** `setup_operator_wallets()`

```python
wallets = [
    {
        "wallet_type": "bookmaker_capital",
        "current_balance": 10000.0,
        "description": "Operator's own capital (capped at $10,000)"
    },
    {
        "wallet_type": "liquidity_pool", 
        "current_balance": 40000.0,
        "description": "Community liquidity pool"
    },
    {
        "wallet_type": "revenue",
        "current_balance": 0.0,
        "description": "Surplus revenue from bookmaker capital"
    },
    {
        "wallet_type": "community",
        "current_balance": 0.0,
        "description": "Community share of profits"
    }
]
```

---

## 6. Web3 Integration Points

### 6.1 Blockchain Wallet Integration

#### User Wallet Connection
**File:** `src/routes/tenant_auth.py` (Future Enhancement)
**Function:** `connect_web3_wallet()`

```python
# Web3 Integration Points:
# 1. MetaMask wallet connection
# 2. Wallet signature verification
# 3. On-chain balance checking
# 4. Smart contract interaction
```

#### Smart Contract Integration
**File:** `src/services/web3_service.py` (To be created)
**Functions:**
- `deploy_betting_contract()` - Deploy betting smart contract
- `place_bet_on_chain()` - Place bet via smart contract
- `settle_bet_on_chain()` - Settle bet on blockchain
- `withdraw_funds()` - Withdraw to user's wallet

### 6.2 Token Economics

#### Revenue Token Distribution
**File:** `src/services/token_service.py` (To be created)
**Functions:**
- `mint_revenue_tokens()` - Mint tokens for revenue share
- `distribute_tokens()` - Distribute to community holders
- `burn_tokens()` - Burn tokens for deflationary mechanism

### 6.3 Decentralized Governance

#### DAO Integration
**File:** `src/services/dao_service.py` (To be created)
**Functions:**
- `create_proposal()` - Create governance proposals
- `vote_on_proposal()` - Vote on platform changes
- `execute_proposal()` - Execute approved proposals

---

## 🔧 Implementation Checklist

### Phase 1: Core Web3 Integration
- [ ] Implement MetaMask wallet connection
- [ ] Create smart contract for betting
- [ ] Integrate on-chain balance checking
- [ ] Add wallet signature verification

### Phase 2: Token Economics
- [ ] Deploy revenue sharing token
- [ ] Implement token distribution logic
- [ ] Add staking mechanisms
- [ ] Create token burn functionality

### Phase 3: Decentralized Features
- [ ] Implement DAO governance
- [ ] Add community voting
- [ ] Create proposal system
- [ ] Implement decentralized settlement

### Phase 4: Advanced Features
- [ ] Cross-chain compatibility
- [ ] Layer 2 scaling solutions
- [ ] NFT integration for special bets
- [ ] DeFi yield farming integration

---

## 📚 API Reference Summary

### Core APIs for Web3 Migration

| API Endpoint | File | Purpose | Web3 Integration |
|--------------|------|---------|------------------|
| `POST /api/register-sportsbook` | `sportsbook_registration.py` | Operator registration | Smart contract deployment |
| `POST /{subdomain}/api/register` | `tenant_auth.py` | User registration | Wallet connection |
| `POST /{subdomain}/api/place-bet` | `betting.py` | Place bet | On-chain bet placement |
| `POST /admin/settle-bet` | `rich_admin_interface.py` | Manual settlement | Smart contract settlement |
| `POST /api/update-wallets` | `update_operator_wallets.py` | Wallet updates | Token distribution |

### Database Tables for Web3

| Table | Purpose | Web3 Enhancement |
|-------|---------|------------------|
| `sportsbook_operators` | Operator data | Add contract_address |
| `users` | User accounts | Add wallet_address |
| `operator_wallets` | 4-wallet system | Add token_balances |
| `bets` | Betting records | Add transaction_hash |
| `revenue_calculations` | Daily revenue | Add token_distributions |

---

## 🚀 Getting Started with Web3 Migration

1. **Set up Web3 development environment**
2. **Deploy smart contracts for betting and revenue sharing**
3. **Integrate MetaMask wallet connection**
4. **Implement on-chain balance checking**
5. **Add smart contract settlement logic**
6. **Create token distribution system**
7. **Implement DAO governance features**

---

*This guide provides the foundation for migrating the Kryzel Sports Betting Platform to Web3 while maintaining all existing functionality and adding decentralized features.*
