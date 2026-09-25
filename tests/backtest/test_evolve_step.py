"""Per-fold evolution (GAP-P12D-18): every instrument evolves each regime, the best holdout
expectancy is staged, nothing at or after the train end is read, and a rerun reproduces it."""

from __future__ import annotations

import random
from datetime import timedelta
from types import SimpleNamespace

from core.optimizer.plateau import PlateauVerdict
from core.optimizer.qiea import EvolutionResult
from tests.backtest.evolve_step import cost_model, evolve_fold


def _costs(cfg, **kw):
    return {i: cost_model(cfg, i, **kw) for i in ("EUR_USD", "USD_JPY")}
from tests.backtest.harness import FoldData
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import (T0, CapturingLogger, bars_from_closes, make_paramset, opt_cfg,
                                     zigzag_closes)

SPEC = LabelSpec(source="test", bar_seconds=60, cycle_s=120.0, regime_config="{}")
TRAIN_END = T0 + timedelta(minutes=500)                  # bars 0..499 open before it


class _Stager:
    def __init__(self) -> None:
        self.staged: list = []

    def stage(self, params, *, now) -> str:
        self.staged.append((params, now))
        return "pending"


def _cfg(acis_config):
    system = acis_config.system.model_copy(update={"optimizer": opt_cfg()})
    return acis_config.model_copy(update={"system": system})


def _run(tmp_path, acis_config, n_bars: int):
    bars = bars_from_closes(zigzag_closes(n_bars))
    cache = LabelledBarCache(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars)
    loop = SimpleNamespace(params=_Stager())
    # fold index 1: the index only seeds QIEA (seed_for), and fold 0's EUR_USD zigzag champion is
    # a knife-edge (rsi_period ±10% dies) that the §5.6 plateau law refuses (GAP-P12D-34)
    fold = Fold(1, T0, TRAIN_END, TRAIN_END + timedelta(days=7),      # only the cached year
                TRAIN_END + timedelta(days=365))
    cfg = _cfg(acis_config)
    record = evolve_fold(loop, FoldData(fold, ()), cfg=cfg, costs=_costs(cfg), cache=cache,
                         instruments=["EUR_USD", "USD_JPY"], logger=CapturingLogger())
    return record, loop.params.staged


def test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read(tmp_path, acis_config) -> None:
    record, staged = _run(tmp_path / "600", acis_config, 600)       # 100 bars lie after train_end
    trend = record["regimes"]["STRONG_TREND_UP"]
    eur, jpy = trend["candidates"]
    assert (eur["instrument"], jpy["instrument"]) == ("EUR_USD", "USD_JPY")
    assert eur["bars"] == jpy["bars"] == 500                       # only bars before train_end
    assert eur["champion"] and trend["staged_from"] == "EUR_USD"
    # USD/JPY's 0.002 friction on 1.1-priced bars cannot carry positive expectancy
    assert not jpy["champion"]
    assert record["champions"] == 1 and len(staged) == 1
    # a perfect zigzag makes every holdout trade identical (5 × 0.00186): zero variance means no
    # Sharpe, so this champion is NOT a Deflated Sharpe trial (GAP-P12D-25)
    assert eur["holdout_trade_sharpe"] is None and record["trial_sharpes"] == []
    assert "holdout_trade_sharpe" not in jpy                       # no champion, no trial
    params, now = staged[0]
    assert params.regime.value == "STRONG_TREND_UP" and now == TRAIN_END
    assert set(record["regimes"]) == {"STRONG_TREND_UP", "STRONG_TREND_DOWN", "WEAK_TREND_UP",
                                      "WEAK_TREND_DOWN", "RANGING_TIGHT", "RANGING_WIDE",
                                      "BREAKOUT_IMMINENT", "POST_BREAKOUT", "MEAN_REVERTING"}

    again, staged_again = _run(tmp_path / "500", acis_config, 500)  # the same 500 bars, nothing after
    assert again == record                                          # no leakage, and reproducible
    assert staged_again[0][0].param_set_id == params.param_set_id


