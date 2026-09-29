# ACIS-08 — Monitoring & MCP Control Plane — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-MCP-008` |
| **Version** | 1.4 (**LOCKED** 2026-09-29 — `acis_set_mode(practice)`: human token plus the dual-hash ack, no rung-2 record; orders only to a venue-reported demo account; master v2.23, GAP-P12D-69) · 1.3 (**LOCKED** 2026-09-25 — `set_mode(live)` reads the master §14 rung-2 record) · 1.2 (**LOCKED** 2026-07-18, phase-10 dual-audit triage) |
| **Layer / DIR** | Cross-cutting control plane · `[DIR:monitoring]` |
| **Consumes** | read-only views of all stores/logs; control intents from an orchestrator/human |
| **Emits** | MCP resources (read) + MCP tools (control) → mapped onto Governor/Risk interfaces |
| **Depends On** | `../ACIS_SPEC.md` §12, §10, §9, §9.5, §5.6, §3.5, §2 · all layers (observes), `ACIS-05`/`ACIS-07` (control targets) |
| **Blocks** | live-mode enablement (phase 12) |
| **Corrections applied** | human-token gate, `acis_stage_config` guardrail-path rejection, heartbeat SLAs, safety asymmetry, idempotency, **v1.1: full v2.12 §12 resource/tool/prompt surface, dual-hash live ack (guardrail + rulebook §9.5), untrusted-input law extension (§3.5), per-gate skip-attribution surfacing (§10 C15, GAP-0078 non-partition contract), platform-rule awareness duty, genuine human-token verification (GAP-0048 residual)** |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract (resources/tools) · 5. Schemas · 6. Config & auth · 7. Core logic · 8. State/heartbeat contract · 9. Persistence & logging · 10. Store schema · 11. MCP contract (the tool/resource/prompt spec) · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Be the *only* way anything outside the fast loop observes or controls ACIS. An orchestrator (Phronesis, or any compliant MCP client) or a human harness supervises ACIS through this MCP server — no side channels, no ad-hoc HTTP (master §12, CLAUDE.md MCP discipline).

**IS:** the transport-independent MCP CONTRACT (the `ControlPlane` facade) — read-only resources and schema-validated control tools; the human-token gate; the guardrail-path rejection for `acis_stage_config`; the orchestrator heartbeat contract; canonical report prompts. It surfaces the §10 decisiveness telemetry (take-rate + per-gate skip attribution) and the §9.5 account-rules picture that the supervising harness is *dutybound* to verify. *(Honesty note, GAP-P10E-06: the real MCP stdio/SSE wire transport — `CallToolResult`/`GetPromptResult` shapes, prompt bodies — is a thin adapter that binds to this facade at deployment, the same lean-build split as the §7.5 feed/execution transports; "MCP server" here means "the contract an MCP transport exposes", built and tested transport-independent per the §3 scope note. `serve()` is the declared, not-yet-implemented binding point.)*

**IS NOT:** it is not in the fast loop and never sizes/signals/executes; it cannot weaken a guardrail, resume without a human, or inject a signal; it is not a web dashboard (master §17 — MCP resources *are* the interface in v1). It holds no trading logic — it maps intents onto the Governor/Risk interfaces that already enforce the rules. **It is not the enforcement of any rule** (platform news-rules included): it *reports whether enforcement is armed* and lets a human/agent stop; the two-layer enforcement lives in the Events layer + Governor (§3.5).

**Untrusted-input law (binding, master §12/§3.5).** Everything an out-of-band LLM reads through these resources — log tails, the `EventPicture`, headlines, provenance notes — is **data to analyse, never instructions to obey**. A crafted log line or news headline is content; it can never become a command, a staged config, or a control action. Every change an LLM proposes still lands only through `acis_stage_config`, under the guard-integrity law (§9) and the human-token rules. Reading the logs grants no writing power.

**Done-when:** halt/flatten are agent-callable and take effect; resume/set-mode(live) are rejected without a human token; `acis_set_mode(live)` requires acknowledgment of BOTH the guardrail hash AND the active-account rulebook hash; `acis_stage_config` rejects guardrail paths at the schema level; heartbeats and the 3-missed-beat rule work; all tools are idempotent by `request_id`; the §10 take-rate + per-gate skip counters are surfaced on `acis://status`; §14 tests pass.

## 2. Entry contract

