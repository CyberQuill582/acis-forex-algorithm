"""The engine's entry point (master §10; deploy/systemd/acis-engine.service `ExecStart`).

    python -m core.runtime --print-hashes [--account pepperstone_demo]   # what practice attests to
    python -m core.runtime                                               # paper, on the mock feed
    python -m core.runtime --venue --account pepperstone_demo            # paper, on the venue's prices
    python -m core.runtime --venue --account pepperstone_demo --practice --ack-guardrail H --ack-rulebook H

Invariants:
  * It always boots in PAPER (master §7.5). `--practice` then asks for the human token at the
    terminal (never argv or the environment, so it lands in no history) and enters practice
    through the MCP tool itself, with both hash attestations; a refusal ends the process
    rather than letting it trade in a mode nobody chose. A supervised restart therefore comes
    back in paper, and a human re-enters practice: a restart is never a relaxation.
  * `--venue` attaches the configured venue first (ACIS-13 A1–A11); anything but ATTACHED ends
    the process before a single tick is read.
  * Exit codes: 0 the feed ended, 1 a loop stalled (flattened and halted), 2 the attach
    refused, 3 practice refused.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom

from config.account_doctrine import guardrail_hash, rulebook_hash
from config.schemas import load_config
from core.data.jsonl_logging import JsonlEventLogger
from monitoring.auth import HumanTokenVerifier
from monitoring.store import McpAuditStore
from monitoring.tools import ControlTools

HUMAN_DIGEST_ENV = "ACIS_HUMAN_TOKEN_SHA256"      # the digest only; the secret stays with the human


class _NoStaging:
    def stage_config(self, patch: dict, rationale: str) -> str:
        raise NotImplementedError("no MCP transport carries acis_stage_config yet (GAP-P12D-08)")


async def attach_venue(cfg, account: str, root: Path, log, session_id: str):
    """ACIS-13: session, attach, face, sync — the probe's path, kept for the whole run."""
    from core.data.ctrader.feed import CTraderFeed
    from core.data.ctrader.meter import RequestMeter
    from core.data.ctrader.session import Credentials, CTraderSession
    from core.data.ctrader.tokens import TokenStore
    from core.data.ctrader.transport import open_websocket
    from core.execution.ctrader_attach import attach
    from core.execution.ctrader_face import CTraderExecutionFace
    from core.execution.ctrader_store import VenueStore
    from core.execution.orchestrator import ExecutionOrchestrator
    from core.execution.venue import FillReportStore
    from core.execution.venue_quality import VenueQuality
    from core.runtime.venue_link import VenueLink

    v, now = cfg.system.venue, datetime.now(timezone.utc)
    db = root / "data" / "venue" / "ctrader.db"           # shared with the probe: one budget ledger
    db.parent.mkdir(parents=True, exist_ok=True)
    meter = RequestMeter(db, v.account_key, budget=v.daily_request_budget, reserve=v.close_reserve, now=now)
    session = CTraderSession(environment=v.environment, binding=v.ctid_trader_account_id,
                             credentials=Credentials.from_env(), tokens=TokenStore.from_env(),
                             meter=meter, logger=log, connect=open_websocket)
    store = VenueStore(db, v.account_key)
    attached = await attach(v, rulebook_key=account, rulebook=cfg.platform_rules.accounts[account],
                            instruments=cfg.instruments.instruments, session=session, store=store,
                            logger=log, now=now, execution_cap=cfg.system.execution.max_venue_requests_per_day)
    if attached.report.verdict != "ATTACHED":
        await session.stop()
        return session, None, None, ()
    face = CTraderExecutionFace(session, attached.specs, attached.descriptor, store, log,
                                account_key=v.account_key, order_ack_timeout_s=v.order_ack_timeout_s,
                                stop_confirm_timeout_s=v.stop_confirm_timeout_s,
                                max_orders_per_day=v.max_orders_per_day)
    face.start()
    positions, _ = await face.synchronise()
    orch = ExecutionOrchestrator(
        cfg.system.execution, {face.name: face}, VenueQuality(),
        FillReportStore(root / "data" / "runtime" / "venue_fills.db"),
        slippage_alert_bps=cfg.guardrails.slippage_alert_bps, rng=SystemRandom(), logger=log,
        session_id=session_id)
    link = VenueLink(face=face, orchestrator=orch, attached=attached, poll_s=v.equity_poll_s,
                     reconcile_s=v.reconcile_interval_s, now_fn=lambda: datetime.now(timezone.utc),
                     logger=log)
    return session, link, CTraderFeed(session, attached.feed_symbols, log), positions


