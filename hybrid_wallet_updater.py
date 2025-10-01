#!/usr/bin/env python3
"""
Hybrid Wallet Updater - Web2 + Web3 USDT Integration
Updates operator_wallets based on revenue_calculations with both USD and USDT support
"""

import os
import sys
import sqlite3
from datetime import datetime, date

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('local_app.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_unprocessed_revenue_calculations(conn):
    """Get all revenue calculation entries that haven't been processed yet"""
    query = """
    SELECT 
        rc.id,
        rc.operator_id,
        rc.calculation_date,
        rc.bookmaker_own_share,
        rc.community_share_30,
        rc.calculation_metadata,
        so.sportsbook_name,
        so.web3_enabled
    FROM revenue_calculations rc
    JOIN sportsbook_operators so ON rc.operator_id = so.id
    WHERE rc.calculation_metadata IN ('false', 'hybrid_processed', 'traditional_processed')
    AND rc.calculation_metadata != 'wallet_updated'
    ORDER BY rc.calculation_date ASC, rc.processed_at ASC
    """
    
    return conn.execute(query).fetchall()

def get_hybrid_wallet_balances(operator_id, conn):
    """Get current USD and USDT wallet balances for an operator"""
    query = """
    SELECT 
        wallet_type,
        current_balance as usd_balance,
        usdt_balance,
        aptos_wallet_address,
        web3_enabled
    FROM operator_wallets 
    WHERE operator_id = ?
    """
    
    wallets = conn.execute(query, (operator_id,)).fetchall()
    
    # Convert to dictionary for easier access
    wallet_dict = {}
    for wallet in wallets:
        wallet_dict[wallet['wallet_type']] = {
            'usd_balance': float(wallet['usd_balance'] or 0),
            'usdt_balance': float(wallet['usdt_balance'] or 0),
            'aptos_wallet_address': wallet['aptos_wallet_address'],
            'web3_enabled': bool(wallet['web3_enabled'])
        }
    
    return wallet_dict

def update_hybrid_wallet_balance(operator_id, wallet_type, new_usd_balance, new_usdt_balance, conn):
    """Update both USD and USDT balance for a specific wallet"""
    query = """
    UPDATE operator_wallets 
    SET current_balance = ?, usdt_balance = ?, updated_at = ?
    WHERE operator_id = ? AND wallet_type = ?
    """
    
    conn.execute(query, (new_usd_balance, new_usdt_balance, datetime.now(), operator_id, wallet_type))

def execute_hybrid_wallet_transfers(operator_id, wallet_updates, conn):
    """Execute USDT transfers for wallet updates (simulated for now)"""
    
    try:
        from src.services.hybrid_wallet_service import HybridWalletService
        
        hybrid_service = HybridWalletService()
        
        print(f"   💱 Executing hybrid wallet transfers...")
        
        for wallet_type, update_info in wallet_updates.items():
            usd_change = update_info['usd_change']
            usdt_change = update_info['usdt_change']
            
            if usdt_change != 0:
                # Record USDT transaction (simulated for now)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO usdt_transactions 
                    (entity_type, entity_id, wallet_type, transaction_type, usdt_amount,
                     usdt_contract, status, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)
                """, (
                    'operator',
                    operator_id,
                    wallet_type,
                    'wallet_update',
                    usdt_change,
                    "0x6fa59123f70611f2868a5262b22d8c62f354dd6acdf78444e914eb88e677a745::simple_usdt::SimpleUSDT",
                    f'Wallet update: {usd_change:+.2f} USD, {usdt_change:+.2f} USDT',
                    datetime.now()
                ))
                
                print(f"   ✅ {wallet_type}: {usdt_change:+.2f} USDT transfer recorded")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error in hybrid wallet transfers: {e}")
        return False

def process_hybrid_revenue_calculation(revenue_calc, conn):
    """Process a single revenue calculation entry and update both USD and USDT wallets"""
    calc_id = revenue_calc['id']
    operator_id = revenue_calc['operator_id']
    operator_name = revenue_calc['sportsbook_name']
    calculation_date = revenue_calc['calculation_date']
    bookmaker_share = float(revenue_calc['bookmaker_own_share'] or 0)
    community_share = float(revenue_calc['community_share_30'] or 0)
    web3_enabled = bool(revenue_calc['web3_enabled'])
    
    print(f"\n🏢 Processing operator: {operator_name} (ID: {operator_id})")
    print(f"   📅 Calculation date: {calculation_date}")
    print(f"   🔗 Web3 enabled: {web3_enabled}")
    print(f"   💰 Bookmaker share: ${bookmaker_share:.2f}")
    print(f"   🌍 Community share: ${community_share:.2f}")
    
    # Get current hybrid wallet balances
    current_wallets = get_hybrid_wallet_balances(operator_id, conn)
    
    bookmaker_capital = current_wallets.get('bookmaker_capital', {})
    liquidity_pool = current_wallets.get('liquidity_pool', {})
    revenue_wallet = current_wallets.get('revenue', {})
    community_wallet = current_wallets.get('community', {})
    
    print(f"   🏦 Current balances:")
    print(f"      - Bookmaker capital: ${bookmaker_capital.get('usd_balance', 0):.2f} USD, {bookmaker_capital.get('usdt_balance', 0):.2f} USDT")
    print(f"      - Liquidity pool: ${liquidity_pool.get('usd_balance', 0):.2f} USD, {liquidity_pool.get('usdt_balance', 0):.2f} USDT")
    print(f"      - Revenue wallet: ${revenue_wallet.get('usd_balance', 0):.2f} USD, {revenue_wallet.get('usdt_balance', 0):.2f} USDT")
    print(f"      - Community wallet: ${community_wallet.get('usd_balance', 0):.2f} USD, {community_wallet.get('usdt_balance', 0):.2f} USDT")
    
    # Track wallet updates
    wallet_updates = {}
    
    # Process bookmaker_own_share (goes to bookmaker_capital, overflow to revenue)
    bookmaker_capital_before_usd = bookmaker_capital.get('usd_balance', 0)
    bookmaker_capital_before_usdt = bookmaker_capital.get('usdt_balance', 0)
    revenue_wallet_before_usd = revenue_wallet.get('usd_balance', 0)
    revenue_wallet_before_usdt = revenue_wallet.get('usdt_balance', 0)
    
    new_bookmaker_capital_usd = bookmaker_capital_before_usd + bookmaker_share
    new_bookmaker_capital_usdt = bookmaker_capital_before_usdt + bookmaker_share
    new_revenue_wallet_usd = revenue_wallet_before_usd
    new_revenue_wallet_usdt = revenue_wallet_before_usdt
    
    surplus_usd = 0
    surplus_usdt = 0
    deficit_usd = 0
    deficit_usdt = 0
    
    if bookmaker_share > 0:  # Positive revenue day
        if new_bookmaker_capital_usd > 10000:
            surplus_usd = new_bookmaker_capital_usd - 10000
            surplus_usdt = new_bookmaker_capital_usdt - 10000
            new_bookmaker_capital_usd = 10000
            new_bookmaker_capital_usdt = 10000
            new_revenue_wallet_usd += surplus_usd
            new_revenue_wallet_usdt += surplus_usdt
            
            print(f"   📈 Bookmaker capital update (Profit Day):")
            print(f"      - New balance: ${new_bookmaker_capital_usd:.2f} USD, {new_bookmaker_capital_usdt:.2f} USDT (capped at $10,000)")
            print(f"      - Surplus to revenue: ${surplus_usd:.2f} USD, {surplus_usdt:.2f} USDT")
            print(f"      - New revenue wallet: ${new_revenue_wallet_usd:.2f} USD, {new_revenue_wallet_usdt:.2f} USDT")
            
            # Track updates
            wallet_updates['bookmaker_capital'] = {
                'usd_change': new_bookmaker_capital_usd - bookmaker_capital_before_usd,
                'usdt_change': new_bookmaker_capital_usdt - bookmaker_capital_before_usdt
            }
            wallet_updates['revenue'] = {
                'usd_change': new_revenue_wallet_usd - revenue_wallet_before_usd,
                'usdt_change': new_revenue_wallet_usdt - revenue_wallet_before_usdt
            }
        else:
            print(f"   📈 Bookmaker capital update (Profit Day):")
            print(f"      - New balance: ${new_bookmaker_capital_usd:.2f} USD, {new_bookmaker_capital_usdt:.2f} USDT")
            
            # Track updates
            wallet_updates['bookmaker_capital'] = {
                'usd_change': new_bookmaker_capital_usd - bookmaker_capital_before_usd,
                'usdt_change': new_bookmaker_capital_usdt - bookmaker_capital_before_usdt
            }
    
    elif bookmaker_share < 0:  # Negative revenue day (loss)
        if new_bookmaker_capital_usd < 0:
            # Bookmaker capital can't go negative, so we absorb the deficit
            deficit_usd = abs(new_bookmaker_capital_usd)
            deficit_usdt = abs(new_bookmaker_capital_usdt)
            new_bookmaker_capital_usd = 0
            new_bookmaker_capital_usdt = 0
            
            print(f"   📉 Bookmaker capital update (Loss Day):")
            print(f"      - New balance: ${new_bookmaker_capital_usd:.2f} USD, {new_bookmaker_capital_usdt:.2f} USDT (capped at $0)")
            print(f"      - Deficit absorbed: ${deficit_usd:.2f} USD, {deficit_usdt:.2f} USDT")
            print(f"      - Note: Losses beyond bookmaker capital are absorbed by the system")
            
            # Track updates
            wallet_updates['bookmaker_capital'] = {
                'usd_change': new_bookmaker_capital_usd - bookmaker_capital_before_usd,
                'usdt_change': new_bookmaker_capital_usdt - bookmaker_capital_before_usdt
            }
        else:
            print(f"   📉 Bookmaker capital update (Loss Day):")
            print(f"      - New balance: ${new_bookmaker_capital_usd:.2f} USD, {new_bookmaker_capital_usdt:.2f} USDT")
            
            # Track updates
            wallet_updates['bookmaker_capital'] = {
                'usd_change': new_bookmaker_capital_usd - bookmaker_capital_before_usd,
                'usdt_change': new_bookmaker_capital_usdt - bookmaker_capital_before_usdt
            }
    
    else:  # Zero revenue day
        print(f"   📊 Bookmaker capital update (Break-even Day):")
        print(f"      - Balance unchanged: ${new_bookmaker_capital_usd:.2f} USD, {new_bookmaker_capital_usdt:.2f} USDT")
    
    # Process community_share_30 (goes to community wallet)
    community_wallet_before_usd = community_wallet.get('usd_balance', 0)
    community_wallet_before_usdt = community_wallet.get('usdt_balance', 0)
    new_community_wallet_usd = community_wallet_before_usd + community_share
    new_community_wallet_usdt = community_wallet_before_usdt + community_share
    
    if community_share != 0:
        print(f"   🌍 Community wallet update:")
        print(f"      - Change: ${community_share:+.2f} USD, {community_share:+.2f} USDT")
        print(f"      - New balance: ${new_community_wallet_usd:.2f} USD, {new_community_wallet_usdt:.2f} USDT")
        
        # Track updates
        wallet_updates['community'] = {
            'usd_change': community_share,
            'usdt_change': community_share
        }
    
    # Execute hybrid wallet transfers (if Web3 enabled)
    if web3_enabled and wallet_updates:
        transfer_success = execute_hybrid_wallet_transfers(operator_id, wallet_updates, conn)
        if not transfer_success:
            print(f"   ⚠️ USDT transfers failed, proceeding with USD-only updates")
    
    # Update wallet balances in database
    if 'bookmaker_capital' in wallet_updates:
        update_hybrid_wallet_balance(
            operator_id, 'bookmaker_capital', 
            new_bookmaker_capital_usd, 
            new_bookmaker_capital_usdt if web3_enabled else bookmaker_capital_before_usdt,
            conn
        )
    
    if 'revenue' in wallet_updates:
        update_hybrid_wallet_balance(
            operator_id, 'revenue', 
            new_revenue_wallet_usd, 
            new_revenue_wallet_usdt if web3_enabled else revenue_wallet_before_usdt,
            conn
        )
    
    if 'community' in wallet_updates:
        update_hybrid_wallet_balance(
            operator_id, 'community', 
            new_community_wallet_usd, 
            new_community_wallet_usdt if web3_enabled else community_wallet_before_usdt,
            conn
        )
    
    # Mark revenue calculation as processed
    update_query = """
    UPDATE revenue_calculations 
    SET calculation_metadata = 'wallet_updated'
    WHERE id = ?
    """
    conn.execute(update_query, (calc_id,))
    
    print(f"   ✅ Hybrid wallet update completed")
    
    return True

def update_hybrid_operator_wallets():
    """Main function to update operator wallets with hybrid support"""
    
    print(f"🔄 Starting hybrid operator wallet updates for {date.today()}")
    
    conn = get_db_connection()
    
    try:
        # Get all unprocessed revenue calculations
        unprocessed_calcs = get_unprocessed_revenue_calculations(conn)
        
        if not unprocessed_calcs:
            print("✅ No unprocessed revenue calculations found")
            return
        
        print(f"📊 Found {len(unprocessed_calcs)} unprocessed revenue calculations")
        
        processed_count = 0
        
        for revenue_calc in unprocessed_calcs:
            try:
                success = process_hybrid_revenue_calculation(revenue_calc, conn)
                if success:
                    processed_count += 1
                else:
                    print(f"   ❌ Failed to process calculation ID {revenue_calc['id']}")
                    
            except Exception as e:
                print(f"   ❌ Error processing calculation ID {revenue_calc['id']}: {e}")
                continue
        
        # Commit all changes
        conn.commit()
        print(f"\n🎉 Hybrid wallet updates completed successfully!")
        print(f"📊 Processed {processed_count}/{len(unprocessed_calcs)} revenue calculations")
        
    except Exception as e:
        print(f"❌ Error during hybrid wallet updates: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

def get_wallet_balance_summary(operator_id=None):
    """Get summary of wallet balances for analysis"""
    
    conn = get_db_connection()
    
    try:
        # Base query for wallet balances
        base_query = """
        SELECT 
            ow.operator_id,
            so.sportsbook_name,
            so.web3_enabled,
            ow.wallet_type,
            ow.current_balance as usd_balance,
            ow.usdt_balance,
            ow.aptos_wallet_address,
            ow.updated_at
        FROM operator_wallets ow
        JOIN sportsbook_operators so ON ow.operator_id = so.id
        WHERE so.is_active = TRUE
        """
        
        if operator_id:
            base_query += " AND ow.operator_id = ?"
            params = (operator_id,)
        else:
            params = ()
        
        base_query += " ORDER BY ow.operator_id, ow.wallet_type"
        
        results = conn.execute(base_query, params).fetchall()
        
        print(f"\n📊 Wallet Balance Summary")
        print("=" * 100)
        
        if not results:
            print("No wallet data found")
            return
        
        current_operator = None
        total_usd = 0
        total_usdt = 0
        
        for result in results:
            if current_operator != result['operator_id']:
                if current_operator is not None:
                    print()
                current_operator = result['operator_id']
                print(f"\n🏢 {result['sportsbook_name']} (ID: {result['operator_id']}) - Web3: {result['web3_enabled']}")
                print("-" * 80)
            
            usd_bal = result['usd_balance'] or 0
            usdt_bal = result['usdt_balance'] or 0
            wallet_type = result['wallet_type']
            aptos_addr = result['aptos_wallet_address']
            
            sync_status = "✅" if abs(usd_bal - usdt_bal) < 0.01 else "❌"
            
            print(f"  {wallet_type.upper()}:")
            print(f"    USD: ${usd_bal:.2f}")
            print(f"    USDT: {usdt_bal:.2f}")
            print(f"    Sync: {sync_status}")
            if aptos_addr:
                print(f"    Aptos: {aptos_addr}")
            print(f"    Updated: {result['updated_at']}")
            
            total_usd += usd_bal
            total_usdt += usdt_bal
        
        print(f"\n📈 TOTALS:")
        print(f"  Total USD: ${total_usd:.2f}")
        print(f"  Total USDT: {total_usdt:.2f}")
        print(f"  Overall Sync: {'✅' if abs(total_usd - total_usdt) < 0.01 else '❌'}")
        
    except Exception as e:
        print(f"❌ Error getting wallet summary: {e}")
    finally:
        conn.close()

def main():
    """Main entry point"""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'summary':
            # Show wallet balance summary
            operator_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            get_wallet_balance_summary(operator_id)
        else:
            # Run wallet updates
            update_hybrid_operator_wallets()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
