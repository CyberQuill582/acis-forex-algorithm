"""Look-ahead canary (GAP-P12D-28, owner falsification item 3): deliberately leak future prices
into evolution — the pipeline must catch it."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.optimizer.param_types import RegimeLabelledHistory
from tests.backtest.evolve_step import evolve_fold
from tests.backtest.harness import Backtest, FoldData, refuse_lookahead
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.test_evolve_step import _cfg, _Stager
from tests.backtest.test_harness_regressions import _FakeLoop, _ms
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import T0, CapturingLogger, bars_from_closes, zigzag_closes

UTC = timezone.utc
SPEC = LabelSpec(source="test", bar_seconds=60, cycle_s=120.0, regime_config="{}")
TRAIN_END = T0 + timedelta(minutes=500)


class _LeakyCache(LabelledBarCache):
    """The canary: serves bars up to a week PAST the requested end — future prices."""

    def history(self, instrument, regime, start, end, n):
        honest = super().history(instrument, regime, start, end + timedelta(days=7), n)
        return RegimeLabelledHistory(instrument, honest.bars, honest.bar_seconds)


def _fold() -> Fold:
    return Fold(0, T0, TRAIN_END, TRAIN_END + timedelta(days=3), TRAIN_END + timedelta(days=10))


def _cache(cls, tmp_path) -> LabelledBarCache:
    cache = cls(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars_from_closes(zigzag_closes(600)))   # 100 bars after train end
    return cache


def _run_with(cache, acis_config):
    fold = _fold()
    first = fold.test_start
    bt = Backtest(account="a", cost_models=defaultdict(lambda: None))
    return bt.run(loop=_FakeLoop({}), folds=[FoldData(fold, [_ms(first, 1.10)])],
                  evolve_fn=lambda lp, fd: evolve_fold(SimpleNamespace(params=_Stager()), fd,
                                                       cfg=_cfg(acis_config), cache=cache,
                                                       instruments=["EUR_USD", "USD_JPY"],
                                                       logger=CapturingLogger()),
                  spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")


def test_evolution_fed_future_prices_is_caught(tmp_path, acis_config) -> None:
    with pytest.raises(ValueError, match="look-ahead"):
        _run_with(_cache(_LeakyCache, tmp_path / "leaky"), acis_config)


def test_the_honest_path_is_not_flagged() -> None:
    fold = _fold()
    ok = {"regimes": {"STRONG_TREND_UP": {"candidates": [
        {"instrument": "EUR_USD", "last_bar": (TRAIN_END - timedelta(minutes=1)).isoformat()}]}}}
    refuse_lookahead(ok, fold)                                    # no raise
    leaked = {"regimes": {"STRONG_TREND_UP": {"candidates": [
        {"instrument": "EUR_USD", "last_bar": TRAIN_END.isoformat()}]}}}
    with pytest.raises(ValueError, match="look-ahead"):
        refuse_lookahead(leaked, fold)
