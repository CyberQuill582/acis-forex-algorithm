"""Synthetic tick markets with a known answer, for engine-level falsification (GAP-P12D-28).

Three kinds, generated deterministically from one `MarketSpec`:
  * null     — iid zero-mean returns. No edge exists: the pipeline must NOT pass it.
  * planted  — the same noise plus trending episodes: for 1–4 hours at a time every step
               carries a drift of ±`drift_sigma`·σ. A trend-follower's edge: the pipeline
               MUST find it and pass it.
  * permuted — planted's returns, shuffled. Every move is kept and only their order changes,
               so the episodes (the edge) are destroyed: the pipeline must NOT pass it.
Every kind is demeaned, so no market carries net drift a buy-and-hold could harvest. Ticks
fall only on weekdays (Mon 00:00 – Fri 24:00 UTC; the loader applies its own weekend window).
`synthetic_spx` gives daily closes independent of every market, so the SPX gate is answerable.
"""

from __future__ import annotations

import math
import random
from array import array
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterator

from core.data.normaliser import RawTick
from tests.backtest.data_loader import TickSource

UTC = timezone.utc
KINDS = ("null", "planted", "permuted")


@dataclass(frozen=True)
class MarketSpec:
    kind: str
    start: datetime                            # a Monday, 00:00 UTC
    days: int
    prices: tuple[tuple[str, float], ...]      # (instrument, first mid)
    tick_seconds: int = 20
    daily_vol: float = 0.005                   # σ of one weekday's log return
    drift_sigma: float = 0.15                  # planted drift per step, in step σ
    episode_hours: tuple[float, float] = (1.0, 4.0)
    spread_frac: float = 0.00004
    seed: int = 7

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if self.start.utcoffset() != timedelta(0) or self.start.weekday() != 0 \
                or self.start != self.start.replace(hour=0, minute=0, second=0, microsecond=0):
            raise ValueError("start must be a Monday 00:00 UTC")
        if self.days <= 0 or self.tick_seconds <= 0 or 86400 % self.tick_seconds:
            raise ValueError("days must be positive and tick_seconds must divide a day")

    @property
    def end(self) -> datetime:
        return self.start + timedelta(days=self.days)

    @property
    def ticks_per_day(self) -> int:
        return 86400 // self.tick_seconds

    def weekdays(self) -> int:
        full, rest = divmod(self.days, 7)
        return full * 5 + min(rest, 5)


def _returns(spec: MarketSpec, instrument_index: int) -> array:
    # null and planted share the noise; permuted shuffles exactly planted's returns
    rng = random.Random(spec.seed * 1000 + instrument_index)
    n = spec.weekdays() * spec.ticks_per_day
    sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
    out = [rng.gauss(0.0, sigma) for _ in range(n)]
    if spec.kind != "null":
        lo, hi = (max(1, round(h * 3600 / spec.tick_seconds)) for h in spec.episode_hours)
        k = 0
        while k < n:
            length = rng.randint(lo, hi)
            drift = rng.choice((-1.0, 1.0)) * spec.drift_sigma * sigma
            for j in range(k, min(n, k + length)):
                out[j] += drift
            k += length
        if spec.kind == "permuted":
            rng.shuffle(out)
    mean = math.fsum(out) / n
    return array("d", (r - mean for r in out))


class SyntheticMarket(TickSource):
    def __init__(self, spec: MarketSpec) -> None:
        self.spec = spec
        self.name = f"synthetic-{spec.kind}"
        self._index = {inst: i for i, (inst, _) in enumerate(spec.prices)}
        self._first = dict(spec.prices)
        self._returns: dict[str, array] = {}
        self._log_mid: dict[str, array] = {}

    def returns(self, instrument: str) -> array:
        if instrument not in self._returns:                  # built on first use, per instrument
            self._returns[instrument] = _returns(self.spec, self._index[instrument])
        return self._returns[instrument]

    def _path(self, instrument: str) -> array:
        if instrument not in self._log_mid:
            acc, path = math.log(self._first[instrument]), array("d")
            for r in self.returns(instrument):
                acc += r
                path.append(acc)
            self._log_mid[instrument] = path
        return self._log_mid[instrument]

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        spec, log_mid = self.spec, self._path(instrument)
        tick = timedelta(seconds=spec.tick_seconds)
        lo, hi = max(start, spec.start), min(end, spec.end)
        day = spec.start + timedelta(days=(lo - spec.start).days)
        while day < hi:
            d = (day - spec.start).days
            if d % 7 < 5:
                base = (d // 7 * 5 + d % 7) * spec.ticks_per_day
                for i in range(max(0, math.ceil((lo - day) / tick)), spec.ticks_per_day):
                    t = day + i * tick
                    if t >= hi:
                        return
                    mid = math.exp(log_mid[base + i])
                    half = mid * spec.spread_frac / 2
                    yield RawTick(event_time=t, recv_time=t, instrument=instrument, bid=mid - half,
                                  ask=mid + half, volume=1.0, book=None, provider=self.name,
                                  raw_payload={})
            day += timedelta(days=1)


def synthetic_spx(start: datetime, days: int, seed: int = 11) -> dict[date, float]:
    """Business-day closes of a random walk seeded apart from every market."""
    rng, level, out = random.Random(seed), 2000.0, {}
    for k in range(days):
        d = (start + timedelta(days=k)).date()
        if d.weekday() < 5:
            level *= math.exp(rng.gauss(0.0, 0.01))
            out[d] = level
    return out
