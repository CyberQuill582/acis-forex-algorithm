"""GOTOBI's book on synthetic Dukascopy tick files (GAP-P12D-158): the vectorised decoder's refusals, prices
from the last tick at or before each wall time (never after, never stale), costs on both sides of each leg,
the gated reversal, P&L on the 17:00 New York mark after the last exit, and a planted rise earning."""

from __future__ import annotations

import lzma
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.bi5 import TICK, Bi5Error, decode_arrays
from tests.backtest.event_sim import NY
from tests.backtest.event_window import Leg, simulate_window, window_prices

UTC, JST = timezone.utc, "Asia/Tokyo"
TIMES = {"entry": time(3, 0), "nine": time(9, 0), "fix": time(9, 55), "noon": time(12, 0)}
H1 = Leg("entry", "fix", 1.0)
H2 = Leg("fix", "noon", -1.0, gate=("entry", "nine"))


def _write(root, utc_day: date, ticks: list[tuple[int, float, float]]) -> None:
    """`ticks` = (seconds from the UTC day's start, bid, ask)."""
    r = np.zeros(len(ticks), TICK)
    r["ms"] = [s * 1000 for s, _, _ in ticks]
    r["bid"] = [round(b * 1000) for _, b, _ in ticks]
    r["ask"] = [round(a * 1000) for _, _, a in ticks]
    f = root / "USD_JPY" / str(utc_day.year) / f"{utc_day.month - 1:02d}" / f"{utc_day.day:02d}_ticks.bi5"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE))


def _jst_mornings(root, paths: dict[date, dict[time, float]], spread: float = 0.004) -> None:
    """Ticks at each day's JST wall times, 1 s before each (so 'at or before' is exercised), merged per UTC file."""
    by_day: dict[date, list] = {}
    for d, path in paths.items():
        for t, mid in path.items():
            at = datetime.combine(d, t, tzinfo=ZoneInfo(JST)).astimezone(UTC) - timedelta(seconds=1)
            by_day.setdefault(at.date(), []).append((at.hour * 3600 + at.minute * 60 + at.second,
                                                     mid - spread / 2, mid + spread / 2))
    for day, ticks in by_day.items():
        _write(root, day, sorted(ticks))


def test_the_vectorised_decoder_refuses_a_wrong_scale_and_ticks_out_of_order(tmp_path) -> None:
    r = np.zeros(2, TICK)
    r["ms"], r["bid"], r["ask"] = [5, 1], [110_000, 110_000], [110_004, 110_004]
    with pytest.raises(Bi5Error, match="out of order"):
        decode_arrays(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE), "USD_JPY", datetime(2020, 1, 7, tzinfo=UTC))
    r["ms"], r["bid"] = [1, 5], [110, 110]
    with pytest.raises(Bi5Error, match="scale"):
        decode_arrays(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE), "USD_JPY", datetime(2020, 1, 7, tzinfo=UTC))


def test_a_price_is_the_last_tick_at_or_before_the_time_never_a_later_or_stale_one(tmp_path) -> None:
    d = date(2020, 1, 7)                                                   # a Tuesday; 09:55 JST = 00:55 UTC
    _write(tmp_path, d, [(55 * 60 - 1, 108.000, 108.004), (55 * 60 + 1, 109.000, 109.004)])
    s = window_prices(tmp_path, "USD_JPY", [d], JST, {"fix": time(9, 55), "noon": time(12, 0)})[0]
    assert s.prices["fix"] == pytest.approx((108.002, 0.004))              # the tick after 09:55 is not used
    assert s.prices["noon"] is None                                         # last tick ~2 h earlier: stale


def test_each_leg_pays_both_sides_and_the_gated_reversal_trades_only_after_a_rise(tmp_path) -> None:
    up, flat = date(2020, 1, 7), date(2020, 1, 8)
    _jst_mornings(tmp_path, {up: {time(3, 0): 108.0, time(9, 0): 108.3, time(9, 55): 108.5, time(12, 0): 108.2},
                             flat: {time(3, 0): 108.0, time(9, 0): 107.9, time(9, 55): 108.1, time(12, 0): 107.6}})
    sessions = window_prices(tmp_path, "USD_JPY", [up, flat], JST, TIMES)
    cost = CostModel(0.0, 0.001)
    r = simulate_window(sessions, cost, date(2020, 1, 6), date(2020, 1, 6), date(2020, 1, 10), [H1, H2], JST, TIMES)
    side = lambda p: cost.per_side_cost(0.004) / p                          # noqa: E731
    want_up = (108.5 / 108.0 - 1 - 2 * side(108.0)) + (-(108.2 / 108.5 - 1) - 2 * side(108.5))
    want_flat = 108.1 / 108.0 - 1 - 2 * side(108.0)                          # no rise by 09:00: H2 stays out
    by_day = dict(zip(r.days, r.daily))
    assert by_day[up] == pytest.approx(want_up) and by_day[flat] == pytest.approx(want_flat)
    assert [e["legs"] for e in r.events] == [["entry->fix", "fix->noon"], ["entry->fix"]]


