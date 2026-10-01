"""What a family-version declares at registration besides its plan (ACIS-09 C-BT-11 v2 step 3; the
R1.2 external audit's E-R12-03; GAP-P12D-136 item 4).

Mental model:
  * A DECLARATION travels on the claim into the look line. It says whether the family-version is
    FIXED (one pooled combination, graded by the HAC lower bound) or EXPLORED (a declared grid,
    graded by max-t with PBO, so it also fixes the stationary bootstrap's block length and seed);
    its LOOK BUDGET k in {1, 2, 3}, each look tested at alpha/k; and the PASSIVE BENCHMARK its
    paired-excess condition is measured against. An append-only register cannot acquire these
    after a look, so a claim without them is not a pre-registration.
  * DECLARATIONS ARE STICKY per variant: every look of a variant carries its first declaration, so
    a failed look cannot be followed by a friendlier benchmark or a larger budget; and a variant's
    (k+1)-th real-data look in one tier is refused.
  * The benchmarks are RSIM arms on the family's own book: PASSIVE_LONG holds every instrument long
    at its vol-scaled average position (forecast +10), the arm the lab runs (`rsim_lab.MEMBERS`).
  * A cycle's HOLM SET is the cycle row's, not the claim's (`look_claims.cycle_line`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

KINDS = ("fixed", "explored")
BENCHMARKS = ("PASSIVE_LONG",)
MAX_LOOK_BUDGET = 3


@dataclass(frozen=True)
class Declaration:
    kind: str
    look_budget: int
    benchmark: str
    block_length: int | None = None       # explored only: the stationary bootstrap's mean block, in days
    bootstrap_seed: int | None = None     # explored only

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"a family-version is one of {KINDS}")
        if type(self.look_budget) is not int or not 1 <= self.look_budget <= MAX_LOOK_BUDGET:
            raise ValueError(f"the look budget k is 1..{MAX_LOOK_BUDGET}: each look is tested at alpha/k")
        if self.benchmark not in BENCHMARKS:
            raise ValueError(f"the passive benchmark is a registered RSIM arm, one of {BENCHMARKS}")
        boot = (self.block_length, self.bootstrap_seed)
        if self.kind == "fixed" and boot != (None, None):
            raise ValueError("a fixed family has no bootstrap: block length and seed belong to explored ones")
        if self.kind == "explored" and not (all(type(v) is int for v in boot)
                                            and self.block_length >= 1 and self.bootstrap_seed >= 0):
            raise ValueError("an explored family fixes its bootstrap's block length (>= 1 day) and seed (>= 0)")

    def line(self) -> dict:
        return {"kind": self.kind, "look_budget": self.look_budget, "benchmark": self.benchmark,
                "block_length": self.block_length, "bootstrap_seed": self.bootstrap_seed}


def admit_declaration(variant_hash: str, declaration: Declaration, tier: int, lines: Sequence[dict | None]) -> None:
    """Refuse a declaration unlike the variant's first, or a real-data look past its budget."""
    prior = [x for x in lines if x is not None and x.get("kind", "look") == "look"
             and (x.get("claim") or {}).get("variant_hash") == variant_hash]
    first = next((x["claim"].get("declaration") for x in prior), None)
    if first is not None and first != declaration.line():
        raise ValueError(f"variant {variant_hash[:12]} was registered with {first}: a declaration is sticky "
                         "(a new benchmark, kind or budget is a new plan, not a new look)")
    spent = sum(1 for x in prior if x.get("tier", 0) == tier)
    if tier > 0 and spent >= declaration.look_budget:
        raise ValueError(f"variant {variant_hash[:12]} has spent its look budget k={declaration.look_budget} "
                         "in this tier")
