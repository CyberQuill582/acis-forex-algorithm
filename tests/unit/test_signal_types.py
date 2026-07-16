"""Signal output contract gates (ACIS-04 §4, postcondition style)."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from core.data.errors import DataQualityError
from core.regime.regime_types import RegimeType
from core.signals.signal_types import Signal, StrategyType
from tests.signals_fixtures import T0


def mk_signal(**overrides) -> Signal:
    base = dict(
        signal_id="sig-1", instrument="EUR_USD", direction=1, conviction=0.6,
        entry_price=1.1, stop_loss=1.095, take_profit=1.11,
        strategy_type=StrategyType.TREND,
        regime_at_generation=RegimeType.STRONG_TREND_UP,
        param_set_id="ps-1", generated_at=T0, valid_for_seconds=300, group_id=None,
    )
    base.update(overrides)
    return Signal(**base)


def test_valid_long_and_short_construct() -> None:
    assert mk_signal().direction == 1
    s = mk_signal(direction=-1, stop_loss=1.105, take_profit=1.09)
    assert s.direction == -1


@pytest.mark.parametrize("overrides", [
    {"direction": 0},
    {"conviction": 0.44},                      # below the emitted floor
    {"conviction": 1.01},
    {"conviction": float("nan")},
    {"entry_price": float("inf")},
    {"stop_loss": 1.105},                      # long with stop above entry
    {"take_profit": 1.09},                     # long with target below entry
    {"direction": -1},                         # short with long-sided SL/TP
    {"generated_at": datetime(2026, 7, 6)},    # naive
    {"valid_for_seconds": 0},
    {"param_set_id": ""},
    {"group_id": "g-1"},                       # group id on a non-pair signal
])
def test_contract_violations_raise(overrides: dict) -> None:
    with pytest.raises(DataQualityError):
        mk_signal(**overrides)


def test_pair_signal_requires_group_id() -> None:
    s = mk_signal(strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="g-1")
    assert s.group_id == "g-1"
    with pytest.raises(DataQualityError):
        mk_signal(strategy_type=StrategyType.PAIR_DIVERGENCE, group_id=None)


def test_signal_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        mk_signal().conviction = 0.9  # type: ignore[misc]
