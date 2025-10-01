#!/usr/bin/env python3
"""
Hybrid Revenue Calculator - Web2 + Web3 USDT Integration
Updates revenue_calculations table with daily profit/loss calculations and distributes both USD and USDT
"""

import os
import sys
import sqlite3
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('local_app.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_operator_hybrid_wallet_balances(operator_id, conn):
    """Get both USD and USDT balances for operator wallets"""
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
    
    results = conn.execute(query, (operator_id,)).fetchall()
    
    wallets = {}
    for result in results:
        wallets[result['wallet_type']] = {
            'usd_balance': float(result['usd_balance'] or 0),
            'usdt_balance': float(result['usdt_balance'] or 0),
            'aptos_wallet_address': result['aptos_wallet_address'],
            'web3_enabled': bool(result['web3_enabled'])
        }
    
    return wallets

def calculate_hybrid_revenue_distribution(profit, wallets):
    """Calculate revenue distribution for both USD and USDT based on profit/loss and wallet balances"""
    
    bookmaker_capital = wallets.get('bookmaker_capital', {}).get('usd_balance', 0)
    liquidity_pool = wallets.get('liquidity_pool', {}).get('usd_balance', 0)
    
    # Avoid division by zero
    total_wallet_balance = bookmaker_capital + liquidity_pool
    if total_wallet_balance == 0:
        return {
            'bookmaker_own_share': 0.0,
            'kryzel_fee_from_own': 0.0,
            'bookmaker_net_own': 0.0,
            'community_share_30': 0.0,
            'remaining_profit': 0.0,
            'usdt_bookmaker_own_share': 0.0,
            'usdt_kryzel_fee_from_own': 0.0,
            'usdt_community_share_30': 0.0,
            'usdt_remaining_profit': 0.0
        }
    
    # Calculate ratios
    bookmaker_ratio = bookmaker_capital / total_wallet_balance
    liquidity_ratio = liquidity_pool / total_wallet_balance
    
    if profit > 0:
        # Profit distribution (same for USD and USDT)
        bookmaker_own_share = (0.90 * profit * bookmaker_ratio) + (0.60 * profit * liquidity_ratio)
        kryzel_fee_from_own = 0.10 * profit
        bookmaker_net_own = 0.0
        community_share_30 = 0.30 * profit * liquidity_ratio
        
    else:
        # Loss distribution (same for USD and USDT)
        bookmaker_own_share = (0.95 * profit * bookmaker_ratio) + (0.65 * profit * liquidity_ratio)
        kryzel_fee_from_own = 0.0
        bookmaker_net_own = 0.0
        community_share_30 = 0.35 * profit * liquidity_ratio
    
    return {
        # USD distributions
        'bookmaker_own_share': round(bookmaker_own_share, 2),
        'kryzel_fee_from_own': round(kryzel_fee_from_own, 2),
        'bookmaker_net_own': round(bookmaker_net_own, 2),
        'community_share_30': round(community_share_30, 2),
        'remaining_profit': 0.0,
        
        # USDT distributions (mirror USD amounts)
        'usdt_bookmaker_own_share': round(bookmaker_own_share, 2),
        'usdt_kryzel_fee_from_own': round(kryzel_fee_from_own, 2),
        'usdt_community_share_30': round(community_share_30, 2),
        'usdt_remaining_profit': 0.0
    }

def execute_hybrid_revenue_distribution(operator_id, distribution, wallets, conn):
    """Execute the actual USD and USDT transfers for revenue distribution"""
    
    try:
        from src.services.hybrid_wallet_service import HybridWalletService
        
        hybrid_service = HybridWalletService()
        
        print(f"   💱 Executing hybrid revenue distribution...")
        
        # Check if operator has Web3 enabled
        cursor = conn.cursor()
        cursor.execute("SELECT web3_enabled FROM sportsbook_operators WHERE id = ?", (operator_id,))
        result = cursor.fetchone()
        web3_enabled = bool(result[0]) if result else False
        
        if not web3_enabled:
            print(f"   ⚠️ Web3 not enabled for operator {operator_id}, skipping USDT distributions")
            return execute_traditional_revenue_distribution(operator_id, distribution, conn)
        
        # 1. Transfer bookmaker_own_share to revenue wallet
        if distribution['bookmaker_own_share'] != 0:
            # Update revenue wallet (USD)
            cursor.execute("""
                UPDATE operator_wallets 
                SET current_balance = current_balance + ?
                WHERE operator_id = ? AND wallet_type = 'revenue'
            """, (distribution['bookmaker_own_share'], operator_id))
            
            # Update revenue wallet (USDT) - simulated for now
            cursor.execute("""
                UPDATE operator_wallets 
                SET usdt_balance = usdt_balance + ?
                WHERE operator_id = ? AND wallet_type = 'revenue'
            """, (distribution['usdt_bookmaker_own_share'], operator_id))
            
            print(f"   ✅ Revenue wallet: +${distribution['bookmaker_own_share']} USD, +{distribution['usdt_bookmaker_own_share']} USDT")
        
        # 2. Transfer community_share_30 to community wallet
        if distribution['community_share_30'] != 0:
            # Update community wallet (USD)
            cursor.execute("""
                UPDATE operator_wallets 
                SET current_balance = current_balance + ?
                WHERE operator_id = ? AND wallet_type = 'community'
            """, (distribution['community_share_30'], operator_id))
            
            # Update community wallet (USDT) - simulated for now
            cursor.execute("""
                UPDATE operator_wallets 
                SET usdt_balance = usdt_balance + ?
                WHERE operator_id = ? AND wallet_type = 'community'
            """, (distribution['usdt_community_share_30'], operator_id))
            
            print(f"   ✅ Community wallet: +${distribution['community_share_30']} USD, +{distribution['usdt_community_share_30']} USDT")
        
        # 3. Record USDT revenue distribution transaction
        cursor.execute("""
            INSERT INTO usdt_revenue_distributions 
            (operator_id, distribution_date, total_profit_usd, total_profit_usdt,
             bookmaker_share_usd, bookmaker_share_usdt, community_share_usd, community_share_usdt,
             kryzel_fee_usd, kryzel_fee_usdt, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
        """, (
            operator_id,
            date.today(),
            distribution['bookmaker_own_share'] + distribution['community_share_30'],
            distribution['usdt_bookmaker_own_share'] + distribution['usdt_community_share_30'],
            distribution['bookmaker_own_share'],
            distribution['usdt_bookmaker_own_share'],
            distribution['community_share_30'],
            distribution['usdt_community_share_30'],
            distribution['kryzel_fee_from_own'],
            distribution['usdt_kryzel_fee_from_own'],
            datetime.now()
        ))
        
        print(f"   ✅ Hybrid revenue distribution completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Error in hybrid revenue distribution: {e}")
        # Fall back to traditional distribution
        return execute_traditional_revenue_distribution(operator_id, distribution, conn)

def execute_traditional_revenue_distribution(operator_id, distribution, conn):
    """Execute traditional USD-only revenue distribution"""
    
    try:
        cursor = conn.cursor()
        
        print(f"   💵 Executing traditional USD revenue distribution...")
        
        # 1. Transfer bookmaker_own_share to revenue wallet
        if distribution['bookmaker_own_share'] != 0:
            cursor.execute("""
                UPDATE operator_wallets 
                SET current_balance = current_balance + ?
                WHERE operator_id = ? AND wallet_type = 'revenue'
            """, (distribution['bookmaker_own_share'], operator_id))
            
            print(f"   ✅ Revenue wallet: +${distribution['bookmaker_own_share']} USD")
        
        # 2. Transfer community_share_30 to community wallet
        if distribution['community_share_30'] != 0:
            cursor.execute("""
                UPDATE operator_wallets 
                SET current_balance = current_balance + ?
                WHERE operator_id = ? AND wallet_type = 'community'
            """, (distribution['community_share_30'], operator_id))
            
            print(f"   ✅ Community wallet: +${distribution['community_share_30']} USD")
        
        print(f"   ✅ Traditional revenue distribution completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Error in traditional revenue distribution: {e}")
        return False

def get_previous_total_revenue(operator_id, conn):
    """Get the previous total_revenue from the last revenue_calculations record"""
    query = """
    SELECT total_revenue 
    FROM revenue_calculations 
    WHERE operator_id = ? 
    ORDER BY calculation_date DESC, processed_at DESC 
    LIMIT 1
    """
    
    result = conn.execute(query, (operator_id,)).fetchone()
    return float(result['total_revenue'] or 0) if result else 0.0

def update_hybrid_daily_revenue_calculations():
    """Main function to update revenue_calculations table for all operators with hybrid support"""
    
    print(f"🔄 Starting hybrid daily revenue calculations for {date.today()}")
    
    conn = get_db_connection()
    
    try:
        # Get all active operators
        operators_query = """
        SELECT id, sportsbook_name, web3_enabled 
        FROM sportsbook_operators 
        WHERE is_active = TRUE
        """
        
        operators = conn.execute(operators_query).fetchall()
        
        if not operators:
            print("❌ No active operators found")
            return
        
        print(f"📊 Found {len(operators)} active operators")
        
        for operator in operators:
            operator_id = operator['id']
            operator_name = operator['sportsbook_name']
            web3_enabled = bool(operator['web3_enabled'])
            
            print(f"\n🏢 Processing operator: {operator_name} (ID: {operator_id})")
            print(f"   🔗 Web3 Enabled: {web3_enabled}")
            
            # Get current total_revenue from sportsbook_operators table
            current_revenue_query = """
            SELECT total_revenue 
            FROM sportsbook_operators 
            WHERE id = ?
            """
            
            current_result = conn.execute(current_revenue_query, (operator_id,)).fetchone()
            current_total_revenue = float(current_result['total_revenue'] or 0)
            
            # Get previous total_revenue from last revenue_calculations record
            previous_total_revenue = get_previous_total_revenue(operator_id, conn)
            
            # Calculate today's profit
            todays_profit = current_total_revenue - previous_total_revenue
            
            print(f"   💰 Current total_revenue: ${current_total_revenue:.2f}")
            print(f"   📈 Previous total_revenue: ${previous_total_revenue:.2f}")
            print(f"   📊 Today's profit: ${todays_profit:.2f}")
            
            # Get hybrid wallet balances
            wallets = get_operator_hybrid_wallet_balances(operator_id, conn)
            
            print(f"   🏦 Wallet Balances:")
            for wallet_type, wallet_info in wallets.items():
                print(f"      {wallet_type.upper()}:")
                print(f"        USD: ${wallet_info['usd_balance']:.2f}")
                print(f"        USDT: {wallet_info['usdt_balance']:.2f}")
                if wallet_info['aptos_wallet_address']:
                    print(f"        Aptos: {wallet_info['aptos_wallet_address']}")
            
            # Calculate hybrid revenue distribution
            distribution = calculate_hybrid_revenue_distribution(todays_profit, wallets)
            
            print(f"   📋 Hybrid Distribution:")
            print(f"      USD:")
            print(f"        - Bookmaker own share: ${distribution['bookmaker_own_share']:.2f}")
            print(f"        - Kryzel fee: ${distribution['kryzel_fee_from_own']:.2f}")
            print(f"        - Community share (30%): ${distribution['community_share_30']:.2f}")
            
            if web3_enabled:
                print(f"      USDT:")
                print(f"        - Bookmaker own share: {distribution['usdt_bookmaker_own_share']:.2f}")
                print(f"        - Kryzel fee: {distribution['usdt_kryzel_fee_from_own']:.2f}")
                print(f"        - Community share (30%): {distribution['usdt_community_share_30']:.2f}")
            
            # Execute the revenue distribution
            distribution_success = execute_hybrid_revenue_distribution(
                operator_id, distribution, wallets, conn
            )
            
            if not distribution_success:
                print(f"   ⚠️ Revenue distribution failed, skipping record creation")
                continue
            
            # Insert new revenue calculation record
            insert_query = """
            INSERT INTO revenue_calculations (
                operator_id, calculation_date, total_revenue, total_bets_amount, 
                total_payouts, bookmaker_own_share, kryzel_fee_from_own, 
                bookmaker_net_own, community_share_30, remaining_profit, 
                calculation_metadata, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(insert_query, (
                operator_id,
                date.today(),
                current_total_revenue,
                0.0,  # total_bets_amount - set to zero as requested
                0.0,  # total_payouts - set to zero as requested
                distribution['bookmaker_own_share'],
                distribution['kryzel_fee_from_own'],
                distribution['bookmaker_net_own'],
                distribution['community_share_30'],
                distribution['remaining_profit'],
                'hybrid_processed' if web3_enabled else 'traditional_processed',
                datetime.now()
            ))
            
            print(f"   ✅ Hybrid revenue calculation record created")
        
        # Commit all changes
        conn.commit()
        print(f"\n🎉 Hybrid daily revenue calculations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during hybrid revenue calculations: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

def get_revenue_distribution_summary(operator_id=None, days=7):
    """Get summary of revenue distributions for analysis"""
    
    conn = get_db_connection()
    
    try:
        # Base query for revenue calculations
        base_query = """
        SELECT 
            rc.operator_id,
            so.sportsbook_name,
            rc.calculation_date,
            rc.total_revenue,
            rc.bookmaker_own_share,
            rc.community_share_30,
            rc.kryzel_fee_from_own,
            rc.calculation_metadata,
            urd.bookmaker_share_usdt,
            urd.community_share_usdt,
            urd.kryzel_fee_usdt
        FROM revenue_calculations rc
        JOIN sportsbook_operators so ON rc.operator_id = so.id
        LEFT JOIN usdt_revenue_distributions urd ON rc.operator_id = urd.operator_id 
            AND rc.calculation_date = urd.distribution_date
        WHERE rc.calculation_date >= date('now', '-{} days')
        """.format(days)
        
        if operator_id:
            base_query += " AND rc.operator_id = ?"
            params = (operator_id,)
        else:
            params = ()
        
        base_query += " ORDER BY rc.calculation_date DESC, rc.operator_id"
        
        results = conn.execute(base_query, params).fetchall()
        
        print(f"\n📊 Revenue Distribution Summary (Last {days} days)")
        print("=" * 100)
        
        if not results:
            print("No revenue distributions found")
            return
        
        current_operator = None
        total_usd_distributed = 0
        total_usdt_distributed = 0
        
        for result in results:
            if current_operator != result['operator_id']:
                if current_operator is not None:
                    print()
                current_operator = result['operator_id']
                print(f"\n🏢 {result['sportsbook_name']} (ID: {result['operator_id']})")
                print("-" * 60)
            
            date_str = result['calculation_date']
            usd_total = (result['bookmaker_own_share'] or 0) + (result['community_share_30'] or 0)
            usdt_total = (result['bookmaker_share_usdt'] or 0) + (result['community_share_usdt'] or 0)
            
            print(f"  {date_str}:")
            print(f"    USD: ${usd_total:.2f} (Bookmaker: ${result['bookmaker_own_share'] or 0:.2f}, Community: ${result['community_share_30'] or 0:.2f})")
            
            if result['bookmaker_share_usdt'] is not None:
                print(f"    USDT: {usdt_total:.2f} (Bookmaker: {result['bookmaker_share_usdt']:.2f}, Community: {result['community_share_usdt']:.2f})")
            else:
                print(f"    USDT: Not distributed")
            
            print(f"    Type: {result['calculation_metadata'] or 'traditional'}")
            
            total_usd_distributed += usd_total
            total_usdt_distributed += usdt_total
        
        print(f"\n📈 TOTALS:")
        print(f"  Total USD Distributed: ${total_usd_distributed:.2f}")
        print(f"  Total USDT Distributed: {total_usdt_distributed:.2f}")
        
    except Exception as e:
        print(f"❌ Error getting revenue summary: {e}")
    finally:
        conn.close()

def main():
    """Main entry point"""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'summary':
            # Show revenue distribution summary
            operator_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
            get_revenue_distribution_summary(operator_id, days)
        else:
            # Run daily revenue calculations
            update_hybrid_daily_revenue_calculations()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
