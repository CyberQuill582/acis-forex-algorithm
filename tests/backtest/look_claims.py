"""Register v2 (R1.2; ACIS-09 C-BT-11 v2 step 1; GAP-P12D-98/89/66): what a real-data look declares
before it runs, a cycle's testing order, and the daily return vector a verdict reads.

Mental model:
  * A CLAIM is one registered family-version: its DECLARED SEARCH SPACE (the grid, the formula,
    the instrument list) hashed before the first look (GAP-P12D-89), the variant inside it, the
    universe, its ORIGIN (a dated paper, a human, or an LLM with its model and knowledge cutoff;
    master §5.6 LLM-contamination law), the simulator that grades it, and the `recon_commit` at
    which B0 held.
  * Every hash is sha256 of canonical JSON (sorted keys, no NaN): the same declaration always
    hashes the same, and changing the grid, formula or instruments changes the hash.
  * The COST MAP hash covers each graded instrument's C8 block, spread limit and swap convention,
    plus the run's stress and floor, so two grades priced differently never share it.
  * An LLM plan that repeats a registered variant_hash is refused at registration (§5.6, R1-D13).
  * A CYCLE row is a register line: the ordered family-versions (at most 5) and the cycle's alpha,
    written before any stage-A look of that cycle, at most one cycle a calendar quarter.
  * A grade's DAILY VECTOR is stored once, content-addressed (vectors/<sha256>.json), and its
    outcome carries the hash, so a verdict is a pure function of the register.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from config.schemas import AcisConfig

ORIGINS = ("literature", "human", "llm")
SIMULATORS = ("engine", "rsim")
MAX_CYCLE = 5


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Origin:
    kind: str                            # "literature" | "human" | "llm"
    model_id: str = ""                   # llm: the generating model
    model_cutoff: str = ""               # llm: its knowledge cutoff, ISO date
    reference: str = ""                  # literature: the citation
    published: str = ""                  # literature: the publication date, ISO date

    def __post_init__(self) -> None:
        if self.kind not in ORIGINS:
            raise ValueError(f"origin must be one of {ORIGINS}")
        if self.kind == "llm" and not (self.model_id and self.model_cutoff):
            raise ValueError("an LLM origin records its model and that model's knowledge cutoff (§5.6)")
        if self.kind == "literature" and not (self.reference and self.published):
            raise ValueError("a literature origin records its dated reference (§5.6)")
        for d in (self.model_cutoff, self.published):
            if d:
                date.fromisoformat(d)


@dataclass(frozen=True)
class Claim:
    family: str
    variant: str                         # "fixed" for a fixed combination, else the member's id
    declared_space: dict = field(repr=False)   # the grid, the formula and the instrument list
    universe_id: str
    origin: Origin
    simulator: str
    recon_commit: str                    # the commit at which B0 last held (C-BT-11 v2 step 0)

    def __post_init__(self) -> None:
        if not (self.family.strip() and self.variant.strip() and self.universe_id.strip()):
            raise ValueError("a claim names its family, variant and universe")
        if self.simulator not in SIMULATORS:
            raise ValueError(f"simulator must be one of {SIMULATORS}")
        if not self.recon_commit.strip():
            raise ValueError("a claim names the recon_commit at which B0 held")
        missing = {"grid", "formula", "instruments"} - set(self.declared_space)
        if missing:
            raise ValueError(f"the declared search space lacks {sorted(missing)} (GAP-P12D-89)")

    @property
    def declared_space_hash(self) -> str:
        return canonical_hash(self.declared_space)

    @property
    def variant_hash(self) -> str:
        """What the plan IS, not what it is called (§5.6 R1-D13: rule, parameters, combination,
        universe): renaming a family never makes an LLM plan new."""
        return canonical_hash([self.declared_space_hash, self.variant, self.universe_id])

    def line(self, cost_map_hash: str) -> dict:
        """What the look line records (C-BT-11 v2 step 1)."""
        return {"family": self.family, "variant": self.variant, "variant_hash": self.variant_hash,
                "declared_space_hash": self.declared_space_hash, "universe_id": self.universe_id,
                "origin": asdict(self.origin), "simulator": self.simulator,
                "recon_commit": self.recon_commit, "cost_map_hash": cost_map_hash}


def cost_map_hash(cfg: AcisConfig, instruments: Sequence[str], cost_stress: float, spread_floor: float) -> str:
    specs = cfg.instruments.instruments
    return canonical_hash({"instruments": {i: {"costs": specs[i].costs.model_dump(mode="json") if specs[i].costs else None,
                                               "max_plausible_spread": specs[i].max_plausible_spread,
                                               "swap_convention": specs[i].swap_convention}
                                           for i in sorted(instruments)},
                           "cost_stress": float(cost_stress), "spread_floor": float(spread_floor)})


def refuse_repeated_llm_variant(claim: Claim, lines: Sequence[dict | None]) -> None:
    if claim.origin.kind != "llm":
        return
    seen = {(x.get("claim") or {}).get("variant_hash") for x in lines if x is not None}
    if claim.variant_hash in seen:
        raise ValueError(f"an LLM plan repeats registered variant {claim.variant_hash[:12]} (§5.6, R1-D13)")


def cycle_line(*, cycle_id: str, order: Sequence[str], alpha: float, lines: Sequence[dict | None],
               now: datetime) -> dict:
    """The cycle row's payload, refused if it breaks serial gatekeeping's registration rules."""
    if not cycle_id.strip() or not 1 <= len(order) <= MAX_CYCLE or len(set(order)) != len(order):
        raise ValueError(f"a cycle names itself and orders 1..{MAX_CYCLE} distinct family-versions")
    if not 0.0 < alpha <= 0.05:
        raise ValueError("a cycle's alpha lies in (0, 0.05]")
    cycles = [x for x in lines if x is not None and x.get("kind") == "cycle"]
    if any(x["cycle_id"] == cycle_id for x in cycles):
        raise ValueError(f"cycle {cycle_id!r} is already registered")
    quarter = (now.year, (now.month - 1) // 3)
    for x in cycles:
        then = datetime.fromisoformat(x["registered_utc"])
        if (then.year, (then.month - 1) // 3) == quarter:
            raise ValueError(f"cycle {x['cycle_id']!r} was already registered this quarter: at most one a quarter")
    return {"kind": "cycle", "cycle_id": cycle_id, "order": list(order), "alpha": float(alpha)}


def store_vector(root: Path, dates: Sequence[date], returns: Sequence[float]) -> str:
    """Write the daily portfolio net-return vector once, named by its hash; return the hash."""
    if len(dates) != len(returns) or not dates:
        raise ValueError("one net return per date, and at least one date")
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise ValueError("the dates must be strictly increasing")
    if not all(math.isfinite(r) for r in returns):
        raise ValueError("a daily net return must be finite")
    payload = {"dates": [d.isoformat() for d in dates], "returns": [float(r) for r in returns]}
    digest = canonical_hash(payload)
    path = Path(root) / "vectors" / f"{digest}.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, allow_nan=False), encoding="utf-8")
        tmp.replace(path)
    return digest


def load_vector(root: Path, digest: str) -> tuple[list[date], list[float]]:
    payload = json.loads((Path(root) / "vectors" / f"{digest}.json").read_text(encoding="utf-8"))
    if canonical_hash(payload) != digest:
        raise ValueError(f"vector {digest[:12]} does not match its hash: it was edited")
    return [date.fromisoformat(d) for d in payload["dates"]], payload["returns"]
