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

<!-- ============================================================================
PHASE-12 SPEC DUAL AUDIT — TRIAGE IN PROGRESS (2026-07-21). Two parallel Opus 4.8
adversarial audits of the SPEC ITSELF (master v2.12 + locked specs/) per the
CLAUDE.md constitution-adoption gate: internal-consistency (GAP-SP12I-01..05, all
LOW) + external-referent (GAP-SP12E-01..06). Author ran the A6 refutation gate:
every finding reproduced/verified before triage — SP12E-06 GRADUATED unconfirmed→
confirmed; SP12E-04 confirmed. Pinned brief: SPEC_AUDIT_BRIEF.md; auditor evidence
in SPEC_AUDIT_INTERNAL_PENDING.md + SPEC_AUDIT_EXTERNAL_PENDING.md (archive both +
the brief once the RAISED items close). NO guardrail VALUE, HALT/veto/resume, or
equity-floor semantic weakened — guardrails, layer law, and staging rules SURVIVED
every internal-contradiction attack (10 internal + 7 external honest negatives,
incl. the 2015 CHF -35% gap verified conservative vs the real event, z(0.99)=2.326,
and the v2.12 Hurst drift-invariance fix confirmed right about the world). FIXED now
(honesty/tests, 524 green): SP12I-02, SP12E-04, SP12E-06(precond), SP12E-02(decl),
SP12E-03(runbook). RAISED to owner: SP12E-01, SP12E-02(apply-Lo?), SP12I-03, doc
batch SP12I-01/04/05. Accepted-risk: SP12E-05.
============================================================================= -->

