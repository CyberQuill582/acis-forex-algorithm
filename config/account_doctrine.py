"""Account doctrine composition (SPEC §9.5, ACIS-10 C-EVT-5).

Pure config-level stricter-of composition: ACIS's own guardrails and the
account's rulebook become one EffectiveDoctrine. Platform drawdown rules are
carried under their OWN declared measurement semantics — never merged
numerically with engine limits (the Risk Monitor evaluates each series
its own way, phase 9). Composition can only ever ADD constraints.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from config.schemas import AccountRulebook, DrawdownRule, GuardrailLimits, NewsRules


def rulebook_hash(rulebook: AccountRulebook) -> str:
    """Content hash of the active rulebook (SPEC v2.7, §9.5/§12): exposed on
    acis://account/rules and acknowledged before live mode — the harness's
    attestation that it KNOWS the platform's rules, news restrictions included."""
    canonical = json.dumps(rulebook.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def guardrail_hash(limits: GuardrailLimits) -> str:
    """Content hash of the hard guardrail limits (SPEC §12/§8, ACIS-08 §5):
    exposed on acis://config/guardrails and acknowledged (together with the
    rulebook hash) before live mode — the human attests to the EXACT limits in
    force. Same canonicalisation as rulebook_hash; guard-integrity law means
    this is READ ONLY here — no code path writes guardrail_limits.yaml."""
    canonical = json.dumps(limits.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TaggedDrawdownRule:
    origin: str  # "engine" | "platform"
    rule: DrawdownRule


@dataclass(frozen=True)
class EffectiveDoctrine:
    taper_start_fraction: float
    entry_halt_fraction: float
    news: NewsRules
    min_hold_seconds: int
    max_lots: float | None
    weekend_holding_allowed: bool
    drawdown_constraints: tuple[TaggedDrawdownRule, ...]
    consistency_max_day_profit_pct: float | None
    min_trading_days: int | None


def compose(guardrails: GuardrailLimits, rulebook: AccountRulebook) -> EffectiveDoctrine:
    """Stricter-of law: the effective limit set is engine ∪ platform, and the
    taper acts at the earlier (smaller) fraction. Looser-than-ratified values
    are already unrepresentable at the schema (GAP-0010 floor)."""
    engine_rules = (
        TaggedDrawdownRule(
            "engine",
            DrawdownRule(type="static", anchor="intraday", basis="equity",
                         limit_pct=guardrails.daily_drawdown_pct),
        ),
        TaggedDrawdownRule(
            "engine",
            DrawdownRule(type="static", anchor="intraday", basis="equity",
                         limit_pct=guardrails.per_instrument_drawdown_pct),
        ),
    )
    platform_rules = tuple(TaggedDrawdownRule("platform", r) for r in rulebook.drawdown_rules)
    return EffectiveDoctrine(
        taper_start_fraction=min(
            guardrails.taper_start_fraction,
            rulebook.taper_start_fraction or guardrails.taper_start_fraction,
        ),
        entry_halt_fraction=min(
            guardrails.entry_halt_fraction,
            rulebook.entry_halt_fraction or guardrails.entry_halt_fraction,
        ),
        news=rulebook.news,
        min_hold_seconds=rulebook.min_hold_seconds,
        max_lots=rulebook.max_lots,
        weekend_holding_allowed=rulebook.weekend_holding_allowed,
        drawdown_constraints=engine_rules + platform_rules,
        consistency_max_day_profit_pct=rulebook.consistency_max_day_profit_pct,
        min_trading_days=rulebook.min_trading_days,
    )
