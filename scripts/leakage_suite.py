"""The structural leakage suite, end to end (GAP-P12D-65): T1 and T2 over the REAL decision path.

    python scripts/leakage_suite.py --controls-only     # stage 1 alone: seconds
    python scripts/leakage_suite.py --workers 2         # THE run: stage 1, then the engine sweep

Stage 1 (T7): the oracle positive control goes through the real harness, honest and with a
next-tick peek, once per cut. VOID (exit 4), and the engine never runs, unless T1 AND T2 both
catch the peek and neither flags the honest oracle.
Stage 2: a planted market is labelled, evolved and replayed through the production path once
as the reference, then once per decision day per test (every later price perturbed: T2; the
tape cut off: T1). Every label, evolution record, regime, signal, order and trade decided
before the cut must be byte-identical. Exit 0 clean, 1 leak, 5 VACUOUS (the reference staged
or ordered nothing). Writes data/validation/leakage/<run id>/report.json. Synthetic data only.
The day grid catches a sub-day peek only where it crosses a cut; the per-decision-point guard
is the component sweep in the default suite (tests/backtest/test_leakage_components.py). This
is the end-to-end backstop for long-reach channels, wired like the other slow gates (A16).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.backtest.leakage import future_perturbation, truncation  # noqa: E402
from tests.backtest.leakage_engine import (NullLogger, leak_config, vacuity,  # noqa: E402
                                           variant_decisions)
from tests.backtest.leakage_markets import decision_cuts, oracle_decisions  # noqa: E402
from tests.backtest.synthetic_grade import FIRST_MID, START, plan  # noqa: E402
from tests.backtest.synthetic_market import MarketSpec  # noqa: E402

EMBARGO = timedelta(days=2)            # >= the 48 h max hold the harness checks on the data


def fresh_process_pool(workers: int) -> ProcessPoolExecutor:
    """Every engine variant in a freshly SPAWNED process that runs nothing else (MEDIUM-1): no
    in-memory memo filled by the reference run, or by another variant, can reach it."""
    return ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"), max_tasks_per_child=1)


def controls(cfg, account: str) -> dict:
    """Stage 1: the honest oracle must raise nothing; the next-tick peek must fail T1 AND T2."""
    folds = plan(1, 2, 2, embargo=EMBARGO)
    spec = MarketSpec("planted", START, (folds[-1].test_end - START).days, (("EUR_USD", FIRST_MID["EUR_USD"]),),
                      tick_seconds=300)
    cuts, out = decision_cuts(spec), {}
    for name, every in (("honest", 0), ("peek", 1)):
        def run(t=None, mode="perturb", every=every):
            return oracle_decisions(spec, cfg, account, folds, NullLogger(), instruments=["EUR_USD"],
                                    cut=t, mode=mode, leak_every=every)
        ref = run()
        out[name] = {"t2": future_perturbation(ref, run, cuts), "t1": truncation(ref, lambda t: run(t, "truncate"), cuts)}
    void = [f"the honest oracle failed {s.test}" for s in out["honest"].values() if not s.clean]
    void += [f"the next-tick peek passed {s.test}" for s in out["peek"].values() if s.clean]
    return {"void": void, "sweeps": {f"{n}_{k}": s.summary() for n, r in out.items() for k, s in r.items()}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--account", default=None)
    ap.add_argument("--train-days", type=int, default=12)
    ap.add_argument("--test-days", type=int, default=2)
    ap.add_argument("--folds", type=int, default=3)
    # 12/2/3 at 60 s stages a champion and 20 orders under T6 (probed 2026-09-25). At 300 s every
    # 60 s bar is one tick, every stop is a gap-through, and the reference is VACUOUS.
    ap.add_argument("--tick-seconds", type=int, default=60)
    ap.add_argument("--step-hours", type=int, default=24)
    ap.add_argument("--production-optimizer", action="store_true",
                    help="evolve with the production population (a short tape then usually stages nothing: VACUOUS)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None,
                    help="run directory root (default data/validation/leakage); keep it short on Windows (MAX_PATH)")
    a = ap.parse_args()
    small = not a.production_optimizer
    cfg = leak_config(ROOT, small_optimizer=small)
    account = a.account or cfg.system.active_account
    out = (a.out or ROOT / "data" / "validation" / "leakage") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"stage1": controls(cfg, account)}

    def finish(code: int, verdict: str) -> int:
        report["verdict"] = verdict
        (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        print(verdict, "\nreport:", out / "report.json")
        return code

    for line in report["stage1"]["sweeps"].values():
        print("  control", line, flush=True)
    if report["stage1"]["void"]:
        return finish(4, "VERDICT VOID — the guard does not bite: " + "; ".join(report["stage1"]["void"]))
    if a.controls_only:
        return finish(0, "controls hold: the next-tick peek fails T1 and T2, the honest oracle passes both")

    folds = plan(a.train_days, a.test_days, a.folds, embargo=EMBARGO)
    instruments = sorted(cfg.instruments.enabled)
    spec = MarketSpec("planted", START, (folds[-1].test_end - START).days,
                      tuple((i, FIRST_MID[i]) for i in instruments), tick_seconds=a.tick_seconds)
    cuts = decision_cuts(spec, timedelta(hours=a.step_hours))
    print(f"engine: {len(folds)} folds, {spec.days} days, {len(cuts)} cuts x 2 tests -> {out}", flush=True)
    t0 = time.perf_counter()
    _, _, reference = variant_decisions(spec, account, folds, out / "ref", ROOT, small, None, "perturb")
    kinds = {k: sum(d.kind == k for d in reference) for k in sorted({d.kind for d in reference})}
    report["stage2"] = {"cuts": [c.isoformat() for c in cuts], "reference_decisions": kinds,
                        "optimizer": "small" if small else "production"}
    print(f"  reference: {kinds} ({time.perf_counter() - t0:,.0f} s)", flush=True)
    hollow = vacuity(reference)
    if hollow:
        return finish(5, "VACUOUS — " + "; ".join(hollow) + ": nothing that matters could be compared")

    variants: dict = {}
    with fresh_process_pool(a.workers) as ex:
        futures = [ex.submit(variant_decisions, spec, account, folds, out / f"{mode[0]}{k:03d}", ROOT, small, c, mode)
                   for mode in ("perturb", "truncate") for k, c in enumerate(cuts)]
        for fut in as_completed(futures):
            cut, mode, decisions = fut.result()
            variants[(mode, cut)] = decisions
            print(f"  {mode:8s} {cut.isoformat()} ({time.perf_counter() - t0:,.0f} s)", flush=True)
    sweeps = [future_perturbation(reference, lambda t: variants[("perturb", t)], cuts),
              truncation(reference, lambda t: variants[("truncate", t)], cuts)]
    report["stage2"]["sweeps"] = [s.summary() for s in sweeps]
    report["stage2"]["violations"] = [v.describe(limit=10) for s in sweeps for v in s.violations]
    for s in sweeps:
        print(" ", s.summary())
    if any(s.violations for s in sweeps):
        return finish(1, "LEAK — a decision before a cut changed with the data after it (see violations)")
    return finish(0, "clean: no decision before any cut depends on the data after it")


if __name__ == "__main__":
    sys.exit(main())
