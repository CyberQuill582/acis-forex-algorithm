# PLAN R1: the ACIS training and validation plan (R-1) — **v1**

- **Status: v1, complete in all six sections.**
  - It is written from the four lanes' draft "For PLAN_R1" sections (`PARTIAL_R1A..D.md`, 08:14 UTC), the prior
    cloud review (`../SYNTHESIS.md`, C1–C5) and the local five-agent finals (`archive/RESEARCH_*_2026-09-24.md` at
    BASE).
  - **Lane numbers are DRAFT and not yet lead-verified (P3 pending).** v2 replaces them with the lanes' finals and
    the lead's P3 verdicts.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`.
- **Author:** the cloud lead. Its configuration reads `claude-opus-5-5` at effort `xhigh`. Every lane ran on `opus`.
- **What this is:** a proposal for the local ACIS lead and the owner. It is not a spec. Every §4 item needs owner
  ratification under ACIS governance.
- **Ledger IDs:** every ID cited here exists at BASE; the P12D-52..85 series is on `main` at BASE.
- **Nothing here is a §14 result.** Every number is synthetic, derived, or quoted from a source.
- **Every strategy idea here is LLM-originated.** It may be killed on 2012–2025 history, but credited only forward
  (master §5.6 LLM-contamination law; GAP-P12D-66).

---

## 1. The recommended training and validation architecture (one page)

**The idea in one sentence.** Train almost nothing, and count everything:
- a handful of literature-fixed, economically motivated rules, pooled across ~30 instruments;
- a research simulator that shares the engine's rule code and cost objects;
- a register from which every verdict is computed;
- a lab that proves the machinery on known ground truth before any real-data look;
- a forward record read by anytime-valid tests.

```
RESEARCH FACTORY (out of band; never in the fast loop)
  hypothesis card = a DECLARATIVE PLAN (rule id, ≤3 fixed params, universe id, decision clock, origin + model cutoff)
        │  G0: schema-valid; cost ≤ 1/3 of expected pre-cost SR incl. HOLDING cost; not a graveyard/variant_hash dup
        ▼
  REGISTER  — claim row written FIRST (exclusive create) → one evaluation entry point → result row + daily
              net-return vector (content-addressed). Verdict = pure function of the register.
        │
        ├─ G1 LAB (synthetic, unlimited looks): planted effect detected at theory power; null centred at 0;
        │        leaky oracle refused by structure; RSIM ≡ engine on synthetic tapes
        ├─ G2 DEVELOPMENT (2012–2023, 23 primary instruments, EXPANDING walk-forward, RSIM on daily bars)
        │        verdict over the WHOLE register: Holm/SPA over family streams (+PBO ≤ 0.20 where a grid exists)
        │        AND an absolute OOS-Sharpe lower confidence bound > 0; ≤ 3 registered looks per family
        ├─ G2b ENGINE CONFIRMATION (the real engine on hourly bars-as-ticks, ~25 min/run; ≤ 3 looks; Bonferroni)
        ├─ G3 ONCE: 2024–25 holdout + 7 locked held-out instruments (residualised on the common factor) — kill-only
        ├─ G4 DEMO INCUBATION: cost-gap e-process (fast, ~100–170 fills) · kill e-process (always on) ·
        │        edge e-process (slow; the only place an LLM-originated family can earn "edge shown")
        └─ G5 CHALLENGE (paid): G2–G4 conditions met + human sign-off

ENGINE (live path, deterministic)
  ticks → bars (17:00 NY daily; hourly) → NVMA SAFETY VETO only → rule forecasts (the SAME pure functions RSIM runs)
  → fixed-weight combination × FDM, capped → ONE target position per instrument (risk-sized; 10% no-trade buffer)
  → Governor guards (dampen-only, unchanged) → Orchestrator (broker-side stop) → Risk Monitor (unchanged, sovereign)
```

**The design choices, each with its evidence.**

