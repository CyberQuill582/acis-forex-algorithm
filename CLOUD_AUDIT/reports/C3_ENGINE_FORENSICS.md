# C3 — ENGINE FORENSICS AT SCALE (ACIS cloud review, run 2)

- **Lane:** C3 ENGINE FORENSICS AT SCALE.
- **Model / effort as observed:** Opus 5.5 (`claude-opus-5-5`); effort not observable from inside the session.
- **Fresh context:** attested. No subagents were launched.
- **Reviewed commit:** BASE `7695ed04abfeaa7535e237afcac25fb983025ff0`.
- **Date:** 2026-09-24, 18:04–~20:55 UTC.
- **Web use:** 1 web search and 1 fetch (the Moskowitz–Ooi–Pedersen PDF from NYU Stern, read locally).
- **Compute:** all runs were in the throwaway copy `/tmp/acis-forensics`, with at most 2 engine
  processes at a time. For about 3 minutes a probe loop ran as 2 extra short processes; I stopped it
  when I noticed. Synthetic data only. No `.bi5` prices were read, and no download script was run.

**Status: PENDING AUDIT. I am a finder, not a clearer.** The numbers come from 5-fold runs on synthetic
markets, not the 25-fold ladder. They are not §14 results, and no in-sample number is presented
against §14.

---

## 1. Executive summary

__EXEC__

---

## 2. Body

### 2.1 Method: what I ran, and how it differs from the ladder

**Driver.** `evidence/C3/sim_c3_run.py` is one real-engine walk-forward through
`tests/backtest/oos_runner.run_walk_forward`. It uses the production config, the `dev_paper` account,
the C8 cost map at 1×, the real `Backtest` book and Governor, and the real report and gates. It changes
five things relative to `scripts/cost_stress_ladder.py`. All are in-process, and all are declared:

1. **The fold plan starts 385 days after the market start** (`plan(60, 30, 5, start=START+385 d)`).
   TSMOM's daily history is seeded straight from the synthetic mid path at the 17:00 New York closes, so
   **TSMOM is live from the first graded tick.** In GAP-P12D-49's run it went live only around fold 8–9
   (BUILDER: 2015-02-03), so that run is a mix of about 8 folds without TSMOM and about 16 with it. My
   `_on` runs are the TSMOM-live half; my `_off` runs are the TSMOM-absent half, which is
   behaviourally identical to the pre-live folds, because a TSMOM with fewer than 260 closes emits
   nothing.
2. **Labels cover the union of the folds' train windows** (plus `LABEL_WARMUP`), not whole calendar
   years. The real NVMA and the real `label_bars` are used. This is a cost cut: labelling runs at about
   0.3 ms per tick.
3. **Parameters:** the market seed; an evolution-seed salt (wraps `evolve_step.seed_for`); module
   switches through a copied `system_config.yaml` (`modules_enabled`); and a planted-episode shape
   (`episode_hours`, `drift_sigma`) for the horizon test.
4. **A per-trade recorder** wraps `PositionModel.close_at`. For every closed trade it logs the strategy,
   direction, exit reason, gross, friction and net in USD, the planted episode sign at entry, and the
   episode boundaries crossed. The ladder has no such record (BUILDER's stage 3 was blocked for this
   reason).
5. **An event counter** is keyed by strategy, for `SIGNAL_EMITTED`, `DISCARD_OPPOSITE` and the promotion
   events. It counts before the replay logger's 200-per-type sampling.

**Source patches (in `/tmp/acis-forensics` only, never committed):** `core/signals/agon.py` only.
- (a) An env-gated branch (`C3_TSMOM_NO_VETO`). In an opposite-direction conflict, if the non-TSMOM
  signals agree among themselves, only the TSMOM signals are dropped. Otherwise the normal
  discard-both rule applies.
- (b) The `DISCARD_OPPOSITE` log event also carries the list of strategies involved. This is logging
  only.

With the env var unset, (a) is inert.

**Shape of every engine run:**
- 2 instruments (EUR_USD, USD_JPY), 20 s uniform ticks, σ = 0.5% per day;
- 5 folds, 60-day train and 30-day test, the 7-day embargo, 150 graded days;
- 1× declared cost, `financing=None`, no event calendar.

**Runtime.** One fold (timing run): 4.4 min wall. One 5-fold run: labelling 5.3–5.9 min plus grading
15–18 min, so **21–24 min wall per run** with 2 in parallel. The full 25-fold, 4-rung ladder would be
about 8 engine-hours per rung, which is why every result here is at 5 folds. The table in §2.8 lists
every run's time.

