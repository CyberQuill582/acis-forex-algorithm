"""C2 reproduction: a pair's second leg is charged the FIRST leg's spread, and filled at a stale price.

    cd /tmp/review-acis && python <this file>

Code at BASE 7695ed04:
  * AGON fires PAIR_DIVERGENCE only on leg 0's tick (core/signals/agon.py:453-454; the
    configured pair is [EUR_USD, USD_JPY]), and prices BOTH legs at the last JOINT bar close
    (`a_col[-1]`, `b_col[-1]`, agon.py:476-479), not at a current quote.
  * The harness books every new order against the tick that produced it:
    `apply_order(order, st, ...)` (harness.py:170-172) stores `entry_spread=st.spread`
    (book.py:110). For the USD_JPY leg that is EUR_USD's spread, about 0.0001 in price units,
    where USD_JPY's is about 0.01: roughly 100x too small. A reverse close on a
    cross-instrument order has the same flaw (book.py:100-101 passes `st.spread`).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path.cwd()))
from core.data.normaliser import MarketState                   # noqa: E402
from core.governor.portfolio_types import SizedOrder           # noqa: E402
from core.optimizer.costs import CostModel                     # noqa: E402
from tests.backtest.book import BookState, PositionModel       # noqa: E402

UTC = timezone.utc


def ms(ts, inst, bid, ask):
    return MarketState(timestamp=ts, instrument=inst, bid=bid, ask=ask, spread=ask - bid,
                       mid=(bid + ask) / 2, volume=1.0, order_book_depth=MappingProxyType({}),
                       tick_velocity=1.0, session="london", macro_events_imminent=False,
                       ingest_ts=ts, is_stale=False, raw=MappingProxyType({}))


def main():
    costs = {"EUR_USD": CostModel(0.0, 0.00002), "USD_JPY": CostModel(0.0, 0.002)}
    pm, book = PositionModel(costs=costs, max_hold_s=172800), BookState()
    t = datetime(2026, 1, 6, 12, tzinfo=UTC)
    eur_tick = ms(t, "EUR_USD", 1.10000, 1.10010)            # 1.0 pip EUR_USD spread
    jpy_spread = 0.012                                       # a 1.2 pip USD_JPY spread
    book.last_price.update({"EUR_USD": 1.10005, "USD_JPY": 150.000})
    leg_b = SizedOrder(order_id="b", signal_id="s", instrument="USD_JPY", direction=1,
                       size_units=Decimal("100000"), entry_price=150.000, stop_loss=149.0,
                       take_profit=151.0, reason="pair", factors_snapshot=MappingProxyType({}),
                       sized_at=t, param_set_id="p", group_id="g", action="open")
    pm.apply_order(leg_b, eur_tick, book, "PAIR_DIVERGENCE")
    pos = book.open_by_inst["USD_JPY"]
    charged = costs["USD_JPY"].per_side_cost(pos.entry_spread)
    due = costs["USD_JPY"].per_side_cost(jpy_spread)
    usd = lambda jpy: float(Decimal(str(jpy)) * pos.size_units / Decimal("150"))
    print(f"USD_JPY leg booked on a EUR_USD tick: entry_spread stored = {pos.entry_spread:.5f} "
          f"(EUR_USD's), USD_JPY's own spread = {jpy_spread}")
    print(f"entry friction charged = {charged:.5f} JPY/unit (${usd(charged):.2f} on 100k); "
          f"due = {due:.5f} JPY/unit (${usd(due):.2f}); under-charged by ${usd(due - charged):.2f} "
          f"per leg entry")


if __name__ == "__main__":
    main()
