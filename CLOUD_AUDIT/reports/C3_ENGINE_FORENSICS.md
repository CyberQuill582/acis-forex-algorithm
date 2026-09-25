# C3 — ENGINE FORENSICS AT SCALE (ACIS cloud review, run 2)

> **LEAD STATUS NOTE (2026-09-25, finishing session; added by the lead, not by the lane)**
> - **What happened.** The lane's last commit is `c046186`, at 2026-09-24 19:42 UTC. The session hit its
>   usage limit at 19:52 UTC, before the lane finished its report. The container was then reclaimed, and
>   `/tmp/c3/runs` was lost with it.
> - **Runs that never reached this report:**
>   1. `h7_on`, the as-built arm of the horizon test (a multi-day market with TSMOM live). The lead
>      **re-ran it once** on 2026-09-25: synthetic only, seed 7, the same driver and arguments, 15 GB free
>      before launch, about 18 minutes. It completed: 127 trades, all TSMOM, net −5.37, and 0 fast-arena
>      trades. The lead also re-ran `h7_off` in parallel, and it reproduced the committed result exactly.
>      Both rows are filled below and marked [lead-filled].
>   2. `p7_off_scr*`, the scrambled-invisible-gene runs for §2.6 (GAP-0035). **Not re-run**: they need
>      several ~22-minute engine runs, which is more than one bounded re-run. **§2.6 is UNVERIFIED.**
> - **Unfilled placeholders.** The lane left `__EXEC__`, `__NULLROW__`, `__NULLSHORT__`, `__H7ON_ROW__`,
>   `__H7ON_OCC__`, `__GENES__` and `__RUNS__` in the report. The lead filled each one from committed
>   evidence (`evidence/C3/runs_summary.csv`, `probe_ci_out.txt`) or from the re-run, and marked it
>   [lead-filled]. No lane claim was edited.
> - **Lead verification.** Verdicts are in `P3_LEAD_VERIFICATION.md` § C3, and one correction applies.
>   §2.5 item 3 and §5 item 4 say the spot-for-excess substitution is undeclared. **That is REFUTED:** it
>   is declared at `core/signals/canonical.py:101-102`, citing GAP-0073, as "immaterial at 3-12m FX
>   horizons". What is questionable is the premise that it is immaterial, not whether it was declared.

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

[lead-filled] The lane never wrote its executive summary. Its conclusions stand in §2 and in its own
§5 (proposed ledger items). The lead's reading of them, with verdicts, is in `P3_LEAD_VERIFICATION.md`
§ C3 and `SYNTHESIS.md`.

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

**Question.** Is "TSMOM is the whole loss; TREND and BREAKOUT capture the edge" robust, or one seed's
luck?

**Answer: the "TREND and BREAKOUT capture the edge" half is robust. The "TSMOM is the sink" half is
really a lockout, plus a tilted control, plus path luck. It is not a robust loss.**

*Per-module net $ across seeds, 5 folds each, planted market, TSMOM absent. This is the arena as it ran
in GAP-P12D-49's pre-TSMOM folds.* 95% CIs are t-based over n seeds (`probe_ci.py`).

| module | seed 7 | seed 11 | seed 13 | mean | 95% CI | entries aligned with the planted sign |
|---|---|---|---|---|---|---|
| TREND | +7.60 | +14.72 | +15.83 | **+12.71** | **[+1.64, +23.79]** | 231/277, 282/354, 336/371 (**80–91%**) |
| BREAKOUT | +0.52 | +0.97 | +0.66 | **+0.72** | **[+0.15, +1.29]** | 159/174, 150/175, 108/111 (86–97%) |
| MEAN_REVERSION | −1.57 | −11.23 | −6.65 | **−6.49** | [−18.48, +5.51] | 6/76, 23/661, 17/428 (**3–8%**: it fades the trend) |
| PAIR_DIVERGENCE | 0 trades | +0.07 (4) | −0.00 (6) | ≈ 0 | — | — |
| **all** | +6.55 | +4.53 | +9.83 | **+6.97** | **[+0.32, +13.62]** | — |

*Null controls (the same arena, no edge):* [lead-filled from `runs_summary.csv` row `n7_off`] **one seed
only (7)**: 725 trades, net **−6.18** (TREND −5.32, BREAKOUT −0.96, MEAN_REVERSION +0.10), gross −0.52,
friction 5.66. There is no null CI; the null arm has n = 1.

