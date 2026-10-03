"""Register v2 (R1.2; ACIS-09 C-BT-11 v2 step 1; GAP-P12D-98/89/66/127): what a real-data look declares
before it runs, a cycle's testing order, and the daily return vector a verdict reads.

Mental model:
  * A CLAIM is one registered family-version: its DECLARED SEARCH SPACE (the grid, the formula,
    the instrument list — those keys only) hashed before the first look (GAP-P12D-89), the variant
    inside it, the universe, its ORIGIN (a dated paper, a human, or an LLM with its model and
    training-data cutoff, proposal date and exposure; master v2.24 §5.6) with the certifying
    boundary it implies, the simulator that grades it, the `recon_commit` at which B0 held, and
    its DECLARATION (fixed or explored, look budget k, passive benchmark; `look_declarations`,
    sticky per variant). The claim must describe the run it registers: the same instruments.
  * Hashes are sha256 of Python `json.dumps(sort_keys=True, allow_nan=False)` over a NORMALISED
    payload (not RFC 8785): strings NFC and stripped, integral floats as ints, −0.0 as 0, grid
    values and instruments as sorted sets, the formula's whitespace collapsed and case-folded. So
    the same plan re-spelled hashes the same (GAP-P12D-127, R12I-01/E-R12-08); `variant_hash`
    covers what the plan IS — space and variant — never a family name or a universe label.
  * ORIGIN IS STICKY per variant (E-R12-01): a variant once registered with an LLM origin may
    only be registered again as LLM, which the repeat rule then refuses (§5.6, R1-D13).
  * The COST MAP hash covers each graded instrument's C8 block, spread limit and swap convention,
    plus the run's stress and floor. (The financing inputs are not in it yet: R12I-07, owned.)
  * A CYCLE row orders 1..5 registered-shape variant hashes (the chain, plus its Holm set: those
    outside the chain, 5 in all), none of which has had a real look,
    at the α the spending schedule gives (0.03, then half the unspent), at most one a UTC calendar
    quarter; no line may be stamped earlier than the line before it.
  * A grade's DAILY VECTOR (dates, never datetimes) is stored once, content-addressed, and read
    back before its hash is returned.
  * REAL-DATA LOOKS ARE OPEN, SCOPED (GAP-P12D-127; owner rulings 2026-10-03): only human- or
    literature-origin claims graded by RSIM or the event simulator (`OPEN_ORIGINS`, `OPEN_SIMULATORS`;
    the event grader admits kill-only looks alone, GAP-P12D-154). LLM plans stay refused until the
    motif veto and plan schema (R12I-11) land, engine looks until `Backtest.run` takes a consumed-look
    token (R12I-12).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from config.schemas import AcisConfig
from tests.backtest.look_declarations import Declaration, admit_declaration

ORIGINS = ("literature", "human", "llm")
SIMULATORS = ("engine", "rsim", "event")
EXPOSURES = ("none", "web", "repository")
SPACE_KEYS = frozenset({"grid", "formula", "instruments"})
MAX_CYCLE = 5
REAL_LOOKS_OPEN = True           # GAP-P12D-127: opened 2026-10-03 by the owner, SCOPED (below)
OPEN_ORIGINS = frozenset({"human", "literature"})   # LLM plans wait for R12I-11 (motif veto, plan schema)
OPEN_SIMULATORS = frozenset({"rsim", "event"})      # engine looks wait for R12I-12 (Backtest.run's token)
HEX64 = re.compile(r"[0-9a-f]{64}")


def _norm(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("a declared value must be finite")
        return int(value) if float(value).is_integer() else float(value)
    if isinstance(value, dict):
        return {_norm(k): _norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    raise ValueError(f"a declared value is JSON data, not {type(value).__name__}")


def canonical_space(space: dict) -> dict:
    """The declared space as data, normalised so that re-spelling a plan never makes it new."""
    if set(space) != SPACE_KEYS:
        raise ValueError(f"the declared search space has exactly the keys {sorted(SPACE_KEYS)} (GAP-P12D-89)")
    grid = _norm(space["grid"])
    if not isinstance(grid, dict):
        raise ValueError("the grid maps each parameter to its values")
    as_set = lambda v: sorted({json.dumps(x, sort_keys=True): x for x in v}.values(),   # noqa: E731
                              key=lambda x: json.dumps(x, sort_keys=True))
    return {"grid": {k: as_set(v) if isinstance(v, list) else v for k, v in grid.items()},
            "formula": " ".join(str(_norm(space["formula"])).split()).casefold(),
            "instruments": sorted(set(_norm(space["instruments"])))}


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Origin:
    """Master v2.24 §5.6 (E-R12-02): who proposed the hypothesis, and from when it may be certified."""
    kind: str                            # "literature" | "human" | "llm"
    model_id: str = ""                   # llm: the proposing model; literature: the model that SELECTED it
    model_cutoff: str = ""               # that model's TRAINING-DATA cutoff (the vendor's broader date)
    proposed: str = ""                   # when the model proposed or selected the plan, ISO date
    exposure: str = ""                   # "none" | "web" | "repository": what the proposer could read
    reference: str = ""                  # literature: the citation
    published: str = ""                  # literature: the publication date, ISO date

    def __post_init__(self) -> None:
        for name in ("model_id", "model_cutoff", "proposed", "exposure", "reference", "published"):
            object.__setattr__(self, name, getattr(self, name).strip())
        if self.kind not in ORIGINS:
            raise ValueError(f"origin must be one of {ORIGINS}")
        if self.kind == "llm" and not self.model_id:
            raise ValueError("an LLM origin records its model and that model's training-data cutoff (§5.6)")
        if self.kind == "literature" and not (self.reference and self.published):
            raise ValueError("a literature origin records its dated reference (§5.6)")
        if self.kind == "human" and (self.model_id or self.model_cutoff or self.proposed or self.exposure):
            raise ValueError("model fields belong to an LLM origin or an LLM-selected paper: say llm if a model made it")
        if self.kind != "literature" and (self.reference or self.published):
            raise ValueError("a reference belongs to a literature origin only")
        if self.model_id and not (self.model_cutoff and self.proposed and self.exposure in EXPOSURES):
            raise ValueError(f"a model records its training-data cutoff, the proposal date and exposure in {EXPOSURES}")
        for name in ("model_cutoff", "proposed", "published"):
            if getattr(self, name):
                object.__setattr__(self, name, date.fromisoformat(getattr(self, name)).isoformat())

    @property
    def llm_touched(self) -> bool:
        """LLM-originated, or a paper an LLM selected: the model's memory is in the plan."""
        return bool(self.model_id)

    def boundary(self) -> date | None:
        """The first day data can certify this hypothesis on (§5.6 v2.24); None: no restriction."""
        if self.llm_touched:
            cutoff = date.fromisoformat(self.model_cutoff)
            return cutoff if self.exposure == "none" else max(cutoff, date.fromisoformat(self.proposed))
        return date.fromisoformat(self.published) if self.kind == "literature" else None


