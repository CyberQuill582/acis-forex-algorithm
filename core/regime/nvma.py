"""NVMA — the sovereign gatekeeper (SPEC §4, ACIS-02).

Deterministic classification of MarketState windows into exactly one of 12
regimes, plus the OR-combined veto set. Identical (state, window) inputs yield
an identical RegimeContext (C-REG-5). Indicators are computed on mid-price
windows with stdlib math only — no NaN ever leaves this layer (C-REG-4).
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Callable, Sequence

from config.schemas import RegimeConfig
from core.data.normaliser import MarketState
from core.regime.regime_types import (
    NEVER_TRADEABLE,
    LiqState,
    RegimeContext,
    RegimeType,
    VolClass,
)
from core.regime.stability import RegimeStabilityTracker


# --------------------------------------------------------------------------- #
# Indicators (mid-price series; deterministic, NaN-checked at the call site)
# --------------------------------------------------------------------------- #

def mean_abs_delta(mids: Sequence[float], period: int) -> float:
    """HONESTY RENAME (v2.11, external-referent pass): this is mean |Δmid| over
    the trailing tick window — a volatility PROXY, NOT Wilder's Average True
    Range (no high/low/prev-close/gaps). NVMA's regime thresholds were
    empirically tuned against THIS proxy (phase 3) and are self-consistent;
    nothing outside the regime layer may treat it as ATR.
    (The real true-range ATR lives on bars — core/optimizer/fitness.atr_series.)"""
    if len(mids) < period + 1:
        return math.nan
    deltas = [abs(mids[i] - mids[i - 1]) for i in range(len(mids) - period, len(mids))]
    return sum(deltas) / period


def adx_proxy(mids: Sequence[float], period: int) -> tuple[float, int]:
    """HONESTY RENAME (v2.11): a close-only directional-index PROXY — |Δmid| as
    the true-range stand-in, no high/low. Directionally faithful to Wilder's
    construction, not the standard ADX. Returns (value, direction -1|0|+1)."""
    n = len(mids)
    if n < 2 * period + 1:
        return math.nan, 0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, n):
        up = mids[i] - mids[i - 1]
        plus_dm.append(max(up, 0.0))
        minus_dm.append(max(-up, 0.0))
        trs.append(abs(up))
    dxs = []
    plus_di_last = minus_di_last = 0.0
    for i in range(period, len(trs) + 1):
        tr_sum = sum(trs[i - period:i])
        if tr_sum == 0:
            dxs.append(0.0)
            continue
        plus_di = 100.0 * sum(plus_dm[i - period:i]) / tr_sum
        minus_di = 100.0 * sum(minus_dm[i - period:i]) / tr_sum
        plus_di_last, minus_di_last = plus_di, minus_di
        denom = plus_di + minus_di
        dxs.append(0.0 if denom == 0 else 100.0 * abs(plus_di - minus_di) / denom)
    if len(dxs) < period:
        return math.nan, 0
    value = sum(dxs[-period:]) / period
    direction = 1 if plus_di_last > minus_di_last else (-1 if minus_di_last > plus_di_last else 0)
    return value, direction


def bollinger_width_percentile(mids: Sequence[float], window: int, band_period: int = 20) -> float:
    """Percentile rank of the current BB width within the rolling width history."""
    if len(mids) < window + band_period:
        return math.nan
    widths = []
    for end in range(len(mids) - window, len(mids) + 1):
        chunk = mids[end - band_period:end]
        if len(chunk) < band_period:
            continue
        sd = statistics.pstdev(chunk)
        widths.append(4.0 * sd)  # +/- 2 sigma band width
    if not widths:
        return math.nan
    current = widths[-1]
    return sum(1 for w in widths if w <= current) / len(widths)


def hurst_exponent(mids: Sequence[float], window: int) -> float:
    """Rescaled-range (R/S) Hurst estimate over the trailing `window` mids."""
    series = list(mids[-window:])
    if len(series) < window or window < 100:
        return math.nan
    returns = [series[i] - series[i - 1] for i in range(1, len(series))]
    if all(r == 0 for r in returns):
        return math.nan
    sizes = [len(returns) // 8, len(returns) // 4, len(returns) // 2, len(returns)]
    log_n, log_rs = [], []
    for size in sizes:
        if size < 8:
            continue
        rs_values = []
        for start in range(0, len(returns) - size + 1, size):
            chunk = returns[start:start + size]
            mean = sum(chunk) / len(chunk)
            devs = [c - mean for c in chunk]
            cum, running = [], 0.0
            for d in devs:
                running += d
                cum.append(running)
            r = max(cum) - min(cum)
            s = statistics.pstdev(chunk)
            if s > 0:
                rs_values.append(r / s)
        if rs_values:
            log_n.append(math.log(size))
            log_rs.append(math.log(sum(rs_values) / len(rs_values)))
    if len(log_n) < 2:
        return math.nan
    n_mean = sum(log_n) / len(log_n)
    rs_mean = sum(log_rs) / len(log_rs)
    num = sum((x - n_mean) * (y - rs_mean) for x, y in zip(log_n, log_rs))
    den = sum((x - n_mean) ** 2 for x in log_n)
    return num / den if den else math.nan


# --------------------------------------------------------------------------- #
# Input window
# --------------------------------------------------------------------------- #

@dataclass
class RegimeInputWindow:
    """Rolling per-instrument arrays (ACIS-02 §5); full at max_lookback bars."""

    maxlen: int

    def __post_init__(self) -> None:
        self.mids: deque = deque(maxlen=self.maxlen)
        self.spreads: deque = deque(maxlen=self.maxlen)
        self.velocities: deque = deque(maxlen=self.maxlen)

    def push(self, state: MarketState) -> None:
        self.mids.append(state.mid)
        self.spreads.append(state.spread)
        self.velocities.append(state.tick_velocity)

    @property
    def full(self) -> bool:
        return len(self.mids) >= self.maxlen


# --------------------------------------------------------------------------- #
# Classifier
# --------------------------------------------------------------------------- #

class NVMA:
    """classify(state, window) -> RegimeContext. Writes nothing; commands nothing."""

    def __init__(
        self,
        cfg: RegimeConfig,
        session_median: Callable[[str, str, str], float | None],  # (instrument, session, kind)
        tierg_shock: Callable[[str, datetime], bool],
        has_params_for: Callable[[RegimeType], bool],
    ) -> None:
        self._cfg = cfg
        self._session_median = session_median
        self._tierg = tierg_shock
        self._has_params = has_params_for
        self._trackers: dict[str, RegimeStabilityTracker] = {}

    def _tracker(self, instrument: str) -> RegimeStabilityTracker:
        if instrument not in self._trackers:
            self._trackers[instrument] = RegimeStabilityTracker(
                window=self._cfg.stability_window,
                default_half_life_s=self._cfg.cycle_seconds,
            )
        return self._trackers[instrument]

    def classify(self, state: MarketState, window: RegimeInputWindow) -> RegimeContext:
        cfg = self._cfg
        snapshot: dict[str, object] = {}
        veto_reasons: list[str] = []

        def emit(regime: RegimeType, direction: int, vol: VolClass, liq: LiqState,
                 confidence: float) -> RegimeContext:
            tracker = self._tracker(state.instrument)
            # GAP-0031: gate-states (UNCLASSIFIED / MACRO_EVENT / ILLIQUID) are
            # not market regimes — they never enter the stability history, so
            # warm-up and event windows cannot dilute the score AGON gates on.
            # GAP-0032: stability/half-life are DECLARED historical aggregates
            # over recorded classifiable labels (ACIS-02 §8 scope); the pure
            # fields of the context are functions of (state, window, config).
            if regime not in NEVER_TRADEABLE:
                tracker.record(regime.value, state.timestamp)
                stability = tracker.stability(regime.value)
            else:
                stability = 0.0
            tradeable = regime not in NEVER_TRADEABLE and not veto_reasons
            snapshot["veto_reasons"] = tuple(veto_reasons)
            return RegimeContext(
                regime=regime,
                trend_direction=direction,
                volatility_class=vol,
                liquidity_state=liq,
                tradeable=tradeable,
                regime_stability_score=stability,
                estimated_half_life_seconds=tracker.half_life_seconds(),
                confidence=confidence,
                timestamp=state.timestamp,
                instrument=state.instrument,
                inputs_snapshot=MappingProxyType(dict(snapshot)),
            )

        # 1. Warm-up: never guess (C-REG-2 / F18).
        med_spread = self._session_median(state.instrument, state.session, "spread")
        med_velocity = self._session_median(state.instrument, state.session, "velocity")
        if not window.full or med_spread is None or med_velocity is None:
            veto_reasons.append("REGIME_WARMING")
            snapshot.update(window_full=window.full, median_warm=med_spread is not None)
            return emit(RegimeType.UNCLASSIFIED, 0, VolClass.LOW, LiqState.THIN, 0.0)

        # 2. Median-relative vetoes (evaluated on the incoming state).
        if state.is_stale:
            veto_reasons.append("STALE_STATE")
        if med_spread > 0 and state.spread > cfg.spread_veto_mult * med_spread:
            veto_reasons.append("SPREAD_VETO")
        if med_velocity > 0 and state.tick_velocity < cfg.velocity_veto_mult * med_velocity:
            veto_reasons.append("DEAD_MARKET")

        mids = list(window.mids)
        spreads = list(window.spreads)

        # 3. Precedence: MACRO_EVENT > ILLIQUID > indicators (ACIS-02 §7.4).
        if state.macro_events_imminent or self._tierg(state.instrument, state.timestamp):
            snapshot["macro"] = True
            return emit(RegimeType.MACRO_EVENT, 0, VolClass.HIGH, LiqState.THIN, 1.0)
        # GAP-0028: master §4 defines ILLIQUID as spread deviation > Nσ from the
        # SESSION median (one baseline, shared with the veto rules — a window
        # median would self-track a widening spread and mask sustained
        # illiquidity). σ is the window spread dispersion; the centre is the
        # session median. Dead velocity stays a VETO (master §4), not a regime.
        spread_sigma = statistics.pstdev(spreads) if len(spreads) > 1 else 0.0
        illiquid_spread = (state.spread - med_spread) > cfg.spread_illiquid_sigma * spread_sigma
        if state.session == "closed" or illiquid_spread:
            snapshot.update(session=state.session, spread=state.spread,
                            session_median_spread=med_spread, spread_sigma=spread_sigma)
            return emit(RegimeType.ILLIQUID, 0, VolClass.LOW, LiqState.ILLIQUID, 1.0)

        # 4. Indicators — NaN anywhere means UNCLASSIFIED + veto (C-REG-4).
        p_fast, p_mid, p_slow = cfg.atr_periods
        atr_fast, atr_slow = mean_abs_delta(mids, p_fast), mean_abs_delta(mids, p_slow)
        adx_value, direction = adx_proxy(mids, cfg.adx_period)
        bb_pct = bollinger_width_percentile(mids, cfg.bb_window)
        hurst = hurst_exponent(mids, cfg.hurst_window)
        snapshot.update(atr_fast=atr_fast, atr_slow=atr_slow, adx=adx_value,
                        direction=direction, bb_pct=bb_pct, hurst=hurst)
        values = [atr_fast, atr_slow, adx_value, bb_pct, hurst]
        if any(isinstance(v, float) and not math.isfinite(v) for v in values):
            veto_reasons.append("INDICATOR_NAN")
            return emit(RegimeType.UNCLASSIFIED, 0, VolClass.LOW, LiqState.THIN, 0.0)

        # Volatility class from ATR ratio (fast vs slow).
        ratio = atr_fast / atr_slow if atr_slow > 0 else 0.0
        snapshot["atr_ratio"] = ratio
        if ratio >= cfg.vol_extreme_ratio:
            vol = VolClass.EXTREME
        elif ratio >= cfg.vol_high_ratio:
            vol = VolClass.HIGH
        elif ratio >= cfg.vol_medium_ratio:
            vol = VolClass.MEDIUM
        else:
            vol = VolClass.LOW
        liq = LiqState.NORMAL if med_velocity > 0 and state.tick_velocity >= med_velocity else LiqState.THIN

        # 5. Regime resolution — fixed deterministic precedence, exactly one.
        trending_h = hurst > cfg.hurst_trend
        meanrev_h = hurst < cfg.hurst_meanrev
        agreement: list[float] = []
        if bb_pct <= cfg.bb_squeeze_pct and adx_value < cfg.adx_strong:
            regime, direction_out = RegimeType.BREAKOUT_IMMINENT, 0
            agreement = [1.0, 1.0 - adx_value / cfg.adx_strong]
        elif bb_pct >= cfg.bb_release_pct and vol in (VolClass.HIGH, VolClass.EXTREME) \
                and adx_value < cfg.adx_strong:
            regime, direction_out = RegimeType.POST_BREAKOUT, direction
            agreement = [1.0, bb_pct]
        elif adx_value >= cfg.adx_strong and direction != 0:
            regime = RegimeType.STRONG_TREND_UP if direction > 0 else RegimeType.STRONG_TREND_DOWN
            direction_out = direction
            agreement = [min(adx_value / (2 * cfg.adx_strong) + 0.5, 1.0),
                         1.0 if trending_h else 0.5]
        elif adx_value >= cfg.adx_weak and direction != 0:
            regime = RegimeType.WEAK_TREND_UP if direction > 0 else RegimeType.WEAK_TREND_DOWN
            direction_out = direction
            agreement = [0.7, 1.0 if trending_h else 0.5]
        elif meanrev_h:
            regime, direction_out = RegimeType.MEAN_REVERTING, 0
            agreement = [1.0 - hurst / cfg.hurst_meanrev if cfg.hurst_meanrev else 0.5,
                         1.0 - min(adx_value / cfg.adx_strong, 1.0)]
        elif bb_pct < 0.5:
            regime, direction_out = RegimeType.RANGING_TIGHT, 0
            agreement = [1.0 - bb_pct, 1.0 - min(adx_value / cfg.adx_strong, 1.0)]
        else:
            regime, direction_out = RegimeType.RANGING_WIDE, 0
            agreement = [bb_pct, 1.0 - min(adx_value / cfg.adx_strong, 1.0)]

        confidence = max(0.0, min(1.0, sum(agreement) / len(agreement)))
        snapshot["agreement"] = tuple(agreement)

        # 6. Remaining vetoes (OR-combined).
        if confidence < cfg.confidence_veto:
            veto_reasons.append("LOW_CONFIDENCE")
        if not self._has_params(regime):
            veto_reasons.append("NO_PARAMS_FOR_REGIME")

        return emit(regime, direction_out, vol, liq, confidence)


class NVMAEngine:
    """Medium-loop wrapper: windows, shift detection, store write, logging."""

    def __init__(self, nvma: NVMA, cfg: RegimeConfig, logger,
                 notify_shift: Callable[[str, RegimeType], None] | None = None) -> None:
        self._nvma = nvma
        self._cfg = cfg
        self._log = logger
        self._notify = notify_shift
        self._windows: dict[str, RegimeInputWindow] = {}
        self._previous: dict[str, RegimeType] = {}
        self.regime_store: dict[str, RegimeContext] = {}
        # §10 per-gate skip attribution (C15): NVMA's veto reasons counted at the
        # gate, so "which hand is on the throat" is answerable from counters.
        self.veto_counters: dict[str, int] = {}

    def window(self, instrument: str) -> RegimeInputWindow:
        if instrument not in self._windows:
            self._windows[instrument] = RegimeInputWindow(maxlen=self._cfg.max_lookback)
        return self._windows[instrument]

    def observe(self, state: MarketState) -> None:
        self.window(state.instrument).push(state)

    def classify(self, state: MarketState) -> RegimeContext:
        ctx = self._nvma.classify(state, self.window(state.instrument))
        previous = self._previous.get(state.instrument)
        if previous is not None and previous != ctx.regime:
            self._log.event("REGIME_SHIFT", instrument=state.instrument,
                            from_regime=previous.value, to_regime=ctx.regime.value,
                            inputs=dict(ctx.inputs_snapshot, veto_reasons=list(
                                ctx.inputs_snapshot.get("veto_reasons", ()))))
            if self._notify is not None:
                self._notify(state.instrument, ctx.regime)
        for reason in ctx.inputs_snapshot.get("veto_reasons", ()):
            self.veto_counters[reason] = self.veto_counters.get(reason, 0) + 1
            self._log.event("VETO_APPLIED", instrument=state.instrument, reason=reason,
                            regime=ctx.regime.value)
        self._previous[state.instrument] = ctx.regime
        self.regime_store[state.instrument] = ctx  # last-writer per instrument
        return ctx
