"""Label and grade a synthetic market with the real pipeline (GAP-P12D-28, GAP-P12D-46).

Shared by the two entry points that grade synthetic markets:
  * `scripts/falsify_engine.py`   — does the pipeline give the RIGHT answer (null/permuted
    must fail, planted must pass)? Its first stage, `oracle_row`, grades the oracle positive
    control on the same folds (GAP-P12D-37).
  * `scripts/cost_stress_ladder.py` — how much of a graded edge is friction?
One path, so a ladder rung and a falsification run differ in exactly ONE input — the run's
cost map — and in nothing else.

Invariants:
  * The label cache key (`LabelSpec`) covers the config and the labeller version, NOT the
    `MarketSpec`. Two different synthetic price paths sharing a source name would therefore
    share labels silently. Every run gets its OWN root, and `market_cache` takes that root;
    never point two MarketSpecs at one labels directory.
  * `plan` folds never overlap and never rewind the clock: successive test windows are
    separated by the embargo, which is also each fold's warm-up window (GAP-P12D-35).
  * Labels do not depend on cost, so one labelling pass serves every rung of a ladder.
"""

from __future__ import annotations

import time
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.account_doctrine import guardrail_hash
from config.schemas import AcisConfig, load_config
from core.data.jsonl_logging import JsonlEventLogger
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.deflated_sharpe import sharpe_threshold
from tests.backtest.oos_plan import EMBARGO
from tests.backtest.oos_runner import RunInputs, report_json, run_walk_forward
from tests.backtest.oracle import grade_oracle, non_dsr_failures
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec, label_instrument_year
from tests.backtest.replay_logging import ReplayEventLogger
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, synthetic_spx
from tests.backtest.walk_forward import Fold

START = datetime(2014, 1, 6, tzinfo=timezone.utc)              # a Monday
FIRST_MID = {"EUR_USD": 1.10, "GBP_USD": 1.30, "USD_JPY": 110.0, "AUD_USD": 0.75,
             "USD_CHF": 0.95, "USD_CAD": 1.30, "NZD_USD": 0.70, "XAU_USD": 1800.0}


def plan(train_days: int, test_days: int, n_folds: int, start: datetime = START) -> list[Fold]:
    """Non-overlapping folds (GAP-P12D-35). Each fold's warm-up window is [train_end,
    test_start) — the embargo — so successive test windows must be separated by the embargo
    too, or the warm-up replays days the previous fold already graded and the engine's clock
    jumps backwards. The ratified `oos_plan.plan_folds` has this shape; the pre-2026-09-17
    falsification plan did not, which silently suspended `max_hold` and pushed out-of-order
    timestamps into the equity curve of every run before then."""
    first_test = start + timedelta(days=train_days) + EMBARGO
    step = timedelta(days=test_days) + EMBARGO
    folds = []
    for k in range(n_folds):
        test_start = first_test + k * step
        train_end = test_start - EMBARGO
        folds.append(Fold(k, train_end - timedelta(days=train_days), train_end, test_start,
                          test_start + timedelta(days=test_days)))
    return folds


def market_cache(cfg: AcisConfig, out: Path, source: str, start: datetime = START) -> LabelledBarCache:
    """One directory per market: the cache path is <instrument>/<year>, so markets sharing a
    root would overwrite each other's labels (the first quick falsification run collided)."""
    return LabelledBarCache(out / "labels" / source, LabelSpec.for_config(cfg, source, start))


def run_logger(out: Path, name: str, layer: str, keep: int) -> ReplayEventLogger:
    return ReplayEventLogger(JsonlEventLogger(out / "logs" / f"{name}.jsonl", layer=layer,
                                              session_id=f"synthetic-{name}"), keep_per_type=keep)


def label_year(spec: MarketSpec, instrument: str, year: int, out: Path,
               root: Path) -> tuple[str, str, int, int, float]:
    """Label one instrument-year of a synthetic market. Runs in a worker process, so it
    reloads the config rather than inheriting it."""
    t0, cfg, market = time.perf_counter(), load_config(root / "config"), SyntheticMarket(spec)
    log = run_logger(out, f"labels_{spec.kind}_{instrument}_{year}", "labels", 20)
    n = label_instrument_year(cfg=cfg, loader=BacktestDataLoader({market.name: market}, log),
                              source=market.name, instrument=instrument, year=year,
                              cache=market_cache(cfg, out, market.name), logger=log, data_start=START)
    log.close()
    return spec.kind, instrument, year, n, time.perf_counter() - t0


