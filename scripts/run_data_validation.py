"""Run the independent Dukascopy validation checks (GAP-P12D-14) over the downloaded archive.

Reads data/dukascopy (the verified S3 mirror) and data/macro/ecb_exr.csv
(scripts/download_ecb_rates.py). Writes data/validation/report.json and a readable
report.md listing every flag first. It never edits or averages the data (C-BT-9).

    python scripts/run_data_validation.py                      # all 8 instruments, 2012–2025
    python scripts/run_data_validation.py --years 2024 --workers 2
    python scripts/run_data_validation.py --instruments EUR_USD GBP_USD EUR_GBP --years 2020 2021
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from tests.backtest.bi5 import SYMBOLS  # noqa: E402
from tests.backtest.validation_checks import (  # noqa: E402
    TRIANGLE, day_metrics, summarise_instrument_year, summarise_triangle, triangle_samples)
from tests.backtest.validation_gold import gold_day, second_wednesday, summarise_gold  # noqa: E402

DATA = ROOT / "data" / "dukascopy"
HISTDATA = ROOT / "data" / "histdata"
OUT = ROOT / "data" / "validation"
_RATES: dict[date, dict[str, float]] = {}


def _init() -> None:
    """Worker start: load the ECB rates once per process."""
    from download_ecb_rates import load
    for (d, ccy), v in load().items():
        _RATES.setdefault(d, {})[ccy] = v


def _work(task: tuple[str, str]) -> dict:
    inst, iso = task
    d = date.fromisoformat(iso)
    return day_metrics(DATA, inst, d, _RATES.get(d))


def _days(year: int):
    d = date(year, 1, 1)
    while d.year == year:
        yield d
        d += timedelta(days=1)


def _md(report: dict) -> str:
    lines = [f"# Dukascopy independent validation — {report['generated_utc']}", "",
             f"Scope: {', '.join(report['instruments'])} · {report['years'][0]}–{report['years'][-1]} · "
             f"{report['day_files']:,} day files in {report['seconds']:,.0f} s", "", "## Flags", ""]
    flags = [f"- **{s['instrument']} {s['year']}** — {f}" for s in report["instrument_years"] for f in s["flags"]]
    flags += [f"- **Triangle {t['year']}** — {f}" for t in report["triangle"] for f in t["flags"]]
    flags += [f"- **Gold {g['year']}** — {f}" for g in report["gold"] for f in g["flags"]]
    lines += flags or ["None — every check passed."]
    lines += ["", "## Instrument-years", "",
              "| instrument | year | ticks | ECB median / p95 / max bps | weekend ticks | rollover spread ratio true / early / late "
              "| gold break ticks true / early / late | jobs-report burst true / early / late |",
              "|---|---|---:|---|---:|---|---|---|"]
    for s in report["instrument_years"]:
        e = s.get("ecb")
        ecb = f"{e['median_bps']} / {e['p95_bps']} / {e['max_bps']}" if e else "—"

        def trio(k):
            v = s.get(k)
            return f"{v.get('true', '—')} / {v.get('early', '—')} / {v.get('late', '—')}" if v else "—"
        lines.append(f"| {s['instrument']} | {s['year']} | {s['ticks']:,} | {ecb} | {s['weekend_ticks']} | "
                     f"{trio('roll_spread')} | {trio('gold_break')} | {trio('nfp_burst')} |")
    lines += ["", "## EUR/GBP triangle (hourly samples)", "", "| year | samples | median bps | p99 bps | flagged |",
              "|---|---:|---:|---:|---:|"]
    for t in report["triangle"]:
        lines.append(f"| {t['year']} | {t['samples']:,} | {t.get('median_bps', '—')} | {t.get('p99_bps', '—')} | "
                     f"{t.get('flagged', '—')} |")
    lines += ["", "## Gold vs HistData (second Wednesday of each month, 12:00–16:00 UTC)", "",
              "| year | sample days | median of daily medians bps | worst daily median bps | flags |",
              "|---|---:|---:|---:|---:|"]
    for g in report["gold"]:
        lines.append(f"| {g['year']} | {g['days']} | {g.get('median_of_medians_bps', '—')} | "
                     f"{g.get('worst_median_bps', '—')} | {len(g['flags'])} |")
    if not report["gold"]:
        lines.append("| — | 0 | — | — | no HistData gold months on disk yet |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", type=int, nargs="+", default=list(range(2012, 2026)))
    ap.add_argument("--instruments", nargs="+", default=list(SYMBOLS), choices=list(SYMBOLS))
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    years = sorted(a.years)
    tasks = [(inst, d.isoformat()) for inst in a.instruments for y in years for d in _days(y)]
    print(f"{len(tasks):,} instrument-days · {a.workers} workers", flush=True)

    by_iy: dict[tuple[str, int], list[dict]] = defaultdict(list)
    hourly: dict[str, dict[str, dict]] = defaultdict(dict)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init) as ex:
        for n, r in enumerate(ex.map(_work, tasks, chunksize=64), 1):
            q = r.pop("hourly", None)
            if q is not None:
                hourly[r["day"]][r["instrument"]] = q
            by_iy[(r["instrument"], int(r["day"][:4]))].append(r)
            if n % 2000 == 0:
                el = time.perf_counter() - t0
                print(f"  {n:,}/{len(tasks):,} days · {el:,.0f} s · ETA {el / n * (len(tasks) - n):,.0f} s", flush=True)

    summaries = [summarise_instrument_year(sorted(v, key=lambda r: r["day"])) for _, v in sorted(by_iy.items())]
    triangle = []
    if all(i in a.instruments for i in TRIANGLE):
        per_year: dict[int, list[dict]] = defaultdict(list)
        for day, qs in sorted(hourly.items()):
            if all(i in qs for i in TRIANGLE):
                per_year[int(day[:4])] += triangle_samples(qs["EUR_USD"], qs["GBP_USD"], qs["EUR_GBP"], day)
        triangle = [summarise_triangle(v, y) for y, v in sorted(per_year.items())]

    gold = []
    if "XAU_USD" in a.instruments:                            # sampled; skips months HistData lacks
        for y in years:
            rows = [r for m in range(1, 13) if (r := gold_day(DATA, HISTDATA, second_wednesday(y, m))) is not None]
            if rows:
                gold.append(summarise_gold(rows, y) | {"samples": rows})
        print(f"gold cross-check: {sum(g['days'] for g in gold)} sample days", flush=True)

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "instruments": a.instruments, "years": years, "day_files": len(tasks),
              "seconds": round(time.perf_counter() - t0, 1),
              "instrument_years": summaries, "triangle": triangle, "gold": gold}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (OUT / "report.md").write_text(_md(report), encoding="utf-8")
    n_flags = (sum(len(s["flags"]) for s in summaries) + sum(len(t["flags"]) for t in triangle)
               + sum(len(g["flags"]) for g in gold))
    print(f"done in {report['seconds']:,.0f} s · {n_flags} flag(s) · {OUT / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
