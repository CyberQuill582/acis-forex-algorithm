# R1 lead review: the cloud's PLAN_R1, verified, disputed and re-drafted for ratification

- **What this is:** the local lead's review of `CLOUD_AUDIT/reports/r1/PLAN_R1.md` (v2 final), imported by path
  on 2026-09-25 (`e12a8ab`). It covers:
  - what the lead checked for itself;
  - where the lead disagrees, with evidence;
  - the plan's §4 amendments (A1–A7), re-drafted under ACIS governance for the owner's ratification;
  - the R1 owner decisions, each with a recommendation.
- **Status: PROPOSED.** Nothing here is applied. No spec, guardrail, equity floor or HALT/veto semantic has
  changed. The plan is finder evidence (A5): it clears nothing, and the lead minted its ledger IDs
  (GAP-P12D-89..102).
- **Direction already ratified:** R-1, 2026-09-25 (owner: *"I ratify it"*; relayed from
  `cloud-handoff/RATIFICATIONS.md`). The six directions are:
  1. few pooled rules;
  2. breadth;
  3. an expanding window;
  4. register every run;
  5. unlimited synthetic iteration for the machinery only;
  6. held-out and forward as the only clean tests.

  The *specifics* below are what needs ratifying.
- **Base:** `main` at `689a406`, after merge 3. Every OLD quote below was re-read on that tree. The plan's BASE
  was `974dbda`, and since then master v2.20 and ACIS-03 v1.5 (the plateau law, §6.4) have landed.
- **Evidence scripts:** `archive/r1_lead_probes/`, each with its `.out`.

---

## 1. What the lead verified (and what held)

| Plan claim | Lead check | Result |
|---|---|---|
| FTMO swap table; EUR/USD −9.49/+0.36; markup 1.3–5%/yr | Re-fetched `ftmo.com/wp-json/ftmo/symbols` on 2026-09-25 (`ftmo_symbols_2026-09-25.json`); read the decomposition | **Holds.** The markup decomposition charges only the markup, not the interest rate a futures (excess) return already nets. So no double-count. US500's long swap is −163.19 points, i.e. 9.16%/yr at 6,500. |
| E8 sells a swap-free option (search rendering only in the plan) | E8's own help page, opened in the owner's browser | **Holds, upgraded to (a):** "Swap free option: Yes" for **E8 One (Forex)** and **E8 Pro Forex** (Forex, Metals, Energies, Indices, Crypto); "No" for Signature and Perpetuals. The +10% price is still (c). |
| FTMO offers swap-free/Islamic accounts | FTMO's own FAQ index | **Unconfirmed:** FTMO's FAQ has no swap-free entry, and third-party pages contradict each other. |
| The generator demeans every path (a bridge), and two tests encode it | `synthetic_market.py:113-114`, `test_synthetic_market.py:27-32` | **Holds** on the current tree. |
| The planted market is ~3.3× the null's daily vol; oracle SR ~157 | Generator defaults (`tick_seconds 20`, `drift_sigma 0.15`, episodes 1–4 h) → ~9.6 episodes/day of ~450 ticks | **Holds:** daily drift σ ≈ 67.5·√9.6 ≈ 209 tick-σ against noise ≈ 65.7 → ratio ≈ 3.3; oracle 0.15·√(4320·252) ≈ 156.5. |
| `fitness.py`'s indicators are imported by the signal layer | `core/signals/indicators.py:16` | **Holds** (line 16, not 17). |
| BASE charges OANDA's flat 1% admin fee | `tests/backtest/financing.py:7-11` | **Holds.** |
| 2 instruments are enabled today | `config/instruments.yaml` | **Holds** (EUR/USD, USD/JPY). |

## 2. Where the lead disagrees (with evidence)

**X1 — The plan never models the minimum lot. At the owner's account size most of its breadth cannot be held**
(high/certain; GAP-P12D-101).
- **The plan's sizing is continuous.** It assumes N_eff ≈ 6 and IDM ≈ 2.4–2.5 for 23 instruments with continuous
  positions.