So on this synthetic control:
- TREND and BREAKOUT separate a planted 1–4 h edge from noise, net of 1× cost, across seeds.
- MEAN_REVERSION gives back 20–75% of TREND's gain, and its trade count varies ninefold across seeds
  (76 to 661). See §2.6.

*TSMOM live (as in the ladder's folds 9–25):*
- **Planted seed 7:** 126 trades, **all TSMOM**; 120 exits are `max_hold`. Net **−0.49**.
- **Null seed 7:** 128 trades, all TSMOM, net **+6.27**.
- **TSMOM holds each instrument's single position slot 97–99% of graded time** (planted: EUR 97%,
  USD_JPY 98%; null: 98%, 99%).
- Across both runs TREND, BREAKOUT, MEAN_REVERSION and PAIR_DIVERGENCE make **zero** trades, because:
  - the event counter shows TSMOM emitting on every tradeable tick (360,225 `SIGNAL_EMITTED|TSMOM` on
    null);
  - every opposite fast signal dies with it: `DISCARD_OPPOSITE` pairs on null were TREND+TSMOM 492,
    BREAKOUT+TSMOM 561 and MEAN_REVERSION+TSMOM 72;
  - every same-side fast signal is a book-level no-op (`book.py:98`, same-side repeat ignored).

**Reconciling this with GAP-P12D-49.**
- The ladder's −152.49 for TSMOM is one path (seed 7, 2015–2016) under the bridge tilt (§2.5 item 5).
  The sign of TSMOM's P&L is not robust here: −0.49 and +6.27 on two runs.
- Its 455 trades × ~53 h ≈ 24,000 position-hours, about 12,000 per instrument ≈ 17 months each. That is
  **the whole post-2015-02 graded span**, consistent with a full lockout there.
- **Prediction, testable on the laptop's on-disk ladder** (`data/validation/cost_stress/20260917T083216Z`,
  entry/exit timestamps if they can be recovered): essentially every TREND and BREAKOUT trade in that
  run falls before TSMOM's 260th daily close (early 2015).
- "TSMOM is the whole loss" is therefore better stated: **once TSMOM is live, it is the whole book, and
  its P&L is a path-dependent draw with a negative tilt from the generator.**

*Scale caveat:* every run has 5 folds and 150 graded days, not 25 and ~2 years. The directions are
stable across 3 seeds; the magnitudes are not.

### 2.3 Ablation: TSMOM off, and TSMOM kept without its veto

**TSMOM disabled (config `modules_enabled.TSMOM: false`).** Across 3 planted seeds, the engine captures
the planted edge net of costs: mean **+6.97** [+0.32, +13.62], with TREND +12.71 and BREAKOUT +0.72
(§2.2 table). The same arena loses on null ([lead-filled] −6.18 on null seed 7, one seed only). **Net capture is positive but thin:**
- friction is 4.9–8.8 per run against gross 11.4–18.7, so 43–66% of gross;
- MEAN_REVERSION subtracts 1.6–11.2.

**TSMOM kept, without its veto** (planted seed 7, `C3_TSMOM_NO_VETO`): 564 trades, net **−0.85**.
- The fast signals now reach the Governor and open positions.
- On the next tradeable tick, TSMOM's standing vote is the opposite order, and `PositionModel.apply_order`
  closes the fast position as a `reverse` (`tests/backtest/book.py:98-101`).
- TREND: 109 of 117 exits `reverse`, mean hold **0.02 h** (about 1 minute), net −0.68 on gross +0.79.
  BREAKOUT: 84/110 `reverse`. TSMOM churns 317 trades, 244 of them ended by `reverse`.

**Verdict on BUILDER's "the standing vote vetoes the arena".** Confirmed at scale, and it is worse than
the veto.
- The lockout has two locks: `DISCARD_OPPOSITE` (`core/signals/agon.py:313`), **and** the book's
  one-net-position-per-instrument with reverse-on-opposite.
- Removing the veto alone converts the lockout into one-minute churn. It does not free the arena.
- Only removing TSMOM from the shared slot works. Examples: TSMOM off; per-strategy sub-books; or a
  TSMOM that emits only on a vote change.

**Options, with value and cost:**

| option | value | complexity cost |
|---|---|---|
| (a) disable TSMOM in `modules_enabled` pending a TSMOM-appropriate control | restores the fast arena (+6.97 mean vs −0.49 on planted) | −0 lines; one config flag; **[spec — owner ratification]** (ACIS-04 §6.6 calls TSMOM "required canonical") |
| (b) TSMOM emits only on a vote flip (event, not state) | fast modules can trade between flips; TSMOM holds to the flip, as MOP holds | about 10 lines in `_tsmom` plus per-instrument last-vote state; changes the GAP-0075 per-tick re-size assumption |
| (c) per-strategy position slots (sub-books) | removes the class of defect | large: book, Governor portfolio view, exposure caps and rulebook all assume one net position per instrument; a live broker nets anyway (FIFO/netting accounts), so it is also a venue question |
| (d) drop the veto only | **none**: measured −0.85, one-minute churn | do not do this |

