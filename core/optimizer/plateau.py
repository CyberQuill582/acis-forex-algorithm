"""The §5.6 parameter-plateau law (master §5.6, GAP-P12D-34): "Parameter plateaus required — a
strategy that dies at ±10% on any parameter fails."

Mental model (the operationalisation interprets spec prose; it is flagged for owner ratification
in BUILDER_REPORT_2026-09-24.md and drafted as an ACIS-03 amendment there):
  * A NEIGHBOUR is the champion with ONE gene moved by ±`PLATEAU_STEP` (10%) of that gene's
    declared GENE_SPECS RANGE (hi − lo), so the step means the same thing on every gene (the lead's
    delegated ruling on audit E6; a step of 10% of the VALUE moved rsi_overbought ~45% of its range
    and ema_fast ~7%). It is made valid exactly as QIEA makes a decoded gene valid: an integer gene
    is rounded as `decode_gene` rounds it, the value is clamped into its range, and the cross-field
    invariants (ema_slow > ema_fast, tp > sl) are repaired by `repair_invariants`. A neighbour is
    therefore never invalid, and a repair may move a second gene.
  * A move that lands back on the champion (the gene sits on its range bound, or the repair undoes
    it) is not a neighbour: that side has nothing to test.
  * A neighbour DIES when it fails the C9 gate on the champion's own TRAIN window: the fitness
    function scores it WORST_FITNESS (fewer than `fitness_min_trades` closed trades, or E_R <=
    `expectancy_min_r`). ANY dead neighbour fails the champion ("on any parameter").
  * Every gene is perturbed, including the three the v1 fitness harness does not read (GAP-0035):
    while that gap is open their neighbours trade exactly like the champion and cannot die; when it
    closes they bind with no change here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from core.optimizer.fitness import WORST_FITNESS
from core.optimizer.param_types import GENE_SPECS, repair_invariants

PLATEAU_STEP = 0.10                      # master §5.6 "±10%", as a share of each gene's RANGE (E6)

Genes = Mapping[str, "float | int"]


@dataclass(frozen=True)
class Neighbour:
    gene: str
    direction: int                       # +1: the gene moved up, -1: down
    genes: Mapping[str, "float | int"]   # the complete, valid neighbour


@dataclass(frozen=True)
class PlateauVerdict:
    tested: int                          # neighbours evaluated
    dead: tuple[Neighbour, ...]          # the ones that failed the C9 gate on train

    @property
    def holds(self) -> bool:
        return not self.dead


def _moved(name: str, value: float) -> float | int:
    lo, hi, is_int = GENE_SPECS[name]
    if is_int:
        v = int(round(value))                                  # decode_gene's rounding
        return int(lo) if v < lo else int(hi) if v > hi else v
    return lo if value < lo else hi if value > hi else value


def neighbours(genes: Genes) -> tuple[Neighbour, ...]:
    """Every distinct one-gene ±10%-of-range neighbour of `genes`, in GENE_SPECS order, the
    down-move before the up-move."""
    out: list[Neighbour] = []
    for name, (lo, hi, _) in GENE_SPECS.items():
        for intended in (-1, 1):
            moved = repair_invariants({**genes, name: _moved(name, genes[name] + intended * PLATEAU_STEP * (hi - lo))})
            if moved != dict(genes) and all(moved != n.genes for n in out):
                out.append(Neighbour(name, intended, moved))
    return tuple(out)


def check_plateau(genes: Genes, fitness: Callable[[Genes], float]) -> PlateauVerdict:
    """Score every neighbour with `fitness` (the champion's train-window fitness); the verdict
    names each neighbour that died, so a refusal is explainable gene by gene."""
    hood = neighbours(genes)
    return PlateauVerdict(tested=len(hood),
                          dead=tuple(n for n in hood if fitness(n.genes) <= WORST_FITNESS))
