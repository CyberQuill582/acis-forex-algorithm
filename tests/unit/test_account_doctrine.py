"""Stricter-of composition (SPEC §9.5, ACIS-10 C-EVT-5)."""

from __future__ import annotations

from config.account_doctrine import compose, rulebook_hash


def test_personal_account_uses_ratified_engine_taper(acis_config) -> None:
    doctrine = compose(acis_config.guardrails, acis_config.platform_rules.accounts["dev_paper"])
    assert doctrine.taper_start_fraction == 0.60
    assert doctrine.entry_halt_fraction == 0.80
    assert doctrine.news.restricted is False


def test_prop_account_stricter_taper_wins(acis_config) -> None:
    doctrine = compose(acis_config.guardrails, acis_config.platform_rules.accounts["prop_demo"])
    assert doctrine.taper_start_fraction == 0.50   # account is stricter than the floor
    assert doctrine.entry_halt_fraction == 0.70
    assert doctrine.min_hold_seconds == 60
    assert doctrine.weekend_holding_allowed is False
    assert doctrine.consistency_max_day_profit_pct == 40.0


def test_rulebook_hash_is_deterministic_and_account_specific(acis_config) -> None:
    # SPEC v2.7 attestation: the harness acknowledges THIS rulebook, provably.
    accounts = acis_config.platform_rules.accounts
    h1 = rulebook_hash(accounts["dev_paper"])
    assert h1 == rulebook_hash(accounts["dev_paper"])          # deterministic
    assert h1 != rulebook_hash(accounts["prop_demo"])          # rule-sensitive
    assert len(h1) == 64


def test_constraint_set_is_engine_union_platform_never_merged(acis_config) -> None:
    doctrine = compose(acis_config.guardrails, acis_config.platform_rules.accounts["prop_demo"])
    origins = [c.origin for c in doctrine.drawdown_constraints]
    assert origins.count("engine") == 2      # daily + per-instrument, ACIS semantics
    assert origins.count("platform") == 2    # trailing-intraday-equity + static-eod-balance
    platform = [c.rule for c in doctrine.drawdown_constraints if c.origin == "platform"]
    # Semantics preserved verbatim — the trailing intraday rule is not approximated:
    assert any(r.type == "trailing" and r.anchor == "intraday" and r.basis == "equity"
               for r in platform)
