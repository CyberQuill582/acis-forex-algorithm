"""Engine-level falsification of the §14 pipeline on synthetic markets with a known answer (GAP-P12D-28).

    python scripts/falsify_engine.py --quick         # 10 weeks, 3 short folds: a shape check, never a verdict
    python scripts/falsify_engine.py --workers 4     # THE run: over two graded years per market

Each market (tests/backtest/synthetic_market.py) is labelled, then graded by the real
walk-forward (`run_walk_forward`: production config, account, costs and gates). The expected
answers: null and permuted must NOT pass; planted MUST pass. Writes
data/validation/falsification/<run id>/<kind>.json. Exit 0 only when all three hold. A quick
run exits 3: its graded span is under the two years §14 demands, so nothing can pass by design.
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
from tests.backtest.oos_runner import train_years  # noqa: E402
from tests.backtest.synthetic_grade import FIRST_MID, START, grade, label_year, plan  # noqa: E402
from tests.backtest.synthetic_market import KINDS, MarketSpec  # noqa: E402

EXPECT_PASS = {"null": False, "planted": True, "permuted": False}


def main() -> int:
    cfg = load_config(ROOT / "config")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account", default=cfg.system.active_account)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--train-days", type=int, default=60)
    ap.add_argument("--test-days", type=int, default=30)
    ap.add_argument("--graded-days", type=int, default=735)   # over the two years §14 grades
    ap.add_argument("--kinds", nargs="+", choices=KINDS, default=list(KINDS))
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.quick:
        a.train_days, a.test_days, a.graded_days = 28, 12, 36
    folds = plan(a.train_days, a.test_days, math.ceil(a.graded_days / a.test_days))
    instruments = sorted(cfg.instruments.enabled)
    if any(i not in FIRST_MID for i in instruments):
        print("refused: no synthetic first mid for", [i for i in instruments if i not in FIRST_MID])
        return 2
    days = (folds[-1].test_end - START).days
    specs = {k: MarketSpec(k, START, days, tuple((i, FIRST_MID[i]) for i in instruments)) for k in a.kinds}
    out = ROOT / "data" / "validation" / "falsification" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ("-quick" if a.quick else ""))
    (out / "logs").mkdir(parents=True, exist_ok=True)
    print(f"{len(folds)} folds, {days} days, {len(a.kinds)} markets -> {out}", flush=True)

    results = {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        labels = [ex.submit(label_year, specs[k], i, y, out, ROOT)
                  for k in a.kinds for i in instruments for y in train_years(folds)]
        for fut in as_completed(labels):
            kind, instrument, year, n, secs = fut.result()
            print(f"  labelled {kind} {instrument} {year}: {n:,} bars in {secs:,.0f} s", flush=True)
        for fut in as_completed([ex.submit(grade, specs[k], out, a.account, folds, ROOT)
                                 for k in a.kinds]):
            r = fut.result()
            results[r["kind"]] = r
            print(f"  graded {r['kind']:8s} passed={r['passed']} trades={r['trades']} "
                  f"sharpe={r['sharpe']:.2f} dsr={r['dsr']} trials={r['trials']} "
                  f"champions={r['champions']} failed={r['failed']} ({r['seconds']:,.0f} s)", flush=True)

    if a.quick:
        print("quick run: a shape check only — under two graded years nothing can pass, so no verdict")
        return 3
    wrong = sorted(k for k, r in results.items() if r["passed"] != EXPECT_PASS[k])
    if wrong:
        print("FALSIFICATION FAILED — wrong answer on:", ", ".join(wrong))
        return 1
    print("falsification held: null and permuted fail, planted passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
