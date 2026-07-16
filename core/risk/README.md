# `[DIR:core/risk]` — Layer 7 · Risk Monitor & Guardrails ← SOVEREIGN

**Blueprint only — no implementation yet.** The only layer with upward authority; limits are human-only.

- **Deep spec:** `../../specs/ACIS-07-RISK_MONITOR.md` · **Master:** `../../ACIS_SPEC.md` §8
- **Consumes:** `FillReport` + all stores · **Emits:** `RiskSnapshot`; **HALT/flatten → Capital Governor ONLY** (single upward edge)
- **Planned files:** `monitor.py` (metrics + snapshot), `guardrails.py` (limit checks + HALT/flatten + equity breaker), `alpha_decay.py`
- **Human-only, never weakened by code:** `config/guardrail_limits.yaml`, the equity floor, HALT/veto semantics. No force flag. Halts are cheap; resumes are human-only.
- **Owns corrections:** C-RSK-1/2 (alpha-decay baseline validity + NaN-safe Sharpe/C5,F13), C-RSK-3 (equity breaker), C-RSK-4 (racing HALTs), C-RSK-5 (restart reconcile vs broker), C-RSK-6 (drawdown buffer raised/F9), C-RSK-7 (human-only resume).
- **Conflict priority #1:** Risk HALT beats everything.
