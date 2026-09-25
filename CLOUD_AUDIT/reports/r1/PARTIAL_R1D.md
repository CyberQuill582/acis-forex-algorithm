# PARTIAL R1-D — INNOVATION AND ARCHITECTURE (checkpoint 1, ~30 min)

- **Lane:** R1-D. **Model:** the system prompt names `claude-opus-5-5`; effort not observable from inside the session.
- **Fresh context:** yes; this lane saw only its brief, the prior reports and BASE.
- **BASE:** `974dbda`. **Date:** 2026-09-25. **Web used:** 8 of 40.
- **Status:** first findings only. The "For PLAN_R1" draft arrives in checkpoint 2.

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
