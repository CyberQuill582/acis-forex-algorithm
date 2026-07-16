"""The v1 canonical module provenance (ACIS-04 §6 / ACIS-11 §4 / master §5.6).

Every v1 AGON module's citation, claimed inefficiency, persistence argument,
and falsifier — the reading list in code. Registration is idempotent-by-boot:
`register_canonical` registers whichever ids are missing.
"""

from __future__ import annotations

from datetime import datetime

from core.signals.provenance import ProvenanceRecord, ProvenanceStore
from core.signals.signal_types import StrategyType

STRATEGY_IDS: dict[StrategyType, str] = {
    StrategyType.TREND: "trend_following_v1",
    StrategyType.BREAKOUT: "breakout_v1",
    StrategyType.MEAN_REVERSION: "mean_reversion_v1",
    StrategyType.MOMENTUM_SCALP: "momentum_scalp_v1",
    StrategyType.PAIR_DIVERGENCE: "pair_divergence_v1",
    StrategyType.TSMOM: "tsmom_slow_v1",
}

_CANON: list[tuple[StrategyType, str, str, str, str]] = [
    (StrategyType.TREND,
     "Wilder, New Concepts in Technical Trading Systems (1978, ADX); classic dual-MA "
     "trend following per the CTA canon",
     "serial correlation of directional moves in trending FX regimes",
     "herding + slow diffusion of macro information keeps trends underreacted-to",
     "falsified if 12-month rolling net expectancy < 0 in its gated regimes"),
    (StrategyType.BREAKOUT,
     "Donchian channel breakout (Donchian, 1960s; Turtle rules as published by Faith, "
     "Way of the Turtle, 2007)",
     "post-compression range expansion continues in the break direction",
     "stop-clustering beyond range extremes fuels continuation after a genuine break",
     "falsified if false-break rate makes 12-month net expectancy < 0 despite the "
     "close-beyond filter"),
    (StrategyType.MEAN_REVERSION,
     "Bollinger, Bollinger on Bollinger Bands (2001); RSI divergence per Wilder (1978)",
     "overshoot beyond 2-sigma in ranging regimes reverts to the local mean",
     "liquidity provision & inventory effects fade transient order-flow extremes "
     "when no trend is in force",
     "falsified if reversion hit-rate at the evolved z-entry drops below breakeven "
     "net of costs over a quarter"),
    (StrategyType.MOMENTUM_SCALP,
     "microstructure momentum lineage: short-horizon continuation after volume/velocity "
     "surprise (lineage:trend_following_v1, adapted to the 1-minute bar per GAP-0009)",
     "tick-velocity surges precede short continuation bursts in deep-liquidity trends",
     "latency of the broader market's reaction to a burst leaves 5-15 minutes of drift",
     "falsified if C9 net-of-costs expectancy at the 5-15 minute horizon is <= 0 in "
     "phase-11 raw evaluation (the most cost-sensitive module — no indulgence)"),
    (StrategyType.PAIR_DIVERGENCE,
     "Gatev, Goetzmann & Rouwenhorst, Pairs Trading (RFS 2006); Vidyamurthy, "
     "Pairs Trading: Quantitative Methods (2004)",
     "temporary decoupling of historically coupled FX pairs reverts",
     "shared macro drivers (common currencies, correlated economies) restore coupling "
     "after idiosyncratic order-flow shocks",
     "falsified if declared-pair coupling (rolling correlation at the declared window) "
     "breaks persistently or reversion PnL net of costs < 0 over the comparison window"),
    (StrategyType.TSMOM,
     "Moskowitz, Ooi & Pedersen, Time Series Momentum (JFE 2012); century evidence "
     "1880-2016 (Sharpe ~0.4 every decade, crisis-positive) — v2.9 verified benchmark",
     "12-month-scale continuation of asset-class trends across instruments",
     "slow-moving capital, hedging pressure and behavioural anchoring sustain "
     "multi-month drift; the effect has persisted for a century of data",
     "falsified if the 3-horizon agreement signal's rolling 24-month net Sharpe < 0 "
     "(far below the published benchmark) on its traded instruments"),
]


def register_canonical(store: ProvenanceStore, now: datetime) -> None:
    for stype, citation, inefficiency, persists, falsifier in _CANON:
        sid = STRATEGY_IDS[stype]
        if not store.is_registered(sid):
            store.register(ProvenanceRecord(
                strategy_id=sid, citation=citation, claimed_inefficiency=inefficiency,
                why_it_persists=persists, falsifier=falsifier, registered_at=now,
            ))
