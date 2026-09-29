"""B0, "machinery proven first" (R1.1; ACIS-09 C-BT-11 v2 step 0, GAP-P12D-105): the lab measures a
detector's false-detect rate on the null and its power on a planted effect of known Sharpe, and
compares both with theory. Design: R1-C §2.8 (evidence/R1C/probe_calibration.py).

Mental model:
  * A RULE turns a lab path into one pooled daily P&L series; a DETECTOR turns that series into
    "edge" or "no edge". `calibrate` runs both on the null and on the planted market of the SAME
    seeds (common random numbers), so the two rates differ by the effect alone.
  * B0 holds only if (a) the planted detection rate is within 2 se of the power its theory Sharpe
    implies at this length (lab_theory.detection_power), and (b) the null's false-detect rate is
    at most alpha + 2 se. The se is binomial at the rate theory predicts.
  * THE RULE MATCHES ITS THEORY. `ewmac_pool` holds sign(EWMAC) of each instrument's y (returns
    in volatility units) with equal weights, exactly the premise of pooled_ewmac_sharpe. A rule
    that estimates volatility realises ~4% less and needs its own theory (audit R11I-04).
  * DECLARED ERROR RATES (audit R11I-03). A correct lab still fails (a) about 4.6% of the time and
    (b) about 2.3%. At the declared block of B0_N = 2,000 seeds (1..2,000), the band resolves a
    miscalibration of about ±5% in pooled Sharpe. The block is fixed here and never re-drawn to
    clear a failure: a re-seed is a forking path.
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
        theory Sharpe: (Phi^-1(rate) + z_alpha)/sqrt(years)/theory - 1. Reported, not gated: it
        is the quantity an equivalence-test B0 would bound (audit E-R11-01, an owner decision)."""
        unit = NormalDist()
        rate = min(max(self.planted_hits / self.n, 1e-9), 1 - 1e-9)
        implied = (unit.inv_cdf(rate) + unit.inv_cdf(1 - self.alpha)) / math.sqrt(self.years)
        return implied / self.theory_sharpe - 1.0 if self.theory_sharpe else float("nan")

    def failures(self) -> list[str]:
        out = []
        fpr, se0 = self.null_hits / self.n, math.sqrt(self.alpha * (1 - self.alpha) / self.n)
        if fpr > self.alpha + 2 * se0:
            out.append(f"null false-detect rate {fpr:.3f} > alpha {self.alpha} + 2 se ({se0:.3f})")
        power, p = self.planted_hits / self.n, self.theory_power
        se1 = math.sqrt(p * (1 - p) / self.n)
        if abs(power - p) > 2 * se1:
            out.append(f"planted detection rate {power:.3f} is not within 2 se ({se1:.3f}) of the "
                       f"theory power {p:.3f}")
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