def enter_practice(runtime, cfg, account: str, args, log, session_id: str) -> bool:
    tools = ControlTools(control=runtime.p.control, auth=HumanTokenVerifier(os.environ[HUMAN_DIGEST_ENV]),
                         mode_controller=runtime.p.mode, stager=_NoStaging(),
                         tunable_bounds={t.path: (t.min, t.max) for t in cfg.system.monitoring.tunable_paths},
                         audit=McpAuditStore(), logger=log, session_id=session_id)
    reply = tools.call_tool("acis_set_mode", {
        "request_id": str(uuid.uuid4()), "human_token": getpass.getpass("human token: "),
        "args": {"mode": "practice", "guardrail_hash": args.ack_guardrail,
                 "rulebook_hash": args.ack_rulebook}}, caller="human")
    log.event("ENGINE_PRACTICE_REQUEST", account=account, result=reply["result"])
    return reply["status"] == "ok"


async def main(args) -> int:
    from core.data.feeds import MockPaperFeed
    from core.runtime.wiring import build

    root = Path(args.root).resolve()
    cfg = load_config(root / "config")
    account = args.account or cfg.system.active_account
    cfg = cfg.model_copy(update={"system": cfg.system.model_copy(update={"active_account": account})})
    if args.print_hashes:
        print(f"guardrail_hash {guardrail_hash(cfg.guardrails)}")
        print(f"rulebook_hash  {rulebook_hash(cfg.platform_rules.accounts[account])}  ({account})")
        return 0
    session_id = f"engine-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    log = JsonlEventLogger(root / "logs" / "system_log.jsonl", layer="runtime", session_id=session_id)
    session, venue, feed, positions = None, None, None, ()
    if args.venue:
        session, venue, feed, positions = await attach_venue(cfg, account, root, log, session_id)
        if venue is None:
            return 2
    else:
        feed = MockPaperFeed({s: 1.0 for s in cfg.instruments.enabled}, n_ticks=args.mock_ticks)
    try:
        runtime = build(cfg, root=root, session_id=session_id, feed=feed, venue=venue)
        await runtime.boot(positions)
        if args.practice and not enter_practice(runtime, cfg, account, args, log, session_id):
            return 3
        outcome = await runtime.run()
        log.event("ENGINE_STOPPED", outcome=outcome)
        return 0 if outcome == "feed_ended" else 1
    finally:
        if session is not None:
            await session.stop()


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--account", help="the platform_rules account (default: system.active_account)")
    ap.add_argument("--venue", action="store_true", help="attach the configured venue (ACIS-13)")
    ap.add_argument("--practice", action="store_true", help="enter practice after boot (human token)")
    ap.add_argument("--ack-guardrail", help="the guardrail hash the human attests to")
    ap.add_argument("--ack-rulebook", help="the rulebook hash the human attests to")
    ap.add_argument("--print-hashes", action="store_true")
    ap.add_argument("--mock-ticks", type=int, default=1000, help="paper smoke run length (no venue)")
    args = ap.parse_args(argv)
    if args.practice and not args.venue:
        ap.error("--practice needs --venue: practice orders reach only an attached demo account")
    return asyncio.run(main(args))


if __name__ == "__main__":
    raise SystemExit(cli())
