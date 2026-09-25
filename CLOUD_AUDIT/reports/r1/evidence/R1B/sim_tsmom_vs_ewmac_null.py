"""R1-B receipt (SYNTHETIC ONLY): is MOP-2012 TSMOM a separate family from slow EWMAC?
Driftless Gaussian random walk; no real data. TSMOM = sign(12-month return) (252 days), rebalanced
monthly (every 21 days); EWMAC(f,s) as in sim_rule_turnover_null.py. Reports correlation of positions
and TSMOM's turnover in the same units (round trips of an average position per year).
"""
import numpy as np

rng = np.random.default_rng(7)
D, n = 256, 256 * 400
p = np.cumsum(rng.standard_normal(n))

def ewma(x, span):
    a = 2.0 / (span + 1.0); out = np.empty_like(x); m = x[0]
    for i, v in enumerate(x):
        m = a * v + (1 - a) * m; out[i] = m
    return out

dp = np.diff(p, prepend=p[0]); sig = np.sqrt(ewma(dp ** 2, 25)); sig[sig == 0] = 1
L = 252
ts = np.zeros(n)
for t in range(L, n):
    ts[t] = np.sign(p[t] - p[t - L]) if (t - L) % 21 == 0 else ts[t - 1]
burn = 1000
ts = ts[burn:]
pos = {"TSMOM12m": ts}
for f, s in ((16, 64), (32, 128), (64, 256)):
    r = ((ewma(p, f) - ewma(p, s)) / sig)[burn:]
    pos[f"EWMAC{f},{s}"] = np.clip(r * 10 / np.mean(np.abs(r)), -20, 20) / 10
for k, v in pos.items():
    to = np.sum(np.abs(np.diff(v))) / 2 / np.mean(np.abs(v)) / (len(v) / D)
    print(f"{k:<12} turnover {to:5.1f} round trips/yr; corr with TSMOM12m = {np.corrcoef(v, ts)[0, 1]:.2f}")
