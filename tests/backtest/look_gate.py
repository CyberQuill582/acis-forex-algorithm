"""The grade's gate (GAP-P12D-64, dual audit GAP-P12D-83): everything a grade must prove BEFORE any
compute, after which it consumes its look line (one line is one grade). Split from look_register
under the A12 budget when R1.2 grew the register. It reads CANONICAL and git_state through the
register module, so one patch point serves both."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import tests.backtest.look_register as lr
from config.schemas import AcisConfig
from tests.backtest.walk_forward import Fold


def begin_grade(look: object, *, cfg: AcisConfig, loader, source: str, instruments: Sequence[str],
                folds: Sequence[Fold], account: str, cost_stress: float, spread_floor: float,
                simulator: str) -> dict:
    """Everything a grade must prove BEFORE any compute; then it consumes the line. `simulator` is the
    grader's own ("rsim" for `evaluate`, "engine" for the walk-forward runner): a claim naming another
    is refused (R12I-03), so a look registered for one grader cannot be spent by the other."""
    if not isinstance(look, lr.Look):
        raise lr.LookRefused("no registered look: a grade must write its look-register line first (GAP-P12D-64)")
    if look.claim is not None and look.claim.get("simulator") != simulator:
        raise lr.LookRefused(f"look {look.look_id} claims the {look.claim.get('simulator')!r} simulator; "
                             f"this grader is {simulator!r} (R12I-03)")
    src = loader.source_object(source)
    if getattr(src, "name", None) != source:
        raise lr.LookRefused(f"the loader key {source!r} names a source whose own name is {getattr(src, 'name', None)!r}")
    tier = lr.data_tier(src, folds)
    register = lr.LookRegister(Path(look.path).parent)
    if tier > 0 and register.root.resolve() != lr.CANONICAL.resolve():
        raise lr.LookRefused(f"a {lr.TIER_NAMES[tier]} grade needs its look in {lr.CANONICAL}, not {register.root}")
    scan = register.scan()
    if scan.broken:
        raise lr.LookRefused("the look register is broken: " + "; ".join(scan.broken))
    on_disk = scan.lines[int(look.look_id) - 1] if 0 < int(look.look_id) <= len(scan.lines) else None
    if on_disk != json.loads(json.dumps(asdict(look))):
        raise lr.LookRefused(f"look {look.look_id} is not on disk as registered ({look.path})")
    run = (source, type(src).__qualname__, tuple(sorted(instruments)), min(f.train_start for f in folds).isoformat(),
           max(f.test_end for f in folds).isoformat(), lr.config_hash(cfg), tier, account, float(cost_stress),
           float(spread_floor))
    registered = (look.source, look.source_class, look.instruments, look.start, look.end, look.config_hash,
                  look.tier, look.account, look.cost_stress, look.spread_floor)
    if registered != run:
        raise lr.LookRefused(f"look {look.look_id} was registered for another run: {registered} != {run}")
    if tier > 0:
        commit, dirty = lr.git_state()
        if dirty or commit != look.git_commit:
            raise lr.LookRefused(f"look {look.look_id} was registered at {look.git_commit}; the tree is now "
                                 f"{commit}{' (dirty)' if dirty else ''}: the line would not pin the code that grades")
    register.consume(look)
    return register.summary()
