"""Synthetic tick markets with a known answer, for engine-level falsification (GAP-P12D-28).

Three kinds, generated deterministically from one `MarketSpec`:
  * null     — iid zero-mean increments. No edge exists: the pipeline must NOT pass it.
  * planted  — the same noise plus trending episodes of 1–4 hours, each with a constant drift
               of random sign. A trend-follower's edge: the pipeline MUST find it and pass it.
  * permuted — planted's increments, shuffled, then each given a random sign. Every |move| is
               kept and the episodes (the edge) are destroyed: the pipeline must NOT pass it.

The synthetic-lab law (ACIS-09 C-BT-12) binds this module. Its invariants:
  1. NOTHING IS DEMEANED. A demeaned path is a bridge, which mean-reverts by construction and
     pays a reversal rule (GAP-P12D-91). The nulls are martingales: zero drift in EXPECTATION,
     never pinned to zero in the sample.
  2. PRICES COMPOUND SIMPLE RETURNS. The increment r_k is the zero-mean draw and
     mid_k = mid_(k-1)·(1 + r_k), so E[mid_k − mid_(k-1) | the past] = 0: on the null and the
     permuted market every non-anticipating rule earns nothing in PRICE units, the units the
     harness books (GAP-P12D-117). exp-built prices would pay a long σ²/2 a unit time. The
     log-unit drift is then −σ²/2: a declared deviation, ~1e-5 a day at FX volatility, in units
     nothing grades. A return ≤ −1 is refused, never floored.
  3. PLANTED DIFFERS FROM NULL IN DRIFT ONLY. It shares the null's noise draw (common random
     numbers), its drift is set from the frictionless oracle's annual Sharpe (`oracle_sharpe`,
     the same at any tick size), and the sum is multiplied by one factor (`match_scale`) that makes
     its model variance over the decision horizon (`match_seconds`, default one weekday, as TREND
     decides) EQUAL the null's exactly (GAP-P12D-90). At the default strength the shorter
     horizons, down to one tick, sit 2-7% below the null's (measured; the old planted market was
     12.3x the null's DAILY variance), so volatility level cannot tell planted from null.
  4. ONE SCHEDULE. The episode schedule (`episodes`, `SyntheticMarket.episode_sign`) is the one
     source of the planted drift, and the oracle positive control (oracle.py, GAP-P12D-37) reads
     it. Every kind draws in the same RNG order (noise, then the schedule, then permuted's shuffle,
     then its signs), so null and permuted carry planted's schedule unapplied.
Ticks fall only on weekdays (Mon 00:00 – Fri 24:00 UTC; the loader applies its own weekend window).
`synthetic_spx` gives daily closes independent of every market, so the SPX gate is answerable.
"""

from __future__ import annotations

import bisect
import math
import random
from array import array
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterator, Sequence

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
    daily_vol: float = 0.005                   # σ of one weekday's move, as a fraction of the first mid
    oracle_sharpe: float = 10.0                # planted: the frictionless oracle's annual Sharpe
    match_seconds: int = 86400                 # planted: the decision horizon its variance matches at
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
        if self.oracle_sharpe < 0 or self.match_seconds <= 0 or self.match_seconds % self.tick_seconds:
            raise ValueError("oracle_sharpe must be >= 0 and match_seconds a positive multiple of tick_seconds")

    @property
    def end(self) -> datetime:
        return self.start + timedelta(days=self.days)

    @property
    def ticks_per_day(self) -> int:
        return 86400 // self.tick_seconds

    @property
    def drift_sigma(self) -> float:
        """The planted drift per step in step σ. The oracle holding the episode's sign earns it on
        every step, iid given the schedule, so its annual Sharpe is drift_sigma·√(252·ticks/day)."""
        return self.oracle_sharpe / math.sqrt(252 * self.ticks_per_day)

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


def horizon_mean_square(returns: Sequence[float], steps: int) -> float:
    """The mean square of the sums over consecutive whole blocks of `steps` returns (a partial
    tail block is dropped). Taken about ZERO, not the sample mean: the nulls are zero-mean by
    construction, and a planted path's net drift is part of its variance at that horizon."""
    blocks = len(returns) // steps
    if blocks == 0:
        raise ValueError(f"the path is shorter than one {steps}-step horizon")
    return math.fsum(math.fsum(returns[b * steps:(b + 1) * steps]) ** 2 for b in range(blocks)) / blocks


def planted_drift(spec: MarketSpec, schedule: Sequence[Episode]) -> list[float]:
    """The planted drift of every step: ±drift_sigma·σ, the sign of the episode in force."""
    step = spec.drift_sigma * spec.daily_vol / math.sqrt(spec.ticks_per_day)
    out = [0.0] * (spec.weekdays() * spec.ticks_per_day)
    for ep in schedule:
        out[ep.start:ep.end] = [ep.sign * step] * (ep.end - ep.start)
    return out


def match_scale(spec: MarketSpec, drift: Sequence[float]) -> float:
    """The ONE factor planted is multiplied by so its variance over the decision horizon equals the
    null's EXACTLY in the model: the noise contributes h·σ² per h-step block and the drift, which
    the schedule fixes, contributes its own block mean square D_h; the cross term has mean zero.
    So scale² · (h·σ² + D_h) = h·σ². Matching the SAMPLE's mean square instead would feed the
    sample's own noise into the scale: on a 21-day path it moved the tick-horizon ratio anywhere
    from 0.71 to 1.18 (measured 2026-09-29), a volatility confound of its own."""
    steps = spec.match_seconds // spec.tick_seconds
    noise = steps * spec.daily_vol ** 2 / spec.ticks_per_day
    return math.sqrt(noise / (noise + horizon_mean_square(drift, steps)))


def _returns(spec: MarketSpec, instrument_index: int) -> tuple[array, tuple[Episode, ...]]:
    """Increments as fractions of the first mid. null and planted share the noise (common random
    numbers); permuted shuffles exactly planted's increments, then flips each one's sign."""
    rng, noise, schedule = _draw(spec, instrument_index)
    if spec.kind == "null":
        return array("d", noise), schedule
    drift = planted_drift(spec, schedule)
    scale = match_scale(spec, drift)
    out = [scale * (e + m) for e, m in zip(noise, drift)]
    if spec.kind == "permuted":
        rng.shuffle(out)
        out = [r if rng.random() < 0.5 else -r for r in out]
    return array("d", out), schedule


class SyntheticMarket(TickSource):
    provenance = "synthetic"

    def __init__(self, spec: MarketSpec) -> None:
        self.spec = spec
        self.name = f"synthetic-{spec.kind}"
        self._index = {inst: i for i, (inst, _) in enumerate(spec.prices)}
        self._first = dict(spec.prices)
        self._returns: dict[str, array] = {}
        self._mid: dict[str, array] = {}
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

    def mids(self, instrument: str) -> array:
        """The mid path, one per weekday tick: each mid is the last times (1 + its simple return)."""
        if instrument not in self._mid:
            mid, path = self._first[instrument], array("d")
            for r in self.returns(instrument):
                if r <= -1.0:
                    raise ValueError(f"{instrument} draws a simple return <= -1: lower daily_vol")
                mid *= 1.0 + r
                path.append(mid)
            self._mid[instrument] = path
        return self._mid[instrument]

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        spec, path = self.spec, self.mids(instrument)
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
                    mid = path[base + i]
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
