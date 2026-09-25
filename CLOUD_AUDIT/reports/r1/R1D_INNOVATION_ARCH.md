# R1-D — INNOVATION AND ARCHITECTURE (ACIS mission R1)

- **Lane:** R1-D, INNOVATION AND ARCHITECTURE. A finder, not a clearer. It launched no subagents.
- **Model and effort, as observed:** the system prompt names `claude-opus-5-5`. The effort setting is not observable
  from inside the session.
- **Fresh context:** attested. This lane saw only its brief, the prior reports listed in BRIEF_R1 §0.3, the BASE tree
  and the web.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`, read-only at `/tmp/review-acis`. **Date:** 2026-09-25.
- **Web:** 31 of 40 used (searches and fetches combined, including curl fetches of arXiv, RePEc and CEPR pages).
- **Data:** no real market data. Every simulation is synthetic (numpy PCG64). Numbers from papers are quotations.
- **Receipts:** under `CLOUD_AUDIT/reports/r1/evidence/R1D/`:
  - `sim_rsim_daily.py` and its `.out.json`: research-simulator timing and §14 trade shape;
  - `sim_hedge_vs_equal.py` and its `.out.json`: online allocation against fixed equal weights;
  - `probe_killlist_lines.py` and its `.out.txt`: measured line counts.
- **LLM origin.** Every strategy or design idea in this report is **LLM-originated** unless a quote carries it.
  Under GAP-P12D-66 such ideas may be *falsified* on 2012–2025 history but *credited* only on forward data.

---

## 1. Executive summary

1. **Only three of the eleven "innovative" candidates survive, and none of them is ML.** Grades (a)/(b), fetched.
   - **The survivors:**
     - fully pooled, literature-fixed rules;
     - unfitted ensembles, meaning equal-risk averages of speeds or variants;
     - an LLM as an out-of-band hypothesis proposer, credited only on forward data.
   - **Rejected:**
     - meta-labeling;
     - online regret-bounded allocation;
     - volatility-managed *timing*;
     - soft regime weights;
     - ML forecasters;
     - LLM trading agents;
     - "time-machine" LLMs.

   Each rejection carries a revival condition (§2.1).
2. **The FX-specific ML evidence argues for pooling and linearity, not depth.** Grade (b). Filippou, Rapach, Taylor
   and Zhou's FX forecast works because it pools the currencies in "a high-dimensional panel predictive regression"
   with elastic-net shrinkage. They add: "nonlinearities do not appear substantial in the data." That is R-1's
   design, reached from the ML side.
3. **Volatility scaling belongs *across* instruments, not as timing of one stream.** Grade (a).
   - Kim, Tse and Wald (2016) find that TSMOM's futures alpha is "largely driven by volatility-scaling returns ...
     rather than by time series momentum".
   - Cederburg et al. (2020) find that volatility-managed timing overlays "do not systematically outperform" out of
     sample.
   - **Consequence:** every pooled rule must beat its own volatility-scaled passive benchmark, not zero (new
     recommendation P6).
4. **Online allocation (Hedge) gives no gain at ACIS scale unless dead sleeves pass the gates.** Synthetic receipt,
   400 replications.
   - With 5 equal-quality sleeves (SR 0.5), Hedge loses **−0.18 SR** against 1/K (it beats 1/K only 11% of the time).
   - With one clearly better sleeve (0.8 against 0.3), it gains **+0.05** (it wins 56% of the time).
   - It gains **+0.35** only when three sleeves have zero edge, and removing those is the gates' job.
5. **Gençay (arXiv 2608.27734) adds three design rules VAL did not use.** Grade (b), fetched.
   - **(i)** A verdict needs three instruments. A DSR at the register's N and a PBO **plus** an absolute out-of-sample
     CI, because a large-budget find "kept its rank among mostly losing candidates while losing its absolute edge".
   - **(ii)** One evaluation entry point makes the ledger "complete by construction rather than by author diligence".
   - **(iii)** Strategies are declarative plans. Look-ahead becomes "inexpressible" and "parameter hallucination is
     eliminated rather than punished".
6. **The registry must store each run's return vector, not only a count.** Code-verified, grade S.
   - Two stores at BASE count runs:
     - the BASE `attempts` table (`core/signals/provenance.py:92-95`);
     - BUILDER-2's look register (local WIP; its ledger entry is GAP-P12D-64).
   - Neither can compute SPA/StepM, CSCV-PBO or e-BH, because each of those needs the T×K matrix of per-run daily
     returns.
   - The minimal delta is **+~60 lines on the look register, plus a content-addressed return store (~40)**.
7. **At the daily/hourly clock the research simulator shares the scalar C8 cost model by object identity.** Measured,
   synthetic.
   - The cost call costs 0.26–0.46 µs.
   - A 30-instrument × 14-year run takes 0.11–0.15 s on daily bars and 1.6–2.1 s on hourly bars (one core), and
     makes 56 k–125 k fills.
   - So no vectorised cost twin is needed, and the GAP-P12D-36 class cannot recur.
8. **A tick-level engine confirmation of 30 instruments is infeasible, so reconcile on hourly bars.** Measured and
   extrapolated.
   - About 10.5 B ticks at the measured 1,615–1,821 ticks/s (GAP-P12D-15) is about 70 single-core days.
   - The same engine fed hourly bars as ticks is 2.6 M events, about 25 minutes.
9. **The kill list is larger than C4's.** Measured at BASE.
   - **≈ 1,415 lines retire whole or by line range** (1,101 production + 314 harness), plus an estimated ~365 more
     (NVMA classification and the genome).
   - **Against 7,645 production lines.** `fitness.py` (256) is a new kill, but only after its three indicator
     functions move: `core/signals/indicators.py:17` imports them.
   - **Test lines:** 1,489 in whole files, plus part of 482 more.
10. **§14's trade-shape rows fail a rule that has a real edge.** Synthetic receipt.
    - On a planted market where a daily EWMAC reaches a portfolio SR of 0.87 across 30 instruments, the rows read:
      - win rate 0.18;
      - average hold 53.5 days;
      - positive months 52%.

      Against §14's > 48%, 30 min–48 h and > 70%, all three fail.
    - This confirms PLAN_R1 amendment A6. `ACIS_SPEC.md:213` itself says trend-following "wins ~35–48%".

---

## 2. Body

### 2.1 The hype filter: each candidate

**Reading the "Evidence" column.** Each entry names the primary out-of-sample evidence in FX, futures or CFDs, with
its grade. The verbatim quotes are in §6, keyed as [S#].

| # | Candidate | Evidence | Cost sensitivity | Data needs | Complexity | Verdict | Falsifier / revival condition |
|---|---|---|---|---|---|---|---|
| I1 | **Pooled, literature-fixed rule parameters** | C4 §2.2 (DoF); Gençay E5 on breadth [S1]; Filippou's pooling [S9] | Low: slow rules, one speed-limit check | Daily bars, 20–40 instruments | **Negative**: the QIEA stack retires (§2.6) | **ADOPT** | Drop it if a per-asset-class unpooled variant beats pooled on the register-level verdict at equal looks |
| I2 | **Hierarchical or partially pooled forecasters** (per-instrument parameters shrunk to a pool) | The one FX success is a *linear pooled panel with shrinkage*, monthly, on 70 macro predictors [S9] (b). I found no FX/CFD OOS record for a Bayesian hierarchical rule forecaster | Monthly, so low | A macro/country panel ACIS does not have | +1 model, +~150 lines, a fit window | **REJECT the build; ADOPT the lesson** (pool and shrink, stay linear). R1-A owns shrinkage of *performance* estimates | Revive as one registered family if R1-A's shrinkage shows per-instrument edge dispersion beyond sampling noise on ≥ 2 families |
| I3 | **Meta-labeling** | Joubert (2022, JFDS) shows its value with "a controlled experiment" [S10] (a, via search index). The practitioner demonstration: one instrument (S&P 500 E-mini), about 1 year out of sample, parameters iterated "until we felt comfortable" [S11] (c) | High: it filters trades, and every filter decision needs enough trades to learn | The trade labels of the primary rule: ≈ 2,000 sign-trades per 14 years × 30 instruments (receipt) | +a classifier, +features, +a second CV loop | **REJECT** | Revive only if one pre-registered, fixed-feature filter raises the deflated verdict on ≥ 3 families, credited on held-out instruments |
| I4 | **Ensembles and bagging** | 1/N beats 14 optimised allocations out of sample [S12] (a). Speed ensembles are R1-B's | None added | None | 0 new concepts in the unfitted form | **ADOPT the unfitted form** (equal-risk across speeds or variants). **REJECT** bagged learners | Equal weights lose to the family's single best speed on *forward* data |
| I5 | **Online regret-bounded allocation** (Hedge/EXP3, online portfolio selection) | Receipt [R2]: at K = 5 and 14 years, Hedge ≤ 1/K unless the sleeves have *zero* edge. The online-portfolio-selection record is on equity datasets, with contested cost results (§3) | Turnover grows with η | Sleeve returns only | +~80 lines, +1 concept | **REJECT as the allocator** | A registered *shadow* Hedge beats fixed equal-risk weights net of costs on ≥ 1 year of forward data |
| I6 | **Volatility-managed exposure as timing** (Moreira–Muir) | Cederburg et al. [S2] (a): not implementable in real time, and the OOS versions earn lower Sharpe. Barroso & Santa-Clara [S3] (a) help *equity cross-sectional* momentum crashes, which is not FX. Kim–Tse–Wald [S4] (a): the value lies in scaling *across* futures | Low | Daily vol | +1 overlay, +a fit | **REJECT the timing overlay. ADOPT vol-normalised positions inside the rule** (R1-B) | A pre-registered overlay improves the register-level verdict on ≥ 2 families |
| I7 | **Regime as a soft weight** (HMM or jump-model probabilities) | The best recent case is equity indices only, long/flat, with the jump penalty "selected through a time-series cross-validation method that directly optimizes strategy performance" [S5] (b), which is a search. ACIS's own NVMA label flickers on 30–43% of cycles (C3) | Medium: regime flips cause trades | A regime model and its fit window | +model, +fit, +~150 lines | **REJECT for this cycle.** PLAN A7's "continuous registered weight variant" is allowed in principle, but nothing on the evidence earns one of the scarce V looks | Revive as one registered family if a pre-specified 2-state model, *not tuned on strategy P&L*, improves the verdict on held-out instruments |
| I8 | **ML forecasters under purged and embargoed CV** (GBM, LSTM, transformer) | Deep Momentum Networks, 88 futures [S6] (b): > 2× the traditional methods before costs, and "continue outperforming when considering transaction costs up to 2-3 basis points". The Momentum Transformer [S7] (b) is the authors' own OOS. Neither reports search-aware deflation. FX: "nonlinearities do not appear substantial" [S9] | **High**: the edge claims survive only to 2–3 bp | 10^4–10^5 daily observations, feature engineering | +300–1,000 lines, +dependencies, +an N that C1's frontier cannot pay for | **REJECT as a primary.** At most one pre-registered challenger, after the register exists | Revive if one pre-registered model beats the pooled rules on held-out instruments **and** on the forward e-process |
| I9 | **LLM-generated hypotheses** | Honest evaluation "rejects every LLM-discovered strategy" [S1] (b). FINSABER: advantages "deteriorate significantly under broader cross-section and over a longer-term evaluation" [S8] (a). Recall on pre-cutoff data is non-identifiable (VAL §6.1) | As for any rule | None added | +an origin field | **ADAPT: out-of-band proposer only.** It may kill a hypothesis on history, and may earn credit only on forward data (GAP-P12D-66) | An LLM-originated family clears V **and** the forward e-process at its registered N |
| I10 | **LLM agents in the trading loop** | The surveys: capability "does not reliably translate into trading performance under live market conditions" [S13] (b). Negative results are unreported [S14] (b). Only 26.8% of papers acknowledge look-ahead [S15] (b) | — | — | Forbidden already (CLAUDE.md rule 1) | **REJECT** | — |
| I11 | **"Time-machine" or chronologically consistent LLMs** | ChronoBERT/ChronoGPT: in one news application, "lookahead bias is modest" [S16] (b). Look-Ahead-Bench favours the point-in-time models of the vendor it evaluates [S17] (c for that claim) | — | A text corpus | Large | **REJECT for ACIS.** They matter only when an LLM makes *features from historical text*, which ACIS does not do | Revisit only if ACIS ever adds a text-derived signal (a spec change) |

**The pattern.** Every method that learns *more* from the same 14 years buys N the data cannot afford. C1's frontier
says 80% power at FWER 5% needs 9.3, 15 and 20 years at SR 1.0 for K = 1, 5 and 20. The methods that survive add
**breadth** (instruments and unfitted variants) or **forward time**, and cost nothing in N.

**Receipt R2 in full** (`sim_hedge_vs_equal.out.json`; 400 replications of 14 years; sleeves at unit daily volatility
with ρ = 0.2–0.25; η = √(8 ln K / T) and 10× that):

| Sleeve Sharpes | Cost per unit of turnover | Hedge − 1/K (mean SR; P(beats)) | Hedge ×10 − 1/K | Best-in-hindsight − 1/K |
|---|---|---|---|---|
| 5 × 0.5 | 0 | −0.179; 0.11 | −0.293; 0.09 | −0.036; 0.37 |
| 5 × 0.5 | 0.02 | −0.176; 0.14 | −0.277; 0.11 | −0.020; 0.42 |
| 0.3 ×4, 0.8 | 0 | +0.053; 0.58 | 0.000; 0.52 | +0.201; 0.85 |
| 0.3 ×4, 0.8 | 0.02 | +0.045; 0.56 | −0.020; 0.50 | +0.199; 0.83 |
| 0.0 ×3, 0.8 | 0.02 | +0.351; 0.93 | +0.352; 0.89 | +0.495; 0.99 |

A regret bound is a promise measured against the best sleeve *in hindsight*. Over 14 years, even that best sleeve
beats 1/K only 37–42% of the time when the sleeves are equally good (it trails by 0.02–0.04 on average), and
Hedge's concentration costs diversification.

### 2.2 The hype filter: popular "AI trading" methods that fail honest evaluation

| Method | What fails | Source (grade) |
|---|---|---|
| LLM-discovered strategies with the best reported | All are rejected once deflated by their own trial count. A leaky oracle at Sharpe 35 survives DSR and PBO "completely" | Gençay 2608.27734 [S1] (b) |
| LLM timing agents (FinAgent-style) | "overly conservative in bull markets ... overly aggressive in bear markets"; the advantages deteriorate over longer periods and broader universes | FINSABER [S8] (a, KDD 2026 oral) |
| LLM backtests on pre-cutoff data | Memorisation cannot be told from skill; "Post-cutoff, we observe no recall" | Lopez-Lira et al., quoted in VAL §6.1 (b) |
| Agentic multi-agent trading systems | The benchmarks show capability is not live performance; failed designs go unreported | 2608.31041 [S13], 2605.19337 §13.3 [S14] (b) |
| The published LLM-finance literature as a whole | "only 26.8% acknowledge look-ahead bias, and survivorship bias appears in just 1.2% of studies" (164 main-conference papers, 2023–2025) | Kong, Lopez-Lira et al. 2602.14233 [S15] (b) |
| Evolutionary or genetic search on backtest reward | ACIS's own record: QIEA at 43,200 evaluations per fold (C4), and the engine loses on its positive control (GAP-P12D-49). ARC tells us to avoid QuantaAlpha-style mutation and crossover | C4 (S); ARC §5.8 |
| Deep momentum networks at retail cost | The edge claim holds to "2-3 basis points" of cost, with no search deflation reported | Lim, Zohren & Roberts [S6] (b) |
| Volatility-managed timing | The positive alphas in spanning regressions "are not implementable in real time" | Cederburg et al. [S2] (a) |
| Meta-labeling "improves every metric" | A controlled experiment, plus one instrument and ~1 year OOS, tuned iteratively | [S10] (a), [S11] (c) |
| "Point-in-time LLM" vendor benchmarks | The benchmark's author evaluates the vendor's own models favourably | Look-Ahead-Bench [S17] (c for that claim) |

### 2.3 Gençay 2608.27734: what VAL did not use (fetched at source, grade (b))

VAL used the abstract's leaky oracle and §4.5 (pre-registration means less deflation). Four things were left:

1. **Three failure modes need three instruments** (§7).
   - The quote: "The multi-seed finds were profitable out of sample yet indistinguishable from selection luck at the
     agent's own trial count (a DSR failure); E5's find degraded out of sample exactly as its design-window PBO
     predicted (a CSCV success); and E3's large-budget find collapsed out of sample despite a low PBO, because its
     winner kept its rank among mostly losing candidates while losing its absolute edge, which the held-out
     confidence interval caught."
   - **For ACIS:** VAL's stage 2 (CPCV + PBO ≤ 0.20) needs the absolute CI lower bound as a third condition. PLAN A2
     should carry all three.
2. **One entry point, so the ledger is complete by construction** (§3.2): "every candidate the agent composes flows
   through the same evaluation entry point, which is what makes the trial ledger of Section 4 complete by construction
   rather than by author diligence."
3. **Declarative plans** (§3.1–3.2).
   - Every strategy, including the port of a human trader's system, is "a JSON configuration interpretable at the
     feature level".
   - The tool surface validates each plan: "60 of 60 proposals were rejected" without validation; with it, 99 of 100
     and 80 of 100 were valid.
   - **For ACIS:** an LLM (or a human) proposes a *plan* over a closed rule registry, never code.
4. **Power and breadth** (§6.5, §7).
   - On E5 (39 multi-asset ETFs, 9 held-out years), TSMOM long/flat is positive in both windows "and is still
     under-powered". Also: "Certifying moderate low-frequency edges requires decades or breadth".
   - Only passive benchmarks certified.
   - **Expect the 2024–25 holdout to certify nothing** (VAL §5.4 agrees). R-1 item 6 is right to make forward time
     the decisive test.
   - Limitations: "three of five gpt-4.1 repetitions composed near-identical best strategies". LLM proposals crowd,
     so a duplicate veto is needed (K8 below).

### 2.4 ARC §5, critiqued and extended

| ARC §5 element | Critique under R-1 | Extension |
|---|---|---|
| §5.1 registry "extends ProvenanceStore" with counts and cards | Counts cannot compute SPA/StepM/PBO/e-BH (§1 #6). ProvenanceStore is the *production* lifecycle ledger (rungs, `core/signals`). Research runs are research tooling | Put the **run register** on BUILDER-2's look register, add return vectors. ProvenanceStore keeps family registration and rungs, and its `attempts` is fed by the one entry point (§2.5) |
| §5.2 E 2012–2019 / V 2020–2023 | With literature-fixed pooled parameters there is nothing to train. Splitting 12 years in two halves the t² of each part. VAL's CPCV over 2012–2023 already spends looks honestly | **Merge E and V into one CPCV stage over 2012–2023**, with ≤ 3 registered looks per family (VAL K1). "Exploration" means synthetic data, pre-2012 history and out-of-universe instruments (VAL stage 1) |
| §5.3 RSIM on 1-minute bars, float32 yearly chunks | That is the horizon R-1 abandons. At daily or hourly clocks the whole 30-instrument cache is < 100 MB | A clock-agnostic RSIM: 1-minute bars only for families that declare a 1-minute clock (ARC's H1/H5/H6) |
| §5.3 "fills at the next bar's open ± the half-spread" | At a 17:00 New York daily clock the "next open" *is* rollover, the widest-spread minute of the FX day. On a Friday it is also inside FTMO's 2-hour pre-close ban (GAP-P12D-58) | **Decide on the 17:00 New York close; execute on a declared execution clock** (the next liquid hourly bar, and never inside the rulebook's pre-close window). Both clocks are in the plan |
| §5.3 reconciliation "on shared fixtures" | The tick reference is unaffordable at 30 instruments (§1 #8) | Reference = the engine fed hourly bars as ticks, plus VAL R1–R6 on synthetic tapes (§2.5) |
| §5.4 honest-N DSR + PBO | Two of Gençay's three instruments | Add the **absolute OOS CI** and the **passive-benchmark pair test** (P6) |
| §5.4 "≤ 20 new families a quarter" | At SR ≈ 0.5 no protocol has power (VAL: 25.5%). Twenty families mostly spend looks on noise | **≤ 5 families enter V per quarter** (draft; R1-A's online-FDR result sets the number) |
| §5.5 G5 forward "≥ 3 months and ≥ 60 trades", then a 10th-percentile test | A fixed-sample peek, which the owner's daily monitoring breaks | An **anytime-valid e-process** (R1-A), plus the paired shadow-replay cost gap |
| §5.7 graveyard failure motifs | Good; needs a mechanical key | The `variant_hash` duplicate check plus the motif veto at registration (K8) |
| §5.8 agentic literature | Copy/avoid lists are sound | Add Gençay's single entry point and declarative plans, which are *architecture*, not advice |

### 2.5 The factory architecture, mapped onto ACIS code at BASE

**The invariant (A-inv).** The verdict is a pure function of the register. No graded number exists without a
register row written *before* it was computed, and only one entry point writes rows.

```
plan (declarative, validated) ──► evaluate(plan, tier, span)   ◄── the ONE entry point
                                   │ 1. claim a register row (exclusive create; tier derived)
                                   │ 2. run RSIM (or the engine on hourly bars) with the ONE cost map
                                   │ 3. write returns/<sha256>.npy + an append-only result row
                                   │ 4. ProvenanceStore.record_attempt(family, variant_hash)
                                   ▼
