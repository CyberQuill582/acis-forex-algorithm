"""The tournament's books (TOURNAMENT, 2026-10-04): each registered rule's forward daily net returns, computed
by the SAME simulator and constants as its kill-only looks, from the frozen input store only.

Mental model:
  * Three shapes, so a new family is one registry entry: `rsim_book` (daily target positions on the 17:00
    New York clock: RSIM), `close_book` (a position set at each US cash close: event_daily), `window_book`
    (fixed local-time windows priced from ticks: event_window). Each returns a `BookSeries` of NY-weekday
    marks from the forward start through its SETTLED horizon, flat (and costless) before the forward start.
  * SETTLED: every input of every returned day is frozen. RSIM's day t ends at the fill after decision t,
    so it counts once every instrument's next slot hour is in the data; a close book is settled through
    the minute, S&P and Treasury horizons; a window book through the tick horizon. A later run never
    changes a settled day unless an input was revised, which the record shows as a revision.
  * Causal: the only read of the future is the exchange's published calendar (REBAL's month-end term
    needs the month's remaining NYSE sessions, as a live trader knows them); returns never.
  * D1 starts its market at its development look's origin (2012-01-02), so Carver's 10-year slow volatility
    is the registered rule's; REBAL's signals start at its look's 2011-01-03; GOTOBI needs no warm-up.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np

from core.optimizer.costs import cost_model
from core.runtime.target_decision import class_equal_weights
from core.signals.forecast import WARMUP
from tests.backtest.event_daily import simulate_daily
from tests.backtest.event_window import simulate_window, window_prices
from tests.backtest.exchange_days import holidays as exchange_holidays
from tests.backtest.forward_store import RATE_SIDS, SPX, Y7, InputStore
from tests.backtest.jp_days import gotobi_days
from tests.backtest.rebal import signals
from tests.backtest.rsim import BookSpec, panel, run
from tests.backtest.rsim_lab import carver_pct_vol
from tests.backtest.rsim_real import NY, SLOTS, _slot_index, build, masked
from tests.backtest.universe import BY_NAME

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BookSeries:
    dates: tuple[date, ...]
    net: np.ndarray
    horizon: date
    meta: dict = field(default_factory=dict)


@lru_cache(maxsize=None)
def kill_script(name: str):
    """A registered kill-only look's own script, so its constants define the forward rule by identity; None
    while the script is not on this branch (a survivor whose book the lead has not integrated yet)."""
    if not (ROOT / "scripts" / f"{name}.py").exists():
        return None
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _from(dates, net, forward_start: date, horizon: date, meta: dict) -> BookSeries:
    keep = [k for k, d in enumerate(dates) if forward_start <= d <= horizon]
    return BookSeries(tuple(dates[k] for k in keep), np.asarray(net, float)[keep], horizon, meta)


def _filled(hours: dict, names, days, cutoff: int) -> int:
    """How many leading decision days have every instrument's fill (its next slot hour) in the data."""
    stamps = np.array([int(datetime.combine(d, time(17, 0), tzinfo=NY).timestamp()) for d in days], np.int64)
    n = len(days)
    for name in names:
        h = hours[name]
        slots = h.start[_slot_index(h, *(SLOTS[name] if name in SLOTS else SLOTS[BY_NAME[name].asset_class]))]
        k = np.searchsorted(slots, stamps, side="left")
        real = (k < len(slots)) & (slots[np.minimum(k, len(slots) - 1)] + 3600 <= cutoff)
        n = min(n, int(np.argmin(real)) if not real.all() else n)
    return n


def d1_forecast(member: Callable) -> Callable:
    """A TREND member on the excess-return price, masked through each instrument's warm-up (D1's looks)."""
    return lambda store, real, end, forward_start: masked(panel(real.market, member), real)


