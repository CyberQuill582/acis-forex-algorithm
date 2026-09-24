# C4 — PROVEN PARTS & THE KILL LIST (ACIS cloud review, run 2)

- **Lane:** C4, the software and systems lens (not the strategy lens).
- **Model and effort, as observed:** `claude-opus-5-5` (Opus 5.5). Effort cannot be observed from inside the session; the launcher configured xhigh.
- **Fresh context:** yes. Run 2 started in fresh context, launched no subagents, and started from run 1's `PARTIAL_C4.md`, re-verifying it (the inventory probe reproduces byte for byte).
- **BASE:** `7695ed04abfeaa7535e237afcac25fb983025ff0`, read-only at `/tmp/review-acis`.
- **Date:** 2026-09-24, 18:04–~18:20 UTC.
- **Web use:** 2 WebSearch calls (limit 25). WebFetch was used on the primary pages listed in §6. The PyPI JSON API and the OSV.dev API were called from a script (`evidence/C4/probe_sdk.py`).
- **Evidence:** everything is under `reports/evidence/C4/`:
  - `probe_inventory.py` + `.out.md`: size, tests and open gaps per component;
  - `probe_dof.py` + `.out.md`: the degrees-of-freedom and MinBTL arithmetic;
  - `probe_sdk.py` + `.out.md`: the demo-SDK registry and advisory facts.
- **Every line estimate below counts physical lines at BASE** (`wc -l`). The estimates of what a replacement would cost are **LLM-originated guesses** and are labelled as such.

---

## 1. Executive summary

1. **The DSR counts a small fraction of what QIEA actually searches.**
   - QIEA runs 20 × 30 = 600 fitness evaluations per (regime, instrument). That is 9 tradeable regimes × 8 instruments = **43,200 evaluations per fold** over an 88-bit genome (`config/system_config.yaml:67-69`, `core/optimizer/qiea.py:161-170`, `tests/backtest/evolve_step.py:78-91`).
   - The graded Deflated Sharpe counts only the surviving champions' holdout Sharpes as its trials: at most 72 per fold (`tests/backtest/harness.py:217-218`). That is about 600× fewer than the evaluations searched.
   - Even at an effective N of 100 independent trials, MinBTL at an annual Sharpe of 0.5 is **~26 years**. Each fold's search sees a 2-year window, and within it a regime's own bars only. Under the null, the in-sample Sharpe of the best of N=1,000 on a 20% regime share of 2 years is **~5.2**.
   - **Grade (a) for the method** (Bailey & López de Prado) and **code-verified for the counts**. The per-regime share of 20% is an assumption. **→ RETIRE QIEA from the live path; handcraft plus a plateau grid.**
2. **The contract as written does not fit the venue SCOUT favours** (cTrader).
   - cTrader Open API: an absolute `stopLoss` is *"Not supported for MARKET orders"*; only a `relativeStopLoss` distance is.
   - ACIS §7.5 demands an absolute stop placed *"atomically with the fill"* (`core/execution/venue.py:157-160`). The conformance gate asserts exact equality: `assert stops.get("EUR_USD") == 1.09` (`tests/integration/test_adapter_conformance.py:143`).
   - So a faithful cTrader adapter either fails the gate after any slippage, or places the stop in two steps (not atomic).
   - OANDA v20's `stopLossOnFill.price` fits the contract 1:1. **(a), fetched primary docs.**
3. **The official cTrader Python SDK should not be a dependency.**
   - `ctrader-open-api` 0.9.2 (MIT, last release 2024-06-26) **exact-pins** Twisted 24.3.0, pyOpenSSL 24.1.0, protobuf 3.20.1 and requests 2.32.3.
   - Per OSV, those pinned versions carry **10 published CVEs** between them.
   - It is Twisted-based, while ACIS is asyncio.
   - Spotware's `.proto` files are MIT and can be compiled against a current protobuf instead. **(a), registry/OSV API, `evidence/C4/probe_sdk.out.md`.**
4. **The graded backtest does not run the production money path.**
   - The graded runner composes the test-side `build_paper_loop` (`tests/backtest/oos_runner.py:113`) plus a test-side `PositionModel` whose stop/target/max-hold exits (`tests/backtest/book.py:115-124`) have **no production counterpart**. TODO Track A step 4 says the runtime must *"add the position/holding policy the backtest book stands in for today"*.
   - The Risk Monitor's daily drawdown is re-derived in `tests/backtest/portfolio_view.py:12-14`.
   - That is two implementations of the same rules, and the one that trades has not been written yet.
   - NautilusTrader's design rule is the referent: *"The same strategy and execution-algorithm code can run across backtest and live systems"*. **(a) code; (b) referent.**
