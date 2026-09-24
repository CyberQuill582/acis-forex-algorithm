"""The named alternative on the SAME synthetic path a C3 run graded: a slow, vol-agnostic EWMA
crossover on 17:00-New-York daily closes (8/32-day, Carver-style speed), long/short a fixed notional,
rebalanced once a day, charged the C8 per-side cost (half-spread + slippage) on every flip.
Reports gross/net over the run's graded test windows, per instrument, plus the oracle.
Usage (from the forensic copy): python probe_slow_trend.py /tmp/c3/runs/<run> [notional_usd]"""
import json, math, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path.cwd()))
from tests.backtest.synthetic_grade import FIRST_MID, START
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket

UTC, NY = timezone.utc, ZoneInfo("America/New_York")
run = Path(sys.argv[1]); notional = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
s = json.loads((run / "summary.json").read_text()); a = s["args"]
folds = [[datetime.fromisoformat(x) for x in f] for f in s["folds"]]
days = (folds[-1][3] - START).days
import os
kw = {"seed": int(os.environ.get("C3_SEED", a["seed"]))}
if a["episode_hours"]: kw["episode_hours"] = tuple(a["episode_hours"])
if a["drift_sigma"] is not None: kw["drift_sigma"] = a["drift_sigma"]
spec = MarketSpec(a["kind"], START, days, tuple((i, FIRST_MID[i]) for i in s["instruments"]), **kw)
m = SyntheticMarket(spec); tps = spec.ticks_per_day

def idx(ts):
    d = (ts - START).days; wk, wd = divmod(d, 7)
    if wd >= 5: return (wk * 5 + 5) * tps - 1
    return (wk * 5 + wd) * tps + int((ts - (START + timedelta(days=d))).total_seconds() // 20) - 1

def in_test(t):
    return any(f[2] <= t < f[3] for f in folds)

for inst in s["instruments"]:
    path = m._path(inst); closes = []
    d = START.date()
    while True:
        t = datetime(d.year, d.month, d.day, 17, tzinfo=NY).astimezone(UTC)
        if t >= folds[-1][3]: break
        if d.weekday() < 5 and 0 <= idx(t) < len(path): closes.append((t, math.exp(path[idx(t)])))
        d += timedelta(days=1)
    per_side = FIRST_MID[inst] * spec.spread_frac / 2 + (0.00002 if inst == "EUR_USD" else 0.002)
    ef = es = closes[0][1]; af, as_ = 2 / 9, 2 / 33; pos = 0; g = n = flips = 0.0
    for k in range(1, len(closes)):
        t0, p0 = closes[k - 1]; t1, p1 = closes[k]
        if in_test(t0) and pos:
            units = notional / p0 if inst.startswith("EUR") else notional   # base units
            pnl_q = pos * units * (p1 - p0)
            to_usd = 1.0 if inst.endswith("USD") else 1.0 / p1
            g += pnl_q * to_usd
        ef += af * (p1 - ef); es += as_ * (p1 - es)
        new = 1 if ef > es else -1
        if new != pos and in_test(t1):
            units = notional / p1 if inst.startswith("EUR") else notional
            to_usd = 1.0 if inst.endswith("USD") else 1.0 / p1
            n += (2 if pos else 1) * per_side * units * to_usd; flips += 1
        pos = new
    print(f"{run.name} {inst}: slow EWMA 8/32d on ${notional:.0f} -> gross {g:+.2f} cost {n:.2f} net {g - n:+.2f} flips {flips:.0f}")
