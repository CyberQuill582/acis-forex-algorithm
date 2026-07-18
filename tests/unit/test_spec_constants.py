"""Spec↔config drift gates (owner-ratified 2026-07-17, surface-area reduction).

The load-bearing numeric contracts stated in `ACIS_SPEC.md` prose must equal the
values the engine actually runs on (real YAML through the real loader) and the
schema bounds that enforce their stricter-only ratified floors. A contradiction
between the master spec and config/schema is a RED TEST here, not something an
auditor has to notice across 100KB of prose.

Each extraction is anchored to the exact ratified sentence. If an anchor stops
matching, the test fails loudly: a deliberate spec rewording must consciously
re-anchor here (and a value change must be human-ratified per the guard-integrity
law — this test cites, never sets, guardrail semantics).
"""

from __future__ import annotations

import re
from pathlib import Path

import annotated_types

from config.schemas import GuardrailLimits

_ROOT = Path(__file__).resolve().parent.parent.parent
_MASTER = (_ROOT / "ACIS_SPEC.md").read_text(encoding="utf-8")
_ACIS04 = (_ROOT / "specs" / "ACIS-04-ALPHA_ARENA.md").read_text(encoding="utf-8")


def _extract(pattern: str, text: str = _MASTER, source: str = "ACIS_SPEC.md") -> float:
    m = re.search(pattern, text)
    assert m, (
        f"spec anchor {pattern!r} not found in {source} — if the wording changed "
        f"deliberately, re-anchor this test consciously (never delete the check)"
    )
    return float(m.group(1))


def _schema_bound(field: str, kind: type, attr: str) -> float:
    for meta in GuardrailLimits.model_fields[field].metadata:
        if isinstance(meta, kind):
            return float(getattr(meta, attr))
    raise AssertionError(f"GuardrailLimits.{field} lost its {attr} bound")


def test_halt_limits_match_master_spec(acis_config) -> None:
    g = acis_config.guardrails
    assert g.daily_drawdown_pct == _extract(r"daily_drawdown (\d+\.\d+)%")
    assert g.per_instrument_drawdown_pct == _extract(r"per-instrument drawdown (\d+\.\d+)%")
    assert g.alpha_decay_sharpe_mult == _extract(r"Sharpe threshold (\d+\.\d+)× baseline")
    assert g.var_cap_pct == _extract(r"VaR cap (\d+\.\d+)% NAV")
    assert g.cluster_cap_pct == _extract(r"cluster cap (\d+)%")
    assert g.slippage_alert_bps == _extract(r"slippage alert (\d+\.\d+) bps")


def test_prelimit_taper_matches_ratified_floor(acis_config) -> None:
    spec_start = _extract(r"`taper_start_fraction` \(default \*\*(0\.\d+)")
    spec_halt = _extract(r"`entry_halt_fraction` \(default (0\.\d+)")
    g = acis_config.guardrails
    assert g.taper_start_fraction == spec_start
    assert g.entry_halt_fraction == spec_halt
    # stricter-only: the schema ceiling IS the ratified floor
    assert _schema_bound("taper_start_fraction", annotated_types.Le, "le") == spec_start
    assert _schema_bound("entry_halt_fraction", annotated_types.Le, "le") == spec_halt


def test_single_currency_delta_cap_matches_master(acis_config) -> None:
    spec_cap = _extract(r"single-currency delta > (\d+)%")
    assert acis_config.guardrails.single_currency_delta_cap_pct == spec_cap
    assert _schema_bound("single_currency_delta_cap_pct", annotated_types.Le, "le") == spec_cap


def test_conviction_discard_matches_c4(acis_config) -> None:
    spec_floor = _extract(r"< (0\.\d+) discard test")
    assert acis_config.system.signals.conviction_discard == spec_floor


def test_medium_vol_discount_matches_c4(acis_config) -> None:
    spec_discount = _extract(r"MEDIUM-volatility ×(0\.\d+) uncertainty discount")
    assert acis_config.system.signals.medium_vol_discount == spec_discount


def test_regime_veto_thresholds_match_master(acis_config) -> None:
    r = acis_config.system.regime
    assert r.confidence_veto == _extract(r"confidence < (0\.\d+); spread")
    assert r.spread_veto_mult == _extract(r"spread > (\d+)× session median")
    assert r.velocity_veto_mult == _extract(r"tick velocity < (0\.\d+)× session median")


def test_hurst_meanrev_matches_v212_ratified_value(acis_config) -> None:
    spec_h = _extract(r"`hurst_meanrev` \(re-derived (0\.\d+)\)")
    assert acis_config.system.regime.hurst_meanrev == spec_h


def test_alpha_decay_recovery_matches_master_spec(acis_config) -> None:
    # master §8: "restore only after confirmed recovery (20 trades with Sharpe
    # > 0.8× baseline)" — the GAP-0050 clear contract, now in the risk config.
    r = acis_config.system.risk
    assert r.alpha_decay_recovery_trades == _extract(
        r"confirmed recovery \((\d+) trades with Sharpe")
    assert r.alpha_decay_recovery_mult == _extract(
        r"Sharpe > (0\.\d+)× baseline\)")
    # the baseline-validity minimum (C5) and the fire minimum (§8)
    assert r.alpha_decay_min_trades == _extract(r"minimum (\d+) trades → flag")


def test_decision_budget_matches_acis04(acis_config) -> None:
    spec_ms = _extract(
        r"`fast_loop_decision_budget_ms = (\d+)`", _ACIS04, "specs/ACIS-04-ALPHA_ARENA.md"
    )
    assert acis_config.system.signals.fast_loop_decision_budget_ms == spec_ms