def rsim_book(forecast: Callable, names: tuple[str, ...], market_from: date, *, idm: float, buffer: float,
              capital: float = 1_000_000.0, vol_target: float = 0.20, input_end: Callable | None = None):
    """`forecast(store, real, end, forward_start)` is the family's panel (rows before the start are masked
    flat anyway); `input_end(store, today)` the last decision day its other inputs have settled."""
    def book(store: InputStore, cfg, forward_start: date, today: date) -> BookSeries:
        t = cfg.system.targets
        seen = store.minute_horizon(names, today)
        end = min(seen, *(store.through(s) for s in RATE_SIDS),           # decisions need that day's rates
                  *((input_end(store, today),) if input_end else ()))
        hours: dict = {}
        def loader(n: str):
            if n not in hours:
                hours[n] = store.hourly(n, seen)                        # fills may fall after `end`
            return hours[n]
        rates = store.rates(end, t.rate_max_stale_days, t.rate_max_stale_days_weekly)
        real = build(None, names, rates, market_from, end, tier="forward", loader=loader)
        m = real.market
        f = np.array(forecast(store, real, end, forward_start), float, copy=True)
        f[np.array([d < forward_start for d in m.days])] = np.nan          # flat before the forward start
        spec = BookSpec(costs={n: cost_model(cfg, n) for n in names}, capital=capital, vol_target=vol_target,
                        idm=idm, buffer=buffer, world="swap_free",
                        weights=class_equal_weights({n: cfg.instruments.instruments[n].asset_class for n in names}))
        res = run(m, f, carver_pct_vol(m), spec)
        cutoff = int(datetime.combine(seen + timedelta(days=1), time(0), tzinfo=timezone.utc).timestamp())
        k = _filled(hours, names, m.days, cutoff)
        settled = m.days[k - 1] if k else forward_start - timedelta(days=1)
        return _from(m.days, res.daily, forward_start, settled, {"fills": res.fills, "warmup": WARMUP})
    return book


def nyse_sessions_after(end: date, months: int = 2) -> list[date]:
    """The NYSE's published sessions after `end` through the end of the next month: weekdays off its
    holiday rules, which hold every holiday that can fall in a month's last ten days (exchange_days)."""
    y, m = end.year + (end.month + months - 1) // 12, (end.month + months - 1) % 12 + 1
    stop, out, d = date(y, m, 1), [], end + timedelta(days=1)
    while d < stop:
        if d.weekday() < 5 and d not in exchange_holidays("XNYS", d.year):
            out.append(d)
        d += timedelta(days=1)
    return out


def rebal_position(days: list[date], spx: dict, y7: dict) -> np.ndarray:
    """REBAL's paper position on each S&P business day, its calendar term reading the published sessions."""
    future = nyse_sessions_after(days[-1])
    ext = {**spx, **{d: spx[days[-1]] for d in future}}           # no return after today: rs = rb = 0
    return signals(days + future, ext, y7)["position"][: len(days)]


def close_book(instrument: str, position: Callable, signal_from: date):
    def book(store: InputStore, cfg, forward_start: date, today: date) -> BookSeries:
        end = min(store.minute_horizon((instrument,), today), store.through(SPX), store.through(Y7))
        spx, y7 = store.closes(SPX, end), store.closes(Y7, end)
        days = [d for d in sorted(spx) if signal_from <= d <= end]
        res = simulate_daily(store.hourly(instrument, end), days, position(days, spx, y7), cost_model(cfg, instrument),
                             forward_start, forward_start, end)
        return _from(res.days, res.daily, forward_start, end, {"skipped": len(res.skipped)})
    return book


def gotobi_tue_fri(first: date, last: date, holidays: frozenset[date]) -> list[date]:
    g = kill_script("r1_gotobi_kill_test")
    return [d for d in gotobi_days(first, last, holidays, last_day="30") if d.weekday() in g.WEEKDAYS]


def window_book(instrument: str, legs: tuple, times: dict, zone: str, day_rule: Callable):
    def book(store: InputStore, cfg, forward_start: date, today: date) -> BookSeries:
        end = store.tick_horizon(instrument, today)
        days = day_rule(forward_start, end, store.holidays_jp()) if end >= forward_start else []
        sessions = window_prices(store.root / "ticks", instrument, days, zone, times)
        res = simulate_window(sessions, cost_model(cfg, instrument), forward_start, forward_start, end, legs, zone,
                              times) if end >= forward_start else None
        if res is None:
            return BookSeries((), np.zeros(0), end, {})
        return _from(res.days, res.daily, forward_start, end, {"traded": len(res.events), "skipped": len(res.skipped)})
    return book
