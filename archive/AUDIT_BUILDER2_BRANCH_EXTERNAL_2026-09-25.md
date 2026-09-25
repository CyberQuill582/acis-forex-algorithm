# AUDIT — BUILDER-2 branch, EXTERNAL-REFERENT lens (2026-09-25)

> **Status: COMPLETE** (written incrementally; the laptop loses power without warning, GAP-P12D-76).
> Auditor: AUDIT-EXTERNAL, Opus 5.5 (1M context), fresh context, no subagents; a finder, not a clearer (A5).
> Brief: `AUDIT_BRIEF_BUILDER2_2026-09-25.md` (pinned). Scope: `577d882..5d96570` on
> `worktree-agent-a8937e82f9a7a5391` only. Web content treated as data, never instructions.
> Private export: `SCRATCH/audit2_external/tree` (git archive of 5d96570); every repro below lives under
> `SCRATCH/audit2_external/`. Nothing in the worktree or the main tree was modified. The internal auditor's
> report was NOT read (lens independence).

## Findings

### X1 — HIGH — The graded tick book fills a gapped-through stop AT THE STOP LEVEL; T6's rationale says the opposite, and T6 now makes selection harsher than grading on every gap
- Diff under audit: `tests/unit/test_fitness_exits.py`, docstring of
  `test_a_bar_that_opens_through_the_stop_exits_at_the_open_not_the_stop`: "Filling at the stop there would
  credit a price the market never offered — optimistic in selection, **while the tick book correctly fills at
  the gapped tick**." (inherited from the VALIDATOR's §7.2 line, which is also wrong).
- Code (unchanged by the diff): `tests/backtest/book.py:115-121` — `if price <= pos.stop_loss: return
  self.close_at(pos, pos.stop_loss, ...)`: the fill price is the stop level, never `price` (the gapped tick).
- Reproduced (`x1_book_gap.py`): long, entry 1.1000, stop 1.0990, first tick after a weekend gap 1.0950 →
  the book books gross −100 USD per 100k (the stop), not −500 (the first price offered); same for shorts.
