# PARTIAL — C1 CALIBRATOR (run 2)

- Lane: C1 CALIBRATOR. Model as observed: claude-opus-5-5 (Opus 5.5); effort not observable. Fresh context: yes.
- BASE 7695ed04. Date 2026-09-24. Launch 18:04 UTC. Web searches used: 0 so far.
- VALIDATOR files: NOT opened (framing discipline; first table not yet committed).

## Status (18:15 UTC)
- Read BRIEF §0.0–§4, FLEET_PLAN §1/§6.
- Read the as-built gate: `tests/backtest/deflated_sharpe.py`, `report.py:109-120` (`passed`),
  `harness.py:217-248` (trial set, `n_trials = len(trials)+min_trials`), `evolve_step.py:76-113`
  (trials = holdout per-trade Sharpe of every per-instrument × regime candidate champion),
  `oos_plan.py` (2y train, calendar-year tests 2014–2023, 7-day embargo, holdout 2024–2025 graded once).
- Design note (to be tested): the as-built DSR deflates the OOS record by the IN-FOLD candidate count,
  which is a selection the OOS record did not undergo, and it is blind to K (pipeline revisions re-scored
  on the same history), which is the selection it did undergo. Prediction: over-conservative at K=1,
  under-protective at K=20. Existing ledger context: GAP-P12D-33, GAP-P12D-37.
- Next: numpy simulator in `evidence/C1/sim_protocols.py`; first table; then prop-EV Monte Carlo.

## Status 18:27 UTC
- Protocol simulator built (`evidence/C1/sim_protocols.py`, `run_grid.py`); ~2.1 s/replication, 2 workers.
  iid null (R=400) done in a first version; nulls + planted worlds re-running with two added columns.
  Early iid-null signal (R=400, first version): as-built WF+DSR gate FPR 0.000 in every cell;
  "keep the best of K=20 revisions" inflates any 5% test to 43–57% FPR; SPA/StepM over the union of
  all revisions hold ~5%; a 2-year holdout graded once holds ~5%, but 29–57% if looked at K=20 times.
- Prop first-passage MC (`sim_prop.py`, validated vs closed form: S=0 P_pass 0.336 vs 0.333; S=0.5 0.503 vs 0.499)
  under FTMO 2-Step $10k rules as fetched from ftmo.com (daily loss on equity vs the 00:00 CE(S)T BALANCE).
  Early: zero-edge EV is within ~±$70 of zero and its sign flips with discount/haircut; a zero-GROSS-edge
  strategy is -EV above ~160 round trips/yr (1.5 bp all-in) even on optimistic economics.
- S1 (Topstep 2025 figures) VERIFIED at topstep.com, grade (a). S7 (Hall arXiv 2609.14859) EXISTS and the
  34.8%/3.9% figures are in its Table 11 — but they are the paper's own SIMULATION of an EOD-trailing
  futures account, not measured data. S6 VERIFIED at ftmo.com/en/trading-objectives (a).

## 18:47 UTC — planted 1.0 world done (measured truth of the fixed best config: 1.22 annual; the "0.5" world's is 0.65)
VALIDATOR read after the first table. Independent agreement on: as-built gate dead (0 FPR/0 power), keep-best-of-K
inflation, and 2-year WF selection throwing the edge away (mine 0.02/0.65 and 0.15-0.19/1.22 realised vs theirs 0.04/0.44 ACIS-style).
Nulls (garch, factor, iid rerun) and the fast-edge world still running.

## 19:40 UTC — superseded by the final report `C1_CALIBRATOR.md` (this PARTIAL is kept in place per BRIEF §3).
