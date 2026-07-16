"""AGON — the signal arena (ACIS-04, master §5.5). Reflex, not committee.

Six regime-gated modules fire independently; conviction is a per-module
deterministic formula; conflicts resolve by the fixed §2 table (opposite
directions => discard both); pair legs emit as complete groups or not at all.
No module reads another module's output; nothing here reads capital,
portfolio, or execution. Randomness does not exist in this layer.
"""

from __future__ import annotations

import math
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from config.schemas import PairRelationship, SignalsConfig
from core.data.errors import DataQualityError
from core.data.normaliser import MarketState
from core.optimizer.param_types import ParamSet
from core.regime.regime_types import LiqState, RegimeContext, RegimeType, VolClass
from core.signals.canonical import STRATEGY_IDS
from core.signals.indicators import (
    adx,
    atr,
    bollinger_z,
    clamp01,
    ema_series,
    pair_spread_z,
    rolling_correlation,
    rsi_series,
)
from core.signals.provenance import ProvenanceStore
from core.signals.signal_types import Signal, StrategyType

_TREND_REGIMES = frozenset({
    RegimeType.STRONG_TREND_UP, RegimeType.STRONG_TREND_DOWN,
    RegimeType.WEAK_TREND_UP, RegimeType.WEAK_TREND_DOWN,
})
_BREAKOUT_REGIMES = frozenset({RegimeType.BREAKOUT_IMMINENT, RegimeType.POST_BREAKOUT})
_RANGING_REGIMES = frozenset({
    RegimeType.RANGING_TIGHT, RegimeType.RANGING_WIDE, RegimeType.MEAN_REVERTING,
})
_SCALP_LIQ = frozenset({LiqState.DEEP, LiqState.NORMAL})
_ATR_PERIOD = 14


@dataclass(frozen=True)
class _Raw:
    """A module's raw proposal, pre-pipeline (ACIS-04 §7 step 1)."""

    strategy_type: StrategyType
    instrument: str
    direction: int
    conviction: float          # raw, [0,1]
    entry: float
    atr_value: float
    group_id: str | None = None


