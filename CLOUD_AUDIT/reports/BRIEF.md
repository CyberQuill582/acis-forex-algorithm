# BRIEF — ACIS cloud review, pinned before launch (A4)

- **Lead:** the cloud lead session. The system reports model `claude-opus-5-5` (Opus 5.5). The reasoning
  effort cannot be observed from inside the session; the launcher configured xhigh. Every lane is launched
  with `model: "opus"`, and none is an Explore-type agent.
- **Reviewed commit (BASE):** `7695ed04abfeaa7535e237afcac25fb983025ff0` on `main`, per
  `CLOUD_AUDIT/SNAPSHOT.md`, handoff built 2026-09-24T17:27:44Z.
- **Session branch (the only one pushed):** `claude/acis-cloud-review-2026-09-24`. The container
  started on `main`, and reports must not be pushed to the default branch, so the lead cut this branch
  from `main` at BASE. The import command in `CLOUD_AUDIT/README.md` fetches `claude/*`, so this name fits it.
- **Pinned:** 2026-09-24, about 17:55 UTC.

---

## 0. Baseline (P0), run once in `/tmp/review-acis` at BASE — 2026-09-24 17:34 UTC

| Check | Result |
|---|---|
| `python -m pytest -q` | **808 passed, 6 skipped in 23.8 s.** This matches the laptop's count. The skips need `data/`. |
| `python scripts/ledger_check.py` | **187 entries, 0 violations** |
| `python scripts/governance_gate.py --session` | **RED (exit 1).** The comment-shape ratchet (A12) has 4 new violations: `core/optimizer/costs.py` HEADER+BLOCK and `scripts/cost_stress_ladder.py` HEADER+BLOCK. One burn-down is also pending (`core/data/feeds.py` HISTORY 1→0). The HEAD commit therefore does not pass the project's own session gate. This is a practicality finding for the lead, not a lane task. |

The container has 4 cores and 15 GB of RAM, with Python 3.11 and Node 22. `pip install` works.

## 0.1 Environment constraint every lane must know: the web egress is narrow

- **WebSearch works.** It returns titles and URLs, plus a summary written by the search tool.
- **WebFetch is blocked for most primary domains.** Probed and blocked: arxiv.org, ssrn, ftmo.com,
  help.darwinex.com and qoppac.blogspot.com. github.com is fetchable.
- **Rules:**
  - Try WebFetch on the primary URL once.
  - If it returns `EGRESS_BLOCKED`, you may cite the search result instead. Label it **"snippet-only, not
    fetched"** and **drop its grade by one level**: an (a) paper known only from a snippet counts as (b).
  - Never present a snippet summary as a verbatim quote from the source. Quote only what you fetched, or
    quote the local pass's verbatim quotes and attribute them to that pass.
- **Compute is the cloud's real advantage.** Spend effort there.

---

## 1. Field brief — what the profitable minority actually does (lead reconnaissance, ~11 searches)

This adds to the local ECONOMIST final (`_context/local-wip/files/archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`)
without repeating it. That report is the primary survey; read its §1.3–1.5 if your lane needs the playbook.

**What is solid (graded):**
1. **The base rates are brutal, and the minority is thin.**
   - Topstep's own 2025 cohort disclosure (snippet-only, via quantvps.com; the local ECONOMIST fetched
     and graded it (a)): 16.8% of Combines completed, 33.3% of funded traders ever paid, and 0.71% moved to
     live capital.
   - FPFX via Finance Magnates (ECONOMIST, (b)): ~14% pass, and ~7% are ever paid.
   - ESMA-mandated broker disclosures: 74–89% of retail CFD accounts lose money (snippet-only, (b)).
2. **The prop contract pays for variance.** The local ECONOMIST and ARCHITECT each derived independently
   that a zero-edge sizer passes a two-step challenge 25–37% of the time, and that
   P_pass = L/(L+T) at zero drift. **So "a minority is crushing it" is largely what survivorship produces
   under zero skill.** A pass, a payout or a leaderboard is not evidence of edge. This is the central
   "false encouragement" trap in the owner's own framing.
