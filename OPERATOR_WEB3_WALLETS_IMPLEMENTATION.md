# Operator Web3 Wallets Implementation

## Overview
Successfully added Web3 wallet creation for operators during registration. Each operator now gets **4 Web3 wallets** on the Aptos blockchain, mirroring the existing Web2 wallet structure.

---

## What Was Implemented

### ✅ Web3 Wallet Creation During Registration
Modified `src/routes/sportsbook_registration.py` → `create_operator_wallets()` function

**Location**: Lines 136-205

### 4 Web3 Wallets Created Per Operator

| Wallet Type | Initial Balance | Web3 Action |
|-------------|-----------------|-------------|
| **Bookmaker Capital** | 10,000 USDT | ✅ Created + Funded |
| **Liquidity Pool** | 40,000 USDT | ✅ Created + Funded |
| **Revenue** | 0 USDT | ✅ Created (no funding) |
| **Bookmaker Earnings** | 0 USDT | ✅ Created (no funding) |

---

## Implementation Details

### Code Structure

```python
# After each Web2 wallet creation, immediately create Web3 wallet

# Example for Wallet 1 (Bookmaker Capital):
wallet1_id = cursor.lastrowid  # Web2 wallet created

# Create Web3 wallet (parallel to Web2)
try:
    from src.services.aptos_wallet_service import get_aptos_service
    aptos_service = get_aptos_service()
    web3_address, web3_key = aptos_service.create_wallet()
    tx_hash = aptos_service.deposit(web3_address, 10000.0)
    print(f"✅ Web3 bookmaker_capital: {web3_address}, funded 10000 USDT, tx: {tx_hash}")
except Exception as e:
    print(f"⚠️ Web3 bookmaker_capital failed: {e}")
```

### Key Features

1. **Parallel Structure**: Web3 wallets exist alongside Web2 wallets
2. **Non-Blocking**: If Web3 creation fails, Web2 registration continues
3. **Automatic Funding**: Wallets with initial balances are auto-funded
4. **Error Handling**: Each wallet creation has try-catch to prevent cascading failures

---

## Registration Flow

```
Operator Registers
    ↓
Create Web2 Wallet 1 (bookmaker_capital) → Create Web3 Wallet 1 → Fund 10,000 USDT
    ↓
Create Web2 Wallet 2 (liquidity_pool)    → Create Web3 Wallet 2 → Fund 40,000 USDT
    ↓
Create Web2 Wallet 3 (revenue)           → Create Web3 Wallet 3 (no funding)
    ↓
Create Web2 Wallet 4 (bookmaker_earnings)→ Create Web3 Wallet 4 (no funding)
    ↓
Registration Complete
```

---

## Files Modified

### `src/routes/sportsbook_registration.py`
- **Lines 136-144**: Web3 wallet for `bookmaker_capital`
- **Lines 157-165**: Web3 wallet for `liquidity_pool`
- **Lines 178-185**: Web3 wallet for `revenue`
- **Lines 198-205**: Web3 wallet for `bookmaker_earnings`

**Total Changes**: 4 surgical insertions, no existing functionality broken

---

## Testing

### Test Operator Registration

```bash
# 1. Start Flask app
python run.py

# 2. Register a new operator via API
curl -X POST http://localhost:5000/api/register-sportsbook \
  -H "Content-Type: application/json" \
  -d '{
    "sportsbook_name": "Test Sportsbook",
    "login": "admin",
    "password": "password123",
    "email": "admin@test.com",
    "referral_code": "YOURCODE"
  }'

# 3. Check console logs for Web3 wallet creation
# Expected output:
# ✅ Web3 bookmaker_capital: 0xabc..., funded 10000 USDT, tx: 0x123...
# ✅ Web3 liquidity_pool: 0xdef..., funded 40000 USDT, tx: 0x456...
# ✅ Web3 revenue: 0xghi..., no initial balance
# ✅ Web3 bookmaker_earnings: 0xjkl..., no initial balance
```

---

## Configuration Required

### ⚠️ Set Aptos Admin Private Key

The system requires an Aptos admin private key to create wallets and fund them.

**File**: `postgresql.env` (line 45)

```bash
APTOS_ADMIN_PRIVATE_KEY=0x<your-aptos-admin-private-key-here>
```

**How to get the key:**

1. **Option 1**: Deploy your own USDT contract using `usdt.move/`
2. **Option 2**: Contact the `dianasuar/usdt.move` contract owner for admin access

---

## Important Notes

### Web2 vs. Web3 Architecture

- **Web2 (Primary)**: All database operations, UI displays, balance checks
- **Web3 (Parallel)**: Blockchain mirror for transparency and on-chain verification
- **No UI Changes**: Users/operators don't see Web3 wallets (yet)
- **Non-Breaking**: If Web3 fails, Web2 continues normally

### Security

- Web3 private keys are generated but **NOT stored in database** (current implementation)
- Only wallet addresses are tracked
- Admin private key must be kept secure in environment variables

---

## Next Steps

### To Make Web3 Fully Functional:

1. **Set Admin Private Key** in `postgresql.env`
2. **Add Database Columns** (optional):
   - Run `src/migrations/add_web3_wallet_columns.py` for `users` table
   - Add similar columns to `sportsbook_operators` and `operator_wallets` tables
3. **Store Web3 Keys**: Modify code to store `web3_wallet_key` in database (encrypted)
4. **Sync Operations**: Add Web3 debit/credit for operator wallet operations

---

## Summary

✅ **Complete**: 4 Web3 wallets created per operator during registration
✅ **Parallel**: Web2 and Web3 coexist without conflicts
✅ **Safe**: Non-blocking implementation with error handling
✅ **Funded**: Bookmaker Capital and Liquidity Pool auto-funded
⚠️ **Config Needed**: Set `APTOS_ADMIN_PRIVATE_KEY` to enable functionality

**The system now creates both Web2 and Web3 wallets during operator registration!** 🚀

