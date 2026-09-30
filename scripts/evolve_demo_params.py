"""Evolve the demo's parameter sets (owner ruling 2026-09-30, GAP-P12D-129). Server-run.

    python scripts/build_labelled_bars.py --instruments EUR_USD USD_JPY --years 2022 2023 --workers 4
    python scripts/evolve_demo_params.py --params data/runtime/params.db

One fold of the walk-forward's own `evolve_fold`, training on the 730 days that end on
2023-12-31 (`train_end` 2024-01-01, exclusive), for the venue's mapped instruments. The
champions are STAGED in the ParamLibrary the runtime opens; the runtime promotes them at a
session boundary while flat (ACIS-03 §7 C2). Invariants:
  * Nothing from 2024 on is read: the label builder refuses the holdout years, and
    `evolve_fold` reads only bars that open before `train_end`. No graded look is written.
  * The sets are UNVALIDATED (master §5: the as-built demo trades QIEA sets nobody validated);
    the record says so. The demo proves plumbing, not edge (GAP-P12D-49).
  * The record (span, instruments, seeds' fold index, champions, commit) is kept beside the
    library, so the demo's parameters can always be traced to the run that made them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build_labelled_bars import DATA_START, OUT, SOURCE  # noqa: E402
from config.schemas import load_config  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from core.optimizer.param_library import ParamLibrary  # noqa: E402
from tests.backtest.evolve_step import cost_model, evolve_fold  # noqa: E402
from tests.backtest.harness import FoldData  # noqa: E402
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec  # noqa: E402
from tests.backtest.replay_logging import ReplayEventLogger  # noqa: E402
from tests.backtest.walk_forward import Fold  # noqa: E402

UTC = timezone.utc
TRAIN_START = datetime(2022, 1, 1, tzinfo=UTC)
TRAIN_END = datetime(2024, 1, 1, tzinfo=UTC)          # exclusive: the last bar is 2023-12-31
RULING = ("owner 2026-09-30, 'Evolve pre-2024 (Recommended)': QIEA champions on the 730 days "
          "ending 2023-12-31, traded at one minimum lot, UNVALIDATED (GAP-P12D-129)")


class _Flat:
    """Staging only: nothing is promoted here, so the gate is never read for a decision."""

    def open_position_count(self) -> int:
        return 0


def main(argv=None) -> int:
    cfg = load_config(ROOT / "config")
    venue = cfg.system.venue
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--params", default="data/runtime/params.db")
    ap.add_argument("--instruments", nargs="+",
                    default=sorted(venue.symbol_names) if venue else ["EUR_USD", "USD_JPY"])
    a = ap.parse_args(argv)
    cache = LabelledBarCache(OUT, LabelSpec.for_config(cfg, SOURCE, DATA_START))
    missing = [(i, y) for i in a.instruments for y in (2022, 2023) if not cache.has(i, y)]
    if missing:
        print(f"refused: no labelled bars for {missing} — run scripts/build_labelled_bars.py first")
        return 2
    params = Path(a.params)
    params.parent.mkdir(parents=True, exist_ok=True)
    log = ReplayEventLogger(JsonlEventLogger(params.with_suffix(".evolve.jsonl"), layer="optimizer",
                                             session_id="demo-evolve"), keep_per_type=50)
    lib = ParamLibrary(params, cfg.system.session_boundaries,
                       cfg.system.param_stall_alert_boundaries, _Flat(), log)
    fold = Fold(0, TRAIN_START, TRAIN_END, TRAIN_END, datetime(2024, 1, 2, tzinfo=UTC))
    costs = {i: cost_model(cfg, i) for i in a.instruments}
    record = evolve_fold(SimpleNamespace(params=lib), FoldData(fold, test_states=()), cfg=cfg,
                         costs=costs, cache=cache, instruments=a.instruments, logger=log)
    lib.close()
    log.close()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip()
    record.update(ruling=RULING, validated=False, instruments=a.instruments, commit=commit,
                  train_start=TRAIN_START.isoformat(), made_at=datetime.now(UTC).isoformat(),
                  staged={r: e["staged_from"] for r, e in record["regimes"].items()})
    params.with_suffix(".evolution.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"{record['champions']} champion(s); staged per regime: {record['staged']}")
    return 0 if record["champions"] else 1


if __name__ == "__main__":
    sys.exit(main())
