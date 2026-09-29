"""Intraday ticks on demand from the daily lab (R1.1 C-4). ACIS-09 C-BT-12: "intraday refinement
of correlated daily bars bridges the common factor jointly" (GAP-P12D-92). Design: R1-C §2.6.

Mental model:
  * THE DAY IS THE FX DAY. Weekday d runs [rollover(d - 1), rollover(d)): 17:00 New York to 17:00
    New York on core/data/fx_clock, DST-correct, with Monday opening on Sunday at 17:00. So no
    tick falls in the weekend window, and a day lasts 23, 24 or 25 hours.
  * EXACT. A day's diffusive part is Gaussian GIVEN (sigma, the mixing draws), so a Brownian
    bridge pinned at the day's own endpoint has exactly the law of generating forward. That is
    the lawful bridge; GAP-P12D-91's whole-path demeaning pinned an endpoint no forward process
    would reach. The ticks' simple increments (fractions of the previous close) sum to the day's
    spot return to rounding.
  * JOINT. One bridge for the common factor plus one per idiosyncratic shock, so no instrument's
    path so far predicts another's rest of day. Bridging each instrument's combined shock on its
    own (joint=False, kept only to prove the test's power) plants a spurious lead-lag edge.
  * The drift and the financing accrual spread in proportion to session variance; a jump lands
    on one random tick; Monday's gap lands on the first tick.
  * Spreads and quote thinning are knobs, NOT a calibration: the hour shapes are R1-C's
    (LLM-chosen), and the rollover spike sits inside ACIS_SPEC's recorded 6-13x. Spikes above an
    instrument's max_plausible_spread exercise the loader's rejection path on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from core.data.fx_clock import rollover_utc
from tests.backtest.lab_market import LabPath

# relative variance and spread per UTC hour: Asia low, London open up, the London/New York overlap
# highest, late New York low, the rollover hour widest (a lab shape, not fitted to any series)
HOUR_VAR = np.array([0.6, 0.6, 0.7, 0.7, 0.6, 0.6, 0.8, 1.4, 1.8, 1.6, 1.4, 1.3,
                     1.6, 2.0, 2.2, 1.9, 1.5, 1.1, 0.8, 0.6, 0.5, 0.35, 0.4, 0.5])
HOUR_SPREAD = np.array([1.8, 1.8, 1.6, 1.5, 1.5, 1.4, 1.2, 1.0, 0.9, 0.9, 0.9, 0.9,
                        0.9, 0.85, 0.85, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 1.9, 1.8])
_STREAM = {"null": 0, "planted": 0, "permuted": 1}      # null and planted share intraday noise too


@dataclass(frozen=True)
class DayTicks:
    open: datetime          # the day's first tick, UTC (its 17:00-New-York open)
    tick_seconds: int
    inc: np.ndarray         # (N, n) simple increments, fractions of the previous close
    spread: np.ndarray      # (N, n) quoted spread, a fraction of the mid
    emit: np.ndarray        # (N, n) whether a quote is published on that tick

    def time(self, k: int) -> datetime:
        return self.open + timedelta(seconds=k * self.tick_seconds)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """The FX day that ends at `day`'s 17:00-New-York rollover."""
    return rollover_utc(day - timedelta(days=1)), rollover_utc(day)


def bridge(rng: np.random.Generator, weights: np.ndarray, var, endpoint, shape) -> np.ndarray:
    """Gaussian increments with variances weights·var, conditioned to sum to `endpoint` (exact:
    the residual inc - weights·sum(inc) is independent of the sum)."""
    inc = rng.standard_normal(shape) * np.sqrt(weights * var)
    return inc - weights * (inc.sum(axis=-1, keepdims=True) - endpoint)


def intraday(path: LabPath, t: int, tick_seconds: int = 60, *, joint: bool = True,
             base_spread: float | np.ndarray = 1e-4, roll_minutes: int = 10, roll_mult: float = 8.0,
             spike_prob: float = 0.002, spike_mult: float = 8.0, tick_rate: float = 0.5) -> DayTicks:
    """All instruments' ticks for weekday t; each instrument's increments sum to spot[t]."""
    open_, close = day_bounds(path.dates[t].astype(object))
    n = int((close - open_).total_seconds()) // tick_seconds
    rng = np.random.default_rng([path.spec.seed, 104729, t, _STREAM[path.kind]])
    secs = np.arange(n) * tick_seconds
    hours = (open_.hour * 3600 + open_.minute * 60 + secs) // 3600 % 24
    w = HOUR_VAR[hours] / HOUR_VAR[hours].sum()
    b = path.loadings[:, None]
    if joint:
        f = bridge(rng, w, path.wf[t], path.fac[t], (n,))
        e = bridge(rng, w, path.we[t][:, None], path.idio[t][:, None], (len(b), n))
        diffusive = path.diff_scale * (b * f + np.sqrt(1.0 - b * b) * e)
    else:
        var = path.diff_scale ** 2 * (b[:, 0] ** 2 * path.wf[t] + (1.0 - b[:, 0] ** 2) * path.we[t])
        total = path.diff_scale * (b[:, 0] * path.fac[t] + np.sqrt(1.0 - b[:, 0] ** 2) * path.idio[t])
        diffusive = bridge(rng, w, var[:, None], total[:, None], (len(b), n))
    y = path.scale * (diffusive + w * path.m[t][:, None])
    for i in np.flatnonzero(path.jumps[t]):
        y[i, rng.integers(n)] += path.scale * path.jumps[t, i]
    y[:, 0] += path.scale * path.gap[t]
    inc = path.sigma[t][:, None] * y - w * path.accrual[t][:, None]
    spread = np.asarray(base_spread, float).reshape(-1, 1) * HOUR_SPREAD[hours]
    spread = np.where(secs < roll_minutes * 60, spread * roll_mult, spread)
    spread = np.where(rng.random(inc.shape) < spike_prob, spread * spike_mult, spread)
    emit = rng.random(inc.shape) < np.clip(tick_rate * HOUR_VAR[hours] / HOUR_VAR.mean(), 0.0, 1.0)
    emit[:, 0] = True
    return DayTicks(open_, tick_seconds, inc, spread, emit)