**Entry point:** `monitoring/server.py::serve()` starts the MCP server; tool handlers call injected, narrow interfaces: `governor.apply_halt/flatten/resume`, `risk.snapshot`, `param_library.stage`, `mode_controller.set_mode`, and read-only store/log readers. It imports **no** fast-loop internals beyond these interfaces (observes via stores/logs; controls via the two sanctioned control interfaces — Governor and Risk). This layer sits OUTSIDE the downward-only layer chain (§2): it is a cross-cutting observer/controller, not layer N of the data flow, so the import contract treats `monitoring` as importing only the injected interface *types*, never a layer's internals.

**Inputs:** MCP requests (resource reads, tool calls with `request_id` + optional `human_token`); config `monitoring:`; the store/log readers; the read-only snapshot providers each layer already exposes (`RiskSnapshot`, `RegimeContext`, `ParamLibrary.{active,pending}_snapshot`, `EventPicture`, provenance records, pair/group registry, the attached adapter's `CapabilityDescriptor`, the account rulebook + `PlatformDrawdownState` series, the §10 skip counters).

## 3. Architecture & responsibility

Units: `server.py` (MCP wiring + heartbeat view), `resources.py` (read-only views), `tools.py` (control tools + auth + idempotency), `prompts.py` (report templates), `auth.py` (human-token verification), `mode.py` (the mode controller + dual-hash live gate). Single responsibility: **observability + gated control.** The safety rules are enforced *downstream* (Governor/Risk); this layer's job is to (a) never offer a tool that bypasses them, (b) enforce the human-vs-agent asymmetry and idempotency, and (c) faithfully surface the decisiveness/account-rules telemetry the supervising harness depends on — without ever *being* the enforcement.

## 4. Output contract — resources & tools

**Resources (read-only) — the canonical master-§12 list:**
| Resource | Content |
|---|---|
| `acis://status` | mode (backtest\|paper\|live), loop heartbeats, open positions, session, **fast-loop take-rate (signals-considered vs trades-taken) + per-gate skip counters (§10 C15)**, `BLACKOUT_OVERRIDE_ENFORCED` near-miss surfacing |
| `acis://risk/snapshot` | latest `RiskSnapshot` (incl. `alpha_decay_state`, VaR, cluster/per-instrument exposure) |
| `acis://regime/current` | latest `RegimeContext` per instrument (incl. advisory half-life) |
| `acis://params/active` · `acis://params/pending` | active sets + pending (incl. `boundaries_skipped`/stall alerts) |
| `acis://performance/daily` | daily perf rollup |
| `acis://config/guardrails` | **read-only** view of `guardrail_limits.yaml` |
| `acis://events/picture` | `EventPicture` + active blackout windows + calendar-feed health (§3.5) |
| `acis://pairs/relationships` | coupling states, correlation windows/methods, open groups (§5.5) |
| `acis://strategies/provenance` | per-module citation, lineage, falsifier, attempt count, current rung, declared deviations (§5.6) |
| `acis://account/rules` | active rulebook + **rulebook hash**, platform-measured drawdown series (`PlatformDrawdownState` per rule), distance-to-limit per rule (§9.5) |
| `acis://venues/adapters` | attached adapter, `CapabilityDescriptor`, conformance status (§7.5) |
| `acis://logs/tail/{stream}` | bounded, filterable tail of a log stream |

**Tools (schema-validated, idempotent via `request_id`, audit-logged to `risk_log`):**
| Tool | Auth | Effect |
|---|---|---|
| `acis_halt(scope: all\|instrument, reason)` | any agent | → `governor.apply_halt` (Risk HALT semantics) |
| `acis_flatten(reason)` | any agent | close all positions then halt |
| `acis_resume(scope)` | **human token** | clear a halt (never for equity/global without human) |
| `acis_set_mode(backtest\|paper\|practice\|live)` | **human token**; practice AND live also need BOTH guardrail-hash AND rulebook-hash ack (§9.5); live alone also needs the rung-2 record | change mode |
| `acis_stage_config(patch, rationale)` | agent (staged) | stage a *tunable* change for next boundary; **guardrail/equity paths + >1.0 caution multipliers rejected at schema level** |
| `acis_run_backtest(params)` · `acis_report(period)` | agent | out-of-band analysis |

**No ad-hoc endpoints.** Adding a resource or tool requires a master-§12 edit; a component that opens a side channel violates CLAUDE.md MCP discipline and must fail review.

## 5. Schemas

- **Tool request envelope:** `{request_id: str, human_token?: str, args: {...}}`. `request_id` makes every tool idempotent (a repeated `request_id` returns the first result, does not re-execute).
- **`acis_stage_config` bounded allowlist (GAP-P10I-01/02, GAP-P10E-04 — safe by construction):** the allowlist is a config schema (`monitoring.tunable_paths`), each entry a `TunableParam{path, min, max}`, itself human-committed and pydantic-validated at load (a guardrail/equity path in the allowlist is a load-time fatal). At the tool boundary — BEFORE any staging side effect — each patched value is checked: the path must be in the bounded allowlist, and the value must be a real finite number inside its declared `[min, max]`. This replaces the earlier fragile substring "caution/size multiplier > 1.0" heuristic: a `>max` size-scaler, a string like `"1.5"`, a negative, a zero on a dampen-only path, a NaN/inf, or a bool are ALL rejected — there is no risk-raising value that stages on any allowlisted path, and no non-allowlisted path stages at all. *(Mechanism-honesty note per GAP-P10E-02: the allowlist itself is JSON-Schema-enforced in config; the incoming patch is validated imperatively at the tool boundary before any handler side effect — two independent layers, but the phrase "schema-level rejection of the incoming patch" was an overstatement and is corrected to "boundary validation before any side effect, over a schema-enforced allowlist".)*
- **`acis_set_mode(live)`:** requires `guardrail_hash` matching the current `guardrail_limits.yaml` hash **AND** `rulebook_hash` matching the active account's `platform_rules.yaml` rulebook hash (§9.5) — a human explicitly acknowledges BOTH the exact hard limits AND the platform's own rules (news restrictions included) before any account goes live. A missing/mismatched EITHER hash → reject. `rulebook_hash` is computed by `config/account_doctrine.rulebook_hash` (already shipped).
- **`acis://status` skip attribution (GAP-0078 non-partition contract):** the per-gate skip counters are surfaced as **three per-layer VIEWS** (`nvma`, `agon`, `governor`), explicitly **NOT a partition** — one physical vetoed tick appears in both `nvma[<reason>]` and `agon["vetoed_regime"]` (the AGON count is a redundant re-count of the NVMA veto one layer down). The resource schema documents this: consumers read per-layer and MUST NOT sum across layers to form a "total skips" (that double-counts every veto). Take-rate is the honest ratio the fast loop itself reports.

## 6. Config & auth

- **Human token (GAP-0048 residual — genuine verification is THIS layer's job).** A human-only credential, verified in `auth.py` against a configured verifier (`monitoring.human_token_verifier`): the v1 verifier is a constant-time compare (`hmac.compare_digest`) against the SHA-256 digest of a human-held secret loaded from the environment/secret store (NOT a plaintext config value, NOT a mere non-empty presence check). Agent identities never possess it. The token gates `acis_resume`, `acis_set_mode`, and any equity/global HALT clear. This encodes the master §12 asymmetry: **any agent may stop trading; only a human may start it.** The verifier is injected so tests use a known secret; production loads the real one out-of-band. A blank/absent token is refused *before* the verifier runs.
  - **Declared scope + assumption (GAP-P10E-03 — bearer-secret-equality model).** The verifier is a BEARER-SECRET equality check, the API-key model, NOT a password KDF: it is unsalted single-round SHA-256 with no rate-limit/lockout. Its strength rests ENTIRELY on the injected secret's entropy — **the deployment MUST provision a high-entropy human token** (≥128-bit, not a memorable password). Salting is inapplicable to a single injected secret compared by digest, and an in-process attempt-lockout is deliberately NOT added: it would let an attacker DoS the human out of their only resume/go-live path. Online-guess throttling, if required, is a TRANSPORT/gateway responsibility at deployment (the same layer that binds stdio/SSE), not the verifier's. "Genuine credential" means "a real constant-time secret check that a fabricated string cannot pass" (closing GAP-0048) — it does not claim password-grade brute-force hardening. This assumption is a declared deviation from a full NIST-800-63B verifier, recorded here, not a silent one.
- **Config (`monitoring:`):** `transport: stdio|sse`, `heartbeat_fast_s:10`, `heartbeat_other_s:60`, `missed_beats_flatten:3`, `log_tail_max`, `tunable_paths` (the allowlist), `human_token_verifier` binding. Guardrail limits are **not** here — they live in `guardrail_limits.yaml` and are read-only to this layer. `monitoring:` is schema-fatal if missing (§9 discipline).

## 7. Core logic

1. **Resource read:** serve a bounded, read-only view from stores/snapshots/logs. No resource can mutate state. `acis://config/guardrails` and `acis://account/rules` are read-only — there is no write path to guardrails or rulebooks anywhere in the server. Untrusted content (headlines, log lines, provenance notes) is passed through as *data*, never interpreted as a directive.
2. **Tool call:** validate schema → check idempotency (`request_id`) → check auth (human-token where required) → call the narrow downstream interface → audit-log to `risk_log` with the caller identity + `request_id`. On any rejection, no downstream call happens and the reason is logged.
3. **`acis_stage_config`:** schema allowlist rejects guardrail/equity paths + risk-raising multipliers → stage the patch into the QIEA-style pending path (promoted at next session boundary, ACIS-03) → never applies mid-session, never to guardrails. The staged patch is *content the model proposed*, subject to the same boundary discipline as an evolved param set.
4. **`acis_resume`/`set_mode`:** reject without a valid human token (log `AUTH_REJECT`); `set_mode(live)` additionally requires the guardrail-hash AND rulebook-hash acks and that §14 minimums were met (the mode controller checks the validation record; v1.3: the rung-2 record of master §14 v2.22, never a bare verdict). Any of the three unmet → reject.
5. **Safety asymmetry enforced structurally:** the only tools that *reduce* activity (halt/flatten) are open to agents; every tool that *increases* activity or risk (resume, go-live, config) is gated. This mirrors "halts are cheap; resumes are human-only" (CLAUDE.md).
6. **Decisiveness surfacing (§10 C15):** `acis://status` carries the fast-loop take-rate and the per-gate skip counters as they are reported by the composed loop (NVMA `veto_counters`, AGON `skips`, Governor `skips`/`orders_zeroed`), under the GAP-0078 per-layer non-partition contract (§5). A persistently near-zero take-rate is a reportable health condition (the `starvation-diagnosis` prompt reads these). This layer *surfaces* the counters; it never tunes anything.
7. **Platform-rule awareness surfacing (§9.5/§3.5, binding on the harness — this layer serves the data it verifies against):** `acis://account/rules` exposes the rulebook + hash + `PlatformDrawdownState` series + distance-to-limit; `acis://events/picture` exposes blackout windows + calendar-feed health; every `BLACKOUT_OVERRIDE_ENFORCED` the Governor logs is surfaced on `acis://status` as a visible near-miss. The supervising harness's duty (verify rulebook present + hash-matched + news-enforcement armed at attach/session-start/pre-resume; treat a mismatch as a halt condition) is a *client* obligation master §12 places on Phronesis/any client; this layer's obligation is to serve the truthful picture and to make `acis_set_mode(live)` un-passable without the rulebook-hash ack.

## 8. State / heartbeat contract

Each loop writes a heartbeat into `acis://status`: fast loop ≤ `heartbeat_fast_s` (10 s), medium/slow ≤ `heartbeat_other_s` (60 s) (master §12). **Orchestrator contract:** 3 missed fast-loop beats **with open positions** → the orchestrator should call `acis_flatten` (the safety asymmetry again — the external supervisor can stop, but only a human restarts). The server reports missed-beat state; it does not itself flatten (that is the orchestrator's call), but a stalled fast loop with open positions also triggers the Risk Monitor's own flatten-and-halt (master §10) and the §8.6 watchdog's flatten on heartbeat silence — belt, suspenders, and a watchdog. The heartbeat SOURCE of truth is the §8.6 heartbeat file the Risk Monitor writes (ACIS-12); `acis://status` reflects it, never forges it.

**Built (GAP-P10I-05 / GAP-P10E-05):** `monitoring/heartbeat.py::HeartbeatMonitor` computes the missed-beat picture from the injected last-beat timestamp + `now` + config (`heartbeat_fast_s`, `missed_beats_flatten`) and surfaces it on `acis://status` under `heartbeat` (`missed_beats`, `healthy`, `flatten_recommended`, `reason`). `flatten_recommended` is True ONLY when the beat is stale past `missed_beats_flatten` AND positions are open; stale-but-flat is `missed_beats_but_flat` (alert only — nothing to flatten, matching the watchdog's `stale_but_flat`); a never-synced beat is treated as maximally stale (unknown never degrades to healthy). C-MCP-6 has behavioral tests (fresh/3-missed-with-positions/missed-but-flat/never-synced). The last-beat timestamp is injected (read from the §8.6 file at wiring time); the monitor never forges a beat.

## 9. Persistence & logging

Every tool call and its outcome logs to `risk_log` (JSONL): `MCP_TOOL{tool, request_id, caller, human:bool, result}`, `AUTH_REJECT`, `STAGE_CONFIG_REJECT{path}`, `MODE_CHANGE`, `HEARTBEAT_MISS`, `BLACKOUT_OVERRIDE_ENFORCED` (surfaced, not authored here). The control plane's audit trail is part of the risk audit spine — every halt/flatten/resume is attributable to a caller and (for resume/live) a human. Structured JSONL envelope `{timestamp, event_type, layer:"monitoring", data, session_id}` like every module (CLAUDE.md rule 3).

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
`request_id` PK enforces idempotency at the store level too (a duplicated tool call cannot double-execute — the second insert collides and the first result is returned).

## 11. MCP contract (authoritative resource/tool/prompt spec)

This layer *is* the MCP contract (master §12). The resource/tool tables in §4 are the canonical list; adding a resource or tool requires a master-spec edit (no ad-hoc endpoints).

**Prompts (canonical templates for LLM-side analysis, reading only from resources/logs — all research out-of-band per the §0 LLM boundary; output lands only as staged code/config, never live signals):**
- `daily-performance-brief` — daily rollup narrative from `acis://performance/daily` + logs.
- `halt-postmortem` — reconstruct a HALT from the risk log; proposes scenario-book additions (§8.5).
- `literature-distil` — from a cited source → a faithful strategy spec + falsifier (§5.6 research loop).
- `strategy-provenance-audit` — walks the model honestly through attempt counts, plateaus, and rung history before any live-promotion proposal (`acis://strategies/provenance`).
- `geopolitical-brief` — §3.6 slow lane: world events → staged watchlist/taxonomy/caution proposals, never live signals.
- `starvation-diagnosis` — §10: per-gate skip attribution → a targeted staged-config proposal, or the honest conclusion that the market offered nothing (reads the `acis://status` skip counters under the §5 non-partition contract).

## 12. Error taxonomy

| Event | Handling |
|---|---|
| tool missing/invalid `human_token` where required | reject, `AUTH_REJECT`, no effect |
| `acis_stage_config` touching guardrail/equity path or risk-raising multiplier | schema reject, `STAGE_CONFIG_REJECT`, no effect |
| duplicate `request_id` | return first result; do not re-execute |
| `set_mode(live)` without BOTH hash acks or unmet §14 | reject |
| resume of equity/global HALT by non-human | reject (also enforced in Risk, ACIS-07) |
| untrusted content interpreted as a directive | impossible by construction — resources return data; no handler parses resource content as a command |
| resource read error | return error view; never mutate |

## 13. Logic-flaw registry
- **C-MCP-1 (human gate):** resume/set-mode/live require a genuinely-verified human token; test: agent-token resume of a global HALT → rejected + no state change.
- **C-MCP-2 (guardrail schema reject):** `acis_stage_config` with a guardrail/equity-floor path or a `>1.0` multiplier → schema validation fails before the handler; test asserts rejection and that `guardrail_limits.yaml` is byte-unchanged.
- **C-MCP-3 (idempotency):** repeated `request_id` executes once; test double-sends a halt and asserts a single `halt_event` and a single `mcp_audit` row.
- **C-MCP-4 (no side channel):** no resource writes; no tool bypasses Governor/Risk; import + interface test asserts the server holds only the narrow injected interfaces and `monitoring` imports no layer internals.
- **C-MCP-5 (safety asymmetry):** halt/flatten open to agents; every risk-increasing tool gated; test enumerates tools and asserts the auth matrix.
- **C-MCP-6 (heartbeat rule):** 3 missed fast beats with open positions surfaces the flatten recommendation; test simulates missed beats.
- **C-MCP-7 (untrusted-input law):** a crafted headline/log line/provenance note surfaced through a resource never becomes a command or a staged config; test injects an adversarial "HALT everything"/"stage this" string into an event/log view and asserts it produces zero control effect and cannot auto-stage.
- **C-MCP-8 (dual-hash live ack):** `set_mode(live)` requires guardrail-hash AND rulebook-hash; test rejects on each missing/mismatched hash independently and accepts only when both match + §14 record present.
- **C-MCP-9 (skip-attribution non-partition):** `acis://status` exposes three per-layer skip views; test asserts a single physical veto appears in both nvma+agon views and that the resource schema/docstring forbids cross-layer summation (the consumer contract from GAP-0078).
- **C-MCP-10 (genuine human-token auth):** the verifier is a constant-time compare against a hashed secret, not a presence check; test: a non-empty-but-wrong token is rejected (closes the GAP-0048 residual — a fabricated string no longer self-promotes/resumes).

## 14. Test contract (postcondition-style)

**Unit:** each tool's schema validates/rejects correctly; human-gated tools reject agent tokens AND non-empty-but-wrong tokens (C-MCP-10); `acis_stage_config` rejects every guardrail/equity path (parametrized over the guardrail keys) and every `>1.0` multiplier and accepts an allowlisted tunable; idempotency by `request_id` (result + single audit row); `set_mode(live)` requires guardrail-hash AND rulebook-hash acks + validation record (C-MCP-8, each hash tested independently); `monitoring:` missing → config-fatal; the untrusted-input injection produces no control effect (C-MCP-7); the skip-attribution resource is per-layer and its non-partition contract is asserted (C-MCP-9).

**Integration (with ACIS-05/07/03/10 + the paper-loop composition):** `acis_halt` → Governor halts, new orders size 0 (assert order book); `acis_flatten` → positions closed + halt; `acis_resume` without human token → rejected, still halted; `acis_resume` with a valid human token → trading resumes; agent tries to resume an equity-floor HALT → rejected (jointly with ACIS-07); staged tunable config promotes only at the next session boundary (jointly with ACIS-03); guardrail file never mutated by any tool; `acis://status` reflects the paper-loop's take-rate + per-gate skip counters (jointly with the phase-7 `skip_attribution`); `acis://account/rules` surfaces the rulebook hash the `set_mode(live)` ack must match; a `BLACKOUT_OVERRIDE_ENFORCED` event is surfaced on `acis://status`.

## 15. Integration gate

**What the orchestrator (Phronesis / any MCP client) consumes:** the resources + tools + prompts above, under the heartbeat contract and the human/agent asymmetry. **Owns:** the entire external control surface; the `acis_stage_config` guardrail rejection; the human-token gate; the dual-hash live ack; the truthful decisiveness/account-rules telemetry. **Done-when (phase 10, master §15):** §14 green; a proof test that no guardrail can be weakened through any MCP path and no non-human resume of an equity/global HALT succeeds; the untrusted-input law holds through the resources; `set_mode(live)` is un-passable without both hash acks; import contract passing (`monitoring` holds only injected interfaces).

**Scope note (lean-build, §18).** §15 phase 10 is the MCP plane. This layer is built and tested against the existing layer interfaces (Governor/Risk/ParamLibrary/Events) and the phase-7 paper-loop composition — the same integration surface phase 7 used — NOT against an always-on production three-loop runtime. The full §10 three-loop asyncio runtime (and the in-loop wiring of VaR marks GAP-0091b, per-fill fast-breaker GAP-0099, and position-dedup GAP-0075) lands when a live always-on process is genuinely needed (phase 12 live connection); those GAPs remain phase-12-owned wiring requirements, recorded so a reviewer does not read their absence here as a regression. The MCP contract does not depend on that runtime existing — it reads snapshots/stores and drives the same Governor/Risk interfaces either way.

## Changelog
- **1.4 (LOCKED, 2026-09-29)** — Master v2.23, owner-ratified (ACIS-13 OQ-01, GAP-P12D-69): `acis_set_mode(practice)`. It needs the human token plus the guardrail-hash and rulebook-hash acknowledgment, but not the rung-2 record. Practice orders reach only an account the venue reports as demo and whose rulebook declares `account_class: practice` (ACIS-13 §7.1 A2). Live's gate is unchanged. The code change lands with the adapter (TODO Track A).
- **1.3 (LOCKED, 2026-09-25)** — Master v2.22 (the R1 audit triage, owner-ratified): `set_mode(live)`'s "§14 minimums" is the rung-2 record, never a bare verdict (GAP-P12D-104). The code change lands with the verdict module.
- **1.2 (LOCKED, 2026-07-18 — phase-10 dual-audit triage)** — every finding from the two parallel Opus 4.8 adversarial audits (internal-consistency GAP-P10I-01..09 + external-referent GAP-P10E-01..06) triaged. FIXED-with-regression: the `stage_config` guard is now a BOUNDED allowlist (`TunableParam{path,min,max}`), safe by construction — no substring heuristic, no string/negative/over-cap/size-scale evasion (P10I-01/02, P10E-04); idempotency is crash-safe and exactly-once (record-on-error so a replay never re-executes; pure pre-dispatch rejections are not cached so a legit retry is allowed; the store PK gracefully absorbs a concurrent duplicate) (P10I-04/09, P10E-01); the `ModeController` validates its reference hashes at construction so the `None==None` live-gate coincidence is impossible (P10I-03); the C-MCP-6 heartbeat/missed-beat monitor is BUILT + tested (`heartbeat.py`, surfaced on `acis://status`) (P10I-05, P10E-05); the guardrails resource deep-copies on read (P10I-07); guardrail-path guards normalize whitespace (P10I-08); the §14 integration is extended (real config-hash live gate, blackout-override surfacing, stage-doesn't-mutate-live) (P10I-06). SPEC-HONESTY corrections (mechanism was sound, the wording overclaimed): the `stage_config` rejection is boundary-validation-over-a-schema-enforced-allowlist, not incoming-patch JSON-Schema (P10E-02); the human token is a declared BEARER-SECRET equality model requiring a high-entropy secret, throttling deferred to the transport/deployment, not password-grade hardening (P10E-03, accepted-risk with declared assumption); "MCP server" is the transport-independent `ControlPlane` contract with the wire transport deferred to deployment (P10E-06). Residual honestly deferred to the phase-12 always-on runtime under the §15 lean-build note: the ParamLibrary config-staging-promotes-at-boundary joint test and the real-paper-loop take-rate wiring (the surfacing contract is unit-proven; the runtime that owns the mark/beat/boundary cadence lands with the live connection). No guardrail VALUE, HALT, veto, resume, or equity-floor semantic changed — every triage fix TIGHTENS a guard (bounded staging, crash-safe idempotency, safe-by-construction live gate, built heartbeat) or makes a named quantity/claim honest.
- **1.1 (LOCKED, 2026-07-18 — phase-10 start consistency update, master v2.5→v2.12)** — folded in the full master-§12 surface that post-dated the DRAFT: the five added read-only resources (`acis://events/picture` §3.5, `acis://pairs/relationships` §5.5, `acis://strategies/provenance` §5.6, `acis://account/rules` §9.5 incl. rulebook hash + `PlatformDrawdownState` series + distance-to-limit, `acis://venues/adapters` §7.5); `acis://status` now carries the §10 C15 take-rate + per-gate skip counters and the `BLACKOUT_OVERRIDE_ENFORCED` near-miss surfacing; `acis_set_mode(live)` now requires the DUAL hash ack (guardrail hash AND active-account rulebook hash, §9.5 — closing the v2.7 carry-forward); `acis_stage_config` now also schema-rejects `>1.0` caution/size multipliers; the four added prompts (`literature-distil`, `strategy-provenance-audit`, `geopolitical-brief`, `starvation-diagnosis`); the untrusted-input-law extension made a §1/§7/§12 contract with a test (C-MCP-7); the GAP-0078 per-layer skip-attribution non-partition contract made a resource-schema + consumer obligation (C-MCP-9); the GAP-0048 residual closed by requiring a genuine hashed-secret constant-time human-token verifier (C-MCP-10, no longer a presence check); the layer-contract note that `monitoring` sits outside the downward chain and imports only injected interface types; done-when/integration-gate renumbered from phase 9 to phase 10 (a DRAFT error); a lean-build scope note recording that the always-on three-loop runtime + GAP-0091b/0099/0075 in-loop wiring stay phase-12-owned. New registry entries C-MCP-7..10. No guardrail value, HALT, veto, or resume semantic changed — this pass only tightens (dual-hash live, genuine auth, risk-raising-multiplier reject) and completes the observability surface master §12 already specifies.
- **1.0 (DRAFT)** — From master §12 + CLAUDE.md MCP discipline; human-token gate, guardrail-path schema rejection, `request_id` idempotency, and the halt-cheap/resume-human asymmetry made testable contracts.
