# ACIS — Adaptive Capital Intelligence System

A production-grade, **deterministic (no-LLM-in-the-fast-loop)** autonomous forex engine with an MCP monitoring/control plane. Separate project from AXIS and Phronesis — nothing here imports them.

> **This repository is currently a specification + skeleton.** No engine code is implemented yet. Build strictly in the SPEC §15 phase order, only into the `[DIR:...]`-tagged directory for each section, and never start a phase before the previous phase's tests pass.

## Read in this order
1. **`ACIS_SPEC.md`** — the master specification / constitution (build authority). Start here.
2. **`CLAUDE.md`** — operating rules for the implementing agent.
3. **`specs/ACIS-00-INDEX.md`** — the deep per-layer spec set (one document per layer, in build order).
4. **`SPEC_AUDIT.md`** — cross-source contradiction & logic-flaw register (what was reconciled, what is still open).
5. **`KNOWN_GAPS.md`** — living ledger of gaps/accepted risks.
6. **`_SPEC_AUTHORING_GUIDE.md`** (how the deep specs were authored) and **`_SPEC_REVIEW_PASS.md`** (how to run the next verification pass).

## Layout (blueprint)
```
core/{data,regime,optimizer,signals,governor,execution,risk}/  # 7 layers, downward-only data flow
monitoring/        # MCP control plane (SPEC §12)
config/            # system_config.yaml, instruments.yaml, guardrail_limits.yaml (human-only)
tests/{unit,integration,backtest}/
scripts/  logs/  specs/
```
Each `core/*` and `monitoring/` directory carries a `README.md` marker pointing to its deep spec, inputs/outputs, and the corrections it owns.

## The hard rules (see CLAUDE.md / SPEC §0, §2, §8, §17)
- No LLM / network reasoning / human prompt in the fast loop — deterministic Python only.
- Downward-only layer communication; single upward edge = Risk Monitor HALT → Governor.
- `config/guardrail_limits.yaml`, the equity floor, and HALT/veto semantics are **human-only**. There is no force flag. Halts are cheap; resumes are human-only.
- Everything runs in paper mode until phase 11; live requires §14 minimums **out-of-sample** + human sign-off.
