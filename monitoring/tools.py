"""MCP control tools (ACIS-08 §4/§7, master §12).

The safety asymmetry is structural: the only tools open to agents are the ones
that REDUCE activity (halt/flatten) or are read-only analysis (report/backtest)
or staged-and-boundary-gated (stage_config). Every tool that INCREASES activity
or risk (resume, set_mode live) is human-token gated. "Halts are cheap; resumes
are human-only" (CLAUDE.md).

Every call is idempotent by `request_id` (C-MCP-3) and audit-logged (§9). This
layer maps intents onto injected NARROW interfaces — it holds no trading logic
and cannot reach a guardrail (C-MCP-4).
"""

from __future__ import annotations

import math
from typing import Callable, Protocol, runtime_checkable

from monitoring.auth import HumanTokenVerifier
from monitoring.mode import ModeChangeRejected, ModeController
from monitoring.store import AuditRecord, McpAuditStore


@runtime_checkable
class ControlTarget(Protocol):
    """The single narrow control surface (an adapter over Governor + the flatten
    path, wired at runtime). Restrictive verbs + the human-gated resume — there
    is deliberately no `set_size`/`raise_limit` here (master §2/§12)."""

    def apply_halt(self, scope: str, reason: str) -> None: ...
    def flatten(self, scope: str, reason: str) -> None: ...
    def resume(self, human_token: str) -> None: ...


class ConfigStager(Protocol):
    """Stages a tunable-value patch into the QIEA-style pending path (ACIS-03);
    promoted only at the next session boundary, never mid-session, never to a
    guardrail (the allowlist + schema already excluded those)."""

    def stage_config(self, patch: dict, rationale: str) -> str: ...


# Tools open to any agent (reduce activity / staged / read-only analysis) vs
# tools that require a verified human token (start/raise activity).
_HUMAN_GATED = {"acis_resume", "acis_set_mode"}
_ALL_TOOLS = {
    "acis_halt", "acis_flatten", "acis_resume", "acis_set_mode",
    "acis_stage_config", "acis_run_backtest", "acis_report",
}


