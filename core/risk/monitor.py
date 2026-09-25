"""Risk Monitor — metrics, snapshot, ingest, heartbeat (ACIS-07 §3/§7).

Watch everything, size nothing, and be the one component allowed to say stop.
Consumes `FillReport`s (position/trade/PnL accounting, F17 Decimal) and broker
account truth; computes the `RiskSnapshot`; drives the equity breaker, drawdown
HALTs, the ratified taper, alpha-decay throttle, and Tier-G flatten through the
single upward `HaltSink`. Owns the §8.6 heartbeat and restart reconciliation.

Accounting note (recorded as GAP at phase 9): realised PnL is booked in the
instrument's QUOTE currency and treated as account currency — exact for
USD-quoted pairs (EUR_USD, XAU_USD); multi-quote FX→USD conversion is the
phase-11 cost-calibration / adapter concern (master §13). Broker `equity` is
always authoritative for the breaker and drawdown series (§9.5).
"""

from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from config.schemas import RiskConfig, GuardrailLimits
from core.data.errors import DataQualityError
from core.execution.venue import BrokerAccount, BrokerPosition, FillReport, FillStatus
from core.risk.alpha_decay import AlphaDecayDetector
from core.risk.exposure_metrics import max_cluster_pct, portfolio_var_pct
from core.risk.guardrails import GuardrailContext, Guardrails
from core.risk.risk_types import RiskPosition, RiskSnapshot, Trade
from core.risk.sink import HaltSink
from core.risk.usd_conversion import usd_factor


@dataclass
class _Pos:
    signed_units: Decimal
    avg_price: float
    opened_at: datetime
    param_set_id: str
    group_id: str | None
    stop_loss: float | None
    take_profit: float | None