@dataclass(frozen=True)
class Claim:
    family: str
    variant: str                         # "fixed" for a fixed combination, else the member's id
    declared_space: dict = field(repr=False)   # the grid, the formula and the instrument list
    universe_id: str
    origin: Origin
    simulator: str
    recon_commit: str                    # the commit at which B0 last held (C-BT-11 v2 step 0)
    declaration: Declaration             # kind, look budget, passive benchmark (E-R12-03; look_declarations)

    def __post_init__(self) -> None:
        for name in ("family", "variant", "universe_id", "recon_commit"):
            object.__setattr__(self, name, str(_norm(getattr(self, name))))
        if not (self.family and self.variant and self.universe_id):
            raise ValueError("a claim names its family, variant and universe")
        if self.simulator not in SIMULATORS:
            raise ValueError(f"simulator must be one of {SIMULATORS}")
        if not self.recon_commit:
            raise ValueError("a claim names the recon_commit at which B0 held")
        if not isinstance(self.declaration, Declaration):
            raise ValueError("a claim carries its registration-time declaration (E-R12-03)")
        object.__setattr__(self, "declared_space", canonical_space(self.declared_space))

    @property
    def declared_space_hash(self) -> str:
        return canonical_hash(self.declared_space)

    @property
    def variant_hash(self) -> str:
        """What the plan IS (§5.6 R1-D13): the normalised space and the variant, never a name."""
        return canonical_hash([self.declared_space_hash, self.variant.casefold()])

    def line(self, cost_map_hash: str) -> dict:
        """What the look line records (C-BT-11 v2 step 1)."""
        return {"family": self.family, "variant": self.variant, "variant_hash": self.variant_hash,
                "declared_space_hash": self.declared_space_hash, "universe_id": self.universe_id,
                "origin": asdict(self.origin), "simulator": self.simulator,
                "certifying_boundary": (lambda b: b.isoformat() if b else None)(self.origin.boundary()),
                "recon_commit": self.recon_commit, "cost_map_hash": cost_map_hash,
                "declaration": self.declaration.line()}


