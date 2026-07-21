# OPERATIONS_LEDGER.md — runtime/operational ledger (ACIS)

**Activates at go-live (phase 12, first live fill). Empty until then — this is a placeholder wired into the process so the mechanism exists before it is needed, not scrambled together after the first surprise.**

## What this is (and why it is separate from KNOWN_GAPS.md)
`KNOWN_GAPS.md` records **build-time** gaps against the spec. This file records **operational (runtime) surprises** once the engine trades real money — the "tribal knowledge" that only exists after a live VPS, real fills, a real financing table, and a real broker generate it. Kept separate so the build ledger stays clean, but in the **identical format** so both adversarial audit lenses can consume it without translation.

This ledger is **guard 3 of three** (CLAUDE.md "Operational correctness"): it is one guard, never the whole. It captures surprises *after* they surface; it does not replace guard 1 (the two-lens audit) or guard 2 (real out-of-sample validation + human sign-off before live). A log is not a validation gate.

## What goes here (log it the day it surfaces)
Anything where live reality diverged from what the code/spec assumed:
- **Real-vs-modelled fills** (GAP-0001): actual slippage/partial-fill/latency vs the declared C8 model.
- **Financing/carry reality**: actual broker swap charges vs `carry.py`/the financing table (incl. the triple-swap day and any Friday-triple metals convention).
- **Broker quirks**: symbol-suffix surprises, rejects, quote/depth anomalies, order-type handling, server-side stop behaviour.
- **Connectivity**: reconnect/backoff behaviour, weekend-gap handling, restart reconciliation vs the broker's authoritative state.
- **Observed live risk**: the **VaR breach frequency actually observed vs the 1% level** (the GAP-0103 quantity, now measured live), realised drawdown vs modelled, cluster/delta behaviour.
- Any HALT/flatten/resume in production and its post-mortem.

## Format — identical to KNOWN_GAPS.md (one entry per surprise, newest first, never delete)
```
## OPS-NNNN: <one-line title>
- Severity: critical | high | medium | low
- Likelihood: high | medium | low          (recurrence, once observed)
- Status: open | mitigated | accepted-risk | closed
- Area: [DIR:...] / adapter / broker / config §
- Observed: what live reality did, with the log timestamp / session_id / fill id that proves it
- Modelled: what the code/spec assumed (cite the module + the modelling GAP if any, e.g. GAP-0001)
- Delta + impact: how far off, and what it distorts (PnL, a §14 metric, a guard's trigger point)
- Justification: why this status (esp. accepted-risk); Linked: commits / test names / the audit pass that found it
```
Guardrail-adjacent operational findings (anything touching a HALT/veto/equity-floor trigger *in reality*) are ALSO summarised in `SPEC_AUDIT.md`, same as build-time guardrail findings. **Never** let an operational finding become a reason to weaken a guardrail without a human commit — a live divergence that makes a guard misfire is a finding to raise, not a knob to turn.

## How the audits consume this (owner directive 2026-07-18)
- **The operational-referent pass** (CLAUDE.md audit §, "standing, from go-live") reads this ledger + the live JSONL logs and re-runs the external-referent lens against **live behaviour, not just the spec**: does modelled cost/carry/slippage/fill still match what the broker actually did? It triages exactly like a phase audit (fixed+test / mitigated / accepted-risk), and its findings land here.
- **The internal-consistency lens** uses this ledger to check that a logged surprise was actually acted on — no operational finding rots, same never-rot rule as build findings.

---

## Entries
_(none yet — activates at the first live fill. Do not backfill build-time gaps here; those live in `KNOWN_GAPS.md`.)_