- **The inputs.** FTMO's own contract sizes put one minimum lot (0.01) at 1,000 base units for FX, 1 oz for gold,
  50 oz for silver, and 0.01 × the index for index CFDs. The 0.01 minimum is an **assumption**: the JSON has no
  min-volume field. The lead applied Carver sizing (budget = capital × vol target × weight × IDM, class-equal
  weights) and ACIS's round-down (GAP-P12D-57), with labelled round prices and vols
  (`lot_granularity.py` → `.out`).
- **Results:**

  | Account | Vol target | Instruments that can never hold one lot | Everything else |
  |---|---|---|---|
  | $6,000 | 10% | **15 of 23:** all 13 FX pairs, gold, silver | — |
  | $10,000 | 10% | **6 FX pairs** | FX needs \|f\| ≥ 13–20 (near the cap, so it is mostly flat); gold needs \|f\| ≥ 18 |
  | $10,000 | 20% | 0 | — |
  | $25,000 | 10% | 0 | — |

- **The instruments fine-grained enough to hold are the index CFDs.** Those carry FTMO's *highest* markups
  (3.6–5%/yr). So the swap regime (R1-D9) and the account size are one decision.
- **The same hole reaches the research simulator.** RSIM as specified trades continuous target positions. If it
  does not round to lot steps exactly as execution does (ACIS-06 C-EXE-6), the graded book is not the tradeable
  book, and B4 ("the engine realises what RSIM measured") fails by construction. That is the GAP-P12D-36 class.

**X2 — Even swap-free, the flagship D1 most likely fails the plan's own development bar** (high/high;
GAP-P12D-102).
- **The mismatch.** The plan's own estimate of D1's net portfolio SR is **+0.32..+0.79 swap-free**
  (−0.15..+0.32 at FTMO swaps). B2's bar is SR̂ > 0.81 (K ≤ 10, Y = 10), or 0.74 at K = 5.
- **Power, from `d1_power.py` → `.out`, with the plan's own se = 1/√Y:**

  | Test | Bar | Swap-free low (0.32) | Swap-free mid (0.55) | Swap-free high (0.79) | FTMO mid (0.08) |
  |---|---|---|---|---|---|
  | Holm, K = 10, Y = 10 | 0.81 | 6% | 21% | 47% | 1% |
  | Holm, K = 5 | 0.74 | 9% | 28% | 57% | 2% |
  | **Fixed-sequence, D1 first at full α, Y = 11** | **0.50** | **28%** | **58%** | **84%** | 9% |

- **The fix costs nothing in rigour.** A pre-registered testing ORDER (fixed-sequence / gatekeeping: the primary
  family at the full α, the next only if it passes) controls family-wise error exactly as Holm does. It gives
  the family the plan itself ranks first about twice the power.
- **The price.** If the primary fails, nothing else passes in that cycle. That is the right price when the plan
  itself caps a cycle at 3–5 families.
- **Y is 11, not 10.** D1 has no training step: the plan's own §3.2 says fixed combinations "have no training
  step". So it needs only its 256-day lookback warm, not the 2-year burn-in A1 imposes. Over 2012–2023 that is
  11 OOS years.

**X3 — "Execute FX at 17:05 New York" buys the day's worst spread** (medium/high; folded into GAP-P12D-95).
- **Measured.** On our own Dukascopy ticks, Jan–Feb 2019 (spreads only; `rollover_spread.py` → `.out`):
  - EUR/USD median spread: 2.4 pips at 17:00–17:05, 2.2 at 17:05–17:10, and still 1.1–1.7 until 18:00. The rest
    of the London/New York day: 0.3.
  - USD/JPY: 1.7 against 0.3.
- **The spec already knows.** Master §13 uses "the spread spike at the real 17:00-New-York rollover" as a
  *clock mark* (ACIS_SPEC.md:355).
- **What it costs.** For a daily rule, 7× the day's spread on every rebalance moves turnover cost from the
  plan's ~0.01–0.02 SR/yr to roughly 0.07–0.14. That is material against a 0.3–0.8 book.
