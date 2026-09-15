"""Per-fold evolution (GAP-P12D-18): every instrument evolves each regime, the best holdout
expectancy is staged, nothing at or after the train end is read, and a rerun reproduces it."""

from __future__ import annotations

import random
from datetime import timedelta
from types import SimpleNamespace

from tests.backtest.evolve_step import evolve_fold
from tests.backtest.harness import FoldData
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import (T0, CapturingLogger, bars_from_closes, make_paramset, opt_cfg,
                                     zigzag_closes)

SPEC = LabelSpec(source="test", bar_seconds=60, cycle_s=120.0, regime_config="{}")
TRAIN_END = T0 + timedelta(minutes=500)                  # bars 0..499 open before it


class _Stager:
    def __init__(self) -> None:
        self.staged: list = []

    def stage(self, params, *, now) -> str:
        self.staged.append((params, now))
        return "pending"


def _cfg(acis_config):
    system = acis_config.system.model_copy(update={"optimizer": opt_cfg()})
    return acis_config.model_copy(update={"system": system})


def _run(tmp_path, acis_config, n_bars: int):
    bars = bars_from_closes(zigzag_closes(n_bars))
    cache = LabelledBarCache(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars)
    loop = SimpleNamespace(params=_Stager())
    fold = Fold(0, T0, TRAIN_END, TRAIN_END + timedelta(days=7),      # only the cached year
                TRAIN_END + timedelta(days=365))
    record = evolve_fold(loop, FoldData(fold, ()), cfg=_cfg(acis_config), cache=cache,
                         instruments=["EUR_USD", "USD_JPY"], logger=CapturingLogger())
    return record, loop.params.staged


def test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read(tmp_path, acis_config) -> None:
    record, staged = _run(tmp_path / "600", acis_config, 600)       # 100 bars lie after train_end
    trend = record["regimes"]["STRONG_TREND_UP"]
    eur, jpy = trend["candidates"]
    assert (eur["instrument"], jpy["instrument"]) == ("EUR_USD", "USD_JPY")
    assert eur["bars"] == jpy["bars"] == 500                       # only bars before train_end
    assert eur["champion"] and trend["staged_from"] == "EUR_USD"
    # USD/JPY's 0.002 friction on 1.1-priced bars cannot carry positive expectancy
    assert not jpy["champion"]
    assert record["champions"] == 1 and len(staged) == 1
    # a perfect zigzag makes every holdout trade identical (5 × 0.00186): zero variance means no
    # Sharpe, so this champion is NOT a Deflated Sharpe trial (GAP-P12D-25)
    assert eur["holdout_trade_sharpe"] is None and record["trial_sharpes"] == []
    assert "holdout_trade_sharpe" not in jpy                       # no champion, no trial
    params, now = staged[0]
    assert params.regime.value == "STRONG_TREND_UP" and now == TRAIN_END
    assert set(record["regimes"]) == {"STRONG_TREND_UP", "STRONG_TREND_DOWN", "WEAK_TREND_UP",
                                      "WEAK_TREND_DOWN", "RANGING_TIGHT", "RANGING_WIDE",
                                      "BREAKOUT_IMMINENT", "POST_BREAKOUT", "MEAN_REVERTING"}

    again, staged_again = _run(tmp_path / "500", acis_config, 500)  # the same 500 bars, nothing after
    assert again == record                                          # no leakage, and reproducible
    assert staged_again[0][0].param_set_id == params.param_set_id


class _FixedQIEA:
    """Stands in for QIEA: returns one fixed param set for whatever regime it is asked about."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def evolve(self, regime, history, *, seed, now):
        return make_paramset(regime=regime) if history.bars else None


def test_every_candidate_champion_with_a_sharpe_is_a_trial(tmp_path, acis_config, monkeypatch) -> None:
    monkeypatch.setattr("tests.backtest.evolve_step.QIEA", _FixedQIEA)
    rng = random.Random(3)
    closes = [c + rng.uniform(-0.0003, 0.0003) for c in zigzag_closes(600)]
    bars = bars_from_closes(closes)
    cache = LabelledBarCache(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars)
    loop = SimpleNamespace(params=_Stager())
    fold = Fold(0, T0, TRAIN_END, TRAIN_END + timedelta(days=7), TRAIN_END + timedelta(days=365))
    record = evolve_fold(loop, FoldData(fold, ()), cfg=_cfg(acis_config), cache=cache,
                         instruments=["EUR_USD", "USD_JPY"], logger=CapturingLogger())
    eur, jpy = record["regimes"]["STRONG_TREND_UP"]["candidates"]
    assert eur["holdout_trade_sharpe"] is not None and jpy["holdout_trade_sharpe"] is not None
    assert eur["holdout_trade_sharpe"] != jpy["holdout_trade_sharpe"]   # each pays its own friction
    # both candidates are trials, even though only one of them is staged
    assert record["trial_sharpes"] == [eur["holdout_trade_sharpe"], jpy["holdout_trade_sharpe"]]
    assert len(loop.params.staged) == 1
