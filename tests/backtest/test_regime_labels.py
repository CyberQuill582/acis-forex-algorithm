"""Offline regime labels for QIEA (ACIS-03 §5, GAP-P12D-18): no look-ahead, the real NVMA,
a cache that refuses a different labelling spec, and year jobs that warm up first."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.data.normaliser import RawTick
from core.optimizer.param_types import LabelledBar
from core.regime.regime_types import RegimeType
from tests.backtest.data_loader import BacktestDataLoader, TickSource
from tests.backtest.regime_labels import (LabelledBarCache, LabelSpec, StaleLabelsError,
                                          build_nvma, label_bars, label_instrument_year)
from tests.backtest.test_harness_regressions import _ms
from tests.integration.test_paper_trading_pipeline import flat_ticks
from tests.optimizer_fixtures import CapturingLogger

UTC = timezone.utc
R, T = RegimeType.RANGING_TIGHT, RegimeType.STRONG_TREND_UP


class _SwitchingEngine:
    """Classifies RANGING_TIGHT for the first `switch_at` ticks, STRONG_TREND_UP after."""

    def __init__(self, switch_at: int) -> None:
        self.regime_store: dict = {}
        self._n, self._switch = 0, switch_at

    def observe(self, st) -> None:
        pass

    def classify(self, st):
        ctx = SimpleNamespace(regime=R if self._n < self._switch else T)
        self._n += 1
        self.regime_store[st.instrument] = ctx
        return ctx


def test_a_bar_gets_the_regime_from_before_the_tick_that_closed_it() -> None:
    t0 = datetime(2026, 1, 6, 9, tzinfo=UTC)
    states = [_ms(t0 + timedelta(minutes=i), 1.10 + 0.0001 * i) for i in range(10)]
    out = list(label_bars(states, _SwitchingEngine(5), cycle_s=0, bar_seconds=60))
    # bar i completes when tick i+1 arrives, and must carry classify(tick i), not classify(tick i+1)
    assert [b.regime for _, b in out] == [R, R, R, R, R, T, T, T, T]
    assert [b.ts for _, b in out] == [t0 + timedelta(minutes=i) for i in range(9)]


def test_the_real_nvma_labels_flat_noise_mean_reverting(acis_config, factory) -> None:
    engine = build_nvma(acis_config, factory, CapturingLogger())
    states = [s for s in (factory.build(r).state for r in flat_ticks()) if s is not None]
    out = list(label_bars(states, engine, cycle_s=acis_config.system.regime.cycle_seconds,
                          bar_seconds=acis_config.system.signals.signal_bar_seconds))
    assert len(out) == len(states) - 1
    assert out[-1][1].regime is RegimeType.MEAN_REVERTING


def _bars(start: datetime, regimes: list[RegimeType]) -> list[LabelledBar]:
    return [LabelledBar(ts=start + timedelta(minutes=i), open=1.1, high=1.1002, low=1.0998,
                        close=1.1001, spread=0.0001, regime=r) for i, r in enumerate(regimes)]


def _spec(cycle: float = 120.0) -> LabelSpec:
    return LabelSpec(source="test", bar_seconds=60, cycle_s=cycle, regime_config='{"k": 1}')


def test_cache_round_trips_and_refuses_another_spec(tmp_path) -> None:
    bars = _bars(datetime(2013, 5, 1, tzinfo=UTC), [R, T, R])
    cache = LabelledBarCache(tmp_path, _spec())
    assert cache.write("EUR_USD", 2013, bars) == 3
    assert list(cache.read("EUR_USD", 2013)) == bars and cache.years("EUR_USD") == [2013]
    other = LabelledBarCache(tmp_path, _spec(cycle=300.0))
    assert not other.has("EUR_USD", 2013)
    with pytest.raises(StaleLabelsError):
        list(other.read("EUR_USD", 2013))


def test_history_takes_the_last_n_regime_bars_before_the_train_end(tmp_path) -> None:
    cache = LabelledBarCache(tmp_path, _spec())
    cache.write("EUR_USD", 2013, _bars(datetime(2013, 12, 31, 23, 50, tzinfo=UTC), [T, R, T, R]))
    cache.write("EUR_USD", 2014, _bars(datetime(2014, 1, 6, tzinfo=UTC), [T, T, R, T]))
    end = datetime(2014, 1, 6, 0, 3, tzinfo=UTC)                  # excludes the last 2014 bar
    h = cache.history("EUR_USD", T, end, n=3)
    assert h.bar_seconds == 60 and all(b.regime is T for b in h.bars)
    assert [b.ts for b in h.bars] == [datetime(2013, 12, 31, 23, 52, tzinfo=UTC),
                                      datetime(2014, 1, 6, 0, 0, tzinfo=UTC),
                                      datetime(2014, 1, 6, 0, 1, tzinfo=UTC)]


class _MinuteSource(TickSource):
    """30-second ticks that stop two days into 2014 (a full synthetic year is ~1 M ticks)."""
    name = "test"
    UNTIL = datetime(2014, 1, 2, tzinfo=UTC)

    def load(self, instrument, start, end):
        rng, t, i = random.Random(7), start.replace(second=0, microsecond=0), 0
        while t < min(end, self.UNTIL):
            mid = 1.10 + (0.00005 if i % 2 else -0.00005) + rng.uniform(-0.00002, 0.00002)
            spread = 0.00012 + rng.uniform(-0.00002, 0.00002)
            bid = round(mid - spread / 2, 6)
            yield RawTick(event_time=t, recv_time=t, instrument=instrument, bid=bid,
                          ask=round(bid + spread, 6), volume=1.0, book=None, provider="test",
                          raw_payload={})
            t, i = t + timedelta(seconds=30), i + 1


def test_a_year_job_warms_up_before_the_year_and_keeps_only_its_bars(tmp_path, acis_config) -> None:
    log = CapturingLogger()
    loader = BacktestDataLoader({"test": _MinuteSource()}, log)
    cache = LabelledBarCache(tmp_path, LabelSpec.for_config(acis_config, "test"))
    n = label_instrument_year(cfg=acis_config, loader=loader, source="test", instrument="EUR_USD",
                              year=2014, cache=cache, logger=log,
                              data_start=datetime(2013, 12, 30, 12, tzinfo=UTC))
    bars = list(cache.read("EUR_USD", 2014))
    assert n == len(bars) > 0
    assert bars[0].ts == datetime(2014, 1, 1, tzinfo=UTC) and all(b.ts.year == 2014 for b in bars)
    assert len(log.events("BACKTEST_LOAD")) == 1                     # one stream, read to the end