- **The fix is free.** Decide on the 17:00 New York close, and execute FX in a liquid hour (e.g. 03:00–11:00
  New York), outside every gap-rule window. The delay costs a daily rule nothing measurable.

**X4 — The plateau law should not be demoted to "descriptive". Keep it binding as kill-only**
(GAP-P12D-34 residual).
- **What the plan proposes.** A4 re-homes `plateau.py` as a descriptive check.
- **Why that is a loosening.** Master §5.6 makes the plateau law binding ("a strategy that dies at ±10% on any
  parameter fails"), and ACIS-03 v1.5 §6.4 built it as a gate on 2026-09-25.
- **Why the plan's reason fails.** Its reason, that evaluating neighbours spends looks, does not apply to a
  kill-only check. A test that can only REFUSE cannot raise the false-positive rate, so it spends no α.
- **So:** keep it binding for every family, fixed ones included, as a kill-only stage-A condition.

**X5 — A6 is also owner-only, not only A7.**
- **What A6 does.** It removes the §14 Sharpe, win-rate, profit-factor, positive-months and duration rows from
  `passed`. §14 is the live-trading gate (CLAUDE.md), and `report.py:30-31` says it outright: *"tightening the
  grader is allowed, loosening is a master-spec change"*.
- **So:** A6 loosens the live gate. It cannot be applied under any delegation, only on the owner's explicit
  ruling.

**X6 — A4 is also a re-baseline under the untrained-baseline freeze. The plan does not mention it.**
- `config/baseline_manifest.json` freezes the QIEA `gene_space` (tag `baseline-untrained-v1`). BASELINE.md makes a
  changed space "a conscious re-baseline, not an edit", logged append-only.
- Retiring QIEA therefore needs:
  - an append-only re-baseline entry, with the tag kept;
  - the drift-guard test re-pointed;
  - the owner's explicit approval.
- CLAUDE.md rule 5 ("QIEA staging rule … is law") also needs owner wording.

**X7 — Minor points, recorded rather than disputed:**
- **The fill model.** After merge 3, selection (the fitness simulator) fills a favourable gap through the
  target at the open (X3), while the graded book fills targets at their level. When RSIM replaces the fitness
  simulator (A4), ONE fill model must serve both (GAP-P12D-87).
- **Forecast scalars.** The null-derived scalars (4.66/3.26/2.28) sit about 23% above the values the lead
  recalls from Carver's published tables (3.75/2.65/1.87; to verify at source). If real data runs hot, the
  Governor's dampen-only vol normalisation (§6 C16) catches it, so this is a demo-time check, not a blocker.

## 3. The amendments, re-drafted (OLD verbatim at `689a406`; NEW proposed)

Each is a versioned change with a changelog line. None moves a guardrail value, the equity floor, or HALT/veto
semantics. **Owner-only (no delegation): A4's re-baseline, A6, A7.**

### A1 — Walk-forward: 2-year rolling → expanding (R1-D1; GAP-P12D-67; ACIS-09 v1.6 → v1.7)

**OLD** (`tests/backtest/OOS_VALIDATION.md:36-39`, owner-ratified 2026-07-21):
> - **Walk-forward (development):** **2-yr train / 1-yr test / 1-yr step**, with a
>   **~1-week embargo** between train and test (purge boundary leakage; embargo ≥ the
>   48 h max-hold). Over 2012→2024 this is **~10 rolling folds, ~10 yr concatenated
>   OOS** — far above the §14 ≥2-yr / >1-fold / ≥30-trade floors.

**OLD** (`OOS_VALIDATION.md:19-20`): "The only legitimate optimisation is QIEA evolving genes on each train fold;
the validation design is not an optimisation target."

**OLD** (`specs/ACIS-09-BACKTEST_VALIDATION.md:151`, C-BT-11, excerpt): "folds carry an embargo at least as long
as the max hold, enforced on the real data (GAP-SP12E-03)."

**NEW:**
> - **Walk-forward (development): EXPANDING train / 1-yr test / 1-yr step.** The fold testing year Y trains on
>   every validated day from the instrument's first validated day (never before `DATA_START`) up to 1 January Y.
> - A family WITH a training step needs ≥ 2 years before its first test year.
> - A **fixed family** fits nothing on data (master §5, A4), so its first test year opens as soon as its longest
>   lookback is warm (EWMAC(64,256): 256 trading days).
> - **Embargo:** at least max(7 days, the 95th percentile of the rule set's holding period, measured on the lab).
>   Any CPCV stage (explored families only) also purges the longest lookback.
>
> The only legitimate selection is **among the members of a declared search space, hashed and registered before
> the first look** (A2). The validation design is not an optimisation target.

- **Changelog:** "ACIS-09 v1.7: C-BT-11's walk-forward is expanding and its embargo is the measured holding
  horizon (GAP-P12D-67; R-1 item 3)."
- **Code:** `oos_plan.py` (fold start = max(first validated day, `DATA_START`), plus an embargo argument), and
  the fold-plan tests.
- **Falsifier:** on the lab, a planted pooled trend at a known Sharpe realises LESS under expanding than under
  rolling.
- **Lead change from the plan:** no 2-year burn-in for fixed families (X2).

### A2 — `passed`: DSR ≥ 0.95 → a register-aware verdict (R1-D2; supersedes GAP-P12D-16 and local D1; ACIS-09 v1.7)

**OLD** (`specs/ACIS-09-BACKTEST_VALIDATION.md:151`, C-BT-11, excerpt): "`passed` requires a Deflated Sharpe ≥ 0.95
over at least 2 trials, so a report that does not record its trials cannot pass (owner-ratified 2026-09-15,
GAP-P12D-16). The trials are the candidate champions at each fold's selection — every instrument × regime QIEA
evolved — each contributing its holdout per-trade Sharpe; …" The code is `tests/backtest/report.py:43-45` and the
`passed` expression.

**NEW (C-BT-11 v2):**
> 1. **Registration.** A graded number exists only if the look register (`data/validation/looks`, GAP-P12D-64)
>    wrote its line first. The line holds the declared search space's hash, the origin (human / LLM + model
>    cutoff), the cost-map hash and the universe id. The grade stores the family's **daily portfolio net-return
>    vector** (GAP-P12D-98). A verdict is a pure function of the register.
> 2. **Unit of test.** A registered **family-version**: a fixed pooled combination of its members, with no
>    argmax inside, graded on its **portfolio** daily series, never on the stacked instrument × day panel
>    (GAP-P12D-100).
> 3. **Stage A — development.** Tested in a **pre-registered order** (fixed-sequence).
>    - The primary family is tested first, at α = 0.05. It passes when the lower bound of its expanding-WF OOS
>      Sharpe is > 0 (SR̂ > z₀.₉₅/√Y), its paired excess over the registered passive benchmark is > 0, and it is
>      net > 0 at 2× modelled cost including swap.
>    - Each later family is tested only if every earlier one passed.
>    - Families outside the order are Holm-adjusted among themselves.
>    - **Explored families** (a declared grid) use max-t over that grid, plus PBO ≤ 0.20.
>    - **The plateau law binds every family as a kill-only condition:** a ±10% neighbour failing C9 refuses the
>      family.
> 4. **Stage B — engine confirmation.** One frozen expanding-WF run through the engine on hourly bars-as-ticks,
>    graded on daily OOS net returns, with Bonferroni over ≤ 3 registered engine looks. The engine's OOS Sharpe
>    must not be significantly below RSIM's (one-sided 5%).
> 5. **Stage C — kill-only, once.** The held-out instruments are residualised on the explored set's class
>    factor; the 2024–25 holdout is graded once. Each kills at t < −0.5 (GAP-P12D-97).
> 6. **Stage D — forward.** The E1/E2/E3 bettors (PLAN_R1 §3.4). For an LLM-originated family (master §5.6),
>    this is the only stage that can credit a pass.
>
> `passed` = stage A and stage B passed, and stage C did not kill. The Deflated Sharpe stays as an informational
> column.

- **Changelog:** "ACIS-09 v1.7: C-BT-11 v2, the register-aware verdict. It supersedes the DSR ≥ 0.95 gate
  (GAP-P12D-16), which passed nothing (GAP-P12D-33/37)."
- **Falsifier:** on the lab, under an adaptive researcher, the verdict's FPR exceeds 5% plus 2 se; or its power
  at a realistic planted edge falls more than 15 points below declared-grid max-t.
- **Lead change from the plan:** fixed-sequence instead of plain Holm for the first cycle (X2), and the plateau
  law binding as kill-only (X4).

### A3 — "Required canonical TSMOM" → the TREND family (R1-D3; GAP-P12D-71; master v2.20 → v2.21, ACIS-04 v1.2 → v1.3)

**OLD** (`ACIS_SPEC.md:203`, master §5.6): "ACIS's momentum modules currently live at short horizons; **a slow
multi-month time-series-momentum module is a required canonical implementation for v1** (ACIS-04/ACIS-11), and
multi-horizon ensembling is the declared direction."

**OLD** (`specs/ACIS-04-ALPHA_ARENA.md:77`): "| Slow TSMOM | **every tradeable regime** (canonical unconditional —
the century evidence is regime-blind; the NVMA veto stays sovereign via `tradeable`) | ≥ `tsmom_min_history_days`
daily closes | — |"

