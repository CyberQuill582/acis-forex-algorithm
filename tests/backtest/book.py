"""The backtest's position book and declared fill/close model (ACIS-09 §6, GAP-0001).

A backtest IS a runtime, so the position layer the fast-loop GAPs (0075/0091b/0099)
deferred lives here. Invariants:

  * An order fills at its `entry_price`. A position closes on a stop or target touch, an
    opposite-direction order (reverse), an `action="close"` order (at the tick's mid; nothing
    to close is a no-op), or the max hold. A same-side repeat is ignored (GAP-0075: the loop
    re-sizes every tradeable tick).
  * PnL is Decimal: gross minus the instrument's OWN C8 friction — one cost model per
    instrument, because costs are in price units and prices differ by scale (EUR/USD
    ~1.1, USD/JPY ~150; GAP-P12D-19) — plus financing on every real 17:00-New-York
    business-day rollover held (carry.py, GAP-P12D-06/07). Everything is converted
    quote → USD once, at the close rate (money.py, GAP-P12D-05).
  * An instrument without a cost model raises: there is no silent zero-cost instrument.
  * A book is ONE continuous record: realised PnL and open positions persist across
    folds (GAP-P11I-03). Every open position is marked off its instrument's last-seen
    price (GAP-P11E-03); the intraday high-water is tracked on every tick (GAP-P11I-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from core.data.fx_clock import business_rollovers
from core.data.normaliser import MarketState
from core.optimizer.costs import CostModel
from tests.backtest.carry import FinancingRate, financing_charge
from tests.backtest.metrics import ClosedTrade
from tests.backtest.money import quote_to_account
from tests.backtest.rollover_marks import RolloverMarker


@dataclass
class OpenPos:
    instrument: str
    direction: int
    entry_price: float
    size_units: Decimal
    entry_ts: datetime
    stop_loss: float
    take_profit: float | None
    strategy_type: str
    param_set_id: str = ""
    group_id: str | None = None
    regime: str | None = None            # regime ACTIVE at entry (GAP-P12D-31)
    entry_spread: float = 0.0            # the quoted spread paid on entry (C8, GAP-P12D-36)


@dataclass
class BookState:
    """`equity` is sampled once per calendar day (the daily-return metrics); `peak` and
    `max_dd_pct` follow the intraday high-water (the §14 drawdown); `marker` holds the
    17:00-New-York marks for the date-joined SPX correlation (GAP-SP12E-06)."""
    realised: Decimal = Decimal("0")
    open_by_inst: dict[str, OpenPos] = field(default_factory=dict)
    last_price: dict[str, float] = field(default_factory=dict)
    equity: list[tuple[datetime, Decimal]] = field(default_factory=list)
    trades: list[ClosedTrade] = field(default_factory=list)
    last_day: object = None
    peak: Decimal | None = None
    max_dd_pct: float = 0.0
    marker: RolloverMarker = field(default_factory=RolloverMarker)
    day_anchor: Decimal | None = None      # equity at the current FX trading day's first tick

    def book_close(self, closed: ClosedTrade, instrument: str) -> None:
        self.trades.append(closed)
        self.realised += closed.pnl
        del self.open_by_inst[instrument]


class PositionModel:
    def __init__(self, *, costs: Mapping[str, CostModel], max_hold_s: float,
                 financing: FinancingRate | None = None,
                 swap_conventions: Mapping[str, str] | None = None) -> None:
        self._costs = costs
        self.max_hold_s = max_hold_s
        self._financing = financing                     # None ⇒ no carry (caveated)
        self._conventions = dict(swap_conventions or {})  # default tom_next

    def cost(self, instrument: str) -> CostModel:
        try:
            return self._costs[instrument]
        except KeyError:
            raise ValueError(f"no C8 cost model for {instrument} — refusing a zero-cost "
                             "instrument (GAP-P12D-19)") from None

    def apply_order(self, order, st: MarketState, book: BookState,
                    strategy: str | None = None, regime: str | None = None) -> None:
        """`strategy` is the signal's strategy recorded by the loop (GAP-P12D-20); the
        Governor's factors snapshot carries none, so the snapshot key is only a fallback.
        `regime` is the regime active when the loop opened the order (GAP-P12D-31), so a
        run can say which regime made or lost the money."""
        existing = book.open_by_inst.get(order.instrument)
        if order.action == "close":
            # a flatten fills at THIS tick's mid, as a max-hold close does — never at the order's
            # entry_price (a Governor close carries its leg's original entry price)
            if existing is not None:
                book.book_close(self.close_at(existing, st.mid, st.timestamp, "close", book, st.spread),
                                order.instrument)
            return
        if existing is not None:
            if existing.direction == order.direction:
                return                                   # same-side dedup (GAP-0075)
            book.book_close(self.close_at(existing, order.entry_price, st.timestamp,
                                          "reverse", book, st.spread), order.instrument)
        book.open_by_inst[order.instrument] = OpenPos(
            instrument=order.instrument, direction=order.direction,
            entry_price=order.entry_price, size_units=order.size_units,
            entry_ts=order.sized_at, stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            strategy_type=strategy or (order.factors_snapshot.get("strategy_type", "UNKNOWN")
                                       if isinstance(order.factors_snapshot, Mapping) else "UNKNOWN"),
            param_set_id=order.param_set_id, group_id=order.group_id, regime=regime,
            entry_spread=st.spread)

    def maybe_close(self, pos: OpenPos, st: MarketState, book: BookState) -> ClosedTrade | None:
        # GAP-P12D-84: a triggered stop fills at the first price equal to or WORSE than it (a
        # gap past the stop books the gap); a target keeps its level (conservative on gaps).
        price = st.mid
        if pos.direction == 1:
            if price <= pos.stop_loss:
                return self.close_at(pos, min(price, pos.stop_loss), st.timestamp, "stop", book,
                                     st.spread)
            if pos.take_profit is not None and price >= pos.take_profit:
                return self.close_at(pos, pos.take_profit, st.timestamp, "target", book, st.spread)
        else:
            if price >= pos.stop_loss:
                return self.close_at(pos, max(price, pos.stop_loss), st.timestamp, "stop", book,
                                     st.spread)
            if pos.take_profit is not None and price <= pos.take_profit:
                return self.close_at(pos, pos.take_profit, st.timestamp, "target", book, st.spread)
        if (st.timestamp - pos.entry_ts).total_seconds() >= self.max_hold_s:
            return self.close_at(pos, price, st.timestamp, "max_hold", book, st.spread)
        return None

    def carry_quote(self, pos: OpenPos, exit_ts: datetime) -> Decimal:
        """Financing over every business-day rollover held, in QUOTE currency."""
        if self._financing is None:
            return Decimal("0")
        return financing_charge(
            instrument=pos.instrument, direction=pos.direction,
            value=pos.size_units * Decimal(str(pos.entry_price)),
            nights=business_rollovers(pos.entry_ts, exit_ts),
            rate=self._financing,
            swap_convention=self._conventions.get(pos.instrument, "tom_next"))

    def close_at(self, pos: OpenPos, exit_price: float, ts: datetime,
                 reason: str, book: BookState, exit_spread: float = 0.0) -> ClosedTrade:
        """GAP-P12D-36: friction is the DECLARED C8 cost on both sides — `per_side_cost` is
        `spread/2 + commission + slippage`, the same function the optimizer's fitness charges
        (master §5 C8: one model, both places). Omitting the spread here made every graded
        number optimistic while selection was scored against the stricter world."""
        cost = self.cost(pos.instrument)
        gross = (Decimal(str(exit_price)) - Decimal(str(pos.entry_price))) \
            * Decimal(pos.direction) * pos.size_units
        friction = Decimal(str(cost.per_side_cost(pos.entry_spread)
                               + cost.per_side_cost(exit_spread))) * pos.size_units
        carry = self.carry_quote(pos, ts)
        # all three are QUOTE-currency amounts — convert once, at the close rate
        to_acct = quote_to_account(pos.instrument, exit_price, book.last_price)
        return ClosedTrade(entry_ts=pos.entry_ts, exit_ts=ts,
                           pnl=(gross - friction + carry) * to_acct,
                           strategy_type=pos.strategy_type, regime=pos.regime,
                           notional_usd=pos.size_units * Decimal(str(pos.entry_price)) * to_acct,
                           friction=friction * to_acct, carry=carry * to_acct)

    def unrealised(self, book: BookState) -> Decimal:
        total = Decimal("0")
        for pos in book.open_by_inst.values():
            mark = book.last_price.get(pos.instrument)
            if mark is None:
                continue
            total += (Decimal(str(mark)) - Decimal(str(pos.entry_price))) \
                * Decimal(pos.direction) * pos.size_units \
                * quote_to_account(pos.instrument, mark, book.last_price)
        return total

    @staticmethod
    def mark_drawdown(book: BookState, equity: Decimal) -> None:
        """Update the running intraday high-water and worst peak-to-trough %."""
        if book.peak is None or equity > book.peak:
            book.peak = equity
        if book.peak and book.peak > 0:
            dd = float((book.peak - equity) / book.peak) * 100.0
            if dd > book.max_dd_pct:
                book.max_dd_pct = dd