def cost_map_hash(cfg: AcisConfig, instruments: Sequence[str], cost_stress: float, spread_floor: float) -> str:
    specs = cfg.instruments.instruments
    return canonical_hash({"instruments": {i: {"costs": specs[i].costs.model_dump(mode="json") if specs[i].costs else None,
                                               "max_plausible_spread": specs[i].max_plausible_spread,
                                               "swap_convention": specs[i].swap_convention}
                                           for i in sorted(instruments)},
                           "cost_stress": float(cost_stress), "spread_floor": float(spread_floor)})


HOLDOUT_TIER = 3                     # look_tiers.TIER_NAMES: the 2024-25 holdout, graded once per variant (stage C)


def admit_claim(claim: Claim, instruments: Sequence[str], lines: Sequence[dict | None], tier: int) -> None:
    """Refuse a claim that does not describe its run, launders an LLM variant (§5.6), changes its
    declaration or overruns its look budget (look_declarations)."""
    if claim.declared_space["instruments"] != sorted(set(instruments)):
        raise ValueError("the claim's declared instruments are not the instruments this look grades (R12I-03)")
    if tier > 0 and (claim.origin.kind not in OPEN_ORIGINS or claim.simulator not in OPEN_SIMULATORS):
        raise ValueError(f"real looks are open for {sorted(OPEN_ORIGINS)} claims graded by {sorted(OPEN_SIMULATORS)} "
                         "only (owner ruling 2026-10-03): LLM plans wait for R12I-11, engine looks for R12I-12")
    prior = [(x.get("claim") or {}) for x in lines if x is not None and x.get("kind", "look") == "look"]
    origins = [c["origin"] for c in prior if c.get("variant_hash") == claim.variant_hash]
    if any(o.get("model_id") for o in origins) and not claim.origin.llm_touched:
        raise ValueError(f"variant {claim.variant_hash[:12]} was registered as an LLM plan: its origin is "
                         "the hypothesis's, and a new label does not remove the model's memory (§5.6)")
    if claim.origin.llm_touched and origins and tier != HOLDOUT_TIER:
        raise ValueError(f"an LLM plan repeats registered variant {claim.variant_hash[:12]} (§5.6, R1-D13)")
    # v2.35 (GAP-P12D-159): stage C's one holdout look at a registered variant is not a re-proposal. An LLM
    # boundary falls after 2026-01-01, so every holdout look is kill-only, and the budget below allows one.
    admit_declaration(claim.variant_hash, claim.declaration, tier, lines)


def refuse_backwards_clock(lines: Sequence[dict | None], now: datetime) -> None:
    stamps = [x["registered_utc"] for x in lines if x is not None and "registered_utc" in x]
    if stamps and datetime.fromisoformat(stamps[-1]) > now:
        raise ValueError(f"the clock reads {now.isoformat()}, before the last line's {stamps[-1]}: fix the clock")


def spending_alpha(prior_cycles: int) -> float:
    """C-BT-11 v2 D-d: cycle 1 spends 0.03, each later cycle half the lifetime 0.05 still unspent."""
    return 0.03 if prior_cycles == 0 else 0.02 / 2 ** prior_cycles      # unspent 0.02, then halves