**OLD** (`specs/ACIS-04-ALPHA_ARENA.md:88`, opening): "6. **Slow TSMOM** (v2.9 required canonical;
Moskowitz–Ooi–Pedersen 2012, implemented faithfully-simple, tested raw first per §5.6) — on **daily closes**: …"

**NEW (master §5.6):**
> The **trend family is the required canonical implementation for v1.** It is a fixed, equal-weight combination
> of EWMA-crossover forecasts at (16,64), (32,128) and (64,256), on 17:00 New York daily closes.
> - Its members are the breakout form (40/80/160) and the MOP-2012 12-month sign, the literature-fixed
>   **baseline variant**, run raw first.
> - Parameters are pooled across instruments.
> - A speed is admitted per instrument only if its cost, including the venue's swap, is ≤ ⅓ of its expected
>   pre-cost Sharpe.
> - Forecast scalars are fixed before any real-data look, spending zero looks.
> - Forecasts are scaled, capped at ±20, and combined into **one target position per instrument** (A7).
> - **Execution:** positions are rounded down to the venue's lot step exactly as ACIS-06 C-EXE-6 does, in RSIM
>   and live alike. Execution runs on a per-symbol clock that lies **outside the 17:00 New York rollover window**
>   and every gap-rule window.

**NEW (ACIS-04 §6.6):** TSMOM's 63/126/252 vote stays as one registered member of the trend family, with:
- the §8.6 disaster stop as a broker-side stop;
- exit by target-position change;
- no harness-only `max_hold`.

