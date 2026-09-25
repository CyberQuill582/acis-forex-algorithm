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


def test_every_gene_moves_ten_percent_of_its_range_each_way_and_nothing_else_moves() -> None:
    """The step is 10% of each gene's declared RANGE (audit E6, the lead's delegated ruling):
    ema_fast 45 x 0.1 = 4.5, ema_slow 18, rsi_period 1.4, rsi thresholds 1.5, sl 0.25, tp 0.35,
    momentum 4.5, breakout 0.15, zscore 0.1, max_holding 4.7 — then decode_gene's rounding."""
    assert PLATEAU_STEP == 0.10
    moves = _moves(CHAMPION)
    assert moves == pytest.approx({
        ("ema_fast", -1): 6, ("ema_fast", 1): 14,                        # 5.5 -> 6, 14.5 -> 14 (half-even)
        ("ema_slow", -1): 82, ("ema_slow", 1): 118,
        ("rsi_period", -1): 9, ("rsi_period", 1): 11,                    # 8.6 -> 9, 11.4 -> 11
        ("rsi_overbought", -1): 68.5, ("rsi_overbought", 1): 71.5,
        ("rsi_oversold", -1): 28.5, ("rsi_oversold", 1): 31.5,
        ("atr_multiplier_sl", -1): 1.75, ("atr_multiplier_sl", 1): 2.25,
        ("atr_multiplier_tp", -1): 2.65, ("atr_multiplier_tp", 1): 3.35,
        ("momentum_lookback", -1): 16, ("momentum_lookback", 1): 24,     # 15.5 -> 16, 24.5 -> 24
        ("breakout_atr_threshold", -1): 0.85, ("breakout_atr_threshold", 1): 1.15,
        ("mean_rev_zscore_entry", -1): 1.9, ("mean_rev_zscore_entry", 1): 2.1,
        ("max_holding_periods", -1): 5, ("max_holding_periods", 1): 15})  # 5.3 -> 5, 14.7 -> 15
    for n in neighbours(CHAMPION):                                      # ONE gene moves
        assert {k for k in GENE_SPECS if n.genes[k] != CHAMPION[k]} == {n.gene}
        lo, hi, is_int = GENE_SPECS[n.gene]
        assert lo <= n.genes[n.gene] <= hi and isinstance(n.genes[n.gene], int) is is_int


def test_bounds_and_invariants_are_respected() -> None:
    edge = dict(CHAMPION, rsi_overbought=65.0, max_holding_periods=3, ema_fast=25,
                ema_slow=26, atr_multiplier_sl=2.9)
    moves = _moves(edge)
    assert ("rsi_overbought", -1) not in moves and moves[("rsi_overbought", 1)] == pytest.approx(66.5)
    # 3 - 4.7 rounds to -2 and clamps to the floor 1; 3 + 4.7 = 7.7 -> 8
    assert moves[("max_holding_periods", -1)] == 1 and moves[("max_holding_periods", 1)] == 8
    # decode_gene's rounding: 20.5 -> 20, 29.5 -> 30 (half to even)
    assert moves[("ema_fast", -1)] == 20 and moves[("ema_fast", 1)] == 30
    hood = {(n.gene, n.direction): n.genes for n in neighbours(edge)}
    assert hood[("ema_fast", 1)]["ema_slow"] == 31                      # 30 >= 26: slow repaired to 31
    assert hood[("atr_multiplier_sl", 1)]["atr_multiplier_tp"] == pytest.approx(3.25)   # 3.15 >= 3.0
    # ema_slow 26 - 18 clamps to 20 <= fast 25 and repairs back to 26; tp 3.0 - 0.35 <= sl 2.9
    # repairs back to 3.0: neither side exists
    assert ("ema_slow", -1) not in moves and ("atr_multiplier_tp", -1) not in moves


