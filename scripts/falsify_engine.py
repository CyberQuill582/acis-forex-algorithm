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
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.schemas import load_config  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from tests.backtest.data_loader import BacktestDataLoader  # noqa: E402
from tests.backtest.oos_plan import EMBARGO  # noqa: E402
from tests.backtest.oos_runner import RunInputs, report_json, run_walk_forward, train_years  # noqa: E402
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec, label_instrument_year  # noqa: E402
from tests.backtest.replay_logging import ReplayEventLogger  # noqa: E402
from tests.backtest.synthetic_market import KINDS, MarketSpec, SyntheticMarket, synthetic_spx  # noqa: E402
from tests.backtest.walk_forward import Fold  # noqa: E402

START = datetime(2014, 1, 6, tzinfo=timezone.utc)              # a Monday
FIRST_MID = {"EUR_USD": 1.10, "GBP_USD": 1.30, "USD_JPY": 110.0, "AUD_USD": 0.75,
             "USD_CHF": 0.95, "USD_CAD": 1.30, "NZD_USD": 0.70, "XAU_USD": 1800.0}
EXPECT_PASS = {"null": False, "planted": True, "permuted": False}


def plan(train_days: int, test_days: int, n_folds: int) -> list[Fold]:
    """Non-overlapping folds (GAP-P12D-35). Each fold's warm-up window is [train_end,
    test_start) — the embargo — so successive test windows must be separated by the embargo
    too, or the warm-up replays days the previous fold already graded and the engine's clock
    jumps backwards. The ratified `oos_plan.plan_folds` has this shape; this one did not,
    which silently suspended `max_hold` and pushed out-of-order timestamps into the equity
    curve of every falsification run before 2026-09-17."""
    first_test = START + timedelta(days=train_days) + EMBARGO
    step = timedelta(days=test_days) + EMBARGO
    folds = []
    for k in range(n_folds):
        test_start = first_test + k * step
        train_end = test_start - EMBARGO
        folds.append(Fold(k, train_end - timedelta(days=train_days), train_end, test_start,
                          test_start + timedelta(days=test_days)))
    return folds


def _cache(cfg, out: Path, source: str) -> LabelledBarCache:
    # one directory per market: the cache path is <instrument>/<year>, so markets sharing a root
    # would overwrite each other's labels (the first quick run collided on the same file)
    return LabelledBarCache(out / "labels" / source, LabelSpec.for_config(cfg, source, START))


def _log(out: Path, name: str, layer: str, keep: int) -> ReplayEventLogger:
    return ReplayEventLogger(JsonlEventLogger(out / "logs" / f"{name}.jsonl", layer=layer,
                                              session_id=f"falsify-{name}"), keep_per_type=keep)


def _label(spec: MarketSpec, instrument: str, year: int, out: Path) -> tuple[str, str, int, int, float]:
    t0, cfg, market = time.perf_counter(), load_config(ROOT / "config"), SyntheticMarket(spec)
    log = _log(out, f"labels_{spec.kind}_{instrument}_{year}", "labels", 20)
    n = label_instrument_year(cfg=cfg, loader=BacktestDataLoader({market.name: market}, log),
                              source=market.name, instrument=instrument, year=year,
                              cache=_cache(cfg, out, market.name), logger=log, data_start=START)
    log.close()
    return spec.kind, instrument, year, n, time.perf_counter() - t0


def _grade(spec: MarketSpec, out: Path, account: str, folds: list[Fold]) -> dict:
    t0, cfg, market = time.perf_counter(), load_config(ROOT / "config"), SyntheticMarket(spec)
    log = _log(out, f"run_{spec.kind}", "backtest", 200)
    report = run_walk_forward(RunInputs(
        cfg=cfg, account=account, source=market.name,
        loader=BacktestDataLoader({market.name: market}, log), cache=_cache(cfg, out, market.name),
        folds=folds, spx_closes=synthetic_spx(START, spec.days), financing=None,
        work_dir=out / "engine" / spec.kind, logger=log))
    log.close()
    (out / f"{spec.kind}.json").write_text(report_json(report), encoding="utf-8")
    oos = report.out_of_sample
    return {"kind": spec.kind, "passed": report.passed, "trades": oos.n_trades,
            "sharpe": oos.annual_sharpe, "dsr": report.deflated_sharpe, "trials": report.trial_count,
            "champions": [r["champions"] for r in report.in_sample_evolution],
            "failed": sorted(k for k, ok in report.targets_met.items() if not ok),
            "seconds": time.perf_counter() - t0}


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
        labels = [ex.submit(_label, specs[k], i, y, out)
                  for k in a.kinds for i in instruments for y in train_years(folds)]
        for fut in as_completed(labels):
            kind, instrument, year, n, secs = fut.result()
            print(f"  labelled {kind} {instrument} {year}: {n:,} bars in {secs:,.0f} s", flush=True)
        for fut in as_completed([ex.submit(_grade, specs[k], out, a.account, folds) for k in a.kinds]):
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