The "every tradeable regime" row stands.

- **Changelog:** "master v2.21 / ACIS-04 v1.3: the trend family replaces required-canonical TSMOM (GAP-P12D-71;
  R-1 item 1)."
- **Falsifier:** on the lab, the pooled multi-speed family captures a planted multi-speed trend at a lower
  realised fraction than the TSMOM vote alone.
- **Lead change from the plan:** lot-step rounding in RSIM (X1), and the execution clock outside the rollover
  (X3).

### A4 — QIEA per-regime × per-instrument evolution → pooled fixed parameters (R1-D4; master v2.21, ACIS-03 v1.5 → v2.0; OWNER-ONLY re-baseline)

**OLD** (`ACIS_SPEC.md:171`): "Quantum-inspired binary chromosome evolution maintaining a **regime-indexed
parameter library** (best `ParamSet` per RegimeType)."

**OLD** (`specs/ACIS-03-QIEA_OPTIMIZER.md:21`): "**Purpose.** Evolve, per regime, the best strategy `ParamSet`
using a Quantum-Inspired Evolutionary Algorithm, and maintain a **regime-indexed parameter library** the fast loop
reads. …"

**OLD** (`ACIS_SPEC.md:93`, the §2 table): "| Regime shift + no evolved params for new regime | `tradeable=False`
until QIEA completes evolution |"

