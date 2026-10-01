"""GAP-P12D-135 (owner ruling 2026-10-01): a deliberate stop closes every position, halts, then exits."""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import pytest

from config.account_doctrine import guardrail_hash, rulebook_hash
from core.data.feeds import MockPaperFeed
from core.runtime.__main__ import install_stop
from core.runtime.wiring import build
from tests.ctrader_fixtures import capture_logger
from tests.integration.test_ctrader_adapter import _bind, _face, _open
from tests.integration.test_paper_trading_pipeline import flat_ticks
from tests.integration.test_runtime import ClockedFeed, TickClock, events
from tests.integration.test_track_a_runtime_fixes import link_over


class SilentAfter(ClockedFeed):
    """Its ticks, then silence with the connection alive: only a stop can end the run."""

    async def stream(self):
        async for tick in super().stream():
            yield tick
        await asyncio.Event().wait()


async def test_a_deliberate_stop_in_practice_closes_every_position_and_halts(tmp_path, acis_config) -> None:
    _bind(tmp_path)
    venue, session, face, _ = await _face(tmp_path)
    await _open(face)                                                  # an ACIS position, on its stop
    positions, foreign = await face.synchronise()
    assert len(positions) == 1 and foreign == ()
    clock, (log, _buf) = TickClock(), capture_logger()
    rts: list = []
    feed = SilentAfter(clock, flat_ticks()[:20], at_tick={10: lambda: rts[0].request_stop("SIGTERM")})
    rt = build(acis_config, root=tmp_path, session_id="rt", now_fn=clock, intended_mode="practice", feed=feed,
               venue=link_over(acis_config, face, session, tmp_path, clock, log))
    rts.append(rt)
    rulebook = acis_config.platform_rules.accounts[acis_config.system.active_account]
    rt.p.mode.set_mode("practice", guardrail_hash=guardrail_hash(acis_config.guardrails),
                       rulebook_hash=rulebook_hash(rulebook))
    await rt.boot(positions)
    assert len(rt.p.risk.positions()) == 1                             # adopted from venue truth
    assert await asyncio.wait_for(rt.run(), 30) == "stopped"
    assert venue.positions == {}                                       # flat AT THE VENUE
    assert rt.p.risk.positions() == ()
    halts = {(h.kind, h.reason) for h in rt.p.risk_store.open_halts()}
    assert {("flatten", "operator_stop"), ("halt", "operator_stop")} <= halts   # the next start needs a human
    assert halts - {("flatten", "operator_stop"), ("halt", "operator_stop")} == {
        ("halt", "restart_drift")}       # the boot's own: this Risk store never saw the position (C-RSK-5)
    assert [e["data"]["reason"] for e in events(tmp_path, "system_log", "ENGINE_STOP_REQUESTED")] == ["SIGTERM"]
    assert not events(tmp_path, "system_log", "STOP_LEFT_POSITIONS")
    await session.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals; the engine runs on Linux")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_a_signal_is_a_deliberate_stop(tmp_path, acis_config, sig) -> None:
    rt = build(acis_config, root=tmp_path, session_id="rt", feed=SilentAfter(TickClock(), flat_ticks()[:5]))
    loop = asyncio.get_running_loop()
    install_stop(rt)
    try:
        await rt.boot()
        run = asyncio.ensure_future(rt.run())
        await asyncio.sleep(0.2)
        os.kill(os.getpid(), sig)
        assert await asyncio.wait_for(run, 30) == "stopped"
    finally:
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(s)
    assert rt.stop_reason == sig.name
    assert {(h.kind, h.reason) for h in rt.p.risk_store.open_halts()} == {
        ("flatten", "operator_stop"), ("halt", "operator_stop")}

