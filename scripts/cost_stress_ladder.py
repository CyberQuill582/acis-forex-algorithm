"""The cost-stress ladder (GAP-P12D-46): how much of a graded edge is friction?

    python scripts/cost_stress_ladder.py --quick                   # shape check, no verdict
    python scripts/cost_stress_ladder.py --workers 4               # THE run

Grades ONE market several times, changing nothing but the run's C8 cost map. Rungs are
multiples of the declared per-side cost (half-spread + commission + slippage), optionally over
a spread floor: a flat stress ladder, NEVER a venue calibration (GAP-P12D-46's overlay is
additive and per-session; a flat multiplier must not be mistaken for it).

Reading it:
  * `pass = meets §14 out-of-sample at 2x`: a real edge over a 30 min – 48 h hold survives 2x.
  * A small 1x net PnL that collapses by 2x means the edge is priced by turnover, not venue.
  * A synthetic market quotes a CONSTANT spread, so the spread-floor rung is inert there.

Labels do not depend on cost, so one labelling pass serves every rung. Writes
data/validation/cost_stress/<run id>/{ladder.json,rung_*.json}.
"""

from __future__ import annotations

import argparse
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.schemas import load_config  # noqa: E402
from tests.backtest.oos_runner import strict_json, train_years  # noqa: E402
from tests.backtest.synthetic_grade import FIRST_MID, START, grade, label_year, plan  # noqa: E402
from tests.backtest.synthetic_market import KINDS, MarketSpec  # noqa: E402


def rung_tag(stress: float, floor: float) -> str:
    return f"rung_{stress:g}x" + (f"_floor{floor:g}" if floor else "")


def decompose(rows: list[dict]) -> dict:
    """Split the 1x result into direction, friction and carry EXACTLY — the number the ladder
    exists for. Every graded trade carries the C8 friction and the financing it was charged
    (audit R11I-01), so net = direction - friction + carry at 1x, per strategy too, with no
    estimate. The old least-squares slope over the rungs assumed a FIXED trade set; the rungs of
    2026-09-29 traded 1,690 / 1,568 / 665 / 548 times, so it measured selection, not friction.
    A row without per-trade friction (a pre-R11I-01 ladder) gets no split at all."""
    one = next((r for r in rows if r["cost_stress"] == 1.0 and not r["spread_floor"]), None)
    if one is None or "friction" not in one:
        return {}
    net, friction, carry = float(one["net_pnl"]), float(one["friction"]), float(one["carry"])

    def split(net: float, friction: float, carry: float) -> dict:
        return {"net": net, "friction": friction, "carry": carry, "direction": net + friction - carry}
    return {**{f"{k}_1x": v for k, v in split(net, friction, carry).items()},
            "friction_share_of_loss_1x": friction / -net if net < 0 else None,
            "per_strategy_1x": {k: split(float(v["net_pnl"]), float(v["friction"]), float(v["carry"]))
                                for k, v in one.get("per_strategy", {}).items()}}


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
    n1, n2 = float(one["net_pnl"]), float(two["net_pnl"])
    if n1 > 0:
        tail = f"net PnL {n1:,.2f} at 1x, {n2 / n1:.0%} of it left at {bar:g}x"
    else:
        # a ratio of two losses is not a "fraction kept" — 115% of a loss means it GREW by 15%
        tail = (f"net PnL {n1:,.2f} at 1x is ALREADY A LOSS before stressing; "
                f"{bar:g}x deepens it by a further {n1 - n2:,.2f}")
    d = decompose(rows)
    if d:
        tail += (f"; exactly, at 1x: direction {d['direction_1x']:+,.2f}, friction {d['friction_1x']:,.2f}, "
                 f"carry {d['carry_1x']:+,.2f}")
    return f"NO EDGE TO STRESS: §14 fails at 1x already ({tail})"


def ladder_document(*, kind: str, account: str, folds: int, days: int, bar: float, quick: bool,
                    rows: list[dict]) -> str:
    """ladder.json, as strict RFC 8259 JSON (audits F6/E7): a rung whose §14 duration band is
    empty has avg_duration_s NaN, and a run with no Sharpe has dsr NaN — both are written null."""
    return strict_json({"kind": kind, "account": account, "folds": folds, "days": days, "bar": bar,
                        "quick": quick, "verdict": verdict(rows, bar),
                        "cost_decomposition": decompose(rows), "rungs": rows})


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
    (out / "ladder.json").write_text(ladder_document(
        kind=a.kind, account=a.account, folds=len(folds), days=days, bar=a.bar, quick=a.quick,
        rows=rows), encoding="utf-8")
    print("\n" + ("quick run: a shape check only — under two graded years nothing can pass, "
                  "so no verdict" if a.quick else line))
    print("ladder:", out / "ladder.json")
    return 3 if a.quick else 0


if __name__ == "__main__":
    sys.exit(main())
