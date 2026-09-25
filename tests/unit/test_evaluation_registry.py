"""Every QIEA evaluation is recorded, whichever gate ends the run (GAP-P12D-33 [impl], logging only).

Before this, only champions were recorded: a run the train, holdout or plateau gate refused left no
trace of the ~600 configurations it evaluated, so PBO/CSCV could not be computed and the attempt
count was truncated by survivorship. `EVOLUTION_EVALUATIONS` lists each distinct genome with its
train fitness and draw count; the genomes re-simulate to the logged fitness, which is what makes
a later PBO/CSCV pass possible. No gate reads it.
"""

from __future__ import annotations

from core.optimizer.fitness import WORST_FITNESS
from core.optimizer.param_types import GENE_SPECS, RegimeLabelledHistory
from core.optimizer.qiea import QIEA, fitness_window
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import (T0, TEST_COSTS, CapturingLogger, bars_from_closes, opt_cfg,
                                      zigzag_closes, zigzag_history)

REGIME = RegimeType.STRONG_TREND_UP
CFG = opt_cfg()
DRAWS = CFG.population_size * CFG.generations                           # 64


def _evolve(history, seed):
    log = CapturingLogger()
    qiea = QIEA(CFG, TEST_COSTS, log, signal_bar_seconds=60, atr_period=14)
    return qiea, qiea.evolve(REGIME, history, seed=seed, now=T0), log


def _registry(log) -> dict:
    (event,) = log.events("EVOLUTION_EVALUATIONS")
    return event["data"]


def test_a_staged_run_records_every_draw_and_the_rows_re_simulate() -> None:
    history = zigzag_history(500)
    qiea, champ, log = _evolve(history, 5)
    reg = _registry(log)
    assert champ is not None and reg["outcome"] == "EVOLUTION_RUN" and reg["seed"] == 5
    assert reg["genes"] == list(GENE_SPECS)
    assert sum(row[-1] for row in reg["evaluated"]) == DRAWS                 # every draw counted
    assert len({tuple(row[:-2]) for row in reg["evaluated"]}) == len(reg["evaluated"])   # distinct
    best = max(reg["evaluated"], key=lambda row: row[-2])
    assert best[-2] == champ.fitness_score
    assert dict(zip(reg["genes"], best[:-2])) == champ.gene_values()
    assert reg["holdout_trades"] >= CFG.holdout_min_trades
    bars = fitness_window(history, CFG, T0)
    train = bars[:-max(1, round(len(bars) * CFG.holdout_fraction))]
    for row in reg["evaluated"][:5]:                                      # enough to re-run PBO later
        genes = dict(zip(reg["genes"], row[:-2]))
        assert qiea._train_fitness(genes, REGIME, train, T0) == row[-2]


def test_a_train_gated_run_still_records_its_evaluations() -> None:
    """Flat train: every draw is gated out. Before, this run left no trace of what it tried."""
    closes = [1.1] * 400 + zigzag_closes(100, base=1.1)
    _, champ, log = _evolve(RegimeLabelledHistory("EUR_USD", bars_from_closes(closes, REGIME), 60), 42)
    reg = _registry(log)
    assert champ is None and reg["outcome"] == "EVOLUTION_REJECTED_TRAIN"
    assert sum(row[-1] for row in reg["evaluated"]) == DRAWS
    assert {row[-2] for row in reg["evaluated"]} == {WORST_FITNESS}
    assert reg["holdout_trades"] is None and reg["holdout_e_r"] is None


def test_holdout_and_plateau_refusals_record_their_evaluations_too() -> None:
    closes = zigzag_closes(400) + [zigzag_closes(400)[-1]] * 100          # flat holdout tail
    _, champ, log = _evolve(RegimeLabelledHistory("EUR_USD", bars_from_closes(closes, REGIME), 60), 42)
    assert champ is None and _registry(log)["outcome"] == "EVOLUTION_REJECTED_OOS"
    assert sum(row[-1] for row in _registry(log)["evaluated"]) == DRAWS
    _, champ, log = _evolve(zigzag_history(500), 7)                      # the knife-edge champion
    reg = _registry(log)
    assert champ is None and reg["outcome"] == "EVOLUTION_REJECTED_PLATEAU"
    assert reg["holdout_trades"] >= CFG.holdout_min_trades and sum(row[-1] for row in reg["evaluated"]) == DRAWS


def test_repeat_draws_are_counted_not_dropped() -> None:
    """At the production population (20 x 30) QIEA converges and draws genomes repeatedly: each
    distinct genome is one row, and its draw count keeps the attempt tally honest. (The 8 x 8
    fixtures above never repeat a genome, so only this test sees the counting.)"""
    log = CapturingLogger()
    QIEA(opt_cfg(population_size=20, generations=30), TEST_COSTS, log, signal_bar_seconds=60,
         atr_period=14).evolve(REGIME, zigzag_history(500), seed=1, now=T0)
    reg = _registry(log)
    assert len(reg["evaluated"]) < 600                                   # repeats exist
    assert sum(row[-1] for row in reg["evaluated"]) == 600               # and every draw is counted


def test_the_plateau_neighbours_are_recorded_too() -> None:
    """Audit F9: a run that reaches the §5.6 plateau check evaluates each neighbour on train; those
    evaluations are recorded under `neighbours` and re-simulate to their logged fitness. Seed 7's
    two dead neighbours are exactly the WORST rows; a gate-ended run records none."""
    history = zigzag_history(500)
    qiea, champ, log = _evolve(history, 7)
    reg, (refusal,) = _registry(log), log.events("EVOLUTION_REJECTED_PLATEAU")
    assert champ is None and len(reg["neighbours"]) == refusal["data"]["neighbours"] == 22
    assert sum(row[-1] == WORST_FITNESS for row in reg["neighbours"]) == len(refusal["data"]["dead"]) == 2
    bars = fitness_window(history, CFG, T0)
    train = bars[:-max(1, round(len(bars) * CFG.holdout_fraction))]
    for row in reg["neighbours"][:4]:
        assert qiea._train_fitness(dict(zip(reg["genes"], row[:-1])), REGIME, train, T0) == row[-1]
    _, staged, log = _evolve(history, 5)
    assert staged is not None and len(_registry(log)["neighbours"]) > 0
    closes = [1.1] * 400 + zigzag_closes(100, base=1.1)                  # gated on train: no plateau
    _, _, log = _evolve(RegimeLabelledHistory("EUR_USD", bars_from_closes(closes, REGIME), 60), 42)
    assert _registry(log)["neighbours"] == []


def test_nothing_evaluated_nothing_recorded() -> None:
    _, champ, log = _evolve(zigzag_history(80), 1)                       # under fitness_min_bars
    assert champ is None and log.events("EVOLUTION_EVALUATIONS") == []
