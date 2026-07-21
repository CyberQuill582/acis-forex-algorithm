"""Phase-11 dual-audit regression tests for the harness position/runtime layer.

Each test pins ONE audit fix as an observable postcondition, driving `Backtest`
with a synthetic scripted loop (so the trade sequence is deterministic and the
fix — not the real engine's stochastics — is what is under test):

  · GAP-P11I-03 / P11E-02 — the OOS book is ONE continuous curve across folds
    (realised PnL and trades accumulate; the book never resets per fold);
  · GAP-P11I-01 — the graded `period` is DERIVED from the real OOS data span,
    never a caller's Fold-date claim;
  · GAP-P11I-02 / C-BT-7 — the §9.5 rulebook is ACTIVE during the run: a
    min-hold / weekend-holding breach populates `rule_violations` and fails the
    run — and grading is PER ACCOUNT (a second account with a laxer rulebook
    over the SAME trades is graded independently);
  · GAP-P11E-04 — overnight carry (triple-swap Wednesday) is charged on a held
    position when a daily_swap rate is supplied.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from config.schemas import AccountRulebook, NewsRules
from core.data.normaliser import MarketState
from core.governor.portfolio_types import SizedOrder
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import TEST_COSTS

_UTC = timezone.utc
_INST = "EUR_USD"


def _ms(ts: datetime, mid: float) -> MarketState:
    half = 0.00005
    bid, ask = mid - half, mid + half
    return MarketState(
        timestamp=ts, instrument=_INST, bid=bid, ask=ask, spread=ask - bid,
        mid=(bid + ask) / 2.0, volume=100.0,
        order_book_depth=MappingProxyType({}), tick_velocity=1.0, session="london",
        macro_events_imminent=False, ingest_ts=ts, is_stale=False,
        raw=MappingProxyType({}))


def _order(ts: datetime, direction: int, entry: float, stop: float,
           target: float | None) -> SizedOrder:
    return SizedOrder(
        order_id=f"o{ts.isoformat()}", signal_id="s", instrument=_INST,
        direction=direction, size_units=Decimal("1000"), entry_price=entry,
        stop_loss=stop, take_profit=target, reason="test",
        factors_snapshot=MappingProxyType({"strategy_type": "TREND"}),
        sized_at=ts, param_set_id="p", group_id=None, action="open")


class _FakeBook:
    def __init__(self) -> None:
        self.orders: list[SizedOrder] = []


class _FakeLoop:
    """A scripted loop: at each ticked timestamp it emits any orders scheduled for
    that instant, appending them to the accumulating book exactly as the real loop
    does (the harness reads `book.orders[seen:]`)."""

    def __init__(self, script: dict[datetime, list[SizedOrder]]) -> None:
        self.book = _FakeBook()
        self._script = script

    def on_state(self, st: MarketState) -> None:
        for o in self._script.get(st.timestamp, ()):
            self.book.orders.append(o)


def _rulebook(**over) -> AccountRulebook:
    base = dict(platform="dev", news=NewsRules(restricted=False),
                min_hold_seconds=0, max_lots=None, weekend_holding_allowed=True,
                drawdown_rules=[])
    base.update(over)
    return AccountRulebook(**base)


def _noop(loop, train) -> None:
    return None


# -- continuous equity + trades accumulate across folds (P11I-03 / P11E-02) --- #

def test_oos_book_is_continuous_across_folds() -> None:
    """Two separate OOS folds each realise a winning trade. Because the OOS book
    persists across folds, BOTH trades land in the graded record — a per-fold
    reset would keep only the last fold's trade."""
    d0 = datetime(2026, 1, 5, 10, tzinfo=_UTC)               # Monday, fold 0
    d1 = datetime(2026, 1, 12, 10, tzinfo=_UTC)              # Monday, fold 1
    # each fold: open long @1.10, tick up to target 1.11 (closes for +profit)
    f0_states = [_ms(d0, 1.10), _ms(d0 + timedelta(minutes=1), 1.11)]
    f1_states = [_ms(d1, 1.10), _ms(d1 + timedelta(minutes=1), 1.11)]
    script = {d0: [_order(d0, 1, 1.10, 1.05, 1.11)],
              d1: [_order(d1, 1, 1.10, 1.05, 1.11)]}
    loop = _FakeLoop(script)
    folds = [FoldData(Fold(0, d0, d0, d0, d0), (), f0_states),
             FoldData(Fold(1, d1, d1, d1, d1), (), f1_states)]
    bt = Backtest(account="acc", cost_model=TEST_COSTS)
    r = bt.run(loop=loop, folds=folds, evolve_fn=_noop, spx_returns=[0.0] * 8,
               guardrail_hash="GH", expected_guardrail_hash="GH")
    assert r.out_of_sample.n_trades == 2                     # BOTH folds' trades kept
    assert r.out_of_sample.win_rate == 1.0                   # both were winners


