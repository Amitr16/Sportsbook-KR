#!/usr/bin/env python3
"""
Daily Revenue Calculator
Updates revenue_calculations table with daily profit/loss calculations and revenue distribution
"""

import os
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src import sqlite3_shim as sqlite3

def get_db_connection():
    """Get database connection using the same method as the main app"""
    conn = sqlite3.connect()
    conn.row_factory = sqlite3.Row
    return conn

def get_operator_wallet_balances(operator_id, conn):
    """Get bookmaker_capital and liquidity_pool balances for an operator"""
    query = """
    SELECT 
        SUM(CASE WHEN wallet_type = 'bookmaker_capital' THEN current_balance ELSE 0 END) as bookmaker_capital,
        SUM(CASE WHEN wallet_type = 'liquidity_pool' THEN current_balance ELSE 0 END) as liquidity_pool
    FROM operator_wallets 
    WHERE operator_id = ?
    """
    
    result = conn.execute(query, (operator_id,)).fetchone()
    
    bookmaker_capital = float(result['bookmaker_capital'] or 0)
    liquidity_pool = float(result['liquidity_pool'] or 0)
    
    return bookmaker_capital, liquidity_pool

def calculate_casino_revenue(operator_id, conn):
    """Calculate casino revenue from game_round table for a specific operator"""
    try:
        # Calculate casino revenue from game_round table
        # Revenue = Total stakes - Total payouts (same logic as sportsbook)
        casino_query = """
        SELECT 
            SUM(gr.stake) as total_stakes,
            SUM(gr.payout) as total_payouts
        FROM game_round gr
        JOIN users u ON gr.user_id = u.id::text
        WHERE u.sportsbook_operator_id = ?
        """
        
        result = conn.execute(casino_query, (operator_id,)).fetchone()
        
        total_stakes = float(result['total_stakes'] or 0)
        total_payouts = float(result['total_payouts'] or 0)
        
        # Casino revenue = Money kept from losing games - Money paid to winners
        casino_revenue = total_stakes - total_payouts
        
        return casino_revenue
        
    except Exception as e:
        print(f"Error calculating casino revenue for operator {operator_id}: {e}")
        return 0.0

def calculate_sportsbook_revenue(operator_id, conn):
    """Calculate sportsbook revenue from bets table for a specific operator"""
    try:
        # Calculate sportsbook revenue from settled bets
        sportsbook_query = """
        SELECT 
            SUM(CASE WHEN b.status = 'lost' THEN b.stake ELSE 0 END) as total_stakes_lost,
            SUM(CASE WHEN b.status = 'won' THEN b.actual_return - b.stake ELSE 0 END) as total_net_payouts
        FROM bets b
        JOIN users u ON b.user_id = u.id
        WHERE b.status IN ('won', 'lost') AND u.sportsbook_operator_id = ?
        """
        
        result = conn.execute(sportsbook_query, (operator_id,)).fetchone()
        
        total_stakes_lost = float(result['total_stakes_lost'] or 0)
        total_net_payouts = float(result['total_net_payouts'] or 0)
        
        # Sportsbook revenue = Money kept from losing bets - Extra money paid to winners
        sportsbook_revenue = total_stakes_lost - total_net_payouts
        
        return sportsbook_revenue
        
    except Exception as e:
        print(f"Error calculating sportsbook revenue for operator {operator_id}: {e}")
        return 0.0

def calculate_total_combined_revenue(operator_id, conn):
    """Calculate total revenue combining both sportsbook and casino"""
    try:
        sportsbook_revenue = calculate_sportsbook_revenue(operator_id, conn)
        casino_revenue = calculate_casino_revenue(operator_id, conn)
        
        total_revenue = sportsbook_revenue + casino_revenue
        
        print(f"   📊 Sportsbook revenue: ${sportsbook_revenue:.2f}")
        print(f"   🎰 Casino revenue: ${casino_revenue:.2f}")
        print(f"   💰 Total combined revenue: ${total_revenue:.2f}")
        
        return total_revenue
        
    except Exception as e:
        print(f"Error calculating total combined revenue for operator {operator_id}: {e}")
        return 0.0

