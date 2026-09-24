"""Quantum-Inspired Evolutionary Algorithm (ACIS-03 §6, master §5).

Canonical Han & Kim QEA shape (proven-parts law): Q-bit probability
population -> observe/collapse -> fixed-point decode into GENE_SPECS ranges
(clamp + invariant repair, never emitted invalid) -> fitness on the TRAIN
split -> rotation toward the best observed individual. Stdlib random only;
every run's seed is logged (EVOLUTION_RUN) — same seed + same history =>
identical champion (reproducibility, §3 determinism scope).
"""

from __future__ import annotations

import json
import math
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from config.schemas import OptimizerConfig
from core.data.errors import DataQualityError
from core.optimizer.costs import CostModel
from core.optimizer.fitness import (
    WORST_FITNESS,
    expectancy_r,
    fitness_of,
    passes_expectancy_gate,
    simulate_trades,
)
from core.optimizer.param_types import (
    GENE_SPECS,
    LabelledBar,
    ParamSet,
    RegimeLabelledHistory,
    repair_invariants,
)
from core.optimizer.plateau import check_plateau
from core.regime.regime_types import RegimeType

_GENE_ORDER = list(GENE_SPECS)
# GAP-0037: genuine qubit-angle encoding. Each bit is an angle theta with
# P(observe 1) = sin^2(theta); the rotation gate turns theta toward the best
# observed individual by rotation_angle_rad (Han–Kim-style simplified rotation:
# comparison is always against the generation best, so the delta-theta lookup
# table reduces to a fixed signed step). Clamped away from saturation so no
# bit becomes unrecoverable.
_THETA_MIN, _THETA_MAX = 0.05, math.pi / 2 - 0.05
_PARAM_ID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000ace5")


def decode_gene(name: str, raw: float) -> float | int:
    """Fixed-point decode of raw in [0,1] into the gene's range; clamps out-of-range raws."""
    lo, hi, is_int = GENE_SPECS[name]
    raw = 0.0 if raw < 0.0 else 1.0 if raw > 1.0 else raw
    value = lo + raw * (hi - lo)
    if is_int:
        v = int(round(value))
        return int(lo) if v < lo else int(hi) if v > hi else v
    return value


def fitness_window(history: RegimeLabelledHistory, cfg: OptimizerConfig,
                   now: datetime) -> tuple[LabelledBar, ...]:
    """The bars evolution reads (master §5 v2.18, GAP-P12D-29): every target-regime bar that
    opens within `fitness_span_days` before `now`. A time span, never a bar count — a fixed
    500 bars left the 1-minute holdout too few trades to ever stage a champion — and never
    full history."""
    since = now - timedelta(days=cfg.fitness_span_days)
    return tuple(b for b in history.bars if b.ts >= since)


@dataclass
class _Individual:
    bits: list[int]
    genes: dict[str, float | int]
    fitness: float


