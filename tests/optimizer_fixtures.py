"""Shared synthetic fixtures for the phase-4 optimizer tests (ACIS-03 §14).

Zigzag price legs give the dual-EMA harness real crosses and profitable rides;
amplitudes are large relative to the declared C8 friction so positive-expectancy
param sets exist for evolution to find (empirically tuned, phase-3 precedent).
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

from config.schemas import OptimizerConfig
from core.data.jsonl_logging import JsonlEventLogger
from core.optimizer.costs import CostModel
from core.optimizer.param_types import LabelledBar, ParamSet, RegimeLabelledHistory
from core.regime.regime_types import RegimeType

T0 = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)  # a Monday

TEST_COSTS = CostModel(commission_per_side=0.0, slippage_per_side=0.00002)


def opt_cfg(**overrides) -> OptimizerConfig:  # not test_-prefixed: pytest must not collect it
    base = dict(
        population_size=8, generations=8, qbit_resolution=8, rotation_angle_rad=0.05,
        qiea_cycle_seconds=14_400, fitness_span_days=730, fitness_min_bars=100,
        fitness_min_trades=5, holdout_fraction=0.20, holdout_min_trades=2,
        expectancy_min_r=0.0,
    )
    base.update(overrides)
    return OptimizerConfig(**base)


def zigzag_closes(n: int, leg: int = 20, step: float = 0.0005, base: float = 1.1) -> list[float]:
    closes, level, sign = [], base, +1
    for i in range(n):
        if i % leg == 0 and i > 0:
            sign = -sign
        level += sign * step
        closes.append(level)
    return closes


def bars_from_closes(
    closes: list[float],
    regime: RegimeType = RegimeType.STRONG_TREND_UP,
    spread: float = 0.0001,
    wick: float = 0.0002,
) -> tuple[LabelledBar, ...]:
    bars, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        bars.append(
            LabelledBar(
                # GAP-0071: fixtures carry the DECLARED 60s signal-bar spacing
                ts=T0 + timedelta(seconds=60 * i),
                open=o, high=max(o, c) + wick, low=min(o, c) - wick, close=c,
                spread=spread, regime=regime,
            )
        )
        prev = c
    return tuple(bars)


BAR_SECONDS = 60  # the declared signal bar (signals.signal_bar_seconds)
ATR_PERIOD = 14   # the declared signals.atr_period, threaded per GAP-0071


def zigzag_history(
    n: int = 500, regime: RegimeType = RegimeType.STRONG_TREND_UP, **kw
) -> RegimeLabelledHistory:
    return RegimeLabelledHistory("EUR_USD",
                                 bars_from_closes(zigzag_closes(n, **kw), regime),
                                 bar_seconds=BAR_SECONDS)


def make_paramset(regime: RegimeType = RegimeType.STRONG_TREND_UP, **overrides) -> ParamSet:
    base = dict(
        ema_fast=5, ema_slow=20, rsi_period=7, rsi_overbought=75.0, rsi_oversold=25.0,
        atr_multiplier_sl=2.0, atr_multiplier_tp=3.0, momentum_lookback=10,
        breakout_atr_threshold=1.0, mean_rev_zscore_entry=2.0, max_holding_periods=24,
        regime=regime, param_set_id="ps-test-0001", fitness_score=0.5,
        evolved_at=T0,
    )
    base.update(overrides)
    return ParamSet(**base)


class CapturingLogger:
    """JsonlEventLogger over StringIO; .events() returns parsed envelopes."""

    def __init__(self) -> None:
        self._buf = io.StringIO()
        self._logger = JsonlEventLogger(self._buf, layer="optimizer", session_id="opt-test")

    def event(self, event_type: str, **data) -> None:
        self._logger.event(event_type, **data)

    def events(self, event_type: str | None = None) -> list[dict]:
        out = [json.loads(line) for line in self._buf.getvalue().splitlines() if line.strip()]
        if event_type is not None:
            out = [e for e in out if e["event_type"] == event_type]
        return out
