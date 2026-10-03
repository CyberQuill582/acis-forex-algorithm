"""FXHEDGE's real-data looks: kill tests of currencies into the month-end London 4 pm fix (GAP-P12D-158).

    python scripts/r1_fxhedge_kill_test.py --dry-check        # P&L-blind
    python scripts/r1_fxhedge_kill_test.py --line v1          # v1a and v1c, both registered before either grade
    python scripts/r1_fxhedge_kill_test.py --line exit1559    # v1d: v1a leaving at 15:59, a minute before the fix

Mental model (register-first: every refusal happens before any compute):
  * The book (`fxhedge.py`): on each month's last weekday, each of EUR, GBP, JPY and AUD against the USD holds
    minus its equity market's month-to-date return relative to the five countries' mean (Melvin & Prins 2015,
    §5.1 eq. (3)) over the paper's hour, 15:00 to the 16:00 London fix: v1a always, v1c under the cost gate.
  * DECLARED departures: five of the paper's ten countries (no index on disk for CAD, CHF, NZD, SEK, NOK;
    AUS200 starts 2013-01; JP225/AUS200 quote nothing in their cash sessions 2015-05..10, so JPY/AUD sit
    out); CFD price indices (US500, EU50, UK100, JP225, AUS200) for total-market ones; Dukascopy ticks at
    15:00/16:00 for 5-minute TWAPs and the 2015 5-minute fix window; WM fixes on UK bank holidays too.
  * The benchmark is the control: the same rules a week before each fix day (context only; it carries the
    register's only benchmark name, PASSIVE_LONG, as GOTOBI's looks did: X-1, GAP-P12D-159).
  * Its origin is the literature PROPOSED by this session's lead (claude-opus-5-5, web) on 2026-10-03, so
    master §5.6 certifies a pass only after that date: this look can only KILL (HAC t < -0.5).
  * `--dry-check` reads no strategy return; every look's numbers go to data/validation/r1_kill_test/.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, time, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.event_window import window_prices  # noqa: E402
from tests.backtest.exchange_days import holidays  # noqa: E402
from tests.backtest.fxhedge import (BETA, COUNTRY, LONDON, PAIR, fix_days, legs, positions, reform_split,  # noqa: E402
                                    signal, simulate_fix)
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2012, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
PAIRS = tuple(sorted(p for p, _ in PAIR.values()))
TIMES = {"open": time(8, 0), "entry": time(15, 0), "early": time(15, 59), "fix": time(16, 0)}
CORE = ("fxhedge: on each month's last weekday hold eur, gbp, jpy and aud against the usd at minus 25 x their equity "
        "index's return (first session's close to the last close before the day) less the five countries' mean "
        "(us500, eu50, uk100, jp225, aus200), into the 16:00 london fix, dukascopy ticks, c8 costs at each side's spread")


@dataclass(frozen=True)
class Version:
    formula: str
    entry: str
    beta: float | None = None                   # set: the cost gate (`fxhedge.simulate_fix`)
    exit: str = "fix"                           # "early": a minute before the fix, reachable from a CFD


LINES = {"v1": {"fxhedge_v1a_hour": Version(f"{CORE}; from 15:00 london (the paper's hour)", "entry"),
                "fxhedge_v1c_hour_gated": Version(f"{CORE}; from 15:00 london, a pair-day only if 0.0142 x its "
                                                  "currency's demeaned return beats a c8 round trip at its entry "
                                                  "spread", "entry", BETA)},
         "exit1559": {"fxhedge_v1d_exit1559": Version(f"{CORE}; from 15:00 london, leaving at 15:59:00, a minute "
                                                      "before the fix", "entry", exit="early")}}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-03",
                exposure="web", reference="Melvin & Prins, Equity hedging and exchange rates at the London 4 p.m. "
                "fix, Journal of Financial Markets 22 (2015) 50-72; proposed by the lead 2026-10-03 (GAP-P12D-158)",
                published="2015-01-01")


class TickSource(CandleSource):
    name = "dukascopy-ticks"


def books(index_legs, days, vetted=True):
    """{day: {pair: units}} and the per-day reasons a country sat out."""
    out, why = {}, {}
    for d in days:
        s, w = signal(index_legs, d, vetted)
        why[d] = w
        if s:
            out[d] = positions(s)
    return out, why


def dry_check(index_legs, ticks: Path, costs) -> dict:
    """Also the EX-ANTE size (GAP-P12D-158): the paper's beta on our signals against C8 round trips at each
    day's own 15:00/16:00 spreads; the IR is the paper's R^2 per demeaned currency. No FX return is read."""
    days = fix_days(GRADED_FROM, END)
    book, why = books(index_legs, days)
    sig = {d: signal(index_legs, d)[0] for d in days}
    present = Counter(len(s) for s in sig.values())
    size = {c: [abs(s[c]) for s in sig.values() if c in s] for c in COUNTRY}
    out = {"fix_days": len(days), "months_traded": len(book), "countries_per_month": dict(sorted(present.items())),
           "sat_out": dict(Counter(f"{c}:{r}" for w in why.values() for c, r in w.items())),
           "weekday": dict(Counter(d.strftime("%a") for d in days)),
           "uk_bank_holiday_fix_days": [d.isoformat() for d in days if d in holidays("XLON", d.year)],
           "abs_demeaned_return": {c: {"median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "n": len(v)}
                                   for c, v in size.items() if v},
           "mean_gross_units": float(np.mean([sum(abs(x) for x in b.values()) for b in book.values()])),
           "control_days": len(books(index_legs, [d - timedelta(days=7) for d in days], vetted=False)[0])}
    gross = sum(BETA * sum(v * v for v in x.values()) for x in sig.values() if x)
    spent, cleared = 0.0, {}
    for pair in PAIRS:
        sessions = window_prices(ticks, pair, days, LONDON, TIMES)
        trip = {s.day: sum(costs[pair].per_side_cost(s.prices[k][1]) for k in ("entry", "fix")) / s.prices["entry"][0]
                for s in sessions if s.prices["entry"] and s.prices["fix"]}
        ccy = next(c for c, (p, _) in PAIR.items() if p == pair)
        moves = [(abs(sig[d][ccy]), trip[d]) for d in days if ccy in sig[d] and d in trip]
        spent += sum(a * t for a, t in moves)
        cleared[pair] = {"median_predicted_move_bp": float(np.median([BETA * a for a, _ in moves]) * 1e4),
                         "median_round_trip_bp": float(np.median([t for _, t in moves]) * 1e4),
                         "share_move_beats_cost": float(np.mean([BETA * a > t for a, t in moves]))}
        bp = {k: np.array([s.prices[k][1] / s.prices[k][0] * 1e4 for s in sessions if s.prices[k]]) for k in TIMES}
        out[pair] = {"missing": {k: int(sum(s.prices[k] is None for s in sessions)) for k in TIMES},
                     "spread_bp": {f"{TIMES[k]:%H:%M}": {"median": float(np.median(v)), "p95": float(np.percentile(v, 95))}
                                   for k, v in bp.items() if len(v)}}
    ir = np.sqrt(0.03 / 0.97) * np.mean([np.sqrt(len(x) - 1) for x in sig.values() if x]) * np.sqrt(12)
    out["ex_ante"] = {"per_pair": cleared, "cost_share_of_expected_gross": spent / gross,
                      "annual_ir_gross": float(ir), "annual_ir_net": float(ir * (1 - spent / gross))}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--ticks", type=Path, default=ROOT / "data" / "dukascopy")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: months, signal sizes, prices, no look")
    ap.add_argument("--line", choices=sorted(LINES), help="the registered line to look at (required for a look)")
    a = ap.parse_args(argv)
    index_legs = legs({i: load(a.candles, i, (END.year, END.month)) for i, _ in COUNTRY.values()})
    cfg = load_config(ROOT / "config")
    costs = {p: cost_model(cfg, p) for p in PAIRS}
    if a.dry_check:
        print(json.dumps(dry_check(index_legs, a.ticks, costs), indent=1))
        return 0
    if a.line is None:
        ap.error("a look needs --line")
    versions, reg = LINES[a.line], LookRegister(CANONICAL)
    looks = {}
    for family, v in versions.items():                       # every line first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-FXHEDGE-G5", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": v.formula, "instruments": list(PAIRS)},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=TickSource(), claim=claim,
                                            account="research", instruments=PAIRS, costs=costs,
                                            start=START, graded_from=GRADED_FROM, end=END)
    days = fix_days(GRADED_FROM, END)
    controls = [d - timedelta(days=7) for d in days]
    book, cbook = books(index_legs, days)[0], books(index_legs, controls, vetted=False)[0]
    prices = {p: window_prices(a.ticks, p, days, LONDON, TIMES) for p in PAIRS}
    cprices = {p: window_prices(a.ticks, p, controls, LONDON, TIMES) for p in PAIRS}
    stressed = lambda s: {p: c.__class__(c.commission_per_side, c.slippage_per_side, stress=c.stress * s,  # noqa: E731
                                         spread_floor=c.spread_floor) for p, c in costs.items()}
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    out = {}
    for family, (look, fold) in looks.items():
        entry, beta, leave = versions[family].entry, versions[family].beta, versions[family].exit
        grade_event_look(look, fold, register=reg, cfg=cfg, source=TickSource(), costs=costs, graded_from=GRADED_FROM,
                         run=lambda s, entry=entry, beta=beta, leave=leave: simulate_fix(
                             prices, book, stressed(s), START, GRADED_FROM, END, TIMES, entry, leave, beta=beta),
                         benchmark=lambda entry=entry, leave=leave: simulate_fix(cprices, cbook, costs, START,
                                                                                 GRADED_FROM, END, TIMES, entry, leave).daily,
                         summary=lambda r: {"pair_days_skipped": dict(Counter(x["reason"] for x in r.skipped)),
                                            "pair_days_traded": len(r.events), "reform_split": reform_split(r, GRADED_FROM)})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "pair_days_traded": outcome["pair_days_traded"],
                       "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])), "hac_t": verdict.hac_t,
                       "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "control_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "pair_days_skipped": outcome["pair_days_skipped"], "reform_split": outcome["reform_split"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"fxhedge_{a.line}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
