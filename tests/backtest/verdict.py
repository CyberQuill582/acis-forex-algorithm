"""The register-aware stage-A verdict of a cycle of FIXED families (ACIS-09 C-BT-11 v2 steps 2-3;
GAP-P12D-111, GAP-P12D-100; the R1.4 verdict module).

    v = cycle_verdict(register_root, "cycle-1")      # v.chain, v.holm, v.passed

Mental model:
  * A pure function of the register: the cycle row (its chain order, Holm set and spending alpha) and
    the graded stage-A looks (tier 2, 2012-2023) of its members that NAME this cycle, each re-read by
    `stage_a.from_register` from the look's stored PORTFOLIO daily vector. `store_vector` refuses a
    repeated date, so an instrument x day panel can never be the graded unit (GAP-P12D-100).
  * A member's p-value is k x the smallest one-sided HAC p over its graded looks, k its declared look
    budget (each look is tested at alpha/k). A look failing a kill-only condition (paired excess over
    its benchmark, net at 2x cost, every C9 member and plateau neighbour) counts as p = 1.
  * Serial gatekeeping: the chain's members are tested in the registered order at the cycle's alpha,
    and testing stops at the first member that has not passed. The Holm set is tested only when the
    whole chain passed, Holm-adjusted among itself at the cycle's alpha.
  * A member's status: `passed`; `failed` (its k looks are spent and graded, none passed); `pending`
    (a registered look has no outcome yet); `open` (looks left, none passed); `not_built` (an explored
    family: max-t + PBO is not built, so it can never pass); `untested` (after the chain stopped).
  * Fail closed: a broken or torn register, or an unknown cycle, refuses the verdict.
  * Master §5.6: a look's HAC p counts toward a pass only over its days on or after the claim's
    certifying boundary (a literature rule: its publication; an LLM-selected or LLM-originated one:
    the later of the model's cutoff and the proposal date). Kill-only looks (the whole window before
    the boundary; `look_cycles.is_kill_only`) name no cycle; `kill_verdict` judges them by stage C's
    rule, killed at HAC t < -0.5 (owner rulings 2026-10-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import NormalDist

import numpy as np

from tests.backtest.hac import hac_t
from tests.backtest.look_claims import load_vector

from tests.backtest.look_cycles import STAGE_A_TIER
from tests.backtest.look_outcomes import read as read_outcome
from tests.backtest.look_register import LookRegister
from tests.backtest.stage_a import from_register


KILL_T = -0.5                        # stage C's kill rule (C-BT-11 v2 step 6), owner-chosen for kill-only looks


class VerdictRefused(Exception):
    """The register cannot support a verdict: broken, torn, or no such cycle."""


@dataclass(frozen=True)
class Member:
    variant: str
    status: str                      # passed | failed | pending | open | not_built | untested
    p: float | None                  # k x the best look's p; None before any graded look
    looks: tuple[str, ...]           # the graded stage-A look ids read
    budget: int | None               # the declared look budget k


@dataclass(frozen=True)
class CycleVerdict:
    cycle_id: str
    alpha: float
    chain: tuple[Member, ...]
    holm: tuple[Member, ...]

    @property
    def passed(self) -> tuple[str, ...]:
        return tuple(m.variant for m in self.chain + self.holm if m.status == "passed")


def _member(root: Path, lines: list[dict], variant: str, alpha: float, cycle_id: str) -> Member:
    mine = [x for x in lines if x.get("kind", "look") == "look"
            and (x.get("claim") or {}).get("variant_hash") == variant]
    if not mine:
        return Member(variant, "open", None, (), None)
    declaration = mine[0]["claim"].get("declaration") or {}
    k = declaration.get("look_budget")
    if declaration.get("kind") != "fixed":
        return Member(variant, "not_built", None, (), k)
    stage = [x for x in mine if x["tier"] == STAGE_A_TIER and (x.get("cycle") or {}).get("cycle_id") == cycle_id]
    ps, graded = [], []
    for x in stage:
        outcome = read_outcome(lines, x["look_id"])
        if outcome is not None:
            a = from_register(root, x["look_id"], alpha / k, outcome)
            graded.append(x["look_id"])
            kill_ok = a.paired_excess > 0 and a.net_2x > 0 and not a.refusing
            t = _certifying_t(root, outcome, x["claim"].get("certifying_boundary"))
            ps.append(1.0 - NormalDist().cdf(t) if kill_ok and t is not None else 1.0)
    p = min(1.0, k * min(ps)) if ps else None
    if p is not None and p < alpha:
        status = "passed"
    elif len(graded) < len(stage):
        status = "pending"
    elif len(stage) >= k:
        status = "failed"
    else:
        status = "open"
    return Member(variant, status, p, tuple(graded), k)


def _holm(members: list[Member], alpha: float) -> tuple[Member, ...]:
    """Holm step-down at alpha; a member with no p, or not a fixed family, counts as p = 1."""
    p = {m.variant: (m.p if m.p is not None and m.status != "not_built" else 1.0) for m in members}
    order = sorted(members, key=lambda m: p[m.variant])
    passed, stopped = set(), False
    for i, m in enumerate(order):
        stopped = stopped or not p[m.variant] < alpha / (len(order) - i)
        if not stopped:
            passed.add(m.variant)
    def refused(m: Member) -> Member:            # passed alone, not after Holm: spent or still open
        status = ("failed" if len(m.looks) >= m.budget else "open") if m.status == "passed" else m.status
        return Member(m.variant, status, m.p, m.looks, m.budget)
    return tuple(m if m.variant in passed else refused(m) for m in members)


def cycle_verdict(root: Path, cycle_id: str) -> CycleVerdict:
    root = Path(root)
    scan = LookRegister(root).scan()
    if scan.broken or scan.torn:
        raise VerdictRefused("the register is broken or torn: " + "; ".join(scan.broken + scan.torn))
    lines = [x for x in scan.lines if x is not None]
    row = next((x for x in lines if x.get("kind") == "cycle" and x["cycle_id"] == cycle_id), None)
    if row is None:
        raise VerdictRefused(f"no cycle {cycle_id!r} in the register")
    alpha = row["alpha"]
    chain, stopped = [], False
    for variant in row["order"]:
        m = Member(variant, "untested", None, (), None) if stopped else _member(root, lines, variant, alpha, cycle_id)
        chain.append(m)
        stopped = stopped or m.status != "passed"
    holm = [_member(root, lines, v, alpha, cycle_id) for v in row["holm"]]
    holm = _holm(holm, alpha) if not stopped else tuple(Member(m.variant, "untested", m.p, m.looks, m.budget)
                                                        for m in holm)
    return CycleVerdict(cycle_id, alpha, tuple(chain), tuple(holm))


def _certifying_t(root: Path, outcome: dict, boundary: str | None) -> float | None:
    """The HAC t over the graded days that may count toward a pass (master §5.6); None if too few."""
    dates, returns = load_vector(root, outcome["daily_vector"])
    keep = [r for d, r in zip(dates, returns) if boundary is None or d >= date.fromisoformat(boundary)]
    return hac_t(np.asarray(keep)) if len(keep) >= 3 else None


@dataclass(frozen=True)
class KillVerdict:
    look_id: str
    hac_t: float                     # of the look's whole graded net daily portfolio series
    killed: bool                     # hac_t < KILL_T


def kill_verdict(root: Path, look_id: str) -> KillVerdict:
    """A kill-only look's verdict, read from the register alone."""
    scan = LookRegister(Path(root)).scan()
    if scan.broken or scan.torn:
        raise VerdictRefused("the register is broken or torn: " + "; ".join(scan.broken + scan.torn))
    outcome = read_outcome(scan.lines, look_id)
    if outcome is None:
        raise VerdictRefused(f"look {look_id} has no outcome in the register")
    t = hac_t(np.asarray(load_vector(Path(root), outcome["daily_vector"])[1]))
    return KillVerdict(look_id, t, t < KILL_T)
