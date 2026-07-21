"""Backtest tick loader with declared provenance (ACIS-09 §5, master §13 v2.9).

Backtest tick data comes from a DECLARED, reproducible source named in config —
never "whatever was lying around". Dukascopy is primary (institutional tick,
bid/ask); TrueFX is a cross-check validator (not primary). Ingested data passes
the SAME source-level §3 filtering as live ticks (NaN/inf/crossed/non-positive
rejection + weekend filtering, every reject logged), then flows into the real
`MarketStateFactory` in the harness — the engine's own validation is not bypassed.

The loader owns a cross-source sanity check: Dukascopy vs TrueFX drift on
overlapping windows ⇒ FLAG for investigation, never average silently (C-BT-9).

The concrete network download adapters (Dukascopy/TrueFX HTTP) are thin, deferred
to data-ops like the §7.5 feed transports; a `TickSource` is injected, so tests
use synthetic sources and an undeclared source name is REFUSED.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, Sequence

from core.data.normaliser import RawTick
from core.optimizer.costs import CostModel


class ProvenanceError(Exception):
    """An undeclared / unknown tick source (provenance is mandatory, §13)."""


class TickSource(ABC):
    """A declared, named historical tick source (Dukascopy, TrueFX, or a test
    synthetic). The real network adapters subclass this at data-ops time."""

    name: str

    @abstractmethod
    def load(self, instrument: str, start: datetime, end: datetime) -> Iterable[RawTick]:
        ...


@dataclass(frozen=True)
class DriftReport:
    instrument: str
    n_compared: int
    max_bps: float
    mean_bps: float
    threshold_bps: float
    flagged: bool          # True ⇒ investigate; the loader NEVER averages the two


@dataclass(frozen=True)
class LoadResult:
    instrument: str
    source: str
    ticks: tuple[RawTick, ...]
    rejected: int          # bad ticks dropped (logged)
    weekend_dropped: int


def _is_weekend(ts: datetime) -> bool:
    """Forex weekend closure (fx_default): Fri ≥22:00 UTC, all Saturday,
    Sun <22:00 UTC. A tick inside the closed window is dropped."""
    wd = ts.weekday()                    # Mon=0 … Sun=6
    if wd == 5:                          # Saturday
        return True
    if wd == 4 and ts.hour >= 22:        # Friday after 22:00
        return True
    if wd == 6 and ts.hour < 22:         # Sunday before 22:00
        return True
    return False


def _bad_tick(t: RawTick, max_spread: float | None) -> bool:
    if not (math.isfinite(t.bid) and math.isfinite(t.ask)):
        return True                      # NaN/inf
    if t.bid <= 0 or t.ask <= 0:
        return True                      # non-positive price
    if t.ask < t.bid:
        return True                      # crossed book
    if max_spread is not None and (t.ask - t.bid) > max_spread:
        return True                      # implausible spread (bad tick / spike)
    return False


class BacktestDataLoader:
    def __init__(self, sources: dict[str, TickSource], logger) -> None:
        # only these named sources are legal — an undeclared source is refused.
        self._sources = dict(sources)
        self._log = logger

    def load(self, *, source: str, instrument: str, start: datetime, end: datetime,
             max_plausible_spread: float | None = None) -> LoadResult:
        if source not in self._sources:
            raise ProvenanceError(
                f"undeclared tick source {source!r} — provenance is mandatory "
                f"(§13); declared: {sorted(self._sources)}")
        kept: list[RawTick] = []
        rejected = weekend = 0
        for t in self._sources[source].load(instrument, start, end):
            if _is_weekend(t.event_time):
                weekend += 1
                continue
            if _bad_tick(t, max_plausible_spread):
                rejected += 1
                self._log.event("BACKTEST_BAD_TICK", source=source,
                                instrument=instrument, ts=t.event_time.isoformat(),
                                bid=t.bid, ask=t.ask)
                continue
            kept.append(t)
        self._log.event("BACKTEST_LOAD", source=source, instrument=instrument,
                        kept=len(kept), rejected=rejected, weekend_dropped=weekend)
        return LoadResult(instrument=instrument, source=source, ticks=tuple(kept),
                          rejected=rejected, weekend_dropped=weekend)

    def cross_source_drift(self, *, instrument: str, primary: Sequence[RawTick],
                           secondary: Sequence[RawTick], threshold_bps: float,
                           align_tol_s: float = 1.0) -> DriftReport:
        """Compare primary vs cross-check mids on overlapping timestamps. A drift
        beyond `threshold_bps` FLAGS the window for investigation — the loader
        never averages the two sources (C-BT-9). Alignment is nearest-in-time
        within `align_tol_s`."""
        sec = sorted(secondary, key=lambda t: t.event_time)
        diffs_bps: list[float] = []
        for p in primary:
            match = _nearest(sec, p.event_time, align_tol_s)
            if match is None:
                continue
            mp = (p.bid + p.ask) / 2.0
            ms = (match.bid + match.ask) / 2.0
            if mp > 0:
                diffs_bps.append(abs(mp - ms) / mp * 1e4)
        if not diffs_bps:
            report = DriftReport(instrument, 0, 0.0, 0.0, threshold_bps, False)
        else:
            mx = max(diffs_bps)
            report = DriftReport(instrument, len(diffs_bps), mx,
                                 sum(diffs_bps) / len(diffs_bps), threshold_bps,
                                 mx > threshold_bps)
        if report.flagged:
            self._log.event("BACKTEST_SOURCE_DRIFT", instrument=instrument,
                            max_bps=round(report.max_bps, 3),
                            mean_bps=round(report.mean_bps, 3),
                            threshold_bps=threshold_bps)
        return report


def _nearest(sorted_ticks: Sequence[RawTick], ts: datetime,
             tol_s: float) -> RawTick | None:
    best = None
    best_gap = tol_s
    for t in sorted_ticks:
        gap = abs((t.event_time - ts).total_seconds())
        if gap <= best_gap:
            best, best_gap = t, gap
    return best


def calibrate_cost_model(*, observed_spreads: Sequence[float],
                         commission_per_side: float = 0.0,
                         slippage_fraction_of_spread: float = 0.25) -> CostModel:
    """OANDA practice-feed spread calibration of the C8 cost model (§13/v2.9): a
    per-side slippage estimate as a fraction of the median observed spread, so
    backtest friction matches the venue ACIS will paper/live on. Returns the
    SAME `CostModel` (ACIS-03 §5) the optimizer/execution use — one cost model."""
    spreads = [s for s in observed_spreads if math.isfinite(s) and s >= 0]
    median = (sorted(spreads)[len(spreads) // 2] if spreads else 0.0)
    return CostModel(commission_per_side=commission_per_side,
                     slippage_per_side=median * slippage_fraction_of_spread)


def batched(items: Iterable[RawTick], size: int) -> Iterator[list[RawTick]]:
    """GAP-0067: yield ticks in batches so the ≥2-yr ingest commits per batch
    (transaction batching), never per row."""
    if size <= 0:
        raise ValueError("batch size must be positive")
    batch: list[RawTick] = []
    for t in items:
        batch.append(t)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
