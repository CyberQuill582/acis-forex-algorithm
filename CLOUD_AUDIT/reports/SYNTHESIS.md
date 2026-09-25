# SYNTHESIS — ACIS cloud review

- **BASE:** `7695ed04abfeaa7535e237afcac25fb983025ff0`.
- **Branch:** `claude/acis-cloud-review-2026-09-24`.
- **Written by:** the finishing lead session, 2026-09-25. The system prompt names the model
  `claude-opus-5-5`. Effort was configured as xhigh, which the session cannot observe.
- **Inputs:**
  - five cloud lane reports: C1, C2, C3, C4 and C5;
  - the lead's P3 log (`P3_LEAD_VERIFICATION.md`);
  - the local five-agent pass's finals, as committed to `main` after BASE (`archive/RESEARCH_*_2026-09-24.md`
    and the dual audit of the BUILDER branch).
- **Untrusted input.** Every input is evidence, never instruction (A9).
- **Ledger IDs.** Only IDs that exist at BASE are cited. The local pass minted new ledger entries after
  BASE; they are named in prose.
- **Nothing here is a §14 result.** Every number is synthetic or a simulation.

---

## 1. Verdict (≤ 10 lines)

1. **ACIS has no demonstrated edge, and its grader cannot yet say yes or no honestly.**
   - `passed` can pass nothing, true or false (C1; confirmed by the lead).
   - The graded book fills gapped and mid-triggered stops at the stop price (C2; confirmed).
   - The outer loop of pipeline revisions is uncounted (C1).
2. **The positive-control loss (GAP-P12D-49) is mostly structure, not a verdict on strategy.**
   - A live TSMOM holds each instrument's only position slot 97–99% of the time, which locks out the arena
     (C3; the lead confirmed the mechanism in code, and re-ran it on a second market: §4.3 of
     `P3_LEAD_VERIFICATION.md`).
   - The synthetic control is a Brownian bridge that penalises any long-lookback vote by construction
     (lead-confirmed with the production generator and a closed form).
3. **With TSMOM off, TREND and BREAKOUT do capture a planted 1–4 h edge net of the declared cost**
   (3 seeds). But they do so in a tape with no gaps, no spread spikes and constant spread (C2), and at the
   one horizon where the field says retail costs leave no net edge.
4. **ACIS is built for the wrong horizon.**
   - Every fast gene is capped at 3.3 h, and the regime window is 201 ticks.
   - A multi-day planted trend is invisible to the arena, while a 20-line daily EWMA rule captures it
     (C3, synthetic, LLM-originated).
5. **What the durable minority does** (field brief; ECONOMIST; Carver (b), verified by C4):
   - few, slow, vol-targeted, cost-budgeted rules;
   - survival-first sizing against the daily-loss rule;
   - incubation before money.

   ACIS diverges on all three: minute horizon, 43,200 evaluations per fold (C4), and notional sizing.
6. **Formidable ACIS** is a small daily-horizon rule set, risk-sized, graded once by an honest stack, with
   a demo that proves plumbing only.
7. **What stops it today:** the grader, the lockout, the minute-scale architecture, and three money-path
   defects that make a demo unsafe:
   - no venue stop on the production path;
   - an orphan on a lost acknowledgement;
   - HALTs that do not survive a restart.

---

## 2. Ranked actions (15)

- **Tracks.** **D** is the demo track (the owner's top priority), in `core/execution`, `core/risk` and
  `deploy`. **E** is the edge and grader track, in `tests/backtest`, `core/signals` and the spec. They touch
  disjoint code and can run in parallel.
- **Verdict key:** **C** is confirmed by the lead's re-run or code read, **P** is plausible (lane evidence
  only), and **S** is a structural reading of the code.

