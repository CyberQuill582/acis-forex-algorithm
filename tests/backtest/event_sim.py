"""A research simulator for scheduled-window rules: D3, the turn-of-month index long (GAP-P12D-154). It
grades on RSIM's daily clock, so the register, the HAC kill rule and stage D read one kind of series.

Mental model (D3 v1, owner ruling 2026-10-03 "Papers' window": McConnell & Xu's [-1, +3]):
  * WINDOWS: each index in its OWN market, from its exchange's calendar (`exchange_days`), never from
    the CFD's hours: long from the cash close of T-2 to the cash close of T+3.
  * ANCHOR(d): the close mid of the last traded hour ending at or before the cash close of session d,
    if that hour starts inside d's session (UK100 and EU50 close on the half hour, so theirs is 30
    minutes early at both ends, declared). A missing anchor skips the turn with its reason.
  * COST: each side pays THE C8 model, `per_side_cost(spread)` at its anchor hour's open spread, on the
    units bought. Swap-free (R1-D9): no financing. Returns are in each index's own currency.
  * MARKS: every New York weekday at 17:00 New York (RSIM's clock). A leg holds fixed units, marked at
    the last traded close at or before each mark; the exit's piece and cost go on the first mark at or
    after the exit, so a leg's daily pieces sum to its weight times its event's net return.
  * SIZING: equal risk: weight LEG_RISK over the trailing VOL_MARKS mark-return volatility, read before
    the entry (no look-ahead). The kill rule's HAC t does not depend on LEG_RISK.
  * CONTEXT, never a verdict: the passive long on the same marks and weights (no cost).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Mapping
from zoneinfo import ZoneInfo

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.exchange_days import SESSION, month_turn

HOME = {"US500": "XNYS", "US30": "XNYS", "UK100": "XLON", "EU50": "XEUR", "JP225": "XTKS", "AUS200": "XASX"}
NY = ZoneInfo("America/New_York")
VOL_MARKS, LEG_RISK = 60, 0.01


@dataclass(frozen=True)
class EventResult:
    days: tuple[date, ...]           # every New York weekday mark, start..end
    daily: np.ndarray                # the book's net return on each
    events: tuple[dict, ...]         # one per index per traded month turn
    skipped: tuple[dict, ...]        # a graded turn that could not be traded, with its reason


def _epoch(d: date, t: time, zone: ZoneInfo) -> int:
    return int(datetime.combine(d, t, tzinfo=zone).timestamp())


def marks(start: date, end: date) -> list[tuple[date, int]]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append((d, _epoch(d, time(17, 0), NY)))
        d += timedelta(days=1)
    return out


def turns(exchange: str, graded_from: date, end: date) -> list[tuple[date, date]]:
    """(T-2, T+3) of every month turn wholly inside [graded_from, end]."""
    out, (y, m) = [], (graded_from.year, graded_from.month)
    while (y, m) <= (end.year, end.month):
        t2, _, _, _, t3 = month_turn(exchange, y, m)
        if graded_from <= t2 and t3 <= end:
            out.append((t2, t3))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class Leg:
    """One index's traded hours, its price at every mark and its mark-to-mark returns."""

    def __init__(self, h: Hourly, stamps: np.ndarray) -> None:
        self.starts, self.closes, self.spreads = h.start[h.traded], h.mid_close[h.traded], h.spread_open[h.traded]
        self.ends = self.starts + 3600
        k = np.searchsorted(self.ends, stamps, side="right") - 1
        self.mark = np.where(k >= 0, self.closes[np.maximum(k, 0)], np.nan)
        self.rets = self.mark[1:] / self.mark[:-1] - 1.0

    def anchor(self, exchange: str, d: date) -> int | None:
        zone, open_, close = SESSION[exchange]
        j = int(np.searchsorted(self.ends, _epoch(d, close, ZoneInfo(zone)), side="right")) - 1
        return j if j >= 0 and self.starts[j] >= _epoch(d, open_, ZoneInfo(zone)) else None

    def weight(self, t: int) -> float | None:
        """LEG_RISK over the volatility of the returns ending at marks before t."""
        past = self.rets[max(0, t - 1 - VOL_MARKS):max(0, t - 1)]
        past = past[np.isfinite(past)]
        sd = float(np.std(past, ddof=1)) if len(past) >= VOL_MARKS // 2 else 0.0
        return LEG_RISK / sd if sd > 0 else None


