"""GAP-P12D-38 — the "79% zero-duration trades" were never trades: the minimal reproduction.

Two facts, each pinned here, produced the finding:
  1. On a synthetic tape every tick is 20 s after the last, so the factory's 10 s tick-velocity
     window always holds exactly one tick: velocity == its own session median, the surge ratio
     is exactly 1.0, and MOMENTUM_SCALP (ratio >= momentum_scalp_surge_ratio, schema-floored
     above 1) can NEVER fire on any synthetic market. Its population is empty in every run.
     (A second, independent barrier: at ratio 1.0 its conviction clamp01(ratio / 3) = 0.333 is
     under conviction_discard, whose stageable floor is 0.45. Loosening the gate alone is an
     equivalent mutant; only removing both lets it fire, which this test catches.)
  2. `metrics._avg_duration` reported an EMPTY population's mean as 0.0 — the same number a
     population of genuinely zero-duration trades would give. A finder read the empty scalp
     carve-out as ~1,598 zero-duration trades. The mean of nothing is now NaN (null in JSON).
"""

from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from config.schemas import load_config
from core.regime.regime_types import LiqState, RegimeType
from core.signals.agon import AGON
from core.signals.canonical import register_canonical
from core.signals.provenance import ProvenanceStore
from core.signals.signal_types import StrategyType
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.metrics import ClosedTrade, compute_metrics
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket
from tests.backtest.tick_stream import build_factory, market_states
from tests.optimizer_fixtures import CapturingLogger
from tests.signals_fixtures import make_paramset, mk_regime

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
START = datetime(2014, 1, 6, tzinfo=UTC)


def test_momentum_scalp_can_never_fire_on_a_uniform_synthetic_tape(tmp_path) -> None:
    cfg = load_config(ROOT / "config")
    m = SyntheticMarket(MarketSpec("planted", START, 7, (("EUR_USD", 1.10),)))
    factory = build_factory(cfg, ["EUR_USD"])
    store = ProvenanceStore(tmp_path / "provenance.db", cfg.system.provenance.revalidation_cadence_days,
                            CapturingLogger())
    register_canonical(store, START)

    def agon() -> AGON:          # wired exactly as build_paper_loop wires it
        return AGON(cfg.system.signals, cfg.instruments.pair_relationships, store,
                    lambda inst, sess, kind: factory.session_median(inst, sess, kind) or 0.0,
                    CapturingLogger())

    real, surged = agon(), agon()
    regime = mk_regime(RegimeType.STRONG_TREND_UP, liq=LiqState.DEEP)   # the scalp's gate is open
    params = make_paramset()
    fired = {"real": 0, "surged": 0}
    ratios = set()
    states = market_states(cfg=cfg, loader=BacktestDataLoader({m.name: m}, CapturingLogger()),
                           factory=factory, source=m.name, instruments=["EUR_USD"],
                           start=START, end=START + timedelta(hours=4))
    for st in states:
        median = factory.session_median("EUR_USD", st.session, "velocity")
        if median is not None:
            ratios.add(st.tick_velocity / median)
        fast = dataclasses.replace(st, tick_velocity=st.tick_velocity * 2)  # the SAME bars, surging
        for name, a, s in (("real", real, st), ("surged", surged, fast)):
            a.observe(s)
            sigs = a.generate(s, regime, params, s.timestamp)
            fired[name] += sum(sig.strategy_type is StrategyType.MOMENTUM_SCALP for sig in sigs)
    assert ratios == {1.0}                                     # pinned, every tick
    assert cfg.system.signals.momentum_scalp_surge_ratio > 1.0
    assert fired["real"] == 0
    assert fired["surged"] > 0                                 # the module is alive, the tape is not


def _trade(minutes: float, strategy: str) -> ClosedTrade:
    t0 = datetime(2026, 1, 6, 10, tzinfo=UTC)
    return ClosedTrade(entry_ts=t0, exit_ts=t0 + timedelta(minutes=minutes), pnl=Decimal("1"),
                       strategy_type=strategy)


def _metrics(trades):
    eq = [(datetime(2026, 1, 5, tzinfo=UTC), Decimal("10000"))]
    return compute_metrics(trades=trades, equity_curve=eq, rollover_marks=[], spx_closes={},
                           periods_per_year=252)


def test_an_empty_carve_out_has_no_mean_duration_never_zero() -> None:
    m = _metrics([_trade(60, "TREND")])
    assert math.isnan(m.scalp_avg_duration_s) and math.isnan(m.tsmom_avg_duration_s)
    assert m.as_dict()["scalp_avg_duration_s"] is None          # null in every report json
    zero = _metrics([_trade(60, "TREND"), _trade(0, "MOMENTUM_SCALP")])
    assert zero.scalp_avg_duration_s == 0.0                      # a REAL zero is still visible
    empty_band = _metrics([_trade(30, "TSMOM")])
    assert math.isnan(empty_band.avg_trade_duration_s)
