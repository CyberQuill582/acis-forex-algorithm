# PARTIAL — C3 ENGINE FORENSICS AT SCALE (run 2)

- Lane C3; model Opus 5.5 (claude-opus-5-5), effort not observable; fresh context, no subagents.
- BASE 7695ed04; date 2026-09-24; launched 18:04 UTC; web searches used: 0.
- Work copy: `/tmp/acis-forensics` (cp of `/tmp/review-acis`). One env-gated patch in that copy only
  (`core/signals/agon.py`, `C3_TSMOM_NO_VETO`: in an opposite-direction conflict, drop only the TSMOM
  signals if the remaining fast signals agree). Never committed.

## Status (18:10 UTC)
- Driver written: `evidence/C3/sim_c3_run.py` (real engine via `oos_runner.run_walk_forward`; per-trade
  recorder; TSMOM seeded from the synthetic mid path so it is live from fold 0; labels over train windows only).
- Timing run (planted, seed 7, 1 fold, 2 instruments) in flight. Labelling ~60 s per instrument per 63 days.
- Next: project cost, then planted/null/permuted x seeds; ablation (TSMOM off; TSMOM no-veto); horizon test.
