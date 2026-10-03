"""D1's first real-data look: the 2012-2023 kill test (owner rulings 2026-10-03; GAP-P12D-127/140/150).

    python scripts/r1_d1_kill_test.py --candles data/r1_real/dukascopy_candles --macro data/r1_real/macro
    python scripts/r1_d1_kill_test.py ... --universe r21 --changed "<what changed since the last look>"

Mental model (register-first: every refusal happens before any compute):
  * D1 is the registered TREND combination (`core/signals/rules.d1`: EWMAC 16/64, 32/128, 64/256 at equal
    weight, x FDM, capped) on a universe: `fx13` the demo's 13 FX (`targets.universe`), or `r21` R6-4's 21
    non-energy instruments (13 FX, gold, silver, six indices: a NEW family-version, its own look), at
    class-equal weights as the target book sizes them, graded by RSIM: the research book
    (capital $1M so the lot grid never binds, the 20% vol target, the targets' IDM and buffer), the
    SWAP-FREE world (R1-D9, re-ruled 2026-10-02), the declared C8 costs plus the real quoted spread at
    each fill, decisions at 17:00 New York and fills at the 08:00 New York slot (`rsim_real`).
  * Its origin is Carver's published rule SELECTED by the cloud lead's R1 plan (claude-opus-5-5 with web
    search, 2026-09-24). Master §5.6 then certifies a pass only after 2026-09-24, so this look can only
    KILL: it names no cycle and spends no alpha (owner ruling "LLM-selected, kill test").
  * `evaluate` writes the look line (pushed to the GitHub anchor), consumes it, runs RSIM and every
    stage-A arm (the passive benchmark, D1 at 2x cost, the six C9 EWMAC/breakout members, D1's six
    plateau neighbours), and chains the outcome. `verdict.kill_verdict` then judges it: killed at a HAC
    t below -0.5 on the net daily portfolio series (stage C's rule, owner ruling "t < -0.5").
  * Every number is printed and written to data/validation/r1_kill_test/d1.json. A kill drops D1 from
    the forward demo; a survival credits nothing, and the forward record carries on.
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
    a = ap.parse_args(argv)
    cfg = load_config(ROOT / "config")
    t = cfg.system.targets
    universe_id, wide = UNIVERSES[a.universe]
    names = tuple(sorted(wide or t.universe))
    real = build(a.candles, names, load_rate_table(a.macro), START, END, tier="development")
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
                       graded_from=m.days[WARMUP], changed=a.changed, arms=arms(m, real, f))
    out = report(CANONICAL, look, kill_verdict(CANONICAL, look.look_id))
    a.out.mkdir(parents=True, exist_ok=True)
    out["universe"], out["instruments"] = universe_id, list(names)
    (a.out / f"d1_{a.universe}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
