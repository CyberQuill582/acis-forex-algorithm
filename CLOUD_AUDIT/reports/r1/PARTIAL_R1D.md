# PARTIAL R1-D — INNOVATION AND ARCHITECTURE (checkpoint 1, ~30 min)

- **Lane:** R1-D. **Model:** the system prompt names `claude-opus-5-5`; effort not observable from inside the session.
- **Fresh context:** yes; this lane saw only its brief, the prior reports and BASE.
- **BASE:** `974dbda`. **Date:** 2026-09-25. **Web used:** 8 of 40.
- **Status:** SUPERSEDED by the final `R1D_INNOVATION_ARCH.md` (§2.9 is the final "For PLAN_R1"; its numbers supersede the drafts below).

## First findings

1. **Gençay (arXiv 2608.27734): three things VAL did not use.** Grade (b), fetched at source 2026-09-25.
   - **Three failure modes need three instruments.** Quote (§7): "E3's large-budget find collapsed out of sample despite a
     low PBO, because its winner kept its rank among mostly losing candidates while losing its absolute edge, which the
     held-out confidence interval caught."
     - So a PBO ≤ 0.20 screen alone can pass a family whose best member has lost its absolute edge.
     - ACIS's verdict needs a DSR over the register's honest N, plus PBO/CSCV, plus an absolute out-of-sample Sharpe
       confidence interval. All three are needed; any one alone is not enough.
   - **The trial ledger is complete by construction, not by diligence.** Quote (§3.2): "every candidate the agent
     composes flows through the same evaluation entry point, which is what makes the trial ledger of Section 4
     complete by construction rather than by author diligence."
     - For ACIS: **one evaluation entry point.** The research simulator refuses to run without writing its register
       row first, and no other code path can produce a graded number.
   - **Strategies are declarative plans, not code.** Quote (§3.2): "look-ahead is inexpressible" when the feature registry
     excludes leaky features by construction.
     - For ACIS: a pooled rule is a small typed record (a family, a few fixed parameters, instruments, a clock), run by
       a fixed interpreter. This is the data-not-code pattern of ARC change 3, generalised.
   - **Breadth.** Quote (E5, 39 multi-asset ETFs, 9 held-out years): TSMOM "is positive in both windows ... and is still
     under-powered". Also: "Certifying moderate low-frequency edges requires decades or breadth". This is independent
     support for R-1 item 2.
2. **The agentic-trading surveys call for exactly the discipline R-1 already has.**
   - arXiv 2608.31041 (Hua et al., 2026), grade (b): "strong model or forecasting capability does not reliably translate
     into trading performance under live market conditions".
   - arXiv 2605.19337, §13.3, grade (b): "We therefore interpret the absence of negative results as a reporting limitation
     rather than as evidence that the design space is uniformly promising."
   - arXiv 2602.14233 (Kong, Lopez-Lira et al., 2026), grade (b): "only 26.8% acknowledge look-ahead bias, and
     survivorship bias appears in just 1.2% of studies" (164 main-conference papers, 2023–2025).
   - FINSABER (arXiv 2505.07078, KDD 2026 Datasets & Benchmarks, oral), grade (a): "previously reported LLM advantages
     deteriorate significantly under broader cross-section and over a longer-term evaluation."
   - **Verdict:** reject LLM-in-the-loop trading agents for ACIS. Adapt LLMs as out-of-band hypothesis proposers under
     the contamination rule (GAP-P12D-66). Detail in checkpoint 2.
3. **New architecture finding: the §14 trade-shape rows will fail R-1's rules whatever their edge.** This is an
   LLM-originated reading of the code and spec.
   - `tests/backtest/report.py:34-39` hard-codes three rows:
     - win rate > 0.48;
     - average duration 30 min–48 h;
     - positive months > 70%.

     `passed` requires all of them (`report.py:113-123`).
   - The spec contradicts itself here. `ACIS_SPEC.md:213` says "published trend-following wins ~35–48% of trades", while
     §14 (`ACIS_SPEC.md:363`) demands > 48%.
   - A daily-horizon pooled trend rule holds for weeks, so the 48 h duration cap fails it by construction. The only
     escape is the `_DURATION_CARVE_OUT` for TSMOM (`tests/backtest/metrics.py:19`).
   - **This is a sixth ratified item R-1 touches, and BRIEF §0.2 does not list it.** A synthetic receipt measuring these
     rows on a planted-edge rule is in progress.
