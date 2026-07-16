# ACIS-08 — Monitoring & MCP Control Plane — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-MCP-008` |
| **Version** | 1.0 (DRAFT) |
| **Layer / DIR** | Cross-cutting control plane · `[DIR:monitoring]` |
| **Consumes** | read-only views of all stores/logs; control intents from an orchestrator/human |
| **Emits** | MCP resources (read) + MCP tools (control) → mapped onto Governor/Risk interfaces |
| **Depends On** | `../ACIS_SPEC.md` §12, §9, §2 · all layers (observes), `ACIS-05`/`ACIS-07` (control targets) |
| **Blocks** | live-mode enablement (phase 11) |
| **Corrections applied** | human-token gate, `acis_stage_config` guardrail-path rejection, heartbeat SLAs, safety asymmetry, idempotency |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract (resources/tools) · 5. Schemas · 6. Config & auth · 7. Core logic · 8. State/heartbeat contract · 9. Persistence & logging · 10. Store schema · 11. MCP contract (the tool/resource spec) · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Be the *only* way anything outside the fast loop observes or controls ACIS. An orchestrator (Phronesis, or any compliant MCP client) or a human harness supervises ACIS through this MCP server — no side channels, no ad-hoc HTTP (master §12, CLAUDE.md MCP discipline).

**IS:** an MCP server (stdio + optional SSE) exposing read-only resources and schema-validated control tools; the human-token gate; the guardrail-path rejection for `acis_stage_config`; the orchestrator heartbeat contract; canonical report prompts.

**IS NOT:** it is not in the fast loop and never sizes/signals/executes; it cannot weaken a guardrail, resume without a human, or inject a signal; it is not a web dashboard (master §17 — MCP resources *are* the interface in v1). It holds no trading logic — it maps intents onto the Governor/Risk interfaces that already enforce the rules.

**Done-when:** halt/flatten are agent-callable and take effect; resume/set-mode(live) are rejected without a human token; `acis_stage_config` rejects guardrail paths at the schema level; heartbeats and the 3-missed-beat rule work; all tools are idempotent by `request_id`; §14 tests pass.

## 2. Entry contract

**Entry point:** `monitoring/server.py::serve()` starts the MCP server; tool handlers call injected, narrow interfaces: `governor.apply_halt/flatten/resume`, `risk.snapshot`, `param_library.stage`, `mode_controller.set_mode`, and read-only store/log readers. It imports **no** fast-loop internals beyond these interfaces (observes via stores/logs; controls via the two sanctioned interfaces).

**Inputs:** MCP requests (resource reads, tool calls with `request_id` + optional `human_token`); config `monitoring:`; the store/log readers.

## 3. Architecture & responsibility

Units: `server.py` (MCP wiring), `resources.py` (read-only views), `tools.py` (control tools + auth), `prompts.py` (report templates), `auth.py` (human-token verification). Single responsibility: **observability + gated control.** The safety rules are enforced *downstream* (Governor/Risk); this layer's job is to (a) never offer a tool that bypasses them, and (b) enforce the human-vs-agent asymmetry and idempotency.

## 4. Output contract — resources & tools

**Resources (read-only):**
| Resource | Content |
|---|---|
| `acis://status` | mode (backtest\|paper\|live), loop heartbeats, open positions, session |
| `acis://risk/snapshot` | latest `RiskSnapshot` (incl. `alpha_decay_state`) |
| `acis://regime/current` | latest `RegimeContext` per instrument (incl. advisory half-life) |
| `acis://params/active` · `acis://params/pending` | active sets + pending (incl. `boundaries_skipped`/stall) |
| `acis://performance/daily` | daily perf rollup |
| `acis://config/guardrails` | **read-only** view of `guardrail_limits.yaml` |
| `acis://logs/tail/{stream}` | bounded, filterable tail of a log stream |

