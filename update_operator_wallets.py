#!/usr/bin/env python3
"""
Operator Wallets Updater
Updates operator_wallets based on revenue_calculations table entries that haven't been processed yet
"""

import os
import sys
from datetime import datetime, date

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables (same as main app)
from src.config.env_loader import *  # noqa: F401 - just to execute the loader

from src import sqlite3_shim as sqlite3

def get_db_connection():
    """Get database connection using the same method as the main app"""
    conn = sqlite3.connect()
    conn.row_factory = sqlite3.Row
    return conn

def get_unprocessed_revenue_calculations(conn):
    """Get all revenue calculation entries that haven't been processed yet (metadata = 'false')"""
    query = """
    SELECT 
        rc.id,
        rc.operator_id,
        rc.calculation_date,
        rc.bookmaker_own_share,
        rc.community_share_30,
        rc.kryzel_fee_from_own,
        so.sportsbook_name
    FROM revenue_calculations rc
    JOIN sportsbook_operators so ON rc.operator_id = so.id
    WHERE rc.calculation_metadata = 'false'
    ORDER BY rc.calculation_date ASC, rc.processed_at ASC
    """
    
    return conn.execute(query).fetchall()

def get_current_wallet_balances(operator_id, conn):
    """Get current wallet balances for an operator"""
    query = """
    SELECT 
        wallet_type,
        current_balance
    FROM operator_wallets 
    WHERE operator_id = ?
    """
    
    wallets = conn.execute(query, (operator_id,)).fetchall()
    
    # Convert to dictionary for easier access
    wallet_dict = {}
    for wallet in wallets:
        wallet_dict[wallet['wallet_type']] = float(wallet['current_balance'] or 0)
    
    return wallet_dict

def update_wallet_balance(operator_id, wallet_type, new_balance, conn):
    """Update a specific wallet balance for an operator"""
    query = """
    UPDATE operator_wallets 
    SET current_balance = ?, updated_at = ?
    WHERE operator_id = ? AND wallet_type = ?
    """
    
    conn.execute(query, (new_balance, datetime.now(), operator_id, wallet_type))

