"""The cost-stress ladder (GAP-P12D-46): how much of a graded edge is friction?

    python scripts/cost_stress_ladder.py --quick                   # shape check, no verdict
    python scripts/cost_stress_ladder.py --workers 4               # THE run

The cheapest decisive test available before any venue is chosen or any money is spent: grade
ONE market several times, changing nothing but the run's C8 cost map. The rungs are multiples
of the declared per-side cost (half-spread + commission + slippage), optionally over a spread
floor — a flat stress ladder, NEVER a venue calibration (the hybrid overlay GAP-P12D-46
describes is additive and per-session; a flat multiplier must not be mistaken for it).

Reading it:
  * `pass = meets §14 out-of-sample at 2x` is the bar the entry sets. A real edge over a
    30 min – 48 h hold should survive 2x comfortably.
  * If net PnL at 1x is small and collapses by 2x, the venue question is moot: the edge is
    priced entirely by turnover, and that is a larger finding than the data-source one.
  * A synthetic market quotes a CONSTANT spread, so the spread-floor rung is inert there;
    it is the rung that will matter on a real tape.

Labels do not depend on cost, so one labelling pass serves every rung. Writes
data/validation/cost_stress/<run id>/{ladder.json,rung_*.json}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.schemas import load_config  # noqa: E402
from tests.backtest.oos_runner import train_years  # noqa: E402
from tests.backtest.synthetic_grade import FIRST_MID, START, grade, label_year, plan  # noqa: E402
from tests.backtest.synthetic_market import KINDS, MarketSpec  # noqa: E402


def rung_tag(stress: float, floor: float) -> str:
    return f"rung_{stress:g}x" + (f"_floor{floor:g}" if floor else "")


def verdict(rows: list[dict], bar: float) -> str:
    """The entry's bar, stated in one line. `passed` is the full §14 gate; net PnL is the
    quantity the ladder is really about, because §14 can fail for reasons friction never
    touches (the duration band, the trial count) while the edge itself is still intact."""
    at = {r["cost_stress"]: r for r in rows if not r["spread_floor"]}
    one, two = at.get(1.0), at.get(bar)
    if one is None or two is None:
        return f"no verdict: the ladder has no 1x and {bar:g}x pair"
    if two["passed"]:
        return f"SURVIVES: §14 still met at {bar:g}x declared cost"
    if one["passed"]:
        return (f"FRAGILE: §14 met at 1x but NOT at {bar:g}x — the edge is priced by turnover, "
                "so venue cost decides it")
    kept = (float(two["net_pnl"]) / float(one["net_pnl"])) if float(one["net_pnl"]) else float("nan")
    return (f"NO EDGE TO STRESS: §14 fails at 1x already (net PnL {float(one['net_pnl']):,.2f}, "
            f"{kept:.0%} of it left at {bar:g}x) — the ladder measures sensitivity only")


def main() -> int:
    cfg = load_config(ROOT / "config")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account", default=cfg.system.active_account)
    ap.add_argument("--kind", choices=KINDS, default="planted",
                    help="the market to stress; only `planted` carries an edge worth pricing")
    ap.add_argument("--rungs", nargs="+", type=float, default=[1.0, 2.0, 3.0, 5.0])
    ap.add_argument("--spread-floor", type=float, default=0.0,
                    help="price units; adds one further rung at 1x over this floor (inert on "
                         "a synthetic market, whose spread is constant)")
    ap.add_argument("--bar", type=float, default=2.0, help="the rung §14 must still be met at")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--train-days", type=int, default=60)
    ap.add_argument("--test-days", type=int, default=30)
    ap.add_argument("--graded-days", type=int, default=735)   # over the two years §14 grades
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.quick:
        a.train_days, a.test_days, a.graded_days = 28, 12, 36
    if any(r < 1.0 for r in a.rungs):
        print("refused: a rung below 1x would price the world CHEAPER than declared")
        return 2

    folds = plan(a.train_days, a.test_days, math.ceil(a.graded_days / a.test_days))
    instruments = sorted(cfg.instruments.enabled)
    if any(i not in FIRST_MID for i in instruments):
        print("refused: no synthetic first mid for", [i for i in instruments if i not in FIRST_MID])
        return 2
    days = (folds[-1].test_end - START).days
    spec = MarketSpec(a.kind, START, days, tuple((i, FIRST_MID[i]) for i in instruments))
    out = ROOT / "data" / "validation" / "cost_stress" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ("-quick" if a.quick else ""))
    (out / "logs").mkdir(parents=True, exist_ok=True)
    rungs = [(r, 0.0) for r in sorted(a.rungs)] + ([(1.0, a.spread_floor)] if a.spread_floor else [])
    print(f"{a.kind}: {len(folds)} folds, {days} days, {len(rungs)} rungs -> {out}", flush=True)

    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        # one labelling pass serves every rung: labels are cost-independent
        for fut in as_completed([ex.submit(label_year, spec, i, y, out, ROOT)
                                 for i in instruments for y in train_years(folds)]):
            kind, instrument, year, n, secs = fut.result()
            print(f"  labelled {kind} {instrument} {year}: {n:,} bars in {secs:,.0f} s", flush=True)
        futures = [ex.submit(grade, spec, out, a.account, folds, ROOT, tag=rung_tag(s, f),
                             cost_stress=s, spread_floor=f) for s, f in rungs]
        for fut in as_completed(futures):
            r = fut.result()
            rows.append(r)
            print(f"  {r['tag']:16s} passed={r['passed']} trades={r['trades']:5d} "
                  f"net={float(r['net_pnl']):10,.2f} sharpe={r['sharpe']:6.2f} "
                  f"pf={r['profit_factor']:.3f} wr={r['win_rate']:.3f} "
                  f"dur={r['avg_duration_s']:,.0f}s failed={r['failed']} "
                  f"({r['seconds']:,.0f} s)", flush=True)

    rows.sort(key=lambda r: (r["spread_floor"], r["cost_stress"]))
    line = verdict(rows, a.bar)
    (out / "ladder.json").write_text(json.dumps(
        {"kind": a.kind, "account": a.account, "folds": len(folds), "days": days,
         "bar": a.bar, "quick": a.quick, "verdict": line, "rungs": rows}, indent=1), encoding="utf-8")
    print("\n" + ("quick run: a shape check only — under two graded years nothing can pass, "
                  "so no verdict" if a.quick else line))
    print("ladder:", out / "ladder.json")
    return 3 if a.quick else 0


if __name__ == "__main__":
    sys.exit(main())
