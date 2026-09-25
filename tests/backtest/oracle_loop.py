"""The oracle's decision side (GAP-P12D-37): what it trades, when, and how much. Grading lives in
oracle.py.

Mental model:
  * On every graded tick the oracle wants to hold one NAV of USD notional (`NOTIONAL_FRACTION`,
    audit E9) per instrument in the direction of the planted episode IN FORCE
    (`SyntheticMarket.episode_sign`): never the next episode, never the noise.
  * It re-asserts at the first graded tick of each UTC day, so a max-hold close does not leave it
    flat, and reverses when the episode changes.
  * A graded RUNG (audit E1) is the same oracle wrong on a fixed share of whole episodes
    (`sign_error`): a weaker, known edge on the SAME tape, so the harness can be asked to pass a
    rung just above the §14 cut-offs and refuse one just below them. `sign_error = 0` is perfect.
  * It OBEYS the account's evaluable §9.5 rules (audit F2), so a refusal of it can only come from
    the grade, never from a rule it could have kept:
      - weekend-flat accounts: it opens nothing in the `min_hold + FLATTEN_LEAD` before Friday's
        rollover and closes every position `FLATTEN_LEAD` before it (the harness books a hold
        across that rollover as `weekend_holding`). It does the same before each fold's test end
        (`flat_before`): the harness then carries open positions through the observe-only embargo,
        where no strategy can act and which always spans a weekend;
      - `min_hold_seconds`: it never reverses or closes a position younger than that.
    News blackouts are enforced by the Governor, which the oracle bypasses; with no event
    calendar they never apply (GAP-P12D-03). No other rule is evaluable from closed trades.
  * Warm-up ticks decide nothing (`observe_only`), as for the engine.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Sequence

from config.schemas import AccountRulebook
from core.data.fx_clock import rollover_utc
from core.governor.portfolio_types import SizedOrder
from tests.backtest.money import quote_to_account
from tests.backtest.synthetic_market import SyntheticMarket

NOTIONAL_FRACTION = Decimal("1")       # USD notional per instrument, as a fraction of NAV (E9)
FLATTEN_LEAD = timedelta(minutes=30)   # weekend-flat accounts: flat this long before Friday's roll
STRATEGY = "ORACLE"                    # graded inside the §14 duration band (no carve-out)


@dataclass(frozen=True)
class OracleTick:
    """The MarketState fields the harness and book read — and nothing it would have to invent."""
    timestamp: datetime
    instrument: str
    bid: float
    ask: float
    spread: float
    mid: float


class _NoParams:
    """The ParamLibrary stand-in: the oracle stages nothing, so a boundary promotes nothing."""

    def on_boundary(self, now: datetime) -> list[str]:
        return []


class _Orders:
    def __init__(self) -> None:
        self.orders: list[SizedOrder] = []
        self.strategy_of: dict[str, str] = {}
        self.regime_of: dict[str, str] = {}


class OracleLoop:
    """The loop surface `Backtest` drives: `on_state`, `observe_only`, `book`, `params`."""

    def __init__(self, market: SyntheticMarket, nav: Decimal, rulebook: AccountRulebook | None = None,
                 flat_before: Sequence[datetime] = (), sign_error: float = 0.0) -> None:
        if not 0.0 <= sign_error < 0.5:
            raise ValueError("sign_error must be in [0, 0.5): at 0.5 the oracle knows nothing")
        self.book = _Orders()
        self.params = _NoParams()
        self._market = market
        self._sign_error = sign_error
        self._notional = nav * NOTIONAL_FRACTION
        self._weekend_flat = rulebook is not None and not rulebook.weekend_holding_allowed
        self._fold_ends = sorted(flat_before)
        self._min_hold = timedelta(seconds=rulebook.min_hold_seconds if rulebook else 0)
        self._last: dict[str, float] = {}                   # every instrument's last mid (crosses)
        self._held: dict[str, tuple[int, object]] = {}      # instrument -> (sign, UTC day)
        self._opened: dict[str, datetime] = {}              # instrument -> time of its last open

    def units(self, instrument: str, mid: float) -> Decimal:
        """Whole units whose USD notional is `NOTIONAL_FRACTION` of NAV (audit E9: a fixed unit
        count made gold 10,000 oz = $18M on a $10k account), converted exactly as the book books
        PnL (`money.quote_to_account`)."""
        usd_per_unit = Decimal(str(mid)) * quote_to_account(instrument, mid, self._last)
        return Decimal(int(self._notional / usd_per_unit))

    def _zone(self, now: datetime) -> str | None:
        """"flatten" or "wind_down" before the next deadline — Friday's rollover, or the fold's
        test end — on a weekend-flat account, else None."""
        if not self._weekend_flat:
            return None
        deadlines = [rollover_utc(now.date())] if now.weekday() == 4 else []
        k = bisect.bisect_right(self._fold_ends, now)
        deadlines += self._fold_ends[k:k + 1]
        upcoming = [d for d in deadlines if d > now]
        if not upcoming:
            return None
        cutoff = min(upcoming)
        if now >= cutoff - FLATTEN_LEAD:
            return "flatten"
        return "wind_down" if now >= cutoff - FLATTEN_LEAD - self._min_hold else None

    def _young(self, instrument: str, now: datetime) -> bool:
        opened = self._opened.get(instrument)
        return opened is not None and now - opened < self._min_hold

    def observe_only(self, st: OracleTick) -> None:
        self._last[st.instrument] = st.mid                  # warm-up decides nothing

    def on_state(self, st: OracleTick) -> None:
        inst, now = st.instrument, st.timestamp
        self._last[inst] = st.mid
        sign, zone, held = self.sign(inst, now), self._zone(now), self._held.get(inst)
        if zone == "flatten":
            if held is not None:                            # opened before the wind-down: old enough
                self._order(st, held[0], "close")
                del self._held[inst]
            return
        if held == (sign, now.date()):
            return                                          # same episode, same day: hold
        flipping = held is not None and held[0] != sign
        if flipping and self._young(inst, now):
            return                                          # min hold: keep the old side a while
        if zone == "wind_down":                             # never open this close to the weekend
            if flipping:
                self._order(st, held[0], "close")
                del self._held[inst]
            return
        self._order(st, sign, "open")
        self._held[inst], self._opened[inst] = (sign, now.date()), now

    def sign(self, instrument: str, now: datetime) -> int:
        """The episode in force's sign, WRONG on a fixed `sign_error` share of episodes: a graded
        rung (audit E1). Which episodes are wrong is a hash of (instrument, episode start), so the
        rung is deterministic and its errors fall on whole episodes, as a real filter's would."""
        ep = self._market.episode_at(instrument, now)
        digest = hashlib.sha256(f"{instrument}|{ep.start}".encode()).digest()
        wrong = int.from_bytes(digest[:8], "big") / 2 ** 64 < self._sign_error
        return -int(ep.sign) if wrong else int(ep.sign)

    def _order(self, st: OracleTick, sign: int, action: str) -> None:
        oid = f"oracle-{len(self.book.orders)}"
        self.book.orders.append(SizedOrder(
            order_id=oid, signal_id=oid, instrument=st.instrument, direction=sign,
            size_units=self.units(st.instrument, st.mid), entry_price=st.mid,
            # a stop no planted episode reaches: the oracle exits by reversing or closing, never by stop
            stop_loss=st.mid * (0.5 if sign > 0 else 2.0), take_profit=None,
            reason=f"oracle: {action} on the planted episode in force",
            factors_snapshot=MappingProxyType({"strategy_type": STRATEGY}),
            sized_at=st.timestamp, param_set_id="oracle", action=action))
        self.book.strategy_of[oid] = STRATEGY
