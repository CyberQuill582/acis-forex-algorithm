"""Real-engine walk-forward harness (ACIS-09 §2/§3/§7, master §13/§15).

Drives the ACTUAL ACIS decision layers — the real `MarketStateFactory`, NVMA,
AGON and Capital Governor composed exactly as production (reusing the phase-7
`build_paper_loop` wiring) — over walk-forward folds, per account. It is NOT a
re-implementation (C-BT-3): a change in NVMA behaviour changes the backtest
result, because NVMA itself runs.

The harness owns the position lifecycle + a DECLARED fill/close model (the
fidelity modelling GAP-0001 mandates the report surface): an order fills at its
`entry_price`; a position closes on a stop/target touch, an opposite-direction
signal (reverse), or a max-hold timeout; PnL is Decimal, net of the C8
`CostModel` round-trip friction PLUS overnight financing (`carry.py`). This is the
position/runtime layer the fast-loop GAPs (0075/0091b/0099) deferred — a backtest
IS a runtime, so it lives here.

Every money amount is converted from the instrument's QUOTE currency to the
ACCOUNT currency (USD) before it touches realised PnL or the equity curve
(GAP-P12D-05): a USD_JPY move is a JPY amount, and booking it as dollars inflates
it ~100-150×. XXX_USD → ×1; USD_XXX → ÷price; a cross (EUR_GBP) converts through
its quote leg's last-seen price (GBP_USD), and a run that lacks the leg raises
`ConversionUnavailable` rather than silently booking pounds as dollars.

Financing is direction- and size-aware (GAP-P12D-06): each business-day rollover
held charges units × entry_price × rate/100/365 × the convention's multiplier,
where `financing(instrument, night, direction)` returns the annualised rate (%)
for THAT side — the rate differential net of the broker fee, so a long and a short
never carry the same sign. Entry price stands in for the 5pm-ET rollover price (a
declared approximation; holds are capped at 48 h).

Audit-hardened (phase-11 dual audit): the out-of-sample equity is ONE CONTINUOUS
curve across folds — realised PnL and open positions persist, never reset per
fold (GAP-P11I-03/P11E-02); every open position is marked each day off its
instrument's LAST-SEEN price, not only the just-ticked one (GAP-P11E-03); the
graded `period` is DERIVED from the actual OOS data span, never a caller claim
(GAP-P11I-01); the account's §9.5 rulebook is enforced during the run and a
breach populates `rule_violations` (GAP-P11I-02/C-BT-7); the VaR-breach rate is a
real expanding-window delta-normal backtest, never a 0.0 stub (GAP-P11I-08/
P11E-01). `run` grades ONLY the concatenated out-of-sample folds (C-BT-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from core.data.normaliser import MarketState
from core.optimizer.costs import CostModel
from tests.backtest.carry import swap_multiplier
from tests.backtest.metrics import (ClosedTrade, MetricBlock, _returns_from_equity,
                                    compute_metrics, rolling_var_breach_rate)
from tests.backtest.report import ValidationReport, build_report
from tests.backtest.walk_forward import Fold

_UTC = timezone.utc
ACCOUNT_CCY = "USD"
_DAYS_PER_YEAR = Decimal("365")                  # OANDA: position value × rate × 1/365

# (instrument, business-day rollover date, direction) -> annualised % for that side
FinancingRate = Callable[[str, date, int], Decimal]


class ConversionUnavailable(Exception):
    """A quote-currency amount has no route to the account currency in this run."""


def quote_to_account(instrument: str, price: float, last_price: Mapping[str, float]) -> Decimal:
    """Factor converting a QUOTE-currency amount of `instrument` to ACCOUNT_CCY at
    `price` (that instrument's own price) or via a cross's quote leg."""
    base, _, quote = instrument.partition("_")
    if quote == ACCOUNT_CCY:
        return Decimal("1")
    if base == ACCOUNT_CCY:
        return Decimal("1") / Decimal(str(price))
    leg = last_price.get(f"{quote}_{ACCOUNT_CCY}")
    if leg:
        return Decimal(str(leg))
    leg = last_price.get(f"{ACCOUNT_CCY}_{quote}")
    if leg:
        return Decimal("1") / Decimal(str(leg))
    raise ConversionUnavailable(
        f"{instrument}: no {quote}_{ACCOUNT_CCY} or {ACCOUNT_CCY}_{quote} price seen yet — "
        f"a cross needs its conversion leg in the same run")


@dataclass
class _OpenPos:
    instrument: str
    direction: int
    entry_price: float
    size_units: Decimal
    entry_ts: datetime
    stop_loss: float
    take_profit: float | None
    strategy_type: str


@dataclass
class _BookState:
    """One continuous trading record (in-sample OR out-of-sample) that PERSISTS
    across folds — the fix for the fold-boundary equity discontinuity.

    Two equity tracks are kept deliberately (GAP-P11I-04): `equity` is sampled
    once per calendar DAY (the base for the daily-return metrics — Sharpe on a
    252-periods/yr base, positive-months), while `peak`/`max_dd_pct` track the
    INTRADAY high-water continuously (updated every tick) so the §14 max-drawdown
    is measured off the intraday peak, never understated by an EOD approximation
    (the exact failure the §13 trailing-DD glitch class condemns)."""
    realised: Decimal = Decimal("0")
    open_by_inst: dict[str, _OpenPos] = field(default_factory=dict)
    last_price: dict[str, float] = field(default_factory=dict)
    equity: list[tuple[datetime, Decimal]] = field(default_factory=list)
    trades: list[ClosedTrade] = field(default_factory=list)
    last_day: object = None
    peak: Decimal | None = None                  # running intraday high-water
    max_dd_pct: float = 0.0                       # worst intraday peak-to-trough %


@dataclass(frozen=True)
class FoldData:
    fold: Fold
    train_states: Sequence[MarketState]
    test_states: Sequence[MarketState]


class Backtest:
    def __init__(self, *, account: str, cost_model: CostModel, rulebook=None,
                 nav: Decimal = Decimal("10000"), max_hold_s: float = 48 * 3600,
                 periods_per_year: float = 252.0,
                 financing: FinancingRate | None = None,
                 swap_conventions: Mapping[str, str] | None = None) -> None:
        self._account = account
        self._cost = cost_model
        self._rulebook = rulebook                    # §9.5 account rules (or None)
        self._nav0 = nav
        self._max_hold_s = max_hold_s
        self._ppy = periods_per_year
        self._financing = financing                  # None ⇒ no carry (caveated)
        self._conventions = dict(swap_conventions or {})   # default tom_next
        # global watermark over the loop's accumulating order book.
        self._seen_orders = 0

    # -- one replay through the REAL engine into a persistent book ------------- #

    def _replay(self, loop, states: Sequence[MarketState], book: _BookState) -> None:
        for st in states:
            book.last_price[st.instrument] = st.mid
            # (1) mark/close the existing position on this instrument
            pos = book.open_by_inst.get(st.instrument)
            if pos is not None:
                closed = self._maybe_close(pos, st, book)
                if closed is not None:
                    book.trades.append(closed)
                    book.realised += closed.pnl
                    del book.open_by_inst[st.instrument]
            # (2) run the REAL decision path (NVMA → AGON → Governor)
            loop.on_state(st)
            # (3) consume newly sized orders under position management
            new_orders = loop.book.orders[self._seen_orders:]
            self._seen_orders = len(loop.book.orders)
            for order in new_orders:
                self._apply_order(order, st, book)
            # (4) mark equity EVERY tick for the intraday high-water/drawdown
            # (GAP-P11I-04), and additionally sample the daily curve once per day.
            marked = self._nav0 + book.realised + self._unrealised(book)
            self._mark_drawdown(book, marked)
            day = st.timestamp.date()
            if day != book.last_day:
                book.equity.append((st.timestamp, marked))
                book.last_day = day

    @staticmethod
    def _mark_drawdown(book: _BookState, equity: Decimal) -> None:
        """Update the running intraday high-water and worst peak-to-trough %."""
        if book.peak is None or equity > book.peak:
            book.peak = equity
        if book.peak and book.peak > 0:
            dd = float((book.peak - equity) / book.peak) * 100.0
            if dd > book.max_dd_pct:
                book.max_dd_pct = dd

    def _apply_order(self, order, st: MarketState, book: _BookState) -> None:
        existing = book.open_by_inst.get(order.instrument)
        if existing is not None:
            if existing.direction == order.direction:
                return                          # same-side dedup (GAP-0075)
            closed = self._close_at(existing, order.entry_price, st.timestamp, "reverse", book)
            book.trades.append(closed)
            book.realised += closed.pnl
            del book.open_by_inst[order.instrument]
        book.open_by_inst[order.instrument] = _OpenPos(
            instrument=order.instrument, direction=order.direction,
            entry_price=order.entry_price, size_units=order.size_units,
            entry_ts=order.sized_at, stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            strategy_type=order.factors_snapshot.get("strategy_type", "UNKNOWN")
            if isinstance(order.factors_snapshot, Mapping) else "UNKNOWN")

    def _maybe_close(self, pos: _OpenPos, st: MarketState,
                     book: _BookState) -> ClosedTrade | None:
        price = st.mid
        if pos.direction == 1:
            if price <= pos.stop_loss:
                return self._close_at(pos, pos.stop_loss, st.timestamp, "stop", book)
            if pos.take_profit is not None and price >= pos.take_profit:
                return self._close_at(pos, pos.take_profit, st.timestamp, "target", book)
        else:
            if price >= pos.stop_loss:
                return self._close_at(pos, pos.stop_loss, st.timestamp, "stop", book)
            if pos.take_profit is not None and price <= pos.take_profit:
                return self._close_at(pos, pos.take_profit, st.timestamp, "target", book)
        if (st.timestamp - pos.entry_ts).total_seconds() >= self._max_hold_s:
            return self._close_at(pos, price, st.timestamp, "max_hold", book)
        return None

    def _carry_quote(self, pos: _OpenPos, exit_ts: datetime) -> Decimal:
        """Financing over every business-day rollover held, in QUOTE currency."""
        if self._financing is None:
            return Decimal("0")
        conv = self._conventions.get(pos.instrument, "tom_next")
        value = pos.size_units * Decimal(str(pos.entry_price))    # position value, quote ccy
        total = Decimal("0")
        for night in _nights(pos.entry_ts, exit_ts):
            rate = Decimal(str(self._financing(pos.instrument, night, pos.direction)))
            total += value * rate / Decimal("100") / _DAYS_PER_YEAR \
                * Decimal(swap_multiplier(night, conv))
        return total

    def _close_at(self, pos: _OpenPos, exit_price: float, ts: datetime,
                  reason: str, book: _BookState) -> ClosedTrade:
        gross = (Decimal(str(exit_price)) - Decimal(str(pos.entry_price))) \
            * Decimal(pos.direction) * pos.size_units
        friction = Decimal(str(self._cost.slippage_per_side * 2
                               + self._cost.commission_per_side * 2)) * pos.size_units
        carry = self._carry_quote(pos, ts)
        # all three are QUOTE-currency amounts — convert once, at the close rate
        to_acct = quote_to_account(pos.instrument, exit_price, book.last_price)
        return ClosedTrade(entry_ts=pos.entry_ts, exit_ts=ts,
                           pnl=(gross - friction + carry) * to_acct,
                           strategy_type=pos.strategy_type)

    def _unrealised(self, book: _BookState) -> Decimal:
        """Mark EVERY open position off its instrument's last-seen price, converted
        to the account currency at that price."""
        total = Decimal("0")
        for pos in book.open_by_inst.values():
            mark = book.last_price.get(pos.instrument)
            if mark is None:
                continue
            total += (Decimal(str(mark)) - Decimal(str(pos.entry_price))) \
                * Decimal(pos.direction) * pos.size_units \
                * quote_to_account(pos.instrument, mark, book.last_price)
        return total

    def _rule_violations(self, trades: Sequence[ClosedTrade]) -> tuple[str, ...]:
        """§9.5/C-BT-7: platform rules ACTIVE during the run — a breach forces
        passed=False. v1 enforces the rules evaluable from closed trades: min-hold
        and weekend-holding. (News-blackout is already enforced upstream by the
        Governor's two-layer §3.5 gate during the replay.)"""
        if self._rulebook is None:
            return ()
        out: list[str] = []
        for t in trades:
            if t.duration_s < self._rulebook.min_hold_seconds:
                out.append("min_hold")
            if not self._rulebook.weekend_holding_allowed and _crosses_weekend(t.entry_ts, t.exit_ts):
                out.append("weekend_holding")
        return tuple(dict.fromkeys(out))             # dedup, order-preserving

    # -- full walk-forward run ------------------------------------------------- #

    def run(self, *, loop, folds: Sequence[FoldData],
            evolve_fn: Callable[[object, Sequence[MarketState]], None],
            spx_returns: Sequence[float], guardrail_hash: str,
            expected_guardrail_hash: str,
            extra_caveats: Sequence[str] = ()) -> ValidationReport:
        """Drive the ONE composed real `loop` across walk-forward folds. Per fold:
        `evolve_fn` evolves QIEA on the TRAIN states and freezes; the train replay
        feeds a CONTINUOUS in-sample book (transparency only); the test replay
        feeds a CONTINUOUS out-of-sample book — the graded record (C-BT-1)."""
        oos, insample = _BookState(), _BookState()
        for fd in folds:
            evolve_fn(loop, fd.train_states)         # QIEA evolves on TRAIN only
            self._replay(loop, fd.train_states, insample)
            self._replay(loop, fd.test_states, oos)

        # period DERIVED from the real OOS data span (GAP-P11I-01), never a claim.
        if oos.equity:
            period = (oos.equity[0][0], oos.equity[-1][0])
        else:
            now = datetime.now(_UTC)
            period = (now, now)                      # no data ⇒ 0 years ⇒ cannot pass

        oos_returns = _returns_from_equity(oos.equity)
        caveats = (
            "tick backtest cannot fully reproduce live microstructure (GAP-0001)",
            "fills modelled at order price ± declared C8 friction",
            ("overnight financing applied per business-day rollover from the supplied "
             "dated rate model (entry price as the rollover price)"
             if self._financing is not None else
             "NO overnight financing modelled (no rate model supplied) — overnight "
             "and weekend holds are flattered"),
            "PnL converted quote→USD at the close rate (crosses via their quote leg)",
            *extra_caveats,
        )
        return build_report(
            account=self._account, period=period, n_folds=len(folds),
            in_sample=self._metrics(insample, spx_returns),
            out_of_sample=self._metrics(oos, spx_returns), per_regime={},
            guardrail_hash=guardrail_hash, expected_guardrail_hash=expected_guardrail_hash,
            var_breach_frequency=rolling_var_breach_rate(oos_returns),
            rule_violations=self._rule_violations(oos.trades), fidelity_caveats=caveats)

    def _metrics(self, book: _BookState, spx_returns: Sequence[float]) -> MetricBlock:
        equity = book.equity or [(datetime.now(_UTC), self._nav0)]
        # GAP-P11I-04: grade drawdown off the INTRADAY high-water, not the daily curve
        return compute_metrics(trades=book.trades, equity_curve=equity,
                               spx_returns=spx_returns, periods_per_year=self._ppy,
                               max_drawdown_pct_override=book.max_dd_pct)


def _nights(entry: datetime, exit: datetime) -> list:
    """Business days (Mon–Fri) whose 22:00-UTC rollover falls within (entry, exit]
    (22:00 UTC is the spec's daily-boundary anchor, C1). Nothing rolls on Saturday
    or Sunday — the weekend is billed inside the week by the convention's triple
    day (carry.py), so counting weekend nights would charge it twice (GAP-P12D-06)."""
    nights = []
    roll = datetime.combine(entry.date(), time(22, 0), tzinfo=_UTC)
    if roll <= entry:
        roll += timedelta(days=1)
    while roll <= exit:
        if roll.weekday() < 5:
            nights.append(roll.date())
        roll += timedelta(days=1)
    return nights


def _crosses_weekend(entry: datetime, exit: datetime) -> bool:
    """True if the holding period spans the Fri-22:00 → Sun-22:00 closed window
    (a Saturday falls within, or the position is held across it)."""
    d = entry
    while d <= exit:
        if d.weekday() == 5:                         # any Saturday inside the hold
            return True
        d += timedelta(days=1)
    return False
