"""R1-C task 1: the whole-path demeaning bias, restated for R-1 (pooled, daily, breadth) and the fix.

Synthetic only (numpy). Daily-analogue of tests/backtest/synthetic_market.py:113-114 at BASE 974dbda
(`mean = math.fsum(out) / n` ... `r - mean`), which the lead already confirmed on the PRODUCTION
generator (CLOUD_AUDIT/reports/evidence/LEAD/probe_bridge_production.py). This probe does not redo
that; it asks what the bias does to R-1's instruments of choice:
  (1) slow rules (126-day momentum, EWMA crossovers at Carver speeds, the 63/126/252 vote) and the
      mirror-image reversal rules;
  (2) POOLED over N instruments: the bias has the same sign on every path, so it adds coherently
      while noise averages -> the pooled Sharpe bias grows like sqrt(N);
  (3) the three kinds: null, planted (multi-day episodes), permuted. Variants:
        BASE        demean the whole path (every kind)
        FIX-A       demean nothing
        FIX-B       demean only the planted drift component (noise untouched)
        FIX-C       permuted := random sign-flip of the shuffled planted returns (a martingale
                    difference sequence given the pool: exact zero expected P&L for any
                    non-anticipating rule), instead of shuffle-then-demean.
Closed form (demeaned iid path, lookback L, hold h, length n):
    E[sign(P) F] = -(h/n) * s * sqrt(L) / sqrt(1 - L/n) * sqrt(2/pi)        per holding step
  -> annual-Sharpe drag of one instrument ~= -sqrt(252 * L) * sqrt(2/pi) / (n * sqrt(1 - L/n))
Usage: OMP_NUM_THREADS=1 python repro_bridge.py [paths] [seed]
"""
import math
import sys

import numpy as np

P = int(sys.argv[1]) if len(sys.argv) > 1 else 400
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260925
S = 0.005                      # daily sd (the generator's default daily_vol)
N_INST = 20


def pnl_rules(x, first):
    """x: (paths, n) daily log returns. Returns dict rule -> (paths,) summed daily P&L over [first, n),
    unit notional, position decided on data up to t-1, no costs (a pure mean test)."""
    lp = np.concatenate([np.zeros((x.shape[0], 1)), np.cumsum(x, axis=1)], axis=1)  # lp[:, t] = log price after t returns
    n = x.shape[1]
    out = {}
    # 126-day momentum, rebalanced daily
    L = 126
    pos = np.sign(lp[:, first:n] - lp[:, first - L:n - L])          # uses lp up to index t only
    fwd = x[:, first:n]
    out["mom126"] = (pos * fwd).sum(axis=1)
    out["rev126"] = -out["mom126"]
    # 63/126/252 vote
    v = sum(np.sign(lp[:, first:n] - lp[:, first - L:n - L]) for L in (63, 126, 252))
    out["vote"] = (np.sign(v) * fwd).sum(axis=1)
    # EWMA crossovers on log price (Carver-style speeds), daily rebalance
    for f in (8, 16, 32):
        sl = 4 * f
        af, asl = 2 / (f + 1), 2 / (sl + 1)
        ef = np.zeros(x.shape[0]); es = np.zeros(x.shape[0])
        acc = np.zeros(x.shape[0])
        for t in range(1, n + 1):          # lp[:, t] known after return t-1 (0-based)
            if t - 1 >= first:
                acc += np.sign(ef - es) * x[:, t - 1]
            ef += af * (lp[:, t] - ef); es += asl * (lp[:, t] - es)
        out[f"ewmac{f}_{sl}"] = acc
    return out


def closed_form(L, n, first, s=S):
    per_step = -(1 / n) * s * math.sqrt(L) / math.sqrt(1 - L / n) * math.sqrt(2 / math.pi)
    return per_step * (n - first)


def summarize(tag, res, n_active, n_inst=N_INST):
    """Per-instrument mean P&L per path, its t, and the annual Sharpe of the POOLED book
    (equal-weight N independent instruments) implied by mean/sd."""
    print(f"-- {tag}")
    yrs = n_active / 252
    for k, v in res.items():
        v = np.asarray(v)
        m, sd = v.mean(), v.std(ddof=1)
        t = m / (sd / math.sqrt(len(v)))
        sr1 = (m / yrs) / (S * math.sqrt(252))                       # one instrument
        srN = sr1 * math.sqrt(n_inst)                                # pooled, independent
        print(f"   {k:12s} mean/path {m:+.5f}  t {t:+6.1f}  frac<0 {np.mean(v < 0):.3f}  "
              f"annual SR bias 1 inst {sr1:+.3f}  pooled N={n_inst} {srN:+.3f}")


def episodes_drift(rng, paths, n, lo, hi, d):
    """Multi-day planted episodes (daily analogue): +-d per day for lo..hi days, random sign."""
    out = np.zeros((paths, n))
    for p in range(paths):
        k = 0
        while k < n:
            ln = rng.integers(lo, hi + 1)
            out[p, k:k + ln] = d * rng.choice((-1.0, 1.0))
            k += ln
    return out


def main():
    rng = np.random.default_rng(SEED)
    for n in (705, 3640):                  # the ladder's 2.8 y span; 14 y (2012-2025)
        first = 260
        noise = rng.normal(0.0, S, size=(P * N_INST // 10, n))
        print(f"=== NULL, n={n} weekdays, {noise.shape[0]} paths, first graded day {first}")
        summarize("BASE (whole-path demeaned)", pnl_rules(noise - noise.mean(axis=1, keepdims=True), first), n - first)
        summarize("FIX-A (undemeaned)", pnl_rules(noise, first), n - first)
        for L in (126,):
            print(f"   closed form mom{L} BASE mean/path {closed_form(L, n, first):+.5f}")
    # planted / permuted, daily analogue with multi-day episodes (5-20 days, 0.15 sd/day)
    n, first = 705, 260
    paths = P * N_INST // 10
    noise = rng.normal(0.0, S, size=(paths, n))
    drift = episodes_drift(rng, paths, n, 5, 20, 0.15 * S)
    planted = noise + drift
    shuf = np.array([rng.permutation(row) for row in planted])
    flips = rng.choice((-1.0, 1.0), size=shuf.shape)
    print(f"=== PLANTED / PERMUTED daily analogue, n={n}, {paths} paths, episodes 5-20 d at 0.15 sd/day")
    summarize("planted BASE (demean all)", pnl_rules(planted - planted.mean(axis=1, keepdims=True), first), n - first)
    summarize("planted FIX-A (demean none)", pnl_rules(planted, first), n - first)
    summarize("planted FIX-B (demean drift only)", pnl_rules(noise + drift - drift.mean(axis=1, keepdims=True), first), n - first)
    summarize("permuted BASE (shuffle, demean)", pnl_rules(shuf - shuf.mean(axis=1, keepdims=True), first), n - first)
    summarize("permuted undemeaned shuffle", pnl_rules(shuf, first), n - first)
    summarize("permuted FIX-C (shuffle + sign-flip)", pnl_rules(shuf * flips, first), n - first)
    print("net path drift sd, planted undemeaned: %.4f  (noise-only sd %.4f)"
          % (planted.sum(axis=1).std(), noise.sum(axis=1).std()))


if __name__ == "__main__":
    main()
