"""The daily lab as a harness tick source (R1.1 C-4/C-5/C-6/C-7). It plugs the lab into the SAME
harness, cost model, financing model and clock as every other source (R1-C §2.7), so the lab
can never grade with a second model of any of them.

Mental model:
  * TICKS. `LabTickSource.load` yields each FX day's published quotes (lab_intraday), mid =
    the previous close · (1 + the running sum of the day's increments), bid/ask = mid ∓ spread/2.
    The day's last mid is the daily close, so the tick tape and the daily bars are one path.
  * TRUTH (C-5). `truth(instrument, ts)` is planted's drift in force on ts's FX day: fixed at
    the day's open, never the next day's, and the SAME on every kind (null and permuted carry it
    unapplied), so an oracle reading its sign trades the same days everywhere and only planted
    pays it. `detection_power` (lab_theory) states the power in VOLATILITY units, i.e. for P&L
    sized by the true sigma; a fixed-notional grade in price units earns ~10% less.
  * FINANCING (C-6). `rate_table` hands the lab's own rate differentials to the harness's
    RateTable / make_financing, and the lab's accrual uses the harness's rollover calendar, so a
    financed long on the null earns nothing but the broker fee. With `financing=False` the rates
    are zero and a carry cannot be planted.
  * COSTS (C-7). `lab_config` is a TEST-ONLY config: each lab instrument copies a declared
    instrument's spec (its C8 costs and max_plausible_spread included), every real instrument
    is disabled, and nothing is written to config/instruments.yaml.
"""

from __future__ import annotations

import bisect
from datetime import datetime
from typing import Iterator, Sequence

import numpy as np

from config.schemas import AcisConfig
from core.data.normaliser import RawTick
from tests.backtest.data_loader import TickSource
from tests.backtest.financing import RateTable
from tests.backtest.lab_intraday import DayTicks, day_bounds, intraday
from tests.backtest.lab_market import LabPath

QUOTE = "USD"                  # every lab instrument is quoted in a currency whose rate is zero
LAB_SWAP_CONVENTION = "tom_next"   # lab_market's accrual calendar: carry.swap_multiplier's default
_KEEP_DAYS = 4                 # intraday days cached: the harness streams one instrument at a time


def lab_names(n: int) -> tuple[str, ...]:
    """L00_USD, L01_USD, ...: one base currency per instrument, so each owns its rate series."""
    return tuple(f"L{i:02d}_{QUOTE}" for i in range(n))


class LabTickSource(TickSource):
    provenance = "synthetic"

    def __init__(self, path: LabPath, names: Sequence[str] | None = None,
                 first_mids: Sequence[float] | float = 1.0, tick_seconds: int = 60, **intraday_kw) -> None:
        names = tuple(names or lab_names(path.r.shape[1]))
        if len(names) != path.r.shape[1] or len(set(names)) != len(names):
            raise ValueError("one distinct name per lab instrument")
        self.path, self.name = path, f"lab-{path.kind}"
        self._index = {n: i for i, n in enumerate(names)}
        self._first = np.broadcast_to(np.asarray(first_mids, float), (len(names),))
        self._close = path.mids(self._first)
        self._opens = [day_bounds(d.astype(object))[0] for d in path.dates]
        self._tick_seconds, self._kw = tick_seconds, intraday_kw
        self._days: dict[int, DayTicks] = {}

    def _day(self, t: int) -> DayTicks:
        if t not in self._days:
            if len(self._days) >= _KEEP_DAYS:
                self._days.pop(next(iter(self._days)))
            self._days[t] = intraday(self.path, t, self._tick_seconds, **self._kw)
        return self._days[t]

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        i = self._index[instrument]
        for t in range(max(0, bisect.bisect_right(self._opens, start) - 1), len(self._opens)):
            if self._opens[t] >= end:
                return
            day = self._day(t)
            prev = self._first[i] if t == 0 else self._close[t - 1, i]
            mids = prev * (1.0 + np.cumsum(day.inc[i]))
            for k in np.flatnonzero(day.emit[i]):
                ts = day.time(int(k))
                if ts < start:
                    continue
                if ts >= end:
                    return
                half = mids[k] * day.spread[i, k] / 2.0
                yield RawTick(event_time=ts, recv_time=ts, instrument=instrument,
                              bid=float(mids[k] - half), ask=float(mids[k] + half), volume=1.0,
                              book=None, provider=self.name, raw_payload={})

    def truth(self, instrument: str, ts: datetime) -> float:
        """Planted's drift (vol units) in force on ts's FX day, whatever the path's kind."""
        t = bisect.bisect_right(self._opens, ts) - 1
        if t < 0 or ts >= day_bounds(self.path.dates[t].astype(object))[1]:
            raise ValueError(f"{ts.isoformat()} is not inside a lab trading day")
        return float(self.path.truth[t, self._index[instrument]])

    def rate_table(self) -> RateTable:
        """C-6: each instrument's base currency carries its rate differential (% p.a.), the
        quote currency carries zero, so make_financing(table) books exactly the lab's accrual."""
        days = [d.astype(object) for d in self.path.dates]
        series = {name.split("_")[0]: list(zip(days, (100.0 * self.path.rate[:, i]).tolist()))
                  for name, i in self._index.items()}
        series[QUOTE] = [(d, 0.0) for d in days]
        return RateTable(series)


def lab_config(cfg: AcisConfig, names: Sequence[str], template: str = "EUR_USD") -> AcisConfig:
    """C-7: a test-only config whose enabled instruments are exactly the lab's, each a copy of
    `template`'s declared spec (C8 costs, max_plausible_spread, calendar). The swap convention is
    the LAB's (`tom_next`, the calendar its accrual uses), never the template's: one financing
    calendar (audit E-R11-06)."""
    spec = cfg.instruments.instruments[template]
    lab = {n: spec.model_copy(update={"enabled": True, "base_ccy": n.split("_")[0], "quote_ccy": QUOTE,
                                      "swap_convention": LAB_SWAP_CONVENTION})
           for n in names}
    real = {s: sp.model_copy(update={"enabled": False}) for s, sp in cfg.instruments.instruments.items()}
    return cfg.model_copy(update={"instruments": cfg.instruments.model_copy(
        update={"instruments": {**real, **lab}})})