3. **What long-lived systematic practitioners do**, from verifiable records and the local pass's quotes:
   - **Few rules, at slow speed.** Carver's cost "speed limit": costs should consume at most about a third
     of the expected Sharpe. That pushes expensive instruments to holds of weeks. Trend at 3 weeks to 3
     months is where retail costs can still take part (snippet-only, qoppac.blogspot.com; (b)).
   - **Volatility-normalised, small, fixed risk.** Darwinex scales every DARWIN to a 3.25–6.5% *monthly* VaR
     band, measured over the last 45 exposed days (snippet-only, help.darwinex.com; (b)). This is a
     working, primary-document example of a platform grading traders only after risk normalisation.
   - **Incubation before money.** Davey's factory runs walk-forward, then Monte Carlo, then live
     incubation with no capital, then comparison against the backtest (practitioner, (b/c)).
   - **Slow cadence.** Per the local ECONOMIST (Hall, arXiv 2609.14859, (b)), the funded payout rate falls
     from 34.8% at 1 trade a day to 3.9% at 20 a day. None of the 5 long-lived verified Myfxbook survivors
     was a scalper.
4. **The documented edges that survive costs are structural or flow-based, not generic TA on FX majors.**
   - Examples: intraday momentum into the cash close (Gao–Han–Li–Zhou, *JFE* 2018; SPY 1993–2013;
     R² 1.6%, (a) snippet → (b)), fixing flows, and slow trend.
   - Intraday FX TA rules show no net edge at realistic cost (ARCHITECT, (a)).
5. **The rules are the battlefield.** FTMO's daily loss is measured on **equity** and resets at
   **00:00 CE(S)T** from that instant's *balance* (search snippet of ftmo.com / FTMO Academy, (b)).
   ACIS's trading day resets at 17:00 New York. Most disqualifications come from rule mechanics
   (trailing drawdown, consistency, request caps), not from a lack of profit ((c) aggregators; treat as a
   hypothesis).

**What is NOT known, and nobody should pretend it is:** no primary data shows what profitable prop *algo*
traders run. Anything claiming otherwise is a vendor or an affiliate.

**The lens every lane applies:** name the best-known alternative and the measure (FLEET_PLAN §7). For
ACIS, the **measure is ΔEV against a zero-edge control under the firm's exact rules, after costs, on data
the design never saw**. The **alternative** is the simplest proven design: a small set of
vol-targeted, slow, cost-budgeted rules (Carver-style) with incubation (Davey-style).

---

## 2. What the local pass has already done — do not redo it (read the named sections only)