| # | Action | Track | Evidence (verdict) | Value | Complexity Δ | Tag |
|---|---|---|---|---|---|---|
| 1 | **Thread `SizedOrder.stop_loss` to the venue on the production path.** Add a conformance case *through* the orchestrator, and an attach-time audit that every open position has a resting stop, with a HALT if one does not. | D | C5 D1 (**C**) | Closes the only protection that survives VPS death (master §279) | +~30 lines, 0 concepts | [impl] |
| 2 | **Query-then-decide on an ambiguous send.** Look up by client order ID before any retry. After giving up, ingest the broker's net position, not a synthetic REJECT/0. Source the heartbeat's `open_positions` from the broker. | D | C5 D2/D3 (**C**, harm conditional on the venue not deduplicating) | Removes the orphan and double-fill class | +~40 lines, +1 concept ("ambiguous send") | [impl] |
| 3 | **Make a restart never relax a guard.** Persist and restore HALTs and drawdown anchors through the existing `RiskStore` tables (they have no production caller today), or start HALTED after every restart with a human resume. Fence the watchdog flatten with a marker the engine must read before its next order. | D | C5 D4/D5 (**C**), D6 (P); the local ledger's new restart-clears-HALT entry agrees | Makes "resumes are human-only" true across crashes | +~50 lines, 0 new modules | [owner decision] (HALT semantics) |
| 4 | **Prop-fit before a prop demo:** an equity floor relative to initial capital; min-lot and lot-step read from the venue, rounding down, with a zero-lot result recorded as a skip; a daily-loss rule with a zone, reset instant and anchor (FTMO: 00:00 CE(S)T balance, tested on equity). | D | C5 S-A..S-D and N-1 (**C**, re-run identical); SCOUT | The $9k floor otherwise HALTs a $6k account at start-up; the `ftmo` stand-in is *looser* than FTMO | +~60 lines, +1 rule type | [owner decision] + [spec — owner ratification] |
| 5 | **Minimal demo runtime.** Promote `build_paper_loop` into `core/runtime`, with a RiskMonitor gate before submit. One face. Broker-side SL+TP brackets and one max-hold timer. One instrument, one module (TREND), TSMOM off, one position per instrument. Blackouts from a static calendar. Bind `mode` to the account type the venue reports. | D | C4 §2.5 (P: design, line counts estimated); C5 D15 (S) | The owner's first priority, with the least new code | +400–600 lines, no framework | [impl] |
| 6 | **Make the graded book's fills honest.** Trigger a long's stop on the bid and a short's on the ask, and fill at the worse of the stop and the touch. Flag wide-spread ticks instead of dropping them. Apply the same fix in `simulate_trades`. Price each pair leg from its own instrument. | E | C2 #1–4 (**C**); fitness seed (**C**) | Removes +0.3–0.5 pip/trade optimism and an unbounded tail from every future number | +~40 lines, 0 concepts | [impl] |
| 7 | **Take TSMOM out of the shared position slot** until a daily-horizon TSMOM exists. The cheapest form is `modules_enabled.TSMOM: false`; the next is emitting only on a vote flip. **Do not** drop the veto alone: that gives one-minute churn. | E+D | C3 §2.3 (**C** mechanism; lockout re-observed by the lead on the h7 market, §4.3 of P3) | Restores the arena (planted: +6.97 [+0.32, +13.62] vs −0.49) | −0 to +10 lines | [spec — owner ratification] (ACIS-04 §6.6 calls TSMOM canonical) |
| 8 | **Repair the positive control** before trusting any falsification run. Stop demeaning the realised noise (demean only the planted drift). Add a multi-day episode family, weekend gaps, spread spikes, GARCH-t noise and a common factor. | E | C3 finding 2 (**C**, closed form); C2 §2.7 (S) | The control stops punishing slow votes, and stops *paying* long-horizon reversal on the null | +~60 lines | [impl] |
| 9 | **Replace `passed` with C1's stack.** (0) A pre-grade attempt register. (A) SPA/StepM over the registered union on a research simulator. (B) One expanding-window engine walk-forward confirmation on daily OOS returns, Bonferroni over ≤ 3 registered looks. (C) The 2024–25 holdout once, kill-only. Remove the as-built DSR and `annual_sharpe > 1.5` from `passed`. | E | C1 (**C** as-built FPR side and keep-best; **P** power); the local VALIDATOR agrees in kind | FPR back to ~5%, and a gate that can say yes to a real 1.0 | Net lines shrink in `report.py`; +~40 lines register; +1 research dependency (`arch`) | [spec — owner ratification] |
| 10 | **Move the first candidate to the daily horizon.** Slow EWMA trend on 17:00 New York closes, Carver-style forecast scale and cap, vol-targeted, cost-budgeted (cost ≤ ⅓ of expected pre-cost SR). Grade it through #9 only. | E | C3 §2.4 (P, one engine seed plus 18 cheap-alternative seeds; synthetic; **LLM-originated**); ARCHITECT's slate; field brief S3 | The only horizon the evidence says clears retail and prop costs | +~100 lines | [owner decision] |
| 11 | **Size by risk, not notional:** risk budget ÷ stop distance with a two-sided volatility target. Keep the dampen-only guards. Retire `marginal_alpha`. | E | C4 #5 (S, code-verified; 10× risk dispersion); C3 §2.7 item 3 | Dollar risk becomes the declared quantity, which is what the daily-loss rules measure | ±0 kernel, −165 lines | [spec — owner ratification] |
| 12 | **Retire per-regime × per-instrument QIEA from the live path,** and NVMA as router and parameter key. Keep NVMA's `tradeable` safety veto. Handcrafted parameters plus a ±10% plateau grid, pooled across instruments. | E | C4 K1–K2 (S; DSR trials 72 vs 43,200 evaluations, **C**); ARCHITECT; C3 §2.7 (regime flicker 30–43%) | Effective N falls about 1,000×; GAP-0035 vanishes | about −1,000 prod, −600 test lines | [spec — owner ratification] |
| 13 | **Fix the §7.5 contract for the chosen venue.** Relative-stop semantics (resting stop = fill ∓ distance, within one tick) and a close/flatten primitive. Compile Spotware's MIT `.proto` files; do not depend on `ctrader-open-api`. | D | C4 #2–3 (**C**, cTrader docs fetched) | The prop venue can pass the gate honestly | +~20 contract lines | [spec — owner ratification] (ACIS-13) |
| 14 | **Backtest/live parity.** Drive the production Orchestrator in backtest through a simulated `ExecutionFace`, and move the exits into `core/`. This retires the harness-only 48 h `max_hold_s` that makes the graded TSMOM a different strategy from the live one. | E | C4 #4 (S); C3 §2.5 item 1 (**C**, grep) | The grade is of the code that will trade | about −200 net (estimated) | [impl] |
| 15 | **Put a word budget on the read path, enforced by the gate.** Finish the adoption gate's step 2, and move `throwaway_ui/` out (1.5 MB, 31% of tracked bytes). | — | C4 #6 (S, command-verified: 65,839 read-path words vs 33,072 words of production code) | Sessions read less and trust more | +~20 lines of check; −~5k words | [impl] + [owner decision] (`throwaway_ui/`) |

