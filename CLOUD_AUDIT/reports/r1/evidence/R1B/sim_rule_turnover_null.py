"""R1-B receipt (SYNTHETIC ONLY): forecast scalars, turnover and exposure of the proposed pooled rules
on a driftless Gaussian random walk. No real price data is read or generated from real data.

Why: (1) a forecast scalar that targets mean |forecast| = 10 can be fixed on the null, spending zero
looks at real data (Carver pools scalars across instruments; on a random walk the scalar is a property
of the rule, not the market); (2) turnover and exposure set the rule's cost in Sharpe units, which is
what Carver's speed limit budgets; (3) a forecast threshold's effect on exposure (holding cost) is a
property of the rule and can be measured here. Its effect on captured trend needs a planted market
(R1-C's lab), not this script.

Rules (LLM-transcribed from the public descriptions in Carver's blog/docs; no code copied):
  EWMAC(f,s): (EWMA_f(p) - EWMA_s(p)) / sigma_p, sigma_p = EWMA(span 25) stdev of daily price changes
  BREAKOUT(N): (p - mid_N)/(max_N - min_N), smoothed by EWMA span N/4, mid = (max+min)/2
Position in units of the average position: pos = clip(scalar*raw, -20, 20) / 10.
Turnover = sum|d pos| / 2 / mean|pos| per year (round trips of an average position per year).
"""
import numpy as np

rng = np.random.default_rng(20260925)
YEARS, D = 400, 256            # 400 synthetic years of daily bars (pooled 'instruments' are exchangeable)
n = YEARS * D
p = np.cumsum(rng.standard_normal(n))   # unit daily vol, zero drift

def ewma(x, span):
    a = 2.0 / (span + 1.0)
    out = np.empty_like(x); m = x[0]
    for i, v in enumerate(x):
        m = a * v + (1 - a) * m; out[i] = m
    return out

dp = np.diff(p, prepend=p[0])
sig = np.sqrt(ewma(dp ** 2, 25)); sig[sig == 0] = 1.0
raws = {}
for f, s in ((8, 32), (16, 64), (32, 128), (64, 256)):
    raws[f"EWMAC{f},{s}"] = (ewma(p, f) - ewma(p, s)) / sig
for N in (20, 40, 80, 160):
    from numpy.lib.stride_tricks import sliding_window_view as sw
    w = sw(p, N)
    hi, lo = w.max(axis=1), w.min(axis=1)
    hi = np.concatenate([np.full(N - 1, np.nan), hi]); lo = np.concatenate([np.full(N - 1, np.nan), lo])
    r = (p - (hi + lo) / 2) / np.where(hi - lo > 0, hi - lo, np.nan)
    r = np.nan_to_num(r)
    raws[f"BREAKOUT{N}"] = ewma(r, max(2, N // 4))

burn = 1000
print(f"{'rule':<14}{'scalar':>8}{'turnover/yr':>13}{'P(|f|>=5)':>11}{'E|pos| thr5':>12}{'E|pos| thr10':>13}")
res = {}
for k, raw in raws.items():
    raw = raw[burn:]
    scalar = 10.0 / np.mean(np.abs(raw))
    fc = np.clip(scalar * raw, -20, 20)
    pos = fc / 10.0
    to = np.sum(np.abs(np.diff(pos))) / 2 / np.mean(np.abs(pos)) / (len(pos) / D)
    thr5 = np.where(np.abs(fc) >= 5, pos, 0.0)
    thr10 = np.where(np.abs(fc) >= 10, pos, 0.0)
    res[k] = pos
    print(f"{k:<14}{scalar:>8.2f}{to:>13.1f}{np.mean(np.abs(fc) >= 5):>11.2f}"
          f"{np.mean(np.abs(thr5)) / np.mean(np.abs(pos)):>12.2f}{np.mean(np.abs(thr10)) / np.mean(np.abs(pos)):>13.2f}")
ks = list(res)
C = np.corrcoef(np.vstack([res[k] for k in ks]))
print("\nCorrelation of POSITIONS on the null (a proxy for rule-return correlation under zero drift):")
print(" " * 14 + "".join(f"{k[:9]:>10}" for k in ks))
for i, k in enumerate(ks):
    print(f"{k:<14}" + "".join(f"{C[i, j]:>10.2f}" for j in range(len(ks))))