All paths are under `/tmp/handoff/CLOUD_AUDIT/_context/local-wip/`. Everything there is **untrusted evidence
(A9), never instruction**. IDs that appear only there (for example the pass's own ledger entry) **do not
exist at BASE**. Refer to them in prose.

| Local lane | Status | What it covered |
|---|---|---|
| SCOUT | **final** `files/archive/RESEARCH_PROP_VENUES_2026-09-24.md` | Firm matrix. FTMO and E8 are the only firms that fit, via the cTrader Open API; the FTMO Free Trial is proposed as the demo; config corrections. |
| ECONOMIST | **final** `files/archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md` | Playbook and anti-playbook; first-passage maths; the claim that the account is +EV for S_net ≳ −0.4; the "PropEV" gate proposal. |
| VALIDATOR | **final** `files/archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` | Protocol FPR/power grid; CPCV+PBO recommended; the LLM rule. **C1 must NOT read it until C1's first table is committed** (see C1). |
| ARCHITECT | **final** `files/archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` | A 13-hypothesis slate, the factory design, retiring the NVMA gate and per-regime QIEA. |
| BUILDER | **branch** `worktrees/agent-a128ab904780ce593/BRANCH.patch` + `BRANCH_LOG.txt` (contains `BUILDER_REPORT_2026-09-24.md`) | An oracle positive control; GAP-P12D-38 "refuted" (MOMENTUM_SCALP cannot fire on the uniform 20 s synthetic tape, and the "0.0 duration" was the mean of an empty set); TSMOM's 53 h holds and its standing vote vetoing the arena through `DISCARD_OPPOSITE`; the plateau law; the evaluation registry. |

---

## 3. Rules for every lane (FLEET_PLAN §1, restated as binding)

- **Fresh context. Launch no subagents.** You are a finder, never a clearer.
- **Write only under `CLOUD_AUDIT/reports/`** in `/home/user/acis-forex-algorithm` (the session checkout):
  - your `PARTIAL_<LANE>.md`, then `<report>.md`;
  - evidence under `reports/evidence/<LANE>/`.
- **Evidence file and folder names must never contain `test` or `spec`, in any position.** Use `repro_*`,
  `sim_*` and `probe_*`. No file may exceed 2 MB, and no market data is allowed at all.
- **Run code in the review tree `/tmp/review-acis`** (BASE, dependencies installed) or in your own copy
  `/tmp/<lane>-acis`.
  - Anything that mutates source, including `scripts/mutation_gate.py` or logging patches, runs **only in
    your own `/tmp` copy**.
  - Never modify `/tmp/review-acis`: other lanes share it.
  - Never modify anything in the session checkout outside `CLOUD_AUDIT/reports/`.
- **Synthetic data only.**
  - No historical prices from any source, including datasets bundled with libraries (`arch.data`,
    `statsmodels.datasets`, and the like).
  - Never read the prices in `tests/backtest/fixtures/*.bi5`.
  - Never run `scripts/download_*`, `dl_common.py`, `dl_supervisor.ps1`, `build_labelled_bars.py` or
    `run_data_validation.py`. Run `run_oos_validation.py` only on synthetic input.
- **The guardrails are owner-only:** `config/guardrail_limits.yaml`, the equity floor, and the HALT, veto and
  resume semantics. Findings about them are tagged **[owner decision]**.
- **Never present in-sample numbers against the §14 targets.** Mark every idea generated or refined by an
  LLM (you included) as **LLM-originated**, and say which data could test it honestly.
- **Ledger IDs:** cite only IDs that exist in `/tmp/review-acis/KNOWN_GAPS.md` or `KNOWN_GAPS_CLOSED.md` at
  BASE. Name new items in prose.
- **Never copy code from any source.** Extract the lesson and cite it. Do not read leaked or closed-source
  harness internals.
- **Commit and push your own files, by path, every time you update them:**
  ```bash
  cd /home/user/acis-forex-algorithm
  git add CLOUD_AUDIT/reports/<your files> && git commit -m "<LANE>: <what>" -- CLOUD_AUDIT/reports/<your files> && git push origin claude/acis-cloud-review-2026-09-24
  ```
  - On `index.lock` or a rejected push, wait 5–10 s and retry; up to 4 tries with backoff.
  - Never pull, rebase, force, `add -A` or `add .`, and never make a bare commit.
- **Durability:** write your PARTIAL within about 30 minutes and keep it current. The final report
  replaces it; leave the PARTIAL in place.
- **Report contract** (FLEET_PLAN §6):
  - **Header:** the lane; the model and effort as observed; an attestation of fresh context; BASE; the
    date; the web searches used.
  - **Sections:**
    1. an executive summary of at most 10 bullets, each graded;
    2. the body;
    3. what I could not verify;
    4. residual risk;
    5. proposed ledger items (no IDs; Severity, Likelihood and proposed Status; tagged **[impl]**,
       **[spec — owner ratification]** or **[owner decision]**);
    6. sources, with URL, date accessed and grade.
  - **Every recommendation states both its VALUE and its COMPLEXITY COST:** lines and concepts added or
    removed.
- **Time box:** write your final report before the box ends, even if it is incomplete, and state what is
  unfinished. The lead stops any lane more than 15 minutes over.
- **The stop phrase:** if the lead relays "acis: stop lanes, synthesise, push", you have 10 minutes to write
  your final and push it.

---

## 4. The lanes

The lead re-cut the mission's lanes after reconnaissance. **Why:**
- The local VALIDATOR has landed a final that covers most of C1's original core grid.
- BUILDER has already built the oracle and addressed GAP-P12D-38.

So C1 pivots to **independent replication** plus the protocols and the prop-objective question the local
pass left open or disputed. C3 pivots to **multi-seed scale, ablation and the horizon test**, building on
BUILDER's single-seed findings.

### C1 CALIBRATOR — 3 h box · ≤ 12 web searches · `reports/C1_CALIBRATOR.md`, evidence `reports/evidence/C1/`

**Mission.** Independently measure what ACIS's validation protocols actually certify: their false-positive
rate (FPR) under a realistic search, and their power at a modest real edge. Then give the number of
real-data looks ACIS can afford. Adjudicate the prop-objective question.

**Framing discipline (binding).**
- Build your own simulator from the code and first principles, and commit your first results table
  **before** you open any local VALIDATOR file (`PARTIAL_VALIDATION_FIREWALL_*` or
  `RESEARCH_VALIDATION_FIREWALL_*`).
- Only then read it, compare, and reconcile. State which result is right, and why.
- Agreement from an independent path is itself a finding.

**Core grid (must finish).**
- **Data shape:** 8 instruments, daily and hourly resolution as appropriate, a 2012–2023 development span
  (12 years) and a 2-year holdout.
- **Nulls:** iid, GARCH(1,1)-t, and a common factor at ρ ≈ 0.4.
- **Planted edges:** multi-day at annual Sharpe 0.5 and 1.0, and intraday at 0.5, at one realistic prop
  cost.
- **Search:** N ∈ {1, 60, 1000} configurations, selected by the protocol's own in-sample stage.
- **The outer loop:** K ∈ {1, 20} pipeline revisions re-scored on the same history (keep the best).
- **Protocols:**
  - **as built:** walk-forward plus the repo's DSR gate. Import `tests/backtest/deflated_sharpe.py`,
    `report.py`, `walk_forward.py` and `oos_plan.py` **read-only**, and reproduce how `passed` uses them;
  - walk-forward with a repaired DSR (honest N, floored trial variance, a commensurate basis);
  - CPCV with PBO (CSCV);
  - Hansen's SPA (the `arch` package is allowed; its bundled datasets are not);
  - Romano–Wolf StepM;
  - the Harvey–Liu–Zhu haircut;
  - Bailey–López de Prado MinBTL;
  - a 2-year time holdout.
- **Replications:** R = 2,000 per cell (1,000 for CPCV), each with a Monte-Carlo CI. If the box forces
  fewer, say so and give the resulting CIs.
- **Use all 4 cores** (multiprocessing), with vectorised numpy strategies. Do not use the ACIS engine.

**Deliverables.**
- The main table: protocol × null family, giving FPR (with CI), power at Sharpe 0.5 and 1.0 (with CI), data
  needed, and compute.
- **The detectability frontier:** the years needed for 80% power at FPR ≤ 5%, as a function of Sharpe, at
  realistic N and K.
- The recommended protocol (possibly a stack of several), with its **looks budget** for 2012–2023 and the
  kill criteria.

**Extended, and consequential for money.** Do this before any other extended cell.
- **Adjudicate the prop-EV claims.** The local passes disagree on the zero-edge pass probability of a
  2-step challenge: ~25% (ARCHITECT, FTMO), 37%/33% (ECONOMIST, FundedNext/FTMO), 49.7% (VALIDATOR,
  "illustrative rules").
  - ECONOMIST claims a disciplined **zero-edge** static-floor account is **+EV** (≈ +$88 per $6K attempt),
    with a working threshold of "S_net ≥ 0".
  - Build your own first-passage Monte Carlo under an **FTMO 2-Step Swing $10k**-style rulebook:
    - a 10% phase-1 target and a 5% phase-2 target;
    - a 5% daily loss on **equity**, reset at **00:00 CE(S)T** from that instant's **balance**, with the
      loss measured intraday;
    - a 10% static max loss on equity;
    - 4 minimum trading days;
    - a fee of about €89, refundable with the first reward;
    - an 80–90% split.
  - Use fat tails, overnight/weekend gaps, and a trading **cost** drag that depends on turnover.
  - Is a zero-edge account +EV **after the costs a real strategy pays**? At what OOS Sharpe and turnover
    does EV cross zero?
  - How many months of OOS or demo record make the CIs on P(pass), P(breach) and EV useful (block
    bootstrap)?
  - **This is the number the owner's money rests on. Be ruthless about false encouragement.**
- Then, if time remains: regime-switching volatility, Sharpe 0.25, a second cost level, N ∈ {10, 200},
  K = 5, and the Masters permutation test.

**Do not duplicate:** the local VALIDATOR's LLM-contamination survey, or its leakage-paper task.

### C2 FALSE-ENCOURAGEMENT HUNTER — 2 h box · ≤ 10 web searches · `reports/C2_HARNESS_REDTEAM.md`, evidence `reports/evidence/C2/`

**Mission.** Find every way the ACIS harness can report a profit the market would not have paid, each
reproduced in code on a synthetic fixture. Attack from the code **first**: the spec's justifying prose is
untrusted framing (A4).

**Scope.**
- `tests/backtest/`: `harness`, `book`, `walk_forward`, `oos_plan`, `report`, `metrics`,
  `deflated_sharpe`, `financing`, `carry`, `rollover_marks`, `boundary_clock`, `data_loader`, `bi5`
  (decoder logic only; never the fixture's prices), and `synthetic_market`;
- `core/optimizer/fitness.py` and the C8 cost object (`core/optimizer/costs.py`);
- `core/data/bars.py` and the FX clock;
- `config/instruments.yaml`;
- `scripts/falsify_engine.py` and `scripts/cost_stress_ladder.py`.

**Attack classes.** Mark each one caught, not caught, or not applicable, with a reproduction.
- **Look-ahead:**
  - a signal on an incomplete bar, or a close used before it exists;
  - rollover-anchored daily bars;
  - indicator warm-up;
  - cross-instrument timestamp alignment (pair legs);
  - fold boundaries: GAP-P12D-35 was one; find its siblings.
- **Fills:**
  - buys at the ask and sells at the bid;
  - stale quotes, or fills at the mid;
  - stops and limits gapped through. **Seed:** `core/optimizer/fitness.py:115-125` exits at the stop price
    even on a gap. Confirm it, find its siblings in the tick `book`, and say whether the *graded* harness
    has the same flaw as the *fitness* sim;
  - opening and closing on the same tick;
  - partial fills and latency.
- **Costs:**
  - the spread at the 17:00 New York rollover and around news;
  - commission and slippage;
  - the swap sign and the triple-Wednesday charge;
  - what the cost-stress ladder really covers.
- **Configuration look-ahead:** costs or parameters calibrated on data that overlaps later folds or the
  holdout. **Seed:** `config/instruments.yaml:98-101`. Find the rest.
- **Selection look-ahead:** the universe, the regime thresholds and the module set chosen with knowledge
  of the whole period; survivorship.
- **Accounting:**
  - equity marks (intraday vs close) and how drawdown is measured;
  - P&L currency conversion (GAP-P12D-05);
  - compounding;
  - trade counting.
- **The synthetic generator as a grader:** does `synthetic_market.py`'s tape (uniform 20 s ticks, per the
  local BUILDER) make whole modules untestable, or make the planted market easier or harder in ways that
  mislead? What would a faithful positive-control tape need?
- **The canary itself:** build a leak that passes `refuse_lookahead` and
  `tests/backtest/test_lookahead_canary.py`.

**For every confirmed hole:** a minimal synthetic reproduction script, plus the regression test the local
lead should write, **described in prose**.

**Do not duplicate:**
- the local VALIDATOR's leakage-paper task (its §7 lists eight structural tests; extend them, don't redo
  them);
