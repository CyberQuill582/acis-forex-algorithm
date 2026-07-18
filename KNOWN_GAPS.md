# KNOWN_GAPS.md — living ledger (ACIS)

Format — one entry per gap, newest first. Never delete entries; close them with Status.

```
## GAP-NNNN: <one-line title>
- Severity: critical | high | medium | low
- Likelihood: high | medium | low
- Status: open | mitigated | accepted-risk | closed
- Area: [DIR:...] or spec §
- Description: what can go wrong and how we know
- Justification: why this status (esp. for accepted-risk)
- Linked: commits / test names / halt-postmortems
```


> **Archive note (2026-07-17, owner-ratified surface-area reduction):** entries with
> `Status: closed` and historical audit-run banners are moved VERBATIM (never edited,
> never deleted) to `KNOWN_GAPS_CLOSED.md` when closed. This file is the LIVE ledger:
> open / mitigated / accepted-risk only. Ledger discipline is unchanged — new findings
> land here first; closure moves the entry to the archive with its closing note.

## GAP-0092: Risk Monitor books realised PnL in the instrument's QUOTE currency and treats it as account currency — exact only for USD-quoted pairs
- Severity: medium
- Likelihood: high
- Status: open (declared limitation, owned by phase 11 — the OANDA cost-calibration/adapter pass, master §13/v2.9)
- Area: [DIR:core/risk] monitor.py `_apply_fill`/`_book_trade`/`_unrealised`, ACIS-07 §5
- Description: `RiskMonitor` computes realised/unrealised PnL as `(price_diff) × units × direction` in the instrument's QUOTE currency and treats that number as account (USD) currency. This is exact for USD-quoted instruments (EUR_USD, XAU_USD, GBP_USD…) but wrong for non-USD-quoted pairs (USD_JPY books JPY, EUR_GBP books GBP) — the daily_pnl/open-drawdown/per-instrument-drawdown figures for those instruments are off by the quote→USD rate. Broker `equity` remains authoritative for the equity breaker and the §9.5 drawdown series (those read broker truth, unaffected), so no guardrail is weakened; the affected quantities are the ENGINE's own internal PnL view (snapshot fields + per-instrument dd taper input). Consistent with the phase-6 Governor simplification (per-currency deltas as "USD-notional terms"). Reproduced by construction: USD_JPY 1000 units 110.00→110.50 books pnl=500 (JPY) surfaced as $500.
- Justification: honest scoping — a correct multi-quote FX→USD conversion layer needs live cross rates, which arrive with the phase-11 loader + OANDA calibration and the phase-12 adapters (master §13, v2.9). Recorded so per-instrument drawdown/daily-PnL for non-USD-quoted instruments is not trusted as account-ccy until then; the phase-9 tests use USD-quoted EUR_USD where the identity holds. The taper/HALT arithmetic is exact; only the currency scale of the internal PnL view is approximate.
- Linked: core/risk/monitor.py `_apply_fill`/`_book_trade`/`_unrealised`/`_per_instrument_drawdown`, ACIS-07 §5, master §13/v2.9