# -- graded period is derived from the OOS data span (P11I-01) ---------------- #

def test_period_is_derived_from_oos_data_not_fold_claim() -> None:
    """The Fold carries deliberately BOGUS dates (all = d0); the graded period must
    still be the true span of the OOS equity samples across both folds."""
    d0 = datetime(2026, 1, 5, 10, tzinfo=_UTC)
    d1 = datetime(2026, 3, 9, 10, tzinfo=_UTC)
    f0 = [_ms(d0, 1.10)]
    f1 = [_ms(d1, 1.10)]
    bogus = Fold(0, d0, d0, d0, d0)                          # dates the harness must ignore
    folds = [FoldData(bogus, (), f0), FoldData(bogus, (), f1)]
    bt = Backtest(account="acc", cost_model=TEST_COSTS)
    r = bt.run(loop=_FakeLoop({}), folds=folds, evolve_fn=_noop,
               spx_returns=[0.0] * 4, guardrail_hash="GH", expected_guardrail_hash="GH")
    assert r.period[0] == d0 and r.period[1] == d1           # true data span, not the claim


# -- §9.5 rulebook is active + per-account (P11I-02 / C-BT-7) ------------------ #

def test_min_hold_violation_populates_rule_violations_and_fails() -> None:
    """A trade held below the account's min-hold is a §9.5 breach: it surfaces in
    `rule_violations` and forces passed=False — the rulebook is enforced during
    the run, not merely declared."""
    d0 = datetime(2026, 1, 5, 10, tzinfo=_UTC)
    # open @1.10, close on target 1.11 one minute later — 60s hold
    states = [_ms(d0, 1.10), _ms(d0 + timedelta(minutes=1), 1.11)]
    script = {d0: [_order(d0, 1, 1.10, 1.05, 1.11)]}
    strict = _rulebook(min_hold_seconds=3600)                # 1h min hold
    bt = Backtest(account="strict", cost_model=TEST_COSTS, rulebook=strict)
    r = bt.run(loop=_FakeLoop(script), folds=[FoldData(Fold(0, d0, d0, d0, d0), (), states)],
               evolve_fn=_noop, spx_returns=[0.0] * 4,
               guardrail_hash="GH", expected_guardrail_hash="GH")
    assert "min_hold" in r.rule_violations
    assert r.passed is False


def test_rule_enforcement_is_per_account() -> None:
    """The SAME 60s trade is a violation for a strict account and clean for a lax
    one — grading is per account (C-BT-7), not a global verdict."""
    d0 = datetime(2026, 1, 5, 10, tzinfo=_UTC)
    states = [_ms(d0, 1.10), _ms(d0 + timedelta(minutes=1), 1.11)]
    script = {d0: [_order(d0, 1, 1.10, 1.05, 1.11)]}
    fold = [FoldData(Fold(0, d0, d0, d0, d0), (), states)]

    strict = Backtest(account="strict", cost_model=TEST_COSTS,
                      rulebook=_rulebook(min_hold_seconds=3600))
    lax = Backtest(account="lax", cost_model=TEST_COSTS,
                   rulebook=_rulebook(min_hold_seconds=0))
    common = dict(evolve_fn=_noop, spx_returns=[0.0] * 4,
                  guardrail_hash="GH", expected_guardrail_hash="GH")
    r_strict = strict.run(loop=_FakeLoop(dict(script)), folds=fold, **common)
    r_lax = lax.run(loop=_FakeLoop(dict(script)), folds=fold, **common)
    assert "min_hold" in r_strict.rule_violations
    assert r_lax.rule_violations == ()                       # independent verdict


# -- overnight carry is charged on a held position (P11E-04) ------------------- #

def test_overnight_carry_reduces_pnl_of_a_held_position() -> None:
    """With a negative daily_swap, a position held across a 22:00-UTC rollover is
    charged carry — enough carry turns an otherwise-winning round-trip into a LOSS
    (the carry the tick model would otherwise ignore, GAP-P11E-04). Held Tue→Wed
    covers two nights and the Wed night is triple-swap."""
    d0 = datetime(2026, 1, 6, 20, tzinfo=_UTC)               # Tue, before 22:00 rollover
    exit_ts = datetime(2026, 1, 8, 10, tzinfo=_UTC)          # Thu — spans Tue + Wed nights
    states = [_ms(d0, 1.10), _ms(exit_ts, 1.11)]             # open, then close on target
    script = {d0: [_order(d0, 1, 1.10, 1.05, 1.11)]}
    fold = [FoldData(Fold(0, d0, d0, d0, d0), (), states)]
    common = dict(folds=fold, evolve_fn=_noop, spx_returns=[0.0] * 4,
                  guardrail_hash="GH", expected_guardrail_hash="GH")

    no_carry = Backtest(account="a", cost_model=TEST_COSTS)
    # gross on the round-trip is +10.0 (0.01 × 1000 units); a −5.0/night swap over
    # Tue(1×)+Wed(3×) = 4 nights → −20.0 carry, flipping the trade to a net loss.
    with_carry = Backtest(account="a", cost_model=TEST_COSTS,
                          daily_swap={_INST: Decimal("-5.0")})
    r0 = no_carry.run(loop=_FakeLoop(dict(script)), **common)
    r1 = with_carry.run(loop=_FakeLoop(dict(script)), **common)
    assert r0.out_of_sample.n_trades == r1.out_of_sample.n_trades == 1
    assert r0.out_of_sample.win_rate == 1.0                  # profitable without carry
    assert r1.out_of_sample.win_rate == 0.0                  # carry turned it into a loss


