#!/usr/bin/env python3
"""
Compare the test implementation with the actual game implementation
"""

import hmac
import hashlib

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

def crash_multiplier_game(target_rtp, server_seed="default_server_seed", client_seed="default_client_seed", nonce=0):
    """ACTUAL GAME IMPLEMENTATION (from casino_api.py)"""
    alpha = float(target_rtp)  # e.g. 0.96

    # provably-fair r in [0,1)
    r = uniform_from_seeds(server_seed, client_seed, nonce)

    # ✅ Correct α-scaled fair crash:
    #   M_fair = 1/(1-r) has tail P(M_fair >= x) = 1/x
    #   M = α * M_fair  ⇒  P(M >= x) = α/x  ⇒ EV at any cashout x is α
    denom = max(1e-12, 1.0 - r)
    m = alpha / denom

    # Map the <1x mass (prob = 1-α) to an explicit 1.00x insta-bust
    if m < 1.0:
        m = 1.0

    # Cap at 20x for risk management (matches UI)
    m = min(m, 20.0)

    return round(m, 2)

def crash_multiplier_test(alpha, r):
    """TEST IMPLEMENTATION (from crash_ev_test_sigma.py)"""
    raw = alpha / (1.0 - r)   # unbounded raw multiplier
    return raw

def test_comparison():
    """Compare the two implementations"""
    
    print("🔍 COMPARING GAME vs TEST IMPLEMENTATIONS")
    print("=" * 60)
    
    alpha = 0.96
    test_cases = [
        ("Test 1", "seed1", "client1", 1000),
        ("Test 2", "seed1", "client1", 1001),
        ("Test 3", "seed1", "client1", 1002),
    ]
    
    for name, server_seed, client_seed, nonce in test_cases:
        print(f"\n{name}:")
        
        # Generate r using game's method
        r = uniform_from_seeds(server_seed, client_seed, nonce)
        print(f"  r = {r:.10f}")
        
        # Game implementation
        game_multiplier = crash_multiplier_game(alpha, server_seed, client_seed, nonce)
        print(f"  Game multiplier: {game_multiplier:.2f}x")
        
        # Test implementation
        test_raw = crash_multiplier_test(alpha, r)
        print(f"  Test raw: {test_raw:.10f}")
        
        # Check if they match
        if abs(game_multiplier - test_raw) < 0.01:
            print(f"  ✅ MATCH!")
        else:
            print(f"  ❌ DIFFERENT!")

def analyze_win_logic():
    """Analyze the win determination logic"""
    
    print(f"\n🎯 WIN DETERMINATION LOGIC ANALYSIS:")
    print("=" * 50)
    
    print("TEST IMPLEMENTATION:")
    print("  raw = alpha / (1 - r)")
    print("  win = (raw >= cashout_x)")
    print("  payout = cashout_x if win else 0")
    print("  ✅ CORRECT: Uses raw multiplier for win determination")
    
    print(f"\nGAME IMPLEMENTATION:")
    print("  m = alpha / (1 - r)")
    print("  if m < 1.0: m = 1.0")
    print("  m = min(m, 20.0)")
    print("  win = (m >= cashout_x)  # ❌ WRONG!")
    print("  payout = cashout_x if win else 0")
    print("  ❌ PROBLEM: Uses clamped multiplier for win determination")
    
    print(f"\n🚨 CRITICAL ISSUE FOUND:")
    print("  The game uses the CLAMPED multiplier (m) for win determination")
    print("  But it should use the RAW multiplier for win determination")
    print("  This breaks the RTP calculation!")

if __name__ == "__main__":
    test_comparison()
    analyze_win_logic()