5. **Governor sizing is notional, not risk.**
   - `raw_usd = base_unit × conviction × liq × corr × regime_f × marginal_alpha × vol_f × taper` (`core/governor/capital_governor.py:283-284`). The stop distance never enters it.
   - Stops are `sl_mult × ATR` with `sl_mult` from 1.0 to 3.5, or **10.0 for TSMOM** (`core/signals/agon.py:280-291`, `config/system_config.yaml:40`). At equal notional, dollar risk to the stop varies by up to **10×**.
   - `vol_norm` is dampen-only: *"1.0 at/below the declared target"* (`core/governor/factors.py:43-50`). So it is not volatility targeting.
   - **REPLACE the kernel with risk budget ÷ stop distance** (Carver-style volatility scaling), and keep every dampen-only guard. **(a) code.** The link to TSMOM's loss is an LLM-originated hypothesis for C3.
6. **Process is outgrowing the product.** Measured from 85e1cf0 (2026-09-13) to BASE:
   - production Python grew **+3.0%**; live Markdown **+20%**; `archive/` 58 KB → 1,017 KB; tests +51%;
   - there were 87 root-Markdown file touches against 12 in `core/`;
   - the "short" orienting read path is **65,839 words**, twice the words of all production code (33,072);
   - `throwaway_ui/` holds 1.5 MB of JPEGs, **31% of tracked bytes**;
   - the governance *tooling* is lean (560 lines); the bloat is in the prose.
   - **(a) command-verified.**
7. **Event intake is built but not composed.**
   - `core/data/events.py` (295 lines) is imported by one test file only.
   - The paper loop defaults blackouts and Tier-G to always-False (`tests/integration/paper_loop.py:210-211, 236, 269`).
   - The graded runner declares this (`oos_runner.py:17,48`, NO_CALENDAR), so it is honest, but it is not wired. **(a) code.**