4. **The kill list moved since C4.** Measured with `wc -l` at BASE `974dbda`:
   - `qiea.py` is 291 lines, not C4's 242, because the evaluation registry added 49;
   - `evolve_step.py` is 117, not 113.

   Under R-1, `fitness.py` (256) and `plateau.py` (74) also lose their reason to exist in the live path, because the
   research simulator takes over the plateau probe. The updated table comes in checkpoint 2.
5. **Registry direction (draft).**
   - Neither the BASE `attempts` table (`core/signals/provenance.py:92-95`: family, descriptor, time) nor BUILDER-2's
     look register can compute a search-aware verdict. Both store **counts**, not **return vectors**. (The look
     register is local WIP; its ledger entry is GAP-P12D-64.)
   - SPA/StepM, CSCV-PBO and e-BH all need each run's daily net-return series, aligned by date.
   - **Minimal delta:** one append-only run row, plus one content-addressed return vector per run. The full schema comes
     in checkpoint 2.
6. **Research-simulator cost sharing needs no vectorised cost model at the daily horizon.**
   - A daily pooled rule on 30 instruments makes about 10^3–10^5 fills per 14-year run.
   - So the research simulator can call the one scalar `CostModel.per_side_cost` (`core/optimizer/costs.py:52`) once per
     fill, by object identity. There is then no vectorised twin that could drift (the GAP-P12D-36 class).
   - Timing receipt in progress.

---

# CHECKPOINT 2 (08:10 UTC; brought forward at the lead's request): DRAFT "For PLAN_R1"

**Everything below is a DRAFT.**
- **Verdict grades:** marked (a)/(b)/(c) where a primary source has been fetched this session. **[pending]** means the
  verdict rests on my prior knowledge of that literature and will be quote-verified before the final report.
- **Line counts:** measured with `wc -l` at BASE `974dbda`, unless marked est.
- **Timing receipts:** `evidence/R1D/sim_rsim_daily.py` and `sim_rsim_daily.out.json`, synthetic only.

## D1. Innovation verdict table (draft)

