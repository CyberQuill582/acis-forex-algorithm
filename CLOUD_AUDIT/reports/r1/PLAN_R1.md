# PLAN R1: the ACIS training and validation plan (R-1) — **v2 (final)**

- **Status: v2, final for this pass.** It is built from:
  - the four lanes' **final** reports: `R1A_VALIDATION_SCIENCE.md`, `R1B_EDGE_BREADTH.md`, `R1C_SYNTH_LAB.md` and
    `R1D_INNOVATION_ARCH.md`;
  - the lead's **P3** (`P3_R1_LEAD_VERIFICATION.md`), in which **13 of 13** load-bearing lane claims were
    confirmed;
  - the prior cloud review (`../SYNTHESIS.md`, C1–C5);
  - the local five-agent finals in `archive/` at BASE (VAL, ARC, ECO, SCO).

  v1 (`a12c6cf`) was written from the lanes' drafts. v2 corrects it where the finals moved:
  - the verdict rule;
  - the development bar (0.81, not 0.74);
  - the held-out and holdout kill threshold;
  - the held-out draw;
  - the swap economics.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`. `cloud-handoff` was re-fetched at close and had not moved
  (still built 2026-09-25T07:53:40Z). So there is no delta since the snapshot.
- **Author:** the cloud lead. Its configuration reads `claude-opus-5-5` at effort `xhigh`. Every lane ran on `opus`.
- **What this is:** a proposal for the local ACIS lead and the owner. It is not a spec. Every §4 item needs owner
  ratification under ACIS governance. The local lead mints any ledger IDs (§9 lists them without IDs).
- **Ledger IDs:** every ID cited exists at BASE. The P12D-52..85 series is on `main` at BASE.
- **Nothing here is a §14 result.** Every number is synthetic, derived, or quoted from a source.
- **Every strategy idea here is LLM-originated.** It may be killed on 2012–2025 history, but credited only forward
  (master §5.6 LLM-contamination law; GAP-P12D-66).

---

## 1. The recommended training and validation architecture (one page)

**The idea in one sentence.** Train almost nothing, and count everything:
- a handful of literature-fixed, economically motivated rules, each a **fixed pooled combination**, on 30
  instruments (23 explored, 7 locked away);
- a research simulator that shares the engine's rule code and cost objects;
- a register from which every verdict is computed;
- a lab that proves the machinery on known ground truth before any real-data look;
- a forward record read by anytime-valid tests.

```
RESEARCH FACTORY (out of band; never in the fast loop)
  hypothesis card = a DECLARATIVE PLAN: rule id, ≤3 literature-fixed params, a FIXED pooled combination
                    (no argmax inside), universe id, decision clock + execution clock, origin + model cutoff
        │  G0: schema-valid; declared search space hashed; cost ≤ 1/3 of pre-cost SR INCLUDING swap;
        │      not a graveyard motif or variant_hash duplicate; a passive benchmark arm registered beside it
        ▼
  REGISTER — ONE evaluation entry point writes the claim row FIRST (exclusive create), then the result row and
             the run's daily net-return vector (content-addressed). Verdict = a pure function of the register.
        │
        ├─ G1 LAB (synthetic, unlimited): planted effect found at its theory power; null centred on 0;
        │        leaky oracle refused by structure; RSIM ≡ engine on lab tapes (VAL R1–R6)
        ├─ G2 DEVELOPMENT (2012–2023 × 23 explored instruments; EXPANDING walk-forward; RSIM daily + hourly)
        │        Holm over the K registered family-versions, on each family's PORTFOLIO daily series:
        │        lower bound of OOS SR > 0 ⇔ SR̂ > 0.81 at K ≤ 10, 10 OOS years (72% power at a true 1.0)
        │        + paired excess over the passive benchmark > 0 + net > 0 at 2× cost incl. swap
        ├─ G2b ENGINE CONFIRMATION (the real engine on hourly bars-as-ticks, ~25 min; ≤ 3 looks; Bonferroni)
        ├─ G3 ONCE, kill-only: 7 held-out instruments (residualised; kill at t < −0.5) and the 2024–25
        │        holdout (kill at t < −0.5, i.e. SR̂ < −0.35)
        ├─ G4 DEMO: live-vs-replay decisions identical (look-ahead detector) · cost-gap bettor E3 (weeks) ·
        │        kill bettor E2 (always on) · edge bettor E1 (years; the only credit an LLM-originated family earns)
        └─ G5 CHALLENGE (paid): G2–G3 passed, E3 certified, E2 silent ≥ 3 months, human sign-off

