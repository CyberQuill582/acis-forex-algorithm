"""Read-only MCP resources (ACIS-08 §4/§7, master §12).

Every resource is a bounded, read-only VIEW served from injected providers
(callables returning JSON-able data produced by the layers/stores). No resource
can mutate state; there is no write path to guardrails or rulebooks anywhere in
this module (C-MCP-4).

Untrusted-input law (C-MCP-7): headlines, log lines and provenance notes are
returned as DATA. This module never interprets resource content as a directive —
there is no code path from a resource string to a control action.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable, Mapping

from monitoring.heartbeat import HeartbeatMonitor

_CANON = (
    "status", "risk/snapshot", "regime/current", "params/active",
    "params/pending", "performance/daily", "config/guardrails",
    "events/picture", "pairs/relationships", "strategies/provenance",
    "account/rules", "venues/adapters",
)

# GAP-0078: the three per-layer skip views are NOT a partition — a single
# physical veto appears in both `nvma[<reason>]` and `agon["vetoed_regime"]`.
# Consumers read PER LAYER and must NOT sum across layers (that double-counts
# every veto). The contract rides on the resource so a consumer cannot miss it.
_SKIP_CONTRACT = (
    "per-layer views, NOT a partition; do not sum across layers "
    "(one veto appears in both nvma and agon) — GAP-0078 / ACIS-08 §5"
)


class ResourceError(Exception):
    """Unknown resource URI or a provider failure (returned as an error view)."""


class Resources:
    def __init__(self, *, providers: Mapping[str, Callable[[], object]],
                 mode_getter: Callable[[], str], guardrail_view: dict,
                 guardrail_hash: str, rulebook_hash: str, log_tail_max: int,
                 log_reader: Callable[[str, int], list] | None = None,
                 heartbeat_monitor: HeartbeatMonitor | None = None,
                 heartbeat_getter: Callable[[], tuple[datetime | None, int]] | None = None,
                 now_fn: Callable[[], datetime] | None = None) -> None:
        self._p = dict(providers)
        self._mode = mode_getter
        self._guardrail_view = copy.deepcopy(dict(guardrail_view))
        self._guardrail_hash = guardrail_hash
        self._rulebook_hash = rulebook_hash
        self._log_tail_max = log_tail_max
        self._log_reader = log_reader
        self._hb_monitor = heartbeat_monitor
        self._hb_getter = heartbeat_getter
        self._now_fn = now_fn

    # -- dispatch --------------------------------------------------------------- #

    def read(self, uri: str) -> dict:
        if not uri.startswith("acis://"):
            raise ResourceError(f"not an acis resource: {uri!r}")
        path = uri[len("acis://"):]
        if path.startswith("logs/tail/"):
            return self._logs_tail(path[len("logs/tail/"):])
        if path == "status":
            return self._status()
        if path == "config/guardrails":
            # deep copy on read (GAP-P10I-07): a caller mutating the returned
            # view cannot change what the next reader sees — the resource is
            # observably read-only.
            return {"limits": copy.deepcopy(self._guardrail_view),
                    "hash": self._guardrail_hash}
        if path == "account/rules":
            return self._account_rules()
        if path in _CANON:
            return self._provider_view(path)
        raise ResourceError(f"unknown resource: {uri!r}")

    # -- individual views ------------------------------------------------------- #

    def _provider_view(self, name: str) -> dict:
        provider = self._p.get(name)
        if provider is None:
            return {"available": False, "resource": name}
        try:
            return {"available": True, "resource": name, "data": provider()}
        except Exception as exc:                     # never mutate; return error view
            return {"available": False, "resource": name, "error": str(exc)}

    def _status(self) -> dict:
        view = {"mode": self._mode()}
        raw = self._p.get("status")
        if raw is not None:
            try:
                payload = dict(raw())  # type: ignore[arg-type]
            except Exception as exc:
                return {"mode": self._mode(), "available": False, "error": str(exc)}
            # Wrap the per-gate skip attribution with its non-partition contract.
            if "skip_attribution" in payload:
                payload["skip_attribution"] = {
                    "views": payload["skip_attribution"],
                    "_contract": _SKIP_CONTRACT,
                }
            view.update(payload)
        # C-MCP-6: the server computes+surfaces the missed-beat state and the
        # flatten RECOMMENDATION (it never flattens — the orchestrator's call).
        hb = self._heartbeat_state()
        if hb is not None:
            view["heartbeat"] = hb
        return view

    def _heartbeat_state(self) -> dict | None:
        if self._hb_monitor is None or self._hb_getter is None:
            return None
        now = self._now_fn() if self._now_fn is not None else datetime.now(timezone.utc)
        last_beat, open_positions = self._hb_getter()
        return self._hb_monitor.state(
            last_beat=last_beat, now=now, open_positions=open_positions).as_dict()

    def _account_rules(self) -> dict:
        provider = self._p.get("account/rules")
        base = {"resource": "account/rules", "rulebook_hash": self._rulebook_hash}
        if provider is None:
            base["available"] = False
            return base
        try:
            base["available"] = True
            base["data"] = provider()
        except Exception as exc:
            base["available"] = False
            base["error"] = str(exc)
        return base

    def _logs_tail(self, stream: str) -> dict:
        if self._log_reader is None:
            return {"stream": stream, "available": False, "lines": []}
        lines = list(self._log_reader(stream, self._log_tail_max))[-self._log_tail_max:]
        return {"stream": stream, "available": True, "lines": lines,
                "truncated_to": self._log_tail_max}
