# AUDIT R1.1 — EXTERNAL-REFERENT LENS (2026-09-29)

- **Brief:** `AUDIT_BRIEF_R1_1_2026-09-29.md` (pinned; followed as written). **Audited state:** commit `b5c284a`, read with `git show b5c284a:<path>`; every run was on the Google compute server in the external auditor's own checkout of `b5c284a` (`remote_audit.sh external`).
- **Auditor:** Claude Opus 5.5 (`claude-opus-5-5[1m]`) — an Opus-lineage model at or above the A2 floor; the brief named Opus 5. **Fresh context, finder not clearer (A5).** No subagents were launched. No git writes, no edits other than this file.
- **Web budget:** 8 of the 20 allowed WebSearch calls were used; every other source was fetched directly (WebFetch or `curl`). All sources were accessed on 2026-09-29 and are listed in §6.
- **Probes:** each is in `…/scratchpad/audit/external/probes/` (session scratchpad, not in the repo) and runs as `python probes/<file>.py` on the server. Receipts are quoted inline.
- **Lens:** the implementation AND the design against the outside world — the cited literature, the standard definitions and the venue conventions. Defects only.

## 1. Executive summary

Nine findings: 1 medium-high, 1 medium, 3 medium-low / low-medium, 4 low. The machinery is sound where it is Gaussian by construction. The bridge is exact, the variance match survives GARCH, and the oracle, carry and season forms are exact in volatility units. The defects are all at the seams: between the lab's own units and the grader's, between a closed form and a non-Gaussian, price-unit rule, and between a fixed-seed test and the quantity it claims to measure.

Top three:
1. **E-R11-01 (medium-high).** B0 is tested against a closed-form power, and that closed form is only an approximation. It is off by 1.3–5.3 percentage points of power, depending on knobs and horizon. The 2-se binomial band shrinks with the number of paths while that error does not, so B0 refuses a CORRECT lab once the path count is large enough.
   - At the default knobs over 13.3 years: 92.9% against a theory of 91.6% on 3,000 seeds, **refused**.
   - With ρ = 0: 53.7% against 59.0%, **refused** (5.8 se).
   - With ρ = 0.6 and N = 40: 20.8% against 24.0%, **refused**.
   - At the pinned 400 seeds and 2.8 years it passes. At those settings B0 cannot see a lab whose Sharpe is off by less than about ±9%.
