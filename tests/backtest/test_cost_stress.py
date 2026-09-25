"""The GAP-P12D-46 cost-stress ladder: one knob, both places, and it can only hurt.

The ladder answers the question that needs no venue and no money — how much of a graded
edge is friction? — so its correctness rests on three things, each pinned here:
  1. stress multiplies the WHOLE per-side cost and can never make the world cheaper;
  2. the run's cost map is ONE map: selection (QIEA, via `evolve_fold`) and the graded book
     hold the same instances, so a run cannot select cheap and be graded expensive
     (the GAP-P12D-36 defect class, this time structurally excluded);
  3. a stressed run SAYS so in its report, so its §14 numbers can never be read as
     declared-cost ones.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.data.errors import DataQualityError
from core.optimizer.costs import CostModel
from tests.backtest.book import BookState, OpenPos, PositionModel
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.look_register import LookRegister
from tests.backtest.oos_runner import RunInputs, run_walk_forward, stress_caveat
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.test_oos_runner import _Synthetic, _folds
from tests.optimizer_fixtures import CapturingLogger, bars_from_closes, zigzag_closes
from core.regime.regime_types import RegimeType

UTC = timezone.utc
ROOT_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
DECLARED = CostModel(commission_per_side=0.00001, slippage_per_side=0.00002)


def test_stress_multiplies_the_whole_per_side_cost() -> None:
    """Not just the spread: the destination's cost is what is stressed, not one term."""
    for k in (1.0, 2.0, 3.0, 5.0):
        stressed = CostModel(commission_per_side=0.00001, slippage_per_side=0.00002, stress=k)
        assert stressed.per_side_cost(0.0002) == pytest.approx(k * DECLARED.per_side_cost(0.0002))
        assert stressed.round_trip_cost(0.0002, 0.0003) == pytest.approx(
            k * DECLARED.round_trip_cost(0.0002, 0.0003))


def test_the_declared_model_is_unchanged_by_the_knob_existing() -> None:
    """1x is bit-identical to the pre-ladder arithmetic — the ladder is additive, and a
    default run is the same run it was before."""
    assert DECLARED.per_side_cost(0.0002) == 0.0002 / 2.0 + 0.00001 + 0.00002
    assert DECLARED.stressed is False


