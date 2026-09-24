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

## Findings so far (18:37 UTC) — provisional
1. **The planted/null/permuted generator is a Brownian bridge, and a bridge punishes TSMOM.**
   `synthetic_market._returns` demeans every path over its whole span. On a daily analogue of the
   ladder span (704 weekdays, σ 0.5%/day, 4,000 paths) the ACIS 63/126/252 vote held 2 days loses
   **−0.036 to −0.039 log units per path (t ≈ −24; 64–65% of paths negative)**; without the demeaning
   it is ≈ 0 (t −0.1 to +2.0). `evidence/C3/sim_bridge_tilt.py`. So part of "TSMOM is the sink" is the
   positive control, not the engine.
2. **The 48 h max hold exists only in the backtest harness** (`tests/backtest/harness.py:98`
   `max_hold_s: float = 48 * 3600`); `grep -rn max_hold core/` finds only the fitness gene. Live TSMOM would
   hold to the vote flip (ACIS-04 §6.6), so the graded TSMOM is not the TSMOM the engine would run.
3. **One-position-per-instrument + an always-on TSMOM vote = a lockout.** Timing run (planted seed 7,
   1 fold, TSMOM live): 24 trades, **all TSMOM, all `max_hold`**; the fast modules traded 0 times.
   Multi-fold runs in flight to measure it at scale.

4. **First scale pair (planted seed 7, 5 folds x 30 d, TSMOM live from fold 0; ~21 min per run):**
   - TSMOM ON: 126 trades, **all TSMOM** (120 `max_hold`, 6 `reverse`), net −0.49; TSMOM occupies the
     instrument's single position slot **97% (EUR_USD) and 98% (USD_JPY) of graded time**; fast modules: 0 trades.
   - TSMOM OFF: 527 trades, net +6.55, gross +11.45; TREND +7.60 (231/277 entries aligned with the planted
     episode sign), BREAKOUT +0.52 (159/174 aligned), MEAN_REVERSION −1.57 (70/76 against the sign).
   - Scale: sizes are ~$40–$200 notional on a $10k NAV (base_unit_usd 1000 x conviction x liquidity x
     regime≈0.35), so every $ figure is tiny; read the signs and ratios.
   - More seeds, null, no-veto and the horizon test running (queue in the report).
