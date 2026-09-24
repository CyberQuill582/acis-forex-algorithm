"""C5 MONEY-PATH SAFETY — synthetic reproductions against BASE 7695ed04 (read-only import).

Run:  PYTHONDONTWRITEBYTECODE=1 python repro_money_path.py /tmp/review-acis
Every probe prints PASS-OF-DEFECT ("DEFECT REPRODUCED") or "not reproduced". Synthetic data only;
no file in the review tree is written (bytecode writing is disabled; the watchdog probe uses a temp dir).
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

sys.dont_write_bytecode = True
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis")
sys.path.insert(0, str(ROOT))

from config.schemas import ExecutionConfig  # noqa: E402
from core.execution.orchestrator import ExecutionOrchestrator  # noqa: E402
from core.execution.venue import (  # noqa: E402
    BrokerPosition, FillReport, FillReportStore, FillStatus, MockExecutionFace, VenueQuality)
from core.governor.portfolio_types import SizedOrder  # noqa: E402
from tests.optimizer_fixtures import CapturingLogger  # noqa: E402

T0 = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)
RESULTS: dict[str, str] = {}


def exec_cfg(**kw) -> ExecutionConfig:
    base = dict(fragment_threshold_lots=1.0, fragment_size_jitter=[0.85, 1.15],
                fragment_time_jitter_s=[0.5, 3.0], min_fragment_lots=0.10,
                vwap_threshold_lots=5.0, vwap_window_s=300, fast_decay_seconds=30,
                signature_lot_variance=0.15, dispatch_budget_ms=100)
    base.update(kw)
    return ExecutionConfig(**base)


def order(units: str, *, stop: float = 1.0700, action: str = "open", direction: int = 1,
          inst: str = "EUR_USD", oid: str = "o-1") -> SizedOrder:
    return SizedOrder(order_id=oid, signal_id="sig", instrument=inst, direction=direction,
                      size_units=Decimal(units), entry_price=1.0800, stop_loss=stop,
                      take_profit=None, reason="probe", factors_snapshot=MappingProxyType({}),
                      sized_at=T0, param_set_id="ps", action=action)


def orch(face, tmp: Path, **kw) -> ExecutionOrchestrator:
    import random
    return ExecutionOrchestrator(exec_cfg(), {"mock": face}, VenueQuality(),
                                 FillReportStore(tmp / "fills.db"), 8.0, random.Random(1),
                                 CapturingLogger(), "s1", now_fn=lambda: T0, **kw)


# --------------------------------------------------------------------------- #
# P1  §279 stop never reaches the venue through the production dispatch path
# --------------------------------------------------------------------------- #
async def p1(tmp: Path) -> None:
    face = MockExecutionFace()
    o = orch(face, tmp)
    reports = await o.submit(order("1000", stop=1.0700), valid_for_seconds=300)
    stops = await face.resting_stops()
    pos = await face.open_positions()
    ok = reports and reports[0].status is FillStatus.FILLED and not stops and pos[0].stop_loss is None
    RESULTS["P1_stop_not_threaded"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: filled={reports[0].filled_units} "
        f"SizedOrder.stop_loss=1.0700 venue resting_stops={stops} position.stop_loss={pos[0].stop_loss}")


# --------------------------------------------------------------------------- #
# P2  ack-lost fill -> orchestrator books REJECT(0) -> orphan position at venue
# --------------------------------------------------------------------------- #
class AckLostFace(MockExecutionFace):
    """Realistic ambiguity: the order REACHES the venue and fills, then the ack is
    lost (ConnectionError on the response). No broker dedupe by fragment id."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def submit_order(self, **kw) -> FillReport:  # type: ignore[override]
        self.calls += 1
        self._net[kw["instrument"]] = self._net.get(kw["instrument"], Decimal(0)) + kw["direction"] * kw["units"]
        raise ConnectionError("ack lost after the venue filled")


async def p2(tmp: Path) -> None:
    from tests.risk_fixtures import RecordingSink, build_monitor, load_cfg
    face = AckLostFace()
    o = orch(face, tmp)
    reports = await o.submit(order("1000"), valid_for_seconds=300)
    cfg = load_cfg()
    mon, *_ = build_monitor(cfg, RecordingSink())
    for r in reports:
        mon.ingest(r)
    venue_pos = await face.open_positions()
    ok = (reports[-1].status is FillStatus.REJECTED and venue_pos and not mon.positions())
    hb = Path(tmp / "hb.json")
    mon._cfg = mon._cfg.__class__(**{**mon._cfg.__dict__, "heartbeat_path": str(hb)}) if hasattr(mon._cfg, "__dict__") else mon._cfg
    try:
        mon.write_heartbeat(T0, "paper", 1)
        beat = json.loads(hb.read_text())
    except Exception as exc:  # pydantic model may be frozen; report without the beat
        beat = {"open_positions": len(mon.positions()), "note": repr(exc)}
    RESULTS["P2_ack_lost_orphan"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: venue submissions reached={face.calls} "
        f"venue net position={[(p.instrument, p.direction, str(p.size_units)) for p in venue_pos]} "
        f"orchestrator result={[(r.status.value, str(r.filled_units)) for r in reports]} "
        f"risk monitor positions={len(mon.positions())} heartbeat open_positions={beat.get('open_positions')}")


