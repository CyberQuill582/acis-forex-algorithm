# AUDIT BRIEF: everything since the post-R1.6 audits, before the AWS cutover (pinned 2026-10-03)

> **Pinned before launch (constitution A4).** The owner's go came in chat on 2026-10-03 (third session), answering the
> session's standalone ask: "Launch both now (Recommended)". This is the constitution's pair (A3), one agent per lens, on
> Opus 5.5 in fresh context, from the role files `.claude/agents/acis-auditor-internal.md` and `acis-auditor-external.md`.
>
> **What is under audit:** the CHANGE from `f0d9524` (where the post-R1.6 audits ran) to **`9f57a6f`** on `main`
> (27 commits, ~85 files, ~4,200 lines).
> - Read the audited state with `git show 9f57a6f:<path>` and the change with `git diff f0d9524 9f57a6f -- <path>`.
> - The lead may keep working in the tree. The commit that pins this brief adds only documents.
> - The lead measured the full suite at `9f57a6f` on the server: **1428 passed, 6 skipped**, and `scripts/ledger_check.py` reports 296 entries, 0 violations.

## What changed, in priority order

**Tier 1: what reaches the demo at the cutover (2026-10-15..17). Attack this first.**
- **`48663d3` (master v2.31, GAP-P12D-150):** the post-R1.6 audit triage. Alpha decay is report-only on the one-lot demo, ILLIQUID is kept, and weekly rates get 28 days (`core/risk/alpha_decay.py`, `alpha_throttle.py`, `monitor.py`, `store.py`; `core/data/rates.py`; `config/targets_schema.py`, `config/system_config.yaml`; `core/runtime/executor.py`, `portfolio.py`, `engine.py`, `target_loop.py`, `target_decision.py`).
- **`14f160e` (master v2.33, GAP-P12D-152):** the target path's own feed check replaces NVMA. It touches `core/runtime/feed_check.py` (`FeedWatch`), `core/runtime/engine.py`, `core/governor/target_gate.py` (`entry_refusal`), `core/governor/guards.py` (`target=True` skips every regime check), `core/regime/regime_types.py` (`integrity_tradeable` removed), `core/runtime/target_wiring.py` and `target_loop.py`. The residual is owned by GAP-P12D-153.
- **`ce6c598`:** metals and indices DECLARED and disabled in `config/instruments.yaml`, plus `config/calendars.py` and `core/data/fx_clock.py`. The demo trades D1 on the 13 FX only; owner ruling "FX13 only; shelve onboarding" (GAP-P12D-151).
- **`b5dc63a`:** the demo's forward record. The uncapped shadow book in `TARGET_DECIDED` (`core/governor/target.py`, `core/runtime/target_decision.py`) and `scripts/demo_report.py`.
- **`deploy/README.md`, `deploy/systemd/acis-macro.service`, `scripts/download_macro.py` and `scripts/macro_checks.py`:** the host's daily rates.

**Tier 2: the real-data look machinery (R1.4) and its scope.**
- **`bd95e12`, `7a2711d`, `2bf0cb1` (GAP-P12D-104/111/100/149/127/86):** the stage-A verdict and C-BT-11 v2's `passed`; looks name their cycle, outcomes join the hash chain, and the simulator is bound (`look_cycles.py`, `look_outcomes.py`); the register's GitHub anchor (`tests/backtest/look_anchor.py`). The files are `tests/backtest/look_register.py`, `look_gate.py`, `look_claims.py`, `stage_a.py`, `report.py`, `oracle.py`, `evaluate.py`, plus `verdict.py`.
- **`5d75e9e` (master v2.32):** real-data looks open, scoped to literature/human RSIM claims; an LLM-selected claim is kill-only at HAC t < −0.5. Also `scripts/r1_d1_kill_test.py` (GAP-P12D-151).

**Tier 3: the event simulators and the four families' looks (GAP-P12D-154, 156, 157, 158).**
- **D3 (`5fe7a0f`, master v2.34, ACIS-09 v1.12):** `tests/backtest/exchange_days.py`, `event_sim.py`, `evaluate_events.py` and `scripts/r1_d3_kill_test.py`. D3 was dropped.
- **REBAL (`2bbdc27`):** `tests/backtest/rebal.py`, `event_daily.py`, `scripts/download_treasury.py` and `scripts/r1_rebal_kill_test.py`. v1a survived at 0.50.
- **IMOM (`7a38ba1`):** `scripts/download_dukascopy_minutes.py`, `tests/backtest/candles_min.py`, `event_intraday.py` and `scripts/r1_imom_kill_test.py`. Both versions were killed.
- **GOTOBI (`a243f57`, `03e2d58`; the strongest result so far, ATTACK IT FIRST within tier 3):** `scripts/download_jp_holidays.py`, `tests/backtest/jp_days.py`, `bi5.decode_arrays`, `tests/backtest/event_window.py` and `scripts/r1_gotobi_kill_test.py`. v1a scored 1.81 (t 6.51), v1b 1.96 (t 7.12), v1c 1.79 (t 6.49). The forward draft is `archive/GOTOBI_LIVE_DRAFT_2026-10-03.md`, owner rulings in GAP-P12D-158.
- **The tests in the diff:** `tests/backtest/test_*` for each of the above, and `tests/unit/test_target_path.py`, `test_risk_monitor.py`, `test_module_budget.py`, `tests/integration/test_target_*.py`.

