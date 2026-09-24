"""Per-run trade forensics: time TSMOM occupies each instrument's single position slot, and
per-strategy P&L split by alignment with the planted episode sign at entry."""
import csv, json, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
for run in sys.argv[1:]:
    run = Path(run)
    s = json.loads((run / "summary.json").read_text())
    f0, f1 = s["folds"][0], s["folds"][-1]
    graded_h = sum((datetime.fromisoformat(f[3]) - datetime.fromisoformat(f[2])).total_seconds() / 3600
                   for f in s["folds"])
    occ = defaultdict(float); al = defaultdict(lambda: [0, 0.0, 0, 0.0])
    for t in csv.DictReader(open(run / "trades.csv")):
        occ[(t["strategy"], t["instrument"])] += float(t["dur_h"])
        k = t["strategy"]; sgn = int(t["sign_at_entry"]); d = int(t["dir"])
        if sgn == d: al[k][0] += 1; al[k][1] += float(t["net"])
        elif sgn: al[k][2] += 1; al[k][3] += float(t["net"])
    print(f"== {run.name}: graded hours per instrument ~{graded_h:.0f} (incl. weekends)")
    for (st, inst), h in sorted(occ.items()):
        print(f"   occupancy {st:16s} {inst}: {h:8.1f} h = {h / graded_h:.0%}")
    for k, (na, pa, nm, pm) in sorted(al.items()):
        print(f"   {k:16s} aligned n={na} net={pa:.2f} | against n={nm} net={pm:.2f}")
    ec = s.get("event_counts") or {}
    for k, v in sorted(ec.items()):
        print(f"   event {k}: {v}")
