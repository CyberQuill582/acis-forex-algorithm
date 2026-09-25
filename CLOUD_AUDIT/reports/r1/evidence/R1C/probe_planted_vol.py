"""R1-C: the BASE planted tick market is ~3.3x more volatile per day than the null it is compared with.
Calls the PRODUCTION generator read-only. Run from the BASE checkout:
    cd /tmp/review-acis && OMP_NUM_THREADS=1 python <this> [days]
Analytic (episodes shorter than a day, lengths uniform on [lo, hi] steps, drift d = drift_sigma * step sd):
    planted daily var / null daily var ~= 1 + drift_sigma^2 * E[len^2] / E[len]
"""
import math
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from tests.backtest.synthetic_market import MarketSpec, _returns   # noqa: E402

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 70
START = datetime(2014, 1, 6, tzinfo=timezone.utc)
out = {}
for kind in ("null", "planted", "permuted"):
    spec = MarketSpec(kind, START, DAYS, (("EUR_USD", 1.1),))
    r, _ = _returns(spec, 0)
    tpd = spec.ticks_per_day
    days = [math.fsum(r[i * tpd:(i + 1) * tpd]) for i in range(len(r) // tpd)]
    hours = [math.fsum(r[i * 180:(i + 1) * 180]) for i in range(len(r) // 180)]
    out[kind] = statistics.pstdev(days)
    print(f"{kind:9s} weekdays {len(days)}  daily sd {out[kind]:.5f} (spec daily_vol {spec.daily_vol})  "
          f"hourly sd {statistics.pstdev(hours):.6f}  per-tick sd {statistics.pstdev(r):.3e}")
spec = MarketSpec("planted", START, DAYS, (("EUR_USD", 1.1),))
lo, hi = (round(h * 3600 / spec.tick_seconds) for h in spec.episode_hours)
el = (lo + hi) / 2
el2 = sum(k * k for k in range(lo, hi + 1)) / (hi - lo + 1)
print(f"analytic planted/null daily sd ratio ~ {math.sqrt(1 + spec.drift_sigma ** 2 * el2 / el):.2f}; "
      f"measured {out['planted'] / out['null']:.2f}")
# the oracle's frictionless per-step Sharpe is drift_sigma; annualised over 252 x ticks_per_day steps:
print(f"frictionless oracle annual Sharpe ~ drift_sigma * sqrt(252 * ticks_per_day) = "
      f"{spec.drift_sigma * math.sqrt(252 * spec.ticks_per_day):.0f}")