**NEW (master §5, retitled RULE PARAMETERS):**
> - Every rule family has **≤ 3 free parameters**, fixed at literature values or on the synthetic null (spending
>   zero looks).
> - A family is a **fixed combination** of its members, and no member is selected on data.
> - Parameters are pooled across instruments, differing only through a declared, pre-registered cost filter.
> - There is no per-regime or per-instrument parameter library, and no evolutionary search.
> - An **explored** family may declare a ±1-step grid on ≤ 2 parameters (≤ 9 members). The grid is hashed
>   before its first look and graded by max-t (A2).
> - **The staging rule survives verbatim for any parameter change:** never mid-session, never with open
>   positions, promotion only at a valid session boundary.
> - C8 and C9 bind every member.
> - **The plateau law (§5.6, ACIS-03 §6.4) stays binding, as a kill-only check** (X4).

**NEW (the §2 row):** "| Instrument has no registered, validated rule set | `tradeable=False` |"

**Also needed:**
- **The re-baseline.** Append an entry to the BASELINE.md re-baseline log and re-point the drift-guard test's
  gene space. The tag `baseline-untrained-v1` stays.
- **CLAUDE.md rule 5:** "the staging rule and the conflict-resolution table … are law". Owner wording.
- **Retirements, after R1.6** (`git mv` to `archive/`): `qiea.py`, `evolve_step.py`, `fitness.py` (after its
  indicators move, GAP-P12D-99), ParamLibrary staging and the genome.

- **Changelog:** "master v2.21 / ACIS-03 v2.0: pooled fixed rule parameters replace QIEA (R-1 item 1); a
  re-baseline under the freeze."
- **Falsifier:** on the lab, a pooled fixed rule realises a lower fraction of a planted edge than
  QIEA-per-regime at an equal registered look count.

### A5 — The universe: 8 → 30 instruments, 7 held out (R1-D5; OOS_VALIDATION.md; `config/instruments.yaml`)

**OLD** (`tests/backtest/OOS_VALIDATION.md:22-24`): "- **Data:** `2012-01-01 → 2026-01-01` (14 yr). **Enabled
universe RATIFIED 2026-07-22 (owner): 8 instruments** chosen for genuine cross-sectional diversification …"

**NEW:** as PLAN_R1 A5:
- **The research universe is 30 instruments:** FX 16; XAU, XAG and XCU; US500, US30, UK100, JP225, EU50, AUS200,
  GER40 and US100; UKOIL, NATGAS and USOIL.
- **7 are held out and locked,** drawn by `sha256("ACIS-R1-holdout-2026-09-25|" + symbol)`: AUD/NZD, NZD/USD,
  CAD/JPY, XCU/USD, GER40, US100 and USOIL. Re-salting after any real-data look is forbidden.
- **Breadth is measured as effective breadth,** not as a count.

**Plus (lead, X1):** "An instrument is **live-eligible on an account** only if one minimum lot is ≤ its risk
budget at |forecast| = 10 on that account. The rest stay research-only there."

- **Before onboarding:** the owner confirms availability with `scripts/download_dukascopy_s3.py check`.
- **Falsifier:** the realised ρ_P&L of the universe, measured on exploration data only, is > 0.3.

### A6 — §14: trade-shape rows reported, not gated (R1-D7; GAP-P12D-96; master v2.21; OWNER-ONLY)

**OLD** (`ACIS_SPEC.md:361, 363, 365, 367`): "| Annual Sharpe | > 1.5 | > 2.5 |" · "| Win rate | > 48% | > 58% |"
· "| Positive months | > 70% | > 85% |" · "| Avg trade duration | 30min–48h | — |". Also `report.py:32-39`.

**NEW:** §14 becomes the claim ladder of PLAN_R1 §6 (B0–B9):
- **"Validated on history (kill-tested)"** = B0–B5.
- **"Fit to trade at minimum size / challenge-eligible"** = B0–B8, plus human sign-off.
- **"Edge shown forward"** = + B9 (E1 ≥ 20).
- Max DD < 15% and SPX correlation < 0.25 stay as gates.
- Win rate, profit factor, positive months and duration are **reported, never gated**.