verdict(register, family|all, tier) = { DSR at N = rows incl. aborted, CSCV-PBO, SPA/StepM,
                                        absolute OOS CI, paired passive-benchmark test }
```

**A. The plan: a declarative, closed rule registry.** New file `tests/backtest/rules.py` (research side), est. ~150
lines.
- A plan holds `{family, rule_id, params (≤ 3, literature-fixed), universe_id, decision_clock, execution_clock,
  sizing: vol_target}`.
- `rule_id` names ONE pure function `forecast(bars_up_to_t, params) -> capped forecast`. The **same function** is
  imported by the live sleeve (R-a below).
- Adding a rule needs code review and a G0 registration. An LLM can only *compose plans* from existing rules.

**B. The register.** Extend BUILDER-2's `tests/backtest/look_register.py` (164 lines, WIP; ledger entry GAP-P12D-64).

*Keep, as is:*
- the exclusive-create claim;
- the derived tier;
- "say what changed";
- the previous-look pointer.

*Add:*

| Field / artifact | Purpose |
|---|---|
| `variant` (canonical JSON of the plan) + `variant_hash` | Duplicates are detected and counted, never silently re-run |
| `origin`, `model_id`, `model_cutoff` | VAL L1–L2 (GAP-P12D-66): credit only after the cutoff, mechanically |
| `cost_map_hash` (sha256 over every `CostModel`'s fields, `stress` included) | One cost map for selection and grading (GAP-P12D-36/46) |
| `simulator` + `recon_commit` | A research-simulator result is admissible only at a reconciled commit (VAL §8) |
| `universe_id`, with the held-out set as a **locked id** that tier ≤ 2 rows cannot reference | Held-out instruments locked by structure, like `HoldoutGuard` (`tests/backtest/oos_plan.py`) |
| `returns/<sha256>.npy`: daily net returns on the FX trading-day index (`core/data/fx_clock.py:107`) | The matrix every search-aware statistic needs |
| An append-only result row `{run_id, completed_utc, returns_ref, metrics}` | Aborted runs keep a claim row with no result, and still count toward N |

- **Lines:** +~60 on the register, +~40 for the return store.
- **The ProvenanceStore change:** none to the schema. `record_attempt` is called by `evaluate`, so there is one
  counter (`core/signals/provenance.py:155`).

**C. The verdict module.** `tests/backtest/verdict.py`, est. ~120 lines, per PLAN A2 stage A.
- **SPA/StepM:** imported from `arch.bootstrap`.
- **CPCV:** from skfolio's `CombinatorialPurgedCV`, both per C4 §2.3 (permissive licences, research tier only).
- **Its own code:** the DSR at the register's N (reusing `tests/backtest/deflated_sharpe.py`, 99 lines), CSCV-PBO
  (~40), the absolute CI (~15), the paired benchmark test (~15), and the **evaporation curve**.
- **The evaporation curve** is Gençay §4.4: the best-of-first-k against its deflation threshold over the register.
  It is a report of about 20 lines.
- **The plateau law** (`core/optimizer/plateau.py`, 74 lines) is re-aimed. It checks that a registered variant's
  pre-registered ±10% neighbours were also run and stay positive. Its gene-typed `neighbours()` retires.

**D. RSIM, the research simulator.** `tests/backtest/rsim.py`, est. ~150 lines.
- **Clock-agnostic.** Decision and execution clocks come from the plan. Bars come from `core/data/bars.py`:
  `DailyBarAggregator` (17:00 New York, line 100) and `BarAggregator(3600)`.
- **R-a. One rule function, two callers.** RSIM and the live sleeve import the same `forecast`. VAL's R3 (identical
  decisions) then holds by identity.
- **R-b. Scalar cost by identity.** Each fill calls the run's own `CostModel.per_side_cost`
  (`core/optimizer/costs.py:52`).
  - Measured at 0.26–0.46 µs a call.
  - A run makes 56 k fills (daily) to 125 k fills (hourly), well under 0.1 s.
  - There is no vectorised twin.
  - **Prerequisite:** the only CostModel factory is `evolve_step.cost_model()` (`tests/backtest/evolve_step.py:44`),
    so it must move to a shared home before `evolve_step.py` retires.
- **R-c. Shared components, imported and never copied:**
  - `tests/backtest/financing.py:90` `make_financing`;
  - `core/data/fx_clock.py:102-115` (rollover, trading day, weekend);
  - the account rulebook (`config/platform_rules.yaml`) for the pre-close and news windows (GAP-P12D-58).
- **Scope.** RSIM is exploration and validation only. It never produces the engine-confirmation number.

**E. Reconciliation**, VAL §8 as amended.
- **R1, R2, R4, R5 and R6:** unchanged, on the lab's synthetic tapes (R1-C).
- **R3:** becomes "identical target-position series, exact". That is trivial once R-a holds.
- **New reference:** the production engine fed **hourly bars as ticks**. That is 2.6 M events for 30 instruments ×
  14 years, about 25 minutes at the measured 1,615–1,821 events/s. It replaces the tick replay (about 70 core-days).
- **Tests:** ~200 lines, est.

**F. The gates** (they supersede ARC §5.5 where the two differ):

| Gate | Data | Passes when (draft numbers; R1-A calibrates) |
|---|---|---|
| G0 registration | none | The plan validates; ≤ 3 free parameters; origin recorded; literature cost/pre-cost SR ≤ ⅓ (Carver's speed limit, C4 (b)); no `variant_hash` or graveyard-motif duplicate |
| G1 machinery | synthetic (R1-C lab) | planted detected, null not, leaky oracle refused structurally (GAP-P12D-65), RSIM↔engine reconciled |
| G2 validation | 2012–2023, primary universe | ≤ 3 registered looks per family; **all of** register-DSR, PBO ≤ 0.20, absolute OOS-CI lower bound > 0, and it beats the passive benchmark (P6) |
| G3 holdout, once | 2024–25 **and** the held-out instruments | kill-only (VAL stage 4). Expect no certification (Gençay §6.5) |
| G4 demo incubation | forward | an e-process on net daily P&L, plus the paired cost gap inside the band (R1-A) |
| G5 challenge | paid | G2–G4 passed, plus human sign-off |

**G. The looks budget and the kill criteria.**
- **Budget (draft):**
  - ≤ 3 V looks per family;
  - ≤ 5 families entering V per quarter;
  - 1 holdout look;
  - 1 held-out-instrument look;
  - unlimited synthetic runs.

  Each V look is visible as a step on the evaporation curve.
- **Kill criteria:** VAL K1–K6 stand, plus:
  - **K7 (cost):** the measured cost/pre-cost SR at G2 is above ⅓, so the family is killed before a V look is spent.
  - **K8 (duplicate):** a registration that repeats a `variant_hash` or a graveyard motif is refused.
  - **K9 (register integrity):** any graded number without a register row voids that family's results since its
    last clean row. This is the register's twin of VAL K3.
  - **K10 (benchmark):** a pooled rule that fails the paired test against its volatility-scaled passive benchmark at
    G2 is killed.

### 2.6 The kill list, updated for R-1

Measured at BASE `974dbda` with `probe_killlist_lines.py`.

| Item | Lines (measured) | Note |
|---|---|---|
| `core/optimizer/qiea.py` | 291 | C4 measured 242 at `7695ed0`. It grew by 49 net (the evaluation registry and the plateau wiring). Superseded by the run register |
| `core/optimizer/fitness.py` | 256 | **New kill.** Lines 82–256 (simulator, expectancy, fitness components) retire. **Lines 32–81 (`ema_series`, `rsi_series`, `atr_series`) must move first**: `core/signals/indicators.py:17` imports them, and `plateau.py:24` imports `WORST_FITNESS` |
| `tests/backtest/evolve_step.py` | 117 | Retire after `cost_model()` (lines 44-57) moves |
| `core/optimizer/param_library.py` staging/promotion (lines 112-203) | 92 | Keep `PromotionForbiddenError` (`provenance.py:22` imports it) and a static loader. `tests/integration/paper_loop.py:38` uses `ParamLibrary`, so the demo runtime needs the loader |
| `core/optimizer/param_types.py` genome | 143 total, ~90 est. | Keep whatever the sleeves consume |
| NVMA classification (`core/regime/nvma.py`) | 395 total, ~275 est. | Keep the `tradeable` veto (~120). `adx_proxy` is re-exported by `indicators.py:18` |
| `core/regime/stability.py` | 44 | — |
| `tests/backtest/regime_labels.py` | 197 | — |
| AGON MR/SCALP/PAIR modules (`agon.py:407-481`) + pair sampling (`agon.py:140-169`) | 75 + 30 | C4 K5 |
| AGON conviction/discard pipeline (`agon.py:267-358`) | 92 | It becomes forecast netting (~40, est.; PLAN A7) |
| `core/governor/marginal_alpha.py` | 73 | C4 K3 |
| `core/execution/fragmenter.py` + `VenueQuality` (`venue.py:315-342`) | 120 + 28 | C4 K4 |
| **Measured subtotal** (whole files and named line ranges) | **1,415** | 1,101 production + 314 harness |
| **With the estimates** (NVMA ~275 + genome ~90, **minus** 50 indicator lines that move) | **≈ 1,730** | ≈ 1,416 production of **7,645** (−18.5%) |
| **Tests retiring with them**, whole files | **1,489** | `test_qiea` 157, `test_evolve_step` 158, `test_qiea_promotion_cycle` 92, `test_evaluation_registry` 110, `test_fitness*` 593, `test_plateau_law` 128 (rewritten for the grid), `test_regime_labels` 159, `test_marginal_alpha` 92 |
| Tests retiring in part | of 482 | `test_param_library` 207, `test_nvma` 275 |

- **Added back:** the register (+~100), the verdict (+~120), `rules.py` (+~150), RSIM (+~150) and the reconciliation
  tests (+~200). That is about +520 in research tooling and +0 in `core/`.
- **Net:** about **−1,400 production lines**. One search engine is replaced by one register, and the production
  surface shrinks.
- **K6–K10 of C4 and SYNTHESIS §3 are unchanged:** TSMOM-as-wired, the old `passed` conditions, `throwaway_ui/`, the
  spent root docs, and `pydantic-settings`.

### 2.7 The compute estimate

**The laptop:** an i5-8200Y, 2 cores / 4 threads, 7.9 GB (GAP-P12D-12). It loses power abruptly (GAP-P12D-76), so
every long step must resume per instrument-year.

| Step | Basis | Estimate |
|---|---|---|
| One-time bar build, 30 instruments × 14 years | ≈ 10.5 B ticks (30/8 × 2.79 B, **extrapolated**; index CFDs may be denser; R1-B owns the universe) at the **measured** 179,000 ticks/s bi5 decode (GAP-P12D-12) | ≈ 16 h of decode; **~1–1.5 laptop days** with aggregation on 2 cores. Output < 100 MB of daily and hourly bars |
| One RSIM run, 30 instruments × 14 years | **measured** on one container core (pure-Python fill loop): 0.11–0.15 s daily, 1.6–2.1 s hourly | about ×2 on the laptop (est.) |
| **The pooled sweep:** 10 families × 10 coarse variants × 4 cost rungs = 400 runs | the above | **≈ 2 min daily, ≈ 30 min hourly** |
| The verdict over K ≤ 400, T ≈ 3,640 (CPCV, PBO, SPA with 1,000 bootstrap draws) | reuses the stored vectors | minutes |
| Engine confirmation (hourly bars as ticks) | 2.6 M events at 1,615–1,821/s (GAP-P12D-15, measured under load) | **≈ 25 min** per confirmation |
| Tick-level engine replay of 30 instruments | 10.5 B ticks at ~1,700/s | ≈ 70 core-days. **Do not plan it** |
| Synthetic machinery iteration (R1-C lab) | milliseconds per daily path | unlimited |

**Compute is not the constraint. Clean data is:** the looks budget binds long before the CPU does. The one expensive
step is the one-time bar build, and it needs the tick archive's only copy (GAP-P12D-50).

### 2.8 Where out-of-band LLM help fits

| Role | Allowed? | Rule |
|---|---|---|
| Hypothesis proposer | **Yes**, as a *plan* over the closed rule registry. A plan is data the schema validator accepts or refuses | Registered with `origin=llm-originated`, `model_id` and cutoff. It is falsifiable on history and creditable only after the cutoff (GAP-P12D-66, VAL L1–L5) |
| Literature triage into G0 cards | **Yes** | Quotes are verified at the primary source by a fetch or a human. An unverifiable quote is grade (c) |
| Code review | **Yes, as an audit lens** | Author ≠ auditor, per the constitution |
| Red-teaming registrations | **Yes** | Its output is a finding, never an edit |
| Editing a plan after seeing a V/H result | **Only as a new register row** | An LLM in that loop is a search algorithm (ARC §5.8), so every proposal is a trial |
| Any runtime role, or reading market text into signals | **No** | CLAUDE.md rule 1 |

**The untrusted-input law (SPEC §3.5/§12) extends to research.**
- Web pages, papers, other agents' reports and an LLM's own proposals are *content*.
- The only path from an LLM to the factory is a plan that passes schema validation. Free text never becomes a staged
  config, a command, or code that runs.
- This is Gençay's tool surface, applied: look-ahead is "inexpressible" because the rule registry exposes no leaky
  feature.

**The crowding hazard.** LLMs converge: Gençay saw "three of five gpt-4.1 repetitions" land on near-identical best
strategies, and ARC quotes FTMO's warning about EAs shared by many traders. K8 and the family cap are the defence.

### 2.9 For PLAN_R1

Numbered for the lead. **Lines** are measured, or marked est. **Grades:** (a)/(b)/(c) are external; S means
code-structural; R means a synthetic receipt.

| # | Recommendation | Value | Complexity (lines / concepts) | Grade | Falsifier | Verdict |
|---|---|---|---|---|---|---|
| **P1** | **One evaluation entry point** `evaluate(plan, tier, span)`. It claims the register row first, runs, stores the return vector, and feeds `ProvenanceStore.record_attempt`. No other path produces a graded number | The ledger becomes complete by construction; K9 becomes enforceable | +~60 / +1 ("the entry point") | (b) Gençay §3.2; S | A graded number is found whose run has no register row (a structural test that greps the harness for other grade producers) | **ADOPT** |
| **P2** | **Run register = BUILDER-2's look register + `variant_hash`, origin/cutoff, `cost_map_hash`, `simulator`/`recon_commit`, a locked `universe_id`, and a content-addressed daily return vector** (§2.5 B) | It makes SPA/StepM, PBO and e-BH computable from the register alone | +~100 / 0 (it extends GAP-P12D-64's work) | S | The verdict cannot be recomputed bit-for-bit from the register after deleting every cache | **ADOPT** |
| **P3** | **Verdict module (PLAN A2 stage A):** register-DSR + CSCV-PBO + SPA/StepM (imported) + **an absolute OOS-CI lower bound** + the evaporation curve | It closes Gençay's third failure mode, which PBO alone misses | +~120 / +1 (the absolute CI) | (b) Gençay §7 | On the lab, a large-family null in which the best variant keeps its rank but has zero edge passes with CI + PBO at > 5% | **ADOPT** |
| **P4** | **Declarative plans over a closed rule registry** (`rules.py`). One pure `forecast()` per rule, **imported by both RSIM and the live sleeve** | Decision parity by identity (VAL R3 is free); LLM proposals cannot express look-ahead or invalid parameters | +~150 / +1 ("plan") | (b) Gençay §3.1–3.2; C4 (Nautilus lesson) | The RSIM and live target-position series differ on any shared fixture | **ADOPT** |
| **P5** | **A clock-agnostic RSIM on daily and hourly bars.** Scalar `CostModel` by identity; shared financing, FX clock and rulebook windows; decide at 17:00 New York, **execute on a declared liquid execution clock outside the rulebook's pre-close window** | Sweeps take minutes; the GAP-P12D-36 class and the rollover-fill and gap-trading traps are excluded | +~150 / 0. **Prerequisite:** move `evolve_step.cost_model()` | R (timing); S | R4 fails (summed P&L differs from the engine by > 5% of friction, or the SR by > 0.10) | **ADOPT** |
| **P6** | **Passive-benchmark arms in the register.** An equal-risk volatility-scaled long-only arm per non-FX instrument class, plus a random-floor null. Every pooled rule is paired against them at G2 (K10) | It stops a trend rule's P&L on indices and gold being mostly the long-drift premium | +~30 / +1 | (a) Kim–Tse–Wald; (b) Gençay E5 | The rule's paired excess over its benchmark is ≤ 0 at G2 | **ADOPT** |
| **P7** | **Reconcile against the engine on hourly bars as ticks, not a tick replay.** Keep VAL R1–R6 on synthetic tapes | Engine confirmation takes ~25 min instead of ~70 core-days | +~200 test lines | R + measured GAP-P12D-15 rates | The hourly-bar engine and RSIM disagree on the sign of net P&L or on any gate decision | **ADOPT** |
| **P8** | **Merge ARC's E and V into one CPCV stage over 2012–2023**, ≤ 3 looks per family, ≤ 5 families per quarter (draft; R1-A sets the FDR) | Splitting 12 years halves t² for no benefit when parameters are fixed | −1 segment | S; VAL §3 | R1-A's simulation shows the split protocol has higher power at equal FPR | **ADAPT** (the numbers are R1-A's) |
| **P9** | **Kill list, per §2.6:** −1,415 measured (≈ −1,730 with estimates). Order: move the indicators and the cost factory → retire `evolve_step`, `qiea`, `fitness` 82–256, staging, the NVMA classification, `regime_labels`, the AGON modules and pipeline, `marginal_alpha`, `fragmenter`/`VenueQuality` | −18.5% of production; one register instead of one search engine | ≈ −1,400 production, −1,489 test; +~520 research tooling | S (measured) | A retired component is shown to carry OOS value on the lab (e.g. QIEA beats pooled parameters at equal looks, PLAN A4's falsifier) | **ADOPT** (owner ratification for A4/A7) |
| **P10** | **Innovation verdicts (§2.1):** adopt I1 and I4-unfitted; adapt I9; reject I2 (the build), I3, I5, I6 (timing), I7, I8, I10 and I11, each with its revival condition | It keeps N affordable; breadth and forward time are the only free evidence | −(everything not built) | (a)/(b) per row; R for I5 | Any revival condition is met | **ADOPT** these verdicts |
| **P11** | **LLM help (§2.8):** plan proposer, literature triage, review and red-team. Origin and cutoff live in the register. K8 duplicate and motif veto | It uses the LLM for breadth of ideas without letting it certify anything | +1 field, +~20 lines | (a) FINSABER; (b) Gençay, Lopez-Lira | An LLM-originated family is credited on pre-cutoff data anywhere in the register | **ADAPT** |
| **P12** | **Compute plan:** a one-time resumable bar build (~1–1.5 laptop days for 30 instruments); every later sweep is minutes | Compute is not the constraint; the looks budget is | 0 | measured + extrapolated | The measured bar-build rate on the laptop is below 50k ticks/s (then the build takes > 3 days) | **ADOPT** |

---

## 3. What I could not verify

- **Joubert (2022, JFDS)** is behind a paywall: the fetch was redirected to a login. Its abstract ("a controlled
  experiment") is quoted as the search index returned it, not fetched at source.
- **Harvey et al. (2018, JPM), "The Impact of Volatility Targeting".** The publisher, SSRN and Duke pages would not
  serve the abstract (a 17-byte body, a Cloudflare page, and no abstract). Its finding, that Sharpe gains hold only for
  risk assets and not currencies, is therefore **not used as load-bearing**. The I6 verdict rests on Cederburg et al.
  and Kim–Tse–Wald, both fetched verbatim.
- **Moreira & Muir (2017).** RePEc has no abstract. Their finding is cited only through Cederburg et al.'s verbatim
  "Consistent with Moreira and Muir (2017) ...".
- **The online-portfolio-selection cost record.** The search index summarised it as mixed. I fetched no primary
  paper, so I5 rests on the synthetic receipt and on DeMiguel et al. (a).
- **The Momentum Transformer's cost numbers** were not read beyond its abstract.
- **The laptop timing.** It is ×2 the container, which is an assumption. The laptop bar-build rate for index-CFD and
  metal ticks is extrapolated from FX.
- **The research-simulator receipt's shortcuts:**
  - its forecast scalar uses the whole path, which is a look and acceptable only in a timing sketch;
  - its win rate uses a "sign-trade" definition; other definitions give other numbers, but not above 48% on these
    holds.
- **Line estimates.** The NVMA classification (~275) and genome (~90) splits are estimates; only whole files and the
  named ranges were measured.
- **arch/skfolio.** I did not re-check their licences or APIs. C4 §2.3 is the source.

## 4. Residual risk

- **The verdicts could be over-conservative.** A future method might earn a V look that these rejections deny it.
  The revival conditions are the remedy, but each costs a look.
- **The passive-benchmark test could kill real trend edges.** During a long bull market, trend on indices and gold
  may lose to the benchmark (Gençay E6b: a gold system "forfeited a historic bull market"). K10 could then kill a rule
  with genuine diversifying value. Mitigation: pair on risk-adjusted excess, and consider the portfolio correlation
  (owner call).
- **The register's pure-function invariant depends on process discipline outside it.** One ad-hoc notebook grade
  breaks it. The structural test in P1 reduces the risk but cannot remove it.
- **Hourly-bar reconciliation does not test intrabar stop fills.** C2's stop-fill optimism, and the gap-through fix
  on BUILDER-2's branch (ledger GAP-P12D-84), still need the synthetic tick tapes (VAL R5).
- **This lane's model (June 2026 cutoff) wrote every design idea here.** They are all LLM-originated (GAP-P12D-66).

## 5. Proposed ledger items (no IDs)

| Item | S/L | Proposed status | Tag |
|---|---|---|---|
| The search-aware verdict cannot be computed from any register at BASE: attempts and looks store counts, not return vectors | high / high | open | [impl] |
| No single evaluation entry point, so the trial ledger is complete only by diligence | high / medium | open | [impl] |
| `passed` lacks an absolute OOS-CI condition; PBO alone passes a winner that keeps its rank but loses its edge | medium / medium | open | [spec — owner ratification] (with PLAN A2) |
| No passive-benchmark arm: a pooled trend rule's P&L on indices and metals is not separated from the long-drift premium | medium / high | open | [spec — owner ratification] |
| Daily-bar execution at the 17:00 New York rollover prices fills at the day's widest spread, and on Fridays falls inside FTMO's pre-close ban (links GAP-P12D-58) | medium / high | open | [impl] |
| `fitness.py` retirement is blocked by `core/signals/indicators.py:17`, and `evolve_step.py` retirement by the only CostModel factory (`evolve_step.py:44`) | low / high | open (sequencing note for A4) | [impl] |
| A tick-level engine confirmation of 30 instruments is infeasible (~70 core-days); the plan must name the hourly-bar reference | medium / high | open | [spec — owner ratification] (ACIS-09) |
| The innovation verdicts of §2.1, with revival conditions, recorded so that rejected methods are not re-proposed without new evidence | low / medium | accepted-risk (rejected methods) | [impl] (register graveyard motifs) |

## 6. Sources

All accessed 2026-09-25. **Grades:** (a) peer-reviewed, a regulator or a primary document; (b) a credible
practitioner or an unrefereed preprint; (c) unverifiable.

| Key | Source | Verbatim quote used | Grade |
|---|---|---|---|
| S1 | Gençay, "What survives honest evaluation?", arXiv 2608.27734v1 (27 Aug 2026). https://arxiv.org/abs/2608.27734 ; https://arxiv.org/html/2608.27734v1 | the quotes in §2.3; abstract: "rejects every LLM-discovered strategy (across two frontier models, search budgets up to one hundred candidates, and five repeated runs)" | (b) |
| S2 | Cederburg, O'Doherty, Wang & Yan (2020), *JFE* 138(1):95-117. https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html | "Volatility-managed portfolios do not systematically outperform their corresponding unmanaged portfolios in direct comparisons. ... the trading strategies implied by these regressions are not implementable in real time, and reasonable out-of-sample versions generally earn lower certainty equivalent returns and Sharpe ratios than do simple investments in the original, unmanaged portfolios." | (a) |
| S3 | Barroso & Santa-Clara (2015), *JFE* 116(1):111-120. https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html | "Managing this risk virtually eliminates crashes and nearly doubles the Sharpe ratio of the momentum strategy." (equity cross-sectional momentum) | (a) |
| S4 | Kim, Tse & Wald (2016), *J. Financial Markets* 30:103-124. https://ideas.repec.org/a/eee/finmar/v30y2016icp103-124.html | "We find that their results are largely driven by volatility-scaling returns (or the so-called risk parity approach to asset allocation) rather than by time series momentum. Without scaling by volatility, time series momentum and a buy-and-hold strategy offer similar cumulative returns" | (a) |
| S5 | Shu, Yu & Mulvey, arXiv 2402.05272 (7 Feb 2024). https://arxiv.org/abs/2402.05272 | "the optimal jump penalty selected through a time-series cross-validation method that directly optimizes strategy performance"; "major equity indices from the US, Germany, and Japan from 1990 to 2023" | (b) |
| S6 | Lim, Zohren & Roberts, arXiv 1904.04912 (9 Apr 2019). https://arxiv.org/abs/1904.04912 | "Backtesting on a portfolio of 88 continuous futures contracts, we demonstrate that the Sharpe-optimised LSTM improved traditional methods by more than two times in the absence of transactions costs, and continue outperforming when considering transaction costs up to 2-3 basis points." | (b) |
| S7 | Wood, Giegerich, Roberts & Zohren, arXiv 2112.08534 (16 Dec 2021). https://arxiv.org/abs/2112.08534 | "improves performance when considering returns net of transaction costs and naturally adapts to new market regimes" | (b) |
| S8 | Li, Kim, Cucuringu & Ma, FINSABER, arXiv 2505.07078 (KDD 2026 Datasets & Benchmarks, oral). https://arxiv.org/abs/2505.07078 | "previously reported LLM advantages deteriorate significantly under broader cross-section and over a longer-term evaluation"; "overly conservative in bull markets, underperforming passive benchmarks, and overly aggressive in bear markets" | (a) |
| S9 | Filippou, Rapach, Taylor & Zhou, CEPR DP15305 (2020). https://cepr.org/publications/dp15305 | "we use the elastic net to estimate a high-dimensional panel predictive regression and find that the resulting forecast consistently outperforms the naive no-change benchmark"; "When we allow for more complex deep learning models, nonlinearities do not appear substantial in the data." | (b) |
| S10 | Joubert (2022), "Meta-Labeling: Theory and Framework", *JFDS*. https://jfds.pm-research.com/content/early/2022/06/23/jfds.2022.1.098 (paywalled; abstract as returned by the search index) | "using a controlled experiment to show how each component helps to improve strategy metrics" | (a) journal; text not fetched |
| S11 | Singh & Joubert, "Does Meta-Labeling Add to Signal Efficacy?", Hudson & Thames. https://hudsonthames.org/wp-content/uploads/2022/04/Does-Meta-Labeling-Add-to-Signal-Efficacy.pdf (PDF text decoded; the extraction dropped the spaces, which are restored here) | "The focus for our research will be on S&P 500 E-mini futures, for the period 01 July 2011 to 13 February 2019"; "Only when we felt comfortable with the parameters then we used out-of-sample data"; the OOS table spans "2018-01-04:2019-01-28" | (c) vendor capstone |
| S12 | DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5):1915-1953. https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html | "Of the 14 models we evaluate across seven empirical datasets, none is consistently better than the 1-N rule in terms of Sharpe ratio, certainty-equivalent return, or turnover" | (a) |
| S13 | Hua et al., "Agentic Quantitative Trading: A Survey", arXiv 2608.31041v1 (31 Aug 2026). https://arxiv.org/html/2608.31041v1 | "strong model or forecasting capability does not reliably translate into trading performance under live market conditions and reliability controls" | (b) |
| S14 | "Agentic Trading: When LLM Agents Meet Financial Markets", arXiv 2605.19337v1. https://arxiv.org/html/2605.19337v1 | §13.3: "Few papers report failed prompts, abandoned reward schemes, degraded live performance, or architectures that increased turnover without improving net returns. We therefore interpret the absence of negative results as a reporting limitation" | (b) |
| S15 | Kong, Lee, Hwang, Lopez-Lira, Levy, Mehta, Wen et al., arXiv 2602.14233v1 (15 Feb 2026). https://arxiv.org/html/2602.14233v1 | "Among the 164 main conference papers we reviewed from 2023 to 2025 ..., only 26.8% acknowledge look-ahead bias, and survivorship bias appears in just 1.2% of studies." | (b) |
| S16 | He, Lv, Manela & Wu, "Chronologically Consistent Large Language Models", arXiv 2502.21206 (28 Feb 2025). https://arxiv.org/abs/2502.21206 | "ChronoBERT and ChronoGPT's real-time outputs achieve Sharpe ratios comparable to a much larger Llama model, indicating that lookahead bias is modest." | (b) |
| S17 | Benhenda, "Look-Ahead-Bench", arXiv 2601.13770 (20 Jan 2026). https://arxiv.org/abs/2601.13770 | "Results reveal significant lookahead bias in standard LLMs, as measured with alpha decay, unlike Pitinf models" (Pitinf models "from PiT-Inference") | (b); (c) for the claim about its own models |
| C1–C4, VAL, ARC, SYNTHESIS | `CLOUD_AUDIT/reports/*.md`; `/tmp/review-acis/archive/RESEARCH_*_2026-09-24.md` | cited by section, not re-quoted | prior reports |
| Code | BASE `974dbda` at `/tmp/review-acis`, cited as `file:line` in the text | — | S |
| R1, R2, R3 | `evidence/R1D/sim_rsim_daily.*`, `sim_hedge_vs_equal.*`, `probe_killlist_lines.*` | synthetic receipts | R |

**Not finished in the time box:**
- No primary fetch of the online-portfolio-selection cost literature.
- Harvey et al. was not verified at source.
- The NVMA and genome line splits are estimates, not range-measured.