## GAP-0091b: VaR and cluster/per-instrument metrics need marks fed each evaluate; nothing in production wires the mark stream yet (phase-10 runtime)
- Severity: low
- Likelihood: high
- Status: open (owned by phase 10 — the production three-loop runtime that owns Risk's evaluate cadence and its mark/account inputs)
- Area: [DIR:core/risk] monitor.py `evaluate` (marks arg), `_var_pct`/`_max_cluster_pct`, ACIS-07 §7
- Description: `RiskMonitor.evaluate(account, now, marks=…)` computes 1% VaR (delta-normal undiversified, σ from a rolling mark history) and cluster/per-instrument exposure from the `marks` the caller passes. The phase-9 build wires and tests these through direct evaluate calls; the PRODUCTION loop that feeds marks + the broker account snapshot on the Risk cadence is the phase-10 three-loop runtime (lean-build: §15 phase 9 is the Risk build + tests, not the runtime). Until then VaR reads 0 with no mark history — correct-but-inert, never wrong. No decision path depends on VaR in-loop today.
- Justification: consistent with the paper_loop/phase-7 precedent (the composed runtime lands with the phases that need it). Recorded so phase 10 treats "feed Risk its marks + account snapshot each evaluate" as a named wiring requirement, and so a reviewer does not read VaR=0 as a bug.
- Linked: core/risk/monitor.py `evaluate`/`observe_mark`/`_var_pct`, tests/unit/test_risk_monitor.py, ACIS-07 §7

## GAP-0078: `skip_attribution()`'s three per-layer buckets OVERLAP — one physical vetoed tick is counted in BOTH `nvma[reason]` and `agon["vetoed_regime"]`, so the layers are not a partition and any cross-layer sum overcounts
- Severity: low
- Likelihood: medium
- Status: mitigated (2026-07-17 — the non-partition semantics are now DECLARED in `skip_attribution()`'s docstring: three per-layer VIEWS, never summed across layers; an NVMA veto reason EXPLAINS AGON's `vetoed_regime`. The phase-10 `acis://status` implementation must consume per-layer, per this declared contract — carried as a phase-10 build note)
- Area: [DIR:tests/integration] paper_loop.py `skip_attribution` (158-160); [DIR:core/signals] agon.py generate() `vetoed_regime` (192-196); [DIR:core/regime] nvma.py `veto_counters` (361-364)
- Description: A single regime-vetoed tick increments NVMA's `veto_counters[<specific reason>]` (e.g. SPREAD_VETO, NO_PARAMS_FOR_REGIME) AND AGON's `skips["vetoed_regime"]` (generate() sees `not regime.tradeable` and counts it). `skip_attribution()` returns `{"nvma": …, "agon": …, "governor": …}` — coherent as PER-LAYER views, but the same physical skip appears in two buckets, so summing the three dicts to get "total skips" double-counts every veto. The §10 C15 framing ("every skip attributed to THE gate that killed it") implies a partition the structure does not provide — the "gate that killed it" is genuinely NVMA's veto; AGON's `vetoed_regime` is a redundant re-count of the same event one layer down. A phase-10 `acis://status` consumer that aggregates naively will mis-report take-rate. (Symmetric note: the warm-up count `nvma[REGIME_WARMING]==200` in test_per_gate_skip_attribution is asserted `== skips["nvma"]` against the log — but both counter and VETO_APPLIED log are incremented in the SAME loop in nvma.classify, so that equality is structurally tautological and cannot fail even if the mechanism drifted.)
- Justification: not wrong as designed (per-layer buckets are legitimate), but the completeness/partition claim is stronger than the data supports; document that the three buckets are non-disjoint views of the same funnel, or attribute each physical skip to exactly one owning layer.
- Linked: tests/integration/paper_loop.py:157-160, core/signals/agon.py:192-196, core/regime/nvma.py:361-364

## GAP-0075: The phase-7 composed loop opens a NEW position on EVERY tradeable tick (no position/dedup/holding management) — one TSMOM long spawns 67–71 identical orders; `take_rate()["orders_placed"]` conflates sizing decisions with positions and no test guards the spam
- Severity: medium
- Likelihood: medium
- Status: mitigated (2026-07-17 pin; 2026-07-18 phase-9 GRADUATION of the mechanism — the missing position layer now EXISTS: `RiskMonitor` reconstructs open positions from FillReports (`positions()`), and `tests/integration/test_risk_pipeline.py::test_position_accounting_gates_reentry` proves a position-aware re-entry gate turns one repeated signal into ONE held position, not one-per-tick. What remains for phase 10 is only WIRING this gate into the production open-decision loop — the phase-7 `paper_loop.on_state` is unchanged, so its `orders_placed == 67` pin still stands as the phase-7 artifact and is deliberately NOT edited here. Downgraded concern: the accounting the gap asked for is built and tested; the production loop consumes it at phase 10)
- Description: `on_state` calls `agon.generate()` every tick and, for each surviving signal, appends the sized order to `book.orders` unconditionally. TSMOM is unconditional in every tradeable regime and re-fires the SAME long every tick once the daily seed is present, so the composed loop accumulates one identical EUR_USD TSMOM long PER tradeable tick — reproduced: 67 orders (flat e2e fixture), 71 (row-6 fixture), all `ps-MEAN_REVERTING` TSMOM longs. The e2e's `assert len(loop.book.orders) >= 1` and the row tests' count-agnostic assertions mask this entirely; `take_rate()["orders_placed"]` (surfaced as a §10 C15 metric that phase-10 `acis://status` will expose) is thereby not a count of POSITIONS but of per-tick sizing decisions, inflated ~1-per-tick. The real three-loop runtime + Execution Orchestrator (phase 8) supplies the missing position/holding/dedup layer, so this is a harness-scope artifact rather than a decision-path bug — but the phase-7 tests present orders_placed and "orders came out the bottom with the full audit chain" (e2e) without acknowledging that "71 duplicate positions" is what actually came out, and no assertion pins the expected count or flags the duplication.
- Justification: honesty/coverage gap in the phase advertised as the full paper-trading integration; either the harness should model position-existence (so a re-fire is a no-op/adjustment, matching the real engine) or the tests/ledger should state that orders_placed here counts sizing decisions, not positions, and that dedup is deferred to phase 8.
- Linked: scratchpad probe (row6 orders=71 all TSMOM; e2e orders=67), tests/integration/paper_loop.py:104-128

## GAP-0067: MarketStateStore commits per row (~10–30 writes/s fsync-bound on the dev box) — at real feed rates the bounded queue overflows and drop-oldest sheds most ticks from the audit/replay store
- Severity: low
- Likelihood: medium
- Status: open (owned: phase 11 backtest-loader work and the pre-phase-12 VPS gate — TimescaleDB is already the declared prod store, §16)
- Area: [DIR:core/data] store.py `MarketStateStore.write` (per-row `commit()`), AsyncBoundedWriter sizing (`data.queue_max: 1000`)
- Description: observed while building the phase-7 composed-loop tests: draining 280 MarketStates through the writer took ~30s (~9 rows/s; each `write()` issues its own `commit()`, i.e. one fsync per tick on Windows). A live feed at 10–100 ticks/s would fill the 1000-slot queue within seconds-to-minutes and the declared drop-oldest policy would then shed the majority of ticks permanently — logged as DATA_BACKPRESSURE (by design, the fast loop is protected), but the SQLite copy is the audit/replay record, and "audit copy mostly holes" is not what §3/§11 intend for paper mode. Not a correctness bug in any decision path (decisions never read the store in-loop).
- Justification: dev-SQLite is explicitly the dev-only store (§16: TimescaleDB in production) and no phase up to 7 runs a sustained real-rate feed; recorded now so the phase-11 loader and the pre-phase-12 deployment gate treat write throughput (batched transactions or the prod store) as a named requirement, not a surprise. The phase-7 tests sidestep it honestly: only the e2e persistence test drains the writer.
- Linked: tests/integration/paper_loop.py `run(drain=)`, tests/integration/test_paper_trading_pipeline.py, core/data/store.py:48-69

## GAP-0048: ACIS-11 "structurally impossible" claims overstate two provenance guards — the human token is a presence check (any truthy string), and attempt-registry append-only is API-omission not schema-enforced
- Severity: medium
- Likelihood: low
- Status: mitigated (2026-07-16 triage — (a) attempt-registry append-only is now SCHEMA-ENFORCED: BEFORE DELETE/UPDATE triggers abort in the store itself, regression `test_gap0048_attempt_registry_append_only_in_store` proves raw SQL dies; (b) the human token remains a presence check BY DECLARED SCOPE: real token authentication is the ACIS-08 control-plane's job (phase 10, human-token asymmetry) — until then the parameter marks the protocol seam, and ACIS-11 §7's claim is scoped honestly rather than overstated. Residual: phase 10 must wire genuine auth — carried on the phase-10 TODO item)
- Area: [DIR:core/signals] provenance.py `promote_one_rung`/`record_attempt`, ACIS-11 §11/§12/C-PRV-3/C-PRV-4, SPEC §5.6/§9 guard-integrity law
- Description: Two overclaims where the spec's teeth are weaker than stated. (1) **Human token is unauthenticated.** `promote_one_rung` gates PAPER→LIVE with `if to is Rung.LIVE and not human_token` — ANY truthy string passes. Reproduced (repro_audit.py H): `promote_one_rung("h_v1","e",T0, human_token="x")` transitions to LIVE. ACIS-11 §11 says "human sign-off is a token on `promote_one_rung`" and C-PRV-3 promises "no agent self-promotion," but the token is a *presence* check, not a credential — any code path that fabricates a string self-promotes to LIVE. Per the guard-integrity law (§9: a guard the guarded process can reach is not a guard), C-PRV-3 holds only if no code ever passes a string, which is not structurally enforced here (real enforcement is deferred to the phase-10 MCP human-token layer + §14 minimums, but ACIS-11's own C-PRV-3 contract reads as absolute). (2) **Attempt-registry "structurally impossible" to delete overclaims.** §12 error taxonomy: "attempt deletion attempted | no such API — structurally impossible"; §10 DDL comment "append-only: no UPDATE/DELETE path exists." True of the *method surface* only — `store._db` is a live, reachable `sqlite3.Connection`; `store._db.execute("DELETE FROM attempts")` works (no trigger, no append-only schema constraint). The multiple-testing denominator (§5.6 anti-self-deception) is therefore protected by API-omission, not by structure — contrast the genuinely-structural guards CLAUDE.md cites (schema-level rejection). The test only asserts `not hasattr(store,"delete_attempt")`, which does not establish "structurally impossible."
- Justification: either (a) validate the human token against a real credential/one-time-signature (or state honestly in §11/C-PRV-3 that phase-5 scaffolding accepts any non-empty token and the authenticated gate lives at the MCP layer), and (b) enforce append-only at the schema (a `BEFORE DELETE`/`BEFORE UPDATE` trigger that RAISEs) or soften §12's "structurally impossible" to "no API-level delete path." Guardrail-adjacent (promotion gate + anti-self-deception denominator) — also summarised in SPEC_AUDIT.md. Finder-only.
- Linked: scratchpad repro_audit.py (H), core/signals/provenance.py `promote_one_rung`/`record_attempt`/`_db`, tests/unit/test_provenance.py `test_promotion_path_and_human_token_gate`/`test_attempt_registry_append_only_and_monotone`, ACIS-11 §11/§12/C-PRV-3/C-PRV-4, SPEC §5.6/§9