8. **S3 (Carver's speed limit) is VERIFIED at the primary source and upgraded to (b), a practitioner with a public record.**
   - Primary quote: *"DO NOT SPEND MORE THAN ONE THIRD OF YOUR EXPECTED PRE-COST RETURNS ON COSTS"*.
   - pysystemtrade encodes it as `ceiling_cost_SR: 0.13`.
   - The "trend at 3 weeks to 3 months" clause was **not found verbatim**. What was found is a worked example: *"a holding period of about 6 to 7 weeks"*. **Downgrade that clause to (c) paraphrase.**
9. **S4 (Darwinex VaR band) is VERIFIED at the primary source and upgraded to (a), a primary document.**
   - *"the target risk of all DARWINs is the same, 6.5% monthly VaR"*
   - *"oscillate in between a monthly 3.25 and 6.5% VaR"*
   - *"the last 45 days in which the trader has remained exposed to the market"*
   - 95% confidence and a 1-month horizon, per help.darwinex.com/var.
10. **The smallest demo runtime** (the owner's first priority) is about **400–600 new lines**, and it needs **no framework**. It is LLM-originated, and the estimate needs building to confirm.
    - A single asyncio process: an OANDA v20 practice face on `httpx`, or a cTrader face on asyncio TLS with compiled protos.
    - The existing `build_paper_loop` composition, promoted to `core/`, plus the Orchestrator and a RiskMonitor gate.
    - Exits delegated to **broker-side SL+TP brackets**, plus one max-hold timer.
    - One open position per instrument, as the stop-gap for GAP-0075.
    - One instrument and one module.
    - **Grade (b):** my own design, built on verified contracts.

---

## 2. Body

### 2.1 Inventory (task 1), re-verified

The receipt is `evidence/C4/probe_inventory.py`. Re-running it at BASE reproduces `probe_inventory.out.md` exactly.

| Component | files | lines | test fns (files) | open/mitigated gaps citing its path | Spec requirement served |
|---|---|---|---|---|---|
| NVMA 12-regime gate (`core/regime`) | 5 | 548 | 189 (20) | 7 | master §4, ACIS-02 |
| QIEA + param library + fitness + costs (`core/optimizer`) | 6 | 967 | 152 (19) | 12 | master §5, ACIS-03 |
| AGON arena, 6 modules, provenance (`core/signals`) | 6 | 1,199 | 123 (10) | 11 | master §5.6, ACIS-04 |
| Capital Governor (`core/governor`) | 7 | 750 | 124 (10) | 4 | master §6/§7, ACIS-05 |
| Risk Monitor, guardrails, scenario book (`core/risk`) | 8 | 1,249 | 69 (7) | 6 | master §8/§9, ACIS-07 |
| Execution Orchestrator + adapter contract (`core/execution`) | 3 | 753 | 70 (6) | 3 | master §7.5, ACIS-06 |
| MCP plane (`monitoring`) | 9 | 748 | 50 (5) | 2 | master §12, ACIS-08 |
| Event/news intake (`core/data/events.py`) | 1 | 295 | 22 (2) | 0 | master §3.5–3.6, ACIS-10 |
| Data layer (rest of `core/data`) | 11 | 1,010 | 386 (32) | 7 | master §3, ACIS-01 |
| Backtest harness (`tests/backtest`, non-test files) | 28 | 3,125 | 189 (27) | 16 | master §14, ACIS-09 |
| Governance tooling (ledger/gate/concordance/mutation scripts) | 4 | 560 | 8 (3) | 2 | constitution A12–A16 |
| Falsification / ladder / OOS runners | 3 | 333 | 12 (2) | 4 | ACIS-09 |
| Watchdog | 1 | 190 | 9 (1) | 0 | master §8.6 |

**Caveats on the table:**
- `config/schemas.py` (616 lines) is shared and not attributed to any row.
- The "test fns" column counts the tests in files that import the component. That over-counts shared tests.
- Production code (`core/` + `monitoring/`) is **7,519 physical lines, of which 6,186 are non-blank and non-comment.**

**Config surface:**
- `system_config.yaml` has 100 numeric knobs: regime 20, signals 20, optimizer 11, execution 11, risk 10, monitoring 10, data 10, governor 4, provenance 2, and a few more.
- `instruments.yaml` adds 55 and `platform_rules.yaml` 27.
- Count method: `yaml.safe_load` and a count of the int/float leaves. The script is inline in the session. It is reproducible with the 10-line snippet in the `probe_dof.py` style.

**Growth, process against product** (`git ls-tree -r -l <commit>`, byte sums by path class):

| | 85e1cf0 (2026-09-13) | BASE (2026-09-24) | Δ |
|---|---|---|---|
| `core/`+`monitoring/` .py | 326,141 B | 335,797 B | +3.0% |
| live .md (non-archive) | 975,260 B | 1,172,747 B | +20% |
| `archive/` | 58,107 B | 1,016,960 B | ×17.5 |
| `tests/` .py | 469,271 B | 710,651 B | +51% |

- **File touches since 2026-09-13:** tests 104, root `.md` 87, archive 24, throwaway_ui 17, core 12, scripts 11, specs 10.
- **The read path, in words:**
  - README 536; STATUS 1,348; **TODO 15,442**; CLAUDE 3,761; ACIS_SPEC 15,906; specs index 1,361; **KNOWN_GAPS 27,485**;
  - total **65,839**, plus 34,014 words in `specs/`.
- **What this means.** The governance scripts themselves are small and earn their keep: the ledger check, the module budget and mutation-gate runner are 560 lines. What grows is prose that each session must read and keep true. By its own CLAUDE.md rule, a read path this long is a defect, and the constitution adoption gate's step 2 (hygiene) has been open since 2026-07-21 (CLAUDE.md, adoption-gate block).

### 2.2 Degrees of freedom (task 2)

The receipt is `evidence/C4/probe_dof.py`. It reads the BASE config, uses the stdlib only, and touches no data.

**Structure (code-verified):**
- Genome: 11 genes × 8 bits = 88 bits (`core/optimizer/param_types.py:17-29`, `qbit_resolution: 8`).
- Evaluations: population 20 × generations 30 = 600 fitness evaluations per `evolve()` (`qiea.py:161-170`).
- `evolve_fold` runs QIEA for **every tradeable regime (9) × every instrument (8)**. It then stages **one** ParamSet per regime: the instrument whose champion had the best **holdout** E[R] (`tests/backtest/evolve_step.py:78-107`).
  - Two consequences:
    - (i) that holdout is used for **selection** across 8 candidates, so it is no longer a clean holdout for the staged set;
    - (ii) a set evolved on instrument X is applied to all 8 instruments.
  - Both are LLM-originated readings of the code; C2 owns the leakage verdict.
- Other freedoms: 2^6 = 64 module on/off combinations; 100 + 55 numeric config knobs; K pipeline revisions (the spec went from v2.11 to v2.18 in September alone).

**Noise ceiling and MinBTL** (Bailey & López de Prado expected maximum of N iid N(0,1)):

| effective N | E[max z] | noise-max annual SR, 2y window | same, 20% regime share | MinBTL yrs @SR 0.5 | MinBTL yrs @SR 1.0 |
|---|---|---|---|---|---|
| 10 | 1.57 | 1.11 | 2.49 | 9.9 | 2.5 |
| 100 | 2.53 | 1.79 | 4.00 | 25.6 | 6.4 |
| 1,000 | 3.26 | 2.30 | 5.15 | 42.4 | 10.6 |
| 43,200 (raw per fold) | 4.20 | 2.97 | 6.65 | 70.7 | 17.7 |

**What the data can support:**
- 12 development years × 8 instruments.
- At a common factor of ρ ≈ 0.4, the 8 series are worth about 2.1 independent series, so about **25 instrument-years in total**. Each fold's search sees only **2 years**, and a regime sees only its share of that.
- QIEA's trials are correlated (it converges), so the effective N sits somewhere between about 100 and 43,200. **Even the kindest row needs more data than one fold's window holds, by a factor of 12 or more.**
- C1's frontier had not landed in `reports/` when this was written. Its protocol FPR numbers supersede this back-of-envelope wherever they disagree.

**What would fit the data:**
- Fixed literature parameters: **handcrafting**, pysystemtrade's recommended default (*"Personally I'd use handcrafting, which is the default."*).
- A ±10% plateau grid per module (the existing law, GAP-P12D-34), over **a few** configurations per module.
- One pooled parameter set across instruments.
- The result: N falls from about 43,200 per fold to about 10–30 in total, which moves MinBTL at SR 0.5 into the 10-year range the data can afford.

### 2.3 Referents (task 3): which proven design does each job with fewer parameters

Lessons only. Nothing is copied. pysystemtrade is GPL-3.0 and was read for its documentation only.

| ACIS component | Proven referent | Lesson | Parameter delta |
|---|---|---|---|
| AGON conviction + conflict table | pysystemtrade forecast scale and cap: *"Scale forecasts so they have the right average absolute value … Cap forecasts at a maximum value"* (`forecast_cap: 20.0`, average absolute 10) | A continuous, capped forecast per rule, combined by fixed weights, replaces conviction thresholds, `conviction_discard`, `medium_vol_discount` and discard-both-on-conflict. Netting happens in the forecast, not by veto. ARCHITECT change 2 covers the target-position Governor; this is its signal-side twin. | −3 knobs and −1 table; +1 scalar per rule, estimated once |
| Governor sizing (7 multiplicative factors) | Carver volatility targeting (`percentage_vol_target`) | Position = capital × vol target × forecast/10 ÷ instrument vol, applied in **both** directions. ACIS's `vol_norm` only cuts. | Remove `marginal_alpha` (73 lines, a sizing factor that rises to 1.5× after recent wins, the "hot hand") and `regime_f`. Keep liquidity, cluster cap, taper, calendar and lot cap as dampen-only guards. |
| GAP-0075 firehose / no exit policy | pysystemtrade buffering: *"If it's not within 10% (the 'buffer') then we trade to the optimal position, otherwise we don't bother."* | A no-trade band around a target position is the whole order-rate policy, and an exit is the target going to 0. | +1 knob (`buffer_size`) |
| Cost gate (C8 + ladder) | `ceiling_cost_SR: 0.13` ("Max cost to allow for assets, annual SR units") | Enforce the speed limit **per rule and instrument, at design time**: cost in SR units must be ≤ ⅓ of expected SR. That is one line in the registry. The ladder then remains a stress test. | +1 knob |
| QIEA / ParamLibrary | Handcrafting (above) | Fixed weights and fixed parameters. The plateau grid is the only search. | −11 genes × 9 regimes |
| Backtest book vs live runtime | NautilusTrader (LGPL-3.0, Python ≥3.12): *"The same strategy and execution-algorithm code can run across backtest and live systems"*; QuantConnect LEAN (Apache-2.0) uses the same pattern | Drive the **production** `ExecutionOrchestrator` in backtest through a *simulated* `ExecutionFace` (fills at bid/ask with C8 friction). Move `PositionModel`'s exits into `core/`. The harness book then shrinks to an accounting ledger. **Adopt the pattern, not the framework:** Nautilus would replace ACIS wholesale, needs Python 3.12 (ACIS is on 3.11) and is LGPL. | −1 duplicate exit policy; −1 duplicate drawdown (`portfolio_view`) |
| Research simulator (ARCHITECT's RSIM) | vectorbt | Vectorised bar-level screening is the right shape. The licence is **Apache-2.0 + Commons Clause** (the LICENSE forbids "the right to Sell"), with a heavy dependency tree (numba, pandas 3, plotly). **Reject as a dependency; take the lesson.** Numpy RSIM is small. | — |
| Walk-forward + DSR | skfolio `CombinatorialPurgedCV(n_folds, n_test_folds, purged_size, embargo_size)` (BSD-3, released 2026-09-23); `arch.bootstrap.SPA / StepM / MCS / RealityCheck` (NCSA) | If C1 recommends CPCV/PBO or SPA/StepM, **import these rather than hand-roll them**: both are permissive and maintained. mlfinlab is no longer on PyPI (commercial); reject it. | −N hand-rolled lines, +2 dependencies (dev/research only, never the fast loop) |

### 2.4 Per-component verdicts

**Value** is what gets sharper. **Cost** is complexity added (+) or removed (−). The line counts are measured; the replacement sizes are **LLM estimates**.

| Component | Verdict | Value | Cost |
|---|---|---|---|
| **NVMA 12-regime gate** | **SIMPLIFY → safety veto only.** Keep `tradeable`: spread, staleness, illiquid, macro, session. This agrees with ARCHITECT change 7; the systems addition is §2.2: regime-keying multiplies the search by 9 and divides each fitness sample by the regime share. | Removes one classification layer whose thresholds were tuned on a proxy (`nvma.py:36-41`, "HONESTY RENAME") | about −300 prod lines (classification + `stability.py` 44), −197 (`tests/backtest/regime_labels.py`), −159 test lines; 20 regime knobs → about 6 |
| **QIEA + ParamLibrary** | **RETIRE from the live path; REPLACE with handcrafted parameters + a plateau grid.** This agrees with ARCHITECT change 8. | N falls about 1000× (§2.2); the unseen-genes defect (GAP-0035) disappears with the search | −242 (`qiea.py`) −113 (`evolve_step.py`) −~200 of `param_library.py` staging/promotion (a static loader stays) −~460 test lines (`test_qiea` 154, `test_evolve_step` 126, `test_qiea_promotion_cycle` 92, part of `test_param_library`); `fitness.py` survives as the plateau evaluator; −11 optimizer knobs |
| **AGON's six modules** | **SIMPLIFY.** The module retirements are ARCHITECT's (§6 "What to retire"); not repeated here. Systems addition: replace the conviction/discard pipeline (`agon.py:267-358`) with capped forecasts (§2.3). | Continuous forecasts net instead of vetoing (BUILDER's DISCARD_OPPOSITE finding) | about −110 lines for MR/scalp/pair (`agon.py:140-157, 407-481`) + pair config; the pipeline 92 → ~40 (est.) |
| **Capital Governor** | **REPLACE the sizing kernel; KEEP the guards.** Risk budget ÷ stop distance with a two-sided volatility target. Delete `marginal_alpha` and `regime_f`. ARCHITECT change 12 owns the policy; this report supplies the 10× risk-dispersion evidence. | Dollar risk per trade becomes the declared quantity, which is what prop daily-loss rules measure | −73 (`marginal_alpha.py`) −92 test lines; kernel ±0 |
| **Risk Monitor** | **KEEP [owner decision].** Guardrails, the floor and HALT are owner-only. The one systems point: the graded path re-implements its daily drawdown (`portfolio_view.py`). Remove that once the harness drives the real monitor. | Parity | −~40 lines later |
| **Execution Orchestrator** | **SIMPLIFY + FIX THE CONTRACT.** Retire `fragmenter.py` (120 lines, size and time jitter; at $6k no order reaches `fragment_threshold_lots: 1.0`; ARCHITECT change 13 turns it off) and `VenueQuality` multi-venue ranking (~27 lines, one venue). Add to the §7.5 contract: (i) a **close/flatten** primitive, since the face has none today (`venue.py:145-180`) and the watchdog has a separate `flatten_all` plugin (`scripts/acis_watchdog.py:36-50`), so one adapter should serve both; (ii) **stop semantics** that allow a relative stop measured from the fill (cTrader), with conformance asserting "resting stop = fill ∓ declared distance, within one tick" instead of exact equality. | The real venue can pass the gate honestly | −~150 prod, +~20 contract lines **[spec]** |
| **MCP plane** | **KEEP.** It is the Phronesis contract; 748 lines are proportionate. | — | 0 |
| **Event/news intake** | **KEEP, but WIRE it.** It is not composed anywhere. For the demo, a static calendar file → the `blackout` callable is enough. | Prop news rules actually apply | +~30 wiring |
| **Backtest harness** | **SIMPLIFY by parity.** A simulated `ExecutionFace` under the production Orchestrator; move `PositionModel` exits to `core/`; import CPCV/SPA rather than hand-roll them. | Grades the code that will trade | −~200 net (est.) |
| **Governance machinery** | **KEEP the tooling; SIMPLIFY the prose.** Put a **word budget** on the read path, enforced by the gate like the module ratchet. Finish adoption-gate step 2 (relocate the spent root docs, e.g. `SPEC_AUDIT_INTERNAL_PENDING.md`/`SPEC_AUDIT_EXTERNAL_PENDING.md` from 2026-07-21 and `AUDIT_BRIEF_P12D22.md`, whose audit the status line calls triaged; local lead to confirm each is spent). | Sessions read less and trust more | +~20 lines of check; −~5k words of live prose |

### 2.5 Accelerating the demo (task 4)

| Candidate | Licence | Maturity | Linux | Server-side stop | Verdict |
|---|---|---|---|---|---|
| **OANDA v20 REST** via `httpx` (BSD-3), no SDK | n/a | The official `v20` SDK was last released 2018-09-28 and `oandapyV20` 2021-08-27 (both MIT): stale; the REST API itself is current | yes | `stopLossOnFill` with an absolute `price` (*"The associated Trade will be closed by a market price that is equal to or worse than this threshold"*); `clientExtensions` carries the id | **Best fit to the contract as written**, if TODO Track A step 1 (the practice-token check) passes. |
| **cTrader Open API**, own asyncio client + Spotware `.proto` (MIT) compiled with current protobuf | MIT | The protocol is current. The official SDK is stale and pins 10 CVEs (above). | yes | `relativeStopLoss` only on MARKET orders | **The prop-firm path** (SCOUT: FTMO/E8). It needs the §2.4 contract fix. Do **not** take the SDK dependency. |
| MT5 `MetaTrader5` package | MIT | active (2026-09-05) | **no**, win_amd64 wheels only | yes (in-terminal) | Reject for the Linux/Docker deploy. This confirms GAP-P12D-43's note. |
| NautilusTrader | LGPL-3.0 | active (1.231.0, 2026-08-02) | yes | venue-dependent | Reject as a dependency (Python ≥3.12; it would replace the engine). **Adopt its parity pattern.** |

**The smallest demo runtime that puts a first order through the existing Governor and Risk Monitor** (LLM-originated design; line counts are estimates):

1. `core/runtime/loop.py` (~150 lines): promote `tests/integration/paper_loop.py`'s `build_paper_loop` composition, which is already production code wired test-side (its own docstring says so). Add `RiskMonitor.evaluate` before `Orchestrator.submit`. This fills the empty systemd `ExecStart`.
2. **One real face** (~250–350 lines): the OANDA practice `ExecutionFace` + `FeedConnector` (pricing stream; reconnect with backoff, GAP-0020). Or the cTrader equivalent with the contract fix.
3. **Exits delegated to the broker:** SL **and TP** rest at the venue on fill. One max-hold timer calls the new close primitive. This avoids writing an engine exit policy before the demo, and every position is protected even if the process dies (§279).
4. **Order-rate stop-gap for GAP-0075:** at most one open position per instrument, using the existing `PositionGate` wiring. This is not the buffering fix; it only makes the demo safe from the firehose.
5. **Scope:** one instrument (EURUSD), one module (TREND), MODE=paper→practice under a human token, blackouts from a static calendar.

This is plumbing proof only. GAP-P12D-49 still says the engine loses on its positive control.

### 2.6 THE KILL LIST (task 5)

Each item is a `git mv` to `archive/` or the §5.7 graveyard, never a hard delete.

| # | Item | Lines saved (prod / tests) | Evidence it adds no OOS value or is superseded | Tag |
|---|---|---|---|---|
| K1 | QIEA live path: `qiea.py`, `evolve_step.py`, ParamLibrary staging/promotion | ~555 / ~460 | §2.2: 43,200 evaluations per fold against a 2-year window; its OOS record is GAP-P12D-49 (the engine loses on the planted control); GAP-0035 (unseen genes); GAP-P12D-34 (peak-picking) | **[spec — owner ratification]** (master §5) |
| K2 | NVMA classification as router and parameter key; `regime_labels.py` | ~300 + 197 / ~159 | Keyed by a proxy-tuned label (`nvma.py:36-41`); multiplies the search ×9; ARCHITECT change 7 | **[spec]** (master §4) |
| K3 | `marginal_alpha.py` (hot-hand upsizing ×1.5) | 73 / 92 | No OOS evidence that recent-trade P&L predicts; it adds sizing variance on noise; a 50-trade window (`system_config.yaml` `marginal_alpha_window: 50`) | **[spec]** (ACIS-05 §6.1) |
| K4 | `fragmenter.py` + `VenueQuality` routing | ~147 / its tests | Single venue; $6k orders never reach 1.0 lot; FTMO's request cap argues against fragmenting (ARCHITECT change 13) | **[spec]** (ACIS-06) |
| K5 | MR / MOMENTUM_SCALP / PAIR_DIVERGENCE module code | ~110 | ARCHITECT §6 (cited, not repeated): GAP-P12D-38, GAP-P12D-40, GAP-P12D-47 | **[spec]** |
| K6 | `throwaway_ui/` (1.5 MB, 17 files, 31% of tracked bytes) | — | TODO line 200 says it is an experiment and not a build item; §17 "no dashboards" | **[owner decision]** |
| K7 | Spent root docs (the two `SPEC_AUDIT_*_PENDING.md` files, `AUDIT_BRIEF_P12D22.md`) | ~4,700 words | The adoption gate's step 2, open since 2026-07-21; the status line reports their audits triaged | **[impl]** (hygiene; local lead verifies each) |
| K8 | `pydantic-settings` dependency | 1 dependency | Declared in `pyproject.toml`; 0 imports (`grep -rl "pydantic_settings"` returns nothing) | **[impl]** |

**Total, if all are ratified:** about **1,380 production lines out of 7,519 (−18%)** plus about 800 test lines. Also removed: about 25 config knobs, 1 dependency and 1.5 MB. Parts added: a sizing kernel of about equal size, a buffer, a close primitive, and the runtime.

---

## 3. What I could not verify

- **The effective N of QIEA's correlated trials.** The table brackets it; C1's simulation should pin it.
- **The share of bars each regime receives** (20% is assumed). Measuring it needs labelled real bars, which are out of bounds.
- **Whether `evolve_step`'s holdout-based selection across instruments leaks enough to matter.** That is C2's call.
- **cTrader framing and rate limits.** The connection page did not state the length-prefix framing or a requests-per-second limit (§6). The FTMO 2,000/day figure is SCOUT's, not re-verified here.
- **Carver's "3 weeks to 3 months" wording.** Not found verbatim (see summary item 8).
- **Whether the OANDA practice token works** (TODO Track A step 1). That is the owner's one HTTP call.
- **The replacement line counts in §2.4–2.6.** These are estimates.

## 4. Residual risk

- **Retiring QIEA and the regime router is an [owner] spec change.** Until it is ratified, any training run keeps the 43,200-per-fold search against a DSR that counts about 72 trials. Every positive result from it remains indistinguishable from selection noise.
- **The demo path can be mistaken for progress.** "It trades" proves plumbing only (GAP-P12D-49).
- **Broker-side TP brackets change exit behaviour relative to the graded book** (the book also exits on max-hold at tick prices). Demo P&L is therefore not comparable to the backtest until the parity work in §2.3 lands.
- **The contract fix for relative stops touches §279 conformance.** It is guardrail-adjacent and needs the dual audit.

## 5. Proposed ledger items (no IDs)

1. **The DSR trial count omits QIEA's search.** It counts ≤72 surviving champions per fold against 43,200 evaluations. **Severity** High · **Likelihood** Certain · **Status** open. **[impl]** Count the evaluations, or retire the search (see 2).
2. **Retire per-regime × per-instrument QIEA from the live path.** Handcrafted parameters, a ±10% plateau grid, pooled across instruments. **Severity** High · **Likelihood** Certain · **Status** proposed. **[spec — owner ratification]**
3. **§7.5 stop semantics are OANDA-shaped.** cTrader rejects an absolute SL on MARKET orders, and conformance asserts equality (`test_adapter_conformance.py:143`). **Severity** High (blocks the prop venue) · **Likelihood** Certain if cTrader · **Status** open. **[spec — owner ratification]**, into ACIS-13.
4. **The §7.5 contract has no close/flatten primitive,** and the watchdog uses a separate plugin surface. **Severity** Medium · **Likelihood** Certain · **Status** open. **[spec]**, into ACIS-13.
5. **Do not depend on `ctrader-open-api`.** It exact-pins 4 dependencies carrying 10 CVEs; compile the MIT protos instead. **Severity** Medium · **Likelihood** High · **Status** proposed. **[impl]**
6. **The graded path has no backtest/live parity.** The test-side `PositionModel` exits and the drawdown in `portfolio_view` have no production counterpart. **Severity** High · **Likelihood** Certain · **Status** open. **[impl]**, a simulated ExecutionFace under the production Orchestrator.
7. **Governor sizing ignores stop distance.** Dollar risk dispersion is up to 10× at equal notional (TSMOM's 10 ATR stop against 1–3.5 ATR for the others). **Severity** High · **Likelihood** Certain · **Status** open. **[spec — owner ratification]**, with ARCHITECT change 12.
8. **Retire `marginal_alpha`** (hot-hand upsizing). **Severity** Low · **Likelihood** Medium · **Status** proposed. **[spec]**
9. **Retire the fragmenter and VenueQuality routing.** **Severity** Low · **Likelihood** Certain · **Status** proposed. **[spec]**
10. **Event intake is not composed** into the paper or graded loops. **Severity** Medium · **Likelihood** Certain · **Status** open. **[impl]**, required before any prop demo.
11. **A read-path word budget enforced by the gate,** plus completion of adoption-gate step 2. **Severity** Medium · **Likelihood** Certain · **Status** proposed. **[impl]**
12. **`throwaway_ui/` disposition.** **Severity** Low · **Likelihood** Certain · **Status** open. **[owner decision]**
13. **The unused `pydantic-settings` dependency, and unpinned dependencies generally** (`pyproject.toml` has no version pins). **Severity** Low · **Likelihood** Certain · **Status** open. **[impl]**
14. **The field brief's S3 and S4 grades.** S3's speed limit is verified (b), and its "3 weeks–3 months" clause is downgraded to (c). S4 is verified (a). **Status** information.

## 6. Sources (all accessed 2026-09-24)

| Source | URL | Grade |
|---|---|---|
| Carver, "How fast should we trade?" (speed-limit quote; the 6–7 week example) | https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html | (b) |
| Carver, "Fast but not furious" (*"I don't want to allocate more than third of my expected pre-cost Sharpe Ratio towards trading costs."*) | https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html | (b) |
| pysystemtrade docs (forecast scale and cap, buffering, `ceiling_cost_SR`, handcrafting); GPL-3.0, lessons only | https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/docs/backtesting.md ; https://github.com/robcarver17/pysystemtrade | (b) |
| Darwinex risk engine (6.5% target, 3.25–6.5% band, 45 exposed days) | https://help.darwinex.com/risk-manager | (a) |
| Darwinex VaR (95%, 1-month horizon) | https://help.darwinex.com/var | (a) |
| cTrader Open API messages (ProtoOANewOrderReq `stopLoss` / `relativeStopLoss` / `clientOrderId` / volume) | https://help.ctrader.com/open-api/messages/ | (a) |
| cTrader Open API connection (SSL TCP or WebSocket) | https://help.ctrader.com/open-api/connection/ | (a) |
| Spotware OpenApiPy (MIT, Twisted deferreds) and openapi-proto-messages (MIT) | https://github.com/spotware/OpenApiPy ; https://github.com/spotware/openapi-proto-messages | (a) |
| OANDA v20 order definitions (`stopLossOnFill`, StopLossDetails.price) | https://developer.oanda.com/rest-live-v20/order-df/ | (a) |
| NautilusTrader overview (parity quote) | https://nautilustrader.io/docs/latest/concepts/overview/ | (b) |
| skfolio CombinatorialPurgedCV | https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html | (a) |
| arch multiple-comparison reference (SPA, StepM, MCS, RealityCheck) | https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparison-reference.html | (a) |
| vectorbt LICENSE (Commons Clause) | https://raw.githubusercontent.com/polakowo/vectorbt/master/LICENSE | (a) |
| PyPI JSON API (package metadata) and OSV.dev (advisories), via `evidence/C4/probe_sdk.py` | https://pypi.org/pypi/{pkg}/json ; https://api.osv.dev/v1/query | (a) |
| Bailey & López de Prado, expected max Sharpe / MinBTL (method, as implemented at `tests/backtest/deflated_sharpe.py:66-71`) | — (formula cross-checked against the repo's own implementation) | (a) |
| Local ARCHITECT final §6 (cited, not repeated) | `_context/local-wip/files/archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` | untrusted evidence (A9) |
