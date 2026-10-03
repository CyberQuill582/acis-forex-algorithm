# AUDIT — post-R1.6 changes, INTERNAL-CONSISTENCY lens (constitution A3, lens 1), 2026-10-03

- **Brief:** `archive/AUDIT_BRIEF_POST_R1_6_2026-10-03.md` (pinned before launch, A4; the owner's go: "Launch both now (Recommended)").
- **Under audit:** the change `de96a75..f0d9524` on `main` (`d7f0875`, `093cf3e`, `f0d9524` and the documents between). Every citation below is `file:line` at `f0d9524`, read with `git show f0d9524:<path>`; the working tree was not trusted.
- **Auditor:** fresh context, Opus (claude-opus-5-5), no web. **A finder, not a clearer (A5):** a finding binds only after the lead's triage survives refutation (A6). This report is not a sign-off, and its honest negatives are not one either. No agent of any kind was launched.
- **Runs:** every probe and test ran on `acis-compute-1` through `remote_audit_p16.sh` in this lens's own checkout (`/opt/acis/audit-p16-internal`, pinned to `f0d9524`; `--base` = `de96a75`). Probes: the session scratchpad `audit_p16/internal/probes/p1..p10`. pytest `-n 8` at most. Mutants ran on a throwaway copy (`/tmp/acis_mut_*`), never on the checkout.

## Executive summary

The lead's headline claims reproduce: **1347 passed, 6 skipped** at `f0d9524` on the server; `python scripts/ledger_check.py` gives `286 entries checked; 0 violation(s)`; every R1.6 regression test cited as FIXED in GAP-P12D-144 **fails on the `de96a75` source** for a behavioural reason (A16 holds for them); the signal path's guard call is unchanged; a blank token clears nothing; the three new modules are under 300 lines.

The defects are at the edges of the two owner rulings and of one R1.6 fix:

1. **GAP-P12D-145 does not survive a restart.** Every start after a deliberate stop needs `--resume` (GAP-P12D-135), and that resume now clears a restored throttle with an EMPTY trade history. The ruled "re-arm on 30 post-resume trades against the baseline that armed it" then cannot happen: the baseline is gone. On a losing post-resume record the throttle never re-arms (500 trades tried; the in-process control re-arms at 30). [PR16I-01]
2. **The fresh-evidence baseline is the one at the resume, not the one that armed it**, and after 50 post-resume trades the arming trades themselves become the baseline. In three constructed cases the owner's rule re-arms and the code does not; in one, never within 400 decayed trades. [PR16I-02]
3. **Keeping ILLIQUID as an integrity gate keeps 72–76% of the slot blocking GAP-P12D-147 was opened about** (re-measured with the audited guard on the C-BT-12 ticks: 28 of 37 and 26 of 36 blocked slots stay blocked, all ILLIQUID). The owner's keep-list did not name ILLIQUID, yet master v2.30 §4 and ACIS-05 v1.9 present it as part of the ruling. [PR16I-03]
4. **R16I-05's in-flight model counts opens but not closes**, so a flip is judged one lot short, and a slot can carry the book past master §6's 30% single-currency cap (33% reproduced at $10k NAV, the paper book's NAV). Risk does not enforce that cap live. [PR16I-04]
5. **The `--live` rate downloader still demands 10 days of freshness from the weekly sources**, so it rejects BIS AU on Mondays to Wednesdays. On a fresh `data/macro_live` (the AWS cutover) AUD has no file and the three AUD pairs give no target. GAP-P12D-146 closes with `Residual: none`. [PR16I-05]

There are also five lower findings: no age check on the regime context or the mark at the timer-driven slot [PR16I-06]; master §2 and ACIS-02 left unamended against v2.30's veto exception [PR16I-07]; five load-bearing wirings or semantics that no test pins [PR16I-08]; stale read-path claims [PR16I-09]; and the target path not carrying the "validated" half of §2's rule-set row, which is pre-existing [PR16I-10].

| ID | Title | Severity | Likelihood |
|---|---|---|---|
| PR16I-01 | Restart + `--resume` clears a restored throttle with no baseline; the ruled re-arm can never fire | Medium | Medium |
| PR16I-02 | Fresh-evidence baseline is "at the resume", not "that armed it"; arming trades become baseline after 50 | Medium | Low–Medium |
| PR16I-03 | ILLIQUID kept as an integrity gate retains ~3/4 of the measured slot blocking; spec attributes it to the owner | Medium | High (synthetic) |
| PR16I-04 | In-flight closes not modelled: a flip lets a slot cross the 30% single-currency cap | Medium | Low on the $100k demo; Medium at $10k paper |
| PR16I-05 | `--live` downloader rejects weekly sources at 11–21 days; fresh dir leaves AUD with no rates | Low–Medium | High (3 of 5 weekdays) |
| PR16I-06 | Timer-driven slot reads a regime context and mark of any age; a silent feed is never "stale" | Medium | Low |
| PR16I-07 | Master §2 priority #2 and ACIS-02 §1/§7 contradict v2.30's target-entry veto exception | Low | Certain |
| PR16I-08 | A16: five wirings/semantics of this change survive mutation against the FULL suite | Low | Certain |
| PR16I-09 | A13: read path claims contradicted by the spec header and the ledger | Low | Certain |
| PR16I-10 | Target path carries "registered" but not "validated" (pre-existing; answers the brief's question) | Low | Low |

---

## Findings

### PR16I-01 — A restart followed by the `--resume` the next start needs clears a restored throttle with an empty trade history, so the ruled re-arm can never fire

- **Severity:** Medium · **Likelihood:** Medium (it needs the throttle armed at a restart). GATES found it still armed at the end of 38–64% of 10-year lab runs (GAP-P12D-145). Every deliberate stop halts `all` (`core/runtime/engine.py:235-238`), so every next start needs `--resume` (`core/runtime/__main__.py:16, 131`).
- **Where:**
  - `core/runtime/__main__.py:130-131`: `boot()`, then `--resume` → `acis_resume` → `RuntimeControl.resume` → `CapitalGovernor.resume` → `resume_gate` → `RiskMonitor.on_human_resume` (`core/runtime/wiring.py:210`).
  - `core/risk/monitor.py:63`: `_trades` starts empty and is never persisted.
  - `core/risk/monitor.py:302` → `core/risk/alpha_throttle.py:51-58` → `core/risk/alpha_decay.py:100-103`: `clear_by_human(len(trades) == 0)`, so `_fresh_from = 0`.
  - `core/risk/alpha_decay.py:108-111`: the fresh baseline `trades[max(0, f-200):max(0, f-50)]` is `trades[0:0]`, which is empty, so the reading is `inactive_warming` until the fresh window ends.
  - The standard rule then needs 100 trades (`alpha_decay_baseline_min_trades: 50`), and its baseline is made of post-resume trades: a decayed record is compared with itself, and `flag` requires `s_baseline > 0` (`alpha_decay.py:131`).
- **What it contradicts:**
  - The owner's 2026-10-03 ruling (KNOWN_GAPS GAP-P12D-145): "after a human clear the detector reads only post-resume trades as recent, against the baseline that armed it, and re-arms once `alpha_decay_min_trades` (30) of them show the decay".
  - ACIS-07 v1.4 §7 (`specs/ACIS-07-RISK_MONITOR.md:116`), which says the same.
  - The ledger's justification: "A restart needs nothing persisted: the trade history starts empty, so every post-restart trade is fresh evidence". The trades are fresh, but the reference they must be judged against is gone.
  - Before this change, a restart kept the throttle armed (GAP-0050). Now, restart plus the routine `--resume` disarms it with no memory, which is a stronger relaxation than the in-process resume the owner ruled on.
- **Reproduction:** `python probes/p1_restart_resume.py` (server, `f0d9524`):
  ```
  CONTROL in-process resume: re-armed after 30 decayed post-resume trades
  CONTROL in-process resume, losing process: re-armed after 30 post-resume trades
  process 1 armed: True persisted: True
  process 2 restored armed: True governor told: [(1.0, None), (None, True)]
  after --resume armed: False governor told: (None, False) trades in history at the clear: 0
  RESTART + --resume: re-armed after 101 decayed post-resume trades (...)
  RESTART + --resume, losing process: re-armed after None trades (None = never in 500)
  ```
  The flat ±1 record re-arms at 101 only through a parity accident: the first 51 post-resume trades have a mean of +1/51, so `s_baseline` is about +0.02. A losing record (−2/+1) never re-arms.
- **Proposed fix:** persist what the ruling needs across a restart. At the arming edge, store the arming baseline's `mean_sigma` and `n` with the restrictive state (`RiskStore.save_restrictive_state`), together with a fresh-from marker counted in post-restart trades. Judge post-resume trades against that stored value even when the trade history is empty. An alternative is to persist closed trades in `risk.db` and restore them at boot, which also closes the pre-existing "a restart forgets every baseline" gap. If neither is wanted, the owner should rule whether `--resume` at boot may clear a throttle whose baseline cannot be restored. Add a test: arm → persist → restart → `--resume` → 30 losing trades → armed.

### PR16I-02 — The fresh-evidence baseline is the one AT the resume, not the one THAT ARMED it; and after 50 post-resume trades the arming trades become the baseline

- **Severity:** Medium · **Likelihood:** Low–Medium. Case (a) needs trades to close between arming and resume. That is the normal case for a held book: entries are zeroed, but reductions, flats and stops are never blocked (C-EXE-7). Case (c) needs a sound first 30–49 post-resume trades followed by decay.
- **Where:** `core/risk/alpha_decay.py:108-113`. The fresh baseline is `trades[f-200:f-50]` with `f` the trade count at the RESUME. When the window ends, `_fresh_from = None` and the standard `trades[-200:-50]` returns, which then holds the arming trades `[A-50, A)` and every armed-period close. ACIS-07 v1.4 §7 (`specs/ACIS-07-RISK_MONITOR.md:116`) asserts an identity that holds only when no trade closes between arming and resume: "the baseline that armed it (`trades[-200:-50]` at the resume)".
- **Reproduction:** `python probes/p2_baseline_contamination.py`, using the real detector with the shipped config:
  ```
  (a) s(baseline that armed it) = 0.4983; s(baseline at the resume) = 0.3819      # 13 closes while armed
      post-resume 30-trade mean/sigma = 0.1919; ruling's threshold 0.2492 (re-arm), code's threshold 0.1909
      ruling re-arms: True; code re-armed after None of 30 trades (None = not)
  (b) first resume: re-armed after 30 decayed post-resume trades (fresh window works)
      second resume: baseline at it = trades[30:180] holds 30 of the first arming trades; s = 0.2776 vs s(arming) = 0.4983
      ruling re-arms: True; code re-armed after None of 30 (None = not)
  (c) 49 healthy post-resume trades: re-armed after None (None = not)
      s(arming baseline) = 0.4983; decayed recent s = -0.4950 (< 0.2492: the ruling re-arms at 30)
      code: re-armed after None decayed trades (None = not within 400); final baseline s = -0.4983
  ```
  In (c), at the 50th post-resume trade the baseline becomes `trades[50:200]`: 100 good trades plus the 50 arming losers, so `s_baseline < 0`. `flag` needs `s_baseline > 0`, so nothing can re-arm. Once the losers roll out, the baseline is the decayed record itself.
- **Proposed fix:** at the arming edge, snapshot the arming baseline (its slice bounds or its `mean_sigma`). Use the snapshot for the fresh window, and keep excluding pre-resume trades from the reference until they leave `trades[-200:-50]`. How the throttle behaves after 50 fresh trades is an owner call, because the ruling is silent on it. Correct the ACIS-07 §7 wording to match whichever is chosen. Add the (a) and (c) cases as tests.

### PR16I-03 — Keeping ILLIQUID as an integrity gate retains about three quarters of the slot blocking GAP-P12D-147 addressed, and the spec presents ILLIQUID as part of the owner's ruling

- **Severity:** Medium · **Likelihood:** High on the only measurement available (synthetic ticks); the real-tick rate is unmeasured.
- **Where:**
  - `core/regime/regime_types.py:30-34, 81-90`: `integrity_tradeable()` refuses every `NEVER_TRADEABLE` label, ILLIQUID included.
  - `core/governor/guards.py:67-68`: `illiquid` still applies with `target=True`.
  - ILLIQUID is NVMA's window-σ spread test or a closed session (`core/regime/nvma.py:276-281`), which is exactly "a 1-minute classification at its slot". The ruling's stated rationale was that a daily decision should not hang on one.
- **The ruling vs the text:**
  - KNOWN_GAPS GAP-P12D-147, owner ruling 2026-10-02: the integrity gates that "still apply" are "(stale state, the spread veto, a dead market, a macro event, warm-up, NaN indicators)". ILLIQUID is not in the list, while "the regime label itself" is exempted.
  - Master v2.30 §4 (`ACIS_SPEC.md:172`) and ACIS-05 v1.9 (`specs/ACIS-05-CAPITAL_GOVERNOR.md:116`) list ILLIQUID among the kept triggers, under the changelog's "owner-ratified in chat".
  - The lead's Fix note declares the choice. The spec text, however, attributes it to the owner.
- **Reproduction:**
  - `python probes/p7_slot_census_after_147.py {null,planted} 60`: the method of GATES' `nvma_slot_census.py` (production `MarketStateFactory` + NVMA on C-BT-12 ticks, `has_params` True, 120 s cycle, 08:00 New York slot), with each slot judged by the audited `EntryGuards.check(..., target=True)`:
    ```
    null, 60 days, 82 slots
      signal-path guard (de96a75's target behaviour): blocked 37/82
      target=True guard (f0d9524):                    blocked 28/82
      what still blocks the target entry: {'veto:ILLIQUID:-': 28}
      share of the old blocking that remains: 76%
    planted, 60 days, 82 slots
      ... blocked 36/82 → 26/82, all 'veto:ILLIQUID:-'; 72% remains
    ```
  - It agrees with GATES' 126-day file on the server (`/opt/acis/gates_out/nvma_null_126.json`: `slot_veto_reasons {'ILLIQUID': 58, 'LOW_CONFIDENCE': 15}`), so 58 of 73 slots stay blocked after the fix.
  - GATES flags the share as probably inflated by the generator's constant-fraction spread (a near-constant spread has a tiny σ). The direction of the gap is not in doubt; its size on real ticks is.
- **Proposed fix:** put ILLIQUID to the owner as one question, with these numbers. Until the owner rules, change master §4 and ACIS-05 §6.4 so ILLIQUID reads as the lead's restrictive addition, not part of the ruling. Count `TARGET_ENTRY_ZERO` reasons on the demo (already TODO item 3) so the owner rules on real-tick data. If ILLIQUID is exempted, the separate `SPREAD_VETO` (spread > 3× the session median) still guards the spread.

### PR16I-04 — R16I-05 models opens in flight but not closes in flight, so a flip is judged one lot short and a slot can cross master §6's 30% single-currency cap

- **Severity:** Medium · **Likelihood:** Low on the $100k demo, where the caps are inert. Medium at $10k NAV: the paper book's NAV (`config/system_config.yaml` `runtime.paper_nav_usd: 10000.0`; a supervised restart comes back in paper) and the R6-5 design point.
- **Where:**
  - `core/runtime/portfolio.py:55, 68`: in-flight opens are added as positions. The held position that the same WorkItem's reduce-only close will remove still counts.
  - `core/governor/target_gate.py:77-82`: a flip's opening leg is judged against the portfolio that still holds the position being closed, which predates R16I-05.
  - `core/governor/exposure.py:41-47`: the currency cap.
  - Risk has no live single-currency check: only `core/risk/scenario_replay.py:62` reads `single_currency_delta_cap_pct`, so nothing halts once the cap is crossed.
  - The test name claims "so one slot cannot cross a cap".
- **Reproduction:** `python probes/p9_flip_in_flight.py`. At $10k NAV the book holds EUR_USD +1 lot and EUR_JPY −1 lot. The slot flips EUR_USD to −1, then opens EUR_GBP −1:
  ```
  single-currency cap 3000.0 (entry headroom 2700.000)
  EUR_USD: flip [('close', 1, '1000'), ('open', -1, '1000')]
  in flight: EUR delta the next entry is judged against = -1100.000343750107421908569346
  EUR_GBP short: open
  once filled the EUR delta is -3300.0 (33% of NAV; hard cap 30%): OVER the cap
  the flip's own open was judged at -1100.0 (held +1 still counted); with closes modelled it is -2200.0, and EUR_GBP would see -2200.0 -> -3300.0: refused
  ```
- **Proposed fix:** treat in-flight CLOSES as filled too. `Executor` can keep in-flight closes beside opens, and `build_portfolio` nets their units out of the held position. Judge a flip's opening leg against the portfolio net of its own closing leg. Add the flip case to `test_opens_in_flight_count_in_every_exposure_so_one_slot_cannot_cross_a_cap`, or rename the test to what it proves.

### PR16I-05 — `scripts/download_macro.py --live` still demands 10-day freshness from the WEEKLY sources

- **Severity:** Low–Medium · **Likelihood:** High (on BIS's cadence the AU series is rejected on 3 of 5 weekdays).
- **Where:**
  - `scripts/download_macro.py:252`: `ends_by = today - timedelta(days=10)` for every live series, `bis_policy` and `chf_saron` included.
  - `:271-275`: a rejected series is not written, and the script exits 1 (`:295`).
  - `:28`: the docstring still says "fresh within 10 days (R6-1)".
  - The engine accepts 21 days for the same sources (`core/data/rates.py` `WEEKLY_SOURCES`; `config/system_config.yaml` `rate_max_stale_days_weekly: 21`).
- **Effect:**
  - With an existing file, the old file stays (same data), and the `acis-macro.timer` run fails on Mondays to Wednesdays. That trains the operator to ignore its failures.
  - With a FRESH `data/macro_live` (the AWS cutover, 2026-10-15 is a Thursday, but any first run on a Monday to Wednesday), no `bis_policy.csv` is ever written until BIS's next release. `load_rate_table` then has no AUD series (R16I-08's rule) and AUD_USD, AUD_JPY and EUR_AUD give `no_target:stale_rates`: the divergence GAP-P12D-146 was ruled to remove.
  - GAP-P12D-146 closes with "Residual: none". That is a ledger-closure miss (A15): unowned work under a closed label.
- **Reproduction:** `python probes/p4_live_download_weekly.py`, with AU last observed 2026-09-24, as in BIS's 2026-10-01 release cited in the ledger:
  ```
  2026-10-05 (Mon): AU last obs 11 days old -> --live verdict: AU: ends 2026-09-24, expected by 2026-09-25; engine limit 21 days -> fresh
  2026-10-06 (Tue): ... 12 days ... REJECT ...; 2026-10-07 (Wed): ... 13 days ... REJECT
  fresh live dir, Monday 2026-10-05: AUD -> StaleRateError no rate series for AUD
  docstring still says: ['through today (never rolling), no SPX, fresh within 10 days (R6-1); run daily']
  ```
- **Proposed fix:** set `ends_by` per source: `today - (21 if sid in WEEKLY_SOURCES else 10)` days, importing `WEEKLY_SOURCES` from `core/data/rates.py` (one definition). Update the docstring. Add a test that `validate("bis_policy", …)` accepts 13 days in live mode. Reopen GAP-P12D-146's residual.

### PR16I-06 — The slot is timer-driven and reads a regime context and a mark of any age; a symbol whose feed goes silent is never classified stale

- **Severity:** Medium · **Likelihood:** Low (a per-symbol feed silence while the market is open).
- **Where:**
  - `core/runtime/target_loop.py:205-207` checks only that a mark exists. `:215` passes `regime_of(instrument)` (`nvma.regime_store.get`, `core/runtime/target_wiring.py:62-63`) with no age check.
  - `core/governor/guards.py:47-82` reads no timestamp.
  - `STALE_STATE` is set only when a tick ARRIVES late (`core/data/normaliser.py:246`; `core/regime/nvma.py:257`). A silent feed produces no tick and so no stale classification, and the runtime's stall detector fires only when no instrument ticks (`core/runtime/engine.py:190-194`).
- **What it contradicts:** the lead's claim that "a target entry is still refused on a stale … market", and the ruling's "NVMA's data-integrity gates still apply (stale state, …)". These hold for late ticks, not for missing ones. On the signal path a signal is born on a fresh tick, so this hole is specific to the timer-driven target path.
- **Reproduction:** `python probes/p6_stale_context_at_slot.py`:
  ```
  (a) context + mark 2 h old, feed silent since: open
  (b) same, but the last tick arrived late (STALE_STATE): veto
  (c) context 87 days old (the Rig's mk_regime T0 vs its SLOT): open
  ```
  Case (c) is the shipped suite's own setup: `tests/integration/test_target_loop.py` judges slot entries on `mk_regime()` stamped 2026-07-06 (`tests/signals_fixtures.py:20`) against a 2026-10-01 slot.
- **Proposed fix:** an integrity gate for the target path. Refuse the entry (`stale_context`, logged in `TARGET_ENTRY_ZERO`) when the instrument's context or last mark is older than about 2 × `regime.cycle_seconds`. The pieces exist: `RegimeContext.timestamp` and the runtime's tick timestamps. This keeps the ruling's "stale state" true for missing ticks too. The exit path stays ungated.

### PR16I-07 — Master §2's priority #2 and ACIS-02 §1/§7 contradict v2.30's target-entry veto exception

- **Severity:** Low (spec authority) · **Likelihood:** Certain.
- **Where:**
  - `ACIS_SPEC.md:87` (master §2): "Conflict resolution priority (highest wins): 1) Risk Monitor HALT · 2) NVMA `tradeable=False` veto · 3) Governor hard-limit override …". It has no exception.
  - `specs/ACIS-02-NVMA_REGIME.md:24`: "its `tradeable` flag is conflict-priority #2 … Nothing below NVMA can manufacture a trade in a regime NVMA has vetoed."
  - `specs/ACIS-02-NVMA_REGIME.md:81`: "The veto is a structural gate, not advice."
  - v2.30 changed only master §4/§6 (`ACIS_SPEC.md:172, 325`) and ACIS-05 §6.4 (`:116`). The Governor now does place a target entry on a context NVMA marked `tradeable=False` for `LOW_CONFIDENCE`.
  - HALT/veto semantics are human-only (CLAUDE.md). An authority that contradicts itself here is how a later session either "fixes" the code back or widens the exception.
- **Reproduction:** read the cited lines at `f0d9524`. `tests/unit/test_target_path.py::test_a_target_entry_ignores_the_confidence_vetoes_but_not_the_integrity_gates` is the code-side witness (`_nvma()` has `tradeable=False` and gives `open`).
- **Proposed fix:** an owner-ratified editorial pass. Add a target-entry exception to master §2's priority line pointing at §4 v2.30, and amend ACIS-02 §1/§7 the same way (ACIS-02 v1.5).

### PR16I-08 — A16: five load-bearing wirings or semantics of this change survive mutation against the full suite

- **Severity:** Low · **Likelihood:** Certain.
- **Reproduction:** `python probes/p5_mutants.py --full <mutants>` applies one mutant at a time to a COPY of the checkout and runs the whole `tests/` tree (`-n 8 -x`). The `none` control passes. Results:
  ```
  none: SURVIVED (no test fails) :: 1347 passed, 6 skipped in 228.14s            # harness control
  engine_drops_inflight: SURVIVED :: 1347 passed, 6 skipped        # engine.py:154 stops passing inflight= (R16I-05's wiring)
  wiring_drops_weekly: SURVIVED :: 1347 passed, 6 skipped          # target_wiring.py:69 weekly limit -> None (GAP-P12D-146's wiring)
  wiring_clock_always_ok: SURVIVED :: 1347 passed, 6 skipped       # target_wiring.py:63 clock_ok=lambda i: True (R16I-02's wiring)
  fresh_uses_standard_baseline: SURVIVED :: 1347 passed, 6 skipped # alpha_decay.py:111 removed (the "baseline that armed it")
  fresh_window_never_ends: SURVIVED :: 1347 passed, 6 skipped      # alpha_decay.py:109 window never ends (the switch back)
  ```
  Each test proves its unit (`build_portfolio(inflight=…)`, `load_rate_table(…, 21)`, the Rig's `clock_ok`, 30 fresh trades re-arm). None proves that the runtime is wired to it, or that GAP-P12D-145's two declared semantics hold. A regression in any of the five ships green. An extra subset-only mutant (`exemption_admits_unexplained`: drop `bool(reasons)`) was killed, as it should be.
- **The rest of A16:**
  - Every R1.6 fix regression and both rulings' tests fail on the `de96a75` SOURCE (`python probes/p8_regressions_on_base.py`, with `--base`: the audited test files overlaid on the base checkout, and the Rig's new `clock_ok` passed only if the base EngineView has it). The three that pass on base are expected: R16I-07 and R16I-09 pinned existing behaviour, and `test_a_human_resume_leaves_an_unarmed_throttle_alone` is a negative companion.
  - No test pins that `AlphaThrottle.clear_by_human`, and `RiskMonitor.on_human_resume` with it, has the one human caller. The "only the human resume" claim rests on the call graph alone: `RiskMonitor.on_human_resume` checks only that the token is non-blank (`core/risk/monitor.py:297-298`), and any holder of `risk` could call it.
- **Proposed fix:** add one assertion per surviving mutant:
  - a `Runtime.portfolio()` test with an executor item in flight;
  - a `build_targets` test that AUD 15 days old decides;
  - a `build_targets` test that `EngineView.clock_ok` is `runtime.clock_verified`;
  - the PR16I-02 cases;
  - the window's end at 50 fresh trades;
  - plus a structural (AST/grep) test that `clear_by_human` and `on_human_resume` are called only from the resume gate.

### PR16I-09 — A13: read-path claims contradicted by the spec header and the ledger at `f0d9524`

- **Severity:** Low · **Likelihood:** Certain.
- **Where:**
  - `STATUS.md:35`: "**Spec:** master `ACIS_SPEC.md` **v2.26**" (the master is v2.30); "**ACIS-13 (venue adapters) is the only unwritten spec**" (ACIS-13 is LOCKED at v1.4); "Governed by … **v0.5**" (CLAUDE.md: v0.9). The same bullet still carries "1016 tests green".
  - `STATUS.md:7` (edited in this change): "three owner decisions follow (GAP-P12D-145/146/147)", where all three are ruled and fixed in KNOWN_GAPS; and "a $100k demo account … (GAP-P12D-142, the owner's broker step before the cutover)", where the top-up is done (TODO item 2, `c6e56be`).
  - `STATUS.md:3`: "As of 2026-10-02".
  - `TODO.md:3-4`: "STATUS (2026-09-29): SPEC COMPLETE (master v2.24 …)" and "`ACIS_SPEC.md` v2.24 is the build authority".
  - CLAUDE.md status line: "a $100k demo account is the owner's step before the cutover", which is done.
- **Reproduction:** `git show f0d9524:STATUS.md | sed -n 3p;7p;35p`, `git show f0d9524:TODO.md | sed -n 3,4p`, against `git show f0d9524:ACIS_SPEC.md | sed -n 2p` and KNOWN_GAPS GAP-P12D-142/145/146/147.
- **Proposed fix:** refresh those lines in the same pass that triages this report. The CLAUDE.md rule ("a lie in the read path is a bug you fix on sight") applies.

### PR16I-10 — The target path carries §2's "registered" half but not its "validated" half (pre-existing; the brief asked)

- **Severity:** Low · **Likelihood:** Low (no runtime path freezes or retires `trend_d1_v1`; it takes an offline or human provenance action).
- **Where:**
  - Master §2 (`ACIS_SPEC.md:95`): "Instrument has no registered, **validated** rule set → `tradeable=False`".
  - The legacy path enforces the validated half (`core/signals/agon.py:219`, `provenance.entry_allowed`).
  - The target path reads only `is_registered`, at both of its checks: `core/runtime/target_wiring.py:70` (`registered=prov.is_registered`) and `core/runtime/wiring.py:184` (NVMA's targeted `has_params`).
- **Answer to the brief:** skipping `NO_PARAMS_FOR_REGIME` for target entries loses nothing relative to `de96a75`, because both checks read the same predicate. Neither carries "validated", though.
- **Reproduction:** `python probes/p10_validated_half.py`:
  ```
  trend_d1_v1: is_registered=True entry_allowed=False rung=INCUBATION        # after a FAILED re-validation
  target loop's registered(): True | NVMA has_params(): True | AGON would allow an entry: False
  after retire: rung=RETIRED is_registered=True entry_allowed=False
  ```
- **Proposed fix:** give `TargetLoop` `registered=lambda f: prov.is_registered(f) and prov.entry_allowed(f, now)`, checked at the decision AND at the slot. Keep the ledger's "§2's rule-set row" claim only once that holds.

---

## Honest negatives (checked, no defect found)

- **Suite and ledger:** the full suite at `f0d9524` on the server gives `1347 passed, 6 skipped in 226.04s`; `scripts/ledger_check.py` gives `286 entries checked; 0 violation(s)`, exit 0.
- **A16 for GAP-P12D-144's fixes:** every cited R1.6 regression test fails on the `de96a75` source, mostly on its behavioural assertion. Examples: `assert [Decimal('2000')] == [Decimal('1000')]` (cap at the slot); `assert (120 == 500)` (silent truncation); `'target' == 'no_target:fetch_failed'`; the restart re-entry; and `veto` vs `open` for GAP-P12D-147.
- **Guard integrity:**
  - `clear_by_human` is reached only through `CapitalGovernor.resume`'s `resume_gate` (`core/runtime/wiring.py:210`), and the Governor's resume only from `RuntimeControl.resume` (`core/runtime/halt_edge.py:62-63`). That in turn is reached only through `acis_resume`, which is human-token-gated by digest (`monitoring/tools.py:45, 123-126, 137-140`), or `__main__ --resume`, with the token typed at the terminal (`core/runtime/__main__.py:108`).
  - No MCP tunable path touches alpha decay or `confidence_veto` (`config/system_config.yaml:132-136`).
  - `target=True` is passed by `core/governor/target_gate.py:101` only, and `target_orders` is reached only from `TargetLoop.execute`.
  - `CONFIDENCE_VETOES` is a code constant, so no config flag widens the exemption.
- **Signal path unchanged:** `capital_governor.py:352` calls `guards.check` without `target`; with `target=False`, `guards.py:53` and `:65` reduce to the old expressions.
- **The exemption's edges:**
  - `integrity_tradeable` (`regime_types.py:81-90`) refuses every NVMA reason except `LOW_CONFIDENCE` and `NO_PARAMS_FOR_REGIME`, and every gate label. It also refuses a missing or empty `veto_reasons`, and a string-valued `veto_reasons` (its character set is not a subset).
  - Only NVMA constructs `RegimeContext` in production (`core/regime/nvma.py:234`), and it always records the tuple.
  - Adds are refused before any guard (`target_gate.py:72-75`).
  - The target universe gets no legacy signals (R6-3), so there are no pair groups there.
- **The throttle's state machine:**
  - A blank token raises before anything clears (`monitor.py:297-298`). A resume while not armed is a no-op (`alpha_throttle.py:53-54`), and so is a second resume.
  - Arming and the Governor update are synchronous on the same edge (`alpha_throttle.py:33-37`), so there is no resume-between window.
  - The Governor's flag and Risk's agree after every path: arm, recover, restore and human clear each send an explicit `apply_risk_state`.
  - The persisted `alpha_armed` is rewritten False at the next evaluate after a clear. A crash before that restores armed, which is the restrictive direction.
  - The same trades cannot re-arm right after a resume (shipped test, reproduced).
- **R1.6 fixes, other edges:**
  - The 240-day walk terminates: `hi` strictly decreases or ends, and an empty window breaks. `TRUNCATED` (4 days) exceeds every FX closure, and `HOLE` (5 days) exceeds it.
  - The persisted decision record is keyed by the New York decision day, which is DST-stable, and is compared only on the same day.
  - The clock-wait retry re-runs at most every `MAX_SLEEP_S`.
  - In practice mode, the window in which a filled open sits in both `risk.positions()` and `executor.inflight` has no suspension point (`evaluate()` awaits nothing on that branch), so there is no double count there. Elsewhere the double count is restrictive only.
- **Rates:**
  - AUD 18 days old is fresh and USD 11 days old is stale (shipped test).
  - `RateTable`'s and `load_rate_table`'s defaults leave RSIM and the harness on the single 10-day limit.
  - The weekly limit follows the source id, not the currency, so a currency moved to a daily source loses it automatically.
  - A decision loads one table once (`target_loop.py:136`), so a mid-decision refresh cannot mix vintages within it.
  - The historical SARON file on the server (`/opt/acis/data/macro/chf_saron.csv`) holds business-daily observations, so "weekly" can only mean the publication cadence (the external lens owns the cadence question).
- **GAP-P12D-142's deposit claim at `f0d9524`:** `core/execution/ctrader_events.py:120` drops every `EXECUTION_EVENT` whose type is not in `DEALT`, so `DEPOSIT_WITHDRAW` (schema value 10) never reaches the book. The "old engine sizes from the venue NAV" note concerns `4e2d4b2`, outside this audit.
- **A12:**
  - `alpha_throttle.py` is 58 lines, `target_promotion.py` 33, `target_loop.py` 228.
  - `monitor.py` is 332, at its lowered grandfather cap.
  - `scripts/download_macro.py` is 299, under 300 only because `SPX_KNOWN_CLOSES` was folded from 7 lines to 2 in `d7f0875`. That is noted, not filed, because the line is ≤ 120 characters and readable. Its next change crosses the budget.

## What I could not verify

- The real-tick ILLIQUID and slot-veto rate (PR16I-03): no tick set on this server, and the demo still runs the old code.
- Whether cTrader ever silences one symbol's spot stream while others tick (PR16I-06's likelihood).
- The BIS and SNB publication cadences themselves (external lens). PR16I-05 uses the ledger's own BIS example.
- `--resume` interacting with a LIVE venue's restart sync (offline only; the restart path was exercised through `RiskStore` and `restore_on_boot` directly, not a full venue boot).

## Residual risk

- **Alpha decay in practice is only as good as the process lifetime.** PR16I-01 is the sharp case, but the trade history is never persisted. So any restart, armed or not, forgets every baseline, and a strategy that decays across a restart is compared with its own decay. GAP-0050 persisted only the flag. Until GATES R8's shadow-book monitor replaces the throttle (GAP-P12D-61), the throttle is weaker than the spec reads.
- **The slot gate is one shot.** With ILLIQUID kept (PR16I-03) and no retry inside `slot_grace_s` (option b of GAP-P12D-147, not ruled), the demo's forward record may still be thinned by intraday classification noise. Only the demo's `TARGET_ENTRY_ZERO` counts will say by how much.
- **Exposure accounting in flight** (PR16I-04) is inert on the $100k demo and live at $10k. Any future smaller account, or the per-account guardrail profiles, makes it bite.
