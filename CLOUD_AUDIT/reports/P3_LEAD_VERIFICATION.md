# P3 — lead verification log (A6: a finding binds only after it survives refutation)

All checks run by the lead against BASE `7695ed04`, in `/tmp/review-acis`.

## Seeds from the mission

| Seed | Verdict | How checked |
|---|---|---|
| `core/optimizer/fitness.py:115-125` fills a gapped stop at the stop price | **CONFIRMED** | Read lines 115-125. `exit_mid = sl` whenever `bar.low <= sl` (or `bar.high >= sl` for a short). `bar.open` is never consulted, so a bar that opens beyond the stop still exits at the stop. |

## C5 MONEY-PATH (commit 1f21e57)

| Finding | Verdict | How checked |
|---|---|---|
| D-P1: `SizedOrder.stop_loss` is never threaded to `face.submit_order`, so no server-side stop | **CONFIRMED** | Read `core/execution/orchestrator.py:211-215`: the call has no stop argument. Ran `repro_money_path.py` P1: `resting_stops={}`, `position.stop_loss=None`. |
| D-P2: a lost ack leads to a resubmit, 2,000 units open, and the engine seeing 0 | **CONFIRMED (conditional)** | Ran P2 and it reproduces. The code reconciles only by *logging* broker positions (`orchestrator.py:216-221`), then resubmits. The docstring's claim "idempotent fragment_ids make the retry double-fill-safe" holds only if the venue deduplicates. That is unverified for cTrader/FTMO, so the harm is conditional on the venue; the missing reconcile is not. |
| D-P5: HALTs live in memory only; `record_halt` and `load_restrictive_state` have no production caller | **CONFIRMED** | `capital_governor.py:73` is an in-memory dict. Grep: `core/risk/store.py:57,76` are defined but never called outside tests. Ran P5: `{'all':'var_cap'}` becomes `{}`. |
| D10: an agent can stage `marginal_alpha_window=10` and lift the 0.25 size floor | **CONFIRMED [owner decision]** | Ran the repro. Staging is accepted without a token, and a window of 10 yields factor 1.0. ACIS_SPEC.md:286 says staged tunables follow "a staged-promotion path identical to QIEA params", which promotes at a session boundary with no human step (SPEC C2, line 177). The docstring at `monitoring/tools.py:175-183` promises "no risk-raising value on any path", and this patch raises risk. The allowlist bound at `config/system_config.yaml:131` is the defect. |

## C4 PROVEN PARTS (commit f689b60)

| Finding | Verdict | How checked |
|---|---|---|
| The Deflated Sharpe counts only the surviving champions (≤72 per fold), while QIEA runs 600 evaluations per regime and instrument | **CONFIRMED (structural)** | `tests/backtest/harness.py:216-218` builds `trials` from `trial_sharpes` (candidate champions) only. `config/system_config.yaml:67-68` sets population 20 × generations 30. **Caveat:** the local VALIDATOR says the as-built gate passes nothing at all, so the undercount does not bite today. It becomes binding the moment the gate is repaired. The effective number of independent trials, which is below 43,200, is not measured. |
| cTrader rejects an absolute `stopLoss` on MARKET orders, so `venue.py`'s "atomic with the fill" contract and the exact-price conformance assert do not fit cTrader | **CONFIRMED** | WebFetched help.ctrader.com/open-api/messages/ (2026-09-24). Verbatim: "The absolute Stop Loss price … Not supported for MARKET orders." `core/execution/venue.py:155-161` requires the stop to be placed atomically with the fill. |
| The graded backtest runs a test-side loop; the Governor sizes by notional, with no stop distance | **CONFIRMED** | `tests/backtest/oos_runner.py:46` imports `build_paper_loop` from `tests.integration.paper_loop`. `core/governor/capital_governor.py:283-284`: `raw_usd` is the product of seven factors, none of which is the stop distance. `core/governor/factors.py:46-52`: `vol_norm` returns 1.0 at or below target, so it only ever scales down. |
