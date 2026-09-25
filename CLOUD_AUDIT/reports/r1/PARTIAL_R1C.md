# PARTIAL R1-C — SYNTHETIC MARKET LAB (early PARTIAL with a draft "For PLAN_R1")

- **Lane:** R1-C. **Model/effort as observed:** Claude Opus 5.5 (`claude-opus-5-5`), effort not shown to me.
- **Fresh context:** yes. I read only BRIEF_R1, FLEET_PLAN §1/§6, C3 §2.5 + §5, P3 § C3, C2 §2.7, the LEAD bridge
  probe, and the BASE files named below.
- **BASE:** `974dbda` (read-only at `/tmp/review-acis`). **Date:** 2026-09-25. **Web used:** 21 of 25.
- **Status:** PARTIAL, updated 08:25 UTC (first commit 08:14). **Superseded by the final `R1C_SYNTH_LAB.md` (08:35 UTC).** Numbers are **DRAFT** unless marked final. Everything is synthetic.

## First findings

1. **The bridge bias becomes decisive under R-1's breadth, and it pays a REVERSAL rule on the null.** (grade: own
   simulation, `evidence/R1C/repro_bridge.py`, output `repro_bridge_out.txt`)
   - Whole-path demeaning (`tests/backtest/synthetic_market.py:113-114`) gives every path the same-signed tilt, so
     pooling adds the tilt coherently while noise averages. Per instrument on a 2.8-year null path, the annual Sharpe
     bias is −0.26 for 126-day momentum and −0.17 to −0.28 for EWMAC 8/32 to 32/128.
   - Pooled over 20 independent instruments that is about **−1.2 for momentum and +1.2 for the mirror reversal
     rule**. A pooled reversal rule would "pass" the demeaned null. (The pooled figure is per-instrument × √20,
     derived. The direct pooled simulation is in finding 4.)
   - On 14-year paths the bias shrinks to −0.05 per instrument (−0.21 pooled at N=20). That is still about a quarter
     of a realistic pooled edge.
   - Closed form (lead's, re-derived; per holding step): E[sign(P)F] = −(h/n)·σ·√L/√(1−L/n)·√(2/π). For
     mom126 it gives −0.0312 per path at n = 705 (simulated −0.0363 ± 0.004) and −0.0423 at n = 3640 (simulated
     −0.0505 ± 0.010).
2. **The fix is "demean nothing" (FIX-A) for null and planted, plus a sign-flip for permuted (FIX-C). C3's
   alternative, "demean only the planted drift" (FIX-B), is itself a bridge on the drift and costs power.**
   (grade: own simulation, same probe)
   - Planted, daily analogue with 5–20-day episodes: mom126 recovers +0.18 SR per instrument with no demeaning,
     +0.10 with drift-only demeaning, and −0.10 with the BASE demeaning. EWMAC 32/128 gives +0.10 / +0.04 / −0.21.
   - **Permuted is a bridge by construction:** a shuffle of a fixed multiset is exchangeable with a fixed sum.
     Shuffle-then-demean (BASE) gives mom126 −0.25 SR per instrument. An undemeaned shuffle carries the planted
     path's realised net drift, a random but real within-path drift that a trend rule harvests (+0.07 vote).
   - **FIX-C, a random ±1 sign on each shuffled return,** makes permuted a martingale-difference sequence given the
     pool. Every non-anticipating rule then has an exact zero expected gross P&L. Measured |t| < 1 on every rule.
   - At the tick generator's own parameters the planted episodes dominate the path's net drift. The episode-drift
     variance d²·Σlen² is about 11× the noise variance n·σ² (d = 0.15σ, lengths 180–720 steps). So an undemeaned
     *shuffle* there would carry a large spurious drift, which is why the author demeaned. The sign-flip is the
     right tool, not demeaning.
3. **The prototype lab passes 9/9 stylized-fact probes on the null, and a plain GARCH(1,1) fails the discriminating
   one.** (grade: own simulation, `evidence/R1C/gen_lab.py`, `probe_stylized.py`; targets quoted from Cont 2001, grade a)
   - 20 instruments × 3,640 weekdays, 4 seeds. In the vol-model sweep, tolerances marked "lab" are mine.
   - Results:
     - no linear autocorrelation: 5.4% of lags outside a heteroskedasticity-robust band;
     - Hill tail index 3.52, inside Cont's "higher than two and less than five";
     - no gain/loss asymmetry, skew +0.04 (FX, Cont footnote 2);
     - aggregational Gaussianity: excess kurtosis 9.95 → 4.58 → 2.47 at 1 / 5 / 20 days;
     - volatility clustering: acf(|r|) at lags 1–5 is 0.20;
     - conditional heavy tails: kurtosis 7.07 < 12.95;
     - slow decay: β = 0.40, and a power law fits better than an exponential (R² 0.94 vs 0.90).
   - GARCH(1,1) alone gives β = 0.33, *inside* Cont's [0.2, 0.4], yet an exponential fits far better (R² 0.98 vs
     0.78). **So the β-range alone does not discriminate; the shape test does.**
   - The volatility model needed a multi-scale log-volatility component (half-lives 3 to 1,875 days).
   - **Declared tuning:** the vol knobs were swept 6 times on the lab itself toward Cont's quoted qualitative
     targets, never toward data. I also changed two tolerances after the first run and say so: the ACF band went
     iid → robust, because the iid band is invalid under volatility clustering; aggregational Gaussianity went from
     "20-day < 1.0" to "20-day < half of 1-day".
