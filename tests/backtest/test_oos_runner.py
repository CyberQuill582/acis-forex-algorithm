"""The runner end to end on small synthetic data (GAP-P12D-23): real engine, real config,
two embargoed folds, labelled bars, evolution, warm-up, grading and the report file. It is a
pipeline smoke test — never a §14 result."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from core.data.normaliser import RawTick
from core.regime.regime_types import RegimeType
from tests.backtest.data_loader import BacktestDataLoader, TickSource
from tests.backtest.look_register import LookRegister
from tests.backtest.oos_runner import RunInputs, missing_labels, report_json, run_walk_forward, train_years
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import CapturingLogger, bars_from_closes, zigzag_closes

UTC = timezone.utc
PRICE = {"EUR_USD": 1.10, "USD_JPY": 150.0}


class _Synthetic(TickSource):
    """A tick every 5 minutes on weekdays, a small random walk per instrument."""
    name = "synthetic"
    provenance = "synthetic"

    def load(self, instrument, start, end):
        rng = random.Random({"EUR_USD": 1, "USD_JPY": 2}[instrument])   # hash() is salted per process
        mid, t = PRICE[instrument], start.replace(second=0, microsecond=0)
        while t < end:
            if t.weekday() < 5:
                mid *= 1 + rng.gauss(0, 0.0002)
                spread = mid * 0.00008
                bid = mid - spread / 2
                yield RawTick(event_time=t, recv_time=t, instrument=instrument, bid=bid, ask=bid + spread,
                              volume=1.0, book=None, provider="synthetic", raw_payload={})
            t += timedelta(minutes=5)


def _folds() -> list[Fold]:
    t0 = datetime(2014, 3, 3, tzinfo=UTC)                      # Monday
    return [Fold(0, datetime(2014, 1, 1, tzinfo=UTC), t0, t0 + timedelta(days=2), t0 + timedelta(days=4)),
            Fold(1, datetime(2014, 1, 1, tzinfo=UTC), t0 + timedelta(days=7), t0 + timedelta(days=9),
                 t0 + timedelta(days=11))]


def test_the_runner_grades_two_folds_end_to_end(tmp_path, acis_config) -> None:
    folds = _folds()
    cache = LabelledBarCache(tmp_path / "labels", LabelSpec.for_config(acis_config, "synthetic",
                                                                       datetime(2014, 1, 1, tzinfo=UTC)))
    instruments = sorted(acis_config.instruments.enabled)
    assert missing_labels(cache, instruments, folds) == [(i, 2014) for i in instruments]
    bars = bars_from_closes(zigzag_closes(600), RegimeType.STRONG_TREND_UP)
    shifted = tuple(b.__class__(ts=b.ts.replace(year=2014, month=2, day=3), open=b.open, high=b.high,
                                low=b.low, close=b.close, spread=b.spread, regime=b.regime) for b in bars)
    for instrument in instruments:
        cache.write(instrument, 2014, shifted)
    assert missing_labels(cache, instruments, folds) == [] and train_years(folds) == [2014]

    log = CapturingLogger()
    look = LookRegister(tmp_path / "looks").register(cfg=acis_config, source=_Synthetic(), instruments=instruments,
                                                     folds=folds, family="test:runner", account="dev_paper",
                                                     git=("test", False))
    report = run_walk_forward(RunInputs(
        cfg=acis_config, account="dev_paper", source="synthetic",
        loader=BacktestDataLoader({"synthetic": _Synthetic()}, log), cache=cache, folds=folds,
        spx_closes={}, financing=None, work_dir=tmp_path / "engine", logger=log, look=look))

    assert report.account == "dev_paper" and report.n_folds == 2
    assert [r["fold"] for r in report.in_sample_evolution] == [0, 1]
    assert report.guardrail_hash and report.passed is False       # a 4-day synthetic run can never pass
    assert any("event calendar" in c for c in report.fidelity_caveats)
    assert len(log.events("BACKTEST_RUN")) == 1
    loaded = json.loads(report_json(report))
    assert loaded["account"] == "dev_paper" and loaded["n_folds"] == 2
    assert {k: loaded["look"][k] for k in ("look_id", "family", "tier", "family_looks", "tier_totals")} == {
        "look_id": "000001", "family": "test:runner", "tier": "synthetic",           # GAP-P12D-64
        "family_looks": {"test:runner": {"synthetic": 1}}, "tier_totals": {"synthetic": 1}}
    outcome = LookRegister(tmp_path / "looks").outcome("000001")
    assert outcome["passed"] is False and outcome["n_trades"] == report.out_of_sample.n_trades
    assert set(outcome) >= {"annual_sharpe", "deflated_sharpe", "trial_count", "targets_met", "trade_returns"}
    assert (tmp_path / "looks" / "000001.graded.json").exists()                   # the line was consumed
