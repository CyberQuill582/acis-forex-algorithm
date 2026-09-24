"""C2 reproduction: what `passed` does not look at, and one input it over-trusts.

    cd /tmp/review-acis && python <this file>

1. `build_report` (tests/backtest/report.py:265-274) sets `passed` without reading
   `var_breach_frequency` or `fidelity_caveats`. A run whose 1% VaR is breached on 20% of days
   and that says "NO overnight financing modelled" still passes.
2. The Deflated Sharpe's T is the number of TRADES (harness.py:220). Trades that are one
   decision booked twice (a pair's two legs, or one signal on two correlated instruments) count
   as independent observations. Booking every return twice leaves the Sharpe unchanged and
   raises the DSR.
3. Open positions are marked at the MID with no exit friction (book.py:158-167), so the
   equity curve, the drawdown and the Governor's NAV all omit the cost of getting out.
"""

from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from tests.backtest.book import BookState, OpenPos, PositionModel   # noqa: E402
from tests.backtest.deflated_sharpe import deflated_sharpe          # noqa: E402
from tests.backtest.metrics import MetricBlock                      # noqa: E402
from tests.backtest.report import build_report                      # noqa: E402
from core.optimizer.costs import CostModel                          # noqa: E402

UTC = timezone.utc


def one():
    good = MetricBlock(annual_sharpe=2.0, max_drawdown_pct=5.0, win_rate=0.55, profit_factor=1.8,
                       positive_months_pct=80.0, spx_correlation=0.0,
                       avg_trade_duration_s=3600.0, tsmom_avg_duration_s=0.0,
                       scalp_avg_duration_s=0.0, n_trades=400)
    t0 = datetime(2014, 1, 1, tzinfo=UTC)
    rep = build_report(account="a", period=(t0, t0 + timedelta(days=800)), n_folds=10,
                       in_sample=good, out_of_sample=good, per_regime={}, guardrail_hash="g",
                       expected_guardrail_hash="g", var_breach_frequency=0.20,
                       rule_violations=(),
                       fidelity_caveats=("NO overnight financing modelled (no rate model supplied) "
                                         "— overnight and weekend holds are flattered",),
                       trial_count=50, deflated_sharpe=0.97)
    print("1. var_breach_frequency=0.20 (20x the 1% level) + 'NO overnight financing' caveat ->"
          f" passed={rep.passed}")


def two():
    rng = random.Random(1)
    r = [rng.gauss(0.0004, 0.01) for _ in range(300)]      # per-trade returns, weak edge
    trials = [rng.gauss(0.0, 0.05) for _ in range(40)]      # 40 candidate trial Sharpes
    d1 = deflated_sharpe(r, trials, 40)
    d2 = deflated_sharpe(r + r, trials, 40)                # every decision booked as two trades
    d4 = deflated_sharpe(r * 4, trials, 40)
    print(f"2. DSR on 300 independent trade returns = {d1:.3f}; the same decisions booked twice "
          f"= {d2:.3f}; four times = {d4:.3f}  (the Sharpe itself is unchanged)")


def three():
    pm = PositionModel(costs={"EUR_USD": CostModel(0.0, 0.00002)}, max_hold_s=172800)
    book = BookState()
    ts = datetime(2026, 1, 6, 12, tzinfo=UTC)
    book.open_by_inst["EUR_USD"] = OpenPos("EUR_USD", 1, 1.10000, Decimal("100000"), ts,
                                           1.09000, None, "TREND", entry_spread=0.0001)
    book.last_price["EUR_USD"] = 1.10000
    marked = pm.unrealised(book)
    closed = pm.close_at(book.open_by_inst["EUR_USD"], 1.10000, ts, "mark", book, 0.0001)
    print(f"3. a flat 1-lot EUR_USD long, marked: unrealised = {marked:+.2f} USD; what closing it "
          f"at that same mid actually books = {closed.pnl:+.2f} USD (entry + exit friction). "
          "The mark omits all of it, entry friction included.")


if __name__ == "__main__":
    one()
    two()
    three()