4. **The lab is useful: the null centres on zero, and a planted trend is detected at its theoretical rate.**
   (grade: own simulation; `probe_calibration.py`, output `probe_calibration_out.txt`)
   - Setup: a pooled, parameter-free EWMAC 16/64 (sign position, vol-targeted, equal risk) on 20 lab instruments,
     over 13.3 graded years and 100 seeds.
   - **Null:** mean SR −0.013 (se 0.025), false-detect rate 4.0% at one-sided 5%.
   - **Planted trend** (half-life 60 d; theory 0.25 SR per instrument, 0.828 pooled; theory power 0.915): mean SR
     **+0.808** (se 0.023), detected **96%**.
   - With the BASE demeaning re-applied: null −0.031 and planted +0.771 (91%). On 14-year paths with a
     vol-targeted rule the tilt is small, which matches the closed form's 1/n scaling.
   - **The bias is a short-path problem, and the fold/ladder spans (0.2–2.8 years) are where it bites.**

5. **NEW: the BASE planted tick market is ~3.3× more volatile per day than its null.** (grade: own measurement on
   the PRODUCTION generator, read-only; `evidence/R1C/probe_planted_vol.py`)
   - Daily sd: null 0.0053, planted 0.0176, permuted 0.0046. The analytic ratio is 3.51, from
     √(1 + drift_sigma²·E[len²]/E[len]).
   - The planted 1–4 h episodes carry ~92% of planted's daily variance. The frictionless oracle's annual Sharpe
     is ~drift_sigma·√(252·4320) ≈ 157.
   - So "planted passes, null fails" also compares an 8%-vol market against a 28%-vol one: the cost/move ratio,
     ATR and NVMA inputs, stop distances and VaR all differ.
   - A daily lab must plant **variance-matched** effects. Mine does, by construction: the drift is in vol units,
     with var(m) ≈ 0.0024 of the total.
6. **NEW: intraday refinement must bridge the common factor JOINTLY, or it plants a pairs edge.**
   (`probe_intraday.py`, 3,600 days × 3 seeds)
   - Per-instrument bridges pinned at correlated daily endpoints make j's day-so-far predict i's rest-of-day:
     a "catch-up" rule earns +0.08 to +0.12 vol units a day (t 6.3–8.6).
   - One shared factor bridge plus idiosyncratic bridges gives +0.02 / −0.004 / −0.02 (|t| ≤ 1.7). Ticks sum to
     the daily bar to 1e-17.
   - A day pinned to zero (the BASE defect at day scale) pays day-so-far momentum −0.40 (t −356), against ≈0 on
     the lab.
7. **Effects deliver their declared Sharpe.** (`probe_effects.py`, 20 seeds × 20 instruments, target 0.5 per
   instrument, vol units)
   - Delivered: carry rule 0.500, trend oracle 0.501, XS oracle 0.514, season oracle 0.500. EWMAC 16/64 on the
     trend gives 0.135 against a closed form of 0.115 (se 0.021). Null rows are within 2 se of 0.
   - The effects are NOT orthogonal to other families' rules. A planted carry (persistent rates) pays
     EWMAC 16/64 +0.16 and XS-rank +0.17, and a planted XS drift pays EWMAC +0.12. Power must be stated per
     (effect, rule) pair, never per family label.
8. **Short paths (2.8 graded years, 400 seeds):**
   - null −0.020 ± 0.031, detect 4.3%;
   - planted +0.806 against theory 0.828, detect **40.3% against theory 39.8%**;
   - with the BASE demeaning: null **−0.199** (6 se), planted 0.442, and power **halves to 18.8%**.

## Draft "For PLAN_R1" (DRAFT, for the lead's v1)

