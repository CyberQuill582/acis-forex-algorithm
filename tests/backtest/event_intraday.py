"""The event simulator's intraday form: IMOM, intraday momentum into the cash close (GAP-P12D-158;
Baltussen, Da, Lammers & Martens, JFE 142 (2021), eq. (2) and (12); Gao, Han, Li & Zhou, JFE 129 (2018)).

Mental model:
  * PRICES at a session's local wall times come from the 1-minute BID/ASK candles (`candles_min.py`):
    the price at T is the mid close of the last QUOTED minute ending at or before T (traded, or its
    price moved: the owner's 2026-10-03 rule), if it ended within STALE_MIN minutes of T; its spread is
    that minute's ask - bid at the close. A missing price skips the session, with its reason.
  * PREDICTORS: ROD = P(close - 30 min) / P(previous close) - 1 (Baltussen eq. 2), ONFH = P(open + 30 min)
    / P(previous close) - 1 (Gao eq. 1). The book holds sign(predictor) over the last half hour, long
    if positive and short otherwise (Baltussen eq. 12): in at close - 30 min, out at the close, each
    side paying THE C8 model's `per_side_cost` at its minute's spread. Flat overnight: no financing.
  * LARGE-MOVE version (owner ruling 2026-10-03): trade only when |predictor| is at least the
    `top` quantile of the trailing `window` sessions' |predictor| (past sessions only; MIN_HISTORY first).
  * Sessions are the caller's (the S&P's dates for the NYSE). A half day closes early, so its
    close - 30 min minute has no quote on the CFD and the session is skipped (declared).
  * Each session's P&L lands on its 17:00 New York mark (`event_sim.marks`): RSIM's kind of vector.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.candles_min import decode_day
from tests.backtest.event_sim import EventResult, marks
from tests.backtest.universe import BY_NAME

STALE_MIN = 5
MIN_HISTORY = 60
UTC = timezone.utc


@dataclass(frozen=True)
class Session:
    day: date
    prices: Mapping[str, tuple[float, float] | None]     # label -> (mid, spread) or None


def _minutes(root: Path, name: str, utc_day: date) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """The QUOTED minutes of one UTC day as (start epoch, mid close, spread at close), or None if no file."""
    base = Path(root) / BY_NAME[name].duka / str(utc_day.year) / f"{utc_day.month - 1:02d}" / f"{utc_day.day:02d}"
    try:
        bid, ask = (decode_day((base / f"{s}_candles_min_1.bi5").read_bytes(), name, utc_day) for s in ("BID", "ASK"))
    except FileNotFoundError:
        return None
    quoted = (bid["volume"] > 0) | (ask["volume"] > 0) | (bid["open"] != bid["close"])
    mid, spread = (bid["close"] + ask["close"]) / 2, np.maximum(ask["close"] - bid["close"], 0.0)
    return bid["ts"][quoted], mid[quoted], spread[quoted]


def session_prices(root: Path, name: str, sessions: Sequence[date], zone: str,
                   times: Mapping[str, time]) -> list[Session]:
    """Each session's (mid, spread) at each labelled local wall time (the minute ENDING by it)."""
    tz, cache, out = ZoneInfo(zone), {}, []
    for d in sessions:
        prices = {}
        for label, t in times.items():
            at = int(datetime.combine(d, t, tzinfo=tz).timestamp())
            utc_day = datetime.fromtimestamp(at - 60, UTC).date()
            if utc_day not in cache:
                if len(cache) > 3:
                    cache.clear()
                cache[utc_day] = _minutes(root, name, utc_day)
            m = cache[utc_day]
            k = int(np.searchsorted(m[0] + 60, at, side="right")) - 1 if m is not None else -1
            prices[label] = (float(m[1][k]), float(m[2][k])) if k >= 0 and at - (m[0][k] + 60) < STALE_MIN * 60 else None
        out.append(Session(d, prices))
    return out


def simulate_imom(sessions: Sequence[Session], cost: CostModel | None, start: date, graded_from: date, end: date,
                  predictor: str, side: Callable[[float], float] = lambda r: 1.0 if r > 0 else -1.0,
                  top: float | None = None, window: int = 250) -> EventResult:
    """`predictor` "rod" or "onfh"; `cost` None prices nothing; `side` maps the predictor to the position;
    `top` (e.g. 2/3) keeps only sessions whose |predictor| reaches that trailing quantile."""
    grid = marks(start, end)
    at = {d: k for k, (d, _) in enumerate(grid)}
    daily, skipped, prev, past = np.zeros(len(grid)), [], None, deque(maxlen=window)
    for s in sessions:
        p, close_today = s.prices, s.prices.get("close")
        sig = p.get("c30" if predictor == "rod" else "onfh")
        r = sig[0] / prev[0] - 1.0 if sig is not None and prev is not None else None
        bar = float(np.quantile(past, top)) if top is not None and len(past) >= MIN_HISTORY else None
        if graded_from <= s.day <= end:
            need = {"previous close": prev, "signal": sig, "entry": p.get("c30"), "close": close_today}
            missing = [k for k, v in need.items() if v is None]
            if missing:
                skipped.append({"session": s.day.isoformat(), "reason": "no " + missing[0]})
            elif top is not None and (bar is None or abs(r) < bar):
                pass                                                     # a small-move day: flat by rule
            else:
                pos = side(r)
                (pin, sin), (pout, sout) = need["entry"], close_today
                pnl = pos * (pout / pin - 1.0)
                if cost is not None:
                    pnl -= abs(pos) * (cost.per_side_cost(sin) / pin + cost.per_side_cost(sout) / pin)
                daily[at[s.day]] += pnl
        if r is not None:
            past.append(abs(r))
        prev = close_today
    return EventResult(tuple(d for d, _ in grid), daily, (), tuple(skipped))
