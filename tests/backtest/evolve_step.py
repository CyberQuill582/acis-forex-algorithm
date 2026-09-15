"""Per-fold evolution for the walk-forward (ACIS-03 §6–§7, ACIS-09 §6, GAP-P12D-18).

Invariants:
  * Evolution reads ONLY labelled bars that open before the fold's `train_end`
    (`LabelledBarCache.history`), so no test-window price reaches QIEA.
  * Every tradeable regime is evolved on every listed instrument, each with its own C8
    cost model. The champion with the best holdout expectancy — E_R on the same
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
from typing import Sequence

from config.schemas import AcisConfig, OptimizerConfig
from core.optimizer.costs import CostModel
from core.optimizer.fitness import expectancy_r, simulate_trades
from core.optimizer.param_types import ParamSet, RegimeLabelledHistory
from core.optimizer.qiea import QIEA
from core.regime.regime_types import NEVER_TRADEABLE, RegimeType
from tests.backtest.deflated_sharpe import moments
from tests.backtest.regime_labels import LabelledBarCache


def seed_for(fold_index: int, regime: RegimeType, instrument: str) -> int:
    digest = hashlib.sha256(f"{fold_index}|{regime.value}|{instrument}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def cost_model(cfg: AcisConfig, instrument: str) -> CostModel:
    costs = cfg.instruments.instruments[instrument].costs
    if costs is None:
        raise ValueError(f"{instrument} declares no C8 costs — onboard it before evolving on it")
    return CostModel(commission_per_side=costs.commission_per_side,
                     slippage_per_side=costs.slippage_per_side)


def holdout_pnls(champion: ParamSet, history: RegimeLabelledHistory, opt: OptimizerConfig,
                 cost: CostModel, atr_period: int) -> list[float]:
    """Net PnLs of the trades entered in the chronological holdout tail QIEA gates on."""
    bars = history.bars[-opt.fitness_bars:]
    n_hold = max(1, round(len(bars) * opt.holdout_fraction))
    return simulate_trades(champion, bars, cost, entry_start=len(bars) - n_hold,
                           atr_period=atr_period)


def evolve_fold(loop, fd, *, cfg: AcisConfig, cache: LabelledBarCache,
                instruments: Sequence[str], logger) -> dict:
    opt, sig = cfg.system.optimizer, cfg.system.signals
    train_end = fd.fold.train_end
    regimes: dict[str, dict] = {}
    champions = 0
    trial_sharpes: list[float] = []
    for regime in RegimeType:
        if regime in NEVER_TRADEABLE:
            continue
        candidates, best, best_params = [], None, None
        for instrument in instruments:
            cost = cost_model(cfg, instrument)
            history = cache.history(instrument, regime, fd.fold.train_start, train_end, opt.fitness_bars)
            qiea = QIEA(opt, cost, logger, signal_bar_seconds=sig.signal_bar_seconds,
                        atr_period=sig.atr_period)
            champion = qiea.evolve(regime, history, seed=seed_for(fd.fold.index, regime, instrument),
                                   now=train_end)
            entry = {"instrument": instrument, "bars": len(history.bars), "champion": champion is not None,
                     "first_bar": history.bars[0].ts.isoformat() if history.bars else None,
                     "last_bar": history.bars[-1].ts.isoformat() if history.bars else None}
            if champion is not None:
                champions += 1
                pnls = holdout_pnls(champion, history, opt, cost, sig.atr_period)
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
