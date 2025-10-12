#!/usr/bin/env python3
"""
Verify 96% RTP Calculation for Updated Slots Paytable
"""

# Updated paytable (96% RTP)
PAYOUT_MULTIPLIERS = {
    '💎': [0, 0, 81, 400, 4200],      # Diamond: 3=81x, 4=400x, 5=4200x
    '🍒': [0, 0, 33, 160, 1005],      # High fruits: 3=33x, 4=160x, 5=1005x
    '🍌': [0, 0, 33, 160, 1005],      # High fruits: 3=33x, 4=160x, 5=1005x
    '🍊': [0, 0, 33, 160, 1005],      # High fruits: 3=33x, 4=160x, 5=1005x
    '🍇': [0, 0, 33, 160, 1005],      # High fruits: 3=33x, 4=160x, 5=1005x
    '🍓': [0, 0, 17, 66, 505],        # Medium fruits: 3=17x, 4=66x, 5=505x
    '🍎': [0, 0, 17, 66, 505],        # Medium fruits: 3=17x, 4=66x, 5=505x
    '🥝': [0, 0, 17, 66, 505],        # Medium fruits: 3=17x, 4=66x, 5=505x
    '🍑': [0, 0, 17, 66, 505],        # Medium fruits: 3=17x, 4=66x, 5=505x
}

# Symbol probabilities (from actual reel strip: 100 stops total)
SYMBOL_PROBS = {
    '💎': 1/100,   # Diamond: 1 stop
    '🍒': 7/100,   # Cherry: 7 stops
    '🍌': 7/100,   # Banana: 7 stops
    '🍊': 7/100,   # Orange: 7 stops
    '🍇': 7/100,   # Grape: 7 stops
    '🍓': 19/100,  # Strawberry: 19 stops
    '🍎': 18/100,  # Apple: 18 stops
    '🥝': 17/100,  # Kiwi: 17 stops
    '🍑': 17/100   # Peach: 17 stops
}

def calculate_rtp():
    """Calculate RTP using corrected logic"""
    
    print("🎰 RTP Verification for 96% Paytable")
    print("=" * 50)
    
    # 1. Calculate per-line expected payout using EXACTLY counts
    per_line_expected = 0.0
    
    print("\n📊 Per-Line Expected Payouts (EXACTLY counts):")
    print("-" * 50)
    
    for symbol, prob in SYMBOL_PROBS.items():
        multipliers = PAYOUT_MULTIPLIERS[symbol]
        
        # CORRECT: Use EXACTLY 3/4/5 of a kind
        exact3 = prob**3 * (1 - prob) * multipliers[2]  # Exactly 3, 4th must differ
        exact4 = prob**4 * (1 - prob) * multipliers[3]  # Exactly 4, 5th must differ  
        exact5 = prob**5 * multipliers[4]                # Exactly 5
        
        total_exact = exact3 + exact4 + exact5
        
        print(f"{symbol}: 3={exact3:.6f}, 4={exact4:.6f}, 5={exact5:.6f} → Total: {total_exact:.6f}")
        
        per_line_expected += total_exact
    
    print(f"\n✅ Per-line expected payout: {per_line_expected:.6f}")
    
    # 2. Calculate Royal Sequence probability (middle row only) - 2000x
    royal_prob = (SYMBOL_PROBS['🍒'] * SYMBOL_PROBS['🍌'] * 
                  SYMBOL_PROBS['🍊'] * SYMBOL_PROBS['🍇'] * 
                  SYMBOL_PROBS['🍓'])
    royal_payout = 2000.0  # 2000x multiplier
    royal_expected = royal_prob * royal_payout
    
    print(f"\n🏆 Royal Sequence (middle row only):")
    print(f"   Probability: {royal_prob:.8f}")
    print(f"   Payout: {royal_payout}x")
    print(f"   Expected: {royal_expected:.6f}")
    
    # 3. Calculate total expected payout
    # 5 paylines + Royal sequence
    total_expected = (5 * per_line_expected) + royal_expected
    
    print(f"\n📈 Total Expected Payout:")
    print(f"   5 paylines: {5 * per_line_expected:.6f}")
    print(f"   Royal sequence: {royal_expected:.6f}")
    print(f"   Total: {total_expected:.6f}")
    
    # 4. Calculate RTP (CORRECT: divide by total bet)
    # Total bet = 5 lines × 1 per line = 5
    total_bet = 5.0
    rtp = total_expected / total_bet
    house_edge = 1.0 - rtp
    
    print(f"\n🎯 FINAL RESULTS:")
    print(f"   Total Expected Payout: {total_expected:.6f}")
    print(f"   Total Bet: {total_bet}")
    print(f"   RTP: {rtp:.6f} ({rtp*100:.4f}%)")
    print(f"   House Edge: {house_edge:.6f} ({house_edge*100:.4f}%)")
    
    return rtp, house_edge

def show_paytable():
    """Display the new paytable"""
    print("\n🎰 NEW 96% RTP PAYTABLE:")
    print("=" * 40)
    print("Royal Sequence (middle row): 2000x")
    print("\n5 of a kind:")
    print("  💎 Diamond: 4200x")
    print("  🍒🍌🍊🍇 High fruits: 1005x")
    print("  🍓🍎🥝🍑 Medium fruits: 505x")
    print("\n4 of a kind:")
    print("  💎 Diamond: 400x")
    print("  🍒🍌🍊🍇 High fruits: 160x")
    print("  🍓🍎🥝🍑 Medium fruits: 66x")
    print("\n3 of a kind:")
    print("  💎 Diamond: 81x")
    print("  🍒🍌🍊🍇 High fruits: 33x")
    print("  🍓🍎🥝🍑 Medium fruits: 17x")

if __name__ == "__main__":
    show_paytable()
    rtp, house_edge = calculate_rtp()
    
    print(f"\n🎉 VERIFICATION RESULT:")
    print(f"   Target RTP: 96.13%")
    print(f"   Actual RTP: {rtp*100:.4f}%")
    print(f"   Difference: {abs(rtp*100 - 96.13):.4f}%")
    
    if abs(rtp*100 - 96.13) < 0.1:
        print("   ✅ SUCCESS: RTP is very close to target!")
    else:
        print("   ⚠️  WARNING: RTP differs from target")
