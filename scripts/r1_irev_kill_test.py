"""IREV's one real-data look: trading against index serial dependence at each home close (FACTORY, GAP-P12D-158).

    python scripts/r1_irev_kill_test.py --dry-check      # P&L-blind: sessions, anchor spreads, turnover, the cost gate
    python scripts/r1_irev_kill_test.py --look           # the ONE look on the admitted indices, kill-only (t < -0.5)

Mental model (register-first; owner pre-authorisation 2026-10-03: one pre-declared version, one look):
  * Position `irev.py` (Baltussen, van Bekkum & Da 2019, minus MAC(5): -(4,3,2,1) of the last four returns),
    one index per country (the paper drops the Dow as subsumed by the S&P 500), each traded at its own
    cash close (`event_multi.book`), equal risk, C8 costs on every change, swap-free.
  * COST GATE, P&L-blind and fixed before the look: an index is admitted only if the paper's gross (Sharpe
    0.63 on its indexes, no costs) at the book's risk is at least 3x its C8 cost at the measured turnover
    and anchor spreads (`--dry-check` prints both); ADMITTED holds the result.
  * WINDOW ROLES: the paper's sample ends 2016-12, so 2012-2016 was seen and 2017-2023 is a segment; a
    2026 working paper (SPY's reversal lies in magnitude, not sign) is counter-evidence the lead holds.
  * EXPECTED CORRELATION, before the look: REBAL v1a about +0.2 (both lean against recent US equity
    moves; US500 is one leg of three); D1-FX13 and GOTOBI v1a about 0.
  * The origin is the literature SELECTED by the 2026-10-01 slate and FACTORY (claude-opus-5-5, web): kill-only.
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
from tests.backtest import irev  # noqa: E402
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.event_multi import LEG_RISK, book, passive_targets, sessions  # noqa: E402
from tests.backtest.factory_looks import END, GRADED_FROM, claim, context, event_look  # noqa: E402
from tests.backtest.look_claims import Origin  # noqa: E402

FAMILY, UNIVERSE = "irev_v1_mac5", "R1-IREV-HOME-CLOSE"
CANDIDATES = ("US500", "UK100", "EU50", "JP225", "AUS200")
ADMITTED = ("US500", "UK100", "JP225")    # the dry check 2026-10-04: gross/cost 4.1, 4.9, 3.05; EU50 1.6, AUS200 2.7 out
START, SEEN_UNTIL, SOURCE_SHARPE, GATE = date(2012, 1, 2), date(2017, 1, 1), 0.63, 3.0
FORMULA = ("irev: each index at its own cash-close anchor holds -0.01/sigma x clip((4z(s)+3z(s-1)+2z(s-2)+z(s-3))"
           "/sqrt(30), -2, 2) to the next anchor, z = log return / sigma, sigma the sd of the last 60 session returns; "
           "c8 costs on every change, swap-free, flat before 2012-02-01")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                exposure="web", reference="Baltussen, van Bekkum & Da, Indexing and stock market serial dependence "
                "around the world, Journal of Financial Economics 132(1) (2019) 26-48; on the 2026-10-01 slate (IREV), "
                "selected by FACTORY 2026-10-04 (GAP-P12D-158)", published="2019-04-01")


def dry_check(legs, cfg) -> dict:
    out = {}
    for n, s in legs.items():
        graded = np.array([GRADED_FROM <= d <= END for d in s.days])
        t = np.nan_to_num(irev.target(s))[graded]
        side = np.array([cost_model(cfg, n).per_side_cost(sp) / p for sp, p in zip(s.spreads[graded], s.closes[graded])])
        years = graded.sum() / 252.0
        cost = float(np.sum(np.abs(np.diff(np.r_[0.0, t])) * side) / years)
        gross = SOURCE_SHARPE * LEG_RISK * np.sqrt(252)                 # the paper's Sharpe at the book's daily risk
        weekdays = np.busday_count(GRADED_FROM, END) + 1
        out[n] = {"sessions": int(graded.sum()), "weekdays_without_anchor": int(weekdays - graded.sum()),
                  "median_anchor_spread_bp": float(np.median(s.spreads[graded] / s.closes[graded]) * 1e4),
                  "median_c8_side_bp": float(np.median(side) * 1e4),
                  "mean_daily_turnover": float(np.mean(np.abs(np.diff(t)))), "annual_cost": cost,
                  "ex_ante_annual_gross": float(gross), "gross_over_cost": float(gross / cost),
                  "admitted": bool(gross / cost >= GATE)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-check", action="store_true")
    g.add_argument("--look", action="store_true")
    a = ap.parse_args(argv)
    cfg, names = load_config(ROOT / "config"), CANDIDATES if a.dry_check else ADMITTED
    legs = {n: sessions(load(a.candles, n, (END.year, END.month)), n, START, END) for n in names}
    if a.dry_check:
        print(json.dumps(dry_check(legs, cfg), indent=1))
        return 0
    costs, targets = {n: cost_model(cfg, n) for n in names}, {n: irev.target(s) for n, s in legs.items()}
    look_id = event_look(cfg=cfg, cl=claim(FAMILY, FORMULA, names, UNIVERSE, ORIGIN, "event"), costs=costs, start=START,
                         run=lambda c: book(legs, targets, c, START, GRADED_FROM, END),
                         benchmark=lambda: book(legs, passive_targets(legs), None, START, GRADED_FROM, END),
                         summary={"sessions": {n: len(s.days) for n, s in legs.items()}})
    out = context(look_id, [SEEN_UNTIL]) | {"family": FAMILY, "instruments": list(names)}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "irev.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
