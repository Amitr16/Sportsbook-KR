#!/usr/bin/env python3
"""
CRASH GAME RTP VERIFICATION
Correctly test the crash game RTP using the proper methodology
"""

import hmac
import hashlib
import statistics

def hmac_sha256(key, msg):
    """HMAC-SHA256 implementation (matches casino_api.py)"""
    return hmac.new(key.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()

def hash_to_uniform_01(hex_string):
    """Convert first 52 bits of hex string to float in [0,1) (matches casino_api.py)"""
    frac_hex = hex_string[:13]
    h = int(frac_hex, 16)
    E = 2 ** 52
    return h / E

def uniform_from_seeds(server_seed, client_seed, nonce):
    """Generate provably fair uniform random number from seeds (matches casino_api.py)"""
    msg = f"{client_seed}:{nonce}"
    hex_hash = hmac_sha256(server_seed, msg)
    return hash_to_uniform_01(hex_hash)

def crash_multiplier(target_rtp, server_seed="default_server_seed", client_seed="default_client_seed", nonce=0):
    """Current crash multiplier implementation (matches casino_api.py)"""
    alpha = float(target_rtp)  # e.g. 0.96

    # provably-fair r in [0,1)
    r = uniform_from_seeds(server_seed, client_seed, nonce)

    # ✅ Correct α-scaled fair crash:
    #   M_fair = 1/(1-r) has tail P(M_fair >= x) = 1/x
    #   M = α * M_fair  ⇒  P(M >= x) = α/x  ⇒ EV at any cashout x is α
    denom = max(1e-12, 1.0 - r)
    raw = alpha / denom

    # Map the <1x mass (prob = 1-α) to an explicit 1.00x insta-bust
    if raw < 1.0:
        m = 1.0
    else:
        m = raw

    # Cap at 20x for risk management (matches UI)
    m = min(m, 20.0)

    return round(m, 2), raw  # Return both visual and raw multiplier

def test_crash_rtp_correctly():
    """Test crash RTP using the CORRECT methodology"""
    
    print("🎯 CRASH GAME RTP VERIFICATION (CORRECT METHOD)")
    print("=" * 60)
    
    target_rtp = 0.96
    n_games = 100000
    
    print(f"Testing {n_games:,} games with target RTP: {target_rtp*100:.1f}%")
    print(f"Testing different cashout strategies...")
    
    # Test different cashout strategies
    cashout_strategies = [1.5, 2.0, 3.0, 5.0, 10.0, 19.9]
    
    for cashout_x in cashout_strategies:
        print(f"\n📊 Testing cashout at {cashout_x}x:")
        
        payouts = []
        wins = 0
        
        for i in range(n_games):
            visual_m, raw_m = crash_multiplier(target_rtp, nonce=i)
            
            # CORRECT: Use raw multiplier to determine if player wins
            # Player wins if the round reached their cashout target
            if raw_m >= cashout_x:
                payout = cashout_x  # Player gets x times their bet
                wins += 1
            else:
                payout = 0.0  # Player loses their bet
            
            payouts.append(payout)
        
        # Calculate RTP for this strategy
        mean_payout = statistics.mean(payouts)
        win_rate = wins / n_games
        theoretical_win_rate = target_rtp / cashout_x
        
        print(f"  Win rate: {win_rate:.4f} ({win_rate*100:.2f}%)")
        print(f"  Theoretical win rate: {theoretical_win_rate:.4f} ({theoretical_win_rate*100:.2f}%)")
        print(f"  Mean payout: {mean_payout:.4f}")
        print(f"  RTP: {mean_payout*100:.2f}%")
        print(f"  Expected RTP: {target_rtp*100:.1f}%")
        
        # Check if RTP is correct
        if abs(mean_payout - target_rtp) < 0.01:
            print(f"  ✅ CORRECT RTP!")
        else:
            print(f"  ❌ WRONG RTP! (diff: {abs(mean_payout - target_rtp)*100:.2f}%)")

def test_visual_multiplier_stats():
    """Test the visual multiplier statistics (for reference)"""
    
    print(f"\n🎲 VISUAL MULTIPLIER STATISTICS:")
    print("=" * 40)
    
    target_rtp = 0.96
    cap = 20.0
    n_games = 100000
    
    visual_multipliers = []
    raw_multipliers = []
    instant_crashes = 0
    capped_games = 0
    
    for i in range(n_games):
        visual_m, raw_m = crash_multiplier(target_rtp, nonce=i)
        visual_multipliers.append(visual_m)
        raw_multipliers.append(raw_m)
        
        if visual_m == 1.0:
            instant_crashes += 1
        if visual_m == 20.0:
            capped_games += 1
    
    mean_visual = statistics.mean(visual_multipliers)
    mean_raw = statistics.mean(raw_multipliers)
    instant_crash_rate = instant_crashes / n_games
    capped_rate = capped_games / n_games
    
    print(f"Visual multiplier stats:")
    print(f"  Mean visual: {mean_visual:.4f}x")
    print(f"  Mean raw: {mean_raw:.4f}x")
    print(f"  Instant crashes: {instant_crashes:,} ({instant_crash_rate*100:.2f}%)")
    print(f"  Capped at 20x: {capped_games:,} ({capped_rate*100:.2f}%)")
    
    # Theoretical mean visual multiplier
    import math
    theoretical_mean = 1 + target_rtp * math.log(cap)
    print(f"  Theoretical mean visual: {theoretical_mean:.4f}x")
    print(f"  Difference: {abs(mean_visual - theoretical_mean):.4f}x")
    
    print(f"\n⚠️  IMPORTANT: Mean visual multiplier ≠ RTP!")
    print(f"   RTP is about player payouts, not visual multiplier!")

if __name__ == "__main__":
    test_crash_rtp_correctly()
    test_visual_multiplier_stats()
    
    print(f"\n🎉 CONCLUSION:")
    print(f"   The crash game should have 96% RTP for ALL cashout strategies")
    print(f"   The visual multiplier mean (~3.88x) is NOT the RTP")
    print(f"   RTP = Expected payout per $1 bet = 96%")
