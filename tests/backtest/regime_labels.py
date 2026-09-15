"""Offline regime labelling of historical bars for QIEA (ACIS-03 §5, ACIS-09 §5, GAP-P12D-18).

QIEA evolves on OHLC bars tagged with the regime NVMA reported. The labels come from
replaying the REAL NVMA over history, offline, at the §10 Loop-2 cadence, with the same
signal-bar aggregator AGON uses (GAP-0071: one time base).

Invariants:
  * No look-ahead: a bar is labelled with the regime of the instrument's latest
    classification BEFORE the tick that completed it (classified at most once per
    `cycle_s`, exactly as the replay loop does).
  * Labels do not depend on which params exist — `has_params_for` only vetoes
    tradeability, never the regime (nvma.py) — so the labeller passes "always" and one
    labelling serves every fold.
  * NVMA state is per instrument, so instrument-years are labelled independently. Each
    year first replays `LABEL_WARMUP` (never before the declared data start) so windows
    and session medians are warm, and keeps only bars that open inside the year.
  * The cache serves bars only under the exact labelling spec that wrote them (source,
    bar unit, cycle, the regime config); anything else raises. A year is committed by
    its meta file, written last.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

from config.schemas import AcisConfig
from core.data.bars import BarAggregator
from core.data.normaliser import MarketState
from core.optimizer.param_types import LabelledBar, RegimeLabelledHistory
from core.regime.nvma import NVMA, NVMAEngine
from core.regime.regime_types import RegimeType
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.tick_stream import build_factory, market_states

UTC = timezone.utc
LABEL_WARMUP = timedelta(days=3)
_FIELDS = ("ts", "open", "high", "low", "close", "spread", "regime")


class StaleLabelsError(Exception):
    """Cached labels are missing or were written under a different labelling spec."""


def build_nvma(cfg: AcisConfig, factory, logger) -> NVMAEngine:
    nvma = NVMA(cfg=cfg.system.regime, session_median=factory.session_median,
                tierg_shock=lambda instrument, ts: False,
                has_params_for=lambda regime: True)        # labels never depend on params
    return NVMAEngine(nvma, cfg.system.regime, logger)


def label_bars(states: Iterable[MarketState], engine, *, cycle_s: float,
               bar_seconds: int) -> Iterator[tuple[str, LabelledBar]]:
    aggregators: dict[str, BarAggregator] = {}
    classified_at: dict[str, datetime] = {}
    for st in states:
        bar = aggregators.setdefault(st.instrument, BarAggregator(bar_seconds)).add(
            st.timestamp, st.mid, st.spread)
        ctx = engine.regime_store.get(st.instrument)      # the regime BEFORE this tick
        if bar is not None and ctx is not None:
            yield st.instrument, LabelledBar(ts=bar.ts_open, open=bar.open, high=bar.high,
                                             low=bar.low, close=bar.close, spread=bar.spread,
                                             regime=ctx.regime)
        engine.observe(st)
        last = classified_at.get(st.instrument)
        if last is None or (st.timestamp - last).total_seconds() >= cycle_s:
            classified_at[st.instrument] = st.timestamp
            engine.classify(st)


LABELLER_VERSION = 1          # bump whenever NVMA or this labeller changes what a label is


@dataclass(frozen=True)
class LabelSpec:
    source: str
    bar_seconds: int
    cycle_s: float
    regime_config: str                                     # canonical JSON of cfg.system.regime
    inputs: str = ""          # canonical JSON of every other input that can change a label

    @classmethod
    def for_config(cls, cfg: AcisConfig, source: str, data_start: datetime) -> "LabelSpec":
        # GAP-P12D-24 (F-E6/F-I2): the factory settings (session medians, stale and velocity
        # windows) feed NVMA's vetoes; calendars and spread limits decide which ticks survive
        inputs = {"data": cfg.system.data.model_dump(mode="json"),
                  "calendars": {k: v.model_dump(mode="json") for k, v in cfg.instruments.calendars.items()},
                  "instruments": {s: [sp.calendar, sp.max_plausible_spread]
                                  for s, sp in cfg.instruments.instruments.items()},
                  "data_start": data_start.isoformat(), "macro_source": None,
                  "labeller_version": LABELLER_VERSION}
        return cls(source=source, bar_seconds=cfg.system.signals.signal_bar_seconds,
                   cycle_s=float(cfg.system.regime.cycle_seconds),
                   regime_config=json.dumps(cfg.system.regime.model_dump(mode="json"), sort_keys=True),
                   inputs=json.dumps(inputs, sort_keys=True))

    def key(self) -> str:
        blob = json.dumps({"source": self.source, "bar_seconds": self.bar_seconds,
                           "cycle_s": self.cycle_s, "regime": self.regime_config,
                           "inputs": self.inputs, "warmup_s": LABEL_WARMUP.total_seconds()},
                          sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()


class LabelledBarCache:
    def __init__(self, root: Path, spec: LabelSpec) -> None:
        self._root = Path(root)
        self._spec = spec

    def _csv(self, instrument: str, year: int) -> Path:
        return self._root / instrument / f"{year}.csv.gz"

    def _meta(self, instrument: str, year: int) -> Path:
        return self._root / instrument / f"{year}.meta.json"

    def has(self, instrument: str, year: int) -> bool:
        m = self._meta(instrument, year)
        return m.exists() and json.loads(m.read_text(encoding="utf-8")).get("key") == self._spec.key()

    def years(self, instrument: str) -> list[int]:
        folder = self._root / instrument
        found = (int(p.name.split(".")[0]) for p in folder.glob("*.meta.json")) if folder.exists() else ()
        return sorted(y for y in found if self.has(instrument, y))

    def write(self, instrument: str, year: int, bars: Iterable[LabelledBar]) -> int:
        folder = self._root / instrument
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".{year}.csv.gz.tmp"
        n = 0
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(_FIELDS)
            for b in bars:
                w.writerow((b.ts.isoformat(), repr(b.open), repr(b.high), repr(b.low),
                            repr(b.close), repr(b.spread), b.regime.value))
                n += 1
        self._meta(instrument, year).unlink(missing_ok=True)   # un-commit first (GAP-P12D-24 F-I3)
        os.replace(tmp, self._csv(instrument, year))
        meta_tmp = folder / f".{year}.meta.json.tmp"
        meta_tmp.write_text(json.dumps({"key": self._spec.key(), "bars": n,
                                        "written_utc": datetime.now(UTC).isoformat(timespec="seconds")}),
                            encoding="utf-8")
        os.replace(meta_tmp, self._meta(instrument, year))  # the commit
        return n

    def read(self, instrument: str, year: int) -> Iterator[LabelledBar]:
        if not self.has(instrument, year):
            raise StaleLabelsError(f"{instrument} {year}: no labels under the current spec — "
                                   "rebuild with scripts/build_labelled_bars.py")
        with gzip.open(self._csv(instrument, year), "rt", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                yield LabelledBar(ts=datetime.fromisoformat(row["ts"]), open=float(row["open"]),
                                  high=float(row["high"]), low=float(row["low"]),
                                  close=float(row["close"]), spread=float(row["spread"]),
                                  regime=RegimeType(row["regime"]))

    def history(self, instrument: str, regime: RegimeType, start: datetime, end: datetime,
                n: int) -> RegimeLabelledHistory:
        """The last `n` bars of `regime` that open at or after `start` and CLOSE by `end` (the
        fold's train window — no bar straddling the train end, nothing from the test window).
        Every year of the window must be cached, or it raises (GAP-P12D-24 F-I5)."""
        bar = timedelta(seconds=self._spec.bar_seconds)
        picked: list[LabelledBar] = []
        for year in range((end - timedelta(microseconds=1)).year, start.year - 1, -1):
            chunk = [b for b in self.read(instrument, year)
                     if b.regime is regime and start <= b.ts and b.ts + bar <= end]
            picked = chunk + picked
            if len(picked) >= n:
                break
        return RegimeLabelledHistory(instrument=instrument, bars=tuple(picked[-n:]),
                                     bar_seconds=self._spec.bar_seconds)


def label_instrument_year(*, cfg: AcisConfig, loader: BacktestDataLoader, source: str,
                          instrument: str, year: int, cache: LabelledBarCache, logger,
                          data_start: datetime) -> int:
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    factory = build_factory(cfg, [instrument])
    engine = build_nvma(cfg, factory, logger)
    states = market_states(cfg=cfg, loader=loader, factory=factory, source=source,
                           instruments=[instrument], start=max(start - LABEL_WARMUP, data_start),
                           end=end)
    bars = (b for _, b in label_bars(states, engine, cycle_s=cfg.system.regime.cycle_seconds,
                                     bar_seconds=cfg.system.signals.signal_bar_seconds)
            if b.ts >= start)
    return cache.write(instrument, year, bars)