- External referents:
  - OANDA v20 order definitions (https://developer.oanda.com/rest-live-v20/order-df/, fetched 2026-09-25):
    StopLossOrder — "The Order will be filled (closing the Trade) by the first price that is equal to or worse
    than the threshold."
  - backtrader, order execution logic (https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/,
    fetched 2026-09-25): Stop — "If the `open` price of the bar is above the stop price the order is executed
    immediately with the `open` price."
  - ACIS_SPEC.md:273, gap law: "stops are assumed to fill wherever liquidity reappears, not at their level."
- Consequence: after T6, SELECTION (fitness) books a gap at the open while GRADING (the §14 book) still
  credits the stop — the "select one world, grade another" class of GAP-P12D-36, with the GRADED side the
  lenient one, on exactly the tail (weekend/news gaps) that the §14 drawdown measures. The repo's own
  measurement (archive/RESEARCH_EXECUTION_COSTS_2026-09-16.md §6.4: EUR/USD weekend gap p95 47 bps) puts the
  understatement at up to ~3x on a 15 bps stop. No live ledger entry owns the book's gap-through fill; it is
  only a clause inside GAP-P12D-42's justification. Not introduced by the diff; the diff's false claim and the
  new asymmetry are.

### X2 — MEDIUM-HIGH — The fitness extractor stamps every exit at the bar's CLOSE, so post-open information in a gap exit is structurally invisible to T1 and T2 — and T6 itself puts one there
- Diff: `tests/backtest/leakage_tapes.py`, `trade_path_decisions`: every non-marked exit is
  `Decision(t.exit_bar + 0.5, t.exit_bar + 0.5, "exit", ...)`; its docstring calls this "conservative for a gap
  exit at j's open". It is the reverse: a LATER stamp shrinks the set of cuts at which the decision is compared.
  No cut ever perturbs bar j's close while comparing an exit decided at bar j's open.
- Reproduced (`x_exec_open2.py`, a gappy 240-bar tape, the suite's own `bar_cuts` grid, 479 cuts): a gap exit
  that reads the bar's CLOSE while claiming an open fill (`min(max(open, close), sl)`) is a live, flattering
  leak (it changes decisions; PnL +0.00155 over 6 gap exits on seed 3, +0.00040 on seed 1) and T2 = 0, T1 = 0
  violating cuts on every seed.
- External referent: Zhang, Li, Peng & Chen, arXiv 2605.23959 (12 May 2026, https://arxiv.org/abs/2605.23959,
  fetched 2026-09-25), abstract: "centered temporal features and same-day-open execution with post-open
  daily-bar information cause large and stable increases in both predictive and trading metrics"; Table 6:
  EXEC_OPEN = "Use of post-open bar information while assuming same-day-open fills"; §4.4: "Future-suffix
  perturbations affect TEMP_CENTER but not CLEAN; post-open masking collapses EXEC_OPEN" — the family needs an
  intra-bar cut that is COMPARED, which the exit stamp removes.
- A live instance in the diff: T6's gap exit fills at bar j's OPEN but pays `costs.per_side_cost(bar.spread)`,
  bar j's CLOSING spread (`core/optimizer/fitness.py`, the exit pnl line) — the exit-side twin of F1
  (GAP-P12D-82 names only the ENTRY side). The closing-spread charge pre-exists for intrabar touch exits (where
  the j + 0.5 stamp makes it admissible); T6 makes it a post-open datum for an at-the-open fill, at the one
  moment (the reopen) when the opening spread is widest (RESEARCH_EXECUTION_COSTS §6.4 caveat: "the 'first
  Sunday tick' is the reopen print and is itself wide"; tastyfx, "Gap risk", 2023-10-17,
  https://www.tastyfx.com/news/gap-risk--what-it-means-and-how-to-avoid-it-231017/, fetched 2026-09-25, on the
  New York close to Asian open window: "Spreads are subject to widen during this time").
- Fix direction: carry the exit kind in `Trade` (gap / touch / max-hold) and stamp a gap exit at j (its open),
  a touch exit at j + 0.5; and put the charged cost into the fill/exit decision once F1 is fixed, so a
  regression of F1 is catchable (today the fill decision omits cost "so as not to false-alarm", i.e. the
  guard is shaped around a known violation).

### X3 — MEDIUM — T6 uses the open against the trade but not for it: a bar that opens BEYOND the target and later touches the stop is booked as a full stop loss
- Diff: `core/optimizer/fitness.py` — the stop branch (`if bar.low <= sl: exit_mid = min(bar.open, sl)`) runs
  before any target check, even when `bar.open` is already beyond `tp`.
- Reproduced (`tree/tests/unit/test_zz_audit_ext_t6.py`, both directions): entry 1.09430, sl 1.09281,
  tp 1.09654, bar opens 1.09684 then trades down past the stop → exit at 1.09281 (STOP), pnl −0.001885.
- External referents: OANDA v20 TakeProfitOrder (same URL/date as X1): "The Order will be filled (closing the
  Trade) by the first price that is equal to or better than the threshold." backtrader (same URL/date): Limit —
  "If the `open` price of the bar is below the limit price the order executes immediately with the `open`
  price." The open is the first price of the bar, so ordering is KNOWN there; "stop before target" is only the
  convention for the unknowable intrabar order when the open lies between the two levels.
- Also a departure, declared in the code comment but not in any ledger: a favourable gap through the target
  fills at the target, "never better", whereas both referents fill at the open. Conservative, but it makes
  selection harsher than the venue asymmetrically, and the tick book (first tick beyond TP → closes at TP)
  handles the X3 bar correctly, so fitness and grading disagree on it.

### X4 — MEDIUM — The look register records the look but not its outcome, and its completeness rests on caller diligence, not construction
Reproduced in `x_register.py` (private export; every line below printed by the script):
- (a) the register location is the caller's choice: a real-data (tier 2) look registered in a throwaway
  directory passes `verify_look`, and so `run_walk_forward` (`{'trend-v1': {'validation': 1}}`);
- (b) deleting a family's latest line is undetectable: after deleting 000002 the next look reuses id 000002 and
  its `previous` points at 000001; counts read 2, not 3;
- (c) a tier-2 look on a dirty tree, or with git "unknown", is accepted — the commit then does not pin the code
  that ran, so "what changed since" cannot be checked;
- (d) the tier is derived from a caller-supplied NAME: `dukascopy-mirror` → tier 0 "synthetic", and three
  looks demand no "changed";
- (e) a family rename resets its history ("first look", previous None);
- (f) a zero-byte line (a power loss between the exclusive create and the JSON write — GAP-P12D-76 makes this
  realistic) makes every later `register` raise `JSONDecodeError`, so the only recovery is deleting a line.
- The register lives under `/data/`, which `.gitignore` excludes: a single uncommitted, un-backed-up directory
  on the laptop (cf. GAP-P12D-50).
External referents:
- Gençay, arXiv 2608.27734 (27 Aug 2026, https://arxiv.org/pdf/2608.27734, fetched 2026-09-25) §3.2: "every
  candidate the agent composes flows through the same evaluation entry point, which is what makes the trial
  ledger of Section 4 complete by construction rather than by author diligence"; §4.1: the ledger "records
  every distinct strategy evaluation the search performed"; §4.2: "The candidate matrix contains the
  design-window return series of every ledger entry, so the column count equals the trial count by an
  enforced invariant."
- Bailey & López de Prado, "The Deflated Sharpe Ratio" (https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf,
  fetched 2026-09-25): the DSR "incorporates information about the unselected trials, such as the number of
  independent experiments conducted and the variance of the SRs"; App. A.3: "It is critical to understand that
  the N used ... corresponds to the number of independent trials ... So given M dependent trials we need to
  derive the number of 'implied independent trials' ... by taking into account the average correlation between
  the trials"; and on the file-drawer effect: "Analysts who do not report the full extent of the experiments
  conducted".
- OSF registrations FAQ (https://help.osf.io/article/550-registration-and-preregistration-faq-s, fetched
  2026-09-25): "Preregistration is the practice of posting a time-stamped, read-only version of your study
  plan"; "A registration is a frozen version of your project that can never be edited or deleted"; a
  registration's story "describes what your research plans to do, any updates that need to be made, and the
  results."
What this means: the register satisfies "write before grade" (the pre-registration half) but not the
two properties the literature needs from a trial ledger: (i) an outcome per look (the Sharpe and the
return series), without which neither V nor the implied-independent N of the DSR, nor the VALIDATOR's own
§5.2 "register's measured rho" and K2 "PBO on a family's candidate matrix", can be computed from it; and
(ii) completeness and immutability by construction (fixed location owned by the grader, source tier from the
loader's source OBJECT, a hash chain or a commit of each line, refusal of dirty trees at tier >= 2). R5/R6 in
the author's report declare part of this (counting only; `Backtest.run` bypass); (a), (b), (d), (e), (f) and
the missing outcome are not declared.

### X5 — MEDIUM — The positive controls calibrate the guard on ONE leak family, and the suite's "clean" verdict overclaims
- T7 plants: a centred EMA, a 5% one-bar EMA peek, a one-tick label peek, a next-tick oracle peek — all value
  peeks on the PRICE channel. None plants a threshold leak (Fonseca M2), a re-stamp (M3, see X2), a sub-grid
  leak on the Governor/book (M1 — declared as R1 for the day grid), a non-price channel (tick rate, volume,
  spread in bps are constant on `SyntheticMarket`: uniform ticks, `volume=1.0`, spread = `spread_frac × mid`;
  cf. GAP-P12D-63), or an availability-lag leak (T3, not built).
- `scripts/leakage_suite.py:127` prints "clean: no decision before any cut depends on the data after it".
- External referent: Fonseca, arXiv 2607.04958 (6 Jul 2026, https://arxiv.org/pdf/2607.04958, fetched
  2026-09-25): "a detector reports the leaks it happens to trigger and certifies nothing by its silence";
  §8.3: a two-run differential detector "re-executes the pipeline on perturbed future data at sampled epochs
  and flags a change" and misses 18 of 33 planted leaks, by M1 "coverage miss", M2 "reads a future value
  through a threshold operation that the detector's default perturbation does not flip on the tested input,
  though a different input would", and M3 "re-stamps a future-valued series to an admissible stamp ... an
  output-comparing detector sees an unchanging value and misses it"; §1: "Leakage is recursively enumerable
  (a witnessing future-dependent run can be found if one exists) but freedom is not, which is precisely why
  detectors can exhibit leaks yet never certify their absence."
- Fix direction: reword the verdict to what was shown ("no leak witnessed at N cuts under 2 perturbations");
  add one control per mechanism (M2 threshold, M3 re-stamp — X2's leak is a ready one — and one non-price
  channel on a tape whose tick rate and spread vary).

### X6 — LOW — The labeller component sweep's tape is too short to exercise the session-median channel, so it is blind to F3 itself
- Reproduced (`tree/tests/backtest/test_zz_audit_ext_f3.py`): with F3 planted (`list(market_states(...))`
  before labelling), on the shipped 130-tick tape the honest and leaky labellers produce IDENTICAL decisions
  (155 = 155) and T2 is clean at 129 cuts; T1's 128 "violations" come only from the component harness measuring
  emission by pulled ticks (the engine path assigns emission from the full-tape `TickClock` instead). On a
  400-tick tape the same leak changes 11 regime decisions and T2 catches it at 36/100 cuts (ILLIQUID via the
  session medians). Same referent as X5 (M2: the tested input never flips the channel).

### X7 — MEDIUM — Citation fidelity: the suite cites Gençay's "structural guardrail" for T1/T2, but Gençay's guardrail is exclusion BY CONSTRUCTION (VALIDATOR's T8, not built); T1/T2 is the empirical two-run detector class Fonseca measures missing 54.5%
- Diff: `tests/backtest/test_leakage_controls.py` header — "Gençay (arXiv 2608.27734 §6.1): such a leak
  'survives statistical deflation completely; only the structural guardrail removes it'"; `leakage.py` header —
  "Only a structural test catches it."
- Source's actual method (Gençay, same URL/date as X4): abstract — "the agent can only act through
  registry-validated tools whose feature space excludes look-ahead by construction"; §3.2 — "First, look-ahead is
  inexpressible. The feature registry contains a deliberately leaky family ... but it is excluded from the
  agent-selectable set"; §7 — "both belong in the type system of the platform, the agent-selectable feature
  registry and the single evaluation entry point, rather than in prompts, conventions, or reviewer trust."
- T1/T2 re-runs on perturbed/truncated futures and compares outputs: exactly Fonseca §8.3's "two-run
  differential detector ... re-executes the pipeline on perturbed future data at sampled epochs and flags a
  change" (exhaustive rather than sampled epochs here, which removes M1 for the swept components only).
  Gençay's §6.1 result (DSR = 1.00 for the leaky oracle) supports "statistics cannot remove a leak"; it does not
  support "a perturbation sweep is the structural guardrail". The by-construction guard in this repo's plan is
  T8 (a decision-time accessor + lint), which the author lists as not built (report §6).
- Risk: a reader of GAP-P12D-65 takes the Gençay guarantee as delivered. Fix: cite Fonseca's detector class for
  T1/T2 and keep "structural, by construction" for T8; keep GAP-P12D-65 open on T3/T4/T5/T8.

### X8 — LOW (design note, reasoned, not reproduced) — The engine day grid is anchored at 00:00 UTC, not at the engine's decision epochs
- `decision_cuts` steps from `spec.start` (midnight UTC). The engine's daily epochs are 17:00 New York
  (TSMOM daily close, the daily-loss day, rollover). A daily decision at 17:00 NY that peeks less than the
  3-4 h to the next UTC midnight is never compared under a perturbed peeked datum at the engine level. Fonseca
  Definition: freedom is "for every decision emitted at epoch t" — the natural grid is one cut just after each
  decision epoch. `--step-hours` can refine it; a cut at every 17:00 NY + one tick (plus the fold boundaries,
  already on the grid) would cover the daily decisions at no extra cost.

### X9 — LOW — The register's tier 4 "forward" starts at 2026-01-01, before the knowledge cutoff of the models that shaped the hypotheses
- Diff: `tests/backtest/look_register.py` `_window_tier`: tier 4 = [HOLDOUT_END = 2026-01-01, ∞), named
  "forward"; `test_the_tier_is_derived_from_the_data_never_claimed` pins a 2026-01..2026-06 Dukascopy window as
  tier 4.
- External referent: Yan, Tang, Gao, Jiang & Lu, "DatedGPT", arXiv 2603.11838v2 (23 Jul 2026,
  https://arxiv.org/html/2603.11838, fetched 2026-09-25): "When an LLM correctly predicts the 2008 stock market
  crash in a backtest, it is unclear whether the prediction derives from the information available at the
  time, or the model has simply seen the outcome during pretraining." The models building ACIS have a June 2026
  cutoff (this auditor's own; the VALIDATOR's §6 rule: "This session's cutoff (June 2026) covers all of
  2012-2025"). Historical data from Jan-Jun 2026 is therefore not post-cutoff, yet the register would label it
  "forward", the tier the protocol reserves for the only clean record of LLM-shaped hypotheses. Informational
  today (no 2026 ticks are on disk; the tier gates nothing), but the label will be read as evidence grade.
  Fix direction: forward = the demo's own start date (or a declared cutoff), not the holdout's end.

## Answers to the brief's three external questions
1. **Is T1/T2 a sound implementation of temporal non-interference?** As a detector, yes and strict: T2 compares
   by horizon, T1 by emission, and the component sweeps are exhaustive. As a certificate, no, and the literature
   says no sweep can be one (Fonseca §1, §8.3). What it cannot see here: M1 at the engine/Governor/book level
   (daily grid; declared R1) and X8; M2 for any channel the tape holds constant (tick rate, volume, spread in bps)
   or a short tape never exercises (X6); M3 for decisions stamped by the code under test or later than their
   true epoch (X2, demonstrated); and every availability-vs-reference-time family (event calendar vintages, SPX
   16:00 NY vs date joins, provider clock shifts) because synthetic tapes have availability = reference time
   (T3, not built). Zhang et al.'s EXEC_OPEN class is caught at entry (open and close are both cuts) but not
   at a gap exit (X2).
2. **The look register** meets pre-registration's "write before you look" and counts crashed grades, but not
   the ledger properties DSR/PBO need (outcomes, completeness and immutability by construction) — X4.
3. **T6** matches the standard gap-through-stop convention (OANDA v20, backtrader) for stops; it departs for
   targets (X3), charges the wrong spread at the gap (X2), and its claim about the graded book is false (X1).

## Honest negatives
- A whole-tail statistic leak (the efficiency ratio of everything after bar i — invariant under
  reverse/negate/double only when the window is the pure tail) IS caught by both tests in the fitness sweep
  (k = 0.002: T2 177/479 cuts, T1 359/479): every bar before a cut sees a MIXED past+perturbed tail.
  Repro: `tree/tests/backtest/test_zz_audit_ext_m2.py`.
- The F3 materialisation leak IS caught by T2 on a 400-tick synthetic tape (36/100 cuts), and would very likely
  be caught at the engine level, whose tapes are 12+ days.
- T2 compares by HORIZON (the latest datum the decision may use), which is stricter than Fonseca's Definition
  (comparison per emission epoch), and T1 compares by emission: the pair is a faithful, strict operationalisation
  of temporal non-interference at the swept epochs.
- SPX closes are left unperturbed by T1/T2, but they feed only the report's metrics (`harness.py:264`), not any
  decision — not a leak channel.
- Synthetic looks go to per-run registers, never the real one: consistent with Gençay §4.1 ("Deliberately
  planted demonstration arms (the E1 oracle) are excluded so that their pathological Sharpe ratios cannot
  distort the deflation of honest arms").
- T6's stop rule for a bar that OPENS through the stop (exit at the open, long and short) matches both the
  OANDA v20 StopLossOrder semantics and backtrader's Stop rule quoted in X1.
- Exclusive create (`open(path, "x")`) maps to O_CREAT|O_EXCL, atomic on NTFS; two concurrent registrations
  cannot claim one number (only the torn-write case in X4(f) remains).
- A look is written before the grade and survives a crashing grade (the line precedes `verify_look` and all
  compute); the real-data script refuses on missing labels BEFORE registering, so refused runs do not inflate
  the count. Counting refused holdout attempts (look written before `begin_final`) errs conservative.
- The AGON component sweep shares one `ProvenanceStore` across all variants, which would be a cross-variant
  channel if AGON wrote to it; it only reads (`is_registered`, `entry_allowed`, `core/signals/agon.py:78,219`),
  so it is not.
- Lead pre-checks consistent with the diff as read: `report.py` gains only `look: Mapping` (no clause of
  `passed` reads it); the diffstat touches no guardrail config, spec or ledger file.

## Method and budget
- WebSearch: 4 of the 20-call cap. Everything else WebFetch on primary URLs (arXiv abs/html/pdf, OANDA
  developer docs, backtrader docs, OSF help, the DSR paper PDF); PDFs extracted locally with pypdf into
  `SCRATCH/audit2_external/{fonseca,gencay,zhang,dsr}.txt`.
- Runs: private export only, `python -m pytest -p no:cacheprovider` on single files, ~2 GB free checked
  first; `scripts/leakage_suite.py` was NOT run.
- Repro files: `x1_book_gap.py`, `x_register.py`, `x_exec_open2.py` (and the dormant-tape `x_exec_open.py`),
  `m2probe.py`, and in the export `tests/backtest/test_zz_audit_ext_f3.py`,
  `tests/backtest/test_zz_audit_ext_m2.py`, `tests/unit/test_zz_audit_ext_t6.py`.

**Status: COMPLETE (2026-09-25).** Ranked: X1 high; X2 medium-high; X4, X5, X7 medium; X3 medium-low;
X6, X8, X9 low. None is triaged here: a finder, not a clearer (A5); triage belongs to the lead (A6).