class RiskMonitor:
    def __init__(self, cfg: RiskConfig, limits: GuardrailLimits,
                 guardrails: Guardrails, alpha: AlphaDecayDetector,
                 sink: HaltSink, clusters: dict[str, list[str]],
                 session_id: str, logger, *, store=None) -> None:
        self._cfg = cfg
        self._limits = limits
        self._guards = guardrails
        self._alpha = alpha
        self._sink = sink
        self._clusters = clusters
        self._session_id = session_id
        self._log = logger
        self._store = store
        self._positions: dict[str, _Pos] = {}
        self._order_meta: dict[str, dict] = {}   # order_id -> metadata for enrichment
        self._trades: list[Trade] = []
        self._realised_by_day: dict[object, Decimal] = {}
        self._marks: dict[str, deque[float]] = {}
        self._slippage: deque[float] = deque(maxlen=cfg.slippage_window)
        self._alpha_armed_prev = False

    # -- order metadata (so ingest can attach param_set_id/group/sl/tp) ------- #

    def note_order(self, order) -> None:
        self._order_meta[order.order_id] = {
            "param_set_id": order.param_set_id, "group_id": order.group_id,
            "stop_loss": order.stop_loss, "take_profit": order.take_profit,
            "action": order.action,
        }

    # -- ingest (FillReport → positions/trades/PnL) --------------------------- #

    def ingest(self, fill: FillReport) -> None:
        if fill.status in (FillStatus.REJECTED, FillStatus.CANCELLED):
            return                                  # a rejection is a report, not a fill
        if fill.filled_units <= 0:
            return
        meta = self._order_meta.get(fill.order_id, {})
        self._apply_fill(fill, meta)

    def _apply_fill(self, fill: FillReport, meta: dict) -> None:
        inst = fill.instrument
        incoming = Decimal(fill.direction) * fill.filled_units
        pos = self._positions.get(inst)
        if pos is None:
            self._positions[inst] = _Pos(
                signed_units=incoming, avg_price=fill.fill_price,
                opened_at=fill.fill_time,
                param_set_id=meta.get("param_set_id", "unknown:fill"),
                group_id=meta.get("group_id"),
                stop_loss=meta.get("stop_loss"), take_profit=meta.get("take_profit"))
            return
        same_dir = (pos.signed_units > 0) == (incoming > 0)
        if same_dir:
            total = pos.signed_units + incoming
            pos.avg_price = ((pos.avg_price * float(abs(pos.signed_units))
                              + fill.fill_price * float(abs(incoming)))
                             / float(abs(total)))
            pos.signed_units = total
            return
        # opposite side: close up to the existing size, book realised PnL
        closing = min(abs(incoming), abs(pos.signed_units))
        pos_dir = 1 if pos.signed_units > 0 else -1
        realised_quote = (Decimal(str(fill.fill_price)) - Decimal(str(pos.avg_price))) \
            * closing * Decimal(pos_dir)
        realised = self._to_usd(inst, realised_quote, fill.fill_price)  # GAP-P9E-04
        self._book_trade(inst, pos, closing, pos_dir, fill, realised)
        remaining_pos = abs(pos.signed_units) - closing
        leftover_incoming = abs(incoming) - closing
        if remaining_pos > 0:
            pos.signed_units = Decimal(pos_dir) * remaining_pos
        elif leftover_incoming > 0:                 # flip: open the remainder
            new_dir = 1 if incoming > 0 else -1
            self._positions[inst] = _Pos(
                signed_units=Decimal(new_dir) * leftover_incoming,
                avg_price=fill.fill_price, opened_at=fill.fill_time,
                param_set_id=meta.get("param_set_id", "unknown:fill"),
                group_id=meta.get("group_id"),
                stop_loss=meta.get("stop_loss"), take_profit=meta.get("take_profit"))
        else:
            del self._positions[inst]

    def _book_trade(self, inst, pos, closing, pos_dir, fill, realised) -> None:
        day = fill.fill_time.astimezone(timezone.utc).date()
        self._realised_by_day[day] = self._realised_by_day.get(day, Decimal("0")) + realised
        self._trades.append(Trade(
            instrument=inst, direction=pos_dir, units=closing,
            entry_price=pos.avg_price, exit_price=fill.fill_price,
            opened_at=pos.opened_at, closed_at=fill.fill_time,
            pnl=realised, param_set_id=pos.param_set_id))
        self._log.event("TRADE_CLOSED", instrument=inst, units=str(closing),
                        pnl=str(realised), param_set_id=pos.param_set_id)

    def observe_mark(self, instrument: str, price: float) -> None:
        self._marks.setdefault(instrument, deque(maxlen=self._cfg.var_window)).append(price)

    def observe_slippage(self, bps: float) -> None:
        self._slippage.append(abs(bps))

    # -- evaluate ------------------------------------------------------------- #

    def evaluate(self, account: BrokerAccount, now: datetime, *,
                 marks: dict[str, float] | None = None,
                 tierg_flatten: dict | None = None) -> RiskSnapshot:
        now = now.astimezone(timezone.utc)
        marks = marks or {}
        for inst, px in marks.items():
            self.observe_mark(inst, px)
        nav = account.equity if account.equity > 0 else Decimal("1")

        unrealised = self._unrealised(marks)
        day = now.date()
        daily_realised = self._realised_by_day.get(day, Decimal("0"))
        daily_pnl = daily_realised + unrealised

        per_inst_dd = self._per_instrument_drawdown(marks, nav)
        notional = {inst: self._notional(inst, pos, marks) for inst, pos in self._positions.items()}
        var_pct = portfolio_var_pct(notional, self._marks, float(nav),
                                    var_horizon_seconds=self._cfg.var_horizon_seconds,
                                    eval_cadence_s=self._cfg.eval_cadence_s)
        cluster_pct = max_cluster_pct(notional, self._clusters, float(nav))
        slip = (sum(self._slippage) / len(self._slippage)) if self._slippage else 0.0

        outcome = self._guards.check(GuardrailContext(
            now=now, equity=account.equity, balance=account.balance, nav=nav,
            per_instrument_drawdown_pct=per_inst_dd, var_pct=var_pct,
            max_cluster_pct=cluster_pct, slippage_slope_bps=slip,
            tierg_flatten=tierg_flatten or {}))

        # alpha decay — explicit set/clear on the upward edge (GAP-0050, C-RSK-9)
        reading = self._alpha.evaluate(self._trades)
        if reading.flag and not self._alpha_armed_prev:
            self._log.event("ALPHA_DECAY_DETECTED", s_recent=reading.mean_sigma_recent,
                            s_baseline=reading.mean_sigma_baseline, n=reading.n_recent)
            self._sink.apply_risk_state(alpha_decay=True)
        elif not reading.flag and self._alpha_armed_prev:
            self._log.event("ALPHA_DECAY_RECOVERED", s_recent=reading.mean_sigma_recent,
                            s_baseline=reading.mean_sigma_baseline)
            self._sink.apply_risk_state(alpha_decay=False)
        self._alpha_armed_prev = reading.flag

        engine_daily_dd = next((s.measured_pct for s in outcome.platform_drawdown
                                if s.rule_key == "engine:daily"), 0.0)
        open_dd = max(0.0, -float(unrealised)) / float(nav) * 100.0
        recent = self._trades[-self._cfg.alpha_decay_recent_window:]
        win_rate = (sum(1 for t in recent if t.pnl > 0) / len(recent)) if recent else 0.0

        snap = RiskSnapshot(
            timestamp=now, daily_pnl=daily_pnl,
            daily_drawdown_pct=engine_daily_dd, open_drawdown_pct=open_dd,
            total_drawdown_pct=engine_daily_dd + open_dd,
            portfolio_var_1pct=var_pct, max_correlated_cluster_pct=cluster_pct,
            rolling_mean_sigma_50t=reading.mean_sigma_recent, rolling_win_rate_50t=win_rate,
            alpha_decay_flag=reading.flag, alpha_decay_state=reading.state,
            slippage_slope_alert=outcome.slippage_slope_alert,
            equity=account.equity, equity_floor_breached=outcome.equity_floor_breached,
            instruments_halted=outcome.instruments_halted,
            platform_drawdown=tuple(s for s in outcome.platform_drawdown
                                    if s.rule_key != "engine:daily"),
            taper_factor=outcome.taper_factor, session_id=self._session_id)
        if self._store is not None:        # after the guard acted; never gates it (audit F0)
            self._store.persist_evaluate(                     # (GAP-0050 / GAP-P12D-55)
                snap, alpha_armed=self._alpha.armed, taper_factor=outcome.taper_factor,
                anchors=self._guards.series.export(), log=self._log)
        return snap

    # -- quote→USD conversion (GAP-P9E-04 / rescoped GAP-0092) ---------------- #

    def _to_usd(self, instrument: str, amount_quote: Decimal, price: float) -> Decimal:
        factor = usd_factor(instrument, price)
        if factor is None:
            self._log.event("CONVERSION_UNAVAILABLE", instrument=instrument,
                            note="cross pair — quote-ccy used, phase-11 FX table owed")
            return amount_quote
        return amount_quote * Decimal(str(factor))

    # -- metrics -------------------------------------------------------------- #

    def _unrealised(self, marks: dict[str, float]) -> Decimal:
        total = Decimal("0")
        for inst, pos in self._positions.items():
            mark = marks.get(inst)
            if mark is None:
                continue
            pos_dir = 1 if pos.signed_units > 0 else -1
            upnl_quote = (Decimal(str(mark)) - Decimal(str(pos.avg_price))) \
                * abs(pos.signed_units) * Decimal(pos_dir)
            total += self._to_usd(inst, upnl_quote, mark)
        return total

    def _per_instrument_drawdown(self, marks, nav) -> dict[str, float]:
        out: dict[str, float] = {}
        for inst, pos in self._positions.items():
            mark = marks.get(inst)
            if mark is None:
                continue
            pos_dir = 1 if pos.signed_units > 0 else -1
            upnl_quote = (Decimal(str(mark)) - Decimal(str(pos.avg_price))) \
                * abs(pos.signed_units) * Decimal(pos_dir)
            upnl = self._to_usd(inst, upnl_quote, mark)
            loss = max(0.0, -float(upnl))
            out[inst] = loss / float(nav) * 100.0
        return out

    def _notional(self, inst, pos, marks) -> float:
        """USD notional (GAP-P9E-04): quote-notional × the quote→USD factor."""
        mark = marks.get(inst, pos.avg_price)
        quote_notional = Decimal(str(abs(float(pos.signed_units)) * mark))
        return float(self._to_usd(inst, quote_notional, mark))

    # -- heartbeat (§8.6 / ACIS-12) ------------------------------------------ #

    def write_heartbeat(self, now: datetime, mode: str, fast_loop_seq: int) -> None:
        """Atomic temp+rename so the watchdog never reads a half-written beat.
        `open_positions` is broker-reconciled truth (this monitor's positions)."""
        path = Path(self._cfg.heartbeat_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        beat = {"ts_utc": now.astimezone(timezone.utc).isoformat(),
                "session_id": self._session_id, "mode": mode,
                "open_positions": len(self._positions), "fast_loop_seq": fast_loop_seq}
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(beat), encoding="utf-8")
        os.replace(tmp, path)

    # -- restart reconciliation (C-RSK-5) ------------------------------------ #

    def positions(self) -> tuple[RiskPosition, ...]:
        out = []
        for inst, pos in sorted(self._positions.items()):
            pos_dir = 1 if pos.signed_units > 0 else -1
            out.append(RiskPosition(
                instrument=inst, direction=pos_dir, size_units=abs(pos.signed_units),
                avg_entry_price=pos.avg_price, opened_at=pos.opened_at,
                param_set_id=pos.param_set_id, group_id=pos.group_id,
                stop_loss=pos.stop_loss, take_profit=pos.take_profit))
        return tuple(out)

    def restore_restrictive_state(self, *, alpha_armed: bool, taper_factor: float | None = None,
                                  anchors: dict | None = None, halts: list | None = None,
                                  now: datetime | None = None) -> None:
        """Persisted risk-restrictive state is restored BEFORE the first
        evaluate — a restart is never a relaxation (GAP-0050). GAP-P9I-05: the
        restored throttle must be RE-PUSHED to the (fresh) Governor over the upward
        edge; so are the anchors, the taper (GAP-P12D-55) and open halts (ACIS-07 §7).
        A session halt that lapsed while the engine was down is closed, not re-applied."""
        expired = self._guards.restore_state(anchors=anchors or {}, taper_factor=taper_factor,
                                             halts=halts or (), now=now)
        if expired and self._store is not None:
            self._store.expire_halts([h.halt_id for h in expired], now)
        self._alpha.restore_armed(alpha_armed)
        self._alpha_armed_prev = alpha_armed
        if alpha_armed:
            self._sink.apply_risk_state(alpha_decay=True)
            self._log.event("ALPHA_DECAY_RESTORED", armed=True)

    def on_human_resume(self, human_token: str, now: datetime) -> None:
        """A human resume (MCP/Governor, phase 10) re-arms the latches — the equity breaker
        is one-shot per ARMED CYCLE, never per process (GAP-P9I-06) — and clears the
        persisted halts so a restart does not re-apply them (ACIS-07 §7). Human-only by
        construction; a blank token is refused before anything is cleared."""
        if not isinstance(human_token, str) or not human_token.strip():
            raise DataQualityError("human_token", human_token, "only a human resumes")
        if self._store is not None:
            self._store.clear_halts(now, human_token)
        self._guards.rearm()

    def reconcile_on_restart(self, broker_positions: tuple[BrokerPosition, ...],
                             now: datetime) -> bool:
        """Broker is authoritative. Any drift vs the persisted internal view →
        log it and demand a halted start (human review). Returns drift?"""
        broker = {p.instrument: (p.direction, p.size_units) for p in broker_positions}
        internal = {inst: (1 if p.signed_units > 0 else -1, abs(p.signed_units))
                    for inst, p in self._positions.items()}
        drift = broker != internal
        if drift:
            self._log.event("RESTART_RECONCILE", drift=True,
                            broker={k: [v[0], str(v[1])] for k, v in broker.items()},
                            internal={k: [v[0], str(v[1])] for k, v in internal.items()})
            # adopt broker truth (never assume the persisted state is correct).
            # A price the internal view knew is kept for marking; a genuinely
            # unknown position marks at its own first mark later (avg unknown → 1.0
            # placeholder, corrected on the next fill/mark; it never sizes).
            adopted: dict[str, _Pos] = {}
            for p in broker_positions:
                prior = self._positions.get(p.instrument)
                adopted[p.instrument] = _Pos(
                    signed_units=Decimal(p.direction) * p.size_units,
                    avg_price=prior.avg_price if prior is not None else 1.0,
                    opened_at=now, param_set_id="unknown:reconciled",
                    group_id=None, stop_loss=None, take_profit=None)
            self._positions = adopted
            self._sink.apply_halt("all", "restart_drift")
        else:
            self._log.event("RESTART_RECONCILE", drift=False)
        return drift
