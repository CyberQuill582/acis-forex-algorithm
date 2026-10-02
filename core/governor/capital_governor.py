"""Capital Governor — sovereign allocation (ACIS-05, master §6).

The only layer that sees total portfolio state: Signal -> SizedOrder through independent
factors, then hard limits that clamp only downward. The Risk Monitor's upward edge lands
here and is risk-restrictive only (halt, cut, taper — never a size increase, GAP-0014);
guardrail limits are read-only. `resume` is the ONE human-resume path: the injected
`resume_gate` (the risk ledger's clear) runs first, or no halt lifts (audit F8).
"""

from __future__ import annotations

import json
import math
import uuid
from collections import deque
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Callable, Mapping, Sequence

from config.schemas import AccountRulebook, GovernorConfig, GuardrailLimits, ZonedTime
from core.data.errors import DataQualityError
from core.governor.calendar_gates import weekend_flatten_orders, within_closure_buffer
from core.governor.exposure import delta_contributions, exposure_breach
from core.governor.factors import correlation_factor, liquidity_factor, vol_norm
from core.governor.guards import EntryGuards
from core.governor.units import usd_per_base_unit
from core.governor.marginal_alpha import MarginalAlphaEstimator
from core.governor.portfolio_types import PortfolioState, SizedOrder
from core.data.bars import Bar
from core.signals.indicators import AtrMemo
from core.regime.regime_types import RegimeContext
from core.signals.signal_types import Signal

class ResumeForbiddenError(Exception):
    """resume() without a human token — no agent self-resume (master §12)."""