| Choice | Why (evidence) |
|---|---|
| Pooled, literature-fixed rules with ≤ 3 parameters | C4 counted 43,200 QIEA evaluations per fold against a DSR N ≤ 72. C1: keeping the best of 20 passes noise 44–53% of the time. A pooled, fixed rule has no within-family search to deflate (R1-A P6). |
| An expanding window, not a 2-year rolling one | C1 / GAP-P12D-67: the rolling window realises 0.02 of a 0.65 edge; the expanding one 0.52–0.72 of a 1.22 edge. |
| Breadth ~30 (23 explored + 7 held out) | Effective breadth IDM = √(N/(1+(N−1)ρ)) on **P&L** correlation, not price correlation. At ρ = 0.2 it is 2.04 / 2.10 / 2.13 for N = 20 / 30 / 40, and the ceiling is 1/√ρ (R1-A #6, sim). Against the 2 instruments enabled today, 23 roughly doubles the portfolio Sharpe per unit of edge; against the 8 declared it adds only 13–24%. **The larger gain is held-out capacity** (A5, lead arithmetic). |
| Test the portfolio series, never the stacked panel | The stacked N×T panel passes a zero-edge pooled rule 9.5–32% of the time; the portfolio t-test holds 3.8–6.0% (R1-A #5, sim). |
| Carry is a **cost term**, not a return source, at FTMO | FTMO's own swap JSON: the positive-carry side keeps a median of 21% of fair carry; 6 of 28 G10 pairs pay on both sides. Holding markup is 0.08–0.46 SR/yr (median 0.21), about 10× the trading cost of a medium trend speed (R1-B #1, #5; (a) firm document). |
| Research simulator (RSIM) = the same rule function + the same `CostModel`, called per fill | 0.26–0.46 µs per call; a 30 × 14-year daily run takes ~0.1–0.15 s. So no vectorised cost twin exists that could drift (R1-D D3; GAP-P12D-36 class excluded). |
| The engine reconciles on hourly bars-as-ticks, not a tick replay | Tick replay of 30 instruments is ≈ 70 core-days at ~1,700 ticks/s (GAP-P12D-15); hourly bars take ≈ 25 min (R1-D D6). |
| A lab with known ground truth | The BASE generator's whole-path demeaning is a Brownian bridge. Pooled over 20 instruments it biases momentum by about −1.2 SR and *pays a reversal rule* about +1.2 SR on 2.8-year paths. The lab prototype's null centres at −0.013 (se 0.025) and detects a planted 0.83-SR pooled trend 96% of the time against a theory power of 0.915 (R1-C #1, #4, sim). |
| Anytime-valid forward tests | A betting e-process holds FPR 1.5–3.6% under daily looks over 20 years. A daily-peeked t-test reaches 38–47% (R1-A #1, sim). |

**What the forward record can and cannot prove.** This tempers R-1 item 6 honestly (R1-A P4, sim):
- **Cost and plumbing: weeks.** A doubled cost is caught in a median 30–44 fills. The cost model is certified
  inside ±25% in 102–166 fills.
- **Kill a false claim: 1–3 years.** A claim of 1.0 against a truth of 0 is killed 25% of the time by 1 year;
  the median is 3.1 years.
- **Sign of edge (W ≥ 20): median 2.4–3.0 years at a true portfolio Sharpe of 1.5, and 5.8–6.8 years at 1.0.**
- So a 6–12-month demo says "cost certified, edge not contradicted", never "edge proven". The demo is decisive
  for **killing**; for **certification** it is slow.

---

## 2. The phased build plan

- **Order:** R1.0 → R1.1 → R1.2 → R1.3 → R1.4 → (R1.5 in parallel from R1.1) → R1.6 → R1.7.
- **Track A** (the demo, the owner's top priority) runs in parallel on disjoint code: `core/execution`,
  `core/risk`, `deploy`. SYNTHESIS §2 #1–5 and #13 still bind it.
- **Lines** are the lanes' estimates unless marked "measured"; "sessions" means local build sessions.
- **The dual-audit law** applies at each phase end. Launches are the owner's call.

| Phase | What | Depends on | Lines + / − | Effort |
|---|---|---|---|---|
| **R1.0 Preconditions** (mostly local work already under way) | Merge BUILDER-2's look register and leakage suite after its dual audit (GAP-P12D-64, -65, -83). Finish the graded book's fill honesty: bid/ask-side stop triggers and the loader's wide-spread drop (SYNTHESIS #6; GAP-P12D-84 is fixed at BASE by `1e5c2ba`). Keep the oracle positive control (GAP-P12D-37). | — | (local) | in flight |
| **R1.1 Lab** | **C-1** the generator fix: demean nothing for null and planted; permuted = shuffle + an independent ±1 sign per return. **C-2** a daily-first lab module: common factor, Student-t, GARCH × multi-scale log-vol, jumps, Monday gaps, rate differentials, and five plantable effects with theory Sharpe; ticks on demand. **C-3** the synthetic `RateTable` through `make_financing`. **C-4** a test-only cost-class shim, so there is no second cost model. | — | C-1: −2 / +4, and 2 unit tests rewritten (`test_synthetic_market.py:27-32, :42-45`). C-2: +300 lab, +80 `TickSource` adapter, +150 tests. C-3/4: +50 | 1–2 |
| **R1.2 Register v2** | Extend the look register with `variant` + `variant_hash`, `origin` + `model_id` + `model_cutoff`, `cost_map_hash`, `simulator` + `recon_commit`, and a content-addressed daily net-return vector per run. Aborted runs count. `ProvenanceStore.attempts` is fed by the same entry point. | R1.0 | +~100 | 1 |
| **R1.3 Rules + RSIM** | `rules.py`: one pure `forecast(bars_to_t)` per rule (EWMAC ×3 speeds, breakout, turn-of-month), shared by RSIM and the engine. `rsim.py`: target positions → fills at the next bar ± half-spread, a scalar `CostModel` call per fill, `make_financing`, the FX clock. Move `evolve_step.cost_model()` into `core/` first. **Swap: the C8 cost model carries the venue's per-symbol swap table** (a firm-calibrated markup), not central-bank rates plus a flat 1% (R1-B #2). | R1.1, R1.2 | +150 rules, +150 RSIM, +60 swap table | 2 |
| **R1.4 Verdict + e-processes** | `verdict(register, family\|all, tier)`: Holm/SPA over family streams (`arch` SPA/StepM, a new research-only dependency), CSCV-PBO where a grid exists, the ±10% plateau law over the registered coarse grid (re-homed `plateau.py`), and the OOS-CI lower bound. `eprocess.py`: the edge, kill and cost-gap bettors (R1-A P1–P3). Calibrate on the lab: FPR ≤ 5% under a hill-climbing iteration pattern (50–200 runs, 5–15 families). | R1.1–R1.3 | +120 verdict, +50 e-process, +150 tests | 1–2 |
| **R1.5 Data** (parallel from R1.1) | Hourly bid + ask candles for 30 instruments, 2012–2025: ≈ 10,080 monthly files, **≈ 0.1–0.3 GB, a few hours** (R1-B P4; estimate — measure one file first). No new ticks (≈ 45 GB, 1–2 weeks, not needed). Onboard 22 instruments: `instruments.yaml` metadata, calendars (exchange-anchored for indices and energies), cost classes, swap. A per-symbol decision time for symbols with a ≥ 2 h daily break. | owner go on the universe (§5 D5) | config + ~20/instrument of §13 tests | 1–2 |
| **R1.6 Engine parity + position policy** | The forecast → combined target position in `core/` (A7); risk sizing, risk budget ÷ stop with a vol target (SYNTHESIS #11; GAP-P12D-61); the orchestrator drives the target through the venue stop; the harness uses the production exits (retires the harness-only 48 h `max_hold`). Reconcile RSIM with the engine on hourly bars-as-ticks (VAL R1, R2, R4–R6; R3 becomes an identical target series). | R1.3, Track A's runtime | +~300 (−200 harness duplication) | 2–3 |
| **R1.7 Retire** (kill list, `git mv` to `archive/`) | QIEA (291, measured), `evolve_step.py` (117), `fitness.py` (256), ParamLibrary staging (~92), genome/gene types (~90 est.), the NVMA router (keep the veto, ~120; retire ~500), `regime_labels.py` (197), MR/SCALP/PAIR + the conviction pipeline (~105 + 92), `marginal_alpha.py` (73), the fragmenter + VenueQuality (148) | R1.6 + §4 ratified | **≈ −1,760 prod, ≈ −1,490 test** (R1-D D4, measured at BASE) | 1 |

**Net:** ≈ +1,100 added (lab 530, register 100, rules and RSIM 360, verdict 320, parity 300 — partly offset) against
≈ −1,760 production and −1,490 test lines retired. That is **net ≈ −1,000 production lines**: one search engine
replaced by one register, and a smaller engine that grades the code it trades.

**The first real-data look happens only after R1.0–R1.4 are green on the lab.** Each look before that spends a
budget of about 2–3 (C1) and buys nothing.

---

## 3. The experiment plan

### 3.1 The pre-registered slate (builds on ARC §4; every item LLM-originated → falsify on history, credit forward)

| Rank | ID | Family | Hypothesis (fixed parameters) | Instruments | Horizon / data | Standard |
|---|---|---|---|---|---|---|
| 1 | **D1** | TREND | Pooled EWMAC: (16,64), (32,128), (64,256) on daily 17:00 NY closes; σ = 25-day EWMA of daily changes; Carver's forecast scalars; cap ±20; equal weight across speeds × FDM. A speed is dropped per instrument when its cost, **including holding cost**, exceeds ⅓ of the expected pre-cost SR | 23 primary | daily; hourly bars | replication (t ≥ 2 after publication), plus the register verdict |
| 1b | D2 (inside D1's family) | TREND | D1 plus a forecast threshold (flat while \|f\| < 5), to cut holding cost | same | daily | a registered variant: must beat D1 net on development by ≥ 0.05 SR |
| 1c | D4 (inside D1's family) | TREND | Carver-form breakout N = 40/80/160, smoothed N/4, combined inside the trend forecast | same | daily | a family variant |
| — | H8 → folded into D1 | TREND | The MOP-2012 12-month sign is kept as D1's canonical baseline variant, run raw first (A3) | same | daily | — |
| 2 | **D3** | SEASONAL | Turn-of-month index long, T−1 close → T+3 close | US500, US30, UK100, JP225, EU50 | daily | replication |
| 3 | ARC H5 | FLOW | Month-end FX hedging flow into the 4 pm London fix | FX primary | intraday windows | replication |
| 4 | ARC H6 | FLOW | Tokyo fix, USDJPY into 09:55 JST on gotobi days | USD_JPY | intraday | replication |
| 5 | ARC H1 / H12 | IM | Index, gold and oil intraday momentum into the close | primary indices, XAU, UKOIL | intraday (1-minute bars) | replication |
| 6 | ARC H3 | REV | Index 1-day reversal after large down days | primary indices | daily | replication |
| ctrl | ARC H10 | CONTROL | Pre-FOMC drift: **negative control**, expected null after 2015 | US500 | daily | must FAIL |

- **Rejected families,** with evidence (R1-B P1):
  - carry as a return source: confiscated at FTMO; kept as a cost term;
  - FX value: a CPI dependency for about 7 bets;
  - standalone cross-sectional FX momentum: needs about 48 currencies, and is cost-sensitive (Menkhoff et al. 2012).
- **The first quarter's cap is ≤ 8 families.**
- **Conflict with ARC:** R1-B's held-out draw puts GER40 and US100 in the locked set, and ARC's H1 names them. The
  held-out set binds **every** family, so H1 runs on US500, US30 and UK100 only, or the owner re-salts before
  any look (§5 D5).

### 3.2 The data segments and the looks budget

- **Development tier, 2012–2023, on the 23 primary instruments.**
  - A literature-fixed, pooled family is graded **once** there, on the expanding walk-forward, with **≤ 3
    registered looks per family** in total. VAL and C1 agree on ≤ 3.
  - ARC's E/V split (2012–19 / 2020–23) is **not** used for literature-fixed families. They have no training
    step, and halving T halves t² (R1-D D5; C1 frontier).
  - The E/V split is kept **only for families that are genuinely explored**: novel or house hypotheses, and
    any grid wider than coarse ±1 steps.
  - This settles SYNTHESIS L14, subject to the owner (§5 D6).
- **Engine tier:** ≤ 3 engine confirmations per family, Bonferroni.
- **Holdout tier:** 2024–25 × all 30 instruments, plus 2012–2023 × the 7 held-out instruments. **Once** per
  assembled portfolio. Failure burns it, and the next test is forward.
- **Synthetic tier:** unlimited, and unregistered for verdicts. Lab runs are logged, but never enter a real-data
  verdict.
- **The family cap:** ≤ 20 new families a quarter (ARC §5.4). Every family draws on the stream-level error budget
  (R1-A P6).

### 3.3 Kill criteria (pre-registered; each writes a register line)

- **VAL K1–K6 stand:** budget; PBO > 0.5; harness integrity; holdout; forward; LLM provenance.
- **Added:**
  - **K7 (R1-D):** the measured cost, *including holding cost*, is above ⅓ of the pre-cost SR at G2 → kill before
    any further look.
  - **K8 (R1-D):** a registration that duplicates a graveyard motif or a `variant_hash` is refused.
  - **K9 (R1-D):** any graded number without a register row voids that family's results since its last clean row.
  - **K10 (R1-A):** the forward kill e-process reaches ≥ 20 against the pre-registered claim → kill. At ≥ 5 → review,
    and no scale-up.
  - **K11 (R1-A):** any demo day with a loss beyond 6 × the declared daily σ target, or any fill beyond the cost
    bettor's adverse bound (5 modelled costs), is a sizing or reconciliation **tripwire**. It voids the running
    certification, and is never clipped silently: silent clipping produced **43% false "inside-band"
    certifications** in R1-A's simulation.

### 3.4 The demo incubation protocol (G4)

- **Scope:** ONE pre-registered sleeve at minimum size first (GAP-P12D-68 item 9): D1 on the venue's primary
  instruments. Add sleeves only after the cost e-process certifies.
- **The three bettors,** each ≈ 20–25 lines, sharing one wealth process (R1-A P1–P3). The owner may read them
  every day.
  1. **Cost gap (paired, per fill):**
     - d = realised − modelled cost, from a shadow replay on the same feed;
     - band ±25%;
     - breach at e ≥ 20;
     - certify when both one-sided nulls are rejected at e ≥ 20.
     - **Expected: 3–17 weeks** at 10–40 fills a week (LLM estimate of the turnover; R1-A P4).
  2. **Kill:** H0 is "mean ≥ μ_claim", where μ_claim is the lower of half the validated OOS Sharpe and its lower
     confidence bound. Review at e ≥ 5; kill at e ≥ 20.
  3. **Edge:** H0 is "daily net mean ≤ 0", with the bet sized on the **declared** σ target.
     - W ≥ 20 = "sign of edge shown (α = 0.05)";
     - W ≥ 100 = "strong";
     - anything else = "not yet". It is **never "failed"**, which is the kill bettor's job.
- **The minimum before any verdict:** ≥ 100 reconciled round trips (VAL §5.4), ≥ 1 month covering a weekend, a
  rollover and a scheduled macro event, and the cost bettor certified.
- **Reject:**
  - a daily-peeked t-statistic: 38–47% FPR;
  - a Gaussian mSPRT with an assumed σ: 20% FPR at 1.5× the declared vol.

## 4. Spec amendment drafts (OLD/NEW; proposals only; each needs owner ratification)

**How to read these drafts.**
- The OLD text is verbatim at BASE, with its `file:line`.
- The NEW text is a proposal. The local ACIS lead re-drafts it under ACIS governance: a version bump, a
  changelog line, and the dual audit.
- None of this changes a guardrail value, the equity floor, or HALT/veto semantics.
- A7 touches CLAUDE.md engineering rule 5 ("the conflict-resolution table … is law"). It is therefore marked
  **owner-only**.
- Numbers that came from the lanes' draft PARTIALs are marked (DRAFT). v2 replaces them with the finals.

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
> - **The embargo is ≥ the rule set's holding horizon, not 1 week:** max(7 days, the 95th percentile of the rule
>   set's holding period, measured on the lab). R1-D's receipt measured a mean hold of 53.5 days for a daily
>   EWMAC 16/64 (DRAFT), so this is weeks to months.
> - Where a CPCV stage is used, it must also **purge** the longest lookback (256 days for EWMAC(64,256)), because
>   a training block placed after a test block reads features that overlap it.
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
>    FWER ≤ 5%. **The unit of test is a registered family-version:** the equal-risk combination of its coarse,
>    literature-fixed grid, pooled over all primary instruments, tested on the **portfolio** daily series, never
>    the stacked instrument panel. The panel passes a zero-edge pooled rule 9.5–32% of the time, the portfolio
>    3.8–6.0% (R1-A #5, DRAFT). Argmax within a family is forbidden. Across the register's K family-versions it
>    is Holm or SPA; forward, it is a weighted e-Bonferroni, where family j is promoted only if w_j · W_j ≥ 20 with
>    pre-committed Σw_j ≤ 1 (valid under any dependence, and online) (R1-A P6, DRAFT).
> 2. **Stage B — engine confirmation.** One expanding-window walk-forward run of the frozen candidate through the
>    engine. It is graded on **daily** OOS net returns, with Bonferroni over ≤ 3 registered engine looks per
>    family. The OOS Sharpe must not be significantly below stage A's estimate.
> 3. **Stage C — held-out instruments and the 2024–25 holdout.**
>    - Held-out instruments: residualised on the development P&L (VAL §2.6).
>    - The 2024–25 holdout: once, kill-only.
> 4. **Stage D — forward certification.** An anytime-valid **betting** e-process on the demo's net daily returns (W ≥ 20
>    shows the sign of the edge at α = 0.05; FPR 1.5–3.6% under daily looks, R1-A P1, DRAFT), plus a paired
>    shadow-replay cost e-process and an always-on kill e-process (PLAN §3.4). For LLM-originated hypotheses this is
>    the only stage that can credit a pass (master §5.6, the LLM-contamination law).
>
> `passed` in `ValidationReport` means stage B passed and neither A nor C failed. It no longer contains the
> Deflated Sharpe or the §14 `annual_sharpe > 1.5` row (A6).

**Code delta:**
- `report.py`: drop the `deflated_sharpe >= DSR_MIN` and `trial_count` conditions, and add a `stage_a_verdict`
  input. Net about −10 lines.
- `deflated_sharpe.py` stays as an informational column, until the owner retires it.
- Stage A lives in the research simulator's verdict module: about +120 lines (R1-D D2, est.).

**Falsifier:** on the lab's null families under a realistic iteration pattern (50–200 registered runs), the
verdict's FPR exceeds 5% plus two standard errors. Or its power at a true pooled Sharpe of 1.0 on 20–30
instruments is below 80% at its analytic record length (R1-A measured 77–83%, DRAFT).

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
> three speeds, (16,64), (32,128) and (64,256) (R1-B P1, DRAFT):
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
- The trend family's forecast code is part of `rules.py`, about 150 lines for 3–5 rule functions (R1-D D3, est.).

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
> Every rule family has **≤ 3 free parameters**, fixed at literature values. At most **9** (a ±1-step grid on ≤ 2 parameters) coarse, pre-registered
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

Measured at BASE (R1-D D4, `wc -l`): `qiea.py` 291, `evolve_step.py` 117, `fitness.py` 256, `param_library.py` staging ≈ 92, `param_types.py` genome ≈ 90 (est.). C4/SYNTHESIS K1 estimated about −555 production
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
> - **Research universe: 30 instruments** (R1-B P3, DRAFT): 16 FX, 3 metals, 8 index CFDs, 3 energies, all quoted by FTMO. They span FX majors and crosses, spot metals, index
>   CFDs and energies. Each has validated Dukascopy history from ≤ 2012 and is quoted by the chosen venue.
> - **The universe splits once, by a pre-registered, seeded rule stratified by asset class, committed before any
>   look,** into:
>   - a development set D;
>   - a **locked held-out instrument set** H_inst of **7** instruments, drawn by a salted SHA-256 rule per asset class (FX 3, metal 1, index 2, energy 1). It is never explored, and is
>     graded once at stage C.
> - The 2012–2023 / 2024–25 time split is unchanged.
> - **The live-enabled universe** is the subset that has passed the rung ladder (§5.7) and that the venue quotes.
> - "Genuine diversification" is measured as **effective breadth**, IDM = √(N/(1+(N−1)ρ)) on rule P&L correlation (R1-A #6), not as a
>   count.

**What breadth buys, honestly (lead arithmetic on R1-A's formula):**
- IDM = √(N/(1+(N−1)ρ)). Against the **2 instruments enabled today**, 23 primary instruments roughly double the
  portfolio Sharpe per unit of per-instrument edge: IDM 1.29 → 2.06 at ρ = 0.2, and 1.35 → 2.68 at ρ = 0.1.
- Against the **8 declared**, the gain is modest: +13% at ρ = 0.2 (1.83 → 2.06), and +24% at ρ = 0.1
  (2.17 → 2.68).
- So the case for 30 over 8 rests mainly on **held-out capacity** (7 locked instruments, a contamination-free
  test) and on cross-asset decorrelation (low ρ between FX, indices, metals and energies). Raw power is the
  smaller part.

**Falsifier:** on the lab, calibrated to *published* cross-asset correlation levels, the portfolio-level IDM gain
from 8 → 23 is below 1.1×, **and** the held-out set cannot reach 50% power for a kill at a true per-instrument SR
of 0.3. If both hold, keep 8 plus a smaller held-out set, and spare the onboarding cost. Breadth
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
> - a point estimate above the Holm hurdle, e.g. SR̂ > 0.74 at 10 OOS years and K = 10 (R1-A P7, DRAFT);
> - net expectancy > 0 at 1.5× cost;
> - a forward edge e-value W ≥ 20 before any claim that the edge has been shown forward (R1-A P1).
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
>   pre-registered weights (equal within a family, then equal risk across families: handcrafting, R1-B P2), multiplied by the forecast-diversification
>   multiplier and capped.
> - The combined forecast sets **one target position** per instrument, with a no-trade buffer.
> - **Ambiguity still means no trade:** a net forecast inside the buffer places no order.
> - NVMA keeps **only its safety veto**: `tradeable=False` on ILLIQUID, MACRO_EVENT or UNCLASSIFIED, a spread
>   above 3× the session median, or a dead market. Regimes no longer gate families or key parameters.
> - Any regime conditioning must enter as a **continuous, registered weight variant**, graded like any other
>   variant. R1-D (I7, DRAFT) rejects a soft-regime layer for now, and keeps it revivable as one registered family if
>   a pre-specified 2-state model improves the deflated verdict on the held-out instruments.

This retires `DISCARD_OPPOSITE` as the lock that C3 measured holding one slot 97–99% of the time.

**Why it is owner-only:** "opposite ⇒ discard both" is conflict-table law (CLAUDE.md rule 5), and HALT/veto
semantics are untouched. Netting is **risk-reducing relative to independent slots**: a long and a short forecast
cancel instead of each trading. It still changes a law, so the owner rules.

**Falsifier:** in the lab, the netted target-position book has a higher turnover-adjusted cost per unit of
captured edge than the discard-both book, at equal registered looks.

## 5. Owner decisions (each with a recommendation)

| # | Decision | Recommendation | Why | If declined |
|---|---|---|---|---|
| D1 | Ratify **A1**, the expanding window | **Yes** | C1 and VAL measured independently; GAP-P12D-67 | The rolling window throws most of any real edge away, and the iterator keeps revising (GAP-P12D-64) |
| D2 | Ratify **A2**, the register-aware verdict, replacing DSR ≥ 0.95 | **Yes.** Stage A: Holm/SPA over family streams, plus PBO where a grid exists, plus the absolute CI bound (all three, per Gençay's third failure mode) | The as-built gate has FPR 0% and power 0.3% at 1.22 (C1, VAL; GAP-P12D-37) | `passed` can pass nothing, true or false |
| D3 | Ratify **A3**, the trend family replacing the "required canonical TSMOM" module | **Yes**, keeping MOP-12m as the canonical baseline variant | C3 lockout (97–99% of slot time); GAP-P12D-71 (carry premise); R1-B F3 (TSMOM is F1's slowest speed) | TSMOM keeps the slot and the arena stays locked out |
| D4 | Ratify **A4**, retiring QIEA and per-regime/instrument parameters | **Yes** | C4 (43,200 evaluations per fold); R1-D D4 (≈ −1,760 prod lines) | The DSR/register never catches up with the search |
| D5 | Ratify **A5**, the universe: **30 instruments, 23 primary + 7 held-out** (R1-B P3), drawn by the pre-registered salted SHA-256 rule | **Yes, and confirm the salt now**, before any look. Confirm that no strategy grade on real data has touched AUD_USD or EUR_GBP (both drawn into the held-out set; data validation is not a strategy look) | Held-out instruments are one of the two uncontaminated tests (R-1 item 6) | Keep 8. Then there are no held-out instruments at all, and breadth stays ≈ 1.6–1.8 |
| D6 | The data segments for literature-fixed families: **one development tier 2012–2023** (not ARC's E/V split) | **Yes** for literature-fixed pooled families; E/V split only for explored families | Settles SYNTHESIS L14. Splitting halves t² (C1) | Power roughly halves for the core family |
| D7 | Ratify **A6**: §14 becomes the §6 bar below; win rate, duration and positive months are reported, not gated | **Yes** | R1-D measured a planted SR 0.87 rule failing all three rows (win 0.18, hold 53.5 d, positive months 52%); §5.6 contradicts §14 | Every daily-horizon rule fails §14 whatever its edge |
| D8 | Ratify **A7**, forecast netting + NVMA veto-only (**owner-only**: conflict-table law) | **Yes** | C3 lockout; GAP-P12D-68 items 1 and 3; ARC | Slot contention stays; the regime router keeps multiplying the search ×9 |
| D9 | **FTMO swap reality.** Ask FTMO/E8 (draft below) about swap-free accounts and swap stability; universe admission uses the firm's swap table | **Yes, before R1.5 commits the universe** | Holding markup of 0.08–0.46 SR/yr eats the cost budget of a slow rule on most instruments (R1-B #5) | Slow trend may be net-negative on indices and metals at FTMO |
| D10 | What "edge shown" means for going to a paid challenge | **Challenge allowed** after G2 + G3 pass, cost certified, no kill signal over ≥ 3 months. **"Edge proven" claimed only at W ≥ 20.** The challenge is a capped-loss forward test, never evidence (C1 §2.8; GAP-P12D-62) | W ≥ 20 needs 2.4–3 years even at SR 1.5 (R1-A) | Waiting for W ≥ 20 before any challenge means ~3–7 years |
| D11 | Where the research compute runs | The laptop is enough: ~1–1.5 days one-time bar build (resumable), then seconds per run (R1-D D6). Keep the engine confirmation off the power-losing laptop if possible (GAP-P12D-76) | Measured RSIM timing | — |

**Draft message for the owner to send** (SCO has the firm contacts; send nothing on the owner's behalf):

> "For an algorithmic account holding positions for days to weeks on FX majors and crosses, gold and index
> CFDs: (1) do you offer swap-free accounts, and on which instruments; (2) how often do the swap points
> published on ftmo.com/en/symbols change, and is their history available; (3) how are the swap points on
> USOIL/UKOIL to be read in account currency?"

---

## 6. The bar: "bleeding edge" versus "a joke" (measurable acceptance criteria)

**Bleeding edge** means that it survives honest out-of-sample evaluation. Each criterion below is computable from
the register and the forward record alone. All must hold for the stated claim. Thresholds marked DRAFT are R1-A's
simulated numbers, pending its final.

| # | Criterion | Threshold | What it protects against | Evidence |
|---|---|---|---|---|
| B0 | **Machinery proven first.** On the lab: planted effect detected within 2 se of theory power; null false-detect ≤ 5% + 2 se; leaky oracle refused by structure; RSIM ≡ engine (R1–R6) | all pass on the current commit (`recon_commit`) | A grader that is itself wrong (GAP-P12D-37; C2) | R1-C #4 (96% vs 0.915 theory; null 4.0%); VAL §7–8 |
| B1 | **Every number registered.** No graded number exists without a claim row written first; aborted runs count | 0 exceptions (K9) | The outer loop: keep-best-of-20 = 44–53% FPR | C1 #2; Gençay §3.2 (b) |
| B2 | **Register-corrected development verdict.** Holm (or SPA) over the K family streams, on the expanding-WF OOS **portfolio** daily series; the one-sided lower bound of the OOS Sharpe > 0, i.e. SR̂ > z_{1−0.05/K}/√Y | DRAFT: SR̂ > **0.74** at Y = 10 OOS years and K = 10; 80% power at a true portfolio SR 1.0 | Selection, the panel-independence fallacy | R1-A P7(a), #5 (sim) |
| B3 | **No overfit ranking.** PBO ≤ 0.20 for any family with a grid; the ±10% plateau holds across the registered coarse grid | both | A winner that keeps its rank but loses its absolute edge (hence B2's absolute bound as well) | VAL §3; Gençay §7 (b) |
| B4 | **Cost robustness.** Net > 0 at 2× the modelled cost including holding cost; cost ≤ ⅓ of the pre-cost SR | both | A friction-bought edge; the swap markup | ARC G3; Carver speed limit (b, C4 §1 #8); R1-B #5 |
| B5 | **Engine realises what RSIM measured.** Engine OOS Sharpe not significantly below RSIM's (one-sided 5%) | pass | A research-simulator artefact | VAL stage 3 |
| B6 | **Held-out instruments and the 2024–25 holdout, once.** Kill if either residualised Sharpe is < 0 | kill-only (a true 1.0 is wrongly killed ~8% of the time) | The two contamination-free historical tests | R1-A P7(b); VAL §2.6 |
| B7 | **Forward cost certified.** The cost-gap e-process certifies ±25% before any scale-up | e ≥ 20 on both one-sided nulls; median 102–166 fills | Plumbing and cost fantasy (GAP-0001) | R1-A P3 (sim) |
| B8 | **Forward kill never fires.** The kill e-process against the pre-registered claim | e < 5 (review at 5, kill at 20) | Believing a backtest that forward time contradicts | R1-A P2 (sim) |
| B9 | **"Edge shown" (the only credit an LLM-originated family can earn).** Edge e-process on forward daily net returns | W ≥ 20 (α = 0.05, valid under daily looks); "strong" at W ≥ 100 | Daily peeking (38–47% FPR); contamination (GAP-P12D-66) | R1-A P1 (sim); Ramdas et al. (a/b) |

**The markers of "a joke"**, any one of which fails the build:
- a quoted in-sample number;
- a best-of-N without its N;
- a pass on the stacked panel instead of the portfolio;
- a gate that passes nothing, or everything, on the lab;
- an LLM-originated family credited on pre-cutoff data;
- a demo "proof" of edge in months;
- a cost model whose tripwire was clipped.

**The one-line claim ladder:**
- B0–B6 → "validated on history (kill-tested)";
- + B7–B8 → "fit to trade at minimum size / challenge-eligible" (with human sign-off);
- + B9 → "edge shown forward".

Nothing weaker earns any of those words.

---

## 7. Disagreements and resolutions (v1)

| Point | Positions | Resolution |
|---|---|---|
| The generator fix | C3 / SYNTHESIS #8: "demean only the planted drift". R1-C: that is itself a bridge on the drift, and costs power (mom126 +0.10 vs +0.18 undemeaned); fix = demean nothing, plus a sign-flip on permuted | **R1-C** (sim, closed form re-derived). To be P3-verified by the lead in v2 |
| The E/V split vs one development tier | ARC and R1-B (slate gates) use E = 2012–19, V = 2020–23. R1-D and C1: one tier | **One tier for literature-fixed families; E/V for explored ones** (§3.2; owner D6) |
| Stage A: SPA/StepM vs CPCV + PBO | SYNTHESIS L5: keep the local CPCV + PBO decision; SPA as a cross-check. R1-A P6: Holm/SPA over *family streams*; R1-D: all three instruments | **At family granularity with fixed pooled rules, a Holm/SPA test over family streams is the verdict.** PBO applies only where a grid exists. The absolute CI bound always applies (Gençay). Compatible with the local D1 = C + D decision |
| C1's frontier | C1: 9.3 years at SR 1, K = 1. R1-A #7: 6.2 years with daily observations (Lo's factor in annual units overstated it; matches VAL §5.1) | **R1-A**, pending P3 |
| Carry | ARC H8 and master §5.6 include carry in the canon. R1-B: confiscated at FTMO | **A cost term at FTMO**; revisit on a venue with fair swap (§5 D9) |
| Regime as a weight | The mission lists it as a candidate. R1-D I7: reject for now | **Reject for now**, retire the router (A7); revivable as one registered family |

---

## 8. Status of verification (P3) and what v2 adds

- **v1 rests on the lanes' draft PARTIALs** (08:14 UTC). No lane number has yet been reproduced by the lead.
- **v2 will:**
  - replace the DRAFT numbers with the finals;
  - record P3 verdicts on each lane's top three claims: R1-A's e-process FPR and demo table; R1-B's FTMO swap
    table; R1-C's bridge probe and calibration run; R1-D's kill-list line counts and RSIM timing;
  - add the lanes' source lists.
- **Residual risk:** every rule idea is LLM-originated, and grading it on 2012–2025 is a look inside the models'
  training window. Its honest test is the register once, the held-out instruments and holdout once, then forward.
