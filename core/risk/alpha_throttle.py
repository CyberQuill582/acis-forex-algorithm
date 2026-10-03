"""The alpha-decay throttle's edge to the Governor (ACIS-07 §7, GAP-0050, GAP-P12D-145).

Mental model:
  * `AlphaDecayDetector` is pure state (armed or not); this unit turns its transitions into the
    explicit `apply_risk_state(alpha_decay=…)` call over the single upward `HaltSink`, logged.
  * Set on the rising edge; cleared on a confirmed recovery (GAP-0050) or by the one human
    resume (GAP-P12D-145, owner rulings "Human resume clears it" and "Fresh evidence only"):
    after a human clear the detector judges only trades closed after the resume, so the verdict
    on the trades that armed it cannot re-arm it at the next evaluation.
  * A restart restores an armed throttle before the first evaluation: never a relaxation.
"""

from __future__ import annotations

from core.risk.alpha_decay import AlphaDecayDetector, AlphaDecayReading
from core.risk.risk_types import Trade
from core.risk.sink import HaltSink


class AlphaThrottle:
    def __init__(self, detector: AlphaDecayDetector, sink: HaltSink, logger) -> None:
        self._det = detector
        self._sink = sink
        self._log = logger
        self._prev = False

    @property
    def armed(self) -> bool:
        return self._det.armed

    def update(self, trades: list[Trade]) -> AlphaDecayReading:
        reading = self._det.evaluate(trades)
        if reading.flag and not self._prev:
            self._log.event("ALPHA_DECAY_DETECTED", s_recent=reading.mean_sigma_recent,
                            s_baseline=reading.mean_sigma_baseline, n=reading.n_recent)
            self._sink.apply_risk_state(alpha_decay=True)
        elif not reading.flag and self._prev:
            self._log.event("ALPHA_DECAY_RECOVERED", s_recent=reading.mean_sigma_recent,
                            s_baseline=reading.mean_sigma_baseline)
            self._sink.apply_risk_state(alpha_decay=False)
        self._prev = reading.flag
        return reading

    def restore(self, armed: bool) -> None:
        self._det.restore_armed(armed)
        self._prev = armed
        if armed:
            self._sink.apply_risk_state(alpha_decay=True)
            self._log.event("ALPHA_DECAY_RESTORED", armed=True)

    def clear_by_human(self, trades: list[Trade]) -> None:
        """Only the human resume calls this (the token is checked by the caller first)."""
        if not self._det.armed:
            return
        self._det.clear_by_human(len(trades))
        self._prev = False
        self._log.event("ALPHA_DECAY_CLEARED_BY_HUMAN", trades=len(trades))
        self._sink.apply_risk_state(alpha_decay=False)