ENGINE (live path, deterministic)
  ticks → bars (decide on the 17:00 New York daily close) → NVMA SAFETY VETO only → rule forecasts (the SAME pure
  functions RSIM imports) → fixed-weight combination × FDM, capped → ONE target position per instrument
  (risk-sized, 10% no-trade buffer) → EXECUTE on the per-symbol execution clock (after the reopen; never inside the
  firm's pre-close or gap window) → Governor guards (dampen-only, unchanged) → Orchestrator (broker-side stop)
  → Risk Monitor (unchanged, sovereign)
```

**The design choices, each with its evidence.** P3 means lead-verified (`P3_R1_LEAD_VERIFICATION.md`, rows 1–13).

| Choice | Why (evidence) |
|---|---|
| Pooled, literature-fixed rules, each a **fixed combination** (no argmax inside a family) | Under an adaptive, hill-climbing researcher, a test over the *registered union of runs* passes noise **10–16%** of the time, and Bonferroni over the runs **6.5–13%**: counting runs is not enough. Max-t over a **declared** grid holds 5.2–5.5%. **Holm over fixed family combinations: 1.5%, with power 64–69%, against 45–58% for grid selection** (R1-A §2.5, sim R = 400; direction reproduced by the lead at R = 80, P3 row 13). C4: QIEA runs 43,200 evaluations per fold. |
| An expanding window | C1 / GAP-P12D-67: the 2-year rolling window realises 0.02 of a 0.65 edge; the expanding one realises 0.52–0.72 of a 1.22 edge. |
| Breadth: 30 instruments = 23 explored + 7 held out | IDM = √(N/(1+(N−1)ρ_P&L)) with ρ_P&L ≈ 0.10–0.15, from MOP 2012 (a): **2.28–2.63 / 2.37–2.77 / 2.42–2.86 at N = 20 / 30 / 40** (R1-A). Against the **2 instruments enabled today**, 23 roughly doubles the Sharpe per unit of edge. **Against the 8 declared, 8 → 30 cuts the years needed by only 1.2–1.6×** (R1-A). The larger gains are the **held-out set** (a contamination-free test) and cross-asset decorrelation: N_eff 5–8 for the mixed 23, against 2–3 for FX alone (R1-B; P3 rows 3, 10). |
| Test the **portfolio** daily series, never the stacked panel | The stacked instrument × day panel passes a zero-edge rule 9.5–32% of the time; the portfolio test holds 3.8–6.0% (R1-A, sim). |
| **Swap is the dominant cost of a slow rule at FTMO.** Carry is a cost term, not a return source | FTMO's own swap table (a): a markup of 1.3–2.6%/yr on FX, ~4.8% on gold and 3.6–5.0% on index CFDs, or **0.08–0.46 SR a year held** (median 0.21). Spread plus commission is ~0.01–0.02. The G10 positive-carry side keeps a median of 21% of fair carry (P3 row 4). **A pooled trend book nets −0.15 to +0.32 SR at FTMO's swaps, against +0.32 to +0.79 on a swap-free account** (R1-B, derived with (a) inputs). BASE's financing model charges a flat 1% (`tests/backtest/financing.py:7-11`). |
| Decide on the 17:00 New York close; **execute on a per-symbol clock** | FTMO's gap rule forbids opening a trade ≤ 2 h before a ≥ 2 h closure, so a Friday 17:00 rebalance is forbidden. At 17:00 New York, indices, metals and oil are inside their 20:50–22:05 UTC break (R1-B §2.7, (a); GAP-P12D-58). |
| A passive-benchmark arm beside every pooled rule | Stops a trend rule's P&L on indices and gold from being mostly the long-drift premium (R1-D P6; Kim–Tse–Wald (a)). |
| Research simulator = the same `forecast()` + the same scalar `CostModel`, called per fill | 30 instruments × 14 years in ~0.1 s daily and ~1.5–2 s hourly (P3 row 11). No vectorised cost twin, so the GAP-P12D-36 class is excluded by identity. |
| Reconcile the engine on hourly bars-as-ticks, not a tick replay | A tick replay of 30 instruments ≈ 70 core-days (GAP-P12D-15 rates); hourly ≈ 25 min (R1-D). |
| A parametric lab with known ground truth; GANs and diffusion rejected | They train on real data (a look), and none can plant an effect with a known Sharpe (R1-C C-9). The BASE generator's demeaning is a bridge: **−1.2 / +1.2 pooled SR bias** (momentum / reversal) at N = 20 on 2.8-year paths. **The planted market is 3.3× the null's daily volatility, with an oracle SR of ~157** (P3 rows 5, 12). The lab prototype passes 9/9 of Cont's stylized facts; its null centres at zero and a planted trend is detected at theory power (P3 row 6). |
| Anytime-valid forward tests | A betting e-process holds FPR ≤ 3.7% under daily looks; a daily-peeked t-test reaches 38–47% (R1-A; P3 row 1, independently re-implemented). |

**What the forward record can and cannot prove.** This tempers R-1 item 6 honestly (R1-A §2.8 R1A-9; P3 row 2):
- **Weeks 0–4, plumbing.** Live and replay decisions must be identical on the same feed. That is the only check
  that catches a look-ahead bug in the code; no historical test can (R1-A, reasoned).
- **Weeks 3–28, cost certified** by E3 in a median 102–166 fills (≈ 5–8 weeks at 20 fills a week). A doubled cost
  is caught in 30–44 fills.
- **Years, the sign of the edge.** E1 reaches W ≥ 20 in a median **2.4–3.0 years at a true portfolio SR of 1.5,
  and 5.8–6.8 years at 1.0.**
- **Killing a false claim:** 25% by 1 year, median 3.1 years (claim 1.0, truth 0).
- So a 6–12-month demo says "plumbing and cost certified, edge not contradicted", never "edge proven". The demo
  is decisive for **killing** and slow for **certifying**.

---

## 2. The phased build plan

- **Order:** R1.0 → R1.1 → R1.2 → R1.3 → R1.4 → (R1.5 in parallel from R1.1) → R1.6 → R1.7.
- **Track A** (the demo, the owner's top priority) runs in parallel on disjoint code: `core/execution`,
  `core/risk`, `deploy`. SYNTHESIS §2 #1–5 and #13 still bind it.
- **Lines** are the lanes' estimates unless marked "measured"; "sessions" means local build sessions.
- **The dual-audit law** applies at each phase end. Launching the auditors is the owner's call.

| Phase | What | Depends on | Lines + / − | Effort |
|---|---|---|---|---|
| **R1.0 Preconditions** (mostly local work already under way) | Merge BUILDER-2's look register and leakage suite after its dual audit (GAP-P12D-64, -65, -83). Finish the graded book's fill honesty: bid/ask-side stop triggers and the loader's wide-spread drop (SYNTHESIS #6; GAP-P12D-84 is fixed at BASE by `1e5c2ba`). Keep the oracle positive control (GAP-P12D-37). | — | (local) | in flight |
| **R1.1 Lab** | **C-1** the generator fix: demean nothing for null and planted; permuted = shuffle, then an independent ±1 sign per return; rewrite `test_synthetic_market.py:27-32, :42-45`; add a martingale test; re-verify the oracle rungs. **C-2** variance-matched planting (owner D12). **C-3** a daily-first lab (4 modules of ≤ 300 lines: vol units, factor, Student-t, GARCH × multi-scale log-vol, jumps, Monday gaps, rates, five plantable effects with theory Sharpe). **C-4** joint intraday bridges (independent bridges plant a spurious pairs edge, t 6–9). **C-5** a truth API with a power statement per (effect, rule). **C-6** a synthetic `RateTable` through `make_financing`. **C-7** a test-only cost-class shim, so there is no second cost model. **C-8** the stylized-facts probe set as the lab's gate. **C-10** the lab-hygiene law | — | C-1: −2 / +3, 2 tests rewritten, +1. C-2: ~8. C-3: ~460 prod + ~350 tests. C-4–C-8, C-10: ~345 | 2 |
| **R1.2 Register v2 + the one entry point** | `evaluate(plan, tier, span)` is the **only** producer of a graded number. It writes the claim row first, runs, stores the daily return vector, and feeds `ProvenanceStore.record_attempt`. The look register gains `variant` + `variant_hash`, `declared_space_hash` (the grid, formula and instrument list: R1-A R1A-1), `origin` + `model_id` + `model_cutoff`, `cost_map_hash`, `simulator` + `recon_commit` and `universe_id`. Aborted runs count | R1.0 | +~160 | 1 |
| **R1.3 Rules + RSIM + costs** | `rules.py`: one pure `forecast(bars_to_t)` per rule, shared by RSIM and the engine. `rsim.py`: target positions → fills on the **execution clock** ± half-spread; a scalar `CostModel` per fill; `make_financing`; the FX clock. Move `evolve_step.cost_model()` into `core/` first, and `fitness.py`'s three indicator functions (imported by `core/signals/indicators.py:17`). **C8 carries the venue's per-symbol swap table** (firm-calibrated markup) and the **per-symbol execution calendar** (R1-B §2.7). Passive-benchmark arms (R1-D P6) | R1.1, R1.2 | +150 rules, +150 RSIM, +60 swap/calendar, +30 benchmarks | 2 |
| **R1.4 Verdict + e-processes** | `verdict(register, family\|all, tier)`: Holm over family-versions on portfolio series; the paired benchmark excess; the ±10% plateau (re-homed `plateau.py`) as a **descriptive** check over the fixed combination's members; the evaporation curve (dev → V → forward, R1-D). No CPCV/PBO on the R-1 path (R1-A R1A-2); PBO is kept only for explored families. `eprocess.py`: E1 edge, E2 kill, E3 cost gap (R1-A R1A-6..8). **Calibrate every stage's FPR and power on the lab first** | R1.1–R1.3 | +~120 verdict, +~50 e-process, +~150 tests | 1–2 |
| **R1.5 Data** (parallel from R1.1) | Hourly bid + ask candles for the 30 instruments, 2012–2025: **≈ 10,080 files, ≈ 0.1–0.2 GB, a few hours** (R1-B; measure one file first). **No new ticks:** they would add ≈ 33 GB and 96k files, and are not needed. Onboard 22 instruments: `instruments.yaml` metadata, exchange-anchored calendars, cost classes, swap. The owner confirms instrument availability with `scripts/download_dukascopy_s3.py check` | owner go on the universe (§5 D5) | config + ~20/instrument of §13 tests | 1–2 |
| **R1.6 Engine parity + position policy** | The forecast → combined target position in `core/` (A7); risk sizing, risk budget ÷ stop with a vol target (SYNTHESIS #11; GAP-P12D-61); the per-symbol execution clock in the runtime; the orchestrator drives the target through the venue stop; the harness uses the production exits (retiring the harness-only 48 h `max_hold`). Reconcile RSIM with the engine on hourly bars-as-ticks (VAL R1, R2, R4–R6; R3 becomes an identical target series). The demo logs replay decisions beside live ones | R1.3, Track A's runtime | +~300 (−~200 harness duplication) | 2–3 |
| **R1.7 Retire** (`git mv` to `archive/`) | QIEA (291), `evolve_step.py` (117), `fitness.py` (256, after the indicator move), ParamLibrary staging (~92), genome and gene types (~90 est.), the NVMA router (keep the veto, ~120; retire ~500), `regime_labels.py` (197), MR/SCALP/PAIR + the conviction pipeline (~105 + 92), `marginal_alpha.py` (73), the fragmenter + VenueQuality (120 + 28) | R1.6 + §4 ratified | **≈ −1,400 measured to −1,760 with estimates (prod), ≈ −1,490 test** (P3 row 8) | 1 |

**Net:** ≈ +1,700 added (lab ~800 with tests; register, verdict and e-process ~480; rules, RSIM and costs ~390;
parity ~300) against ≈ −1,400 to −1,760 production and −1,490 test lines retired. **Net production change: about
−600 to −1,000 lines** out of 7,645 (measured at BASE). One search engine is replaced by one register, and a
smaller engine grades the code it trades.

**The first real-data look happens only after R1.0–R1.4 are green on the lab.** Each earlier look spends a
budget of about 2–3 (C1) and buys nothing.

---

## 3. The experiment plan

### 3.1 The pre-registered slate (builds on ARC §4; every item LLM-originated → falsify on history, credit forward)

| Rank | ID | Family | The fixed combination (literature parameters) | Instruments | Clock | Standard |
|---|---|---|---|---|---|---|
| 1 (**conditional on the swap regime**, §5 D9) | **D1** | TREND | EWMAC (16,64), (32,128), (64,256) on 17:00 New York closes. σ = 25-day EWMA of daily changes. Scalars **fixed on the synthetic null** (4.66 / 3.26 / 2.28) and spending zero looks. Cap ±20. **Equal weights across speeds** (FDM ≈ 1.09). Instruments class-equal, then equal within class (IDM ≈ 2.4–2.5). A speed is dropped per instrument when its cost, **including swap**, exceeds ⅓ of the expected pre-cost SR. Breakout N = 40/80/160 and the MOP-12m sign are **members of this family**, not families: they correlate 0.95 and 0.77 with the matching EWMAC speed (R1-B, sim) | 23 explored | decide 17:00 New York; execute FX 17:05, others 18:10 New York; no rebalance after 14:30 on Fridays | replication + Holm |
| 1b | D2 (a registered version of D1) | TREND | D1 flat while \|f\| < 5, to cut swap-days | same | same | a family-version: counts in K |
| 2 | **D3** | SEASONAL | Turn-of-month index long, T−1 close → T+3 close | US500, US30, UK100, JP225, EU50, AUS200 | daily | replication |
| 3 | ARC H5 | FLOW | Month-end FX hedging flow into the 4 pm London fix | FX explored | intraday windows | replication |
| 4 | ARC H6 | FLOW | Tokyo fix: USDJPY into 09:55 JST on gotobi days | USD_JPY | intraday | replication |
| 5 | ARC H1 / H12 | IM | Index, gold and oil intraday momentum into the close | **US500, US30, UK100** (GER40 and US100 are held out), XAU, UKOIL | 1-minute bars | replication |
| 6 | ARC H3 | REV | Index 1-day reversal after large down days | explored indices | daily | replication |
| ctrl | ARC H10 | CONTROL | Pre-FOMC drift: a **negative control**, expected null after 2015 | US500 | daily | must FAIL |

- **Rejected,** with evidence (R1-B):
  - carry as a return source (confiscated at FTMO; kept as a cost term);
  - FX value (a CPI dependency for ~7 bets);
  - cross-sectional FX momentum (needs ~48 currencies and is cost-sensitive; Menkhoff et al. 2012 (a));
  - breakout as a separate family.
- **Rejected innovations** (R1-D §2.1), each with a revival condition:
  - meta-labeling;
  - Hedge or online allocation (−0.18 SR against equal weights when the sleeves are equally good; sim);
  - vol-managed timing;
  - soft-regime weights;
  - ML forecasters (at most one pre-registered challenger later);
  - LLM trading agents;
  - time-machine LLMs.
- **Adopted innovations:**
  - pooled fixed rules;
  - unfitted ensembles;
  - an LLM as an out-of-band proposer only.

### 3.2 The data segments and the looks budget

- **Development:** 2012–2023 × the 23 explored instruments, on the expanding walk-forward.
  - **≤ 3–5 family-versions graded on 2012–2023 in the first cycle.** R1-A: certifying a per-instrument net SR of
    0.3 takes 8.4–13 years at K = 1 on 20–40 instruments, and 16–25 years at K = 10.
  - **≤ 3 registered looks per family.**
  - ARC's E/V split is **not** used for fixed combinations, which have no training step.
  - An **explored** family (novel, or with a grid wider than coarse) uses E (2012–19) / V (2020–23) and a declared
    grid with max-t.
  - This settles SYNTHESIS L14, subject to the owner (§5 D6).
- **Families entering development: ≤ 5 a quarter** (R1-D; ARC's 20 would spend the looks on noise).
- **Engine:** ≤ 3 confirmations per family, Bonferroni.
- **Held-out instruments** (AUD/NZD, NZD/USD, CAD/JPY, XCU/USD, GER40, US100, USOIL): never explored; graded once
  per assembled portfolio; kill-only.
- **The holdout:** 2024–25 × every instrument, once, kill-only.
- **Synthetic:** unlimited; never enters a real-data verdict.

### 3.3 Kill criteria (pre-registered; each writes a register line)

- **VAL K1–K6 stand:** budget; PBO > 0.5 (explored families only); harness integrity; holdout; forward; LLM
  provenance.
- **K4 is recalibrated:** kill at **t < −0.5**, not at SR̂ < 0. A below-zero rule wrongly kills 18–32% of real
  edges (R1-A).
- **Added:**
  - **K7:** cost including swap > ⅓ of the pre-cost SR at G2 → kill before any further look.
  - **K8:** a graveyard-motif or `variant_hash` duplicate is refused at registration.
  - **K9:** a graded number without a register row voids that family's results since its last clean row.
  - **K10:** the forward kill bettor E2 ≥ 20 against μ_claim = SR̂_dev / 2 → kill. At ≥ 5: freeze scaling.
  - **K11:** a demo day beyond −6σ*, or a fill beyond 5 modelled costs, is a **tripwire** that voids the running
    certification. It is never clipped silently: silent clipping gave 43% false "inside-band" certifications.
  - **K12:** live and replay decisions differ on the same feed → halt the family (a look-ahead or parity bug).
  - **K13:** the paired excess over the passive benchmark is ≤ 0 at G2 → kill.

### 3.4 The demo incubation protocol (G4)

- **Scope:** ONE pre-registered sleeve at minimum size first (GAP-P12D-68 item 9). D1 runs on the venue's
  explored instruments, and **on a swap-free account if one is lawfully available** (§5 D9). Add sleeves only after
  E3 certifies.
- **The bettors:**

  | Bettor | Input | Null | Verdict |
  |---|---|---|---|
  | **E1 edge** | the book's daily net P&L as a fraction of equity; W = the mean over λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8} of Π(1 + λ·max(r/(6σ*), −1)), with σ* the declared vol target | mean ≤ 0 | W ≥ 20 = "edge shown"; W ≥ 100 = "strong"; else "not yet" (**never "failed"**) |
  | **E2 kill** | the same bettor on (μ_claim − r) | mean ≥ SR̂_dev/2 | ≥ 5 = freeze scaling; ≥ 20 = kill |
  | **E3 cost** | paired per fill: d = realised − modelled cost (shadow replay through the same C8 `CostModel`), in modelled-cost units | the band ±25% | breach at ≥ 20; certify when both one-sided nulls ≥ 20; 5× tripwire |

- **E1, E2 and E3 together are about 45 lines** (R1-A). The owner may read them every day.
- **The timeline to expect:**
  - weeks 0–4: plumbing, with live = replay;
  - weeks 3–28: E3 certification;
  - "edge shown" at a median of 2.4–3.0 years if the true portfolio SR is 1.5.
- **Rejected:**
  - a daily-peeked t-statistic: 38–47% FPR;
  - a Gaussian mSPRT with an assumed σ: 20% FPR at 1.5× the declared vol.

---

## 4. Spec amendment drafts (OLD/NEW; proposals only; each needs owner ratification)

**How to read these drafts.**
- The OLD text is verbatim at BASE, with its `file:line`.
- The NEW text is a proposal. The local ACIS lead re-drafts it under ACIS governance: a version bump, a
  changelog line, and the dual audit.
- None of this changes a guardrail value, the equity floor, or HALT/veto semantics.
- A7 touches CLAUDE.md engineering rule 5 ("the conflict-resolution table … is law"). It is therefore marked
  **owner-only**.

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
>   set's holding period, measured on the lab). A daily EWMAC 16/64 holds ~47–54 days on average (R1-D receipt,
>   P3 row 11).
> - Where any CPCV stage is used (explored families only), it must also **purge** the longest lookback (256 days
>   for EWMAC(64,256)).
> - **Why (C1, VAL; sim):** the 2-year rolling selection realised 0.02 of a 0.65 edge; the expanding one realised
>   0.52–0.72 of a 1.22 edge.
>
> The only legitimate selection is **among the members of a declared search space**, registered before the
> first look (A2). The validation design is not an optimisation target.

**Code delta:** `oos_plan.py`: `train_start = max(DATA_START, first_validated_day)`, and an embargo argument
derived from the rule set's measured holding horizon. About ±10 lines.

**Falsifier:** on the lab, a planted pooled trend at a known Sharpe realises less under the expanding window than
under the rolling one.

### A2 — The `passed` gate: DSR ≥ 0.95 over ≥ 2 trials → a register-aware verdict  [ratified 2026-09-15, GAP-P12D-16]

**OLD** (`specs/ACIS-09-BACKTEST_VALIDATION.md:151`, C-BT-11, excerpt):
> The report carries `trial_count` and the Deflated Sharpe (Bailey & López de Prado 2014, pinned by test to the
> paper's numerical example), and `passed` requires a Deflated Sharpe ≥ 0.95 over at least 2 trials, so a report
> that does not record its trials cannot pass (owner-ratified 2026-09-15, GAP-P12D-16). The trials are the
> candidate champions at each fold's selection — every instrument × regime QIEA evolved — each contributing its
> holdout per-trade Sharpe; …

The code is `tests/backtest/report.py:112-121` (`trial_count >= _MIN_TRIALS`, `deflated_sharpe >= DSR_MIN`,
`all(targets_met.values())`).

**NEW:**
> **C-BT-11 (v2, the register-aware verdict).** A graded number exists only if the one evaluation entry point
> wrote its register row first (exclusive create). A candidate's verdict is computed over the whole register.
>
> 1. **The unit of test is a registered family-version.** It is a **fixed pooled combination** of its members,
>    with no argmax inside it, graded on the family's **portfolio** daily net series. It is never graded on the
>    stacked instrument × day panel. Its declared search space is hashed before the first look.
> 2. **Stage A — development verdict.** Holm over the K registered family-versions:
>    - the family passes if the one-sided lower bound of its expanding-WF OOS Sharpe is > 0, i.e.
>      SR̂ > z_{1−0.05/K}/√Y;
>    - AND its paired excess over the registered passive benchmark is > 0;
>    - AND its net is > 0 at 2× the modelled cost, including swap.
>
>    **Explored families** (a declared grid, with selection) instead use max-t over the declared grid, plus
>    PBO ≤ 0.20.
> 3. **Stage B — engine confirmation.** One expanding-WF run of the frozen family through the engine, on hourly
>    bars as ticks. It is graded on daily OOS net returns, with Bonferroni over ≤ 3 registered engine looks. The
>    engine's OOS Sharpe must not be significantly below RSIM's.
> 4. **Stage C — kill-only.**
>    - The held-out instruments, residualised on the explored set's class factor, kill at t < −0.5.
>    - The 2024–25 holdout, once, kills at t < −0.5.
> 5. **Stage D — forward.** The E1/E2/E3 bettors (PLAN §3.4). For LLM-originated families this is the only stage
>    that can credit a pass (master §5.6).
>
> `passed` in `ValidationReport` means stage A and stage B passed and stage C did not kill. It no longer contains
> the Deflated Sharpe or the §14 `annual_sharpe > 1.5` row (A6).

**Code delta:**
- `report.py`: drop the `deflated_sharpe >= DSR_MIN` and `trial_count` conditions, and take the stage-A verdict
  as an input. Net about −10 lines.
- `deflated_sharpe.py` stays as an informational column until the owner retires it.
- The verdict module is about +120 lines.

**Falsifier:** on the lab, under an adaptive researcher (200 runs, ~6 families), the verdict's FPR exceeds 5% plus
two standard errors. R1-A measured 1.5%. Or its power at a realistic planted edge falls more than 15 points below
the declared-grid max-t's.

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
> The **trend family is the required canonical implementation for v1.** It is a fixed, equal-weight combination of
> EWMA-crossover forecasts at three speeds, (16,64), (32,128) and (64,256), on 17:00 New York daily closes. Its
> members are:
> - the breakout form (40/80/160);
> - the MOP-2012 12-month sign, as the literature-fixed **baseline variant**, run raw first.
>
> Parameters are pooled across instruments. A speed is admitted per instrument only if its cost, **including the
> venue's swap**, is ≤ ⅓ of its expected pre-cost Sharpe (Carver's speed limit, (b), verified at C4 §1 #8).
> Forecasts are scaled, capped and combined with the other families into **one target position per instrument**
> (A7). No family holds an instrument's position slot by itself.

**NEW** (ACIS-04 §6.6): TSMOM's 63/126/252 vote stays as one registered member of the trend family, with
- the §8.6 disaster stop as a broker-side stop;
- exit by target-position change;
- no harness-only `max_hold` (C3; SYNTHESIS #14).

The "every tradeable regime" row stands (A7).

**Code delta:**
- `core/signals/canonical.py` (114 lines) becomes a forecast function inside `rules.py` (~150 lines for 3–5 rule
  functions).
- This also resolves GAP-P12D-71: carry enters as the venue's swap in C8, not as a return omission.

**Falsifier:** on the lab, the pooled multi-speed family captures a planted multi-speed trend at a lower realised
fraction than the TSMOM vote alone. Or, on development data, its stage-A statistic is below the faithful 12-month
sign's, on the same instruments and costs.

### A4 — QIEA per-regime × per-instrument evolution → pooled, fixed rule parameters  [master §5; ACIS-03]

**OLD** (`ACIS_SPEC.md:171`, master §5):
> Quantum-inspired binary chromosome evolution maintaining a **regime-indexed parameter library** (best `ParamSet`
> per RegimeType).

**OLD** (`specs/ACIS-03-QIEA_OPTIMIZER.md:21`, §1 Purpose):
> Evolve, per regime, the best strategy `ParamSet` using a Quantum-Inspired Evolutionary Algorithm, and maintain a
> **regime-indexed parameter library** the fast loop reads.

**OLD** (`ACIS_SPEC.md:93`, the §2 table row):
> | Regime shift + no evolved params for new regime | `tradeable=False` until QIEA completes evolution |

**NEW** (master §5, retitled **RULE PARAMETERS**):
> - Every rule family has **≤ 3 free parameters**, fixed at literature values or on the synthetic null (spending
>   zero looks).
> - A family is a **fixed combination** of its members. No member is selected on data.
> - Parameters are **pooled across instruments**. They may differ per instrument only through a declared,
>   pre-registered cost filter.
> - There is no per-regime and no per-instrument parameter library, and no evolutionary search.
> - An **explored** family may declare a grid (a ±1-step grid on ≤ 2 parameters, ≤ 9 members). Its search space is
>   hashed before the first look, and it is graded by max-t over that declared grid (A2).
>
> **The staging rule survives verbatim for any parameter change.** No live parameter changes mid-session or with
> open positions, and promotion happens only at a valid session boundary (C1/C2 unchanged). C8 (net of costs) and
> C9 (positive expectancy) bind every member.

**NEW** (the §2 row):
> | Instrument has no registered, validated rule set | `tradeable=False` |

**Retired to `archive/`** (a `git mv`), measured at BASE (P3 row 8):
- `core/optimizer/qiea.py` (291);
- `tests/backtest/evolve_step.py` (117);
- `core/optimizer/fitness.py` (256), after its indicator functions move;
- ParamLibrary staging (≈ 92);
- the genome (≈ 90 est.).

`plateau.py` (74) is re-homed as a descriptive check.

**Falsifier:** on the lab, a pooled fixed rule realises a lower fraction of a planted edge than QIEA-per-regime
at an equal registered look count. (C1, C4 and R1-A predict the opposite.)

### A5 — The universe: 8 instruments → 30, with 7 locked held out  [ratified 2026-07-22]

**OLD** (`tests/backtest/OOS_VALIDATION.md:22-26`):
> - **Data:** `2012-01-01 → 2026-01-01` (14 yr). **Enabled universe RATIFIED
>   2026-07-22 (owner): 8 instruments** chosen for genuine cross-sectional
>   diversification (the honest path to a trustworthy Sharpe, GAP-SP12E-01), not more
>   USD-correlated majors: …

**NEW:**
> - **Research universe: 30 instruments, all quoted by FTMO, all with Dukascopy history from ≤ 2013** (R1-B §2.5).
>   - FX 16;
>   - metals: XAU, XAG, XCU;
>   - indices: US500, US30, UK100, JP225, EU50, AUS200, GER40, US100;
>   - energy: UKOIL, NATGAS, USOIL.
> - **Excluded:**
>   - XPT (Dukascopy from 2021) and US2000 (from 2018);
>   - softs (FTMO Swing leverage 1; history from 2017);
>   - exotics (markups of 10–135 points).
> - **Held out, locked: AUD/NZD, NZD/USD, CAD/JPY, XCU/USD, GER40, US100 and USOIL.** They are drawn by
>   `sha256("ACIS-R1-holdout-2026-09-25|" + symbol)` per class (FX 3, metal 1, index 2, energy 1). The 8
>   instruments already on disk are forced into the explored set.
>   - Re-salting after any real-data look is forbidden.
>   - They are never explored, graded once per assembled portfolio, residualised, and kill-only.
>   - Their power is 54–59% at a per-instrument SR of 0.3 (R1-A, derived).
>   - They are clean of the project's looks, **not** of the LLM's knowledge; only forward data is fully clean.
> - **The live-enabled universe** is the subset that passed the rung ladder (§5.7) and that the venue quotes.
> - "Genuine diversification" is measured as **effective breadth**, IDM = √(N/(1+(N−1)ρ_P&L)), not as a count.

**Falsifier:** the realised ρ_P&L of the chosen universe, measured on exploration data only (pre-2012 or
synthetic), is above 0.3. Then 20–40 instruments buy < 1.8×, and the look budget halves (R1-A R1A-4).

### A6 — §14: the targets that contradict a daily-horizon rule set  [master §14; owner-ratified targets]

**OLD** (`ACIS_SPEC.md:361, 363, 367`):
> | Annual Sharpe | > 1.5 | > 2.5 |
> | Win rate | > 48% | > 58% |
> | Avg trade duration | 30min–48h | — |

The code is `tests/backtest/report.py:34-39`. It also hard-codes positive months > 70%.

**Why they contradict the direction and the spec itself:**
- **A planted SR 0.87 daily rule fails all three trade-shape rows:** win rate 0.18, average hold 53.5 days,
  positive months 52% (R1-D receipt; P3 row 11).
- **Win rate > 48%** contradicts master §5.6's own "published trend-following wins ~35–48% of trades"
  (`ACIS_SPEC.md:213`).
- **Annual Sharpe > 1.5** cannot be certified on this history. At 10 OOS years and K ≤ 10 the honest hurdle is
  0.81 (R1-A).

**NEW:**
> §14 becomes the claim ladder of PLAN_R1 §6: the stage-A Holm bound, the paired benchmark excess, net > 0 at 2×
> cost, the stage-C kills, E3 certified, E2 silent, and E1 ≥ 20 for "edge shown".
> - Max DD < 15% and SPX correlation < 0.25 are kept. The drawdown row is guardrail-adjacent and owner-only.
> - Win rate, profit factor, duration and positive months are **reported, never gated** (the §5.6 expectancy law).

**Falsifier:** none statistical. This is an owner decision about what "works" means.

### A7 — Regime as a veto only, and forecasts net instead of "opposite ⇒ discard both"  [master §2, §4, §5.5; CLAUDE.md rule 5 — OWNER-ONLY]

**OLD** (`ACIS_SPEC.md:94`, the §2 conflict table):
> | Two strategies signal opposite directions, same instrument | Discard both. Ambiguity = no trade. |

**OLD** (`ACIS_SPEC.md:195`, excerpt):
> Concurrent strategy modules (regime-gated): **Trend Following** … in trend regimes; **Breakout** … in breakout
> regimes; **Mean Reversion** … in ranging/mean-reverting regimes; …

**NEW:**
> - Rule families emit **forecasts**, not signals. The per-instrument forecasts are combined with fixed,
>   pre-registered weights: equal within a family, then equal risk across families (handcrafting). The result is
>   multiplied by the FDM and capped.
> - The combined forecast sets **one target position** per instrument, with a 10% no-trade buffer, executed on the
>   per-symbol execution clock.
> - **Ambiguity still means no trade:** a net forecast inside the buffer places no order.
> - NVMA keeps **only its safety veto**: `tradeable=False` on ILLIQUID, MACRO_EVENT or UNCLASSIFIED, a spread
>   above 3× the session median, or a dead market. Regimes no longer gate families or key parameters.
> - Any regime conditioning must enter as a **registered family-version**. R1-D (I7) rejects a soft-regime layer
>   for now; it is revivable if a pre-specified 2-state model improves the verdict on the held-out instruments.

This retires `DISCARD_OPPOSITE` as the lock that C3 measured holding one slot 97–99% of the time.

**Why it is owner-only:** "opposite ⇒ discard both" is conflict-table law (CLAUDE.md rule 5). Netting is
risk-reducing relative to independent slots, and HALT/veto semantics are untouched. It still changes a law, so the
owner rules.

**Falsifier:** in the lab, the netted book has a higher turnover-adjusted cost per unit of captured edge than the
discard-both book, at equal registered looks.

---

## 5. Owner decisions (each with a recommendation)

**The single most consequential decision is D9.**

| # | Decision | Recommendation | Why | If declined |
|---|---|---|---|---|
| **D9** | **The swap regime of the account.** At FTMO's published swaps a pooled trend book nets **−0.15 to +0.32 SR**; swap-free, **+0.32 to +0.79** (R1-B, derived with (a) inputs). Ask FTMO and E8 openly about swap-free terms (draft below), **without misrepresenting eligibility** (e.g. an Islamic-account criterion), which would breach their terms | **Ask now, before R1.5 commits the universe.** Choose the venue and account type that makes D1 viable, or rank D1 below ARC's H3 and lead with flat-most-of-the-time families (D3, H5, H6) | Swap is ~10× the trading cost of a medium-speed rule | Slow trend is likely net-negative on indices and metals at FTMO |
| D1 | Ratify **A1**, the expanding window | **Yes** | C1 and VAL measured independently; GAP-P12D-67 | The rolling window throws most of any real edge away |
| D2 | Ratify **A2**, the register-aware verdict: families as fixed combinations, Holm, benchmark pairing and kill-only stage C | **Yes.** This **supersedes the local delegated D1 = C + D (CPCV + PBO) for fixed families**, keeping it for explored ones (R1-A R1A-2: 1.5% FPR and 64–69% power, against 45–58%) | The as-built gate has FPR 0% and power 0.3% at 1.22 (C1; GAP-P12D-37). Counting runs alone leaks 10–16% under adaptivity | `passed` passes nothing; or a union test leaks under hill-climbing |
| D3 | Ratify **A3**, the trend family replacing "required canonical TSMOM" | **Yes**, with MOP-12m kept as the baseline member | C3 lockout; GAP-P12D-71; TSMOM is 0.77-correlated with EWMAC(64,256) | TSMOM keeps the slot and the arena stays locked |
| D4 | Ratify **A4**, retiring QIEA and per-regime/instrument parameters | **Yes** | C4; R1-D (−1,400 measured) | The search outruns any register |
| D5 | Ratify **A5**, the 30-instrument universe and the **7 held-out instruments as drawn** | **Yes, and freeze the salt now.** The owner confirms availability with `download_dukascopy_s3.py check` | Held-out instruments are one of the two uncontaminated tests (R-1 item 6) | Keep 8: no held-out set, and N_eff ≈ 2–3 |
| D6 | One development tier (2012–2023) for fixed families; E/V only for explored ones | **Yes** | Settles SYNTHESIS L14; splitting halves t² (C1) | Power roughly halves for the core family |
| D7 | Ratify **A6**: §14 trade-shape rows reported, not gated; the claim ladder in §6 | **Yes** | A planted SR 0.87 rule fails every shape row | Every daily-horizon rule fails §14 whatever its edge |
| D8 | Ratify **A7** (**owner-only**: conflict-table law) | **Yes** | C3 lockout; GAP-P12D-68 items 1, 3 | Slot contention stays |
| D10 | What earns a paid challenge | **After G2 + G3 pass, E3 certified and E2 silent for ≥ 3 months, with human sign-off. "Edge proven" only at E1 ≥ 20.** The challenge is a capped-loss forward test, never evidence (C1 §2.8; GAP-P12D-62) | E1 ≥ 20 takes 2.4–3 years even at SR 1.5 | Waiting for E1 means ~3–7 years before any challenge |
| D11 | Where research compute runs | **The laptop is enough:** a one-time bar build of ~1–1.5 days (resumable), then seconds per run. Keep engine confirmations off the power-losing laptop (GAP-P12D-76) | Measured RSIM timing (P3 row 11) | — |
| **D12** | **Variance-matched planting** in the BASE tick generator (R1-C C-2) | **Yes, together with C-1,** and **re-state** every recorded synthetic verdict, GAP-P12D-49's ladder included: it was made on a demeaned, 3.3×-volatility planted market (P3 rows 5, 12) | "Planted passes, null fails" is confounded by the volatility level; the oracle SR is ~157 | The positive control keeps flattering any long-volatility rule |
| D13 | The LLM's role | **An out-of-band proposer of declarative plans only**, with origin and cutoff in the register; K8 duplicate veto (R1-D P11) | FINSABER (a): LLM advantages "deteriorate significantly"; Gençay (b): honest evaluation rejected every LLM-discovered strategy | — |

**Draft questions for the owner to send** (merge into SCO's drafts; send nothing on the owner's behalf; ask
openly):

> "For an algorithmic account holding positions for days to weeks on FX majors and crosses, gold and index CFDs:
> (1) Is a swap-free account available to a trader who does not request it on religious grounds, and on which
> instruments? Is there an administration fee or a maximum holding period? (2) How often do the swap points
> published at ftmo.com/en/symbols change, and is their history available? (3) How are the USOIL and UKOIL swaps
> computed in account currency? (4) Is the $5 commission charged per side or per round turn?"

---

## 6. The bar: "bleeding edge" versus "a joke" (measurable acceptance criteria)

**Bleeding edge** means that it survives honest out-of-sample evaluation. Each criterion is computable from the
register and the forward record alone.

| # | Criterion | Threshold | What it protects against | Evidence |
|---|---|---|---|---|
| B0 | **Machinery proven first.** On the lab: planted detected within 2 se of theory power; null false-detect ≤ 5% + 2 se; leaky oracle refused by structure; RSIM ≡ engine (R1–R6); Cont probe set passes; planted/null variance ratio within 1 ± 0.05 | all pass at `recon_commit` | A grader that is itself wrong (GAP-P12D-37; C2; the 3.3× confound) | P3 rows 5, 6, 12; VAL §7–8 |
| B1 | **Every number registered, and the search space declared.** One entry point; claim row first; aborted runs count; the declared-space hash exists before the first look | 0 exceptions (K9) | Keep-best-of-20: 44–53% FPR (C1); union-of-runs under adaptivity: 10–16% (R1-A) | C1; R1-A; P3 row 13; Gençay §3.2 (b) |
| B2 | **Development verdict.** Holm over K family-versions, each a fixed pooled combination, on the expanding-WF **portfolio** daily OOS series: lower bound > 0 | **SR̂ > 0.81** at K ≤ 10 and Y = 10 (0.74 at K = 5); 72% (80%) power at a true 1.0; measured FPR 1.5% | Selection; the panel fallacy (9.5–32%) | R1-A R1A-2, R1A-10 (sim) |
| B3 | **Beats its passive benchmark** (paired excess > 0), and **net > 0 at 2× cost including swap**, with cost ≤ ⅓ of the pre-cost SR | all | Long-drift premium sold as trend; the swap markup | R1-D P6; R1-B; Carver (b) |
| B4 | **Engine realises what RSIM measured** (not significantly below, one-sided 5%) | pass | A research-simulator artefact | VAL stage 3 |
| B5 | **Held-out instruments and the 2024–25 holdout, once, kill-only** | kill at t < −0.5 (holdout: SR̂ < −0.35); residualised FPR 2.5–3.2%; the raw test (14.5–24%) is never used | The two contamination-free historical tests | R1-A R1A-5 (sim); P3 row 13 |
| B6 | **Live = replay** on the demo feed | exact decision match | A look-ahead or parity bug that no historical test can catch | R1-A (reasoned) |
| B7 | **Forward cost certified** (E3) | both one-sided nulls at W ≥ 20; median 102–166 fills | Cost fantasy (GAP-0001) | R1-A (sim) |
| B8 | **The forward kill never fires** (E2 against SR̂_dev / 2) | W < 5 | Believing a backtest that forward time contradicts | R1-A (sim) |
| B9 | **"Edge shown"** (the only credit an LLM-originated family can earn) | E1 W ≥ 20 (α = 0.05, valid under daily looks); "strong" at W ≥ 100 | Daily peeking (38–47%); contamination (GAP-P12D-66) | P3 rows 1, 2 (independently re-implemented) |

**The markers of "a joke"**, any one of which fails the build:
- a quoted in-sample number;
- a best-of-N without its declared search space;
- a pass on the stacked panel;
- a gate that passes nothing, or everything, on the lab;
- a positive control that differs from its null in volatility;
- an LLM-originated family credited on pre-cutoff data;
- a demo "proof" of edge in months;
- a clipped tripwire.

**The claim ladder:**
- B0–B5 → "validated on history (kill-tested)";
- + B6–B8 → "fit to trade at minimum size / challenge-eligible" (human sign-off);
- + B9 → "edge shown forward".

Nothing weaker earns those words.

---

## 7. Disagreements and resolutions

| Point | Positions | Resolution |
|---|---|---|
| Stage A: CPCV + PBO, SPA over the union, or Holm over fixed combinations | The local lead delegated D1 = C + D (CPCV + PBO). C1 proposed SPA over the registered union. R1-D: DSR + PBO + an absolute CI (Gençay). R1-A: the union test leaks 10–16% under adaptive iteration; Holm over fixed combinations is 1.5% with higher power | **R1-A for fixed families** (sim R = 400, direction reproduced at R = 80 by the lead, P3 row 13; logically sound: adaptivity makes the tested set data-dependent). Gençay's absolute-CI requirement **is** the Holm lower bound. PBO and CPCV remain for explored families. Owner D2 |
| The generator fix | C3 / SYNTHESIS #8: "demean only the planted drift". R1-C: that is itself a bridge and costs ~45% of a slow rule's planted Sharpe | **R1-C** (P3 row 7) |
| The E/V split vs one tier | ARC and R1-B (slate gates) vs R1-D, R1-A and C1 | **One tier for fixed families; E/V for explored ones** (owner D6) |
| C1's frontier | C1 9.3 years (SR 1, K = 1); R1-A 6.2 years on daily data | **R1-A** (derived; matches VAL §5.1) |
| The holdout kill threshold | VAL K4: SR̂ < 0. R1-A: that wrongly kills 18–32% of real edges | **t < −0.5** (R1-A, sim) |
| Residualising the held-out set | VAL §2.6: residualise to stop factor leakage. R1-A: residualising also strips a common-factor edge (12–17% power) | **Residualise, kill-only;** a factor-borne edge can be credited only forward |
| Carry | ARC H8 and master §5.6 carry in the canon. R1-B: confiscated at FTMO | **A cost term** at FTMO; revisit on a fair-swap venue (D9) |
| The held-out draw | R1-B's draft (AUD/USD, EUR/GBP, XAG, …) vs its final | **The final:** on-disk instruments forced explored (P3 row 9) |
| Families per quarter | ARC ≤ 20; R1-D ≤ 5 | **≤ 5 into development;** R1-A's K arithmetic supports ≤ 3–5 per cycle |
| Breadth's value | R-1 item 2 ("breadth over length") | **Confirmed, but mostly for held-out capacity and against the 2 enabled instruments.** Against the 8 declared, it cuts years by only 1.2–1.6× (R1-A) |

---

## 8. Verification status (P3) and what could not be verified

- **P3:** 13 of 13 load-bearing claims **CONFIRMED** (`P3_R1_LEAD_VERIFICATION.md`):
  - 2 by independent re-implementation (the e-process FPR and its timing);
  - 1 at the primary source (the FTMO swap JSON);
  - 3 by independent arithmetic or `wc -l` (breadth, line counts, the planted-volatility closed form);
  - 5 by byte-identical receipt re-runs;
  - 1 by a reduced-replication re-run (the register verdict, R = 80);
  - 1 by argument (the sign-flip fix).
- **Not verified by anyone:**
  - E8's own pages (blocked for R1-B);
  - whether FTMO's commission is per side;
  - FTMO's oil swap method;
  - Carver's published forecast scalars (R1-B fixed them on the synthetic null instead);
  - the hourly-candle file layout and size (the owner measures one file);
  - the within-FX correlation of trend P&L (an assumption, 0.25–0.5);
  - the live-vs-replay detector (reasoned, not simulated);
  - the lab adapter through the real harness (designed, not built);
  - R1-A's researcher simulation used Gaussian returns only.
- **The main residual risk is contamination.**
  - Every rule here is LLM-originated, and the held-out instruments are clean of the project's looks, not of the
    model's memory. The honest test is the register once, the held-out set and holdout once, then forward.
  - A lab that is too easy, or a lab artefact learned as an edge, is contained by C-10: the lab grades machinery,
    never edge.

---

## 9. Proposed ledger entries (no IDs; the local lead mints them)

| # | Entry | S / L | Proposed status | Source |
|---|---|---|---|---|
| 1 | Counting runs is not enough under adaptive iteration: the union-of-runs test passes noise 10–16%; the search space must be declared and hashed before the first look, and families graded as fixed combinations | critical / high | open [spec — owner ratification] | R1-A; P3 row 13; **extends** GAP-P12D-64 |
| 2 | The BASE planted market is 3.3× the null's daily volatility (oracle SR ~157); every recorded synthetic verdict is confounded by it | high / certain | open [spec — owner ratification] (it moves recorded runs) | R1-C; P3 row 12; relates to GAP-P12D-49 |
| 3 | The synthetic null is a bridge (demeaning) and the permuted kind too; two unit tests encode the bug | high / high | open [impl] | R1-C; extends SYNTHESIS §6 #10 |
| 4 | Independent per-instrument intraday bridges plant a spurious pairs edge (t 6–9) | medium / high | open [impl] | R1-C C-4 |
| 5 | The C8 financing model charges a flat 1% admin fee; FTMO's markup is 1.3–5.0%/yr per side, and swap dominates a slow rule's cost | high / certain | open [impl] | R1-B; P3 row 4 |
| 6 | At FTMO's swaps a pooled trend book is marginal-to-negative; the account's swap regime is an owner decision | high / high | open [owner decision] | R1-B; PLAN §5 D9 |
| 7 | A 17:00 New York rebalance breaks FTMO's gap rule on Fridays and falls inside the index, metal and oil break: execution needs a per-symbol clock | high / certain | open [impl]; **extends** GAP-P12D-58 | R1-B §2.7 |
| 8 | §14's trade-shape rows (win rate, duration, positive months) fail any daily-horizon rule whatever its edge | high / certain | open [spec — owner ratification] | R1-D; P3 row 11 |
| 9 | The holdout kill at SR̂ < 0 wrongly kills 18–32% of real edges; use t < −0.5 | medium / high | open [spec — owner ratification] | R1-A |
| 10 | The registry stores counts, not return vectors, so no search-aware verdict is computable | high / certain | open [impl]; **extends** GAP-P12D-64 | R1-D D2 |
| 11 | `fitness.py`'s indicator functions are imported by `core/signals/indicators.py:17`: they must move before the kill list runs | low / certain | open [impl] | R1-D |
| 12 | The graded pooled test must use the portfolio series; a stacked-panel test passes a zero-edge rule 9.5–32% | high / medium | open [impl] | R1-A |
