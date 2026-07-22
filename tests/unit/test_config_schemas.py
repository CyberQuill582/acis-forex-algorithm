"""Config schema gates (SPEC §9): a bad config refuses to start — provably."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from config.schemas import CautionMultiplier, ConfigError, load_config

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _mutated_config(tmp_path: Path, filename: str, mutate) -> Path:
    dst = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, dst)
    path = dst / filename
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return dst


def test_dev_config_loads(acis_config) -> None:
    assert acis_config.system.active_account in acis_config.platform_rules.accounts
    assert "EUR_USD" in acis_config.instruments.enabled
    assert acis_config.guardrails.entry_halt_fraction == 0.80


def test_missing_equity_floor_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(tmp_path, "guardrail_limits.yaml", lambda d: d.pop("equity_floor_usd"))
    with pytest.raises(ConfigError):
        load_config(cfg)


@pytest.mark.parametrize("field,value", [("taper_start_fraction", 0.70), ("entry_halt_fraction", 0.90)])
def test_taper_looser_than_ratified_floor_rejected(tmp_path: Path, field: str, value: float) -> None:
    cfg = _mutated_config(tmp_path, "guardrail_limits.yaml", lambda d: d.__setitem__(field, value))
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_taper_order_enforced(tmp_path: Path) -> None:
    def mutate(d):
        d["taper_start_fraction"] = 0.5
        d["entry_halt_fraction"] = 0.4
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "guardrail_limits.yaml", mutate))


def test_cluster_unknown_symbol_is_config_error(tmp_path: Path) -> None:
    cfg = _mutated_config(
        tmp_path, "instruments.yaml", lambda d: d["clusters"]["commodity"].append("NO_SUCH")
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_cluster_disabled_extension_reference_is_fine(acis_config) -> None:
    # C7: XAU_USD is declared-but-disabled; the commodity cluster references it — inert, not an error.
    assert "XAU_USD" in acis_config.instruments.clusters["commodity"]
    assert "XAU_USD" not in acis_config.instruments.enabled


def test_incomplete_contract_metadata_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(
        tmp_path, "instruments.yaml", lambda d: d["instruments"]["EUR_USD"].pop("tick_value")
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_active_account_without_rulebook_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(
        tmp_path, "system_config.yaml", lambda d: d.__setitem__("active_account", "ghost")
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_boundary_diverging_from_fx_calendar_is_fatal(tmp_path: Path) -> None:
    # GAP-0025: the C1 staging list and the session-tagging windows may not
    # silently diverge — a boundary matching no fx session edge is fatal.
    cfg = _mutated_config(
        tmp_path, "system_config.yaml",
        lambda d: d.__setitem__("session_boundaries_utc", ["22:00", "03:00"]),
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_fx_session_start_missing_from_boundaries_is_fatal(tmp_path: Path) -> None:
    # GAP-0033: bidirectional C1 check — a session-name transition can never
    # occur at an instant QIEA staging does not treat as a boundary.
    def mutate(d):
        d["calendars"]["fx_default"]["sessions"]["sydney"] = ["21:00", "23:00"]
    cfg = _mutated_config(tmp_path, "instruments.yaml", mutate)
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_empty_session_boundaries_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(
        tmp_path, "system_config.yaml", lambda d: d.__setitem__("session_boundaries_utc", [])
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_restricted_news_requires_windows(tmp_path: Path) -> None:
    def mutate(d):
        d["accounts"]["dev_paper"]["news"] = {"restricted": True}
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "platform_rules.yaml", mutate))


def test_caution_multiplier_dampen_only() -> None:
    # GAP-0016: the schema clamp itself — >1.0 is unrepresentable.
    assert CautionMultiplier(instrument="EUR_USD", value=0.8).value == 0.8
    with pytest.raises(Exception):
        CautionMultiplier(instrument="EUR_USD", value=1.2)


def test_tierg_flatten_needs_two_confirmations(tmp_path: Path) -> None:
    def mutate(d):
        d["tierg_taxonomy"]["conflict_escalation"]["min_confirmations_for_flatten"] = 1
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "event_sources.yaml", mutate))


# ---------------- phase 4: optimizer + C8 cost gates (ACIS-03 §5) ---------------- #

def test_missing_optimizer_block_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(tmp_path, "system_config.yaml", lambda d: d.pop("optimizer"))
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_expectancy_floor_cannot_go_below_zero(tmp_path: Path) -> None:
    # C9: the gate may be tightened, never loosened below "E <= 0 cannot win".
    def mutate(d):
        d["optimizer"]["expectancy_min_r"] = -0.1
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


def test_enabled_instrument_without_costs_is_fatal(tmp_path: Path) -> None:
    # C8: no silent zero-cost optimisation — enabled instruments declare friction.
    def mutate(d):
        d["instruments"]["EUR_USD"].pop("costs")
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "instruments.yaml", mutate))


def test_qiea_cycle_bounds_enforced(tmp_path: Path) -> None:
    def mutate(d):
        d["optimizer"]["qiea_cycle_seconds"] = 60  # below the 4h slow-loop floor
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


# ---------------- phase 5: signals + pair-relationship gates (ACIS-04 §5) ---------------- #

def test_missing_signals_block_is_fatal(tmp_path: Path) -> None:
    cfg = _mutated_config(tmp_path, "system_config.yaml", lambda d: d.pop("signals"))
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_pair_relationship_without_method_is_fatal(tmp_path: Path) -> None:
    # §5.5: a correlation without its declared window AND method is a bug.
    def mutate(d):
        d["pair_relationships"]["eurusd_usdjpy"].pop("method")
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "instruments.yaml", mutate))


def test_pair_relationship_unknown_leg_is_fatal(tmp_path: Path) -> None:
    def mutate(d):
        # NZD_USD is not declared in the universe (GBP_USD now IS, as a disabled
        # diversification-basket extension — 2026-07-22); use a genuinely unknown leg.
        d["pair_relationships"]["eurusd_usdjpy"]["legs"] = ["EUR_USD", "NZD_USD"]
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "instruments.yaml", mutate))


def test_medium_vol_discount_dampen_only(tmp_path: Path) -> None:
    def mutate(d):
        d["signals"]["medium_vol_discount"] = 1.2  # a boost is unrepresentable
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


def test_modules_enabled_must_be_complete(tmp_path: Path) -> None:
    def mutate(d):
        d["signals"]["modules_enabled"].pop("TSMOM")
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


def test_conviction_discard_cannot_undercut_signal_floor(tmp_path: Path) -> None:
    # GAP-0043: below the Signal contract's 0.45 emitted floor is unrepresentable.
    def mutate(d):
        d["signals"]["conviction_discard"] = 0.30
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


# --------------------------------------------------------------------------- #
# Phase 9 — risk block + scenario-book gates (ACIS-07 §5, ACIS-12 §2/§12)
# --------------------------------------------------------------------------- #

def test_missing_risk_block_is_fatal(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml",
                                    lambda d: d.pop("risk")))


def test_heartbeat_interval_ceiling_enforced(tmp_path: Path) -> None:
    # §12: the heartbeat may never be slower than 10 s — the watchdog's
    # silence detection depends on it (ACIS-12 §4).
    def mutate(d):
        d["risk"]["heartbeat_interval_s"] = 30
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "system_config.yaml", mutate))


def test_scenario_missing_ceiling_is_fatal(tmp_path: Path) -> None:
    # ACIS-12 §14: max_loss_pct_nav is the human-committed ceiling — required.
    def mutate(d):
        d["scenarios"][0].pop("max_loss_pct_nav")
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "scenario_book.yaml", mutate))


def test_scenario_unknown_instrument_is_fatal(tmp_path: Path) -> None:
    def mutate(d):
        d["scenarios"][0]["params"]["instrument"] = "NO_SUCH"
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "scenario_book.yaml", mutate))


def test_scenario_kind_params_enforced(tmp_path: Path) -> None:
    # A gap scenario without its gap_pct is fatal at load (ACIS-12 §12).
    def mutate(d):
        d["scenarios"][0]["params"].pop("gap_pct")
    with pytest.raises(ConfigError):
        load_config(_mutated_config(tmp_path, "scenario_book.yaml", mutate))