## GAP-P12D-01: OOS primary tick source is HistData, not Dukascopy — master §13 provenance substituted (owner-ratified)
- Severity: medium · Likelihood: medium
- Status: superseded (2026-09-11, same day — the owner then chose **Dukascopy's official S3 archive** as the primary, so the primary provenance is Dukascopy again and there is no substitution; HistData moved to the cross-check role — see GAP-P12D-02 / master v2.13. Text below kept as the record of why HistData was vetted.)
- Residual: none — no provenance deviation remains; the HistData↔Dukascopy cross-source check this entry demanded is spec law (master §13, ACIS-09 C-BT-9) and is scheduled in TODO.md's §14 data plan.
- Area: [DIR:tests/backtest] data acquisition, master §13 (v2.9), ACIS-09 §5
- Description: §13 names Dukascopy tick primary (TrueFX validator). Measured from the owner's residential link 2026-09-10/11: Dukascopy admits ~one instrument-day (~24 hourly requests), then imposes a penalty that outlasts 5/10/20/40-min cooldowns (datacenter/GCP IPs are hard-banned outright, 2026-07-31) → the 35,072 day-chunk plan would take years. HistData.com publishes the same universe as one ASCII tick zip per pair-month (1,344 files). Verified 2026-09-11: all 8 instruments cover 2012–2025 (XAUUSD from 2009, EURGBP from 2002); a live month (EURGBP 2012-01) parsed **1,197,028 bid/ask ticks, 0 crossed / 0 non-positive / 0 out-of-order / 0 duplicate, max reported gap 177 s**. Resolution is preserved (tick, bid+ask); the VENDOR changes: retail-aggregated feed, **no tick volume** (ACIS reads none — `volume` is only validated ≥0), timestamps in **fixed EST (UTC−5, no DST)**, converted in the reader. Its quote density drives `tick_velocity`, which NVMA's liquidity veto and the scalp read RELATIVE to the session median — self-consistent within the source, but the live venue's density differs (sharpens [[GAP-0001]]).
- Justification: OWNER DECISION (in-chat 2026-09-11, "HistData primary"). The only free route to the full ratified universe × 14 yr at tick resolution. **Binding condition:** before a §14 pass is presented, run the loader's `cross_source_drift` HistData-vs-Dukascopy on overlapping days (the Dukascopy job, newest-first, supplies them); any window over threshold is investigated, never averaged (C-BT-9). Per-file provenance (sha256, row/anomaly counts, HistData gap report) is recorded in `data/histdata/manifest.jsonl`.
- Linked: scripts/download_histdata.py, archive/download_dukascopy_publicfeed.js (the retired public-feed downloader), tests/backtest/data_loader.py `cross_source_drift`, OOS_VALIDATION.md, [[GAP-0001]], [[GAP-P12D-02]]

## GAP-P12D-02: master §13 names TrueFX as the cross-check source, but TrueFX no longer offers free history
- Severity: low · Likelihood: high
- Status: fixed (2026-09-11 — owner ratified in-chat HistData as the validation cross-check; master §13 → v2.13 and ACIS-09 → v1.2 name HistData, Dukascopy stays primary via its official S3 archive)
- Area: master §13 (v2.13), ACIS-09 §5 (v1.2), tests/backtest/data_loader.py docstring
- Description: TrueFX's site redesign limits free historical downloads to roughly the last year; older history is paid (truefx-downloader README: the site "limited the amount of historical data available"; the downloads page is login-gated). The spec's named validator cannot cross-check a 14-yr window. Found 2026-09-11 while sourcing data — external-referent class (the spec is wrong about the outside world).
- Justification: a source-name substitution in a list the master itself calls "examples, not a hardcode"; no guardrail or provenance rule changed.
- Proof: ACIS_SPEC.md §13 + CHANGELOG v2.13; specs/ACIS-09-BACKTEST_VALIDATION.md v1.2; `tests/backtest/sources.py` `HistDataTickSource`, `test_real_histdata_month_hour_is_sane`
- Residual: none — the cross-check source exists, is built and tested; running it before §14 is spec law (C-BT-9) scheduled in TODO.md.
- Linked: [[GAP-P12D-01]], tests/backtest/data_loader.py

## GAP-P12D-03: the §14 run needs three NON-tick inputs that are not yet sourced — SPX daily, a historical event calendar, time-varying financing
- Severity: high · Likelihood: high
- Status: open (must be sourced and wired before an honest §14 grade — tick data alone is NOT sufficient)
- Area: tests/backtest harness/metrics, core/data/normaliser.py `macro_imminent`, core/regime/nvma.py:268, master §14 / §3.5 / §9.5 / §13
- Description: (1) **SPX daily closes** — the §14 `spx_correlation` <0.25 gate needs a real, date-joined series ([[GAP-SP12E-06]]); today's call sites pass zeros. (2) **Historical high-impact event calendar** — `MarketStateFactory` takes an injected `macro_imminent(instrument, t)`. With no source it is always False, so NVMA never enters **MACRO_EVENT** (its top-precedence regime, nvma.py:268) and the Governor's §3.5 news blackout never fires: the backtest trades straight through NFP/FOMC/CPI where the live engine stands aside — optimistic AND unfaithful, and news-restricted rulebooks (ftmo, prop_demo) can never register a blackout breach. (3) **Financing** — the harness takes ONE constant `daily_swap` per instrument, defaulting to 0 "pending OANDA calibration"; 2012–2025 spans zero rates through the 2022-23 hiking cycle, so any constant misprices carry over most of the window and 0 flatters every overnight/weekend hold.
- Justification: (1) and (3) are small, free sources (daily index history; central-bank policy-rate histories as a rate-differential swap proxy, with the harness taking a dated series instead of a constant). (2) is the hard one — a curated historical high-impact set. Each is a declared evolve-driver input; until wired, a §14 report must carry these as caveats and must NOT be presented as a pass.
- Progress 2026-09-11: sources verified live (research) — SPX: Yahoo `^GSPC` primary, FRED `SP500` cross-check (≈10-yr window only; Stooq now needs a captcha key). Financing: OVERNIGHT rates, not policy rates (OANDA prices off tom-next ≈ overnight + ~1%/yr fee): DFF→SOFR, ECBDFR→€STR, SONIA, TONA (BoJ API), SARON (SNB), CORRA (BoC Valet), RBA cash rate; BIS WS_CBPOL only as fallback (JP hole 2013-04→2016-09; XM is the MRO rate until 2024-09, 40–50 bp above where euro overnight traded from 2015). Gold lease rates are unpublished since 2015 → declared sensitivity band. Calendar: primary-source Tier-1 build from official archives (BLS/Fed/ECB/BoE/BoJ/RBA/SNB/BoC/ONS…) with era-specific release times and IANA tz conversion; per-firm restricted lists + windows (FTMO ±2 min named list on funded accounts; FundedNext ±5 min; The5ers ±2 min opening only); Forex-Factory-derived dumps used for LOCAL cross-check only (ToS). The harness side of (3) is DONE ([[GAP-P12D-06]]: dated, direction-aware `financing` hook); the data + rate model remain.
- Progress 2026-09-11 (later): **(1) SPX and (3) financing DATA + MODEL DONE.** `scripts/download_macro.py` fetched 8/8 series 2011–2025 from the ISSUING institutions (FRED is unreachable from the owner's network — connects, never responds — so every rate comes from its central bank): SPX (Yahoo, 3,772 closes, validated against 5 well-known published closes), USD EFFR (NY Fed), EUR DFR (ECB), SONIA (BoE), TONA (BoJ), SARON (SNB, via OS TLS — its server omits an intermediate cert; verification stays on), CORRA (BoC), BIS policy rates ×7 (AUD source + cross-check). Raw responses + sha256 in `data/macro/manifest.json`. `tests/backtest/financing.py` builds the harness hook: direction × (r_base − r_quote) − fee (OANDA 1% majors), gold on a declared 0.25% lease assumption (0–1% sensitivity band), stale gaps >10 days raise. Real-data test reproduces ZIRP 2013, 2023 USD ≈5%, JPY/CHF negative eras, and positive 2023 USD_JPY long carry. **Remaining: (2) the historical event calendar, and wiring SPX (date-joined, [[GAP-SP12E-06]]) + financing into the evolve-driver.**
- Linked: tests/backtest/metrics.py `spx_correlation`, tests/backtest/harness.py `daily_swap`, core/data/normaliser.py `macro_imminent`, core/regime/nvma.py:268, [[GAP-SP12E-06]], config/platform_rules.yaml

## GAP-P12D-04: `cross_source_drift` matched ticks by linear scan — O(n·m), could never run on real data
- Severity: medium · Likelihood: high
- Status: fixed 2026-09-11 (author-found while wiring real sources; regression test below)
- Area: tests/backtest/data_loader.py `_nearest` / `cross_source_drift`
- Description: every primary tick scanned the ENTIRE secondary list for its nearest match. Inert on 5-tick fixtures; on one real day of two ~50k-tick feeds it is ~2.5×10⁹ comparisons — the HistData↔Dukascopy check that [[GAP-P12D-01]]'s ratification is conditioned on could not have run.
- Justification: replaced by binary search over the sorted secondary; the only minimum-gap candidates are the latest tick at-or-before `ts` and the latest duplicate of the first tick after it, visited in time order with `<=`, so the old later-wins tie-break is reproduced exactly.
- Linked: test `test_bisect_nearest_matches_the_old_linear_scan_exactly` (3,000 probes × 4 tolerances on a duplicate-heavy grid vs the old scan), tests/backtest/test_sources.py
- Residual: none — the matcher is exact and fast; running it on real overlapping Dukascopy/HistData days is spec law (C-BT-9) scheduled in TODO.md's §14 data plan.

## GAP-P12D-05: backtest harness booked PnL in the QUOTE currency as if it were USD — USD_JPY inflated ~100–150× (CONFIRMED)
- Severity: high · Likelihood: high
- Status: fixed 2026-09-11 (author-found while designing dated financing; regression tests below)
- Area: tests/backtest/harness.py `_close_at` / `_unrealised`
- Description: `gross = Δprice × units` is a QUOTE-currency amount; the harness added it straight into realised PnL, the marked equity, the intraday drawdown and every §14 metric. A ¥10,000 USD_JPY gain was booked as $10,000. USD_JPY is ENABLED, so any two-pair §14 run would have been dominated by yen-denominated noise — meaningless Sharpe/DD/PF. The live Risk Monitor was fixed for the same class at phase 9 ([[GAP-0104]]); the harness never was. The spec is silent on account currency, so the external referent governs: PnL is in account currency.
- Justification: every quote-currency amount (gross, friction, financing, marks) is converted once via `quote_to_account` — XXX_USD ×1, USD_XXX ÷price, crosses through the quote leg's last-seen price; a missing leg raises `ConversionUnavailable` (never books pounds as dollars). This also closes the backtest side of [[GAP-0092]]'s cross-pair residual (EUR_GBP is in the ratified universe; its GBP_USD leg is too).
- Linked: tests `test_usd_jpy_pnl_is_booked_in_dollars_not_yen`, `test_cross_pair_converts_through_its_quote_leg_or_refuses`, `test_usd_jpy_open_position_marked_in_dollars` (tests/backtest/test_harness_regressions.py)
- Residual: GAP-0092 — the backtest side is done; the LIVE Risk Monitor still falls back to quote currency for a cross pair, and that entry owns it.

## GAP-P12D-06: carry was one signed constant per instrument — direction- and size-blind — and billed weekends twice
- Severity: medium · Likelihood: high
- Status: fixed 2026-09-11 (inert until now only because the constant defaulted to 0)
- Area: tests/backtest/harness.py `_carry_quote` / `_nights`, tests/backtest/carry.py
- Description: (a) `daily_swap[instrument]` was charged identically to a long and a short and did not scale with position size — real financing flips sign with direction and scales with notional (OANDA: position value × funding rate × 1/365). (b) `_nights` counted every 22:00-UTC rollover including Saturday and Sunday, while `swap_multiplier` also tripled Wednesday — the weekend was billed twice (+2 days per weekend held), contradicting carry.py's own tom-next rationale. (c) An undeclared `swap_convention` (e.g. XAU_USD's `financing_daily`) silently charged 1× every night.
- Justification: the harness now takes `financing(instrument, night, direction) -> annualised %` for THAT side (rate differential net of broker fee, built from the dated overnight-rate series — [[GAP-P12D-03]]) and charges value × rate/100/365 × multiplier per BUSINESS-day rollover. Conventions are explicit: tom_next = Wed ×3, financing_daily = Fri ×3 (OANDA CFD convention; not defined by the spec — declared here); anything else raises. Entry price stands in for the 5pm-ET rollover price (declared; holds ≤48 h).
- Linked: tests `test_financing_is_direction_and_size_aware`, `test_weekend_is_not_billed_twice`, `test_gold_financing_bills_the_weekend_on_friday`, `test_overnight_carry_reduces_pnl_of_a_held_position`, `test_triple_swap_wednesday_carry`
- Residual: GAP-P12D-03, GAP-P12D-07 — wiring the dated rate model into the evolve-driver (P12D-03) and the rollover INSTANT (P12D-07) are owned there.

## GAP-P12D-07: the spec's fixed 22:00-UTC daily anchor is the real FX rollover only in winter — in US summer time it is 21:00 UTC
- Severity: low · Likelihood: high
- Status: fixed for the BACKTEST (2026-09-11 — OWNER RULING in-chat: "make sure that there is no time anomaly"; the engine side is GAP-P12D-10)
- Area: core/data/fx_clock.py (new), tests/backtest/harness.py financing nights + weekend-holding rule, tests/backtest/data_loader.py `_is_weekend`, master §C1 / §13
- Description: the FX day rolls at 17:00 New York; that is 22:00 UTC under EST but **21:00 UTC under EDT** (≈ Mar–Nov). The spec pins 22:00 UTC year-round. In summer that financed positions from the wrong rollover — the WRONG DAY, which changes whether the tom-next triple applies (a Tue-21:30 → Wed-21:30 hold paid Tuesday ×1 instead of Wednesday ×3) — dropped the real Sunday 21:00–22:00 UTC open, and placed the Friday close an hour late. Exactly the §13 DST-boundary glitch class.
- Justification: one dependency-free FX clock (`core/data/fx_clock.py`, exact US rule since 2007: 2nd Sunday of March → 1st Sunday of November; earlier dates raise) now defines the rollover, the weekend window and business-day rollovers; every backtest consumer uses it. No new dependency (the `tzdata` package would have needed a spec edit — A1).
- Proof: `test_daylight_time_switches_on_the_real_us_dates`, `test_rollover_is_21_utc_in_summer_and_22_utc_in_winter`, `test_summer_weekend_boundaries_follow_new_york`, `test_business_rollovers_are_weekdays_at_the_real_instant`, `test_summer_rollover_is_21_utc_not_22`
- Residual: GAP-P12D-10 — the ENGINE's fixed-UTC day boundaries were owned there (fixed the same day, master v2.14); what is left of that work is owned by GAP-P12D-11.
- Linked: [[GAP-P12D-06]], [[GAP-0023]]

## GAP-P12D-10: the engine's day boundaries and sessions were fixed-UTC — an hour off for half the year (owner ruling: no time anomaly)
- Severity: medium · Likelihood: high
- Status: fixed 2026-09-11 (owner ruling "make sure that there is no time anomaly"; the guardrail-adjacent daily-loss instant explicitly owner-ratified in-chat 2026-09-11 — "I ratify all of them"; master v2.14)
- Area: config/calendars.py (new — local-time schema split out of config/schemas.py), config/system_config.yaml `session_boundaries`, config/instruments.yaml calendars, core/data/fx_clock.py (UK/Tokyo/Chicago zones, `local_to_utc`, `to_local`, `trading_day`, `next_local`), core/data/bars.py `DailyBarAggregator`, core/data/asset_classes.py, core/optimizer/param_library.py `is_session_boundary`, core/governor/capital_governor.py weekend ban + `_next_boundary`, core/risk/guardrails.py daily-loss day (GUARDRAIL-ADJACENT)
- Description: each read a fixed UTC clock time, and they disagreed with one another — the rollover/weekend/daily-loss day at 22:00 UTC (New York WINTER time) while London 07:00 and New York 12:00 were SUMMER times. So in summer the TSMOM daily bar closed an hour late, the weekend ban and the daily-loss reset fired an hour late, and in winter the London/New-York session tags and C1 staging instants sat an hour early.
- Justification: every market time is now declared as a LOCAL wall time `{zone, at}` (the schema has no UTC field left to misuse — the old keys are rejected) and resolved per date by the one dependency-free clock. The daily-loss limit no longer takes a reset parameter at all: its day is `fx_clock.trading_day` (17:00 New York). No limit VALUE, HALT/veto/resume semantics or staging rule changed — only when the already-ratified day and sessions begin. The GAP-0025/0033 cross-check compares `(zone, local time)` pairs. GAP-0023 (the uncovered New York close → Tokyo open window) was fixed separately the same day.
- Proof: `test_daily_loss_day_resets_at_the_real_new_york_rollover`, `test_daily_bars_anchor_at_the_new_york_rollover`, `test_windows_follow_each_centres_dst`, `test_boundaries_follow_dst`, `test_gap0053_weekend_ban_covers_the_whole_closed_window`, `test_boundary_in_the_wrong_zone_is_fatal`, `test_fixed_utc_calendar_fields_are_rejected`, `test_config_zones_are_exactly_the_modelled_zones`, `test_uk_summer_time_switches_on_the_real_dates`, `test_each_centre_opens_at_its_own_local_time_all_year`
- Residual: none — the follow-on gold-calendar shape (GAP-P12D-11) and the Sydney window (GAP-0023) were fixed the same day; the phase-12 dual audit re-examines this change as guardrail-adjacent (TODO item, brief point (d)).
- Linked: [[GAP-P12D-07]], [[GAP-0023]], [[GAP-P12D-11]], core/data/fx_clock.py, master §3.7 / §C1

## GAP-P12D-11: XAU_USD (a ~23h/5 spot CFD) was session-tagged against a 6.5-hour CME day-session calendar
- Severity: medium · Likelihood: high
- Status: fixed 2026-09-11 (owner directive in-chat "fix the other findings … leave nothing untouched"; master v2.15)
- Area: config/instruments.yaml `spot_metals` calendar + `XAU_USD.calendar`, config/calendars.py `FxCalendar.daily_break`, core/data/asset_classes.py, master §3.7 ("metals' daily break")
- Description: OANDA's XAU_USD trades roughly Sunday 18:00 → Friday 17:00 New York with a daily one-hour break, but it was declared on `cme_metals` (08:30–15:00 Chicago), so everything outside the US day session was `closed` ⇒ untradeable — ~17 h a day ignored, and §14 would have graded a gold strategy that could only trade the US day.
- Justification: spot metals are OTC, so they now use an fx-type calendar (`spot_metals`: the same centre sessions, week close Friday 17:00 New York, week open Sunday 18:00 New York) with a declared `daily_break` 17:00–18:00 New York. `cme_metals` stays declared for exchange-traded contracts (futures, GAP-0109).
- Proof: `test_trades_around_the_clock_except_the_daily_break`, `test_week_opens_an_hour_after_fx`, `test_gold_is_on_the_spot_metals_calendar`
- Residual: none — XAU_USD is declared-disabled; widening its tradeable hours is re-verified by the scenario-replay step the diversification-onboarding TODO already requires when it is enabled.
- Linked: [[GAP-P12D-10]], [[GAP-0109]], [[GAP-SP12E-01]]

## GAP-P12D-08: the MCP wire transport (`monitoring/server.py` `serve()`) is a declared stub with no owner
- Severity: medium · Likelihood: high
- Status: open (found 2026-09-11 by the ledger-closure check — GAP-P10E-06 was CLOSED with "`serve()` remains a declared not-yet-implemented binding point" and nothing live owned it)
- Area: monitoring/server.py `serve()` (`# pragma: no cover`), ACIS-08 §1/§3/§11, master §12
- Description: the ControlPlane contract is built and tested, but nothing binds it to the MCP wire (`CallToolResult`/`GetPromptResult`, prompt bodies). Phronesis supervises ACIS ONLY through MCP (§0/§12), so without the binding the supervision/control plane cannot be reached by its real client at go-live.
- Justification: a deployment-adapter task that belongs with the phase-12 production runtime (GAP-0075/0091b) and the bearer-auth hardening (GAP-P10E-03); must land before live.
- Linked: KNOWN_GAPS_CLOSED.md GAP-P10E-06, [[GAP-P10E-03]], [[GAP-0075]]

## GAP-P12D-09: ACIS-04 §10's SQLite `signal_log` store was never built
- Severity: low · Likelihood: high
- Status: open (found 2026-09-11 by the ledger-closure check — GAP-0061 was closed after fixing the table's DDL, while noting "the signal_log table is not yet implemented"; nothing live owned it)
- Area: [DIR:core/signals], ACIS-04 §9/§10, master §12
- Description: §9's JSONL `signal_log` IS implemented (`SIGNAL_EMITTED` and every `DISCARD_*` reason are logged). §10's SQLite `signal_log` table — the queryable store every other layer has (market_state, fill_report, risk_snapshot, provenance, param_*) — has no CREATE TABLE anywhere in core.
- Justification: auditability is covered by the JSONL log today, so this is not a safety hole; but the locked spec requires the store and the §12 plane / audits cannot query signals without it. Build it or amend ACIS-04 §10 (owner call).
- Linked: KNOWN_GAPS_CLOSED.md GAP-0061, core/signals/agon.py

## GAP-P12M-01: nine production modules exceed the 300-line legibility budget (SPEC_CONSTITUTION v0.4 A12)
- Severity: medium · Likelihood: high
- Status: open (owner-reported external-review deduction 2026-09-11; decomposition is AUDIT work, deliberately not done in this session)
- Area: config/schemas.py (622, was 702 — calendars extracted to config/calendars.py by GAP-P12D-10), core/signals/agon.py (506), core/governor/capital_governor.py (464), scripts/download_histdata.py (400, was 456), core/regime/nvma.py (395), core/signals/provenance.py (391), core/risk/monitor.py (378), core/execution/venue.py (378), core/risk/guardrails.py (313)
- Description: a review scored ACIS "still coherent, but further decomposition would help newcomers" (capital_governor ~470, monitor ~380). A12 v0.4 now makes >300 lines presumptively a finding unless justified against a spec requirement; "coherent" is not a defense.
- Justification: the next phase-12 dual adversarial audit (recommended auditor: **Fable 5.1**; floor Opus 4.8) must, per module, either name the cohesive extraction (own name, own tests, one responsibility) and do it, or write the spec-requirement justification that clears the length. Until then a RATCHET holds the line: `tests/unit/test_module_budget.py` fails if any new module exceeds 300 lines or any grandfathered one grows, and demands the allowlist line go once a module is back under budget. download_histdata.py slims when the S3 downloader shares its infrastructure.
- Linked: tests/unit/test_module_budget.py, [[GAP-P12M-02]], ../specs_constitution/SPEC_CONSTITUTION.md A12

## GAP-P12M-02: invariant density has no written mental model — a newcomer must reconstruct the gate / human-token / audit system from code
- Severity: medium · Likelihood: high
- Status: open (owner-reported external-review deduction 2026-09-11; for the next audit)
- Area: every invariant-bearing module (governor, risk monitor, guardrails, MCP plane, param library, provenance); the orienting read path (README → STATUS → TODO → CLAUDE → ACIS_SPEC)
- Description: the review noted "occasional density from the sheer number of invariants being upheld; a new reader needs the mental model of the gates/human-token/audit system." A12 v0.4 requires (a) each invariant-bearing module to open with a one-screen mental model (the invariants, where each is enforced, what to hold in mind), and (b) the read path to state the gate / human-token / audit model ONCE. Neither exists today.
- Justification: documentation + audit work. The next phase-12 dual audit (recommended **Fable 5.1**) checks each invariant-bearing module for the one-screen model and checks that a fresh reader can locate every gate from the read path alone; findings triaged per A6. Must not grow into a new standing document (A13) — the model lives in the module docstrings and one read-path section.
- Linked: [[GAP-P12M-01]], ../specs_constitution/SPEC_CONSTITUTION.md A12/A13, CLAUDE.md

## GAP-SP12E-01: §14 Sharpe>1.5 target exceeds the spec's own cited evidence base for a 2-pair book
- Severity: medium · Likelihood: high
- Status: resolved (OWNER DECISION — chose "broaden the universe for an HONEST Sharpe" on 2026-07-22, ratified again in-chat 2026-09-11. The §14 `SHARPE_MIN = 1.5` is UNCHANGED; it is graded on the broadened 8-instrument universe, and any pass must carry the Deflated Sharpe. The "treat 1.5 as a stretch and lower the minimum" option was NOT taken — the owner's standing: "quality, not mediocre results or a lie".)
- Residual: GAP-SP12E-03 — the Deflated-Sharpe/trial-count and embargo that must accompany any pass are owned there; enabling the 6 declared instruments (calibrated costs + vol targets) is the TODO "Diversification-basket onboarding" item.
- Area: master §14 / §5.6 / ACIS-09 / OOS_VALIDATION.md
- Description: `SHARPE_MIN=1.5` OOS, graded per account on the enabled universe (EUR/USD + USD/JPY — 2 highly-correlated USD-legged pairs). Moskowitz–Ooi–Pedersen (the §5.6 canon) reaches ~1.0 Sharpe only after diversifying across 58 markets (~0.3–0.5 per market). 1.5 on 2 pairs is ~50% above the diversified benchmark → clearable in-sample largely by overfit; the likely real outcome is (a) never clears/never live, or (b) a "pass" is an overfit that slipped the ≥30-trade/>1-fold floors. Externally quoted (foxholm MOP summary) in SPEC_AUDIT_EXTERNAL_PENDING.md.
- Justification: OWNER DECISION. Options: treat 1.5 as a STRETCH and set a defensible 2-pair minimum; and/or broaden the enabled universe before §14 is a fair test; and/or REQUIRE the Deflated-Sharpe deflation (SP12E-03) to accompany any pass. Not a guardrail weakening — a target-calibration question. → SPEC_AUDIT.md.
- Linked: SPEC_AUDIT_EXTERNAL_PENDING.md GAP-SP12E-01, [[GAP-SP12E-03]], report.py:29

## GAP-SP12E-02: annual_sharpe uses naïve iid √252 with no autocorrelation correction (Lo 2002); deviation now DECLARED, apply-Lo raised
- Severity: medium · Likelihood: high
- Status: mitigated (2026-07-21 — the iid-annualisation deviation is now in `annual_sharpe`'s DECLARED DEVIATIONS, §5.6/§16; whether to APPLY the Lo autocorrelation correction vs report-raw-with-caveat is RAISED to owner)
- Area: tests/backtest/metrics.py `annual_sharpe`
- Description: `(mean/sd)·√252` on daily returns, no serial-correlation adjustment. Lo (2002): serial correlation can overstate an annualised Sharpe "by as much as 65 percent"; ACIS's trend/momentum returns are positively autocorrelated within trends — the sign that makes √252 OVERSTATE, landing on the §14 gate (SP12E-01). Quoted (CFA Institute / Lo) in the pending file.
- Justification: minimum honesty fix APPLIED (declared deviation + caveat next to the figure). Applying the Lo correction changes the gating number → owner-ratified methodology decision. → SPEC_AUDIT.md.
- Linked: metrics.py `annual_sharpe`, SPEC_AUDIT_EXTERNAL_PENDING.md GAP-SP12E-02

## GAP-SP12E-03: embargo/purge + Deflated Sharpe are cited in the guard-2 runbook but NOT built — required before a §14 pass can gate live
- Severity: medium · Likelihood: high
- Status: mitigated (2026-07-21 — runbook wording FIXED to mark both ⛔ TO-BUILD + REQUIRED-before-grade, not adopted-as-done; the machinery itself is on the ratified build list)
- Area: OOS_VALIDATION.md vs walk_forward.py `generate_folds` / report.py
- Description: `generate_folds` sets `test_start = train_end` (zero embargo/purge — boundary leakage not removed); no Deflated Sharpe / trial-count anywhere in code (grader applies raw `annual_sharpe>1.5`). These are the defences against the SP12E-01 overfit risk; the runbook cited them as its ground truth (López de Prado) while shipping neither.
- Justification: dual-nature (read-path truth + faithful-method). Runbook corrected now; the build (embargo gap in generate_folds + deflated_sharpe/trial_count in ValidationReport) is a REQUIRED pre-grade item on the evolve-driver build, elevated from "enhancement" to "load-bearing".
- Linked: OOS_VALIDATION.md, walk_forward.py:43, report.py, TODO.md phase-12 item (2), [[GAP-SP12E-01]]

## GAP-SP12E-05: delta-normal + √t VaR is Gaussian-blind to the fat tails the 3% cap implicitly bounds
- Severity: low · Likelihood: medium
- Status: accepted-risk (2026-07-21 — the spec does NOT rely on VaR for tail bounding; the §8.5 scenario book + gap law carry tails, and VaR is labelled delta-normal + not-yet-wired-in-loop (GAP-0091b))
- Area: core/risk/monitor.py `_var_pct`, guardrail `var_cap_pct 3.0`
- Description: per-position delta-normal `z·σ` with σ scaled √(horizon/cadence) assumes iid-normal; a 2015-SNB-class gap (>10σ Gaussian) is assigned ≈0 probability. Residual: the 3% cap's calibration to a Gaussian 1-day horizon is unverified vs real FX kurtosis, and its only empirical check (`var_breach_frequency`) is a bare rate, not a significance test (SP12E-04).
- Justification: accepted because tails are carried structurally (scenario book/gap law), not by VaR. Recorded as a declared VaR limitation; the go-live operational-referent audit must use the Kupiec LR test (not a bare rate) for live VaR-breach frequency. → SPEC_AUDIT.md.
- Linked: core/risk/monitor.py `_var_pct`, [[GAP-SP12E-04]], [[gap-0091b]], master §8.5

## GAP-SP12E-06: spx_correlation zips returns by POSITION, not date — a false-clear risk for the §14 SPX-corr gate (CONFIRMED)
- Severity: low · Likelihood: medium
- Status: mitigated (2026-07-21 — graduated unconfirmed→confirmed by author; the caller date-alignment PRECONDITION is now load-bearing in the `spx_correlation` docstring; the date-join + a holiday-mismatch fixture are tracked as an evolve-driver build requirement)
- Area: tests/backtest/metrics.py `spx_correlation`
- Description: `spx_correlation` zips positionally with no date-join; FX (~260 sessions/yr, trades some US holidays) and SPX (~252) calendars differ, so an un-joined positional zip silently correlates mismatched dates → a meaningless near-zero value → a FALSE CLEAR of the §14 <0.25 diversification gate. The current call sites pass flat `[0.0]*n` fixtures so the defect is inert today; the REAL OOS driver must date-join.
- Justification: minimum fix APPLIED (precondition made explicit + load-bearing in the docstring). The date-join + fixture land with the evolve-driver (the component that builds the real SPX series).
- Linked: metrics.py `spx_correlation`, TODO.md phase-12 item (2)

## GAP-SP12I-03: MOMENTUM_SCALP sits exactly on the fast-decay fencepost — the most time-sensitive strategy never takes the IOC path
- Severity: low · Likelihood: high
- Status: mitigated (2026-07-22 — approach DECIDED with the owner: the scalp is not tuned to a fixed base time in isolation; it is VALIDATED under each target account's §9.5 rulebook (enforced in the backtest, GAP-P11I-02). On firms with `min_hold_seconds=0` (all three shortlisted — ftmo/the5ers/atlas_funded, none imposes a min-hold-TIME) the fencepost fix applies — `valid_for_seconds`<`fast_decay_seconds` so the scalp takes IOC; on a strict min-hold firm (`prop_demo` min_hold=60) the scalp fails its gate under the rule and is non-promoted for that account, and ACIS's other strategies carry it. The concrete `valid_for_seconds` value is set per-account at cost-calibration/enable time, not globally now. The §13 fast-decay-boundary test lands with that per-account enablement.)
- Area: config/system_config.yaml (`signals.valid_for_seconds.MOMENTUM_SCALP=30`, `execution.fast_decay_seconds=30`) vs master §7/§5.5, ACIS-06 §7
- Description: ACIS-06 §7 uses strict `<`; scalp `valid_for_seconds=30 == fast_decay_seconds=30`, so the shortest-lived signal (30 s vs 300 s) is EXCLUDED from the aggressive-IOC fast path by one second and routed to fragment/scheduled — the opposite of §5.5 "speed over stealth". Reproduced (repro_sp12i.py). No §13 test covers the fast-decay boundary.
- Justification: OWNER DECISION (recommend: set scalp `valid_for_seconds` to 29 or below so it takes IOC as §5.5 intends; alternatives: ACIS-06 `<=` for the scalp class, or raise `fast_decay_seconds`). Add a §13 fast-decay-boundary test with the chosen value. Not a guardrail.
- Linked: SPEC_AUDIT_INTERNAL_PENDING.md GAP-SP12I-03, config/system_config.yaml:41/113

## GAP-SP12I-DOC / GAP-SP12I-01 / GAP-SP12I-04 / GAP-SP12I-05: read-path documentation drift — three stale spec/config narratives (batch)
- Severity: low · Likelihood: high
- Status: fixed (2026-07-22 — owner ratified "apply all three"; applied: master §5/§8 mean_sigma note, ACIS-02 §6 adx_strong/adx_weak, scenario_book.yaml phase-11-delivered comments; 50 gate tests green. Moves to KNOWN_GAPS_CLOSED.md when the pass's raised items close.)
- Residual: GAP-SP12I-03, GAP-SP12E-02 — the three doc edits are complete; only the archive move of this spec-audit pass waits on those two still-live siblings.
- Area: ACIS_SPEC.md §5/§8; specs/ACIS-02 §6; config/scenario_book.yaml
- Description: (SP12I-01) master §5/§8 still say "Sharpe" for the fitness/alpha-decay metric that GAP-0105 (CLOSED) renamed to `mean_sigma` ("NOT an annualised Sharpe") in the deep specs — a locked spec now must contradict the master to stay honest (functionally harmless: the alpha-decay test is a ratio, annualisation cancels). (SP12I-04) ACIS-02 §6 names config keys `adx_strong_threshold`/`adx_weak_threshold`; the real keys are `adx_strong`/`adx_weak` (ACIS-02 §7 already uses the correct names). (SP12I-05) scenario_book.yaml comments say the GAP-0108 outage refinement is "deferred to phase 11"; phase 11 is ✅ and ACIS-09 §6 states it delivered.
- Justification: pure traceability drift (A13) — no safety impact, but a fresh session is taught an out-of-date story. Recommended edits (for "apply those"): (01) add a one-line master note that §5/§8 "Sharpe" is the per-trade mean/σ of GAP-0105, the annualised Sharpe being only the §14 graded metric; (04) `adx_strong`/`adx_weak` in ACIS-02 §6; (05) update the three scenario_book comments to point at ACIS-09 §6 where the refinement now lives.
- Linked: SPEC_AUDIT_INTERNAL_PENDING.md GAP-SP12I-01/04/05, KNOWN_GAPS_CLOSED.md GAP-0105

## GAP-SP12I-02: the anti-greed levers (marginal-alpha 0.25 floor / 1.0 neutral / 1.5 cap, 25% alpha-decay throttle) were prose constants with no drift gate
- Severity: low · Likelihood: medium
- Status: fixed (2026-07-21, regression tests; recorded as a proper entry 2026-09-11 — it had lived only in an HTML comment, invisible to the ledger)
- Area: core/governor/marginal_alpha.py, core/governor/capital_governor.py, master §6 C6 / §8
- Description: the master's numbers existed in code as literals that nothing tied back to the spec; a silent edit would have changed sizing behaviour with no failing test.
- Proof: `test_marginal_alpha_floor_neutral_cap_match_master`, `test_alpha_decay_throttle_matches_master` (tests/unit/test_spec_constants.py)
- Residual: none — both levers are pinned to the master's values by drift-gate tests.
- Linked: SPEC_AUDIT.md, SPEC_AUDIT_INTERNAL_PENDING.md

## GAP-SP12E-04: `rolling_var_breach_rate` claimed to be a "Kupiec POF backtest" — it is only the exceedance RATE
- Severity: low · Likelihood: high
- Status: fixed (2026-07-21, honesty edit; recorded as a proper entry 2026-09-11 — it had lived only in an HTML comment)
- Area: tests/backtest/metrics.py `rolling_var_breach_rate`, master §16 naming law
- Description: the docstring named a statistical test the function does not perform; a rate is the INPUT to Kupiec's likelihood-ratio test, not the test.
- Proof: tests/backtest/metrics.py `rolling_var_breach_rate` docstring (§16 naming note); `test_metrics_and_grader`
- Residual: GAP-SP12E-05 — the significance test itself (Kupiec LR on the tally) is not implemented; that gap owns it.
- Linked: SPEC_AUDIT_EXTERNAL_PENDING.md

<!-- ============================================================================
PHASE-11 DUAL AUDIT — TRIAGE COMPLETE (2026-07-18; suite green: 515 passed). Two
parallel Opus 4.8 adversarial audits of the phase-11 backtest harness + §14
validation: external-referent (GAP-P11E-01..07) + internal-consistency
(GAP-P11I-01..10). 14 findings FIXED with regression tests (archived
VERBATIM-condensed to KNOWN_GAPS_CLOSED.md), 2 remain LIVE below (GAP-P11I-02
mitigated, GAP-P11I-10 accepted-risk), and GAP-P11E-07 is informational
confirmations (kept below). ACIS-09 → v1.1 LOCKED with the honesty-guard
corrections. NO guardrail VALUE, HALT, veto, resume, or equity-floor semantic
weakened — every fix TIGHTENS an honesty gate (data-derived ≥2yr period, intraday
drawdown, min-trade floor, real Kupiec VaR tally, self-enforced per-account rules,
continuous cross-fold equity, non-overlapping OOS folds, real-guard glitch tests)
or makes a named quantity/claim honest (rf=0 declared, VaR rate≠3% cap, C-BT-1
flow-not-type). The two audits heavily overlapped and closed together:
P11E-01≈P11I-08, P11E-02≈P11I-03, P11E-04≈P11I-05. Author≠auditor; a clean report
is never a sign-off — ✅ still requires a peer/superior model or the human. Repro:
scratchpad/p11e_repro.py, scratchpad/probe*.py.
============================================================================= -->

## GAP-P11E-07: External-referent CONFIRMATIONS (NOT sign-offs) — phase-11 backtest metrics vs their standard definitions
- Severity: n/a (confirmations)
- Likelihood: n/a
- Status: informational (external-referent audit 2026-07-18 — a clean check is never a sign-off; author≠auditor)
- Area: [DIR:tests/backtest], core/risk/scenario_replay.py; master §14
- Description: Referents checked and found FAITHFUL, recorded as honest negatives: (1) **§14 grader constants EXACTLY match master §14** (report.py:26-33 vs spec table: Sharpe>1.5, DD<15%, win>0.48, PF>1.4, pos-months>70%, SPX<0.25, duration 1800–172800s; strict `>`/`<` on the open bounds, inclusive on the duration band — no drift). (2) **`positive_months_pct` == industry "months with positive return"**: `b > a` on consecutive month-end equities is identically the sign of the monthly return `(b−a)/a` (repro D) — correct, first month excluded, denominator = transitions. (3) **`max_drawdown_pct`**: standard running-peak-to-trough, positive percent basis — correct. (4) **Triple-swap Wednesday** (`carry.py`): Wednesday=3× under tom_next is the correct T+2 spot-FX rollover convention for the enabled majors (Wed→Thu roll settles over the weekend) — correct where it fires (but see GAP-P11E-04: not wired into PnL). (5) **`spx_correlation`**: textbook Pearson on paired finite returns, degenerate-variance→0 (no spurious correlation) — sound; alignment is positional (assumes pre-aligned same-clock returns, which the harness owes it). (6) **Sharpe annualisation** uses sample std (n−1) and √periods_per_year — the standard form (but see GAP-P11E-05 rf, GAP-P11E-02 curve). (7) **Data provenance** (data_loader.py): Dukascopy-primary/TrueFX-cross-check characterised faithfully (TrueFX validator-not-primary; OANDA candle-grade excluded as a tick source), drift check on mids with nearest-time alignment FLAGS and never averages — matches master §13/v2.9. (8) **GAP-0108 outage refinement** (scenario_replay.py:79-103): worst ENABLED-instrument gap with a conservative fallback to the overall worst — the refinement only ever makes the per-account outage MORE accurate, never under-provisions below the committed book; the ceiling is unchanged. These are confirmations of faithfulness to the referent, NOT a phase sign-off — the six findings above stand and ✅ still requires a peer/superior model or the human.
- Linked: tests/backtest/report.py:26-33; tests/backtest/metrics.py; tests/backtest/data_loader.py; core/risk/scenario_replay.py:79-103; scratchpad/p11e_repro.py

<!-- ============================================================================
PHASE-10 DUAL AUDIT — TRIAGE COMPLETE (2026-07-18). Two parallel Opus 4.8
adversarial audits of the MCP monitoring/control plane: internal-consistency
(GAP-P10I-01..09) + external-referent (GAP-P10E-01..06), deploy-and-continue.
ALL findings triaged: 13 FIXED with regression tests (archived VERBATIM-condensed
to KNOWN_GAPS_CLOSED.md), 2 remain LIVE below (GAP-P10I-06 mitigated, GAP-P10E-03
accepted-risk). ACIS-08 → v1.2 LOCKED with the mechanism-honesty corrections.
Suite green after triage. NO guardrail VALUE, HALT, veto, resume, or equity-floor
semantic weakened — every fix TIGHTENS a guard (bounded staging, crash-safe
idempotency, safe-by-construction live gate, built heartbeat) or makes a named
quantity/claim honest. The confirmations (both audits) are archived with the
closed findings. Author≠auditor; a clean report is never a sign-off.
============================================================================= -->

## GAP-P11I-02 (P11I): §9.5 "platform rules ACTIVE during the run" (C-BT-7) — self-enforced + per-account PROVEN for the trade-evaluable rules; full drawdown-series/lot-cap/enabled-universe enforcement scoped to phase-12
- Severity: high
- Likelihood: medium
- Status: mitigated (2026-07-18 — core finding FIXED, scoped remainder deferred)
- Area: [DIR:tests/backtest] harness.py `_rule_violations`, specs/ACIS-09 §1/§2/§6/§13 C-BT-7, master §9.5/§14
- Description: the core defect is CLOSED — `rule_violations` is no longer a caller free param. `Backtest.__init__` takes a per-account `rulebook`, and `_rule_violations` computes breaches FROM THE RUN'S closed trades (min-hold, weekend-holding), forcing `passed=False`; per-account independence is proven (`test_rule_enforcement_is_per_account`: the SAME 60s trade is a min-hold violation for a strict account and clean for a lax one). News-blackout is already enforced upstream by the REAL Governor's two-layer §3.5 gate during the replay. REMAINING (scoped, mitigated): (a) the full §9.5 series rules NOT expressible from closed trades — live-tracked trailing/daily drawdown-SERIES and lot-cap enforcement inside `_replay` — are not yet run as their own metric-path checks (drawdown IS measured off the intraday high-water for the §14 metric, GAP-P11I-04; the guardrail layer enforces the series live during the real-engine replay); (b) replayed states are not filtered to a per-account enabled universe (the caller supplies per-account fold states); (c) the §14-mandated SECOND REAL prop universe (XAU-only) independence test lands with futures/metals enablement at phase-12, since XAU is disabled now.
- Justification: mitigated — the honesty guard is now self-enforcing and per-account for the rules a forex-phase-11 run can evaluate, and stricter enforcement (the guardrail layer, the real Governor blackout gate) runs live in the integration harness. The scoped remainder cannot bite the shipped single-universe forex config; it is real work tied to phase-12 (real second universe + in-metric-path series enforcement). Linked to GAP-P11I-10 (per-account universe into ScenarioReplay) and GAP-0109 (phase-12 futures/metals).
- Linked: tests/backtest/harness.py `_rule_violations`, tests/backtest/test_harness_regressions.py, specs/ACIS-09 §14 Integration, master §9.5/§14, [[GAP-P11I-10]]

## GAP-P11I-10 (P11I): GAP-0108 outage-gap refinement keys "enabled" off the GLOBAL instruments flag, not a per-account universe — "per-account accurate" is aspirational; shipped gate unchanged & sound
- Severity: low
- Likelihood: low
- Status: accepted-risk (2026-07-18 — latent, no effect on the shipped single-universe config; per-account universe parameterisation deferred to phase-12 with GAP-P11I-02)
- Area: [DIR:core/risk] scenario_replay.py `_worst_book_gap_pct`, specs/ACIS-09 §6 (GAP-0108), master §8.5
- Description: `_worst_book_gap_pct` sources the outage gap allowance from gap scenarios whose named instrument is `spec.enabled` in `self._instruments` — the GLOBAL `instruments.yaml` enabled flag. ACIS-09 §6 / the docstring frame this as "the worst gap on an ENABLED instrument for THIS ACCOUNT'S universe", but `ScenarioReplay` is not parameterised by a per-account universe, so every account gets the same global-flag-derived allowance; two accounts with different enabled universes would not be distinguished. VERIFIED not to weaken the shipped release gate: with the shipped config (CHF + XAU disabled) the refinement falls back to `max(gaps_all)=35.0`, and the gate numbers are UNCHANGED — chf_depeg 7.0000% (ceiling 7.5%), broker_outage 7.0560% (ceiling 7.5%), all scenarios pass with floor survival. VERIFIED no under-provision path in the shipped semantics: an instrument-less "systemic" gap scenario is REJECTED by the schema (every gap scenario must name an instrument), and dropping a DISABLED instrument's gap is legitimate because a disabled instrument cannot be held during an outage. Recorded as a precision/observability gap, not a guard weakening.
- Justification: FINDER-only, guard-integrity-adjacent (→ SPEC_AUDIT). Fix = when per-account grading is actually implemented (GAP-P11I-02), pass the account's enabled universe into `ScenarioReplay` and key the refinement off THAT, so the "per-account" claim is real; until then, note in the docstring that "enabled" means the global config flag. The conservative fallback + schema instrument-requirement keep the shipped gate sound.
- Linked: core/risk/scenario_replay.py:79-103, tests/backtest/test_scenario_replay.py:130-152, specs/ACIS-09 §6 (GAP-0108), master §8.5

## GAP-0109: two §13 futures-lifecycle glitch classes (contract-roll gap, expiry-with-open-position) have no backtest test yet — they need the unbuilt futures roll-or-flatten policy
- Severity: low
- Likelihood: low
- Status: open (owned by phase 12 futures enablement — inert in phase-11 forex validation)
- Area: [DIR:tests/backtest] test_glitch_classes.py, specs/ACIS-09 §13 C-BT-10, master §13/§3.7
- Description: master §13 names nine glitch classes; ACIS-09 C-BT-10 requires backtest-level tests. SEVEN (triple-swap Wednesday carry, holiday half-day session-end, trailing-drawdown anchor, symbol-suffix non-merge, limit-lock→ILLIQUID gap-law, weekend-ban fencepost, Tier-G-shock-during-blackout) are tested now (`tests/backtest/test_glitch_classes.py`). The remaining TWO — contract-roll gap (a futures position held into its roll window → roll-or-flatten fires, never silent expiry; continuous-contract stitch never fabricates a tradeable price) and expiry-with-open-position (must be structurally unreachable given the roll policy) — depend on a futures roll-or-flatten POLICY that is not yet built (`grep roll_window|continuous_contract core/` is empty of an implementation). No futures instrument is enabled (`instruments.yaml` has none), so these paths are inert in phase-11 forex validation.
- Justification: per master §3.7, futures go live only on futures-specific gates + a SEPARATE human sign-off at phase 12; the roll-or-flatten policy + its two glitch-class tests are legitimately owned by that futures-enablement work, not phase-11 forex §14 validation. Recorded (not silently skipped) so phase 12 treats the roll policy + these two tests as a named requirement; ACIS-09 C-BT-10 is amended to the 7-now / 2-at-phase-12 split.
- Linked: tests/backtest/test_glitch_classes.py, specs/ACIS-09 §13 C-BT-10, master §13/§3.7, TODO.md phase 12

## GAP-P10E-03 (P10E): human-token verifier is an unsalted single-round SHA-256 bearer-secret equality check with no rate-limit — sound compare, but not password-grade
- Severity: medium
- Likelihood: low
- Status: accepted-risk (2026-07-18 — the compare is cryptographically sound (constant-time `hmac.compare_digest` over a sha256 digest, blank refused, genuinely closes GAP-0048); the SCHEME is a BEARER-SECRET equality model (the API-key pattern), NOT a password KDF. ACCEPTED with a DECLARED assumption + spec scoping (ACIS-08 §6): the deployment MUST provision a high-entropy human token (≥128-bit); salting is inapplicable to a single injected secret compared by digest; an in-process attempt-lockout is deliberately NOT added — it would let an attacker DoS the human out of their only resume/go-live path; online-guess throttling, if required, is a TRANSPORT/gateway responsibility at deployment (the same layer that binds stdio/SSE). "Genuine credential" is scoped to mean "a real constant-time secret check a fabricated string cannot pass", not password-grade brute-force hardening. A phase-12 deployment gate should verify the token's entropy + transport throttling before live.)
- Area: [DIR:monitoring] auth.py `HumanTokenVerifier`, ACIS-08 §6/§13 C-MCP-10, master §12 safety asymmetry
- Description: unsalted single-round SHA-256 with no rate-limit/lockout gates `acis_resume` and `acis_set_mode(live)` — the two human-only actions. Reproduced: 8 wrong online guesses, none throttled. Strength = the injected secret's entropy alone. Not a guardrail-value weakening; the token still gates every human-only action.
- Justification: the residual is a deployment-time property (secret entropy + transport throttling), not a code defect in the constant-time compare; recorded as a declared deviation from a full NIST-800-63B verifier per §5.6, with a named phase-12 gate. Adding a KDF/salt/lockout in-process buys little against a single high-entropy injected secret and risks locking out the human.
- Linked: monitoring/auth.py, ACIS-08 §6/§13 C-MCP-10, master §12, SPEC_AUDIT.md (phase-10 external-referent), KNOWN_GAPS_CLOSED.md (phase-10 fixed set)

## GAP-P10I-06 (P10I): §14 integration contract under-covered — three of five mandated end-to-end cases now added; two joint cases deferred to the phase-12 runtime
- Severity: medium
- Likelihood: low
- Status: mitigated (2026-07-18 — FIXED three of the five: the dual-hash live gate is now proven against the REAL config hashes (`guardrail_hash(cfg.guardrails)` + `rulebook_hash(active)`, and a tampered hash rejects — no longer only mock "GHASH"/"RHASH" strings); a `BLACKOUT_OVERRIDE_ENFORCED` near-miss is surfaced on `acis://status`; a staged tunable is proven not to mutate the live config file mid-session. DEFERRED to the phase-12 always-on runtime under the ACIS-08 §15 lean-build scope note: (b) staged-config-promotes-at-the-next-session-boundary jointly with ACIS-03 (the config-staging-to-boundary mechanism is owned by the runtime that owns boundary cadence — the same split as GAP-0091b/0075/0099), and (c) the real composed-paper-loop take-rate/skip surfacing (the surfacing CONTRACT is unit-proven under the C-MCP-9 non-partition test; wiring the live loop's counters is the runtime's job). The equity-floor-specific resume rejection (a) is covered by the non-human-resume-rejected + halt-persists integration test through the real Governor.)
- Area: [DIR:tests/integration] test_mcp_pipeline.py, specs/ACIS-08 §14 (Integration)
- Description: the suite is green, but green over a reduced surface. ACIS-08 §14 "Integration" enumerates cases the phase-10 integration test does NOT cover: (a) "agent tries to resume an **equity-floor** HALT → rejected (jointly with ACIS-07)" — the test resumes a generic MCP-initiated global halt, never an equity-floor-triggered HALT specifically; (b) "staged tunable config promotes only at the next session boundary (jointly with ACIS-03)" — no ParamLibrary/boundary test at all; (c) "`acis://status` reflects the paper-loop's take-rate + per-gate skip counters (jointly with the phase-7 skip_attribution)" — only a MOCK-provider unit test exists, the real composed loop is never wired; (d) "a `BLACKOUT_OVERRIDE_ENFORCED` event is surfaced on `acis://status`" — untested and unhandled; (e) "`acis://account/rules` surfaces the rulebook hash the `set_mode(live)` ack must match" — the fixture hard-codes `RULEBOOK_HASH="RHASH"` for BOTH the surfaced resource and the mode controller, so they match by construction; the REAL `account_doctrine.rulebook_hash(active_rulebook)` is never tied end-to-end to the `set_mode(live)` requirement. The dual-hash live gate is only ever exercised with matching short mock strings ("GHASH"/"RHASH"), so its real-64-hex behaviour is unproven (compounds GAP-P10I-03).
- Justification: fix = add the five §14 integration cases with real fixtures (real hashes, real paper-loop status, an equity-floor HALT path, an ACIS-03 boundary promotion, a BLACKOUT_OVERRIDE_ENFORCED surfacing). Postcondition discipline (CLAUDE.md rule 4/6): the §14 contract is the bar, and the current tests do not meet it. Finder-only.
- Linked: tests/integration/test_mcp_pipeline.py, tests/mcp_fixtures.py:14-15, specs/ACIS-08 §14

<!-- ============================================================================
PHASE-9 DUAL ADVERSARIAL AUDIT (2026-07-18, both Opus 4.8 subagents, deploy-and-
continue). Internal-consistency (GAP-P9I-01..09) + external-referent
(GAP-P9E-01..08) run in parallel, each to its own pending file, merged here.
Real IDs GAP-0093..0108. Suite 413 green after triage (was 404; +9 regressions).
Author≠auditor; every finding reproduced by the finder and re-verified by the
author before triage. FIXED entries archived to KNOWN_GAPS_CLOSED.md; the live
entries below are mitigated / raised-to-owner only. Guardrail-adjacent findings
summarised in SPEC_AUDIT.md. NO guardrail VALUE, HALT, veto, or equity-floor
semantic was weakened — every fix either TIGHTENS a guard (trailing high-water,
daily-anchor, re-arm, clock-skew) or makes a named quantity honest; the two
human-owned value questions (VaR cap horizon, CHF gap magnitude) were RAISED, not
changed, and were subsequently CLOSED by the owner's 2026-07-18 ratification pass
(GAP-0103 ratified as-is; GAP-0108 resolved to a faithful -35% gap + 7.5%
ceilings — both moved to KNOWN_GAPS_CLOSED.md). Internal honest-negatives (verified SOUND): the single upward edge
(risk imports nothing from governor; the sink schema cannot express a size
increase); equity breaker checked-first + unthrottleable within an evaluate;
taper hand-vectors + min-across + prop-stricter; taper-only never clears a
throttle; C5 baseline validity; restart-drift adopts broker + halts; all config
schema gates fire; scenario gate provably can fail; watchdog silence semantics +
zero-core-imports. External honest-negatives: z(0.99)=2.326 exact; undiversified
VaR is a provable conservative upper bound; gap/flash/vacuum/outage loss formulas
dimensionally correct; the taper is exactly the ratified linear schedule.
============================================================================= -->

## GAP-0102 (P9E-02): `DrawdownRule.anchor` (eod vs intraday) — v1 samples INTRADAY for all rules (the risk-conservative choice); true eod-only sampling deferred
- Severity: low
- Likelihood: medium
- Status: mitigated (2026-07-18 — declared deviation, not a silent one: `_RuleAnchor` samples the basis on EVERY observation (intraday) for all rules, which can HALT earlier than a platform measuring only end-of-day but NEVER later, so it never MISSES a platform-enforced breach (stricter-of, §9.5; halts are cheap, CLAUDE.md). True eod-only sampling (prior-session close, once-daily) is a phase-11 adapter refinement. The reset-cadence defect that made this material — daily reset of the trailing high-water — is separately FIXED, GAP-0101)
- Area: [DIR:core/risk] guardrails.py `_RuleAnchor`, config schema `DrawdownRule.anchor`
- Description: the schema offers eod/intraday but v1 measures both intraday. The choice is conservative-by-construction (stricter, never looser) and now documented in `_RuleAnchor`'s docstring; phase-11 adapters implement platform-faithful eod sampling.
- Justification: erring strict is safe under the stricter-of law; recorded as a declared deviation per §5.6.
- Linked: core/risk/guardrails.py `_RuleAnchor`, config/schemas.py `DrawdownRule`

## GAP-0099 (P9I-07): the equity breaker's per-FILL fast path is not wired in the monitor — it fires on each `evaluate`, not on each `ingest`
- Severity: medium
- Likelihood: medium
- Status: mitigated (2026-07-18 — ACIS-07 §7 says the fast breakers run "every eval_cadence_s AND on each fill"; the monitor's `ingest` updates state but does not itself call `evaluate`. The equity/drawdown breakers therefore fire on the evaluate cadence, not intra-fill. The production three-loop runtime (phase 10) owns the fast-loop cadence and drives `evaluate` on the fast path — the same lean-build split as GAP-0091b/paper_loop. Equity is broker-account truth (fetched by the loop, not carried on a fill), so a per-fill check is inherently a loop-owner responsibility. Carried as a phase-10 wiring requirement)
- Area: [DIR:core/risk] monitor.py `ingest`/`evaluate`, ACIS-07 §7
- Description: between evaluate ticks, a fill that drops equity below the floor is not caught until the next evaluate. Bounded by `eval_cadence_s` (10s) in v1; phase-10 wires the fast-path evaluate on the fill edge.
- Justification: lean-build — the runtime that owns loop cadence lands at phase 10; recorded so it treats fast-path evaluate-on-fill as a named requirement.
- Linked: core/risk/monitor.py, ACIS-07 §7, [[gap-0091b]] pattern

## GAP-0092: Risk Monitor books realised PnL in the instrument's QUOTE currency and treats it as account currency — exact only for USD-quoted pairs
- Severity: medium
- Likelihood: high
- Status: mitigated (2026-07-18 — RESCOPED + partially fixed by GAP-0104: quote→USD conversion now covers the entire ENABLED universe exactly (XXX_USD → 1.0; USD_XXX → 1/price), so the per-instrument DD HALT/taper, VaR, and cluster caps are no longer contaminated for EUR_USD/USD_JPY. The self-contradictory "HALT arithmetic is exact" claim is withdrawn. RESIDUAL: a true CROSS pair (neither side USD, e.g. EUR_GBP) still has no derivable rate → falls back to quote-ccy with a logged CONVERSION_UNAVAILABLE; none are enabled. Full FX→USD rate table owned by phase 11)
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

## GAP-0023: fx_default calendar tagged New York close → Tokyo open "closed" daily — spurious dead window vs 24/5 forex
- Severity: low
- Likelihood: high
- Status: fixed 2026-09-11 (owner directive in-chat "fix the other findings … leave nothing untouched"; master v2.15 — was accepted-risk 2026-07-15 as deliberate conservatism around the rollover liquidity vacuum)
- Area: [DIR:config] instruments.yaml fx_default / spot_metals `sydney`, config/calendars.py `Session.close_zone`, [DIR:core/data] asset_classes.py `_in_session`, normaliser.py `SESSIONS`, master §3 / ACIS-01 §6
- Description: no declared session covered the hours between the New York close and the Tokyo open, so `session_at` returned `"closed"` (⇒ untradeable, ACIS-01 §4) for 2–3 hours every weekday although forex trades 24/5 there (the Sydney/Wellington open). The schema could not even declare a session that wraps midnight.
- Justification: `sydney` is now a session from 17:00 New York to 09:00 Tokyo (`close_zone` lets a session close in another centre's local time, which may cross midnight). It opens at the rollover — already a C1 boundary, so staging is unchanged — and never overlaps Tokyo, so the `overlap` label and its spread baseline stay London–New York and are not diluted by Asian hours (a first 07:00–16:00-Sydney-local definition failed exactly that way and was withdrawn). The rollover-vacuum conservatism is kept where it belongs: a new session's median starts cold (REGIME_WARMING, untradeable until warm), then the median-relative SPREAD_VETO / ILLIQUID rules (§4) and the `rollover_liquidity_vacuum` replay scenario still bind.
- Proof: `test_sydney_fills_new_york_close_to_tokyo_open`, `test_single_sessions_and_overlaps`, `test_wrapping_session_needs_a_close_zone`, `test_last_local_is_at_or_before`
- Residual: none — tagging only; the liquidity vetoes that guard the rollover hour are unchanged and each is already tested (ACIS-02 veto tests, `rollover_liquidity_vacuum` replay).
- Linked: [[GAP-P12D-10]], config/instruments.yaml fx_default, core/data/asset_classes.py `_in_session`

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
