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

The episode schedule (`episodes`, `SyntheticMarket.episode_sign`) is the ONE source of the
planted drift: `_returns` applies exactly that schedule, and the oracle positive control
(oracle.py, GAP-P12D-37) reads it. Every kind draws it in the same RNG order (noise, then the
schedule, then permuted's shuffle), so null and permuted carry planted's schedule unapplied.
"""

from __future__ import annotations

import bisect
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


@dataclass(frozen=True)
class Episode:
    start: int          # first weekday-tick return index the drift applies to
    end: int            # exclusive
    sign: float         # +1.0 or -1.0: the drift's direction


def _draw(spec: MarketSpec, instrument_index: int) -> tuple[random.Random, list[float], tuple[Episode, ...]]:
    """Noise first, then the episode schedule, from ONE generator. The order is load-bearing:
    null and planted share the noise, permuted shuffles planted's returns with the generator
    left here, and every recorded synthetic run was drawn in this order."""
    rng = random.Random(spec.seed * 1000 + instrument_index)
    n = spec.weekdays() * spec.ticks_per_day
    sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
    noise = [rng.gauss(0.0, sigma) for _ in range(n)]
    lo, hi = (max(1, round(h * 3600 / spec.tick_seconds)) for h in spec.episode_hours)
    schedule, k = [], 0
    while k < n:
        length = rng.randint(lo, hi)
        schedule.append(Episode(k, min(n, k + length), rng.choice((-1.0, 1.0))))
        k += length
    return rng, noise, tuple(schedule)


def episodes(spec: MarketSpec, instrument_index: int) -> tuple[Episode, ...]:
    """The planted schedule of one instrument. Every kind has it; only planted applies it."""
    return _draw(spec, instrument_index)[2]


def _returns(spec: MarketSpec, instrument_index: int) -> tuple[array, tuple[Episode, ...]]:
    # null and planted share the noise; permuted shuffles exactly planted's returns
    rng, out, schedule = _draw(spec, instrument_index)
    n = len(out)
    if spec.kind != "null":
        sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
        for ep in schedule:
            drift = ep.sign * spec.drift_sigma * sigma
            for j in range(ep.start, ep.end):
                out[j] += drift
        if spec.kind == "permuted":
            rng.shuffle(out)
    mean = math.fsum(out) / n
    return array("d", (r - mean for r in out)), schedule


class SyntheticMarket(TickSource):
    provenance = "synthetic"

    def __init__(self, spec: MarketSpec) -> None:
        self.spec = spec
        self.name = f"synthetic-{spec.kind}"
        self._index = {inst: i for i, (inst, _) in enumerate(spec.prices)}
        self._first = dict(spec.prices)
        self._returns: dict[str, array] = {}
        self._log_mid: dict[str, array] = {}
        self._schedule: dict[str, tuple[Episode, ...]] = {}
        self._starts: dict[str, list[int]] = {}

    def index_of(self, ts: datetime) -> int:
        """The weekday-tick return index of the tick at `ts` — `load`'s own arithmetic."""
        spec = self.spec
        d = (ts - spec.start).days
        offset = (ts - (spec.start + timedelta(days=d))).total_seconds()
        if d < 0 or d % 7 >= 5 or offset % spec.tick_seconds:
            raise ValueError(f"{ts.isoformat()} is not a weekday tick of this market")
        return (d // 7 * 5 + d % 7) * spec.ticks_per_day + int(offset) // spec.tick_seconds

    def episode_at(self, instrument: str, ts: datetime) -> Episode:
        """The planted episode containing the return that produced the tick at `ts`: the state IN
        FORCE now, never the next one (no foresight of a change). On null and permuted the same
        schedule exists but moves no price."""
        self.returns(instrument)                             # the schedule comes with the returns
        k = bisect.bisect_right(self._starts[instrument], self.index_of(ts)) - 1
        return self._schedule[instrument][k]

    def episode_sign(self, instrument: str, ts: datetime) -> float:
        return self.episode_at(instrument, ts).sign

    def returns(self, instrument: str) -> array:
        if instrument not in self._returns:                  # built on first use, per instrument
            ret, schedule = _returns(self.spec, self._index[instrument])
            self._returns[instrument], self._schedule[instrument] = ret, schedule
            self._starts[instrument] = [ep.start for ep in schedule]
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
