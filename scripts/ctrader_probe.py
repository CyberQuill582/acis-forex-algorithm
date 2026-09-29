"""The first-demo-session probe (ACIS-13 Appendix B: OQ-07, OQ-08, OQ-09, OQ-12, OQ-17). Human-run.

    python scripts/ctrader_probe.py --rulebook pepperstone_demo [--spots-s 60] [--trade]

It attaches READ-ONLY (A1–A6), records the venue's raw frames with every secret redacted, watches
spots, and writes one JSON report under logs/. `--trade` adds ONE minimum-lot round trip with a
stop, and only on an account the attach reports practice-eligible (a demo, `isLive` false, a
practice rulebook, master v2.23): the answers to OQ-07 (is the stop atomic with the fill?) and
OQ-17 (does a market IOC fill whole?) need a real fill. Nothing here changes config or the ledger;
a human reads the report and records the answers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.schemas import load_config  # noqa: E402
from core.data.ctrader.meter import RequestMeter  # noqa: E402
from core.data.ctrader.session import Credentials, CTraderSession  # noqa: E402
from core.data.ctrader.tokens import TokenStore  # noqa: E402
from core.data.ctrader.transport import open_websocket  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from core.execution.ctrader_attach import attach  # noqa: E402
from core.execution.ctrader_face import CTraderExecutionFace  # noqa: E402
from core.execution.ctrader_store import VenueStore  # noqa: E402

SECRET = re.compile(r'("(?:accessToken|refreshToken|clientSecret|clientId)"\s*:\s*)"[^"]*"')


class Recorder:
    """Wraps the transport: every frame both ways, secrets redacted, first `limit` kept."""

    def __init__(self, inner, frames: list, limit: int = 400) -> None:
        self._inner, self._frames, self._limit = inner, frames, limit

    def _keep(self, direction: str, data) -> None:
        if len(self._frames) < self._limit:
            text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
            self._frames.append({"t": time.time(), "dir": direction, "binary": isinstance(data, bytes),
                                 "frame": SECRET.sub(r'\1"<redacted>"', text)})

    async def send_str(self, data: str) -> None:
        self._keep("out", data)
        await self._inner.send_str(data)

    async def receive(self):
        data = await self._inner.receive()
        if data is not None:
            self._keep("in", data)
        return data

    async def close(self) -> None:
        await self._inner.close()


async def probe(args) -> dict:
    cfg = load_config(args.config)
    venue = cfg.system.venue
    rulebook = cfg.platform_rules.accounts[args.rulebook]
    frames: list = []
    log = JsonlEventLogger(open(args.log, "a", encoding="utf-8"), "data", "ctrader-probe")
    now = datetime.now(timezone.utc)
    meter = RequestMeter(args.db, venue.account_key, budget=venue.daily_request_budget,
                         reserve=venue.close_reserve, now=now)

    async def connect(environment):
        return Recorder(await open_websocket(environment), frames)

    session = CTraderSession(environment=venue.environment, binding=venue.ctid_trader_account_id,
                             credentials=Credentials.from_env(), tokens=TokenStore.from_env(),
                             meter=meter, logger=log, connect=connect)
    store = VenueStore(args.db, venue.account_key)
    result = await attach(venue, rulebook_key=args.rulebook, rulebook=rulebook,
                          instruments=cfg.instruments.instruments, session=session, store=store,
                          logger=log, now=now,
                          execution_cap=cfg.system.execution.max_venue_requests_per_day)
    out = {"attach": json.loads(result.report.to_json()), "spots": [], "trade": None}
    if result.report.verdict != "ATTACHED":
        await session.stop()
        return out | {"frames": frames}
    from core.data.ctrader.feed import CTraderFeed
    feed = CTraderFeed(session, result.feed_symbols, log)
    stream = feed.stream()
    deadline = time.monotonic() + args.spots_s
    while time.monotonic() < deadline and len(out["spots"]) < 200:
        try:
            tick = await asyncio.wait_for(anext(stream), deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        out["spots"].append({"instrument": tick.instrument, "venue_ms": int(tick.event_time.timestamp() * 1000),
                             "local_ms": int(tick.recv_time.timestamp() * 1000), **tick.raw_payload})
    if args.trade:
        out["trade"] = await round_trip(result, session, store, log, feed)
    await session.stop()
    return out | {"frames": frames}


async def round_trip(result, session, store, log, feed) -> dict:
    if not result.report.practice_eligible:
        return {"refused": "the account is not practice-eligible (master v2.23)"}
    face = CTraderExecutionFace(session, result.specs, result.descriptor, store, log,
                                account_key=store.account_key)
    face.start()
    await face.synchronise()
    spec = result.specs["EUR_USD"]
    quote = await feed.snapshot("EUR_USD")
    stop = round(quote.ask - 0.0050, spec.digits)
    now = datetime.now(timezone.utc)
    opened = await face.submit_order(fragment_id=f"probe-{int(time.time())}", order_id="probe",
                                     instrument="EUR_USD", direction=1, units=spec.min_units,
                                     requested_price=quote.ask, ioc=True, now=now, session_id="probe",
                                     stop_loss=stop)
    stops = await face.resting_stops()
    closed = await face.close_position(fragment_id=f"probe-close-{int(time.time())}", order_id="probe",
                                       instrument="EUR_USD", direction=1, units=Decimal(opened.filled_units),
                                       requested_price=quote.bid, now=datetime.now(timezone.utc),
                                       session_id="probe")
    return {"open": opened.status.value, "filled": str(opened.filled_units), "fill_px": opened.fill_price,
            "slippage_bps": opened.slippage_bps, "stop_at_venue": stops.get("EUR_USD"),
            "requested_stop": stop, "close": closed.status.value}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="config")
    parser.add_argument("--rulebook", required=True)
    parser.add_argument("--spots-s", type=float, default=60.0)
    parser.add_argument("--trade", action="store_true")
    parser.add_argument("--db", default="data/venue/ctrader.db")
    parser.add_argument("--log", default="logs/ctrader_probe.jsonl")
    args = parser.parse_args(argv)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(probe(args))
    path = Path("logs") / f"ctrader_probe_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(f"attach: {report['attach']['verdict']} {report['attach']['reason']}")
    print(f"spots: {len(report['spots'])}; trade: {report['trade']}; report: {path}")
    return 0 if report["attach"]["verdict"] == "ATTACHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