## The authority
- **The spec:** master `ACIS_SPEC.md` v2.34 (the changelog entries v2.31–v2.34; §2 the conflict table; §5.6 the provenance and certification law; §8 alpha decay; §14). Also `specs/ACIS-02` v1.6, `ACIS-04` v1.8 §4b, `ACIS-05` v1.11 §6.4/§7, `ACIS-07` (alpha decay), `ACIS-09` v1.12 (the look register, stage A, the event simulator) and `ACIS-13` v1.4.
- **CLAUDE.md:** "Never touch without a human" and the guard-integrity law.
- **The owner's rulings,** verbatim in `KNOWN_GAPS.md`: GAP-P12D-150 to 158, 86, 104, 127 and 149.

## The lead's claims: re-verify them; they are not settled
- **The feed watch (Tier 1).**
  - A daily target entry reads ONLY the feed check (`no_feed`, `stale_feed`, the spread rule, the market-closed rule) and the integrity of its own inputs. No NVMA state reaches the target path.
  - An exit or flatten is never refused by it.
  - The legacy signal path's vetoes are byte-for-byte unchanged.
- **Alpha decay report-only on the one-lot demo:** this changes NO guardrail, HALT or veto semantics (CLAUDE.md "Never touch without a human"). A human resume is still the only clearing path.
- **The shadow book** records the uncapped target beside the capped one and never feeds an order.
- **The register.**
  - Every real-data grade passed `begin_grade` with the anchor at its head.
  - Paired lines (REBAL v1a/v1b, IMOM v1a/v1b, GOTOBI v1a/v1b) were all registered before either was graded.
  - An event look that is not kill-only is refused.
  - The outcomes for looks `000001`–`000020` chain unbroken (the register is git-ignored, at `data/validation/looks` on the laptop and in `gs://acis-compute-0929-data/validation/2026-10-03f/`).
- **GOTOBI.**
  - Every price is the last tick at or before its JST wall time, within 300 s, so nothing looks ahead.
  - Tick files are UTC days.
  - The day set is Bessho's (5/10/15/20/25/30, the month's last day when shorter, moved to the previous Japanese bank day, Tue–Fri).
  - The bank calendar matches `exchange_days`' XTKS rules on every in-scope day except the TSE outage of 2020-10-01.
  - Control days exclude every gotobi day. Each leg pays C8 at both sides' spreads, and P&L lands on the first 17:00 New York mark after the last exit.
- **Module size:** no module under audit is over 300 lines, and the governance gate is red only on the constitution pin (GAP-C10-01).

## Declared choices the lead made: attack them
- **GOTOBI's book.**
  - A 7-hour trade (14:00 → 20:55 New York in summer) straddles the 17:00 mark and is booked whole on the NEXT mark. Does that bias the annual Sharpe or the HAC t?
  - The Sharpe annualises a sparse vector of 3,108 weekday marks, 740 of them non-zero.
  - Both cost sides are divided by the entry price.
  - The cost model is the C8 USD_JPY entry in `config/instruments.yaml` at Dukascopy's quoted spread.
  - The 300 s staleness bound.
  - Bessho's "30" clipped to February's last day: the paper is silent on February.
  - The 31 Dec – 3 Jan bank closure rule.
  - Mondays are dropped (Bessho §2).
- **The kill rule HAC t < −0.5** and the HAC lag in `verdict.kill_verdict`. Do the GOTOBI t-statistics (6.5–7.1) survive a correct Newey–West on this sparse series?
- **The feed watch's thresholds** (2 × 120 s; the spread multiple; the closed-market rule). Is any NVMA-era protection lost that §2 still requires (a macro-event blackout, `UNCLASSIFIED` warm-up, NaN)?
- **The event simulators' quoted-hour rule** (GAP-P12D-156: a moving zero-volume quote counts as a price in the event book but not in RSIM). Is it applied consistently, and is any look's sample biased by it?
- **REBAL's 7-year par duration approximation** for the note leg, and v1a's signal computed from the close it trades at (declared as an idealisation).