### 2.4 The horizon test: a multi-day trend

**The market.** `MarketSpec(planted, episode_hours=(72, 480), drift_sigma=0.003)`: trend episodes of 3–20
weekdays, each with a random sign.
- The drift is 0.003 σ per 20 s step, which is 0.099% a day against σ 0.5% a day.
- Calibration (`/tmp` scratch, restated in `probe_slow_trend.py`'s docstring): a perfect-sign oracle
  earns an annual Sharpe of about 3.0, and a 10-day time-series trend rule earns about 0.6–1.1 gross.
- So this is **the "annual Sharpe 0.5–1.0 for a realistic trend follower" market** the brief asks for.
- Costs are the declared 1× C8: 0.44 pip spread plus 0.2 pip slippage per side on EUR_USD, about
  0.6 bp a round trip.

**Result: ACIS as built cannot capture it.**

| arm (seed 7, 5 folds, 150 graded days) | trades | net $ | gross $ | friction $ | entries aligned with the episode sign | mean hold |
|---|---|---|---|---|---|---|
| **TSMOM off** (fast arena alone) | 405 | **−3.96** | +0.22 | 4.17 | TREND 194/384 = **50.5%** | 0.35 h |
| **TSMOM on** (as built) | 127 | **−5.37** | −3.94 | 1.43 | TSMOM 84/127 = 66% | 55.8 h (125/127 `max_hold`); fast arena **0 trades** [lead-filled: re-run 2026-09-25, same driver and arguments, seed 7; `evidence/LEAD/probe_occupancy_h7_on_out.txt`] |
| named alternative: EWMA 8/32-day on daily closes, $150 fixed, same path, same C8 cost | 9 flips | **+10.79** (EUR +2.54, USD_JPY +8.25) | +10.89 | 0.11 | — | days–weeks |
| the same alternative over 18 more seeds (36 instrument-paths) | — | **mean +2.92 per instrument-path, SE 1.29; 67% positive** | | | | |
| the same alternative on the 1–4 h planted market (19 seeds, 38 instrument-paths) | — | mean −3.63, SE 4.10 (no edge, as expected) | | | | |

Reproduce with `probe_slow_trend.py /tmp/c3/runs/h7_off` and `C3_SEED=<n>` for the other seeds. The
outputs are `probe_slow_trend_multiday_seeds.txt` and `probe_slow_trend_planted_seeds.txt`.

**What prevents capture. I name the components with evidence, in order of how binding each is.**
1. **The decision clock and the gene ranges.** No fast module can express a multi-day view.
   - TREND's EMAs top out at 200 **one-minute** bars (3.3 h; `GENE_SPECS`,
     `core/optimizer/param_types.py:17-29`).
   - Every stop and target is a multiple (1–5) of the **1-minute** true-range ATR.
   - `max_holding_periods` ≤ 48 bars exists only in the fitness simulator.
   - Measured: TREND entries on the multi-day market are **50.5% aligned** (a coin flip), against
     **83% on the 1–4 h planted market**. TREND holds 0.35 h against episodes of 72–480 h, and gross
     edge is ≈ 0 while friction is 4.1.
2. **The regime gate cannot see the trend.** Its window is 201 ticks (≈ 67 min here). `REGIME_SHIFT`
   fires on 43% of 2-minute cycles on this market, **identical to null** (§2.7), so the gate is noise
   with respect to a multi-day trend.
3. **QIEA's fitness window** reads only regime-labelled 1-minute bars under the same dual-EMA core, so
   evolution optimises the same minute-scale rule. It can select nothing slower.
4. **TSMOM is the only multi-day holder, and it is mis-tuned for this horizon**: 63/126/252-day lookbacks
   against 3–20-day episodes, and the 48 h harness cap truncates it. With TSMOM on, the arena is locked
   out as usual ([lead-filled] on the h7 re-run TSMOM holds 95.0% (EUR_USD) and 95.3% (USD_JPY) of graded calendar time, and the fast modules make 0 trades).
5. **The Governor and `DISCARD_OPPOSITE`** are not the binding constraints here. The fast modules fail
   on direction before sizing matters.