**Tools (schema-validated, idempotent via `request_id`, audit-logged to `risk_log`):**
| Tool | Auth | Effect |
|---|---|---|
| `acis_halt(scope: all\|instrument, reason)` | any agent | → `governor.apply_halt` (Risk HALT semantics) |
| `acis_flatten(reason)` | any agent | close all positions then halt |
| `acis_resume(scope)` | **human token** | clear a halt (never for equity/global without human) |
| `acis_set_mode(backtest\|paper\|live)` | **human token**; live also needs guardrail-hash ack | change mode |
| `acis_stage_config(patch, rationale)` | agent (staged) | stage a *tunable* change for next boundary; **guardrail paths rejected at schema level** |
| `acis_run_backtest(params)` · `acis_report(period)` | agent | out-of-band analysis |

## 5. Schemas

- **Tool request envelope:** `{request_id: str, human_token?: str, args: {...}}`. `request_id` makes every tool idempotent (a repeated `request_id` returns the first result, does not re-execute).
- **`acis_stage_config` patch schema:** a JSON-Schema that **enumerates the allowed tunable paths** (allowlist) and structurally excludes anything under `guardrail_limits.*` and `*.equity_floor` — a patch touching those fails schema validation *before* any handler runs (defense in depth: schema rejects, and the handler re-checks).
- **`acis_set_mode(live)`:** requires `guardrail_hash` matching the current `guardrail_limits.yaml` hash (so a human explicitly acknowledges the exact limits in force before going live).

## 6. Config & auth

- **Human token:** a human-only credential (out-of-band issuance; verified in `auth.py`). Agent identities never possess it. The token gates `acis_resume`, `acis_set_mode`, and any equity/global HALT clear. This encodes the master §12 asymmetry: **any agent may stop trading; only a human may start it.**
- **Config (`monitoring:`):** `transport: stdio|sse`, `heartbeat_fast_s:10`, `heartbeat_other_s:60`, `missed_beats_flatten:3`, `log_tail_max`, allowed tunable-path allowlist. Guardrail limits are **not** here — they live in `guardrail_limits.yaml` and are read-only to this layer.

## 7. Core logic

1. **Resource read:** serve a bounded, read-only view from stores/logs. No resource can mutate state. `acis://config/guardrails` is read-only — there is no write path to guardrails anywhere in the server.
2. **Tool call:** validate schema → check idempotency (`request_id`) → check auth (human-token where required) → call the narrow downstream interface → audit-log to `risk_log` with the caller identity + `request_id`.
3. **`acis_stage_config`:** schema allowlist rejects guardrail/equity paths → stage the patch into the QIEA-style pending path (promoted at next session boundary, ACIS-03) → never applies mid-session, never to guardrails.
4. **`acis_resume`/`set_mode`:** reject without a valid human token (log `AUTH_REJECT`); `set_mode(live)` additionally requires the guardrail-hash ack and that §14 minimums were met (the mode controller checks the validation record).
5. **Safety asymmetry enforced structurally:** the only tools that *reduce* activity (halt/flatten) are open to agents; every tool that *increases* activity or risk (resume, go-live, config) is gated. This mirrors "halts are cheap; resumes are human-only" (CLAUDE.md).

## 8. State / heartbeat contract

