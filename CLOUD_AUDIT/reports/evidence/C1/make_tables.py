"""Build the markdown result tables for C1_CALIBRATOR.md from sim_out_*.json."""
import json, os, math, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def load(w):
    p = os.path.join(HERE, f"sim_out_{w}.json")
    return json.load(open(p)) if os.path.exists(p) else None

NULLS = [w for w in ("iid", "garch", "factor") if load(w)]
PL = [w for w in ("planted_md05", "planted_md10", "planted_id05") if load(w)]
PROTOS = ["WF_asbuilt_DSR", "WF_asbuilt_DSR+S14", "WF_PSR0_keepbest", "WF_PSR_bonfK", "WF_DSR_repairedK",
          "WF_DSR_NxK_dev", "CPCV_PBO<0.2", "CPCV_PBO<0.5&z", "SPA_keepbest", "SPA_union", "StepM_keepbest",
          "StepM_union", "HLZ_bonf_keepbest", "HLZ_bonf_NK", "HLZ_BHY_NK", "MinBTL_gate_NK", "Holdout_keepbest",
          "Holdout_once", "STACK_WFbonfK+Holdout"]
CELLS = ["N1_K1", "N60_K1", "N60_K20", "N1000_K1", "N1000_K20"]

def rate(w, c, p):
    d = load(w)
    a = d["agg"].get(c, {}).get(p)
    return None if a is None else (a["rate"], a["ci95"])

def fmt(x):
    return "–" if x is None else f"{100 * x[0]:.1f}"

out = []
out.append(f"FPR % = worst null (then {'/'.join(NULLS)}); R=300 per null; Wilson 95% CI at 5% is about 2.9-8.5%, at 0% is 0-1.3%, at 45% is +/-5.6 pp.")
out.append("")
out.append("| protocol | " + " | ".join(CELLS) + " |")
out.append("|---|" + "---|" * len(CELLS))
for p in PROTOS:
    row = []
    for c in CELLS:
        vals = [rate(w, c, p) for w in NULLS]
        vals = [v for v in vals if v is not None]
        if not vals:
            row.append("–"); continue
        mx = max(vals, key=lambda v: v[0])
        row.append(f"**{100 * mx[0]:.1f}** ({'/'.join(f'{100*v[0]:.1f}' for v in vals)})")
    out.append(f"| {p} | " + " | ".join(row) + " |")
out.append("")
for w in PL:
    d = load(w)
    st = d["agg"].get("stats", {})
    truth = st.get("N1_wf_oos_annual_sr", {}).get("mean", float("nan"))
    out.append(f"**Power, {w}** (fixed best config's measured OOS annual Sharpe {truth:.2f}; R={d['R']}; Wilson 95% CI half-width <= 5.7 pp)")
    out.append("")
    out.append("| protocol | " + " | ".join(CELLS) + " |")
    out.append("|---|" + "---|" * len(CELLS))
    for p in PROTOS:
        out.append(f"| {p} | " + " | ".join(fmt(rate(w, c, p)) for c in CELLS) + " |")
    out.append("")
    keys = [k for k in st if any(s in k for s in ("wf_oos", "holdout_annual", "dev_best", "sr0"))]
    out.append("Selection diagnostics (mean over replications): " + "; ".join(f"{k} {st[k]['mean']:.2f}" for k in keys))
    out.append("")
open(os.path.join(HERE, "tables.md"), "w").write("\n".join(out))
print("\n".join(out))
