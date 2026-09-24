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