Each loop writes a heartbeat into `acis://status`: fast loop ≤ `heartbeat_fast_s` (10 s), medium/slow ≤ `heartbeat_other_s` (60 s) (master §12). **Orchestrator contract:** 3 missed fast-loop beats **with open positions** → the orchestrator should call `acis_flatten` (the safety asymmetry again — the external supervisor can stop, but only a human restarts). The server reports missed-beat state; it does not itself flatten (that is the orchestrator's call), but a stalled fast loop with open positions also triggers the Risk Monitor's own flatten-and-halt (master §10) — belt and suspenders.

## 9. Persistence & logging

Every tool call and its outcome logs to `risk_log` (JSONL): `MCP_TOOL{tool, request_id, caller, human:bool, result}`, `AUTH_REJECT`, `STAGE_CONFIG_REJECT{path}`, `MODE_CHANGE`, `HEARTBEAT_MISS`. The control plane's audit trail is part of the risk audit spine — every halt/flatten/resume is attributable to a caller and (for resume/live) a human.

## 10. Store schema (DDL)

```sql
CREATE TABLE mcp_audit (
    request_id TEXT PRIMARY KEY,     -- idempotency key
    ts TIMESTAMPTZ NOT NULL,
    tool TEXT NOT NULL,
    caller TEXT NOT NULL,
    is_human BOOLEAN NOT NULL,
    args JSONB NOT NULL,
    result TEXT NOT NULL,            -- ok | rejected:<reason>
    session_id TEXT NOT NULL
);
```
`request_id` PK enforces idempotency at the store level too (a duplicated tool call cannot double-execute).

## 11. MCP contract (authoritative resource/tool spec)

This layer *is* the MCP contract (master §12). The resource/tool tables in §4 are the canonical list; adding a resource or tool requires a master-spec edit (no ad-hoc endpoints). **Prompts:** `daily-performance-brief` and `halt-postmortem` are canonical templates for LLM-side analysis, reading only from resources/logs. All observability and control flow through here — a component adding a side channel violates CLAUDE.md MCP discipline and must fail review.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| tool missing/invalid `human_token` where required | reject, `AUTH_REJECT`, no effect |
| `acis_stage_config` touching guardrail/equity path | schema reject, `STAGE_CONFIG_REJECT`, no effect |
| duplicate `request_id` | return first result; do not re-execute |
| `set_mode(live)` without hash ack or unmet §14 | reject |
| resume of equity/global HALT by non-human | reject (also enforced in Risk, ACIS-07) |
| resource read error | return error view; never mutate |

## 13. Logic-flaw registry
- **C-MCP-1 (human gate):** resume/set-mode/live require a human token; test: agent-token resume of a global HALT → rejected + no state change.
- **C-MCP-2 (guardrail schema reject):** `acis_stage_config` with a guardrail/equity-floor path → schema validation fails before the handler; test asserts rejection and that `guardrail_limits.yaml` is byte-unchanged.
- **C-MCP-3 (idempotency):** repeated `request_id` executes once; test double-sends a halt and asserts a single `halt_event`.
- **C-MCP-4 (no side channel):** no resource writes; no tool bypasses Governor/Risk; import + interface test asserts the server holds only the narrow injected interfaces.
- **C-MCP-5 (safety asymmetry):** halt/flatten open to agents; every risk-increasing tool gated; test enumerates tools and asserts the auth matrix.
- **C-MCP-6 (heartbeat rule):** 3 missed fast beats with open positions surfaces the flatten recommendation; test simulates missed beats.

## 14. Test contract (postcondition-style)

**Unit:** each tool's schema validates/rejects correctly; human-gated tools reject agent tokens; `acis_stage_config` rejects every guardrail/equity path (parametrized over the guardrail keys) and accepts an allowlisted tunable; idempotency by `request_id`; `set_mode(live)` requires hash ack + validation record.

**Integration (with ACIS-05/07):** `acis_halt` → Governor halts, new orders size 0 (assert order book); `acis_flatten` → positions closed + halt; `acis_resume` without human token → rejected, still halted; `acis_resume` with human token → trading resumes; agent tries to resume an equity-floor HALT → rejected (jointly with ACIS-07); staged tunable config promotes only at the next session boundary (jointly with ACIS-03); guardrail file never mutated by any tool.

## 15. Integration gate

**What the orchestrator (Phronesis / any MCP client) consumes:** the resources + tools above, under the heartbeat contract and the human/agent asymmetry. **Owns:** the entire external control surface; the `acis_stage_config` guardrail rejection; the human-token gate. **Done-when (phase 9, master §15):** §14 green; a proof test that no guardrail can be weakened through any MCP path and no non-human resume of an equity/global HALT succeeds; import contract passing.

## Changelog
- **1.0 (DRAFT)** — From master §12 + CLAUDE.md MCP discipline; human-token gate, guardrail-path schema rejection, `request_id` idempotency, and the halt-cheap/resume-human asymmetry made testable contracts.
