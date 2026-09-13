"""Fast point lookups into Dukascopy day files for the data-validation checks (GAP-P12D-14).

The checks ask many small questions of each UTC day — "the mid at 13:15:00", "the median
spread in the five minutes after the rollover", "how many ticks between 21:00 and 22:00".
`DayTicks` decompresses one `.bi5` day file ONCE, keeps the raw 20-byte records and a
sorted list of their millisecond offsets, and answers each question by binary search —
no per-tick Python objects for the ~100,000 ticks of a busy day. The same point scale and
plausibility envelope as `bi5.decode` apply, so a wrong scale still fails loudly.
"""

from __future__ import annotations

import bisect
import lzma
import struct
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tests.backtest.bi5 import PLAUSIBLE, RECORD, SYMBOLS, Bi5Error

UTC = timezone.utc
_MS_ONLY = struct.Struct(">I16x")                  # the ms offset of each 20-byte record
_ASK_BID = struct.Struct(">4xII8x")                # ask, bid integers of one record


def day_path(root: Path, instrument: str, day: date) -> Path:
    """The official-S3-layout path of one UTC day (month ZERO-based)."""
    return Path(root) / instrument / str(day.year) / f"{day.month - 1:02d}" / f"{day.day:02d}_ticks.bi5"


class DayTicks:
    """One instrument's ticks for one UTC day, decompressed once, queried by instant."""

    def __init__(self, root: Path, instrument: str, day: date) -> None:
        self.instrument, self.day = instrument, day
        self.start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        self._scale = SYMBOLS[instrument][1]
        self._lo, self._hi = PLAUSIBLE[instrument]
        p = day_path(root, instrument, day)
        raw = p.read_bytes() if p.exists() else b""
        try:
            self._data = lzma.decompress(raw, format=lzma.FORMAT_ALONE) if raw else b""
        except lzma.LZMAError as e:
            raise Bi5Error(f"{instrument} {day}: bad LZMA stream: {e}") from e
        if len(self._data) % RECORD.size:
            raise Bi5Error(f"{instrument} {day}: torn record ({len(self._data)} bytes)")
        self.ms = [m for (m,) in _MS_ONLY.iter_unpack(self._data)]

    def __len__(self) -> int:
        return len(self.ms)

    def _ms(self, t: datetime) -> int:
        return int((t - self.start) / timedelta(milliseconds=1))

    def quote(self, i: int) -> tuple[float, float]:
        """(bid, ask) of record `i`, scaled and bounds-checked."""
        ask_i, bid_i = _ASK_BID.unpack_from(self._data, i * RECORD.size)
        bid, ask = bid_i / self._scale, ask_i / self._scale
        if not (self._lo <= bid <= self._hi and self._lo <= ask <= self._hi):
            raise Bi5Error(f"{self.instrument} {self.day}: price {bid}/{ask} outside "
                           f"{self._lo}–{self._hi} — wrong point scale?")
        return bid, ask

    def last_at_or_before(self, t: datetime, max_age_s: float) -> tuple[float, float] | None:
        """(bid, ask) of the latest tick at or before `t`, if no older than `max_age_s`."""
        ms = self._ms(t)
        k = bisect.bisect_right(self.ms, ms) - 1
        if k < 0 or ms - self.ms[k] > max_age_s * 1000:
            return None
        return self.quote(k)

    def index_range(self, t0: datetime, t1: datetime) -> range:
        """Record indices with t0 <= tick time < t1."""
        return range(bisect.bisect_left(self.ms, self._ms(t0)), bisect.bisect_left(self.ms, self._ms(t1)))

    def count(self, t0: datetime, t1: datetime) -> int:
        return len(self.index_range(t0, t1))

    def spreads(self, t0: datetime, t1: datetime) -> list[float]:
        """ask − bid of every tick in [t0, t1), in price units."""
        return [a - b for b, a in (self.quote(i) for i in self.index_range(t0, t1))]
