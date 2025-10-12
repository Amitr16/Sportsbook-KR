# Web3 Operator Wallets Implementation

## Overview
Successfully extended the superadmin "Run Daily Revenue Calculator" and "Update Operator Wallets" buttons to perform **parallel Web3 operations** on operator wallets. The system now mirrors all Web2 operations on the Aptos blockchain.

---

## What Was Implemented

### ✅ **Web3 Operator Wallet Service**
**File**: `src/services/web3_operator_wallet_service.py`

**Core Functions**:
- `get_operator_web3_wallets()` - Retrieve Web3 wallet addresses for an operator
- `store_operator_web3_wallet()` - Store Web3 wallet address and private key
- `sync_web3_operator_wallet_debit()` - Withdraw from Web3 operator wallet
- `sync_web3_operator_wallet_credit()` - Deposit to Web3 operator wallet
- `create_web3_revenue_calculation()` - Create Web3 revenue calculation records
- `get_unprocessed_web3_revenue_calculations()` - Get pending Web3 calculations
- `mark_web3_revenue_calculation_processed()` - Mark Web3 calculations as complete

### ✅ **Database Migration**
**File**: `src/migrations/add_operator_web3_wallet_columns.py`

**Added Columns to `operator_wallets` table**:
- `web3_wallet_address VARCHAR(255)` - Aptos wallet address
- `web3_wallet_key TEXT` - Encrypted private key

### ✅ **Operator Registration Enhancement**
**File**: `src/routes/sportsbook_registration.py`

**Enhanced `create_operator_wallets()` function**:
- Now stores Web3 wallet addresses in database after creation
- Each of the 4 Web3 wallets (bookmaker_capital, liquidity_pool, revenue, bookmaker_earnings) gets stored with address and private key

### ✅ **Superadmin Interface Extension**
**File**: `src/routes/rich_superadmin_interface1.py`

**Extended Two Buttons**:

#### 1. "Run Daily Revenue Calculator" Button
**Location**: `/superadmin/api/run-daily-revenue-calculator`

**New Web3 Operations**:
- Creates parallel Web3 revenue calculations for each Web2 calculation
- Uses `calculation_metadata = 'web3_false'` to track Web3-specific records
- Returns Web3 statistics in response

#### 2. "Update Operator Wallets" Button  
**Location**: `/superadmin/api/run-update-operator-wallets`

**New Web3 Operations**:
- Processes unprocessed Web3 revenue calculations
- Updates Web3 operator wallets with same logic as Web2:
  - **Bookmaker Capital**: Credits `bookmaker_own_share`
  - **Revenue Wallet**: Credits `community_share_30`
- Marks Web3 calculations as processed (`calculation_metadata = 'web3_true'`)
- Returns Web3 statistics in response

---

## How It Works

### **Revenue Calculator Flow**
```
1. Web2: Calculate daily revenue → Create revenue_calculations record (metadata='false')
2. Web3: Create parallel record → Create revenue_calculations record (metadata='web3_false')
3. Both records have identical amounts and dates
```

### **Wallet Updater Flow**
```
1. Web2: Process revenue_calculations (metadata='false') → Update operator_wallets → Mark processed (metadata='true')
2. Web3: Process revenue_calculations (metadata='web3_false') → Update Web3 wallets → Mark processed (metadata='web3_true')
```

### **Web3 Wallet Operations**
```
Bookmaker Share > 0:
├── Web2: Credit bookmaker_capital wallet
└── Web3: Deposit to bookmaker_capital Web3 wallet

Community Share > 0:
├── Web2: Credit revenue wallet  
└── Web3: Deposit to revenue Web3 wallet
```

---

## Files Modified

### **New Files Created**
1. `src/services/web3_operator_wallet_service.py` - Core Web3 operator wallet logic
2. `src/migrations/add_operator_web3_wallet_columns.py` - Database migration
3. `WEB3_OPERATOR_WALLETS_IMPLEMENTATION.md` - This documentation

