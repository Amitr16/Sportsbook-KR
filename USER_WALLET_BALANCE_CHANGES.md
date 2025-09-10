# User Wallet Balance Changes Documentation

This document outlines all events that result in changes to a user's cash balance in their wallet, including the specific files, functions, and APIs involved.

## Overview

User wallet balance changes occur through various transaction types tracked in the `transactions` table. Each transaction includes:
- `amount`: Positive for credits, negative for debits
- `transaction_type`: Type of transaction
- `balance_before`: User balance before the transaction
- `balance_after`: User balance after the transaction
- `description`: Human-readable description

## Transaction Types

### 0. **ACCOUNT_CREATION** - New User Registration (Credit)
**Effect**: Sets initial balance for new user accounts

#### Files & Functions:
- **File**: `src/routes/auth.py`
- **Function**: `register()` (lines 433-489)
- **API**: `POST /api/auth/register`
- **Function**: `google_callback()` (lines 150-489)
- **API**: `GET /api/auth/google/callback`
- **File**: `src/routes/tenant_auth.py`
- **Function**: `tenant_register()` (lines 38-137)
- **API**: `POST /api/auth/<subdomain>/register`

#### Code Location:
```python
# Standard registration
try:
    from src.routes.rich_admin_interface import get_default_user_balance
    default_balance = get_default_user_balance(1) if hasattr(current_app, 'db') else 1000.0
except Exception as e:
    default_balance = 1000.0  # Fall back to default

user = User(
    username=username,
    email=email,
    password_hash=password_hash,
    balance=default_balance  # Configurable starting balance
)

# Google OAuth registration
try:
    from src.routes.rich_admin_interface import get_default_user_balance
    default_balance = get_default_user_balance(operator_id)
except Exception as e:
    default_balance = 1000.0  # Fall back to default

conn.execute(
    """
    INSERT INTO users (username, email, password_hash, balance, is_active, created_at, last_login, sportsbook_operator_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """,
    (username, email, generate_password_hash(f"google:{sub}"), default_balance, True,
     datetime.datetime.utcnow(), datetime.datetime.utcnow(), operator_id),
)

# Tenant-specific registration with custom default balance
try:
    from src.routes.rich_admin_interface import get_default_user_balance
    default_balance = get_default_user_balance(operator['id'])
except Exception as e:
    default_balance = 1000.0  # Fall back to default

new_user = User(
    username=username,
    email=email,
    password_hash=password_hash,
    balance=default_balance,  # Custom default balance
    sportsbook_operator_id=operator['id'],
    is_active=True,
    created_at=datetime.utcnow()
)
```

#### Default Balance Logic:
- **Standard Registration**: Uses `get_default_user_balance(1)` (operator 1) with $1000.00 fallback
- **Google OAuth**: Uses `get_default_user_balance(operator_id)` for the specific operator
- **Tenant Registration**: Uses `get_default_user_balance(operator_id)` for the specific operator
- **Fallback**: $1000.00 if no custom setting found or function fails

#### Default Balance Configuration:
- **File**: `src/routes/rich_admin_interface.py`
- **Function**: `get_default_user_balance()` (lines 52-77)
- **Storage**: Stored in `sportsbook_operators.settings` JSON field
- **Key**: `default_user_balance`

### 1. **BET** - Bet Placement (Debit)
**Effect**: Decreases user balance by stake amount

#### Files & Functions:
- **File**: `src/routes/betting.py`
- **Function**: `place_bet()` (lines 245-390)
- **API**: `POST /api/betting/place`
- **Function**: `place_combo_bet()` (lines 392-551)
- **API**: `POST /api/betting/place-combo`

#### Code Location:
```python
# Deduct balance on the ORM user object
user.balance -= stake

# Create transaction record
transaction = Transaction(
    user_id=user.id,
    bet_id=bet.id,
    amount=-stake,  # Negative amount
    transaction_type='bet',
    description=f'Bet placement - {selection}',
    balance_before=user.balance + stake,
    balance_after=user.balance
)
```

### 2. **WIN** - Bet Settlement (Credit)
**Effect**: Increases user balance by actual return amount

