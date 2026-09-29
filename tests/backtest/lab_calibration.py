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


def ewmac_pool(fast: int = 16, slow: int = 64, vol_span: int = 36) -> Rule:
    """sign(EWMA_fast - EWMA_slow) of each instrument's cumulative return, sized to equal risk by
    an EWMA variance estimate, pooled with equal weights; decided from data up to t-1."""
    a_f, a_s, a_v = 2 / (fast + 1), 2 / (slow + 1), 2 / (vol_span + 1)

    def rule(path: LabPath) -> np.ndarray:
        r = path.r
        cum = np.cumsum(r, axis=0)
        ef, es = np.zeros(r.shape[1]), np.zeros(r.shape[1])
        var, out = np.mean(r[:60] ** 2, axis=0), np.empty(len(r))
        for t in range(len(r)):
            out[t] = np.mean(np.sign(ef - es) / np.sqrt(var) * r[t])
            ef += a_f * (cum[t] - ef)
            es += a_s * (cum[t] - es)
            var += a_v * (r[t] ** 2 - var)
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
        null_hits += detect(rule(distort(generate(replace(spec, seed=seed))))[burn:])
        planted_hits += detect(rule(distort(generate(replace(spec, seed=seed, effect=effect))))[burn:])
        n += 1
    return Calibration(theory_sharpe, (spec.days - burn) / YEAR, alpha, n, null_hits, planted_hits)
