# 🚀 Deploy Updated Smart Contract

## ✅ What We Added:

### **New Function 1: `admin_withdraw`**
```move
public entry fun admin_withdraw(admin: &signer, from_user: address, amount: u128)
```
**Purpose**: Admin can withdraw from ANY user wallet to admin wallet  
**Use Case**: Process user withdrawal requests

**Example:**
```bash
# Withdraw 50 USDT from user to admin
aptos move run --profile contract_admin \
  --function-id 0x...::custodial_usdt::admin_withdraw \
  --args address:0xUSER_ADDRESS u128:50000000 \
  --assume-yes
```

### **New Function 2: `admin_transfer`**
```move
public entry fun admin_transfer(admin: &signer, from_user: address, to_user: address, amount: u128)
```
**Purpose**: Admin can transfer between ANY two user wallets  
**Use Case**: Bonuses, corrections, internal transfers

**Example:**
```bash
# Transfer 10 USDT from User A to User B
aptos move run --profile contract_admin \
  --function-id 0x...::custodial_usdt::admin_transfer \
  --args address:0xUSER_A address:0xUSER_B u128:10000000 \
  --assume-yes
```

---

## 📋 Deployment Steps:

### **Step 1: Compile the Contract**
```bash
cd usdt.move
aptos move compile --named-addresses sportsbook_platform=0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085
```

### **Step 2: Deploy/Upgrade**
```bash
aptos move publish \
  --profile contract_admin \
  --named-addresses sportsbook_platform=0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085 \
  --assume-yes
```

### **Step 3: Test New Functions**

#### **Test admin_withdraw:**
```bash
# Withdraw 1 USDT from test user to admin
aptos move run --profile contract_admin \
  --url https://fullnode.testnet.aptoslabs.com \
  --function-id 0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085::custodial_usdt::admin_withdraw \
  --args address:0xf4d71ac9c2618b137bff9b7d45d21fcfe1a19cafe3bb10ac59ab364cf9d8ebec u128:1000000 \
  --assume-yes
```

#### **Test admin_transfer:**
```bash
# Transfer 0.5 USDT from User A to User B
aptos move run --profile contract_admin \
  --url https://fullnode.testnet.aptoslabs.com \
  --function-id 0xfc26c5948f1865f748fe43751cd2973fc0fd5b14126104122ca50483386c4085::custodial_usdt::admin_transfer \
  --args address:0xUSER_A address:0xUSER_B u128:500000 \
  --assume-yes
```

---

## ⚠️ Important Notes:

1. **This is a contract upgrade** - The address stays the same
2. **Existing balances are preserved** - Data persists across upgrades
3. **You must have admin rights** - Only the original deployer can upgrade
4. **Gas required** - Your admin account needs APT (already funded ✅)

---

## 🎯 After Deployment:

### **Your Complete Withdrawal Flow:**

```
User requests withdrawal ($50)
        ↓
Admin approves in backend
        ↓
Call admin_withdraw(user_address, 50.0)
        ↓
User's balance reduced by $50
Admin's balance increased by $50
        ↓
Admin sends real funds to user's bank/wallet
```

### **Your Complete Transfer Flow:**

```
Need to move funds between users
        ↓
Call admin_transfer(user_a, user_b, 10.0)
        ↓
User A: -$10
User B: +$10
```

---

## ✅ Summary:

**After deploying this update, you'll have:**
- ✅ `deposit` - Admin deposits to users
- ✅ `admin_withdraw` - Admin withdraws from users (NEW!)
- ✅ `admin_transfer` - Admin transfers between users (NEW!)
- ✅ `withdraw` - Users withdraw (requires their signature via Crossmint)
- ✅ `transfer` - Users transfer (requires their signature via Crossmint)
- ✅ `balance_of` - Check any balance
- ✅ `admin_reset_one/all/top_k` - Reset balances

**Full admin control + optional user self-service!** 🎯

