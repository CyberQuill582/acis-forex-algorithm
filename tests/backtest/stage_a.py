"""Stage A's pass conditions for a FIXED family (ACIS-09 C-BT-11 v2 step 3; master §5 C9, plateau).

A family-version passes stage A when ALL of these hold on its portfolio daily series:
  1. the one-sided HAC lower bound of its annual Sharpe is > 0 at the look's alpha (`hac.py`);
  2. its paired excess over the registered passive benchmark is > 0 (K13, kill-only);
  3. it is net > 0 at 2x modelled cost (the C8 model's stress = 2, the whole per-side cost);
  4. every C9 member and every ±10% plateau neighbour has mean daily net P&L > 0 (kill-only).
Only (1) spends alpha; (2)-(4) can only refuse, so they spend none (master §5.6).

Mental model:
  * Pure functions of daily series: the caller (the lab run here; `evaluate()` on real data,
    GAP-P12D-136) produces every series through RSIM, so no number here has a second source.
  * `from_register` re-reads a stage-A look's stored series (`evaluate(arms=...)`), so the verdict
    of a real look is a pure function of the register.
  * The plateau neighbours of D1 (master §5): speeds ×0.9 and ×1.1 jointly (ratios kept), then
    each of its three parameters ±10% alone: the speed scale, the slow/fast ratio, the
    normaliser's span. The joint and the speed-scale-alone neighbours coincide for D1, so the
    set has 6 distinct members, not 8.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Mapping

import numpy as np

from tests.backtest.hac import hac_t
from tests.backtest.look_claims import load_vector

D1_BASE = {"speed_scale": 1.0, "ratio": 4.0, "vol_days": 35.0}


def d1_neighbours(base: Mapping[str, float] = D1_BASE) -> dict[str, dict[str, float]]:
    out = {}
    for step in (0.9, 1.1):
        for key in base:                      # speed_scale alone == the joint scaling for D1
            out[f"{key}x{step}"] = {**base, key: base[key] * step}
    return out


@dataclass(frozen=True)
class StageA:
    hac_t: float
    crit: float
    paired_excess: float
    net_2x: float
    refusing: tuple[str, ...]        # C9 members and plateau neighbours with mean <= 0

    @property
    def bound_above_zero(self) -> bool:
        return self.hac_t > self.crit

    @property
    def passed(self) -> bool:
        return self.bound_above_zero and self.paired_excess > 0 and self.net_2x > 0 and not self.refusing


def stage_a(daily: np.ndarray, benchmark: np.ndarray, daily_2x: np.ndarray,
            kill_only_means: Mapping[str, float], alpha: float) -> StageA:
    """`alpha` is the look's share: the cycle's alpha over the family's declared look budget k."""
    if not (daily.shape == benchmark.shape == daily_2x.shape):
        raise ValueError("one span: the family, its benchmark and its 2x-cost run must align")
    return StageA(hac_t=hac_t(daily), crit=NormalDist().inv_cdf(1.0 - alpha),
                  paired_excess=float(np.mean(daily - benchmark)), net_2x=float(np.mean(daily_2x)),
                  refusing=tuple(sorted(k for k, m in kill_only_means.items() if not m > 0)))


def from_register(root: Path, look_id: str, alpha: float) -> StageA:
    """Stage A of one graded stage-A look, read back from the register alone (`evaluate(arms=...)`)."""
    outcome = json.loads((Path(root) / f"{look_id}.outcome.json").read_text(encoding="utf-8"))
    if "stage_a" not in outcome:
        raise ValueError(f"look {look_id} is not a stage-A grade: it stored no benchmark, 2x or kill-only series")
    arms = outcome["stage_a"]
    vec = lambda h: np.asarray(load_vector(root, h)[1])                       # noqa: E731
    return stage_a(vec(outcome["daily_vector"]), vec(arms["benchmark_vector"]), vec(arms["cost2x_vector"]),
                   {k: float(vec(h).mean()) for k, h in arms["kill_only_vectors"].items()}, alpha)
