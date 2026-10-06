"""RATES' real-data looks: kill tests of trend on the Treasury par curve (GAP-P12D-161).

    python scripts/r1_rates_kill_test.py --dry-check     # P&L-blind
    python scripts/r1_rates_kill_test.py --line v1       # v1a and v1b, both registered before either grade

Mental model (register-first: every refusal happens before any compute):
  * The books (`ust_trend.py`): v1a runs the registered TREND rule (D1: Carver's three EWMACs) on each of the
    2-, 5-, 10- and 30-year par yields; v1b runs MOP's 12-month sign on them. Both trade the yield per unit
    DV01 at Carver's vol sizing, class-equal over the four tenors, at the micro yield futures' cost (one tick
    plus fees a round trip, AUCTION's MICRO map). Owner ruling 2026-10-06: pre-register and run, kill-only.
  * DECLARED departures: constant-maturity par yields for the micro contracts' on-the-run benchmarks (no roll,
    no rolldown, no carry); the Treasury's daily close for the futures' settlement; one fill a day at the next
    close; the legs are research-only instruments declared HERE (never in config/instruments.yaml).
  * WINDOW: graded 2012-02-01..2023-12-29, warm-up from the file's 2011-01-03. The 2024-25 holdout is not read;
    a stage C needs its own ruling. The selector (agent A) knew 2022-23 was a strong bond-trend run: that is why
    the look is kill-only (§5.6) and why the segments 2012-17 / 2018-23 are reported beside the total.
  * The benchmark is the passive long-duration control (short every yield at the same sizing).
  * `--dry-check` reads no strategy return; every look's numbers go to data/validation/r1_kill_test/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import InstrumentCosts, InstrumentSpec, load_config  # noqa: E402
from core.optimizer.costs import CostModel  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.opex import segments  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.ust_auction import book  # noqa: E402
from tests.backtest.ust_trend import FORECASTS, load_yields, positions, yield_changes  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2011, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
HALF = date(2018, 1, 1)
MICRO = InstrumentCosts(commission_per_side=0.00062, slippage_per_side=0.0005)   # % of yield: ~$0.62 fees, 1/2 tick
TENOR_LEG = {"2y": "UST2Y", "5y": "UST5Y", "10y": "UST10Y", "30y": "UST30Y"}
LEGS = {n: InstrumentSpec(enabled=False, asset_class="future", quote_ccy="USD", tick_size=0.001, tick_value=1.0,
                          lot_step=1.0, min_lot=1.0, margin_model="exchange_future", swap_convention="none",
                          max_plausible_spread=0.005, calendar="cme_metals", roll_window_days=1, costs=MICRO)
        for n in TENOR_LEG.values()}                                      # research-only, disabled
YIELD_SIDE = (0.001 / 2 + 0.00062 + 0.0005) / 100                         # one side, per unit DV01 (AUCTION's)


@dataclass(frozen=True)
class Version:
    formula: str
    forecast: str


LINES = {"v1": {
    "rates_v1a_d1_curve": Version("rates: the registered TREND rule (D1, Carver's EWMAC 16/64, 32/128, 64/256, FDM, "
                                  "cap 20) on each of the 2/5/10/30-year par yields, long the yield on a positive "
                                  "forecast; position = forecast/10 x tau / 35-day mixed vol of the yield change, "
                                  "class-equal over the four tenors; 1 tick plus fees a round trip", "d1"),
    "rates_v1b_mop_curve": Version("rates: MOP 2012's 12-month sign of each of the 2/5/10/30-year par yields, held to "
                                   "the next month end; the same sizing, weights and costs as v1a", "mop")}}
ORIGIN = Origin("literature", model_id="claude-fable-5-1", model_cutoff="2026-10-05", proposed="2026-10-05",
                exposure="web", reference="Brooks, Katz & Lustig, Post-FOMC Announcement Drift in U.S. Bond Markets, "
                "NBER w25127 (2018); bond TSMOM per Baltas & Kosowski; rules Carver (D1) and Moskowitz, Ooi & "
                "Pedersen (2012); selected by the 2026-10-05 research agent A (model_cutoff: the vendor date is "
                "unknown to the lead, so the proposal date is declared as its upper bound)", published="2018-10-01")


class UstSource(CandleSource):
    name = "treasury-par-yields"


def research_cfg(cfg):
    specs = {**cfg.instruments.instruments, **LEGS}
    return cfg.model_copy(update={"instruments": cfg.instruments.model_copy(update={"instruments": specs})})


def run(days, curve, pos, stress: float = 1.0):
    parts = [book(days, pos[t], yield_changes(curve[t]), YIELD_SIDE * stress, START, GRADED_FROM, END) for t in curve]
    return parts[0].__class__(parts[0].days, sum(p.daily for p in parts), (), ())


def dry_check(days, curve) -> dict:
    graded = np.array([GRADED_FROM <= d <= END for d in days])
    out = {"curve_days": int(graded.sum()), "first": days[0].isoformat(), "last": days[-1].isoformat()}
    for family, v in LINES["v1"].items():
        pos = positions(days, curve, FORECASTS[v.forecast])
        out[family] = {"days_flat_all_tenors": int(sum(all(pos[t][k] == 0 for t in pos) for k in np.flatnonzero(graded))),
                       "turnover_over_mean_abs": {t: float(np.abs(np.diff(pos[t][graded])).sum()
                                                           / max(np.abs(pos[t][graded]).mean(), 1e-12) / 12)
                                                  for t in pos},
                       "share_long_yield": {t: float((pos[t][graded] > 0).mean()) for t in pos}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--treasury", type=Path, default=ROOT / "data" / "r1_real" / "treasury")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: days flat, turnover, sign shares, no look")
    ap.add_argument("--line", choices=sorted(LINES), help="the registered line to look at (required for a look)")
    a = ap.parse_args(argv)
    days, curve = load_yields(a.treasury / "raw")
    keep = [k for k, d in enumerate(days) if START <= d <= END]           # the holdout is never loaded into a book
    days, curve = [days[k] for k in keep], {t: y[keep] for t, y in curve.items()}
    if a.dry_check:
        print(json.dumps(dry_check(days, curve), indent=1))
        return 0
    if a.line is None:
        ap.error("a look needs --line")
    cfg, reg = research_cfg(load_config(ROOT / "config")), LookRegister(CANONICAL)
    inputs = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((a.treasury / "raw").glob("*.csv"))
              if int(f.stem) <= END.year}
    instruments = tuple(sorted(LEGS))
    costs = {n: CostModel(MICRO.commission_per_side, MICRO.slippage_per_side) for n in instruments}
    looks = {}
    for family, v in LINES[a.line].items():                    # every line first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-RATES-UST", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": v.formula, "instruments": list(instruments)},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=UstSource(), claim=claim, account="research",
                                            instruments=instruments, costs=costs, start=START,
                                            graded_from=GRADED_FROM, end=END)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    control = positions(days, curve, None, passive=True)
    out = {}
    for family, (look, fold) in looks.items():
        pos = positions(days, curve, FORECASTS[LINES[a.line][family].forecast])
        grade_event_look(look, fold, register=reg, cfg=cfg, source=UstSource(), costs=costs, graded_from=GRADED_FROM,
                         run=lambda s, pos=pos: run(days, curve, pos, s),
                         benchmark=lambda: run(days, curve, control).daily,
                         summary=lambda r: {"inputs": inputs, "segments": segments(r, [HALF], GRADED_FROM)})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])),
                       "hac_t": verdict.hac_t, "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "passive_long_duration_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "segments": outcome["segments"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"rates_{a.line}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
