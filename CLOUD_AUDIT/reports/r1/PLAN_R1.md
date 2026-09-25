# PLAN R1: the ACIS training and validation plan (R-1) — SKELETON (v0; v1 lands when the lane PARTIALs do)

- **Status:** v0 skeleton, written at launch. §4 (the OLD/NEW drafts) is drafted from the verbatim spec at BASE.
  §1–§3, §5 and §6 are filled from the four lanes.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`.
- **Author:** the cloud lead. Its configuration reads `claude-opus-5-5` at effort `xhigh`.

## 1. The recommended training and validation architecture (one page)
*(pending R1-A/B/C/D PARTIALs)*

## 2. The phased build plan
*(pending)*

## 3. The experiment plan
*(pending)*

## 4. Spec amendment drafts (OLD/NEW; proposals only; each needs owner ratification)

**How to read these drafts.**
- The OLD text is verbatim at BASE, with its `file:line`.
- The NEW text is a proposal. The local ACIS lead re-drafts it under ACIS governance: a version bump, a
  changelog line, and the dual audit.
- None of this changes a guardrail value, the equity floor, or HALT/veto semantics.
- A7 touches CLAUDE.md engineering rule 5 ("the conflict-resolution table … is law"). It is therefore marked
  **owner-only**.
- Numbers marked ⟨…⟩ are filled in at v1 from the lane reports.

### A1 — The training window: 2-year rolling → expanding  [ratified 2026-07-21, OOS_VALIDATION]

**OLD** (`tests/backtest/OOS_VALIDATION.md:36-39`):
> - **Walk-forward (development):** **2-yr train / 1-yr test / 1-yr step**, with a
>   **~1-week embargo** between train and test (purge boundary leakage; embargo ≥ the
>   48 h max-hold). Over 2012→2024 this is **~10 rolling folds, ~10 yr concatenated
>   OOS** — far above the §14 ≥2-yr / >1-fold / ≥30-trade floors.

The code is `tests/backtest/oos_plan.py:27` (`TRAIN_YEARS = 2`) and `:43` (`train_start = year - train_years`).

**OLD** (`tests/backtest/OOS_VALIDATION.md:19-20`):
> The only legitimate optimisation is QIEA evolving genes on each
> train fold; the validation design is not an optimisation target.

**NEW:**
> - **Walk-forward (development): EXPANDING train / 1-yr test / 1-yr step.** The fold testing year Y trains on
>   every validated day from `DATA_START` (per instrument, its first validated day ≥ 2012-01-01) to 1 January Y.
>   The first test year needs ≥ 2 years of training.
> - **The embargo is ≥ the longest of:** the rule set's maximum declared hold, its longest lookback, and 7 days.
>   For daily-horizon rules that is ⟨weeks; from R1-B's slowest speed⟩, not 1 week.
> - Over 2012→2024 this gives ~10 folds and ~10 years of concatenated OOS.
> - **Why (C1, VAL; sim):** the 2-year rolling selection realised 0.02 of a 0.65 edge and 0.15–0.19 of a 1.22
>   edge. The expanding window realised 0.52–0.72, and lifted the expanding WF's power from 66% to 74% at 0.94.
>
> The only legitimate selection is **among pre-registered, coarse rule variants** (A4), on each expanding train
> fold. Every variant is written to the register before it is evaluated (A2). The validation design is not an
> optimisation target.

**Code delta:** `oos_plan.py`: `train_start = max(DATA_START, first_validated_day)`, and an embargo argument
derived from the rule set's declared horizons. About ±10 lines.

**Falsifier:** on the new lab (R1-C), a planted pooled trend at a known Sharpe realises less under the
expanding window than under the rolling one.

### A2 — The `passed` gate: DSR ≥ 0.95 over ≥ 2 trials → a register-aware verdict  [ratified 2026-09-15, GAP-P12D-16]

**OLD** (`specs/ACIS-09-BACKTEST_VALIDATION.md:151`, C-BT-11, excerpt):
> The report carries `trial_count` and the Deflated Sharpe (Bailey & López de Prado 2014, pinned by test to the
> paper's numerical example), and `passed` requires a Deflated Sharpe ≥ 0.95 over at least 2 trials, so a report
> that does not record its trials cannot pass (owner-ratified 2026-09-15, GAP-P12D-16). The trials are the
> candidate champions at each fold's selection — every instrument × regime QIEA evolved — each contributing its
> holdout per-trade Sharpe; …

The code is `tests/backtest/report.py:112-121`, which requires `trial_count >= _MIN_TRIALS` and
`deflated_sharpe >= DSR_MIN` alongside `all(targets_met.values())`.

**NEW:**
> **C-BT-11 (v2, the register-aware verdict).** No grade on real data runs unless its register line is written
> first (exclusive create), and a grade without one cannot pass. A candidate's verdict is computed over the
> **whole register of its family**, never over the best run. It has four stages:
>
> 1. **Stage A — search-aware screen.** Over the registered union of every configuration the family ever
>    evaluated on the development span, one of:
>    - Hansen SPA / Romano–Wolf StepM on the config × day net-P&L matrix;
>    - CPCV (purge ≥ the longest lookback) with PBO ≤ 0.20, deflated by the family's registered looks.
>
>    FWER ≤ 5%. ⟨R1-A: the pooled-across-instruments form, and the stream-level FDR rule across families⟩.
> 2. **Stage B — engine confirmation.** One expanding-window walk-forward run of the frozen candidate through the
>    engine. It is graded on **daily** OOS net returns, with Bonferroni over ≤ 3 registered engine looks per
>    family. The OOS Sharpe must not be significantly below stage A's estimate.
> 3. **Stage C — held-out instruments and the 2024–25 holdout.**
>    - Held-out instruments: residualised on the development P&L (VAL §2.6).
>    - The 2024–25 holdout: once, kill-only.
> 4. **Stage D — forward certification.** An anytime-valid e-process on the demo's net daily returns ⟨R1-A:
>    threshold, e.g. e ≥ 20⟩, plus a paired shadow-replay cost e-process. For LLM-originated hypotheses this is
>    the only stage that can credit a pass (master §5.6, the LLM-contamination law).
>
> `passed` in `ValidationReport` means stage B passed and neither A nor C failed. It no longer contains the
> Deflated Sharpe or the §14 `annual_sharpe > 1.5` row (A6).

**Code delta:**
- `report.py`: drop the `deflated_sharpe >= DSR_MIN` and `trial_count` conditions, and add a `stage_a_verdict`
  input. Net about −10 lines.
- `deflated_sharpe.py` stays as an informational column, until the owner retires it.
- Stage A lives in the research simulator's verdict module: ⟨R1-D: lines⟩.

**Falsifier:** on the lab's null families under a realistic iteration pattern (50–200 registered runs), the
verdict's FPR exceeds 5% plus two standard errors. Or its power at a true pooled Sharpe of 1.0 on 20–30
instruments is below ⟨R1-A⟩.

### A3 — TSMOM "required canonical" → the TREND family, multi-speed and pooled  [ratified v2.9; ACIS-04 §6.6]

**OLD** (`ACIS_SPEC.md:203`, master §5.6, excerpt):
> ACIS's momentum modules currently live at short horizons; **a slow multi-month time-series-momentum module is a
> required canonical implementation for v1** (ACIS-04/ACIS-11), and multi-horizon ensembling is the declared
> direction.

**OLD** (`specs/ACIS-04-ALPHA_ARENA.md:77`):
> | Slow TSMOM | **every tradeable regime** (canonical unconditional — the century evidence is regime-blind; the NVMA
> veto stays sovereign via `tradeable`) | ≥ `tsmom_min_history_days` daily closes | — |

**OLD** (`specs/ACIS-04-ALPHA_ARENA.md:88`, excerpt):
> 6. **Slow TSMOM** (v2.9 required canonical; Moskowitz–Ooi–Pedersen 2012, implemented faithfully-simple, tested
> raw first per §5.6) — on **daily closes**: trailing simple returns over 63/126/252 trading days; … exit = vote
> flip / re-evaluation.

**NEW** (master §5.6):
> The **trend family is the required canonical implementation for v1.** It is a continuous trend forecast at
> ⟨R1-B: e.g. 3–4⟩ speeds:
> - EWMA crossovers;
> - the MOP-2012 12-month sign as the literature-fixed **baseline variant**, run raw first.
>
> Parameters are pooled across instruments. Each speed is admitted per instrument only if its cost is ≤ ⅓ of
> its expected pre-cost Sharpe (Carver's speed limit, (b), verified at C4 §1 #8). Forecasts are scaled, capped
> and combined with the other families' forecasts into **one target position per instrument** (A7). No family
> holds an instrument's position slot by itself. Multi-horizon ensembling is the design, not a direction.

**NEW** (ACIS-04 §6.6): TSMOM's 63/126/252 vote is kept as one registered variant of the trend family, with
- the §8.6 disaster stop as a broker-side stop;
- exit by target-position change;
- no harness-only `max_hold` (C3; SYNTHESIS #14).

The "every tradeable regime" row stands, because the trend family is regime-blind (A7).

**Code delta:**
- `core/signals/canonical.py` (114 lines) becomes a forecast function rather than a `Signal` emitter.
- The trend family's forecast code is ⟨R1-B/R1-D: ~60–100 lines⟩.

**Falsifier:** on the lab, the pooled multi-speed trend family captures a planted multi-speed trend at a lower
realised fraction than the TSMOM vote alone. Or, on real development data, its registered stage-A statistic
is worse than the faithful 12-month sign, on the same instruments and costs.

### A4 — QIEA per-regime × per-instrument evolution → pooled, coarse, literature-fixed rule parameters  [master §5; ACIS-03]

**OLD** (`ACIS_SPEC.md:171`, master §5):
> Quantum-inspired binary chromosome evolution maintaining a **regime-indexed parameter library** (best `ParamSet`
> per RegimeType).

**OLD** (`specs/ACIS-03-QIEA_OPTIMIZER.md:21`, §1 Purpose):
> Evolve, per regime, the best strategy `ParamSet` using a Quantum-Inspired Evolutionary Algorithm, and maintain a
> **regime-indexed parameter library** the fast loop reads.

**OLD** (`ACIS_SPEC.md:93`, the §2 table row):
> | Regime shift + no evolved params for new regime | `tradeable=False` until QIEA completes evolution |

**NEW** (master §5, retitled **RULE PARAMETERS**):
> Every rule family has **≤ 3 free parameters**, fixed at literature values. At most ⟨k⟩ coarse, pre-registered
> robustness variants may be evaluated; each is written to the register first.
> - Parameters are **pooled across instruments**.
> - They may differ by asset class, or by an instrument's cost tier, only when a declared, pre-registered rule
>   (the cost speed-limit) says so.
> - There is no per-regime and no per-instrument parameter library, and no evolutionary search.
>
> **The staging rule survives verbatim for any parameter change.** No live parameter changes mid-session or with
> open positions, and promotion happens only at a valid session boundary (C1/C2 unchanged). C8 (net-of-costs)
> and C9 (positive expectancy) bind the variant selection exactly as they bound QIEA fitness.

**NEW** (the §2 row):
> | Instrument has no registered, validated rule set | `tradeable=False` |

**Retired to `archive/`** (a `git mv`, never a delete):
- `core/optimizer/qiea.py` (291 lines);
- `tests/backtest/evolve_step.py`;
- ParamLibrary's per-regime staging;
- the regime-labelled fitness window.

The line counts for all of these are ⟨R1-D, measured at BASE⟩. C4/SYNTHESIS K1 estimated about −555 production
and −460 test lines. `plateau.py` (the ±10% law) is kept, re-aimed at the coarse variants.

**Falsifier:** on the lab, the pooled, fixed-parameter rule's OOS realised fraction of a planted edge is lower
than QIEA-per-regime's, at an equal registered look count. (C1/C4 predict the opposite.)

### A5 — The universe: 8 instruments → a 20–40-instrument research universe with a locked held-out set  [ratified 2026-07-22]

**OLD** (`tests/backtest/OOS_VALIDATION.md:22-26`):
> - **Data:** `2012-01-01 → 2026-01-01` (14 yr). **Enabled universe RATIFIED
>   2026-07-22 (owner): 8 instruments** chosen for genuine cross-sectional
>   diversification (the honest path to a trustworthy Sharpe, GAP-SP12E-01), not more
>   USD-correlated majors: …

**NEW:**
> - **Research universe: ⟨R1-B: N = 20–40⟩ instruments.** They span FX majors and crosses, spot metals, index
>   CFDs and energies. Each has validated Dukascopy history from ≤ 2012 and is quoted by the chosen venue.
> - **The universe splits once, by a pre-registered, seeded rule stratified by asset class, committed before any
>   look,** into:
>   - a development set D;
>   - a **locked held-out instrument set** H_inst of ⟨R1-A/B: 6–10⟩ instruments. It is never explored, and is
>     graded once at stage C.
> - The 2012–2023 / 2024–25 time split is unchanged.
> - **The live-enabled universe** is the subset that has passed the rung ladder (§5.7) and that the venue quotes.
> - "Genuine diversification" is measured as **effective breadth**, correlation-adjusted (⟨R1-A/B⟩), not as a
>   count.

**Falsifier:** the effective breadth ⟨R1-A/B⟩ at the proposed N is below ~1.5× that of the current 8. Breadth
would then not pay for its onboarding cost, which is per-instrument metadata, calendars and §13 tests.

### A6 — §14: the targets that contradict a daily-horizon rule set  [master §14; owner-ratified targets]

**OLD** (`ACIS_SPEC.md:359-367`, rows):
> | Annual Sharpe | > 1.5 | > 2.5 |
> | Win rate | > 48% | > 58% |
> | Avg trade duration | 30min–48h | — |

**Why these three contradict the ratified direction and the spec itself:**
- **Annual Sharpe > 1.5 cannot be certified on this history.** C1's frontier puts 80% power at a realised Sharpe
  of 1.0 at 9.3 years even for K = 1. The row adds a point hurdle above what any honest daily-horizon book
  reports: the century trend study reports 0.76 net *on 67 markets* (master §5.6 itself).
- **Win rate > 48%** contradicts master §5.6's own sentence: "published trend-following wins ~35–48% of trades
  yet profits through R:R".
- **The avg trade duration of 30 min–48 h** excludes a daily-horizon trend book by definition. GAP-0055 already
  carves TSMOM out of it.

**NEW:**
> §14 becomes the acceptance bar of PLAN_R1 §6:
> - a register-corrected lower confidence bound on the OOS Sharpe > 0;
> - a point estimate ≥ ⟨R1-A⟩;
> - net expectancy > 0 at 1.5× cost;
> - a forward e-value ≥ ⟨R1-A⟩.
>
> Max DD < 15% and SPX correlation < 0.25 are kept (the drawdown row is guardrail-adjacent and owner-only).
> Win rate, profit factor and duration are **reported, never gated** (the §5.6 expectancy law).

**Falsifier:** none statistical. This is an owner decision about what "works" means. The simulation evidence
is C1 §2.2 and VAL §4.1.

### A7 — Regime as a veto only, and forecasts net instead of "opposite ⇒ discard both"  [master §2, §4, §5.5; CLAUDE.md rule 5 — OWNER-ONLY]

**OLD** (`ACIS_SPEC.md:94`, the §2 conflict table):
> | Two strategies signal opposite directions, same instrument | Discard both. Ambiguity = no trade. |

**OLD** (`ACIS_SPEC.md:195`, excerpt):
> Concurrent strategy modules (regime-gated): **Trend Following** … in trend regimes; **Breakout** … in breakout
> regimes; **Mean Reversion** … in ranging/mean-reverting regimes; …

**NEW:**
> - Rule families emit **forecasts**, not signals. The per-instrument forecasts are combined with fixed,
>   pre-registered weights (⟨R1-B: handcrafted, equal-risk⟩), multiplied by the forecast-diversification
>   multiplier and capped.
> - The combined forecast sets **one target position** per instrument, with a no-trade buffer.
> - **Ambiguity still means no trade:** a net forecast inside the buffer places no order.
> - NVMA keeps **only its safety veto**: `tradeable=False` on ILLIQUID, MACRO_EVENT or UNCLASSIFIED, a spread
>   above 3× the session median, or a dead market. Regimes no longer gate families or key parameters.
> - Any regime conditioning must enter as a **continuous, registered weight variant** (⟨R1-D: verdict on "regime
>   as a weight"⟩), graded like any other variant.

This retires `DISCARD_OPPOSITE` as the lock that C3 measured holding one slot 97–99% of the time.

**Why it is owner-only:** "opposite ⇒ discard both" is conflict-table law (CLAUDE.md rule 5), and HALT/veto
semantics are untouched. Netting is **risk-reducing relative to independent slots**: a long and a short forecast
cancel instead of each trading. It still changes a law, so the owner rules.

**Falsifier:** in the lab, the netted target-position book has a higher turnover-adjusted cost per unit of
captured edge than the discard-both book, at equal registered looks.

## 5. Owner decisions
*(pending)*

## 6. The bar: "bleeding edge" versus "a joke"
*(pending)*
