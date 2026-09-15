"""Per-fold evolution (GAP-P12D-18): every instrument evolves each regime, the best holdout
expectancy is staged, nothing at or after the train end is read, and a rerun reproduces it."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from tests.backtest.evolve_step import evolve_fold
from tests.backtest.harness import FoldData
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import T0, CapturingLogger, bars_from_closes, opt_cfg, zigzag_closes

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
    params, now = staged[0]
    assert params.regime.value == "STRONG_TREND_UP" and now == TRAIN_END
    assert set(record["regimes"]) == {"STRONG_TREND_UP", "STRONG_TREND_DOWN", "WEAK_TREND_UP",
                                      "WEAK_TREND_DOWN", "RANGING_TIGHT", "RANGING_WIDE",
                                      "BREAKOUT_IMMINENT", "POST_BREAKOUT", "MEAN_REVERTING"}

    again, staged_again = _run(tmp_path / "500", acis_config, 500)  # the same 500 bars, nothing after
    assert again == record                                          # no leakage, and reproducible
    assert staged_again[0][0].param_set_id == params.param_set_id
