"""A grade's outcome as a line of the register's hash chain (the R1.2 audit's R12I-08 / E-R12-06;
GAP-P12D-127).

Mental model:
  * A graded look has at most one outcome, and the outcome is a `kind: outcome` LINE of the chain, not
    a side file: editing or deleting it breaks the chain like any other line, so the verdict (a pure
    function of the register) reads only what the chain vouches for.
  * An outcome is accepted only for a look of THIS register whose line is on disk exactly as written
    and that was graded (its `.graded.json` marker). A second outcome for the same look is refused, and
    `LookRegister.scan` breaks on an outcome line that names no earlier look line.
  * The daily portfolio vector is stored by its content hash (`look_claims.store_vector`); the chained
    outcome line carries that hash, so the vector is tamper-evident through the line.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import tests.backtest.look_claims as lc


def record(register, look, outcome: dict, daily: tuple[Sequence, Sequence[float]] | None = None) -> None:
    from tests.backtest.look_register import LookRefused       # look_register delegates here
    root = register.root
    line = root / f"{look.look_id}.json"
    if (Path(look.path).parent.resolve() != root.resolve() or not line.exists()
            or json.loads(line.read_bytes()) != json.loads(json.dumps(asdict(look)))
            or not (root / f"{look.look_id}.graded.json").exists()):
        raise LookRefused(f"look {look.look_id} is not a graded look of this register")
    if daily is not None:
        outcome = {**outcome, "daily_vector": lc.store_vector(root, *daily)}
    payload = json.loads(json.dumps(outcome, sort_keys=True, allow_nan=False))   # plain JSON; NaN refused

    def build(scan, path) -> dict:
        now = datetime.now(timezone.utc)
        try:
            lc.refuse_backwards_clock(scan.lines, now)
        except ValueError as e:
            raise LookRefused(str(e)) from None
        if read(scan.lines, look.look_id) is not None:
            raise LookRefused(f"look {look.look_id} already has its outcome: one grade, one outcome")
        return {"kind": "outcome", "look_id": look.look_id, "outcome": payload, "prev_hash": scan.head,
                "registered_utc": now.isoformat(timespec="seconds")}
    register._append(build)


def read(lines: Sequence[dict | None], look_id: str) -> dict | None:
    """The chained outcome of `look_id`, or None if it has none."""
    return next((x["outcome"] for x in lines if x is not None and x.get("kind") == "outcome"
                 and x.get("look_id") == look_id), None)
