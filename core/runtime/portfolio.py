"""The Governor's portfolio snapshot in production (ACIS-05 §5): the twin of the harness's
tests/backtest/portfolio_view.py, fed from Risk's positions instead of the backtest book.

The Governor zeroes an order at the daily-drawdown limit and applies the cluster and currency
caps to this snapshot, so it must be the real one. Invariants:
  * NAV is the account's equity: broker truth in practice, the paper venue's ledger in paper.
  * Exposure is accumulated exactly as the Governor sizes a new order: each position's USD
    notional at entry counts once for every cluster of its instrument and adds ±notional to
    its base and quote currency deltas, signed by direction (the harness's arithmetic).
  * The daily drawdown is Risk's engine daily measure (the latest RiskSnapshot).
  * A position whose strategy the runtime never recorded (adopted from the venue after a
    restart, which halts entries) still counts in every exposure. It is left out of
    `open_positions`, whose `Position` needs a strategy, and logged: never a guessed strategy.
  * `stale` when the account is older than `max_age_s`: the Governor then zeroes entries.
  * Opens IN FLIGHT (submitted, not yet reported) count in every exposure as if filled, so the
    entries of one slot, or of one tick, are judged against each other (R16I-05).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

from core.governor.portfolio_types import PortfolioState, Position, SizedOrder
from core.governor.units import usd_per_base_unit
from core.risk.risk_types import RiskPosition
from core.signals.signal_types import StrategyType


@dataclass(frozen=True)
class _Close:
    close: float


class _Open:
    """An open in flight, read as the position it will be."""

    def __init__(self, order: SizedOrder) -> None:
        self.instrument, self.direction, self.size_units = order.instrument, order.direction, order.size_units
        self.avg_entry_price = order.entry_price


def build_portfolio(*, positions: Iterable[RiskPosition], strategy_of: Mapping[str, StrategyType],
                    marks: Mapping[str, float], nav: Decimal, daily_drawdown_pct: float,
                    clusters: Mapping[str, Sequence[str]], as_of: datetime,
                    account_age_s: float, max_age_s: float, logger,
                    inflight: Iterable[SizedOrder] = ()) -> PortfolioState:
    prices = {sym: (_Close(p),) for sym, p in marks.items()}
    out: list[Position] = []
    cluster_exposure: dict[str, Decimal] = {}
    currency_delta: dict[str, Decimal] = {}
    for pos in [*positions, *(_Open(o) for o in inflight)]:
        per_unit = usd_per_base_unit(pos.instrument, pos.avg_entry_price, prices)
        if per_unit is None:                # a cross with no USD leg marked: exposure unknown
            logger.event("PORTFOLIO_NO_USD_RATE", instrument=pos.instrument)
            return _stale(nav, as_of, daily_drawdown_pct)
        notional = pos.size_units * per_unit
        for cluster, members in clusters.items():
            if pos.instrument in members:
                cluster_exposure[cluster] = cluster_exposure.get(cluster, Decimal("0")) + notional
        base, _, quote = pos.instrument.partition("_")
        signed = Decimal(pos.direction) * notional
        currency_delta[base] = currency_delta.get(base, Decimal("0")) + signed
        currency_delta[quote] = currency_delta.get(quote, Decimal("0")) - signed
        if isinstance(pos, _Open):
            continue                        # exposure only: not yet a position
        strategy = strategy_of.get(pos.instrument)
        if strategy is None:
            logger.event("PORTFOLIO_STRATEGY_UNKNOWN", instrument=pos.instrument,
                         param_set_id=pos.param_set_id)
            continue
        out.append(Position(
            instrument=pos.instrument, direction=pos.direction, size_units=pos.size_units,
            entry_price=pos.avg_entry_price,
            stop_loss=pos.stop_loss if pos.stop_loss is not None else pos.avg_entry_price,
            take_profit=pos.take_profit, opened_at=pos.opened_at, strategy_type=strategy,
            param_set_id=pos.param_set_id, group_id=pos.group_id))
    return PortfolioState(nav=nav, open_positions=tuple(out),
                          per_currency_delta=MappingProxyType(currency_delta),
                          per_cluster_exposure=MappingProxyType(cluster_exposure),
                          daily_drawdown_pct=max(0.0, daily_drawdown_pct), as_of=as_of,
                          stale=account_age_s > max_age_s)


def _stale(nav: Decimal, as_of: datetime, daily_drawdown_pct: float) -> PortfolioState:
    """Exposure that cannot be measured is never reported as zero: the snapshot is stale."""
    empty = MappingProxyType({})
    return PortfolioState(nav=nav, open_positions=(), per_currency_delta=empty,
                          per_cluster_exposure=empty, daily_drawdown_pct=max(0.0, daily_drawdown_pct),
                          as_of=as_of, stale=True)
