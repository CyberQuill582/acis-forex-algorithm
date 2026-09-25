"""EXTERNAL R1 audit probe: C-BT-12 'variance-matched to its null within 1 +/- 0.05' — at WHICH horizon?
Re-implements the repo generator's defaults (tests/backtest/synthetic_market.py, read-only): 20 s ticks,
daily_vol 0.005, drift_sigma 0.15 per step, episodes 1-4 h with random sign. Compares planted/null variance
at the native step and at the daily horizon."""
import numpy as np
rng = np.random.default_rng(7)
tick_s, daily_vol, drift_sigma = 20, 0.005, 0.15
tpd = 86400 // tick_s; days = 250; n = tpd * days
s = daily_vol / np.sqrt(tpd)
noise = rng.normal(0, s, n)
drift = np.empty(n); k = 0
while k < n:
    L = rng.integers(round(3600 / tick_s), round(4 * 3600 / tick_s) + 1)
    drift[k:k + L] = rng.choice([-1.0, 1.0]) * drift_sigma * s; k += L
planted = noise + drift
for name, h in (("step (20 s)", 1), ("1 hour", 180), ("1 day", tpd)):
    v_null = noise[: n // h * h].reshape(-1, h).sum(1).var()
    v_pl = planted[: n // h * h].reshape(-1, h).sum(1).var()
    print(f"{name:12} planted/null variance ratio {v_pl / v_null:7.3f}   within 1 +/- 0.05: {abs(v_pl / v_null - 1) <= 0.05}")