- the local BUILDER's `_avg_duration` empty-mean fix (read `BRANCH.patch`, and check that its fix is right).

### C3 ENGINE FORENSICS AT SCALE — 3 h box · ≤ 5 web searches · `reports/C3_ENGINE_FORENSICS.md`, evidence `reports/evidence/C3/`

**Mission.** Run what the laptop cannot: the real engine, end to end, on synthetic markets, across many
seeds. Establish **why** ACIS loses on its own positive control, and whether ACIS **as built** can capture
the kind of edge that survives retail and prop costs.

**Setup.**
- `cp -r /tmp/review-acis /tmp/acis-forensics` and work only there. Check `nproc` (4) and `free -g`
  (15 GB), and parallelise across seeds within memory.
- You may patch logging in that copy. BUILDER found that the replay logger keeps only the first 200 events
  of each type and records no close events. **Describe every patch in the report, and never commit patched
  code.**
- You may apply BUILDER's `BRANCH.patch` in a *second* copy, if it helps, to compare against its oracle.

**Tasks, in priority order.**
1. **Replicate GAP-P12D-49,** the planted market at the 1× rung, with the settings of
   `scripts/cost_stress_ladder.py` and `scripts/falsify_engine.py`.
   - First time a single run and project the cost. Then run as many seeds of planted, null and coin-flip
     as the box allows (target 5 each).
   - Report each module's P&L across seeds: the mean and a CI.
   - Is "TSMOM is the whole loss; TREND and BREAKOUT capture the edge" robust, or one seed's luck?
   - If a full run cannot finish, use the largest informative subset (fewer folds or a shorter span) and
     say so.
