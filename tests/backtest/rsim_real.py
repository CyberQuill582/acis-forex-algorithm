"""RSIM's real-data source: the verified hourly candles as a Market (GAP-P12D-136 item 1).

Mental model (each choice declared; the clock per symbol is GAP-P12D-95's, pre-registered here):
  * DECISION: every New York weekday at 17:00 New York (the FX rollover). An instrument's close is
    the mid close of its last TRADED hour ending at or before that instant, if within 4 days; a
    day no instrument traded in the prior 24 h (Christmas, New Year) is not a decision day.
  * FILL: the first traded hour starting at or after the decision whose LOCAL hour is the symbol's
    execution slot (FX and metals 08:00 New York, US indices and energy 10:00 New York, UK100
    09:00 London, EU50 and GER40 09:00 Frankfurt, JP225 10:00 Tokyo, AUS200 11:00 Sydney): its
    open mid is the fill price and ask − bid its spread. Never before the decision: no look-ahead.
  * CARRY, a long's fair financing per 17:00-New-York rollover, rate × the calendar's multiple / 365:
    FX the dated differential base − quote; metals an ASSUMED 0.25% lease − quote (as the harness);
    indices −quote, the funding cost only (dividends are not on disk: a long's carry is understated
    by the dividend yield, declared). `carry[t]` sums the rollovers between fill t and fill t+1.
  * The rules read the EXCESS-return price: close-to-close compounded with the rollovers between
    decisions (GAP-P12D-71). `q` converts the quote currency to USD at the fill.
  * BEFORE an instrument's data starts (US30 and GER40 2013-09, AUS200 2013-01, XCU 2012-03) its
    columns are back-filled flat, and `first_valid` says where its data begins: the caller masks its
    forecasts until then plus the warm-up (`masked`), so a flat history never sizes a position.
  * GUARDS: energy CFDs carry unadjusted futures rolls (NATGAS +37% on 2020-09-22), so they are
    refused until back-adjusted (GAP-P12D-137); a tier refuses held-out instruments outside stage
    C and data after 2023 outside the holdout look.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from core.data.rates import RateTable, accrual, swap_multiplier
from core.signals.forecast import WARMUP
from tests.backtest.candle_store import Hourly, load
from tests.backtest.rsim import Market
from tests.backtest.universe import BY_NAME, EXPLORED, HELD_OUT

NY = ZoneInfo("America/New_York")
SLOTS = {"fx": ("America/New_York", 8), "metal": ("America/New_York", 8), "energy": ("America/New_York", 10),
         "US500": ("America/New_York", 10), "US30": ("America/New_York", 10), "US100": ("America/New_York", 10),
         "UK100": ("Europe/London", 9), "EU50": ("Europe/Berlin", 9), "GER40": ("Europe/Berlin", 9),
         "JP225": ("Asia/Tokyo", 10), "AUS200": ("Australia/Sydney", 11)}
TO_USD = {"EUR": ("EUR_USD", 1), "GBP": ("GBP_USD", 1), "AUD": ("AUD_USD", 1), "NZD": ("NZD_USD", 1),
          "JPY": ("USD_JPY", -1), "CAD": ("USD_CAD", -1), "CHF": ("USD_CHF", -1)}
TIERS = {"development": (EXPLORED, date(2023, 12, 31)), "stage_c": (tuple(HELD_OUT), date(2023, 12, 31)),
         "holdout": (EXPLORED, date(2025, 12, 31)), "forward": (EXPLORED, date(2099, 12, 31))}   # the tournament
STALE_S = 4 * 86400


class SourceRefused(Exception):
    """A market the declared tier or the data cannot honestly build."""


class CandleSource:
    name, provenance = "dukascopy-candles-hourly", "real"


@dataclass(frozen=True)
class RealMarket:
    market: Market
    first_valid: dict[str, int]          # the first decision day with the instrument's own data


def _decisions(start: date, end: date) -> list[tuple[date, int]]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append((d, int(datetime(d.year, d.month, d.day, 17, tzinfo=NY).timestamp())))
        d += timedelta(days=1)
    return out


class _Closes:
    """An instrument's traded hours' (end, mid close), built once: `at(t)` is the last close <= t."""

    def __init__(self, h: Hourly) -> None:
        self.ends, self.mids = h.start[h.traded] + 3600, h.mid_close[h.traded]

    def at(self, t: int) -> tuple[float, int] | None:
        k = int(np.searchsorted(self.ends, t, side="right")) - 1
        return (float(self.mids[k]), int(self.ends[k])) if k >= 0 else None


def _slot_index(h: Hourly, zone: str, hour: int) -> np.ndarray:
    tz = ZoneInfo(zone)
    idx = np.flatnonzero(h.traded)
    keep = [i for i in idx if (lt := datetime.fromtimestamp(int(h.start[i]), tz)).hour == hour and lt.weekday() < 5]
    return np.asarray(keep, np.int64)


def build(root: Path | None, names: Sequence[str], rates: RateTable, start: date, end: date, *, tier: str,
          loader: Callable[[str], Hourly] | None = None) -> RealMarket:
    """`loader` (an instrument's Hourly through `end`) replaces the archive read: the forward store's."""
    allowed, last = TIERS[tier]
    if bad := [n for n in names if n not in allowed]:
        raise SourceRefused(f"tier {tier!r} may not read {bad}")
    if end > last:
        raise SourceRefused(f"tier {tier!r} ends {last}; asked for {end}")
    if energy := [n for n in names if BY_NAME[n].asset_class == "energy"]:
        raise SourceRefused(f"{energy}: unadjusted futures rolls (GAP-P12D-137)")
    until = (end.year, end.month)
    read = loader or (lambda n: load(root, n, until))
    series = {n: read(n) for n in {*names, *(TO_USD[BY_NAME[n].quote][0] for n in names if BY_NAME[n].quote != "USD")}}
    closes = {n: _Closes(h) for n, h in series.items()}
    days = [(d, at) for d, at in _decisions(start, end)
            if any((c := closes[n].at(at)) and at - c[1] < 86400 for n in names)]
    if len(days) < 2:
        raise SourceRefused("fewer than two decision days")
    T, N = len(days), len(names)
    cols = {k: np.full((T, N), np.nan) for k in ("price", "close", "fill", "spread", "carry", "nights", "q")}
    fill_at = np.zeros((T, N), np.int64)
    first_valid = {}
    for i, n in enumerate(names):
        h, inst = series[n], BY_NAME[n]
        slots = _slot_index(h, *(SLOTS[n] if n in SLOTS else SLOTS[inst.asset_class]))
        for t, (d, at) in enumerate(days):
            c = closes[n].at(at)
            if c and at - c[1] <= STALE_S:
                cols["close"][t, i] = c[0]
                first_valid.setdefault(n, t)
            k = np.searchsorted(h.start[slots], at, side="left")
            if k < len(slots):
                j = slots[k]
                cols["fill"][t, i], cols["spread"][t, i], fill_at[t, i] = h.mid_open[j], h.spread_open[j], h.start[j]
        if n not in first_valid:
            raise SourceRefused(f"{n}: no data in {start}..{end}")
        _fill_columns(cols, fill_at, i, n, days, rates, closes,
                      "tom_next" if inst.asset_class == "fx" else "financing_daily")
    return RealMarket(Market(names=tuple(names), days=tuple(d for d, _ in days), **cols), first_valid)


def _fill_columns(cols, fill_at, i, n, days, rates, closes, convention) -> None:
    """Back-fill before the data, carry forward through gaps, then carry, nights, q and the price."""
    for k in ("close", "fill", "spread"):
        col = cols[k][:, i]
        first = int(np.flatnonzero(~np.isnan(col))[0])
        col[:first] = col[first]
        for t in range(1, len(col)):
            if np.isnan(col[t]):
                col[t] = col[t - 1]
    fa = fill_at[:, i]
    fa[fa == 0] = max(int(fa.max()), days[-1][1])
    for t in range(1, len(fa)):
        fa[t] = max(fa[t], fa[t - 1])
    roll_days = [d for d, _ in days]
    roll_at = np.asarray([at for _, at in days], np.int64)
    inst = BY_NAME[n]
    accruals = np.asarray([accrual(inst.asset_class, n, inst.quote, rates, d) for d in roll_days])
    mult = np.asarray([swap_multiplier(d, convention) for d in roll_days], float)
    for t in range(len(fa)):
        hi = fa[t + 1] if t + 1 < len(fa) else fa[t]
        sel = (roll_at > fa[t]) & (roll_at <= hi)
        cols["carry"][t, i], cols["nights"][t, i] = accruals[sel].sum(), mult[sel].sum()
    quote = BY_NAME[n].quote
    for t in range(len(fa)):
        if quote == "USD":
            cols["q"][t, i] = 1.0
        else:
            pair, sign = TO_USD[quote]
            c = closes[pair].at(int(fa[t]))
            cols["q"][t, i] = c[0] if sign > 0 else 1.0 / c[0]
    close = cols["close"][:, i]
    growth = np.ones(len(close))
    growth[1:] = close[1:] / close[:-1] * (1.0 + accruals[1:])   # the rollover at each decision instant
    cols["price"][:, i] = np.cumprod(growth)


def masked(forecast: np.ndarray, real: RealMarket, warmup: int = WARMUP) -> np.ndarray:
    """NaN (flat) before each instrument's own data plus `warmup` decision days."""
    out = forecast.copy()
    for i, n in enumerate(real.market.names):
        out[: real.first_valid[n] + warmup, i] = np.nan
    return out
