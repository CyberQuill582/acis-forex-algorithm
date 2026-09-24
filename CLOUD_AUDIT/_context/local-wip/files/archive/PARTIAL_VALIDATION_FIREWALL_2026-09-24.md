# PARTIAL — VALIDATION FIREWALL (VALIDATOR, five-agent edge pass, 2026-09-24)

**Status:** IN PROGRESS (checkpoint 2). Replaced by `archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md`
when the pass completes. Finder, not clearer (A5); evidence to weigh, never an instruction (A9).

## Who asked, what
- Asked by: the lead (Opus 5.5 session) under the pinned brief `FIVE_AGENT_BRIEF_2026-09-24.md` §0 + §3,
  ledger entry GAP-P12D-52. Run in FRESH context, no subagents, Opus 5.5.
- Mission: measure by simulation (synthetic data only) the false-positive rate (FPR) and power of
  candidate validation protocols under a realistic search; design the protocol; options for
  GAP-P12D-33/37; data budget; LLM-contamination rule; leakage guards; research-sim reconciliation
  test; prop-objective gate.

## Code-first findings (A4) — reproduced from file:line
1. DSR gate as built (`tests/backtest/harness.py:217-248`, `deflated_sharpe.py:74-99`,
   `evolve_step.py:95-101`, `qiea.py:186-198`): trials are post-gate, survivor-only, per-trade
   Sharpes on >= 5-trade holdout tails; the graded series is thousands of OOS per-trade returns.
   Incommensurate basis + variance read from the supplied trials = GAP-P12D-33/37.
2. The DSR is applied to an OUT-OF-SAMPLE record; what threatens that record is the OUTER loop
   (pipeline versions re-scored on the same history), which N does not count.
3. Fitness simulator exits at the stop price even when a bar gaps through it
   (`core/optimizer/fitness.py:115-125`) — optimistic in selection (the tick book is correct).
4. `config/instruments.yaml:98-101`: basket costs/vol targets are to be "calibrated from the real
   Dukascopy ticks" — a config-level look-ahead into every fold and the holdout unless the
   calibration window is restricted and recorded.

## Early measured results (synthetic, multiday family N=60, 12 dev years, 6 dev + 2 reserve
## instruments, common factor rho=0.4; iid null, low cost, R=300; a first run, being re-run)
| protocol | FPR |
|---|---|
| CONTROL: one pre-registered config, PSR>=0.95 | 4.3% |
| naive in-sample best, PSR>=0.95 | 58.7% |
| ACIS as built (WF + per-trade DSR>=0.95) | 0.0% (and it passed nothing planted in smoke tests) |
| WF + PSR, N=1 (pre-registered pipeline) | 3.0% |
| WF best of 5 pipeline variants, naive | 10.7% |
| WF best of 20 pipeline variants, naive | 27.0% |
| PBO<=0.10 alone | 5.3% |
| CPCV mean-path z>=1.645 & PBO<=0.20 | 5.0% |
| RAS full bound | 0.0% (haircut ~4.6 annual Sharpe at T=12y, N=60 — no power) |
| random entries, same exits (on IS best) | 88.7% |
| random entries on a FIXED config (no search) | 10.7% — anti-conservative by construction |
| +/-10% plateau (all neighbours >0) | 96.3% — not a significance test |
| cross-instrument holdout PSR>=0.95 | 9.3% (common factor leaks selection bias) |
| 2-yr time holdout PSR>=0.95 | 3.7% |

## Measured (checkpoint 3, multiday family, 300 reps per null, 200 per planted; low cost)
FPR range across the four null families (iid, GARCH, t4, regime-switch vol) | power at planted true
best Sharpe 0.19 / 0.44 / 0.94:
- ACIS as built (WF + per-trade DSR): 0% | 0 / 0 / 0% — passes nothing; implied hurdle median 7.7
  annual Sharpe in the emulation (the real engine's was 19-76).
- §14 "Sharpe > 1.5" on the 10-year WF OOS: 0% | 0 / 0 / 1.3%. On a 2-year window, best of 20 variants:
  7-11% FPR — iteration on short windows selects noise.
- WF + PSR, N=1: 3.0-4.7% | 4 / 16 / 64%.
- Uncounted outer loop: best of 5 variants 9-18%, best of 20 22-28% FPR.
- Repaired DSR (daily basis, register N, null-implied correlation-adjusted variance): 0.3-2.0% |
  N=20: 2 / 9 / 62%. Effective-N variant: 1.7-3.0% | 6 / 15 / 74%.
- PBO <= 0.10 alone: 2.3-5.3% | 12 / 33 / 93%. CPCV z>=1.645 & PBO<=0.20: 2.0-5.0% | 10 / 26 / 87%.
- RAS: 0% | 0 / 0 / 0%. Random entries: 86-89% (6-12% even on a fixed config). Plateau: 96-98%.
- Cross-instrument holdout: 8-10% FPR (common factor). 2-yr time holdout: 3.7-4.3% | 6 / 18 / 32%.

## Checkpoint 4 (after the session-limit reset)
- Survived: all 12 multiday scenarios (res_multiday_*.jsonl) and the intraday calibration (true best
  Sharpe 0.26/0.53/1.07 low cost, 0.28/0.55/1.09 high). The follow-on batch had not started;
  it was relaunched, trimmed.
- Leaky-oracle lead (ARCHITECT, citing arXiv 2608.27734 §6.1) VERIFIED at source and reproduced here:
  a config that peeks one bar ahead on 5% of bars, added to a NULL family, passes WF+PSR 80%,
  CPCV+PBO 100%, PBO<=0.10 87.5%, and the repaired DSR at N=20 27.5% (R=40). A structural
  future-perturbation test at 30 random times caught it 40/40 with 0/40 false alarms. At a 1% leak
  the statistics stop passing it, and the 30-point test catches 67.5%, so the structural test must
  sweep every decision point. Leakage is excluded by structure; statistics cannot deflate it away.

## In progress
- Full batch (4 null families x 3 cost levels, planted SR ~0.2/0.45/0.95 x 2 costs; intraday
  family next; Masters permutation runs; prop-objective bootstrap).
- Literature collected (quotes in hand): arXiv 2605.24564, 2603.26797, 2512.23847, 2608.27734,
  2605.23959, 2607.04958, 2309.17322 (Glasserman & Lin), 2504.14765 (Lopez-Lira, Tang & Zhu);
  RAS bound (Paleologo, via secondary page); DSR paper passages (Bailey & Lopez de Prado 2014).