2. **Ablation.** This is the cheapest decisive experiment.
   - Rerun the planted market with TSMOM disabled (and, separately, with TSMOM kept but prevented from
     vetoing through `DISCARD_OPPOSITE`), by config or a throwaway patch.
   - Does the engine then capture the planted edge net of costs, across seeds?
   - This tests BUILDER's "the standing vote vetoes the arena" at scale.
3. **The horizon test** (the most strategic question).
   - Plant a **multi-day** trend: episodes lasting days to weeks, with drift sized to an annual Sharpe of
     about 0.5–1.0.
   - Run the engine at realistic retail/prop costs.
   - Can ACIS as built capture it? If not, name the component that prevents it, with evidence: the
     decision clock, the 48 h `max_hold_s`, the regime gate, the QIEA fitness window, the Governor, or
     `DISCARD_OPPOSITE`.
4. **TSMOM faithfulness:** what `_tsmom` computes on 1-minute bars, compared with Moskowitz–Ooi–Pedersen.
   Extend BUILDER's point 6; don't repeat it.
5. **The invisible genes (GAP-0035):** how much of the per-module P&L variance comes from genes that fitness
   cannot see? Use seed-varied evolution.
6. **Record the runtime of every run.**

**Coordination.** BUILDER's single-seed claims are the hypotheses you test at scale. Where it disagrees with
you, say so and explain.

