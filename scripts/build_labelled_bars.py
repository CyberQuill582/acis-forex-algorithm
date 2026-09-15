"""Build the regime-labelled bar cache QIEA evolves on (ACIS-03 §5, GAP-P12D-18).

    python scripts/build_labelled_bars.py                                  # enabled instruments, 2012–2023
    python scripts/build_labelled_bars.py --instruments EUR_USD --years 2023 --workers 2

Each instrument-year is an independent job (NVMA state is per instrument), so jobs run in
parallel. A year already cached under the current labelling spec is skipped. The locked
2024–2025 holdout is never labelled here: no fold's training may read it.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.schemas import load_config  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from tests.backtest.data_loader import BacktestDataLoader  # noqa: E402
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec, label_instrument_year  # noqa: E402
from tests.backtest.replay_logging import ReplayEventLogger  # noqa: E402
from tests.backtest.sources import DukascopyTickSource  # noqa: E402

SOURCE = "dukascopy"
DATA_START = datetime(2012, 1, 1, tzinfo=timezone.utc)
HOLDOUT_YEAR = 2024                          # OOS_VALIDATION.md: 2024–2025 untouched
OUT = ROOT / "data" / "labelled_bars"


def _job(instrument: str, year: int) -> tuple[str, int, int, float]:
    t0 = time.perf_counter()
    cfg = load_config(ROOT / "config")
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    log = ReplayEventLogger(JsonlEventLogger(OUT / "logs" / f"{instrument}_{year}.jsonl",
                                             layer="labels", session_id=f"labels-{instrument}-{year}"),
                            keep_per_type=20)
    loader = BacktestDataLoader({SOURCE: DukascopyTickSource(ROOT / "data" / "dukascopy")}, log)
    cache = LabelledBarCache(OUT, LabelSpec.for_config(cfg, SOURCE))
    n = label_instrument_year(cfg=cfg, loader=loader, source=SOURCE, instrument=instrument,
                              year=year, cache=cache, logger=log, data_start=DATA_START)
    log.close()
    return instrument, year, n, time.perf_counter() - t0


def main() -> int:
    cfg = load_config(ROOT / "config")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instruments", nargs="+", default=sorted(cfg.instruments.enabled))
    ap.add_argument("--years", type=int, nargs="+", default=list(range(2012, HOLDOUT_YEAR)))
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if any(y >= HOLDOUT_YEAR for y in a.years):
        print(f"refused: {HOLDOUT_YEAR}+ is the locked holdout — no fold trains on it")
        return 2
    cache = LabelledBarCache(OUT, LabelSpec.for_config(cfg, SOURCE))
    jobs = [(i, y) for i in a.instruments for y in a.years if not cache.has(i, y)]
    print(f"{len(jobs)} instrument-years to label ({a.workers} workers)", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for fut in as_completed([ex.submit(_job, i, y) for i, y in jobs]):
            instrument, year, n, secs = fut.result()
            print(f"  {instrument} {year}: {n:,} bars in {secs:,.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
