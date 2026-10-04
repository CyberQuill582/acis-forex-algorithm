"""The tournament's pre-registered promotion rule (TOURNAMENT, 2026-10-04; proposal in
archive/TOURNAMENT_SPEC_PROPOSAL_2026-10-03.md). Its output is "eligible for owner review", never a promotion
and never live: the §14 rungs, stage D and the human sign-off are untouched.

Mental model:
  * PARAMS are hashed into the record's `rule` line before the first forward day; `evaluate` refuses a
    record whose rule is not this one, so the rule cannot be changed after the data is seen.
  * MILESTONE D's screen (the owner's ruling, 2026-10-03): >= 126 forward days at a net annual Sharpe
    >= 0.5, not killed by stage D's E2, no tripwire. On its own a zero-edge strategy passes it about a
    third of the time, and one of N about 1 - 0.64^N, so `luck_one`/`luck_any` are always reported with it.
  * SIGNIFICANCE, corrected for every strategy the tournament could hold (its capacity, not the current
    count, so adding entries never helps an earlier one): at the pre-registered looks only (126, 252, 504
    days) the one-sided Newey-West HAC p of the mean over the first n rows; Bonferroni over the looks;
    weighted Holm over the capacity (an empty slot or a retired entry keeps its alpha in the family);
    OR, anytime-valid, E1 >= 1/alpha_i (e-Bonferroni; Ville). Peeking between looks earns nothing.
  * STAGE D (ACIS-09 C-BT-11 v2 step 7): E1 and E2 as specified, sigma* the entry's declared daily vol;
    E2's claim is half the development look's DAILY Sharpe times sigma*. The TRIPWIRE (master v2.36, P-5): a day
    below -k sigma* voids E1, k = max(6, 1.5 x the entry's worst history day in sigma* units), pinned per entry.
  * ELIGIBLE = the screen AND significance AND an intact, reproducible record (the caller's check).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import NormalDist

import numpy as np

from tests.backtest.forward_record import State
from tests.backtest.hac import hac_t
from tests.backtest.look_claims import canonical_hash

PARAMS = {"version": "tournament-v1.1", "alpha_total": 0.05, "capacity": 20, "looks": [126, 252, 504],
          "min_days": 126, "min_sharpe": 0.5, "lambdas": [0.05, 0.1, 0.2, 0.4, 0.8], "e_freeze": 5.0,
          "e_kill": 20.0, "e_shown": 20.0,
          "tripwire": {"rule": "k = max(floor, multiple x the worst day of the entry's registered history looks, in sigma* units); a pinned value, else the entry's own history_worst_sigmas", "multiple": 1.5, "floor": 6.0,
                       "pinned": {"D1-FX13": 5.49, "REBAL-v1a": 8.46, "GOTOBI-v1a": 9.60, "HALLOWEEN-v1": 12.64,
                                  "HEDGEP-gold": 9.52, "FXVALUE-ppp": 2.21}},
          "test": "one-sided Newey-West HAC p of the mean daily net return over the first n rows at each look; "
                  "Bonferroni over the looks; weighted Holm over the capacity at alpha_total; or E1 >= 1/alpha_i",
          "output": "eligible for owner review: never a promotion, never live"}
N = NormalDist()


class RuleMismatch(Exception):
    """The record was registered under a different promotion rule."""


def rule_line() -> dict:
    return {"kind": "rule", "params": PARAMS, "rule_hash": canonical_hash(PARAMS)}


@dataclass(frozen=True)
class Verdict:
    strategy: str
    days: int
    annual_sharpe: float | None
    hac_t: float | None
    p_looks: tuple[tuple[int, float], ...]     # (look size, one-sided p) for each completed look
    p_star: float                              # Bonferroni over the looks
    holm_rejected: bool
    e1: float
    e1_voided: bool
    e2: float
    e2_max: float
    frozen: bool
    killed: bool
    e_bonferroni: bool
    screen_d: bool
    luck_one: float | None
    luck_any: float | None
    eligible: bool
    reasons: tuple[str, ...]


def wealth(x: np.ndarray, lambdas) -> np.ndarray:
    """The stage-D mixture bettor's running wealth: mean over lambda of prod(1 + lambda*max(x, -1))."""
    if not len(x):
        return np.ones(0)
    f = np.maximum(np.asarray(x, float), -1.0)
    return np.mean([np.cumprod(1.0 + lam * f) for lam in lambdas], axis=0)


