"""Which cycle a stage-A look belongs to (ACIS-09 C-BT-11 v2 step 3; the R1.2 audit's R12I-04 / E-R12-05,
GAP-P12D-127).

Mental model:
  * A stage-A look is a real-data RSIM look in the development tier (tier 2, 2012-2023). It is tested
    only inside a registered cycle, so its line NAMES that cycle and its look index (1..k) at
    registration; the verdict counts a look only in the cycle it names (`verdict.cycle_verdict`).
  * The cycle is the LATEST cycle row, written before the look, whose chain or Holm set names the
    variant. A variant left untested by an earlier cycle's stopped chain may be listed again later
    (`cycle_line` refuses only variants that were already looked at), and its looks then belong there.
  * A stage-A look of a variant no cycle names is refused: its order must be registered first.
"""

from __future__ import annotations

from typing import Sequence

STAGE_A_TIER = 2                     # look_tiers: 2 = validation, 2012-2023


def is_stage_a(tier: int, simulator: str | None) -> bool:
    return tier == STAGE_A_TIER and simulator == "rsim"


def stage_a_cycle(variant: str, lines: Sequence[dict | None]) -> dict:
    """{cycle_id, look_index} for the next stage-A look of `variant`, or ValueError if no cycle names it."""
    rows = [x for x in lines if x is not None and x.get("kind") == "cycle"
            and variant in (*x["order"], *x.get("holm", ()))]
    if not rows:
        raise ValueError("a stage-A look belongs to a registered cycle: register the cycle's order first "
                         "(C-BT-11 v2 step 1, R12I-04)")
    cycle_id = rows[-1]["cycle_id"]
    prior = sum(1 for x in lines if x is not None and x.get("kind", "look") == "look"
                and (x.get("claim") or {}).get("variant_hash") == variant
                and (x.get("cycle") or {}).get("cycle_id") == cycle_id)
    return {"cycle_id": cycle_id, "look_index": prior + 1}