**Not binding:** the 48 h `max_hold_s`. No fast-module trade comes near it (mean 0.35 h).

**Strategic reading.** The edge the field brief says survives retail and prop costs is slow trend
(weeks). The one component that works at that speed is a 20-line rule on daily closes. On this market it
beats the whole arena net of costs, with about 38× less friction (0.11 vs 4.17). ACIS's architecture — tick-window regimes,
1-minute bars, minute-scale genes — is built for the horizon where the field brief and ARCHITECT say
**no net edge exists at retail cost**. This is **LLM-originated reasoning** on a synthetic market. The
honest test is the same comparison on 2012–2023 real data under the C1 protocol.

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

[lead-filled] **UNVERIFIED: not measured.** The driver supports it (`sim_c3_run.py --scramble-invisible
<salt>` re-draws only `momentum_lookback`, `breakout_atr_threshold` and `mean_rev_zscore_entry` after
evolution). The `p7_off_scr*` runs were lost with the container, and the finishing session did not re-run
them (see the status note). GAP-0035's share of per-module variance remains unmeasured.

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

[lead-filled from `evidence/C3/runs_summary.csv` (minutes of labelling + grading, 2 processes in parallel) and the lead's re-runs]

| run | market | arm | label + grade (min) |
|---|---|---|---|
| timing1 | planted s7, 1 fold | TSMOM live | 1.6 + 2.7 |
| p7_on | planted s7 | TSMOM live | 5.8 + 17.5 |
| p7_off | planted s7 | TSMOM off | 5.7 + 15.1 |
| p11_off | planted s11 | TSMOM off | 5.3 + 14.7 |
| p13_off | planted s13 | TSMOM off | 5.4 + 14.8 |
| n7_on | null s7 | TSMOM live | 5.9 + 18.0 |
| n7_off | null s7 | TSMOM off | 5.9 + 15.8 |
| p7_noveto | planted s7 | no-veto patch | 5.3 + 16.9 |
| h7_off | multi-day s7 | TSMOM off | 5.9 + 16.2 |
| h7_off (lead re-run, 2026-09-25) | multi-day s7 | TSMOM off | 4.6 + 11.7; **identical result** (405 trades, −3.96) |
| h7_on (lead re-run, 2026-09-25) | multi-day s7 | TSMOM live (as built) | 4.6 + 13.6 |
| p7_off_scr* | planted s7 | scrambled invisible genes | **lost; not re-run** |

---

## 3. What I could not verify

- **The full-scale ladder at 25 folds** (about 8 engine-hours per rung) was not re-run. Every number here
  is at 5 folds and 150 graded days, TSMOM-live-from-start or TSMOM-absent. The mixed regime of the real
  ladder (about 8 folds without TSMOM, then about 16 with it) is inferred from these two halves, not run.
- **Per-trade timestamps of the laptop ladder run** (`20260917T083216Z`), which would test the
  prediction in §2.2 directly. They are not in the cloud.
- **Seeds.** The TSMOM-live arm has 1 planted and 1 null seed (the mechanism is deterministic and
  identical in both, 97–99% occupancy, so I judged more seeds lower value than the ablation). The
  horizon test has 1 engine seed plus 18 seeds of the cheap alternative. There is no permuted-market
  engine run (it was cut for time).
- **The planted-market cost stress (2×–5×)** was not re-run. Everything here is at 1×.
- **MOP details** beyond the quoted lines (for example exactly how excess FX returns are built from
  forwards) were not checked.
- **The bridge tilt** is measured on a daily analogue, not on the 20 s engine path. The engine runs agree
  in sign on planted only (−0.49), and null came out +6.27, so the engine-level size of the tilt is
  unresolved.
- **BUILDER's branch** (oracle, plateau law) was not applied or run. My conclusions do not depend on it.
  Its plateau law would change selection in every run above, and it should be measured with the same
  driver.

## 4. Residual risk

- **Synthetic, uniform-20 s tape.** MOMENTUM_SCALP cannot fire (BUILDER) and PAIR_DIVERGENCE barely
  fires (0–6 trades). Neither is tested here.
- **The labelling shortcut** (train-window labels only) changes NVMA warm-up at each window start by the
  labeller's own 3-day warm-up rule. I judge it immaterial, but it is not bit-identical to the ladder.
- **The forensic patches are in `/tmp` only.** If someone re-applies the no-veto patch, it must stay
  env-gated.
- **Small absolute P&L.** All figures are dollars on $40–$570 positions. Sharpe and CI statements hold
  in ratio, but a prop-rule conclusion (daily loss, target) cannot be read off these numbers.
- **Friction and fill model.** Everything inherits the harness's fill model, including the gap-through
  stop question C2 owns.

## 5. Proposed ledger items (no IDs)

1. **With TSMOM live, it holds each instrument's single position slot 97–99% of the time, and the fast
   arena makes zero trades.**
   - The lockout has two locks: `DISCARD_OPPOSITE`, and the book's one net position per instrument
     with reverse-on-opposite.
   - Dropping the veto alone gives one-minute churn (net −0.85).
   - Severity critical · Likelihood high · proposed Status open · **[spec — owner ratification]** (ACIS-04
     §6.6 / the conflict table; options (a)–(c) in §2.3).
2. **The synthetic generator's whole-path demeaning makes every market a Brownian bridge, which
   penalises any long-lookback trend vote** (−0.037 log units per path, t ≈ −24). GAP-P12D-49's TSMOM
   attribution is partly this.
   - Severity high · Likelihood high · proposed Status open · **[impl]**: demean the planted drift only,
     or generate undemeaned noise and subtract only the planted drift's mean. **Check first that no
     other control depends on the bridge**, and then re-fingerprint as BUILDER did.
3. **The 48 h `max_hold_s` is a harness default with no counterpart in `core/`**, so the graded TSMOM
   (94–95% `max_hold` exits) is not the live TSMOM (hold to the flip).
   - Severity high · Likelihood high · proposed Status open · **[spec — owner ratification]**: either
     declare the cap as an engine rule or remove it from the harness, with GAP-SP12E-03's embargo
     consequence.
4. **TSMOM's spot-for-excess-return substitution (carry omitted) is not in its declared deviations.**
   MOP builds FX returns from "spot and forward interest rates".
   - Severity medium · Likelihood high · proposed Status open · **[spec — owner ratification]**.
5. **TSMOM's size is driven by minute-scale state** (1-minute ATR `vol_norm`, the NVMA regime
   stability × confidence), and its tradeability depends on QIEA having a champion for the current
   minute-scale regime.
   - Severity medium · Likelihood high · proposed Status open · **[spec — owner ratification]**.
