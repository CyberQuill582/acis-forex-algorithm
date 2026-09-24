"""The §5.6 parameter-plateau law (master §5.6, GAP-P12D-34), hand-worked.

"Parameter plateaus required — a strategy that dies at ±10% on any parameter fails." Before
this file `grep -rn plateau --include=*.py` found one prompt string; QIEA staged the single best
scorer however sharp its peak. core/optimizer/plateau.py states the operationalisation.
"""

from __future__ import annotations

import pytest

from core.optimizer.fitness import WORST_FITNESS
from core.optimizer.param_types import GENE_SPECS
from core.optimizer.plateau import PLATEAU_STEP, check_plateau, neighbours
from core.optimizer.qiea import QIEA
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import T0, TEST_COSTS, CapturingLogger, opt_cfg, zigzag_history

REGIME = RegimeType.STRONG_TREND_UP
CHAMPION = {"ema_fast": 10, "ema_slow": 100, "rsi_period": 10, "rsi_overbought": 70.0,
            "rsi_oversold": 30.0, "atr_multiplier_sl": 2.0, "atr_multiplier_tp": 3.0,
            "momentum_lookback": 20, "breakout_atr_threshold": 1.0, "mean_rev_zscore_entry": 2.0,
            "max_holding_periods": 10}


def _moves(genes) -> dict[tuple[str, int], float]:
    return {(n.gene, n.direction): n.genes[n.gene] for n in neighbours(genes)}


def test_every_gene_moves_ten_percent_each_way_and_nothing_else_moves() -> None:
    assert PLATEAU_STEP == 0.10
    moves = _moves(CHAMPION)
    assert moves == pytest.approx({
        ("ema_fast", -1): 9, ("ema_fast", 1): 11, ("ema_slow", -1): 90, ("ema_slow", 1): 110,
        ("rsi_period", -1): 9, ("rsi_period", 1): 11,
        ("rsi_overbought", -1): 65.0, ("rsi_overbought", 1): 77.0,        # 63 clamps to the 65 floor
        ("rsi_oversold", -1): 27.0, ("rsi_oversold", 1): 33.0,
        ("atr_multiplier_sl", -1): 1.8, ("atr_multiplier_sl", 1): 2.2,
        ("atr_multiplier_tp", -1): 2.7, ("atr_multiplier_tp", 1): 3.3,
        ("momentum_lookback", -1): 18, ("momentum_lookback", 1): 22,
        ("breakout_atr_threshold", -1): 0.9, ("breakout_atr_threshold", 1): 1.1,
        ("mean_rev_zscore_entry", -1): 1.8, ("mean_rev_zscore_entry", 1): 2.2,
        ("max_holding_periods", -1): 9, ("max_holding_periods", 1): 11})
    for n in neighbours(CHAMPION):                                      # ONE gene moves
        assert {k for k in GENE_SPECS if n.genes[k] != CHAMPION[k]} == {n.gene}
        lo, hi, is_int = GENE_SPECS[n.gene]
        assert lo <= n.genes[n.gene] <= hi and isinstance(n.genes[n.gene], int) is is_int


def test_bounds_resolution_and_invariants_are_respected() -> None:
    edge = dict(CHAMPION, rsi_overbought=65.0, max_holding_periods=3, ema_fast=25,
                ema_slow=26, atr_multiplier_sl=2.9)
    moves = _moves(edge)
    assert ("rsi_overbought", -1) not in moves and moves[("rsi_overbought", 1)] == pytest.approx(71.5)
    # 3 -> 2.7 and 3.3 both round back to 3: below the gene's resolution, no neighbour either side
    assert ("max_holding_periods", -1) not in moves and ("max_holding_periods", 1) not in moves
    # decode_gene's rounding: 22.5 -> 22 (half to even), 27.5 -> 28
    assert moves[("ema_fast", -1)] == 22 and moves[("ema_fast", 1)] == 28
    hood = {(n.gene, n.direction): n.genes for n in neighbours(edge)}
    assert hood[("ema_fast", 1)]["ema_slow"] == 29                      # 28 >= 26: slow repaired to 29
    assert hood[("atr_multiplier_sl", 1)]["atr_multiplier_tp"] == pytest.approx(3.29)   # 3.19 >= 3.0
    # tp 3.0 -> 2.7 <= sl 2.9 repairs straight back to 3.0: that side has no neighbour
    assert ("atr_multiplier_tp", -1) not in moves


def test_a_single_dead_neighbour_fails_the_champion_and_is_named() -> None:
    def cliff(genes) -> float:                  # fitness that dies the moment ema_fast passes 10
        return 0.5 if genes["ema_fast"] <= 10 else WORST_FITNESS
    verdict = check_plateau(CHAMPION, cliff)
    assert verdict.tested == 22 and not verdict.holds
    assert [(n.gene, n.direction, n.genes["ema_fast"]) for n in verdict.dead] == [("ema_fast", 1, 11)]
    assert check_plateau(dict(CHAMPION, ema_fast=8), cliff).holds        # 8 -> 7 and 9: a plateau


def _qiea(cls=QIEA) -> tuple[QIEA, CapturingLogger]:
    log = CapturingLogger()
    return cls(opt_cfg(), TEST_COSTS, log, signal_bar_seconds=60, atr_period=14), log


def test_qiea_refuses_the_same_champion_once_its_neighbourhood_dies() -> None:
    """Seed 42 stages a champion on a plateau. Dig a trench at exactly its two ±10%
    max_holding_periods neighbours (real fitness everywhere else): QIEA reaches the SAME champion,
    clears C9 on train and holdout, and the plateau law alone refuses it, naming both."""
    qiea, log = _qiea()
    champ = qiea.evolve(REGIME, zigzag_history(500), seed=42, now=T0)
    assert champ is not None and log.events("EVOLUTION_REJECTED_PLATEAU") == []
    assert len(log.events("EVOLUTION_RUN")) == 1
    m = champ.max_holding_periods
    trench = {int(round(m * 0.9)), int(round(m * 1.1))} - {m}
    assert len(trench) == 2, m                                          # fixture precondition

    class _Trench(QIEA):
        def _train_fitness(self, genes, regime, train, evolved_at):
            if genes["max_holding_periods"] in trench:
                return WORST_FITNESS
            return super()._train_fitness(genes, regime, train, evolved_at)

    trenched, log = _qiea(_Trench)
    assert trenched.evolve(REGIME, zigzag_history(500), seed=42, now=T0) is None
    (event,) = log.events("EVOLUTION_REJECTED_PLATEAU")
    assert event["data"]["champion"] == champ.gene_values()             # the SAME champion
    assert {(d["gene"], d["direction"], d["value"]) for d in event["data"]["dead"]} == {
        ("max_holding_periods", -1, min(trench)), ("max_holding_periods", 1, max(trench))}
    assert log.events("EVOLUTION_REJECTED_OOS") == [] and log.events("EVOLUTION_RUN") == []


def test_a_knife_edge_champion_on_the_real_landscape_is_refused() -> None:
    """Seed 7's zigzag champion (staged before the law) dies when rsi_period moves 10%."""
    qiea, log = _qiea()
    assert qiea.evolve(REGIME, zigzag_history(500), seed=7, now=T0) is None
    (event,) = log.events("EVOLUTION_REJECTED_PLATEAU")
    assert [d["gene"] for d in event["data"]["dead"]] == ["rsi_period"]
    assert event["data"]["neighbours"] == 22
