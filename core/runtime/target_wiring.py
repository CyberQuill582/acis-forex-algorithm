"""Build the target-position path's slow loop from config (ACIS-05 v1.7 §6.4; R1.6), for wiring.py.

Invariants:
  * The path exists only with a `targets:` block AND an attached venue: the daily history is the
    venue's own bars (ACIS-04 v1.6 §4b). Without a venue it is logged and left off.
  * The config is checked against the account actually attached (config/targets_schema.py): the
    universe is the enabled set (R6-3) and the rulebook declares capital_ref and vol_target.
  * Lots are the venue's per symbol; in paper and practice the target is capped at one venue
    minimum lot (master §5 D-a), read from the mode at decision time, so a mode change applies.
  * The family's provenance records are registered at build (idempotent), and the loop refuses
    to target with an unregistered family (ACIS-04 §4b: ids registered at emission).
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from config.targets_schema import check_targets
from core.data.ctrader.history import hourly_bars
from core.data.rates import load_rate_table
from core.governor.target_gate import target_orders
from core.runtime.history_store import HistoryStore
from core.runtime.target_decision import BookSizing, Lots, class_equal_weights
from core.runtime.target_loop import EngineView, Member, TargetLoop
from core.signals.daily import slot_of
from core.signals.families import register_family


def build_targets(cfg, *, root: Path, venue, calendars, prov, governor, risk, executor, nvma, runtime, mode,
                  now_fn, logger, governor_log):
    t = cfg.system.targets
    if t is None:
        return None
    if venue is None:
        logger.event("TARGETS_NO_VENUE", family=t.family)
        return None
    check_targets(cfg)
    register_family(prov)
    rulebook = cfg.platform_rules.accounts[cfg.system.active_account]
    specs = {i: cfg.instruments.instruments[i] for i in t.universe}
    members = {i: Member(i, sp.asset_class, sp.quote_ccy, slot_of(i, sp.asset_class),
                         lambda now, cal=calendars[sp.calendar]: cal.session_at(now) != "closed")
               for i, sp in specs.items()}
    sizing = BookSizing(capital_ref=rulebook.initial_capital, vol_target=rulebook.vol_target_annual,
                        idm=t.idm, buffer=t.buffer, weights=class_equal_weights({i: sp.asset_class for i, sp in specs.items()}))

    def lots_of(instrument: str) -> Lots | None:
        spec = venue.attached.specs.get(instrument)
        if spec is None:
            return None
        capped = mode.mode in ("paper", "practice")
        return Lots(spec.step_units, spec.min_units, spec.min_units if capped else None)

    async def fetch(instrument, start, end):
        spec = venue.attached.specs[instrument]
        return await hourly_bars(venue.session, spec.symbol_id, spec.digits, start, end, logger=logger)

    view = EngineView(
        held_of=lambda i: next((p for p in risk.positions() if p.instrument == i), None),
        busy=lambda: frozenset(executor.busy), marks=lambda: runtime.marks, portfolio=runtime.portfolio,
        regime_of=nvma.regime_store.get, submit=executor.submit, flatten=executor.submit_flatten,
        clock_ok=runtime.clock_verified)
    gate = partial(target_orders, governor, limits=cfg.guardrails, rules=rulebook, clusters=cfg.instruments.clusters,
                   stop_mult=cfg.system.signals.tsmom_disaster_stop_atr, logger=governor_log)
    return TargetLoop(
        members=members, store=HistoryStore(root / "data" / "runtime" / "targets.db"), fetch=fetch,
        rates=lambda: load_rate_table(root / t.macro_dir, t.rate_max_stale_days,
                                       t.rate_max_stale_days_weekly), sizing=sizing,
        lots_of=lots_of, gate=gate, engine=view, family=t.family, registered=prov.is_registered,
        history_days=t.history_days, settle_s=t.settle_s, slot_grace_s=t.slot_grace_s,
        atr_period=cfg.system.signals.atr_period, now_fn=now_fn, logger=logger)