## Rules for both auditors
- **Fresh context, Opus 5.5, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit, or run git commands that write. Read the audited state with `git show 9f57a6f:<path>`; never trust the working tree to equal it.
- **LOOK DISCIPLINE (binding, master §5.6, ACIS-09):** never compute a strategy's P&L, Sharpe or any return-dependent statistic on REAL market data outside the register. That would be an unregistered look.
  - You MAY read the stored outcomes and vectors of looks `000001`–`000020` (`tests/backtest/look_claims.load_vector`, `LookRegister.outcome`).
  - You MAY run P&L-blind checks on real data: timestamps, prices at a wall time, spreads, calendars, counts.
  - You MAY run ANY probe on synthetic data.
  - To show a defect changes a result, build a synthetic counter-example. Do not re-run a varied rule on real data.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite or any probe that does real work locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of the audited commit:
    `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/5bfd3abc-d062-49c8-82c5-18c2305e8ba8/scratchpad/remote_audit_pc.sh" <internal|external> "<command>"`.
  - Pass `--base` as a third argument to run in a checkout of `f0d9524` instead (to show a regression test fails there).
  - Put probe scripts in `…/scratchpad/audit_pc/<internal|external>/probes/` (they ship on each call) and run them as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - The real tick, minute and candle data are NOT on the server. For a P&L-blind check on real data, read a FEW of the laptop's git-ignored files locally: `data/dukascopy/<INSTRUMENT>/…_ticks.bi5`, `data/r1_real/dukascopy_minutes/`, `data/r1_real/jp_holidays/`, `data/r1_real/treasury/`, `data/validation/looks/`. A handful of file decodes is fine; bulk scans are not.
- **Refutation (A6).** Every internal-lens finding is reproduced by a script and cites `file:line` at `9f57a6f`. Every external-lens finding quotes its source with a dated, retrievable URL. An unreproduced claim is recorded as *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar:
  - correctness, and requirement gaps against the spec;
  - hollow or weakened tests (A16);
  - A12 size and legibility;
  - A13 hygiene: a read-path claim the code or the ledger contradicts, or spent scaffolding;
  - ledger closure: `python scripts/ledger_check.py` green, plus a spot-check that each new `Residual:` honestly owns what is unbuilt.

  Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_PRECUTOVER_INTERNAL_2026-10-03.md`; EXTERNAL writes `archive/AUDIT_PRECUTOVER_EXTERNAL_2026-10-03.md`. That file is your ONLY repo write. Its shape: an executive summary; findings (ID, Severity/Likelihood, tier, reproduction, proposed fix); honest negatives; what you could not verify; residual risk. Put the cutover-blocking findings first. The lead triages the report into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **Guard integrity at the cutover.**
   - Can the feed watch, the report-only alpha decay, the shadow book or a config flag weaken a guardrail, a HALT, or a veto on the signal path?
   - Can a restart or a missing rate file let an entry through that the spec refuses?
   - Does master §2's priority (HALT > veto > hard limit) still hold on the target path?
2. **The feed watch's edges.** A feed that ticks but freezes its price; a weekend open; a DST change; a reconnect storm; a spread spike at the 17:00 slot; an instrument whose clock is unproven; an exit while the feed is stale.
3. **The register's integrity.**
   - Can a look be graded without its line, graded twice, or graded at a different commit or cost than it registered?
   - Can the anchor fall behind silently?
   - Can an event look claim a pass?
   - Do the pairs' "both lines before either grade" hold in the scripts' actual order?
4. **GOTOBI's result, from every side.**
   - Look-ahead at 03:00 and 09:55; the time zone (JST has no DST; the tick files are UTC); the calendar; the control's construction; the cost model; the booking mark; the HAC t.
   - Whether 740 trades with a mean of +5.3 bp could arise from a defect: for example a mis-scaled price, a wrong sign, entry and exit swapped, gotobi days leaking into the control, or a day counted twice.
   - Prove a defect with a synthetic market, never by re-running a varied rule on real data.
5. **The other simulators.** D3's windows, REBAL's equations against the paper, IMOM's book. Is every recorded number reproducible from the stored vectors?
6. **Tests (A16).** Would each new test fail on `f0d9524` or on a plausible wrong implementation? Is any assertion weaker than its name claims?

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces 1, 2, 3, 4 and 6.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch only; the lead has already fetched arXiv 2301.13204 and NBER w22820's abstract):** the design and the implementation against the outside world.
  - **GOTOBI.** Check against Bessho, Sugimoto & Suzuki (arXiv 2301.13204), Ito & Yamada (JIE 109, 2017) and Akiyama et al. (JAFEE 2021):
    - the exact day definition, including the month's end and February, and the holiday move;
    - the entry and exit times, the data and the cost treatment;
    - every departure: is it declared?
    - whether the TTM is set at 09:55 JST on every bank day;
    - the Japanese bank-holiday law (the 31 Dec – 3 Jan closure);
    - independent evidence on whether the gotobi effect persisted or decayed after 2020;
    - Dukascopy's USD/JPY quotes against EBS at 03:00 and 09:55 JST;
    - realistic retail-venue (Pepperstone cTrader) USD/JPY spreads at those times.
  - **The other families:** Baltussen, Da, Lammers & Martens (JFE 2021) for IMOM's ROD and its last-half-hour book; Harvey, Mazzoleni & Melone (SSRN 5122748) for REBAL's Threshold and Calendar equations and position; McConnell & Xu (2008) for D3's window.
  - **Statistics:** the Newey–West HAC t and its lag choice; annualising the Sharpe of a sparse daily series; whether a kill rule at t < −0.5 is a sound one-sided screen.
  - **The feed watch:** do its thresholds match how the cTrader Open API delivers spot quotes (heartbeat and quote cadence)?
  - **The rule for every item:** a spec that is wrong about the world is a finding.