def cycle_line(*, cycle_id: str, order: Sequence[str], alpha: float | None, lines: Sequence[dict | None],
               now: datetime, holm: Sequence[str] = ()) -> dict:
    """The cycle row's payload, refused if it breaks serial gatekeeping's registration rules. `holm` is
    the cycle's family-versions outside the chain (tested only if the whole chain passed, Holm-adjusted
    among themselves at the cycle's alpha); chain and Holm set together hold at most MAX_CYCLE."""
    if not REAL_LOOKS_OPEN:
        raise ValueError("cycle rows open with real-data looks, at R1.4 (GAP-P12D-127)")
    if not isinstance(order, (list, tuple)) or not all(isinstance(h, str) and HEX64.fullmatch(h) for h in order):
        raise ValueError("a cycle orders variant hashes (64 lower-case hex each)")
    if not cycle_id.strip() or not 1 <= len(order) <= MAX_CYCLE or len(set(order)) != len(order):
        raise ValueError(f"a cycle names itself and orders 1..{MAX_CYCLE} distinct family-versions")
    holm = list(holm) if isinstance(holm, (list, tuple)) else [holm]
    if not all(isinstance(h, str) and HEX64.fullmatch(h) for h in holm) or len(set(holm)) != len(holm)             or set(holm) & set(order) or len(order) + len(holm) > MAX_CYCLE:
        raise ValueError(f"a Holm set names distinct variant hashes outside the chain, at most {MAX_CYCLE} in all")
    refuse_backwards_clock(lines, now)
    cycles = [x for x in lines if x is not None and x.get("kind") == "cycle"]
    if any(x["cycle_id"] == cycle_id for x in cycles):
        raise ValueError(f"cycle {cycle_id!r} is already registered")
    utc = now.astimezone(timezone.utc)
    for x in cycles:
        then = datetime.fromisoformat(x["registered_utc"]).astimezone(timezone.utc)
        if (then.year, (then.month - 1) // 3) == (utc.year, (utc.month - 1) // 3):
            raise ValueError(f"cycle {x['cycle_id']!r} was already registered this quarter: at most one a quarter")
    due = spending_alpha(len(cycles))
    if alpha is not None and not math.isclose(alpha, due, rel_tol=0, abs_tol=1e-15):
        raise ValueError(f"this cycle's alpha is {due} by the spending schedule, not {alpha}")
    looked = {(x.get("claim") or {}).get("variant_hash") for x in lines
              if x is not None and x.get("kind", "look") == "look" and x.get("tier", 0) > 0}
    if looked & (set(order) | set(holm)):
        raise ValueError("a cycle's order is registered before any real look of its members")
    return {"kind": "cycle", "cycle_id": cycle_id, "order": list(order), "holm": holm, "alpha": due}


def store_vector(root: Path, dates: Sequence[date], returns: Sequence[float]) -> str:
    """Write the daily portfolio net-return vector once, named by its hash; return the hash."""
    if len(dates) != len(returns) or not dates:
        raise ValueError("one net return per date, and at least one date")
    if not all(type(d) is date for d in dates):
        raise ValueError("a daily vector is keyed by dates, never datetimes")
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise ValueError("the dates must be strictly increasing")
    if not all(math.isfinite(r) for r in returns):
        raise ValueError("a daily net return must be finite")
    payload = {"dates": [d.isoformat() for d in dates], "returns": [float(r) for r in returns]}
    digest = canonical_hash(payload)
    path = Path(root) / "vectors" / f"{digest}.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
        with tmp.open("wb") as f:
            f.write(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass                                          # a twin writer won; verified below
        finally:
            tmp.unlink()
    load_vector(root, digest)                             # read back: never hand out a bad hash
    return digest


def load_vector(root: Path, digest: str) -> tuple[list[date], list[float]]:
    try:
        payload = json.loads((Path(root) / "vectors" / f"{digest}.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"vector {digest[:12]} is unreadable: it was edited or torn") from exc
    if canonical_hash(payload) != digest:
        raise ValueError(f"vector {digest[:12]} does not match its hash: it was edited")
    return [date.fromisoformat(d) for d in payload["dates"]], payload["returns"]
