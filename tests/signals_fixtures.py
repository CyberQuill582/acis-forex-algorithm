"""Shared fixtures for phase-5 AGON tests (ACIS-04 §14).

Module-trigger series are empirically tuned against the real indicator maths
(phase-3 precedent) — each generator documents what it must provoke.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

from config.schemas import PairRelationship, SignalsConfig
from core.data.normaliser import MarketState, deep_freeze
from core.regime.regime_types import LiqState, RegimeContext, RegimeType, VolClass
from core.signals.agon import AGON
from core.signals.canonical import register_canonical
from core.signals.provenance import ProvenanceStore
from tests.optimizer_fixtures import CapturingLogger, make_paramset  # noqa: F401

T0 = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)

PAIR_RELS = {
    "eurusd_usdjpy": PairRelationship(
        legs=("EUR_USD", "USD_JPY"), expected_sign=-1, correlation_window=50,
        method="pearson_log_returns", stability_floor=0.40, zscore_window=50,
    )
}


def signals_cfg(**overrides) -> SignalsConfig:
    base = dict(
        signal_bar_seconds=60, atr_period=14, tsmom_disaster_stop_atr=10.0,
        conviction_discard=0.45, medium_vol_discount=0.85,
        valid_for_seconds={"TREND": 300, "BREAKOUT": 120, "MEAN_REVERSION": 300,
                           "MOMENTUM_SCALP": 30, "PAIR_DIVERGENCE": 300, "TSMOM": 86400},
        momentum_scalp_horizon_bars=(5, 15), momentum_scalp_bar_seconds=60,
        momentum_scalp_surge_ratio=1.5, fast_loop_decision_budget_ms=250,
        tsmom_lookback_days=(63, 126, 252), tsmom_min_history_days=260,
        modules_enabled={"TREND": True, "BREAKOUT": True, "MEAN_REVERSION": True,
                         "MOMENTUM_SCALP": True, "PAIR_DIVERGENCE": True, "TSMOM": True},
    )
    base.update(overrides)
    return SignalsConfig(**base)


def mk_state(instrument="EUR_USD", mid=1.1, spread=0.0002, session="london",
             velocity=10.0, ts=T0) -> MarketState:
    bid, ask = mid - spread / 2.0, mid + spread / 2.0
    return MarketState(
        timestamp=ts, instrument=instrument, bid=bid, ask=ask, spread=ask - bid,
        mid=mid, volume=1.0, order_book_depth=deep_freeze({"bids": (), "asks": ()}),
        tick_velocity=velocity, session=session, macro_events_imminent=False,
        ingest_ts=ts, is_stale=False, raw=deep_freeze({}),
    )


def mk_regime(regime=RegimeType.STRONG_TREND_UP, vol=VolClass.HIGH,
              liq=LiqState.DEEP, tradeable=True, instrument="EUR_USD") -> RegimeContext:
    return RegimeContext(
        regime=regime, trend_direction=1, volatility_class=vol, liquidity_state=liq,
        tradeable=tradeable, regime_stability_score=0.9,
        estimated_half_life_seconds=600, confidence=0.9, timestamp=T0,
        instrument=instrument, inputs_snapshot=MappingProxyType({}),
    )


def make_agon(tmp_path, cfg: SignalsConfig | None = None, pairs=None,
              median_velocity: float = 10.0) -> tuple[AGON, CapturingLogger, ProvenanceStore]:
    from pathlib import Path

    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    log = CapturingLogger()
    store = ProvenanceStore(tmp_path / "provenance.db", 90, log)
    register_canonical(store, T0)
    agon = AGON(
        cfg or signals_cfg(),
        pairs if pairs is not None else PAIR_RELS,
        store,
        lambda inst, sess, kind: median_velocity,
        log,
    )
    return agon, log, store


def feed_mids(agon: AGON, instrument: str, mids) -> None:
    """v2.11 bars: one tick per 60s bucket, plus a final bucket-advancing tick so
    every mid becomes a CLOSED bar close — window closes == mids exactly."""
    from datetime import timedelta

    for i, m in enumerate(mids):
        agon.observe(mk_state(instrument=instrument, mid=m,
                              ts=T0 + timedelta(seconds=60 * i)))
    agon.observe(mk_state(instrument=instrument, mid=mids[-1],
                          ts=T0 + timedelta(seconds=60 * len(mids))))


def feed_daily(agon: AGON, instrument: str, closes) -> None:
    for c in closes:
        agon.observe_daily_close(instrument, c)


def feed_pair(agon: AGON, inst_a: str, a_mids, inst_b: str, b_mids) -> None:
    """Interleaved per-bucket ticks: both legs bar on the SHARED bar clock, so the
    GAP-0047 joint window gets one aligned sample per bucket (v2.11 strong form)."""
    from datetime import timedelta

    for i, (ma, mb) in enumerate(zip(a_mids, b_mids)):
        ts = T0 + timedelta(seconds=60 * i)
        agon.observe(mk_state(instrument=inst_a, mid=ma, ts=ts))
        agon.observe(mk_state(instrument=inst_b, mid=mb, ts=ts))
    ts = T0 + timedelta(seconds=60 * len(a_mids))
    agon.observe(mk_state(instrument=inst_a, mid=a_mids[-1], ts=ts))
    agon.observe(mk_state(instrument=inst_b, mid=b_mids[-1], ts=ts))


# ------------------- empirically tuned trigger series ------------------------- #

def trend_cross_up_mids(n_flat: int = 80) -> list[float]:
    """Gentle downdrift then a rise with small pullbacks (keeps RSI below the
    overbought filter), truncated exactly at the EMA5/20 up-cross so the cross
    lands on the LAST tick (found numerically)."""
    from core.optimizer.fitness import ema_series

    mids = [1.1 - i * 0.0003 for i in range(n_flat)]  # real downtrend: EMA5 well under EMA20
    step = 0
    while True:
        delta = -0.00035 if step % 3 == 2 else 0.0004  # two up, one down: RSI stays moderate
        mids.append(mids[-1] + delta)
        step += 1
        f, s = ema_series(mids, 5), ema_series(mids, 20)
        if f[-2] <= s[-2] and f[-1] > s[-1]:
            return mids
        if len(mids) > n_flat + 80:
            raise AssertionError("fixture failed to cross")


def breakout_up_mids() -> list[float]:
    """A tight 40-tick range then a decisive pop above the channel."""
    base = [1.1 + (0.00005 if i % 2 else -0.00005) for i in range(60)]
    base.append(1.1020)  # far beyond channel_high + threshold*ATR
    return base


def meanrev_low_mids() -> list[float]:
    """A tall shoulder then a drop to a stalling low: z <= -1.5 (the shoulder
    dominates the 20-window mean) while RSI recovers >= 5 points off its trough
    during the stall — the §6.3 divergence gate."""
    mids = [1.1 + (0.00003 if i % 2 else -0.00003) for i in range(30)]  # shoulder
    mids += [1.1 - 0.002 * (i + 1) for i in range(2)]   # sharp drop to 1.096
    low = mids[-1]
    mids += [low + 0.00006 * (i + 1) for i in range(4)]  # stalling recovery at the low
    return mids


def tsmom_series(votes: str = "all_up") -> list[float]:
    """Daily closes: 'all_up' = 3-of-3 agreement; 'two_up' = 2-of-3 (r252 down);
    'split' = zero-sum (no signal)."""
    if votes == "all_up":
        return [1.0 + 0.001 * i for i in range(300)]
    if votes == "two_up":
        down = [1.6 - 0.6 * i / 240 for i in range(240)]   # long decline
        up = [down[-1] + 0.005 * i for i in range(1, 61)]  # strong 60-day recovery
        return down + up
    if votes == "split":
        flat = [1.2] * 300
        return flat  # zero returns on all horizons -> total 0 -> no signal
    raise ValueError(votes)


def pair_divergence_series() -> tuple[list[float], list[float]]:
    """Two anti-correlated legs (mirror waves) whose spread s = logA + logB is
    stable, then a joint move that blows the spread z past 2 while the trailing
    correlation window still shows coupling."""
    import math

    a, b = [], []
    for i in range(120):
        wave = 0.002 * math.sin(i / 3.0)
        a.append(1.10 + wave)
        b.append(1.10 - wave)   # mirrored: log-returns strongly negative-corr
    for i in range(2):          # divergence: both legs rise together (small ticks —
        a.append(a[-1] + 0.0004)  # the spread sd is tiny, so z blows out while the
        b.append(b[-1] + 0.0004)  # 50-return correlation window stays coupled)
    return a, b
