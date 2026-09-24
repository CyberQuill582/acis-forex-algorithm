"""Watchdog contract (ACIS-12 §14, C-SWN-6, master §8.6)."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
WATCHDOG_PY = REPO / "scripts" / "acis_watchdog.py"


def _load_watchdog():
    spec = importlib.util.spec_from_file_location("acis_watchdog", WATCHDOG_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["acis_watchdog"] = mod       # dataclass resolution needs this
    spec.loader.exec_module(mod)
    return mod


wd_mod = _load_watchdog()


def _write_beat(path: Path, ts: datetime, positions: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ts_utc": ts.astimezone(timezone.utc).isoformat(), "session_id": "s1",
        "mode": "paper", "open_positions": positions, "fast_loop_seq": 1}),
        encoding="utf-8")


def _make(tmp_path, *, timeout=30, plugin_script=None, started_at=1000.0):
    hb = tmp_path / "heartbeat.json"
    cfg = {"heartbeat_path": str(hb), "watchdog_timeout_s": timeout,
           "poll_interval_s": 5, "flatten_plugin": "mock", "credentials_ref": "x"}
    plugin = wd_mod.MockFlattenPlugin(script=plugin_script)
    logger = wd_mod.WatchdogLogger(tmp_path / "watchdog_log.jsonl")
    wd = wd_mod.Watchdog(cfg, plugin, logger, marker_path=tmp_path / ".marker",
                         started_at=started_at)
    return wd, plugin, hb, tmp_path / "watchdog_log.jsonl"


def _events(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


# -- C-SWN-6: zero core/ imports (AST-proven) -------------------------------- #

def test_watchdog_imports_nothing_from_core() -> None:
    tree = ast.parse(WATCHDOG_PY.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names if a.name.split(".")[0] == "core"]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] == "core":
                offenders.append(node.module)
    assert not offenders, f"watchdog must not import from core/: {offenders}"


# -- silence + positions ⇒ exactly one flatten (idempotent across polls) ------ #

def test_stale_with_positions_flattens_once(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=0.0)
    beat_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    _write_beat(hb, beat_time, positions=2)
    now = beat_time.timestamp()
    assert wd.poll(now) == "ok"                         # fresh
    stale = now + 40
    assert wd.poll(stale) == "flatten"                  # silence + positions
    assert wd.poll(stale + 5) == "already_flattened"    # idempotent
    assert wd.poll(stale + 10) == "already_flattened"
    assert plugin.calls == 1
    kinds = [e["event_type"] for e in _events(log)]
    assert kinds.count("WATCHDOG_FLATTEN") == 1


# -- stale + flat ⇒ alert only ----------------------------------------------- #

def test_stale_but_flat_alerts_only(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=0.0)
    beat_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    _write_beat(hb, beat_time, positions=0)
    assert wd.poll(beat_time.timestamp()) == "ok"          # establish the baseline
    assert wd.poll(beat_time.timestamp() + 40) == "alert"  # no update → stale + flat
    assert plugin.calls == 0
    assert any(e["event_type"] == "WATCHDOG_ALERT"
               and e["data"]["reason"] == "stale_but_flat" for e in _events(log))


# -- malformed / missing heartbeat = silence (last-good decides) -------------- #

def test_malformed_heartbeat_is_silence(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=0.0)
    beat_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    _write_beat(hb, beat_time, positions=3)
    wd.poll(beat_time.timestamp())                      # establishes last-good
    hb.write_text("{ this is not json", encoding="utf-8")   # corrupt
    # silence beyond timeout with last-good positions>0 ⇒ flatten (not "alive")
    assert wd.poll(beat_time.timestamp() + 45) == "flatten"


def test_never_seen_heartbeat_alerts_not_flattens(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=1000.0)
    # no heartbeat file at all; before timeout = ok, after = alert (cannot
    # confirm positions, never flatten blind)
    assert wd.poll(1005.0) == "ok"
    assert wd.poll(1040.0) == "alert"
    assert plugin.calls == 0
    assert any(e["data"].get("reason") == "no_heartbeat_seen" for e in _events(log))


# -- plugin failure ⇒ retry + WATCHDOG_FLATTEN_FAILED ------------------------ #

def test_flatten_failure_retries(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, plugin_script=[False, True],
                                started_at=0.0)
    beat_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    _write_beat(hb, beat_time, positions=1)
    assert wd.poll(beat_time.timestamp()) == "ok"       # establish the baseline
    stale = beat_time.timestamp() + 40
    assert wd.poll(stale) == "flatten_failed"           # first attempt refused
    assert wd.poll(stale + 5) == "flatten"              # retried, succeeded
    assert plugin.calls == 2
    kinds = [e["event_type"] for e in _events(log)]
    assert "WATCHDOG_FLATTEN_FAILED" in kinds and "WATCHDOG_FLATTEN" in kinds


# -- GAP-P9E-07: clock skew (engine ahead) must not defeat the switch --------- #

def test_clock_skew_engine_ahead_still_flattens(tmp_path) -> None:
    # The engine's embedded ts_utc runs 10 min AHEAD of the watchdog's clock.
    # Staleness is measured on the WATCHDOG's own timeline (content-change), so a
    # future-timestamped-but-frozen heartbeat still goes stale and flattens.
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=0.0)
    engine_clock = datetime(2026, 7, 15, 12, 10, tzinfo=timezone.utc)  # +10 min ahead
    _write_beat(hb, engine_clock, positions=1)          # ts_utc is in the "future"
    assert wd.poll(0.0) == "ok"                          # observed now (local t=0)
    assert wd.poll(40.0) == "flatten"                    # content frozen 40s → stale
    assert plugin.calls == 1


# -- GAP-P9I-04: a SECOND outage after recovery must flatten again ------------ #

def test_second_outage_after_recovery_flattens_again(tmp_path) -> None:
    wd, plugin, hb, log = _make(tmp_path, timeout=30, started_at=0.0)
    t = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    _write_beat(hb, t, positions=1)
    assert wd.poll(0.0) == "ok"
    assert wd.poll(40.0) == "flatten"                   # first outage → flatten
    # engine recovers: a NEW beat (fresh ts_utc → changed content) → re-arm
    _write_beat(hb, t.replace(minute=1), positions=1)
    assert wd.poll(45.0) == "ok"
    assert any(e["event_type"] == "WATCHDOG_REARMED" for e in _events(log))
    # engine hangs AGAIN → the second outage flattens again (not "already")
    assert wd.poll(90.0) == "flatten"
    assert plugin.calls == 2


# -- heartbeat writer emits atomically + monotonically (engine side, ACIS-07) - #

def test_heartbeat_writer_atomic_and_readable(tmp_path) -> None:
    from config.schemas import load_config
    from core.risk.monitor import RiskMonitor
    cfg = load_config(REPO / "config")
    risk_cfg = cfg.system.risk.model_copy(
        update={"heartbeat_path": str(tmp_path / "hb.json")})

    class _NullSink:
        def apply_halt(self, *a, **k): pass
        def apply_session_halt(self, *a, **k): pass
        def apply_risk_state(self, *a, **k): pass
        def flatten(self, *a, **k): pass

    from tests.optimizer_fixtures import CapturingLogger
    from core.risk.guardrails import Guardrails, build_drawdown_series
    from core.risk.alpha_decay import AlphaDecayDetector
    log = CapturingLogger()
    rb = cfg.platform_rules.accounts["dev_paper"]
    series = build_drawdown_series(cfg.guardrails, rb.drawdown_rules, "dev_paper",
                                   initial_capital=rb.initial_capital)
    g = Guardrails(cfg.guardrails, risk_cfg, series, _NullSink(), log,
                   taper_start=0.60, entry_halt=0.80)
    alpha = AlphaDecayDetector(recent_window=50, min_trades=30,
                               baseline_min_trades=50, sharpe_mult=0.5,
                               recovery_trades=20, recovery_mult=0.8)
    mon = RiskMonitor(risk_cfg, cfg.guardrails, g, alpha, _NullSink(),
                      cfg.instruments.clusters, "s1", log)
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    mon.write_heartbeat(now, "paper", 7)
    beat = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert beat["fast_loop_seq"] == 7 and beat["mode"] == "paper"
    assert beat["open_positions"] == 0
    # no leftover temp file (atomic replace)
    assert not list(tmp_path.glob("hb.json.tmp*"))
