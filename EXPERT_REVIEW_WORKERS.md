# Worker Loops - Odds & Settlement Services

## 1. Prematch Odds Service (src/prematch_odds_service.py)

### Key sections where DB connections might be held:

#### Main Loop (Lines ~50-150)

```python
def fetch_and_store_prematch_odds():
    """Main service loop - fetches odds for all sports"""
    while True:
        try:
            # Get list of sports
            sports = ['soccer', 'basketball', 'tennis', ...]
            
            for sport in sports:
                try:
                    # Fetch odds from GoalServe API (HTTP call - no DB)
                    odds_data = fetch_sport_odds(sport)
                    
                    # Store in database
                    with connection_ctx() as conn:
                        with conn.cursor() as cur:
                            # Insert/update odds
                            cur.execute("INSERT INTO odds ...")
                            conn.commit()
                    # ← Connection is released here
                    
                except RateLimitError as e:
                    logger.warning(f"⚠️ API Error for {sport}: 429 - Too Many Requests")
                    # Skip this sport
                    
                # Wait between sports (GoalServe rate limit)
                time.sleep(60)  # ← No connection held during sleep ✅
                
        except Exception as e:
            logger.error(f"Error in odds service: {e}")
            time.sleep(300)  # Wait 5 minutes before retry
```

#### Specific concerns:

1. **Are connections released before `time.sleep(60)`?** ✅ (appears to be)
2. **HTTP calls to GoalServe** - any DB held during network I/O?
3. **Batch inserts** - how long do transactions stay open?
4. **Error handling** - are connections properly released on exceptions?

---

## 2. Bet Settlement Service (src/bet_settlement_service.py)

### Key sections (Lines ~40-200)

```python
def auto_settle_bets():
    """Main settlement loop"""
    check_interval = 300  # 5 minutes
    
    while True:
        try:
            # Check for pending bets (quick query)
            with connection_ctx() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM bets WHERE status='pending'")
                    pending_count = cur.fetchone()[0]
            # ← Connection released
            
            logger.info(f"Found {pending_count} pending bets to check")
            
            if pending_count > 0:
                # Process settlements
                with connection_ctx() as conn:
                    with conn.cursor() as cur:
                        # Get pending bets
                        cur.execute("SELECT * FROM bets WHERE status='pending'")
                        bets = cur.fetchall()
                    
                    # For each bet, check if match is finished
                    for bet in bets:
                        # HTTP call to check match status
                        match_data = fetch_match_result(bet['match_id'])  # ← No DB held during HTTP?
                        
                        if match_data['status'] == 'finished':
                            # Settle the bet
                            with connection_ctx() as conn2:
                                with conn2.cursor() as cur2:
                                    cur2.execute("UPDATE bets SET status=... WHERE id=...", ...)
                                    # Update user balance
                                    cur2.execute("UPDATE users SET balance=... WHERE id=...", ...)
                                    conn2.commit()
                            # ← Connection released
            
            # Wait before next check
            time.sleep(check_interval)  # ← No connection held during sleep ✅
            
        except Exception as e:
            logger.error(f"Error in settlement service: {e}")
            time.sleep(60)
```

#### Specific concerns:

1. **HTTP calls in loop** - are connections released before calling `fetch_match_result()`?
2. **Long transactions** - how many bets are settled in one transaction?
3. **Web3 credit operations** - do these hold DB connections?
4. **Sleep intervals** - confirmed no connections held? ✅

---

## Questions for Expert:

1. **Worker connection patterns**: Are the workers properly releasing connections before HTTP calls and sleeps?
2. **Batch sizes**: Should settlements be batched differently?
3. **Error recovery**: Are connection leaks possible in exception paths?
4. **Queue pattern**: Should workers use a job queue instead of while-true loops?
5. **Single-flight**: Should GoalServe fetches be deduplicated per sport?

