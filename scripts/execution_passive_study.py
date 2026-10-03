"""The passive-first execution study (EXECUTION agent, 2026-10-03): what a resting limit order saves at
ACIS's decision slots, against a market order, on recorded quotes. Proposal: archive/EXECUTION_PROPOSAL_2026-10-03.md.

Mental model:
  * EXECUTION only, never a family's P&L: at each slot of each day a buy AND a sell go through
    `passive_fill.simulate` for every policy (touch or mid; 1, 5, 15, 30 minutes; the venue's touch rule
    and one tick through). No signal is computed, nothing is registered, nothing is a look.
  * Sources: Dukascopy ticks (FX, XAU); Dukascopy 1-minute BID/ASK candles (US500: the order inside a
    minute is unknown, so a fill is stamped at the minute's end, the owner's quoted-minute rule); the
    demo's own Pepperstone ticks (its data_log): the same slots, plus an arrival every minute (hour = unit).
  * An ENTRY rests from its slot (benchmark: the market order there). An EXIT rests a window before its
    deadline (benchmark: the market order at the deadline).
  * The 2024-25 holdout stays sealed: `--end` past 2023-12-31 is refused.
  * Output: per (source, instrument, slot, policy) summaries; the day is the unit of the standard error.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from tests.backtest.bi5 import decode_arrays  # noqa: E402
from tests.backtest.candles_min import decode_day  # noqa: E402
from tests.backtest.exchange_days import holidays  # noqa: E402
from tests.backtest.passive_fill import Policy, Quotes, simulate, summarise  # noqa: E402

UTC, NY, LDN = timezone.utc, "America/New_York", "Europe/London"
SEALED_FROM = date(2024, 1, 1)
CFG = load_config(ROOT / "config")
FX = ("EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD")      # the FX with Dukascopy ticks on disk
D1_FX = tuple(CFG.system.targets.universe)            # the demo's 13 FX (R6-4): its venue ticks after the cutover
US500_TICK = 0.1    # Pepperstone quotes US500 to one decimal; the yaml's 0.01 is unverified, the coarser grid is conservative
SLOTS = {                                   # label -> (instruments, zone, local time, kind)
    "d1_0800ny": (D1_FX + ("XAU_USD",), NY, time(8), "entry"),
    "roll_1700ny": (FX, NY, time(17), "entry"),
    "fxhedge_1500ldn": (FX, LDN, time(15), "entry"),
    "fxhedge_1559ldn": (FX, LDN, time(15, 59), "exit"),
    "goldew_0200ny": (("XAU_USD",), NY, time(2), "entry"),
    "goldew_0200ny_exit": (("XAU_USD",), NY, time(2), "exit"),
    "goldew_1100ny": (("XAU_USD",), NY, time(11), "entry"),
    "goldew_1100ny_exit": (("XAU_USD",), NY, time(11), "exit"),
    "imom_1530et": (("US500",), NY, time(15, 30), "entry"),
    "imom_1600et": (("US500",), NY, time(16), "exit"),
}
WINDOWS = (60, 300, 900, 1800)
POLICIES = (tuple(Policy(lv, w, th) for lv in ("touch", "mid") for w in WINDOWS for th in (0, 1))
            + tuple(Policy("chase", w, th, r) for w in WINDOWS for th in (0, 1) for r in (0, 500, 3000))
            + tuple(Policy("delay", w, 0) for w in WINDOWS))


def tick(inst: str) -> float:
    return US500_TICK if inst == "US500" else CFG.instruments.instruments[inst].tick_size


def _key(p: Policy) -> str:
    return f"{p.level}/{p.window_s}s/through{p.through}" + (f"/react{p.react_ms}" if p.react_ms else "")


def run_slots(q: Quotes, inst: str, day: date, unit: str, source: str) -> list[tuple]:
    """Every policy x side at each of `inst`'s slots on `day`; rows (source, inst, slot, policy, unit, outcome)."""
    rows = []
    for label, (insts, zone, at, kind) in SLOTS.items():
        if inst not in insts:
            continue
        due = int(datetime.combine(day, at, tzinfo=ZoneInfo(zone)).timestamp() * 1000)
        for p in POLICIES:
            rest = due if kind == "entry" else due - p.window_s * 1000
            for side in (1, -1):
                o = simulate(q, rest, side, p, tick(inst), "arrival" if kind == "entry" else "deadline")
                if o is not None:
                    rows.append((source, inst, label, _key(p), unit or day.isoformat(), o))
    return rows


def _tick_job(job: tuple[str, str, str]) -> list[tuple]:
    root, inst, iso = job
    day = date.fromisoformat(iso)
    f = Path(root) / inst / str(day.year) / f"{day.month - 1:02d}" / f"{day.day:02d}_ticks.bi5"
    if not f.exists():
        return []
    ms, bid, ask = decode_arrays(f.read_bytes(), inst, datetime(day.year, day.month, day.day, tzinfo=UTC))
    return run_slots(Quotes.from_ticks(ms, bid, ask), inst, day, "", "dukascopy") if len(ms) else []


def minute_quotes(bid: np.ndarray, ask: np.ndarray) -> Quotes:
    """A day's QUOTED minutes (traded, or the bid moved), each stamped at its END, with its extremes."""
    quoted = (bid["volume"] > 0) | (ask["volume"] > 0) | (bid["open"] != bid["close"])
    return Quotes((bid["ts"][quoted] + 60) * 1000, bid["close"][quoted], ask["close"][quoted],
                  ask["low"][quoted], bid["high"][quoted])


