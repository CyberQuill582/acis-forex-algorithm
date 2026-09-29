# AUDIT R1.1 — INTERNAL-CONSISTENCY LENS (2026-09-29)

- **Auditor:** Claude Opus 5.5 (1M context). Fresh context, finder not clearer (A5). No subagents were launched, and no web access was used.
- **Brief:** `AUDIT_BRIEF_R1_1_2026-09-29.md` (pinned).
- **Audited state:** `b5c284a`. Files were read with `git show b5c284a:<path>`.
- **Where things ran:** every run went to the Google compute server (`acis-compute-1`), on this auditor's own checkout of `b5c284a`. The server has numpy 2.4.6 and Python 3.11.2.
- **Probes:** the scripts are in the session scratchpad under `audit/internal/probes/` (`p_*.py`). Each finding below states its own reproduction.
- **Scope of writes:** this file is the only repo write.

## Executive summary

**Findings: 14.**

| Severity | Count |
|---|---|
| Medium-high | 1 |
| Medium | 2 |
| Medium-low | 2 |
| Low-medium | 3 |
| Low | 6 |

**The lead's headline claims reproduce:**
- 1050 passed, 6 skipped. All six skips need real data.
- B0: planted 37.8%, null 5.5%, demeaned 18.2%, theory 0.8284 / 39.81%.
- Stylized facts: β 0.389, Hill 3.57, acf share 0.045.
- `RUNGS`: 0.18 → PF 1.414, 0.19 → PF 1.398.
- Every trade count, P&L, Sharpe and PF in the GAP-P12D-49 and GAP-P12D-31 re-statements matches the JSON reports.
- `ledger_check.py`: green, 260 entries, 0 violations.

**The numbers are right, but three kinds of claim built on them do not hold.**

1. **The re-statement's "~98% direction, friction ~2%" is an artifact** (R11I-01).
   - It comes from a least-squares slope across ladder rungs whose trade sets differ 3× (1,690 → 548 trades).
   - The friction the book actually charges at 1x is about **$21, ~30% of the loss**. That estimate uses the logged order sizes and the declared C8 costs.
   - At TREND's 12.6-minute mean hold, even a PERFECT-direction trader earns at most a third of the round-trip friction on this market.
   - So the claim "no module captures the planted trend" is a friction and holding-period statement, not a direction verdict. It is in the read path (CLAUDE.md, STATUS.md, TODO.md).
2. **Three statistical gates pass only on their committed seeds** (R11I-02, R11I-03, R11I-10):
   - **C-8 Cont β:** the defaults average β ≈ 0.405, and 6 of 10 four-seed blocks fail the gate.
   - **B0:** seeds 401–800 fail on the correct lab.
   - **The oracle positive control:** its PSR is 0.961 on the committed seed, and 2 of 5 other seeds fail.
3. **The B0 theory is wrong by 3.2%, and B0's rule misses its theory by another 4% in the opposite direction** (R11I-04). B0 "holds" because the two errors offset, and B0's ±2 se band is too wide to see either one.

**The latent lab defects fire when R1.2+ wires the lab into the harness:**
- The lab's truth API breaks the oracle positive-control contract on both controls (R11I-05).
- The intraday tape pays a rollover-timed carry rule on the financing-on null (R11I-07).
- The effects' stated Sharpe holds in volatility units only; in price units it is ~10% lower (R11I-08).

## Findings

### R11I-01 — The re-statement's friction/direction split (~2% / ~98%) is unsupported and contradicted. "TREND and BREAKOUT withdrawn" is not a direction verdict.
**Severity: medium-high · Likelihood: certain (it is in the read path).**

**Where the claim lives:**
- `KNOWN_GAPS.md:1360` (GAP-P12D-49): "friction is ~2% of the 1x→2x loss, and the rest is DIRECTION".
- `:1361-1366`: "At a realistic edge, NO module captures the planted trend … 'TREND and BREAKOUT genuinely work' is WITHDRAWN".
- `:158` (GAP-P12D-124 item 2): "~98% direction".
- Repeated in `CLAUDE.md:17`, `STATUS.md:11,27` and `TODO.md:40`.

