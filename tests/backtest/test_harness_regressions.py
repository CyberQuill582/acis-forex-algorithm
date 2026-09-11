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
    position when a financing rate model is supplied;
  · GAP-P12D-05 — PnL and marks are converted quote→USD (USD_JPY, crosses via
    their quote leg; a missing leg raises instead of booking pounds as dollars);
  · GAP-P12D-06 — financing is direction- and size-aware and never bills a
    weekend night (the triple day already pays for the weekend).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from config.schemas import AccountRulebook, NewsRules
from core.data.normaliser import MarketState
from core.governor.portfolio_types import SizedOrder
from tests.backtest.harness import (Backtest, ConversionUnavailable, FoldData, _BookState,
                                    _OpenPos, _nights, quote_to_account)
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
    """With a negative financing rate, a position held across 22:00-UTC rollovers is
    charged carry — enough carry turns an otherwise-winning round-trip into a LOSS
    (the carry the tick model would otherwise ignore, GAP-P11E-04). Held Tue→Wed
    covers two rollovers and the Wed one is triple."""
    d0 = datetime(2026, 1, 6, 20, tzinfo=_UTC)               # Tue, before 22:00 rollover
    exit_ts = datetime(2026, 1, 8, 10, tzinfo=_UTC)          # Thu — spans Tue + Wed nights
    states = [_ms(d0, 1.10), _ms(exit_ts, 1.11)]             # open, then close on target
    script = {d0: [_order(d0, 1, 1.10, 1.05, 1.11)]}
    fold = [FoldData(Fold(0, d0, d0, d0, d0), (), states)]
    common = dict(folds=fold, evolve_fn=_noop, spx_returns=[0.0] * 4,
                  guardrail_hash="GH", expected_guardrail_hash="GH")

    no_carry = Backtest(account="a", cost_model=TEST_COSTS)
    # gross +10.0 (0.01 × 1000), friction 0.04. A deliberately extreme −100%/yr rate
    # (a mechanics test, not a realistic rate) on a 1,100 position value over
    # Tue(1×)+Wed(3×) = 4 days → −1100 × 4/365 ≈ −12.05, flipping it to a net loss.
    with_carry = Backtest(account="a", cost_model=TEST_COSTS,
                          financing=lambda inst, night, d: Decimal("-100"))
    r0 = no_carry.run(loop=_FakeLoop(dict(script)), **common)
    r1 = with_carry.run(loop=_FakeLoop(dict(script)), **common)
    assert r0.out_of_sample.n_trades == r1.out_of_sample.n_trades == 1
    assert r0.out_of_sample.win_rate == 1.0                  # profitable without carry
    assert r1.out_of_sample.win_rate == 0.0                  # carry turned it into a loss


# -- quote→USD conversion + direction/size-aware financing (P12D-05/06) -------- #

def _pos(inst: str, direction: int, entry: float, units: str, ts: datetime) -> _OpenPos:
    return _OpenPos(instrument=inst, direction=direction, entry_price=entry,
                    size_units=Decimal(units), entry_ts=ts, stop_loss=0.0,
                    take_profit=None, strategy_type="TREND")


_NOFRICTION = type(TEST_COSTS)(commission_per_side=0.0, slippage_per_side=0.0)


def test_usd_jpy_pnl_is_booked_in_dollars_not_yen() -> None:
    """Long 10,000 USD_JPY 150.00 → 151.00 is a ¥10,000 gain = $66.23 at the close
    rate. Before the fix the harness booked 10,000 'dollars' — 151× too large."""
    t = datetime(2026, 1, 6, 10, tzinfo=_UTC)
    bt = Backtest(account="a", cost_model=_NOFRICTION)
    closed = bt._close_at(_pos("USD_JPY", 1, 150.0, "10000", t), 151.0, t, "target",
                          _BookState())
    assert closed.pnl == pytest.approx(Decimal("10000") / Decimal("151"), rel=1e-12)
    assert closed.pnl < 100


def test_cross_pair_converts_through_its_quote_leg_or_refuses() -> None:
    """EUR_GBP PnL is in GBP; it converts at the last-seen GBP_USD. With no GBP leg
    in the run the harness must raise, never book pounds as dollars."""
    t = datetime(2026, 1, 6, 10, tzinfo=_UTC)
    bt = Backtest(account="a", cost_model=_NOFRICTION)
    book = _BookState(last_price={"GBP_USD": 1.25})
    closed = bt._close_at(_pos("EUR_GBP", -1, 0.8600, "100000", t), 0.8500, t, "target", book)
    assert closed.pnl == pytest.approx(Decimal("1000") * Decimal("1.25"))   # £1,000 → $1,250
    assert quote_to_account("EUR_GBP", 0.85, {"USD_GBP": 0.8}) == Decimal("1.25")
    with pytest.raises(ConversionUnavailable):
        bt._close_at(_pos("EUR_GBP", 1, 0.86, "1000", t), 0.85, t, "target", _BookState())


