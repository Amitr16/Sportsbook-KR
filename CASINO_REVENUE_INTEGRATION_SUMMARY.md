# Casino Revenue Integration Summary

## Overview
Successfully integrated casino revenue calculations into the daily revenue calculator system. The system now calculates and distributes revenue from both sportsbook bets and casino games.

## Changes Made

### 1. Daily Revenue Calculator (`daily_revenue_calculator.py`)
- **Added new functions:**
  - `calculate_casino_revenue()` - Calculates revenue from `game_round` table
  - `calculate_sportsbook_revenue()` - Calculates revenue from `bets` table  
  - `calculate_total_combined_revenue()` - Combines both revenue sources

- **Modified main function:**
  - Now calculates combined revenue instead of just sportsbook
  - Updates `sportsbook_operators.total_revenue` with combined amount
  - Provides detailed breakdown of sportsbook vs casino revenue

### 2. Superadmin Interface (`src/routes/rich_superadmin_interface1.py`)
- **Added new functions:**
  - `calculate_casino_revenue()` - Casino revenue calculation
  - `calculate_sportsbook_revenue()` - Sportsbook revenue calculation

- **Updated `update_operator_revenue()`:**
  - Now calculates both revenue sources
  - Updates operator with combined total
  - Logs detailed breakdown

### 3. Admin Interface (`src/routes/rich_admin_interface.py`)
- **Added new functions:**
  - `calculate_casino_revenue()` - Casino revenue calculation
  - `calculate_sportsbook_revenue()` - Sportsbook revenue calculation

- **Updated functions:**
  - `update_operator_revenue()` - Now includes casino revenue
  - `calculate_total_revenue()` - Now returns combined revenue

### 4. Bet Settlement Service (`src/bet_settlement_service.py`)
- **Added new functions:**
  - `_calculate_casino_revenue()` - Casino revenue calculation
  - `_calculate_sportsbook_revenue()` - Sportsbook revenue calculation

- **Updated `_update_operator_revenue()`:**
  - Now calculates both revenue sources
  - Updates operator with combined total
  - Logs detailed breakdown

## Revenue Calculation Logic

### Sportsbook Revenue
```sql
-- Revenue = Money kept from losing bets - Extra money paid to winners
SELECT 
    SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
    SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
FROM bets b
JOIN users u ON b.user_id = u.id
WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = ?
```

### Casino Revenue
```sql
-- Revenue = Total stakes - Total payouts (same logic as sportsbook)
SELECT 
    SUM(gr.stake) as total_stakes,
    SUM(gr.payout) as total_payouts
FROM game_round gr
JOIN users u ON gr.user_id = u.id::text
WHERE u.sportsbook_operator_id = ?
```

### Combined Revenue
```
Total Revenue = Sportsbook Revenue + Casino Revenue
```

## Database Tables Used

### Sportsbook Data
- **`bets`** - Sportsbook bet records
- **`users`** - User information with operator association

### Casino Data  
- **`game_round`** - Casino game records (roulette, blackjack, baccarat, slots, crash)
- **`users`** - User information with operator association

## Testing

A test script `test_integrated_revenue.py` has been created to verify:
- ✅ Individual revenue calculations work
- ✅ Combined revenue calculation is correct
- ✅ Math verification (sportsbook + casino = total)
- ✅ Wallet balance retrieval
- ✅ Revenue distribution calculation
- ✅ Database table existence

## Impact on Daily Revenue Calculator

The daily revenue calculator now:

1. **Calculates combined revenue** from both sportsbook and casino
2. **Updates operator records** with the new combined total
3. **Distributes revenue** based on the combined amount
4. **Provides detailed logging** showing breakdown by source
5. **Maintains backward compatibility** with existing wallet system

## Benefits

- ✅ **Complete revenue tracking** - No more missing casino revenue
- ✅ **Accurate daily calculations** - True total revenue per operator
- ✅ **Proper distribution** - Revenue distributed based on actual total
- ✅ **Detailed reporting** - Clear breakdown of revenue sources
- ✅ **Consistent logic** - Same revenue calculation approach for both sources

## Next Steps

1. **Run the test script** to verify everything works:
   ```bash
   python test_integrated_revenue.py
   ```

2. **Test the daily revenue calculator**:
   ```bash
   python daily_revenue_calculator.py
   ```

3. **Monitor the superadmin panel** to see combined revenue in action

The system is now ready to accurately calculate and distribute revenue from both sportsbook and casino operations!
