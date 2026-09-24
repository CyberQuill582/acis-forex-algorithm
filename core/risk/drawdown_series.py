"""The §9.5 drawdown series: every drawdown limit measured under its OWN semantics.
Split out of core/risk/guardrails.py (GAP-P12M-01), which re-exports these names.
  * One `_RuleAnchor` per rule key. Rules are never merged numerically, and two rules may
    never share a key (they would share one anchor, and one persisted record).
  * measured % = (anchor − basis) / denominator × 100, floored at 0. The denominator is
    the anchor, or the declared initial capital for a `limit_of: initial` rule.
  * static: the anchor is the declared initial capital, else the first observed basis,
    and never moves. trailing: the high-water mark since inception (seeded at the
    declared initial capital); it only ratchets up, never resets on a calendar boundary.
  * daily-reset: the engine's own limit (master §8; the day rolls at 17:00 New York) and
    a platform `daily` rule (GAP-P12D-54; at its own local `reset`). The engine's day
    anchors on its first observation (ratified). A platform day anchors its `reset_basis`
    on the LARGER of the last observation before the reset and the first after it: the
    firm reads its value AT the reset, and the engine keeps the stricter bracketing sample.
  * A restart is never a relaxation (GAP-0050, GAP-P12D-55): `export()` is persisted after
    every evaluate and `restore()` puts it back before the first one. A restored static or
    trailing anchor never sits below the declared capital; a restored daily anchor is kept
    for the same day, and a rollover missed while down brackets the downtime the same way
    (the larger of the last persisted and the first new observation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from config.schemas import DrawdownRule, GuardrailLimits
from core.data.errors import DataQualityError
from core.data.fx_clock import last_local, trading_day
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


def _value(kind: str, equity: float, balance: float) -> float:
    if kind == "equity":
        return equity
    return balance if kind == "balance" else max(equity, balance)    # "max"


@dataclass
class _RuleAnchor:
    """Running anchor for one drawdown rule (semantics in the module docstring).
    Every rule samples on EVERY observation (intraday): it can HALT earlier than a
    platform measuring only end-of-day, never later (stricter-of law, §9.5; true
    eod sampling is GAP-P9E-02). Halts are cheap, so erring strict is safe."""

    anchor: float | None = None
    day: str | None = None           # the reset instant / trading day (ISO) of the anchor
    last: float | None = None        # the captured value at the previous observation
    restored: bool = False           # put back from disk: a missed reset brackets the downtime

    def update(self, rule: DrawdownRule, basis: float, now: datetime, *,
               resets_daily: bool, capture: float | None = None,
               initial: float | None = None) -> float:
        value = basis if capture is None else capture
        if resets_daily:
            # the engine's day starts at the real 17:00 New York rollover (GAP-P9I-03,
            # GAP-P12D-10); a platform daily rule's at its own local reset (GAP-P12D-54)
            today = (last_local(now, rule.reset.zone, rule.reset.at) if rule.type == "daily"
                     else trading_day(now)).isoformat()
            if self.anchor is None or self.day != today:
                bracket = (rule.type == "daily" or self.restored) and self.last is not None
                self.anchor = max(value, self.last) if bracket else value
                self.day = today
            self.last = value
        else:
            if self.anchor is None:
                self.anchor = value if initial is None else initial   # inception reference
            if rule.type == "trailing":
                self.anchor = max(self.anchor, value)  # high-water since inception
        self.restored = False
        denominator = initial if rule.limit_of == "initial" else self.anchor
        if denominator is None or denominator <= 0:
            return 0.0
        return max(0.0, (self.anchor - basis) / denominator * 100.0)


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
    initial: float | None = None                             # the rulebook's declared capital
    _anchors: dict[str, _RuleAnchor] = field(default_factory=dict)

    def measure(self, *, equity: float, balance: float, now: datetime,
                start: float, halt: float) -> list[PlatformDrawdownState]:
        out: list[PlatformDrawdownState] = []
        for key, origin, rule, resets_daily in self.rules:
            capture = (_value(rule.reset_basis, equity, balance)
                       if rule.reset_basis is not None else None)
            measured = self._anchors.setdefault(key, _RuleAnchor()).update(
                rule, _value(rule.basis, equity, balance), now, resets_daily=resets_daily,
                capture=capture, initial=self.initial if origin == "platform" else None)
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
        for key, origin, _rule, resets_daily in self.rules:
            st = saved.get(key)
            anchor = None if st is None else _positive(key, "anchor", st.get("anchor"))
            if anchor is None:
                continue
            if not resets_daily and origin == "platform" and self.initial is not None:
                anchor = max(anchor, self.initial)     # never below the declared capital
            self._anchors[key] = _RuleAnchor(anchor=anchor, day=st.get("day"),
                                             last=_positive(key, "last", st.get("last")),
                                             restored=True)
            restored.append(key)
        return tuple(restored)


def build_drawdown_series(limits: GuardrailLimits, platform_rules: list[DrawdownRule],
                          account_name: str, *, initial_capital: float | None) -> DrawdownSeries:
    """The engine daily loss limit (resets at the FX rollover, master §8) + every
    platform rule under its own semantics: trailing ratchets, static is fixed, daily
    resets at its declared local instant. `initial_capital` is the rulebook's declared
    capital (None if undeclared). Per-instrument drawdown is handled separately."""
    rules: list[tuple[str, str, DrawdownRule, bool]] = [
        ("engine:daily", "engine",
         DrawdownRule(type="static", anchor="intraday", basis="equity",
                      limit_pct=limits.daily_drawdown_pct), True),
    ]
    for r in platform_rules:
        key = f"{account_name}:{r.type}:{r.anchor}:{r.basis}"
        if r.limit_of == "initial" and initial_capital is None:
            raise DataQualityError("initial_capital", None,
                                   f"{key} is sized on initial capital, which is undeclared")
        rules.append((key, "platform", r, r.type == "daily"))
    keys = [k for k, *_ in rules]
    if len(set(keys)) != len(keys):
        raise DataQualityError("drawdown_rules", keys, "two rules share a key (and an anchor)")
    return DrawdownSeries(limits=limits, rules=tuple(rules), initial=initial_capital)