def tripwire_sigmas(entry: dict, p: dict) -> float:
    """k for this entry (P-5): the pinned history worst day, else the entry's own declared one."""
    t = p["tripwire"]
    worst = t["pinned"].get(entry["strategy"], entry.get("history_worst_sigmas"))
    if worst is None:
        raise RuleMismatch(f"{entry['strategy']} declares no history_worst_sigmas for its tripwire (P-5)")
    return max(t["floor"], t["multiple"] * abs(float(worst)))


def stage_d(r: np.ndarray, sigma: float, sharpe_dev_annual: float, p: dict,
            k: float = 6.0) -> tuple[float, bool, float, float]:
    """(E1 now, E1 voided by a tripwire at -k sigma*, E2 now, E2's running maximum)."""
    if not len(r):
        return 1.0, False, 1.0, 1.0
    unit = k * sigma
    voided = bool(np.any(r < -unit))
    e1 = 0.0 if voided else float(wealth(r / unit, p["lambdas"])[-1])
    claim = sharpe_dev_annual / math.sqrt(252.0) / 2.0 * sigma
    w2 = wealth((claim - r) / unit, p["lambdas"])
    return e1, voided, float(w2[-1]), float(w2.max())


def look_p(r: np.ndarray, looks) -> tuple[tuple[int, float], ...]:
    return tuple((n, 1.0 - N.cdf(hac_t(r[:n]))) for n in looks if len(r) >= n)


def holm(p: dict[str, float], alpha: dict[str, float], alpha_total: float, empty_mass: float) -> set[str]:
    """Weighted Holm (Holm 1979): reject the least p/alpha_i while p_i <= alpha_i * alpha_total / (alpha
    mass still unrejected, empty slots included)."""
    left, out = dict(alpha), set()
    while left:
        sid = min(left, key=lambda s: p[s] / left[s])
        if not p[sid] <= left[sid] * alpha_total / (sum(left.values()) + empty_mass):
            break
        out.add(sid)
        del left[sid]
    return out


def evaluate(state: State, integrity_ok: bool | dict[str, bool], as_of: date | None = None) -> tuple[Verdict, ...]:
    """Every entry's verdict; `integrity_ok` is one flag for the record or one per strategy."""
    if state.rule is None or state.rule["params"] != PARAMS:
        raise RuleMismatch("the record's rule is not tournament-v1 as registered in code")
    p, entries = PARAMS, state.entries
    series = {s: np.array([v for d, v in state.days[s] if as_of is None or d <= as_of]) for s in entries}
    pl = {s: look_p(r, p["looks"]) for s, r in series.items()}
    pstar = {s: min(1.0, len(p["looks"]) * min((q for _, q in pl[s]), default=1.0)) for s in entries}
    alpha = {s: float(e["alpha"]) for s, e in entries.items()}
    empty = max(0.0, p["alpha_total"] - sum(alpha.values()))
    rejected = holm(pstar, alpha, p["alpha_total"], empty)
    out = []
    for s, e in entries.items():
        r, ok = series[s], integrity_ok if isinstance(integrity_ok, bool) else integrity_ok.get(s, False)
        sr = float(r.mean() / r.std(ddof=1) * math.sqrt(252)) if len(r) > 2 and r.std(ddof=1) > 0 else None
        t = hac_t(r) if len(r) >= 3 else None
        k = tripwire_sigmas(e, p)
        e1, voided, e2, e2max = stage_d(r, float(e["sigma_daily"]), float(e["sharpe_dev"]), p, k)
        killed, e_bon = e2max >= p["e_kill"], (not voided) and e1 >= 1.0 / alpha[s]
        screen = len(r) >= p["min_days"] and sr is not None and sr >= p["min_sharpe"] and not killed and not voided
        luck = None if sr is None else 1.0 - N.cdf(sr * math.sqrt(len(r) / 252.0))
        why = [f"{len(r)} of {p['min_days']} days"] if len(r) < p["min_days"] else []
        why += [f"Sharpe {sr:.2f} < {p['min_sharpe']}"] if sr is not None and sr < p["min_sharpe"] else []
        why += ["killed: E2 reached 20"] * killed + [f"E1 voided by a -{k:.1f} sigma* day"] * voided
        why += [] if s in rejected or e_bon else ["not significant after the correction for the capacity"]
        why += [] if ok else ["the record failed its integrity or recompute check"]
        out.append(Verdict(s, len(r), sr, t, pl[s], pstar[s], s in rejected, e1, voided, e2, e2max,
                           e2 >= p["e_freeze"], killed, e_bon, screen, luck,
                           None if luck is None else 1.0 - (1.0 - luck) ** len(entries),
                           screen and (s in rejected or e_bon) and ok, tuple(why)))
    return tuple(out)
