"""GOTOBI's real-data looks: the 2012-2023 kill tests of USD/JPY into the 09:55 Tokyo fix (GAP-P12D-158).

    python scripts/r1_gotobi_kill_test.py --dry-check   # P&L-blind
    python scripts/r1_gotobi_kill_test.py --line v1        # v1a and v1b (looks 000015/000016, 2026-10-03)
    python scripts/r1_gotobi_kill_test.py --line exit0954  # v1c: v1a leaving at 09:54 (owner ruling 2026-10-03)

Mental model (register-first: every refusal happens before any compute):
  * The book (`event_window.py`): on each gotobi bank day (`jp_days.py`), Tuesday to Friday JST, hold
    USD/JPY long from ENTRY to the 09:55 fix (Bessho et al. 2023 §3.1, H1); a version may add their
    H2, short from 09:55 to 12:00 only if the mid rose from ENTRY to 09:00. Prices from the Dukascopy
    ticks, each side paying THE C8 model at its tick's spread; flat outside the window.
  * LINES: `v1` registers v1a and v1b together (no grade between them); `exit0954` registers v1c alone,
    v1a with the exit at 09:54:00, the minute a live order would fire before the fix.
  * The benchmark is the paper's control: the same legs on every non-gotobi bank day, Tuesday-Friday.
  * Its origin is the literature SELECTED by the 2026-10-01 research agent (claude-opus-5-5, web), so
    master §5.6 certifies a pass only after that date: this look can only KILL (HAC t < -0.5).
  * `--dry-check` reads no strategy return: day counts per rule, prices found, skip reasons, and the
    spreads in basis points at each wall time.
  * Every number goes to data/validation/r1_kill_test/gotobi_<line>.json (v1's first run wrote gotobi.json).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, time, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.event_window import Leg, simulate_window, window_prices  # noqa: E402
from tests.backtest.jp_days import gotobi_days, is_bank_day, load_holidays  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2012, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
ZONE, NAME, WEEKDAYS = "Asia/Tokyo", "USD_JPY", (1, 2, 3, 4)          # Tuesday-Friday (Bessho §2)
TIMES = {"entry": time(3, 0), "nine": time(9, 0), "fix": time(9, 55), "noon": time(12, 0)}
DRY_TIMES = {**TIMES, "seven": time(7, 0), "eight": time(8, 0)}
H1, H2 = Leg("entry", "fix", 1.0), Leg("fix", "noon", -1.0, gate=("entry", "nine"))
CORE = ("gotobi: hold usd/jpy long from 03:00 to the 09:55 jst fix on gotobi bank days (5, 10, 15, 20, 25, 30 or "
        "the month's last day if shorter, moved to the previous japanese bank day), tuesday-friday, dukascopy "
        "ticks, c8 costs at each side's spread")
LINES = {"v1": {"gotobi_v1a_h1_usdjpy": (CORE, (H1,), TIMES),
                "gotobi_v1b_h1h2_usdjpy": (f"{CORE}; plus short 09:55 to 12:00 when the mid rose 03:00 to 09:00",
                                           (H1, H2), TIMES)},
         "exit0954": {"gotobi_v1c_h1_exit0954_usdjpy": (CORE.replace("to the 09:55 jst fix", "to 09:54 jst, a minute "
                                                                     "before the 09:55 fix"), (H1,),
                                                        {**TIMES, "fix": time(9, 54)})}}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-01",
                exposure="web", reference="Bessho, Sugimoto & Suzuki, Forex Trading Strategy That Might Be Executed "
                "Due to the Popularity of Gotobi Anomaly, arXiv 2301.13204 (2023); Ito & Yamada, Puzzles in the Tokyo "
                "fixing in the forex market, JIE 109 (2017); selected by the 2026-10-01 research agent EDGE (S6)",
                published="2023-01-29")


class TickSource(CandleSource):
    name = "dukascopy-ticks"


def days_of(holidays: frozenset[date], last_day: str) -> tuple[list[date], list[date]]:
    """(gotobi days, control days): Tuesday-Friday JST bank days in START..END."""
    gotobi = [d for d in gotobi_days(START, END, holidays, last_day=last_day) if d.weekday() in WEEKDAYS]
    g, control, d = set(gotobi), [], START
    while d <= END:
        if d.weekday() in WEEKDAYS and is_bank_day(d, holidays) and d not in g:
            control.append(d)
        d += timedelta(days=1)
    return gotobi, control


def dry_check(ticks: Path, holidays: frozenset[date]) -> dict:
    out = {}
    for rule in ("30", "month_end"):
        gotobi, control = days_of(holidays, rule)
        mondays = [d for d in gotobi_days(START, END, holidays, last_day=rule) if d.weekday() == 0]
        out[rule] = {"gotobi_tue_fri": len(gotobi), "per_year": dict(Counter(d.year for d in gotobi)),
                     "gotobi_mondays_excluded": len(mondays), "control_days": len(control)}
    gotobi, _ = days_of(holidays, "30")
    sessions = [s for s in window_prices(ticks, NAME, gotobi, ZONE, DRY_TIMES) if GRADED_FROM <= s.day <= END]
    missing = Counter(next((k for k in TIMES if s.prices[k] is None), "priced") for s in sessions)
    bp = {k: np.array([s.prices[k][1] / s.prices[k][0] * 1e4 for s in sessions if s.prices[k]]) for k in DRY_TIMES}
    out["prices_30_rule"] = {"days": len(sessions), "first_missing": dict(missing),
                             "spread_bp": {f"{DRY_TIMES[k]:%H:%M}": {"median": float(np.median(v)),
                                                                     "p95": float(np.percentile(v, 95)), "n": len(v)}
                                           for k, v in bp.items()}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ticks", type=Path, default=ROOT / "data" / "dukascopy")
    ap.add_argument("--holidays", type=Path, default=ROOT / "data" / "r1_real" / "jp_holidays" / "holidays.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: day counts, prices, spreads, no look")
    ap.add_argument("--line", choices=sorted(LINES), help="the registered line to look at (required for a look)")
    a = ap.parse_args(argv)
    holidays = load_holidays(a.holidays)
    if a.dry_check:
        print(json.dumps(dry_check(a.ticks, holidays), indent=1))
        return 0
    if a.line is None:
        ap.error("a look needs --line")
    versions = LINES[a.line]
    cfg, reg = load_config(ROOT / "config"), LookRegister(CANONICAL)
    cost = cost_model(cfg, NAME)
    looks = {}
    for family, (formula, _, _) in versions.items():         # every line first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-GOTOBI-USDJPY", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": formula, "instruments": [NAME]},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=TickSource(), claim=claim,
                                            account="research", instruments=(NAME,), costs={NAME: cost},
                                            start=START, graded_from=GRADED_FROM, end=END)
    gotobi, control = days_of(holidays, "30")
    stressed = lambda s: cost.__class__(cost.commission_per_side, cost.slippage_per_side,   # noqa: E731
                                        stress=cost.stress * s, spread_floor=cost.spread_floor)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    out = {}
    for family, (look, fold) in looks.items():
        _, legs, times = versions[family]
        g_sessions, c_sessions = (window_prices(a.ticks, NAME, ds, ZONE, times) for ds in (gotobi, control))
        grade_event_look(look, fold, register=reg, cfg=cfg, source=TickSource(), costs={NAME: cost},
                         graded_from=GRADED_FROM,
                         run=lambda s, g=g_sessions, legs=legs, times=times: simulate_window(
                             g, stressed(s), START, GRADED_FROM, END, legs, ZONE, times),
                         benchmark=lambda c=c_sessions, legs=legs, times=times: simulate_window(
                             c, cost, START, GRADED_FROM, END, legs, ZONE, times).daily,
                         summary=lambda r: {"days_skipped": len(r.skipped), "days_traded": len(r.events)})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "days_traded": outcome["days_traded"],
                       "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])), "hac_t": verdict.hac_t,
                       "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "control_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "days_skipped": outcome["days_skipped"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"gotobi_{a.line}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
