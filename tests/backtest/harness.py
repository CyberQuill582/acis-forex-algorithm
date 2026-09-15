"""Real-engine walk-forward harness (ACIS-09 §2/§3/§7, master §13/§15).

Drives the ACTUAL ACIS decision layers — the real `MarketStateFactory`, NVMA, AGON and
Capital Governor composed exactly as production (the phase-7 `build_paper_loop` wiring)
— over walk-forward folds, per account. It is NOT a re-implementation (C-BT-3): a change
in NVMA behaviour changes the result, because NVMA itself runs. The position book and
fill/close model live in `book.py`.

Invariants:
  * Per fold, `evolve_fn` evolves on data before `fold.train_end` and stages params; then
    the fold's TEST ticks replay into ONE continuous out-of-sample book (GAP-P11I-03). The
    graded record is that book only (C-BT-1). Test ticks may be a lazy stream, iterated
    once, so years of ticks never sit in memory.
  * Training windows are NOT replayed through the engine: rolling folds would send the
    engine back in time, and it is transparency only. The in-sample record is each fold's
    evolution summary (owner ruling 2026-09-15, GAP-P12D-18).
  * The first test tick must come at least the max hold after `fold.train_end`, checked on
    the real data (embargo, GAP-SP12E-03). Warm-up ticks between the two feed the engine's
    windows and manage open positions, but decide nothing (GAP-P12D-24).
  * On every tick, open positions are managed BEFORE the boundary sweep, so a position
    closed on that tick does not block a promotion.
  * Staged params promote only at simulated session boundaries, through
    `ParamLibrary.on_boundary`, and only when THIS book is flat: the harness is the
    loop's `PositionGate` (ACIS-03 §7 C2; wire it with `build_paper_loop(position_gate=…)`).
  * Deflated Sharpe (owner ruling GAP-P12D-25, "real selection set"): the trials are the
    holdout per-trade Sharpe ratios of every candidate champion in the fold records; N is
    their count plus `min_trials` (the attempt-registry entries); the graded series is the
    out-of-sample per-trade return (pnl / USD notional). With fewer than 2 trial Sharpe
    ratios no N may be claimed, so the run cannot pass.
  * The graded `period` is derived from the OOS data span (GAP-P11I-01); the §9.5 rulebook
    is enforced on the realised trades (C-BT-7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable, Mapping, Sequence

from config.schemas import ZonedTime
from core.data.fx_clock import holds_through_weekend
from core.data.normaliser import MarketState
from core.optimizer.costs import CostModel
from tests.backtest.book import BookState, PositionModel
from tests.backtest.boundary_clock import BoundaryClock
from tests.backtest.carry import FinancingRate
from tests.backtest.deflated_sharpe import deflated_sharpe
from core.governor.portfolio_types import PortfolioState
from tests.backtest.metrics import (ClosedTrade, MetricBlock, _returns_from_equity,
                                    compute_metrics, rolling_var_breach_rate)
from tests.backtest.portfolio_view import build_portfolio_state
from tests.backtest.report import ValidationReport, build_report
from tests.backtest.walk_forward import Fold, require_embargo

_UTC = timezone.utc
NOT_REPLAYED = MetricBlock(
    annual_sharpe=math.nan, max_drawdown_pct=math.nan, win_rate=math.nan,
    profit_factor=math.nan, positive_months_pct=math.nan, spx_correlation=math.nan,
    avg_trade_duration_s=math.nan, tsmom_avg_duration_s=math.nan,
    scalp_avg_duration_s=math.nan, n_trades=0)


@dataclass(frozen=True)
class FoldData:
    fold: Fold
    test_states: Iterable[MarketState]      # time-ordered; may be a one-shot stream
    # observe-only ticks from train_end up to test_start: the engine's windows stay warm
    # through the embargo, but nothing is decided on them (GAP-P12D-24 F-E3/F-E4)
    warmup_states: Iterable[MarketState] = ()


EvolveFn = Callable[[object, FoldData], "Mapping | None"]


def refuse_lookahead(record: Mapping, fold: Fold) -> None:
    """GAP-P12D-28: an evolution record may not cite a bar that opens at or after its fold's
    train end — that bar's price belongs to the embargo or the test window. It checks the
    spans the record reports (evolve_step.py records every candidate's first and last bar),
    so it catches a leaky data path, not an evolve function that misreports its own spans."""
    for regime, entry in record.get("regimes", {}).items():
        for c in entry.get("candidates", ()):
            last = c.get("last_bar")
            if last is not None and datetime.fromisoformat(last) >= fold.train_end:
                raise ValueError(f"look-ahead: fold {fold.index} evolved {regime} on "
                                 f"{c.get('instrument')} with a bar at {last}, at or after its "
                                 f"train end {fold.train_end.isoformat()}")


class Backtest:
    def __init__(self, *, account: str, cost_models: Mapping[str, CostModel], rulebook=None,
                 nav: Decimal = Decimal("10000"), max_hold_s: float = 48 * 3600,
                 periods_per_year: float = 252.0,
                 financing: FinancingRate | None = None,
                 swap_conventions: Mapping[str, str] | None = None,
                 session_boundaries: Sequence[ZonedTime] = (),
                 clusters: Mapping[str, Sequence[str]] | None = None) -> None:
        self._clusters = dict(clusters or {})
        self._last_ts: datetime | None = None
        self._account = account
        self.positions = PositionModel(costs=cost_models, max_hold_s=max_hold_s,
                                       financing=financing, swap_conventions=swap_conventions)
        self._rulebook = rulebook                    # §9.5 account rules (or None)
        self._nav0 = nav
        self._max_hold_s = max_hold_s
        self._ppy = periods_per_year
        self._financing = financing
        self._clock = BoundaryClock(session_boundaries) if session_boundaries else None
        self._active: BookState | None = None
        self._seen_orders = 0                        # watermark over the loop's order list

    def open_position_count(self) -> int:
        """The ParamLibrary `PositionGate` in a backtest: this book is the position layer."""
        return len(self._active.open_by_inst) if self._active is not None else 0

    def portfolio_state(self) -> PortfolioState:
        """The Governor's `portfolio_fn` in a replay (GAP-P12D-21): the real snapshot."""
        book = self._active or BookState()
        nav = self._nav0 + book.realised + self.positions.unrealised(book)
        return build_portfolio_state(book=book, nav=nav, clusters=self._clusters,
                                     as_of=self._last_ts or datetime.now(_UTC))

    # -- one fold's test replay through the REAL engine ------------------------- #

    def _replay(self, loop, fd: FoldData, book: BookState) -> None:
        self._active = book
        for st in fd.warmup_states:                  # observe-only: no signals, no orders
            self._tick(loop, st, book, trade=False)
        first = True
        for st in fd.test_states:
            if first:                                # embargo, on the real data
                require_embargo(fd.fold.index, fd.fold.train_end, st.timestamp, self._max_hold_s)
                first = False
            self._tick(loop, st, book, trade=True)

    def _tick(self, loop, st: MarketState, book: BookState, *, trade: bool) -> None:
        book.last_price[st.instrument] = st.mid
        pos = book.open_by_inst.get(st.instrument)
        if pos is not None:                          # existing positions are always managed
            closed = self.positions.maybe_close(pos, st, book)
            if closed is not None:
                book.book_close(closed, st.instrument)
        if self._clock is not None:                  # after the close, so a carried position frees the gate (F-I7)
            for boundary in self._clock.crossed(st.timestamp):
                loop.params.on_boundary(boundary)    # C2: promotes only when flat
        self._last_ts = st.timestamp
        # the daily-limit anchor moves at the new trading day's FIRST observation, before any
        # decision on this tick reads the portfolio (the Risk Monitor's semantics)
        pre = self._nav0 + book.realised + self.positions.unrealised(book)
        if book.marker.observe(st.timestamp, pre) or book.day_anchor is None:
            book.day_anchor = pre
        if not trade:
            loop.observe_only(st)
        else:
            loop.on_state(st)                        # NVMA → AGON → Governor
            new_orders = loop.book.orders[self._seen_orders:]
            self._seen_orders = len(loop.book.orders)
            strategy_of = getattr(loop.book, "strategy_of", {})     # GAP-P12D-20
            for order in new_orders:
                self.positions.apply_order(order, st, book, strategy_of.get(order.order_id))
        marked = self._nav0 + book.realised + self.positions.unrealised(book)
        self.positions.mark_drawdown(book, marked)
        day = st.timestamp.date()
        if day != book.last_day:
            book.equity.append((st.timestamp, marked))
            book.last_day = day

    def _rule_violations(self, trades: Sequence[ClosedTrade]) -> tuple[str, ...]:
        """§9.5/C-BT-7: min-hold and weekend-holding, evaluable from closed trades. (The
        news blackout is enforced upstream by the Governor's §3.5 gate during the replay.)"""
        if self._rulebook is None:
            return ()
        out: list[str] = []
        for t in trades:
            if t.duration_s < self._rulebook.min_hold_seconds:
                out.append("min_hold")
            if not self._rulebook.weekend_holding_allowed and holds_through_weekend(t.entry_ts, t.exit_ts):
                out.append("weekend_holding")
        return tuple(dict.fromkeys(out))

    # -- full walk-forward run ------------------------------------------------- #

    def run(self, *, loop, folds: Sequence[FoldData], evolve_fn: EvolveFn,
            spx_closes: Mapping[date, float], guardrail_hash: str,
            expected_guardrail_hash: str, extra_caveats: Sequence[str] = (),
            min_trials: int = 0) -> ValidationReport:
        oos = BookState()
        evolution: list[Mapping] = []
        for fd in folds:
            record = evolve_fn(loop, fd)             # evolves on data before train_end only
            if record is not None:
                evolution.append(record)
                refuse_lookahead(record, fd.fold)    # GAP-P12D-28 look-ahead canary guard
                if record.get("champions") and self._clock is None:   # GAP-P12D-24 F-I6
                    raise ValueError("params were staged but this backtest declares no session "
                                     "boundaries, so they could never promote")
            self._replay(loop, fd, oos)

        if oos.equity:                               # GAP-P11I-01: derived, never claimed
            period = (oos.equity[0][0], oos.equity[-1][0])
        else:
            now = datetime.now(_UTC)
            period = (now, now)                      # no data ⇒ 0 years ⇒ cannot pass

        # GAP-P12D-25: every candidate champion's holdout per-trade Sharpe is a trial
        trials = [s for r in evolution for s in r.get("trial_sharpes", ()) if s is not None]
        n_trials = len(trials) + min_trials if len(trials) >= 2 else len(trials)
        trade_returns = [float(t.pnl / t.notional_usd) for t in oos.trades if t.notional_usd]
        oos_returns = _returns_from_equity(oos.equity)
        caveats = (
            "tick backtest cannot fully reproduce live microstructure (GAP-0001)",
            "fills modelled at order price ± each instrument's declared C8 friction",
            ("overnight financing applied per business-day rollover from the supplied "
             "dated rate model (entry price as the rollover price)"
             if self._financing is not None else
             "NO overnight financing modelled (no rate model supplied) — overnight "
             "and weekend holds are flattered"),
            "PnL converted quote→USD at the close rate (crosses via their quote leg)",
            "in-sample block not replayed: the per-fold evolution records are the in-sample "
            "transparency record (GAP-P12D-18)",
            "Deflated Sharpe on per-trade returns; its trials are the candidate champions scored "
            "by QIEA's dual-EMA fitness harness, not the full engine (GAP-P12D-25, GAP-0035)",
            *(() if n_trials >= 2 else ("fewer than 2 candidate-champion Sharpe ratios — selection "
                                        "bias is uncorrected, so the run cannot pass (GAP-P12D-16)",)),
            *extra_caveats,
        )
        return build_report(
            account=self._account, period=period, n_folds=len(folds),
            in_sample=NOT_REPLAYED, out_of_sample=self._metrics(oos, spx_closes), per_regime={},
            guardrail_hash=guardrail_hash, expected_guardrail_hash=expected_guardrail_hash,
            var_breach_frequency=rolling_var_breach_rate(oos_returns),
            rule_violations=self._rule_violations(oos.trades), fidelity_caveats=caveats,
            trial_count=n_trials,
            deflated_sharpe=deflated_sharpe(trade_returns, trials, n_trials),
            in_sample_evolution=evolution)

    def _metrics(self, book: BookState, spx_closes: Mapping[date, float]) -> MetricBlock:
        equity = book.equity or [(datetime.now(_UTC), self._nav0)]
        return compute_metrics(trades=book.trades, equity_curve=equity,
                               rollover_marks=book.marker.marks, spx_closes=spx_closes,
                               periods_per_year=self._ppy,
                               max_drawdown_pct_override=book.max_dd_pct)
