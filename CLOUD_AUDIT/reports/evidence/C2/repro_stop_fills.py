"""C2 reproduction: three ways the GRADED book (tests/backtest/book.py) pays out profit
that a broker's server-side stop would not have paid. Synthetic ticks only.

Run from the review tree (read-only use; writes nothing):
    cd /tmp/review-acis && python <this file>

Each scenario drives the REAL Backtest.run -> PositionModel -> ValidationReport path,
with the REAL loader filter (BacktestDataLoader.stream + max_plausible_spread from
config/instruments.yaml) and the REAL MarketStateFactory. Only the decision loop is
scripted: it opens ONE long EUR_USD position at a fixed tick, the way a signal would.

  A  weekend gap through the stop   -> the book exits AT the stop price
  B  rollover spread spike (> 5 pip)-> the loader DROPS the tick; the stop never fires,
                                       and the trade later books as a WIN
  C  a 4-pip spread (kept) with the BID through the stop -> the mid never reaches
                                       the stop, so the position survives
"Fair" = a broker sell-stop: it triggers on bid <= stop and fills at that bid (or worse).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from config.schemas import load_config                         # noqa: E402
from core.data.normaliser import RawTick                       # noqa: E402
from core.governor.portfolio_types import SizedOrder           # noqa: E402
from tests.backtest.data_loader import BacktestDataLoader, TickSource  # noqa: E402
from tests.backtest.evolve_step import cost_model              # noqa: E402
from tests.backtest.harness import Backtest, FoldData          # noqa: E402
from tests.backtest.tick_stream import build_factory, market_states  # noqa: E402
from tests.backtest.walk_forward import Fold                   # noqa: E402

UTC = timezone.utc
INST = "EUR_USD"
UNITS = Decimal("100000")          # one standard lot, so pips read as $10


class _Log:
    def event(self, *a, **k):
        pass


class ListSource(TickSource):
    name = "scripted"

    def __init__(self, quotes):
        self._q = quotes            # [(ts, bid, ask)]

    def load(self, instrument, start, end):
        for ts, bid, ask in self._q:
            if start <= ts < end:
                yield RawTick(event_time=ts, recv_time=ts, instrument=instrument, bid=bid,
                              ask=ask, volume=1.0, book=None, provider=self.name, raw_payload={})


class _Book:
    def __init__(self):
        self.orders = []


class ScriptedLoop:
    """Opens one long at `at` with the given stop/target: the only scripted part."""

    def __init__(self, at, stop, target):
        self.book = _Book()
        self._at, self._stop, self._target = at, stop, target

    def on_state(self, st):
        if st.timestamp == self._at:
            self.book.orders.append(SizedOrder(
                order_id="o1", signal_id="s1", instrument=INST, direction=1, size_units=UNITS,
                entry_price=st.mid, stop_loss=self._stop, take_profit=self._target,
                reason="scripted", factors_snapshot=MappingProxyType({"strategy_type": "TREND"}),
                sized_at=st.timestamp, param_set_id="p", group_id=None, action="open"))

    def observe_only(self, st):
        pass


def run(quotes, open_at, stop, target, label, fair_exit_bid, cfg):
    loader = BacktestDataLoader({"scripted": ListSource(quotes)}, _Log())
    factory = build_factory(cfg, [INST])
    start, end = quotes[0][0], quotes[-1][0] + timedelta(seconds=1)
    fold = Fold(0, start - timedelta(days=10), start - timedelta(days=3), start, end)
    states = list(market_states(cfg=cfg, loader=loader, factory=factory, source="scripted",
                                instruments=[INST], start=start, end=end))
    bt = Backtest(account="scripted", cost_models={INST: cost_model(cfg, INST)})
    rep = bt.run(loop=ScriptedLoop(open_at, stop, target), folds=[FoldData(fold, states)],
                 evolve_fn=lambda lp, fd: None, spx_closes={}, guardrail_hash="g",
                 expected_guardrail_hash="g")
    booked = sum((s.net_pnl for s in rep.per_strategy.values()), Decimal("0"))
    entry = next(q for q in quotes if q[0] == open_at)
    slip = cost_model(cfg, INST).slippage_per_side
    fair = (Decimal(str(fair_exit_bid)) - Decimal(str(entry[2])) - Decimal(str(2 * slip))) * UNITS
    print(f"\n[{label}]")
    print(f"  ticks supplied={len(quotes)}  ticks that reached the engine={len(states)}")
    print(f"  harness booked net PnL = {booked:+.2f} USD over {rep.out_of_sample.n_trades} trade(s)"
          f"  win_rate={rep.out_of_sample.win_rate:.2f}")
    print(f"  broker sell-stop (fills at the bid) = {fair:+.2f} USD")
    print(f"  harness flatters this trade by {booked - fair:+.2f} USD")
    return booked, fair


def main():
    cfg = load_config(ROOT / "config")
    print("EUR_USD max_plausible_spread =", cfg.instruments.instruments[INST].max_plausible_spread,
          "| C8 slippage/side =", cfg.instruments.instruments[INST].costs.slippage_per_side)

    # A: Friday 20:00 UTC long, stop 5.5 pips below; the market reopens Sunday 50 pips lower.
    fri = datetime(2026, 1, 9, 20, 0, tzinfo=UTC)
    sun = datetime(2026, 1, 11, 22, 5, tzinfo=UTC)
    qa = [(fri, 1.10000, 1.10010), (fri + timedelta(minutes=30), 1.10000, 1.10010),
          (sun, 1.09490, 1.09510), (sun + timedelta(minutes=5), 1.09480, 1.09500)]
    run(qa, fri, 1.09950, 1.10500, "A weekend gap through the stop", 1.09490, cfg)

    # B: Tuesday long; at the 17:00 New York rollover (22:00 UTC in January) the spread blows out
    # to 20 pips and the bid trades 10 pips through the stop; then price recovers to the target.
    tue = datetime(2026, 1, 6, 20, 0, tzinfo=UTC)
    roll = datetime(2026, 1, 6, 22, 0, 30, tzinfo=UTC)
    qb = [(tue, 1.10000, 1.10010), (roll, 1.09850, 1.10050),
          (roll + timedelta(minutes=10), 1.10050, 1.10060),
          (roll + timedelta(hours=2), 1.10320, 1.10330)]
    run(qb, tue, 1.09950, 1.10300, "B rollover spike: the tick is dropped, the stop never fires",
        1.09850, cfg)

    # C: a 4-pip spread (under the 5-pip filter, so kept); bid 1.09930 <= stop 1.09950 but the
    # mid 1.09950+ is not below it -> no trigger; price then rallies to the target.
    qc = [(tue, 1.10000, 1.10010), (roll, 1.09930, 1.09972),
          (roll + timedelta(minutes=10), 1.10050, 1.10060),
          (roll + timedelta(hours=2), 1.10320, 1.10330)]
    run(qc, tue, 1.09950, 1.10300, "C mid-triggered stop: bid through the stop, mid not", 1.09930, cfg)


if __name__ == "__main__":
    main()
