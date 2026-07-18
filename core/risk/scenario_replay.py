"""Gap-law scenario replay (ACIS-12 §5–7, master §8.5).

Deterministic replay of `scenario_book.yaml` against the WORST book the
Governor could legally build (C-SWN-1: no conviction/vol-norm/taper softening
credit — those are formula factors a full-conviction book can max out). Pure
functions over config + synthetic paths — no feed, no stores, no RNG. Two
invariants per scenario (C-SWN-7): loss ≤ the human-committed `max_loss_pct_nav`
ceiling AND equity-floor survival. A failing invariant is a HUMAN problem
(resize the caps or re-ratify the ceiling) — nothing is auto-adjusted.

`atr_multiplier_sl_cap` is injected (the caller reads it from
`GENE_SPECS['atr_multiplier_sl']`) so this module keeps zero optimizer imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from config.schemas import GuardrailLimits, InstrumentSpec, Scenario, ScenarioBook


@dataclass(frozen=True)
class ReplayVerdict:
    scenario: str
    kind: str
    instrument: str | None
    worst_book_notional: Decimal
    loss_pct_nav: float
    ceiling_pct_nav: float
    equity_after: Decimal
    floor_survives: bool
    passed: bool


class ScenarioReplayError(Exception):
    """A scenario references something the config cannot honour (ACIS-12 §12)."""


class ScenarioReplay:
    def __init__(self, book: ScenarioBook, guardrails: GuardrailLimits,
                 instruments: dict[str, InstrumentSpec], logger, *,
                 nav: Decimal, equity_floor_usd: float,
                 atr_multiplier_sl_cap: float) -> None:
        self._book = book
        self._g = guardrails
        self._instruments = instruments
        self._log = logger
        self._nav = nav
        self._floor = Decimal(str(equity_floor_usd))
        self._sl_cap = atr_multiplier_sl_cap

    def _worst_notional(self) -> Decimal:
        """C-SWN-1: the largest single-instrument exposure the Governor could
        ever legally hold against the shock = min(cluster_cap, delta_cap) × NAV."""
        frac = min(self._g.cluster_cap_pct, self._g.single_currency_delta_cap_pct) / 100.0
        return Decimal(str(frac)) * self._nav

    def _worst_book_gap_pct(self) -> float:
        """The book's worst same-instrument gap magnitude — the §8.5 allowance
        applied on top of the outage stop geometry (C-SWN-4)."""
        gaps = [abs(float(s.params["gap_pct"])) for s in self._book.scenarios
                if s.kind == "gap_through_stop"]
        return max(gaps) if gaps else 0.0

    def replay_one(self, sc: Scenario) -> ReplayVerdict:
        worst = self._worst_notional()
        inst = sc.params.get("instrument")
        if isinstance(inst, str) and inst not in self._instruments:
            raise ScenarioReplayError(f"scenario {sc.name!r}: unknown instrument {inst!r}")

        if sc.kind == "gap_through_stop":
            loss = worst * Decimal(str(abs(float(sc.params["gap_pct"])) / 100.0))
        elif sc.kind == "flash_crash":
            loss = worst * Decimal(str(abs(float(sc.params["drop_pct"])) / 100.0))
        elif sc.kind == "broker_outage":
            # C-SWN-4: worst stop geometry (SL cap × vol target as price fraction)
            # PLUS the book's worst gap allowance — never "fills at level".
            vol_fracs = [sp.vol_target_atr_frac for sp in self._instruments.values()
                         if sp.vol_target_atr_frac is not None]
            vol_frac = max(vol_fracs) if vol_fracs else 0.0
            stop_frac = self._sl_cap * vol_frac
            gap_frac = self._worst_book_gap_pct() / 100.0
            loss = worst * Decimal(str(stop_frac + gap_frac))
        elif sc.kind == "liquidity_vacuum":
            spec = self._instruments[str(inst)]
            ref_price = float(sc.params["ref_price"])
            spread_cost = (float(sc.params["spread_mult"]) * spec.max_plausible_spread
                           * float(worst) / ref_price)
            loss = Decimal(str(spread_cost))
        else:                                    # unreachable — schema-guarded
            raise ScenarioReplayError(f"unknown kind {sc.kind!r}")

        loss_pct = float(loss) / float(self._nav) * 100.0
        equity_after = self._nav - loss
        floor_survives = equity_after > self._floor
        passed = loss_pct <= sc.max_loss_pct_nav and floor_survives
        verdict = ReplayVerdict(
            scenario=sc.name, kind=sc.kind,
            instrument=inst if isinstance(inst, str) else None,
            worst_book_notional=worst, loss_pct_nav=loss_pct,
            ceiling_pct_nav=sc.max_loss_pct_nav, equity_after=equity_after,
            floor_survives=floor_survives, passed=passed)
        self._log.event("SCENARIO_REPLAY_VERDICT", scenario=sc.name, kind=sc.kind,
                        loss_pct_nav=round(loss_pct, 4),
                        ceiling_pct_nav=sc.max_loss_pct_nav,
                        floor_survives=floor_survives, passed=passed)
        return verdict

    def replay_all(self) -> list[ReplayVerdict]:
        return [self.replay_one(sc) for sc in self._book.scenarios]