def test_a_cheaper_than_declared_world_is_refused() -> None:
    """A knob that could flatter a run into a §14 pass is the bug; the asymmetry is enforced
    in the type, not in the caller's discipline."""
    for bad in (0.99, 0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(DataQualityError):
            CostModel(commission_per_side=0.0, slippage_per_side=0.0, stress=bad)
    with pytest.raises(DataQualityError):
        CostModel(commission_per_side=0.0, slippage_per_side=0.0, spread_floor=-0.0001)


def test_the_spread_floor_only_ever_raises_the_spread() -> None:
    """The "p95 as a constant" rung is applied as a FLOOR: on a tick already wider than the
    floor the observed spread stands, so the rung can never charge less than the tape did."""
    floored = CostModel(commission_per_side=0.0, slippage_per_side=0.0, spread_floor=0.0004)
    assert floored.per_side_cost(0.0001) == pytest.approx(0.0002)      # floor binds
    assert floored.per_side_cost(0.0009) == pytest.approx(0.00045)     # observed stands
    assert floored.stressed is True


def test_the_book_charges_exactly_the_stressed_friction() -> None:
    """A closed trade at k× costs the declared trade plus (k−1)× its round-trip friction —
    nothing else about the fill moves."""
    entry_ts = datetime(2024, 1, 2, 12, tzinfo=UTC)
    exit_ts = entry_ts + timedelta(minutes=20)

    def close(cost: CostModel) -> Decimal:
        book = BookState(last_price={"EUR_USD": 1.1050})
        pos = OpenPos(instrument="EUR_USD", direction=1, entry_price=1.1000,
                      size_units=Decimal("100000"), entry_ts=entry_ts, stop_loss=1.0950,
                      take_profit=None, strategy_type="TREND", entry_spread=0.00020)
        return PositionModel(costs={"EUR_USD": cost}, max_hold_s=48 * 3600).close_at(
            pos, 1.1050, exit_ts, "target", book, exit_spread=0.00030).pnl

    base = close(DECLARED)
    for k in (2.0, 3.0, 5.0):
        stressed_cost = CostModel(commission_per_side=0.00001, slippage_per_side=0.00002, stress=k)
        extra = Decimal(str((k - 1.0) * DECLARED.round_trip_cost(0.00020, 0.00030))) * Decimal("100000")
        assert close(stressed_cost) == pytest.approx(base - extra)


def test_a_stressed_run_declares_itself_and_a_declared_run_stays_silent(acis_config, tmp_path) -> None:
    common = dict(cfg=acis_config, account="dev_paper", source="synthetic",
                  loader=None, cache=None, folds=(), spx_closes={}, financing=None,
                  work_dir=tmp_path, logger=None, look=None)
    assert stress_caveat(RunInputs(**common)) == ()
    caveat, = stress_caveat(RunInputs(**common, cost_stress=2.0))
    assert "COST-STRESS RUN" in caveat and "2.0" in caveat and "NOT a venue calibration" in caveat
    floored, = stress_caveat(RunInputs(**common, spread_floor=0.0004))
    assert "spread floor" in floored


def test_selection_and_grading_hold_the_same_stressed_cost_map(tmp_path, acis_config, monkeypatch) -> None:
    """The GAP-P12D-36 regression, generalised: whatever the run charges the book, it also
    charges selection — the SAME objects, not merely equal ones."""
    import tests.backtest.oos_runner as runner

    seen: dict[str, object] = {}
    real_backtest, real_evolve = runner.Backtest, runner.evolve_fold

    def spy_backtest(**kw):
        seen["book"] = kw["cost_models"]
        return real_backtest(**kw)

    def spy_evolve(loop, fd, **kw):
        seen["selection"] = kw["costs"]
        return real_evolve(loop, fd, **kw)

    monkeypatch.setattr(runner, "Backtest", spy_backtest)
    monkeypatch.setattr(runner, "evolve_fold", spy_evolve)

    folds = _folds()
    cache = LabelledBarCache(tmp_path / "labels",
                             LabelSpec.for_config(acis_config, "synthetic", datetime(2014, 1, 1, tzinfo=UTC)))
    bars = bars_from_closes(zigzag_closes(600), RegimeType.STRONG_TREND_UP)
    shifted = tuple(b.__class__(ts=b.ts.replace(year=2014, month=2, day=3), open=b.open, high=b.high,
                                low=b.low, close=b.close, spread=b.spread, regime=b.regime) for b in bars)
    for instrument in sorted(acis_config.instruments.enabled):
        cache.write(instrument, 2014, shifted)

    log = CapturingLogger()
    look = LookRegister(tmp_path / "looks").register(
        cfg=acis_config, source=_Synthetic(), instruments=sorted(acis_config.instruments.enabled), folds=folds,
        family="test:cost-stress", account="dev_paper", cost_stress=3.0, git=("test", False))
    report = run_walk_forward(RunInputs(
        cfg=acis_config, account="dev_paper", source="synthetic",
        loader=BacktestDataLoader({"synthetic": _Synthetic()}, log), cache=cache, folds=folds,
        spx_closes={}, financing=None, work_dir=tmp_path / "engine", logger=log, look=look, cost_stress=3.0))

    assert seen["book"] is seen["selection"]
    assert all(c.stress == 3.0 for c in seen["book"].values())
    assert any("COST-STRESS RUN" in c for c in report.fidelity_caveats)


def test_the_ladder_verdict_separates_no_edge_from_fragile_from_survives() -> None:
    """The verdict is the entry's bar in one line, and the three cases are not the same
    finding: "fails at 1x already" says the venue question is moot, "met at 1x but not at 2x"
    says turnover decides it, and only the third says the edge is real enough to price."""
    import sys
    sys.path.insert(0, str(ROOT_SCRIPTS))
    from cost_stress_ladder import rung_tag, verdict

    rows = [{"cost_stress": 1.0, "spread_floor": 0.0, "passed": False, "net_pnl": "10.0"},
            {"cost_stress": 2.0, "spread_floor": 0.0, "passed": False, "net_pnl": "-3.0"}]
    assert verdict(rows, 2.0).startswith("NO EDGE TO STRESS")
    rows[0]["passed"] = True
    assert verdict(rows, 2.0).startswith("FRAGILE")
    rows[1]["passed"] = True
    assert verdict(rows, 2.0).startswith("SURVIVES")
    assert verdict(rows[:1], 2.0).startswith("no verdict")
    assert rung_tag(2.0, 0.0) == "rung_2x" and rung_tag(1.0, 0.0004) == "rung_1x_floor0.0004"


def test_a_ratio_of_two_losses_is_never_reported_as_a_fraction_kept() -> None:
    """The 2026-09-17 run printed "115% of it left at 2x" for a 1x result that was already a
    LOSS — 115% of a loss means the loss GREW by 15%, the opposite of what "left" reads as.
    A negative 1x result is stated as a deepening, never as a share retained."""
    import sys
    sys.path.insert(0, str(ROOT_SCRIPTS))
    from cost_stress_ladder import verdict

    rows = [{"cost_stress": 1.0, "spread_floor": 0.0, "passed": False, "net_pnl": "-147.84"},
            {"cost_stress": 2.0, "spread_floor": 0.0, "passed": False, "net_pnl": "-170.62"}]
    line = verdict(rows, 2.0)
    assert "ALREADY A LOSS" in line and "deepens it by a further 22.78" in line
    assert "% of it left" not in line


def test_the_decomposition_separates_friction_from_direction() -> None:
    """The number the ladder exists for: net PnL is linear in the multiplier for a fixed trade
    set, so the slope over the rungs recovers the friction charged at 1x — and with it whether
    the result is priced by cost or by direction. A planted market that loses 89% of its money
    on direction cannot be rescued by any venue."""
    import sys
    sys.path.insert(0, str(ROOT_SCRIPTS))
    from cost_stress_ladder import decompose

    # gross +100, friction -30 per 1x: net = 100 - 30k
    rows = [{"cost_stress": k, "spread_floor": 0.0, "net_pnl": str(100.0 - 30.0 * k)}
            for k in (1.0, 2.0, 3.0, 5.0)]
    d = decompose(rows)
    assert d["friction_per_1x"] == pytest.approx(30.0)
    assert d["gross_pnl_1x"] == pytest.approx(100.0)
    assert d["friction_share_of_1x"] == pytest.approx(30.0 / 70.0)
    assert decompose(rows[:1]) == {}