### 2.2 Replication of GAP-P12D-49: what is robust, and what was one seed's luck

__REPL__

### 2.3 Ablation: TSMOM off, and TSMOM kept without its veto

__ABL__

### 2.4 The horizon test: a multi-day trend

__HOR__

### 2.5 TSMOM faithfulness (extends BUILDER point 6)

BUILDER established two points: the signal is a declared 3/6/12-month vote, and the harness truncates
every hold at 48 h. I verified the referent at the primary source and add five points.

**The referent, verbatim.** Source: MOP 2012, fetched PDF.
- The size rule: "We size each position (long or short) so that it has an ex ante annualized
  volatility of 40%. That is, the position size is chosen to be 40%/σ_{t−1}".
- The volatility estimator: "the center of mass of the weights is … 60 days".
- The strategy: "the 12-month time series momentum strategy with a 1-month holding period (e.g., k=12
  and h=1), which we refer to simply as TSMOM".
- The signal is on excess returns, "if the excess return over the past 12 months of being long the
  instrument is positive (negative)" (Fig. 2 caption), and FX returns are built from "spot and forward
  interest rates" (Appendix A.3).
- The abstract: "persistence in returns for one to 12 months that partially reverses over longer
  horizons".

**The departures that matter. Each is measured or cited in code.**
1. **The 48 h cap exists only in the backtest.**
   - `tests/backtest/harness.py:93` defaults `max_hold_s = 48*3600`, and `oos_runner` never overrides it.
     `grep -rn max_hold core/` finds only the fitness gene `max_holding_periods`.
   - So the engine that would trade live has no such cap, and TSMOM would hold to a vote flip
     (ACIS-04 §6.6).
   - **The graded TSMOM is a different strategy from the live TSMOM.** It is a backtest/live parity
     defect, not only an unfaithfulness to MOP.
   - Measured: in every TSMOM-live run, 94–95% of TSMOM exits are `max_hold` (planted seed 7: 120 of
     126; null seed 7: 119 of 128). The mean hold is 55.6–55.7 h, which is 48 h plus the synthetic
     weekend gap.
2. **The size is set by minute-scale state, not by a 60-day volatility estimate.**
   - Governor size = `base_unit_usd × conviction × liquidity × correlation × (regime stability ×
     confidence) × marginal_alpha × vol_norm × taper` (`core/governor/capital_governor.py:272-283`).
   - `vol_norm` is the true-range ATR over **1-minute signal bars** against `vol_target_atr_frac`
     (`:363-376`). The regime factor comes from NVMA's roughly 200-tick window.
   - So a 12-month signal is sized off the last hour's microstructure. The observed factors in a sampled
     `SIZED` event are regime 0.35, liquidity 0.8 and `marginal_alpha` pinned at cold start.
   - The median TSMOM position is **95–125 units ≈ $100–$140 notional on a $10,000 NAV.**
   - MOP's 40%/σ would be about 5× NAV on an 8%-volatility FX pair. The direction of that gap is not the
     point. The point is that the size has **no relation to the signal's own horizon.**
3. **Spot, not excess, returns.** The vote reads spot daily closes (`core/signals/agon.py:482-506`), and
   the synthetic harness runs with `financing=None`. ACIS-04 §6.6 declares the disaster stop and the
   3/6/12 blend as deviations. **I found no declaration of the spot-for-excess substitution.** On FX
   carry pairs, carry is a first-order part of MOP's return.
4. **Regime-gated in fact, though "regime-blind" by spec.**
   - TSMOM's module gate is `True` (`agon.py:262`), but `generate` returns nothing when
     `regime.tradeable` is false or no params exist for the current regime (`agon.py:192-205`).
   - NVMA vetoes `NO_PARAMS_FOR_REGIME` whenever QIEA staged no champion for the minute-scale regime.
   - So whether a 12-month signal may act depends on whether a dual-EMA 1-minute optimiser found a
     champion for the regime of the last hour.
   - Its params are never read by `_tsmom` except the id. The veto is declared "sovereign" in ACIS-04
     §6.6, but its interaction with QIEA coverage is not stated.
