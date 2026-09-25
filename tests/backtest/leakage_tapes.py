"""Short tapes and decision extractors for the component-level leakage sweeps (GAP-P12D-65).

Mental model:
  * Each tape is small enough to rerun once per cut, because the sweep is exhaustive: one
    cut per decision point of the component (every tick, or every bar), never a sample.
  * A tape's future is changed at the source and only there: `tick_tape_variant` perturbs or
    deletes every tick stamped >= the cut (prices, spreads and tick rates); `bar_tape_variant`
    does the same for bars on a bar-index time axis (bar k opens at k, closes before k + 1).
  * Bar tapes carry an independent OPEN per bar (a two-point path per bar): bar k opens at k
    and closes at k + 0.5, and both points are cuts. Truncating only at whole bars would hide
    a peek at the NEXT close, because a signal is emitted with its fill at the next open.
  * `trade_path_decisions` stamps the fitness simulator's decisions on that axis: an entry
    signal is decided at its bar's close (i + 0.5) and emitted with its fill at the next open
    (i + 1); an exit the open settles (a gap through the stop, or an open beyond the target)
    is decided at bar j's OPEN and stamped j, so any read of bar j's
    close, range or closing spread shows (the audit's MEDIUM-2 / X2); an intrabar or
    max-hold exit is stamped j + 0.5;
    the window-end mark (GAP-0039) is bookkeeping, not a decision, and is never compared.
    The fill's C8 cost is NOT in the fill decision: the simulator charges the entry bar's
    CLOSING spread for a fill at its open (a finding; tests/unit/test_fitness_exits.py pins the
    charge exactly, e.g. `test_a_trade_open_at_the_window_end_is_marked_at_the_last_close`).
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Sequence

from core.optimizer.fitness import AT_THE_OPEN, Trade
from core.optimizer.param_types import LabelledBar
from core.regime.regime_types import RegimeType
from tests.backtest.leakage import Decision, perturb_path


class TickTape:
    """Parallel lists: a tick's time, mid, spread and tick velocity."""

    def __init__(self, ts: Sequence[datetime], mid: Sequence[float], spread: Sequence[float],
                 velocity: Sequence[float]) -> None:
        self.ts, self.mid, self.spread, self.velocity = list(ts), list(mid), list(spread), list(velocity)

    def __len__(self) -> int:
        return len(self.ts)


def tick_tape(start: datetime, n: int, seed: int, *, gap_s: tuple[int, int] = (5, 40),
              vol: float = 3e-4) -> TickTape:
    rng = random.Random(seed)
    ts, t = [], start
    for _ in range(n):
        ts.append(t)
        t += timedelta(seconds=rng.randint(*gap_s))
    mid = [1.1]
    for i in range(1, n):
        drift = vol * 0.4 * (1 if (i // 25) % 2 else -1)          # trending stretches
        mid.append(mid[-1] * math.exp(rng.gauss(drift, vol)))
    return TickTape(ts, mid, [1e-4 * (1 + rng.random()) for _ in range(n)],
                    [10.0 * (0.3 + 2.7 * rng.random()) for _ in range(n)])


def tick_tape_variant(tape: TickTape, cut: datetime, mode: str) -> TickTape:
    k = next((i for i, t in enumerate(tape.ts) if t >= cut), len(tape))
    if mode == "truncate":
        return TickTape(tape.ts[:k], tape.mid[:k], tape.spread[:k], tape.velocity[:k])
    if k == 0:
        raise ValueError(f"cut {cut} is at or before the first tick: nothing is past")

    def tail(xs: list[float]) -> list[float]:
        return xs[:k] + [2.0 * x for x in reversed(xs[k:])]
    return TickTape(tape.ts, perturb_path(tape.mid, k), tail(tape.spread), tail(tape.velocity))


def bar_tape(n: int, seed: int, *, vol: float = 8e-4, wick: float = 2e-4, gap: float = 1.0) -> list[LabelledBar]:
    """n bars from a two-point-per-bar path (open, close) with trending stretches. `gap`
    scales the close-to-next-open step, so a gappy tape exercises the gap-exit branch."""
    rng = random.Random(seed)
    path = [1.1]
    for i in range(1, 2 * n):
        drift = vol * 0.35 * (1 if (i // 30) % 2 else -1)          # 15-bar trending stretches
        path.append(path[-1] * math.exp(rng.gauss(drift, vol * (gap if i % 2 == 0 else 1.0))))
    spreads = [1e-4 * (1 + rng.random()) for _ in range(n)]
    return bars_from_path(path, spreads, wick)


def bars_from_path(path: Sequence[float], spreads: Sequence[float], wick: float = 2e-4) -> list[LabelledBar]:
    t0 = datetime(2026, 7, 6, tzinfo=timezone.utc)
    out = []
    for k in range(len(path) // 2):
        o, c = path[2 * k], path[2 * k + 1]
        out.append(LabelledBar(ts=t0 + timedelta(minutes=k), open=o, high=max(o, c) + wick,
                               low=min(o, c) - wick, close=c, spread=spreads[k],
                               regime=RegimeType.STRONG_TREND_UP))
    return out


def bar_cuts(n: int) -> list[float]:
    """Every data point of an n-bar tape after the first: each bar's open and its close."""
    return [p / 2 for p in range(1, 2 * n)]


def bar_tape_variant(bars: Sequence[LabelledBar], cut: float, mode: str, wick: float = 2e-4) -> list[LabelledBar]:
    """Data stamped >= `cut` perturbed or deleted, on the bar axis (bar k's open at k, its close
    — with its high, low and closing spread — at k + 0.5). A truncated tape keeps a bar whose
    open precedes the cut as that open alone (O = H = L = C): what was known at the cut."""
    p = round(2 * cut)
    if p / 2 != cut or not 1 <= p <= 2 * len(bars):
        raise ValueError(f"cut {cut} is not a data point of a {len(bars)}-bar tape")
    k = p // 2
    if mode == "truncate":
        out = list(bars[:k])
        if p % 2:
            b = bars[k]
            out.append(replace(b, high=b.open, low=b.open, close=b.open))
        return out
    path = [x for b in bars for x in (b.open, b.close)]
    spreads = [b.spread for b in bars]
    return list(bars[:k]) + bars_from_path(perturb_path(path, p),
                                           spreads[:k] + [2 * s for s in reversed(spreads[k:])], wick)[k:]


def trade_path_decisions(trades: Sequence[Trade]) -> list[Decision]:
    out = []
    for t in trades:
        out.append(Decision(t.signal_bar + 0.5, t.signal_bar + 1.0, "signal", (t.signal_bar, t.direction)))
        out.append(Decision(t.signal_bar + 1.0, t.signal_bar + 1.0, "fill", (t.signal_bar, t.entry_price)))
        if t.exit_kind in AT_THE_OPEN:              # decided at bar j's OPEN (MEDIUM-2 / X2 / X3)
            out.append(Decision(float(t.exit_bar), float(t.exit_bar), "exit",
                                (t.signal_bar, t.exit_bar, t.exit_price, t.pnl)))
        elif not t.marked:
            out.append(Decision(t.exit_bar + 0.5, t.exit_bar + 0.5, "exit",
                                (t.signal_bar, t.exit_bar, t.exit_price, t.pnl)))
    return out
