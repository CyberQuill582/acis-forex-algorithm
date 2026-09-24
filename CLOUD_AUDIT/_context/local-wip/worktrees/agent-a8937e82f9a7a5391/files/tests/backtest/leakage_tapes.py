"""Short tapes and decision extractors for the component-level leakage sweeps (GAP-P12D-65).

Mental model:
  * Each tape is small enough to rerun once per cut, because the sweep is exhaustive: one
    cut per decision point of the component (every tick, or every bar), never a sample.
  * A tape's future is changed at the source and only there: `tick_tape_variant` perturbs or
    deletes every tick stamped >= the cut (prices, spreads and tick rates); `bar_tape_variant`
    does the same for bars on a bar-index time axis (bar k opens at k, closes before k + 1).
  * Bar tapes carry an independent OPEN per bar (a two-point path per bar), so the open of
    bar k — the fill price of a decision taken at bar k-1's close — belongs to bar k's future.
  * `trade_path_decisions` stamps the fitness simulator's decisions on that axis: an entry
    signal is decided at its bar's close (k + 0.5) and emitted with its fill at the next open
    (k + 1); an exit on bar j is stamped j + 0.5 (conservative for a gap exit at j's open);
    the window-end mark (GAP-0039) is bookkeeping, not a decision, and is never compared.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Sequence

from core.optimizer.fitness import Trade
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


def bar_tape(n: int, seed: int, *, vol: float = 8e-4, wick: float = 2e-4) -> list[LabelledBar]:
    """n bars from a two-point-per-bar path (open, close) with trending stretches."""
    rng = random.Random(seed)
    path = [1.1]
    for i in range(1, 2 * n):
        drift = vol * 0.35 * (1 if (i // 30) % 2 else -1)          # 15-bar trending stretches
        path.append(path[-1] * math.exp(rng.gauss(drift, vol)))
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


def bar_tape_variant(bars: Sequence[LabelledBar], cut: int, mode: str, wick: float = 2e-4) -> list[LabelledBar]:
    """Bars [0, cut) untouched; from bar `cut` on (its OPEN included) perturbed or deleted."""
    if mode == "truncate":
        return list(bars[:cut])
    path = [p for b in bars for p in (b.open, b.close)]
    spreads = [b.spread for b in bars]
    return (list(bars[:cut]) + bars_from_path(perturb_path(path, 2 * cut),
                                              spreads[:cut] + [2 * s for s in reversed(spreads[cut:])],
                                              wick)[cut:])


def trade_path_decisions(trades: Sequence[Trade]) -> list[Decision]:
    out = []
    for t in trades:
        out.append(Decision(t.signal_bar + 0.5, t.signal_bar + 1.0, "signal", (t.signal_bar, t.direction)))
        out.append(Decision(t.signal_bar + 1.0, t.signal_bar + 1.0, "fill", (t.signal_bar, t.entry_price)))
        if not t.marked:
            out.append(Decision(t.exit_bar + 0.5, t.exit_bar + 0.5, "exit",
                                (t.signal_bar, t.exit_bar, t.exit_price, t.pnl)))
    return out
