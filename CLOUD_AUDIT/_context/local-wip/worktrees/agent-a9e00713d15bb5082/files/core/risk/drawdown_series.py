"""The §9.5 drawdown series: every drawdown limit measured under its OWN semantics.

Split out of core/risk/guardrails.py (legibility budget, GAP-P12M-01), which re-exports
these names. Mental model — the invariants a change here must keep:

  * One `_RuleAnchor` per rule key. Rules are never merged numerically, and two rules may
    never share a key (they would share one anchor, and one persisted record).
  * measured % = (anchor − basis) / anchor × 100, floored at 0.
  * static: the anchor is the first observed basis, and it never moves. trailing: the
    high-water mark since inception; it only ratchets up and never resets on a calendar
    boundary (GAP-P9E-01).
  * daily-reset (the engine's own limit, master §8): the day rolls at the real 17:00
    New York rollover and the new day anchors on its first observation (ratified).
  * A restart is never a relaxation (GAP-0050, GAP-P12D-55). `export()` is persisted after
    every evaluate and `restore()` puts it back before the first one, so a restarted engine
    measures from the same anchors as the one that died. A restored daily anchor is kept
    for the same day. If a day boundary passed while the engine was down, the new day
    anchors on the LARGER of the last persisted observation and the first new one: the
    engine did not watch the rollover, so it keeps the stricter of the two samples that
    bracket it, and a loss taken while it was down is never forgotten by the restart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from config.schemas import DrawdownRule, GuardrailLimits
from core.data.errors import DataQualityError
from core.data.fx_clock import trading_day
from core.risk.risk_types import PlatformDrawdownState


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
    """Running anchor for one drawdown rule (semantics in the module docstring).

    v1 samples the basis on EVERY observation (intraday) for all rules — the
    risk-conservative choice: it can HALT earlier than a platform that measures
    only end-of-day, never later (stricter-of law, §9.5). True eod-only sampling
    is recorded as GAP-P9E-02. Halts are cheap (CLAUDE.md), so erring strict is safe."""

    anchor: float | None = None
    day: str | None = None           # the trading day (ISO) the daily anchor belongs to
    last: float | None = None        # the basis at the previous observation
    restored: bool = False           # put back from disk: a missed rollover brackets the downtime

    def update(self, rule: DrawdownRule, basis: float, now: datetime, *,
               resets_daily: bool) -> float:
        if resets_daily:
            # GAP-P9I-03: the daily limit's day starts at the FX rollover, NOT calendar
            # midnight; the rollover is the real 17:00 New York instant (GAP-P12D-10).
            today = trading_day(now).isoformat()
            if self.anchor is None or self.day != today:
                bracket = self.restored and self.last is not None
                self.anchor = max(basis, self.last) if bracket else basis   # day-open
                self.day = today
            self.last = basis
        else:
            if self.anchor is None:
                self.anchor = basis                   # inception reference
            if rule.type == "trailing":
                self.anchor = max(self.anchor, basis)  # high-water since inception
        self.restored = False
        if self.anchor <= 0:
            return 0.0
        return max(0.0, (self.anchor - basis) / self.anchor * 100.0)


def _positive(key: str, name: str, raw) -> float | None:
    if raw is None:
        return None
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise DataQualityError(f"{key}.{name}", raw, "a persisted anchor must be finite > 0")
    return value


@dataclass
class DrawdownSeries:
    """Account-level drawdown rules measured from broker account state, each
    under its own semantics (§9.5). Never merged numerically with one another —
    each keeps its own key and taper."""

    limits: GuardrailLimits
    rules: tuple[tuple[str, str, DrawdownRule, bool], ...]  # (key, origin, rule, resets_daily)
    _anchors: dict[str, _RuleAnchor] = field(default_factory=dict)

    def measure(self, *, equity: float, balance: float, now: datetime,
                start: float, halt: float) -> list[PlatformDrawdownState]:
        out: list[PlatformDrawdownState] = []
        for key, _origin, rule, resets_daily in self.rules:
            basis = equity if rule.basis == "equity" else balance
            anchor = self._anchors.setdefault(key, _RuleAnchor())
            measured = anchor.update(rule, basis, now, resets_daily=resets_daily)
            distance = measured / rule.limit_pct if rule.limit_pct > 0 else 0.0
            out.append(PlatformDrawdownState(
                rule_key=key, measured_pct=measured, limit_pct=rule.limit_pct,
                distance_fraction=distance,
                taper_factor=taper_factor(distance, start, halt)))
        return out

    def export(self) -> dict[str, dict]:
        """Every live anchor, JSON-ready, for the restrictive-state store."""
        return {k: {"anchor": a.anchor, "day": a.day, "last": a.last}
                for k, a in self._anchors.items() if a.anchor is not None}

    def restore(self, saved: Mapping[str, Mapping]) -> tuple[str, ...]:
        """Put persisted anchors back BEFORE the first measure (GAP-P12D-55). A key the
        rulebook no longer declares is not restored. Returns the restored keys."""
        restored = []
        for key, _origin, _rule, _resets_daily in self.rules:
            st = saved.get(key)
            anchor = None if st is None else _positive(key, "anchor", st.get("anchor"))
            if anchor is None:
                continue
            self._anchors[key] = _RuleAnchor(anchor=anchor, day=st.get("day"),
                                             last=_positive(key, "last", st.get("last")),
                                             restored=True)
            restored.append(key)
        return tuple(restored)


def build_drawdown_series(limits: GuardrailLimits,
                          platform_rules: list[DrawdownRule],
                          account_name: str) -> DrawdownSeries:
    """The engine daily loss limit (resets at the FX trading-day rollover,
    master §8) + every platform rule under its own semantics (trailing
    ratchets, static is a fixed inception reference — neither resets daily).
    Per-instrument drawdown is handled separately (it needs per-instrument
    PnL, not account state)."""
    rules: list[tuple[str, str, DrawdownRule, bool]] = [
        ("engine:daily", "engine",
         DrawdownRule(type="static", anchor="intraday", basis="equity",
                      limit_pct=limits.daily_drawdown_pct), True),
    ]
    for r in platform_rules:
        key = f"{account_name}:{r.type}:{r.anchor}:{r.basis}"
        rules.append((key, "platform", r, False))     # platform rules never reset daily
    keys = [k for k, *_ in rules]
    if len(set(keys)) != len(keys):
        raise DataQualityError("drawdown_rules", keys, "two rules share a key (and an anchor)")
    return DrawdownSeries(limits=limits, rules=tuple(rules))
