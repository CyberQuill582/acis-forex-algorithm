"""R1.3 lab calibration: the TREND family's members through RSIM on the daily lab, many seeds.

Synthetic markets grade MACHINERY, never edge (ACIS-09 C-BT-12): this asks whether each member,
priced by the one C8 model, earns nothing on the null (no bias, a false-detect rate near alpha)
and is found on planted trends of known oracle Sharpe. It never enters a real-data verdict.

    python scripts/r1_lab_rsim.py --seeds 1-1000 --workers 16 --out data/validation/r1_lab/<run>

Each seed draws ONE null and one planted path per effect (common random numbers: the same noise),
runs every member's standalone book, and writes one JSON row per (seed, kind, member) to
rows.jsonl; summary.json aggregates them per (kind, member).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.schemas import load_config  # noqa: E402
from tests.backtest.lab_market import Effect, LabSpec, generate  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_lab import run_member  # noqa: E402

MEMBERS = ("D1", "EWMAC16_64", "EWMAC32_128", "EWMAC64_256", "BREAKOUT40", "BREAKOUT80",
           "BREAKOUT160", "MOP12", "PASSIVE_LONG")
EFFECTS = {"trend0.5_h40": Effect(trend_sharpe=0.5, trend_halflife=40.0),
           "trend1.0_h40": Effect(trend_sharpe=1.0, trend_halflife=40.0),
           "trend0.5_h160": Effect(trend_sharpe=0.5, trend_halflife=160.0),
           "trend1.0_h160": Effect(trend_sharpe=1.0, trend_halflife=160.0)}
BURN = 300                     # weekdays: the slowest member's warm-up
ALPHA = 0.05
_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        _CFG = load_config(Path(__file__).resolve().parents[1] / "config")
    return _CFG


def one_seed(seed: int) -> list[dict]:
    rows = []
    paths = {"null": generate(LabSpec(seed=seed, effect=EFFECTS["trend1.0_h40"]), null=True)}
    for name, eff in EFFECTS.items():
        paths[name] = generate(LabSpec(seed=seed, effect=eff))
    for kind, path in paths.items():
        for member in MEMBERS:
            res = run_member(path, member, _cfg())
            net = res.daily[BURN:]
            gross = (res.gross.sum(1) + res.financing.sum(1))[BURN:] / res.capital
            years = len(net) / 252.0
            rows.append({"seed": seed, "kind": kind, "member": member,
                         "sr_net": annual_sharpe(net), "sr_gross": annual_sharpe(gross),
                         "t_net": annual_sharpe(net) * math.sqrt(years),
                         "cost_per_year": float(res.cost[BURN:].sum() / res.capital / years),
                         "fills": res.fills})
    return rows


def summarise(rows: list[dict]) -> dict:
    crit = NormalDist().inv_cdf(1 - ALPHA)
    out: dict = {}
    for r in rows:
        out.setdefault(r["kind"], {}).setdefault(r["member"], []).append(r)
    summary = {}
    for kind, members in out.items():
        for member, rs in members.items():
            srs = [r["sr_net"] for r in rs]
            n = len(srs)
            mean = sum(srs) / n
            sd = math.sqrt(sum((x - mean) ** 2 for x in srs) / (n - 1)) if n > 1 else float("nan")
            summary.setdefault(kind, {})[member] = {
                "n": n, "sr_net_mean": mean, "sr_net_se": sd / math.sqrt(n), "sr_net_sd": sd,
                "sr_gross_mean": sum(r["sr_gross"] for r in rs) / n,
                "detect_rate": sum(r["t_net"] > crit for r in rs) / n,
                "cost_per_year": sum(r["cost_per_year"] for r in rs) / n}
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-100")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
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
    summary = {"seeds": args.seeds, "burn": BURN, "alpha": ALPHA, "members": MEMBERS,
               "effects": {k: vars(v) for k, v in EFFECTS.items()}, "elapsed_s": time.time() - t0,
               "by_kind": summarise(rows)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary["by_kind"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