class CapitalGovernor:
    def __init__(
        self,
        cfg: GovernorConfig,
        guardrails: GuardrailLimits,
        rulebook: AccountRulebook,
        base_unit_usd: float,
        clusters: dict[str, list[str]],
        vol_targets: dict[str, float],
        confidence_veto: float,
        session_boundaries: list[ZonedTime],
        week_close: ZonedTime,
        week_open: ZonedTime,
        holidays: Sequence[date],        # declared whole-day FX closures (audit X5)
        scalp_horizon_s: int,
        atr_period: int,
        blackout: Callable[[str, datetime], bool],
        logger,
        resume_gate: Callable[[str], None],   # clears the halt ledger; raises to refuse
        fixed_units: Callable[[str], Decimal | None] = lambda instrument: None,   # v1.6 min size
    ) -> None:
        self._cfg = cfg
        self._limits = guardrails
        self._rules = rulebook
        self._base_unit = base_unit_usd
        self._clusters = clusters
        self._vol_targets = vol_targets
        self._closure = (week_close, week_open, tuple(holidays))   # every >= 2 h closure
        self._atr = AtrMemo(atr_period)   # GAP-P12D-15: recomputed only when a window changes
        self._log, self._resume_gate = logger, resume_gate
        self.guards = EntryGuards(limits=guardrails, rules=rulebook, cfg=cfg, confidence_veto=confidence_veto,
                                  boundaries=session_boundaries, closure=self._closure,
                                  scalp_horizon_s=scalp_horizon_s, blackout=blackout, logger=logger)
        self._fixed_units = fixed_units
        self.marginal_alpha = MarginalAlphaEstimator(
            cfg.marginal_alpha_window, cfg.marginal_alpha_min_trades, cfg.marginal_alpha_min_bucket)
        self._bars: dict[str, deque[Bar]] = {}
        self._taper_factor = 1.0                   # neutral until Risk exists (phase 9)
        self._alpha_decay = False
        self._open_groups: dict[str, tuple[SizedOrder, SizedOrder]] = {}
        # §10 per-gate skip attribution (C15): every zero-sized order increments
        # the gate that killed it; placed vs zeroed is the layer's take-rate.
        self.skips: dict[str, int] = {}
        self.orders_placed = 0
        self.orders_zeroed = 0

    def take_rate(self) -> dict:
        return {"orders_placed": self.orders_placed, "orders_zeroed": self.orders_zeroed,
                "skips": dict(self.skips)}

    # -- market context (vol-norm input; GAP-0059: BARS, the v2.11 time base) ---- #

    def observe_bar(self, instrument: str, bar: Bar) -> None:
        """Fed completed signal bars by the loop owner (the same aggregation AGON
        uses — one declared time base, one aggregator)."""
        self._bars.setdefault(instrument, deque(maxlen=64)).append(bar)

    # -- the single upward edge (risk-restrictive only, GAP-0014) ---------------- #

    def apply_risk_state(self, *, taper_factor: float | None = None,
                         alpha_decay: bool | None = None) -> None:
        """GAP-0050: None means UNCHANGED — no instruction is ever implicit.
        Clearing an active alpha-decay throttle (a relaxation) must be an
        explicit `alpha_decay=False` and is logged as such; a taper-only call
        can never silently relax anything else."""
        if taper_factor is not None:
            if not math.isfinite(taper_factor) or not (0.0 <= taper_factor <= 1.0):
                self._log.event("RISK_STATE_REJECTED", taper_factor=taper_factor)
                raise DataQualityError(
                    "taper_factor", taper_factor,
                    "the upward edge is risk-restrictive only — taper must be in [0,1]",
                )
            self._taper_factor = taper_factor
        if alpha_decay is not None:
            if alpha_decay and not self._alpha_decay:
                self._log.event("ALPHA_DECAY_THROTTLE", multiplier=0.25)
            elif not alpha_decay and self._alpha_decay:
                self._log.event("ALPHA_DECAY_CLEARED")   # explicit relaxation, audited
            self._alpha_decay = alpha_decay

    @property
    def throttle(self) -> tuple[float, bool]:
        """(taper factor, alpha-decay flag): the Risk edge's state, read by the target path."""
        return self._taper_factor, self._alpha_decay

    def apply_halt(self, scope: str, reason: str) -> None:
        self.guards.halts[scope] = reason
        self._log.event("HALT_APPLIED", scope=scope, reason=reason)

    def apply_session_halt(self, now: datetime, reason: str) -> None:
        """Upward-edge session-scoped halt (ACIS-07 §7, phase 9): no new entries
        until the next session boundary, then auto-clears — the master §8
        daily-drawdown semantics. Risk-restrictive only: it can only ever set
        or extend the halt, never shorten one already in force."""
        until = self.guards.halt_session(now)
        self._log.event("HALT_APPLIED", scope="session", reason=reason,
                        until=until.isoformat())

    def resume(self, human_token: str) -> None:
        if not isinstance(human_token, str) or not human_token.strip():
            raise ResumeForbiddenError("resume requires a human token (master §12)")
        self._resume_gate(human_token)       # the ledger clears first, or nothing lifts (F8)
        self.guards.clear()
        self._log.event("HALT_RESUMED", by="human_token")

    # -- allocation -------------------------------------------------------------- #

    def allocate(self, signal: Signal, portfolio: PortfolioState,
                 regime: RegimeContext, now: datetime) -> SizedOrder:
        order = self._allocate_one(signal, portfolio, regime, now)
        self._log_order(order)
        return order

    def allocate_group(self, signals: tuple[Signal, Signal],
                       portfolio: PortfolioState, regime: RegimeContext,
                       now: datetime) -> tuple[SizedOrder, SizedOrder]:
        """§5.5: both legs or neither, min-size balanced, once per cluster."""
        a, b = signals
        if a.group_id is None or a.group_id != b.group_id:
            raise DataQualityError("group_id", (a.group_id, b.group_id),
                                   "a pair group shares one group_id")
        leg_a = self._allocate_one(a, portfolio, regime, now, in_group=True)
        leg_b = self._allocate_one(b, portfolio, regime, now, in_group=True)
        if leg_a.size_units == 0 or leg_b.size_units == 0:
            blocked = leg_a if leg_a.size_units == 0 else leg_b
            reason = f"group_blocked:{blocked.reason}"
            self._log.event("GROUP_BLOCKED", group_id=a.group_id,
                            leg_reason=blocked.reason)
            out = (self._rewrite(leg_a, Decimal("0"), reason),
                   self._rewrite(leg_b, Decimal("0"), reason))
        else:
            # GAP-P12D-26: balance in USD — the smaller leg's USD notional, in each leg's units
            per_a, per_b = (usd_per_base_unit(s.instrument, s.entry_price, self._bars) for s in (a, b))
            usd = min(leg_a.size_units * per_a, leg_b.size_units * per_b)
            units_a, units_b = ((usd / p).quantize(Decimal("0.01")) for p in (per_a, per_b))
            # GAP-0049: caps on the GROUP AGGREGATE — notional counted ONCE per cluster,
            # currency deltas NETTED across both legs (§7.6: one relationship bet).
            notional_a, notional_b = units_a * per_a, units_b * per_b
            group_notional = max(notional_a, notional_b)
            union_clusters = {c for c, members in self._clusters.items()
                              if a.instrument in members or b.instrument in members}
            net_deltas: dict[str, Decimal] = {}
            for sig, notional in ((a, notional_a), (b, notional_b)):
                for ccy, contrib in delta_contributions(sig, notional).items():
                    net_deltas[ccy] = net_deltas.get(ccy, Decimal("0")) + contrib
            breach = exposure_breach(
                self._limits, portfolio, {c: group_notional for c in union_clusters},
                net_deltas, f"group:{a.group_id}", self._log)
            if breach is not None:
                reason = f"group_blocked:{breach}"
                self._log.event("GROUP_BLOCKED", group_id=a.group_id,
                                leg_reason=breach)
                out = (self._rewrite(leg_a, Decimal("0"), reason),
                       self._rewrite(leg_b, Decimal("0"), reason))
            else:
                out = (self._rewrite(leg_a, units_a, "formula:group"),
                       self._rewrite(leg_b, units_b, "formula:group"))
                self._open_groups[a.group_id] = out
        for o in out:
            self._log_order(o)
        return out

    def check_group_exits(self, coupling_flags: Mapping[str, str],
                          now: datetime) -> tuple[SizedOrder, ...]:
        """GAP-0040: a coupling break / reconvergence closes BOTH legs — never one."""
        closes: list[SizedOrder] = []
        for group_id, reason in coupling_flags.items():
            legs = self._open_groups.pop(group_id, None)
            if legs is None:
                self._log.event("GROUP_EXIT_UNKNOWN", group_id=group_id)
                continue
            if reason not in ("coupling_break", "reconvergence"):
                raise DataQualityError("reason", reason, "unknown group-exit reason")
            for leg in legs:
                closes.append(SizedOrder(
                    order_id=str(uuid.uuid4()), signal_id=leg.signal_id,
                    instrument=leg.instrument, direction=leg.direction,
                    size_units=leg.size_units, entry_price=leg.entry_price,
                    stop_loss=leg.stop_loss, take_profit=leg.take_profit,
                    reason=reason, factors_snapshot=leg.factors_snapshot,
                    sized_at=now, param_set_id=leg.param_set_id,
                    group_id=group_id, action="close",
                ))
            self._log.event("GROUP_EXIT", group_id=group_id, reason=reason)
        return tuple(closes)

    def weekend_flatten(self, portfolio: PortfolioState,
                        now: datetime) -> tuple[SizedOrder, ...]:
        """§9.5: a no-weekend-holding account is flattened from the pre-close entry ban
        on, by reduce-only closes naming each open position (both legs of a pair); called
        every tick, so a close that fails is re-emitted. A position still open once the
        market has closed is surfaced (WEEKEND_FLATTEN_INCOMPLETE), never ignored."""
        if self._rules.weekend_holding_allowed:
            return ()
        closes = weekend_flatten_orders(portfolio, now, *self._closure,
                                        self._cfg.weekend_entry_buffer_s)
        for close in closes:
            self._open_groups.pop(close.group_id, None)
            self._log_order(close)
        if closes:
            closed = within_closure_buffer(now, *self._closure, 0)
            self._log.event("WEEKEND_FLATTEN_INCOMPLETE" if closed else "WEEKEND_FLATTEN",
                            instruments=sorted({c.instrument for c in closes}))
        return closes

    def open_groups(self) -> tuple[str, ...]:
        return tuple(self._open_groups)

    def rebuild_groups(self, portfolio: PortfolioState) -> int:
        """GAP-0052: the registry is in-memory; after a restart, rebuild it from
        the open positions' group_ids so pre-restart groups remain closeable
        (a live pair leg is never orphaned by a process restart)."""
        by_group: dict[str, list] = {}
        for pos in portfolio.open_positions:
            if pos.group_id is not None:
                by_group.setdefault(pos.group_id, []).append(pos)
        rebuilt = 0
        for gid, legs in by_group.items():
            if gid in self._open_groups:
                continue
            if len(legs) != 2:
                self._log.event("GROUP_REBUILD_ORPHAN", group_id=gid, legs=len(legs))
                continue
            self._open_groups[gid] = tuple(
                SizedOrder(
                    order_id=str(uuid.uuid4()), signal_id=f"rebuilt:{gid}",
                    instrument=pos.instrument, direction=pos.direction,
                    size_units=pos.size_units, entry_price=pos.entry_price,
                    stop_loss=pos.stop_loss, take_profit=pos.take_profit,
                    reason="rebuilt_from_portfolio",
                    factors_snapshot=MappingProxyType({"rebuilt": True}),
                    sized_at=portfolio.as_of, param_set_id=pos.param_set_id,
                    group_id=gid,
                ) for pos in legs
            )
            self._log.event("GROUP_REBUILT", group_id=gid)
            rebuilt += 1
        return rebuilt

    # -- internals ----------------------------------------------------------------- #

    def _allocate_one(self, signal: Signal, portfolio: PortfolioState,
                      regime: RegimeContext, now: datetime,
                      in_group: bool = False) -> SizedOrder:
        snapshot: dict = {"half_life_advisory": regime.estimated_half_life_seconds}

        guard = self._guards(signal, portfolio, regime, now, snapshot)
        if guard is not None:
            return self._zero(signal, guard, snapshot, now)

        liq = liquidity_factor(regime.liquidity_state)
        clusters = [c for c, members in self._clusters.items()
                    if signal.instrument in members]
        corr = correlation_factor(clusters, portfolio.per_cluster_exposure,
                                  portfolio.nav, self._limits.cluster_cap_pct)
        regime_f = regime.regime_stability_score * regime.confidence
        ma = self.marginal_alpha.factor()
        if ma.pinned:
            self._log.event("MARGINAL_ALPHA_PINNED", detail=ma.detail)
        vol_f = self._vol_factor(signal.instrument, snapshot)

        snapshot.update(conviction=signal.conviction, liquidity=liq, correlation=corr,
                        regime=regime_f, marginal_alpha=ma.factor,
                        marginal_alpha_pinned=ma.pinned, vol_norm=vol_f,
                        taper=self._taper_factor, base_unit_usd=self._base_unit)

        raw_usd = (self._base_unit * signal.conviction * liq * corr * regime_f
                   * ma.factor * vol_f * self._taper_factor)
        if self._alpha_decay:
            raw_usd *= 0.25
            snapshot["alpha_decay_throttle"] = 0.25
        per_unit = usd_per_base_unit(signal.instrument, signal.entry_price, self._bars)
        if per_unit is None:                          # a cross with no USD leg yet (GAP-P12D-22)
            return self._zero(signal, "no_usd_rate", snapshot, now)
        size_units = (Decimal(str(raw_usd)) / per_unit).quantize(Decimal("0.01"))
        if size_units <= 0:
            return self._zero(signal, "formula_zero", snapshot, now)
        fixed = self._fixed_units(signal.instrument)      # ACIS-05 v1.6: paper and practice
        if fixed is not None:                             # trade one minimum lot (master §5)
            snapshot["formula_units"], size_units = str(size_units), fixed

        # hard limits — clamp only downward (§7.4)
        # §9.5 lot cap: zero, never clamp-to-cap (master §6 overrides are zero-overrides)
        if (self._rules.max_lots is not None
                and size_units / Decimal("100000") > Decimal(str(self._rules.max_lots))):
            self._log.event("LOT_CAP_ZERO", instrument=signal.instrument,
                            size_units=str(size_units), max_lots=self._rules.max_lots)
            return self._zero(signal, "lot_cap", snapshot, now)
        if not in_group:
            # GAP-0049: group legs defer exposure checks to allocate_group, which
            # runs them on the AGGREGATE (cluster counted once, deltas netted) —
            # per-leg checks here would understate the group's true exposure.
            notional = size_units * per_unit          # USD notional
            breach = exposure_breach(
                self._limits, portfolio, {c: notional for c in clusters},
                delta_contributions(signal, notional), signal.instrument, self._log)
            if breach is not None:
                return self._zero(signal, breach, snapshot, now)

        return SizedOrder(
            order_id=str(uuid.uuid4()), signal_id=signal.signal_id,
            instrument=signal.instrument, direction=signal.direction,
            size_units=size_units, entry_price=signal.entry_price,
            stop_loss=signal.stop_loss, take_profit=signal.take_profit,
            reason="formula", factors_snapshot=MappingProxyType(dict(snapshot)),
            sized_at=now, param_set_id=signal.param_set_id,
            group_id=signal.group_id,
        )

    def _guards(self, signal: Signal, portfolio: PortfolioState,
                regime: RegimeContext, now: datetime, snapshot: dict) -> str | None:
        """§7.1 in order (core/governor/guards.py). Returns the zero-reason or None."""
        return self.guards.check(signal.instrument, portfolio, regime, now, strategy=signal.strategy_type,
                                 expires_at=signal.generated_at + timedelta(seconds=signal.valid_for_seconds))

    def _vol_factor(self, instrument: str, snapshot: dict) -> float:
        bars = self._bars.get(instrument)
        if bars is None or len(bars) <= self._atr.period + 1:
            self._log.event("VOL_NORM_PINNED", instrument=instrument)
            snapshot["vol_norm_pinned"] = True
            return 1.0
        seq = list(bars)
        # C16 realized vol = true-range ATR / close over signal BARS (GAP-0059:
        # same unit as the declared per-bar vol_target_atr_frac target)
        a = self._atr(instrument, seq)
        if not math.isfinite(a) or a <= 0:
            self._log.event("VOL_NORM_PINNED", instrument=instrument)
            snapshot["vol_norm_pinned"] = True
            return 1.0
        return vol_norm(a / seq[-1].close, self._vol_targets[instrument])

    def _zero(self, signal: Signal, reason: str, snapshot: dict,
              now: datetime) -> SizedOrder:
        return SizedOrder(
            order_id=str(uuid.uuid4()), signal_id=signal.signal_id,
            instrument=signal.instrument, direction=signal.direction,
            size_units=Decimal("0"), entry_price=signal.entry_price,
            stop_loss=signal.stop_loss, take_profit=signal.take_profit,
            reason=reason, factors_snapshot=MappingProxyType(dict(snapshot)),
            sized_at=now, param_set_id=signal.param_set_id,
            group_id=signal.group_id,
        )

    def _rewrite(self, order: SizedOrder, size: Decimal, reason: str) -> SizedOrder:
        return replace(order, size_units=size, reason=reason)   # a pair leg: always an open

    def _log_order(self, order: SizedOrder) -> None:
        if order.action == "open":
            if order.size_units > 0:
                self.orders_placed += 1
            else:
                # attribution key = the gate in the reason ("group_blocked:x" -> x)
                gate = order.reason.rsplit(":", 1)[-1]
                self.skips[gate] = self.skips.get(gate, 0) + 1
                self.orders_zeroed += 1
        self._log.event(
            "SIZED", order_id=order.order_id, instrument=order.instrument,
            direction=order.direction, size_units=str(order.size_units),
            reason=order.reason, action=order.action, group_id=order.group_id,
            factors=json.dumps({k: (str(v) if isinstance(v, Decimal) else v)
                                for k, v in order.factors_snapshot.items()}),
        )