# -- intraday drawdown is captured, not EOD-understated (P11I-04) -------------- #

def test_intraday_drawdown_is_not_understated_by_daily_sampling() -> None:
    """An open position dips hard intraday and recovers before the next daily
    equity sample. A daily-sampled max-drawdown would report ~0; the intraday
    high-water tracking must surface the real excursion (the §13 trailing-DD
    'EOD approximation must fail' condition applied to the harness's own equity)."""
    d0 = datetime(2026, 1, 5, 8, tzinfo=_UTC)
    # open long @1.10 at 08:00, price craters to 1.05 at 12:00, recovers to 1.10
    # by 16:00 — all on the SAME calendar day, so daily sampling sees only ~flat.
    states = [_ms(d0, 1.10),
              _ms(d0.replace(hour=12), 1.0550),               # deep intraday dip
              _ms(d0.replace(hour=16), 1.10)]                 # recovered by EOD
    script = {d0: [_order(d0, 1, 1.10, 1.00, None)]}          # wide stop, no target
    bt = Backtest(account="a", cost_model=TEST_COSTS)
    r = bt.run(loop=_FakeLoop(script),
               folds=[FoldData(Fold(0, d0, d0, d0, d0), (), states)],
               evolve_fn=_noop, spx_returns=[0.0] * 4,
               guardrail_hash="GH", expected_guardrail_hash="GH")
    # 1000 units × 0.045 dip on a ~10000 NAV ≈ 0.45% intraday DD — must NOT be 0
    assert r.out_of_sample.max_drawdown_pct > 0.3


# -- every open position marked each day, not only the ticked one (P11E-03) ---- #

def test_all_open_positions_marked_each_day() -> None:
    """A two-instrument book: only USD_JPY ticks on the sampling day, but EUR_USD
    is deep underwater. The daily equity mark must reflect BOTH legs (marked off
    each instrument's last-seen price), so the drawdown is visible even though
    EUR_USD did not tick that day (the frozen-at-entry bug would hide it)."""
    other = "USD_JPY"

    def _ms2(ts, inst, mid):
        half = 0.005 if inst == other else 0.00005
        bid, ask = mid - half, mid + half
        return MarketState(
            timestamp=ts, instrument=inst, bid=bid, ask=ask, spread=ask - bid,
            mid=(bid + ask) / 2.0, volume=100.0, order_book_depth=MappingProxyType({}),
            tick_velocity=1.0, session="london", macro_events_imminent=False,
            ingest_ts=ts, is_stale=False, raw=MappingProxyType({}))

    d0 = datetime(2026, 1, 5, 8, tzinfo=_UTC)
    # Day 1: open EUR_USD long @1.10 and mark it down to 1.05 (a fresh EUR_USD
    # tick drives the entry then the markdown). Day 2: only USD_JPY ticks.
    eur_order = SizedOrder(
        order_id="e", signal_id="s", instrument=_INST, direction=1,
        size_units=Decimal("1000"), entry_price=1.10, stop_loss=0.90,
        take_profit=None, reason="t",
        factors_snapshot=MappingProxyType({"strategy_type": "TREND"}),
        sized_at=d0, param_set_id="p", group_id=None, action="open")

    class _L:
        def __init__(self):
            self.book = _FakeBook()
        def on_state(self, st):
            if st.timestamp == d0:
                self.book.orders.append(eur_order)

    states = [_ms2(d0, _INST, 1.10),                          # day1: open EUR_USD
              _ms2(d0.replace(hour=12), _INST, 1.05),         # day1: EUR_USD marked down
              _ms2(d0 + timedelta(days=1), other, 150.0)]     # day2: only USD_JPY ticks
    bt = Backtest(account="a", cost_model=TEST_COSTS)
    r = bt.run(loop=_L(), folds=[FoldData(Fold(0, d0, d0, d0, d0), (), states)],
               evolve_fn=_noop, spx_returns=[0.0] * 4,
               guardrail_hash="GH", expected_guardrail_hash="GH")
    # EUR_USD down 0.05 × 1000 = −50 on ~10000 NAV ≈ 0.5% DD, still visible on day 2
    assert r.out_of_sample.max_drawdown_pct > 0.3
