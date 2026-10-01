"""R1.3: each TREND member's forecast turnover and time in market on the synthetic NULL (P&L-blind,
no real-data look), the fixed inputs of master §5.6's cost filters (tests/backtest/cost_filters.py).

    python scripts/r1_lab_turnover.py --seeds 1-50 --workers 16
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from core.signals import rules  # noqa: E402
from tests.backtest.cost_filters import forecast_turnover, time_in_market  # noqa: E402
from tests.backtest.lab_market import LabSpec, generate  # noqa: E402

BURN = 300
MEMBERS = {"D1": rules.d1,
           **{f"EWMAC{f}_{s}": (lambda f, s: lambda p: rules.ewmac(p, f, s))(f, s) for f, s in rules.EWMAC_SCALARS},
           **{f"BREAKOUT{n}": (lambda n: lambda p: rules.breakout(p, n))(n) for n in rules.BREAKOUT_SCALARS}}


def one(seed: int) -> dict:
    path = generate(LabSpec(seed=seed), null=True)
    price = np.cumprod(1.0 + path.r, axis=0)
    days = [d.astype(object) for d in path.dates]
    out: dict[str, list] = {m: [] for m in [*MEMBERS, "MOP12"]}
    for i in range(price.shape[1]):
        p = price[:, i].tolist()
        for m, f in MEMBERS.items():
            fc = f(p)[BURN:]
            out[m].append((forecast_turnover(fc), time_in_market(fc)))
        fc = rules.mop_12m(p, days)[BURN:]
        out["MOP12"].append((forecast_turnover(fc), time_in_market(fc)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-50")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    lo, hi = map(int, a.seeds.split("-"))
    with Pool(a.workers) as pool:
        parts = pool.map(one, range(lo, hi + 1))
    summary = {}
    for m in parts[0]:
        t = [x[0] for p in parts for x in p[m]]
        tim = [x[1] for p in parts for x in p[m]]
        summary[m] = {"turnover_median": statistics.median(t), "turnover_p10": float(np.percentile(t, 10)),
                      "turnover_p90": float(np.percentile(t, 90)), "time_in_market_median": statistics.median(tim),
                      "n": len(t)}
    print(json.dumps({"seeds": a.seeds, "burn": BURN, "by_member": summary}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
