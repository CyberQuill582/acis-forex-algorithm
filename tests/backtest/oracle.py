"""The oracle positive control (GAP-P12D-37): a strategy KNOWN to be good, graded by the SAME
harness, book, C8 cost map, metrics and §14 report as the engine.

The oracle knows the planted episode state perfectly (`SyntheticMarket.episode_sign`): on every
graded tick it holds one NAV of USD notional (`NOTIONAL_FRACTION`) per instrument in the direction
of the episode in force and reverses the moment the state changes. It never sees the noise and never sees the NEXT episode, so its edge
is exactly the planted edge. On null and permuted it holds the SAME signs, which move no price
there: knowing the sign of a zero drift is worthless.

Invariants:
  * The path is the engine's (`oos_runner.run_walk_forward`): the production config's C8 cost
    map (`evolve_step.cost_model`), account rulebook, swap conventions, session boundaries and
    clusters; ticks through `BacktestDataLoader` (§3 filtering, the FX weekend) merged by event
    time; `Backtest.run` books, marks and grades them. Only the decision layers are replaced.
  * The ticks skip the `MarketStateFactory` (~1 ms/tick: session calendars, velocity rings),
    because nothing downstream of the oracle reads what it adds. `OracleTick` carries ONLY the
    fields the harness and book read, identical to the factory's (`test_oracle_ticks_equal_the
    _factory_path`), so a future read of any other field fails loudly, never on a fake value.
  * Warm-up ticks decide nothing (`observe_only`), as for the engine; the book still manages
    an open position through them.
  * The position is re-asserted at the first graded tick of each UTC day, so a max-hold close
    (48 h, and every weekend) is re-opened rather than leaving the oracle flat.
  * The oracle selects nothing, so its honest trial record is EMPTY. The ratified gate needs
    >= 2 trials, so `passed` is False BY CONSTRUCTION; `non_dsr_failures` is every OTHER clause
    of `report.build_report`'s `passed`, which is what a positive control must clear. Nothing
    here modifies that gate.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Iterator, Mapping, Sequence

from config.account_doctrine import guardrail_hash
from config.schemas import AcisConfig
from core.governor.portfolio_types import SizedOrder
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.evolve_step import cost_model
from tests.backtest.harness import Backtest, FoldData, per_trade_returns
from tests.backtest.money import quote_to_account
from tests.backtest.report import _MIN_FOLDS, _MIN_TRADES, _MIN_YEARS, ValidationReport
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, synthetic_spx
from tests.backtest.walk_forward import Fold

NOTIONAL_FRACTION = Decimal("1")       # USD notional per instrument, as a fraction of NAV (E9)
STRATEGY = "ORACLE"                    # graded inside the §14 duration band (no carve-out)
CAVEAT = ("ORACLE positive control: the decision layers are replaced by perfect knowledge of "
          "the planted episode state; it selects nothing, so its trial record is empty and the "
          "ratified gate (>= 2 trials) cannot pass it (GAP-P12D-37)")


@dataclass(frozen=True)
class OracleTick:
    """The MarketState fields the harness and book read — and nothing it would have to invent."""
    timestamp: datetime
    instrument: str
    bid: float
    ask: float
    spread: float
    mid: float


def oracle_ticks(cfg: AcisConfig, loader: BacktestDataLoader, source: str,
                 instruments: Sequence[str], start: datetime, end: datetime) -> Iterator[OracleTick]:
    """`tick_stream.market_states` without the factory: the same loader filtering and the same
    merge; spread and mid computed exactly as `MarketStateFactory.build` computes them."""
    streams = [loader.stream(source=source, instrument=i, start=start, end=end,
                             max_plausible_spread=cfg.instruments.instruments[i].max_plausible_spread)
               for i in instruments]
    for raw in heapq.merge(*streams, key=lambda t: t.event_time):
        yield OracleTick(timestamp=raw.event_time, instrument=raw.instrument, bid=float(raw.bid),
                         ask=float(raw.ask), spread=float(raw.ask - raw.bid),
                         mid=float((raw.bid + raw.ask) / 2.0))


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

    def __init__(self, market: SyntheticMarket, nav: Decimal) -> None:
        self.book = _Orders()
        self.params = _NoParams()
        self._market = market
        self._notional = nav * NOTIONAL_FRACTION
        self._last: dict[str, float] = {}                   # every instrument's last mid (crosses)
        self._held: dict[str, tuple[int, object]] = {}      # instrument -> (sign, UTC day)

    def units(self, instrument: str, mid: float) -> Decimal:
        """Whole units whose USD notional is `NOTIONAL_FRACTION` of NAV (audit E9: a fixed unit
        count made gold 10,000 oz = $18M on a $10k account), converted exactly as the book books
        PnL (`money.quote_to_account`)."""
        usd_per_unit = Decimal(str(mid)) * quote_to_account(instrument, mid, self._last)
        return Decimal(int(self._notional / usd_per_unit))

    def observe_only(self, st: OracleTick) -> None:
        self._last[st.instrument] = st.mid                  # warm-up decides nothing

    def on_state(self, st: OracleTick) -> None:
        self._last[st.instrument] = st.mid
        sign = int(self._market.episode_sign(st.instrument, st.timestamp))
        key = (sign, st.timestamp.date())
        if self._held.get(st.instrument) == key:
            return                                          # same episode, same day: hold
        self._held[st.instrument] = key
        oid = f"oracle-{len(self.book.orders)}"
        self.book.orders.append(SizedOrder(
            order_id=oid, signal_id=oid, instrument=st.instrument, direction=sign,
            size_units=self.units(st.instrument, st.mid), entry_price=st.mid,
            # a stop no planted episode reaches: the oracle exits by reversing, never by stop
            stop_loss=st.mid * (0.5 if sign > 0 else 2.0), take_profit=None,
            reason="oracle: the planted episode in force",
            factors_snapshot=MappingProxyType({"strategy_type": STRATEGY}),
            sized_at=st.timestamp, param_set_id="oracle"))
        self.book.strategy_of[oid] = STRATEGY


@dataclass(frozen=True)
class OracleGrade:
    kind: str
    report: ValidationReport
    trade_returns: tuple[float, ...]        # pnl / USD notional, the Deflated Sharpe's series
    net_pnl: Decimal


def grade_oracle(spec: MarketSpec, cfg: AcisConfig, account: str, folds: Sequence[Fold], logger,
                 *, instruments: Sequence[str] | None = None) -> OracleGrade:
    market = SyntheticMarket(spec)
    insts = sorted(instruments if instruments is not None else cfg.instruments.enabled)
    specs = cfg.instruments.instruments
    bt = Backtest(account=account, cost_models={i: cost_model(cfg, i) for i in insts},
                  rulebook=cfg.platform_rules.accounts[account],
                  swap_conventions={i: specs[i].swap_convention for i in insts},
                  session_boundaries=cfg.system.session_boundaries, clusters=cfg.instruments.clusters)
    loader = BacktestDataLoader({market.name: market}, logger)

    def stream(start: datetime, end: datetime) -> Iterator[OracleTick]:
        return oracle_ticks(cfg, loader, market.name, insts, start, end)

    limits = guardrail_hash(cfg.guardrails)
    report = bt.run(
        loop=OracleLoop(market, nav=bt.portfolio_state().nav),
        folds=[FoldData(f, stream(f.test_start, f.test_end), warmup_states=stream(f.train_end, f.test_start))
               for f in folds],
        evolve_fn=lambda lp, fd: {"fold": fd.fold.index, "champions": 0, "trial_sharpes": [], "regimes": {}},
        spx_closes=synthetic_spx(spec.start, spec.days), guardrail_hash=limits,
        expected_guardrail_hash=limits, extra_caveats=(CAVEAT,))
    trades = bt.graded_trades()
    return OracleGrade(kind=spec.kind, report=report, trade_returns=tuple(per_trade_returns(trades)),
                       net_pnl=sum((t.pnl for t in trades), Decimal("0")))


def non_dsr_failures(report: ValidationReport, expected_guardrail_hash: str) -> tuple[str, ...]:
    """Every clause of the ratified `passed` EXCEPT the trial count and the Deflated Sharpe,
    read from report.py's own constants (one source): what a positive control must clear."""
    out = [f"section-14 {k}" for k, ok in report.targets_met.items() if not ok]
    years = (report.period[1] - report.period[0]) / timedelta(days=365.25)
    if years < _MIN_YEARS:
        out.append(f"graded span {years:.2f} y < {_MIN_YEARS:g} y")
    if report.n_folds < _MIN_FOLDS:
        out.append(f"{report.n_folds} fold(s) < {_MIN_FOLDS}")
    if report.out_of_sample.n_trades < _MIN_TRADES:
        out.append(f"{report.out_of_sample.n_trades} trades < {_MIN_TRADES}")
    out += [f"rule violation {v}" for v in report.rule_violations]
    if report.guardrail_hash != expected_guardrail_hash:
        out.append("guardrail hash differs from production")
    return tuple(out)


def void_reasons(failures: Mapping[str, Sequence[str]]) -> list[str]:
    """Why an engine falsification verdict is VOID (GAP-P12D-37): the harness must recognise
    the oracle on planted (no non-DSR failure) and refuse it wherever its knowledge is
    worthless (null, permuted: at least one). `failures` maps market kind -> the oracle's
    `non_dsr_failures` on that market."""
    out = []
    for kind, fails in sorted(failures.items()):
        if kind == "planted" and fails:
            out.append(f"the planted oracle failed: {', '.join(fails)}")
        elif kind != "planted" and not fails:
            out.append(f"the {kind} oracle cleared every non-DSR clause: the grader cannot tell "
                       "knowledge of a zero drift from an edge")
    return out
