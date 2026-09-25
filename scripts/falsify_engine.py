"""Engine-level falsification of the §14 pipeline on synthetic markets with a known answer (GAP-P12D-28).

    python scripts/falsify_engine.py --quick         # 10 weeks, 3 short folds: a shape check, never a verdict
    python scripts/falsify_engine.py --workers 4     # THE run: over two graded years per market

Stage 1, the ORACLE positive control (GAP-P12D-37; tests/backtest/oracle.py): the perfect oracle
and two graded rungs (`oracle.RUNGS`, just above and just below the §14 cut-offs) are graded on
every market with the same folds, account and costs. The verdict is VOID unless the harness
passes the oracle and the near-pass rung and refuses the near-fail rung, null and permuted.
Stage 2: each market is labelled and graded by the real walk-forward (`run_walk_forward`); null
and permuted must NOT pass, planted MUST. Writes data/validation/falsification/<run id>/. Each
engine run reports the per-trade SR0 HURDLE the ratified gate demands (a hurdle, never "the
oracle's Deflated Sharpe": the oracle is not in the trial set; audit E4).

Exit codes: 0 held; 1 FALSIFICATION FAILED; 2 an enabled instrument lacks a synthetic first mid;
3 quick run, never a verdict; 4 VERDICT VOID (stage 1 failed, the engine never ran); 5 NO VERDICT
(no planted, or no control; audits E3/F4); 6 GATE-LIMITED (planted met every non-DSR clause and
failed ONLY the trial-count / DSR gate, reported as the gate's, not the engine's; audit E2).
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
from tests.backtest.oracle import RUNGS, void_reasons  # noqa: E402
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
    if not a.quick and ("planted" not in a.kinds or set(a.kinds) == {"planted"}):
        # audits E3/F4: without planted there is no positive control and no expected pass, so a
        # dead grader would "hold" on the controls alone; without a control, a grader that passes
        # everything would "hold" on planted alone
        print(f"NO VERDICT: --kinds {' '.join(a.kinds)} — a falsification verdict needs planted (the "
              "positive control and the one expected pass) AND at least one of null / permuted")
        return 5
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
        jobs = [ex.submit(oracle_row, specs[k], out, a.account, folds, ROOT) for k in a.kinds]
        if "planted" in specs:          # audit E1: rungs just above and just below the §14 cut-offs
            jobs += [ex.submit(oracle_row, specs["planted"], out, a.account, folds, ROOT,
                               sign_error=p, tag=tag) for tag, p in RUNGS.items()]
        for fut in as_completed(jobs):
            r = fut.result()
            oracle[r["kind"]] = r
            print(f"  oracle {r['kind']:17s} trades={r['trades']} net={float(r['net_pnl']):,.2f} "
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

    for k, r in sorted(results.items()):
        print(f"  {k}: the ratified gate's per-trade SR0 hurdle over this run's {r['trials']} trials "
              f"= {r['sr0_hurdle']:.3f} (a hurdle the selected strategy's per-trade Sharpe must clear; "
              "not a Deflated Sharpe of anything)")

    if a.quick:
        print("quick run: a shape check only — under two graded years nothing can pass, so no verdict")
        return 3
    wrong = sorted(k for k, r in results.items() if r["passed"] != EXPECT_PASS[k])
    planted = results["planted"]
    if wrong == ["planted"] and not planted["non_dsr_failed"]:
        # audit E2: every other clause of `passed` held, so the only refusal is the ratified
        # trial-count / Deflated Sharpe gate (GAP-P12D-33/37) — that says nothing about the engine
        print(f"GATE-LIMITED — planted met every non-DSR clause of passed and failed only the "
              f"trial-count / Deflated Sharpe gate (dsr={planted['dsr']}, trials={planted['trials']}; "
              "GAP-P12D-33/37): uninterpretable, NOT an engine verdict")
        return 6
    if wrong:
        print("FALSIFICATION FAILED — wrong answer on:", ", ".join(wrong),
              f"(planted's non-DSR failures: {planted['non_dsr_failed']})" if "planted" in wrong else "")
        return 1
    controls = [k for k in sorted(results) if k != "planted"]
    print(f"falsification held on the markets graded in this run: planted passed; "
          f"{', '.join(controls)} did not")
    return 0


if __name__ == "__main__":
    sys.exit(main())
