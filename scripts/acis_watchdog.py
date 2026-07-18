"""ACIS watchdog — the breaker that must not die with the loop (SPEC §8.6 v2.10,
ACIS-12 §2–8).

A separate, minimal OS process. It consumes the engine's heartbeat file and, on
silence beyond `watchdog_timeout_s` WITH open positions, flattens via the broker
plugin — from OUTSIDE the blast radius. It can ONLY ever flatten/halt: no
sizing, no resume, no config write, no strategy state.

**Guard-integrity law (§8.6): ZERO imports from `core/`.** This file uses stdlib
+ pyyaml only; an AST contract test proves it. The engine cannot reach this
process's config, and this process cannot expand risk — its entire broker
surface is one call, `flatten_all(credentials) -> FlattenResult`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FlattenResult:
    ok: bool
    positions_closed: int
    error: str = ""


class MockFlattenPlugin:
    """v1 flatten plugin (real per-platform plugins land with ACIS-13, phase 12).
    `script` lets tests force failures: a queue of bools consumed per call."""

    name = "mock"

    def __init__(self, script: list[bool] | None = None) -> None:
        self._script = list(script or [])
        self.calls = 0

    def flatten_all(self, credentials: str) -> FlattenResult:
        self.calls += 1
        ok = self._script.pop(0) if self._script else True
        if not ok:
            return FlattenResult(ok=False, positions_closed=0, error="mock: broker refused")
        return FlattenResult(ok=True, positions_closed=1)


_PLUGINS = {"mock": MockFlattenPlugin}


class WatchdogLogger:
    """Own JSONL log — the SPEC §11 envelope, but NOT sharing a handle with the
    process it watches (a separate file, own writer)."""

    def __init__(self, path: str | Path, session_id: str = "watchdog") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id

    def event(self, event_type: str, **data: object) -> None:
        rec = {"timestamp": datetime.now(timezone.utc).isoformat(),
               "event_type": event_type, "layer": "watchdog",
               "session_id": self._session_id, "data": data}
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


def resolve_credentials(ref: str) -> str:
    """`env:NAME` → the env var; anything else is treated as a literal ref.
    A secret is never stored in config — only a reference to it."""
    if ref.startswith("env:"):
        return os.environ.get(ref[4:], "")
    return ref


class Watchdog:
    """Pure, tick-driven core (tests call `poll(now)` directly; `main()` sleeps).
    Silence semantics: a missing/malformed heartbeat is SILENCE — the last good
    open_positions decides whether silence means flatten (positions) or alert
    (flat). Unknown never degrades to 'alive'."""

    def __init__(self, cfg: dict, plugin, logger: WatchdogLogger, *,
                 marker_path: str | Path, started_at: float) -> None:
        self._heartbeat_path = Path(cfg["heartbeat_path"])
        self._timeout = float(cfg["watchdog_timeout_s"])
        self._credentials = resolve_credentials(cfg.get("credentials_ref", ""))
        self._plugin = plugin
        self._log = logger
        self._marker = Path(marker_path)
        self._started_at = started_at
        # GAP-P9E-07: staleness is measured on the WATCHDOG's OWN timeline — the
        # local time at which the heartbeat CONTENT last changed — never
        # local-now minus the engine-written timestamp (an engine clock running
        # ahead would make stale beats look fresh and defeat the switch).
        self._sig: tuple | None = None            # last observed (ts_utc, seq)
        self._last_change_local: float | None = None
        self._last_good_positions = 0
        self._flattened = self._marker.exists()   # idempotent across restart

    def _read_heartbeat(self) -> dict | None:
        try:
            beat = json.loads(self._heartbeat_path.read_text(encoding="utf-8"))
            beat["open_positions"] = int(beat["open_positions"])
            _ = beat["ts_utc"]                     # presence check (part of the sig)
            return beat
        except (OSError, ValueError, KeyError, TypeError):
            return None                            # unreadable/malformed = silence

    def poll(self, now: float) -> str:
        beat = self._read_heartbeat()
        if beat is not None:
            self._last_good_positions = beat["open_positions"]
            sig = (beat["ts_utc"], beat.get("fast_loop_seq"))
            if sig != self._sig:                   # the engine wrote a NEW beat
                self._sig = sig
                self._last_change_local = now
                if self._flattened:                # engine recovered → re-arm
                    self._flattened = False        # (GAP-P9I-04: a SECOND outage
                    try:                           #  must flatten again)
                        self._marker.unlink()
                    except FileNotFoundError:
                        pass
                    self._log.event("WATCHDOG_REARMED")

        if self._last_change_local is None:
            # never seen a good beat — cannot confirm positions; after the
            # timeout, alert (never assume alive, never flatten blind).
            if now - self._started_at >= self._timeout:
                self._log.event("WATCHDOG_ALERT", reason="no_heartbeat_seen")
                return "alert"
            return "ok"

        age = now - self._last_change_local        # observer's own timeline
        if age <= self._timeout:
            return "ok"                            # fresh — no action

        self._log.event("WATCHDOG_STALE", age_s=round(age, 3),
                        open_positions=self._last_good_positions)
        if self._last_good_positions <= 0:
            self._log.event("WATCHDOG_ALERT", reason="stale_but_flat")
            return "alert"                         # silence + flat = alert only
        if self._flattened:
            return "already_flattened"             # idempotent — flatten once
        try:
            result = self._plugin.flatten_all(self._credentials)
        except Exception as exc:                   # noqa: BLE001 — loud, never silent
            self._log.event("WATCHDOG_FLATTEN_FAILED", error=repr(exc))
            return "flatten_failed"
        if not result.ok:
            self._log.event("WATCHDOG_FLATTEN_FAILED", error=result.error)
            return "flatten_failed"                # retried on the next poll (backoff)
        self._flattened = True
        self._marker.write_text(str(now), encoding="utf-8")
        self._log.event("WATCHDOG_FLATTEN", positions=result.positions_closed)
        return "flatten"


def load_watchdog_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACIS watchdog (SPEC §8.6)")
    parser.add_argument("--config", default="config/watchdog.yaml")
    parser.add_argument("--log", default="logs/watchdog_log.jsonl")
    parser.add_argument("--marker", default="logs/.watchdog_flatten_marker")
    args = parser.parse_args(argv)

    cfg = load_watchdog_config(args.config)
    plugin_name = cfg.get("flatten_plugin", "mock")
    plugin = _PLUGINS[plugin_name]()
    logger = WatchdogLogger(args.log)
    wd = Watchdog(cfg, plugin, logger, marker_path=args.marker,
                  started_at=time.time())
    logger.event("WATCHDOG_STARTED", heartbeat_path=cfg["heartbeat_path"],
                 timeout_s=cfg["watchdog_timeout_s"], plugin=plugin_name)
    poll_interval = float(cfg["poll_interval_s"])
    while True:                                     # pragma: no cover — the live loop
        wd.poll(time.time())
        time.sleep(poll_interval)


if __name__ == "__main__":                         # pragma: no cover
    raise SystemExit(main())
