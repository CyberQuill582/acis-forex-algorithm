"""AUCTION's real-data looks: kill tests of the Treasury auction cycle on the par curve (GAP-P12D-158).

    python scripts/r1_auction_kill_test.py --dry-check     # P&L-blind
    python scripts/r1_auction_kill_test.py --line v1       # v1a and v1b, both registered before either grade

Mental model (register-first: every refusal happens before any compute):
  * The books (`ust_auction.py`): v1a is the paper's (Lou, Yan & Zhang 2013, Table V, t = 10): short the 2-year
    against duration-matched 6-month + 10-year wings for the 10 closes into each 2-year auction, reversed for
    the 10 after, at the paper's 1.46 bp round trip. v1b is the micro yield futures' form: long the auctioned
    tenor's yield for the 5 closes into each 2-, 5- and 10-year auction (reopenings count) and short it for the
    5 after, at about 0.32 bp of yield a round trip (1 tick plus fees).
  * DECLARED departures: the Treasury's constant-maturity par yields for CRSP on-the-run notes (no rolldown,
    no specific-issue cheapness); auctions after 2008 at today's sizes and frequencies; the legs are
    research-only instruments declared HERE (never in config/instruments.yaml: the engine's rulebook is
    untouched before the cutover).
  * WINDOW ROLES: the selecting evidence is the paper (1980-2008) and a desk note that supply shocks still move
    yields; no post-2012 cycle magnitude was read, so 2012-2023 is unseen. Segments 2012-17 / 2018-23 are context.
  * The benchmark is a control: the same windows 10 closes earlier. Kill-only: the lead PROPOSED it on 2026-10-03.
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
from tests.backtest.ust_auction import auctions, book, butterfly, load_curve, windows  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2012, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
CONTROL_SHIFT, HALF = 10, date(2018, 1, 1)
MICRO = InstrumentCosts(commission_per_side=0.00062, slippage_per_side=0.0005)   # % of yield: ~$0.62 fees, 1/2 tick
LEGS = {n: InstrumentSpec(enabled=False, asset_class="future", quote_ccy="USD", tick_size=0.001, tick_value=1.0,
                          lot_step=1.0, min_lot=1.0, margin_model="exchange_future", swap_convention="none",
                          max_plausible_spread=0.005, calendar="cme_metals", roll_window_days=1, costs=MICRO)
        for n in ("UST6M", "UST2Y", "UST5Y", "UST10Y")}                  # CME's calendar; research-only, disabled
YIELD_SIDE = (0.001 / 2 + 0.00062 + 0.0005) / 100                         # one side, per unit DV01, in the book's units


@dataclass(frozen=True)
class Version:
    formula: str
    tenors: tuple[str, ...]
    t: int
    per_side: float
    instruments: tuple[str, ...]


LINES = {"v1": {
    "auction_v1a_butterfly": Version("auction: short the 2-year par note against duration-matched 6-month + 10-year "
                                     "wings for the 10 closes into each 2-year note auction, reversed for the 10 "
                                     "after; par-curve returns with carry; 0.73 bp a side (the paper's 1.46 bp round "
                                     "trip)", ("2y",), 10, 0.73e-4, ("UST10Y", "UST2Y", "UST6M")),
    "auction_v1b_outright": Version("auction: long the auctioned tenor's par yield per unit dv01 for the 5 closes into "
                                    "each fixed-rate nominal 2-, 5- and 10-year note auction (reopenings count), short "
                                    "it for the 5 after; no carry; 1 tick plus fees a round trip (micro yield futures)",
                                    ("2y", "5y", "10y"), 5, YIELD_SIDE, ("UST10Y", "UST2Y", "UST5Y"))}}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-03",
                exposure="web", reference="Lou, Yan & Zhang, Anticipated and Repeated Shocks in Liquid Markets, Review "
                "of Financial Studies 26(8) (2013) 1891-1912 (FMG DP684); proposed by the lead 2026-10-03 "
                "(GAP-P12D-158)", published="2013-08-01")


class UstSource(CandleSource):
    name = "treasury-par-yields"


def research_cfg(cfg):
    specs = {**cfg.instruments.instruments, **LEGS}
    return cfg.model_copy(update={"instruments": cfg.instruments.model_copy(update={"instruments": specs})})


def positions(days, curve, events, v: Version, shift: int = 0):
    """{tenor: position} for each auctioned tenor, the events moved `shift` closes earlier for the control."""
    at = {d: k for k, d in enumerate(days)}
    out, skipped = {}, []
    for tenor in v.tenors:
        moved = [days[at[e] - shift] for e in events[tenor] if e in at and at[e] - shift >= 0]
        out[tenor], s = windows(days, moved, v.t)
        skipped += [dict(x, tenor=tenor) for x in s] + [{"auction": e.isoformat(), "tenor": tenor,
                                                         "reason": "no curve row"} for e in events[tenor] if e not in at]
    return out, skipped


def run(days, curve, pos, v: Version, stress: float = 1.0):
    if v.tenors == ("2y",):
        return book(days, pos["2y"], butterfly(days, curve), v.per_side * stress, START, GRADED_FROM, END)
    parts = [book(days, pos[t], np.r_[0.0, np.diff(curve[t])] / 100, v.per_side * stress, START, GRADED_FROM, END)
             for t in v.tenors]
    return parts[0].__class__(parts[0].days, sum(p.daily for p in parts), (), ())


def dry_check(days, curve, events) -> dict:
    out = {"curve_days": len([d for d in days if GRADED_FROM <= d <= END])}
    for family, v in LINES["v1"].items():
        pos, skipped = positions(days, curve, events, v)
        graded = np.array([GRADED_FROM <= d <= END for d in days])
        out[family] = {"auctions": {t: sum(GRADED_FROM <= e <= END for e in events[t]) for t in v.tenors},
                       "skipped": len(skipped),
                       "days_in_market": {t: int((pos[t][graded] != 0).sum()) for t in v.tenors},
                       "days_overlapping": {t: int((np.abs(pos[t][graded]) > 1).sum()) for t in v.tenors},
                       "turnover_per_year": float(sum(np.abs(np.diff(pos[t][graded])).sum() for t in v.tenors) / 12),
                       "cost_bp_per_year": float(sum(np.abs(np.diff(pos[t][graded])).sum() for t in v.tenors)
                                                 * v.per_side * 1e4 / 12)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--treasury", type=Path, default=ROOT / "data" / "r1_real" / "treasury")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: auctions, days held, turnover, no look")
    ap.add_argument("--line", choices=sorted(LINES), help="the registered line to look at (required for a look)")
    a = ap.parse_args(argv)
    days, curve = load_curve(a.treasury / "raw")
    events = auctions(a.treasury / "auctions.csv", ("2y", "5y", "10y"))
    if a.dry_check:
        print(json.dumps(dry_check(days, curve, events), indent=1))
        return 0
    if a.line is None:
        ap.error("a look needs --line")
    cfg, reg = research_cfg(load_config(ROOT / "config")), LookRegister(CANONICAL)
    inputs = {"auctions.csv": hashlib.sha256((a.treasury / "auctions.csv").read_bytes()).hexdigest()}
    looks = {}
    for family, v in LINES[a.line].items():                    # every line first: no grade between them
        costs = {n: CostModel(LEGS[n].costs.commission_per_side, LEGS[n].costs.slippage_per_side) for n in v.instruments}
        claim = Claim(family=family, variant="fixed", universe_id="R1-AUCTION-UST", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": v.formula, "instruments": list(v.instruments)},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = (register_event_look(register=reg, cfg=cfg, source=UstSource(), claim=claim, account="research",
                                             instruments=v.instruments, costs=costs, start=START,
                                             graded_from=GRADED_FROM, end=END), costs)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    out = {}
    for family, ((look, fold), costs) in looks.items():
        v = LINES[a.line][family]
        pos, skipped = positions(days, curve, events, v)
        control, _ = positions(days, curve, events, v, CONTROL_SHIFT)
        grade_event_look(look, fold, register=reg, cfg=cfg, source=UstSource(), costs=costs, graded_from=GRADED_FROM,
                         run=lambda s, pos=pos, v=v: run(days, curve, pos, v, s),
                         benchmark=lambda control=control, v=v: run(days, curve, control, v).daily,
                         summary=lambda r, skipped=skipped: {"auctions_skipped": len(skipped), "inputs": inputs,
                                                             "segments": segments(r, [HALF], GRADED_FROM)})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])),
                       "hac_t": verdict.hac_t, "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "control_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "auctions_skipped": outcome["auctions_skipped"], "segments": outcome["segments"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"auction_{a.line}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
