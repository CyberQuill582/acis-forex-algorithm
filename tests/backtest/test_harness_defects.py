"""Regressions for the two harness defects the 2026-09-16 research pass found (GAP-P12D-35/36).

Both were invisible to every existing test because they change *how much* a run loses, not
whether it runs: the falsification fold plan replayed graded days twice, and the book charged
less than the cost model it declares. A harness that errs in the flattering direction is worse
than none, so each defect gets a test that fails loudly if it returns.

(The harness-level positive control — a scripted edge that MUST pass every gate — lives in
`test_falsification_harness.py`; this file is only about the two defects.)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.optimizer.costs import CostModel
from tests.backtest.synthetic_grade import plan   # the shared fold plan (was scripts/falsify_engine)
from tests.backtest.book import BookState, PositionModel
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.test_harness_regressions import _FakeLoop, _ms, _order
from tests.backtest.walk_forward import Fold

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 12, tzinfo=UTC)


# ----------------------------- GAP-P12D-35: the clock never runs backwards ------------- #

def test_falsification_folds_never_overlap() -> None:
    """Each fold's warm-up is [train_end, test window start); unless successive test windows
    are separated by the embargo, that warm-up replays days the previous fold already graded."""
    folds = plan(train_days=60, test_days=30, n_folds=5)
    for earlier, later in zip(folds, folds[1:]):
        assert later.train_end >= earlier.test_end, (
            f"fold {later.index} warms up from {later.train_end}, inside fold "
            f"{earlier.index}'s graded window ending {earlier.test_end}")


def test_an_overlapping_fold_plan_raises_instead_of_replaying_backwards() -> None:
    """The invariant that would have caught GAP-P12D-35: the book is continuous across folds,
    so a fold starting before the previous one ended makes (now - entry_ts) negative, which
    silently suspends max_hold, and puts out-of-order points in the graded equity curve."""
    bt = Backtest(account="dev_paper", cost_models=defaultdict(lambda: None))
    first = T0
    fold_a = Fold(0, first - timedelta(days=737), first - timedelta(days=7),
                  first, first + timedelta(days=1))
    fold_b = Fold(1, first - timedelta(days=730), first, first + timedelta(minutes=30),
                  first + timedelta(days=2))
    folds = [
        FoldData(fold_a, [_ms(first + timedelta(minutes=i), 1.10) for i in range(5)]),
        FoldData(fold_b, [_ms(first + timedelta(minutes=30 + i), 1.10) for i in range(3)],
                 warmup_states=[_ms(first - timedelta(minutes=10), 1.10)]),
    ]
    with pytest.raises(ValueError, match="replays backwards"):
        bt.run(loop=_FakeLoop({}), folds=folds, evolve_fn=lambda lp, fd: None,
               spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")


# ----------------------------- GAP-P12D-36: the book charges the declared C8 cost ------ #

def test_the_book_charges_the_declared_c8_cost_including_the_spread() -> None:
    """master §5 C8: one cost model, both places. The book used to charge slippage and
    commission only, so the optimizer was scored in a stricter world than the engine was
    graded in, and every §14 number came out optimistic."""
    cost = CostModel(commission_per_side=0.00001, slippage_per_side=0.00002)
    model = PositionModel(costs={"EUR_USD": cost}, max_hold_s=48 * 3600)
    book, units = BookState(), Decimal("1000")
    entry = _ms(T0, 1.10)                      # the helper quotes a 0.0001 spread
    model.apply_order(_order(T0, 1, entry.mid, entry.mid * 0.99, None), entry, book,
                      "TREND", "STRONG_TREND_UP")

    exit_st = _ms(T0 + timedelta(minutes=5), 1.10)
    closed = model.close_at(book.open_by_inst["EUR_USD"], exit_st.mid,
                            exit_st.timestamp, "flat", book, exit_st.spread)

    per_side = cost.per_side_cost(entry.spread)
    assert per_side == pytest.approx(0.0001 / 2 + 0.00001 + 0.00002)
    # flat price, so the whole PnL is friction, both sides, at the DECLARED cost
    assert float(closed.pnl) == pytest.approx(-2 * per_side * float(units))
    # the spread is the dominant term: omitting it charged well under half the real cost
    assert float(closed.pnl) < -0.9 * 2 * (0.0001 / 2) * float(units)


def test_a_position_opened_through_the_book_remembers_its_entry_spread() -> None:
    cost = CostModel(commission_per_side=0.0, slippage_per_side=0.0)
    model = PositionModel(costs={"EUR_USD": cost}, max_hold_s=48 * 3600)
    book = BookState()
    entry = _ms(T0, 1.10)
    model.apply_order(_order(T0, 1, entry.mid, entry.mid * 0.99, None), entry, book, "TREND", "X")
    assert book.open_by_inst["EUR_USD"].entry_spread == pytest.approx(entry.spread)


# ------------- GAP-P12D-84: a gapped-through stop fills at the gap, never at the stop ----------- #

def _stopped_out(direction: int, stop: float, gap_mid: float):
    cost = CostModel(commission_per_side=0.0, slippage_per_side=0.0)
    model = PositionModel(costs={"EUR_USD": cost}, max_hold_s=48 * 3600)
    book = BookState()
    entry = _ms(T0, 1.1000)
    model.apply_order(_order(T0, direction, entry.mid, stop, None), entry, book, "TREND", "X")
    gap = _ms(T0 + timedelta(days=2), gap_mid)          # e.g. a weekend gap past the stop
    return model.maybe_close(book.open_by_inst["EUR_USD"], gap, book)


def test_a_long_stop_gapped_through_books_the_gap_price_not_the_stop() -> None:
    """A real venue fills a triggered stop at the first price equal to or worse than it (OANDA
    v20; backtrader). Booking the stop level on a gap understated every gap loss (GAP-P12D-84):
    here 1.0950 against a 1.0990 stop is −50 pips, not −10."""
    closed = _stopped_out(1, stop=1.0990, gap_mid=1.0950)
    # 1,000 units: gross (1.0950 − 1.1000)·1000 = −5.00, plus 0.10 round-trip spread = −5.10.
    # Booked at the stop it read −1.10: the gap loss understated almost fivefold.
    assert closed is not None and float(closed.pnl) == pytest.approx(-5.10)


def test_a_short_stop_gapped_through_books_the_gap_price_not_the_stop() -> None:
    closed = _stopped_out(-1, stop=1.1010, gap_mid=1.1060)
    # short 1,000: gross (1.1060 − 1.1000)·(−1)·1000 = −6.00, plus 0.10 spread = −6.10 (not −1.10)
    assert closed is not None and float(closed.pnl) == pytest.approx(-6.10)


def test_a_stop_touched_exactly_still_fills_at_the_stop() -> None:
    closed = _stopped_out(1, stop=1.0990, gap_mid=1.0990)
    assert closed is not None and float(closed.pnl) == pytest.approx(-1.10)
