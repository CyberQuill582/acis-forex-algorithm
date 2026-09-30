# AUDIT BRIEF — Track A steps 3–5: the cTrader adapter, the three-loop runtime, feed reconnect (pinned 2026-09-30)

> **Pinned before launch (constitution A4).** The owner's go, in chat on 2026-09-30, answering the
> session's standalone ask: "Launch both now (Recommended)". This is the constitution's pair (A3),
> one agent per lens, on Opus 5 in fresh context.
>
> **What is under audit:** the code at commit **`86ea8d3`** on `main` (the commit that pins this brief
> adds only documents). Read it with `git show 86ea8d3:<path>`; the lead may keep working in the tree.
> - **Step 3, the cTrader adapter** (built `d4ade2a`, ACIS-13 v1.1): `core/data/ctrader/` (schema, wire,
>   transport, link, session, meter, tokens, feed), `core/execution/ctrader_*.py` (symbols, orders, events,
>   sync, store, account, face, attach), the watchdog's cTrader plugin `scripts/watchdog_plugins/ctrader_flatten.py` (+ `scripts/acis_watchdog.py`, `config/watchdog.yaml`),
>   `scripts/ctrader_probe.py`, `config/venue.py`, the `pepperstone_demo` rulebook in
>   `config/platform_rules.yaml`.
> - **Step 4, the three-loop runtime** (`6863267`, `2000bbe`): `core/runtime/` (policy, executor, engine,
>   halt_edge, paper, portfolio, venue_link, wiring, boundaries, `__main__`), `config/runtime_schema.py`;
>   the orchestrator's stop threading (`core/execution/orchestrator.py`, GAP-P12D-130); the Governor's
>   minimum size (`core/governor/capital_governor.py`, ACIS-05 v1.6); `scripts/evolve_demo_params.py`;
>   `deploy/systemd/acis-engine.service`, `docker-compose.yml`.
> - **Step 5, feed reconnect** (`86ea8d3`): `core/execution/ctrader_reconnect.py`, the `stop()` fix in
>   `core/data/ctrader/session.py`.
> - **The tests:** `tests/ctrader_fixtures.py` (the fake venue), `tests/integration/test_ctrader_*.py`,
>   `tests/integration/test_runtime*.py`, `tests/integration/test_adapter_conformance.py`,
>   `tests/unit/test_runtime_*.py`, `tests/unit/test_governor.py` (the v1.6 tests),
>   `tests/unit/test_import_contract.py`, `tests/unit/test_config_schemas.py` (the runtime block), `tests/unit/test_ctrader_watchdog_plugin.py`.
>
> **The authority.**
> - The spec: master `ACIS_SPEC.md` v2.25 — §1/§10 (the runtime, `[DIR:core/runtime]`), §7.5 (the attach
>   protocol and the `practice` mode), §2 (the conflict table), §5 ("validated" per mode: paper and practice
>   at minimum size), §8/§8.6 (Risk, the equity breaker, the watchdog), §12 (MCP asymmetry: halts cheap,
>   resumes human-only); `specs/ACIS-13-VENUE_ADAPTERS.md` v1.1 (all of it, esp. §6.5 budget, §6.6 backoff,
>   §7.1 A1–A11, §7.3 submit, §7.8 sync, §8.1 state machine); ACIS-05 v1.6, ACIS-06 v1.4, ACIS-07, ACIS-08.
> - The ledger: `KNOWN_GAPS.md` GAP-0075, GAP-0099, GAP-0091b, GAP-0020 (all marked fixed today),
>   GAP-P12D-126, 128, 129, 130, 131, 69, 70, 57, 42.
>
> **The lead's claims — re-verify them; they are not settled:**
> - the full suite at `86ea8d3` gives 1168 passed, 6 skipped on the server;
> - on the phase-7 market that made 67 identical orders, the runtime sends ONE open, protected by its stop;
> - paper mode can never send an order to the venue; practice reaches only a practice-eligible demo account;
> - every fill (solicited, venue-made, recovered at restart, missed during a disconnect) reaches Risk exactly once;
> - the runtime's request spend stays inside ACIS-13 §6.5's feasibility budget;
> - no module under audit is over 300 lines; `python scripts/ledger_check.py` is green.
>
> **Declared choices the lead made — attack them:**
> - the as-built position policy (the backtest book's) instead of the ratified Carver band (R1.6, GAP-P12D-118);
> - max hold = the harness's 48 h, as a declared config value (`runtime.max_hold_s`), pinned equal by test;
> - paper and practice size every open at exactly one venue minimum lot (ACIS-05 v1.6 step 3b), applied
>   BEFORE the hard limits; a zero is never raised;
> - practice equity is the last account poll (every `equity_poll_s`, 300 s): a declared lag (GAP-P12D-131 a);
> - the heartbeat is written by Risk's timer, not per tick; a stalled loop is a task that ends or raises;
> - a periodic reconcile drift is adopted and halts everything (the restart rule, reused);
> - a flatten freezes EVERY orchestrator; only the human resume lifts the freeze;
> - practice needs a human at a terminal (the token typed, never argv/env) and a restart comes back in paper;
> - a link lost while an order is in flight halts entries (GAP-P12D-131 h);
> - the demo trades QIEA sets evolved on 2022–2023 only; the run staged ONE champion (GAP-P12D-129).

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit, or run git commands that write. Read the audited state with `git show 86ea8d3:<path>`; never trust the working tree to equal it.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite or any probe that does real work locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of the audited commit: `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/14bd46d6-f525-4929-8270-74bd2077dacc/scratchpad/remote_audit_ta.sh" <internal|external> "<command>"`.
  - Put probe scripts in `…/scratchpad/audit_ta/<internal|external>/probes/` (they ship on each call) and run them as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - Reading files and quick `grep`s locally are fine.
- **Refutation (A6).** Every finding is reproduced by a script on the server and cites `file:line` at `86ea8d3` (internal lens), or quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps against the spec, hollow or weakened tests (A16), A12 size and legibility (a module over 300 lines; a missing one-screen mental model in an invariant-bearing module), A13 hygiene (a read-path claim the code or the ledger contradicts; spent scaffolding), and ledger closure (`python scripts/ledger_check.py` green, plus a spot-check that each `Residual:` just written honestly owns what is unbuilt). Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_TRACK_A_INTERNAL_2026-09-30.md`; EXTERNAL writes `archive/AUDIT_TRACK_A_EXTERNAL_2026-09-30.md`. That file is your ONLY repo write. Its shape: an executive summary; findings (ID, Severity/Likelihood, reproduction, proposed fix); honest negatives; what you could not verify; residual risk. The lead triages it into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **Money reach.** Can any path send an order to the venue in paper mode, or in practice to an account that is not a demo with `account_class: practice`? A mode change mid-run with positions open; a restart; the ModeController's gates; `route_to`; the executor; the watchdog plugin.
2. **Protection.** Does every open carry its stop to the venue (orchestrator threading, relative-stop arithmetic, stop verification and amend, the unprotected close)? Can a close, a flatten or a reversal ever open or cross through flat? Can a stop be voided (GAP-P12D-42)?
3. **Exactly-once.** Solicited fills, venue fills (a stop firing), deals missed while down, an open in flight at a crash or a disconnect: each reaches Risk once? The deal cursor and the router's dedup across a restart AND across a reconnect.
4. **Budget.** Any loop that can spend past `daily_request_budget` or starve the close reserve: reconnect attempts, account polls while flat, reconciles, restarts under systemd, flatten pacing, evaluate-on-fill. Does the runtime's real cadence fit §6.5's feasibility formula?
5. **Engine parity.** Is the runtime's position policy the backtest book's (`tests/backtest/book.py`), so the demo is the engine the harness grades? Max hold measured from which clock; target at which price; the reverse price; pairs; exits blocked by busy instruments.
6. **Risk wiring and the guard law.** Evaluate cadence, on each fill and venue fill; the equity breaker with a stale practice account; halt persistence and restore at boot; the freeze; human-only resume (can any agent path lift a halt or the freeze?); a stalled loop's flatten-and-halt actually executing its closes; the heartbeat semantics the watchdog reads.
7. **Concurrency.** The busy set; serial execution; blocking sqlite writes on the event loop; the fast loop starving other tasks; cancellation and shutdown ordering; the reconnect racing an in-flight order; `CTraderSession.stop()`'s new gather.
8. **Clocks.** The A8 first-live-tick check; tick time vs wall time (account age, `opened_at` from fill time vs exits on tick time); DST and the session-boundary sweep (`BoundaryClock`, now shared with the harness).
9. **Sizing.** ACIS-05 v1.6: can the minimum lot bypass a cap, a taper or a halt; interplay with pairs; is "at most one venue minimum lot per instrument" (master §5) actually held?
10. **Secrets and the untrusted-input law.** Tokens and secrets never logged or in argv/env where they persist; venue text never obeyed as a command (C-VEN-15).
11. **The demo evolution.** `scripts/evolve_demo_params.py`: no bar at or after 2024-01-01 read; the record traceable; staging only.

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces 1, 2, 3, 4, 6 and 7.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch only):** the design and the implementation against the outside world.
  - Spotware's cTrader Open API documentation and forum (help.ctrader.com/open-api, the Spotware forum): heartbeats and disconnects, `ProtoErrorRes`/maintenance fields, `relativeStopLoss` semantics and precision, market IOC behaviour, `clientOrderId`, `ProtoOAReconcileReq`, deal-list paging, the documented rate limits, what happens to open positions and stops on a disconnect, hedging-account semantics.
  - Backoff: "Exponential Backoff And Jitter" (Marc Brooker, AWS Architecture Blog, 2015) — is this full jitter, faithfully?
  - Pepperstone's cTrader demo: minimum lot and step on EURUSD/USDJPY, hedging vs netting, stop-out level, demo expiry, swap on demo.
  - Backtest–live divergence in systematic trading (position management, exits, fills) and dead-man's-switch / watchdog practice for unattended trading engines.
  - Does anything the spec or code assumes about the venue contradict the venue's published behaviour? A spec that is wrong about the world is a finding.
