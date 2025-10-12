#!/usr/bin/env python3
"""
Slots Version 2 Win Frequency Analysis
Calculate what percentage of spins result in any win
"""

# Version 2 Slots Configuration (from casino_api.py)
REEL_STRIP = [
    '🍒', '🍌', '🍊', '🍇', '🍓', '🍎', '🥝', '🍑', '💎'
]

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

# Payout multipliers (from casino_api.py - 96% RTP paytable)
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

def calculate_line_win_probability(symbol, count):
    """Calculate probability of getting exactly 'count' of a symbol on one line"""
    prob = SYMBOL_PROBS[symbol]
    
    if count == 3:
        # Exactly 3: prob^3 * (1-prob)^2
        return prob**3 * (1-prob)**2
    elif count == 4:
        # Exactly 4: prob^4 * (1-prob)
        return prob**4 * (1-prob)
    elif count == 5:
        # Exactly 5: prob^5
        return prob**5
    else:
        return 0.0

def calculate_royal_sequence_probability():
    """Calculate probability of Royal Sequence on middle row"""
    # Royal = Cherry-Banana-Orange-Grape-Strawberry
    royal_prob = (SYMBOL_PROBS['🍒'] * SYMBOL_PROBS['🍌'] * 
                  SYMBOL_PROBS['🍊'] * SYMBOL_PROBS['🍇'] * 
                  SYMBOL_PROBS['🍓'])
    return royal_prob

def calculate_per_line_win_probability():
    """Calculate probability of any win on a single line"""
    
    total_win_prob = 0.0
    
    for symbol, prob in SYMBOL_PROBS.items():
        multipliers = PAYOUT_MULTIPLIERS[symbol]
        
        # Calculate probability of each winning count
        for count in [3, 4, 5]:
            win_prob = calculate_line_win_probability(symbol, count)
            if win_prob > 0:
                total_win_prob += win_prob
                print(f"  {symbol} {count} of a kind: {win_prob:.6f} ({win_prob*100:.4f}%)")
    
    return total_win_prob

def calculate_any_win_probability():
    """Calculate probability of any win across all 5 paylines"""
    
    print("🎰 SLOTS VERSION 2 WIN FREQUENCY ANALYSIS")
    print("=" * 60)
    
    # Calculate per-line win probability
    print("\n📊 Per-Line Win Probabilities:")
    per_line_win_prob = calculate_per_line_win_probability()
    print(f"\n✅ Per-line win probability: {per_line_win_prob:.6f} ({per_line_win_prob*100:.4f}%)")
    
    # Calculate Royal Sequence probability (middle row only)
    royal_prob = calculate_royal_sequence_probability()
    print(f"\n🏆 Royal Sequence probability (middle row): {royal_prob:.8f} ({royal_prob*100:.6f}%)")
    
    # Calculate probability of NO wins on any line
    no_win_per_line = 1 - per_line_win_prob
    no_win_all_lines = no_win_per_line ** 5  # 5 paylines
    
    # Calculate probability of ANY win
    any_win_prob = 1 - no_win_all_lines + royal_prob
    
    print(f"\n🎯 WIN FREQUENCY CALCULATION:")
    print(f"  Per-line win probability: {per_line_win_prob:.6f}")
    print(f"  No win per line: {no_win_per_line:.6f}")
    print(f"  No win on all 5 lines: {no_win_all_lines:.6f}")
    print(f"  Royal sequence bonus: {royal_prob:.8f}")
    print(f"  ANY WIN probability: {any_win_prob:.6f}")
    
    return any_win_prob

def simulate_win_frequency():
    """Simulate win frequency to verify calculation"""
    
    print(f"\n🎲 SIMULATION VERIFICATION:")
    print("=" * 30)
    
    import random
    
    n_spins = 100000
    wins = 0
    
    # Simulate spins
    for i in range(n_spins):
        # Generate 5 reels with 3 symbols each
        reels = []
        for reel in range(5):
            symbols = []
            for row in range(3):
                symbol = random.choices(list(SYMBOL_PROBS.keys()), 
                                     weights=list(SYMBOL_PROBS.values()))[0]
                symbols.append(symbol)
            reels.append(symbols)
        
        # Check for wins on each line
        has_win = False
        
        # Check 5 paylines
        lines = [
            [reels[0][0], reels[1][0], reels[2][0], reels[3][0], reels[4][0]],  # Top
            [reels[0][1], reels[1][1], reels[2][1], reels[3][1], reels[4][1]],  # Middle
            [reels[0][2], reels[1][2], reels[2][2], reels[3][2], reels[4][2]],  # Bottom
            [reels[0][0], reels[1][0], reels[2][0], reels[3][2], reels[4][2]],  # Diag1
            [reels[0][2], reels[1][2], reels[2][2], reels[3][0], reels[4][0]]   # Diag2
        ]
        
        for line in lines:
            # Check for 3, 4, 5 of a kind
            for symbol in SYMBOL_PROBS.keys():
                count = line.count(symbol)
                if count >= 3:
                    has_win = True
                    break
            
            if has_win:
                break
            
            # Check for Royal Sequence on middle row
            if line == lines[1]:  # Middle row
                if line == ['🍒', '🍌', '🍊', '🍇', '🍓']:
                    has_win = True
                    break
        
        if has_win:
            wins += 1
    
    simulated_win_rate = wins / n_spins
    print(f"  Simulated {n_spins:,} spins")
    print(f"  Wins: {wins:,}")
    print(f"  Win rate: {simulated_win_rate:.6f} ({simulated_win_rate*100:.4f}%)")
    
    return simulated_win_rate

if __name__ == "__main__":
    theoretical_win_rate = calculate_any_win_probability()
    simulated_win_rate = simulate_win_frequency()
    
    print(f"\n🎉 FINAL RESULTS:")
    print(f"  Theoretical win rate: {theoretical_win_rate*100:.4f}%")
    print(f"  Simulated win rate: {simulated_win_rate*100:.4f}%")
    print(f"  Difference: {abs(theoretical_win_rate - simulated_win_rate)*100:.4f}%")
    
    print(f"\n📈 SUMMARY:")
    print(f"  Approximately {theoretical_win_rate*100:.1f}% of spins will result in some win")
    print(f"  This means about {100-theoretical_win_rate*100:.1f}% of spins will be complete losses")
