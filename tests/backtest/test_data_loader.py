"""Phase-11 tests for the provenance loader (ACIS-09 §5/§13 C-BT-9)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from core.data.normaliser import RawTick
from tests.backtest.data_loader import (BacktestDataLoader, ProvenanceError,
                                        TickSource, batched, calibrate_cost_model)
from tests.optimizer_fixtures import CapturingLogger

# a Monday 08:00 UTC (mid-London session, not a weekend)
T0 = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)


def mk_tick(ts, bid=1.10000, ask=1.10002, provider="dukascopy") -> RawTick:
    return RawTick(event_time=ts, recv_time=ts, instrument="EUR_USD", bid=bid,
                   ask=ask, volume=1.0, book=None, provider=provider, raw_payload={})


class ListSource(TickSource):
    def __init__(self, name, ticks):
        self.name = name
        self._ticks = ticks

    def load(self, instrument, start, end):
        return [t for t in self._ticks if start <= t.event_time < end]


def _loader(**sources):
    return BacktestDataLoader({k: ListSource(k, v) for k, v in sources.items()},
                              CapturingLogger())


def test_undeclared_source_is_refused() -> None:
    ldr = _loader(dukascopy=[mk_tick(T0)])
    with pytest.raises(ProvenanceError):
        ldr.load(source="whatever_was_lying_around", instrument="EUR_USD",
                 start=T0, end=T0 + timedelta(hours=1))


def test_bad_ticks_rejected_and_logged() -> None:
    ticks = [
        mk_tick(T0),                                             # good
        mk_tick(T0 + timedelta(seconds=1), bid=float("nan")),   # NaN
        mk_tick(T0 + timedelta(seconds=2), bid=1.5, ask=1.4),   # crossed
        mk_tick(T0 + timedelta(seconds=3), bid=-1.0, ask=1.0),  # non-positive
        mk_tick(T0 + timedelta(seconds=4), bid=1.10, ask=1.20), # implausible spread
    ]
    ldr = _loader(dukascopy=ticks)
    res = ldr.load(source="dukascopy", instrument="EUR_USD", start=T0,
                   end=T0 + timedelta(hours=1), max_plausible_spread=0.0005)
    assert len(res.ticks) == 1 and res.rejected == 4


def test_weekend_ticks_dropped() -> None:
    sat = datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc)      # Saturday
    fri_late = datetime(2026, 1, 2, 22, 30, tzinfo=timezone.utc)  # Fri after 22:00
    sun_early = datetime(2026, 1, 4, 10, 0, tzinfo=timezone.utc)  # Sun before 22:00
    ldr = _loader(dukascopy=[mk_tick(T0), mk_tick(sat), mk_tick(fri_late), mk_tick(sun_early)])
    res = ldr.load(source="dukascopy", instrument="EUR_USD",
                   start=fri_late, end=T0 + timedelta(hours=1))
    assert len(res.ticks) == 1 and res.weekend_dropped == 3


def test_cross_source_drift_flags_but_never_averages() -> None:
    prim = [mk_tick(T0 + timedelta(seconds=i)) for i in range(5)]
    # secondary within ~0.9 bps → not flagged
    close = [mk_tick(T0 + timedelta(seconds=i), bid=1.10001, ask=1.10003,
                     provider="truefx") for i in range(5)]
    ldr = _loader(dukascopy=prim, truefx=close)
    r = ldr.cross_source_drift(instrument="EUR_USD", primary=prim, secondary=close,
                               threshold_bps=5.0)
    assert r.n_compared == 5 and not r.flagged
    # secondary ~18 bps off → flagged
    far = [mk_tick(T0 + timedelta(seconds=i), bid=1.10200, ask=1.10202,
                   provider="truefx") for i in range(5)]
    r2 = ldr.cross_source_drift(instrument="EUR_USD", primary=prim, secondary=far,
                                threshold_bps=5.0)
    assert r2.flagged and r2.max_bps > 5.0
    # the loader returns a REPORT — it never mutates/averages the primary ticks
    assert all(t.bid == 1.10000 for t in prim)


def test_calibrate_cost_model_from_spreads() -> None:
    cm = calibrate_cost_model(observed_spreads=[0.0002, 0.0004, 0.0006],
                              slippage_fraction_of_spread=0.25)
    assert cm.slippage_per_side == pytest.approx(0.0004 * 0.25)   # median 0.0004
    assert cm.commission_per_side == 0.0


def test_batched_yields_full_and_partial_batches() -> None:
    ticks = [mk_tick(T0 + timedelta(seconds=i)) for i in range(7)]
    batches = list(batched(iter(ticks), 3))
    assert [len(b) for b in batches] == [3, 3, 1]
    with pytest.raises(ValueError):
        list(batched(iter(ticks), 0))


def test_cross_source_drift_flags_when_nothing_aligns() -> None:
    # GAP-P12D-13: an hour-shifted secondary aligns with nothing — a FAILURE, never a clear
    # (it used to return n_compared=0, flagged=False)
    prim = [mk_tick(T0 + timedelta(seconds=i)) for i in range(5)]
    shifted = [mk_tick(T0 + timedelta(hours=1, seconds=i), provider="histdata") for i in range(5)]
    ldr = _loader(dukascopy=prim, histdata=shifted)
    r = ldr.cross_source_drift(instrument="EUR_USD", primary=prim, secondary=shifted,
                               threshold_bps=5.0)
    assert r.n_compared == 0 and r.coverage == 0.0 and r.flagged and "aligned" in r.reason
    assert ldr.cross_source_drift(instrument="EUR_USD", primary=[], secondary=shifted,
                                  threshold_bps=5.0).flagged
