"""ACIS-13 §14.2 case 8 (OQ-06): the watchdog flattens while the engine's connection is alive. Human-run.

    python scripts/ctrader_case8.py            # on the engine host, DEMO binding only, engine stopped

A child process attaches like the probe, opens ONE minimum-lot EUR_USD position with its stop, and
holds its socket open. The parent SIGSTOPs it (a frozen engine whose connection is still alive),
runs the watchdog's own cTrader plugin from `config/watchdog.yaml`, then reconciles the account
through a second plugin pass. It refuses a live binding, a non-flat account, or a binding that
differs between the two config files. The child is killed at the end, whatever happens.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.acis_watchdog import _PLUGINS  # noqa: E402


async def _open_and_hold() -> None:
    from config.schemas import load_config
    from core.data.ctrader.feed import CTraderFeed
    from core.data.ctrader.meter import RequestMeter
    from core.data.ctrader.session import Credentials, CTraderSession
    from core.data.ctrader.tokens import TokenStore
    from core.data.jsonl_logging import JsonlEventLogger
    from core.execution.ctrader_attach import attach
    from core.execution.ctrader_face import CTraderExecutionFace
    from core.execution.ctrader_store import VenueStore

    cfg = load_config("config")
    venue = cfg.system.venue
    log = JsonlEventLogger(open("logs/ctrader_case8.jsonl", "a", encoding="utf-8"), "data", "ctrader-case8")
    now = datetime.now(timezone.utc)
    meter = RequestMeter("data/venue/ctrader.db", venue.account_key, budget=venue.daily_request_budget,
                         reserve=venue.close_reserve, now=now)
    session = CTraderSession.from_venue(venue, credentials=Credentials.from_env(), tokens=TokenStore.from_env(),
                                        meter=meter, logger=log)
    store = VenueStore("data/venue/ctrader.db", venue.account_key)
    result = await attach(venue, rulebook_key="pepperstone_demo", rulebook=cfg.platform_rules.accounts["pepperstone_demo"],
                          instruments=cfg.instruments.instruments, session=session, store=store, logger=log,
                          now=now, execution_cap=cfg.system.execution.max_venue_requests_per_day)
    report = result.report
    if report.verdict != "ATTACHED" or report.open_positions or not report.practice_eligible:
        print(f"REFUSED {report.verdict} {report.reason} positions={report.open_positions}", flush=True)
        return
    feed = CTraderFeed(session, result.feed_symbols, log)
    stream = feed.stream()
    while True:                                      # wait for a two-sided EUR_USD quote
        tick = await asyncio.wait_for(anext(stream), 60)
        if tick.instrument == "EUR_USD":
            break
    face = CTraderExecutionFace(session, result.specs, result.descriptor, store, log, account_key=store.account_key)
    face.start()
    await face.synchronise()
    spec, quote = result.specs["EUR_USD"], await feed.snapshot("EUR_USD")
    opened = await face.submit_order(fragment_id=f"case8-{int(time.time())}", order_id="case8", instrument="EUR_USD",
                                     direction=1, units=spec.min_units, requested_price=quote.ask, ioc=True,
                                     now=datetime.now(timezone.utc), session_id="case8",
                                     stop_loss=round(quote.ask - 0.0050, spec.digits))
    print(f"OPEN {opened.status.value} {opened.filled_units}", flush=True)
    await asyncio.sleep(3600)                        # hold the socket open; the parent stops and kills us


def _plugin_pass(wd: dict) -> dict:
    res = _PLUGINS["ctrader"](wd).flatten_all("")
    return {"ok": res.ok, "positions_closed": res.positions_closed, "error": res.error}


def main() -> int:
    from config.schemas import load_config
    wd = yaml.safe_load((ROOT / "config" / "watchdog.yaml").read_text(encoding="utf-8"))
    venue = load_config(str(ROOT / "config")).system.venue
    if venue.environment != "demo" or wd.get("environment") != "demo" \
            or int(wd.get("ctid_trader_account_id", 0)) != venue.ctid_trader_account_id:
        print("REFUSED: case 8 runs only on a demo binding that both config files agree on")
        return 2
    child = subprocess.Popen([sys.executable, __file__, "--child"], stdout=subprocess.PIPE, text=True, cwd=ROOT)
    out: dict = {"started": datetime.now(timezone.utc).isoformat()}
    try:
        line = child.stdout.readline().strip()
        out["child"] = line
        if not line.startswith("OPEN FILLED"):
            print(json.dumps(out))
            return 1
        os.kill(child.pid, signal.SIGSTOP)           # frozen engine, socket still open
        out["flatten"] = _plugin_pass(wd)
        out["second_pass"] = _plugin_pass(wd)        # reconciles again: 0 closed means flat
        out["flat"] = out["flatten"]["ok"] and out["flatten"]["positions_closed"] >= 1 \
            and out["second_pass"]["ok"] and out["second_pass"]["positions_closed"] == 0
    finally:
        child.kill()
        child.wait()
    print(json.dumps(out, indent=1))
    return 0 if out.get("flat") else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        asyncio.run(_open_and_hold())
    else:
        raise SystemExit(main())
