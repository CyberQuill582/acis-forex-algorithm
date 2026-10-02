# ACIS — Adaptive Capital Intelligence System

A production-grade, **deterministic (no-LLM-in-the-fast-loop)** autonomous forex engine with an MCP monitoring/control plane. Separate project from AXIS and Phronesis — nothing here imports them.

> **Status (2026-10-02): SPEC complete (master v2.29). Build phases 1–11 are ✅ — built, dual-audited and triaged. Phase 12 (live readiness) is in progress; everything is still paper.** **The demo track is the priority:** the cTrader adapter for a Pepperstone demo is built (ACIS-13 v1.1), and the **three-loop runtime is built** (`core/runtime/`, `python -m core.runtime`): one position per instrument, stops resting at the venue, Risk on every fill, practice entered only by a human. The demo's parameter set is evolved (one champion, GAP-P12D-129), feed reconnect is built (GAP-0020), and the Track A dual audit is triaged (GAP-P12D-132); Spotware approved the owner's app, and since 2026-10-01 the engine trades the Pepperstone demo in practice, unattended, guarded by the watchdog. R1.1 and R1.2 are built, dual-audited and triaged; real-data looks stay closed until R1.4. **R1.6 is built (2026-10-02):** the TREND family's D1 trades the 13 explored FX pairs as target positions at one minimum lot (a venue-seeded daily history, the 17:00 New York decision, the per-symbol slot clock, a 10 × ATR disaster stop), and it reaches the demo at the AWS cutover. A demo proves the plumbing, not an edge (GAP-P12D-49). See `STATUS.md`.

## Read in this order
1. **`STATUS.md`** — one-screen current state: what's built, what's open, the pre-live gate. **Read this first.**
2. **`TODO.md`** — the binding build ledger; its header + "Phase 12 — LIVE readiness" section are the work queue.
3. **`CLAUDE.md`** — operating rules for the implementing agent (guardrails human-only, layer law, audit constitution).
4. **`ACIS_SPEC.md`** — the master specification / constitution (the build authority; the spec wins over code).
5. **`specs/ACIS-00-INDEX.md`** — the deep per-layer spec set (one LOCKED document per layer, in build order).
6. **`KNOWN_GAPS.md`** — the LIVE ledger: open / mitigated / accepted-risk items only; `python scripts/ledger_check.py --summary` prints the live counts.
7. **`SPEC_AUDIT.md`** — cross-source contradiction & audit register.

> Archive / grep-only (not part of the read path): `KNOWN_GAPS_CLOSED.md` (closed items — the regression test named in each entry is the permanent record), `CONCORDANCE.md`, and `archive/` (superseded audit scratch). Grep these when tracing "why does the code do it this way"; never read top-to-bottom.
>
> Reference: `BASELINE.md` + `config/baseline_manifest.json` — the pristine, market-**untrained** baseline (git tag `baseline-untrained-v1`), kept immutable and always-cloneable so future runs can re-evolve it differently; `tests/unit/test_baseline_paramset.py` is the drift guard. `deploy/README.md` — the VPS deployment runbook.
>
> Go-live artifact: `OPERATIONS_LEDGER.md` — the **runtime** ledger (empty until the first live fill). From go-live it logs operational surprises (real-vs-modelled fills, financing/broker reality, observed live VaR breach frequency) in the same format as `KNOWN_GAPS.md`, feeding a standing **operational-referent audit pass**. Guard 3 of the three go-live guards (see CLAUDE.md "Operational correctness").

## Layout
```
core/{data,regime,optimizer,signals,governor,execution,risk}/  # 7 layers, downward-only data flow ✅
core/runtime/      # the three-loop runtime, the composition root (SPEC §10, v2.25)
monitoring/        # MCP monitoring/control plane (SPEC §12) ✅
config/            # system_config.yaml, instruments.yaml, guardrail_limits.yaml (human-only)
tests/{unit,integration,backtest}/                             # 1160+ passed (Google server)
deploy/  Dockerfile  docker-compose.yml  .github/workflows/    # VPS deployment-readiness gate ✅
scripts/  logs/  specs/
```
Each `core/*` and `monitoring/` directory carries a `README.md` marker pointing to its deep spec, inputs/outputs, and the corrections it owns.

## The hard rules (see CLAUDE.md / SPEC §0, §2, §8, §17)
- No LLM / network reasoning / human prompt in the fast loop — deterministic Python only.
- Downward-only layer communication; single upward edge = Risk Monitor HALT → Governor.
- `config/guardrail_limits.yaml`, the equity floor, and HALT/veto/resume semantics are **human-only**. There is no force flag. Halts are cheap; resumes are human-only.
- Everything runs in paper mode; live requires §14 minimums **out-of-sample** + human sign-off. Never enable live yourself.
- Every completed phase gets **two** parallel adversarial audits (internal-consistency + external-referent); every finding is triaged before the phase is ✅ (CLAUDE.md audit constitution).
