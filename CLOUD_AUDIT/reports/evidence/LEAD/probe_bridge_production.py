"""Lead P3 check of C3 finding 2, by a different path than C3's sim_bridge_tilt.py.

C3 re-implemented the demeaning in numpy. This probe calls the PRODUCTION generator,
tests/backtest/synthetic_market._returns, at one tick per weekday (tick_seconds=86400, so
each return is one weekday), and compares it with the SAME rng draws left undemeaned.
It also checks a single 126-day lookback against the closed form for a demeaned iid path:
    E[sign(P) * F] = -(h / (n - L)) * s * sqrt(L * (1 - L/n)) * sqrt(2/pi)   per holding step
(P = past L-day return, F = next h-day return; demeaning makes Cov(F, P) = -h L s^2 / n).
Run from a copy of the repo at BASE:  cd /tmp/review-acis && python <this> [paths]
"""
import math, random, sys
from datetime import datetime, timezone
import numpy as np
sys.path.insert(0, ".")
from tests.backtest.synthetic_market import MarketSpec, _returns

R = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
START = datetime(2014, 1, 6, tzinfo=timezone.utc)          # a Monday
H, FIRST = 2, 260                                          # the 48 h cap; TSMOM live after 252+
res = {k: [] for k in ("vote_dm", "vote_raw", "L126_dm", "L126_raw")}
n = None
for p in range(R):
    spec = MarketSpec("null", START, 985, (("EUR_USD", 1.1),), tick_seconds=86400,
                      daily_vol=0.005, seed=p + 1)
    dm = np.asarray(_returns(spec, 0))                    # production path, demeaned
    rng = random.Random(spec.seed * 1000 + 0)             # same draws, not demeaned
    n = len(dm)
    sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
    raw = np.array([rng.gauss(0.0, sigma) for _ in range(n)])
    assert np.allclose(dm, raw - raw.mean())
    for tag, x in (("dm", dm), ("raw", raw)):
        lp = np.concatenate([[0.0], np.cumsum(x)])
        v_tot = l_tot = 0.0
        for t in range(FIRST, n - H, H):
            fwd = lp[t + H] - lp[t]
            v = sum(np.sign(lp[t] - lp[t - L]) for L in (63, 126, 252))
            if v != 0:
                v_tot += np.sign(v) * fwd
            l_tot += np.sign(lp[t] - lp[t - 126]) * fwd
        res["vote_" + tag].append(v_tot)
        res["L126_" + tag].append(l_tot)
s, L = 0.005, 126
steps = len(range(FIRST, n - H, H))
closed = -steps * (H / (n - L)) * s * math.sqrt(L * (1 - L / n)) * math.sqrt(2 / math.pi)
print(f"paths={R} weekdays={n} holding steps={steps}")
for k, v in res.items():
    v = np.array(v); se = v.std(ddof=1) / math.sqrt(len(v))
    print(f"{k:9s} mean {v.mean():+.5f}  se {se:.5f}  t {v.mean()/se:+6.1f}  frac<0 {np.mean(v < 0):.3f}")
print(f"closed form, single 126-day lookback, demeaned: {closed:+.5f}")
