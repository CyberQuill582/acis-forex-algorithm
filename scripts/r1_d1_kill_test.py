"""D1's first real-data look: the 2012-2023 kill test (owner rulings 2026-10-03; GAP-P12D-127/140/150).

    python scripts/r1_d1_kill_test.py --candles data/r1_real/dukascopy_candles --macro data/r1_real/macro
    python scripts/r1_d1_kill_test.py ... --universe r21 --changed "<what changed since the last look>"
    python scripts/r1_d1_kill_test.py ... --stage-c       # fx13 on the sealed 2024-25 holdout, once (GAP-P12D-159)

Mental model (register-first: every refusal happens before any compute):
  * D1 is the registered TREND combination (`core/signals/rules.d1`: EWMAC 16/64, 32/128, 64/256 at equal
    weight, x FDM, capped) on `fx13` (the demo's 13 FX) or `r21` (R6-4's 21 non-energy instruments, a NEW
    family-version), class-equal weights, graded by RSIM: the research book ($1M so the lot grid never
    binds, 20% vol target, the targets' IDM and buffer), SWAP-FREE (R1-D9), the declared C8 costs plus
    each fill's quoted spread, decisions 17:00 New York, fills at the 08:00 New York slot (`rsim_real`).
  * Its origin is Carver's rule SELECTED by the cloud lead's R1 plan (claude-opus-5-5, web, 2026-09-24):
    §5.6 certifies only after that, so this look can only KILL, names no cycle, spends no alpha.
  * `evaluate` writes the look line (pushed to the GitHub anchor), consumes it, runs RSIM and every
    stage-A arm (passive benchmark, 2x cost, the six C9 members, six plateau neighbours) and chains the
    outcome; `verdict.kill_verdict` kills at a HAC t below -0.5 on the net daily portfolio series.
  * Every number goes to data/validation/r1_kill_test/d1_<universe>[_stage_c].json. A kill drops D1 from
    the forward demo; a survival credits nothing. `--stage-c`: 2024-25 graded once, warm-up from 2022.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from core.signals import rules  # noqa: E402
from core.signals.forecast import WARMUP  # noqa: E402
from tests.backtest.evaluate import StageArms, evaluate  # noqa: E402
from tests.backtest.financing import load_rate_table  # noqa: E402
from tests.backtest.hac import hac_t  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rsim import BookSpec, annual_sharpe, panel  # noqa: E402
from tests.backtest.rsim_lab import carver_pct_vol  # noqa: E402
from tests.backtest.rsim_real import CandleSource, build, masked  # noqa: E402
from tests.backtest.stage_a import d1_neighbours  # noqa: E402
from tests.backtest.universe import EXPLORED, BY_NAME  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402
from core.runtime.target_decision import class_equal_weights  # noqa: E402

FAMILY = "trend_d1_v1"
FORMULA = "d1: equal-weight ewmac 16/64, 32/128, 64/256 (carver scalars) x fdm, capped at 20"
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-09-24",
                exposure="web", reference="Carver, Systematic Trading (Harriman House, 2015); pysystemtrade "
                "a62269d2 `ewmac`; selected by the cloud lead's PLAN_R1", published="2015-09-01")
START, END = date(2012, 1, 2), date(2023, 12, 29)
HOLDOUT = (date(2022, 1, 3), date(2024, 1, 2), date(2025, 12, 31))   # market from (warm-up), graded from, to
STAGE_C = "stage C (ACIS-09 C-BT-11 v2 step 6): the same fx13 d1, graded once on the sealed 2024-25 holdout"
UNIVERSES = {"fx13": ("R6-4-FX13", None), "r21": ("R6-4-21", tuple(n for n in EXPLORED if BY_NAME[n].asset_class != "energy"))}


def arms(m, real, vol_forecast) -> StageArms:
    f = vol_forecast
    kill = {f"EWMAC{a}_{b}": f(lambda p, a=a, b=b: rules.ewmac(p, a, b)) for a, b in rules.EWMAC_SCALARS}
    kill |= {f"BREAKOUT{n}": f(lambda p, n=n: rules.breakout(p, n)) for n in rules.BREAKOUT_SCALARS}
    kill |= {f"D1:{k}": f(lambda p, kw=kw: rules.d1(p, **kw)) for k, kw in d1_neighbours().items()}
    return StageArms(benchmark="PASSIVE_LONG", benchmark_forecast=f(lambda p: [10.0] * len(p)), kill_only=kill)


def report(root: Path, look, verdict) -> dict:
    outcome = LookRegister(root).outcome(look.look_id)
    vec = lambda h: np.asarray(load_vector(root, h)[1])                       # noqa: E731
    daily, sa = vec(outcome["daily_vector"]), outcome["stage_a"]
    out = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"], "cycle": look.cycle,
           "graded": [look.start, look.end], "graded_days": outcome["graded_days"], "fills": outcome["fills"],
           "world": outcome["world"], "annual_sharpe": annual_sharpe(daily), "hac_t": verdict.hac_t,
           "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
           "paired_excess_daily": float(np.mean(daily - vec(sa["benchmark_vector"]))),
           "benchmark_annual_sharpe": annual_sharpe(vec(sa["benchmark_vector"])),
           "cost2x_annual_sharpe": annual_sharpe(vec(sa["cost2x_vector"])),
           "kill_only_arms": {k: {"annual_sharpe": annual_sharpe(vec(h)), "hac_t": hac_t(vec(h))}
                              for k, h in sa["kill_only_vectors"].items()}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, required=True)
    ap.add_argument("--macro", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--universe", choices=sorted(UNIVERSES), default="fx13")
    ap.add_argument("--changed", default="", help="what changed since the family's last look (the register asks)")
    ap.add_argument("--stage-c", action="store_true", help="fx13 on the sealed 2024-25 holdout, once")
    a = ap.parse_args(argv)
    if a.stage_c and a.universe != "fx13":
        ap.error("stage C is ruled for fx13 only")
    cfg = load_config(ROOT / "config")
    if a.stage_c and any(x and x.get("family") == FAMILY and x.get("tier") == 3
                         for x in LookRegister(CANONICAL).scan().lines):
        raise SystemExit("stage C grades the 2024-25 holdout once: D1 already looked at it")
    start, end, tier = (HOLDOUT[0], HOLDOUT[2], "holdout") if a.stage_c else (START, END, "development")
    t = cfg.system.targets
    universe_id, wide = UNIVERSES[a.universe]
    names = tuple(sorted(wide or t.universe))
    real = build(a.candles, names, load_rate_table(a.macro), start, end, tier=tier)
    m = real.market
    f = lambda rule: masked(panel(m, rule), real)                               # noqa: E731
    weights = class_equal_weights({n: cfg.instruments.instruments[n].asset_class for n in names})
    spec = BookSpec(costs={n: cost_model(cfg, n) for n in names}, capital=1_000_000.0, vol_target=0.20,
                    idm=t.idm, buffer=t.buffer, world="swap_free", weights=weights)
    claim = Claim(family=FAMILY, variant="fixed", universe_id=universe_id, origin=ORIGIN, simulator="rsim",
                  declared_space={"grid": {}, "formula": FORMULA, "instruments": list(names)},
                  recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
    look, _ = evaluate(register=LookRegister(CANONICAL), cfg=cfg, source=CandleSource(), family=FAMILY, claim=claim,
                       account="research", market=m, forecast=f(rules.d1), pct_vol=carver_pct_vol(m), spec=spec,
                       graded_from=next(d for d in m.days if d >= HOLDOUT[1]) if a.stage_c else m.days[WARMUP],
                       changed=STAGE_C if a.stage_c else a.changed, arms=arms(m, real, f))
    out = report(CANONICAL, look, kill_verdict(CANONICAL, look.look_id))
    a.out.mkdir(parents=True, exist_ok=True)
    out["universe"], out["instruments"] = universe_id, list(names)
    (a.out / f"d1_{a.universe}{'_stage_c' if a.stage_c else ''}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
