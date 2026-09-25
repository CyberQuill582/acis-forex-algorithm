"""Look-ahead DETECTORS T1 and T2 (GAP-P12D-65; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md §7.3).

No statistic can deflate a leak away: a leaky strategy's advantage is real in sample and out
of sample alike (DSR, PBO and CPCV all pass it, §7.2; Gençay, arXiv 2608.27734 §6.1). T1 and T2
are two-run differential detectors (Fonseca, arXiv 2607.04958 §8.3): they re-run on a changed
future and can EXHIBIT a leak, but "certify nothing by their silence". The by-construction
guard, a decision-time data accessor (T8), is not built. A silent sweep is reported as "no
violation detected at N cuts", never as clean.

Mental model:
  * A run is a list of `Decision`s. Each carries two stamps on the run's own time axis:
      horizon — the latest datum the decision may legitimately depend on;
      emitted — the earliest moment the system can have produced it (>= horizon: a bar is
                emitted by the tick that COMPLETES it, which lies after the bar's own ticks).
  * A cut t splits every tape: data stamped < t is the past, data stamped >= t the future.
  * T2, future-perturbation invariance: perturb every datum stamped >= t. Every decision whose
    HORIZON is < t must be byte-identical (the same multiset of (kind, repr(payload))).
  * T1, truncation invariance: delete every datum stamped >= t. Every decision EMITTED before
    t must be byte-identical. Emission, not horizon: a bar whose completing tick was deleted
    is legitimately never emitted, and that is not a leak.
  * Sweeps are EXHAUSTIVE over the caller's decision grid, never sampled: one random t catches
    a 5% one-bar peek about 15% of the time (VALIDATOR §7.2). The grid is the caller's claim;
    a coarse grid can only see leaks that reach across its own spacing.
  * `perturb_returns` reverses, negates and doubles every return from the cut on. Every later
    price moves, and so does the future's scale, so a whole-sample statistic moves too.
  * Silence certifies nothing unless the guard bites: the T7 controls (test_leakage_controls
    and scripts/leakage_suite.py stage 1) plant a next-bar peek that both tests must catch,
    and count how many decisions each sweep actually compared (0 compared = no verdict).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

T1, T2 = "T1 truncation", "T2 future-perturbation"


@dataclass(frozen=True)
class Decision:
    horizon: Any                  # comparable with the cuts (a datetime, or a bar-index float)
    emitted: Any
    kind: str
    payload: tuple

    def __post_init__(self) -> None:
        if self.emitted < self.horizon:
            raise ValueError(f"{self.kind}: emitted {self.emitted!r} before its horizon {self.horizon!r}")

    def key(self) -> tuple[str, str]:
        """Byte-identity: repr is exact for floats, Decimals and datetimes, and NaN equals NaN."""
        return self.kind, repr(self.payload)


@dataclass(frozen=True)
class Violation:
    test: str
    cut: Any
    missing: tuple[Decision, ...]     # decided in the reference run, absent from the variant
    extra: tuple[Decision, ...]       # decided in the variant, absent from the reference

    def describe(self, limit: int = 3) -> str:
        def show(ds: Sequence[Decision]) -> str:
            first = sorted(ds, key=lambda d: d.horizon)[:limit]
            return "; ".join(f"{d.kind}@{d.horizon}: {d.payload!r:.160}" for d in first)
        return (f"{self.test} at cut {self.cut}: {len(self.missing)} decision(s) lost "
                f"[{show(self.missing)}], {len(self.extra)} changed or new [{show(self.extra)}]")


@dataclass(frozen=True)
class Sweep:
    test: str
    cuts: int
    compared: int                     # reference decisions checked, summed over every cut
    violations: tuple[Violation, ...]

    @property
    def silent(self) -> bool:
        """No violation witnessed: a detector's silence, never a certificate."""
        return not self.violations

    def summary(self) -> str:
        head = f"{self.test}: {self.cuts} cuts, {self.compared} decisions compared, "
        if self.silent:
            return head + "no violation detected"
        return head + f"{len(self.violations)} violating cut(s); first: {self.violations[0].describe()}"


def _compare(test: str, cut: Any, reference: Iterable[Decision], variant: Iterable[Decision],
             keep: Callable[[Decision], bool]) -> tuple[int, Violation | None]:
    ref = [d for d in reference if keep(d)]
    var = [d for d in variant if keep(d)]
    a, b = Counter(d.key() for d in ref), Counter(d.key() for d in var)
    if a == b:
        return len(ref), None
    lost, new = a - b, b - a
    return len(ref), Violation(test, cut, tuple(d for d in ref if d.key() in lost),
                               tuple(d for d in var if d.key() in new))


def future_perturbation(reference: Sequence[Decision], perturbed: Callable[[Any], Sequence[Decision]],
                        cuts: Iterable[Any]) -> Sweep:
    """T2: `perturbed(t)` reruns the system on the tape with every datum stamped >= t perturbed."""
    compared, bad, n = 0, [], 0
    for t in cuts:
        n += 1
        k, v = _compare(T2, t, reference, perturbed(t), lambda d, t=t: d.horizon < t)
        compared += k
        if v is not None:
            bad.append(v)
    return Sweep(T2, n, compared, tuple(bad))


def truncation(reference: Sequence[Decision], truncated: Callable[[Any], Sequence[Decision]],
               cuts: Iterable[Any]) -> Sweep:
    """T1: `truncated(t)` reruns the system on the tape with every datum stamped >= t deleted."""
    compared, bad, n = 0, [], 0
    for t in cuts:
        n += 1
        k, v = _compare(T1, t, reference, truncated(t), lambda d, t=t: d.emitted < t)
        compared += k
        if v is not None:
            bad.append(v)
    return Sweep(T1, n, compared, tuple(bad))


def perturb_returns(returns: Sequence[float], cut: int) -> list[float]:
    """Returns [0, cut) unchanged; from `cut` on, the tail reversed, negated and doubled."""
    if not 0 <= cut <= len(returns):
        raise ValueError(f"cut {cut} outside 0..{len(returns)}")
    return list(returns[:cut]) + [-2.0 * r for r in reversed(returns[cut:])]


def perturb_path(prices: Sequence[float], cut: int) -> list[float]:
    """A positive price path with prices[cut:] perturbed and prices[:cut] untouched (cut >= 1):
    the log-return INTO price k is perturbed for every k >= cut."""
    if cut < 1:
        raise ValueError("cut must be >= 1: the first price anchors the path")
    moves = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    out = list(prices[:cut])
    for r in perturb_returns(moves, cut - 1)[cut - 1:]:
        out.append(out[-1] * math.exp(r))
    return out