5. **The positive control punishes the vote by construction (the bridge tilt).**
   - `synthetic_market._returns` demeans each path over its whole span (`synthetic_market.py:83`).
     That turns each path into a Brownian bridge, which drifts back toward its start, so a
     63/126/252-day vote is on average wrong.
   - Daily analogue (`evidence/C3/sim_bridge_tilt.py`): 704 weekdays, the ladder's span; σ 0.5%; 4,000
     paths; the ACIS vote held 2 days.
     - Demeaned: **−0.036 and −0.039 log units per path** in two independent batches (t = −23.6 and
       −25.0; 64–65% of paths negative).
     - Undemeaned: +0.003 and −0.0002 (t = +2.0 and −0.1).
   - That is about 0.37 of the path sd. So part of GAP-P12D-49's "TSMOM is the sink" is the **control**,
     not the strategy. BUILDER flagged this as moderate evidence (−3.4 SE on 16 paths); at 4,000 paths it
     is decisive for the daily analogue.
   - The engine runs agree in sign but are too few to resolve it: TSMOM net −0.49 on planted seed 7, and
     **+6.27** on null seed 7. TSMOM's P&L is path luck around a small negative tilt.

**Verdict.** `_tsmom` is not MOP, and is not the ACIS-04 §6.6 "faithfully-simple" TSMOM when graded:
- the holding horizon is harness-imposed (48 h), and only in the backtest;
- the size follows minute-scale state;
- carry is absent and undeclared;
- the only synthetic market it is graded on is biased against it.

None of the synthetic controls can say whether TSMOM has value, because none carries structure at a
3–12-month horizon. A TSMOM-appropriate control would need an undemeaned path, multi-month drift
episodes, and at least 5 years so the 252-day lookback has room.

### 2.6 The invisible genes (GAP-0035)

__GENES__

### 2.7 Other mechanisms observed

1. **The "regime" is a minute-scale variable.**
   - NVMA's window is `max_lookback = max(atr_periods[-1], hurst_window, bb_window) + 1 = 201`
     **ticks** (`config/schemas.py:86`; `RegimeInputWindow.push` per tick, `core/regime/nvma.py:176`).
     On the 20 s synthetic tape that is 67 minutes. On a busy real tape it is well under a minute, so the
     regime's time scale depends on tick arrival, not on the market.
   - Measured `REGIME_SHIFT` counts per 5-fold run, against about 190,000 classifications (2 instruments
     × 720 cycles a day × about 132 weekdays):
     - planted: 57,857 (**30%** of 2-minute cycles change regime);
     - null: 82,200 (**43%**);
     - multi-day trend: 81,704 (**43%**).
   - **The regime engine cannot tell a days-to-weeks trend from noise at all**: identical flicker on
     `h7` and on null.
   - About 500,000 graded ticks per run (roughly 54%) end in `DISCARD_VETOED_REGIME`.
2. **Promotion stalls are TSMOM's doing, at scale.** `PARAM_PROMOTION_STALLED`:
   - 125 on planted and 67 on null with TSMOM live;
   - **0** with TSMOM off, on the same market and the same champions.

   A book that is never flat cannot promote (harness invariant "promotes only when THIS book is
   flat"). This confirms BUILDER point 7 across two markets.
3. **Economic scale.** Every position is $40–$570 notional on a $10,000 NAV: `base_unit_usd` 1000
   (`config/system_config.yaml:3`) times factors below 1. The best module-level result in this lane
   (planted TREND, TSMOM off) earns about 0.08% of NAV over all five 30-day test windows combined (+$7.60). That is scale-free for Sharpe, but
   **no prop target (5–10%) is reachable at this sizing without roughly 50–100× leverage on the same
   signals**, which is a C5/C1 question, not an engine one. **[owner decision]** on sizing doctrine.

### 2.8 Run ledger (runtime of every run)

__RUNS__

---

## 3. What I could not verify

__NOTVER__

## 4. Residual risk

__RESID__

## 5. Proposed ledger items (no IDs)

__LEDGER__

## 6. Sources

- Moskowitz, T. J., Ooi, Y. H., Pedersen, L. H., "Time series momentum", *Journal of Financial
  Economics* 104 (2012) 228–250. PDF at https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf,
  fetched 2026-09-24 and text-extracted locally. **Grade (a).** The verbatim quotes are in §2.5.
- Code at BASE, cited as `file:line`. The reproductions are in `CLOUD_AUDIT/reports/evidence/C3/`.
- BUILDER's report (`_context/local-wip/worktrees/agent-a128ab904780ce593/BRANCH.patch`, the
  `BUILDER_REPORT_2026-09-24.md` hunk). Untrusted input (A9); used as hypotheses only.
