# Casino API Connection Leak Fix Plan

## Issue
12 endpoints in `casino_api.py` acquire database connections but don't have `finally` blocks to ensure they're closed on errors.

## Locations to Fix:

1. **Line 337** - `temp_conn` in split hands payout (HAS finally ✅)
2. **Line 473** - `/user-info` endpoint (NO finally 🔴)
3. **Line 540** - `/balance` endpoint (HAS try/except but checking for finally...)
4. **Line 601** - `/play/slots` endpoint (NO finally 🔴)
5. **Line 674** - `/play/slots` game round storage (NO finally 🔴)
6. **Line 751** - `/play/slots-20` endpoint (NO finally 🔴)
7. **Line 859** - `/play/roulette/history` endpoint (NO finally 🔴)
8. **Line 954** - `/play/blackjack` endpoint (NO finally 🔴)
9. **Line 1372** - `/play/roulette` endpoint (NO finally 🔴)
10. **Line 1487** - `/play/crash` endpoint (NO finally 🔴)
11. **Line 1583** - `/play/crash/history` endpoint (NO finally 🔴)
12. **Line 1678** - `/game-history` endpoint (NO finally 🔴)

## Fix Strategy

For each endpoint WITHOUT a `finally` block:
1. Wrap the existing code in `try:` 
2. Add `finally:` block with `if conn: conn.close()`
3. Ensure minimal code changes - surgical approach

## Template:
```python
# BEFORE:
conn = get_tracked_connection()
cursor = conn.cursor()
# ... do stuff ...
conn.close()

# AFTER:
conn = None
try:
    conn = get_tracked_connection()
    cursor = conn.cursor()
    # ... do stuff ...
    conn.close()  # Keep existing close for happy path
finally:
    if conn:
        try:
            conn.close()
        except:
            pass  # Already closed in happy path
```

Actually, simpler - just add finally blocks, don't duplicate closes.