#### Files & Functions:
- **File**: `src/bet_settlement_service.py`
- **Function**: `_auto_settle_bets_for_match()` (lines 753-819)
- **File**: `src/routes/betting.py`
- **Function**: `settle_bets()` (lines 755-811)
- **API**: `POST /api/betting/settle`

#### Code Location:
```python
# Update user balance - EXPLICIT WALLET UPDATE
user = current_app.db.session.get(User, bet.user_id)
if user:
    balance_before = user.balance or 0
    user.balance = balance_before + bet.actual_return
    balance_after = user.balance
    
    # Create transaction record
    transaction = Transaction(
        user_id=bet.user_id,
        bet_id=bet.id,
        amount=bet.actual_return,  # Positive amount
        transaction_type='win',
        description=f'💰 Won bet on {bet.match_name} - {bet.selection}',
        balance_before=balance_before,
        balance_after=balance_after
    )
```

### 3. **REFUND** - Bet Cancellation (Credit)
**Effect**: Increases user balance by refunded stake amount

#### Files & Functions:
- **File**: `src/routes/rich_admin_interface.py`
- **Function**: `reset_all_users()` (lines 884-929)
- **API**: `POST /<subdomain>/admin/api/users/reset`

#### Code Location:
```python
# Create refund transaction for this bet
conn.execute(
    "INSERT INTO transactions (user_id, bet_id, amount, transaction_type, description, balance_before, balance_after, created_at) VALUES (?, ?, ?, 'refund', ?, ?, ?, CURRENT_TIMESTAMP)",
    (bet['user_id'], bet['id'], bet['stake'], f'Bet cancelled - {bet["match_name"]} (Admin Reset)', bet['stake'], bet['stake'] * 2)
)
```

### 4. **DEPOSIT** - Manual Balance Addition (Credit)
**Effect**: Increases user balance by specified amount

#### Files & Functions:
- **File**: `src/routes/tenant_admin.py`
- **Function**: `update_user_balance()` (lines 264-329)
- **API**: `POST /api/admin/<subdomain>/update-user-balance`

#### Code Location:
```python
# Calculate new balance
current_balance = user['balance']
if action == 'add':
    new_balance = current_balance + amount
else:
    new_balance = max(0, current_balance - amount)  # Don't allow negative balance

# Update balance
conn.execute("""
    UPDATE users 
    SET balance = ?
    WHERE id = ?
""", (new_balance, user_id))
```

### 5. **WITHDRAWAL** - Manual Balance Subtraction (Debit)
**Effect**: Decreases user balance by specified amount

#### Files & Functions:
- **File**: `src/routes/tenant_admin.py`
- **Function**: `update_user_balance()` (lines 264-329)
- **API**: `POST /api/admin/<subdomain>/update-user-balance`

#### Code Location:
```python
# Calculate new balance
current_balance = user['balance']
if action == 'add':
    new_balance = current_balance + amount
else:
    new_balance = max(0, current_balance - amount)  # Don't allow negative balance
```

### 6. **ADMIN_RESET** - Mass Balance Reset (Credit/Debit)
**Effect**: Sets all user balances to a specified amount

#### Files & Functions:
- **File**: `src/routes/rich_admin_interface.py`
- **Function**: `reset_all_users()` (lines 884-929)
- **API**: `POST /<subdomain>/admin/api/users/reset`
- **File**: `src/routes/rich_superadmin_interface1.py`
- **Function**: `reset_all_global_users()` (lines 543+)
- **API**: `POST /superadmin/api/global-users/reset`

#### Code Location:
```python
# Reset all user balances for this operator
users_reset = conn.execute(
    "UPDATE users SET balance = ? WHERE sportsbook_operator_id = ?",
    (new_balance, operator['id'])
).rowcount
```

### 7. **MANUAL_SETTLE** - Manual Bet Settlement (Credit)
**Effect**: Increases user balance when admin manually settles a winning bet

