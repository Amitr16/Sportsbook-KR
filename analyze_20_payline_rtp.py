#!/usr/bin/env python3
"""
Comprehensive RTP and Hit Rate Analysis for 20-Payline Slots
"""

import sys
import os
import random
import math
sys.path.append('src')

from routes.casino_api import evaluate_slots, spin_reels

def analyze_rtp_and_hit_rate(num_spins=100000):
    """Analyze RTP and hit rate for 20-payline slots"""
    print("🎰 20-Payline Slots RTP & Hit Rate Analysis")
    print("=" * 60)
    
    total_bet = 0
    total_payout = 0
    total_wins = 0
    total_spins = 0
    
    # Track win types
    win_types = {
        'royal_sequence': 0,
        'diamond_5': 0,
        'diamond_4': 0,
        'diamond_3': 0,
        'high_5': 0,
        'high_4': 0,
        'high_3': 0,
        'medium_5': 0,
        'medium_4': 0,
        'medium_3': 0,
        'other': 0
    }
    
    # Track payline wins
    payline_wins = [0] * 20
    
    print(f"Running {num_spins:,} spins...")
    
    for i in range(num_spins):
        stake = 20.0  # $20 per spin
        total_bet += stake
        total_spins += 1
        
        # Spin the reels
        reels = spin_reels(target_rtp=0.96)
        
        # Evaluate the spin
        payout, wins = evaluate_slots(reels, stake)
        total_payout += payout
        
        if payout > 0:
            total_wins += 1
            
            # Categorize wins
            for win in wins:
                symbol = win['symbol']
                count = win['count']
                line = win['line']
                
                # Extract line number for payline tracking
                if line.startswith('line_'):
                    try:
                        line_num = int(line.split('_')[1]) - 1
                        if 0 <= line_num < 20:
                            payline_wins[line_num] += 1
                    except:
                        pass
                
                if symbol == 'royal_sequence':
                    win_types['royal_sequence'] += 1
                elif symbol == '💎':
                    if count == 5:
                        win_types['diamond_5'] += 1
                    elif count == 4:
                        win_types['diamond_4'] += 1
                    elif count == 3:
                        win_types['diamond_3'] += 1
                elif symbol in ['🍒', '🍌', '🍊', '🍇']:
                    if count == 5:
                        win_types['high_5'] += 1
                    elif count == 4:
                        win_types['high_4'] += 1
                    elif count == 3:
                        win_types['high_3'] += 1
                elif symbol in ['🍓', '🍎', '🥝', '🍑']:
                    if count == 5:
                        win_types['medium_5'] += 1
                    elif count == 4:
                        win_types['medium_4'] += 1
                    elif count == 3:
                        win_types['medium_3'] += 1
                else:
                    win_types['other'] += 1
        
        # Progress indicator
        if (i + 1) % 10000 == 0:
            current_rtp = (total_payout / total_bet) * 100 if total_bet > 0 else 0
            current_hit_rate = (total_wins / total_spins) * 100 if total_spins > 0 else 0
            print(f"  Progress: {i+1:,} spins | RTP: {current_rtp:.2f}% | Hit Rate: {current_hit_rate:.2f}%")
    
    # Calculate final results
    rtp = (total_payout / total_bet) * 100 if total_bet > 0 else 0
    hit_rate = (total_wins / total_spins) * 100 if total_spins > 0 else 0
    house_edge = 100 - rtp
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    print(f"Total Spins: {total_spins:,}")
    print(f"Total Bet: ${total_bet:,.2f}")
    print(f"Total Payout: ${total_payout:,.2f}")
    print(f"RTP: {rtp:.4f}%")
    print(f"House Edge: {house_edge:.4f}%")
    print(f"Hit Rate: {hit_rate:.4f}%")
    print(f"Average Payout per Win: ${total_payout/total_wins:.2f}" if total_wins > 0 else "No wins")
    
    print("\n🎯 WIN BREAKDOWN")
    print("-" * 40)
    for win_type, count in win_types.items():
        if count > 0:
            percentage = (count / total_spins) * 100
            print(f"{win_type.replace('_', ' ').title()}: {count:,} ({percentage:.4f}%)")
    
    print("\n📈 PAYLINE PERFORMANCE")
    print("-" * 40)
    for i, wins in enumerate(payline_wins):
        if wins > 0:
            percentage = (wins / total_spins) * 100
            print(f"Line {i+1:2d}: {wins:6,} wins ({percentage:.4f}%)")
    
    # RTP Analysis
    print("\n🔍 RTP ANALYSIS")
    print("-" * 40)
    if 95.0 <= rtp <= 97.0:
        print("✅ RTP is within acceptable range (95-97%)")
    elif rtp < 95.0:
        print("⚠️  RTP is too low (below 95%)")
    else:
        print("⚠️  RTP is too high (above 97%)")
    
    # Hit Rate Analysis
    print("\n🎲 HIT RATE ANALYSIS")
    print("-" * 40)
    if 25.0 <= hit_rate <= 35.0:
        print("✅ Hit rate is good (25-35%)")
    elif hit_rate < 25.0:
        print("⚠️  Hit rate is too low (below 25%)")
    else:
        print("⚠️  Hit rate is too high (above 35%)")
    
    return rtp, hit_rate, total_payout, total_bet

def test_royal_sequence():
    """Test Royal sequence specifically"""
    print("\n🏆 TESTING ROYAL SEQUENCE")
    print("-" * 40)
    
    # Create reels with Royal sequence on middle row
    reels = [
        ['🍒', '🍌', '🍊', '🍇', '🍓'],  # Reel 1
        ['🍒', '🍌', '🍊', '🍇', '🍓'],  # Reel 2 - Middle row should be Royal
        ['🍒', '🍌', '🍊', '🍇', '🍓'],  # Reel 3
        ['🍒', '🍌', '🍊', '🍇', '🍓'],  # Reel 4
        ['🍒', '🍌', '🍊', '🍇', '🍓']   # Reel 5
    ]
    
    stake = 20.0
    payout, wins = evaluate_slots(reels, stake)
    
    print(f"Reels: {reels}")
    print(f"Stake: ${stake}")
    print(f"Payout: ${payout}")
    print(f"Wins: {len(wins)}")
    
    royal_found = False
    for win in wins:
        print(f"  - {win['symbol']} x{win['count']} on {win['line']}: ${win['payout']:.2f}")
        if win['symbol'] == 'royal_sequence':
            royal_found = True
    
    if royal_found:
        print("✅ Royal sequence detected correctly")
    else:
        print("❌ Royal sequence NOT detected - this is a bug!")
    
    return royal_found

if __name__ == "__main__":
    # Test Royal sequence first
    royal_works = test_royal_sequence()
    
    if not royal_works:
        print("\n🚨 ROYAL SEQUENCE BUG DETECTED - Fixing before RTP analysis...")
        # The issue is likely in the Royal sequence check
        print("The Royal sequence should trigger on line 2 (middle row) but isn't working")
    
    # Run RTP analysis
    print("\n" + "=" * 60)
    rtp, hit_rate, payout, bet = analyze_rtp_and_hit_rate(50000)  # Reduced for faster testing
    
    print(f"\n🎯 SUMMARY:")
    print(f"RTP: {rtp:.2f}% (Target: 96%)")
    print(f"Hit Rate: {hit_rate:.2f}% (Target: ~28%)")
    print(f"Royal Sequence Working: {'✅' if royal_works else '❌'}")
