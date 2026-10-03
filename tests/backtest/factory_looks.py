"""The factory's one-look graders and their context (FACTORY 2026-10-04, GAP-P12D-158: owner pre-authorised
ONE kill-only look per candidate on 2012-02..2023-12, killed at a HAC t below -0.5).

Mental model:
  * `rsim_look` and `event_look` write the candidate's ONE register line and grade it, through the house
    graders only (`evaluate.evaluate` for daily targets on the 17:00 New York clock, `evaluate_events`
    for a close-to-close index book): every refusal happens before any compute, the line is consumed
    once, the outcome and its daily vector are chained, and the verdict is `verdict.kill_verdict`.
  * Each grade also stores the PASSIVE_LONG arm and the book at 2x C8 cost, as context, never a verdict.
  * `context` reads ONLY stored vectors: per-year Sharpe, the Sharpe without the 10 best days, the
    pre-declared segments, and the correlation with D1-FX13, REBAL v1a and GOTOBI v1a on common dates.
    Nothing is re-simulated after a look.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Callable, Mapping, Sequence

import numpy as np

from tests.backtest.evaluate import StageArms, evaluate
from tests.backtest.evaluate_events import grade_event_look, register_event_look
from tests.backtest.event_sim import EventResult
from tests.backtest.look_claims import Claim, Origin, load_vector
from tests.backtest.look_declarations import Declaration
from tests.backtest.look_register import CANONICAL, LookRegister, git_state
from tests.backtest.rsim import BookSpec, Market, annual_sharpe
from tests.backtest.rsim_real import CandleSource
from tests.backtest.verdict import KILL_T, kill_verdict

GRADED_FROM, END = date(2012, 2, 1), date(2023, 12, 29)
REFERENCES = {"D1-FX13": "000001", "REBAL_v1a": "000007", "GOTOBI_v1a": "000015"}


def claim(family: str, formula: str, names: Sequence[str], universe_id: str, origin: Origin, simulator: str) -> Claim:
    return Claim(family=family, variant="fixed", universe_id=universe_id, origin=origin, simulator=simulator,
                 declared_space={"grid": {}, "formula": formula, "instruments": sorted(names)},
                 recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))


def rsim_look(*, cfg, cl: Claim, market: Market, forecast: np.ndarray, pct_vol: np.ndarray, spec: BookSpec) -> str:
    """Daily targets on RSIM's clock; the benchmark is +10 wherever the family forecasts."""
    graded_from = next(d for d in market.days if d >= GRADED_FROM)
    arms = StageArms(benchmark="PASSIVE_LONG", benchmark_forecast=np.where(np.isnan(forecast), np.nan, 10.0))
    look, _ = evaluate(register=LookRegister(CANONICAL), cfg=cfg, source=CandleSource(), family=cl.family,
                       claim=cl, account="research", market=market, forecast=forecast, pct_vol=pct_vol,
                       spec=spec, graded_from=graded_from, arms=arms)
    return look.look_id


def event_look(*, cfg, cl: Claim, costs: Mapping, start: date, run: Callable[[Mapping], EventResult],
               benchmark: Callable[[], EventResult], summary: dict) -> str:
    """A close-to-close book; `run(costs)` books it at the given cost models (1x graded, 2x context)."""
    reg = LookRegister(CANONICAL)
    look, fold = register_event_look(register=reg, cfg=cfg, source=CandleSource(), claim=cl, account="research",
                                     instruments=tuple(costs), costs=costs, start=start,
                                     graded_from=GRADED_FROM, end=END)
    scaled = lambda s: {n: replace(c, stress=c.stress * s) for n, c in costs.items()}   # noqa: E731
    grade_event_look(look, fold, register=reg, cfg=cfg, source=CandleSource(), costs=costs, graded_from=GRADED_FROM,
                     run=lambda s: run(scaled(s)), benchmark=lambda: benchmark().daily, summary=lambda r: summary)
    return look.look_id


def _vectors(look_id: str) -> tuple[dict[date, float], dict[str, dict[date, float]]]:
    out = LookRegister(CANONICAL).outcome(look_id)
    ctx = out.get("context") or out.get("stage_a") or {}
    as_map = lambda h: dict(zip(*load_vector(CANONICAL, h)))                       # noqa: E731
    return as_map(out["daily_vector"]), {k: as_map(ctx[k]) for k in ("benchmark_vector", "cost2x_vector") if k in ctx}


def _sharpe(m: Mapping[date, float], lo: date | None = None, hi: date | None = None) -> float | None:
    x = np.array([v for d, v in sorted(m.items()) if (lo is None or d >= lo) and (hi is None or d < hi)])
    return annual_sharpe(x) if len(x) > 2 else None


def context(look_id: str, cuts: Sequence[date] = ()) -> dict:
    """What the lead reads after a look, from the register's stored vectors alone."""
    daily, arms = _vectors(look_id)
    x = np.array([v for _, v in sorted(daily.items())])
    years = sorted({d.year for d in daily})
    edges = [min(daily), *cuts, None]
    corr = {}
    for name, ref in REFERENCES.items():
        r, _ = _vectors(ref)
        common = sorted(set(daily) & set(r))
        a, b = np.array([daily[d] for d in common]), np.array([r[d] for d in common])
        corr[name] = float(np.corrcoef(a, b)[0, 1]) if len(common) > 30 and a.std() > 0 and b.std() > 0 else None
    verdict = kill_verdict(CANONICAL, look_id)
    return {"look_id": look_id, "annual_sharpe": annual_sharpe(x), "hac_t": verdict.hac_t,
            "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed, "graded_days": len(x),
            "benchmark_annual_sharpe": _sharpe(arms["benchmark_vector"]) if "benchmark_vector" in arms else None,
            "cost2x_annual_sharpe": _sharpe(arms["cost2x_vector"]) if "cost2x_vector" in arms else None,
            "per_year": {y: _sharpe(daily, date(y, 1, 1), date(y + 1, 1, 1)) for y in years},
            "without_10_best_days": annual_sharpe(np.sort(x)[:-10]) if len(x) > 20 else None,
            "segments": {f"{a}..{b or 'end'}": _sharpe(daily, a, b) for a, b in zip(edges[:-1], edges[1:])},
            "corr": corr}