| # | Candidate | Verdict | Why (one line) | Complexity | Falsifier (what makes us drop the verdict) | Grade |
|---|---|---|---|---|---|---|
| I1 | Pooled parameters (full pooling) with coarse robustness variants | **ADOPT** (this is R-1 itself) | Removes the per-instrument degrees of freedom C4 counted (43,200 evaluations per fold) | −(QIEA stack, D4) | A per-asset-class unpooled variant beats pooled on the register-deflated CPCV verdict | C4 (S), C1 |
| I2 | Hierarchical or partially pooled *forecasters* (per-instrument parameters shrunk toward the pool) | **REJECT for build; ADAPT as one registered challenger family later** | The only per-instrument deviation R-1 allows is cost-driven speed (R1-B). A hierarchical forecaster adds a model where a pooled rule already exists, and its OOS gain in FX/futures is unshown. R1-A owns the shrinkage of *performance estimates* | +1 model, +~150 lines | Revive if R1-A's shrinkage shows per-instrument edge dispersion beyond sampling noise on ≥ 2 families | [pending] |
| I3 | Meta-labeling (a secondary ML filter on a primary rule's trades) | **REJECT** | A daily pooled rule makes ~2,000 sign-trades over 14 years × 30 instruments (receipt). A secondary classifier on that sample is a new search with many more free parameters than the rule. Its public record is largely synthetic or equity | +classifier, +features, +a second CV | Revive only if a pre-registered filter raises the deflated CPCV path Sharpe on ≥ 3 families at a fixed feature set | [pending] |
| I4 | Ensembles and bagging | **ADOPT the unfitted form only**: several speeds or variants of one rule, equal-risk or handcrafted (R1-B owns the weights). **REJECT** bagged ML | Unfitted averaging adds breadth without adding search. Bagging a learner adds search | 0 new concepts (it is forecast combination) | Equal weights lose to the family's best single speed on the forward record | R1-B |
| I5 | Online regret-bounded allocation among rules (Hedge/EXP3, online portfolio selection) | **REJECT as the allocator; optional shadow logger** | Regret bounds are stated against the best rule *in hindsight*, before costs. At the ACIS scale (3–6 sleeves) the weights turn over on noise, and the online-portfolio-selection record degrades sharply once costs are charged | +~80 lines, +1 concept | A registered shadow Hedge beats fixed equal-risk weights net of costs on ≥ 1 year of *forward* data | [pending] |
| I6 | Volatility-managed exposure as *timing* (Moreira–Muir) | **REJECT the timing overlay; ADOPT plain vol targeting inside the rule** (R1-B) | The out-of-sample critique finds no systematic gain from the timing overlay across many factors. Vol scaling that is part of the rule's position formula is a different thing, and it stays | 0 | A registered overlay improves the deflated verdict on ≥ 2 families | [pending] |
| I7 | Regime as a soft *weight*, not a gate (HMM or jump-model probabilities) | **REJECT for now; retire the hard NVMA router** (kill list) | The NVMA label flickers on 30–43% of cycles (C3). A soft-regime layer is a second model with its own fit. The best evidence is for equity-index allocation, not pooled FX/CFD rules | +model, +fit window | Revive as one registered family if a pre-specified 2-state model improves the deflated verdict on held-out instruments | [pending] |
| I8 | ML forecasters (GBM, LSTM, transformer) under purged and embargoed CV | **REJECT as a primary; at most ONE pre-specified challenger**, after the register exists | Each architecture is a large search that the register must charge. The published futures deep-momentum results are authors' own OOS, and cost-sensitive. C1's frontier leaves no room for another 100× in N | +300–1,000 lines, +deps | A single pre-registered model beats the pooled rules on held-out instruments AND forward time | [pending] |
| I9 | LLM-generated hypotheses, graded under the contamination rule | **ADAPT: out-of-band proposer only.** Falsify on history; credit only forward (GAP-P12D-66) | Gençay: honest evaluation "rejects every LLM-discovered strategy"; FINSABER: LLM advantages "deteriorate significantly"; one survey finds "only 26.8% acknowledge look-ahead bias" | +origin field only | An LLM-originated family passes V *and* the forward e-process at its registered N | (a)/(b), fetched |
| I10 | LLM trading agents in the loop ("agentic trading") | **REJECT** | CLAUDE.md rule 1 already forbids it. The surveys find capability "does not reliably translate into trading performance under live market conditions" | — | — | (b), fetched |
| I11 | "Time-machine" or chronologically consistent LLMs | **REJECT for ACIS** | They matter only when an LLM produces *features from historical text*. ACIS does not, and should not start | — | — | [pending] |

## D2. The registry: minimal schema delta

**The invariant.** The verdict is a **pure function of the register**. No graded number may exist without a
register row written *before* it was computed. This is Gençay §3.2's "complete by construction", enforced by one
evaluation entry point.

**Base it on BUILDER-2's look register** (local WIP; its ledger entry is GAP-P12D-64). Keep what it already has:
- the exclusive-create claim;
- the data tier, derived and never claimed;
- "say what changed" for a family's repeat look.

**Add four fields and one artifact.**

| Field | Why |
|---|---|
| `variant` (canonical JSON of the declarative plan: rule id, fixed params, universe id, decision clock) + `variant_hash` | Duplicate variants are counted, not silently re-run. Equal-hash plans are one hypothesis. |
| `origin` + `model_id` + `model_cutoff` | VAL L1 (GAP-P12D-66). It makes "credit only after the cutoff" mechanical. |
| `cost_map_hash` (sha256 of every `CostModel`'s fields, including `stress`) | One cost map for selection and grading (GAP-P12D-36/46), checkable afterwards. |
| `simulator` (`rsim`\|`engine`) + `recon_commit` (the last commit where reconciliation passed) | A research-simulator number is admissible only at a reconciled commit (VAL §8). |
| **Artifact:** `returns/<sha256>.npy`, the run's daily net-return vector on the FX trading-day index (`core/data/fx_clock.py:107` `trading_day`), referenced by hash in an append-only result row | DSR counts N. **SPA/StepM, CSCV-PBO and e-BH need the T×K return matrix.** Counts alone cannot give a search-aware verdict. |

**Two more rules:**
- **Aborted runs** keep their claim row and have no result row. They count toward N.
- **`ProvenanceStore.attempts`** (`core/signals/provenance.py:92-95,155-167`) is fed by the same entry point:
  `record_attempt(family, variant_hash)`. There is one counter, not two.

**Lines (est.):**
- +~60 on BUILDER-2's 164-line register;
- +~40 for the return store;
- +~120 for `verdict(register, family|all, tier)`, which imports `arch.bootstrap.SPA/StepM` and skfolio CPCV per C4
  §2.3, not hand-rolled.

## D3. The research simulator (RSIM) and its reconciliation (extends ARC §5.3 and VAL §8)

**The critique of ARC §5.3.** It is designed for 1-minute bars (~5 M bars per instrument), which is the horizon R-1
abandons. At a daily or hourly decision clock the design gets simpler:

- **R-a. One rule function, two callers.** Each rule is ONE pure function `forecast(bars_to_t) → capped forecast`.
  RSIM and the live sleeve import the same function. So VAL's R3 ("identical decisions") holds by identity, and
  reconciliation only has to test fills and accounting.
  - This applies the NautilusTrader parity lesson (C4 §2.3) at the rule level, without the framework.
- **R-b. A scalar cost call per fill, by identity.**
  - Receipt: `per_side_cost` costs 0.26–0.46 µs a call. A 30-instrument × 14-year daily run makes ~56 k fills, and an
    hourly run ~125 k, so pricing costs well under 0.1 s a run.
  - No vectorised cost twin is needed, so the GAP-P12D-36 class cannot recur.
  - `evolve_step.cost_model()` (`tests/backtest/evolve_step.py:44`) is the only CostModel factory. It must move before
    `evolve_step.py` retires.
- **R-c. Shared components.** RSIM shares, read-only:
  - the financing model, `tests/backtest/financing.py:90` `make_financing`;
  - the FX clock, `core/data/fx_clock.py:102-115` (rollover and trading day);
  - the daily bars, `core/data/bars.py:100` `DailyBarAggregator` (17:00 New York).

  Hourly bars come from the same `BarAggregator(3600)`.
- **R-d. Reconciliation reference: the real engine fed hourly bars as ticks, not the tick replay.**
  - A tick replay of 30 instruments × 14 years is ~10.5 B ticks. At the measured 1,615–1,821 ticks/s (GAP-P12D-15)
    that is ≈ 70 single-core days, which is infeasible.
  - An hourly bar stream is ~2.6 M events, ≈ 25 min.
  - Keep VAL's R1, R2, R4, R5 and R6 on synthetic tapes as specified.
  - R3 becomes "identical target-position series" (exact), which is trivial once R-a holds.
- **Lines (est.):**
  - `rsim.py` ~150;
  - `rules.py`, the interpreter plus 3–5 rule functions, ~150;
  - reconciliation tests ~200.

## D4. The kill list, updated for R-1 (measured at BASE `974dbda`)

C4's K1–K8 stand. The deltas:

| Item | C4 said | Measured now | R-1 delta |
|---|---|---|---|
| `core/optimizer/qiea.py` | 242 | **291** | +49 lines of evaluation registry (`qiea.py:173-251`), now superseded by D2. Retire the whole file. |
| `tests/backtest/evolve_step.py` | 113 | **117** | Retire. Move `cost_model()` (lines 44-57) first (R-b). |
| `core/optimizer/fitness.py` | "survives as the plateau evaluator" | **256** | **NEW KILL.** RSIM replaces this minute-bar simulator; R-1 has no genes to evaluate. |
| `core/optimizer/plateau.py` | kept (law) | **74** | **Re-home.** The ±10% plateau law becomes a check over the registered coarse grid in `verdict()`. The gene-typed `neighbours()` retires. |
| `core/optimizer/param_library.py` | ~200 staging | **268** (stage/promote/on_boundary, lines 112-203, ≈ 92) | Retire staging and promotion. A static loader for the fixed pooled parameters stays. |
| `core/optimizer/param_types.py` | — | **143** | Genome and gene bounds retire, est. ~90. ParamSet stays only if the sleeves still consume it. |
| NVMA router (`core/regime/nvma.py` 395, `stability.py` 44, `tests/backtest/regime_labels.py` 197) | ~300 + 197 | **636** in total | Keep the `tradeable` veto only (est. ~120). Retire ~500. |
| AGON MR/SCALP/PAIR (`agon.py:140-169, 407-481`) + conviction pipeline (`agon.py:267-358`) | ~110 | **~105 + 92** | Retire the three modules. The pipeline becomes forecast netting (~40, est.). |
| `marginal_alpha.py` / `fragmenter.py` + `VenueQuality` (`venue.py:315-342`) | 73 / ~147 | **73 / 120 + 28** | Unchanged (C4 K3/K4). |
| **Tests that go with them** | ~800 | `test_qiea` 157, `test_evolve_step` 158, `test_qiea_promotion_cycle` 92, `test_evaluation_registry` 110, `test_fitness*` 593, `test_plateau_law` 128, `test_regime_labels` 159, `test_marginal_alpha` 92, part of `test_param_library` 207 and `test_nvma` 275 | **≈ 1,490 + part of 482** |

**Net production retirement if all are ratified:** ≈ 291 + 117 + 256 + 92 + 90 + 500 + 197 + 73 + 148 ≈ **1,760
lines** of the 7,519 in `core/` + `monitoring/`, plus the harness files. That compares with C4's ~1,380.
- **Added back:** D2 (~220) + D3 (~300) + reconciliation tests (~200).
- **Net ≈ −1,000 production lines**, with one search engine replaced by one register.

## D5. Gates (ARC §5.5 as amended; VAL's stages)

| Gate | Data | Passes when (draft) | Delta from ARC |
|---|---|---|---|
| G0 register | none | Declarative plan, ≤ 3 free parameters, cost/pre-cost SR ≤ ⅓ at literature speed, origin recorded | + the `variant_hash` duplicate check and the graveyard-motif veto |
| G1 machinery | synthetic (R1-C's lab) | planted detected, null not, leaky oracle refused by structure (GAP-P12D-65), RSIM↔engine reconciled | unchanged |
| G2 validation | 2012–2023 primary universe, CPCV, ≤ 3 registered looks per family | **all three instruments:** register-DSR, PBO ≤ 0.20, AND an absolute OOS-CI lower bound > 0 (Gençay's third failure mode) | **ARC's E/V split merged into one CPCV stage.** With literature-fixed pooled parameters there is no training, and halving T halves t² |
| G3 holdout once | 2024–25 **and** the locked held-out instruments | kill-only (VAL stage 4) | + held-out instruments (R-1 item 6) |
| G4 demo incubation | forward | an anytime-valid e-process (R1-A owns the numbers) + the paired cost gap in band | **replaces** ARC's fixed "≥ 3 months and ≥ 60 trades" peek |
| G5 challenge | paid | G2–G4 passed and human sign-off | unchanged |

**Kill criteria.** VAL K1–K6 stand, plus:
- **K7:** the measured cost/pre-cost SR is above ⅓ at G2. Kill before any V look.
- **K8:** a registration that duplicates a graveyard motif or `variant_hash` is refused.
- **K9:** any graded number without a register row voids that family's results since its last clean row.

## D6. Compute estimate (draft; laptop = i5-8200Y 2C/4T per GAP-P12D-12)

| Step | Basis | Estimate |
|---|---|---|
| One-time bar build, 30 instruments | ≈ 10.5 B ticks (30/8 × 2.79 B, **extrapolated**; index CFDs may be denser) at the measured 179,000 ticks/s decode (GAP-P12D-12) | ≈ 16 h decode, **~1–1.5 laptop days** with aggregation, 2 cores. Resumable per instrument-year (GAP-P12D-76: the laptop loses power). Output < 100 MB |
| One RSIM run, 30 instruments × 14 years | **measured** here: 0.11–0.15 s daily, 1.6–2.1 s hourly, on one container core (pure-Python fill loop) | ×2 for the laptop (est.): ≈ 0.3 s / 4 s |
| A pooled sweep: 10 families × 10 variants × 4 cost rungs = 400 runs | the above | **≈ 2 min daily, ≈ 30 min hourly** |
| Verdict (CPCV/PBO/SPA over K ≤ 400, T ≈ 3,640) | reuses the stored vectors | minutes |
| Engine reconciliation on hourly bars-as-ticks | 2.6 M events at 1,615–1,821/s (GAP-P12D-15) | **≈ 25 min** per full confirmation |
| Tick-level engine replay of 30 instruments | 10.5 B at ~1,700/s | **≈ 70 core-days: do not plan it** |

**The receipt also measures the §14 trade shape.** On the planted market, with a portfolio SR of 0.87 (daily
EWMAC 16/64, 30 instruments), the rows read:
- win rate 0.18 (sign-trade definition);
- average hold 53.5 days;
- positive months 52%.

So §14's > 48%, 30 min–48 h and > 70% all fail on a rule that has a real edge. This supports amendment A6; no more
is spent on it.

## D7. Where out-of-band LLM help fits (draft)

- **Allowed:**
  - proposing registrations as declarative plans, validated against the rule-registry schema. This is Gençay's tool
    surface: "parameter hallucination is eliminated rather than punished";
  - literature triage into G0 cards, with quotes verified at the primary source;
  - code review as an audit lens;
  - red-teaming registrations.
- **Forbidden:**
  - any runtime role;
  - editing a plan after seeing a V/H result without a new register row;
  - certifying on pre-cutoff data (GAP-P12D-66).
- **The untrusted-input law (SPEC §3.5/§12) extends to research.** An LLM proposal is *data* that the schema
  validator accepts or refuses. It is never code that runs, and never an instruction.
- **The convergence hazard.** Gençay (§8) reports that "three of five gpt-4.1 repetitions composed near-identical best
  strategies". LLM proposals crowd, so the K8 duplicate veto and the family cap matter.
