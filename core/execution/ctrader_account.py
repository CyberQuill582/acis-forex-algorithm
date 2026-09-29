"""The cTrader account snapshot (ACIS-13 §4.4, C-VEN-12): balance, equity and margin as Decimal, read
downstream by Risk only (master §7.5).

Invariants:
  * cTrader has no equity field (F-40), so equity is DERIVED, and it is NEVER overstated: it is the
    balance plus the net unrealized P&L, minus each open position's estimated closing commission
    (taken equal to its opening one) and minus any swap charged against it — both subtracted until
    OQ-15 settles whether `netUnrealizedPnL` already carries them. Guardrail-adjacent: it feeds the
    equity breaker and the §9.5 platform-measured series.
  * Money arrives as integers scaled by `moneyDigits` (F-21): converted exactly, no float.
  * A snapshot costs two requests (§6.5); positions come from the face's reconcile-seeded view.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from core.data.ctrader.schema import PT
from core.execution.venue import BrokerAccount


def money(raw, digits: int) -> Decimal:
    return Decimal(int(raw)).scaleb(-int(digits))


def derive(trader: Mapping, unrealized: Mapping, positions: Iterable[Mapping]) -> BrokerAccount:
    digits = int(trader.get("moneyDigits", 2))
    balance = money(trader["balance"], digits)
    pnl_digits = int(unrealized.get("moneyDigits", digits))
    net = sum((money(u["netUnrealizedPnL"], pnl_digits)
               for u in unrealized.get("positionUnrealizedPnL", ())), Decimal(0))
    haircut = Decimal(0)
    margin = Decimal(0)
    for p in positions:
        d = int(p.get("moneyDigits", digits))
        haircut += abs(money(p.get("commission", 0), d))              # the close's commission, estimated
        haircut += max(-money(p.get("swap", 0), d), Decimal(0))       # swap charged, if not yet in P&L
        margin += money(p.get("usedMargin", 0), d)
    return BrokerAccount(equity=balance + net - haircut, balance=balance, margin_used=margin)


async def snapshot(session, positions: Iterable[Mapping]) -> BrokerAccount:
    trader = (await session.request(PT.TRADER_REQ, {}, req_class="query")).payload["trader"]
    unrealized = (await session.request(PT.GET_POSITION_UNREALIZED_PNL_REQ, {},
                                        req_class="query")).payload
    return derive(trader, unrealized, positions)
