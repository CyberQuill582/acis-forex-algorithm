"""The venue's hourly trendbars against the fake venue (ACIS-04 v1.6 §4b seeding; core/data/ctrader/
history.py): decoding, the backward walk, truncation, a refused range, and the budget's reserve."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.data.ctrader.history import HOUR, decode_bar, end_of, hourly_bars
from core.data.ctrader.meter import BudgetRefused, RequestMeter
from core.data.ctrader.schema import PT
from core.data.ctrader.session import Credentials, CTraderSession
from core.data.ctrader.tokens import TokenPair, TokenStore
from core.data.ctrader.wire import VenueError
from core.data.errors import DataQualityError
from tests.ctrader_fixtures import ACCOUNT, T0, FakeVenue, capture_logger, events, h1_bar

KEY = f"ctrader:demo:{ACCOUNT}"
END = T0.replace(minute=0)


async def _session(tmp_path, venue, *, budget=1000, reserve=100):
    log, buf = capture_logger()
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("access-1", "refresh-1", T0 + timedelta(days=20), T0, "trading"))
    meter = RequestMeter(tmp_path / "venue.db", KEY, budget=budget, reserve=reserve, now=T0)
    session = CTraderSession(environment="demo", binding=ACCOUNT, credentials=Credentials("cid", "sec"),
                             tokens=tokens, meter=meter, logger=log, connect=venue.connect,
                             now_fn=lambda: venue.clock, rate_per_s=10_000, history_per_s=10_000,
                             request_timeout_s=0.5)
    await session.start()
    session.mark_ready()
    return session, meter, log, buf


def _hours(n: int, end=END, step=0.0001) -> list[dict]:
    return [h1_bar(end - (n - k) * HOUR, round(1.1 + k * step, 5)) for k in range(n)]


def test_a_bar_decodes_from_integer_deltas_floored_to_its_hour() -> None:
    raw = {"low": 109_990, "deltaClose": 15, "deltaHigh": 30, "utcTimestampInMinutes": int(END.timestamp() // 60) + 3}
    bar = decode_bar(raw, 5)
    assert (bar.ts_open, bar.low, bar.close, bar.high, end_of(bar)) == (END, 1.0999, 1.10005, 1.1002, END + HOUR)
    assert (bar.open, bar.duration_s, bar.spread) == (1.0999, 3600, 0.0)        # no deltaOpen: open = low
    with pytest.raises(DataQualityError):
        decode_bar({**raw, "period": 12}, 5)                      # a D1 bar in an H1 response
    with pytest.raises(DataQualityError):
        decode_bar({"deltaClose": 1, "utcTimestampInMinutes": 1}, 5)   # no low: never guessed


async def test_a_long_history_walks_back_in_windows_and_keeps_only_complete_bars(tmp_path) -> None:
    venue = FakeVenue()
    venue.trendbars[1] = _hours(3 * 24 * 30) + [h1_bar(END, 1.2)]          # the last is still forming
    session, _, log, buf = await _session(tmp_path, venue)
    bars = await hourly_bars(session, 1, 5, END - timedelta(days=90), END, logger=log,
                             window=timedelta(days=40))
    assert len(bars) == 3 * 24 * 30 and end_of(bars[-1]) == END                 # the forming bar is left out
    assert [b.ts_open for b in bars] == sorted(b.ts_open for b in bars)
    assert venue.requests.count(PT.GET_TRENDBARS_REQ) == 3                  # 90 days in 40-day windows
    assert events(buf, "TRENDBARS_FETCHED")[-1]["bars"] == len(bars)


async def test_a_truncated_response_continues_below_its_earliest_bar(tmp_path) -> None:
    venue = FakeVenue()
    venue.trendbars[1] = _hours(500)
    venue.trendbar_cap = 120                                                # the latest 120, hasMore
    session, _, log, _ = await _session(tmp_path, venue)
    bars = await hourly_bars(session, 1, 5, END - 500 * HOUR, END, logger=log)
    assert len(bars) == 500 and len({b.ts_open for b in bars}) == 500


async def test_a_refused_range_halves_the_window_and_too_small_a_window_raises(tmp_path) -> None:
    venue = FakeVenue()
    venue.trendbars[1] = _hours(24 * 60)
    venue.trendbar_max_range_ms = int(timedelta(days=20).total_seconds() * 1000)
    session, _, log, buf = await _session(tmp_path, venue)
    bars = await hourly_bars(session, 1, 5, END - timedelta(days=60), END, logger=log,
                             window=timedelta(days=60))
    assert len(bars) == 24 * 60
    assert [e["window_days"] for e in events(buf, "TRENDBARS_WINDOW_HALVED")] == [30.0, 15.0]
    venue.trendbar_max_range_ms = int(timedelta(days=1).total_seconds() * 1000)
    with pytest.raises(VenueError):
        await hourly_bars(session, 1, 5, END - timedelta(days=30), END, logger=log, window=timedelta(days=8))


async def test_history_is_a_metered_query_refused_inside_the_close_reserve(tmp_path) -> None:
    venue = FakeVenue()
    venue.trendbars[1] = _hours(48)
    session, meter, log, _ = await _session(tmp_path, venue, budget=10, reserve=7)
    sent = len(venue.requests)                                             # the authorisation's
    with pytest.raises(BudgetRefused):
        await hourly_bars(session, 1, 5, END - 48 * HOUR, END, logger=log)
    assert len(venue.requests) == sent                                     # nothing left: the exits keep the reserve


async def test_a_silently_truncated_response_is_walked_past_and_an_empty_window_ends_the_walk(tmp_path) -> None:
    """R16E-03: coverage is judged from the bars, never from `hasMore` alone."""
    venue = FakeVenue()
    venue.trendbars[1] = _hours(500)
    venue.trendbar_cap, venue.trendbar_silent = 120, True                  # cut back, no hasMore
    session, _, log, _ = await _session(tmp_path, venue)
    bars = await hourly_bars(session, 1, 5, END - timedelta(days=200), END, logger=log)
    assert len(bars) == 500 and len({b.ts_open for b in bars}) == 500
    sent = venue.requests.count(PT.GET_TRENDBARS_REQ)
    assert sent <= 500 // 120 + 2                                          # one empty window ends it


def test_the_default_window_is_inside_spotwares_documented_h1_range() -> None:
    from core.data.ctrader.history import WINDOW
    assert WINDOW <= timedelta(weeks=35)                                   # proto release 88 (R16E-03)