def test_the_pnl_lands_on_the_17_00_new_york_mark_after_the_last_exit_and_a_missing_price_skips(tmp_path) -> None:
    d = date(2020, 1, 9)                                                   # Thursday JST morning
    _jst_mornings(tmp_path, {d: {time(3, 0): 108.0, time(9, 55): 108.4}})
    sessions = window_prices(tmp_path, "USD_JPY", [d, date(2020, 1, 10)], JST, TIMES)
    r = simulate_window(sessions, None, date(2020, 1, 6), date(2020, 1, 6), date(2020, 1, 10), [H1], JST,
                        {k: TIMES[k] for k in ("entry", "fix")})
    exit_utc = datetime.combine(d, time(9, 55), tzinfo=ZoneInfo(JST))
    mark = datetime.combine(d, time(17, 0), tzinfo=NY)
    assert exit_utc < mark and dict(zip(r.days, r.daily))[d] == pytest.approx(108.4 / 108.0 - 1)
    assert r.skipped == ({"day": "2020-01-10", "reason": "no entry"},)


def test_a_planted_gotobi_rise_earns_net_and_a_flat_market_loses_only_its_costs(tmp_path) -> None:
    days = [date(2020, 1, 7) + timedelta(days=7 * k + j) for k in range(8) for j in range(4)]
    rng = np.random.default_rng(5)
    planted_paths = {}
    for d in days:
        p0 = 108 + rng.normal(0, 0.5)
        planted_paths[d] = {time(3, 0): p0, time(9, 55): p0 + 0.05}
    _jst_mornings(tmp_path, planted_paths)
    flat_root = tmp_path / "flat"
    _jst_mornings(flat_root, {d: {time(3, 0): 108.0, time(9, 55): 108.0} for d in days})
    t = {k: TIMES[k] for k in ("entry", "fix")}
    cost = CostModel(0.0, 0.001)
    span = (days[0], days[0], days[-1] + timedelta(days=1))
    planted = simulate_window(window_prices(tmp_path, "USD_JPY", days, JST, t), cost, *span, [H1], JST, t)
    flat = simulate_window(window_prices(flat_root, "USD_JPY", days, JST, t), cost, *span, [H1], JST, t)
    assert planted.daily.sum() > 0 and len(planted.events) == len(days)
    assert flat.daily.sum() == pytest.approx(-len(days) * 2 * cost.per_side_cost(0.004) / 108.0)


def test_the_weekday_contrast_cancels_a_friday_drift_and_keeps_a_gotobi_one(tmp_path) -> None:
    """PC-I-08: half the event days are Fridays and few controls are, as in GOTOBI's real calendar. A
    Friday-only drift earns the plain long book but nothing in the contrast; an event-day drift survives it."""
    from tests.backtest.event_window import weekday_contrast
    events = [date(2020, 1, 10) + timedelta(days=7 * k) for k in range(10)]                 # Fridays
    events += [date(2020, 1, 8) + timedelta(days=14 * k) for k in range(10)]               # some Wednesdays
    controls = [date(2020, 1, 7) + timedelta(days=7 * k + j) for k in range(20) for j in (0, 1, 2)
                if date(2020, 1, 7) + timedelta(days=7 * k + j) not in events]
    controls += [date(2020, 1, 17) + timedelta(days=21 * k) for k in range(5)]             # a few control Fridays
    t = {k: TIMES[k] for k in ("entry", "fix")}
    span = (date(2020, 1, 6), date(2020, 1, 6), date(2020, 6, 30))
    for name, drift, earns in (("friday", lambda d: 0.05 if d.weekday() == 4 else 0.0, False),
                               ("gotobi", lambda d: 0.05 if d in events else 0.0, True)):
        root = tmp_path / name
        _jst_mornings(root, {d: {time(3, 0): 108.0, time(9, 55): 108.0 + drift(d)} for d in events + controls})
        ev, ct = (window_prices(root, "USD_JPY", ds, JST, t) for ds in (events, controls))
        plain = simulate_window(ev, None, *span, [H1], JST, t).daily.sum()
        contrast = weekday_contrast(ev, ct, *span, [H1], JST, t).daily.sum()
        assert plain > 0
        assert (contrast > 0.5 * plain) if earns else contrast == pytest.approx(0.0, abs=1e-12)