class ControlTools:
    """Single-threaded by contract (the MCP stdio transport dispatches one call
    at a time); the store's request_id PK is the backstop against a concurrent
    duplicate racing the check-then-act window (GAP-P10E-01)."""

    def __init__(self, *, control: ControlTarget, auth: HumanTokenVerifier,
                 mode_controller: ModeController, stager: ConfigStager,
                 tunable_bounds: dict[str, tuple[float, float]],
                 audit: McpAuditStore, logger, session_id: str,
                 backtest_runner: Callable[[dict], str] | None = None,
                 reporter: Callable[[str], str] | None = None) -> None:
        self._control = control
        self._auth = auth
        self._mode = mode_controller
        self._stager = stager
        self._bounds = {p.strip(): (lo, hi) for p, (lo, hi) in tunable_bounds.items()}
        self._audit = audit
        self._log = logger
        self._session = session_id
        self._backtest = backtest_runner
        self._report = reporter

    # -- public dispatch -------------------------------------------------------- #

    def call_tool(self, name: str, request: dict, *, caller: str = "agent") -> dict:
        """Validate envelope → idempotency → dispatch (auth inside). Exactly-once
        by request_id: a side-effecting outcome (ok/error) is recorded so a
        replay NEVER re-executes; a pure pre-dispatch rejection (no side effect)
        is NOT cached, so a legitimate retry with the same id is allowed
        (GAP-P10I-04/09, GAP-P10E-01)."""
        if name not in _ALL_TOOLS:
            return {"status": "rejected", "reason": f"unknown_tool:{name}"}
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            return {"status": "rejected", "reason": "missing_request_id"}

        prior = self._audit.find(request_id)
        if prior is not None:                       # C-MCP-3: never re-execute
            return {"status": "idempotent_replay", "result": prior.result,
                    "request_id": request_id}

        try:
            result, is_human = self._dispatch(name, request)
        except Exception as exc:                    # crash AFTER a partial side
            # effect: record it so a replay returns the error, never re-executes.
            result, is_human = f"error:{type(exc).__name__}:{exc}", name in _HUMAN_GATED

        # A pure rejection (auth/schema/bad-arg) never reached a downstream call,
        # so it is safe to NOT persist — the client may retry the same id. Every
        # side-effecting or errored outcome IS persisted (exactly-once).
        if not result.startswith("rejected:"):
            if not self._audit.record_once(AuditRecord(
                    request_id=request_id, tool=name, caller=caller,
                    is_human=is_human, args=request.get("args", {}) or {},
                    result=result, session_id=self._session)):
                # a concurrent duplicate won the race; return its stored result.
                won = self._audit.find(request_id)
                if won is not None:
                    return {"status": "idempotent_replay", "result": won.result,
                            "request_id": request_id}
        self._log.event("MCP_TOOL", tool=name, request_id=request_id,
                        caller=caller, human=is_human, result=result)
        status = "ok" if result.startswith("ok") else "rejected"
        return {"status": status, "result": result, "request_id": request_id}

    # -- per-tool handlers ------------------------------------------------------ #

    def _dispatch(self, name: str, request: dict) -> tuple[str, bool]:
        args = request.get("args", {}) or {}
        token = request.get("human_token")

        if name in _HUMAN_GATED:
            if not self._auth.verify(token):
                self._log.event("AUTH_REJECT", tool=name)
                return "rejected:auth", False

        if name == "acis_halt":
            scope = str(args.get("scope", "all"))
            self._control.apply_halt(scope, str(args.get("reason", "mcp_halt")))
            return f"ok:halted:{scope}", False

        if name == "acis_flatten":
            self._control.flatten("all", str(args.get("reason", "mcp_flatten")))
            return "ok:flattened", False

        if name == "acis_resume":
            # token already verified above; the Governor's own teeth re-check it.
            self._control.resume(str(token))
            return "ok:resumed", True

        if name == "acis_set_mode":
            mode = args.get("mode")
            if mode not in ("backtest", "paper", "live"):
                return f"rejected:bad_mode:{mode}", True
            try:
                self._mode.set_mode(
                    mode, guardrail_hash=args.get("guardrail_hash"),
                    rulebook_hash=args.get("rulebook_hash"))
            except ModeChangeRejected as exc:
                return f"rejected:{exc}", True
            return f"ok:mode:{mode}", True

        if name == "acis_stage_config":
            reason = self._validate_patch(args.get("patch"))
            if reason is not None:
                self._log.event("STAGE_CONFIG_REJECT", path=reason)
                return f"rejected:{reason}", False
            staged_id = self._stager.stage_config(
                dict(args["patch"]), str(args.get("rationale", "")))
            return f"ok:staged:{staged_id}", False

        if name == "acis_run_backtest":
            if self._backtest is None:
                return "ok:unavailable", False
            return f"ok:{self._backtest(args)}", False

        if name == "acis_report":
            if self._report is None:
                return "ok:unavailable", False
            return f"ok:{self._report(str(args.get('period', 'daily')))}", False

        return f"rejected:unhandled:{name}", False   # unreachable — guarded above

    # -- stage_config bounded allowlist (C-MCP-2) ------------------------------- #

    def _validate_patch(self, patch) -> str | None:
        """Return a rejection reason, or None if the patch is a legal staged
        tunable. Safe BY CONSTRUCTION (GAP-P10I-01/02, GAP-P10E-04): every path
        must be in the human-committed bounded allowlist AND its value must be a
        finite number inside the declared [min, max] — no substring heuristic,
        no string/negative/inf evasion, no risk-raising value on any path.
        Guardrail/equity paths are rejected first (defense in depth)."""
        if not isinstance(patch, dict) or not patch:
            return "empty_or_invalid_patch"
        for raw_path, value in patch.items():
            path = str(raw_path).strip()
            low = path.lower()
            if low.startswith("guardrail_limits") or "equity_floor" in low:
                return f"guardrail_path:{raw_path}"
            if path not in self._bounds:
                return f"not_in_allowlist:{raw_path}"
            # require a real numeric TYPE (bool is an int subclass — reject; a
            # string like "1.5" is rejected outright, never coerced-and-staged).
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"non_numeric:{raw_path}"
            num = float(value)
            if not math.isfinite(num):
                return f"non_finite:{raw_path}"
            lo, hi = self._bounds[path]
            if not (lo <= num <= hi):
                return f"out_of_bounds:{raw_path}"   # incl. negative/zero/over-cap
        return None
