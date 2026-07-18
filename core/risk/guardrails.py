"""Guardrail checks + the stop authority (ACIS-07 §6/§7).

The equity breaker, platform-measured drawdown series (§9.5, each rule under
its OWN semantics), the ratified pre-limit taper (min across limits), Tier-G
flatten (GAP-0011), racing-HALT coalescing (C-RSK-4), and human-only-resume
scope. Limits are read-only (guard-integrity law); nothing here writes config.

The upward edge is the injected `HaltSink` — issuance is idempotent and
serialized so two conditions firing "simultaneously" resolve to one halt state,
most-severe scope winning (global flatten > session halt > instrument halt).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from config.schemas import DrawdownRule, GuardrailLimits, RiskConfig
from core.risk.risk_types import PlatformDrawdownState
from core.risk.sink import HaltSink


def taper_factor(distance: float, start: float, halt: float) -> float:
    """§9.5 piecewise taper on d = measured/limit: 1.0 at/below `start`, linear
    to 0.0 at `halt`, 0.0 beyond. Hand-vectors (start .60, halt .80):
    d=.60→1.0, d=.70→0.5, d=.80→0.0."""
    if distance <= start:
        return 1.0
    if distance >= halt:
        return 0.0
    return (halt - distance) / (halt - start)


@dataclass
class _RuleAnchor:
    """Running anchor for one drawdown rule under its declared semantics."""

    anchor: float | None = None
    period_id: object | None = None

    def _period(self, rule: DrawdownRule, now: datetime) -> object:
        # intraday resets each UTC trading day; eod anchors to the day too — the
        # discriminator the §14 fixture proves is trailing (high-water) vs
        # static (period-open), not the reset cadence.
        return now.astimezone(timezone.utc).date()

    def update(self, rule: DrawdownRule, basis: float, now: datetime) -> float:
        pid = self._period(rule, now)
        if self.period_id != pid or self.anchor is None:
            self.period_id = pid
            self.anchor = basis                       # period open
        if rule.type == "trailing":
            self.anchor = max(self.anchor, basis)     # high-water (C-RSK-8)
        # static: anchor stays the period-open value
        if self.anchor <= 0:
            return 0.0
        return max(0.0, (self.anchor - basis) / self.anchor * 100.0)


@dataclass
class DrawdownSeries:
    """Account-level drawdown rules measured from broker account state, each
    under its own semantics (§9.5). Never merged numerically with one another —
    each keeps its own key and taper."""

    limits: GuardrailLimits
    rules: tuple[tuple[str, str, DrawdownRule], ...]  # (key, origin, rule)
    _anchors: dict[str, _RuleAnchor] = field(default_factory=dict)

    def measure(self, *, equity: float, balance: float, now: datetime,
                start: float, halt: float) -> list[PlatformDrawdownState]:
        out: list[PlatformDrawdownState] = []
        for key, _origin, rule in self.rules:
            basis = equity if rule.basis == "equity" else balance
            anchor = self._anchors.setdefault(key, _RuleAnchor())
            measured = anchor.update(rule, basis, now)
            distance = measured / rule.limit_pct if rule.limit_pct > 0 else 0.0
            out.append(PlatformDrawdownState(
                rule_key=key, measured_pct=measured, limit_pct=rule.limit_pct,
                distance_fraction=distance,
                taper_factor=taper_factor(distance, start, halt)))
        return out


def build_drawdown_series(limits: GuardrailLimits,
                          platform_rules: list[DrawdownRule],
                          account_name: str) -> DrawdownSeries:
    """The engine daily limit (static/intraday/equity) + every platform rule,
    each with a stable rule_key. Per-instrument drawdown is handled separately
    (it needs per-instrument PnL, not account state)."""
    rules: list[tuple[str, str, DrawdownRule]] = [
        ("engine:daily", "engine",
         DrawdownRule(type="static", anchor="intraday", basis="equity",
                      limit_pct=limits.daily_drawdown_pct)),
    ]
    for r in platform_rules:
        key = f"{account_name}:{r.type}:{r.anchor}:{r.basis}"
        rules.append((key, "platform", r))
    return DrawdownSeries(limits=limits, rules=tuple(rules))


# scope severity for racing-HALT coalescing (C-RSK-4)
_SEVERITY = {"instrument": 1, "session": 2, "all": 3, "flatten": 4}


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
