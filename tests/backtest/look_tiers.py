"""The look register's data tiers (GAP-P12D-64/66), split out of look_register.py (A12 budget).
Invariant: the tier comes from the source OBJECT's declared provenance and the folds' test windows,
never from a caller's string; a source declaring no provenance is refused, never tier 0; one look
grades one tier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from tests.backtest.oos_plan import DATA_START, HOLDOUT_END, HOLDOUT_START
from tests.backtest.walk_forward import Fold

FORWARD_START = datetime(2026, 7, 1, tzinfo=timezone.utc)   # after the June-2026 model cutoff (X9)
TIER_NAMES = ("synthetic", "exploration", "validation", "holdout", "forward")
# (from, to, tier): real test windows. 2026-01..06 is pre-cutoff history the models may have
# seen, so it is exploration, never "forward" (X9, GAP-P12D-66).
_WINDOWS = ((None, DATA_START, 1), (DATA_START, HOLDOUT_START, 2), (HOLDOUT_START, HOLDOUT_END, 3),
            (HOLDOUT_END, FORWARD_START, 1), (FORWARD_START, None, 4))


class TierRefused(Exception):
    """A source or fold set that cannot be tiered honestly."""


def data_tier(src: object, folds: Sequence[Fold]) -> int:
    provenance = getattr(src, "provenance", None)
    if provenance == "synthetic":
        return 0
    if provenance != "real":
        raise TierRefused(f"source {getattr(src, 'name', src)!r} ({type(src).__qualname__}) declares no "
                          "provenance: it cannot be graded, and it is never tier 0")
    tiers = set()
    for f in folds:
        tier = next((t for lo, hi, t in _WINDOWS if (lo is None or lo <= f.test_start)
                     and (hi is None or f.test_end <= hi)), None)
        if tier is None:
            raise TierRefused(f"the test window {f.test_start.date()} -> {f.test_end.date()} straddles two data tiers")
        tiers.add(tier)
    if len(tiers) != 1:
        raise TierRefused(f"one look grades one data tier; these folds span {sorted(TIER_NAMES[t] for t in tiers)}")
    return tiers.pop()