def _skip_reason(leg: Leg, exchange: str, t2: date, i: int | None, j: int | None, w: float | None) -> str | None:
    zone, _, close = SESSION[exchange]
    if not len(leg.starts) or _epoch(t2, close, ZoneInfo(zone)) < leg.starts[0]:
        return "before_data"
    return "no_entry_anchor" if i is None else "no_exit_anchor" if j is None else "vol_warmup" if w is None else None


def simulate(hourly: Mapping[str, Hourly], costs: Mapping[str, CostModel], start: date, graded_from: date,
             end: date) -> EventResult:
    grid = marks(start, end)
    stamps = np.array([t for _, t in grid], np.int64)
    daily, events, skipped = np.zeros(len(grid)), [], []
    for name in sorted(hourly):
        leg, exchange, cm = Leg(hourly[name], stamps), HOME[name], costs[name]
        for t2, t3 in turns(exchange, graded_from, end):
            base = {"index": name, "t_minus_2": t2.isoformat(), "t_plus_3": t3.isoformat()}
            i, j = leg.anchor(exchange, t2), leg.anchor(exchange, t3)
            first = int(np.searchsorted(stamps, leg.ends[i], side="left")) if i is not None else 0
            w = leg.weight(first) if i is not None else None
            reason = _skip_reason(leg, exchange, t2, i, j, w)
            if reason:
                skipped.append({**base, "reason": reason})
                continue
            out = int(np.searchsorted(stamps, leg.ends[j], side="left"))   # the first mark at or after the exit
            p_in, p_out = float(leg.closes[i]), float(leg.closes[j])
            c_in, c_out = cm.per_side_cost(float(leg.spreads[i])) / p_in, cm.per_side_cost(float(leg.spreads[j])) / p_in
            prev = p_in
            for k in range(first, out):
                daily[k] += w * (leg.mark[k] - prev) / p_in
                prev = leg.mark[k]
            daily[out] += w * ((p_out - prev) / p_in - c_out)
            daily[first] -= w * c_in
            events.append({**base, "gross": p_out / p_in - 1.0, "net": (p_out - p_in) / p_in - c_in - c_out, "weight": w})
    return EventResult(tuple(d for d, _ in grid), daily, tuple(events), tuple(skipped))


def passive_long(hourly: Mapping[str, Hourly], start: date, end: date) -> np.ndarray:
    """Every index held long on every mark at the same equal-risk weight, no cost (stage A's benchmark)."""
    stamps = np.array([t for _, t in marks(start, end)], np.int64)
    daily = np.zeros(len(stamps))
    for name in sorted(hourly):
        leg = Leg(hourly[name], stamps)
        for t in range(1, len(stamps)):
            w = leg.weight(t)
            if w is not None and np.isfinite(leg.rets[t - 1]):
                daily[t] += w * leg.rets[t - 1]
    return daily


def per_index(events: tuple[dict, ...], skipped: tuple[dict, ...]) -> dict:
    """What the outcome line carries per index: counts, means and the skip reasons (never a verdict)."""
    out = {}
    for name in sorted({e["index"] for e in events} | {s["index"] for s in skipped}):
        net = np.array([e["net"] for e in events if e["index"] == name])
        gross = np.array([e["gross"] for e in events if e["index"] == name])
        reasons = [s["reason"] for s in skipped if s["index"] == name]
        out[name] = {"events": int(len(net)), "mean_gross": float(gross.mean()) if len(net) else None,
                     "mean_net": float(net.mean()) if len(net) else None,
                     "hit_rate": float((net > 0).mean()) if len(net) else None,
                     "skipped": {r: reasons.count(r) for r in sorted(set(reasons))}}
    return out
