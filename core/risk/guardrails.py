"""Guardrail checks + the stop authority (ACIS-07 §6/§7).

The equity breaker, platform-measured drawdown series (§9.5, each rule under
its OWN semantics — core/risk/drawdown_series.py), the ratified pre-limit taper
(min across limits), Tier-G flatten (GAP-0011), racing-HALT coalescing (C-RSK-4),
and human-only-resume scope. Limits are read-only (guard-integrity law); nothing
here writes config. A restart restores the series' anchors and the last taper
before the first check (`restore_state`, GAP-P12D-55): a restart is never a
relaxation (GAP-0050).

The upward edge is the injected `HaltSink` — issuance is idempotent and
serialized so two conditions firing "simultaneously" resolve to one halt state,
most-severe scope winning (global flatten > session halt > instrument halt).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from config.schemas import GuardrailLimits, RiskConfig
from core.risk.drawdown_series import (DrawdownSeries, _RuleAnchor,  # noqa: F401 (re-export)
                                       build_drawdown_series, taper_factor)
from core.risk.risk_types import PlatformDrawdownState
from core.risk.sink import HaltSink


@dataclass
class GuardrailContext:
    now: datetime
    equity: Decimal
    balance: Decimal
    nav: Decimal
    per_instrument_drawdown_pct: dict[str, float]   # instrument -> loss % NAV
    var_pct: float
    max_cluster_pct: float
    slippage_slope_bps: float
    tierg_flatten: dict[str, tuple[str, tuple[str, ...]]]  # instrument -> (class, sources)


@dataclass
class GuardrailOutcome:
    platform_drawdown: tuple[PlatformDrawdownState, ...]
    taper_factor: float
    instruments_halted: tuple[str, ...]
    equity_floor_breached: bool
    slippage_slope_alert: bool


class Guardrails:
    def __init__(self, limits: GuardrailLimits, cfg: RiskConfig,
                 series: DrawdownSeries, sink: HaltSink, logger, *,
                 taper_start: float, entry_halt: float) -> None:
        self._limits = limits
        self._cfg = cfg
        self._series = series
        self._sink = sink
        self._log = logger
        self._start = taper_start
        self._halt = entry_halt
        self._halted_scopes: set[str] = set()  # {"all","session",<instrument>}
        self._flattened_scopes: set[str] = set()
        self._instruments_halted: set[str] = set()
        self._session_halted = False
        self._equity_flattened = False
        self._last_taper: float | None = None

    # -- re-arm on human resume (GAP-P9I-06) --------------------------------- #

    def rearm(self) -> None:
        """A human resume clears the Governor's halts; the Risk layer must drop
        its idempotency latches too, or a later re-breach (a NEW equity-floor
        hit, a fresh drawdown) would be silently suppressed as 'already issued'.
        The equity breaker is a one-shot PER ARMED CYCLE, never for the process
        lifetime. Only a human resume calls this (never any agent path)."""
        self._halted_scopes.clear()
        self._flattened_scopes.clear()
        self._instruments_halted.clear()
        self._session_halted = False
        self._equity_flattened = False
        self._log.event("GUARDRAILS_REARMED")

    # -- restart: restore before the first check (GAP-P12D-55 / GAP-0050) --- #

    @property
    def series(self) -> DrawdownSeries:
        return self._series

    def restore_state(self, *, anchors: Mapping[str, Mapping],
                      taper_factor: float | None) -> None:
        """Put the persisted drawdown anchors back and RE-PUSH the last delivered
        taper to the (fresh) Governor, before the first check. Restore-only: it can
        put back a restriction the dead process had; it cannot loosen one."""
        restored = self._series.restore(anchors)
        self._log.event("ANCHORS_RESTORED", rule_keys=list(restored),
                        ignored=sorted(set(anchors) - set(restored)))
        if taper_factor is not None:
            self._sink.apply_risk_state(taper_factor=taper_factor)
            self._last_taper = taper_factor
            self._log.event("TAPER_RESTORED", factor=taper_factor)

    # -- racing-HALT coalescing (C-RSK-4) ------------------------------------ #
    # Idempotent + serialized: a scope already covered by an equal-or-more-severe
    # active halt is a no-op. Severity: instrument < session < all < flatten.

    def _covered(self, scope: str) -> bool:
        if "all" in self._flattened_scopes:
            return True
        if "all" in self._halted_scopes and scope != "all":
            return True
        if scope in self._flattened_scopes:
            return True
        return scope in self._halted_scopes

    def _issue_halt(self, scope: str, reason: str) -> None:
        if self._covered(scope):
            return
        self._halted_scopes.add(scope)
        self._sink.apply_halt(scope, reason)
        if scope not in ("all", "session"):
            self._instruments_halted.add(scope)

    def _issue_session_halt(self, now: datetime, reason: str) -> None:
        if "all" in self._flattened_scopes or "all" in self._halted_scopes \
                or self._session_halted:
            return
        self._session_halted = True
        self._sink.apply_session_halt(now, reason)

    def _issue_flatten(self, scope: str, reason: str) -> None:
        if scope in self._flattened_scopes or "all" in self._flattened_scopes:
            return
        self._flattened_scopes.add(scope)
        self._sink.flatten(scope, reason)
        if scope != "all":
            self._instruments_halted.add(scope)

    # -- the evaluation ------------------------------------------------------ #

    def check(self, ctx: GuardrailContext) -> GuardrailOutcome:
        equity_breached = ctx.equity < Decimal(str(self._limits.equity_floor_usd))

        # 1. Equity breaker — highest, unthrottleable, human-only resume. Spec
        #    §7: flatten THEN global HALT (both are distinct wiring actions —
        #    flatten closes via execution, HALT blocks new entries). One-shot
        #    (idempotent via `_equity_flattened`); both mark the scope covered so
        #    every later halt/flatten coalesces under them.
        if equity_breached and not self._equity_flattened:
            self._equity_flattened = True
            self._log.event("EQUITY_FLOOR_BREACH", equity=str(ctx.equity),
                            floor=self._limits.equity_floor_usd)
            self._sink.flatten("all", "equity_floor")
            self._sink.apply_halt("all", "equity_floor")
            self._flattened_scopes.add("all")
            self._halted_scopes.add("all")

        # 2. Platform + engine drawdown series, each under its own semantics.
        states = self._series.measure(
            equity=float(ctx.equity), balance=float(ctx.balance), now=ctx.now,
            start=self._start, halt=self._halt)
        taper_candidates = [s.taper_factor for s in states]
        for s in states:
            if s.distance_fraction >= 1.0:
                self._log.event("PLATFORM_DD_BREACH", rule_key=s.rule_key,
                                measured=s.measured_pct, limit=s.limit_pct)
                if s.rule_key == "engine:daily":
                    # master §8: session-scoped, auto-clears at the next boundary
                    self._issue_session_halt(ctx.now, "daily_drawdown")
                else:
                    # a platform limit at 1.0 HALTs like an engine limit (§9.5)
                    self._issue_halt("all", f"platform_dd:{s.rule_key}")

        # 3. Per-instrument drawdown → scoped HALT + taper candidate.
        for inst, dd in ctx.per_instrument_drawdown_pct.items():
            limit = self._limits.per_instrument_drawdown_pct
            distance = dd / limit if limit > 0 else 0.0
            taper_candidates.append(taper_factor(distance, self._start, self._halt))
            if distance >= 1.0:
                self._log.event("PLATFORM_DD_BREACH", rule_key=f"instrument:{inst}",
                                measured=dd, limit=limit)
                self._issue_halt(inst, "per_instrument_drawdown")

        # 4. VaR / cluster caps.
        if ctx.var_pct > self._limits.var_cap_pct:
            self._log.event("VAR_BREACH", var_pct=ctx.var_pct,
                            cap=self._limits.var_cap_pct)
            self._issue_halt("all", "var_cap")
        if ctx.max_cluster_pct > self._limits.cluster_cap_pct:
            self._log.event("CLUSTER_BREACH", cluster_pct=ctx.max_cluster_pct,
                            cap=self._limits.cluster_cap_pct)
            self._issue_halt("all", "cluster_cap")

        # 5. Tier-G flatten (GAP-0011): condition already confirmed by ACIS-10.
        for inst, (cls, sources) in ctx.tierg_flatten.items():
            self._log.event("TIERG_FLATTEN", taxonomy_class=cls,
                            instrument=inst, sources=list(sources))
            self._issue_flatten(inst, "tierg_flatten")

        # 6. Slippage alert (F10 alert-only — no auto-throttle knob, GAP-0004).
        slip_alert = ctx.slippage_slope_bps > self._limits.slippage_alert_bps
        if slip_alert:
            self._log.event("SLIPPAGE_ALERT", bps=ctx.slippage_slope_bps,
                            limit=self._limits.slippage_alert_bps)

        # 7. Deliver the min-across-limits taper over the upward edge (only on
        #    change — every change names the binding limit).
        taper = min(taper_candidates) if taper_candidates else 1.0
        if self._last_taper is None or abs(taper - self._last_taper) > 1e-12:
            binding = self._binding_rule(states, ctx.per_instrument_drawdown_pct, taper)
            self._log.event("TAPER_UPDATED", rule_key=binding, factor=taper)
            self._sink.apply_risk_state(taper_factor=taper)
            self._last_taper = taper

        return GuardrailOutcome(
            platform_drawdown=tuple(states),
            taper_factor=taper,
            instruments_halted=tuple(sorted(self._instruments_halted)),
            equity_floor_breached=equity_breached,
            slippage_slope_alert=slip_alert)

    def _binding_rule(self, states, per_instrument, taper) -> str:
        for s in states:
            if abs(s.taper_factor - taper) <= 1e-12:
                return s.rule_key
        for inst, dd in per_instrument.items():
            limit = self._limits.per_instrument_drawdown_pct
            if abs(taper_factor(dd / limit if limit > 0 else 0.0,
                                self._start, self._halt) - taper) <= 1e-12:
                return f"instrument:{inst}"
        return "none"

    @property
    def instruments_halted(self) -> tuple[str, ...]:
        return tuple(sorted(self._instruments_halted))
