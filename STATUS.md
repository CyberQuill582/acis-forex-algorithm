# STATUS — ACIS current state (read first)

**As of 2026-09-11.** One-screen digest. Authoritative sources: `TODO.md` (work queue), `CLAUDE.md` (rules), `KNOWN_GAPS.md` (live ledger). This file summarises them; if it ever disagrees with those, they win — update this.

## Where we are
- **Spec:** master `ACIS_SPEC.md` **v2.14** (2026-09-11: v2.13 — §13 cross-check source HistData replaces TrueFX, Dukascopy primary via its official S3 archive; v2.14 — every market time declared in LOCAL time and resolved per date, GAP-P12D-10). Deep specs ACIS-01..12 LOCKED (ACIS-01 → v1.2, ACIS-03 → v1.3, ACIS-09 → v1.2); **ACIS-13 (venue adapters) is the only unwritten spec**. Governed by `../specs_constitution/SPEC_CONSTITUTION.md` **v0.5**.
- **Build:** **phases 1–11 ✅** — built, dual-audited, every finding triaged. **Phase 12 in progress:** VPS deployment-readiness gate ✅, untrained-baseline freeze ENFORCED (tag `baseline-untrained-v1`), and the **OOS data layer** under way — HistData cross-check engine + tick readers built, SPX + dated overnight rates + financing model done, backtest PnL now converted to USD, DST-correct market time in the backtest AND the engine (sessions, staging boundaries, daily bars, weekend ban, daily-loss day). **586 tests green** in a full run.
- **Implemented:** the 7 core layers (`core/{data,regime,optimizer,signals,governor,execution,risk}`), the MCP control plane contract (`monitoring/`; the wire transport is GAP-P12D-08), the backtest + §14 harness (`tests/backtest/`), data-ops downloaders (`scripts/`).
- **Mode:** **PAPER only.** No live trading. No real-money path is enabled.

## Next: phase 12 — LIVE readiness (the final §15 phase)
Full checklist in `TODO.md` → "Phase 12 — LIVE readiness". Headline items:
1. **Real out-of-sample §14 validation** — Dukascopy S3 downloader (owner creates the AWS account), HistData cross-check download, the historical event calendar, then the evolve-driver and the per-account grade. *Never present in-sample numbers vs §14.* **← next**
2. **Gold calendar shape** (GAP-P12D-11) — XAU_USD is tagged against a 6.5-h CME day session; needs a daily-break calendar before the gold leg is graded. *(The engine-side DST fix GAP-P12D-10 is done — owner-ratified.)*
3. **Three-loop runtime + in-loop wiring** — GAP-0091b, GAP-0099, GAP-0075, the MCP wire transport GAP-P12D-08, the SQLite signal store GAP-P12D-09.
4. **Per-account universe + full §9.5 enforcement**, **futures/metals roll policy** (GAP-0109), **ACIS-13 spec**, phase-12 dual audits (recommended auditor Fable 5.1; the brief includes legibility GAP-P12M-01/02).
5. **LIVE sign-off — HUMAN ONLY.** §14 minimums met out-of-sample on real data + explicit owner sign-off.

## Open risk — generated, never hand-copied
`python scripts/ledger_check.py --summary` prints every **owner decision pending**, **open**, **mitigated** and **accepted-risk** item from the ledger. It runs automatically at every session start. This file deliberately carries no copy of those lists: a hand-kept copy is what went stale here before (A13). Closed items live in `KNOWN_GAPS_CLOSED.md`, each pinned by the proof named in its entry.

## Operational correctness at go-live — three independent guards (none substitutes for another)
Build correctness (the phase audits) is not operational correctness; the gap opens the day it trades real money.
1. **Two-lens per-phase audit stays as-is** — never downgrade the external-referent lens (the only structural attack on a co-designed system's shared-priors seam).
2. **Real out-of-sample data + human sign-off before live** — separate from auditing, non-negotiable. Never present in-sample numbers vs §14.
3. **Runtime ledger from the first live fill** — `OPERATIONS_LEDGER.md` logs real-vs-modelled fills, financing reality, broker quirks, reconnects, observed live VaR breach frequency, in the same ledger format, so the standing **operational-referent audit pass** stays effective. A log records surprises *after* they surface — it never replaces guard 2. See CLAUDE.md "Operational correctness" + audit §3.

## Never touch without a human (guard-integrity law, SPEC §9)
`config/guardrail_limits.yaml`, the equity-floor value, and HALT/veto/resume semantics are human-commit-only. There is no force flag. These are safe because the code *cannot reach them*, not because anyone promises care. A change that makes a guardrail reachable is the bug — halt and raise it.

## Process
Every completed phase gets **two** parallel adversarial audits (internal-consistency + external-referent); every finding is triaged (fixed+test / mitigated / accepted-risk) before the phase is ✅. Author ≠ auditor; a clean report is never a sign-off. Ledgers are append-only, never-delete. **Ledger closure law** (CLAUDE.md, constitution A15): nothing unfinished lives only in chat; a closure names its residual; `scripts/ledger_check.py` gates CI. **Legibility budget** (A12): no new production module over 300 lines.
