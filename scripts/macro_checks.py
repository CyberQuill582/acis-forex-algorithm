"""The acceptance rules for a downloaded macro series (scripts/download_macro.py; split from it under the
A12 legibility budget, PR16E-03). A series is saved only if `validate` returns None: rows exist, dates
strictly increase, values sit in the declared band, the series starts and ends where it must, the SPX
matches its known closes, and the BIS file holds exactly the areas asked for."""

from __future__ import annotations

import math
from datetime import date

BIS_AREAS = ("US", "XM", "JP", "GB", "AU", "CH", "CA")
LIVE_BIS_AREAS = ("AU",)       # the runtime reads BIS for AUD only (core/data/rates.py); R16E-02
SPX_KNOWN_CLOSES = {date(2012, 1, 3): 1277.06, date(2019, 12, 31): 3230.78, date(2020, 3, 23): 2237.40,  # COVID low
                    date(2021, 12, 31): 4766.18, date(2022, 12, 30): 3839.50}


def validate(sid: str, rows, lo: float, hi: float, first_by: date | None,
             ends_by: date = date(2025, 12, 1), areas=BIS_AREAS) -> str | None:
    """Return a rejection reason, or None if the series is usable."""
    if not rows:
        return "no rows"
    if sid == "spx_yahoo":
        got = dict(rows)
        for d, want in SPX_KNOWN_CLOSES.items():
            if d not in got or abs(got[d] - want) > 0.02:
                return f"known close {d} = {want}, series has {got.get(d)}"
    keyed = [(r[0], r[1]) for r in rows] if sid == "bis_policy" else [(r[0], "") for r in rows]
    per_key: dict[str, list] = {}
    for (d, k), r in zip(keyed, rows):
        per_key.setdefault(k, []).append((d, r[-1]))
    for k, pts in per_key.items():
        ds = [d for d, _ in pts]
        if any(b <= a for a, b in zip(ds, ds[1:])):
            return f"{k or sid}: dates not strictly increasing"
        bad = [v for _, v in pts if not (math.isfinite(v) and lo <= v <= hi)]
        if bad:
            return f"{k or sid}: {len(bad)} values outside [{lo}, {hi}] e.g. {bad[:3]}"
        if first_by and ds[0] > first_by:
            return f"{k or sid}: starts {ds[0]}, expected by {first_by}"
        if ds[-1] < ends_by:
            return f"{k or sid}: ends {ds[-1]}, expected by {ends_by}"
    if sid == "bis_policy" and sorted(per_key) != sorted(areas):
        return f"areas {sorted(per_key)} != {sorted(areas)}"
    return None
