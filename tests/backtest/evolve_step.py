"""Per-fold evolution for the walk-forward (ACIS-03 §6–§7, ACIS-09 §6, GAP-P12D-18).

Invariants:
  * Evolution reads ONLY labelled bars that open before the fold's `train_end`
    (`LabelledBarCache.history`), so no test-window price reaches QIEA.
  * The window is a time span, not a bar count (master §5 v2.18, GAP-P12D-29): every
    target-regime bar inside both the fold's train window and `fitness_span_days`.
  * Every tradeable regime is evolved on every listed instrument, each with its own C8
    cost model — the caller's map, which is the SAME map the graded book charges
    (master §5 C8 "one model, both places"; GAP-P12D-36/46). The champion with the best holdout expectancy — E_R on the same
    chronological holdout tail QIEA gates on — is staged; ties keep instrument order.
  * Params are STAGED only. Promotion happens later, at a simulated session boundary when
    the backtest book is flat (harness.py, ACIS-03 §7).
  * Seeds derive from (fold, regime, instrument), so a rerun reproduces every champion
    (ACIS-03 §3).
  * The returned record is the fold's in-sample transparency record. `trial_sharpes` holds
    the holdout per-trade Sharpe of EVERY candidate champion (every instrument × regime that
    produced one): the selection set the Deflated Sharpe deflates by (owner ruling GAP-P12D-25).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Mapping, Sequence

from config.schemas import AcisConfig, OptimizerConfig
from core.optimizer.costs import CostModel
from core.optimizer.fitness import expectancy_r, simulate_trades
from core.optimizer.param_types import ParamSet, RegimeLabelledHistory
from core.optimizer.qiea import QIEA, fitness_window
from core.regime.regime_types import NEVER_TRADEABLE, RegimeType
from tests.backtest.deflated_sharpe import moments
from tests.backtest.regime_labels import LabelledBarCache


def seed_for(fold_index: int, regime: RegimeType, instrument: str) -> int:
    digest = hashlib.sha256(f"{fold_index}|{regime.value}|{instrument}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def cost_model(cfg: AcisConfig, instrument: str, *, stress: float = 1.0,
               spread_floor: float = 0.0) -> CostModel:
    """The declared C8 model for `instrument`, optionally stressed (GAP-P12D-46).

    `stress`/`spread_floor` are RUN properties: the caller builds the map ONCE and hands
    the same instances to selection and to grading, so a stressed run cannot select in a
    cheap world and be graded in an expensive one (the GAP-P12D-36 defect class)."""
    costs = cfg.instruments.instruments[instrument].costs
    if costs is None:
        raise ValueError(f"{instrument} declares no C8 costs — onboard it before evolving on it")
    return CostModel(commission_per_side=costs.commission_per_side,
                     slippage_per_side=costs.slippage_per_side,
                     stress=stress, spread_floor=spread_floor)


def holdout_pnls(champion: ParamSet, history: RegimeLabelledHistory, opt: OptimizerConfig,
                 cost: CostModel, atr_period: int, now: datetime) -> list[float]:
    """Net PnLs of the trades entered in the chronological holdout tail QIEA gates on, over
    the same `fitness_window` QIEA read."""
    bars = fitness_window(history, opt, now)
    n_hold = max(1, round(len(bars) * opt.holdout_fraction))
    return simulate_trades(champion, bars, cost, entry_start=len(bars) - n_hold,
                           atr_period=atr_period)


def evolve_fold(loop, fd, *, cfg: AcisConfig, costs: Mapping[str, CostModel],
                cache: LabelledBarCache, instruments: Sequence[str], logger) -> dict:
    """`costs` is the run's cost map — the SAME instances the graded book charges. It is
    required, not derived from `cfg` here, so the two sides cannot drift apart."""
    opt, sig = cfg.system.optimizer, cfg.system.signals
    train_end = fd.fold.train_end
    window_start = max(fd.fold.train_start, train_end - timedelta(days=opt.fitness_span_days))
    regimes: dict[str, dict] = {}
    champions = 0
    trial_sharpes: list[float] = []
    for regime in RegimeType:
        if regime in NEVER_TRADEABLE:
            continue
        candidates, best, best_params = [], None, None
        for instrument in instruments:
            try:
                cost = costs[instrument]
            except KeyError:
                raise ValueError(f"no C8 cost model supplied for {instrument} — the run's cost "
                                 "map must cover every evolved instrument") from None
            history = cache.history(instrument, regime, window_start, train_end, None)
            qiea = QIEA(opt, cost, logger, signal_bar_seconds=sig.signal_bar_seconds,
                        atr_period=sig.atr_period)
            champion = qiea.evolve(regime, history, seed=seed_for(fd.fold.index, regime, instrument),
                                   now=train_end)
            entry = {"instrument": instrument, "bars": len(history.bars), "champion": champion is not None,
                     "first_bar": history.bars[0].ts.isoformat() if history.bars else None,
                     "last_bar": history.bars[-1].ts.isoformat() if history.bars else None}
            if champion is not None:
                champions += 1
                pnls = holdout_pnls(champion, history, opt, cost, sig.atr_period, train_end)
                res, m = expectancy_r(pnls), moments(pnls)
                sharpe = m.sharpe if m is not None else None
                if sharpe is not None:
                    trial_sharpes.append(sharpe)
                entry.update(fitness=champion.fitness_score, holdout_e_r=res.e_r,
                             holdout_trades=res.n_trades, holdout_trade_sharpe=sharpe,
                             param_set_id=champion.param_set_id)
                if best is None or res.e_r > best["holdout_e_r"]:
                    best, best_params = entry, champion
            candidates.append(entry)
        if best_params is not None:
            loop.params.stage(best_params, now=train_end)
        regimes[regime.value] = {"staged_from": best["instrument"] if best else None,
                                 "candidates": candidates}
    return {"fold": fd.fold.index, "train_end": train_end.isoformat(),
            "champions": champions, "trial_sharpes": trial_sharpes, "regimes": regimes}