2. **E-R11-02 (medium).** Cont's fact 8 gate (β ∈ [0.2, 0.4]) passes only on its pinned seeds 1–4 (β 0.389).
   - The lab's expected β at default knobs is **0.417** over 200 seeds, OUTSIDE Cont's range.
   - 61% of single seeds fail, and so do **74% of disjoint 4-seed groups** (the gate's own statistic).
3. **E-R11-03 (medium-low).** Cont's fact 2 (tail index 2 < α ≤ 5, "typically close to four") is met only by bias in the Hill estimator.
   - The model's tail index is ≈ 7.8: the Student-t(8) mixing, and a GARCH Kesten root of 7.8.
   - On 400,000-day paths the Hill plot climbs from 2.97 to 4.46 as k shrinks and never settles.
   - So every detector calibrated on the lab is calibrated in a world whose fourth moments are finite and stable, while Cont says real ones are not.

## 2. Findings

### E-R11-01 — B0's criterion is decided by the path count, not by the lab: the theory power is an approximation whose error is comparable to 2 se
- **Severity:** medium-high · **Likelihood:** high. R1.4 will calibrate the new detectors through `calibrate`, and C-BT-11 v2 step 0 makes B0 a precondition of every real-data verdict.
- **Where:** `tests/backtest/lab_calibration.py:74-84` (`Calibration.failures`: |realised − theory| ≤ 2 binomial se at the theory rate); `lab_theory.py:74-112` (`ewmac_sharpe`, `pooled_ewmac_sharpe`, `detection_power`); spec: ACIS-09 v1.8 C-BT-11 v2 step 0 ("a planted effect detected within 2 se of its theory power").
- **Reproduction** (`probes/b0_calibrate.py`, through the audited `calibrate` and `Calibration`, identical rule, spec and effect; only the seed count, length or knobs vary):

| graded (lab years) | seeds | knobs | null | planted | theory power | B0 |
|---|---|---|---|---|---|---|
| 2.8 | 1–400 | default | 22 | 151 (37.8%) | 39.8% | holds (lead's claim reproduced exactly) |
| 2.8 | 1–1000 | default | 60 | 365 (36.5%) | 39.8% | **refused** |
| 2.8 | 1–4000 | default | 202 | 1542 (38.6%) | 39.8% | holds: the 1000-seed refusal was partly chance; the structural gap here is −1.3 pp |
| 13.3 | 1–400 | default | 16 | 375 (93.8%) | 91.6% | holds |
| 13.3 | 1–1000 | default | 41 | 935 (93.5%) | 91.6% | **refused (above theory)** |
| 13.3 | 1–3000 | default | 133 | 2786 (92.9%) | 91.6% | **refused**: a structural +1.3 pp, 2.6 se |
| 2.8 | 1–3000 | ρ = 0 | 167 | 1611 (53.7%) | 59.0% | **refused**: a structural −5.3 pp, 5.8 se |
| 2.8 | 1–3000 | ρ = 0.6, N = 40 | 119 | 624 (20.8%) | 24.0% | **refused**: −3.2 pp, about 4 se |
| 2.8 | 1–400 | default, demeaned | 11 | 73 (18.2%) | 39.8% | refused (lead's claim reproduced) |

- **Where the error comes from** (`probes/b0_horizon.py`, `probes/units.py`, `probes/misc.py` B).
  - **The per-instrument closed form is a volatility-unit statement, and B0's rule is not the object it describes.** On 13.3-year paths, 400 seeds × 20 instruments, ρ = 0, se 0.003:
    - the closed form's own object, sign(EWMAC of y)·y, earns 0.259, so even the closed form is +3.6% off;
    - B0's rule signs the EWMAC of the PRICE-unit r and sizes by an EWMA variance estimate. It earns **0.240 against the stated 0.25**: −2.8% from the price-unit signal and −4.6% from the estimated volatility. With the true σ it earns 0.252.
    - In price units E|X|/sd(X) is 0.755, not √(2/π) = 0.798 (−5.4%). X is a heteroskedastic scale mixture, and the identity E[sign X·Y] = √(2/π)·Cov/sd(X) requires joint Gaussianity (E[Y|X] linear in X; Wikipedia, multivariate normal conditional mean, §6 [7]).
  - **The arcsine (Sheppard) pool correlation overstates the P&L correlation.** Sheppard's formula is stated for the bivariate normal (Sheppard 1898 via Genz–Bretz, §6 [6]).
    - At default knobs: measured 0.032 against the coded 0.043. Even with the jumps' and the Monday gap's cross-instrument independence corrected, the theory is 0.037.
    - At ρ = 0.6 and N = 40: 0.130 against 0.179.
    - At default knobs this overstated correlation roughly cancels the per-instrument overstatement. That is why the pooled mean Sharpe (0.81–0.84) matches the theory's 0.828. It is cancellation, not correctness, and it disappears at ρ = 0.
  - **The t-statistic's dispersion is not 1:** measured 0.943 at 13.3 years, 0.863 at ρ = 0.6 / N = 40, and 1.07 at ρ = 0.
    - `detection_power` = Φ(SR·√Y − z_α) assumes the iid-normal sampling law.
    - Lo (2002) derives the Sharpe ratio's distribution under iid, stationary non-iid and time-aggregated returns. The iid-normal variance is (1 + SR²/2)/T, and assuming normality "may be up to 70% off" (Mertens, as reviewed by Two Sigma; §6 [4], [5]).
    - The pooled P&L's autocorrelations are ≈ 0 once the −1/T sample bias is removed (Bartlett VR(61) = 0.9975 at 13.3 years). So the excess power at long horizons (the question the brief asks) is **not** Lo's serial-correlation effect. It is the non-iid, non-normal sampling law of t.
    - Even Φ applied to the realised mean and sd of t (0.388) misses the realised 36.5% at 2.8 years: t is not normal either.
- **Consequences.**
  - With enough paths, any correct lab is refused. With few paths, B0 has little resolution. At n = 400 the pass band [34.9%, 44.7%] corresponds to a pooled Sharpe of about [0.75, 0.91], ±9% around 0.828.
  - The chance that a CORRECT lab is refused at the pinned n = 400 is about 7% at 2.8 years, about 13% at 13.3 years and about 56% at ρ = 0. Each figure comes from the measured structural gap and the binomial se.
  - The pinned `range(1, 401)` is therefore load-bearing, a hidden degree of freedom for the next person who retunes knobs.
- **Proposed fix (spec plus implementation):**
  - Grade the detection rate against a **Monte-Carlo-calibrated reference power** for the exact (effect, rule, detector, knobs, length). This is R1-C §4's own recommendation: "calibrate the theory constants by Monte Carlo per (effect, rule) and record them, not trust the closed form blindly". Compute it on an independent seed block, recorded with its se.
  - Keep the closed form as a sanity bound with a declared tolerance.
  - Alternatively, state B0 as an equivalence test with a declared Sharpe tolerance δ and a declared n.
  - Either way, state the theory in the rule's units, or run the rule in volatility units.
  - Amend C-BT-11 v2 step 0's "within 2 se of its theory power" accordingly.

### E-R11-02 — Cont fact 8: the lab's expected β is 0.417, outside [0.2, 0.4]; the gate passes on its four pinned seeds
- **Severity:** medium · **Likelihood:** certain. It is a hollow gate (A16) and fails the external referent.
- **Where:** `tests/backtest/test_lab_stylized.py:47-77, 107-110` (seeds 1–4, `0.2 <= beta <= 0.4`).
- **External referent:** Cont (2001), fact 8: "the autocorrelation function of absolute returns decays slowly as a function of the time lag, roughly as a power law with an exponent β ∈ [0.2, 0.4]"; §5 eq. (17): "with a coefficient β ∈ [0.2, 0.4] for absolute or squared returns" (§6 [1]).
- **Reproduction** (`probes/beta_seeds.py`, the gate's own statistic per seed):
  - β over seeds 1–200: mean **0.417**, sd 0.041;
  - 61% of seeds have β > 0.4;
  - of 50 disjoint 4-seed groups, **74% fail** the gate, spanning 0.381 to 0.471;
  - seeds 1–4 give 0.389, the lead's claim.
  - R1-C itself recorded "β = 0.400 sits at the edge … fragile across seeds". The production defaults did not move it inside.
- **Proposed fix:**
  - Re-tune the volatility knobs so the EXPECTED β sits well inside the range. R1-C notes that log-vol sd 0.6 moved β to 0.391 on its seeds, at the cost of kurtosis.
  - Assert on a many-seed estimate with its se, e.g. 40 seeds, requiring 0.2 + 2 se ≤ β̄ ≤ 0.4 − 2 se, not on four pinned seeds.
  - Pin the tolerance with its quote, per R1-C's own "tolerance drift" risk.

### E-R11-03 — Cont fact 2: the model's tail index is ≈ 7.8; the Hill-at-2.5% pass (3.57) is estimator bias
- **Severity:** medium-low · **Likelihood:** certain.
- **Where:** `lab_market.py:69` (`nu = 8.0`, Student-t by variance mixing); `test_lab_stylized.py:34-37, 85-86`.
- **External referent:** Cont (2001) §6 [1]:
  - fact 2: "a tail index which is finite, higher than two and less than five for most data sets studied";
  - §4.2: daily returns of "stocks, market indices and exchange rates, yield … ξ between 0.2 and 0.4, which means a tail index 2 < α(T) ⩽ 5";
  - §5.3: "the tail index obtained for most assets is typically close to four (sometimes less) which means that the fourth moment is not a well-defined numerically stable quantity";
  - §4.1 illustrates asset-like tails with "a Student distribution with four degrees of freedom".
  - Cont also warns that "a positive value of ξ does not imply power-law tails".
- **Reproduction** (`probes/hill.py`, `probes/kesten.py`):
  - the gate's statistic is reproduced: Hill 3.571 at k = 2.5% of 3,640;
  - on three 400,000-day default paths (10% volatility), the Hill plot runs **2.97 (k = 5%), 3.31, 3.60, 3.76, 3.99, 4.05, 4.20, 4.46 (k = 0.02%)**. It rises monotonically without a plateau;
  - by numerical integration, the GARCH(1,1) Kesten root of E[(a y² + b)^(κ/2)] = 1 at (0.04, 0.90) with a unit Student-t(8) shock is **κ ≈ 7.8**;
  - the t(8) mixing bounds the index at 8, and the lognormal SV factor has every moment, so by Breiman's lemma the product keeps the index. The tape's true tail index is therefore ≈ 7.8, outside Cont's range. Its apparent heaviness is the lognormal mixture's body;
  - sample excess kurtosis over the first 3,640 / 36,400 / 100,000 / 400,000 days of one path: 21.6 / 9.7 / 10.6 / 18.2. Finite in theory, erratic in practice.
- **Why it matters:** the lab exists to calibrate detectors under realistic nuisance: B0, GAP-P12D-121's size claim "under fat tails", and the register's FPR (R1-C §2.9). The Sharpe estimator's variance depends on the fourth moment (Mertens, §6 [5]), and the lab's is stable where Cont's real tails are not.
- **Proposed fix:**
  - Lower ν toward 4–5, so the model's index (min(ν, κ)) sits inside (2, 5], then re-tune kurtosis with `sv_sd`.
  - Alternatively, declare the deviation.
  - Replace the one-k Hill assertion with an assertion on the model's tail index, or on a Hill-plot plateau.

### E-R11-04 — C-6 fails for holds inside one FX day: the day's accrual is spread over the ticks, but financing is booked only at the rollover
- **Severity:** medium-low · **Likelihood:** medium. It is a spurious anti-carry edge for any intraday rule, and for frictionless machinery runs (RSIM reconciliation, B0-style checks) on tick tapes.
- **Where:** `lab_intraday.py:16, 89` (`inc = sigma·y − w·accrual`: the drift is spread in proportion to session variance); `lab_source.py:12-15` and `lab_market.py:9-11` (C-6: "a financing-on null is null in the P&L the grader books"). The harness bills only rollovers in (entry, exit] (`core/data/fx_clock.py:130-140`, `book.py:141-149`).
- **External referent:**
  - OANDA books financing only for positions "open at the end of each trading day, at 5pm ET"; a long "open[ed] … at 8:30am ET Wednesday and close[d] … at 3:30pm ET Wednesday" has "no financing cost because no open position is held at 5pm ET" (§6 [8]).
  - Dukascopy ties the charge to the value-date roll: "the difference between the value dates for the rollover trades define[s], how many times the overnight swap rate is applied" (§6 [10]).
  - The deterministic carry adjustment therefore belongs at the rollover instant, where the booked financing offsets it, not across the day.
- **Reproduction** (`probes/intraday_carry.py`: financing-on NULL lab, 16 seeds × 3,639 days × 20 instruments):
  - a same-day hold (tick 0 to the last tick) is billed no rollovers, charge 0;
  - the anti-carry rule held the same way earns **+6.8e-5 a day, pooled t +11.0, per-instrument annual Sharpe +0.18** at the default `rate_sd` 0.02, and **t +25.9 (Sharpe +0.42)** at `rate_sd` 0.05;
  - adding the day's financing makes it vanish (t +1.0, which is the w[0] residue).
  - The lab's quoted spread (1e-4 a round trip) exceeds the default edge, so only frictionless or low-cost runs see it.
- **Proposed fix:**
  - Put each day's whole accrual on the tick at the rollover instant, on the same side of the harness's (entry, exit] boundary as the billed rollover. Every holding window then books a null.
  - Add a test: "an intraday anti-carry hold earns nothing on the financing-on null".

### E-R11-05 — Units: the lab's "known Sharpe" and its "years" are not the grader's
- **Severity:** low-medium · **Likelihood:** high.
- **Where:** `lab_theory.py:1-12` ("VOLATILITY UNITS", `YEAR = 252`); `lab_market.py:42, 64` (`days: 3640 # weekdays (~14.4 years)`); `lab_source.py:9-11` (C-5: `truth` plus `detection_power` "states the power a grade has at its length"); the harness books price units and measures years in calendar time (`report.py:113`, 365.25 days).
- **Reproduction** (`probes/misc.py` D, F):
  - The trend oracle planted at 0.5 earns 0.504 in volatility units, but **0.454 in price units at constant notional (−9%)**. That is the Jensen factor E[σ]/√E[σ²] of the SV/GARCH volatility. A constant-notional harness oracle on a lab tape (C-5) grades about 0.45 against a stated power computed at 0.5.
  - The lab calendar has **261.0 weekdays per calendar year** (no holidays), not 252. The default 3,640 weekdays are 13.95 calendar years, not "~14.4". B0's "2.8 years" are 2.70 calendar years. Each stated annual Sharpe is per 252 weekdays, so it reads 1.8% higher per calendar year. The same applies to the tick generator's `oracle_sharpe`, which uses 252 × ticks per day.
- **Proposed fix:**
  - State the unit at the truth API.
  - Provide the price-unit theory, or the Jensen factor, for constant-notional grades.
  - Name the year convention (252 weekdays) wherever "years" meets the harness's calendar years (C-BT-2 "≥ 2 yr").

### E-R11-06 — C-6's "one financing calendar" is not structural: the lab accrual hard-codes tom_next, while `lab_config` copies any template's convention
- **Severity:** low-medium · **Likelihood:** low-medium. The parameter is public, and a declared template exists that breaks it.
- **Where:** `lab_market.py:222` (`swap_multiplier(d)`, which defaults to `tom_next`); `lab_source.py:104-112` (`lab_config(..., template=...)` copies the template's `swap_convention`, per its own docstring); `book.py:149` (the harness reads `swap_conventions` from the specs).
- **Reproduction** (`probes/misc.py` E):
  - With `template="EUR_USD"`: 0 mismatches.
  - With `template="XAU_USD"`, a declared instrument whose convention is `financing_daily`: the harness charge differs from the lab accrual on **8 of 20** (night, instrument) rows, every Wednesday and Friday. For example, 2012-01-04 (Wed): charge 2.0e-5 against accrual 6.0e-5.
  - A long held over Wednesday but not Friday then books a non-null ±2 nights of rate.
- **Proposed fix:**
  - Give `LabSpec` the convention and use it in `generate`, or make `lab_config` refuse a template whose convention differs from the lab's.
  - Test the identity per convention.

### E-R11-07 — C-BT-12's "every horizon the lab's rules use" is unsatisfiable for any persistent planted effect under its literal reading
- **Severity:** low (spec wording) · **Likelihood:** certain.
- **Where:** ACIS-09 v1.8 C-BT-12, bullet 4 ("daily for TREND; every horizon the lab's rules use").
- **External referent:**
  - The variance of an h-period sum is σ²(h + 2Σ(h−k)ρ_k). This is Lo (2002)'s time-aggregation identity, as reviewed in §6 [5].
  - A persistent predictable component makes predictability horizon-dependent: "an increase in the horizon may increase the R² statistic" (Campbell 2001, §6 [11]).
  - One scale therefore matches one horizon. A trend's longer-horizon variance excess IS the effect.
- **Reproduction** (`probes/vr.py`), planted/null mean-square ratio:
  - lab, trend Sharpe 0.5: 1.000 at 1 day, 1.006 at 5, 1.022 at 16, **1.07–1.08 at 64 and 1.11–1.13 at 126**. EWMAC 16/64 and 126-day momentum use those horizons;
  - tick generator: 0.957 at one tick, 0.971 at one hour, 0.998 at one day.
- **Proposed fix:**
  - Reword to "each graded rule's DECISION (holding) horizon, matched exactly".
  - Declare that planted and null differ at longer horizons by construction.
  - The lab and the tick generator already comply under that reading.

### E-R11-08 — The intraday lab's DST claim is false and its test clause vacuous
- **Severity:** low · **Likelihood:** certain.
- **Where:** `lab_intraday.py:5-7` ("a day lasts 23, 24 or 25 hours"); `test_lab_intraday.py:41` (`lengths <= {1380, 1440, 1500}  # DST days are 23 or 25 hours`).
- **External referent:** NIST: US daylight time "begins at 2:00 a.m. on the second Sunday of March … ends at 2:00 a.m. on the first Sunday of November" (§6 [12]). Both instants fall inside the FX weekend (Friday 17:00 to Sunday 17:00 New York), so every FX day is 24 hours.
- **Reproduction** (`probes/misc.py` A): 3,640 of 3,640 default lab days are 24.0 hours.
  - The real DST effect on an intraday tape is that the UTC position of the session shape moves, including the weeks when US and EU DST disagree. It is not modelled: `HOUR_VAR` and `HOUR_SPREAD` are fixed in UTC.
- **Proposed fix:**
  - Correct the mental model and the test comment.
  - If DST coverage is wanted from the lab, key the hour profile to local session times through `fx_clock`.

### E-R11-09 (inherited harness convention, outside the R1.1 diff) — the rollover calendar contradicts the venues on gold, USD/CAD and holidays
- **Severity:** low · **Likelihood:** medium, once either instrument is enabled. Both are `enabled: false` today.
- **Where:**
  - `tests/backtest/carry.py:11-14, 26`: `financing_daily` = Friday ×3 "per OANDA's published CFD financing convention", declared for XAU_USD;
  - `config/instruments.yaml`: USD_CAD is `tom_next`, i.e. Wednesday ×3;
  - `swap_multiplier` has no holiday rule.
- **External referent:**
  - OANDA (§6 [8]): "FX, gold, and silver trades typically settle on a T+2 basis, which effectively means that weekend financing is usually applied two days earlier on Wednesdays … Indices typically factor in weekend financing on a Friday … this timeline is similarly impacted by public holidays."
  - Dukascopy (§6 [10]): "Some instruments have different value dates, notably USD/CAD, USD/TRY or USD/RUB with T+1 … As a result of holidays, multiple swaps or no swaps at all may be applied."
  - Equiti (§6 [9]): for T+1 pairs such as USDCAD, the tripled adjustment "occurs … on a Thursday".
  - So XAU_USD's Friday triple contradicts OANDA's current page; that Friday triple is encoded by `test_gold_financing_bills_the_weekend_on_friday`. USD_CAD's triple is Thursday, not Wednesday.
- **Relevance to R1.1:** the lab inherits these functions. It uses EUR_USD and has no holidays, so it can never exercise the holiday class.
- **Proposed fix:**
  - Verify against the actual venue: the OANDA v20 financing fields, or the prop platform's swap table. GAP-P12D-123 E17, the "swap charge calendar in C8", is the natural owner.
  - Add a `spot_t1` convention (Thursday ×3) and a holiday multiplier.

## 3. Honest negatives (checked, no defect)

- **Brownian-bridge exactness.**
  - `bridge` is the Gaussian conditional X | 1'X = s ~ N(w·s, diag(w)v − ww'v) (Wikipedia, multivariate normal, §6 [7]).
  - Forward against bridged covariance of (three partial sums, the endpoint) over 400,000 simulated days on real session weights: max deviation 0.00044·v against an MC se of 0.0022 (`probes/bridge_exact.py`).
  - Ticks sum to the day's spot return (test green).
- **GARCH on the scaled y keeps the variance match in PRICE units:** planted/null mean-square of r is 0.9999 ± 0.0002 at trend Sharpe 0.5, and 1.0035 ± 0.0017 at 3.0 (`misc.py` C).
- **The closed forms that are Gaussian by construction are exact in volatility units:**
  - the oracle measures 0.504 against 0.5;
  - carry (m = κz, z Gaussian) and season are algebraically exact;
  - EWMAC of y has E|X|/sd 0.808 against √(2/π) 0.798.
- **Cont (2001) quotes in R1-C §2.5 and `test_lab_stylized.py` are verbatim-correct:** facts 1, 2, 3 (with the exchange-rate footnote 2), 4, 6, 7 and 8, checked against the PDF's text.
- **Baillie & Bollerslev (1989):** the abstract supports the anchor as used, "a generalized autoregressive conditional heteroscedasticity model with daily dummy variables and conditionally t-distributed errors", and the Monday gap is the lab's analogue of the day dummies. The parameter values are not verified (§4).
- **OANDA /365 and the Wednesday triple for FX are confirmed** (§6 [8]: "Daily financing charge or credit = size of position x applicable funding rate/365"). The lab accrual equals the harness charge on the EUR_USD template (0 mismatches).
- **The entry-price financing value (a declared choice):**
  - OANDA prices FX financing on the position's units, and indices on "price at the end of trading day (5pm ET)". The entry price differs from that by rate × H/365 × ΔP/P, which is second order: ~5e-6 on the null over a 60-day hold at a 2% differential.
  - The "holds ≤ 48 h" justification in `carry.py` will not hold for R-1's daily families, but the error stays second order.
- **Compounded simple returns with a −σ²/2 log drift** is correct arithmetic and gives no price-unit bias. A long-biased rule earns nothing in price units (tests green).
- **The oracle reads TODAY's drift:**
  - `truth` returns m[t] from day t's open (the rollover instant) until its close. The quote at the open already contains inc[0]; the next day's state is never read.
  - This is an oracle of the latent state, not look-ahead. The daily-lab oracle holds sign(m_t) over the whole day, which a tick oracle can match only from the open tick (w[0] of the day is missed, negligibly).
- **Carr & López de Prado (2014) is cited faithfully:** "Calibrating a trading rule using a historical simulation (also called backtest) contributes to backtest overfitting".
  - Their STEP 1 fits the O-U parameters by OLS "using the entire historical sample" (§6 [3]): a look.
  - R1-C's "the safer half" framing is accurate, and C-10 correctly excludes their fitting step.
- **Variance-matching a positive control at its DECISION horizon is a sound device:**
  - it removes the volatility-level confound (GAP-P12D-90) and leaves the effect's horizon structure, which is the signal;
  - "model, not sample" is the right choice, since a sample match feeds sampling noise into the scale, as the lead measured.
  - The only defect is the spec's wording (E-R11-07).
- **The null false-detect rate is ≤ α + 2 se everywhere I ran it:** 5.5% (400 seeds), 6.0% (1,000; the limit is 6.38%), 5.05% (4,000), 4.0–4.4% at 13.3 years, 3.6–4.0% at ρ = 0.6. The plain t is if anything conservative for this trend rule.
- **The declared R1.4 path works at these settings:** a Newey–West (Bartlett) t-detector through `calibrate` holds B0 at lag 6/20 with 400 seeds, lag 6 with 1,000 seeds and lag 9 over 13.3 years with 400 seeds (`probes/b0_hac.py`). E-R11-01 still applies to its theory side.
- **The r ≤ −1 refusal is reachable only in principle:** the worst daily simple return over 200 default paths × 20 × 3,640 is −0.34, and the median path minimum is −0.12.
- **The lead's claims reproduced:**
  - B0: 151/400 and 22/400 against theory 0.398; demeaned 73/400;
  - β 0.389 (seeds 1–4) and Hill 3.571;
  - the 54 tests in `test_lab_*.py` and `test_synthetic_market.py` pass on the server (61.6 s).

## 4. What I could not verify

- **Baillie & Bollerslev's (1989) parameter estimates** (GARCH α, β and ν per currency). Only the abstract was reachable, and ResearchGate returned 403. So whether (a, b) = (0.04, 0.90) and ν = 8 are within their FX estimates is unverified. The knobs are declared lab tuning, not a B&B fit.
- **A prop venue's actual swap calendar** (FTMO, E8). Only broker glossaries were reachable, and they report "Forex & Metals: Wednesday; Indices & Oils: Friday" in general. The spec's own E17 item (GAP-P12D-123) owns this.
- **The mechanism of the t-dispersion below 1** (E-R11-01). It is measured, and not explained by serial correlation. Lo's GMM non-iid variance, with the long-run covariance of the mean and variance moments, is the natural candidate, but I did not derive it.
- **Whether Cont's β range, compiled largely from equity and high-frequency studies (his refs [21, 22, 74]), is the right target for daily G10 FX.** It is taken as the stated referent.
- **Outside my lens's weighting and left to the internal audit:**
  - the full suite count (1050 passed, 6 skipped);
  - the `RUNGS` / `COARSE_RUNGS` sweeps;
  - the 5.0 → `SHARPE_MIN` and two → six folds changes;
  - the re-statement numbers (GAP-P12D-124/49/31/28);
  - the hygiene law (surface 6);
  - `model_copy`'s skipped validation in `lab_config`;
  - ledger closure.

## 5. Residual risk

- **The closed forms will keep being read as exact.** Every lab user who grades a price-unit rule against a volatility-unit theory inherits E-R11-01 and E-R11-05's few-percent errors. Those errors are the size of B0's resolution.
- **A lab that matches Cont's facts only through estimator choices** (one k, four seeds) certifies detector size in a world with lighter extreme tails than FX. Detectors that pass B0 there may be liberal on real data.
- **The venue conventions (E-R11-09) are dated facts.** OANDA's page says "typically" and "impacted by public holidays". They need the same annual re-verification as the holiday list.
- **Honest caveat on E-R11-01:** at the pinned default (2.8 years, 400 seeds) B0 holds. The 1,000-seed refusal at 2.8 years was partly chance: 4,000 seeds put the realised power at 38.6% ± 0.8, a structural −1.3 pp. The refusals at 13.3 years, at ρ = 0 and at ρ = 0.6 / N = 40 are structural (2.6–5.8 se at 3,000 seeds).

## 6. Sources (all accessed 2026-09-29)

| # | Source | Used for |
|---|---|---|
| 1 | Cont, R. (2001), "Empirical properties of asset returns: stylized facts and statistical issues", *Quantitative Finance* 1:223–236. http://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf (fetched by curl; the https host fails its certificate) | facts 1–11, the tail index §4.1–4.2, β eq. (17), Mikosch–Starica §5.3 |
| 2 | Baillie, R.T. & Bollerslev, T. (1989), *JBES* 7(3):297–305, abstract. https://ideas.repec.org/a/bes/jnlbes/v7y1989i3p297-305.html | the t-GARCH plus day-dummies anchor |
| 3 | Carr, P. & López de Prado, M. (2014), "Determining Optimal Trading Rules without Backtesting". https://arxiv.org/abs/1408.1159 (abstract and PDF) | the precedent and its STEP 1 fit |
| 4 | Lo, A.W. (2002), "The Statistics of Sharpe Ratios", *FAJ* 58(4):36–52, abstract. https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios | the distributions under iid, stationary and aggregated returns |
| 5 | Riondato, M. (2018), "Sharpe Ratio: Estimation, Confidence Intervals, and Hypothesis Testing", Two Sigma TR 2018-001. https://www.twosigma.com/wp-content/uploads/sharpe-tr-1.pdf | √n(ζ̂ − ζ) → N(0, 1 + ζ²/2) under iid normal; Mertens: "up to 70% off"; Lo's GMM approach; the aggregation identity |
| 6 | SAS *The DO Loop*, "Compute multivariate normal orthant probabilities" (citing Genz & Bretz 2009 and Sheppard 1898). https://blogs.sas.com/content/iml/?p=58590 | Sheppard's formula, stated for the bivariate normal |
| 7 | Wikipedia, "Multivariate normal distribution", conditional distributions. https://en.wikipedia.org/wiki/Multivariate_normal_distribution | the conditional mean and covariance (bridge; sign identity) |
| 8 | OANDA, "Financing Costs" (Canada) https://www.oanda.com/ca-en/trading/financing-costs/ and Help "financing costs" (UK/BVI) https://help.oanda.com/uk/en/faqs/financing-costs-uk.htm | /365; T+2 FX, gold and silver → Wednesday; indices → Friday; holidays; 5 pm ET booking |
| 9 | Equiti, "Financing Fees". https://www.equiti.com/sc-en/financing-fees/ | USDCAD T+1 → Thursday triple; /360 for index CFDs |
| 10 | Dukascopy Wiki, "Rollovers". https://www.dukascopy.com/wiki/en/forex-cfds/account-management/rollovers/ | T+1 pairs; value-date mechanics; holidays |
| 11 | Campbell, J.Y. (2001), "Why long horizons? A study of power against persistent alternatives", *J. Empirical Finance* 8(5):459–491, abstract. https://ideas.repec.org/a/eee/empfin/v8y2001i5p459-491.html | persistent components make predictability horizon-dependent |
| 12 | NIST, "Daylight Saving Time Rules". https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst | the US switch at 2:00 a.m. Sunday |

**Probe index** (scratchpad `audit/external/probes/`, runnable on the server as `python probes/<file> …`): `b0_calibrate.py`, `b0_horizon.py`, `units.py`, `b0_hac.py`, `beta_seeds.py`, `hill.py`, `kesten.py`, `intraday_carry.py`, `misc.py` (A: DST, B: the sign constant, C: GARCH match, D: year convention, E: template convention, F: price-unit oracle), `vr.py`, `bridge_exact.py`.
