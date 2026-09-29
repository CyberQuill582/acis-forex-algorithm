# AUDIT BRIEF — R1.1, the synthetic lab (pinned 2026-09-29)

> **Pinned before launch (constitution A4).** The owner's go, in chat on 2026-09-29, answering the
> session's standalone ask: "Launch both audits now (Recommended)". This is the constitution's pair
> (A3), one agent per lens, on Opus 5 in fresh context.
>
> **What is under audit:** commits `369242a..b5c284a` on `main` (R1.1). Audit commit **`b5c284a`**; `git show b5c284a`, `git log 63034ef..b5c284a`, `git diff 63034ef b5c284a`.
> - **The tick generator under ACIS-09 C-BT-12** (GAP-P12D-90/91/117):
>   - `tests/backtest/synthetic_market.py`, `test_synthetic_market.py`;
>   - the recalibrated oracle ladder: `oracle.py` `RUNGS`, `test_oracle_full_scale.py` `COARSE_RUNGS`;
>   - `test_oracle_control.py`: the drift identity, six folds instead of two, and the Sharpe bar moved from 5.0 to `SHARPE_MIN`.
> - **The daily-first lab** (C-3..C-8, C-10): `tests/backtest/lab_theory.py`, `lab_market.py`, `lab_intraday.py` (C-4, GAP-P12D-92), `lab_source.py` (C-5/C-6/C-7), and their tests `test_lab_market.py`, `test_lab_stylized.py` (C-8), `test_lab_intraday.py`, `test_lab_source.py`, `test_lab_hygiene.py` (C-10).
> - **B0 machinery** (GAP-P12D-105): `lab_calibration.py`, `test_lab_calibration.py`.
> - **numpy** added to `pyproject.toml` dev and `.github/workflows/ci.yml`.
> - **The re-statement of every old synthetic verdict** (GAP-P12D-124, and GAP-P12D-49/31/28 as rewritten): ledger text plus the run reports in `data/validation/cost_stress/20260929T114406Z-gce/` and `data/validation/falsification/20260929T114406Z-gce/`.
>
> **The authority.**
> - The spec: `specs/ACIS-09-BACKTEST_VALIDATION.md` v1.8, **C-BT-12** and **C-BT-11 v2 step 0 (B0)**.
> - The design as FINDER evidence, not authority: `CLOUD_AUDIT/reports/r1/PLAN_R1.md` (the R1.1 row), `CLOUD_AUDIT/reports/r1/R1C_SYNTH_LAB.md` and its prototype `CLOUD_AUDIT/reports/r1/evidence/R1C/gen_lab.py`.
> - The ledger: `KNOWN_GAPS.md` entries GAP-P12D-90, 91, 92, 105, 117, 124, 49, 31, 28.
>
> **The lead's claims — re-verify them; they are not settled:**
> - the full suite at `b5c284a` gives 1050 passed, 6 skipped on the server;
> - B0 on 400 paths of 2.8 years: planted 37.8% against a theory power of 39.8%, null 5.5%; demeaned 18.2%;
> - the stylized facts at default knobs: β 0.389, Hill 3.57, acf share 0.045;
> - `RUNGS` 0.18 / 0.19 bracket PF 1.4 (1.414 / 1.398);
> - the re-statement numbers in GAP-P12D-49's 2026-09-29 bullet.
>
> **Declared choices the lead made — attack them:**
> - the tick generator's default `oracle_sharpe = 10`;
> - variance matched in the MODEL, not the sample;
> - the oracle reads TODAY's drift, where R1-C's prototype read yesterday's;
> - prices compound simple returns, so the log-unit drift is −σ²/2;
> - the lab matches variance at the daily horizon only;
> - the financing value is taken at the entry price, the harness's own approximation;
> - B0's se is binomial at the theory rate;
> - B0's detector is the plain t-test, a placeholder until R1.4.

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit or run git commands that write. The lead works on R1.2 in the same tree, so read the audited state with `git show b5c284a:<path>`, or diff against it. Never trust the working tree to equal `b5c284a`.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite, the statistical tests or any probe that generates many paths locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of `b5c284a`: `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/688e2ed6-575e-479f-a856-d4e3a1e59865/scratchpad/remote_audit.sh" <internal|external> "<command>"`.
  - Put probe scripts in `…/scratchpad/audit/<internal|external>/probes/` (they ship on each call) and run them as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - Reading files and quick `grep`s locally are fine.