**Mechanism:**
- `scripts/cost_stress_ladder.py:41-59` estimates friction as minus the LS slope of net P&L over the rungs. Its own docstring states the premise: "linear in the stress multiplier for a FIXED trade set".
- In `ladder.json` the rungs trade **1,690 / 1,568 / 665 / 548** times. The 3x rung nets −21.18, the 1x rung −70.84.
- So the slope (friction_per_1x = 1.21) measures a change in trade selection, not friction.
- `:82-84` then prints "the rest is direction" with no check on trade-count dispersion.
- The exact friction is computed per trade at `tests/backtest/book.py:160` and discarded. `ClosedTrade` (`metrics.py:23-29`) has no friction field.

**Reproduction (`p_friction.py`; the 200 logged `SIZED` events of `run_planted.jsonl` from `gs://…/runs/20260929/…/falsification/…/logs/`):**
- Order sizes: EUR_USD 18.7–353 units (median 124); USD_JPY 65.7–366 units (median 159).
- Round-trip C8 cost from `cost_model(cfg, inst)` at spread = mid·4e-5: 8.4e-5 USD per EUR_USD unit and 7.64e-5 USD per USD_JPY unit.
- **At 1x:** estimated friction **$20.95** on 1,690 trades, **30% of −70.84**. At the smallest logged order it would still be $2.66, above the regression's 1.21. The regression implies a mean notional of **$8.9**, below every logged order.
- **Per strategy:**

  | Strategy | Net | Estimated friction | Share of the loss | Gross |
  |---|---|---|---|---|
  | TREND | −10.44 | 8.86 | 85% | ≈ −1.6 |
  | BREAKOUT | −2.65 | 6.09 | 230% | ≈ +3.4 |
  | MEAN_REVERSION | −0.31 | 0.47 | 152% | ≈ +0.2 |
  | TSMOM | −57.44 | 5.53 | 10% | — |

- **The ceiling on any edge at that hold:** on this market the planted edge per 20 s step is 7.13e-7 of price (scale 0.980 × drift_sigma 0.00958 × σ_tick). Over TREND's 725.7–755 s mean hold, a trader who is always right earns at most **2.6e-5**. The round-trip friction is **7.6e-5**.
- Even the two nearly comparable rungs (1x→2x, 1,690 → 1,568 trades) imply $5.63 per 1x, 4.7× the regression figure.

**What survives:**
- The engine loses at every rung.
- TSMOM's loss is mostly direction (~90%).

**What does not survive:**
- "~98% direction".
- "no module captures the planted trend" as a statement about TREND, BREAKOUT or MR.

**Proposed fix:**
1. Carry `friction` (and `carry`) on `ClosedTrade`, and have the ladder report Σ friction at 1x exactly.
2. Make `decompose` refuse to print a share when rung trade counts differ by more than a declared tolerance.
3. Correct GAP-P12D-49/124 and the read-path copies.
4. Attribute TREND/BREAKOUT only against a same-hold perfect-sign benchmark (the maximum-edge bound above). On this market no hold under ~36 min can profit even when always right.

### R11I-02 — The C-8 Cont β gate is a seed artifact: at default knobs the lab fails it in expectation
**Severity: medium · Likelihood: high.**

