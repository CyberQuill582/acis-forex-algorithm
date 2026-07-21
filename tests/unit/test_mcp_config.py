"""Phase-10 config gates for the MCP plane (ACIS-08 §6, C-MCP-2)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from config.account_doctrine import guardrail_hash, rulebook_hash
from config.schemas import (ConfigError, MonitoringConfig, load_config)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def test_monitoring_block_required_schema_fatal(tmp_path) -> None:
    """A system config without a `monitoring:` block cannot even load."""
    raw = yaml.safe_load((CONFIG_DIR / "system_config.yaml").read_text(encoding="utf-8"))
    del raw["monitoring"]
    # rebuild a config dir with the mutated system config
    dst = tmp_path / "config"
    dst.mkdir()
    for f in CONFIG_DIR.glob("*.yaml"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (dst / "system_config.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(dst)


def _mon(**over):
    base = dict(transport="stdio", heartbeat_fast_s=10, heartbeat_other_s=60,
                missed_beats_flatten=3, log_tail_max=100,
                tunable_paths=[{"path": "signals.conviction_discard",
                                "min": 0.45, "max": 0.95}])
    base.update(over)
    return MonitoringConfig(**base)


def test_tunable_allowlist_cannot_name_a_guardrail_path() -> None:
    """Even the human-committed allowlist may not name a guardrail/equity path
    (defense in depth — the schema rejects it before any handler runs)."""
    with pytest.raises(Exception):
        _mon(tunable_paths=[{"path": "guardrail_limits.var_cap_pct", "min": 0, "max": 1}])
    with pytest.raises(Exception):
        _mon(tunable_paths=[{"path": "system.equity_floor", "min": 0, "max": 1}])


def test_tunable_bounds_min_le_max_enforced() -> None:
    with pytest.raises(Exception):
        _mon(tunable_paths=[{"path": "signals.conviction_discard", "min": 0.9, "max": 0.5}])


def test_tunable_bounds_helper_maps_path_to_range() -> None:
    m = _mon()
    assert m.tunable_bounds() == {"signals.conviction_discard": (0.45, 0.95)}


def test_heartbeat_fast_capped_at_10s() -> None:
    with pytest.raises(Exception):
        _mon(heartbeat_fast_s=11)


def test_guardrail_hash_is_deterministic_and_content_bound() -> None:
    cfg = load_config(CONFIG_DIR)
    h1 = guardrail_hash(cfg.guardrails)
    h2 = guardrail_hash(cfg.guardrails)
    assert h1 == h2 and len(h1) == 64
    tampered = cfg.guardrails.model_copy(update={"var_cap_pct": 2.0})
    assert guardrail_hash(tampered) != h1        # any change moves the hash


def test_rulebook_hash_is_deterministic_and_content_bound() -> None:
    cfg = load_config(CONFIG_DIR)
    rb = cfg.platform_rules.accounts[cfg.system.active_account]
    h1 = rulebook_hash(rb)
    assert h1 == rulebook_hash(rb) and len(h1) == 64