def _minute_job(job: tuple[str, str]) -> list[tuple]:
    root, iso = job
    day = date.fromisoformat(iso)
    base = Path(root) / "USA500IDXUSD" / str(day.year) / f"{day.month - 1:02d}" / f"{day.day:02d}"
    try:
        bid, ask = (decode_day((base / f"{s}_candles_min_1.bi5").read_bytes(), "US500", day) for s in ("BID", "ASK"))
    except FileNotFoundError:
        return []
    return run_slots(minute_quotes(bid, ask), "US500", day, "", "dukascopy_min")


def demo_quotes(path: Path) -> dict[str, Quotes]:
    """The demo's MARKET_STATE extract (instrument, event_time, bid, ask, is_stale): fresh ticks only."""
    cols = defaultdict(lambda: ([], [], []))
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["is_stale"] == "1":
                continue
            c = cols[r["instrument"]]
            c[0].append(int(datetime.fromisoformat(r["event_time"]).timestamp() * 1000))
            c[1].append(float(r["bid"]))
            c[2].append(float(r["ask"]))
    out = {}
    for inst, (t, b, a) in cols.items():
        order = np.argsort(np.array(t), kind="stable")
        out[inst] = Quotes.from_ticks(np.array(t)[order], np.array(b)[order], np.array(a)[order])
    return out


def demo_slot(at: datetime) -> str | None:
    """The rollover (20:55-21:30 UTC, the demo's dates are in EDT), the day (outside 20:00-23:00 UTC), or neither."""
    if (20, 55) <= (at.hour, at.minute) < (21, 30):
        return "demo_rollover"
    return None if 20 <= at.hour <= 22 else "demo_day"


def demo_rows(quotes: dict[str, Quotes]) -> list[tuple]:
    """The venue's own slots on each day of the demo's span, then an entry arrival every minute of it."""
    rows = []
    for inst, q in quotes.items():
        d0, d1 = (datetime.fromtimestamp(int(x) / 1000, UTC).date() for x in (q.t[0], q.t[-1]))
        for k in range((d1 - d0).days + 1):
            rows.extend(run_slots(q, inst, d0 + timedelta(k), "", "pepperstone_demo"))
        first, last = int(q.t[0]) // 60_000 * 60_000 + 300_000, int(q.t[-1]) - 3_600_000
        for rest in range(first, last, 60_000):
            at = datetime.fromtimestamp(rest / 1000, UTC)
            slot = demo_slot(at)
            for p in POLICIES if slot else ():
                for side in (1, -1):
                    o = simulate(q, rest, side, p, tick(inst))
                    if o is not None:
                        rows.append(("pepperstone_demo", inst, slot, _key(p), at.strftime("%Y-%m-%dT%H"), o))
    return rows


def aggregate(rows: list[tuple]) -> list[dict]:
    """Group by (source, instrument, slot, policy); the unit (a day, or a demo clock hour) carries the SE."""
    groups: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for source, inst, slot, pol, unit, o in rows:
        groups[(source, inst, slot, pol)][unit].append(o)
    out = []
    for (source, inst, slot, pol), units in sorted(groups.items()):
        s = summarise(units.values())
        years, spreads = defaultdict(list), defaultdict(list)
        for unit, os in units.items():
            years[unit[:4]].append(np.mean([o.saving_bp for o in os]))
            spreads[unit[:4]].extend(o.arrival_spread_bp * o.arrival_mid / 1e4 for o in os)
        out.append({"source": source, "instrument": inst, "slot": slot, "policy": pol, **asdict(s),
                    "by_year": {y: round(float(np.mean(v)), 4) for y, v in sorted(years.items())},
                    "spread_px_by_year": {y: float(np.median(v)) for y, v in sorted(spreads.items())}})
    return out


def _weekdays(start: date, end: date, skip: frozenset = frozenset()) -> list[str]:
    n = (end - start).days + 1
    return [d.isoformat() for d in (start + timedelta(k) for k in range(n)) if d.weekday() < 5 and d not in skip]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ticks", type=Path, help="Dukascopy day files: <root>/<INST>/<YYYY>/<MM0>/<DD>_ticks.bi5")
    ap.add_argument("--minutes", type=Path, help="Dukascopy 1-minute candles root (USA500IDXUSD below it)")
    ap.add_argument("--demo", type=Path, help="the demo's MARKET_STATE extract (csv.gz)")
    ap.add_argument("--instruments", default=",".join(FX + ("XAU_USD",)))
    ap.add_argument("--start", type=date.fromisoformat, default=date(2019, 1, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=date(2023, 12, 31))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.end >= SEALED_FROM:
        ap.error(f"--end {a.end} reaches the sealed 2024-25 holdout")
    rows: list[tuple] = []
    with ProcessPoolExecutor(a.workers) as ex:
        if a.ticks:
            jobs = [(str(a.ticks), i, d) for i in a.instruments.split(",") for d in _weekdays(a.start, a.end)]
            for r in ex.map(_tick_job, jobs, chunksize=16):
                rows.extend(r)
        if a.minutes:
            nyse = frozenset(h for y in range(a.start.year, a.end.year + 1) for h in holidays("XNYS", y))
            for r in ex.map(_minute_job, [(str(a.minutes), d) for d in _weekdays(a.start, a.end, nyse)], chunksize=16):
                rows.extend(r)
    if a.demo:
        rows.extend(demo_rows(demo_quotes(a.demo)))
    summary = aggregate(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"start": a.start.isoformat(), "end": a.end.isoformat(), "rows": summary}, indent=1),
                     encoding="utf-8")
    print(f"{len(rows)} outcomes, {len(summary)} groups -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
