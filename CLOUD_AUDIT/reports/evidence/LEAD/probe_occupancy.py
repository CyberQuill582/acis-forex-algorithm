"""Lead P3 receipt: how much of each instrument's graded time is one strategy's position?
Reads a C3 driver run dir (summary.json + trades.csv, written by evidence/C3/sim_c3_run.py) and prints,
per instrument and strategy, the union of open-position time inside the graded test windows divided by
the test windows' total calendar time, plus trade count, exit reasons and net.
Usage: python probe_occupancy.py /tmp/c3/runs/<run>"""
import csv, json, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

run = Path(sys.argv[1])
s = json.loads((run / "summary.json").read_text())
wins = [(datetime.fromisoformat(f[2]), datetime.fromisoformat(f[3])) for f in s["folds"]]
total = sum((b - a).total_seconds() for a, b in wins)
iv, n, net, why = defaultdict(list), Counter(), defaultdict(float), defaultdict(Counter)
with open(run / "trades.csv") as fh:
    for t in csv.DictReader(fh):
        k = (t["instrument"], t["strategy"])
        iv[k].append((datetime.fromisoformat(t["entry_ts"]), datetime.fromisoformat(t["exit_ts"])))
        n[k] += 1; net[k] += float(t["net"]); why[k][t["reason"]] += 1
for k in sorted(iv):
    covered = 0.0
    for a, b in wins:
        segs = sorted((max(x, a), min(y, b)) for x, y in iv[k] if min(y, b) > max(x, a))
        end = None
        for x, y in segs:
            if end is None or x > end:
                covered += (y - x).total_seconds(); end = y
            elif y > end:
                covered += (y - end).total_seconds(); end = y
    print(f"{k[0]:8s} {k[1]:15s} n={n[k]:4d} net={net[k]:+8.2f} occupancy={covered / total:6.1%} "
          f"exits={dict(why[k])}")
print(f"passed={s['passed']} n_trades={s['n_trades']} net={s['net']:+.2f} "
      f"label_s={s['seconds_label']:.0f} grade_s={s['seconds_grade']:.0f}")
