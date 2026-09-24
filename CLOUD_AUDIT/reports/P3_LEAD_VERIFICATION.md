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
| D10: an agent can stage `marginal_alpha_window=10` and lift the 0.25 size floor | **PLAUSIBLE** | Ran the repro. Staging is accepted without a token, and a window of 10 yields factor 1.0. Not checked: whether a staged patch takes effect without a human promotion step. If promotion is human-gated, the severity drops to "an allowlist bound is too loose". |