class AGON:
    def __init__(
        self,
        cfg: SignalsConfig,
        pair_relationships: dict[str, PairRelationship],
        provenance: ProvenanceStore,
        session_median: Callable[[str, str, str], float],
        logger,
    ) -> None:
        # C-PRV-1: every enabled module must be provenance-registered to exist.
        for stype, enabled in cfg.modules_enabled.items():
            if enabled and not provenance.is_registered(STRATEGY_IDS[StrategyType(stype)]):
                raise DataQualityError("module", stype,
                                       "unregistered strategy cannot enter the Arena (§5.6)")
        self._cfg = cfg
        self._pairs = pair_relationships
        self._prov = provenance
        self._median = session_median
        self._log = logger
        self._mids: dict[str, deque[float]] = {}
        self._daily: dict[str, deque[float]] = {}
        # GAP-0047: pair statistics run on JOINT samples appended only when both
        # legs have a current mid — time-aligned by construction, never two
        # independently-indexed deques.
        self._pair_samples: dict[str, deque[tuple[float, float]]] = {
            name: deque(maxlen=256) for name in pair_relationships
        }
        self.signals_considered = 0
        self.signals_emitted = 0

    # -- windows (ACIS-04 §8) -------------------------------------------------- #

    def observe(self, state: MarketState) -> None:
        self._mids.setdefault(state.instrument, deque(maxlen=256)).append(state.mid)
        for name, rel in self._pairs.items():
            # one aligned sample per pair-update: the SECOND leg's tick closes the
            # sample with the latest value of the first (last-value alignment)
            if state.instrument == rel.legs[1]:
                a_mids = self._mids.get(rel.legs[0])
                if a_mids:
                    self._pair_samples[name].append((a_mids[-1], state.mid))

    def observe_daily_close(self, instrument: str, close: float) -> None:
        if not math.isfinite(close) or close <= 0:
            raise DataQualityError("close", close, "daily close must be finite and > 0")
        self._daily.setdefault(instrument, deque(maxlen=300)).append(close)

    def take_rate(self) -> dict:
        return {"signals_considered": self.signals_considered,
                "signals_emitted": self.signals_emitted}

    # -- the reflex (ACIS-04 §7) ------------------------------------------------ #

    def generate(self, state: MarketState, regime: RegimeContext,
                 params: ParamSet | None, now: datetime) -> tuple[Signal, ...]:
        t0 = time.perf_counter()
        if not regime.tradeable:
            self._log.event("DISCARD_VETOED_REGIME", instrument=state.instrument,
                            regime=regime.regime.value)
            return ()
        if params is None:
            return ()

        raws: list[_Raw] = []
        for stype, fn in (
            (StrategyType.TREND, self._trend),
            (StrategyType.BREAKOUT, self._breakout),
            (StrategyType.MEAN_REVERSION, self._mean_reversion),
            (StrategyType.MOMENTUM_SCALP, self._momentum_scalp),
            (StrategyType.PAIR_DIVERGENCE, self._pair_divergence),
            (StrategyType.TSMOM, self._tsmom),
        ):
            if not self._cfg.modules_enabled.get(stype.value, False):
                continue
            if not self._module_gate(stype, regime):
                continue
            if not self._prov.entry_allowed(STRATEGY_IDS[stype], now):
                self._log.event("DISCARD_ENTRY_FROZEN", instrument=state.instrument,
                                strategy=stype.value)
                continue
            produced = fn(state, regime, params)
            for raw in produced:
                self.signals_considered += 1
                if any(not math.isfinite(v) for v in
                       (raw.conviction, raw.entry, raw.atr_value)) or raw.atr_value <= 0:
                    self._log.event("SIGNAL_NAN_SKIP", instrument=raw.instrument,
                                    strategy=stype.value)
                    continue
                raws.append(raw)

        signals = self._pipeline(raws, regime, params, now)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if elapsed_ms > self._cfg.fast_loop_decision_budget_ms:
            self._log.event("DECISION_BUDGET_EXCEEDED", instrument=state.instrument,
                            elapsed_ms=round(elapsed_ms, 3),
                            budget_ms=self._cfg.fast_loop_decision_budget_ms)
        self.signals_emitted += len(signals)
        return signals

    def _module_gate(self, stype: StrategyType, regime: RegimeContext) -> bool:
        # C4 "LOW-vol ranging disables Trend + Breakout": satisfied STRUCTURALLY —
        # those modules' active-regime sets are disjoint from the ranging regimes,
        # so no extra vol condition exists here (GAP-0044: the previous redundant
        # clause was dead code; the §14 test proves the law holds via the gate).
        if stype is StrategyType.TREND:
            return regime.regime in _TREND_REGIMES
        if stype is StrategyType.BREAKOUT:
            return regime.regime in _BREAKOUT_REGIMES
        if stype is StrategyType.MEAN_REVERSION:
            return regime.regime in _RANGING_REGIMES
        if stype is StrategyType.MOMENTUM_SCALP:
            return (regime.regime in _TREND_REGIMES
                    and regime.liquidity_state in _SCALP_LIQ)
        if stype is StrategyType.PAIR_DIVERGENCE:
            return regime.regime in _RANGING_REGIMES
        if stype is StrategyType.TSMOM:
            return True  # every tradeable regime — canonical unconditional (§6.6)
        return False

    # -- conviction pipeline (C4 order fixed) ------------------------------------- #

    def _pipeline(self, raws: list[_Raw], regime: RegimeContext,
                  params: ParamSet, now: datetime) -> tuple[Signal, ...]:
        candidates: list[Signal] = []
        for raw in raws:
            conviction = raw.conviction
            if regime.volatility_class is VolClass.MEDIUM:   # 1. discount FIRST
                conviction *= self._cfg.medium_vol_discount
            if conviction < self._cfg.conviction_discard:    # 2. THEN discard
                self._log.event("DISCARD_SUBTHRESHOLD", instrument=raw.instrument,
                                strategy=raw.strategy_type.value,
                                conviction=round(conviction, 4))
                continue
            sl_mult, tp_mult = params.atr_multiplier_sl, params.atr_multiplier_tp
            try:
                # GAP-0042: NO clamp — a module emitting conviction > 1 is a bug
                # and must die on the Signal contract (C-ALP-2), never be masked.
                sig = Signal(
                    signal_id=str(uuid.uuid4()), instrument=raw.instrument,
                    direction=raw.direction, conviction=conviction,
                    entry_price=raw.entry,
                    stop_loss=raw.entry - raw.direction * sl_mult * raw.atr_value,
                    take_profit=raw.entry + raw.direction * tp_mult * raw.atr_value,
                    strategy_type=raw.strategy_type,
                    regime_at_generation=regime.regime,
                    param_set_id=params.param_set_id, generated_at=now,
                    valid_for_seconds=self._cfg.valid_for_seconds[raw.strategy_type.value],
                    group_id=raw.group_id,
                )
            except DataQualityError as exc:
                self._log.event("SIGNAL_CONSTRUCTION_ERROR", instrument=raw.instrument,
                                strategy=raw.strategy_type.value, reason=str(exc))
                continue
            candidates.append(sig)

        # 5. conflicts: opposite direction on the same instrument => discard both
        dead: set[str] = set()
        by_instrument: dict[str, list[Signal]] = {}
        for s in candidates:
            by_instrument.setdefault(s.instrument, []).append(s)
        for instrument, sigs in by_instrument.items():
            directions = {s.direction for s in sigs}
            if directions == {1, -1}:
                for s in sigs:
                    dead.add(s.signal_id)
                self._log.event("DISCARD_OPPOSITE", instrument=instrument,
                                count=len(sigs))
        # group integrity (C-ALP-7): a dead leg kills its whole group
        dead_groups = {s.group_id for s in candidates
                       if s.group_id is not None and s.signal_id in dead}
        for s in candidates:
            if s.group_id in dead_groups and s.signal_id not in dead:
                dead.add(s.signal_id)
                self._log.event("DISCARD_GROUP_INCOMPLETE", instrument=s.instrument,
                                group_id=s.group_id)
        survivors = [s for s in candidates if s.signal_id not in dead]

        # same-direction duplicates on one instrument: keep the higher conviction.
        # GAP-0041: a surviving GROUP leg also claims its (instrument, direction) —
        # a solo signal duplicating a leg is redundant exposure and is dropped
        # (the group is the relationship trade; it is never deduped away itself).
        group_legs = [s for s in survivors if s.group_id is not None]
        leg_keys = {(s.instrument, s.direction) for s in group_legs}
        best: dict[tuple[str, int], Signal] = {}
        for s in survivors:
            if s.group_id is not None:
                continue
            key = (s.instrument, s.direction)
            if key in leg_keys:
                self._log.event("DISCARD_DUPLICATES_GROUP_LEG", instrument=s.instrument,
                                strategy=s.strategy_type.value)
                continue
            if key not in best or s.conviction > best[key].conviction:
                best[key] = s
        out = group_legs + list(best.values())

        for s in out:
            self._log.event("SIGNAL_EMITTED", instrument=s.instrument,
                            strategy=s.strategy_type.value, direction=s.direction,
                            conviction=round(s.conviction, 4), signal_id=s.signal_id,
                            group_id=s.group_id, param_set_id=s.param_set_id)
        return tuple(out)

    # -- the six modules (each a pure function of its inputs, C-ALP-8) ------------- #

    def _trend(self, state: MarketState, regime: RegimeContext,
               params: ParamSet) -> list[_Raw]:
        mids = self._mids.get(state.instrument)
        if mids is None or len(mids) < params.ema_slow + 1:
            return []
        seq = list(mids)
        ema_f, ema_s = ema_series(seq, params.ema_fast), ema_series(seq, params.ema_slow)
        crossed_up = ema_f[-2] <= ema_s[-2] and ema_f[-1] > ema_s[-1]
        crossed_down = ema_f[-2] >= ema_s[-2] and ema_f[-1] < ema_s[-1]
        if not (crossed_up or crossed_down):
            return []
        rsi = rsi_series(seq, params.rsi_period)[-1]
        if crossed_up and rsi >= params.rsi_overbought:
            return []
        if crossed_down and rsi <= params.rsi_oversold:
            return []
        adx_value, _ = adx(seq, _ATR_PERIOD)
        return [_Raw(StrategyType.TREND, state.instrument,
                     1 if crossed_up else -1, clamp01(adx_value / 50.0),
                     state.mid, atr(seq, _ATR_PERIOD))]

    def _breakout(self, state: MarketState, regime: RegimeContext,
                  params: ParamSet) -> list[_Raw]:
        mids = self._mids.get(state.instrument)
        lookback = params.momentum_lookback
        if mids is None or len(mids) < lookback + 1:
            return []
        seq = list(mids)
        channel_high = max(seq[-lookback - 1:-1])
        channel_low = min(seq[-lookback - 1:-1])
        a = atr(seq, _ATR_PERIOD)
        if a <= 0 or math.isnan(a):
            return []
        threshold = params.breakout_atr_threshold * a
        # false-break filter: the current mid (the "close") must be beyond the
        # level by the threshold — a wick that came back does not qualify.
        if seq[-1] > channel_high + threshold:
            magnitude = seq[-1] - channel_high
            return [_Raw(StrategyType.BREAKOUT, state.instrument, 1,
                         clamp01((magnitude / a) / 2.0), state.mid, a)]
        if seq[-1] < channel_low - threshold:
            magnitude = channel_low - seq[-1]
            return [_Raw(StrategyType.BREAKOUT, state.instrument, -1,
                         clamp01((magnitude / a) / 2.0), state.mid, a)]
        return []

    def _mean_reversion(self, state: MarketState, regime: RegimeContext,
                        params: ParamSet) -> list[_Raw]:
        mids = self._mids.get(state.instrument)
        if mids is None or len(mids) < max(20, params.rsi_period + 1):
            return []
        seq = list(mids)
        z = bollinger_z(seq, 20)
        if math.isnan(z) or abs(z) < params.mean_rev_zscore_entry:
            return []
        # §6.3: divergence is a GATE (classic form — RSI walks away from the
        # extreme while price holds it); magnitude comes from z.
        rsi_window = rsi_series(seq, params.rsi_period)[-20:]
        rsi_now = rsi_window[-1]
        if z < 0:
            if rsi_now - min(rsi_window) < 5.0:
                return []
            direction = 1
        else:
            if max(rsi_window) - rsi_now < 5.0:
                return []
            direction = -1
        a = atr(seq, _ATR_PERIOD)
        return [_Raw(StrategyType.MEAN_REVERSION, state.instrument, direction,
                     clamp01(abs(z) / 2.0), state.mid, a)]

    def _momentum_scalp(self, state: MarketState, regime: RegimeContext,
                        params: ParamSet) -> list[_Raw]:
        mids = self._mids.get(state.instrument)
        if mids is None or len(mids) < params.ema_fast + 2:
            return []
        median_velocity = self._median(state.instrument, state.session, "velocity")
        if not math.isfinite(median_velocity) or median_velocity <= 0:
            return []
        ratio = state.tick_velocity / median_velocity
        if ratio < self._cfg.momentum_scalp_surge_ratio:
            return []
        seq = list(mids)
        ema_f = ema_series(seq, params.ema_fast)
        slope = ema_f[-1] - ema_f[-2]
        if slope == 0:
            return []
        return [_Raw(StrategyType.MOMENTUM_SCALP, state.instrument,
                     1 if slope > 0 else -1, clamp01(ratio / 3.0),
                     state.mid, atr(seq, _ATR_PERIOD))]

    def _pair_divergence(self, state: MarketState, regime: RegimeContext,
                         params: ParamSet) -> list[_Raw]:
        out: list[_Raw] = []
        for name, rel in self._pairs.items():
            if rel.legs[0] != state.instrument:
                continue  # deterministic anchor: the group fires from leg 0 only
            leg_a, leg_b = rel.legs
            joint = self._pair_samples[name]   # GAP-0047: time-aligned samples
            warm = max(rel.correlation_window + 1, rel.zscore_window)
            if len(joint) < warm:
                continue
            a_col = [t[0] for t in joint]
            b_col = [t[1] for t in joint]
            corr = rolling_correlation(a_col, b_col, rel.correlation_window)
            if math.isnan(corr):
                continue
            if abs(corr) < rel.stability_floor or (corr > 0) != (rel.expected_sign > 0):
                continue  # coupling broken or wrong-signed: no entry (§6.5)
            z = pair_spread_z(a_col, b_col, rel.expected_sign, rel.zscore_window)
            if math.isnan(z) or abs(z) < params.mean_rev_zscore_entry:
                continue
            dir_a = -1 if z > 0 else 1
            dir_b = -rel.expected_sign * dir_a
            conviction = clamp01(abs(z) / 3.0) * abs(corr)
            group_id = str(uuid.uuid4())
            atr_a, atr_b = atr(a_col, _ATR_PERIOD), atr(b_col, _ATR_PERIOD)
            out.append(_Raw(StrategyType.PAIR_DIVERGENCE, leg_a, dir_a, conviction,
                            a_col[-1], atr_a, group_id))
            out.append(_Raw(StrategyType.PAIR_DIVERGENCE, leg_b, dir_b, conviction,
                            b_col[-1], atr_b, group_id))
        return out

    def _tsmom(self, state: MarketState, regime: RegimeContext,
               params: ParamSet) -> list[_Raw]:
        daily = self._daily.get(state.instrument)
        if daily is None or len(daily) < self._cfg.tsmom_min_history_days:
            return []
        seq = list(daily)
        signs = []
        for lb in self._cfg.tsmom_lookback_days:
            r = seq[-1] / seq[-1 - lb] - 1.0
            signs.append(1 if r > 0 else -1 if r < 0 else 0)
        total = sum(signs)
        if total == 0:
            return []
        direction = 1 if total > 0 else -1
        agreement = sum(1 for s in signs if s == direction)  # ACIS-04 §6.6: a/3
        return [_Raw(StrategyType.TSMOM, state.instrument, direction,
                     agreement / 3.0, state.mid, atr(seq, _ATR_PERIOD))]
