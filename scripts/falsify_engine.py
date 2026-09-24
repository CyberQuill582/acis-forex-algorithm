"""Engine-level falsification of the §14 pipeline on synthetic markets with a known answer (GAP-P12D-28).

    python scripts/falsify_engine.py --quick         # 10 weeks, 3 short folds: a shape check, never a verdict
    python scripts/falsify_engine.py --workers 4     # THE run: over two graded years per market

Stage 1 (GAP-P12D-37): the ORACLE positive control (tests/backtest/oracle.py) is graded on
every market with the same folds, account and declared costs. The engine's verdict is VOID,
and the engine is not run (exit 4), unless the harness recognises the oracle on planted (every
non-DSR clause of `passed` met) and refuses it on null and permuted. A quick run only prints
this stage: its graded span is too short for any verdict.

Stage 2: each market (tests/backtest/synthetic_market.py) is labelled, then graded by the real
walk-forward (`run_walk_forward`: production config, account, costs and gates). The expected
answers: null and permuted must NOT pass; planted MUST pass. Writes
data/validation/falsification/<run id>/<kind>.json (and oracle_<kind>.json,
oracle_deflation.json: the Deflated Sharpe the ratified gate gives the oracle under each engine
run's own selection set). Exit 0 only when all three hold. A quick run exits 3: its graded
span is under the two years §14 demands, so nothing can pass by design.
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
from tests.backtest.deflated_sharpe import deflated_sharpe  # noqa: E402
from tests.backtest.oos_runner import train_years  # noqa: E402
from tests.backtest.oracle import void_reasons  # noqa: E402
from tests.backtest.report import DSR_MIN  # noqa: E402
from tests.backtest.synthetic_grade import FIRST_MID, START, grade, label_year, oracle_row, plan  # noqa: E402
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

    results, oracle = {}, {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        # stage 1 (GAP-P12D-37): no engine verdict means anything until the grader recognises
        # a strategy KNOWN to be good, and refuses the same logic where it knows nothing
        for fut in as_completed([ex.submit(oracle_row, specs[k], out, a.account, folds, ROOT)
                                 for k in a.kinds]):
            r = fut.result()
            oracle[r["kind"]] = r
            print(f"  oracle {r['kind']:8s} trades={r['trades']} net={float(r['net_pnl']):,.2f} "
                  f"sharpe={r['sharpe']:.2f} psr={r['psr']:.3f} non-DSR failures={r['non_dsr_failures']} "
                  f"({r['seconds']:,.0f} s)", flush=True)
        void = void_reasons({k: r["non_dsr_failures"] for k, r in oracle.items()})
        if void and not a.quick:
            print("VERDICT VOID — the oracle positive control failed:", "; ".join(void))
            return 4
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

    # what the ratified gate says about the oracle had it been the strategy each run selected
    deflation = {k: deflated_sharpe(oracle[k]["trade_returns"], r["trial_sharpes"], r["trials"])
                 for k, r in results.items()}
    for k, dsr in sorted(deflation.items()):
        print(f"  oracle deflated by the {k} run's {results[k]['trials']} trials: DSR={dsr:.4f} "
              f"(the gate needs {DSR_MIN})")
    (out / "oracle_deflation.json").write_text(json.dumps(deflation, indent=1), encoding="utf-8")

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
