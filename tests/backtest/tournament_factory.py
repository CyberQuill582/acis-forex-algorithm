"""FACTORY's survivors as forward books (TOURNAMENT, 2026-10-04; archive/RESEARCH_FACTORY_2026-10-03.md on
main): HALLOWEEN, HEDGEP and FXVALUE, each computed by its kill-only look's own module and constants.

Mental model:
  * Their modules (`halloween`, `event_multi`, `hedgep`, `fx_value`) and kill scripts are on main at
    00b9d3c; they are imported only when a book runs, so this branch builds before the lead integrates.
  * INPUT VIEWS: the frozen ECB fixings, BIS CPI and CFTC gold report are rewritten in each module's own
    file format (`<store>/views/`) and read by the module's own loader, as the looks read theirs.
  * SETTLED: HEDGEP through the day before its next report could be used (the release of the frozen
    as-of + 7 days); FXVALUE through the last month whose ranks' inputs are frozen (the ECB to the end of
    the month before, CPI to that month - 5); HALLOWEEN through every index's minute horizon.
  * HALLOWEEN's target on its last session reads the season of the NEXT session; forward that is the
    next weekday (the calendar), never a price. Only a feed hole on that weekday at a season's turn
    could make the full-data recompute differ, and the record would show it as a revision.
"""

from __future__ import annotations

import importlib
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from core.optimizer.costs import cost_model
from tests.backtest.forward_store import COT, COT_FIELDS, CPI, ECB, InputStore
from tests.backtest.tournament_books import BookSeries, _from, kill_script


def _module(name: str):
    return importlib.import_module(f"tests.backtest.{name}")


def _write(store: InputStore, name: str, header: str, lines) -> Path:
    path = store.root / "views" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(header + "\n" + "".join(f"{x}\n" for x in lines), encoding="utf-8")
    os.replace(tmp, path)
    return path


def ecb_view(store: InputStore) -> Path:
    rows = store.series(ECB, store.through(ECB))
    return _write(store, "ecb_daily.csv", "date,currency,eur_rate", (f"{d.isoformat()},{c},{v!r}" for d, c, v in rows))


def cpi_view(store: InputStore) -> Path:
    rows = store.series(CPI, store.through(CPI))
    return _write(store, "bis_cpi.csv", "month,area,cpi", (f"{d:%Y-%m},{a},{v!r}" for d, a, v in rows))


def cot_view(store: InputStore) -> Path:
    by: dict[date, dict[str, float]] = defaultdict(dict)
    for d, k, v in store.series(COT, store.through(COT)):
        by[d][k] = v
    lines = (f"{d.isoformat()}," + ",".join(str(int(by[d][k])) for k in COT_FIELDS)
             for d in sorted(by) if set(by[d]) == set(COT_FIELDS))
    return _write(store, "cot_gold.csv", "as_of," + ",".join(COT_FIELDS), lines)


def hedgep_forecast(store: InputStore, real, end: date, forward_start: date) -> np.ndarray:
    h = _module("hedgep")
    return h.panel(real.market.days, h.load(cot_view(store)))[:, None]


def hedgep_end(store: InputStore, today: date) -> date:
    """The day before the next report (as of the frozen one + 7 days) could be read."""
    nxt = store.through(COT) + timedelta(days=7)
    return (_module("hedgep").release(nxt) or nxt + timedelta(days=3)) - timedelta(days=1)


def _month_end(y: int, m: int) -> date:
    return date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)


def fxvalue_forecast(store: InputStore, real, end: date, forward_start: date) -> np.ndarray:
    """Ranks from the forward start only: rows before it are flat, and the US CPI print for 2025-10 is
    missing (the shutdown), so 2026-02's warm-up rank is undefined under the registered rule."""
    fx, k = _module("fx_value"), kill_script("r1_fxvalue_kill_test")
    days = real.market.days
    k0 = next((i for i, d in enumerate(days) if d >= forward_start), len(days))
    out = np.full((len(days), len(real.market.names)), np.nan)
    out[k0:] = fx.panel(days[k0:], real.market.names, fx.load_spot(ecb_view(store)), fx.load_cpi(cpi_view(store)),
                        k.FIRST)
    return out


def fxvalue_end(store: InputStore, today: date) -> date:
    """Month M trades month M-1's ranks: the ECB through M-1's end, CPI through M-5."""
    nxt = store.through(ECB) + timedelta(days=1)
    by_ecb = nxt.year * 12 + nxt.month - 1
    c = store.through(CPI)
    by_cpi = c.year * 12 + c.month - 1 + 5
    n = min(by_ecb, by_cpi)
    return _month_end(n // 12, n % 12 + 1)


def halloween_book(names: tuple[str, ...], start: date):
    def book(store: InputStore, cfg, forward_start: date, today: date) -> BookSeries:
        hw, em = _module("halloween"), _module("event_multi")
        end = store.minute_horizon(names, today)
        legs = {n: em.sessions(store.hourly(n, end), n, start, end) for n in names}
        targets = {}
        for n, s in legs.items():
            nxt = s.days[-1] + timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            ext = em.Sessions(s.name, s.exchange, s.days + (nxt,), np.r_[s.closes, s.closes[-1]],
                              np.r_[s.spreads, s.spreads[-1]])
            targets[n] = hw.target(ext)[:-1]
        res = em.book(legs, targets, {n: cost_model(cfg, n) for n in names}, forward_start, forward_start, end)
        return _from(res.days, res.daily, forward_start, end, {"sessions": {n: len(s.days) for n, s in legs.items()}})
    return book


def read_rows(raw_ecb=None, raw_cpi=None, raw_cot=None) -> dict[str, list]:
    """The issuers' parsed rows in the store's (date, area, value) form."""
    out = {}
    if raw_ecb is not None:
        out[ECB] = [(date.fromisoformat(d), c, v) for d, c, v in raw_ecb]
    if raw_cpi is not None:
        out[CPI] = [(date.fromisoformat(m + "-01"), a, v) for m, a, v in raw_cpi]
    if raw_cot is not None:
        out[COT] = [(date.fromisoformat(d), k, float(x)) for d, *xs in raw_cot for k, x in zip(COT_FIELDS, xs)]
    return out