def test_fold_evolves_on_every_bar_in_the_span_not_the_last_500(tmp_path, acis_config) -> None:
    """GAP-P12D-29 (master §5 v2.18): the fold's window is every target-regime bar inside both
    the train window and `fitness_span_days`. With 48 h of train bars and a 1-day span, all
    1,440 bars of the last day are read (no 500-bar cap) and nothing older."""
    train_end = T0 + timedelta(days=2)
    cache = LabelledBarCache(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars_from_closes(zigzag_closes(3000)))
    system = acis_config.system.model_copy(update={"optimizer": opt_cfg(fitness_span_days=1)})
    cfg = acis_config.model_copy(update={"system": system})
    fold = Fold(0, T0, train_end, train_end + timedelta(days=7), train_end + timedelta(days=365))
    record = evolve_fold(SimpleNamespace(params=_Stager()), FoldData(fold, ()), cfg=cfg,
                         costs=_costs(cfg), cache=cache, instruments=["EUR_USD", "USD_JPY"],
                         logger=CapturingLogger())
    eur, jpy = record["regimes"]["STRONG_TREND_UP"]["candidates"]
    assert eur["bars"] == jpy["bars"] == 1440
    assert eur["first_bar"] == (train_end - timedelta(days=1)).isoformat()
    assert eur["last_bar"] == (train_end - timedelta(minutes=1)).isoformat()


class _FixedQIEA:
    """Stands in for QIEA: returns one fixed param set for whatever regime it is asked about."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def evolve_outcome(self, regime, history, *, seed, now):
        p = make_paramset(regime=regime) if history.bars else None
        return EvolutionResult(p, p)


def test_every_candidate_champion_with_a_sharpe_is_a_trial(tmp_path, acis_config, monkeypatch) -> None:
    monkeypatch.setattr("tests.backtest.evolve_step.QIEA", _FixedQIEA)
    rng = random.Random(3)
    closes = [c + rng.uniform(-0.0003, 0.0003) for c in zigzag_closes(600)]
    bars = bars_from_closes(closes)
    cache = LabelledBarCache(tmp_path, SPEC)
    for instrument in ("EUR_USD", "USD_JPY"):
        cache.write(instrument, T0.year, bars)
    loop = SimpleNamespace(params=_Stager())
    fold = Fold(0, T0, TRAIN_END, TRAIN_END + timedelta(days=7), TRAIN_END + timedelta(days=365))
    cfg = _cfg(acis_config)
    record = evolve_fold(loop, FoldData(fold, ()), cfg=cfg, costs=_costs(cfg), cache=cache,
                         instruments=["EUR_USD", "USD_JPY"], logger=CapturingLogger())
    eur, jpy = record["regimes"]["STRONG_TREND_UP"]["candidates"]
    assert eur["holdout_trade_sharpe"] is not None and jpy["holdout_trade_sharpe"] is not None
    assert eur["holdout_trade_sharpe"] != jpy["holdout_trade_sharpe"]   # each pays its own friction
    # both candidates are trials, even though only one of them is staged
    assert record["trial_sharpes"] == [eur["holdout_trade_sharpe"], jpy["holdout_trade_sharpe"]]
    assert len(loop.params.staged) == 1


def test_a_plateau_refused_candidate_stays_a_deflated_sharpe_trial(tmp_path, acis_config, monkeypatch) -> None:
    """Audit F3: the §5.6 plateau law runs AFTER the holdout gate, so a candidate it refuses has
    already been scored on the holdout. It must stay in the DSR selection set (GAP-P12D-25), or the
    law shrinks N and loosens the ratified gate. Fold 0 of this noisy zigzag stages a champion with
    the law off ("base") and refuses it with the law on ("head"): both must count the same trials."""
    rng = random.Random(3)
    closes = [c + rng.gauss(0, 0.00015) for c in zigzag_closes(600)]
    cfg = _cfg(acis_config)

    def run(root):
        cache = LabelledBarCache(root, SPEC)
        for instrument in ("EUR_USD", "USD_JPY"):
            cache.write(instrument, T0.year, bars_from_closes(closes))
        fold = Fold(0, T0, TRAIN_END, TRAIN_END + timedelta(days=7), TRAIN_END + timedelta(days=365))
        return evolve_fold(SimpleNamespace(params=_Stager()), FoldData(fold, ()), cfg=cfg, costs=_costs(cfg),
                           cache=cache, instruments=["EUR_USD", "USD_JPY"], logger=CapturingLogger())

    head = run(tmp_path / "head")
    monkeypatch.setattr("core.optimizer.qiea.check_plateau", lambda genes, fitness: PlateauVerdict(0, ()))
    base = run(tmp_path / "base")
    assert (head["champions"], base["champions"]) == (0, 1)            # the fixture exercises a refusal
    assert head["trial_sharpes"] == base["trial_sharpes"] and len(head["trial_sharpes"]) == 1
    refused = [c for r in head["regimes"].values() for c in r["candidates"] if c.get("plateau_refused")]
    assert len(refused) == 1 and not refused[0]["champion"]
    assert refused[0]["holdout_trade_sharpe"] == head["trial_sharpes"][0]
