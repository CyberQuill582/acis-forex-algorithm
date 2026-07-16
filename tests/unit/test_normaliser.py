"""MarketStateFactory validation, dedupe, ordering, staleness, immutability
(ACIS-01 §14 unit contract — postcondition style)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from core.data.errors import DataQualityError
from core.data.normaliser import RawTick

T0 = datetime(2026, 7, 14, 8, 0, 0, tzinfo=timezone.utc)  # Tuesday, tokyo/london overlap


def tick(
    *,
    event=T0,
    recv=None,
    instrument="EUR_USD",
    bid=1.10000,
    ask=1.10012,
    volume=10.0,
    book=None,
) -> RawTick:
    return RawTick(
        event_time=event,
        recv_time=recv if recv is not None else event + timedelta(milliseconds=5),
        instrument=instrument,
        bid=bid,
        ask=ask,
        volume=volume,
        book=book,
        provider="test",
        raw_payload={"src": "test"},
    )


class TestValidation:
    def test_valid_tick_builds_full_state(self, factory) -> None:
        result = factory.build(tick())
        ms = result.state
        assert ms is not None
        assert ms.spread == pytest.approx(0.00012)
        assert ms.mid == pytest.approx(1.10006)
        assert ms.session == "overlap"
        assert ms.is_stale is False
        assert ms.macro_events_imminent is False
        assert ms.tick_velocity > 0

    def test_ask_below_bid_rejected(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(bid=1.2, ask=1.1))

    def test_nan_rejected_never_coerced(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(bid=math.nan))
        with pytest.raises(DataQualityError):
            factory.build(tick(volume=math.inf))

    def test_negative_volume_rejected(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(volume=-1.0))

    def test_naive_timestamp_rejected(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(event=datetime(2026, 7, 14, 8)))

    def test_future_timestamp_beyond_skew_rejected(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(recv=T0 - timedelta(seconds=5)))

    def test_unknown_instrument_rejected(self, factory) -> None:
        with pytest.raises(DataQualityError):
            factory.build(tick(instrument="NO_SUCH"))

    def test_non_monotone_ladder_rejected(self, factory) -> None:
        bad = {"bids": ((1.0999, 5.0), (1.1000, 5.0)), "asks": ((1.1002, 5.0),)}
        with pytest.raises(DataQualityError):
            factory.build(tick(book=bad))

    @pytest.mark.parametrize(
        "book",
        [
            {"bids": ((1.0999,),), "asks": ()},          # wrong arity (GAP-0027 repro)
            {"bids": ((),), "asks": ()},                 # empty level
            {"bids": (("x", 5.0),), "asks": ()},         # non-numeric price
            {"bids": 5, "asks": ()},                     # scalar ladder
            {"bids": ((1.1, 5.0, 9.0),), "asks": ()},    # 3-arity level
        ],
    )
    def test_malformed_book_raises_dataquality_never_valueerror(self, factory, book) -> None:
        # GAP-0027: shape problems must reject as DataQualityError so the
        # ingest loop's catch keeps the stream alive.
        with pytest.raises(DataQualityError):
            factory.build(tick(book=book))


class TestStreamSemantics:
    def test_duplicate_dropped_and_logged(self, factory) -> None:
        first = factory.build(tick())
        second = factory.build(tick())
        assert first.state is not None
        assert second.state is None
        assert ("DUP_TICK", {"instrument": "EUR_USD", "ts": T0.isoformat()}) in second.events

    def test_out_of_order_emitted_flagged_history_not_rewritten(self, factory) -> None:
        factory.build(tick(event=T0))
        late = factory.build(tick(event=T0 - timedelta(seconds=2), bid=1.09990, ask=1.10002))
        assert late.state is not None
        assert late.state.raw["_acis_meta"]["out_of_order"] is True
        assert any(e[0] == "OUT_OF_ORDER" for e in late.events)
        assert factory.context("EUR_USD").last_event_time == T0  # history intact

    def test_staleness_flips_strictly_beyond_threshold(self, factory) -> None:
        at = factory.build(tick(recv=T0 + timedelta(milliseconds=2500)))
        assert at.state is not None and at.state.is_stale is False
        beyond = factory.build(
            tick(event=T0 + timedelta(seconds=1), recv=T0 + timedelta(seconds=1, milliseconds=2501))
        )
        assert beyond.state is not None and beyond.state.is_stale is True

    def test_clock_skew_flagged_never_adjusted(self, factory) -> None:
        result = factory.build(tick(recv=T0 + timedelta(milliseconds=1600)))
        assert result.state is not None
        assert result.state.timestamp == T0  # unaltered
        assert result.state.raw["_acis_meta"]["clock_skew"] is True
        assert any(e[0] == "CLOCK_SKEW" for e in result.events)

    def test_velocity_cold_start_reports_warming(self, factory) -> None:
        result = factory.build(tick())
        assert result.state.raw["_acis_meta"]["velocity_warming"] is True

    def test_out_of_order_tick_does_not_corrupt_velocity(self, factory) -> None:
        # GAP-0022 repro: in-order t0..t2, out-of-order at t0-8s, then t3.
        # The stale entry must be evicted once outside the trailing window.
        for i in range(3):
            factory.build(tick(event=T0 + timedelta(seconds=i), bid=1.1 + i * 1e-5,
                               ask=1.10012 + i * 1e-5))
        factory.build(tick(event=T0 - timedelta(seconds=8), bid=1.09, ask=1.09012))
        result = factory.build(tick(event=T0 + timedelta(seconds=3), bid=1.11, ask=1.11012))
        # Window is 10s anchored at t3: {t0,t1,t2,t3} in, t0-8s out => 4/10.
        assert result.state.tick_velocity == pytest.approx(0.4)

    def test_implausible_spread_flagged_not_rejected(self, factory) -> None:
        result = factory.build(tick(bid=1.1000, ask=1.1010))  # > 0.0005 max
        assert result.state is not None
        assert result.state.raw["_acis_meta"]["implausible_spread"] is True

    def test_session_median_warms_then_reports(self, factory, acis_config) -> None:
        n = acis_config.system.data.session_median_min_samples
        assert factory.session_median("EUR_USD", "overlap", "spread") is None
        for i in range(n):
            factory.build(tick(event=T0 + timedelta(seconds=i + 1)))
        median = factory.session_median("EUR_USD", "overlap", "spread")
        assert median == pytest.approx(0.00012)


class TestDeepImmutability:
    def test_raw_and_book_are_deeply_frozen(self, factory) -> None:
        ms = factory.build(tick(book={"bids": ((1.0999, 5.0),), "asks": ((1.1002, 5.0),)})).state
        assert ms is not None
        with pytest.raises(TypeError):
            ms.raw["injected"] = 1  # type: ignore[index]
        with pytest.raises(TypeError):
            ms.raw["_acis_meta"]["injected"] = 1  # type: ignore[index]
        with pytest.raises(TypeError):
            ms.order_book_depth["bids"] = ()  # type: ignore[index]
        with pytest.raises(Exception):
            delattr(ms, "bid")

    def test_frozen_dataclass_attribute_reassignment_fails(self, factory) -> None:
        ms = factory.build(tick()).state
        with pytest.raises(Exception):
            ms.bid = 0.0  # type: ignore[misc]