def oracle_row(spec: MarketSpec, out: Path, account: str, folds: list[Fold], root: Path, *,
               sign_error: float = 0.0, tag: str | None = None) -> dict:
    """Stage 1 of a falsification verdict (GAP-P12D-37): the oracle positive control on this
    market, with the SAME folds, account and declared costs the engine is graded on; a
    `sign_error` rung under its own `tag` (audit E1). Runs in a worker process, so it reloads
    the config."""
    t0, cfg, tag = time.perf_counter(), load_config(root / "config"), tag or spec.kind
    log = run_logger(out, f"oracle_{tag}", "backtest", 200)
    g = grade_oracle(spec, cfg, account, folds, log, sign_error=sign_error)
    log.close()
    (out / f"oracle_{tag}.json").write_text(report_json(g.report), encoding="utf-8")
    oos = g.report.out_of_sample
    return {"kind": tag, "sign_error": sign_error, "trades": oos.n_trades, "net_pnl": str(g.net_pnl),
            "sharpe": oos.annual_sharpe, "psr": g.report.deflated_sharpe,
            "non_dsr_failures": list(non_dsr_failures(g.report, guardrail_hash(cfg.guardrails))),
            "seconds": time.perf_counter() - t0}


def grade(spec: MarketSpec, out: Path, account: str, folds: list[Fold], root: Path, *,
          tag: str | None = None, cost_stress: float = 1.0, spread_floor: float = 0.0) -> dict:
    """Grade one synthetic market with the production config, account, gates and cost map.

    `tag` names this grading run's artifacts (report json, log, engine work dir): a ladder
    grades ONE market several times, so the tag, not the market kind, must be unique."""
    t0, cfg, market = time.perf_counter(), load_config(root / "config"), SyntheticMarket(spec)
    tag = tag or spec.kind
    log = run_logger(out, f"run_{tag}", "backtest", 200)
    report = run_walk_forward(RunInputs(
        cfg=cfg, account=account, source=market.name,
        loader=BacktestDataLoader({market.name: market}, log), cache=market_cache(cfg, out, market.name),
        folds=folds, spx_closes=synthetic_spx(START, spec.days), financing=None,
        work_dir=out / "engine" / tag, logger=log, cost_stress=cost_stress, spread_floor=spread_floor))
    log.close()
    (out / f"{tag}.json").write_text(report_json(report), encoding="utf-8")
    oos = report.out_of_sample
    return {"kind": spec.kind, "tag": tag, "cost_stress": cost_stress, "spread_floor": spread_floor,
            "passed": report.passed, "trades": oos.n_trades, "sharpe": oos.annual_sharpe,
            "profit_factor": oos.profit_factor, "win_rate": oos.win_rate,
            "avg_duration_s": oos.avg_trade_duration_s, "max_drawdown_pct": oos.max_drawdown_pct,
            # every trade carries a strategy, so the per-strategy slices partition the book:
            # their net PnLs sum to the run's net PnL exactly (Decimal, no re-derivation)
            "net_pnl": str(sum((v.net_pnl for v in report.per_strategy.values()), Decimal("0"))),
            "dsr": report.deflated_sharpe, "trials": report.trial_count,
            # the per-trade SR0 the ratified gate demands of this run's selection (audit E4: a
            # HURDLE; the DSR's own trial filter and N, deflated_sharpe.sharpe_threshold)
            "sr0_hurdle": sharpe_threshold([s for r in report.in_sample_evolution
                                            for s in r.get("trial_sharpes", ()) if s is not None],
                                           report.trial_count),
            "champions": [r["champions"] for r in report.in_sample_evolution],
            "per_strategy": {k: {"n_trades": v.n_trades, "net_pnl": str(v.net_pnl),
                                 "win_rate": v.win_rate, "profit_factor": v.profit_factor}
                             for k, v in report.per_strategy.items()},
            "failed": sorted(k for k, ok in report.targets_met.items() if not ok),
            # every clause of `passed` but the trial count and the DSR (audit E2): empty while
            # passed is False means the run failed ONLY the ratified DSR gate
            "non_dsr_failed": list(non_dsr_failures(report, guardrail_hash(cfg.guardrails))),
            "seconds": time.perf_counter() - t0}
