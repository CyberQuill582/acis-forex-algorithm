"""The MCP control plane's config block (ACIS-08 §5–§6), split out of config/schemas.py, which re-exports
it (GAP-P12M-01). Invariants: `tunable_paths` is the human-committed BOUNDED allowlist that
`acis_stage_config` may stage; a guardrail or equity path is refused at the schema, so it is
structurally unreachable (guard-integrity law, C-MCP-2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from config.calendars import _Strict


class TunableParam(_Strict):
    """One human-committed tunable `acis_stage_config` may stage, WITH its
    declared numeric bounds (ACIS-08 §5, GAP-P10I-01/GAP-P10E-04). Staging is
    safe BY CONSTRUCTION: a staged value must fall inside [min, max] — there is
    no substring heuristic to evade and no way to stage a risk-raising value on
    an allowlisted path. Guardrail/equity paths are structurally forbidden."""

    path: str
    min: float
    max: float

    @model_validator(mode="after")
    def _bounds_and_not_guardrail(self) -> "TunableParam":
        low = self.path.strip().lower()
        if low.startswith("guardrail_limits") or "equity_floor" in low:
            raise ValueError(
                f"tunable path {self.path!r} is a guardrail/equity path — "
                "structurally forbidden (guard-integrity law, ACIS-08 §5)")
        if self.min > self.max:
            raise ValueError(f"tunable {self.path!r}: min must be <= max")
        return self


class MonitoringConfig(_Strict):
    """MCP monitoring/control plane operational config (ACIS-08 §6). Required —
    the block is schema-fatal if missing. Guardrail LIMITS are NOT here (they
    live in guardrail_limits.yaml, read-only to this layer). `tunable_paths` is
    the human-committed BOUNDED allowlist `acis_stage_config` may touch;
    guardrail/equity paths are structurally excluded (ACIS-08 §5, C-MCP-2)."""

    transport: Literal["stdio", "sse"]
    heartbeat_fast_s: float = Field(gt=0, le=10.0)     # §12 fast-loop SLA ceiling
    heartbeat_other_s: float = Field(gt=0)
    missed_beats_flatten: int = Field(gt=0)            # §12: 3 missed beats → flatten rec
    log_tail_max: int = Field(gt=0)
    tunable_paths: list[TunableParam] = Field(min_length=1)  # bounded allowlist

    @model_validator(mode="after")
    def _unique_paths(self) -> "MonitoringConfig":
        seen = [t.path.strip() for t in self.tunable_paths]
        if len(set(seen)) != len(seen):
            raise ValueError("tunable_paths: duplicate path")
        return self

    def tunable_bounds(self) -> dict[str, tuple[float, float]]:
        """path -> (min, max) for the tool-layer validator."""
        return {t.path.strip(): (t.min, t.max) for t in self.tunable_paths}
