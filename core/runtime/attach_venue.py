"""Attaching the configured venue for the engine (ACIS-13 §7.1 A1–A11, §6.6; GAP-P12D-132).

Invariants:
  * A transient failure (maintenance, an unreachable host, a spent budget, a venue error on a query)
    is retried IN-PROCESS with full-jitter backoff, sleeping through a stated maintenance end or a
    spent budget's window, up to `backoff.max_consecutive` attempts: never a tight process-restart
    loop (TAE-01, TAI-02). The budget is hard, so the attempts cannot spend past it.
  * A refusal (an AttachReport verdict other than ATTACHED, a detached grant) is final: exit 2, a
    human decides. So is a FOREIGN position at a start (A7, TAI-10): ACIS never trades beside
    what it did not open.
  * The session takes the declared cadences (`CTraderSession.from_venue`, TAE-03/11); the face's
    event consumer is handed to the runtime to supervise (TAE-08).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom

EXIT_REFUSED, EXIT_UNREACHABLE = 2, 4


@dataclass
class VenueAttach:
    session: object
    link: object | None = None
    feed: object | None = None
    positions: tuple = ()
    exit_code: int | None = None


async def attach_venue(cfg, account: str, root: Path, log, session_id: str, *,
                       connect=None) -> VenueAttach:
    from core.data.ctrader.feed import CTraderFeed
    from core.data.ctrader.meter import BudgetRefused, RequestMeter
    from core.data.ctrader.session import Credentials, CTraderSession
    from core.data.ctrader.tokens import TokenStore
    from core.data.ctrader.wire import VenueError
    from core.execution.ctrader_attach import attach
    from core.execution.ctrader_face import CTraderExecutionFace
    from core.execution.ctrader_reconnect import Reconnector, backoff_delay, hold_until
    from core.execution.ctrader_store import VenueStore
    from core.execution.orchestrator import ExecutionOrchestrator
    from core.execution.venue import FillReportStore
    from core.execution.venue_quality import VenueQuality
    from core.runtime.venue_link import VenueLink

    v, rng = cfg.system.venue, SystemRandom()
    db = root / "data" / "venue" / "ctrader.db"           # shared with the probe: one budget ledger
    for d in (db.parent, root / "data" / "runtime"):     # attach runs before build() makes the tree
        d.mkdir(parents=True, exist_ok=True)
    meter = RequestMeter(db, v.account_key, budget=v.daily_request_budget, reserve=v.close_reserve,
                         now=datetime.now(timezone.utc))
    session = CTraderSession.from_venue(v, credentials=Credentials.from_env(),
                                        tokens=TokenStore.from_env(), meter=meter, logger=log,
                                        **({"connect": connect} if connect is not None else {}))
    store = VenueStore(db, v.account_key)
    attached = None
    for attempt in range(v.backoff.max_consecutive):
        try:
            attached = await attach(v, rulebook_key=account, rulebook=cfg.platform_rules.accounts[account],
                                    instruments=cfg.instruments.instruments, session=session, store=store,
                                    logger=log, now=datetime.now(timezone.utc),
                                    execution_cap=cfg.system.execution.max_venue_requests_per_day)
            break
        except (BudgetRefused, VenueError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
            await session.stop()
            now = datetime.now(timezone.utc)
            until, why = hold_until(exc, now)
            delay = backoff_delay(v.backoff, attempt, rng) + (
                max(0.0, (until - now).total_seconds()) if until is not None else 0.0)
            log.event("ATTACH_RETRY", attempt=attempt, error=getattr(exc, "code", None) or type(exc).__name__,
                      hold=why, delay_s=round(delay, 3))
            await asyncio.sleep(delay)
    if attached is None:
        log.event("ATTACH_UNREACHABLE", attempts=v.backoff.max_consecutive)
        return VenueAttach(session, exit_code=EXIT_UNREACHABLE)
    if attached.report.verdict != "ATTACHED":
        await session.stop()
        return VenueAttach(session, exit_code=EXIT_REFUSED)
    face = CTraderExecutionFace(session, attached.specs, attached.descriptor, store, log,
                                account_key=v.account_key, order_ack_timeout_s=v.order_ack_timeout_s,
                                stop_confirm_timeout_s=v.stop_confirm_timeout_s,
                                max_orders_per_day=v.max_orders_per_day)
    events = face.start()
    positions, foreign = await face.synchronise()
    if foreign:                                            # A7: an AttachHalt, at every start
        log.event("ATTACH_HALTED_OPEN_POSITIONS", foreign=len(foreign), at="start")
        events.cancel()
        await session.stop()
        return VenueAttach(session, exit_code=EXIT_REFUSED)
    orch = ExecutionOrchestrator(
        cfg.system.execution, {face.name: face}, VenueQuality(),
        FillReportStore(root / "data" / "runtime" / "venue_fills.db"),
        slippage_alert_bps=cfg.guardrails.slippage_alert_bps, rng=SystemRandom(), logger=log,
        session_id=session_id)
    feed = CTraderFeed(session, attached.feed_symbols, log)
    reconnector = Reconnector(session=session, face=face, feed=feed, backoff=v.backoff, rng=rng, logger=log)
    link = VenueLink(face=face, orchestrator=orch, attached=attached, session=session, events=events,
                     poll_s=v.equity_poll_s, reconcile_s=v.reconcile_interval_s,
                     now_fn=lambda: datetime.now(timezone.utc), logger=log, reconnector=reconnector)
    return VenueAttach(session, link, feed, tuple(positions))
