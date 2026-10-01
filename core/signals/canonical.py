"""The v1 canonical module provenance (ACIS-04 §6 / ACIS-11 §4 / master §5.6).

Every v1 AGON module's citation, claimed inefficiency, persistence argument,
and falsifier — the reading list in code. Registration is idempotent-by-boot:
`register_canonical` registers whichever ids are missing.

A record is written once (ACIS-11 §6). A correction is a NEW id whose citation names
`lineage:<parent>`; the parent stays in any store that holds it, exactly as written, as the
record of what was once declared. TSMOM is the one so far: `tsmom_slow_v1` was registered
with GAP-0073's "immaterial" note, which master v2.22 withdrew (GAP-P12D-116), so its
corrected declaration is `tsmom_slow_v2`, registered on the correction date.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.signals.provenance import ProvenanceRecord, ProvenanceStore
from core.signals.signal_types import StrategyType

STRATEGY_IDS: dict[StrategyType, str] = {
    StrategyType.TREND: "trend_following_v1",
    StrategyType.BREAKOUT: "breakout_v1",
    StrategyType.MEAN_REVERSION: "mean_reversion_v1",
    StrategyType.MOMENTUM_SCALP: "momentum_scalp_v1",
    StrategyType.PAIR_DIVERGENCE: "pair_divergence_v1",
    StrategyType.TSMOM: "tsmom_slow_v2",
}

# a corrected record registers on its correction date, not the canon's boot date
_REGISTERED = {StrategyType.TSMOM: datetime(2026, 10, 1, tzinfo=timezone.utc)}

# (type, citation, inefficiency, persistence, falsifier, declared_deviations)
# §5.6 declared-deviations law (v2.11): every departure from the cited source's
# ACTUAL method, exhaustively — an empty tuple asserts "as published".
_CANON: list[tuple[StrategyType, str, str, str, str, tuple[str, ...]]] = [
    (StrategyType.TREND,
     "Wilder, New Concepts in Technical Trading Systems (1978, ADX); classic dual-MA "
     "trend following per the CTA canon",
     "serial correlation of directional moves in trending FX regimes",
     "herding + slow diffusion of macro information keeps trends underreacted-to",
     "falsified if 12-month rolling net expectancy < 0 in its gated regimes",
     ("entry/exit parameters (EMA spans, RSI bounds, ATR stop/target multiples) "
      "are QIEA-evolved per regime, not source-published values",
      "regime-gated activation via NVMA rather than always-on",
      "signals on 1-minute bars (signal_bar_seconds), not daily charts",
      "conviction 'ADX/50' uses the close-only adx_proxy (|delta-close| as the "
      "true-range stand-in), NOT Wilder's high/low true-range ADX — GAP-0072")),
    (StrategyType.BREAKOUT,
     "Donchian channel breakout (Donchian, 1960s; Turtle rules as published by Faith, "
     "Way of the Turtle, 2007)",
     "post-compression range expansion continues in the break direction",
     "stop-clustering beyond range extremes fuels continuation after a genuine break",
     "falsified if false-break rate makes 12-month net expectancy < 0 despite the "
     "close-beyond filter",
     ("channel lookback and break threshold are QIEA-evolved, not the published "
      "20/55-day Donchian spans",
      "ATR stop/target multiples added (evolved), source uses N-day exit channels",
      "signals on 1-minute bars, not daily")),
    (StrategyType.MEAN_REVERSION,
     "Bollinger, Bollinger on Bollinger Bands (2001); RSI divergence per Wilder (1978)",
     "overshoot beyond 2-sigma in ranging regimes reverts to the local mean",
     "liquidity provision & inventory effects fade transient order-flow extremes "
     "when no trend is in force",
     "falsified if reversion hit-rate at the evolved z-entry drops below breakeven "
     "net of costs over a quarter",
     ("z-entry threshold QIEA-evolved; divergence gate uses RSI recovery off its "
      "20-window trough (ACIS-04 §6.3 exact form), not chart-pattern divergence",
      "ATR stop/target multiples added (evolved)",
      "signals on 1-minute bars")),
    (StrategyType.MOMENTUM_SCALP,
     "microstructure momentum lineage: short-horizon continuation after volume/velocity "
     "surprise (lineage:trend_following_v1, adapted to the 1-minute bar per GAP-0009)",
     "tick-velocity surges precede short continuation bursts in deep-liquidity trends",
     "latency of the broader market's reaction to a burst leaves 5-15 minutes of drift",
     "falsified if C9 net-of-costs expectancy at the 5-15 minute horizon is <= 0 in "
     "phase-11 raw evaluation (the most cost-sensitive module — no indulgence)",
     ("bespoke by lineage (not a published system): velocity-surge trigger with "
      "declared session-median baseline; 1-minute bar horizon per GAP-0009",
      "ATR stop/target multiples from the evolved ParamSet")),
    (StrategyType.PAIR_DIVERGENCE,
     "Gatev, Goetzmann & Rouwenhorst, Pairs Trading (RFS 2006); Vidyamurthy, "
     "Pairs Trading: Quantitative Methods (2004)",
     "temporary decoupling of historically coupled FX pairs reverts",
     "shared macro drivers (common currencies, correlated economies) restore coupling "
     "after idiosyncratic order-flow shocks",
     "falsified if declared-pair coupling (rolling correlation at the declared window) "
     "breaks persistently or reversion PnL net of costs < 0 over the comparison window",
     ("correlation/spread z on declared windows over 1-minute bar closes, not the "
      "published daily normalized-price distance method",
      "entry z-threshold QIEA-evolved; source uses 2 historical std devs",
      "per-leg ATR stops added; source exits on convergence/window-end only")),
    (StrategyType.TSMOM,
     "Moskowitz, Ooi & Pedersen, Time Series Momentum (JFE 2012); century evidence "
     "1880-2016 (Sharpe ~0.4 every decade, crisis-positive) — v2.9 verified benchmark "
     "(lineage:tsmom_slow_v1, its declaration corrected by GAP-P12D-116)",
     "12-month-scale continuation of asset-class trends across instruments",
     "slow-moving capital, hedging pressure and behavioural anchoring sustain "
     "multi-month drift; the effect has persisted for a century of data",
     "falsified if the 3-horizon agreement signal's rolling 24-month net Sharpe < 0 "
     "(far below the published benchmark) on its traded instruments",
     ("far disaster-stop (tsmom_disaster_stop_atr x daily ATR) added — the §8.6 "
      "safety law requires a broker-side stop on every order; published TSMOM "
      "has none. NO take-profit (faithful, v2.11)",
      "continuous signal evaluation with exit on vote flip, instead of the "
      "published calendar-monthly rebalance (scheduler lands at phase 7)",
      "position size via the Governor's C16 vol-norm + formula, not the "
      "published 40%/sigma ex-ante vol scaling",
      "3-horizon sign agreement (63/126/252d) instead of the single published "
      "12-month lookback",
      "signs RAW spot returns, not MOP 2012's excess returns, and NOT immaterially: "
      "on the repo's rates the 12-month spot and excess signs disagree on 3.0-12.1% "
      "of FX days, 2013-2025 (GAP-0073's note withdrawn by master v2.22, "
      "GAP-P12D-116; MOP's own rule is the separate member trend_mop12_v1)")),
]


def register_canonical(store: ProvenanceStore, now: datetime) -> None:
    for stype, citation, inefficiency, persists, falsifier, deviations in _CANON:
        sid = STRATEGY_IDS[stype]
        if not store.is_registered(sid):
            store.register(ProvenanceRecord(
                strategy_id=sid, citation=citation, claimed_inefficiency=inefficiency,
                why_it_persists=persists, falsifier=falsifier,
                registered_at=_REGISTERED.get(stype, now),
                declared_deviations=deviations,
            ))
