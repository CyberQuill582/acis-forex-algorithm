# AUDIT BRIEF — the post-R1.6 changes that reach the demo at the cutover (pinned 2026-10-03)

> **Pinned before launch (constitution A4).** The owner's go, in chat on 2026-10-03, answering the
> session's standalone ask: "Launch both now (Recommended)". This is the constitution's pair (A3),
> one agent per lens, on Opus 5 in fresh context.
>
> **What is under audit:** the CHANGE from `de96a75` (where R1.6's audits ran) to **`f0d9524`** on `main`.
> Read the audited state with `git show f0d9524:<path>` and the change with `git diff de96a75 f0d9524 -- <path>`;
> the lead may keep working in the tree. The commit that pins this brief adds only documents.
> - **`d7f0875` — the R1.6 audit's fixes** (GAP-P12D-144: R16I-01..13, R16E-01..06): the rates fetched from
>   2011 (`scripts/download_macro.py --live`); opens in flight counted in every exposure (`core/runtime/executor.py`,
>   `core/runtime/portfolio.py`); A8 on every tick and the decision waiting for a proven clock
>   (`core/runtime/target_loop.py`, `core/runtime/engine.py`); the day's decision persisted, no re-entry after a
>   restart; `no_target:fetch_failed` and the history-hole rule; 240-day history windows with coverage checks
>   (`core/data/ctrader/history.py`); a missing rate file stales only its currency (`core/data/rates.py`); the cap
>   re-applied at the slot; flatten-then-promote moved to `core/runtime/target_promotion.py`; the mock face mapping
>   the shipped universe (`core/execution/mock_face.py`); the TREND record's declared deviations
>   (`core/signals/families.py`).
> - **`093cf3e` — master v2.29, GAP-P12D-146:** R6-1's rate freshness per source cadence, 21 days for the weekly
>   sources (BIS for AUD, the SNB cube for CHF), 10 for the daily (`core/data/rates.py` `WEEKLY_SOURCES`,
>   `RateTable(per_ccy=…)`, `config/targets_schema.py`, `config/system_config.yaml`, `core/runtime/target_wiring.py`).
> - **`f0d9524` — master v2.30:** GAP-P12D-145, a human resume clears the alpha-decay throttle, which then re-arms
>   only on post-resume trades against the arming baseline (`core/risk/alpha_decay.py`, the new
>   `core/risk/alpha_throttle.py`, `core/risk/monitor.py`); GAP-P12D-147, a daily target entry ignores NVMA's
>   confidence and label vetoes and the low-confidence guard and keeps the data-integrity gates
>   (`core/regime/regime_types.py` `integrity_tradeable`, `core/governor/guards.py` `target=True`,
>   `core/governor/target_gate.py`).
> - **The tests** in the diff: `tests/unit/test_target_path.py`, `test_risk_monitor.py`, `test_download_macro_live.py`,
>   `test_module_budget.py`; `tests/integration/test_target_loop.py`, `test_target_runtime.py`,
>   `test_ctrader_history.py`, `test_adapter_conformance.py`; `tests/ctrader_fixtures.py`.
>
> **The authority.**
> - The spec: master `ACIS_SPEC.md` v2.30 (its v2.29 and v2.30 changelog entries; §2 the conflict table; §4 the
>   NVMA veto, as amended; §6 hard overrides, as amended; §8 alpha decay; §10 decisiveness);
>   `specs/ACIS-04-ALPHA_ARENA.md` v1.7 §4b (R6-1); `specs/ACIS-05-CAPITAL_GOVERNOR.md` v1.9 §6.4 and §7;
>   `specs/ACIS-07-RISK_MONITOR.md` v1.4 §7 (alpha decay, GAP-0050, restart reconciliation);
>   `specs/ACIS-13-VENUE_ADAPTERS.md` v1.4 (A8, §6.5); CLAUDE.md "Never touch without a human" (HALT/veto semantics;
>   the guard-integrity law).
> - The owner's rulings, verbatim in `KNOWN_GAPS.md`: GAP-P12D-145 (incl. the 2026-10-03 "Fresh evidence only"),
>   146, 147. The triage of R1.6's audits: GAP-P12D-144 (and the reports `archive/AUDIT_R1_6_*_2026-10-02.md`).
>
> **The lead's claims — re-verify them; they are not settled:**
> - the full suite at `f0d9524` gives 1347 passed, 6 skipped on the server; `python scripts/ledger_check.py` is green;
> - every R1.6 finding GAP-P12D-144 calls FIXED is actually fixed by the change, and each cited regression test
>   would FAIL on `de96a75` (A16: a test that passes on the unfixed code proves nothing);
> - a human resume is the ONLY path that clears the throttle early; a blank token clears nothing; the trades that
>   armed it cannot re-arm it after a resume, and 30 decayed post-resume trades do; a restart can never relax it;
> - the signal path's vetoes are byte-for-byte unchanged; a target entry is still refused on a stale, spread-vetoed
>   or dead market, MACRO_EVENT, ILLIQUID, UNCLASSIFIED (warm-up, NaN), or a veto whose reasons were not recorded;
>   an unregistered family still gets no target;
> - AUD 18 days old is fresh, USD 11 days old is stale; RSIM's and the harness's rate callers are unchanged;
> - no module under audit is over 300 lines (monitor.py fell from 343 to 332).
>
> **Declared choices the lead made — attack them:**
> - 147 keeps ILLIQUID as an integrity gate (the ruling's list named stale, spread, dead market, macro event,
>   warm-up and NaN; ILLIQUID is spread- or closed-session-based and the code already treats it as a gate state);
> - 147 also skips §7.1's `low_confidence` guard for target entries, because it reads the same confidence as NVMA's
>   veto (exempting only the veto would have changed nothing);
> - `NO_PARAMS_FOR_REGIME` is skipped for target entries on the grounds that the target loop refuses an
>   unregistered family itself — check that this really carries master §2's "no registered, validated rule set" row;
> - 145's fresh-evidence window uses the baseline at the resume (`trades[-200:-50]` then) until the recent window is
>   all post-resume trades, then reverts to the standard rule; the fresh-evidence marker is not persisted (the lead
>   argues a restart empties the trade history, so every post-restart trade is fresh anyway);
> - 146's weekly sources are exactly `bis_policy` and `chf_saron`; is the SNB cube's SARON series really weekly, and is
>   21 days the right bound for both publication cadences?
> - the deposit-safety claim in GAP-P12D-142 (a deposit's `DEPOSIT_WITHDRAW` event is ignored; only an equity fall
>   trips a guard) and the "old engine sizes from the venue NAV" note.

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit, or run git
  commands that write. Read the audited state with `git show f0d9524:<path>`; never trust the working tree to equal it.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite or any probe that does real work locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of the audited commit:
    `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/23ea9019-cc22-46bc-9447-7c6cc3146f29/scratchpad/remote_audit_p16.sh" <internal|external> "<command>"`.
    Pass `--base` as a third argument to run in a checkout of `de96a75` instead (to show a regression test fails there).
  - Put probe scripts in `…/scratchpad/audit_p16/<internal|external>/probes/` (they ship on each call) and run them
    as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - Reading files and quick `grep`s locally are fine.
- **Refutation (A6).** Every finding is reproduced by a script on the server and cites `file:line` at `f0d9524`
  (internal lens), or quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as
  *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps against the spec, hollow or weakened tests (A16), A12
  size and legibility, A13 hygiene (a read-path claim the code or the ledger contradicts; spent scaffolding), and ledger
  closure (`python scripts/ledger_check.py` green, plus a spot-check that each new `Residual:` honestly owns what is
  unbuilt). Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_POST_R1_6_INTERNAL_2026-10-03.md`; EXTERNAL writes
  `archive/AUDIT_POST_R1_6_EXTERNAL_2026-10-03.md`. That file is your ONLY repo write. Its shape: an executive summary;
  findings (ID, Severity/Likelihood, reproduction, proposed fix); honest negatives; what you could not verify; residual
  risk. The lead triages it into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **Guard integrity.** Can any caller other than the one human resume reach `clear_by_human` or pass `target=True`?
   Can an agent, an MCP tool, a config flag or a restart clear the throttle or widen the veto exemption? Does the
   exemption leak into the signal path, a pair group, or an add?
2. **The veto exemption's edges.** Every NVMA reason and gate state against the target path: which admit, which refuse?
   A RegimeContext built without `veto_reasons` (the runtime's own defaults, a restored or synthetic context)? A
   stale classification read at the slot? Does §2's priority order (HALT > veto > hard limit) still hold?
3. **The throttle's state machine.** Resume while armed, while warming, while not armed; resume twice; a resume between
   arming and the Governor applying it; trades closing during the fresh window; the switch back to the standard rule;
   the persisted `alpha_armed` after a resume and a restart; the Governor's own throttle flag versus Risk's.
4. **The R1.6 fixes.** Is each one complete, and does any of them break something else (in-flight exposure counting
   double-counting after a fill; the persisted decision across a DST change or a day boundary; the coverage rule on a
   legitimate long holiday; the 240-day walk's termination)?
5. **Rate freshness.** The per-currency limit on every path that reads rates (decision, sizing, carry accrual, the
   restart re-derivation); a currency whose source changes cadence; the macro timer refreshing mid-decision.
6. **Tests (A16).** Would each new test fail on `de96a75` or on a plausible wrong implementation? Is any assertion
   weaker than the claim its name makes?

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces
  1, 2, 3, 4 and 6.
- **EXTERNAL (WebSearch capped at 15 calls, then WebFetch only):** the design and the implementation against the outside world.
  - Publication cadences and lags: the BIS central bank policy rate dataset (WS_CBPOL) release schedule; the SNB's
    SARON series on data.snb.ch (daily or weekly; its publication lag); the daily sources (NY Fed EFFR, ECB DFR via
    the ECB data portal, BoE SONIA, BoJ TONA, BoC CORRA): is 10 days a sound bound for each, and 21 for the weekly ones?
  - Alpha-decay / strategy-retirement practice in systematic trading (Carver's and others' views on equity-curve
    filters and drawdown-based throttles; Harvey & Liu on performance decay): is a throttle that can lock a book out,
    and a human-reset with fresh-evidence re-arming, consistent with practice? Is the 0.5 × baseline mean/σ test on
    30–50 trades statistically meaningful, and what false-alarm rate does it have on a zero-change process?
  - Regime-filter vetoes on slow trend systems: does the literature support gating a daily trend entry on an intraday
    confidence measure, or on liquidity/spread only (the ruling's split)?
  - Does anything the spec or code assumes about the world contradict it? A spec that is wrong about the world is a finding.
