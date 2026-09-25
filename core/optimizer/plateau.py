"""The master §5.6 parameter-plateau law, specified as ACIS-03 v1.5 §6.4 (GAP-P12D-34).

Mental model (the operationalisation is the lead's delegated ruling D8, for the owner's review):
  * A NEIGHBOUR is the champion with ONE gene moved by ±`PLATEAU_STEP` (10%) of that gene's
    declared GENE_SPECS RANGE (hi − lo), the same meaning on every gene (audit E6). It is made
    valid exactly as QIEA makes a decoded gene valid: an integer gene is rounded as `decode_gene`
    rounds, the value is clamped into its range, and `repair_invariants` restores ema_slow >
    ema_fast and tp > sl. A neighbour is never invalid, and a repair may move a second gene.
  * A move that lands back on the champion (a range bound, or a repair that undoes it) is not a
    neighbour. A repair can carry a move PAST the champion, so `direction` is the gene's ACTUAL
    signed move after repair, never the intended one (audit F5).
  * A neighbour DIES when it fails C9 on the champion's own TRAIN window (fitness WORST_FITNESS:
    too few closed trades, or E_R <= `expectancy_min_r`). ANY dead neighbour fails the champion.
  * Every gene is perturbed, including the three the v1 harness does not read (GAP-0035): until
    that closes, their neighbours trade like the champion and cannot die.
  * Passing proves nothing by itself: it is a fragility veto, not evidence (VALIDATOR, GAP-P12D-33).
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
    direction: int                       # +1 / -1: the ACTUAL move of `gene` after repair (F5)
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
    intended down-move before the up-move; `direction` is the actual move after repair."""
    out: list[Neighbour] = []
    for name, (lo, hi, _) in GENE_SPECS.items():
        for intended in (-1, 1):
            moved = repair_invariants({**genes, name: _moved(name, genes[name] + intended * PLATEAU_STEP * (hi - lo))})
            if moved != dict(genes) and all(moved != n.genes for n in out):
                out.append(Neighbour(name, 1 if moved[name] > genes[name] else -1, moved))
    return tuple(out)


def check_plateau(genes: Genes, fitness: Callable[[Genes], float]) -> PlateauVerdict:
    """Score every neighbour with `fitness` (the champion's train-window fitness); the verdict
    names each neighbour that died, so a refusal is explainable gene by gene."""
    hood = neighbours(genes)
    return PlateauVerdict(tested=len(hood),
                          dead=tuple(n for n in hood if fitness(n.genes) <= WORST_FITNESS))