| # | Recommendation | Value | Complexity | Grade | Falsifier | Verdict |
|---|---|---|---|---|---|---|
| C-1 | **Fix the generator's null.** At `synthetic_market.py:113-114`, delete the whole-path demean for null and planted. For permuted, replace shuffle-then-demean with shuffle followed by an independent ±1 sign per return, drawn from the same rng *after* the shuffle so that null and planted draws are unchanged. | The null becomes a martingale: zero expected P&L for any rule at any horizon. It removes a −1.2 (momentum) / +1.2 (reversal) pooled-SR bias at N = 20 on 2.8-year paths. | About −2 / +4 lines. **Two unit tests codify the bug and must change** (`tests/backtest/test_synthetic_market.py:27-32` asserts `abs(fsum(returns)) < 1e-9`, i.e. zero *realised* drift; `:42-45` asserts `sorted` equality). Replace them with zero *expected* drift (the mean of path sums over ~200 seeds within 3 se) and `sorted(abs)` equality. Re-verify the oracle rungs (`oracle.py:127`, 0.42/0.46), because planted returns shift by the removed mean (~1% of the drift). | own sim (probe) + closed form | Undemeaned null paths still show a pooled rule mean more than 3 se from 0 over 1,000 seeds. | **adopt** |
| C-2 | **Build the daily-first lab** (`gen_lab.py` design) as a new module, beside the tick generator. Components: vol-unit construction; one common factor (ρ knob); Student-t by scale mixture; GARCH(1,1) × multi-scale log-volatility; compound-Poisson jumps; a Monday gap; rate differentials with a financing accrual; five plantable effects (trend at speed and strength, carry, XS momentum, turn-of-month, null) whose Sharpe is closed-form or calibrated; intraday ticks on demand by a *conditionally exact* bridge inside each day on a session time-change, with session spreads, a rollover spike and random spikes. | Unlimited machinery iteration with known ground truth at R-1's horizon. 20 instruments × 14 years takes ~0.2–0.3 s. | ~300 lines (the lab) + ~80 (the `TickSource` adapter) + ~150 (tests). New concepts: vol units, the effect registry, theory functions. | own sim; stylized facts vs Cont (a) | The lab fails the Cont probe set under default knobs, or a planted effect's detect rate misses its theory power by more than 2 se over 500 seeds. | **adopt** (prototype) |
| C-3 | **The null is null only in the P&L the grader books.** If grading books no financing (`financing=None`, as in the synthetic harness today), the lab must set rate differentials to 0: under UIP the spot drifts by −(rate diff), and a spot-only grader would score that as an edge. With financing on, build the lab's rates as a synthetic `RateTable` (`tests/backtest/financing.py:52`), fed through `make_financing` (`:90`), so there is no second financing model. | Stops carry-null false positives. | ~20 lines (a synthetic `RateTable` builder). | own reasoning; code refs | A spot-only grade on a financing-on lab null shows a carry "edge" → the guard is missing. | **adopt** |
| C-4 | **No second cost model.** The lab sets only the *quoted* bid/ask in the tape (session spread profile, rollover ×4, random spikes). Commission and slippage stay in `CostModel` (`core/optimizer/costs.py:27`), built by `evolve_step.cost_model(cfg, i)` from `instruments.yaml`. RSIM prices daily bars with the same `CostModel.per_side_cost(spread)` instance. Synthetic instruments map onto declared cost classes in a test-only `AcisConfig`, never in production config. | One friction path (the GAP-P12D-36 class excluded). | ~30 lines of config shim. | code refs | Any lab-only friction constant found outside `CostModel`. | **adopt** |
| C-5 | **Stylized-facts probe set as the lab's own gate.** Cont's 1, 2, 3 (FX: symmetry), 4, 6, 7 and 8, with a *shape* test for 8 (power vs exponential), a heteroskedasticity-robust ACF band for 1, and intraday seasonality as self-consistency only. | Catches a lab that is too easy (Gaussian iid, like BASE: C2 §2.7). | ~150 lines. | Cont 2001 (a) | — | **adopt** |
| C-7 | **Variance-matched planting and a common factor bridge.** The planted drift is set by a target Sharpe (vol units), and the noise is scaled so that planted and null have equal variance. Intraday ticks come from one factor bridge plus idiosyncratic bridges. Permuted = shuffled days plus one random sign per day (the cross-section is kept). | Planted vs null differ ONLY by the edge. No spurious pairs edge. | ~10 lines in the lab. For the BASE tick generator, a `drift_sigma` default change needs owner ratification (it moves every recorded run). | own measurement / sim | The planted/null variance ratio is outside 1 ± 0.05, or the joint-bridge catch-up rule has \|t\| > 3 over 3 seeds. | **adopt** |
| C-6 | **Machinery-lab family choice: parametric wins** (draft; sources pending). GANs and diffusion need real data to train, which is a look under §0.4, and give no plantable ground truth. Agent-based simulators give ground truth only at the agent-rule level, not at the Sharpe level. | Known Sharpe, so power is computable. | — | pending (web) | — | draft: **adopt parametric; reject GAN/diffusion for the machinery lab; adapt ABM only for microstructure tests** |

## Not yet done
The generator-family literature (task 2, web), calibration on 2.8-year paths and for carry, XS and season, and the integration line count
measured against the BASE tests. Also: per-currency rates (the prototype uses per-instrument differentials), and
the XS-momentum and carry closed-form checks.
