"""Order fragmentation + signature randomisation (ACIS-06 v1.1 §6).

The critical invariant (C-EXE-1): fragments sum EXACTLY to the parent total —
execution never creates or destroys a unit the Governor sized. Randomness is
injected (seeded `random.Random` in tests, `SystemRandom` in production);
time is injected via `now`.

v2.11 naming law: the large-order path is `scheduled`, not "VWAP" — v1's
retail-FX venue set has no consolidated volume tape, so weighting is "time"
(declared per plan). A future depth-bearing feed may set weighting "volume".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from config.schemas import ExecutionConfig
from core.data.errors import DataQualityError
from core.execution.venue import UNITS_PER_LOT

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Fragment:
    fragment_id: str
    parent_order_id: str
    units: Decimal
    scheduled_at: datetime
    venue: str

    def __post_init__(self) -> None:
        if not isinstance(self.units, Decimal) or self.units <= 0:
            raise DataQualityError("units", self.units, "must be positive Decimal")
        if self.scheduled_at.tzinfo is None:
            raise DataQualityError("scheduled_at", self.scheduled_at, "must be tz-aware")


@dataclass(frozen=True)
class FragmentPlan:
    path: str                      # "ioc" | "single" | "fragment" | "scheduled"
    weighting: str                 # "none" | "time"  (v2.11: never mislabel VWAP)
    fragments: tuple[Fragment, ...]


def _split_units(total: Decimal, n: int, lo: float, hi: float, rng) -> list[Decimal]:
    """n jittered sizes summing EXACTLY to total (renormalised multipliers,
    cent-quantized, remainder absorbed by the last fragment)."""
    weights = [rng.uniform(lo, hi) for _ in range(n)]
    scale = float(total) / sum(weights)
    sizes = [(Decimal(str(w * scale))).quantize(_CENT) for w in weights[:-1]]
    sizes.append(total - sum(sizes, Decimal("0")))
    return sizes


def plan(order_id: str, total_units: Decimal, *, fast_decay: bool,
         cfg: ExecutionConfig, venues: list[str], now: datetime, rng) -> FragmentPlan:
    """Classify and split one SizedOrder (ACIS-06 §7 steps 2–3).

    - fast-decay -> one aggressive IOC fragment, no fragmentation (speed > stealth)
    - > vwap_threshold_lots -> `scheduled`: fragments spread across vwap_window_s
    - > fragment_threshold_lots -> `fragment`: jittered sizes + jittered delays
    - else one plain fragment.
    Venue order rotates across fragments (signature randomisation); n is chosen
    so no fragment can quantize below min_fragment_lots (dust merged by
    construction)."""
    if total_units <= 0:
        raise DataQualityError("total_units", total_units, "plan needs size > 0")
    if not venues:
        raise DataQualityError("venues", venues, "plan needs >= 1 venue")
    total_lots = total_units / UNITS_PER_LOT
    lo, hi = cfg.fragment_size_jitter
    tlo, thi = cfg.fragment_time_jitter_s

    if fast_decay:
        path, n, window = "ioc", 1, 0.0
    elif float(total_lots) > cfg.vwap_threshold_lots:
        path, window = "scheduled", float(cfg.vwap_window_s)
        n = max(2, round(float(total_lots) / cfg.fragment_threshold_lots))
    elif float(total_lots) > cfg.fragment_threshold_lots:
        path, window = "fragment", 0.0
        n = max(2, round(float(total_lots) / cfg.fragment_threshold_lots))
    else:
        path, n, window = "single", 1, 0.0

    # dust law: never allow a fragment that could quantize under min_fragment_lots
    # (worst case is the lo-jittered share of the renormalised split)
    min_units = Decimal(str(cfg.min_fragment_lots)) * UNITS_PER_LOT
    while n > 1 and (total_units / n) * Decimal(str(lo / ((lo + hi) / 2))) < min_units:
        n -= 1

    sizes = _split_units(total_units, n, lo, hi, rng) if n > 1 else [total_units]

    # venues arrive best-quality-first; fragment 0 routes to the best venue,
    # later fragments rotate through the list (§6 signature randomisation —
    # the non-determinism lives in sizes/timing, the rotation in the order)
    fragments = []
    t = now
    for i, units in enumerate(sizes):
        if path == "scheduled":
            base = window * i / max(1, len(sizes) - 1) if len(sizes) > 1 else 0.0
            t = now + timedelta(seconds=base + rng.uniform(0.0, tlo))
        elif i > 0:
            t = t + timedelta(seconds=rng.uniform(tlo, thi))
        fragments.append(Fragment(
            fragment_id=f"{order_id}:{i}",
            parent_order_id=order_id,
            units=units,
            scheduled_at=t,
            venue=venues[i % len(venues)],
        ))

    assert sum(f.units for f in fragments) == total_units, \
        "C-EXE-1 violated: fragment sum != parent total"
    return FragmentPlan(path=path, weighting="time" if path == "scheduled" else "none",
                        fragments=tuple(fragments))
