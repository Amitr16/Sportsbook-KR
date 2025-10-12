# Web3 Wallet Reset Functionality

## Overview

The Web3 wallet reset functionality extends the existing "Reset Contest" feature in the Super Admin panel to also reset all Web3 wallets to a specified balance amount. This ensures that both Web2 (database) and Web3 (blockchain) user balances are synchronized when administrators perform a global reset.

## How It Works

### 1. **Admin Interface Integration**

The functionality is integrated into the existing "Reset Contest" feature in the Super Admin panel:

- **Location**: Global User Management → Reset Contest
- **Input Fields**: 
  - Balance Amount (USD)
  - Contest End Date
- **Action**: Reset Contest button

### 2. **Reset Process Flow**

When an admin clicks "Reset Contest", the system performs the following steps:

1. **Backup Leaderboards** - Creates snapshot of current standings
2. **Save Contest End Date** - Records the new contest period
3. **Cancel Pending Bets** - Refunds all pending bet stakes
4. **Reset Web2 Balances** - Updates all user balances in the database
5. **Update Operator Defaults** - Sets new default balance for future users
6. **🆕 Reset Web3 Wallets** - Resets all Aptos blockchain wallets to the specified USDT amount

### 3. **Web3 Wallet Reset Logic**

For each user with a Web3 wallet:

```python
# Get current Web3 balance
current_balance = aptos_service.get_balance(wallet_address)

# Calculate difference needed
balance_diff = new_balance - current_balance

if balance_diff > 0:
    # Deposit USDT to user's wallet (admin → user)
    tx_hash = aptos_service.deposit(wallet_address, balance_diff)
else:
    # Withdraw USDT from user's wallet (user → admin)
    tx_hash = aptos_service.withdraw(user_private_key, abs(balance_diff))
```

### 4. **User Experience**

#### **Warning Message**
```
⚠️ WARNING: This will:

1. Cancel ALL pending bets (refund stakes) across ALL operators
2. Reset ALL user balances to $5000 across ALL operators
3. Reset ALL Web3 wallets to 5000 USDT across ALL operators
4. Set default balance for NEW users to $5000
5. Create backup snapshot of current leaderboards
6. Save contest end date: 12/31/2024, 11:59:59 PM
7. This action cannot be undone!

Are you sure you want to continue?
```

#### **Success Message**
```
✅ Successfully reset all users across all operators!

- 45 pending bets cancelled (refunded)
- 123 user balances reset to $5000
- New users will now get $5000 by default

🌐 Web3 Wallets Reset:
- 89 Web3 wallets reset to 5000 USDT
- 2 Web3 wallets failed to reset
- Web3 errors: Connection timeout, Invalid wallet address
```

## Technical Implementation

### 1. **New Service: `web3_reset_service.py`**

**Location**: `src/services/web3_reset_service.py`

**Key Functions**:
- `reset_all_web3_wallets(new_balance)` - Resets all user Web3 wallets
- `reset_web3_wallet_for_user(user_id, new_balance)` - Resets individual user's wallet

**Features**:
- ✅ Handles both deposits (admin → user) and withdrawals (user → admin)
- ✅ Skips wallets that already have the correct balance
- ✅ Comprehensive error handling and logging
- ✅ Returns detailed statistics (success/failure counts)

### 2. **Integration Points**

**Modified Files**:
- `src/routes/rich_superadmin_interface1.py` - Added Web3 reset to existing reset contest function
- Frontend JavaScript - Updated success/warning messages to include Web3 statistics

**Database Requirements**:
- Users must have `web3_wallet_address` and `web3_wallet_key` columns populated
- Only users with complete Web3 wallet info are processed

### 3. **Error Handling**

The Web3 reset is designed to be **non-blocking**:
- ✅ If Web3 reset fails, the Web2 reset still completes
- ✅ Detailed error logging for troubleshooting
- ✅ Statistics show success/failure counts
- ✅ Individual wallet failures don't stop the entire process

## Configuration

### 1. **Environment Variables**

Required for Web3 functionality:
```bash
APTOS_NODE_URL=https://fullnode.mainnet.aptoslabs.com
APTOS_MODULE_ADDRESS=0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085
APTOS_ADMIN_PRIVATE_KEY=0x...
```

