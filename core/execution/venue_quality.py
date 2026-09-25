"""Per-(venue, instrument) rolling execution quality (ACIS-06 §5). Moved out of
core/execution/venue.py (legibility budget, GAP-P12M-01). Invariant: fed only by this
layer's own FillReports (internal feedback, never upstream); the score is deterministic
and monotone — a higher fill rate raises it, adverse slippage and rejects lower it.
"""

from __future__ import annotations

from core.execution.venue import FillReport, FillStatus


class VenueQuality:
    """Per-(venue, instrument) rolling execution quality (ACIS-06 §5). Fed by
    this layer's own FillReports — internal feedback, never upstream. Score is
    deterministic and monotone: higher fill rate raises it, adverse slippage
    and rejects lower it."""

    def __init__(self, window: int = 50) -> None:
        self._window = window
        self._records: dict[tuple[str, str], list[tuple[bool, float]]] = {}

    def update(self, report: FillReport) -> None:
        key = (report.venue, report.instrument)
        rows = self._records.setdefault(key, [])
        rejected = report.status in (FillStatus.REJECTED, FillStatus.CANCELLED)
        rows.append((not rejected, 0.0 if rejected else report.slippage_bps))
        if len(rows) > self._window:
            del rows[0]

    def score(self, venue: str, instrument: str) -> float:
        rows = self._records.get((venue, instrument))
        if not rows:
            return 0.5                       # unknown venue: neutral prior
        fill_rate = sum(1 for ok, _ in rows if ok) / len(rows)
        fills = [s for ok, s in rows if ok]
        avg_adverse = max(0.0, sum(fills) / len(fills)) if fills else 0.0
        return fill_rate / (1.0 + avg_adverse / 10.0)
