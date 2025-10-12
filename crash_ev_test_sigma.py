#!/usr/bin/env python3
"""
Crash EV Unit Test (with statistical tolerance)
- Uses per-x 3σ tolerance based on Binomial variance: Var(I_reach(x)) = p(1-p)
- EV(x) = x * p, with p = alpha/x. Std error for EV estimator:
    se_EV = x * sqrt( p*(1-p) / N )
  We accept if |EV_hat - alpha| <= z * se_EV, with z=3 (≈99.7% conf).
- N can be set via env N_ROUNDS (default 2_000_000).
"""

import os, hmac, hashlib, math, sys

ALPHA = float(os.getenv("ALPHA", "0.96"))
CAP   = float(os.getenv("CAP", "20.0"))
SERVER_SEED = os.getenv("SERVER_SEED", "unit-test-server-seed").encode()
CLIENT_SEED = os.getenv("CLIENT_SEED", "unit-test-client")
N_ROUNDS = int(os.getenv("N_ROUNDS", "2000000"))
CASHOUTS = [1.5, 2.0, 3.0, 5.0, 10.0, 19.9]
Z = 3.0  # 3-sigma

def hmac_uniform(server_key: bytes, message: str) -> float:
    """Return r in [0,1) from HMAC-SHA256(server_key, message)."""
    digest = hmac.new(server_key, message.encode(), hashlib.sha256).digest()
    # Use full 256 bits to build a uniform float in [0,1)
    n = int.from_bytes(digest, "big")
    return n / float(1 << (8*len(digest)))  # divide by 2^256

def simulate_ev(alpha: float, x: float) -> float:
    total = 0.0
    for i in range(N_ROUNDS):
        r = hmac_uniform(SERVER_SEED, f"{CLIENT_SEED}:{i}")
        raw = alpha / (1.0 - r)   # unbounded raw multiplier
        total += (x if raw >= x else 0.0)
    return total / N_ROUNDS

def main():
    print("Crash EV Unit Test (3σ tolerance)")
    print(f"alpha: {ALPHA:.6f}  cap:{CAP:.1f}  rounds:{N_ROUNDS:,}  z={Z}")
    ok = True
    for x in CASHOUTS:
        p = ALPHA / x                      # success probability at cashout x
        se_ev = x * math.sqrt(p*(1-p)/N_ROUNDS)
        ev = simulate_ev(ALPHA, x)
        diff = ev - ALPHA
        within = abs(diff) <= Z * se_ev
        status = "OK " if within else "FAIL"
        print(f"x={x:>5}: EV={ev:.6f}  diff={diff:+.6f}  se={se_ev:.6f}  |diff|/se={abs(diff)/se_ev:.2f}  -> {status}")
        if not within:
            ok = False
    # Instant crash check (Option A display model): P = 1 - alpha
    inst = 0
    for i in range(N_ROUNDS):
        r = hmac_uniform(SERVER_SEED, f"{CLIENT_SEED}:inst:{i}")
        raw = ALPHA / (1.0 - r)
        if raw < 1.0: inst += 1
    inst_p = inst / N_ROUNDS
    print(f"Instant crash fraction ≈ {inst_p:.4%} (theory {(1-ALPHA):.4%})")
    if not ok:
        print("❌ Some EV checks failed beyond 3σ (increase N_ROUNDS or review logic).")
        sys.exit(1)
    print("✅ All EV checks within 3σ tolerance of alpha.")

if __name__ == "__main__":
    main()
