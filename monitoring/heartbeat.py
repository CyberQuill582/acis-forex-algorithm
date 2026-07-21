"""Heartbeat / missed-beat monitor (ACIS-08 §8, C-MCP-6, master §12).

Loops heartbeat into `acis://status`; **3 missed fast-loop beats WITH open
positions → the orchestrator should call `acis_flatten`.** The server REPORTS
the missed-beat state and surfaces the flatten RECOMMENDATION; it does not
itself flatten (the orchestrator's call — the safety asymmetry) and it never
forges a beat: the last-beat timestamp is read from the §8.6 heartbeat file the
Risk Monitor writes (ACIS-12), injected here as a getter.

Stale-but-FLAT is an alert only (nothing to flatten), matching the watchdog's
`stale_but_flat` semantics — halts/flattens are for open exposure.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass(frozen=True)
class HeartbeatState:
    last_beat: str | None
    age_s: float | None
    missed_beats: int
    open_positions: int
    healthy: bool
    flatten_recommended: bool
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


class HeartbeatMonitor:
    def __init__(self, *, heartbeat_fast_s: float, missed_beats_flatten: int) -> None:
        if heartbeat_fast_s <= 0:
            raise ValueError("heartbeat_fast_s must be > 0")
        self._interval = float(heartbeat_fast_s)
        self._threshold = int(missed_beats_flatten)

    def state(self, *, last_beat: datetime | None, now: datetime,
              open_positions: int) -> HeartbeatState:
        """Compute the missed-beat picture. `last_beat` None (never synced) is
        treated as maximally stale — unknown never degrades to 'healthy'."""
        if last_beat is None:
            missed = self._threshold                 # unknown ⇒ assume breached
            return HeartbeatState(
                last_beat=None, age_s=None, missed_beats=missed,
                open_positions=open_positions, healthy=False,
                flatten_recommended=open_positions > 0,
                reason="never_synced" if open_positions == 0
                else "never_synced_with_positions")
        age = (now - last_beat).total_seconds()
        missed = int(age // self._interval) if age > 0 else 0
        breached = missed >= self._threshold
        healthy = not breached
        if not breached:
            reason = "healthy"
        elif open_positions > 0:
            reason = "missed_beats_with_positions"
        else:
            reason = "missed_beats_but_flat"          # alert only, nothing to flatten
        return HeartbeatState(
            last_beat=last_beat.isoformat(), age_s=age, missed_beats=missed,
            open_positions=open_positions, healthy=healthy,
            flatten_recommended=breached and open_positions > 0, reason=reason)
