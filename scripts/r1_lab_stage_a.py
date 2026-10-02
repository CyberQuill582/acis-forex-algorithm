"""R1.4 lab calibration of stage A for the TREND family's D1 (ACIS-09 C-BT-11 v2 step 3).

Synthetic markets grade MACHINERY (C-BT-12): on the null, how often does D1 pass stage A (the
false-pass rate, which must sit at or below the look's alpha), and on planted trends how often
(the power), and which condition refuses it. Never a real-data verdict.

    python scripts/r1_lab_stage_a.py --seeds 1-1000 --workers 16 --out data/validation/r1_lab/<run>
    (J1, PACE 2026-10-01: add --capital 10000 --vol-target 0.10 --lot 1000 --world swap_free for one
     account-size cell; the venue's minimum lot rounds positions toward zero, GAP-P12D-101)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.schemas import load_config  # noqa: E402
from tests.backtest.lab_market import Effect, LabSpec, generate  # noqa: E402
from tests.backtest.lab_source import lab_names  # noqa: E402
from tests.backtest.rsim import Lots  # noqa: E402
from tests.backtest.rsim_lab import run_member  # noqa: E402
from tests.backtest.stage_a import d1_neighbours, stage_a  # noqa: E402

ALPHA = 0.03                     # cycle 1's alpha, one declared look (k = 1): ACIS-09 D-d
BURN = 300
C9_MEMBERS = ("EWMAC16_64", "EWMAC32_128", "EWMAC64_256", "BREAKOUT40", "BREAKOUT80", "BREAKOUT160", "MOP12")
KINDS = {"null": None, "trend0.5_h40": Effect(trend_sharpe=0.5, trend_halflife=40.0),
         "trend1.0_h40": Effect(trend_sharpe=1.0, trend_halflife=40.0),
         "trend0.5_h160": Effect(trend_sharpe=0.5, trend_halflife=160.0)}
_CFG = None
_SPEC: dict = {}           # the account cell: BookSpec fields (capital, vol_target, world) and --lot


def one_seed(seed: int) -> list[dict]:
    global _CFG
    _CFG = _CFG or load_config(Path(__file__).resolve().parents[1] / "config")
    rows = []
    for kind, eff in KINDS.items():
        path = generate(LabSpec(seed=seed, effect=eff or KINDS["trend1.0_h40"]), null=eff is None)
        spec = {k: v for k, v in _SPEC.items() if k != "lot"}
        if _SPEC.get("lot"):
            spec["lots"] = {n: Lots(_SPEC["lot"], _SPEC["lot"]) for n in lab_names(path.r.shape[1])}
        book = lambda m, **kw: run_member(path, m, _CFG, **{**spec, **kw})          # noqa: E731
        d = lambda m, **kw: book(m, **kw).daily[BURN:]                              # noqa: E731
        d1 = book("D1")
        daily, bench, daily_2x = d1.daily[BURN:], d("PASSIVE_LONG"), d("D1", stress=2.0)
        held = float((d1.units[BURN:] != 0).mean())
        means = {m: float(d(m).mean()) for m in C9_MEMBERS}
        means.update({f"D1:{k}": float(d("D1", d1_params=p).mean()) for k, p in d1_neighbours().items()})
        a = stage_a(daily, bench, daily_2x, means, ALPHA)
        rows.append({"seed": seed, "kind": kind, "passed": a.passed, "bound": a.bound_above_zero, "held": held,
                     "hac_t": a.hac_t, "paired_excess": a.paired_excess, "net_2x": a.net_2x,
                     "refusing": list(a.refusing)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-100")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    ap.add_argument("--capital", type=float, default=None, help="the book's declared capital (default RSIM's)")
    ap.add_argument("--vol-target", type=float, default=None, help="annual vol target (default RSIM's 0.20)")
    ap.add_argument("--lot", type=float, default=0.0, help="the venue's lot step = minimum, in units (0: none)")
    ap.add_argument("--world", default="fair", choices=("fair", "swap_free"))
    args = ap.parse_args()
    _SPEC.update({k: v for k, v in (("capital", args.capital), ("vol_target", args.vol_target)) if v is not None})
    _SPEC.update(world=args.world, lot=args.lot)
    lo, hi = map(int, args.seeds.split("-"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0, rows = time.time(), []
    with Pool(args.workers) as pool, (out / "rows.jsonl").open("w", encoding="utf-8") as f:
        for i, seed_rows in enumerate(pool.imap_unordered(one_seed, range(lo, hi + 1)), 1):
            rows.extend(seed_rows)
            f.writelines(json.dumps(r) + "\n" for r in seed_rows)
            if i % 50 == 0:
                f.flush()
                print(f"{i} seeds, {time.time() - t0:.0f}s", flush=True)
    summary = {}
    for kind in KINDS:
        rs = [r for r in rows if r["kind"] == kind]
        n = len(rs)
        refusals: dict[str, int] = {}
        for r in rs:
            for k in r["refusing"]:
                refusals[k] = refusals.get(k, 0) + 1
        summary[kind] = {"n": n, "pass_rate": sum(r["passed"] for r in rs) / n,
                         "bound_rate": sum(r["bound"] for r in rs) / n,
                         "excess_le_0": sum(r["paired_excess"] <= 0 for r in rs) / n,
                         "net_2x_le_0": sum(r["net_2x"] <= 0 for r in rs) / n,
                         "mean_held_frac": sum(r["held"] for r in rs) / n,
                         "refusals": dict(sorted(refusals.items(), key=lambda kv: -kv[1]))}
    doc = {"seeds": args.seeds, "alpha": ALPHA, "burn": BURN, "spec": _SPEC, "elapsed_s": time.time() - t0,
           "by_kind": summary}
    (out / "summary.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