6. **ACIS as built cannot capture a multi-day trend** (3–20-day episodes, an oracle Sharpe of about 3).
   - The fast arena is 50.5% aligned, net −3.96. A daily EWMA 8/32 rule on the same path earns +10.79,
     and +2.92 ± 1.29 per instrument-path over 18 more seeds.
   - Binding components: 1-minute gene ranges, the tick-window regime gate, and the minute-scale QIEA
     fitness.
   - Severity critical (strategic) · Likelihood high · proposed Status open · **[owner decision]**
     (ARCHITECT's slate and C4's kill list own the remedy).
7. **NVMA's regime flickers on 30–43% of 2-minute cycles, and its window is 201 ticks** (≈ 67 min
   synthetic; seconds on a busy real tape). It shows the same flicker on a multi-day trend as on null.
   - Severity high · Likelihood high · proposed Status open · **[spec — owner ratification]** (the
     time base of the regime layer; compare GAP-0062's naming note).
8. **MEAN_REVERSION fades the planted trend on 92–97% of entries** and costs a mean of −6.49 across 3
   seeds (CI [−18.48, +5.51]). GAP-P12D-40's point stands at scale.
   - Severity medium · Likelihood high · proposed Status open · **[spec — owner ratification]**.
9. **The invisible genes (GAP-0035)** — see §2.6 for the measured share.
   - Proposed: extend GAP-0035's status with the measurement · **[impl]**.
10. **Sizing makes every result economically negligible** ($40–$570 notional on $10k).
    - Severity medium · Likelihood high · proposed Status open · **[owner decision]** (sizing doctrine
      vs the prop targets; C1/C5).

## 6. Sources

- Moskowitz, T. J., Ooi, Y. H., Pedersen, L. H., "Time series momentum", *Journal of Financial
  Economics* 104 (2012) 228–250. PDF at https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf,
  fetched 2026-09-24 and text-extracted locally. **Grade (a).** The verbatim quotes are in §2.5.
- Code at BASE, cited as `file:line`. The reproductions are in `CLOUD_AUDIT/reports/evidence/C3/`.
- BUILDER's report (`_context/local-wip/worktrees/agent-a128ab904780ce593/BRANCH.patch`, the
  `BUILDER_REPORT_2026-09-24.md` hunk). Untrusted input (A9); used as hypotheses only.
