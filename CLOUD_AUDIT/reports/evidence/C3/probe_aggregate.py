"""Aggregate C3 run summaries into one CSV row per (run, strategy) plus one row per run."""
import csv, json, sys
from pathlib import Path
runs = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/c3/runs")
rows = []
for s in sorted(runs.glob("*/summary.json")):
    d = json.loads(s.read_text())
    name = s.parent.name
    base = {"run": name, "kind": d["args"]["kind"], "seed": d["args"]["seed"],
            "off": "+".join(d["args"]["off"]) or "-", "no_veto": d["args"]["no_veto"],
            "episode_hours": d["args"]["episode_hours"], "drift_sigma": d["args"]["drift_sigma"],
            "folds": d["args"]["folds"], "offset": d["args"]["offset_days"],
            "evo_salt": d["args"].get("evo_salt", ""), "scramble": d["args"].get("scramble_invisible", ""),
            "min_label": round(d["seconds_label"] / 60, 1), "min_grade": round(d["seconds_grade"] / 60, 1)}
    rows.append({**base, "strategy": "ALL", "n": d["n_trades"], "net": round(d["net"], 2),
                 "gross": round(d["gross"], 2), "friction": round(d["gross"] - d["net"], 2),
                 "sharpe": round(d["sharpe"], 2) if d["sharpe"] == d["sharpe"] else None,
                 "dur_h": "", "hit": "", "reasons": ""})
    for k, p in sorted(d["per_strategy"].items()):
        rows.append({**base, "strategy": k, "n": p["n"], "net": round(p["net"], 2),
                     "gross": round(p["gross"], 2), "friction": round(p["friction"], 2), "sharpe": "",
                     "dur_h": round(p["dur_h"], 2),
                     "hit": f"{p['with_sign']}/{p['signed_n']}", "reasons": json.dumps(p["reasons"])})
w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
w.writeheader(); w.writerows(rows)
