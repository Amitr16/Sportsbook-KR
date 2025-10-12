#!/usr/bin/env python3
"""
Crash EV Unit Test
Validates that for house parameter alpha (RTP), the expected return per 1-unit bet
is approximately alpha for a range of cashout targets x, using provably-fair RNG.

Model (Option A):
  r ~ U(0,1) via HMAC(server_seed, f"{client_seed}:{nonce}")
  raw = alpha / (1 - r)              # true crash multiplier (unclamped)
  m   = min(max(raw, 1.0), CAP)      # displayed multiplier (for UI only)
  win(x) iff raw >= x                # IMPORTANT: compare x to 'raw', not 'm'
  payout = x if win else 0           # stake normalized to 1 (EV is payout)

Theoretical EV at any fixed x (<= CAP) is alpha.

Run:
  python crash_ev_test.py
"""

import hmac, hashlib, math, statistics, sys

ALPHA = 0.96
CAP   = 20.0
SERVER_SEED = b"unit-test-server-seed"
CLIENT_SEED = "unit-test-client"
N_ROUNDS = 200_000
CASHOUTS = [1.5, 2.0, 3.0, 5.0, 10.0, 19.9]

def hmac_uniform(server_key: bytes, message: str) -> float:
    """Return r in [0,1) from HMAC-SHA256(server_key, message)."""
    digest = hmac.new(server_key, message.encode(), hashlib.sha256).digest()
    # take first 8 bytes => 64-bit int, scale to [0,1)
    n = int.from_bytes(digest[:8], "big")
    return (n >> 11) / (1 << 53)  # 53-bit mantissa like JS Math.random

def play_round(alpha: float, r: float):
    """Return raw (true multiplier) and m (clamped UI multiplier)."""
    raw = alpha / (1.0 - r)
    m = max(1.0, min(raw, CAP))
    return raw, m

def simulate(alpha: float, x: float) -> float:
    total = 0.0
    for i in range(N_ROUNDS):
        r = hmac_uniform(SERVER_SEED, f"{CLIENT_SEED}:{i}")
        raw, _ = play_round(alpha, r)
        total += (x if raw >= x else 0.0)
    return total / N_ROUNDS  # EV per 1 unit bet

def main():
    print("Crash EV Unit Test")
    print(f"alpha (target RTP): {ALPHA:.4f}, cap: {CAP:.1f}, rounds: {N_ROUNDS:,}")
    ok = True
    for x in CASHOUTS:
        ev = simulate(ALPHA, x)
        diff_bp = (ev - ALPHA) * 10_000  # basis points
        print(f"x={x:>5}: EV={ev:.6f}  target={ALPHA:.6f}  diff={diff_bp:+.1f} bp")
        # allow ±50 bp tolerance (0.50%) due to finite sampling
        if abs(ev - ALPHA) > 0.005:
            ok = False
    # Additional sanity: instant-crash prob = 1 - alpha
    # Using raw < 1 condition
    inst_p = 0.0
    for i in range(N_ROUNDS):
        r = hmac_uniform(SERVER_SEED, f"{CLIENT_SEED}:inst:{i}")
        raw, _ = play_round(ALPHA, r)
        inst_p += (1.0 if raw < 1.0 else 0.0)
    inst_p /= N_ROUNDS
    print(f"Instant crash prob ~ {inst_p:.4%} (theory={(1-ALPHA):.4%})")

    if not ok:
        print("❌ EV check failed (outside tolerance).")
        sys.exit(1)
    print("✅ EV checks passed (≈ alpha across x).")

if __name__ == "__main__":
    main()
