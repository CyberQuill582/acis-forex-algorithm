"""The Governor's portfolio snapshot, built from the backtest book (GAP-P12D-21; ACIS-05 §5).

The Governor zeroes an order at the daily-drawdown limit and applies the cluster and
single-currency caps to this snapshot, so a replay must hand it the real one — a flat
snapshot would silently switch those guardrails off. Invariants:

  * NAV = the starting NAV + realised PnL + unrealised PnL marked at last-seen prices (USD).
  * Exposure is accumulated exactly as the Governor sizes a new order: each open position's
    USD notional at entry (units × the USD value of one base unit, core/governor/units.py)
    counts once for every cluster its instrument belongs to, and adds +notional to its base
    currency's delta and −notional to its quote currency's, signed by direction.
  * The daily drawdown is the Risk Monitor's engine daily limit (core/risk/guardrails.py):
    measured from the equity at the FX trading day's first observation (after the 17:00
    New York rollover), never negative.
  * Every open position must carry a known strategy and param set (GAP-P12D-20); a cross
    with no USD rate raises. Nothing is guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Sequence

from core.data.errors import DataQualityError
from core.governor.portfolio_types import PortfolioState, Position
from core.governor.units import usd_per_base_unit
from core.signals.signal_types import StrategyType
from tests.backtest.book import BookState


@dataclass(frozen=True)
class _Close:
    close: float


def build_portfolio_state(*, book: BookState, nav: Decimal, clusters: Mapping[str, Sequence[str]],
                          as_of: datetime) -> PortfolioState:
    prices = {sym: (_Close(p),) for sym, p in book.last_price.items()}
    positions: list[Position] = []
    cluster_exposure: dict[str, Decimal] = {}
    currency_delta: dict[str, Decimal] = {}
    for pos in book.open_by_inst.values():
        if pos.strategy_type not in StrategyType._value2member_map_ or not pos.param_set_id:
            raise DataQualityError("strategy_type", pos.strategy_type,
                                   "an open position needs its strategy and param set (GAP-P12D-20)")
        per_unit = usd_per_base_unit(pos.instrument, pos.entry_price, prices)
        if per_unit is None:
            raise DataQualityError("instrument", pos.instrument, "no USD rate for this cross")
        notional = pos.size_units * per_unit
        for cluster, members in clusters.items():
            if pos.instrument in members:
                cluster_exposure[cluster] = cluster_exposure.get(cluster, Decimal("0")) + notional
        base, _, quote = pos.instrument.partition("_")
        signed = Decimal(pos.direction) * notional
        currency_delta[base] = currency_delta.get(base, Decimal("0")) + signed
        currency_delta[quote] = currency_delta.get(quote, Decimal("0")) - signed
        positions.append(Position(
            instrument=pos.instrument, direction=pos.direction, size_units=pos.size_units,
            entry_price=pos.entry_price, stop_loss=pos.stop_loss, take_profit=pos.take_profit,
            opened_at=pos.entry_ts, strategy_type=StrategyType(pos.strategy_type),
            param_set_id=pos.param_set_id, group_id=pos.group_id))
    anchor = book.day_anchor
    daily_dd = (max(0.0, float((anchor - nav) / anchor) * 100.0)
                if anchor is not None and anchor > 0 else 0.0)
    return PortfolioState(nav=nav, open_positions=tuple(positions),
                          per_currency_delta=MappingProxyType(currency_delta),
                          per_cluster_exposure=MappingProxyType(cluster_exposure),
                          daily_drawdown_pct=daily_dd, as_of=as_of, stale=False)
