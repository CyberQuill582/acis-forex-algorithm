"""B0, "machinery proven first" (R1.1; ACIS-09 C-BT-11 v2 step 0, GAP-P12D-105): the lab measures a
detector's false-detect rate on the null and its power on a planted effect of known Sharpe, and
compares both with theory. Design: R1-C §2.8 (evidence/R1C/probe_calibration.py).

Mental model:
  * A RULE turns a lab path into one pooled daily P&L series; a DETECTOR turns that series into
    "edge" or "no edge". `calibrate` runs both on the null and on the planted market of the SAME
    seeds (common random numbers), so the two rates differ by the effect alone.
  * B0 holds only if (a) the planted detection rate, read back as a Sharpe through the same
    sampling law, lies within ±B0_DELTA (10%) of the closed-form theory Sharpe, on at least the
    declared B0_N paths (ACIS-09 v1.9, owner-ratified D-R11-1: an equivalence test, because the
    closed form is itself approximate), and (b) the null's false-detect rate is at most alpha +
    2 se, the se binomial at alpha.
  * THE RULE MATCHES ITS THEORY. `ewmac_pool` holds sign(EWMAC) of each instrument's y (returns
    in volatility units) with equal weights, exactly the premise of pooled_ewmac_sharpe. A rule
    that estimates volatility realises ~4% less and needs its own theory (audit R11I-04).
  * DECLARED ERROR RATES (audit R11I-03). At the declared block of B0_N = 2,000 seeds (1..2,000)
    the implied Sharpe carries ~±5% sampling error, so (a)'s ±10% band holds a correct lab and
    refuses a gross defect (a bridged lab reads ~50% low); (b) still fails a correct lab ~2.3% of
    the time. The block is fixed here and never re-drawn to clear a failure: a re-seed is a
    forking path.
  * Where the rest of B0 lives: (c) a leaky oracle refused by structure is the leakage suite
    (GAP-P12D-65); (e) planted variance-matched to its null is pinned in both generators; (d) the
    research simulator equal to the engine on lab tapes arrives with R1.3 and R1.6. The verdict
    (R1.4) may issue no real-data verdict unless all five hold at the same `recon_commit`.
  * The detector here is the plain one-sided t-test on the daily series, a placeholder. R1.4's
    stage-A HAC bound (GAP-P12D-121) must be calibrated through this same function before it binds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from statistics import NormalDist
from typing import Callable, Iterable

import numpy as np

from tests.backtest.lab_market import Effect, LabPath, LabSpec, generate
from tests.backtest.lab_theory import YEAR, detection_power

Rule = Callable[[LabPath], np.ndarray]
Detector = Callable[[np.ndarray], bool]


def one_sided_t(alpha: float = 0.05) -> Detector:
    """Detects when the daily series' t-statistic exceeds the one-sided alpha critical value."""
    crit = NormalDist().inv_cdf(1.0 - alpha)
    return lambda pnl: bool(pnl.mean() / pnl.std(ddof=1) * math.sqrt(pnl.size) > crit)


B0_N = 2000                    # the declared seed block: 1..B0_N
B0_SEEDS = range(1, B0_N + 1)
B0_DELTA = 0.10                # (a)'s equivalence band on the implied Sharpe (ACIS-09 v1.9, D-R11-1)


def ewmac_pool(fast: int = 16, slow: int = 64) -> Rule:
    """sign(EWMA_fast - EWMA_slow) of each instrument's cumulative y, pooled with equal weights and
    decided from data up to t-1: the premise of lab_theory.pooled_ewmac_sharpe."""
    a_f, a_s = 2 / (fast + 1), 2 / (slow + 1)

    def rule(path: LabPath) -> np.ndarray:
        y = path.y
        cum = np.cumsum(y, axis=0)
        ef, es, out = np.zeros(y.shape[1]), np.zeros(y.shape[1]), np.empty(len(y))
        for t in range(len(y)):
            out[t] = np.mean(np.sign(ef - es) * y[t])
            ef += a_f * (cum[t] - ef)
            es += a_s * (cum[t] - es)
        return out
    return rule


@dataclass(frozen=True)
class Calibration:
    theory_sharpe: float     # the rule's pooled Sharpe on the planted market, from lab_theory
    years: float             # graded length of each path
    alpha: float
    n: int                   # paths per market
    null_hits: int
    planted_hits: int

    @property
    def theory_power(self) -> float:
        return detection_power(self.theory_sharpe, self.years, self.alpha)

    @property
    def implied_sharpe_gap(self) -> float:
        """The planted rate read back as a Sharpe through the same sampling law, relative to the
        theory Sharpe: (Phi^-1(rate) + z_alpha)/sqrt(years)/theory - 1. B0 (a) bounds it by
        B0_DELTA (ACIS-09 v1.9, D-R11-1); NaN when there is no theory Sharpe to compare with."""
        unit = NormalDist()
        rate = min(max(self.planted_hits / self.n, 1e-9), 1 - 1e-9)
        implied = (unit.inv_cdf(rate) + unit.inv_cdf(1 - self.alpha)) / math.sqrt(self.years)
        return implied / self.theory_sharpe - 1.0 if self.theory_sharpe else float("nan")

    def failures(self) -> list[str]:
        out = []
        fpr, se0 = self.null_hits / self.n, math.sqrt(self.alpha * (1 - self.alpha) / self.n)
        if fpr > self.alpha + 2 * se0:
            out.append(f"null false-detect rate {fpr:.3f} > alpha {self.alpha} + 2 se ({se0:.3f})")
        if self.n < B0_N:
            out.append(f"{self.n} paths < the declared B0_N {B0_N}: the equivalence band is not resolved")
        gap = self.implied_sharpe_gap
        if not abs(gap) <= B0_DELTA:                       # NaN (no theory Sharpe) fails too
            out.append(f"planted implied Sharpe is {gap:+.1%} off the theory Sharpe {self.theory_sharpe:.3f}; "
                       f"the equivalence band is ±{B0_DELTA:.0%} (ACIS-09 v1.9)")
        return out

    @property
    def holds(self) -> bool:
        return not self.failures()


def calibrate(rule: Rule, spec: LabSpec, effect: Effect, theory_sharpe: float, seeds: Iterable[int],
              *, alpha: float = 0.05, burn: int = 300, detector: Detector | None = None,
              distort: Callable[[LabPath], LabPath] = lambda p: p) -> Calibration:
    """Detection rates on the null and the planted market of each seed. `distort` rewrites a path
    before the rule sees it: the identity for B0, a known defect to prove the check has power."""
    detect = detector or one_sided_t(alpha)
    null_hits = planted_hits = n = 0
    for seed in seeds:
        this = replace(spec, seed=seed, effect=effect)
        null_hits += detect(rule(distort(generate(this, null=True)))[burn:])
        planted_hits += detect(rule(distort(generate(this)))[burn:])
        n += 1
    return Calibration(theory_sharpe, (spec.days - burn) / YEAR, alpha, n, null_hits, planted_hits)