- **Refutation (A6).** Every finding is reproduced by a script on the server, cites `file:line` at `b5c284a` (internal lens), or quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps against the spec, hollow or weakened tests (A16), A12 size and legibility (a module over 300 lines; a missing one-screen mental model in an invariant-bearing module), A13 hygiene (a read-path claim the code or the ledger contradicts; spent scaffolding), and ledger closure (`python scripts/ledger_check.py` green, plus a spot-check that no `Residual: none` in GAP-P12D-92/117/124/28 hides unowned work). Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_R1_1_INTERNAL_2026-09-29.md`; EXTERNAL writes `archive/AUDIT_R1_1_EXTERNAL_2026-09-29.md`. That file is your ONLY repo write. Its shape: an executive summary; findings (ID, Severity/Likelihood, reproduction, proposed fix); honest negatives; what you could not verify; residual risk. The lead triages it into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **The tick generator** (`synthetic_market.py`).
   - Does the model-exact `match_scale` meet C-BT-12's "variance-matched … at the graded rule's DECISION horizon … by construction … never by a sampled tolerance"?
   - Does the draw order still hold, so null, planted and permuted share their draws as claimed?
   - Is the sign flip applied to arithmetic increments?
   - Does the oracle's Sharpe equal `oracle_sharpe` at any tick size?
   - Construct a spec that breaks an invariant.
2. **The re-calibrated oracle ladder and the control-test changes.**
   - Are `RUNGS` / `COARSE_RUNGS` a bracket that tests power near the cut-off, or did any change WEAKEN a guard? Look at 5.0 → `SHARPE_MIN`, two folds → six, and the per-instrument claim in the old `RUNGS` comment.
3. **The daily lab** (`lab_market.py`, `lab_theory.py`).
   - Is each closed form right: the oracle, EWMAC, the pooled arcsine law, carry, season?
   - Does each effect's realised Sharpe equal its theory? Does GARCH on the scaled y keep the variance match?
   - Is the permuted control exactly a martingale? Is the r ≤ −1 refusal reachable at default knobs?
   - Does the lab's accrual equal what the harness books (`carry.financing_charge` over `business_rollovers`), including Wednesday ×3, /365, entry-price value and holds over several nights?
4. **The intraday bridges and the source** (`lab_intraday.py`, `lab_source.py`).
   - Exactness; DST days; the UTC hour of each tick; `truth` at the day boundary (no foresight).
   - The loader's rejection path; the load window and its cache.
   - `lab_config`: `model_copy` skips validation, so can it produce an AcisConfig that real code would refuse?
   - Is C-7's "no second cost model" really structural?
5. **B0** (`lab_calibration.py`).
   - Are the se conventions right? Are the 400 fixed seeds a real test, or tuned?
   - Does "demeaned is refused" prove power? What would a subtly biased lab (not a bridge) do to B0?
6. **The hygiene law** (`test_lab_hygiene.py`): can a lab module still reach real data or a friction constant without tripping it?
7. **The re-statement** (GAP-P12D-124/49/31/28): do the ledger numbers match the run reports? Is "TREND and BREAKOUT withdrawn" supported? Was GAP-P12D-28 closed on adequate proof?

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces 1, 2, 3, 5 and 7.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch only):** the implementation AND the design against the outside world.
  - Cont (2001)'s stylized facts as quoted, including the β ∈ [0.2, 0.4] range and the tail index.
  - Baillie & Bollerslev (1989) for daily FX t-GARCH.
  - The validity of E[sign(X)·Y] = √(2/π)·Cov(X, Y)/sd(X) and of the arcsine (Sheppard) law under fat tails and GARCH.
  - The tom-next "triple Wednesday" and /365 day-count conventions for spot FX rollover (OANDA, the prop venues).
  - Brownian-bridge conditioning exactness.
  - Whether variance-matching a positive control "at the decision horizon" is sound design in simulation-based power studies.
  - Lo (2002) on the Sharpe ratio's sampling variance, and why realised power beat theory at long horizons.
  - The Carr & López de Prado (2014) synthetic-path precedent that R1-C cites.
