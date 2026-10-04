"""The tournament's weekly report, read from the forward record alone (TOURNAMENT, 2026-10-04).

    python scripts/tournament_report.py --record data/forward/record [--anchor-repo .] [--out report.json] [--md report.md]

Mental model (it computes, it never decides):
  * INTEGRITY first: the chain (no broken or torn line), the anchor when a repo is given, and each
    strategy's revision lines. Any failure is printed at the top and makes that strategy ineligible.
  * Per strategy: forward days, cumulative and annualised net return, Sharpe, HAC t, stage D's E1/E2,
    the completed looks' p-values, the next look, and the Sharpe a look would need to clear the
    capacity-corrected test (what "not yet" means in numbers).
  * The pre-registered rule's verdict (`tournament_rule.evaluate`): "eligible for owner review" or why
    not, with the milestone-D screen and its luck probabilities beside it, labelled NOT EVIDENCE.
  * The forward series' pairwise correlations on shared dates: breadth by mechanism, never a selection.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.backtest.forward_record import ForwardRecord, fold  # noqa: E402
from tests.backtest.tournament_rule import PARAMS, evaluate  # noqa: E402


def integrity(rec: ForwardRecord, anchor_repo: Path | None, remote: str) -> dict:
    scan = rec.scan()
    revisions: dict[str, int] = {}
    for x in scan.lines:
        if x and x["kind"] == "revision":
            revisions[x["strategy"]] = revisions.get(x["strategy"], 0) + 1
    anchored = None if anchor_repo is None else rec.anchored(anchor_repo, remote)
    return {"lines": len(scan.lines), "head": scan.head, "broken": list(scan.broken), "torn": list(scan.torn),
            "anchored": anchored, "revisions": revisions}


def needed_sharpe(alpha_i: float) -> dict[int, float]:
    z = NormalDist().inv_cdf(1.0 - alpha_i / len(PARAMS["looks"]))
    return {n: z / math.sqrt(n / 252.0) for n in PARAMS["looks"]}


def build(rec: ForwardRecord, anchor_repo: Path | None = None, remote: str = "origin") -> dict:
    integ = integrity(rec, anchor_repo, remote)
    st = fold(rec.scan().lines)
    chain_ok = not integ["broken"] and not integ["torn"] and integ["anchored"] is not False
    ok = {s: chain_ok and not integ["revisions"].get(s) for s in st.entries}
    verdicts = {v.strategy: v for v in evaluate(st, ok)}
    rows = {}
    for s, e in st.entries.items():
        r = np.array([v for _, v in st.days[s]])
        v = verdicts[s]
        rows[s] = {"forward_start": e["forward_start"], "days": len(r),
                   "last_day": st.days[s][-1][0].isoformat() if len(r) else None,
                   "cumulative_net": float(r.sum()) if len(r) else 0.0,
                   "annual_net_mean": float(r.mean() * 252) if len(r) else None,
                   "annual_sharpe": v.annual_sharpe, "hac_t": v.hac_t, "e1": v.e1, "e1_voided": v.e1_voided,
                   "e2": v.e2, "e2_max": v.e2_max, "frozen": v.frozen, "killed": v.killed,
                   "looks_done": [{"days": n, "p": p} for n, p in v.p_looks], "p_star": v.p_star,
                   "next_look": next((n for n in PARAMS["looks"] if n > len(r)), None),
                   "sharpe_needed_at_looks": needed_sharpe(float(e["alpha"])),
                   "screen_D_not_evidence": v.screen_d, "luck_one": v.luck_one, "luck_any_of_n": v.luck_any,
                   "eligible_for_owner_review": v.eligible, "why_not": list(v.reasons), "retired": st.retired.get(s)}
    return {"rule": st.rule["params"]["version"] if st.rule else None, "integrity": integ, "strategies": rows,
            "correlations": correlations(st)}


def correlations(st) -> dict[str, float]:
    out, ids = {}, sorted(st.entries)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            da, db = dict(st.days[a]), dict(st.days[b])
            common = sorted(set(da) & set(db))
            x, y = np.array([da[d] for d in common]), np.array([db[d] for d in common])
            if len(common) > 20 and x.std() > 0 and y.std() > 0:
                out[f"{a}~{b}"] = float(np.corrcoef(x, y)[0, 1])
    return out


def markdown(rep: dict) -> str:
    i = rep["integrity"]
    lines = [f"# Forward tournament ({rep['rule']})", "",
             f"Record: {i['lines']} lines, head `{i['head'][:16]}`, broken {len(i['broken'])}, torn {len(i['torn'])}, "
             f"anchored {i['anchored']}, revisions {i['revisions'] or 0}.", "",
             "| Strategy | Days | Net Sharpe | HAC t | E1 | E2 (max) | Next look | Screen D (NOT evidence) | Eligible |",
             "|---|---|---|---|---|---|---|---|---|"]
    f = lambda x: "—" if x is None else f"{x:.2f}"                              # noqa: E731
    for s, r in rep["strategies"].items():
        lines.append(f"| {s} | {r['days']} | {f(r['annual_sharpe'])} | {f(r['hac_t'])} | {f(r['e1'])} | "
                     f"{f(r['e2'])} ({f(r['e2_max'])}) | {r['next_look']} | {r['screen_D_not_evidence']} "
                     f"(luck {f(r['luck_any_of_n'])}) | {r['eligible_for_owner_review']} |")
    lines += ["", "Sharpe a look needs (capacity-corrected): " + "; ".join(
        f"{n} days {v:.1f}" for n, v in next(iter(rep["strategies"].values()))["sharpe_needed_at_looks"].items())
        if rep["strategies"] else "", "", "Never a promotion: eligible means only that the owner may review it."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", type=Path, default=ROOT / "data" / "forward" / "record")
    ap.add_argument("--anchor-repo", type=Path)
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--md", type=Path)
    a = ap.parse_args(argv)
    rep = build(ForwardRecord(a.record), a.anchor_repo, a.remote)
    if a.out:
        a.out.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    if a.md:
        a.md.write_text(markdown(rep), encoding="utf-8")
    print(json.dumps(rep, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