# --------------------------------------------------------------------------- #
# P3  execution freeze checked once per order, not per fragment (racing HALT)
# --------------------------------------------------------------------------- #
async def p3(tmp: Path) -> None:
    face = MockExecutionFace()
    holder: dict = {}

    async def sleep_then_halt(delay: float) -> None:
        # a HALT/flatten lands while the orchestrator waits for fragment #2
        holder["o"].set_freeze(True, "equity_floor")

    o = orch(face, tmp, sleep_fn=sleep_then_halt)
    holder["o"] = o
    reports = await o.submit(order("300000"), valid_for_seconds=300)  # 3 lots -> fragmented
    filled_after = [r for r in reports[1:] if r.filled_units > 0]
    ok = o.frozen and len(filled_after) > 0
    RESULTS["P3_freeze_race"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: fragments={len(reports)} "
        f"freeze active after fragment 1; OPEN fragments still filled after freeze={len(filled_after)} "
        f"units={[str(r.filled_units) for r in filled_after]}")


# --------------------------------------------------------------------------- #
# P4  restart reconcile adopts unknown positions at avg_price 1.0 -> fake P&L
# --------------------------------------------------------------------------- #
def p4() -> None:
    from tests.risk_fixtures import RecordingSink, acct, build_monitor, load_cfg
    cfg = load_cfg()
    sink = RecordingSink()
    mon, *_ = build_monitor(cfg, sink)
    drift = mon.reconcile_on_restart(
        (BrokerPosition(instrument="USD_JPY", direction=1, size_units=Decimal("1000")),), T0)
    snap = mon.evaluate(acct(10000), T0, marks={"USD_JPY": 150.0})
    sink2 = RecordingSink()
    mon2, *_ = build_monitor(cfg, sink2)
    mon2.reconcile_on_restart(
        (BrokerPosition(instrument="USD_JPY", direction=-1, size_units=Decimal("1000")),), T0)
    snap2 = mon2.evaluate(acct(10000), T0, marks={"USD_JPY": 150.0})
    ok = drift and abs(float(snap.daily_pnl)) > 500
    RESULTS["P4_reconcile_placeholder_price"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: long 1000 USD_JPY adopted -> daily_pnl="
        f"{float(snap.daily_pnl):.2f} USD (true unrealised unknown, ~0); short -> daily_pnl="
        f"{float(snap2.daily_pnl):.2f}, halts={sink2.halts}")


# --------------------------------------------------------------------------- #
# P5  every human-only halt lives in process memory; a restart forgets it
# --------------------------------------------------------------------------- #
def p5() -> None:
    sys.path.insert(0, str(ROOT / "tests" / "unit"))
    from test_governor import mk_governor  # read-only import of the fixture
    gov, _ = mk_governor()
    for scope, why in (("all", "mcp_halt"), ("all", "platform_dd:ftmo"), ("all", "var_cap")):
        gov.apply_halt(scope, why)
    before = dict(gov._halts)
    gov2, _ = mk_governor()  # what systemd Restart=always hands back 5 s later
    import subprocess
    callers = subprocess.run(
        ["grep", "-rn", "record_halt\\|save_restrictive_state\\|load_restrictive_state",
         "--include=*.py", "core", "monitoring", "scripts"], cwd=ROOT, capture_output=True, text=True).stdout
    prod_callers = [ln for ln in callers.splitlines() if "def " not in ln]
    ok = before and not gov2._halts and not prod_callers
    RESULTS["P5_halts_not_persisted"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: halts before restart={before}; "
        f"after restart={gov2._halts}; production callers of record_halt/save_/load_restrictive_state={prod_callers}")


