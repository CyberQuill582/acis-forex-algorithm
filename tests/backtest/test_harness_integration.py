"""Phase-11 integration: the harness drives the REAL engine (ACIS-09 §14, C-BT-3).

Reuses the phase-7 organic composition (`make_loop` = the real NVMA/AGON/Governor
from real config) to prove the backtest exercises the actual layers — not a
re-implementation — and produces a per-account `ValidationReport`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from config.account_doctrine import guardrail_hash
from core.governor.capital_governor import CapitalGovernor
from core.signals.agon import AGON
from core.regime.nvma import NVMAEngine
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.walk_forward import Fold
from tests.integration.test_paper_trading_pipeline import (T0, flat_portfolio,
                                                           flat_ticks, make_loop)
from tests.optimizer_fixtures import TEST_COSTS


def _states(factory, n=250):
    """Build real MarketStates through the real §3 factory (interleaved so the
    session medians warm as they would live)."""
    out = []
    for raw in flat_ticks(n):
        res = factory.build(raw)
        if res.state is not None:
            out.append(res.state)
    return out


def _two_folds(states):
    """Two test windows over 60-s ticks, with a 10-tick gap between them. Each fold's
    declared training ends 6 minutes before its first test tick, clearing the 300-s max
    hold (the GAP-SP12E-03 embargo). Training windows are not replayed (GAP-P12D-18)."""
    def fold(i, test):
        first = test[0].timestamp
        return FoldData(Fold(i, first - timedelta(days=1), first - timedelta(minutes=6), first,
                             test[-1].timestamp), test)
    return [fold(0, states[:120]), fold(1, states[130:])]


def test_harness_drives_real_engine_and_produces_report(tmp_path, acis_config, factory) -> None:
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    # C-BT-3: the harness composes the REAL layer classes, not reimplementations
    assert isinstance(loop.nvma, NVMAEngine)
    assert isinstance(loop.agon, AGON)
    assert isinstance(loop.governor, CapitalGovernor)

    states = _states(factory)
    folds = _two_folds(states)
    gh = guardrail_hash(acis_config.guardrails)
    bt = Backtest(account="dev_paper", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=300)

    report = bt.run(loop=loop, folds=folds, evolve_fn=lambda lp, tr: None,
                    spx_closes={}, guardrail_hash=gh,
                    expected_guardrail_hash=gh)

    # a populated per-account report came out of the REAL engine
    assert report.account == "dev_paper"
    assert report.n_folds == 2
    assert report.fidelity_caveats                      # GAP-0001 surfaced
    assert set(report.targets_met) >= {"annual_sharpe", "max_drawdown"}
    assert isinstance(report.passed, bool)
    # the real engine actually traded (orders came out the bottom)
    assert len(loop.book.orders) > 0


def test_no_promoted_params_means_no_trades(tmp_path, acis_config, factory) -> None:
    """C-BT-3 flavour: with NO params promoted, the real ParamLibrary/NVMA gating
    makes every regime untradeable → zero orders. A change in the engine's state
    changes the backtest result — the harness is not fabricating trades."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio, regimes=())
    loop.boot(flat_portfolio())
    states = _states(factory)
    bt = Backtest(account="dev_paper", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=300)
    report = bt.run(loop=loop, folds=_two_folds(states), evolve_fn=lambda lp, tr: None,
                    spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")
    assert report.out_of_sample.n_trades == 0
    assert len(loop.book.orders) == 0


def test_relaxed_limits_flagged_invalid(tmp_path, acis_config, factory) -> None:
    """C-BT-4: a run whose guardrail hash does not match the production limits
    cannot pass — a relaxed-limit backtest can never gate live."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    states = _states(factory)
    bt = Backtest(account="dev_paper", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=300)
    report = bt.run(loop=loop, folds=_two_folds(states), evolve_fn=lambda lp, tr: None,
                    spx_closes={}, guardrail_hash="RELAXED_LIMITS",
                    expected_guardrail_hash=guardrail_hash(acis_config.guardrails))
    assert report.passed is False
