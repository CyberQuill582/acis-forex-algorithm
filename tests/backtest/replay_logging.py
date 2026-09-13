"""Replay-mode event logging (GAP-P12D-12).

Live, every NVMA veto and AGON discard is one JSONL line — right for an audit trail at
live tick rates. Replaying 14 years (~2.8 billion ticks) that way measured ~583 bytes per
tick, ≈1.6 TB. `ReplayEventLogger` stands in for `JsonlEventLogger` during a historical
replay: it COUNTS every event exactly, writes every event of the rare types in full, and
writes only the first `keep_per_type` lines of the high-volume per-tick types (a
representative sample). `close()` records the exact counts as one REPLAY_LOG_SUMMARY line.

The §10 C15 per-gate skip counters live in the layers themselves and are untouched, and
the graded record is the ValidationReport's trade list — neither depends on these lines.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# per-tick decision chatter: counted exactly, sampled in the log
SAMPLED_TYPES = frozenset({"VETO_APPLIED", "REGIME_SHIFT", "SIGNAL_EMITTED", "SIZED",
                           "MARGINAL_ALPHA_PINNED", "VOL_NORM_PINNED"})
SAMPLED_PREFIXES = ("DISCARD_",)


class ReplayEventLogger:
    """Same `event` / `close` interface as JsonlEventLogger; wraps a real one."""

    def __init__(self, inner, keep_per_type: int = 200) -> None:
        self._inner = inner
        self._keep = keep_per_type
        self.counts: Counter[str] = Counter()

    @staticmethod
    def sampled(event_type: str) -> bool:
        return event_type in SAMPLED_TYPES or event_type.startswith(SAMPLED_PREFIXES)

    def event(self, event_type: str, **data: Any) -> None:
        self.counts[event_type] += 1
        if not self.sampled(event_type) or self.counts[event_type] <= self._keep:
            self._inner.event(event_type, **data)

    def close(self) -> None:
        self._inner.event("REPLAY_LOG_SUMMARY", counts=dict(sorted(self.counts.items())),
                          keep_per_type=self._keep,
                          sampled_types=sorted(SAMPLED_TYPES) + [p + "*" for p in SAMPLED_PREFIXES])
        self._inner.close()