**Why:**
- A planted SR 0.87 daily rule fails every shape row: win 0.18, hold 53.5 d, positive months 52%.
- Win rate > 48% contradicts §5.6's own "trend-following wins ~35–48%" (`ACIS_SPEC.md:213`).

**Owner-only:** this loosens the live gate (X5).

### A7 — Regime as a veto only; forecasts net instead of "opposite ⇒ discard both" (R1-D8; master v2.21; CLAUDE.md rule 5; OWNER-ONLY)

**OLD** (`ACIS_SPEC.md:94`): "| Two strategies signal opposite directions, same instrument | Discard both.
Ambiguity = no trade. |"

**OLD** (`ACIS_SPEC.md:195`, opening): "Concurrent strategy modules (regime-gated): **Trend Following** … in trend
regimes; **Breakout** … in breakout regimes; **Mean Reversion** … in ranging/mean-reverting regimes; …"

**NEW:** as PLAN_R1 A7:
- Families emit forecasts, combined with fixed pre-registered weights × FDM, capped, into one target position
  with a 10% no-trade buffer.
- **Ambiguity still means no trade:** a net forecast inside the buffer places no order.
- NVMA keeps only its safety veto (ILLIQUID, MACRO_EVENT, UNCLASSIFIED, a spread > 3× the session median, a dead
  market).
- A target reduction executes through the reduce-only atomic close (ACIS-06 C-EXE-7), and pair groups stay
  all-or-none (C-EXE-8).

**Owner-only:** conflict-table law.

## 4. The R1 owner decisions (PLAN_R1 §5, renumbered R1-D* so they do not collide with the local D1–D9)

| # | Decision | Lead recommendation |
|---|---|---|
| **R1-D9** | The swap regime | **RULED 2026-09-25:** decide at the first real-data look. The cost model carries both worlds (FTMO's published table, and swap-free). E8 One/Pro Forex swap-free is confirmed (a); FTMO swap-free is unconfirmed. |
| **R1-D14 (new)** | Account size and vol target against lot granularity (X1) | Decide WITH D9, at the first real-data look. At $6k and 10% vol the FX sleeve cannot be held at all. |
| R1-D1 | A1, the expanding window | Yes, with fixed families exempt from the 2-year burn-in. |
| R1-D2 | A2, the register-aware verdict | Yes, with a **fixed-sequence** order and the plateau law kill-only. It supersedes local D1 (C+D) for fixed families. |
| R1-D3 | A3, the trend family | Yes, with lot-rounded RSIM and the rollover-free execution clock. |
| R1-D4 | A4, retiring QIEA | Yes, as a conscious re-baseline (**owner-only**). |
| R1-D5 | A5, 30 instruments / 7 held out | Yes; freeze the salt now; add the live-eligibility rule. |
| R1-D6 | One development tier for fixed families; E/V only for explored ones | Yes. |
| R1-D7 | A6, §14 as the claim ladder | Yes, keeping the DD and SPX gates (**owner-only**). |
| R1-D8 | A7, netting and a veto-only NVMA | Yes (**owner-only**). |
| R1-D10 | What earns a paid challenge | As the plan: after G2 + G3, E3 certified and E2 silent ≥ 3 months, with sign-off. Never "edge proven" before E1 ≥ 20. |
| R1-D11 | Where research compute runs | The laptop for RSIM; engine confirmations off the laptop (GAP-P12D-76). |
| R1-D12 | Variance-matched planting + the generator fix | Yes. Re-state every recorded synthetic verdict, GAP-P12D-49 included. |
| R1-D13 | The LLM's role | An out-of-band proposer of declarative plans only. |

## 5. What is due next

- **The dual audit of these amendments** (A3, two lenses). The session asks the owner when it runs.
- **Buildable now, [impl], tightening or test-only:**
  - the register v2 fields (GAP-P12D-98);
  - the generator fix, once R1-D12 is ruled (GAP-P12D-91);
  - the swap table in C8 as data (GAP-P12D-93);
  - the indicator move (GAP-P12D-99).
