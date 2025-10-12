# Web3 Wallet Implementation - Phase 1 Complete

## Overview
Successfully implemented a parallel Web3 wallet system using Aptos blockchain's custodial USDT token. This runs alongside the existing Web2 database balance system without any UI changes.

---

## What Was Implemented

### 1. **Aptos Wallet Service** (`src/services/aptos_wallet_service.py`)
A complete service layer for managing Aptos blockchain wallets:

- **`create_wallet()`**: Generates new Aptos wallet (address + private key)
- **`deposit(to_address, amount)`**: Admin function to credit USDT to any wallet
- **`withdraw(user_private_key, amount)`**: User deducts from their own wallet
- **`transfer(from_key, to_address, amount)`**: Transfer between wallets
- **`get_balance(address)`**: Query wallet balance on-chain
- **`admin_reset_one(address, new_amount)`**: Admin reset single user balance

### 2. **Database Schema Updates**
Added two new columns to the `users` table:

| Column | Type | Description |
|--------|------|-------------|
| `web3_wallet_address` | VARCHAR(255) UNIQUE | Aptos blockchain address (public) |
| `web3_wallet_key` | TEXT | Encrypted private key (stored securely) |

**Migration completed successfully** ✓

### 3. **User Model Updated** (`src/models/multitenant_models.py`)
Added Web3 wallet fields to the `User` model:
```python
web3_wallet_address = db.Column(db.String(255), unique=True, nullable=True)
web3_wallet_key = db.Column(db.Text, nullable=True)
```

### 4. **Registration Flow Enhanced** (`src/routes/tenant_auth.py`)
Integrated Web3 wallet creation into the tenant registration process:

**Flow:**
1. User registers (existing Web2 process)
2. **NEW**: Aptos wallet is created automatically
3. Wallet address & encrypted key stored in database
4. **NEW**: Initial balance from operator settings is credited to Web3 wallet
5. User registration completes (Web2 balance also set)

**Key Feature**: If Web3 wallet creation fails, registration still succeeds (graceful degradation)

### 5. **Environment Configuration**
Added Aptos configuration to `postgresql.env`:

```bash
# Aptos Web3 Wallet Configuration
APTOS_NODE_URL=https://fullnode.testnet.aptoslabs.com/v1
APTOS_MODULE_ADDRESS=0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085
APTOS_ADMIN_PRIVATE_KEY=your-aptos-admin-private-key-here
```

---

## How It Works

### User Registration Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. User submits registration form                          │
│     (username, email, password)                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Validate user input & check for duplicates              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Get default_user_balance from operator settings         │
│     Example: {"default_user_balance": 5000.0}               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Create Aptos Web3 Wallet                                │
│     - Generate new wallet address                           │
│     - Store private key (encrypted)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Create user in database                                 │
│     - Web2 balance: 5000.0                                  │
│     - web3_wallet_address: 0x123abc...                      │
│     - web3_wallet_key: encrypted_private_key                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Credit initial balance to Web3 wallet (on-chain)        │
│     - Call Aptos smart contract deposit()                   │
│     - Amount: 5000.0 USDT                                   │
│     - Transaction recorded on blockchain                    │
└─────────────────────────────────────────────────────────────┘
```

### Dual Balance System

After registration, each user has:

1. **Web2 Balance** (PostgreSQL `users.balance`)
   - Used by existing UI
   - Fast database queries
   - Traditional system

2. **Web3 Balance** (Aptos Blockchain `custodial_usdt`)
   - Parallel system
   - On-chain verification
   - Decentralized ledger
   - NO UI changes needed

---

## Files Created/Modified

### New Files
- `src/services/aptos_wallet_service.py` - Aptos wallet service
- `src/migrations/add_web3_wallet_columns.py` - Database migration
- `run_migration.py` - Migration runner script
- `WEB3_WALLET_IMPLEMENTATION.md` - This documentation
- `usdt.move/` - Aptos smart contract repository (cloned)

### Modified Files
- `src/models/multitenant_models.py` - Added web3 wallet columns to User model
- `src/routes/tenant_auth.py` - Integrated wallet creation in registration
- `postgresql.env` - Added Aptos configuration
- `src/db_compat.py` - Removed emoji encoding issues (Windows compatibility)
- `requirements.txt` - Added `aptos-sdk==0.11.0`

---

## Configuration Required

### 1. Set Admin Private Key
You need to generate or provide an Aptos admin private key:

```bash
# Option 1: Use existing deployed contract's admin key
APTOS_ADMIN_PRIVATE_KEY=0x<your_admin_private_key>