def test_usd_jpy_open_position_marked_in_dollars() -> None:
    """A ¥-denominated mark must not blow up the equity curve: a 1.0 JPY move on
    10,000 units is ~$66, i.e. a ~0.66% move on a $10,000 book — not 100%."""
    t = datetime(2026, 1, 6, 10, tzinfo=_UTC)
    bt = Backtest(account="a", cost_model=_NOFRICTION)
    book = _BookState(open_by_inst={"USD_JPY": _pos("USD_JPY", 1, 150.0, "10000", t)},
                      last_price={"USD_JPY": 149.0})
    assert bt._unrealised(book) == pytest.approx(-Decimal("10000") / Decimal("149"))


def test_financing_is_direction_and_size_aware() -> None:
    """Same instrument, same nights: the long receives what its rate says, the
    short pays its own (different-signed) rate, and doubling size doubles carry.
    The old model charged one signed constant to both sides regardless of size."""
    entry = datetime(2026, 1, 6, 12, tzinfo=_UTC)             # Tue
    exit_ts = datetime(2026, 1, 7, 12, tzinfo=_UTC)           # Wed noon — 1 rollover (Tue)
    rates = {1: Decimal("2.0"), -1: Decimal("-3.0")}          # differential ± fee, per side
    bt = Backtest(account="a", cost_model=_NOFRICTION,
                  financing=lambda inst, night, d: rates[d])
    one_day = Decimal("100000") * Decimal("1.1") / Decimal("100") / Decimal("365")
    long_ = bt._carry_quote(_pos("EUR_USD", 1, 1.1, "100000", entry), exit_ts)
    short = bt._carry_quote(_pos("EUR_USD", -1, 1.1, "100000", entry), exit_ts)
    double = bt._carry_quote(_pos("EUR_USD", 1, 1.1, "200000", entry), exit_ts)
    assert long_ == pytest.approx(one_day * 2)                # +2%/yr for one day
    assert short == pytest.approx(-one_day * 3)               # −3%/yr for one day
    assert double == pytest.approx(long_ * 2)


def test_weekend_is_not_billed_twice() -> None:
    """Held Fri 12:00 → Mon 23:00: rollovers are Fri and Mon only (2 days under
    tom_next). The old count added Sat + Sun on top of the triple-Wednesday that
    already pays for the weekend."""
    fri = datetime(2026, 1, 9, 12, tzinfo=_UTC)
    mon_late = datetime(2026, 1, 12, 23, tzinfo=_UTC)
    assert _nights(fri, mon_late) == [date(2026, 1, 9), date(2026, 1, 12)]
    bt = Backtest(account="a", cost_model=_NOFRICTION,
                  financing=lambda inst, night, d: Decimal("-3.65"))  # −0.01% of value/day
    carry = bt._carry_quote(_pos("EUR_USD", 1, 1.0, "100000", fri), mon_late)
    assert carry == pytest.approx(Decimal("-20"))             # 2 days × −$10, not 4


def test_gold_financing_bills_the_weekend_on_friday() -> None:
    """XAU_USD is declared financing_daily: Friday ×3, no Wednesday triple; an
    undeclared convention is refused rather than silently charged 1×."""
    wed = datetime(2026, 1, 7, 12, tzinfo=_UTC)
    sat = datetime(2026, 1, 10, 12, tzinfo=_UTC)              # Wed, Thu, Fri rollovers
    rate = lambda inst, night, d: Decimal("-36.5")            # −0.1% of value per day
    gold = Backtest(account="a", cost_model=_NOFRICTION, financing=rate,
                    swap_conventions={"XAU_USD": "financing_daily"})
    carry = gold._carry_quote(_pos("XAU_USD", 1, 2000.0, "10", wed), sat)
    assert carry == pytest.approx(Decimal("-20") * 5)         # Wed 1 + Thu 1 + Fri 3
    bad = Backtest(account="a", cost_model=_NOFRICTION, financing=rate,
                   swap_conventions={"XAU_USD": "made_up"})
    with pytest.raises(ValueError):
        bad._carry_quote(_pos("XAU_USD", 1, 2000.0, "10", wed), sat)


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