#### Files & Functions:
- **File**: `src/routes/tenant_admin.py`
- **Function**: `settle_bet()` (lines 134-189)
- **API**: `POST /api/admin/<subdomain>/settle-bet`
- **File**: `src/routes/comprehensive_superadmin.py`
- **Function**: `global_manual_settle_bets()` (lines 606+)
- **API**: `POST /api/superadmin/global-manual-settle-bets`
- **File**: `src/routes/rich_admin_interface.py`
- **Function**: `manual_settle_bets()` (lines 1521+)
- **API**: `POST /<subdomain>/admin/api/betting/manual-settle`
- **File**: `src/routes/rich_superadmin_interface1.py`
- **Function**: `global_manual_settle_bets()` (lines 1387+)
- **API**: `POST /superadmin/api/global-manual-settle-bets`

#### Code Location:
```python
# Update user balance if won
if result == 'won':
    conn.execute("""
        UPDATE users 
        SET balance = balance + ?
        WHERE id = ?
    """, (actual_return, bet['user_id']))
```

## Database Schema

### Transactions Table
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    sportsbook_operator_id INTEGER,
    bet_id INTEGER,
    amount DECIMAL(10,2) NOT NULL,  -- Positive for credits, negative for debits
    transaction_type VARCHAR(50) NOT NULL,  -- 'bet', 'win', 'refund', 'deposit', 'withdrawal', 'admin_reset'
    description TEXT,
    balance_before DECIMAL(10,2),
    balance_after DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Users Table (Balance Field)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    balance DECIMAL(10,2) DEFAULT 1000.0,  -- User's wallet balance
    -- ... other fields
);
```

## Balance Validation

### Positive Integer Validation
- **File**: `src/routes/betting.py`
- **Functions**: `place_bet()` and `place_combo_bet()`
- **Validation**: Ensures betting amounts are positive integers

```python
# Validate stake amount - must be positive integer
if stake <= 0:
    return jsonify({
        'success': False,
        'message': 'Betting amount must be greater than zero'
    }), 400

if not isinstance(stake, (int, float)) or stake != int(stake):
    return jsonify({
        'success': False,
        'message': 'Betting amount must be a whole number'
    }), 400
```

## Real-time Balance Updates

### WebSocket Events
- **File**: `src/routes/betting.py`
- **Functions**: `place_bet()` and `place_combo_bet()`
- **Events**: `bet:placed`, `bet:settled`

```python
# Emit socket events using primitives only
socketio.emit('bet:placed', {
    'user_id': user.id,
    'bet_id': bet.id,
    'new_balance': new_balance,
    'stake': stake
})
```

### Session Cache Updates
- **File**: `src/routes/betting.py`
- **Functions**: `place_bet()` and `place_combo_bet()`

```python
# Update session cache with the new balance
try:
    from src.routes.tenant_auth import build_session_user
    updated_user_data = build_session_user(user)
    session['user_data'] = updated_user_data
    logger.info("Session cache updated successfully")
except Exception as e:
    logger.warning(f"Failed to update session user data: {e}")
```

## Security Considerations

1. **Authorization**: All balance-changing operations require proper authentication
2. **Validation**: Input validation prevents negative or invalid amounts
3. **Atomicity**: Database transactions ensure consistency
4. **Audit Trail**: All changes are logged in the transactions table
5. **Multi-tenancy**: Operations are scoped to the correct operator

## Monitoring & Logging

All balance changes are logged with:
- User ID
- Transaction type
- Amount (positive/negative)
- Balance before/after
- Timestamp
- Description

Example log entry:
```
💰 Wallet updated u=123 Δ=50.00 new=1050.00 bet=456
```

## Summary

User wallet balance changes occur through 8 main transaction types:
0. **ACCOUNT_CREATION** - New user registration (credit) - Sets initial balance
1. **BET** - Placing bets (debit)
2. **WIN** - Winning bets (credit)
3. **REFUND** - Cancelled bets (credit)
4. **DEPOSIT** - Manual additions (credit)
5. **WITHDRAWAL** - Manual subtractions (debit)
6. **ADMIN_RESET** - Mass resets (credit/debit)
7. **MANUAL_SETTLE** - Manual settlements (credit)

**Note**: Account creation doesn't create a transaction record in the `transactions` table - it directly sets the initial balance in the `users.balance` field. All other changes are tracked in the `transactions` table and include proper validation, authorization, and audit trails.