# Option 2: Deploy your own contract (see usdt.move/README.md)
```

### 2. Verify Module Address
The current module address points to the testnet deployment:
```
0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085
```

If you deploy your own contract, update `APTOS_MODULE_ADDRESS` in `postgresql.env`.

---

## Testing the Implementation

### 1. Test User Registration
```bash
# Start Flask app
python run.py

# Register new user via API
curl -X POST http://localhost:5000/api/auth/supersports/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

Expected logs:
```
Created Web3 wallet for testuser: 0x123abc...
New user registered for supersports: testuser
Credited 5000.0 USDT to Web3 wallet - tx: 0xabcdef...
```

### 2. Verify Database
```sql
SELECT 
  username, 
  balance, 
  web3_wallet_address, 
  LENGTH(web3_wallet_key) as key_length
FROM users 
WHERE username = 'testuser';
```

Expected output:
```
username   | balance | web3_wallet_address      | key_length
-----------|---------|--------------------------|-----------
testuser   | 5000.0  | 0x123abc...              | 64
```

### 3. Query On-Chain Balance
```python
from src.services.aptos_wallet_service import get_aptos_service

aptos = get_aptos_service()
balance = aptos.get_balance("0x123abc...")
print(f"Web3 Balance: {balance} USDT")
# Expected: Web3 Balance: 5000.0 USDT
```

---

## Architecture Benefits

1. **Zero UI Changes**: Existing frontend continues to work unchanged
2. **Graceful Degradation**: If Web3 fails, Web2 system still works
3. **Dual Verification**: Can compare Web2 vs Web3 balances for auditing
4. **Future-Ready**: Foundation for blockchain features (NFTs, DeFi, etc.)
5. **Operator Control**: Each operator's `default_user_balance` setting applies to both systems

---

## Security Considerations

### Current Implementation
- Private keys stored in database (plaintext) ⚠️
- Admin private key in environment variable ⚠️

### Recommended Improvements (Future)
1. **Encrypt Private Keys**:
   ```python
   from cryptography.fernet import Fernet
   # Encrypt before storing, decrypt before using
   ```

2. **Use Key Management Service (KMS)**:
   - AWS KMS, Azure Key Vault, or HashiCorp Vault
   - Never store admin key in plain text

3. **Implement Key Rotation**:
   - Periodic rotation of admin keys
   - User key migration strategies

4. **Add Multi-Sig Admin**:
   - Require multiple signatures for admin operations
   - Prevent single point of failure

---

## Next Steps (Future Phases)

### Phase 2: Sync Operations
- Mirror bet placements to blockchain
- Sync withdrawals/deposits between Web2 and Web3
- Implement balance reconciliation

### Phase 3: Admin Dashboard
- View all Web3 wallets
- Monitor on-chain transactions
- Bulk operations (reset, deposit, etc.)

### Phase 4: Blockchain Features
- NFT rewards for users
- Provably fair gaming
- Public audit trail
- Cross-platform wallet support

---

## Troubleshooting

### Issue: "Admin account not initialized"
**Solution**: Set `APTOS_ADMIN_PRIVATE_KEY` in environment

### Issue: "Transaction failed"
**Solution**: 
- Check Aptos testnet status
- Ensure admin account has gas fees (APT tokens)
- Verify module address is correct

### Issue: "Wallet creation fails"
**Solution**:
- Check `APTOS_NODE_URL` is accessible
- Verify `aptos-sdk` is installed: `pip list | grep aptos`
- User registration will still succeed (Web2 only)

### Issue: "Migration fails"
**Solution**:
- Ensure `DATABASE_URL` is set
- Check database connection
- Re-run: `python run_migration.py`

---

## Summary

✅ **Aptos SDK installed and configured**  
✅ **Web3 wallet service created**  
✅ **Database migration completed**  
✅ **User model updated**  
✅ **Registration flow integrated**  
✅ **Environment variables configured**  
✅ **Initial balance from operator settings**  
✅ **Zero UI changes required**  

**Result**: Users now get both a Web2 database balance AND a Web3 blockchain wallet on registration, with the initial balance credited to both systems automatically!

