"""The Governor's entry guards and the halt state they read (ACIS-05 §7 step 1, §7 step 8), moved out of
capital_governor.py (legibility budget, GAP-P12M-01) so the signal path and the target-position path
(ACIS-05 v1.7 §6.4: "an increase is an ENTRY and meets every entry gate") run ONE set of guards.

Invariants:
  * `check` returns the FIRST zero-reason in §7.1's order, or None; it never sizes anything.
  * Halts are scoped ("all" or an instrument) and lift only through the Governor's one human
    `resume` (§7 step 8), which calls `clear`. The session drawdown halt alone auto-clears, at
    the next session boundary (master §8); reaching the daily-drawdown limit sets it.
  * Guards gate ENTRIES only. A reduction never passes through here, so no guard can block it.
  * `target=True` (the daily target path only): no regime check applies (`regime` is None). The
    target path's data check is its own feed watch (core/runtime/feed_check.py, master v2.33);
    every other guard applies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from core.governor.calendar_gates import next_boundary, within_closure_buffer
from core.governor.portfolio_types import PortfolioState
from core.regime.regime_types import LiqState, RegimeContext
from core.signals.signal_types import StrategyType


class EntryGuards:
    def __init__(self, *, limits, rules, cfg, confidence_veto: float, boundaries, closure,
                 scalp_horizon_s: int, blackout: Callable[[str, datetime], bool], logger) -> None:
        self._limits, self._rules, self._cfg = limits, rules, cfg
        self._confidence_veto, self._boundaries, self._closure = confidence_veto, boundaries, closure
        self._scalp_horizon_s, self._blackout, self._log = scalp_horizon_s, blackout, logger
        self.halts: dict[str, str] = {}               # scope ("all" | instrument) -> reason
        self.session_halt_until: datetime | None = None

    def halt_session(self, now: datetime) -> datetime:
        """Set or extend (never shorten) the session halt to the next boundary; return its end."""
        until = next_boundary(now, self._boundaries)
        if self.session_halt_until is None or until > self.session_halt_until:
            self.session_halt_until = until
        return until

    def clear(self) -> None:
        self.halts.clear()
        self.session_halt_until = None

    def check(self, instrument: str, portfolio: PortfolioState, regime: RegimeContext | None, now: datetime, *,
              expires_at: datetime | None = None, strategy: StrategyType | None = None,
              target: bool = False) -> str | None:
        """§7.1 in order. Returns the zero-reason or None."""
        if expires_at is not None and now >= expires_at:
            return "expired"
        if not target and not regime.tradeable:
            return "veto"
        if "all" in self.halts or instrument in self.halts:
            return "halt"
        if self.session_halt_until is not None:
            if now < self.session_halt_until:
                return "drawdown_halt"
            self.session_halt_until = None        # auto-clears at the boundary (master §8)
        if portfolio.daily_drawdown_pct >= self._limits.daily_drawdown_pct:
            self.session_halt_until = next_boundary(now, self._boundaries)
            self._log.event("HALT_APPLIED", scope="session", reason="daily_drawdown_limit")
            return "drawdown_halt"
        if not target and regime.confidence < self._confidence_veto:
            return "low_confidence"
        if not target and regime.liquidity_state is LiqState.ILLIQUID:
            return "illiquid"
        if portfolio.stale:
            self._log.event("PORTFOLIO_STALE", as_of=portfolio.as_of.isoformat())
            return "portfolio_stale"
        if self._rules.news.restricted and self._blackout(instrument, now):
            self._log.event("BLACKOUT_OVERRIDE_ENFORCED",     # v2.7 carry-forward
                            instrument=instrument, account=self._rules.platform)
            return "blackout"
        if within_closure_buffer(now, *self._closure,             # EVERY account and every
                                 self._cfg.weekend_entry_buffer_s):  # closure (P12D-58, X5)
            return "weekend_ban"
        if (self._cfg.scalp_min_hold_conflict and strategy is StrategyType.MOMENTUM_SCALP
                and self._rules.min_hold_seconds > self._scalp_horizon_s):
            return "min_hold_conflict"
        return None