### C4 PROVEN PARTS & THE KILL LIST — 2 h box · ≤ 25 web searches · `reports/C4_PROVEN_PARTS.md`

**Mission.** Decide for each ACIS component: **KEEP, SIMPLIFY, REPLACE-with-a-proven-part, or RETIRE**, with
evidence. The aim is a smaller, sharper ACIS. You are the **software and systems lens**, not the strategy
lens.

**Tasks.**
1. **Inventory** (with lines of code, tests, open gaps and the spec requirement served) for:
   - the 12-regime NVMA gate;
   - QIEA (11 genes, per regime × instrument);
   - AGON's six modules;
   - the Governor;
   - the Risk Monitor;
   - the Execution Orchestrator;
   - the MCP plane;
   - event and news intake;
   - the backtest harness;
   - the governance machinery (the gate scripts, ledger tooling and module-budget ratchet — are they
     growing faster than the product?).
2. **Degrees of freedom.**
   - Estimate the effective search space: regimes × instruments × genes × modules × pipeline revisions.
   - Compare it with what 12 years on 8 instruments supports, using a MinBTL-style bound (C1's frontier if
     it has landed in `reports/`).
3. **Referents** (read, don't copy, mind the licences):
   - Carver's `pysystemtrade` (**GPL-3.0**: lessons only):
     - forecast scaling and capping;
     - volatility targeting;
     - position buffering as a no-trade band;
     - cost-based speed limits;
     - instrument diversification;
     - handcrafting instead of optimisation;
   - NautilusTrader: backtest/live parity, adapters, the order state machine;
   - QuantConnect LEAN and vectorbt;
   - CPCV/PBO implementations (skfolio, mlfinlab);
   - `arch`.

   For each ACIS component, ask which proven design does the job with fewer parameters.
4. **Accelerate the demo** (the owner's top priority). Which maintained, permissively licensed SDKs or
   frameworks shorten TODO Track A steps 3–5: the practice adapter, the three-loop runtime, and the feed
   and reconnect?
   - Venues: the **cTrader Open API** (SCOUT's front-runner, via FTMO or E8), an OANDA v20 practice
     account, and an MT5 bridge.
   - For each candidate: licence, maturity, Linux support, server-side stops, and what ACIS still owns.
   - Respect the LLM-free fast loop and the §7.5 adapter contract.
   - Name the **smallest** demo runtime that could put a first order through the existing Governor and
     Risk Monitor.
5. **The kill list:** what to delete, the lines saved, and the evidence that each item adds no
   out-of-sample value or is superseded.

**Do not duplicate:** ARCHITECT's edge slate and "minimal changes". Read its final §-headings, and cite it
rather than repeating it.

### C5 MONEY-PATH SAFETY — 2 h box · ≤ 15 web searches · `reports/C5_MONEY_PATH.md`

**Mission.** Find every way the path from signal to broker and back can lose money, lose control, or break
a firm's rules for reasons that have nothing to do with edge. Then write the pre-first-order checklist.

**Scope.**
- `core/governor/`, `core/execution/` and `core/risk/`;
- `config/*.yaml` (read-only);
- `monitoring/` and `deploy/`;
- `scripts/acis_watchdog.py`;
- the §9.5 rulebook machinery;
- the adapter contract and the mock adapter;
- TODO Track A; GAP-0075, GAP-0091b, GAP-0099 and GAP-0020.

**Attack list.**
- **The order lifecycle:**
  - idempotency and client order IDs across retries and reconnects;
  - duplicates;
  - orphaned positions after a crash or restart (the broker is the truth to reconcile against);
  - partial fills and rejects;
  - the per-tick firehose (GAP-0075) against rate caps (FTMO: 2,000 server requests a day).
- **Protection:**
  - a server-side stop on every position (master §279);
  - death of the process, VPS or network with positions open;
  - weekend gaps through stops;
  - the watchdog's flatten path.
- **Time:**
  - the laptop clock runs about 16 min slow (GAP-P12D-51). Which decisions hang on the wall clock: the
    17:00 New York reset, news blackouts, session opens, rollover?
  - **FTMO resets its daily loss at 00:00 CE(S)T from that instant's balance, on equity**, while ACIS's
    trading day resets at 17:00 New York. Can ACIS track a daily limit anchored somewhere else?
  - What guards NTP and skew?
- **Rules.** Confirm SCOUT's three findings:
  - the $9,000 equity floor halts a $6k account;
  - daily-loss rules cannot be expressed (`resets_daily=False`);
  - sizes at $6k fall below the minimum lot.

  Also confirm SCOUT's "a restart re-bases every platform drawdown to 0%". Then find what else breaks.
- **The control plane:**
  - can any path, config or MCP tool weaken a guard?
  - is resume human-token only?
  - how fast does the kill switch act?
- **History:** documented failures of automated retail/prop accounts and of broker APIs, cited.

**Output.**
1. A defect list: `file:line`, a unit-level synthetic reproduction where feasible, and a severity.
2. A **pre-demo checklist** (what must be true before the first demo order) and a **pre-funded checklist**.
3. A day-one demo runbook outline: what to watch, and when to halt.

**Do not duplicate:** SCOUT's rule matrix and pre-mortem. Extend them into engineering failure modes.

---

## 5. What the lanes must not see in advance

The lead keeps the P3 reconciliation checklist from the mission and does not relay it. In particular, the
local VALIDATOR's headline numbers are withheld from C1 until its first table is committed.
