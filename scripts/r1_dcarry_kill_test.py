"""DCARRY's one real-data look: the dollar carry trade, spot only, on the six dollar pairs (FACTORY, GAP-P12D-158).

    python scripts/r1_dcarry_kill_test.py --dry-check       # P&L-blind: the AFD's sign by month, turnover, spreads
    python scripts/r1_dcarry_kill_test.py --look            # the ONE look, kill-only (HAC t < -0.5)

Mental model (register-first; owner pre-authorisation 2026-10-03: one pre-declared version, one look):
  * Signal `dollar_carry.py` (Lustig, Roussanov & Verdelhan 2014: long the foreign basket against the
    dollar when the average foreign rate is above the US rate, else short), monthly, graded by RSIM on
    the six dollar pairs exactly as FXVALUE is: 17:00 New York decisions, 08:00 fills, $1M, 20% vol
    target, IDM 1, equal weights, the 10% buffer, swap-free, C8 costs plus each fill's quoted spread.
  * DECLARED departures: six currencies (EUR, JPY, GBP, AUD, CAD, CHF), not the paper's developed basket;
    overnight and policy rates for its 1-month forward discounts; risk-weighted pairs for its equal
    notional basket; spot only (swap-free), the paper's 3.77% of 5.60% a year.
  * WINDOW ROLES: the paper's sample ends 2010-12, so 2012-2023 is after it; no other evidence selected it.
  * EXPECTED CORRELATION, before the look: D1-FX13 about +0.1 (a dollar bet held for years can ride a
    dollar trend); REBAL v1a and GOTOBI v1a about 0. Measured afterwards from the stored vectors.
  * The origin is the literature SELECTED by FACTORY (claude-opus-5-5, web) on 2026-10-04: kill-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest import dollar_carry  # noqa: E402
from tests.backtest.factory_looks import END, claim, context, rsim_look  # noqa: E402
from tests.backtest.financing import load_rate_table  # noqa: E402
from tests.backtest.look_claims import Origin  # noqa: E402
from tests.backtest.rsim import BookSpec  # noqa: E402
from tests.backtest.rsim_lab import carver_pct_vol  # noqa: E402
from tests.backtest.rsim_real import build  # noqa: E402

FAMILY, UNIVERSE = "dcarry_v1_spot", "R1-DCARRY-6USD"
NAMES = ("AUD_USD", "EUR_USD", "GBP_USD", "USD_CAD", "USD_CHF", "USD_JPY")
START, FIRST, HALF = date(2012, 1, 2), (2012, 1), date(2018, 1, 1)    # segments: the two halves
FORMULA = ("dcarry: at each month's last decision day, afd = mean over eur jpy gbp aud cad chf of (overnight rate - "
           "usd overnight rate) read 3 calendar days earlier; for the next month forecast +10 on xxx_usd and -10 on "
           "usd_xxx when afd > 0, the opposite otherwise; rsim 17:00 new york decisions, swap-free, spot only")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                exposure="web", reference="Lustig, Roussanov & Verdelhan, Countercyclical currency risk premia, Journal "
                "of Financial Economics 111(3) (2014) 527-553; selected by FACTORY 2026-10-04 (GAP-P12D-158)",
                published="2014-03-01")
EX_ANTE = {"source_dollar_carry_developed": {"mean": 0.0560, "sharpe": 0.66, "spot_part_mean": 0.0377,
                                             "spot_part_se": 0.0167, "sample": "1983-11..2010-12"}}


def dry_check(m, f, rates) -> dict:
    ends = dollar_carry.month_ends(m.days)
    afd = {f"{y}-{mo:02d}": round(dollar_carry.afd(rates, d), 3) for (y, mo), d in sorted(ends.items())
           if date(2012, 1, 1) <= d <= date(2023, 11, 30)}
    signs = [1 if v > 0 else -1 for v in afd.values()]
    flips = [k for k, (a, b) in zip(list(afd)[1:], zip(signs, signs[1:])) if a != b]
    return {"months": len(afd), "months_long_foreign": signs.count(1), "months_long_usd": signs.count(-1),
            "sign_flips_after": flips, "afd_pct_by_month": afd, "ex_ante": EX_ANTE,
            "forecast_trades_per_year": len(flips) / 12.0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-check", action="store_true")
    g.add_argument("--look", action="store_true")
    a = ap.parse_args(argv)
    cfg, rates = load_config(ROOT / "config"), load_rate_table(a.macro)
    m = build(a.candles, NAMES, rates, START, END, tier="development").market
    f = dollar_carry.panel(m.days, m.names, rates, FIRST)
    if a.dry_check:
        print(json.dumps(dry_check(m, f, rates), indent=1))
        return 0
    spec = BookSpec(costs={n: cost_model(cfg, n) for n in m.names}, capital=1_000_000.0, vol_target=0.20, idm=1.0,
                    buffer=cfg.system.targets.buffer, world="swap_free")
    look_id = rsim_look(cfg=cfg, cl=claim(FAMILY, FORMULA, m.names, UNIVERSE, ORIGIN, "rsim"), market=m,
                        forecast=f, pct_vol=carver_pct_vol(m), spec=spec)
    out = context(look_id, [HALF]) | {"family": FAMILY}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "dcarry.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
