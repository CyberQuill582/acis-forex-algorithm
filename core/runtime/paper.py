"""The paper venue: where paper-mode orders go (master §7.5: paper mode never reaches a venue).

It is the conformant mock face (core/execution/mock_face.py) plus what a real venue does
without being asked, so paper Risk sees what a venue would show it. Invariants:
  * A resting stop fires on the mark: a long's when the mid is at or below it, a short's at or
    above it, filled at that mid (a gap fills through the stop, never at it), and the fill
    arrives only on `venue_fills()`, unsolicited — the backtest book's stop rule.
  * Equity is the paper ledger: the starting NAV, plus realised PnL, minus the declared C8
    friction of every fill side (spread/2 + commission + slippage, the harness's charge), plus
    the open positions marked at the mid. Everything is converted quote → USD at the fill or
    mark price; a cross with no USD leg raises, a rate is never guessed.
  * Fills are at the requested price, as the harness fills; realised PnL follows the average
    price of the holding, as the Risk Monitor books it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from core.data.errors import DataQualityError
from core.execution.mock_face import MockExecutionFace
from core.execution.venue import BrokerAccount, CapabilityDescriptor, FillReport
from core.optimizer.costs import CostModel
from core.risk.usd_conversion import usd_factor


def _usd(instrument: str, amount: Decimal, price: float) -> Decimal:
    factor = usd_factor(instrument, price)
    if factor is None:
        raise DataQualityError("instrument", instrument, "a cross with no USD leg: no paper rate")
    return amount * Decimal(str(factor))


class PaperVenue(MockExecutionFace):
    def __init__(self, descriptor: CapabilityDescriptor, costs: Mapping[str, CostModel],
                 nav: Decimal) -> None:
        super().__init__(replace(descriptor, venue="paper"))
        self.name = "paper"
        self._costs = dict(costs)
        self._cash = nav                               # NAV + realised − friction, in USD
        self._avg: dict[str, float] = {}
        self._mid: dict[str, float] = {}
        self._spread: dict[str, float] = {}

    def on_mark(self, instrument: str, bid: float, ask: float, now: datetime) -> FillReport | None:
        """A new quote: remember it, and fire the resting stop it crosses."""
        mid = (bid + ask) / 2.0
        self._mid[instrument], self._spread[instrument] = mid, ask - bid
        stop = self._stops.get(instrument)
        net = self._net.get(instrument, Decimal("0"))
        if stop is None or net == 0 or (mid - stop) * (1 if net > 0 else -1) > 0:
            return None
        return self.trigger_stop(instrument, mid, now)

    def _execute(self, behaviour, fragment_id, order_id, instrument, direction, units,
                 requested_price, now, session_id, stop_loss) -> FillReport:
        before = self._net.get(instrument, Decimal("0"))
        report = super()._execute(behaviour, fragment_id, order_id, instrument, direction, units,
                                  requested_price, now, session_id, stop_loss)
        if report.filled_units > 0:
            self._book(instrument, before, direction, report.filled_units, report.fill_price)
        return report

    def trigger_stop(self, instrument: str, price: float, now: datetime) -> FillReport:
        before = self._net.get(instrument, Decimal("0"))
        report = super().trigger_stop(instrument, price, now)
        self._book(instrument, before, report.direction, report.filled_units, report.fill_price)
        return report

    def _book(self, instrument: str, before: Decimal, side: int, units: Decimal, price: float) -> None:
        cost = self._costs.get(instrument)
        if cost is None:
            raise DataQualityError("instrument", instrument, "no C8 cost model: no zero-cost paper fill")
        fee = Decimal(str(cost.per_side_cost(self._spread.get(instrument, 0.0)))) * units
        self._cash -= _usd(instrument, fee, price)
        if before == 0 or (before > 0) == (side > 0):          # open or add: the average moves
            total = abs(before) + units
            prev = self._avg.get(instrument, price)
            self._avg[instrument] = (prev * float(abs(before)) + price * float(units)) / float(total)
            return
        held_side = 1 if before > 0 else -1                    # a reduce (the mock never crosses)
        gross = (Decimal(str(price)) - Decimal(str(self._avg[instrument]))) * units * held_side
        self._cash += _usd(instrument, gross, price)
        if self._net.get(instrument, Decimal("0")) == 0:
            del self._avg[instrument]

    async def account_snapshot(self) -> BrokerAccount:
        return self.account()

    def account(self) -> BrokerAccount:
        """The paper ledger now: always current, so never stale (the fast loop reads it)."""
        open_pnl = Decimal("0")
        for inst, net in self._net.items():
            mid = self._mid.get(inst)
            if net == 0 or mid is None:
                continue
            open_pnl += _usd(inst, (Decimal(str(mid)) - Decimal(str(self._avg[inst]))) * net, mid)
        return BrokerAccount(equity=self._cash + open_pnl, balance=self._cash, margin_used=Decimal("0"))
