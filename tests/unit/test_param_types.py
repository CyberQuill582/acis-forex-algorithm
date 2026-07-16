"""ParamSet/LabelledBar construction gates (ACIS-03 §4/§5, postcondition style)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from core.data.errors import DataQualityError
from core.optimizer.param_types import GENE_SPECS, LabelledBar
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import T0, make_paramset


@pytest.mark.parametrize("field,bad", [
    ("ema_fast", 4), ("ema_fast", 51), ("ema_slow", 201), ("rsi_period", 6),
    ("rsi_overbought", 81.0), ("rsi_oversold", 19.0), ("atr_multiplier_sl", 0.9),
    ("atr_multiplier_tp", 5.1), ("momentum_lookback", 4),
    ("breakout_atr_threshold", 2.1), ("mean_rev_zscore_entry", 1.4),
    ("max_holding_periods", 0), ("fitness_score", float("nan")),
])
def test_out_of_range_field_raises(field: str, bad) -> None:
    with pytest.raises(DataQualityError):
        make_paramset(**{field: bad})


@pytest.mark.parametrize("overrides", [
    {"ema_fast": 30, "ema_slow": 25},                       # slow must exceed fast
    {"atr_multiplier_sl": 3.0, "atr_multiplier_tp": 2.5},   # tp must exceed sl
])
def test_cross_field_invariant_raises(overrides: dict) -> None:
    with pytest.raises(DataQualityError):
        make_paramset(**overrides)


def test_int_gene_rejects_float() -> None:
    with pytest.raises(DataQualityError):
        make_paramset(ema_fast=10.5)


def test_naive_evolved_at_raises() -> None:
    with pytest.raises(DataQualityError):
        make_paramset(evolved_at=datetime(2026, 7, 6))


def test_paramset_is_frozen() -> None:
    ps = make_paramset()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ps.ema_fast = 6  # type: ignore[misc]


def test_gene_values_covers_every_gene() -> None:
    assert set(make_paramset().gene_values()) == set(GENE_SPECS)


def test_labelled_bar_shape_violation_raises() -> None:
    with pytest.raises(DataQualityError):
        LabelledBar(ts=T0, open=1.1, high=1.05, low=1.0, close=1.1,
                    spread=0.0001, regime=RegimeType.RANGING_TIGHT)
    with pytest.raises(DataQualityError):
        LabelledBar(ts=T0, open=1.1, high=1.2, low=1.0, close=1.1,
                    spread=-0.1, regime=RegimeType.RANGING_TIGHT)
    with pytest.raises(DataQualityError):
        LabelledBar(ts=T0, open=1.1, high=float("nan"), low=1.0, close=1.1,
                    spread=0.0001, regime=RegimeType.RANGING_TIGHT)
    with pytest.raises(DataQualityError):
        LabelledBar(ts=datetime(2026, 7, 6), open=1.1, high=1.2, low=1.0, close=1.1,
                    spread=0.0001, regime=RegimeType.RANGING_TIGHT)