## GAP-0035: v1 fitness harness does not exercise the momentum/breakout/mean-reversion genes
- Severity: low
- Likelihood: high
- Status: open (declared limitation, owned by phase 5 — ACIS-03 §6.1 records it)
- Area: [DIR:core/optimizer] fitness.py `simulate_trades`, ACIS-03 §6.1, SPEC §5/§5.5
- Description: The phase-4 fitness mini-backtest is the declared canonical dual-EMA core (EMA cross + RSI filter + ATR SL/TP + max-holding). It selects on {ema_fast, ema_slow, rsi_*, atr_multiplier_*, max_holding_periods}; the genes `momentum_lookback`, `breakout_atr_threshold`, and `mean_rev_zscore_entry` are decoded, range-validated, and carried on every ParamSet but contribute nothing to fitness — evolution assigns them effectively random (seed-reproducible) values. AGON's Momentum-Scalp/Breakout/Mean-Reversion modules (phase 5) will consume those values without their having been selected-for.
- Justification: honest scoping, not an oversight — module-specific evaluation belongs with the phase-5 AGON module formulas (per-module fitness or a composite harness is an ACIS-04/ACIS-03 §6.1 extension). Until then, phase-5 module tests must not assume evolved quality in those three genes.
- Linked: ACIS-03 §6.1 (declared harness), core/optimizer/fitness.py, specs/ACIS-04 (phase 5)