def test_a_repair_that_carries_the_move_past_the_champion_is_logged_as_it_happened() -> None:
    """Audit F5: tp 2.05 over sl 2.0 — the down-move 2.05 - 0.35 = 1.70 <= sl repairs to
    sl + 0.1 = 2.10, ABOVE the champion. It is a neighbour, and its direction is the actual +1."""
    tight = dict(CHAMPION, atr_multiplier_sl=2.0, atr_multiplier_tp=2.05)
    tp = [(n.direction, n.genes["atr_multiplier_tp"]) for n in neighbours(tight) if n.gene == "atr_multiplier_tp"]
    assert tp == [(1, pytest.approx(2.10)), (1, pytest.approx(2.40))]


def test_a_single_dead_neighbour_fails_the_champion_and_is_named() -> None:
    def cliff(genes) -> float:                  # fitness that dies the moment ema_fast passes 10
        return 0.5 if genes["ema_fast"] <= 10 else WORST_FITNESS
    verdict = check_plateau(CHAMPION, cliff)
    assert verdict.tested == 22 and not verdict.holds
    assert [(n.gene, n.direction, n.genes["ema_fast"]) for n in verdict.dead] == [("ema_fast", 1, 14)]
    assert check_plateau(dict(CHAMPION, ema_fast=5), cliff).holds        # 5 -> floor and 9.5 -> 10: a plateau


def _qiea(cls=QIEA) -> tuple[QIEA, CapturingLogger]:
    log = CapturingLogger()
    return cls(opt_cfg(), TEST_COSTS, log, signal_bar_seconds=60, atr_period=14), log


def test_qiea_refuses_the_same_champion_once_its_neighbourhood_dies() -> None:
    """Seed 5 stages a champion on a plateau. Dig a trench at exactly its two ±10%-of-range
    max_holding_periods neighbours (m ± 4.7, rounded, clamped to 1..48; real fitness everywhere
    else): QIEA reaches the SAME champion, clears C9 on train and holdout, and the plateau law
    alone refuses it, naming both."""
    qiea, log = _qiea()
    champ = qiea.evolve(REGIME, zigzag_history(500), seed=5, now=T0)
    assert champ is not None and log.events("EVOLUTION_REJECTED_PLATEAU") == []
    assert len(log.events("EVOLUTION_RUN")) == 1
    m = champ.max_holding_periods
    trench = {max(1, int(round(m - 4.7))), min(48, int(round(m + 4.7)))} - {m}
    assert len(trench) == 2, m                                          # fixture precondition

    class _Trench(QIEA):
        def _train_fitness(self, genes, regime, train, evolved_at):
            if genes["max_holding_periods"] in trench:
                return WORST_FITNESS
            return super()._train_fitness(genes, regime, train, evolved_at)

    trenched, log = _qiea(_Trench)
    assert trenched.evolve(REGIME, zigzag_history(500), seed=5, now=T0) is None
    (event,) = log.events("EVOLUTION_REJECTED_PLATEAU")
    assert event["data"]["champion"] == champ.gene_values()             # the SAME champion
    assert {(d["gene"], d["direction"], d["value"]) for d in event["data"]["dead"]} == {
        ("max_holding_periods", -1, min(trench)), ("max_holding_periods", 1, max(trench))}
    assert log.events("EVOLUTION_REJECTED_OOS") == [] and log.events("EVOLUTION_RUN") == []


def test_a_knife_edge_champion_on_the_real_landscape_is_refused() -> None:
    """Seed 7's zigzag champion (staged before the law) dies when ema_fast or rsi_period moves
    10% of its range."""
    qiea, log = _qiea()
    assert qiea.evolve(REGIME, zigzag_history(500), seed=7, now=T0) is None
    (event,) = log.events("EVOLUTION_REJECTED_PLATEAU")
    assert sorted(d["gene"] for d in event["data"]["dead"]) == ["ema_fast", "rsi_period"]
    assert event["data"]["neighbours"] == 22
