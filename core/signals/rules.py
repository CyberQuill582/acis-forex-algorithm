"""The TREND family's members as pure forecast functions (master §5.6 v2.22, §5.5; R1.3).

One function per member, shared by the research simulator (tests/backtest/rsim.py) and, from
R1.6, the engine. Each maps the daily closes up to and including the decision day (17:00 New
York) to a forecast series of the same length: NaN while warming up, else capped at ±20.

Mental model:
  * PRICE. A member reads the instrument's EXCESS-return price: spot compounded with the carry
    differential, the analogue of Carver's back-adjusted futures price (GAP-P12D-71/116).
  * EWMAC(f, s) is Carver's `ewmac` (pysystemtrade `CARVER_COMMIT`): (EWMA_f − EWMA_s) of the
    price over his normaliser, the daily price-unit volatility (`mixed_vol` of the daily
    changes), times his published scalar, capped at ±20 (GAP-P12D-122, D-f).
  * BREAKOUT(n) is Carver's `breakout`: 40·(p − mid)/(max − min) over n days, EWMA-smoothed
    with span n/4, times the scalar his `rob_system` config carries, capped.
  * MOP_12M is Moskowitz–Ooi–Pedersen (2012) eq. 5: at each month's last weekday (a calendar
    fact), the sign of the 12-month excess return, held for one month; ±10 (one average
    position), NaN until the month end a year earlier is on record. Its sizing volatility is
    MOP's own ex-ante estimate (`mop_vol`).
  * D1, the registered combination, is the three EWMAC speeds at equal weight × FDM 1.09,
    capped at ±20. Breakout and MOP are registered members graded standalone (C9), not
    weighted into D1 (PLAN_R1 §3.1; they correlate 0.95 and 0.77 with an EWMAC speed).
  * Nothing here sees the future: output t reads inputs [0, t] only, pinned by
    `test_a_forecast_never_reads_past_its_decision_day`.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Sequence

from core.signals.ewm import CARVER_COMMIT, NAN, diff, ewm_mean, ffill, mixed_vol, rolling_max, rolling_min

CAP = 20.0
# (fast, slow) -> Carver's published scalar: futures_chapter15/futuresconfig.yaml at CARVER_COMMIT
EWMAC_SCALARS = {(16, 64): 3.75, (32, 128): 2.65, (64, 256): 1.87}
# lookback -> the scalar in rob_system/config.yaml `forecast_scalars` at CARVER_COMMIT
BREAKOUT_SCALARS = {40: 0.7036929411910525, 80: 0.726260784624834, 160: 0.7388310187414805}
D1_FDM = 1.09        # 1/sqrt(w'ρw), null position correlations 0.87 / 0.58 (R1-B; lab-pinned)
MOP_LOOKBACK_MONTHS = 12
MOP_COM_DAYS = 60    # MOP 2012: the ex-ante variance's centre of mass, delta/(1-delta) = 60
MOP_ANNUALISE = 261  # MOP 2012's trading days per year
SOURCES = {"carver": f"pysystemtrade@{CARVER_COMMIT}",
           "mop": "Moskowitz, Ooi & Pedersen (2012), J. Financial Economics 104(2), eq. 5, App. A.3"}


def capped(raw: Sequence[float], scalar: float, cap: float = CAP) -> list[float]:
    return [x if x != x else max(-cap, min(cap, x * scalar)) for x in raw]


def ewmac(price: Sequence[float], fast: float, slow: float, *, scalar: float | None = None,
          vol_days: float = 35) -> list[float]:
    """Carver's `ewmac` with his normaliser, scaled by his published scalar and capped. The
    keywords exist for the ±10% plateau neighbours only (master §5): a neighbour keeps its base
    speed's scalar (declared), and `vol_days` is the normaliser's span."""
    vol = ffill(mixed_vol(diff(price), days=vol_days))
    f, s = ewm_mean(price, fast, 1), ewm_mean(price, slow, 1)
    raw = [(a - b) / v if v == v else NAN for a, b, v in zip(f, s, vol)]
    return capped(raw, EWMAC_SCALARS[(fast, slow)] if scalar is None else scalar)


def breakout(price: Sequence[float], lookback: int) -> list[float]:
    """Carver's `breakout` (default smooth = max(int(lookback/4), 1)), scaled and capped."""
    smooth = max(int(lookback / 4.0), 1)
    minp = math.ceil(lookback / 2.0)        # Carver: min(len, this) — length-free here, so a
                                            # growing history and a full one agree (declared)
    hi, lo = rolling_max(price, lookback, minp), rolling_min(price, lookback, minp)
    out = []
    for p, h, l in zip(price, hi, lo):
        rng = h - l
        out.append(40.0 * (p - (h + l) / 2.0) / rng if rng == rng and rng != 0 else NAN)
    return capped(ewm_mean(out, smooth, math.ceil(smooth / 2.0)), BREAKOUT_SCALARS[lookback])


def is_month_end(day: date) -> bool:
    """A calendar fact, known in advance: the next weekday falls in another month."""
    nxt = day + timedelta(days=3 if day.weekday() == 4 else 2 if day.weekday() == 5 else 1)
    return nxt.month != day.month


def mop_12m(price: Sequence[float], days: Sequence[date]) -> list[float]:
    """MOP 2012: ±10 from the sign of the excess return over the 12 months to each month end,
    held until the next month end; NaN until the month end 12 months earlier is on record."""
    closes: dict[tuple[int, int], float] = {}
    out, held = [], NAN
    for p, d in zip(price, days):
        if is_month_end(d):
            closes[(d.year, d.month)] = p
            then = closes.get((d.year - 1, d.month))
            if then is not None:
                held = 10.0 * (1.0 if p > then else -1.0 if p < then else 0.0)
        out.append(held)
    return out


def mop_vol(price: Sequence[float]) -> list[float]:
    """MOP's ex-ante DAILY volatility of returns: sqrt(EWMA(r²) − EWMA(r)²), centre of mass 60
    days (span 121), adjusted weights; the paper annualises it by sqrt(261)."""
    r = [NAN] + [b / a - 1.0 for a, b in zip(price, price[1:])]
    m1 = ewm_mean(r, 2 * MOP_COM_DAYS + 1, 1)
    m2 = ewm_mean([x * x for x in r], 2 * MOP_COM_DAYS + 1, 1)
    return [math.sqrt(max(b - a * a, 0.0)) if a == a else NAN for a, b in zip(m1, m2)]


def d1(price: Sequence[float], *, speed_scale: float = 1.0, ratio: float = 4.0,
       vol_days: float = 35) -> list[float]:
    """The registered TREND combination: equal-weight EWMAC speeds × FDM, capped. A day where
    any speed is still warming up is NaN (no target), never a partial average. Its three
    parameters (master §5: <= 3) are the speed scale (fast spans 16/32/64), the slow/fast ratio
    (4) and the normaliser's span (35); the defaults ARE the registered family."""
    speeds = [ewmac(price, f * speed_scale, f * speed_scale * ratio, scalar=k, vol_days=vol_days)
              for (f, _), k in EWMAC_SCALARS.items()]
    out = []
    for xs in zip(*speeds):
        out.append(NAN if any(x != x for x in xs)
                   else max(-CAP, min(CAP, D1_FDM * sum(xs) / len(xs))))
    return out