### 2. **Database Schema**

Users table must have:
```sql
ALTER TABLE users ADD COLUMN web3_wallet_address VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN web3_wallet_key TEXT;
```

## Usage Examples

### 1. **Typical Reset Scenario**

**Admin Input**:
- Balance Amount: `5000`
- Contest End Date: `2024-12-31 23:59:59`

**System Action**:
1. Cancels 45 pending bets (refunds $2,250 in stakes)
2. Resets 123 user Web2 balances to $5,000
3. Resets 89 Web3 wallets to 5,000 USDT
4. Updates operator defaults for new users
5. Saves contest end date

**Result**: All users start fresh with exactly $5,000 in both Web2 and Web3 systems.

### 2. **Partial Web3 Failure**

**Scenario**: 2 out of 89 Web3 wallets fail to reset

**System Response**:
- ✅ Web2 reset completes successfully (123 users)
- ⚠️ Web3 reset completes with warnings (87 success, 2 failures)
- 📊 Admin sees detailed statistics in success message
- 🔍 Error details logged for troubleshooting

## Security Considerations

### 1. **Admin-Only Access**

- ✅ Requires super admin authentication
- ✅ Only accessible through secure admin panel
- ✅ All actions logged with timestamps

### 2. **Blockchain Security**

- ✅ Uses admin private key for deposits (admin → user)
- ✅ Uses user private keys for withdrawals (user → admin)
- ✅ All transactions are recorded on Aptos blockchain
- ✅ Transaction hashes provided for verification

### 3. **Data Integrity**

- ✅ Web2 and Web3 resets are separate operations
- ✅ Web2 reset completes even if Web3 fails
- ✅ Comprehensive error logging for audit trail

## Monitoring and Troubleshooting

### 1. **Log Messages**

```
🔄 WEB3 RESET: Starting Web3 wallet reset to 5000 USDT
🔄 WEB3 RESET: Found 89 users with Web3 wallets
🔄 WEB3 RESET: Resetting wallet for user AtomicPro (57)
✅ WEB3 RESET: Deposited 1500.0 USDT to AtomicPro - tx: 0xabc123...
✅ WEB3 RESET: Successfully reset AtomicPro's wallet to 5000 USDT
✅ WEB3 RESET: Completed! Reset 87 wallets, 2 failed
```

### 2. **Error Types**

Common issues and solutions:
- **Connection timeout**: Check Aptos node URL
- **Invalid wallet address**: Verify wallet creation during user registration
- **Insufficient admin balance**: Ensure admin wallet has enough USDT
- **Transaction failed**: Check Aptos network status

### 3. **Verification**

After reset, admins can verify:
- ✅ Web2 balances updated in database
- ✅ Web3 balances updated on Aptos blockchain
- ✅ Transaction hashes recorded in logs
- ✅ User interface shows correct balances

## Future Enhancements

### 1. **Individual User Reset**

The service includes `reset_web3_wallet_for_user()` for individual resets:
- Could be integrated into user management interface
- Useful for customer support scenarios
- Provides granular control over specific users

### 2. **Batch Processing**

For large user bases:
- Could implement batch processing with rate limiting
- Queue system for handling thousands of wallets
- Progress tracking for long-running operations

### 3. **Advanced Error Recovery**

- Retry mechanism for failed transactions
- Manual intervention tools for stuck wallets
- Detailed error categorization and reporting

---

## Summary

The Web3 wallet reset functionality seamlessly integrates with the existing admin reset contest feature, ensuring that both Web2 and Web3 user balances are synchronized during global resets. The implementation is robust, non-blocking, and provides comprehensive feedback to administrators about the reset process.

**Key Benefits**:
- ✅ **Unified Reset**: Both Web2 and Web3 balances reset together
- ✅ **Non-Blocking**: Web2 reset succeeds even if Web3 fails
- ✅ **Comprehensive Feedback**: Detailed success/failure statistics
- ✅ **Audit Trail**: Full logging and transaction tracking
- ✅ **User-Friendly**: Clear warning and success messages