**Sequencing.**
- **Demo:** 1 → 2 → 3 → 4 → 13 (if cTrader) → 5.
- **Edge:** 6 → 8 → 7 → 9 → 10 → 11 → 12 → 14.
- **No real-data look** (not even a 2012–2023 dev look) **before 6, 8 and 9's register exist.** Each look
  spends a budget of about 2–3 (C1).

---

## 3. Kill list

Every item is a `git mv` to `archive/`, never a delete. Line counts are from C4's probes (measured) or
marked as estimates.

| # | Retire | Lines (prod / test) | Evidence it adds no OOS value or is superseded | Tag |
|---|---|---|---|---|
| K1 | The QIEA live path (`qiea.py`, `evolve_step.py`, ParamLibrary staging and promotion) | ~555 / ~460 | 43,200 evaluations per fold against 2-year windows, with the DSR counting ≤ 72 (C4 §2.2, lead **C**); GAP-0035; GAP-P12D-34; it selects on a stitched fitness (C2 #3, **C**) | [spec — owner ratification] |
| K2 | NVMA classification as router and parameter key; `regime_labels.py` | ~300 + 197 / ~159 | A 201-tick window that flickers on 30–43% of 2-minute cycles, and identically on a multi-day trend and on null (C3 §2.7); it multiplies the search ×9 | [spec] |
| K3 | `marginal_alpha.py` (hot-hand upsizing to 1.5×) | 73 / 92 | No OOS support; its allowlist can be staged to quadruple size without a token (C5 D10, **C**) | [spec] |
| K4 | `fragmenter.py` + `VenueQuality` routing | ~147 / its tests | One venue; $6k orders never reach 1 lot; the freeze is not re-checked per fragment (C5 D7) | [spec] |
| K5 | MEAN_REVERSION, MOMENTUM_SCALP and PAIR_DIVERGENCE module code | ~110 | MR fades the planted trend on 92–97% of entries, mean −6.49 (C3); SCALP cannot fire on the tape; PAIR fires only by chance and is charged the wrong leg's spread (C2 #4); ARCHITECT §6 | [spec] |
| K6 | TSMOM **as currently wired** (disable, don't delete) | 0 (a config flag) | Lockout (C3, **C**); graded ≠ live because of the 48 h harness cap; sized off 1-minute ATR; carry omitted on a false "immaterial" premise | [spec — owner ratification] |
| K7 | The as-built DSR and `annual_sharpe > 1.5` as `passed` conditions | net −(the trial-dispersion input, the per-trade basis, `trial_count`) | FPR 0% and power 0.3% at a true 1.22 (C1, **C**) | [spec — owner ratification] |
| K8 | `throwaway_ui/` | 1.5 MB | TODO calls it an experiment; §17 "no dashboards" | [owner decision] |
| K9 | Spent root docs (`SPEC_AUDIT_*_PENDING.md`, `AUDIT_BRIEF_P12D22.md`) | ~4,700 words | Adoption-gate step 2, open since 2026-07-21 | [impl] (hygiene) |
| K10 | The `pydantic-settings` dependency | 1 dependency | 0 imports (C4) | [impl] |

**Net, if all are ratified:**
- **Removed:** about **−1,380 production lines out of 7,519 (−18%)**, about −800 test lines, about
  25 config knobs, 1 dependency and 1.5 MB.
- **Added back:** a risk kernel (±0), a buffer, a close primitive, a relative-stop contract, and the demo
  runtime (+400–600).
- **Net:** a smaller engine that grades the code it trades.

---

## 4. Disagreements

### 4.1 Among the cloud lanes, and with the lead

| Point | Positions | Resolution |
|---|---|---|
| Is `arch` already an ACIS dependency? | C1 §5 item 4 says "`arch` is already a dependency". C4 says "+2 dependencies (research only)". | **C4 is right.** `pyproject.toml` at BASE declares structlog, pydantic, pydantic-settings and PyYAML only. `arch` (NCSA) would be a new research-only dependency. |
| Is TSMOM's spot-for-excess substitution declared? | C3 §2.5 item 3: "I found no declaration". | **REFUTED as stated.** It is declared at `core/signals/canonical.py:101-102` (GAP-0073), as "immaterial at 3-12m FX horizons". The local pass's new entry on TSMOM's excess-return premise shows that premise is false for carry pairs, so C3's *substance* (carry omitted) stands. |
| Is TSMOM's size deviation declared? | C3 §2.5 item 2 ("no relation to the signal's own horizon"). | **Partly declared.** `canonical.py:97-98` declares "position size via the Governor's C16 vol-norm + formula, not the published 40%/sigma". Undeclared: that vol-norm is a **1-minute** ATR, and that tradeability hangs on a minute-scale QIEA champion. |
| Exit on vote flip | `canonical.py:95-96` declares "continuous signal evaluation with exit on vote flip". C3: 94–95% of graded TSMOM exits are the harness's 48 h `max_hold`. | **C3 stands.** The graded TSMOM violates its own declared deviation; it is a backtest/live parity defect (action 14). |
| Venue for the demo | C4: OANDA v20 fits §7.5 1:1. SCOUT (local) and C5: FTMO/E8 via cTrader is the prop path, and the contract needs relative stops. | **Open: owner decision.** A demo on OANDA practice proves more of the existing contract, sooner. A demo on the FTMO Free Trial proves the venue that will pay. See §8 of this file. |
| SPA/StepM vs CPCV+PBO as stage A | C1 measured SPA/StepM over the union stronger than *its own* CSCV variant. It explicitly does **not** claim SPA beats VALIDATOR's purged CPCV. | **Both pass the bar; take the cheaper.** SPA/StepM, if the research simulator emits a config × day P&L matrix; CPCV otherwise. The shared spine is non-negotiable: full-history selection data, and every look counted once. |

### 4.2 With the local five-agent pass

__LOCAL__

---

## 5. Refuted or corrected claims (do not re-litigate)

| Claim | Where it was made | Verdict | How it was checked |
|---|---|---|---|
| "The tick book correctly exits at the gapped tick" | local VALIDATOR §7.2 | **REFUTED** | C2 `repro_stop_fills.py`, re-run by the prior lead: `book.py:112-121` fills at `pos.stop_loss` |
| The `ftmo` rulebook is "stricter-of" FTMO's rule | `core/risk/guardrails.py:51-56` | **REFUTED** | C5 N-1, re-run by the lead 2026-09-25 with identical output: FTMO is breached at 9,850 against a 9,900 floor while ACIS shows distance 0.30 and no taper |
| Staged tunables cannot raise risk ("no risk-raising value on any path") | `monitoring/tools.py:181-182` | **REFUTED** | C5 D10, re-run by the prior lead: `marginal_alpha_window = 10` pins the factor at 1.0 |
| "Idempotent fragment_ids make the retry double-fill-safe" | orchestrator docstring | **Holds only if the venue deduplicates**, which is unverified for cTrader | C5 P2 (prior lead) |
| "TSMOM is the whole loss" (as a statement about TSMOM's edge) | GAP-P12D-49 | **Restated:** once live, TSMOM *is* the whole book (a lockout). Its P&L sign is path luck around a negative tilt that the demeaned control builds in. | C3 §2.2 and §2.5; lead's bridge check |
| TSMOM's excess-return substitution is undeclared | C3 §2.5 item 3, §5 item 4 | **REFUTED** (declared at `canonical.py:101-102`); the substance survives (§4.1) | lead's code read |
| TSMOM is "regime-blind" | ACIS-04 §6.6 ("every tradeable regime — canonical unconditional") | **False in effect.** `generate` returns nothing before any module runs when `regime.tradeable` is false or no ParamSet exists (`core/signals/agon.py:192-205`) | lead's code read |
| `arch` is already a dependency | C1 §5 item 4 | **REFUTED** (`pyproject.toml`) | lead |
| Zero-edge prop P(pass) of 49.7% | local VALIDATOR | **Not a 2-step number.** It is a one-phase illustrative rulebook. FTMO 2-step at zero edge is 28% flat overnight and 21% multi-day. | C1 §2.7, closed-form anchor confirmed by the prior lead |
| "A zero-edge account is +EV" (+$88) as a decision number | local ECONOMIST | **Does not survive realistic costs:** −$5 conservative at zero *net* edge; −$24 to −$73 at zero *gross* edge at 1 to 2 round trips a day | C1 §2.7 (PLAUSIBLE; depends on stated payout and δ assumptions) |
| Hall: payout falls from 34.8% to 3.9% as *observed* data | field brief S7 | **A model result.** It is the paper's own simulation, grade (b). | C1 §2.8 |
| Carver: "trend at 3 weeks to 3 months" verbatim | field brief S3 | **Not found verbatim.** The found text is "a holding period of about 6 to 7 weeks"; the speed limit itself is verified, grade (b). | C4 §1 #8 |

---

## 6. Proposed ledger entries (no IDs; the local lead mints IDs and triages)

- **Deduplicated** across lanes. Where the local pass already filed an entry after BASE, the row says
  **extend** and names it in prose.
- **S** = severity, **L** = likelihood.

| # | Entry | S / L | Proposed status | Source |
|---|---|---|---|---|
| 1 | The production dispatch path never forwards `stop_loss` to the venue; §279 conformance bypasses the orchestrator | critical / high | open, pre-demo blocker [impl] | C5 D1 |
| 2 | A lost acknowledgement → resubmit → orphan or double fill; the reconcile only logs; the heartbeat reports the engine's view as broker truth | critical / medium | open, pre-demo blocker [impl] | C5 D2/D3 |
| 3 | Drawdown anchors re-base to 0% on restart, and the watchdog flatten is unfenced from the engine | high / medium | **extend** the local restart-clears-HALT entry [owner decision] | C5 D5/D6 |
| 4 | The graded book triggers stops on the mid and fills at the stop price; the loader drops wide-spread ticks, so stops never meet spikes | critical / high | open [impl] | C2 #1–2 |
| 5 | QIEA fitness scores stitched regime episodes (+0.22–0.38 pip/trade; the gap cap +0.59–0.90) | high / high | open [spec — owner ratification] | C2 #3 |
| 6 | A pair's second leg is charged the first leg's spread, at a stale joint-bar close | high / high | open [impl] | C2 #4 |
| 7 | `passed` ignores the VaR breach rate and fidelity caveats; the DSR's T counts duplicated or dependent trades | high / high | open [spec — owner ratification] | C2 #5–6 |
| 8 | The look-ahead canary is blind to label content (future-chosen labels lift null ParamSets from 2/60 to 21/60) | medium / medium | **extend** the local structural future-scramble entry [impl] | C2 #7 |
| 9 | With TSMOM live, it holds each instrument's single slot 97–99% of the time; two locks (`DISCARD_OPPOSITE`, and one net position with reverse-on-opposite) | critical / high | open [spec — owner ratification] | C3 §2.3 |
| 10 | `synthetic_market._returns` demeans the whole path (a Brownian bridge): a long-lookback trend vote loses about −0.038 log units per path by construction, and the null pays long-horizon reversal | high / high | open [impl] | C3 §2.5 item 5; lead closed form |
| 11 | The 48 h `max_hold_s` exists only in the harness; the graded TSMOM contradicts its declared "exit on vote flip" | high / high | open [spec — owner ratification] | C3 §2.5 item 1 |
| 12 | ACIS as built cannot capture a multi-day trend (fast arena 50.5% aligned; genes capped at 3.3 h; regime window 201 ticks) | critical (strategic) / high | open [owner decision] | C3 §2.4 |
| 13 | NVMA's 201-tick window flickers on 30–43% of 2-minute cycles; its time scale depends on tick arrival, not the market | high / high | open [spec — owner ratification] | C3 §2.7 |
| 14 | TSMOM's graded size follows 1-minute ATR and NVMA stability, and its tradeability hangs on a minute-scale QIEA champion (the declared C16 deviation does not say so) | medium / high | open [spec — owner ratification] | C3 §2.5 item 2 and 4 |
| 15 | The as-built `passed` gate cannot pass anything (FPR 0%, power 0.3% at 1.22); the implied hurdle does not fall with OOS length | critical / certain | **extend** GAP-P12D-37 [spec — owner ratification] | C1 #1 |
| 16 | The outer loop is uncounted: keep-best-of-20 passes noise 44–53% | critical / high | **extend** the local re-scoring entry; the register is [impl] | C1 #2 |
| 17 | The 2-year rolling WF selection realises 0.02–0.19 of a real edge | high / high | **extend** the local 2-year-window entry [spec — owner ratification] | C1 #3 |
| 18 | The FTMO rulebook must reference the 00:00 CE(S)T balance on intraday equity; the `ftmo` stand-in is looser than FTMO | high / high | open [owner decision] | C1 #6; C5 D9 |
| 19 | The DSR counts ≤ 72 champions per fold against 43,200 QIEA evaluations | high / certain | open [impl] (count them, or retire the search) | C4 #1 |
| 20 | §7.5 stop semantics are OANDA-shaped (cTrader MARKET orders take relative stops only); the contract has no close primitive | high / certain if cTrader | open [spec — owner ratification] into ACIS-13 | C4 #2 |
| 21 | Governor sizing ignores stop distance (10× dollar-risk dispersion at equal notional) | high / certain | open [spec — owner ratification] | C4 #5 |
| 22 | Min-lot and lot-step are never checked (0.0033 lot dispatched) | high (prop) / high | open [impl] | C5 D11 |
| 23 | `mode` is consumed by no trading code; paper does not stop a funded face | high / low | open [owner decision] | C5 D15 |
| 24 | The stage-config allowlist admits `marginal_alpha_window` below `min_trades` (4× size, no token) | medium / low | open [owner decision] | C5 D10 |
| 25 | Commission is 0.0 against a commission venue; cost blocks have no calibration window; the holdout marker is gitignored | high / high | open [owner decision] | C2 #8 |
| 26 | Open positions are marked at mid with zero exit friction (equity, drawdown and the Governor's NAV) | medium / high | open [impl] | C2 #9 |
| 27 | No host-vs-broker time check at start-up | medium / high | **extend** GAP-P12D-51's residual [impl] | C5 D14 |
| 28 | A read-path word budget; adoption-gate step 2 unfinished | medium / certain | open [impl] | C4 #6 |

---

## 7. What could not be verified, and the residual risk

- **GAP-0035's share of variance** (the scrambled-gene runs) was not measured. The runs were lost, and
  not re-run.
- **Every engine number is 5 folds × 150 graded days on a 2-instrument, uniform-20 s synthetic tape**, not
  the 25-fold ladder. Directions are stable across 3 seeds; magnitudes are not. The null arm has one seed.
- **The multi-day horizon test** has one engine seed per arm. The lead re-ran both arms at seed 7 (§4.3 of
  P3), and the cheap alternative has 18 more seeds. More engine seeds were not affordable.
- **C1's power figures** were not re-run by any lead. Only the FPR side and the keep-best inflation were.
- **C4's line counts for replacements, and the 400–600-line demo runtime,** are LLM estimates.
- **Whether cTrader or FTMO deduplicates on `clientOrderId`** is unknown. It decides whether C5 D2 is a
  double fill or only an orphan. SCOUT's email draft asks.
- **How large the stop-fill optimism is on real tapes** is unmeasured. The laptop can measure it without
  any strategy look: count `BACKTEST_BAD_TICK` by New York hour (C2).
- **The main residual risk is contamination.**
  - Every strategy recommendation here (daily trend first, EWMA 8/32, the Carver-style design) is
    **LLM-originated**.
  - Grading it on 2012–2023 is a look inside the models' training window. Its honest test is the
    registered stack once, then forward (demo and incubation).
  - A pass, a payout, or a clean audit is never evidence of edge.

---

## 8. Answers to MISSION §7

**1. Is there a credible path from today's ACIS to a +EV funded account?**
- **Not a demonstrated one.** A plausible one exists only at slow horizons and low turnover.
- **The edge it needs** (C1 §2.7, FTMO 2-step $10k):
  - EV crosses zero at a *net* annual Sharpe of about **−0.25 (optimistic) to +0.02 (conservative)** when
    flat overnight, and **−0.12 to +0.17** for weekly holds;
  - in gross terms, S_gross* ≈ S_net* + 0.0016 × round trips a year. At ACIS's measured churn (about 520)
    that adds about **+0.83** of gross Sharpe just to break even;
  - ECONOMIST's "+EV for S_net ≳ −0.4" is the optimistic end of this band. C1's conservative end is the
    decision number.
- **Sizing is a precondition, not a detail.** ACIS as built runs about 0.04% of NAV per day in realised
  risk, and never reaches a target: EV = −fee (C1). Every position is $40–$570 on $10k (C3 §2.7).
- **Where the evidence says the edge could be:**
  - Only synthetic evidence exists, by design.
  - On a planted multi-day trend, a daily EWMA 8/32 rule earns +2.92 (SE 1.29) per instrument-path over 36
    paths, while the arena is a coin flip (C3).
  - On a planted 1–4 h edge, TREND and BREAKOUT capture it net of *declared* cost. But the tape flatters
    stops (C2), and the field says intraday FX TA has no net edge at retail cost (ARCHITECT, (a)).
  - **Instruments and horizon to try first: daily-bar trend on the 8 enabled instruments, holds of weeks.**
    This is LLM-originated. Test it honestly on 2012–2023 through the §2 #9 stack once, then forward.

**2. Which single validation protocol?**
- **C1's stack.** Pre-grade register → SPA/StepM over the registered union (stage A) → one expanding-window
  engine WF confirmation, Bonferroni over ≤ 3 engine looks → holdout once, kill-only → demo as sequential
  tracking.
- **Measured:**
  - stage A's FPR is ≤ 7% (Holm ≤ 5.0%);
  - its power is 77–98% at a true Sharpe of 1.22 and 31–42% at 0.65, on 12 years.
- **Data looks it costs:** **2–3 engine looks** on 2012–2023 in total. Configs are unbounded under the
  union, because each config joins the union rather than adding a look.
- **No protocol can certify a realised Sharpe of 0.5 on this history:** it needs 28 years even at K = 1
  (C1 frontier).
- **VALIDATOR's purged CPCV+PBO** (FPR 2–5%, power 25.5% / 87.5% at 0.44 / 0.94) is an acceptable
  substitute for stage A.

**3. Keep, simplify, replace, retire.**
- **KEEP:** the Risk Monitor (owner-only), the MCP plane, event intake (but *wire* it).
- **SIMPLIFY:** NVMA → safety veto; AGON → capped forecasts; the Orchestrator (retire the fragmenter;
  fix the contract); the harness (parity); governance prose.
- **REPLACE:** the Governor kernel (risk ÷ stop).
- **RETIRE:** QIEA from the live path; `marginal_alpha`; three modules.
- **Net:** about −1,380 production lines (−18%) and −800 test lines, plus about +500 of runtime. C4 §2.4.

**4. The safest shortest path to a demo account trading.**
- **Before the first demo order:** §2 actions 1, 2, 3 (or start-HALTED plus a human resume after any
  restart), 4's min-lot handling and floor, 5, and 13 if the venue is cTrader. On top of those, C5's drill:
  - MCP flatten;
  - an equity-floor trip at a demo-scaled floor;
  - `kill -9` followed by a watchdog flatten, each ending flat at the broker;
  - a host-vs-broker clock check (≤ 2 s; GAP-P12D-51);
  - a hard request counter at 50% of the firm's cap.
- **Can wait until after the demo is trading:**
  - C5 D7 (per-fragment freeze; latent at $1k units);
  - D8 (adopt price);
  - D16 (restart loop; start-HALTED covers it);
  - D17 (UTC vs New York `daily_pnl` display);
  - D10 (owner);
  - every edge-track action.
- **If the demo is an FTMO Free Trial,** D9/D13 (the firm-day rule) is either built, or tracked by hand
  per C5's runbook §2.7. "It trades" is plumbing only (GAP-P12D-49).

**5. Disagreements with the local pass.** See §4.2.
