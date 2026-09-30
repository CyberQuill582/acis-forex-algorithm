"""The engine's entry point (master §10; deploy/systemd/acis-engine.service `ExecStart`).

    python -m core.runtime --print-hashes [--account pepperstone_demo]   # what practice attests to
    python -m core.runtime                                               # paper, on the mock feed
    python -m core.runtime --venue --account pepperstone_demo            # paper, on the venue's prices
    python -m core.runtime --venue --account pepperstone_demo --practice --ack-guardrail H --ack-rulebook H
    python -m core.runtime ... --resume                                  # a human lifts the halts at start

Invariants:
  * One engine per deployment root: a second start is refused (exit 2) while the first holds the
    lock (GAP-P12D-132 TAI-11).
  * It boots in PAPER unless a human at the terminal enters practice: the token typed (never argv
    or env), both hashes attested, through the MCP tool, BEFORE Risk's first evaluation and on
    practice's own Risk store (TAI-14). A supervised restart comes back in paper.
  * `--resume` lifts the persisted halts after boot through ACIS-08's `acis_resume` (TAI-07).
  * Exit codes: 0 the feed ended; 1 a loop stalled (flattened, halted); 2 refused (the attach, a
    foreign position, the lock); 3 a human step refused; 4 the venue stayed unreachable. The unit
    does not restart on 2 or 3.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

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


def exclusive_lock(path: Path):
    """Held for the life of the process; the OS releases it if the process dies."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+")
    try:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:                                   # Windows (development only)
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    return handle


def human_call(runtime, cfg, log, session_id: str, tool: str, args: dict, token: str) -> bool:
    tools = ControlTools(control=runtime.p.control, auth=HumanTokenVerifier(os.environ[HUMAN_DIGEST_ENV]),
                         mode_controller=runtime.p.mode, stager=_NoStaging(),
                         tunable_bounds={t.path: (t.min, t.max) for t in cfg.system.monitoring.tunable_paths},
                         audit=McpAuditStore(), logger=log, session_id=session_id)
    reply = tools.call_tool(tool, {"request_id": str(uuid.uuid4()), "human_token": token, "args": args},
                            caller="human")
    log.event("ENGINE_HUMAN_CALL", tool=tool, result=reply["result"])
    return reply["status"] == "ok"


async def main(args) -> int:
    from core.data.feeds import MockPaperFeed
    from core.runtime.attach_venue import attach_venue
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
    try:
        lock = exclusive_lock(root / "data" / "runtime" / "engine.lock")
    except OSError:
        log.event("ENGINE_ALREADY_RUNNING", root=str(root))
        return 2
    token = None
    if args.practice or args.resume:
        if not os.environ.get(HUMAN_DIGEST_ENV):
            log.event("ENGINE_HUMAN_CALL_REFUSED", reason=f"{HUMAN_DIGEST_ENV} is not set")
            return 3
        token = getpass.getpass("human token: ")
    session, venue, feed, positions = None, None, None, ()
    if args.venue:
        attached = await attach_venue(cfg, account, root, log, session_id)
        session = attached.session
        if attached.exit_code is not None:
            return attached.exit_code
        venue, feed, positions = attached.link, attached.feed, attached.positions
    else:
        feed = MockPaperFeed({s: 1.0 for s in cfg.instruments.enabled}, n_ticks=args.mock_ticks)
    try:
        runtime = build(cfg, root=root, session_id=session_id, feed=feed, venue=venue,
                        intended_mode="practice" if args.practice else "paper")
        if args.practice and not human_call(runtime, cfg, log, session_id, "acis_set_mode", {
                "mode": "practice", "guardrail_hash": args.ack_guardrail,
                "rulebook_hash": args.ack_rulebook}, token):
            return 3
        await runtime.boot(positions)
        if args.resume and not human_call(runtime, cfg, log, session_id, "acis_resume", {}, token):
            return 3
        outcome = await runtime.run()
        log.event("ENGINE_STOPPED", outcome=outcome)
        return 0 if outcome == "feed_ended" else 1
    finally:
        if session is not None:
            await session.stop()
        lock.close()


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--account", help="the platform_rules account (default: system.active_account)")
    ap.add_argument("--venue", action="store_true", help="attach the configured venue (ACIS-13)")
    ap.add_argument("--practice", action="store_true", help="enter practice before boot (human token)")
    ap.add_argument("--resume", action="store_true", help="lift persisted halts after boot (human token)")
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