def calculate_revenue_distribution(profit, bookmaker_capital, liquidity_pool):
    """Calculate revenue distribution based on profit/loss and wallet balances"""
    
    # Avoid division by zero
    total_wallet_balance = bookmaker_capital + liquidity_pool
    if total_wallet_balance == 0:
        return {
            'bookmaker_own_share': 0.0,
            'kryzel_fee_from_own': 0.0,
            'bookmaker_net_own': 0.0,
            'community_share_30': 0.0,
            'remaining_profit': 0.0
        }
    
    # Calculate ratios
    bookmaker_ratio = bookmaker_capital / total_wallet_balance
    liquidity_ratio = liquidity_pool / total_wallet_balance
    
    if profit > 0:
        # Profit distribution
        bookmaker_own_share = (0.90 * profit * bookmaker_ratio) + (0.60 * profit * liquidity_ratio)
        kryzel_fee_from_own = 0.10 * profit
        bookmaker_net_own = 0.0
        community_share_30 = 0.30 * profit * liquidity_ratio
        
    else:
        # Loss distribution
        bookmaker_own_share = (0.95 * profit * bookmaker_ratio) + (0.65 * profit * liquidity_ratio)
        kryzel_fee_from_own = 0.0
        bookmaker_net_own = 0.0
        community_share_30 = 0.35 * profit * liquidity_ratio
    
    return {
        'bookmaker_own_share': round(bookmaker_own_share, 2),
        'kryzel_fee_from_own': round(kryzel_fee_from_own, 2),
        'bookmaker_net_own': round(bookmaker_net_own, 2),
        'community_share_30': round(community_share_30, 2),
        'remaining_profit': 0.0  # Always 0 as requested
    }

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

def update_daily_revenue_calculations():
    """Main function to update revenue_calculations table for all operators"""
    
    print(f"🔄 Starting daily revenue calculations for {date.today()}")
    
    conn = get_db_connection()
    
    try:
        # Get all active operators
        operators_query = """
        SELECT id, sportsbook_name 
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
            
            print(f"\n🏢 Processing operator: {operator_name} (ID: {operator_id})")
            
            # Calculate current total revenue from both sportsbook and casino
            current_total_revenue = calculate_total_combined_revenue(operator_id, conn)
            
            # Update the sportsbook_operators table with the new combined revenue
            update_operator_revenue_query = """
            UPDATE sportsbook_operators 
            SET total_revenue = ? 
            WHERE id = ?
            """
            conn.execute(update_operator_revenue_query, (current_total_revenue, operator_id))
            
            # Get previous total_revenue from last revenue_calculations record
            previous_total_revenue = get_previous_total_revenue(operator_id, conn)
            
            # Calculate today's profit
            todays_profit = current_total_revenue - previous_total_revenue
            
            print(f"   💰 Current total_revenue: ${current_total_revenue:.2f}")
            print(f"   📈 Previous total_revenue: ${previous_total_revenue:.2f}")
            print(f"   📊 Today's profit: ${todays_profit:.2f}")
            
            # Get wallet balances
            bookmaker_capital, liquidity_pool = get_operator_wallet_balances(operator_id, conn)
            
            print(f"   🏦 Bookmaker capital: ${bookmaker_capital:.2f}")
            print(f"   💧 Liquidity pool: ${liquidity_pool:.2f}")
            
            # Calculate revenue distribution
            distribution = calculate_revenue_distribution(todays_profit, bookmaker_capital, liquidity_pool)
            
            print(f"   📋 Distribution:")
            print(f"      - Bookmaker own share: ${distribution['bookmaker_own_share']:.2f}")
            print(f"      - Kryzel fee: ${distribution['kryzel_fee_from_own']:.2f}")
            print(f"      - Community share (30%): ${distribution['community_share_30']:.2f}")
            print(f"      - Remaining profit: ${distribution['remaining_profit']:.2f}")
            
            # Insert new revenue calculation record
            insert_query = """
            INSERT INTO revenue_calculations (
                operator_id, calculation_date, total_revenue, total_bets_amount, 
                total_payouts, bookmaker_own_share, kryzel_fee_from_own, 
                bookmaker_net_own, community_share_30, remaining_profit, calculation_metadata, processed_at
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
                'false',  # calculation_metadata - set to false to indicate not yet processed
                datetime.now()
            ))
            
            print(f"   ✅ Revenue calculation record created")
        
        # Commit all changes
        conn.commit()
        print(f"\n🎉 Daily revenue calculations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during revenue calculations: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    """Main entry point"""
    try:
        update_daily_revenue_calculations()
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
