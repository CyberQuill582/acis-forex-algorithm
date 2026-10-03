"""The minute decoder and IMOM's book on synthetic Dukascopy day files (GAP-P12D-158): every refusal of a
bad file, prices at local wall times from the last quoted minute, the last half hour traded on the
predictor's sign, costs on both sides, and a session without a price skipped."""

from __future__ import annotations

import lzma
from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.candles import CandleError
from tests.backtest.candles_min import RAW, decode_day
from tests.backtest.event_intraday import session_prices, simulate_imom
from tests.backtest.event_sim import NY
from tests.backtest.universe import BY_NAME

US500 = BY_NAME["US500"]
TIMES = {"onfh": time(10, 0), "c30": time(15, 30), "close": time(16, 0)}


def _encode(day: date, mids: np.ndarray, spread: float, volume: np.ndarray) -> tuple[bytes, bytes]:
    out = []
    for shift in (-spread / 2, spread / 2):
        r = np.zeros(1440, RAW)
        r["sec"] = np.arange(1440) * 60
        px = np.round((mids + shift) * US500.scale).astype(np.uint32)
        r["open"] = np.r_[px[0], px[:-1]]
        r["close"] = px
        r["low"], r["high"] = np.minimum(r["open"], r["close"]), np.maximum(r["open"], r["close"])
        r["volume"] = volume
        out.append(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE))
    return out[0], out[1]


def _write(root, day: date, price, spread: float = 0.4, quoted=lambda ts: True) -> None:
    ts = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) + np.arange(1440) * 60
    mids = np.array([price(t + 60) for t in ts])                        # the price at each minute's END
    vol = np.array([1.0 if quoted(t) else 0.0 for t in ts], np.float32)
    if not any(quoted(t) for t in ts):
        mids = np.full(1440, mids[0])                                    # a frozen day: flat, no volume
    base = root / US500.duka / str(day.year) / f"{day.month - 1:02d}" / f"{day.day:02d}"
    base.mkdir(parents=True, exist_ok=True)
    bid, ask = _encode(day, mids, spread, vol)
    (base / "BID_candles_min_1.bi5").write_bytes(bid)
    (base / "ASK_candles_min_1.bi5").write_bytes(ask)


def _at(d: date, t: time) -> int:
    return int(datetime.combine(d, t, tzinfo=NY).timestamp())


def test_a_day_decodes_and_every_bad_file_is_refused() -> None:
    day = date(2021, 3, 1)
    good, _ = _encode(day, np.linspace(3800, 3810, 1440), 0.4, np.ones(1440, np.float32))
    rows = decode_day(good, "US500", day)
    assert len(rows) == 1440 and rows["close"][-1] == pytest.approx(3810 - 0.2)
    raw = lzma.decompress(good, format=lzma.FORMAT_ALONE)
    with pytest.raises(CandleError, match="bytes"):
        decode_day(lzma.compress(raw[:-24], format=lzma.FORMAT_ALONE), "US500", day)
    swapped = bytearray(raw)
    swapped[0:4], swapped[24:28] = raw[24:28], raw[0:4]
    with pytest.raises(CandleError, match="in order"):
        decode_day(lzma.compress(bytes(swapped), format=lzma.FORMAT_ALONE), "US500", day)
    far, _ = _encode(day, np.full(1440, 90000.0), 0.4, np.ones(1440, np.float32))
    with pytest.raises(CandleError, match="outside"):
        decode_day(far, "US500", day)


def test_the_last_half_hour_follows_the_rest_of_day_sign_and_pays_both_sides(tmp_path) -> None:
    days = [date(2021, 3, 1), date(2021, 3, 2), date(2021, 3, 3)]
    paths = {date(2021, 3, 1): (4000, 4000, 4010), date(2021, 3, 2): (4010, 3990, 3980),
             date(2021, 3, 3): (3980, 4000, 4004)}                      # (previous close, at 15:30, at 16:00)

    def price(t: int) -> float:
        d = datetime.fromtimestamp(t, NY).date()
        if d not in paths:
            return 4000.0
        prev, c30, close = paths[d]
        return float(np.interp(t, [_at(d, time(9, 30)), _at(d, time(15, 30)), _at(d, time(16, 0))], [prev, c30, close]))
    for d in days:
        _write(tmp_path, d, price)
    s = session_prices(tmp_path, "US500", days, "America/New_York", TIMES)
    assert s[1].prices["c30"][0] == pytest.approx(3990.0) and s[1].prices["close"][1] == pytest.approx(0.4, abs=0.01)
    r = simulate_imom(s, CostModel(0.0, 0.0), days[0], days[1], days[2], "rod")
    mark = lambda d: r.daily[r.days.index(d)]                            # noqa: E731
    assert mark(days[1]) == pytest.approx(-1 * (3980 / 3990 - 1) - 2 * 0.2 / 3990, rel=1e-3)   # down day: short
    assert mark(days[2]) == pytest.approx(+1 * (4004 / 4000 - 1) - 2 * 0.2 / 4000, rel=1e-3)   # up day: long
    later = simulate_imom(s, None, days[0], days[1], days[2], "onfh")
    assert later.daily.sum() != 0 and not r.skipped


def test_a_session_whose_half_hour_has_no_quote_is_skipped_with_its_reason(tmp_path) -> None:
    days = [date(2021, 11, 24), date(2021, 11, 26)]                     # the day after Thanksgiving: 13:00 close
    early = _at(days[1], time(13, 15))
    moving = lambda t: 4600.0 + (t % 7200) / 7200                       # noqa: E731
    _write(tmp_path, days[0], moving)
    _write(tmp_path, days[1], lambda t: moving(min(t, early)), quoted=lambda t: t + 60 <= early)   # closed: flat
    s = session_prices(tmp_path, "US500", days, "America/New_York", TIMES)
    r = simulate_imom(s, None, days[0], days[1], days[1], "rod")
    assert r.skipped == ({"session": "2021-11-26", "reason": "no signal"},)


def test_the_large_move_version_trades_only_above_the_trailing_quantile_of_past_moves() -> None:
    """Owner ruling 2026-10-03: the threshold reads past sessions only, so today's move never sets its own bar."""
    from tests.backtest.event_intraday import MIN_HISTORY, Session
    days = [date(2021, 1, 4) + timedelta(days=k) for k in range(400)]
    days = [d for d in days if d.weekday() < 5][:MIN_HISTORY + 40]
    rng = np.random.default_rng(3)
    moves = rng.normal(0, 0.01, len(days))
    sessions, close = [], 4000.0
    for d, m in zip(days, moves):
        c30 = close * (1 + m)
        sessions.append(Session(d, {"c30": (c30, 0.0), "close": (c30 * 1.001, 0.0), "onfh": (c30, 0.0)}))
        close = c30 * 1.001
    every = simulate_imom(sessions, None, days[0], days[1], days[-1], "rod")
    big = simulate_imom(sessions, None, days[0], days[1], days[-1], "rod", top=2 / 3)
    traded = [d for d in days if big.daily[big.days.index(d)] != 0]
    assert traded and all(d >= days[MIN_HISTORY] for d in traded)
    k = days.index(traded[0])
    bar = np.quantile(np.abs(moves[1:k]), 2 / 3)                         # the sessions before it only
    assert abs(moves[k]) >= bar and big.daily[big.days.index(traded[0])] == pytest.approx(every.daily[every.days.index(traded[0])])
    assert 0.2 < len(traded) / 40 < 0.5
