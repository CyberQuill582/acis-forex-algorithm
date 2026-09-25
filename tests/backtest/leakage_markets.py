"""Synthetic tapes for the structural leakage checks (GAP-P12D-65; leakage.py holds T1/T2).

Mental model:
  * `PerturbedMarket` is `spec`'s market with its future changed at a cut: "perturb" (T2)
    reverses, negates and doubles the return of every tick stamped >= cut; "truncate" (T1)
    deletes those ticks. The change is made at the SOURCE (`returns`), so every channel sees
    it: `load`, the price path, and any side channel that reads `returns` directly. A leak can
    only hide from a perturbation it does not see, so no channel may keep the original future.
  * A tick's price depends on its own return and every earlier one, so ticks stamped < cut
    are bit-identical in every variant (pinned by test).
  * `TickClock` holds the tick times the LOADER actually delivers (the FX weekend dropped), so
    a bar's emission stamp is the tick that really completes it, not a tick the loader drops.
  * `decision_cuts` is the exhaustive grid: every step (a day by default) that holds a tick.
  * `LeakyOracleLoop` is the T7 positive control for the guard: the oracle positive control
    (oracle.py) with ONE change — on every `every`-th tick it holds the sign of the NEXT tick's
    return, read through `market.returns`. It must be caught by T1 and T2; the honest oracle,
    which reads only the episode in force, must not be.
"""

from __future__ import annotations

import bisect
import math
from array import array
from datetime import datetime, timedelta
from functools import partial
from typing import Iterator, Mapping, Sequence

from core.data.normaliser import RawTick
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.leakage import Decision, perturb_returns
from tests.backtest.oracle import grade_oracle
from tests.backtest.oracle_loop import OracleLoop, OracleTick
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket
from tests.backtest.walk_forward import Fold

MODES = ("perturb", "truncate")
_DAY = timedelta(days=1)


def ticks_before(spec: MarketSpec, t: datetime) -> int:
    """How many of the market's weekday ticks are stamped before `t` (`load`'s arithmetic)."""
    t = min(max(t, spec.start), spec.end)
    days, rest = divmod(t - spec.start, _DAY)
    n = (days // 7 * 5 + min(days % 7, 5)) * spec.ticks_per_day
    if days % 7 < 5:
        n += math.ceil(rest.total_seconds() / spec.tick_seconds)
    return n


class PerturbedMarket(SyntheticMarket):
    def __init__(self, spec: MarketSpec, cut: datetime, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        super().__init__(spec)                     # the same name: the same market up to the cut
        self.cut, self.mode = cut, mode
        self._k = ticks_before(spec, cut)
        self._variant: dict[str, array] = {}

    def returns(self, instrument: str) -> array:
        if instrument not in self._variant:
            base = super().returns(instrument)
            self._variant[instrument] = (array("d", perturb_returns(base, self._k))
                                         if self.mode == "perturb" else base[:self._k])
        return self._variant[instrument]

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        yield from super().load(instrument, start, min(end, self.cut) if self.mode == "truncate" else end)


class TickClock:
    """The delivered tick times of one instrument: `after(ts)` is the first tick at or after ts."""

    def __init__(self, loader: BacktestDataLoader, source: str, instrument: str,
                 start: datetime, end: datetime) -> None:
        self._ts = [t.event_time for t in loader.stream(source=source, instrument=instrument,
                                                        start=start, end=end)]

    def after(self, ts: datetime) -> datetime:
        i = bisect.bisect_left(self._ts, ts)
        return self._ts[i] if i < len(self._ts) else datetime.max.replace(tzinfo=ts.tzinfo)


def decision_cuts(spec: MarketSpec, step: timedelta = _DAY) -> list[datetime]:
    """Every grid point after the start at which the market has a tick (weekends hold none)."""
    out, t = [], spec.start + step
    while t < spec.end:
        d = (t - spec.start).days % 7
        if d < 5:
            out.append(t)
        t += step
    return out


class LeakyOracleLoop(OracleLoop):
    def __init__(self, market: SyntheticMarket, *args, every: int = 1, **kw) -> None:
        super().__init__(market, *args, **kw)
        self._every = every

    def on_state(self, st: OracleTick) -> None:
        j = self._market.index_of(st.timestamp)
        if j % self._every == 0 and j + 1 >= len(self._market.returns(st.instrument)):
            self._last[st.instrument] = st.mid
            return                                 # nothing after this tick: no peek, no decision
        super().on_state(st)

    def sign(self, instrument: str, now: datetime) -> int:
        j = self._market.index_of(now)
        if j % self._every:
            return super().sign(instrument, now)
        return 1 if self._market.returns(instrument)[j + 1] > 0 else -1


def order_decisions(orders: Sequence, strategy_of: Mapping[str, str] = {},
                    regime_of: Mapping[str, str] = {}) -> list[Decision]:
    """An order is decided on its tick. Random ids (uuid4) are not decisions: the strategy and
    regime keyed by them are, and group membership is kept as the group's ordinal."""
    groups: dict[str, int] = {}
    return [Decision(o.sized_at, o.sized_at, "order", (
        o.instrument, o.direction, o.size_units, o.entry_price, o.stop_loss, o.take_profit,
        o.reason, o.param_set_id, o.action, strategy_of.get(o.order_id), regime_of.get(o.order_id),
        None if o.group_id is None else groups.setdefault(o.group_id, len(groups))))
        for o in orders]


def trade_decisions(trades: Sequence) -> list[Decision]:
    """A closed trade's exit is decided on its exit tick (the book's fill model)."""
    return [Decision(t.exit_ts, t.exit_ts, "trade", (t.entry_ts, t.pnl, t.strategy_type,
                                                     t.notional_usd, t.regime)) for t in trades]


def oracle_decisions(spec: MarketSpec, cfg, account: str, folds: Sequence[Fold], logger, *,
                     instruments: Sequence[str], cut: datetime | None = None, mode: str = "perturb",
                     leak_every: int = 0) -> list[Decision]:
    """The oracle through the REAL harness (Backtest, book, C8 costs) on `spec`, or on its
    variant at `cut`. `leak_every` > 0 swaps in the leaky control."""
    market = SyntheticMarket(spec) if cut is None else PerturbedMarket(spec, cut, mode)
    loop_cls = partial(LeakyOracleLoop, every=leak_every) if leak_every else OracleLoop
    g = grade_oracle(spec, cfg, account, folds, logger, instruments=instruments, market=market,
                     loop_cls=loop_cls)
    return order_decisions(g.orders) + trade_decisions(g.trades)