# --------------------------------------------------------------------------- #
# P6  watchdog flatten is not fenced from a hung-then-recovered engine
# --------------------------------------------------------------------------- #
async def p6(tmp: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import acis_watchdog as wdm
    hb = tmp / "heartbeat.json"
    cfg = {"heartbeat_path": str(hb), "watchdog_timeout_s": 30, "poll_interval_s": 5,
           "credentials_ref": "x"}
    face = MockExecutionFace()                     # netting venue, as the mock declares

    class VenueFlatten:                            # the real plugin closes at the broker
        def flatten_all(self, credentials: str):
            n = sum(1 for v in face._net.values() if v != 0)
            face._net.clear(); face._stops.clear()
            return wdm.FlattenResult(ok=True, positions_closed=n)

    wd = wdm.Watchdog(cfg, VenueFlatten(), wdm.WatchdogLogger(tmp / "wd.jsonl"),
                      marker_path=tmp / "marker", started_at=0.0)
    o = orch(face, tmp)
    await o.submit(order("1000", oid="open-1"), valid_for_seconds=300)   # engine: long 1000
    hb.write_text(json.dumps({"ts_utc": "t1", "open_positions": 1, "fast_loop_seq": 1}))
    s1 = wd.poll(0.0)
    s2 = wd.poll(40.0)                              # engine hung 40 s (GC pause, blocking I/O)
    hb.write_text(json.dumps({"ts_utc": "t2", "open_positions": 1, "fast_loop_seq": 2}))
    s3 = wd.poll(45.0)                              # engine recovers; watchdog re-arms
    # the engine still believes it is long and now exits its "position"
    await o.submit(order("1000", oid="close-1", direction=-1, action="close"), valid_for_seconds=300)
    pos = await face.open_positions()
    ok = s2 == "flatten" and pos and pos[0].direction == -1
    RESULTS["P6_watchdog_unfenced"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: polls={[s1, s2, s3]}; venue after the "
        f"engine's stale 'close' = {[(p.instrument, p.direction, str(p.size_units), p.stop_loss) for p in pos]} "
        f"(an unintended, unprotected SHORT)")


# --------------------------------------------------------------------------- #
# P7  host clock 949 s slow -> normaliser rejects every live tick
# --------------------------------------------------------------------------- #
def p7() -> None:
    from config.schemas import load_config
    from core.data.asset_classes import build_calendars
    from core.data.errors import DataQualityError
    from core.data.normaliser import FactoryConfig, MarketStateFactory, RawTick
    c = load_config(ROOT / "config")
    d = c.system.data
    cals = build_calendars(c.instruments.calendars)
    en = c.instruments.enabled
    f = MarketStateFactory(
        cfg=FactoryConfig(d.stale_threshold_ms, d.clock_skew_tolerance_ms, d.reorder_tolerance_ms,
                          d.tick_velocity_window_s, d.session_median_window, d.session_median_min_samples),
        calendars_by_instrument={s: cals[sp.calendar] for s, sp in en.items()},
        max_plausible_spread={s: sp.max_plausible_spread for s, sp in en.items()},
        macro_imminent=lambda i, t: False)

    def tick(ev, rv):  # broker stamps event_time; a real adapter stamps recv_time from the HOST clock
        return RawTick(event_time=ev, recv_time=rv, instrument="EUR_USD", bid=1.08, ask=1.0801,
                       volume=1.0, book=None, provider="probe", raw_payload={})
    rejected = 0
    for k in range(100):
        ev = T0 + timedelta(seconds=k)
        try:
            f.build(tick(ev, ev - timedelta(seconds=949)))        # host 949 s SLOW (GAP-P12D-51)
        except DataQualityError:
            rejected += 1
    fast = f.build(tick(T0 + timedelta(seconds=200), T0 + timedelta(seconds=200 + 949)))  # host FAST
    ok = rejected == 100
    RESULTS["P7_slow_host_clock"] = (
        f"{'DEFECT REPRODUCED' if ok else 'not reproduced'}: host 949 s slow -> {rejected}/100 ticks raise "
        f"DataQualityError (feed dead, fails safe); host 949 s fast -> stale={fast.state.is_stale if hasattr(fast.state, 'is_stale') else '?'} "
        f"events={[e for e, _ in fast.events]}. No start-up check compares host time to broker time.")


async def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for i, fn in enumerate((p1, p2, p3, p6)):
            sub = tmp / f"r{i}"
            sub.mkdir()
            try:
                await fn(sub)
            except Exception as exc:  # noqa: BLE001
                RESULTS[fn.__name__] = f"ERROR {exc!r}"
        for fn in (p4, p5, p7):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                RESULTS[fn.__name__] = f"ERROR {exc!r}"
    for k in sorted(RESULTS):
        print(f"{k}: {RESULTS[k]}")


if __name__ == "__main__":
    asyncio.run(main())
