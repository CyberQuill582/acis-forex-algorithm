"""Shared fixtures: real config load + factory construction (postcondition style)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.schemas import AcisConfig, load_config
from core.data.asset_classes import build_calendars
from core.data.normaliser import FactoryConfig, MarketStateFactory

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(scope="session")
def acis_config() -> AcisConfig:
    return load_config(CONFIG_DIR)


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