**Evidence:**
- `test_lab_stylized.py:110` asserts 0.2 ≤ β ≤ 0.4 on seeds 1–4 (`:51`), which give 0.389.
- Reproduction (`p_stylized.py`, the fixture's own code on ten 4-seed blocks):

  | Seeds | β | Result |
  |---|---|---|
  | 1–4 | 0.389 | passes |
  | 5–8 | 0.409 | **fails** |
  | 9–12 | 0.393 | passes |
  | 13–16 | 0.416 | **fails** |
  | 17–20 | 0.402 | **fails** |
  | 21–24 | 0.447 | **fails** |
  | 25–28 | 0.392 | passes |
  | 29–32 | 0.406 | **fails** |
  | 33–36 | 0.415 | **fails** |
  | 37–40 | 0.383 | passes |

- Mean β over 40 seeds ≈ 0.405. 19 of 40 single seeds exceed 0.4. Every other fact passes every block.

**Why it matters:**
- The gate is "the lab's own gate: at default knobs the null lab shows Cont's facts" (`test_lab_stylized.py:1-2`). It holds by draw, not by construction.
- Any benign change to the draw order will turn it red about 60% of the time.
- CI installs **unpinned** numpy (`.github/workflows/ci.yml:51`, `pyproject.toml:14`), and every committed lab number depends on the exact Generator stream.

**Proposed fix:**
- Re-tune the declared knobs (e.g. `sv_halflives` / `sv_sd`), so that β's expectation sits inside [0.2, 0.4] with margin. Assert on ≥ 20 seeds.
- Or declare a lab tolerance explicitly, as the other facts do.
- Pin numpy in both files.

### R11I-03 — B0 passes on seeds 1–400 but fails on the same correct lab at seeds 401–800; it has ≥5% false-fail and ~±12% Sharpe blindness
**Severity: medium · Likelihood: high.**

**Evidence:**
- `test_lab_calibration.py:39` fixes `range(1, 401)`.
- Reproduction (`p_b0_seeds.py`, 4,000 seeds in 400-seed blocks, the test's own `SPEC` / `_planted` / `calibrate`):
  - seeds 1–400: 0.378 (holds);
  - **seeds 401–800: 0.345, which B0 refuses** ("not within 2 se (0.024) of 0.398");
  - the other blocks range 0.365–0.443.
- Pooled over 4,000 seeds, the true planted power is **0.3855 ± 0.0077** against a theory of 0.3981. The null rate is 0.0505.

**Why it matters:**
- Criterion (a) (`lab_calibration.py:79-83`) is a two-sided 95% binomial test, so a correct lab fails it ≥ 4.6% of the time. The rule/theory mismatch in R11I-04 makes that higher.
- The spec requires B0 to hold "at the same `recon_commit`" before any real-data verdict (ACIS-09 C-BT-11 v2 step 0). Spurious blocks will occur, and a re-seed to clear one is a garden of forking paths.
- **Resolution:** at 400 paths the ±2 se band (±4.9 pp) is about ±12% of the pooled Sharpe. A null bias up to a pooled SR of ~0.11 passes (b): at that bias Φ(0.11·√2.8 − 1.645) ≈ 7.2%.
- "Demeaned is refused" proves power only against a −1.2 SR defect. Everything in R11I-04, R11I-07 and R11I-08 is below B0's resolution, and B0 cannot see intraday defects at all.

**Proposed fix:**
- Declare B0's error rates in the spec: the false-fail per evaluation, and the minimum detectable miscalibration.
- Size n so the band resolves the effects that matter, e.g. 2,000+ paths on the server.
- Fix the seed block by registration, not by convention.

### R11I-04 — `pooled_ewmac_sharpe` mis-states the lab's cross-covariance, and B0 grades a different rule than the theory describes; the two errors offset
**Severity: medium-low · Likelihood: certain.**

**Evidence:**
- `lab_theory.py:103-104` takes Cov(noise_i, noise_j) = ρ.
- The lab's diffusive part is `diff_scale·(b·fac + √(1−b²)·idio)` (`lab_market.py:166,179`), so |Cov| = diff_scale²·ρ = 0.929ρ.
- Jumps and Monday gaps are independent across instruments (`:170-171,180`).
- Measured mean |corr(noise_i, noise_j)|: **0.265**, against the formula's premise ρ/other = 0.286.

**Reproduction (`p_pooled.py`, 800 paths × 13.25 graded years):**
- The closed form as coded gives **0.8284**. With the lab's actual covariance it gives **0.8555**.
- Monte Carlo of the closed form's own premise (y-based, equal-weight sign(EWMAC) pool) gives **0.8569 ± 0.0096**. That rejects the coded value at ~3 se.
- B0's actual rule (`lab_calibration.py:42-58`: EWMAC on `path.r` with EWMA vol scaling) realises **0.8212 ± 0.0100**, 4% below the correct theory.
- So B0 "holds" against 0.828 because the theory is 3.2% low and the rule is 4% low.
- `test_lab_calibration.py:38` pins `theory ≈ 0.828 ± 0.03`, which admits the correct value too.

**Proposed fix:**
- Use c = diff_scale²·ρ against the daily noise variance `other` (or Monte-Carlo the pool's theory).
- Grade B0's rule against its own theory, or run B0 on the rule the closed form describes.
- Tighten the pin.

### R11I-05 — The lab's `truth` API breaks the oracle positive-control contract on BOTH controls
**Severity: medium-low · Likelihood: high once wired (latent today).**

**The contract (tick generator):**
- Null and permuted carry planted's schedule *unapplied* (`synthetic_market.py:27-30`).
- The oracle takes the same trades on every kind, and a control may be refused only by a §14 row, never by a sample floor (`oracle.py:127-156`, `void_reasons`).
- R1-C §4 says `truth` "generalises `episode_sign`" and keeps the KINDS contract.

**What the lab does:**
- **Null:** `m ≡ 0`, so `truth` = 0.0 (`lab_source.py:87-92`, asserted by `test_lab_source.py:72`). The oracle holds **0 positions**, and the null would be "refused" by the 30-trade floor, which `void_reasons` VOIDs.
- **Permuted:** `permuted()` signs `m` with the same order and flip as `y` (`lab_market.py:242`). `truth` therefore hands the oracle each permuted day's own drift.

**Reproduction (`p_lab_truth.py`):**
- The oracle at each day's open earns SR **0.996 on planted** and **1.029 on permuted** (34,000 positions each), against **0 positions on null**.
- For contrast, planted's schedule on the permuted path gives 0.12.

**Proposed fix:**
- Give every kind planted's `m` as its truth: generate the effect draws and keep them unapplied on null and permuted, as the tick generator does.
- Add the tick generator's "same trades on every kind" test to `test_lab_source.py`.

### R11I-06 — The tick generator matches variance at a horizon the graded rules do not decide on, and the permuted control is unmatched; GAP-P12D-117's "Residual: none" hides it
**Severity: low-medium · Likelihood: certain.**

**The spec (C-BT-12):** "variance-matched to its null at the graded rule's DECISION horizon (… every horizon the lab's rules use) … by construction".

**The code:**
- It matches at `match_seconds` = one weekday, "as TREND decides" (`synthetic_market.py:23-24,61`).
- But the rules this generator grades are the engine's (`scripts/falsify_engine.py:67`, `cost_stress_ladder.py:127`, default `match_seconds`).
- AGON's TREND, BREAKOUT, MR and SCALP decide on 60 s signal bars: `core/signals/agon.py:359-368` reads `self._bars`, and `config/system_config.yaml:38` sets `signal_bar_seconds: 60`. Only TSMOM decides daily.

**Reproduction (`p_tick_variance.py`, the falsification tape, model-exact):**
- **planted/null:** 0.961 at 20 s; 0.962 at 5 min; 0.974 at 1 h; 1.000 at 1 day.
- **permuted/null:** 0.961 at **every** horizon.
- **planted/permuted at the daily horizon:** **1.041** (EUR_USD) and **1.043** (USD_JPY).
- No test pins permuted's variance. `test_synthetic_market.py:93-101` compares only planted against null.

These magnitudes are small (the old market was 12.3× at daily), but the requirement is unmet at the graded rules' horizon, and the ledger records it as closed.

**Proposed fix:**
- Either match at the engine's decision horizon, or declare the deviation in C-BT-12 and in GAP-P12D-117 with the measured ratios.
- Pin permuted's ratio as well.

### R11I-07 — The financing-on lab null pays a rollover-timed carry rule
**Severity: low-medium · Likelihood: certain once lab tapes feed the harness.**

**Mechanism:**
- `lab_intraday.py:89` spreads each day's accrual across the day's ticks in proportion to session variance (`w·accrual[t]`).
- The harness books the whole night's financing at the 17:00-NY rollover instant (`book.carry_quote`: `financing_charge` over `business_rollovers(entry, exit)`).
- C-6 ("the null is null in the P&L the grader books", `lab_source.py:12-15`) therefore holds only for holds aligned to the FX-day grid.

**Reproduction (`p_rollover.py`, null, 20 instruments × 1,498 rollovers, broker fee 0):**
- Hold sign(rate) from 16:00 to 18:00 NY: **booked +6.7e-5 per unit, t = 5.9**. On Wednesdays: **+1.52e-4, t = 8.9**.
- The same rule open-to-close of the FX day: t = −0.6.
- On average the leak sits below the lab's own spread plus slippage (~1.7e-4 plus 4e-5). A rule that conditions on a large |rate| can clear it.

**Proposed fix:** book −accrual[t] as a price step at the rollover tick (like the Monday gap), not spread by `w`. Then add the straddle test above.

### R11I-08 — The effects deliver their stated Sharpe in volatility units only; in the price units the harness books, a fixed-notional position earns ~10% less
**Severity: low-medium · Likelihood: high once `truth` / `detection_power` state the power of harness grades.**

**Where it comes from:**
- The closed forms are stated in y units (`lab_theory.py:7`).
- `lab_source.py:9-11` says `detection_power` "states the power a grade has at its length".
- Harness grades are in price units, and `OracleLoop` sizes a fixed NAV notional.

**Reproduction (`p_units.py`, 20 seeds × 20 instruments × 3,640 days):**

| Effect | Target | Realised in y units | Realised at unit notional |
|---|---|---|---|
| trend | 0.5 | 0.504 | **0.454** |
| carry | 0.5 | 0.493 | **0.439** |
| season | 0.5 | 0.499 | **0.447** |
| trend | 2.0 | 2.004 | **1.809** |

(GARCH keeps the variance match: E[r²] planted/null = 1.0001; see the honest negatives.)

**Proposed fix:** state the theory in the units being graded. Either scale by E[σ]/√E[σ²] measured on the null, or require vol-targeted sizing wherever the lab's power statement is used.

### R11I-09 — The oracle's Sharpe equals `oracle_sharpe` only when episodes are long in ticks; the "any tick size" test is tautological
**Severity: low · Likelihood: certain.**

**The claims:**
- `synthetic_market.py:22` and GAP-P12D-90 (`KNOWN_GAPS.md:501`): "the oracle's Sharpe is the same at any tick size".
- The built oracle holds the episode in force (`oracle_loop.py:143-147` → `episode_at`, no foresight). Its expected Sharpe is `oracle_sharpe·(1−2p)`, where p is the per-step sign-change share.

**Reproduction (`p_tick_oracle.py`):**

| Tick | Expected | Sampled |
|---|---|---|
| 20 s | 9.98 | — |
| **300 s (the coarse full-scale tape)** | **9.66** | 9.74 |
| 3,600 s | **5.97** | — |
| ≥ 14,400 s | **≈ 0** | — |

- At ≥ 14,400 s the episodes are one step long, so planted is indistinguishable from null for the oracle, and **no error is raised**.
- `episode_hours` is never validated against `tick_seconds`.
- `test_synthetic_market.py:104-107` asserts only the defining identity `drift_sigma·√(252·tpd) = 10` (A16: hollow).

**Proposed fix:**
- Refuse specs whose minimum episode is under ~10 ticks, or define `drift_sigma` from the no-foresight oracle.
- Replace the test with a realised-Sharpe check at 20 s and 300 s.

### R11I-10 — The positive-control test: the moved Sharpe bar is non-binding, and the binding PSR assertion passes only on the committed seed
**Severity: low · Likelihood: high.**

**Evidence:**
- `test_oracle_control.py:256,267-268` (six folds; `annual_sharpe > SHARPE_MIN` = 1.5; `deflated_sharpe ≥ 0.95`).
- Reproduction (`p_oracle_control.py`, the test's own grading at seeds 7–11):
  - The committed seed 7 gives Sharpe 3.38 and **PSR 0.961**.
  - Seeds 8 and 10 give PSR **0.927** and **0.896**, so **the test fails**. Seeds 9 and 11 pass.
- The Sharpe bar never binds.
- The docstring's own rationale for moving from 2 to 6 folds ("not reliably significant") still holds at 6 folds.

**Proposed fix:**
- Size the folds so the planted PSR clears 0.95 with margin across seeds (e.g. 12+ folds, or two instruments).
- Or assert on a seed-averaged statistic.
- Keep a Sharpe bar that would catch a halved oracle.

### R11I-11 — The lab's "return ≤ −1 is refused" guard checks the wrong quantity and is untested
**Severity: low · Likelihood: low (unreachable at defaults).**

**Mechanism:**
- `lab_market.py:218-219` checks `r`.
- But prices compound `spot = r − accrual` (`:223,226`; `mids` at `:127`).
- Intraday mids are additive within a day (`lab_source.py:75`).
- `rate_sd` and `ann_vol` are unvalidated.

**Reproduction (`p_misc.py`):**
- `rate_sd=150` gives 10 mids ≤ 0 with no refusal.
- `ann_vol=(1.6,1.6)`, seed 25, day 68: an intraday mid of −0.059 on a day whose spot is −0.64.
- At defaults the minimum r over 50 seeds × 20 × 3,640 days is −0.266.

No test exercises the lab refusal, although GAP-P12D-117's Residual cites the law.

**Proposed fix:** check `spot` and the intraday running level; bound the knobs; add the test.

### R11I-12 — The hygiene law is a pattern lint, not structural
**Severity: low · Likelihood: low.**

`test_lab_hygiene.py:123-125,153-157` misses all four constructs in `p_misc.py` (d):
1. an allowed import that reads real data (`tests.backtest.financing.load_rate_table`; `lab_source.py:32` already imports that module);
2. `importlib.import_module('tests.backtest.' + 'sources')`;
3. a friction constant as a default argument;
4. a friction constant under another name (`SPREAD_COST`, `MARKUP`).

**Proposed fix:** use an allowlist of importable modules (not a denylist), forbid `importlib` / `__import__`, and apply the friction scan to defaults, attributes and every numeric constant.

### R11I-13 — The tick tape's daily close is not the lab's daily close
**Severity: low · Likelihood: certain (latent for B0 (d)).**

- `lab_source.py:7-8` says "the tick tape and the daily bars are one path".
- But only tick 0 is forced to emit (`lab_intraday.py:93-94`).
- Reproduction (`p_close.py`): the last emitted tick equals the close on **44 of 199** days. The median gap is 5.5e-5 and the maximum 1.2e-3 (a late jump).
- B0 (d), "the research simulator ≡ the engine on lab tapes", will diverge by this much.

**Proposed fix:** force-emit the last grid tick, or state the tolerance (d) must allow.

### R11I-14 — Read-path and ledger hygiene (A13/A15)
**Severity: low · Likelihood: certain.**

1. **Stale Justification lines.** The R1.1 entries say `Status: fixed` while the Justification still reads open or mitigated:
   - GAP-P12D-90 `:499`, GAP-P12D-91 `:489`, GAP-P12D-92 `:479` and GAP-P12D-117 `:232` ("mitigated");
   - GAP-P12D-124 `:162` ("open … stays marked 'made on the old market' until (2) lands", but (2) landed). `:161` is also stale: "once the owner has signed Google Cloud in".
   - `ledger_check.py` does not see this.
2. **Old and new claims side by side.**
   - `CLAUDE.md:17` and `STATUS.md:27` still carry the unqualified "TREND (+13.14, PF 2.04) and BREAKOUT (+1.66) do capture the planted edge" and "~89%", next to the new "NO LONGER capture" and "~98%".
   - In `TODO.md`:
     - `:3` still says "1002 passed … ledger 238";
     - `:13` says GAP-P12D-117 "mitigated" (the ledger says fixed);
     - `:14` says the gate is RED while `:20` says it is green;
     - `:193` still says "~89%".
3. **Phase completion with the gate red.** R1.1 is declared COMPLETE while the phase gate `governance_gate.py` is self-reported RED (`TODO.md:14`, the v0.10 pin). CLAUDE.md line 3 makes that gate the phase-completion check. The red is owned only in TODO (`:746-755`), with no ledger ID.

**Proposed fix:** correct the lines above, and mark superseded clauses in the status lines. Either green the gate before declaring R1.1 complete, or ledger the exception.

## Honest negatives (checked, found sound)

**The suite and the ledger:**
- Full suite at `b5c284a`: **1050 passed, 6 skipped** in 68 s at `-n 8`. The skips are real-data only (`test_financing.py:55`, `test_sources.py:172,187`).
- `ledger_check.py`: 260 entries, 0 violations.

**The tick generator:**
- `match_scale` is exact in the model given the schedule. The identity is pinned.
- Daily blocks aligned to 17:00 NY instead of 00:00 UTC stay within 0.15% (0.9985–0.99998).
- The draw order holds: null and planted share the noise; permuted is planted's increments shuffled, then sign-flipped.
- The sign flip acts on simple returns, so it acts on arithmetic increments. Both nulls are price-unit martingales.

**Re-statement numbers:**
- `RUNGS`: 1.4142 / 1.3979 in `oracle_planted-near-*.json`. Near-pass meets every clause; near-fail fails PF alone.
- Oracle PF 1.853 / Sharpe 9.02; near-pass Sharpe 5.64.
- The ladder: 1x −70.84 / Sharpe −1.92 / PF 0.669 / 1,690 trades; 2x −76.48, 3x −21.18, 5x −82.95.
- Per-strategy net values; TSMOM 55.2 h; engine null −1.19, permuted −0.45.
- All match the reports. The only exception is the friction phrase (R11I-01).

**The lab's closed forms, model and financing:**
- The closed forms for the oracle, EWMAC, carry and season are right in volatility units. The EWMAC weight identity and the O(n) double-sum recursion check out.
- GARCH on scaled y keeps the variance match: E[r²] planted/null is 1.0001 at SR 0.5 and 1.0010 at SR 2.0. The permuted lab is a martingale.
- Per-night financing equals the lab's accrual: Wednesday ×3, /365, rate dated to the rollover night, sign convention for long and short.
- The entry-price approximation is second-order (about rate × price move, ~1e-6 a night) under the 48 h hold cap.
- The oracle reading today's drift is consistent with the tick generator at tick level: the day's open tick already carries day t's first increment.

**Bridges and the source:**
- The bridge conditioning is exact: the residual is independent of the sum.
- DST days run 23, 24 or 25 h, UTC hours are correct, and there are no weekend ticks.
- `load` is window- and split-invariant. The 4-day FIFO cache is safe because `intraday` is deterministic.
- `lab_config` re-validates through `AcisConfig.model_validate`.

**B0:**
- Its se conventions are the correct binomial ones for H0.
- The null is calibrated: 5.05% over 4,000 seeds.
- `ewmac_pool` has no look-ahead after burn-in (the initial variance from r[:60] decays to e⁻¹⁶ by day 300).

**Code size (A12):** every R1.1 module is ≤ 252 lines and opens with a mental-model block.

**GAP-P12D-28's closure is adequate for the grader:** stage 1 passes at full scale, and null and permuted are refused by §14 rows. The unproven labeller → evolution → engine chain is owned by GAP-P12D-31, whose Area names it.

## What I could not verify

- **`governance_gate.py` at `b5c284a`.** The server has no `node`, and the laptop tree is not `b5c284a`.
- **The exact 1x friction** (R11I-01 is an estimate from the 200 logged orders). The book discards per-trade friction, and the reports carry no trades.
- **The intermediate RUNGS sweep values** (0.14–0.17, 0.20–0.22). Only the two committed rungs' reports exist.
- **The engine stage-2 runs themselves.** They were read from the reports, not re-run (over 1 h each).
- **Whether numpy's Generator streams are stable across releases.** That is an external question.

## Residual risk

- **Seed-dependent gates:** C-8 β, B0 and the oracle PSR will flip red on benign draw-order or numpy changes. When they do, the tempting fix is a re-seed, and a re-seed is itself a forking path.
- **B0 resolves only large lab defects:** roughly ±12% Sharpe, or a null bias above ~0.1 pooled SR.
- **Latent lab defects:** R11I-05, R11I-07, R11I-08 and R11I-13 will surface at R1.2–R1.6, when the lab feeds the harness, the oracle and RSIM.
- **The weak planted edge:** at `oracle_sharpe` = 10, the tick-level positive control cannot reward any hold under ~36 min. Every engine verdict on it is bounded by friction for the engine's actual holding periods, whatever the direction skill.
