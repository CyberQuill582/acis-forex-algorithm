"""REBAL's real-data looks: the 2012-2023 kill tests of v1a and v1b (GAP-P12D-157).

    python scripts/r1_rebal_kill_test.py --candles data/r1_real/dukascopy_candles --dry-check   # P&L-blind
    python scripts/r1_rebal_kill_test.py --candles data/r1_real/dukascopy_candles               # the looks

Mental model (owner rulings 2026-10-03; register-first: every refusal happens before any compute):
  * Both versions trade the paper's position (`rebal.py`) close to close at the US cash close
    (`event_daily.py`): v1a on the US500 CFD alone (every venue has it); v1b on US500 minus the
    modelled 10-year note futures (Pepperstone lists one; FTMO and E8's CFDs do not). Swap-free.
  * BOTH lines are registered before EITHER is graded, and forward eligibility is pre-declared:
    survival plus venue fit, never which earned more (GAP-P12D-157). Each is kill-only: the paper was
    SELECTED by the 2026-10-01 research agent (claude-opus-5-5, web), so master §5.6 certifies a pass
    only after that date; `verdict.kill_verdict` kills at a HAC t below -0.5.
  * `--dry-check` reads no strategy return: the signals' facts the paper states (their correlation
    ~0.6, the 1.1% band resetting about monthly and 2.5% quarterly, positive means), the position's
    mean, size and turnover, and the anchors found.
  * Every number goes to data/validation/r1_kill_test/rebal.json, with the inputs' sha256.
"""

from __future__ import annotations

import argparse
import csv
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
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.event_daily import quoted, simulate_daily  # noqa: E402
from tests.backtest.event_sim import Leg  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rebal import TARGET, drift, signals  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

SIGNAL_FROM, START, GRADED_FROM, END = date(2011, 1, 3), date(2012, 1, 2), date(2012, 2, 1), date(2023, 12, 29)
NOTE_COST = 0.0002          # provisional per-side cost of the note leg: about 2 ticks of 1/64 on ~110, halved, + slippage
CORE = ("rebal: position = mean(-threshold/1.5%, calendar term), set at the us cash close and held to the next; "
        "threshold = mean over delta 0..2.5% step 0.1% of the drifted 60/40 weight - 60%, reset the day after a "
        "breach; calendar term = sign(-calendar) in the last 5 business days, sign(calendar at day -4) on the "
        "first; inputs s&p cash closes and the 7-year par yield's duration move; swap-free")
VERSIONS = {"rebal_v1a_us500": f"{CORE}; on us500 alone",
            "rebal_v1b_spread": f"{CORE}; on us500 minus the 10-year note futures (modelled, {NOTE_COST:.2%} a side)"}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-01",
                exposure="web", reference="Harvey, Mazzoleni & Melone, The Unintended Consequences of Rebalancing, "
                "NBER w33554 (version 2026-01-14, SSRN 5122748); selected by the 2026-10-01 research agent EDGE",
                published="2025-03-01")


def _series(path: Path, col: str) -> dict[date, float]:
    with path.open(encoding="utf-8") as f:
        return {date.fromisoformat(r["date"]): float(r[col]) for r in csv.DictReader(f)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resets_per_year(rs: np.ndarray, rb: np.ndarray, delta: float) -> float:
    w, n = TARGET, 0
    for k in range(len(rs)):
        breach = abs(w - TARGET) >= delta
        n += breach
        w = TARGET if breach else drift(w, rs[k], rb[k])
    return n / (len(rs) / 252)


def dry_check(days, sig, us500) -> dict:
    graded = np.array([START <= d <= END for d in days])
    pos, thr, cal = sig["position"][graded], sig["threshold"][graded], sig["calendar"][graded]
    leg = Leg(quoted(us500), np.zeros(1, np.int64))
    missing = [d.isoformat() for d in days if START <= d <= END and leg.anchor("XNYS", d) is None]
    return {"sessions": int(graded.sum()), "corr_threshold_calendar": float(np.corrcoef(thr, cal)[0, 1]),
            "mean_threshold": float(thr.mean()), "mean_calendar": float(cal.mean()),
            "resets_per_year": {f"{d:.1%}": resets_per_year(sig["rs"], sig["rb"], d) for d in (0.011, 0.02, 0.025)},
            "calendar_term_share": float(np.mean(np.abs(pos - 0.5 * (-thr / 0.015)) > 1e-12)),
            "mean_position": float(pos.mean()), "mean_abs_position": float(np.abs(pos).mean()),
            "mean_daily_turnover": float(np.abs(np.diff(pos)).mean()), "sessions_without_anchor": missing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, required=True)
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--treasury", type=Path, default=ROOT / "data" / "r1_real" / "treasury")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: signal facts and anchors, no look")
    a = ap.parse_args(argv)
    spx_path, ust_path = a.macro / "spx_yahoo.csv", a.treasury / "ust_par.csv"
    spx, y7 = _series(spx_path, "value"), _series(ust_path, "y7")
    days = [d for d in sorted(spx) if SIGNAL_FROM <= d <= END]
    sig, us500 = signals(days, spx, y7), load(a.candles, "US500", (END.year, END.month))
    if a.dry_check:
        print(json.dumps(dry_check(days, sig, us500), indent=1))
        return 0
    cfg, reg = load_config(ROOT / "config"), LookRegister(CANONICAL)
    cost, inputs = cost_model(cfg, "US500"), {"spx_yahoo.csv": _sha(spx_path), "ust_par.csv": _sha(ust_path)}
    looks = {}
    for family, formula in VERSIONS.items():                  # both lines first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-REBAL-US500", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": formula, "instruments": ["US500"]},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=CandleSource(), claim=claim,
                                            account="research", instruments=("US500",), costs={"US500": cost},
                                            start=START, graded_from=GRADED_FROM, end=END)
    out = {}
    for family, (look, fold) in looks.items():
        note = sig["rb"] if family.endswith("spread") else None
        run = lambda s, note=note: simulate_daily(us500, days, sig["position"], cost.__class__(  # noqa: E731
            cost.commission_per_side, cost.slippage_per_side, stress=cost.stress * s, spread_floor=cost.spread_floor),
            START, GRADED_FROM, END, note=note, note_cost=NOTE_COST * s)
        grade_event_look(look, fold, register=reg, cfg=cfg, source=CandleSource(), costs={"US500": cost},
                         graded_from=GRADED_FROM, run=run,
                         benchmark=lambda: simulate_daily(us500, days, np.ones(len(days)), None, START, GRADED_FROM, END).daily,
                         summary=lambda r: {"sessions_skipped": len(r.skipped), "inputs": inputs})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])),
                       "hac_t": verdict.hac_t, "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "benchmark_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "sessions_skipped": outcome["sessions_skipped"], "inputs": inputs}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "rebal.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
