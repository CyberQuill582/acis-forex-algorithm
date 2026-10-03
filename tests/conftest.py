"""Shared fixtures: real config load + factory construction (postcondition style).

`acis_config` is the SHIPPED config narrowed to the two pairs the behaviour tests were written for
(tests/legacy_universe.py: EUR_USD, USD_JPY enabled; the target path off), so a universe change in
config/ does not silently re-scope them. `shipped_config` is the config exactly as committed: the R1.6
universe is tested against it (tests/integration/test_target_runtime.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.schemas import AcisConfig, load_config
from core.data.asset_classes import build_calendars
from core.data.normaliser import FactoryConfig, MarketStateFactory
from tests.legacy_universe import legacy_view

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(autouse=True)
def _no_look_anchor_push(monkeypatch):
    """GAP-P12D-86: no test pushes the real repository's look-anchor branch. The anchor's own tests
    import `anchor`/`anchored` directly and run them against a temporary repository and remote."""
    import tests.backtest.look_anchor as la
    monkeypatch.setattr(la, "anchor", lambda register, repo, remote="origin": "")
    monkeypatch.setattr(la, "anchored", lambda register, repo, remote="origin": True)


@pytest.fixture(scope="session")
def shipped_config() -> AcisConfig:
    return load_config(CONFIG_DIR)


@pytest.fixture(scope="session")
def acis_config(shipped_config: AcisConfig) -> AcisConfig:
    return legacy_view(shipped_config)


@pytest.fixture()
def factory(acis_config: AcisConfig) -> MarketStateFactory:
    d = acis_config.system.data
    calendars = build_calendars(acis_config.instruments.calendars)
    enabled = acis_config.instruments.enabled
    return MarketStateFactory(
        cfg=FactoryConfig(
            stale_threshold_ms=d.stale_threshold_ms,
            clock_skew_tolerance_ms=d.clock_skew_tolerance_ms,
            reorder_tolerance_ms=d.reorder_tolerance_ms,
            tick_velocity_window_s=d.tick_velocity_window_s,
            session_median_window=d.session_median_window,
            session_median_min_samples=d.session_median_min_samples,
        ),
        calendars_by_instrument={s: calendars[sp.calendar] for s, sp in enabled.items()},
        max_plausible_spread={s: sp.max_plausible_spread for s, sp in enabled.items()},
        macro_imminent=lambda instrument, ts: False,
    )
