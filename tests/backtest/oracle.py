"""The oracle positive control (GAP-P12D-37): a strategy KNOWN to be good, graded by the SAME
harness, book, C8 cost map, metrics and §14 report as the engine. Its decisions (what, when,
how much, and the account rules it keeps) live in oracle_loop.py; this module grades it.

The oracle knows the planted episode state perfectly and nothing else, so its edge is exactly the
planted edge. On null and permuted it holds the SAME signs, which move no price there: knowing the
sign of a zero drift is worthless.

Invariants:
  * The path is the engine's (`oos_runner.run_walk_forward`): the production config's C8 cost
    map (`evolve_step.cost_model`), account rulebook, swap conventions, session boundaries and
    clusters; ticks through `BacktestDataLoader` (§3 filtering, the FX weekend) merged by event
    time; `Backtest.run` books, marks and grades them. Only the decision layers are replaced.
  * The ticks skip the `MarketStateFactory` (~1 ms/tick: session calendars, velocity rings),
    because nothing downstream of the oracle reads what it adds. `OracleTick` carries ONLY the
    fields the harness and book read, identical to the factory's (`test_oracle_ticks_equal_the
    _factory_path`), so a future read of any other field fails loudly, never on a fake value.
  * The oracle obeys the account's evaluable rules (oracle_loop.py, audit F2). So a rule
    violation on ANY market means the oracle or the rule model is broken, and a control
    (null, permuted) counts as refused only by a §14 row, never by a rule or a sample floor.
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
from typing import Iterator, Mapping, Sequence

from config.account_doctrine import guardrail_hash
from config.schemas import AcisConfig
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.evolve_step import cost_model
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.metrics import ClosedTrade
from tests.backtest.oracle_loop import OracleLoop, OracleTick
from tests.backtest.report import _MIN_FOLDS, _MIN_TRADES, _MIN_YEARS, ValidationReport
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, synthetic_spx
from tests.backtest.walk_forward import Fold

CAVEAT = ("ORACLE positive control: the decision layers are replaced by perfect knowledge of "
          "the planted episode state; it selects nothing, so its trial record is empty and the "
          "ratified gate (>= 2 trials) cannot pass it (GAP-P12D-37)")


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


@dataclass(frozen=True)
class OracleGrade:
    kind: str
    report: ValidationReport
    net_pnl: Decimal
    trades: tuple[ClosedTrade, ...] = ()    # the book's closed trades (the leakage suite's fills)
    orders: tuple = ()                      # the loop's SizedOrders (the leakage suite's decisions)


def grade_oracle(spec: MarketSpec, cfg: AcisConfig, account: str, folds: Sequence[Fold], logger,
                 *, instruments: Sequence[str] | None = None, sign_error: float = 0.0,
                 market: SyntheticMarket | None = None, loop_cls: type[OracleLoop] = OracleLoop) -> OracleGrade:
    """`sign_error` > 0 grades a weaker rung of the same oracle (oracle_loop.py, audit E1). The
    leakage suite passes a perturbed `market` and a leaky `loop_cls` (GAP-P12D-65)."""
    market = market if market is not None else SyntheticMarket(spec)
    insts = sorted(instruments if instruments is not None else cfg.instruments.enabled)
    specs = cfg.instruments.instruments
    rulebook = cfg.platform_rules.accounts[account]
    bt = Backtest(account=account, cost_models={i: cost_model(cfg, i) for i in insts},
                  rulebook=rulebook,
                  swap_conventions={i: specs[i].swap_convention for i in insts},
                  session_boundaries=cfg.system.session_boundaries, clusters=cfg.instruments.clusters)
    loader = BacktestDataLoader({market.name: market}, logger)

    def stream(start: datetime, end: datetime) -> Iterator[OracleTick]:
        return oracle_ticks(cfg, loader, market.name, insts, start, end)

    limits = guardrail_hash(cfg.guardrails)
    loop = loop_cls(market, nav=bt.portfolio_state().nav, rulebook=rulebook,
                    flat_before=[f.test_end for f in folds], sign_error=sign_error)
    report = bt.run(
        loop=loop,
        folds=[FoldData(f, stream(f.test_start, f.test_end), warmup_states=stream(f.train_end, f.test_start))
               for f in folds],
        evolve_fn=lambda lp, fd: {"fold": fd.fold.index, "champions": 0, "trial_sharpes": [], "regimes": {}},
        spx_closes=synthetic_spx(spec.start, spec.days), guardrail_hash=limits,
        expected_guardrail_hash=limits, extra_caveats=(CAVEAT,))
    trades = bt.graded_trades()
    return OracleGrade(kind=spec.kind, report=report,
                       net_pnl=sum((t.pnl for t in trades), Decimal("0")), trades=trades,
                       orders=tuple(loop.book.orders))


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


# What stage 1 expects of each oracle it grades: the perfect oracle and the rung just above the
# §14 cut-offs must PASS every non-DSR clause; the rung just below them, and every control, must be
# REFUSED by a §14 row (audit E1: power near the cut-off, not only against an overwhelming edge).
EXPECTED = {"planted": "pass", "planted-near-pass": "pass", "planted-near-fail": "refuse",
            "null": "refuse", "permuted": "refuse"}
# The rungs' per-episode sign-error rates, calibrated on the falsification default plan
# (plan(60, 30, 25), the 20 s tape, dev_paper). Profit factor (1.4) binds first for this trade
# structure: near-pass 0.42 graded PF 1.593 on EUR_USD + USD_JPY, every clause met; near-fail
# 0.46 graded PF 1.251 (EUR_USD) and 1.316 (USD_JPY), so the pooled PF lies between them
# (the oracle decides per instrument), failing that row alone.
RUNGS = {"planted-near-pass": 0.42, "planted-near-fail": 0.46}


def void_reasons(failures: Mapping[str, Sequence[str]]) -> list[str]:
    """Why an engine falsification verdict is VOID (GAP-P12D-37). `failures` maps an `EXPECTED`
    key -> that oracle's `non_dsr_failures`. A "pass" oracle must show no failure at all; a
    "refuse" oracle must be refused BY A §14 ROW (audit F2: a refusal by a rule violation or a
    sample floor proves nothing about the grade). The oracle keeps the account's rules, so a rule
    violation on any market voids the run by itself."""
    out = []
    for kind, fails in sorted(failures.items()):
        broken = [f for f in fails if f.startswith("rule violation")]
        if broken:
            out.append(f"the {kind} oracle broke the account's rules ({', '.join(broken)}): it is "
                       "built to keep them, so the oracle or the rule model is wrong")
        if EXPECTED[kind] == "pass" and fails:
            out.append(f"the {kind} oracle failed: {', '.join(fails)}")
        elif EXPECTED[kind] == "refuse" and not any(f.startswith("section-14") for f in fails):
            out.append(f"the {kind} oracle was not refused by any section-14 row "
                       f"({', '.join(fails) or 'it cleared every non-DSR clause'}): the grader "
                       "cannot tell it from an edge")
    return out
