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
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

from config.schemas import PairRelationship, SignalsConfig
from core.data.bars import Bar, BarAggregator
from core.data.errors import DataQualityError
from core.data.normaliser import MarketState
from core.optimizer.param_types import ParamSet
from core.regime.regime_types import LiqState, RegimeContext, RegimeType, VolClass
from core.signals.canonical import STRATEGY_IDS
from core.signals.indicators import (
    adx_proxy,
    bollinger_z,
    clamp01,
    ema_series,
    pair_spread_z,
    rolling_correlation,
    rsi_series,
    wilder_atr,
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
_DAILY_S = 86_400


@dataclass(frozen=True)
class _Raw:
    """A module's raw proposal, pre-pipeline (ACIS-04 §7 step 1)."""

    strategy_type: StrategyType
    instrument: str
    direction: int
    conviction: float          # raw, [0,1]
    entry: float
    atr_value: float           # REAL true-range ATR over bars (v2.11)
    group_id: str | None = None
    sl_atr_mult: float | None = None   # None => the evolved ParamSet multiplier
    has_take_profit: bool = True       # TSMOM: False (published method has none)


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
        # v2.11 time base: windows hold completed OHLC BARS of signal_bar_seconds
        # (ext-review C2: capacities DERIVED from config — silent starvation is
        # structurally impossible).
        from core.optimizer.param_types import GENE_SPECS
        pair_need = max((max(rel.correlation_window + 2, rel.zscore_window + 2)
                         for rel in pair_relationships.values()), default=0)
        gene_need = int(GENE_SPECS["ema_slow"][1]) + 1   # GAP-0063: derived, not 201
        self.window_capacity = max(gene_need, pair_need) + 16
        self.daily_capacity = max(cfg.tsmom_min_history_days,
                                  cfg.tsmom_lookback_days[-1] + 1) + 16
        self._bars: dict[str, deque[Bar]] = {}
        self._agg: dict[str, BarAggregator] = {}
        self._daily_bars: dict[str, deque[Bar]] = {}
        self._daily_agg: dict[str, BarAggregator] = {}
        # GAP-0047 (strong branch, v2.11): pair statistics run on JOINT samples
        # resampled onto the SHARED bar clock — one (a_close, b_close) tuple per
        # bar bucket in which BOTH legs completed a bar.
        self._pair_samples: dict[str, deque[tuple[float, float]]] = {
            name: deque(maxlen=self.window_capacity) for name in pair_relationships
        }
        # GAP-0060: joint samples join per BUCKET — a pending half-bucket waits
        # for its partner; buckets abandoned when a later bucket completes are
        # counted + logged, never silently dropped.
        self._pair_pending: dict[str, dict] = {name: {} for name in pair_relationships}
        self.pair_buckets_incomplete: dict[str, int] = {n: 0 for n in pair_relationships}
        self._seed_day: dict[str, int] = {}
        self.signals_considered = 0
        self.signals_emitted = 0
        # §10 per-gate skip attribution (C15): every discard increments the gate
        # that killed it, so starvation is diagnosable, never silent.
        self.skips: dict[str, int] = {}

    def _skip(self, gate: str) -> None:
        self.skips[gate] = self.skips.get(gate, 0) + 1

    # -- windows (ACIS-04 §8, bars) ---------------------------------------------- #

    def observe(self, state: MarketState) -> Bar | None:
        """Returns the completed signal bar, if this tick closed one, so the loop
        owner can feed the SAME bar to the Governor's C16 (GAP-0059: one declared
        aggregation, never two)."""
        inst = state.instrument
        agg = self._agg.setdefault(inst, BarAggregator(self._cfg.signal_bar_seconds))
        bar = agg.add(state.timestamp, state.mid, state.spread)
        if bar is not None:
            self._bars.setdefault(inst, deque(maxlen=self.window_capacity)).append(bar)
            self._sample_pairs(inst)
        daily_agg = self._daily_agg.setdefault(
            inst, BarAggregator(_DAILY_S, anchor_utc="22:00"))   # rollover-anchored
        daily = daily_agg.add(state.timestamp, state.mid, state.spread)
        if daily is not None:
            self._append_daily(inst, daily)
        return bar

    def _sample_pairs(self, instrument: str) -> None:
        for name, rel in self._pairs.items():
            if instrument not in rel.legs:
                continue
            bar = self._bars[instrument][-1]
            side = 0 if instrument == rel.legs[0] else 1
            pending = self._pair_pending[name]
            slot = pending.setdefault(bar.ts_open, [None, None])
            slot[side] = bar.close
            if slot[0] is not None and slot[1] is not None:
                self._pair_samples[name].append((slot[0], slot[1]))
                for ts in [t for t in pending if t <= bar.ts_open]:
                    if ts != bar.ts_open:
                        self.pair_buckets_incomplete[name] += 1
                        self._log.event("PAIR_BUCKET_INCOMPLETE", relationship=name,
                                        ts=ts.isoformat())
                    del pending[ts]

    def observe_daily_close(self, instrument: str, close: float) -> None:
        """History seeding (backfill/tests): appends a synthetic one-value daily
        bar. The LIVE path is the rollover-anchored daily aggregator in observe()."""
        if not math.isfinite(close) or close <= 0:
            raise DataQualityError("close", close, "daily close must be finite and > 0")
        day = self._seed_day.get(instrument, 0)
        self._seed_day[instrument] = day + 1
        ts = datetime(2000, 1, 3, 22, 0, tzinfo=timezone.utc) + timedelta(days=day)
        self._append_daily(instrument, Bar(
            ts_open=ts, open=close, high=close, low=close, close=close,
            spread=0.0, duration_s=_DAILY_S))

    def _append_daily(self, instrument: str, bar: Bar) -> None:
        """GAP-0065: the daily series is strictly ascending in ts_open — a bar at
        or before the last one (seed-after-live, duplicate day) is dropped+logged,
        never silently double-counted into the r63/r126/r252 indices."""
        window = self._daily_bars.setdefault(
            instrument, deque(maxlen=self.daily_capacity))
        if window and bar.ts_open <= window[-1].ts_open:
            self._log.event("DAILY_BAR_ORDER_DROP", instrument=instrument,
                            ts=bar.ts_open.isoformat())
            return
        window.append(bar)

    def take_rate(self) -> dict:
        return {"signals_considered": self.signals_considered,
                "signals_emitted": self.signals_emitted,
                "skips": dict(self.skips)}

    # -- the reflex (ACIS-04 §7) ------------------------------------------------ #

    def generate(self, state: MarketState, regime: RegimeContext,
                 params: ParamSet | None, now: datetime) -> tuple[Signal, ...]:
        t0 = time.perf_counter()
        if not regime.tradeable:
            self._skip("vetoed_regime")
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
                self._skip("entry_frozen")
                self._log.event("DISCARD_ENTRY_FROZEN", instrument=state.instrument,
                                strategy=stype.value)
                continue
            produced = fn(state, regime, params)
            for raw in produced:
                self.signals_considered += 1
                if any(not math.isfinite(v) for v in
                       (raw.conviction, raw.entry, raw.atr_value)) or raw.atr_value <= 0:
                    self._skip("nan")
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
                self._skip("subthreshold")
                self._log.event("DISCARD_SUBTHRESHOLD", instrument=raw.instrument,
                                strategy=raw.strategy_type.value,
                                conviction=round(conviction, 4))
                continue
            sl_mult = (raw.sl_atr_mult if raw.sl_atr_mult is not None
                       else params.atr_multiplier_sl)
            take_profit = ((raw.entry + raw.direction * params.atr_multiplier_tp
                            * raw.atr_value) if raw.has_take_profit else None)
            try:
                # GAP-0042: NO clamp — a module emitting conviction > 1 is a bug
                # and must die on the Signal contract (C-ALP-2), never be masked.
                sig = Signal(
                    signal_id=str(uuid.uuid4()), instrument=raw.instrument,
                    direction=raw.direction, conviction=conviction,
                    entry_price=raw.entry,
                    stop_loss=raw.entry - raw.direction * sl_mult * raw.atr_value,
                    take_profit=take_profit,
                    strategy_type=raw.strategy_type,
                    regime_at_generation=regime.regime,
                    param_set_id=params.param_set_id, generated_at=now,
                    valid_for_seconds=self._cfg.valid_for_seconds[raw.strategy_type.value],
                    group_id=raw.group_id,
                )
            except DataQualityError as exc:
                self._skip("construction_error")
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
                    self._skip("opposite")
                self._log.event("DISCARD_OPPOSITE", instrument=instrument,
                                count=len(sigs))
        # group integrity (C-ALP-7): a dead leg kills its whole group
        dead_groups = {s.group_id for s in candidates
                       if s.group_id is not None and s.signal_id in dead}
        for s in candidates:
            if s.group_id in dead_groups and s.signal_id not in dead:
                dead.add(s.signal_id)
                self._skip("group_incomplete")
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
                self._skip("duplicate_group_leg")
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

    def _window(self, instrument: str) -> tuple[list, list[float]]:
        bars = list(self._bars.get(instrument, ()))
        return bars, [b.close for b in bars]

    def _trend(self, state: MarketState, regime: RegimeContext,
               params: ParamSet) -> list[_Raw]:
        bars, seq = self._window(state.instrument)
        if len(seq) < params.ema_slow + 1:
            return []
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
        adx_value, _ = adx_proxy(seq, self._cfg.atr_period)
        return [_Raw(StrategyType.TREND, state.instrument,
                     1 if crossed_up else -1, clamp01(adx_value / 50.0),
                     state.mid, wilder_atr(bars, self._cfg.atr_period))]

    def _breakout(self, state: MarketState, regime: RegimeContext,
                  params: ParamSet) -> list[_Raw]:
        bars, seq = self._window(state.instrument)
        lookback = params.momentum_lookback
        if len(seq) < max(lookback + 1, self._cfg.atr_period + 2):
            return []
        channel_high = max(seq[-lookback - 1:-1])
        channel_low = min(seq[-lookback - 1:-1])
        a = wilder_atr(bars, self._cfg.atr_period)
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
        bars, seq = self._window(state.instrument)
        if len(seq) < max(20, params.rsi_period + 1, self._cfg.atr_period + 2):
            return []
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
        a = wilder_atr(bars, self._cfg.atr_period)
        return [_Raw(StrategyType.MEAN_REVERSION, state.instrument, direction,
                     clamp01(abs(z) / 2.0), state.mid, a)]

    def _momentum_scalp(self, state: MarketState, regime: RegimeContext,
                        params: ParamSet) -> list[_Raw]:
        bars, seq = self._window(state.instrument)
        if len(seq) < max(params.ema_fast + 2, self._cfg.atr_period + 2):
            return []
        median_velocity = self._median(state.instrument, state.session, "velocity")
        if not math.isfinite(median_velocity) or median_velocity <= 0:
            return []
        ratio = state.tick_velocity / median_velocity
        if ratio < self._cfg.momentum_scalp_surge_ratio:
            return []
        ema_f = ema_series(seq, params.ema_fast)
        slope = ema_f[-1] - ema_f[-2]
        if slope == 0:
            return []
        return [_Raw(StrategyType.MOMENTUM_SCALP, state.instrument,
                     1 if slope > 0 else -1, clamp01(ratio / 3.0),
                     state.mid, wilder_atr(bars, self._cfg.atr_period))]

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
            atr_a = wilder_atr(list(self._bars.get(leg_a, ())), self._cfg.atr_period)
            atr_b = wilder_atr(list(self._bars.get(leg_b, ())), self._cfg.atr_period)
            out.append(_Raw(StrategyType.PAIR_DIVERGENCE, leg_a, dir_a, conviction,
                            a_col[-1], atr_a, group_id))
            out.append(_Raw(StrategyType.PAIR_DIVERGENCE, leg_b, dir_b, conviction,
                            b_col[-1], atr_b, group_id))
        return out

    def _tsmom(self, state: MarketState, regime: RegimeContext,
               params: ParamSet) -> list[_Raw]:
        daily = self._daily_bars.get(state.instrument)
        if daily is None or len(daily) < self._cfg.tsmom_min_history_days:
            return []
        bars = list(daily)
        seq = [b.close for b in bars]
        signs = []
        for lb in self._cfg.tsmom_lookback_days:
            r = seq[-1] / seq[-1 - lb] - 1.0
            signs.append(1 if r > 0 else -1 if r < 0 else 0)
        total = sum(signs)
        if total == 0:
            return []
        direction = 1 if total > 0 else -1
        agreement = sum(1 for s in signs if s == direction)  # ACIS-04 §6.6: a/3
        # v2.11 faithful form (Moskowitz-Ooi-Pedersen): NO take-profit -- the
        # published expectancy lives in the right tail a target would truncate.
        # The only stop is the §8.6 safety-law disaster stop, a DECLARED
        # deviation. Exit is the signal flip / re-evaluation, not a target.
        return [_Raw(StrategyType.TSMOM, state.instrument, direction,
                     agreement / 3.0, state.mid,
                     wilder_atr(bars, self._cfg.atr_period),
                     sl_atr_mult=self._cfg.tsmom_disaster_stop_atr,
                     has_take_profit=False)]
