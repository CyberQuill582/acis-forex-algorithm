"""HEDGEP's one real-data look: gold after the hedgers' weekly net trading, on RSIM's clock (FACTORY, GAP-P12D-158).

    python scripts/r1_hedgep_kill_test.py --dry-check     # P&L-blind: reports, release dates, turnover, the cost gate
    python scripts/r1_hedgep_kill_test.py --look          # the ONE look, kill-only (HAC t < -0.5)

Mental model (register-first; owner pre-authorisation 2026-10-03: one pre-declared version, one look):
  * Signal `hedgep.py` (Kang, Rouwenhorst & Tang 2020: speculators who trade pay hedgers for immediacy, so a
    market hedgers bought outperforms), the CFTC's COMEX gold report, graded by RSIM on XAU_USD: 17:00 New
    York decisions, 08:00 fills, $1M, 20% vol target, the 10% buffer, swap-free, C8 costs plus the spread.
  * COST GATE, ex ante from the paper's numbers: weekly gross per unit z = slope x sd(Q), the slope 8.9 bp
    per 3.5% of open interest (Table 5) and sd(Q) ~1.25 x the paper's mean |Q| (gold 5.06%, silver 3.75%),
    against the measured turnover times the slot's C8 cost; admitted at 3x. Silver fails (its spread).
  * DECLARED departures: one market's time series for the paper's 26-commodity sort; the CFD's spot for the
    front future; legacy-report commercials as hedgers (the paper's main definition).
  * WINDOW ROLES: the paper's sample ends 2014-11, so 2012-2014 was seen; 2015-2023 is its own segment.
  * EXPECTED CORRELATION, before the look: about 0 with D1-FX13, REBAL v1a and GOTOBI v1a.
  * The origin is the literature SELECTED by FACTORY (claude-opus-5-5, web) on 2026-10-04: kill-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest import hedgep  # noqa: E402
from tests.backtest.factory_looks import END, GRADED_FROM, claim, context, rsim_look  # noqa: E402
from tests.backtest.financing import load_rate_table  # noqa: E402
from tests.backtest.look_claims import Origin  # noqa: E402
from tests.backtest.rsim import BookSpec  # noqa: E402
from tests.backtest.rsim_lab import carver_pct_vol  # noqa: E402
from tests.backtest.rsim_real import build  # noqa: E402

FAMILY, UNIVERSE, NAMES = "hedgep_v1_gold", "R1-HEDGEP-XAU", ("XAU_USD",)
START, SEEN_UNTIL, GATE = date(2012, 1, 2), date(2014, 12, 1), 3.0
SLOPE_PER_Q = 8.9e-4 / 0.035                            # Table 5: 8.9 bp next week per 3.5% of open interest
PAPER_MEAN_ABS_Q = {"XAU_USD": 0.0506, "XAG_USD": 0.0375}
FORMULA = ("hedgep: q = weekly change of comex gold commercial net long / previous open interest; z = q / sd of the "
           "last 52 q; forecast 10 x clip(z, -2, 2) from the cftc report's release day (friday, or the next monday "
           "in a federal-holiday week; shutdown reports never used), flat once the report is over 14 days old; rsim "
           "17:00 new york decisions, swap-free")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                exposure="web", reference="Kang, Rouwenhorst & Tang, A tale of two premiums: the role of hedgers and "
                "speculators in commodity futures markets, Journal of Finance 75(1) (2020) 377-417; selected by "
                "FACTORY 2026-10-04 (GAP-P12D-158)", published="2020-02-01")


def dry_check(m, cfg, reports) -> dict:
    """`m` holds XAU_USD and XAG_USD; the turnover is gold's, the paper's |Q| sizes each market's gross."""
    graded = np.array([GRADED_FROM <= d <= END for d in m.days])
    f = hedgep.panel(m.days, reports)[graded]
    turnover = float(np.nansum(np.abs(np.diff(f))) / 10.0 / (graded.sum() / 5.0))   # units of A a week
    gate = {}
    for i, n in enumerate(m.names):
        cm = cost_model(cfg, n)
        side = float(np.median([cm.per_side_cost(s) / p for s, p in zip(m.spread[graded, i], m.fill[graded, i])]))
        gross = SLOPE_PER_Q * 1.25 * PAPER_MEAN_ABS_Q[n]
        gate[n] = {"weekly_gross_per_unit_z": gross, "median_c8_side": side, "weekly_cost": turnover * side,
                   "gross_over_cost": gross / (turnover * side), "admitted": gross / (turnover * side) >= GATE}
    released = [(d, hedgep.release(d)) for d, *_ in reports if GRADED_FROM <= d <= END]
    return {"reports": len(released), "shutdown_reports": sum(r is None for _, r in released),
            "holiday_delayed": sum(1 for d, r in released if r is not None and r.weekday() != 4),
            "decision_days_flat": int(np.isnan(f).sum()), "turnover_A_per_week": turnover,
            "mean_abs_forecast": float(np.nanmean(np.abs(f))), "cost_gate": gate}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--cot", type=Path, default=ROOT / "data" / "r1_real" / "cot" / "cot_gold.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-check", action="store_true")
    g.add_argument("--look", action="store_true")
    a = ap.parse_args(argv)
    cfg, reports = load_config(ROOT / "config"), hedgep.load(a.cot)
    names = ("XAG_USD", "XAU_USD") if a.dry_check else NAMES
    m = build(a.candles, names, load_rate_table(a.macro), START, END, tier="development").market
    inputs = {"cot_gold.csv": hashlib.sha256(a.cot.read_bytes()).hexdigest()}
    if a.dry_check:
        print(json.dumps(dry_check(m, cfg, reports) | {"inputs": inputs}, indent=1, default=str))
        return 0
    f = hedgep.panel(m.days, reports)[:, None]
    spec = BookSpec(costs={n: cost_model(cfg, n) for n in m.names}, capital=1_000_000.0, vol_target=0.20, idm=1.0,
                    buffer=cfg.system.targets.buffer, world="swap_free")
    look_id = rsim_look(cfg=cfg, cl=claim(FAMILY, FORMULA, m.names, UNIVERSE, ORIGIN, "rsim"), market=m,
                        forecast=f, pct_vol=carver_pct_vol(m), spec=spec)
    out = context(look_id, [SEEN_UNTIL]) | {"family": FAMILY, "inputs": inputs}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "hedgep.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
