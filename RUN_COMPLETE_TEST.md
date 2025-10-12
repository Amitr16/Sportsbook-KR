# Complete Web3 Integration Test Instructions

## Steps to Run Complete Test:

### 1. Stop Flask (if running)
```
Press Ctrl+C in the Flask terminal
```

### 2. Start Flask (fresh restart to reload all modules)
```bash
python run.py
```

### 3. Run the complete test (in a new terminal)
```bash
python test_complete_web3_integration.py
```

### 4. Expected Results:

#### Should PASS (8/8):
- [OK] Flask Server
- [OK] Operator Registration
- [OK] User Registration  
- [OK] User Login
- [OK] Single Bet Placement
- [OK] Combo Bet Placement
- [OK] Casino Slots
- [OK] Database Verification

#### Flask Console Should Show:
```
✅ Web3 bookmaker_capital: 0x... (balance tracked in Web2 DB)
✅ Web3 liquidity_pool: 0x... (balance tracked in Web2 DB)
✅ Web3 revenue: 0x..., no initial balance
✅ Web3 bookmaker_earnings: 0x..., no initial balance
✅ Created Web3 wallet for <username>: 0x...
```

#### Test Script Should Show:
```
Operator Web3 Wallets:
[OK] Operator Wallets Found - 4/4 wallets in database
[OK]   bookmaker_capital - Address: 0x...
[OK]   liquidity_pool - Address: 0x...
[OK]   revenue - Address: 0x...
[OK]   bookmaker_earnings - Address: 0x...

User Web3 Wallet:
[OK] User <username> - Address: 0x...
```

## If Tests Still Fail:

### Betting/Casino 405 Errors:
The API endpoints might be different. Check Flask routes with:
```python
from src.main import app
for rule in app.url_map.iter_rules():
    if 'bet' in rule.rule or 'casino' in rule.rule:
        print(f"{rule.methods} {rule.rule}")
```

### Operator Wallets Still NULL:
Check Flask console for the full error traceback. The issue might be:
- Cached Python modules (restart Flask)
- Import error in crossmint_service
- Database connection issue

### Database Verification Fails:
Ensure migrations ran successfully:
```bash
python -c "from dotenv import load_dotenv; load_dotenv('postgresql.env'); from src.migrations.add_operator_web3_wallet_columns import migrate_add_operator_web3_wallet_columns; migrate_add_operator_web3_wallet_columns()"
```

## Quick Database Check (Manual):

```sql
-- Check latest operator wallets
SELECT operator_id, wallet_type, current_balance, web3_wallet_address
FROM operator_wallets
WHERE operator_id = (SELECT MAX(id) FROM sportsbook_operators)
ORDER BY id;

-- Check latest user wallet
SELECT id, username, balance, web3_wallet_address
FROM users
WHERE id = (SELECT MAX(id) FROM users);
```

## Summary of What Gets Tested:

1. **Operator Registration** - Creates operator + 4 Web2 wallets + 4 Web3 wallets
2. **User Registration** - Creates user + Web2 balance + Web3 wallet
3. **User Login** - Establishes session for betting
4. **Single Bet** - Tests Web3 debit on bet placement
5. **Combo Bet** - Tests Web3 debit on combo bet placement  
6. **Casino Slots** - Tests Web3 debit (bet) and credit (win)
7. **Database** - Verifies all Web3 wallet addresses are stored

## Files Modified:

- `run.py` - Loads postgresql.env
- `src/services/web3_sync_service.py` - Uses Crossmint
- `src/services/web3_operator_wallet_service.py` - Uses Crossmint
- `src/services/web3_reset_service.py` - Uses Crossmint
- `src/routes/sportsbook_registration.py` - Unique emails, Crossmint
- `src/routes/tenant_auth.py` - Uses Crossmint
- Migrations run: `add_web3_wallet_columns`, `add_operator_web3_wallet_columns`

---

**After restarting Flask, run the test and check both the script output AND Flask console!**