## GAP-0023: fx_default calendar tags 21:00–00:00 UTC "closed" daily — spurious dead window vs 24/5 forex
- Severity: low
- Likelihood: high
- Status: accepted-risk (2026-07-15, author decision — deliberate conservatism, not an oversight: the 21:00–00:00 UTC band contains the 22:00 rollover liquidity vacuum (scenario_book: rollover_liquidity_vacuum) and Sydney-only depth; staying structurally flat there costs the thinnest hours of the day. Revisit if a strategy demonstrably needs the Asian open: add a wrapping-session capability to FxCalendar + a sydney window, owner-committed)
- Area: [DIR:config] instruments.yaml fx_default / [DIR:core/data] asset_classes.py, SPEC §3/§4
- Description: The fx_default sessions are tokyo 00:00–09:00, london 07:00–16:00, new_york 12:00–21:00. Between 21:00 and 00:00 UTC no window is active, so `session_at` returns `"closed"` every weekday — and `session == "closed"` ⇒ downstream treats the instrument as untradeable (ACIS-01 §4). Reproduced: `session_at(2026-07-14 21:30) == "closed"`. But forex trades 24/5 through this window (the Sydney/Wellington session, which is simply not modelled in the enum). The result is a ~3-hour daily band in which a live forex account is spuriously untradeable, contradicting the 24/5 rollover model (§3.7) and §0's "a system that makes no money has failed." Also a minor fencepost: 21:00–22:00 Friday is already "closed" via sessions though `weekend_close_utc` is 22:00. Additionally, `FxCalendar._times` structurally forbids any session whose start ≥ end, so a genuinely midnight-wrapping session (e.g. Sydney 22:00→06:00) cannot even be declared to fill the gap.
- Justification: config/enum completeness decision — either add a sydney session (and allow midnight-wrapping windows in the FxCalendar schema) or explicitly accept the 21:00–00:00 dead window with rationale. Low severity in paper phase 1 (no live account), but it will silently suppress a third of the Asian session live. Raised for human/config decision.
- Linked: scratchpad repro (session source), config/instruments.yaml fx_default, core/data/asset_classes.py `_fx_session`, config/schemas.py `FxCalendar._times`

