# STATUS — ACIS current state (read first)

**As of 2026-07-18.** One-screen digest. Authoritative sources: `TODO.md` (work queue), `CLAUDE.md` (rules), `KNOWN_GAPS.md` (live ledger). This file summarises them; if it ever disagrees with those, they win — update this.

## Where we are
- **Spec:** master `ACIS_SPEC.md` **v2.12**, complete, all passes owner-ratified. Deep layer specs ACIS-01..12 LOCKED; **ACIS-13 (venue adapters) is the only unwritten spec** (author before the first non-mock live adapter).
- **Build:** **phases 1–11 ✅** — built, dual-audited (two Opus 4.8 audits each), every finding triaged. **515 tests green** in a full run.
- **Implemented:** the 7 core layers (`core/{data,regime,optimizer,signals,governor,execution,risk}`), the MCP monitoring/control plane (`monitoring/`), and the backtest + §14-validation harness (`tests/backtest/`).
- **Mode:** **PAPER only.** No live trading. No real-money path is enabled.

## Next: phase 12 — LIVE readiness (the final §15 phase)
Full checklist in `TODO.md` → "Phase 12 — LIVE readiness". Headline items:
1. **Real out-of-sample §14 validation** — acquire ≥2 yr real Dukascopy/TrueFX tick data, grade OUT-OF-SAMPLE. *Never present in-sample numbers vs §14.* This is the paper→live evidence bar.
2. **VPS deployment-readiness gate** — CI merge gate, Docker, process supervision + §8.6 watchdog, per-adapter server-side-stop.
3. **Three-loop runtime + in-loop wiring** — GAP-0091b (in-loop VaR/marks), GAP-0099 (per-fill breaker), GAP-0075 (position accounting).
4. **Per-account universe + full §9.5 enforcement**, **futures/metals roll policy** (GAP-0109), **ACIS-13 spec**, phase-12 dual audits.
5. **LIVE sign-off — HUMAN ONLY.** §14 minimums met out-of-sample on real data + explicit owner sign-off.

## Open risk (LIVE ledger — 5 items, ALL low severity; none blocks the build)
- **GAP-0020** — feed reconnect/backoff protocol untested until a real feed face exists (phase-12 adapter).
- **GAP-0035** — v1 fitness harness doesn't exercise the momentum/breakout/mean-reversion genes.
- **GAP-0067** — MarketStateStore commits per-row (fsync-bound); at real feed rates the audit/replay store sheds ticks (throughput, phase-11/12).
- **GAP-0091b** — VaR/cluster metrics need marks fed each evaluate; the production mark stream isn't wired yet (phase-12 runtime).
- **GAP-0109** — two §13 futures-lifecycle glitch classes untested; need the futures roll-or-flatten policy (phase-12 futures enablement).

## Accepted-risks to re-confirm before live (5) — decisions we chose to live with
- **GAP-0004** — slippage auto-throttle is **alert-only**, not an automatic size cut (interim; F10).
- **GAP-P10E-03** — human-token verifier is an unsalted single-round SHA-256 bearer-secret equality check; high-entropy-token mandate + transport throttle declared — **harden at the deployment gate**.
- **GAP-0001** — backtest fidelity ≠ live microstructure (inherent; disclosed in every report's `fidelity_caveats`).
- **GAP-0023** — `fx_default` calendar tags 21:00–00:00 UTC "closed" daily (spurious dead window; deliberate conservatism).
- **GAP-P11I-10** — GAP-0108 outage-gap refinement keys off the global instruments flag, not per-account (latent; shipped scenario-replay gate numbers UNCHANGED).

*(11 further items are `mitigated` — `grep '^- Status: mitigated' KNOWN_GAPS.md`. Closed items live in `KNOWN_GAPS_CLOSED.md`, each pinned by the regression test named in its entry — that test is the permanent record.)*

## Never touch without a human (guard-integrity law, SPEC §9)
`config/guardrail_limits.yaml`, the equity-floor value, and HALT/veto/resume semantics are human-commit-only. There is no force flag. These are safe because the code *cannot reach them*, not because anyone promises care. A change that makes a guardrail reachable is the bug — halt and raise it.

## Process
Every completed phase gets **two** parallel adversarial audits (internal-consistency + external-referent); every finding is triaged (fixed+test / mitigated / accepted-risk) before the phase is ✅. Author ≠ auditor; a clean report is never a sign-off. Ledgers are append-only, never-delete.