### **Modified Files**
1. `src/routes/sportsbook_registration.py` - Store Web3 wallet addresses during registration
2. `src/routes/rich_superadmin_interface1.py` - Extended both superadmin buttons

---

## API Response Changes

### **Daily Revenue Calculator Response**
```json
{
  "success": true,
  "message": "Daily revenue calculator completed successfully",
  "operators_processed": 5,
  "calculations_created": 5,
  "web3_calculations_created": 5
}
```

### **Update Operator Wallets Response**
```json
{
  "success": true,
  "message": "Update operator wallets completed successfully", 
  "calculations_processed": 5,
  "wallets_updated": 5,
  "web3_wallets_updated": 10,
  "web3_calculations_processed": 5
}
```

---

## Testing

### **Test the Implementation**

```bash
# 1. Run database migration
python src/migrations/add_operator_web3_wallet_columns.py

# 2. Register a new operator (creates 4 Web3 wallets)
curl -X POST http://localhost:5000/api/register-sportsbook \
  -H "Content-Type: application/json" \
  -d '{
    "sportsbook_name": "Test Sportsbook",
    "login": "admin",
    "password": "password123",
    "email": "admin@test.com",
    "referral_code": "YOURCODE"
  }'

# 3. Run Daily Revenue Calculator (creates Web2 + Web3 calculations)
curl -X POST http://localhost:5000/superadmin/api/run-daily-revenue-calculator

# 4. Update Operator Wallets (updates Web2 + Web3 wallets)
curl -X POST http://localhost:5000/superadmin/api/run-update-operator-wallets
```

### **Expected Console Output**
```
✅ Created 4 Web3 revenue calculations
🔄 Processing Web3 wallet updates for operator 1
✅ Web3 credit: 1500.00 USDT to bookmaker_capital (operator 1) - tx: 0xabc123...
✅ Web3 credit: 200.00 USDT to revenue (operator 1) - tx: 0xdef456...
✅ Web3 wallet updates completed: 8 wallets updated
```

---

## Configuration Required

### ⚠️ **Set Aptos Admin Private Key**

**File**: `postgresql.env` (line 45)

```bash
APTOS_ADMIN_PRIVATE_KEY=0x<your-aptos-admin-private-key-here>
```

**Without this, Web3 operations will fail but Web2 will continue normally.**

---

## Important Notes

### **Parallel Architecture**
- **Web2 (Primary)**: All database operations, UI displays, balance checks
- **Web3 (Parallel)**: Blockchain mirror for transparency and on-chain verification
- **No UI Changes**: Users/operators don't see Web3 operations (yet)
- **Non-Breaking**: If Web3 fails, Web2 continues normally

### **Revenue Calculation Tracking**
- **Web2 Calculations**: `calculation_metadata = 'false'` → `'true'`
- **Web3 Calculations**: `calculation_metadata = 'web3_false'` → `'web3_true'`
- **Same Table**: Both use `revenue_calculations` table with different metadata flags

### **Security**
- Web3 private keys are stored in database (should be encrypted in production)
- Admin private key must be kept secure in environment variables
- All Web3 operations are logged with transaction hashes

---

## Summary

✅ **Complete**: Both superadmin buttons now perform parallel Web3 operations
✅ **Mirror Logic**: Web3 wallets follow exact same debit/credit logic as Web2
✅ **Non-Breaking**: Web2 operations continue unchanged if Web3 fails
✅ **Tracked**: All Web3 operations are logged with transaction hashes
✅ **Stored**: Web3 wallet addresses and keys stored in database

**The system now performs identical operations on both Web2 and Web3 operator wallets!** 🚀

---

## Next Steps

### **To Make Fully Production Ready**:

1. **Encrypt Private Keys**: Store Web3 private keys encrypted in database
2. **Add Web3 UI**: Show Web3 wallet balances in operator/admin interfaces
3. **Add Error Recovery**: Handle Web3 transaction failures with retry logic
4. **Add Monitoring**: Track Web3 wallet balances and transaction status
5. **Add Web3 Reports**: Include Web3 statistics in revenue reports