def process_revenue_calculation(revenue_calc, conn):
    """Process a single revenue calculation entry and update wallets"""
    calc_id = revenue_calc['id']
    operator_id = revenue_calc['operator_id']
    operator_name = revenue_calc['sportsbook_name']
    calculation_date = revenue_calc['calculation_date']
    bookmaker_share = float(revenue_calc['bookmaker_own_share'] or 0)
    community_share = float(revenue_calc['community_share_30'] or 0)
    kryzel_fee = float(revenue_calc['kryzel_fee_from_own'] or 0)
    
    print(f"\n Processing operator: {operator_name} (ID: {operator_id})")
    print(f"    Calculation date: {calculation_date}")
    print(f"    Bookmaker share: ${bookmaker_share:.2f}")
    print(f"    Community share: ${community_share:.2f}")
    print(f"    Kryzel fee: ${kryzel_fee:.2f}")
    
    # Get current wallet balances
    current_wallets = get_current_wallet_balances(operator_id, conn)
    
    bookmaker_capital_before = current_wallets.get('bookmaker_capital', 0)
    liquidity_pool_before = current_wallets.get('liquidity_pool', 0)
    revenue_wallet_before = current_wallets.get('revenue', 0)
    
    print(f"    Current balances:")
    print(f"      - Bookmaker capital: ${bookmaker_capital_before:.2f}")
    print(f"      - Liquidity pool: ${liquidity_pool_before:.2f}")
    print(f"      - Revenue wallet: ${revenue_wallet_before:.2f}")
    
    # Process bookmaker_own_share
    new_bookmaker_capital = bookmaker_capital_before + bookmaker_share
    surplus = 0
    deficit = 0
    
    if bookmaker_share > 0:  # Positive revenue day
        if new_bookmaker_capital > 10000:
            surplus = new_bookmaker_capital - 10000
            new_bookmaker_capital = 10000
            new_revenue_wallet = revenue_wallet_before + surplus
            
            print(f"    Bookmaker capital update (Profit Day):")
            print(f"      - New balance: ${new_bookmaker_capital:.2f} (capped at $10,000)")
            print(f"      - Surplus to revenue: ${surplus:.2f}")
            print(f"      - New revenue wallet: ${new_revenue_wallet:.2f}")
            
            # Update both wallets
            update_wallet_balance(operator_id, 'bookmaker_capital', new_bookmaker_capital, conn)
            update_wallet_balance(operator_id, 'revenue', new_revenue_wallet, conn)
        else:
            print(f"    Bookmaker capital update (Profit Day):")
            print(f"      - New balance: ${new_bookmaker_capital:.2f}")
            
            # Update only bookmaker capital
            update_wallet_balance(operator_id, 'bookmaker_capital', new_bookmaker_capital, conn)
    
    elif bookmaker_share < 0:  # Negative revenue day (loss)
        if new_bookmaker_capital < 0:
            # Bookmaker capital can't go negative, so we need to handle the deficit
            deficit = abs(new_bookmaker_capital)
            new_bookmaker_capital = 0
            
            print(f"    Bookmaker capital update (Loss Day):")
            print(f"      - New balance: ${new_bookmaker_capital:.2f} (capped at $0)")
            print(f"      - Deficit absorbed: ${deficit:.2f}")
            print(f"      - Note: Losses beyond bookmaker capital are absorbed by the system")
            
            # Update bookmaker capital to 0
            update_wallet_balance(operator_id, 'bookmaker_capital', new_bookmaker_capital, conn)
        else:
            print(f"    Bookmaker capital update (Loss Day):")
            print(f"      - New balance: ${new_bookmaker_capital:.2f}")
            
            # Update bookmaker capital
            update_wallet_balance(operator_id, 'bookmaker_capital', new_bookmaker_capital, conn)
    
    else:  # Zero revenue day
        print(f"    Bookmaker capital update (Break-even Day):")
        print(f"      - Balance unchanged: ${new_bookmaker_capital:.2f}")
    
    # Process community_share_30
    new_liquidity_pool = liquidity_pool_before + community_share
    
    if community_share > 0:  # Positive community share
        print(f"    Liquidity pool update (Community Gain):")
        print(f"      - New balance: ${new_liquidity_pool:.2f}")
    elif community_share < 0:  # Negative community share (loss)
        if new_liquidity_pool < 0:
            # Liquidity pool can't go negative, so we cap it at 0
            new_liquidity_pool = 0
            print(f"    Liquidity pool update (Community Loss):")
            print(f"      - New balance: ${new_liquidity_pool:.2f} (capped at $0)")
            print(f"      - Note: Community losses beyond liquidity pool are absorbed")
        else:
            print(f"    Liquidity pool update (Community Loss):")
            print(f"      - New balance: ${new_liquidity_pool:.2f}")
    else:  # Zero community share
        print(f"    Liquidity pool update (No Change):")
        print(f"      - Balance unchanged: ${new_liquidity_pool:.2f}")
    
    # Update liquidity pool
    update_wallet_balance(operator_id, 'liquidity_pool', new_liquidity_pool, conn)
    
    # Process Kryzel fee (transfer to global Kryzel wallet)
    if kryzel_fee > 0:
        # Get current Kryzel wallet balance
        kryzel_wallet = conn.execute("""
            SELECT current_balance FROM operator_wallets 
            WHERE operator_id = 0 AND wallet_type = 'kryzel_platform_fee'
        """).fetchone()
        
        if kryzel_wallet:
            new_kryzel_balance = kryzel_wallet['current_balance'] + kryzel_fee
            update_wallet_balance(0, 'kryzel_platform_fee', new_kryzel_balance, conn)
            print(f"    Kryzel fee transfer:")
            print(f"      - Fee amount: ${kryzel_fee:.2f}")
            print(f"      - New Kryzel balance: ${new_kryzel_balance:.2f}")
        else:
            print(f"    Warning: Kryzel wallet not found - fee ${kryzel_fee:.2f} not transferred")
    
    # Mark this revenue calculation as processed
    mark_as_processed_query = """
    UPDATE revenue_calculations 
    SET calculation_metadata = 'true'
    WHERE id = ?
    """
    
    conn.execute(mark_as_processed_query, (calc_id,))
    
    print(f"   Revenue calculation {calc_id} processed and marked as complete")

def update_operator_wallets():
    """Main function to update operator wallets based on unprocessed revenue calculations"""
    
    print(f"Starting operator wallet updates for {date.today()}")
    
    conn = get_db_connection()
    
    try:
        # Get all unprocessed revenue calculations
        unprocessed_calcs = get_unprocessed_revenue_calculations(conn)
        
        if not unprocessed_calcs:
            print(" No unprocessed revenue calculations found")
            return
        
        print(f" Found {len(unprocessed_calcs)} unprocessed revenue calculations")
        
        # Process each revenue calculation
        for revenue_calc in unprocessed_calcs:
            try:
                process_revenue_calculation(revenue_calc, conn)
            except Exception as e:
                print(f" Error processing revenue calculation {revenue_calc['id']}: {e}")
                continue
        
        # Commit all changes
        conn.commit()
        print(f"\n Operator wallet updates completed successfully!")
        print(f" Processed {len(unprocessed_calcs)} revenue calculations")
        
    except Exception as e:
        print(f" Error during wallet updates: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    """Main entry point"""
    try:
        update_operator_wallets()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