class QIEA:
    """Per-regime evolution. `evolve()` returns a ParamSet or None (§6.3 gates)."""

    def __init__(self, cfg: OptimizerConfig, costs: CostModel, logger, *,
                 signal_bar_seconds: int, atr_period: int) -> None:
        # GAP-0071: the fitness bar and ATR period are the SAME declared units
        # AGON spends the evolved genes on (signals.signal_bar_seconds /
        # signals.atr_period) — wired at composition, refused on mismatch.
        self._cfg = cfg
        self._costs = costs
        self._log = logger
        self._bar_seconds = signal_bar_seconds
        self._atr_period = atr_period

    # -- decode ------------------------------------------------------------ #

    def _decode_bits(self, bits: Sequence[int]) -> dict[str, float | int]:
        res = self._cfg.qbit_resolution
        max_int = (1 << res) - 1
        genes: dict[str, float | int] = {}
        for gi, name in enumerate(_GENE_ORDER):
            chunk = bits[gi * res : (gi + 1) * res]
            intval = 0
            for b in chunk:
                intval = (intval << 1) | b
            genes[name] = decode_gene(name, intval / max_int)
        return repair_invariants(genes)

    def _observe(self, thetas: list[float], rng: random.Random) -> list[int]:
        """Collapse: each qubit observes 1 with probability sin^2(theta)."""
        return [1 if rng.random() < math.sin(t) ** 2 else 0 for t in thetas]

    @staticmethod
    def rotate_toward(thetas: list[float], best_bits: Sequence[int], step: float) -> list[float]:
        """The rotation gate: turn each qubit angle toward the best individual's
        bit (1 => toward pi/2, 0 => toward 0), clamped off saturation."""
        out = []
        for t, b in zip(thetas, best_bits):
            t = t + step if b == 1 else t - step
            out.append(_THETA_MIN if t < _THETA_MIN else _THETA_MAX if t > _THETA_MAX else t)
        return out

    # -- evolution --------------------------------------------------------- #

    def evolve(
        self,
        regime: RegimeType,
        history: RegimeLabelledHistory,
        *,
        seed: int,
        now: datetime | None = None,
    ) -> ParamSet | None:
        cfg = self._cfg
        if history.bar_seconds != self._bar_seconds:
            raise DataQualityError(
                "bar_seconds", history.bar_seconds,
                f"history bar unit must equal the declared signal bar "
                f"({self._bar_seconds}s) — GAP-0071")
        for bar in history.bars:
            if bar.regime is not regime:
                raise DataQualityError("bars", bar.regime, f"mislabelled bar (target {regime.value})")
        evolved_at = now or datetime.now(timezone.utc)
        bars = fitness_window(history, cfg, evolved_at)
        if len(bars) < cfg.fitness_min_bars:
            self._log.event(
                "EVOLUTION_INSUFFICIENT_DATA",
                regime=regime.value, bars=len(bars), required=cfg.fitness_min_bars,
                span_days=cfg.fitness_span_days,
            )
            return None

        n_hold = max(1, round(len(bars) * cfg.holdout_fraction))
        train, holdout = bars[:-n_hold], bars[-n_hold:]

        rng = random.Random(seed)
        n_bits = len(_GENE_ORDER) * cfg.qbit_resolution
        thetas = [math.pi / 4] * n_bits  # sin^2(pi/4) = 0.5: unbiased superposition
        best: _Individual | None = None

        for _generation in range(cfg.generations):
            for _ in range(cfg.population_size):
                bits = self._observe(thetas, rng)
                genes = self._decode_bits(bits)
                fit = self._train_fitness(genes, regime, train, evolved_at)
                if best is None or fit > best.fitness:
                    best = _Individual(bits, genes, fit)
            thetas = self.rotate_toward(thetas, best.bits, cfg.rotation_angle_rad)

        # GAP-0038: the champion must itself clear the C9 gate on TRAIN — when
        # every individual is gated out the "best" is an arbitrary first collapse
        # and must never reach the (small) holdout, let alone staging.
        if best.fitness <= WORST_FITNESS:
            self._log.event(
                "EVOLUTION_REJECTED_TRAIN",
                regime=regime.value, generations=cfg.generations, seed=seed,
            )
            return None

        champion = self._build_paramset(best.genes, regime, best.fitness, seed, evolved_at)

        # §6.3 holdout gate: the champion must carry expectancy out-of-sample.
        # Indicators warm up on the train bars; only entries in the tail count.
        hold_pnls = simulate_trades(champion, bars, self._costs,
                                    entry_start=len(train),
                                    atr_period=self._atr_period)
        hold_res = expectancy_r(hold_pnls)
        if not passes_expectancy_gate(hold_res, cfg.holdout_min_trades, cfg.expectancy_min_r):
            self._log.event(
                "EVOLUTION_REJECTED_OOS",
                regime=regime.value, holdout_trades=hold_res.n_trades,
                holdout_e_r=None if hold_res.e_r != hold_res.e_r else round(hold_res.e_r, 4),
            )
            return None

        # §5.6 plateau law (GAP-P12D-34): a champion whose ±10% neighbourhood dies on the SAME
        # train window is a peak, not a strategy — refused, with every dead neighbour named.
        plateau = check_plateau(best.genes, lambda g: self._train_fitness(g, regime, train, evolved_at))
        if not plateau.holds:
            self._log.event(
                "EVOLUTION_REJECTED_PLATEAU",
                regime=regime.value, seed=seed, neighbours=plateau.tested, champion=best.genes,
                dead=[{"gene": n.gene, "direction": n.direction, "value": n.genes[n.gene]}
                      for n in plateau.dead],
            )
            return None

        self._log.event(
            "EVOLUTION_RUN",
            regime=regime.value, best_fitness=round(best.fitness, 6),
            generations=cfg.generations, seed=seed,
            train_bars=len(train), holdout_bars=len(holdout),
        )
        return champion

    def _train_fitness(
        self,
        genes: dict[str, float | int],
        regime: RegimeType,
        train: Sequence[LabelledBar],
        evolved_at: datetime,
    ) -> float:
        probe = self._build_paramset(genes, regime, 0.0, 0, evolved_at)
        return fitness_of(probe, train, self._costs, self._cfg,
                          atr_period=self._atr_period)

    def _build_paramset(
        self,
        genes: dict[str, float | int],
        regime: RegimeType,
        fitness: float,
        seed: int,
        evolved_at: datetime,
    ) -> ParamSet:
        # GAP-0036: the id is derived from the param CONTENT (genes + regime +
        # seed + evolved_at), so distinct param sets always get distinct ids and
        # the §4 trade→params audit link is genuinely unique; same seed + same
        # history + same `now` still reproduces the same id (§3 determinism).
        identity = json.dumps(
            {"genes": genes, "regime": regime.value, "seed": seed,
             "evolved_at": evolved_at.isoformat()},
            sort_keys=True,
        )
        return ParamSet(
            **genes,
            regime=regime,
            param_set_id=str(uuid.uuid5(_PARAM_ID_NAMESPACE, identity)),
            fitness_score=fitness,
            evolved_at=evolved_at,
        )
