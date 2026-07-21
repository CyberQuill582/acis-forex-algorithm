"""MCP server facade (ACIS-08 §2/§3, master §12).

`ControlPlane` IS the MCP contract: the read-only resource surface + the gated
control tools + the canonical prompts, assembled over narrow INJECTED interfaces
(a control target, read-only providers, the mode controller, a config stager,
an audit store, a human-token verifier). It holds no trading logic and imports
no `core/*` layer internals (C-MCP-4).

`serve()` is where a real MCP stdio/SSE transport binds to this facade. The
transport itself is a thin adapter deferred to deployment (the same lean-build
split as the §7.5 feed/execution transports): everything the phase-10 contract
must guarantee — auth asymmetry, guardrail-unreachability, idempotency, the
untrusted-input law, the dual-hash live gate — lives on `ControlPlane` and is
tested directly, transport-independent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Mapping

from monitoring.auth import HumanTokenVerifier
from monitoring.heartbeat import HeartbeatMonitor
from monitoring.mode import ModeController
from monitoring.prompts import CANONICAL_PROMPTS, PROMPTS_BY_NAME
from monitoring.resources import Resources
from monitoring.store import McpAuditStore
from monitoring.tools import ConfigStager, ControlTarget, ControlTools


class ControlPlane:
    """The assembled, transport-independent MCP contract."""

    def __init__(self, *, control: ControlTarget, auth: HumanTokenVerifier,
                 mode_controller: ModeController, stager: ConfigStager,
                 providers: Mapping[str, Callable[[], object]],
                 guardrail_view: dict, guardrail_hash: str, rulebook_hash: str,
                 tunable_bounds: dict[str, tuple[float, float]],
                 log_tail_max: int, logger, session_id: str,
                 audit: McpAuditStore | None = None,
                 log_reader: Callable[[str, int], list] | None = None,
                 heartbeat_monitor: HeartbeatMonitor | None = None,
                 heartbeat_getter: Callable[[], tuple[datetime | None, int]] | None = None,
                 now_fn: Callable[[], datetime] | None = None,
                 backtest_runner: Callable[[dict], str] | None = None,
                 reporter: Callable[[str], str] | None = None) -> None:
        self._audit = audit or McpAuditStore()
        self._mode = mode_controller
        self.resources = Resources(
            providers=providers, mode_getter=lambda: mode_controller.mode,
            guardrail_view=guardrail_view, guardrail_hash=guardrail_hash,
            rulebook_hash=rulebook_hash, log_tail_max=log_tail_max,
            log_reader=log_reader, heartbeat_monitor=heartbeat_monitor,
            heartbeat_getter=heartbeat_getter, now_fn=now_fn)
        self.tools = ControlTools(
            control=control, auth=auth, mode_controller=mode_controller,
            stager=stager, tunable_bounds=tunable_bounds, audit=self._audit,
            logger=logger, session_id=session_id,
            backtest_runner=backtest_runner, reporter=reporter)
        self.prompts = CANONICAL_PROMPTS

    # -- MCP surface ------------------------------------------------------------ #

    def read_resource(self, uri: str) -> dict:
        return self.resources.read(uri)

    def call_tool(self, name: str, request: dict, *, caller: str = "agent") -> dict:
        return self.tools.call_tool(name, request, caller=caller)

    def list_prompts(self) -> list[dict]:
        return [{"name": p.name, "purpose": p.purpose, "reads": list(p.reads)}
                for p in self.prompts]

    def get_prompt(self, name: str) -> dict | None:
        p = PROMPTS_BY_NAME.get(name)
        return None if p is None else {
            "name": p.name, "purpose": p.purpose, "reads": list(p.reads)}


def serve(plane: ControlPlane) -> None:                # pragma: no cover
    """Bind a real MCP stdio/SSE transport to `plane`. Deferred to deployment
    (the transport is a thin adapter, like the §7.5 feed/execution transports);
    the contract `plane` enforces is what phase 10 builds and tests."""
    raise NotImplementedError(
        "MCP transport binding lands at deployment (ACIS-08 §3 scope note); "
        "the ControlPlane contract is complete and tested transport-independent.")