## GAP-0021: Import-contract ALLOWED map encodes skip-level edges §2 forbids, asymmetrically, without a spec citation
- Severity: low
- Likelihood: low
- Status: mitigated (2026-07-15 — ruling documented in the contract test's docstring with spec citations: §2's one-layer-at-a-time governs DATA FLOW; producer-type IMPORTS follow the spec's own explicit cross-references (§5.5 Arena reads RegimeContext + ActiveParamSet; §6 formula consumes regime factors; §5 QIEA reads regime-labelled history). Every ALLOWED edge now cites its section; widening requires a citation added there. Whether signals→data joins the map is decided at phase 5 when ACIS-04 fixes how indicators receive the price series)
- Area: [DIR:tests/unit] test_import_contract.py `ALLOWED`, SPEC §2 vs §5.5/§6
- Description: §2 states the data flow is "downward only, one layer at a time" and "No layer bypasses the layer directly below it." The `ALLOWED` map permits skip-level (bypass) imports the literal text forbids: `optimizer: {regime, data}` (optimizer→data skips regime) and `governor: {signals, regime}` (governor→regime skips two layers). These may be legitimate — §6's sizing formula genuinely needs `regime_stability`/`regime_confidence` (RegimeContext fields), and QIEA reads historical data — but that is a *reinterpretation* of §2 (adjacent-only) into "any lower producer," made by fiat in a test, with no spec citation. The map is also asymmetric: `signals: {optimizer, regime}` omits `data`, yet §5.5's Alpha Arena indicators (EMA/RSI/BB) require the price series (MarketState) — so the next phase will either add `data` to signals (widening the guard) or thread prices through Signal, and the contract does not pin which. An executable guard that is meant to be the layer law's sole enforcer should be derivable from the spec, not encode undocumented interpretation choices that can drift.
- Justification: needs a one-line spec ruling (deep-spec/human): does §2 mean strict-adjacency (thread all needed fields downward through the boundary dataclasses) or any-lower-producer (the current map)? Then make `ALLOWED` cite it. Low severity now (no violation), but it determines whether every future layer's producer set is a guard or a rubber stamp.
- Linked: tests/unit/test_import_contract.py `ALLOWED`, ACIS_SPEC.md §2/§5.5/§6

## GAP-0020: Feed reconnect/backoff protocol untested until a real feed face exists
- Severity: low
- Likelihood: high
- Status: open (deferred by design — phase 12)
- Area: [DIR:core/data], ACIS-01 §7 step 8 / §14, SPEC §7.5
- Description: ACIS-01 requires backoff-reconnect + FEED_RECONNECT re-baseline via snapshot() and a reconnect-mid-stream integration test. Phase 1 shipped the mock feed only (per ACIS-01 v1.1 scoping); the mock cannot disconnect, so the reconnect path has no implementation or test yet. Risk: phase 12 adapter work must not treat reconnect as done because phase 1 is green.
- Justification: consistent with the lean-build law (SPEC §18) — reconnect behaviour lives in real feed faces, which arrive with the phase-12 adapters; the §7.5 conformance suite already names reconnect-mid-position as a mandatory case, so it cannot be silently skipped.
- Linked: ACIS-01 v1.1 §1, SPEC §7.5 conformance suite, TODO.md phase 12

## GAP-0008: Fitness-window minimum + cross-regime OOS for QIEA params
- Severity: medium
- Likelihood: medium
- Status: mitigated (2026-07-15, phase 4 — optimizer-side half CLOSED in ACIS-03 v1.1 §6.3: `fitness_min_bars` window minimum (fewer labelled bars ⇒ no evolution, regime stays untradeable), `fitness_min_trades` thin-sample gate, and a chronological 20% holdout on which the champion must independently pass the C9 gate or it is never staged (`EVOLUTION_REJECTED_OOS`; indicators warm up on train bars, only tail-entered trades count — no lookahead). Cross-regime out-of-sample validation before live remains OPEN with ACIS-09 (phase 11 walk-forward), as this entry always assigned it)
- Area: [DIR:core/optimizer], SPEC §5/§5.6, audit F23
- Description: ~11 genes evolved over a 500-bar window is a thin fit; QIEA itself OOS-validates only at the final ACIS-09 backtest, so a self-referential estimator can look good in-window and fail forward. Research favours <5 params, ≥20% held-out OOS, walk-forward across regimes, robustness plateaus (§5.6 mitigates partially).
- Justification: touches fitness semantics. ACIS-03 should set a fitness-window minimum (or held-out split) and require cross-regime out-of-sample validation of a promoted param set before live — not only the final backtest gate.
- Linked: SPEC_AUDIT.md F23, specs/ACIS-03-QIEA_OPTIMIZER.md

## GAP-0004: Slippage auto-throttle — alert-only vs automatic size cut
- Severity: medium
- Likelihood: medium
- Status: accepted-risk (interim: alert-only)
- Area: [DIR:core/execution]/[DIR:core/risk], SPEC §7–§8, audit F10
- Description: the v1.0 architecture brief auto-cuts an instrument's allocation (×0.10) on slippage breach; the current spec only emits `slippage_slope_alert` at 8 bps. An automatic size cut is a sizing/guardrail action.
- Justification: guardrail/sizing semantics are human-owned (CLAUDE.md). Interim = keep the alert; an optional per-instrument throttle is config-gated OFF pending a human-ratified value in `guardrail_limits.yaml`. Dark-pool routing from the brief is dropped (not meaningful in retail forex).
- Linked: SPEC_AUDIT.md F10, specs/ACIS-06 C-EXE-3, specs/ACIS-07 C-RSK-6

## GAP-0002: QIEA pending-param promotion can stall indefinitely
- Severity: medium
- Likelihood: medium
- Status: mitigated
- Area: [DIR:core/optimizer], SPEC §5, audit C2/F8
- Description: in 24/5 forex a position can straddle every session boundary, so `open_positions == 0` may never hold at a boundary and staged params never promote — silently going stale.
- Justification: mitigated by making the stall *observable* (`boundaries_skipped`, `PARAM_PROMOTION_STALLED`, surfaced on `acis://params/pending` after 3 skipped boundaries) without weakening the never-promote-mid-session safety rule. Whether a prolonged stall should force a flat-and-promote window is an OPEN human/guardrail decision — an agent must not force-promote.
- Linked: SPEC_AUDIT.md C2/F8, specs/ACIS-03-QIEA_OPTIMIZER.md §7

## GAP-0001: Backtest fidelity vs live microstructure
- Severity: high
- Likelihood: medium
- Status: accepted-risk
- Area: [DIR:tests/backtest], SPEC §13–14
- Description: tick-data backtests cannot fully reproduce live spread dynamics, slippage, and queue position; §14 targets met in backtest do not guarantee live performance.
- Justification: mitigated by mandatory paper-trading phase (SPEC §15 phases 6–10), OANDA practice account before live, and slippage-slope alerting in the Risk Monitor. Residual risk accepted and monitored.
- Linked: —
