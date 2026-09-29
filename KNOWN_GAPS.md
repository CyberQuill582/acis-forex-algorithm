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

## GAP-P12D-13: HistData timestamps follow EUROPEAN summer time, not the documented "EST without DST" — our reader is 1 h wrong for ~7 months of every year, and the drift check passes silently when nothing matches
- Severity: high · Likelihood: high
- Status: fixed 2026-09-13 (owner go "go ahead"; master v2.16)
- Area: tests/backtest/sources.py `HistDataTickSource` (`EST_OFFSET` fixed +5 h), scripts/download_histdata.py `EST_FIXED` (month-boundary verify + manifest `first_utc`), tests/backtest/data_loader.py `cross_source_drift` (n_compared == 0 ⇒ `flagged=False`), tests/backtest/test_sources.py former `test_histdata_converts_fixed_est_to_utc` (encoded the vendor claim) + `test_real_histdata_month_hour_is_sane` (January only), master §13 v2.13 wording "fixed-EST timestamps", OOS_VALIDATION.md
- Description: HistData's spec page says "Eastern Standard Time (EST) time-zone WITHOUT Day Light Savings adjustments". Measured against Dukascopy (UTC; tick-for-tick identical to Dukascopy's own public feed), EUR/USD and USD/JPY HistData ticks match 100% on (millisecond, bid, ask) only after shifting by −1 h during EU summer time and 0 h otherwise, switching exactly on the EU dates: 2023-10-27 −1 h / 2023-10-30 0 h; 2024-03-29 0 h / 2024-04-01 −1 h; 2024-10-25 −1 h / 2024-10-28 0 h; 2024-03-11 and 2024-11-01 (US already/still on EDT) 0 h. I.e. HistData time = Frankfurt local time − 6 h. Consequences: (1) every HistData tick in EU summer time is placed 1 h late; (2) `cross_source_drift` aligns within 1 s, so a 1 h shift yields zero matches and a report with `n_compared=0, flagged=False` — a silent false CLEAR, exactly the failure the check exists to prevent; (3) the FX ticks are the SAME prices as Dukascopy (EUR/USD 2025-12: 1,293,972 ticks, max drift 0.0 bps; USD/JPY a filtered subset), so HistData is NOT an independent check of Dukascopy prices for FX — only of our decoding/timestamps (which it just did); XAU/USD differs in prices and timing (apparently independent).
- Justification: FIXED — (a) `tests/backtest/sources.py` converts HistData time as London wall time − 5 h via `core/data/fx_clock.py` (`histdata_naive_to_utc`, per-day offset cache; `utc_to_histdata` picks the monthly files), and the downloader's manifest times use the same function (still 400 lines); (b) `cross_source_drift` reports `coverage` and FLAGS below `min_coverage` (default 0.5) with a `reason` — zero overlap can no longer clear; (c) master §13 v2.16 + OOS_VALIDATION wording corrected; (d) the 560 manifest records written before the fix were corrected in place (383 EU-summer records; original kept as `data/histdata/manifest.jsonl.pre-p12d13`) with the downloader paused, then it was restarted on the fixed code. Independence of HistData for FX is a separate matter, owned by GAP-P12D-14.
- Proof: `test_histdata_clock_is_frankfurt_minus_six_hours`, `test_real_histdata_ticks_land_on_dukascopy_utc_across_eu_switches`, `test_cross_source_drift_flags_when_nothing_aligns`, `test_summer_month_first_utc_follows_eu_summer_time`, former `test_histdata_converts_fixed_est_to_utc`
- Residual: GAP-P12D-14 — HistData FX ticks are Dukascopy-derived, so an INDEPENDENT price check of Dukascopy (ECB rates, triangular, structural/time, gold) is still to build.
- Linked: [[GAP-P12D-14]], [[GAP-P12D-02]], [[GAP-P12D-04]], [[GAP-P12D-07]], tests/backtest/sources.py, tests/backtest/data_loader.py

## GAP-P12D-14: no INDEPENDENT validation of Dukascopy prices and timestamps exists yet — HistData's FX ticks are Dukascopy's own
- Severity: high · Likelihood: high
- Status: open (checks BUILT and tested 2026-09-13 — `scripts/download_ecb_rates.py`, `scripts/run_data_validation.py`, `tests/backtest/validation_*.py`; 2024 trial: 0 flags; the full 2012–2025 run was started 2026-09-13 and its report `data/validation/report.md` still needs review before this closes)
- Area: tests/backtest (new validation checks + runner), master §13 C-BT-9 wording, OOS_VALIDATION.md
- Description: GAP-P12D-13 showed HistData's EUR/USD and USD/JPY ticks carry Dukascopy's exact prices (EUR/USD 2025-12 tick-for-tick identical, 0.0 bps), so the §13 cross-source check against HistData cannot catch a Dukascopy PRICE error for FX — only decoding/clock errors. XAU/USD on HistData differs (apparently independent).
- Justification: the approved plan replaces "full Dukascopy-vs-HistData drift" for FX with independent, fast, free checks: (1) ECB daily euro reference rates vs Dukascopy mid at 14:15 Frankfurt — trial 2024 EUR/USD: 256 days, |diff| median 1.43 bps, p95 4.81, max 8.60, 0 days > 10 bps; (2) triangular consistency EUR/GBP ≈ EUR/USD ÷ GBP/USD at tick level; (3) structural/time checks from Dukascopy alone (17:00-New-York rollover spread spike, weekend boundaries, London/NY open tick-rate steps, NFP bursts); (4) gold via the (now clock-fixed) HistData XAU or OANDA practice M1 candles (owner-held token via env var). HistData stays downloading as an extra check (owner). Each check needs tests, a flag-never-average report, and the §13 C-BT-9 wording edit.
- Correction (2026-09-13): the sampled gold comparison returned 0.0 bps median AND worst on all 12 sample days of 2024 — HistData's gold is ALSO Dukascopy-derived there, so check 4 is not independent (the earlier "gold looks independent" rested on one 2023 night-time sample). An independent gold source (e.g. OANDA practice M1 candles, owner-held token) is still needed.
- Full run (2026-09-15, all 8 instruments, 2012–2025, 40,912 day files, 76 min; `data/validation/report.md`): **8 flags, each still to be explained.** (1) Gold vs HistData on 13 Mar 2013, 12 Mar 2014, 11 Mar 2015 and 14 Mar 2018 (medians of 6.9–21 bps). All four fall between the US and EU daylight-saving switches, so a one-hour clock offset in the sampled comparison is the first suspect, not a Dukascopy price error; from 2019 HistData gold matches Dukascopy at 0.0 bps. (2) AUD/USD: one day in 2016 (36.8 bps) and one in 2020 (164.9 bps) off the ECB reference; check those dates for a data spike versus a real market move. (3) USD/JPY 2012: 5,915 ticks inside the FX weekend window; all later years have 0. (4) XAU/USD 2025: the jobs-report burst at the true 08:30 New York (1.364) does not beat one hour late (1.379). Everything else passed: ECB medians 0.2–2.3 bps, the EUR/GBP triangle medians ≤ 0.2 bps, the rollover spread spike at the true 17:00 New York in every FX instrument-year, gold's daily break in every year.
- Proof: `test_ecb_fixing_is_1415_frankfurt_in_both_seasons`, `test_day_metrics_ecb_gap_and_weekend_ticks`, `test_a_clock_shifted_by_an_hour_is_flagged`, `test_triangle_flags_an_inconsistent_cross`, `test_a_price_disagreement_is_flagged`
- Linked: [[GAP-P12D-13]], [[GAP-P12D-03]], [[GAP-SP12E-03]], tests/backtest/OOS_VALIDATION.md

## GAP-P12D-124: every synthetic verdict recorded before 2026-09-29 was made on the old tick market (demeaned, 3.3× volatility, oracle Sharpe ~157) — each must be re-stated, and the falsification tape's oracle rungs re-calibrated first
- Severity: high · Likelihood: certain
- Status: fixed (2026-09-29, the same day — all four items re-stated on the Google compute server. Opened when R1.1 C-1/C-2 changed the tick generator, [[GAP-P12D-91]] and [[GAP-P12D-90]]; R1-D12 requires the re-statement)
- Area: `tests/backtest/oracle.py` `RUNGS`, `scripts/falsify_engine.py`, `scripts/cost_stress_ladder.py`, every recorded synthetic run under `data/validation/`
- Description:
  - **Already re-stated by the change itself** (they run in the suite and are green on the new market): the oracle control, the coarse oracle ladder (`COARSE_RUNGS` 0.20 / 0.22), and the leakage suite.
  - **Still owed, in order:**
    1. ~~**`oracle.RUNGS`**~~ **DONE 2026-09-29.**
       - The old 0.42 / 0.46 were calibrated on the OLD falsification tape, plan(60, 30, 25), 20 s ticks, EUR_USD + USD_JPY.
       - Re-calibrated on the committed generator on the Google compute server: the perfect oracle grades PF 1.853; 0.14→1.522, 0.15→1.505, 0.16→1.468, 0.17→1.446, **0.18→1.414 (every clause met)**, **0.19→1.398 (refused by PF alone)**, 0.20→1.387, 0.22→1.377.
       - RUNGS = 0.18 / 0.19.
    2. ~~**[[GAP-P12D-49]]'s cost-stress ladder**~~ **DONE 2026-09-29** (1 h 20 min on 16 vCPUs, against ~10.5 h on the laptop). The verdict holds, ~98% direction; the attribution changed: no module captures the edge. See GAP-P12D-49's re-statement.
    3. ~~**The full `falsify_engine.py` run**~~ **DONE 2026-09-29.** Stage 1 passes at full scale; the engine fails planted. See [[GAP-P12D-31]] and [[GAP-P12D-28]].
    4. ~~**The attribution verdicts**~~ **DONE 2026-09-29**, from the per-strategy blocks of the same runs. [[GAP-P12D-40]]'s MEAN_REVERSION ranking stays superseded: MR is −0.31 on 38 trades.
  - **Where to run them:** these are the long runs the laptop's power cuts kill ([[GAP-P12D-76]]). They are the first candidate job for the Google Cloud compute server (TODO ☁ TWO-CLOUD block), once the owner has signed Google Cloud in.
- Justification: open. Nothing reads these verdicts for a decision yet: the engine's strategy layer is being replaced under R-1. But GAP-P12D-49 is cited in the read path as the engine's standing verdict, so it stays marked "made on the old market" until (2) lands.
- Proof: `data/validation/cost_stress/20260929T114406Z-gce/` and `data/validation/falsification/20260929T114406Z-gce/` (the JSON reports; the engine stores and both logs are in `gs://acis-compute-0929-data/runs/20260929/`); `test_the_harness_passes_a_rung_just_above_the_cut_offs_and_refuses_one_just_below`, `test_the_planted_oracle_clears_every_non_dsr_clause_at_full_fold_scale`.
- Residual: GAP-P12D-49 — the ladder verdict and its attribution; GAP-P12D-31 — the engine failing the planted market. Both are open and own what the re-statement found.
- Linked: [[GAP-P12D-90]], [[GAP-P12D-91]], [[GAP-P12D-49]], [[GAP-P12D-28]], [[GAP-P12D-76]]

## GAP-P12D-123: the low-to-medium batch from the R1 dual audit — twelve clarifications, one disposition each
- Severity: low · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.1–R1.6, one item per disposition] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS_SPEC.md v2.21, ACIS-04 v1.3, ACIS-09 v1.7, OOS_VALIDATION.md, the ACIS-00 index
- Description: the dispositions, each with its finding:
  - **I9:** rung 2 requires the practice mode ([[GAP-P12D-69]]).
  - **I11:** a pair family is refused while either leg is capped.
  - **I14:** the "stricter meanwhile" wording becomes "the as-built v2.20 path", with its axes listed, and no R1.x phase lands before the rules it assumes.
  - **I15:** one lot rule: round the target toward zero, then order = target − current, in RSIM and C-EXE-6 alike.
  - **I16:** no per-fold embargo for fixed families; `train_window` is amended.
  - **I17:** the C9-per-member and plateau conventions are defined.
  - **I18:** the held-out draw's spelling is pinned ("XCU/USD" style, verified by the lead).
  - **I19:** read-path residue: ACIS-11's registry against the look register, ACIS-00 invariant 7 and the ACIS-11 row, the OOS_VALIDATION DSR mark, C-BT-8, master §10, "minimum size" and "freezes scaling".
  - **E14:** the news prong points to [[GAP-P12D-58]]/[[GAP-P12D-03]].
  - **E15:** IDM = √N_eff, with the 2.5 caps.
  - **E16:** rung 3's expected horizon is recorded.
  - **E17 + E18:** a swap charge calendar in C8, and the minimum lot and step read from the platform, dated.
- Justification: open. Disposition: the correction pass C15, pending the owner's go. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]]

## GAP-P12D-122: the trend family's forecast-scalar source is not chosen — null-fixed scalars run ~24% above Carver's published ones
- Severity: low-medium · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.3 (provenance record)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master v2.21 §5.6 ("fixed before any real-data look"), the TREND family's provenance record
- Description: PLAN_R1's null-fixed 4.66/3.26/2.28 against Carver's 3.75/2.65/1.87 (pysystemtrade `futuresconfig.yaml`, archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E12). The (scalar, normaliser, EWMA convention) triple is not pinned.
- Justification: open. Disposition: D-f recommendation: Carver's published values with his normaliser and span convention. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]], [[GAP-P12D-110]]

## GAP-P12D-121: stage A's Sharpe bound ignores autocorrelation — size 6.3–7.2% at lag-1 ρ of 0.05–0.10 (Lo 2002)
- Severity: low-medium · Likelihood: medium
- Status: open [impl — spec corrected v2.22; build R1.4] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 stage A
- Description: SR̂ > z/√Y holds its size under fat tails and GARCH, but not under serial correlation (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E11, seeded).
- Justification: open. Disposition: C14: a HAC (Newey–West) or Lo-corrected standard error. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-111]], [[GAP-P12D-103]]

## GAP-P12D-120: max-t over the declared grid does not say how the null of the maximum is obtained
- Severity: medium-low · Likelihood: medium
- Status: open [impl — spec corrected v2.22; build R1.4] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 (explored families)
- Description: White (2000) needs a dependent-data bootstrap; independent-normal critical values or an i.i.d. bootstrap are wrong for correlated daily series (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E10).
- Justification: open. Disposition: C13: a stationary bootstrap of the members jointly, recentred (White; Romano–Wolf), with the block length pre-registered. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]]

## GAP-P12D-119: PBO ≤ 0.20 is four times looser than the cited paper's customary 0.05, and undeclared
- Severity: medium-low · Likelihood: medium
- Status: open [impl — spec corrected v2.22; build R1.4] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 (explored families)
- Description: Bailey–Borwein–López de Prado–Zhu (2015) §3.1: reject when PBO > 0.05 (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E9).
- Justification: open. Disposition: C12: a declared deviation (max-t carries the α; PBO is a secondary kill), with S = 16 pinned. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]]

## GAP-P12D-118: the no-trade buffer is defined two incompatible ways, and needs portfolio state AGON lacks
- Severity: medium · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.6 (the Governor's band)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master §2 row, §5.5, CLAUDE.md rule 5, ACIS-04 C-ALP-4
- Description: a dead zone around a zero forecast (§2, rule 5) against a band around the current position (§5.5, Carver). Under the first, an open position is KEPT when forecasts cancel (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I10, archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E8).
- Justification: open. Disposition: C11: Carver's band around the current position, owned by the Governor. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]]

## GAP-P12D-117: the synthetic-lab law has two holes — the variance match names no horizon, and the ±1-sign null has zero edge only in log units
- Severity: medium-high · Likelihood: certain
- Status: fixed (2026-09-29 — both holes closed in the tick generator AND in the daily-first lab, R1.1 C-3, built the same day. First raised 2026-09-25 by the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-12, tests/backtest/synthetic_market.py
- Description: the confounded generator passes "1 ± 0.05" at its 20 s step (1.023) while its daily ratio is 14.7; and exp-built prices give a long-biased rule σ²/2 a day (SR +0.31 at NATGAS-like volatility) (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E3, E7, seeded).
- Justification: mitigated. Disposition: C10: match at the decision horizon by construction; flip arithmetic increments, or add antithetic paths; add a price-unit null test. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs.
  - **Built 2026-09-29 in the tick generator:**
    - the match is at `match_seconds`, the graded rule's decision horizon, by construction (see [[GAP-P12D-90]]);
    - every kind's prices COMPOUND SIMPLE RETURNS: the zero-mean draw is the simple return r, and mid_k = mid_(k-1)·(1 + r_k). So E[Δmid | the past] = 0, the permuted null's sign flips act on arithmetic increments, and neither null pays a long bias in price units, the units the harness books. (The first cut, the same day, was additive: first · (1 + running sum). It could cross zero at high volatility, so it was replaced before any daily lab was built on it; one law now serves both generators);
    - the log-unit drift is then −σ²/2 a unit time: a declared deviation, ~1e-5 a day at FX volatility, in units nothing grades;
    - a simple return ≤ −1 is refused, never floored.
  - **For the daily lab (C-3):** R1-C's prototype builds the mid as the exponential of the cumulative return, which is exactly this hole. It takes the same compounded-simple-return law, which stays positive at any volatility the lab uses.
- Proof: `test_prices_compound_simple_returns_so_a_long_bias_earns_nothing_in_price_units` (the identity mid_k = mid_(k-1)·(1 + r_k); a buy-and-hold's price P&L centres on 0 over 2,000 paths at 2% daily vol; the same draws built as exp(Σ) earn σ²T/2 more, at t > 10), `test_a_simple_return_at_or_below_minus_one_is_refused`, `test_planted_matches_the_null_variance_exactly_at_the_decision_horizon`. The first cut's tests are former `test_prices_are_arithmetic_so_a_long_bias_earns_nothing_in_price_units` and former `test_a_path_that_would_cross_zero_is_refused`.
- Residual: none — the daily lab (`tests/backtest/lab_market.py`) takes the same law: prices compound the zero-mean simple return; the planted market's MODEL variance of y over the decision horizon (one weekday) equals the null's by construction (scale² · (Var m + other) = other, common random numbers); the permuted control flips whole days' arithmetic increments. Proof there: `test_planted_is_the_nulls_noise_plus_the_drift_times_one_exact_scale`, `test_a_long_bias_earns_nothing_in_price_units_on_either_null` (the same draws built as exp(sum r), R1-C's prototype law, earn the convexity at t > 10), `test_permuting_keeps_every_day_and_its_cross_section_and_is_a_martingale`.
- Linked: [[GAP-P12D-90]], [[GAP-P12D-91]], [[GAP-P12D-103]], [[GAP-P12D-124]]

## GAP-P12D-116: the TREND family's "MOP-2012 12-month sign" baseline points to a 3-horizon SPOT vote, not MOP's 12-month EXCESS-return sign
- Severity: medium · Likelihood: certain
- Status: open [impl — spec corrected v2.22; build R1.3 (the faithful MOP member)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master v2.21 §5.6, ACIS-04 v1.3 §6.6, core/signals/canonical.py, GAP-0073
- Description: MOP 2012 signs the 12-month excess return (eq. 5; App. A.3). On the repo's rates, spot and excess 12-month signs disagree on 3.0–12.1% of days across FX pairs, 2013–2025. So GAP-0073's "immaterial" is false (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E6).
- Justification: open. Disposition: C9: a faithful excess-return member; the 3-horizon vote stays a separate member; GAP-0073 re-opened. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-71]], [[GAP-P12D-103]]

## GAP-P12D-115: the "cost ≤ ⅓ of pre-cost Sharpe" filter is attributed to Carver but departs from his speed limit twice
- Severity: medium · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.3 (cost filters)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master v2.21 §5.6, ACIS-09 v1.7 stage A
- Description: Carver caps TURNOVER cost at ~0.13 SR units against a fixed expected Sharpe. The spec adds swap, which is mostly carry return for FX, and stage A uses a REALISED per-instrument Sharpe: an unregistered look (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E5).
- Justification: open. Disposition: D-g recommendation: Carver's pinned turnover cap plus a separate swap-markup viability filter against a fixed expectation. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-93]], [[GAP-P12D-103]]

## GAP-P12D-114: stage C's residualised held-out kill fires on ~31% of real factor-borne edges, as often as on noise
- Severity: medium · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.4 (stage C)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 stage C, OOS_VALIDATION.md held-out set
- Description: a zero residual alpha gives t ~ N(0,1), so P(t < −0.5) = 0.309 (verified by the lead). The worst case kills an SR-0.5 edge ~39% of the time. Three picks near-duplicate explored instruments (USOIL/UKOIL, US100/US500, GER40/EU50) (archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E4).
- Justification: open. Disposition: D-e recommendation: grade the held-out set RAW, still kill-only; keep the frozen draw. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-97]], [[GAP-P12D-103]]

## GAP-P12D-113: the spec retires things "at R1.7", a phase defined only in PLAN_R1 — whose list also retires unamended master laws
- Severity: medium-high · Likelihood: low-medium
- Status: fixed (2026-09-25 — master v2.22 §5 and ACIS-03 v2.1 replace "R1.7" with an explicit retirement list; marginal alpha, the fragmenter, C4 and the legacy modules retire only by their own master amendment)
- Area: ACIS_SPEC.md v2.21 §5, ACIS-03 v2.0 §1
- Description: PLAN_R1's R1.7 also retires marginal-alpha (§6's mandatory scale-down floor), the fragmenter, C4 and MR/SCALP/PAIR, none of which v2.21 amended (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I8).
- Justification: open. Disposition: C8: an explicit retirement list in the spec; everything else retires only by its own amendment. Nothing is applied before the owner's go on the triage; the as-built v2.20 behaviour stands meanwhile.
- Proof: master §5 v2.22 (ACIS_SPEC.md), ACIS-03 v2.1 §1.
- Residual: GAP-P12D-107 — the staging mechanism must be re-homed before any retirement lands.
- Linked: [[GAP-P12D-107]], [[GAP-P12D-103]]

## GAP-P12D-112: the family verdict grades the research universe, but §14 and C-BT-7 still require a per-account grade
- Severity: medium-high · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.4 (per-account re-grade)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master §14 (per-account paragraph), ACIS-09 C-BT-7, C-BT-11 v2
- Description: the validated portfolio (23 instruments, its IDM) is not what a small account can hold (GAP-P12D-101), so "the graded book is the tradeable book" is false (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I7).
- Justification: open. Disposition: C7: rung 1 also requires a per-account re-grade on the live-eligible universe with the account's rules active. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-101]], [[GAP-P12D-103]]

## GAP-P12D-111: stage A controls family-wise error at ~2α, not α; its looks go unadjusted; and α restarts every quarter
- Severity: high · Likelihood: certain
- Status: open [impl — spec corrected v2.22; build R1.4 (verdict module)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 stage A
- Description: a fixed-sequence chain plus a parallel Holm set, each at α, gives FWER 0.081–0.096 (seeded; ≈ 0.0975 for independent sets, lead arithmetic). "≤ 3 looks per family" has no correction. The quarterly stream has no lifetime budget (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I13, archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E2, FDA Multiple Endpoints guidance 2022 §§5, 7).
- Justification: open. Disposition: C6: serial gatekeeping, a declared look budget k at α/k, and the order registered before any look; D-d (recommended: α-spending, 0.03 then half the remainder). APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-102]], [[GAP-P12D-121]], [[GAP-P12D-103]]

## GAP-P12D-110: the stage-D forward bettors are mis-specified — E2 mixes a Sharpe with a return, σ* has no unit, and the clip contradicts "never clipped"
- Severity: medium-high · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.4 (e-process module)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 stage D; master §14 rung 2
- Description: a literal E2 kills every family within days (200/200 at a true SR of 0.6). With an annual σ*, E1 never certifies. And "E2 silent ≥ 3 months" is met by 99.8% of dead strategies. PLAN_R1's "25% killed by 1 year" is the FREEZE figure (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I6, archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md E1, E13; the units verified by the lead).
- Justification: open. Disposition: C5: σ* daily; μ_claim = (SR̂_dev/2)·σ*; a tripwire sets W := 0 permanently; E2's weakness stated. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-103]]

## GAP-P12D-109: §4's "NVMA's one effect on trading is the veto" contradicts §6's regime sizing factor, C4, §3.6 and ACIS-02 — built literally, it is an unannounced size-UP
- Severity: high · Likelihood: high
- Status: fixed (2026-09-25 — §4 narrowed in master v2.22 (ACIS_SPEC.md §4) and ACIS-02 v1.4; owner decision D-b: the §6 regime sizing factor STAYS. The as-built sizing already keeps it, so no code changes)
- Area: ACIS_SPEC.md v2.21 §4, §6, §5.5 C4, §3.6; ACIS-02 step 8 and C-REG-6; core/governor/capital_governor.py:292-303
- Description: removing `regime_f` (verified in sizing by the lead) multiplies orders by 1/regime_f (3.3× at stability 0.5, confidence 0.6). "Every trigger stays" is false: the no-params trigger was REPLACED by the A4 row (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I5).
- Justification: open. Disposition: C4: narrow §4 and amend ACIS-02; D-b recommendation: keep `regime_f` until the position policy and NAV-relative sizing ([[GAP-P12D-61]]). Nothing is applied before the owner's go on the triage; the as-built v2.20 behaviour stands meanwhile.
- Proof: master §4 v2.22 (ACIS_SPEC.md), ACIS-02 v1.4 step 8 and C-REG-6; `core/governor/capital_governor.py` keeps `regime_f` unchanged.
- Residual: none — the spec now matches the as-built sizing, and any future removal of `regime_f` is a size increase that needs its own owner ruling.
- Linked: [[GAP-P12D-61]], [[GAP-P12D-103]]

## GAP-P12D-108: the staging rule plus continuous target positions is a permanent promotion deadlock
- Severity: medium · Likelihood: high
- Status: open [impl — spec corrected v2.22; build R1.6 (flatten-then-promote)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master §5 C1/C2, ACIS-03 §7–§8, `param_library.py` `PositionGate`
- Description: promotion needs a flat book, and a pooled trend book is essentially never flat. §5.7's per-strategy demotion is undefined under netting (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I12).
- Justification: open. Disposition: D-c recommendation: keep the law; promote by a staged flatten-then-promote at a valid session boundary. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-107]], [[GAP-P12D-103]]

## GAP-P12D-107: the staging rule is "unchanged", but its only implementation is on the retirement list
- Severity: high · Likelihood: medium
- Status: open [impl — spec corrected v2.22; build before any retirement (re-home the staging mechanism)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-03 v2.0 §1, core/optimizer/param_library.py, core/signals/provenance.py:22
- Description: `PromotionForbiddenError`, `PositionGate` and stage/promote/on_boundary live in `param_library.py`, which "the ParamLibrary staging" retires. `provenance.py:22` imports the error (verified by the lead). The §13 staging test is QIEA-bound (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I4).
- Justification: open. Disposition: C3: re-home the mechanism as the rule registry's staging; carve §7–§8 and C1/C2 out of "legacy"; move the import before any retirement. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-99]], [[GAP-P12D-113]], [[GAP-P12D-103]]

## GAP-P12D-106: "validated", the predicate of the new `tradeable=False` trigger, is defined nowhere
- Severity: high · Likelihood: high
- Status: open [impl — spec corrected v2.22; build the practice mode (GAP-P12D-69) and the Governor's minimum-size cap] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master §2 row (A4), ACIS-03 v2.0, CLAUDE.md rule 5
- Description: read as rung 1, an LLM-originated family can never trade, so it can never build the forward record stage D needs. Read loosely, the veto is vacuous. Today's demo trades QIEA sets nobody validated (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I3).
- Justification: open. Disposition: D-a recommendation: rung 1 in live mode; a registered family whose machinery passed B0 may trade at minimum size in paper/practice mode. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-69]], [[GAP-P12D-103]]

## GAP-P12D-105: the applied claim ladder dropped B0, "machinery proven first", which the ratified A6 draft required
- Severity: high · Likelihood: medium
- Status: mitigated (2026-09-29 — the B0 MACHINERY is built, R1.1: `tests/backtest/lab_calibration.py` measures a detector's null false-detect rate and planted power against theory on the daily lab; not yet wired into the verdict, R1.4. Raised 2026-09-25 by the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: master v2.21 §14 rung 1, ACIS-09 C-BT-11 v2
- Description: R1_LEAD_REVIEW's ratified A6 made rung 1 = B0–B5. The applied text has no lab-calibration precondition, which is the GAP-P12D-37 class: a grader that is itself wrong (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I2).
- Justification: mitigated. Disposition: C2: restore B0 as a precondition of any real-data verdict. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Built 2026-09-29 (the Google compute server; 400 paths of 2.8 graded years, EWMAC 16/64 pooled over 20 instruments):
  - **B0 (a) and (b) HOLD on the lab:** planted detection **37.8%** against a theory power of 39.8% (pooled theory Sharpe 0.828, within 2 se); null false-detect **5.5%** (limit alpha + 2 se = 7.2%).
  - **The check has power:** the same paths demeaned per instrument (GAP-P12D-91's defect) detect the planted trend at **18.2%** and B0 refuses them; a detector that always finds an edge is refused on its false-detect rate.
  - **Where the rest of B0 lives:** (c) a leaky oracle refused by structure is the leakage suite ([[GAP-P12D-65]]); (e) planted variance-matched to its null is pinned in both generators ([[GAP-P12D-90]], [[GAP-P12D-117]]); (d) the research simulator equal to the engine on lab tapes needs RSIM (R1.3) and the engine reconciliation (R1.6).
  - **The detector is a placeholder:** the plain one-sided t-test. R1.4's stage-A HAC bound ([[GAP-P12D-121]]) must pass through `calibrate` before it binds.
- Proof: `test_b0_holds_on_the_lab_detection_at_theory_power_and_the_null_at_alpha`, `test_b0_fails_on_a_bridged_lab_its_power_is_lost`, `test_b0_fails_a_detector_that_always_finds_an_edge`, `test_the_verdict_arithmetic_is_binomial`.
- Residual: GAP-P12D-105 — still owns wiring B0 into `passed` (R1.4) with all five conditions at the same `recon_commit`, including (d), which waits on R1.3/R1.6.
- Linked: [[GAP-P12D-37]], [[GAP-P12D-103]]

## GAP-P12D-104: C-BT-11 v2 redefines `passed`, the field the live gate reads, without the §14 Max DD/SPX gates or C-BT-2/4/7
- Severity: high · Likelihood: medium
- Status: open [impl — spec corrected v2.22; build R1.4 (verdict module; `report.py`, `mode.py`)] (2026-09-25 — from the dual audit of master v2.21; triage in R1_AUDIT_TRIAGE_2026-09-25.md)
- Area: ACIS-09 v1.7 C-BT-11 v2 and its live-gate paragraph; ACIS-08; monitoring/mode.py
- Description: a built verdict would pass a 30% drawdown or a guardrail-hash mismatch to the human token (the live gate reads `passed`: ACIS-09's live-gate paragraph, `mode.py`, verified by the lead). A2 ratified replacing only the DSR clause (archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md I1).
- Justification: open. Disposition: C1: `passed` = the verdict AND §14 gates AND C-BT-2/4/7; the live gate reads rung 2. APPLIED to the spec: the owner ratified the triage 2026-09-25 ("Ratify all"); the spec is corrected in master v2.22 and the deep specs. The build is owed; the as-built v2.20 behaviour stands until it lands.
- Linked: [[GAP-P12D-96]], [[GAP-P12D-103]]

## GAP-P12D-103: the dual audit of the applied R1 amendments (master v2.21, commit 271d8e0)
- Severity: high · Likelihood: high
- Status: fixed (2026-09-25 — both lenses' 37 findings TRIAGED in R1_AUDIT_TRIAGE_2026-09-25.md and RATIFIED by the owner ("Ratify all"); corrections C1–C15 and decisions D-a..D-g APPLIED as master v2.22, ACIS-02 v1.4, ACIS-03 v2.1, ACIS-04 v1.4, ACIS-08 v1.3, ACIS-09 v1.8, ACIS-11 v1.2, OOS_VALIDATION.md and CLAUDE.md rule 5)
- Area: ACIS_SPEC.md v2.21 (§2, §4, §5, §5.5, §14), specs/ACIS-03 v2.0, ACIS-04 v1.3, ACIS-09 v1.7 (C-BT-11 v2, C-BT-12), OOS_VALIDATION.md, CLAUDE.md rule 5
- Description: the guard VALUES are untouched (no `config/` change; master §6–§9.5 byte-identical; the confidence veto kept). But the applied text fails three of its own claims. The findings, verified by the lead where marked:
  - **I1 (high, verified):** C-BT-11 v2 defines `passed` as stages A–C only, while ACIS-09's live gate and `monitoring/mode.py` read `passed`. So a built verdict would pass a 30% drawdown, or a guardrail-hash mismatch, to the human token. A2 ratified replacing only the DSR clause.
  - **I2 (high):** the ratified A6 made rung 1 = B0–B5, but the applied text dropped B0 ("machinery proven first": the lab calibration).
  - **I3 (high):** "validated", the new `tradeable=False` trigger's predicate, is defined nowhere. Read as rung 1, an LLM-originated family can never trade, so it can never earn the forward record stage D needs; and the as-built demo trades unvalidated sets.
  - **I4 (high, verified):** the staging rule is "unchanged", but its only implementation (`param_library.py`: `PromotionForbiddenError`, `PositionGate`, stage/promote/on_boundary) is on the retirement list. `core/signals/provenance.py:22` imports it.
  - **I5 (high, verified):** §4's "NVMA's one effect on trading is the veto" contradicts the unamended §6 regime sizing factor (`capital_governor.py:292-303`), C4, §3.6 and ACIS-02. Built literally, it is an unannounced size-UP (1/regime_f). One trigger (no params for the regime) was REPLACED, not kept.
  - **I6 (medium-high, verified):** the stage-D bettors are mis-specified. E2 subtracts a Sharpe ratio from a return; σ* has no units; the clip contradicts "never clipped"; and "E2 silent ≥ 3 months" is met by 99.8% of dead strategies. PLAN_R1's "25% killed by 1 year" is the FREEZE figure.
  - **I7 (medium-high):** the family verdict on the research universe is not the per-account grade §14/C-BT-7 still require.
  - **I8 (medium-high):** "R1.7" is defined only in PLAN_R1, whose list also retires marginal-alpha, the fragmenter and C4, which v2.21 never amended.
  - **I9–I14 (medium):**
    - I9: rung 2 needs the practice mode ([[GAP-P12D-69]]);
    - I10: two incompatible no-trade buffers, and the buffer needs portfolio state AGON lacks;
    - I11: netting plus the cap leaves a pair leg alone;
    - I12: staging plus continuous positions means promotion never happens;
    - I13: stage A's α split, its look correction and the registration of the order are unstated (union FWER ≈ 0.098);
    - I14: "stricter meanwhile" is false as a universal claim.
  - **I15–I19 (low to low-medium):**
    - I15: rounding positions vs rounding orders;
    - I16: the embargo and config do not fit a fixed family;
    - I17: C9 per member and the fixed-family plateau check are uncomputable as written;
    - F18 (verified): the held-out draw reproduces only with slash spellings ("XCU/USD");
    - I19: read-path residue.
- Justification: open until the triage is applied. Triage (R1_AUDIT_TRIAGE_2026-09-25.md) is written; originally: one consolidated correction pass restoring the ratified intent (tightening), plus owner decisions for I3 (what "validated" means per mode), I5 (whether regime_f leaves sizing, a size-up) and I12 (promotion under netting; the staging rule is law). Until then, no R1.x build starts, and the as-built v2.20 behaviour stands.
- Proof: master v2.22 changelog (ACIS_SPEC.md), ACIS-09 v1.8 C-BT-11 v2 and C-BT-12, `test_spec_constants` still green.
- Residual: GAP-P12D-104..123 — each owns its build (open [impl]); GAP-P12D-109 and GAP-P12D-113 are fixed in the spec.
- Linked: [[GAP-P12D-89]], [[GAP-P12D-96]], [[GAP-P12D-101]], [[GAP-P12D-102]], [[GAP-P12D-69]]

## GAP-P12D-102: even swap-free, the R1 flagship family (pooled trend, "D1") most likely fails the plan's own development bar
- Severity: high · Likelihood: high
- Status: open [impl — RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: ACIS-09 v1.7 C-BT-11 v2 stage A is fixed-sequence; built with the verdict module, R1.4] (2026-09-25 — found by the lead reviewing PLAN_R1; `archive/r1_lead_probes/d1_power.py` → `.out`)
- Area: PLAN_R1 §6 B2 and its A2 (C-BT-11 v2); the testing procedure of stage A
- Description: PLAN_R1 estimates D1's net portfolio Sharpe at +0.32..+0.79 swap-free (−0.15..+0.32 at FTMO's swaps). Its own stage-A bar is SR̂ > 0.81 (Holm, K ≤ 10, Y = 10), or 0.74 at K = 5. With the plan's own se = 1/√Y, D1 passes 6% / 21% / 47% of the time at the low / mid / high swap-free estimate, and 1% at FTMO swaps. A pre-registered fixed-sequence order (D1 first, at the full α; the next family only if it passes) controls family-wise error exactly as Holm does and lowers D1's bar to 0.50 at Y = 11 (fixed families need no 2-year burn-in): 28% / 58% / 84%.
- Justification: open. Recommendation in R1_LEAD_REVIEW_2026-09-25.md §2 X2 and A2: fixed-sequence for the first cycle; Holm only among families outside the order. The owner rules with A2.
- Linked: [[GAP-P12D-89]], [[GAP-P12D-94]], [[GAP-P12D-67]]

## GAP-P12D-101: the R1 plan never models the venue's minimum lot — at the owner's account size most of its breadth cannot be held
- Severity: high · Likelihood: certain
- Status: open [impl — R1-D14 RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: lot rounding in master v2.21 §5 C8 and the live-eligibility rule in OOS_VALIDATION.md; the account size / vol target is decided WITH R1-D9 at the first real-data look] (2026-09-25 — found by the lead; `archive/r1_lead_probes/lot_granularity.py` → `.out`, FTMO contract sizes from `archive/r1_lead_probes/ftmo_symbols_2026-09-25.json`; the 0.01-lot minimum is an ASSUMPTION, since the JSON carries no min-volume field)
- Area: PLAN_R1 A3/A5 (breadth, IDM ≈ 2.4–2.5, N_eff ≈ 6), the research simulator (RSIM), ACIS-06 C-EXE-6 lot rounding, [[GAP-P12D-61]]
- Description: Carver sizing (capital × vol target × weight × IDM) with ACIS's round-down to lot steps, class-equal weights over the 23 explored instruments:
  - at $6,000 and a 10% vol target, 15 of 23 can NEVER hold one minimum lot (all 13 FX pairs, gold, silver);
  - at $10,000 and 10%, 6 FX pairs never can, and the rest only at |forecast| ≥ 13–20, i.e. mostly flat;
  - at $10,000 and 20%, or $25,000 and 10%, all can.

  The instruments fine-grained enough to hold are the index CFDs, which carry FTMO's HIGHEST swap markups (3.6–5%/yr). So the swap regime and the account size are one decision. And unless RSIM rounds to lot steps exactly as execution does, the graded book is not the tradeable book (the GAP-P12D-36 class), and B4 fails by construction.
- Justification: open. (1) [impl] RSIM must round exactly as C-EXE-6 does. (2) [spec, A5] an instrument is live-eligible on an account only if one minimum lot is ≤ its risk budget at |forecast| = 10 there. (3) [owner, R1-D14] account size and vol target are decided with R1-D9, at the first real-data look.
- Linked: [[GAP-P12D-94]], [[GAP-P12D-57]], [[GAP-P12D-61]], [[GAP-P12D-102]]

## GAP-P12D-100: a pooled rule must be graded on its portfolio daily series — the stacked instrument × day panel passes a zero-edge rule 9.5–32% of the time
- Severity: high · Likelihood: medium
- Status: open [impl] (2026-09-25 — from PLAN_R1 §9 #12, R1-A simulation; not re-run by the local lead)
- Area: the verdict module (PLAN_R1 R1.4), C-BT-11 v2 (A2)
- Description: pooling instruments into one panel and testing the stacked instrument-days treats correlated observations as independent. R1-A measured 9.5–32% false passes on a zero-edge rule, against 3.8–6.0% for the portfolio daily series.
- Justification: open; built with the verdict module, pinned by a lab test that the panel form is never the graded unit.
- Linked: [[GAP-P12D-89]], [[GAP-P12D-98]]

## GAP-P12D-99: `core/signals/indicators.py` imports its indicators from `core/optimizer/fitness.py` — they must move before QIEA can be retired
- Severity: low · Likelihood: certain
- Status: open [impl] (2026-09-25 — from PLAN_R1 §9 #11; verified by the lead at `core/signals/indicators.py:16`)
- Area: core/signals/indicators.py, core/optimizer/fitness.py (`atr_series`, `ema_series`, `rsi_series`)
- Description: the signal layer re-exports three indicator functions defined in the optimizer's fitness module. Retiring `fitness.py` (PLAN_R1 A4 / R1.7) would break the signal layer unless they move first.
- Justification: open; a pure move, behaviour-identical, proven by the existing indicator tests. It needs no ratification.
- Linked: [[GAP-P12D-89]]

## GAP-P12D-98: the look register stores per-trade returns, not the daily net-return vector a portfolio-level verdict needs
- Severity: high · Likelihood: certain
- Status: open [impl] (2026-09-25 — from PLAN_R1 §9 #10; after merge 3 each grade records its outcome with per-trade returns, which is not enough for daily-series tests)
- Area: tests/backtest/look_register.py (`record_outcome`), the verdict module
- Description: search-aware tests over the register (Holm or fixed-sequence on family portfolio series, SPA/StepM, CPCV/PBO for explored families) need each registered run's DAILY portfolio net-return vector, content-addressed. The register now keeps pass fields and per-trade returns only. It also lacks the declared-search-space hash, origin + model cutoff, cost-map hash and universe id that PLAN_R1 R1.2 lists.
- Justification: open; additive fields, tightening only, no ratification needed.
- Linked: [[GAP-P12D-64]], [[GAP-P12D-89]], [[GAP-P12D-100]]

## GAP-P12D-97: the holdout kill at SR̂ < 0 wrongly kills 18–32% of real edges
- Severity: medium · Likelihood: high
- Status: open [impl — RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: ACIS-09 v1.7 C-BT-11 v2 stage C kills at t < −0.5] (2026-09-25 — from PLAN_R1 §9 #9, R1-A simulation; not re-run by the local lead)
- Area: the kill rule for the held-out instruments and the 2024–25 holdout (VALIDATOR K4)
- Description: with two years of holdout, a true edge frequently shows a negative sample Sharpe. Killing at SR̂ < 0 throws away 18–32% of real edges; killing at t < −0.5 keeps the kill's power against false claims while sparing most real ones.
- Justification: open; decided with A2 (R1-D2).
- Linked: [[GAP-P12D-89]]

## GAP-P12D-96: §14's trade-shape rows fail any daily-horizon rule whatever its edge
- Severity: high · Likelihood: certain
- Status: open [impl — R1-D7 RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: master v2.21 §14 is the claim ladder; `report.py` keeps the stricter v2.20 rows until the verdict module lands, R1.4] (2026-09-25 — from PLAN_R1 §9 #8, a planted SR 0.87 daily rule: win rate 0.18, average hold 53.5 days, positive months 52%, re-run by the cloud lead)
- Area: master §14 (ACIS_SPEC.md:361-367), tests/backtest/report.py (`WIN_RATE_MIN`, `POSITIVE_MONTHS_MIN_PCT`, `DURATION_*`)
- Description: win rate > 48%, positive months > 70% and a 30 min–48 h average hold exclude every slow rule by construction, and "win rate > 48%" contradicts §5.6's own "trend-following wins ~35–48%" (ACIS_SPEC.md:213). An annual Sharpe > 1.5 cannot be certified on 12 years of history for any plausible edge.
- Justification: open. It LOOSENS the live gate (`report.py:30-31`: "loosening is a master-spec change"), so it is owner-only, never delegated. The draft is A6 in R1_LEAD_REVIEW_2026-09-25.md.
- Linked: [[GAP-P12D-37]], [[GAP-P12D-89]]

## GAP-P12D-95: the execution clock — a 17:00 New York rebalance breaks FTMO's gap rule on Fridays, falls inside the index, metal and oil break, and buys the day's worst FX spread
- Severity: high · Likelihood: certain
- Status: open [impl] (2026-09-25 — from PLAN_R1 §9 #7, FTMO's own trading hours (a); the spread half found by the lead, `archive/r1_lead_probes/rollover_spread.py` → `.out`)
- Area: the runtime's execution scheduling, the research simulator's calendar, [[GAP-P12D-58]]
- Description: FTMO forbids opening trades ≤ 2 h before a ≥ 2 h closure, so a Friday 17:00 New York rebalance is forbidden, and at 17:00 New York indices, metals and oil are inside their 20:50–22:05 UTC break. The plan's fix executes FX at 17:05 New York. But that is the rollover: on Dukascopy ticks (Jan–Feb 2019, spreads only) EUR/USD's median spread is 2.2 pips at 17:05–17:10 against 0.3 over the London/New York day, and USD/JPY 1.7 against 0.3. Master §13 already uses this spike as a clock mark (ACIS_SPEC.md:355).
- Justification: open. Decide on the 17:00 New York close; execute each symbol in a liquid hour outside the rollover window and every gap-rule window (e.g. FX 03:00–11:00 New York); pre-registered per symbol, in RSIM and the runtime alike.
- Linked: [[GAP-P12D-58]], [[GAP-P12D-94]]

## GAP-P12D-94: at FTMO's published swaps a pooled slow-trend book is marginal-to-negative — the account's swap regime is an owner decision
- Severity: high · Likelihood: high
- Status: open [owner decision R1-D9 — RULED 2026-09-25: decide at the first real-data look] (from PLAN_R1 §9 #6, R1-B; the swap table re-fetched and the markup decomposition checked by the lead)
- Area: venue choice, the C8 cost model, the R1 slate's ranking
- Description: net portfolio SR ≈ (s − c)·√N_eff gives −0.15..+0.32 at FTMO's median markup against +0.32..+0.79 swap-free (s = 0.15–0.34 per instrument). Swap is ~10× the trading cost of a medium-speed rule. E8's own help page lists "Swap free option: Yes" for E8 One (Forex) and E8 Pro Forex (Forex, Metals, Energies, Indices, Crypto), grade (a), read 2026-09-25; its +10% price is a search rendering (c). FTMO's own FAQ has no swap-free entry; third parties contradict each other.
- Justification: open by ruling. **OWNER RULING 2026-09-25:** no emails wait on it; the cost model carries both worlds (FTMO's published table, and swap-free) as data ([[GAP-P12D-93]]); the owner picks the venue for slow trend just before the first real-data look, together with the account size ([[GAP-P12D-101]]). Never misrepresent eligibility for a swap-free account.
- Linked: [[GAP-P12D-93]], [[GAP-P12D-101]], [[GAP-P12D-102]], [[GAP-P12D-54]]

## GAP-P12D-93: the C8 financing model charges OANDA's flat 1% admin fee — FTMO's markup is 0.9–2.6%/yr on FX, ~4.8% on gold and 3.6–5.0% on index CFDs, per side
- Severity: high · Likelihood: certain
- Status: open [impl] (2026-09-25 — from PLAN_R1 §9 #5; verified by the lead: `tests/backtest/financing.py:7-11`, and the FTMO table in `archive/r1_lead_probes/ftmo_symbols_2026-09-25.json`)
- Area: tests/backtest/financing.py, tests/backtest/carry.py, the C8 cost model
- Description: the model applies OANDA's published method (tom-next differential minus a 1% fee both sides; gold at an assumed 0.25% lease rate). Against FTMO it under-charges FX by 0.3–1.6 points per side and indices and gold far more, so every slow-rule grade flatters the venue.
- Justification: open. Carry the venue's per-symbol swap table as DATA in C8, both worlds per [[GAP-P12D-94]]'s ruling, with a dated snapshot each time the table is fetched (markups drift; stress ±50%).
- Linked: [[GAP-P12D-94]], [[GAP-P12D-46]], [[GAP-P12D-41]]

## GAP-P12D-92: any intraday refinement of correlated daily bars must bridge the common factor jointly — independent bridges plant a spurious lead-lag/pairs edge (t 6–9)
- Severity: medium · Likelihood: medium
- Status: fixed (2026-09-29, R1.1 C-4: `tests/backtest/lab_intraday.py` bridges one common factor plus one idiosyncratic shock per instrument, each pinned to its own daily endpoint, on the FX day (17:00 New York to 17:00 New York via `core/data/fx_clock`). First raised 2026-09-25 from PLAN_R1 §9 #4, R1-C's own simulation, as a DESIGN constraint on the lab)
- Area: the R1.1 synthetic lab (tick tapes derived from daily factor bars)
- Description: bridging each instrument's day independently decorrelates the intraday path from the common factor, which a pairs or lead-lag rule then harvests as a fake edge (t 6.3–8.6 in R1-C's receipt).
- Justification: open; the lab's C-4 builds one factor bridge plus idiosyncratic bridges, pinned by a no-lead-lag test.
- Proof: `test_joint_bridges_plant_no_lead_lag_edge_and_independent_ones_would` (R1-C's pairs trap, "long i when its correlated j led it so far", on 1,500 days at rho 0.5: joint |t| < 3, while the same days bridged independently show the spurious edge at t > 4), `test_each_days_ticks_sum_to_its_spot_return_on_every_kind`, `test_the_bridge_is_exact_and_a_zero_pinned_day_is_the_old_defect`.
- Residual: none — the lab is the only intraday refinement of correlated daily bars in the repo, and it bridges jointly; the tick generator's instruments are independent, so it holds no common factor to split.
- Linked: [[GAP-P12D-91]]

## GAP-P12D-91: the synthetic null and permuted markets are bridges — every path is demeaned, and two unit tests encode it
- Severity: high · Likelihood: high
- Status: fixed (2026-09-29, R1.1 C-1, built in-session: nothing is demeaned; permuted = shuffle, then an independent ±1 sign per increment drawn after the shuffle from the same RNG, so the noise → schedule → shuffle order and `episode_sign` are untouched. The two tests that encoded the bridge were rewritten. First found 2026-09-25, from PLAN_R1 §9 #3: `synthetic_market.py:113-114` subtracted each path's mean)
- Area: tests/backtest/synthetic_market.py, tests/backtest/test_synthetic_market.py
- Description: a demeaned random walk is a Brownian bridge, which mean-reverts by construction: R1-C measured −1.2 / +1.2 pooled SR bias for momentum / reversal at N = 20 on 2.8-year paths (the cloud lead reproduced it). "Demean only the planted drift" re-creates the bridge on the drift component. The fix is "demean nothing", with a random ±1 sign per shuffled return for the permuted kind.
- Justification: open. [impl] with R1-D12: every recorded synthetic verdict (GAP-P12D-49 included) is re-stated after the fix.
- Proof: `test_nothing_is_demeaned_so_net_drift_is_zero_in_expectation_not_pinned_in_the_sample` (200 seeds, no path pinned), `test_the_nulls_are_martingales_and_the_old_bridge_is_caught` (sign(past L)·next return at L = 63/126/252 within 3 se of 0 on null and permuted; the SAME draws demeaned show the bridge at t < −3, so the test has power), `test_permuting_keeps_every_move_and_changes_order_and_sign`.
- Residual: GAP-P12D-124 — re-stating the verdicts recorded on the old market.
- Linked: [[GAP-P12D-90]], [[GAP-P12D-49]], [[GAP-P12D-92]], [[GAP-P12D-124]]

## GAP-P12D-90: the planted positive-control market is ~3.3× the null's daily volatility, with a frictionless oracle Sharpe of ~157 — every recorded synthetic verdict is confounded by it
- Severity: high · Likelihood: certain
- Status: fixed (2026-09-29, in the tick generator, R1.1 C-2; see below) [was: open impl — R1-D12 RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: ACIS-09 v1.7 C-BT-12; built in the lab, R1.1, then every recorded synthetic verdict is re-stated] (2026-09-25 — from PLAN_R1 §9 #2; the lead's own arithmetic from the generator defaults agrees: ~9.6 episodes/day of ~450 ticks at 0.15σ drift → daily ratio ≈ 3.3; oracle 0.15·√(4320·252) ≈ 156.5)
- Area: tests/backtest/synthetic_market.py (`drift_sigma`, `episode_hours`), every falsification and ladder verdict, [[GAP-P12D-49]]
- Description: "planted passes, null fails" can be read off the volatility level and the cost/move ratio alone, not only off the planted drift. The positive control must differ from its null in drift only (variance-matched planting, R1-C C-2).
- Justification: open; R1-D12. It moves recorded runs, so it is ratified before it is applied.
- **Fixed 2026-09-29 (R1.1 C-2, in-session) in the tick generator:**
  - **The drift** is now set from the frictionless oracle's annual Sharpe, `MarketSpec.oracle_sharpe` (default **10**, was ~157). `drift_sigma` became a property, oracle_sharpe/√(252·ticks per day), so the oracle's Sharpe is the same at any tick size.
  - **The match.** planted = scale · (the null's own noise + the scheduled drift). `match_scale` makes the MODEL variance over the decision horizon (`match_seconds`, default one weekday) equal the null's exactly: the noise gives h·σ² and the schedule fixes the drift's block mean square.
  - **Why the model, not the sample.** Matching the SAMPLE's daily mean square exactly was tried first. It feeds sampling noise into the scale: on 21-day paths the tick-horizon ratio then ranged 0.71–1.18 over 8 seeds × 2 instruments, a volatility confound of its own. Under the model match it holds 0.93–0.98 at every path length.
  - **Why 10 (the lead's choice under R1-D12, declared for the R1.1 audits).** The drift's share of the daily variance is ≈ 0.117·(oracle Sharpe/15.9)². At 10 that is ~4.6%, so every horizon from one tick to one day sits within ~7% of the null. At 157 no match is meaningful: matching at a day would make planted ~3.5× quieter than null at a minute.
  - **A consequence worth knowing** (it sharpens [[GAP-P12D-96]]). With episodes shorter than the match horizon, the per-trade Sharpe is bounded by about √(the drift's variance share), whatever the episode length. So a variance-matched positive control has a profit factor only modestly above §14's 1.4 row: the perfect oracle grades PF **1.827** / Sharpe **6.75** on the coarse full-scale tape, and PF crosses 1.4 between 20% and 22% sign errors.
- Proof: `test_planted_matches_the_null_variance_exactly_at_the_decision_horizon`, `test_at_the_default_strength_no_horizon_tells_planted_from_null_by_volatility`, `test_the_oracle_sharpe_sets_the_drift_at_any_tick_size`, `test_only_the_planted_market_carries_the_scheduled_drift`, `test_the_episode_schedule_is_exactly_the_planted_drift`, `test_the_planted_oracle_clears_every_non_dsr_clause_at_full_fold_scale`, `test_the_harness_passes_a_rung_just_above_the_cut_offs_and_refuses_one_just_below` (COARSE_RUNGS re-calibrated to 0.20 / 0.22), `test_the_harness_recognises_the_oracle_on_planted_and_refuses_it_on_null` (now six folds: at oracle 10, fourteen test days gave PSR 0.82).
- Residual: GAP-P12D-124 — the falsification tape's `oracle.RUNGS` re-calibration and the re-statement of every verdict recorded on the old market.
- Linked: [[GAP-P12D-91]], [[GAP-P12D-49]], [[GAP-P12D-37]], [[GAP-P12D-124]]

## GAP-P12D-89: counting runs is not enough under adaptive iteration — search spaces must be declared and hashed before the first look, and families graded as fixed combinations
- Severity: critical · Likelihood: high
- Status: open [impl — R1-D2/D4 RATIFIED 2026-09-25 (owner: "i ratify all your recommendations for R1-D1 to D14") and the spec APPLIED: master v2.21 §5 and ACIS-09 v1.7 C-BT-11 v2; built in R1.2/R1.4] (2026-09-25 — from PLAN_R1 §9 #1; R1-A simulation at R = 400, direction reproduced by the cloud lead at R = 80; not re-run locally)
- Area: the verdict (C-BT-11 v2), the look register, master §5 (rule parameters)
- Description: when a researcher hill-climbs, the set of tried runs depends on the data, so a union bound over tried runs leaks: max-t over the registered union passes noise 10–16% of the time and Bonferroni over runs 6.5–13%. Max-t over a pre-DECLARED grid holds ~5.2–5.5%; Holm over fixed family combinations 1.5%, with higher power.
- Justification: open; A2 and A4 in R1_LEAD_REVIEW_2026-09-25.md. It extends [[GAP-P12D-64]].
- Linked: [[GAP-P12D-64]], [[GAP-P12D-98]], [[GAP-P12D-100]], [[GAP-P12D-102]]

## GAP-P12D-88: two tooling tickets — the governance gate cannot find the constitution checks from a worktree, and three A16 anchors cannot match on a CRLF checkout
- Severity: low · Likelihood: certain
- Status: open [impl] (2026-09-25 — BUILDER-2's F4/R16; the first reproduced by the lead from a scratch worktree during merge 3: "no checks directory at …\scratchpad\specs_constitution\checks")
- Area: scripts/governance_gate.py (`CHECKS = REPO.parent / "specs_constitution" / "checks"`), `falsify.cases.json` multi-line anchors
- Description: a worktree's `REPO.parent` is not the Knowledgevault folder, so the gate cannot run there; and the three pre-existing multi-line guardrail cases match only LF checkouts.
- Justification: open; resolve the checks folder from the git common dir (or an env override), and make the anchors line-ending-agnostic.
- Linked: [[GAP-P12D-83]]

## GAP-P12D-87: selection and grading now fill a favourable gap through the target differently — one fill model must serve both
- Severity: medium · Likelihood: medium
- Status: open [spec — decided with the research simulator's fill model] (2026-09-25 — BUILDER-2's R11, confirmed by the lead: `core/optimizer/fitness.py` fills an open beyond the target AT THE OPEN (X3), while `tests/backtest/book.py` `maybe_close` fills a target AT ITS LEVEL)
- Area: core/optimizer/fitness.py `trade_path`, tests/backtest/book.py `maybe_close`, the future RSIM (PLAN_R1 R1.3)
- Description: selection is now slightly more lenient than grading on favourable gaps. It is the C8 "one model, both places" law applied to fills. Stops agree (first price at or worse, GAP-P12D-84 / T6).
- Justification: open. The lead's recommendation: ONE fill model, defined once and used by RSIM and the graded book. For targets, keep the conservative level fill until the venue's take-profit gap behaviour is verified on the demo (prop simulators do not document price improvement). Decided with A3/A4, since `fitness.py` is retired under A4.
- Linked: [[GAP-P12D-84]], [[GAP-P12D-83]], [[GAP-P12D-82]]

## GAP-P12D-86: the look register's durability limits — tail deletion is undetectable without an outside anchor, the chain is unsigned, and family names are honour-system
- Severity: medium · Likelihood: low
- Status: open [owner decision — where the anchor lives] (2026-09-25 — BUILDER-2's R8–R10, merged with merge 3)
- Area: tests/backtest/look_register.py, `data/validation/looks` (git-ignored, one copy on this laptop, GAP-P12D-50/76)
- Description: deleting the LAST line with its markers leaves no trace inside the register (each report now carries the chain head as an outside anchor). Anyone running the code can append a valid line, though an appended line is itself a counted look. A renamed family resets its "what changed" history; the per-tier totals do not reset.
- Justification: open. Recommendation: commit the chain head to git with each real-data grade, or copy the register off the laptop with the tick-set second copy (GAP-P12D-50). The owner decides.
- Linked: [[GAP-P12D-64]], [[GAP-P12D-50]], [[GAP-P12D-76]]

## GAP-P12D-85: the walk-forward harness carries open positions through the embargo, where nothing can act — so on weekend-flat accounts every position open at a fold's end is booked as a `weekend_holding` violation
- Severity: medium · Likelihood: high
- Status: open (2026-09-25 — found by the BUILDER agent while fixing F2 of [[GAP-P12D-72]]; the evidence is in its branch report. The lead has NOT reproduced it; verify before relying on it)
- Area: tests/backtest/harness.py (fold boundaries, the embargo), tests/backtest/walk_forward.py, the §9.5 rule-violation tally (C-BT-7)
- Description: at a fold's end the book keeps open positions across the embargo gap, during which no engine decision runs, so nothing can close them. On an account that disallows weekend holding, any engine position still open at a fold's end is later booked as a `weekend_holding` rule violation. The violation is caused by the harness's fold geometry, not by the strategy. So on weekend-flat accounts the §14 `rule_violations` gate fails for a reason unrelated to the engine, and a real violation is indistinguishable from this artifact.
- Justification: open. FIX candidates (the lead's recommendation is the first): (a) flatten every open position at each fold's test end, at that tick's price, as the harness's declared convention; or (b) keep the embargo's rule clock off. Decide during the post-merge work. It interacts with BUILDER-3's weekend flatten ([[GAP-P12D-58]]).
- Linked: [[GAP-P12D-72]], [[GAP-P11I-02]], [[GAP-P12D-58]]

## GAP-P12D-84: PRE-EXISTING ON MAIN — the graded backtest book fills a gapped-through stop AT THE STOP, not at the gap price, so every graded result flatters gap losses
- Severity: high · Likelihood: high
- Status: fixed (2026-09-25 — fixed by the lead in the main session, as the first change after the BUILDER merge. `PositionModel.maybe_close` now fills a triggered stop at `min(price, stop)` for longs and `max(price, stop)` for shorts: the first price equal to or worse than the stop, as OANDA v20 and backtrader do. Targets keep their level, which is conservative on gaps. Falsified per A16: reverting either side turns exactly its test red, and the restore is byte-identical. The full suite gives 856 passed. Originally found by AUDIT-EXTERNAL (X1) of the BUILDER-2 branch, and verified by the lead)
- Area: tests/backtest/book.py `maybe_close` (the graded tick book behind every §14 grade, the falsification runs and the cost ladder); master §8.5's gap law (ACIS_SPEC.md "gap" / black-swan preparedness)
- Description:
  - **The mismatch with real venues.** Real venues fill a triggered stop at the first price equal to or worse than the trigger. OANDA's v20 docs: "filled … by the first price that is equal to or worse than the threshold"; backtrader fills gapped stops at the open.
  - **What the book does instead.** It books the stop level exactly, so weekend gaps, news gaps and thin-liquidity jumps all land at the stop. Every graded result understates gap losses: the "false encouragement" class this project exists to prevent.
  - **The selection side is now stricter than grading.** BUILDER-2's T6 made the selection-side fitness simulator fill gaps at the open.
  - **An earlier test covered a different path.** The phase-9 "weekend gap through stop books loss at gap price" test exercises the Risk Monitor, not this graded book.
- Justification: open. The fix is a TIGHTENING one-liner that fills at `min(price, stop)` for longs and `max(price, stop)` for shorts, pinned by hand-worked tests for a gap through the stop, falsified. It is DEFERRED until after the BUILDER branch merges, because that branch also edits tests/backtest/book.py and a fix on main now would conflict. It is the first change applied after the merges. Until then, any graded number is optimistic on gaps. The ladder's verdict (the engine loses, [[GAP-P12D-49]]) only gets worse, so no conclusion flips.
- Proof: `test_a_long_stop_gapped_through_books_the_gap_price_not_the_stop`, `test_a_short_stop_gapped_through_books_the_gap_price_not_the_stop`, `test_a_stop_touched_exactly_still_fills_at_the_stop`.
- Residual: GAP-P12D-83 — the selection-side twins: T6's fitness-simulator gap exits (on the unmerged BUILDER-2 branch, which also pays the closing spread at an open fill) and X3 (a bar that opens beyond the target and then touches the stop).
- Linked: [[GAP-P12D-83]], [[GAP-P12D-65]], [[GAP-P12D-49]], [[GAP-0001]]

## GAP-P12D-82: four latent look-ahead or artifact paths in the research instrument, found by the structural leakage suite (pre-existing on main)
- Severity: medium · Likelihood: medium
- Status: open (2026-09-25 — surfaced by BUILDER-2's T1/T2 leakage sweeps; see its report archive/BUILDER2_REPORT_2026-09-24.md §2 and §5. Each has a named mechanism and `file:line` evidence. None leaks on the current production call paths, which the sweeps checked clean: 102,998 / 102,961 decisions compared)
- Area: core/optimizer/fitness.py (`trade_path` costs), core/optimizer/qiea.py (`fitness_window`), the NVMA session-median callback via `MarketStateFactory`, the per-regime fitness windows (ACIS-03 §6)
- Description:
  1. **F1: the fitness fill pays the entry bar's CLOSING spread**, a datum from after the fill. It is a small cost look-ahead in selection.
  2. **F2: QIEA's `fitness_window` bounds only the START of the span.** It would evolve on bars after `now` if a caller supplied them. The production caller does not, and `refuse_lookahead` plus the new sweep check it.
  3. **F3: materialising the tick stream leaks end-of-tape session medians into NVMA.** Every current path is lazy; any `list(market_states(...))` before labelling would leak.
  4. **F5: regime-sliced fitness windows are concatenated across time**, so every junction between two regime stretches is a synthetic price jump. After T6's gap-through exit it is no longer optimistic, but the series itself is an artifact.
- Justification: open. **DELEGATED DECISIONS** (the lead's recommendations under the owner's delegation, recorded for review):
  - **F2 [impl]:** the one-line tightening, keeping only `b.ts + bar_seconds <= now`. No ratification is needed.
  - **F1 [spec, ACIS-03]:** charge the SIGNAL bar's closing spread, the latest known at decision time. This is the clean no-look-ahead convention.
  - **F5 [spec, ACIS-03]:** simulate each contiguous regime stretch separately, flat at every junction.
  - **F3 [impl]:** make it structural via the T8 decision-time accessor.

  All four are built AFTER the three open branches merge, to avoid conflicts. F1 and F5 change fitness numbers, so they get an ACIS-03 amendment. The gene search space is unchanged, so no re-baseline is needed.
- **Progress 2026-09-25 (merge 3):** F1's EXIT side is fixed (a gap exit pays the prior bar's closing spread, X2). The ENTRY side is BUILDER-2's R13, still open. Under PLAN_R1's A4, `fitness.py` is retired, so F1 and F5 become requirements on the research simulator's fill model ([[GAP-P12D-87]]) rather than ACIS-03 text.
- Linked: [[GAP-P12D-65]], [[GAP-P12D-64]], [[GAP-P12D-83]]

## GAP-P12D-83: the dual audit of the BUILDER-2 branch (leakage suite, look register, T6)
- Severity: medium · Likelihood: high
- Status: fixed (MERGED 2026-09-25 as merge 3 (`689a406`, the owner's explicit go). Every finding of both lenses was fixed on the branch. The lead verified the combined tree: 1002 passed, 6 skipped; the governance gate green. The auditors' own attacks were re-aimed at the fixed API (archive/r1_lead_probes/r_look_register_v2.py, r_fitness_gap_leak3_v2.py): L1–L4 and the race are refused, L5 is reported not raised, and the MEDIUM-2 gap-exit leak, re-planted, is caught by T1 or T2 on every seed where it changes a decision. The branch report moved to archive/BUILDER2_REPORT_2026-09-24.md)
- Area: the BUILDER-2 branch — the leakage suite (T1/T2/T7), the look register and its `run_walk_forward` refusal, and T6 gap-through exits in `core/optimizer/fitness.py`
- Description: BUILT, PENDING AUDIT.
  - **EXTERNAL lens IN (2026-09-25, archive/AUDIT_BUILDER2_BRANCH_EXTERNAL_2026-09-25.md)**, every finding reproduced by the auditor:
    - **X1:** pre-existing on main, and verified by the lead. It has its own entry, [[GAP-P12D-84]].
    - **X2 (MED-HIGH):** `trade_path_decisions` stamps every exit at bar j+0.5, so a planted leak where a gap exit reads the bar's close gives 0 T1 and 0 T2 violations over 479 cuts. The detector is blind to re-stamped exits. T6's gap exit also pays the bar's CLOSING spread for a fill at the open, the exit-side twin of [[GAP-P12D-82]] F1.
    - **X4 (MED): the register's completeness rests on caller diligence.**
      - a look in a throwaway directory passes `verify_look`;
      - deleting the latest line is undetectable;
      - dirty-tree real-data looks are accepted;
      - `dukascopy-mirror` counts as tier 0;
      - renaming a family resets its history;
      - one empty line, as after a power loss, breaks every later registration;
      - it lives in git-ignored /data/;
      - no per-look outcome is recorded, so the DSR and PBO trial variance cannot be derived.
    - **X5/X7 (MED): honesty wording.** The suite's "clean: no decision depends on data after it" overclaims; an empirical detector certifies nothing by its silence (Fonseca). It also cites Gençay's "structural guardrail" for what is a two-run detector (T8 would be the structural one).
    - **X3 (MED-LOW):** a bar that opens beyond the target and then touches the stop is booked as a stop.
    - **X6/X8/X9 (LOW):** the labeller tape is too short to show F3; the engine grid is anchored at 00:00 UTC, not 17:00 New York; tier "forward" starts 2026-01, before the June-2026 model cutoff ([[GAP-P12D-66]]).
    - **Honest negatives:** whole-tail statistic leaks are caught; exclusive create is atomic; looks survive crashed grades; T6's stop-at-open matches OANDA and backtrader.
    - **The auditor's verdict:** a strict empirical detector for value look-ahead on price data, not a certificate.
  - **INTERNAL lens IN (2026-09-25, archive/AUDIT_BUILDER2_BRANCH_INTERNAL_2026-09-25.md): "every guard can be made to miss"; NOT fit to merge until fixed.** Findings:
    - **HIGH-1: the look register can be bypassed.** The lead REPRODUCED all five cases with `r_look_register.py`:
      - L1: a validation-tier line in a temp dir grades to completion while the canonical register is untouched;
      - L2: a source named `dukascopy` but keyed `synthetic` grades as tier 0;
      - L3: one line serves three grades;
      - L4: a hand-forged line on disk passes `verify_look`;
      - L5: an empty file left by a power cut bricks the register with `JSONDecodeError`, which `run_oos_validation` does not catch.
      The fix: pin ONE canonical register; derive the tier from the source OBJECT; CONSUME a line at grade time, so one line is one grade; hash-chain or otherwise make deletion and forgery detectable; tolerate or repair a truncated line and fail closed; record each look's outcome. This matches EXTERNAL X4.
    - **MEDIUM-1:** a whole-file statistic memoised on the source name hides from both T1 and T2 (0/129 cuts, against 129/129 when recomputed), because `PerturbedMarket` keeps the reference's name and workers are reused. FIX: give each variant a distinct source name, in a fresh spawned process.
    - **MEDIUM-2:** a gap exit reading its own bar's close passes the exhaustive fitness sweep, because every exit is stamped at j+0.5. This agrees with EXTERNAL X2. FIX: stamp at j.
    - **MEDIUM-3:** the evolution sweep's T2 has never caught anything. Only T1 catches the author's own mutation and peeks of +5, +20 and +60 min. FIX: a T2 control that bites.
    - **MEDIUM-4:** the AGON sweep cannot fail on a look-ahead in AGON's own code. With the perturbation switched off, the AGON sweep, the bar-builder sweep and every T7 control stay green. FIX: controls that bite.
    - **LOW:** concurrent first-look registrations; the dirty flag counts untracked files and the commit is not re-checked at grade time; a bar opening beyond the target then touching the stop is booked as a stop (= X3); T6's ACIS-03 amendment is owed; the engine tap is not in the default suite.
    - **Honest negatives:**
      - the engine path catches a planted F3 leak (T2 −2,200, T1 −1,704 decisions), and the honest run is clean;
      - the 60 s reference is not vacuous (51,118 labels, 20 orders);
      - all 14 new falsification cases go red for their stated reasons;
      - 10 of 10 T6 hand mutants were killed;
      - `passed` is byte-identical;
      - the export gives 864 passed, 6 skipped.
  - **Status: BOTH LENSES IN; the fixes are not yet assigned.** Per the owner's 2026-09-25 rule, sending this list back to BUILDER-2 is a NEW launch and needs the owner's explicit go. The alternative is the lead fixing it in-session.
- Justification: open until both lenses' findings are triaged and the branch merges on the owner's go. It merges AFTER the BUILDER branch, which it stacks on.
- Proof: `test_a_real_data_look_outside_the_canonical_register_is_refused`, `test_the_tier_comes_from_the_source_object_never_a_caller_string`, `test_one_line_is_one_grade`, `test_forged_deleted_or_edited_lines_break_the_chain_and_the_register_fails_closed`, `test_a_torn_line_is_reported_and_counted_and_never_bricks_the_register`, `test_concurrent_first_looks_are_unambiguous`, `test_a_whole_file_statistic_memoised_on_the_source_name_is_caught`, `test_every_engine_variant_runs_in_a_fresh_spawned_process`, `test_a_gap_exit_that_reads_its_own_close_is_caught_by_t1_and_t2`, `test_evolution_that_peeks_past_its_train_end_is_caught_by_t2_alone`, `test_a_whole_tape_median_on_agons_channel_is_caught_by_t2`, `test_a_bar_that_opens_beyond_the_target_fills_there_at_the_open`, `test_the_grid_is_the_17h_new_york_decision_epochs_plus_the_fold_boundaries`.
- Residual: GAP-P12D-86 — the register's durability limits (R8–R10); GAP-P12D-87 — one fill model for selection and grading (R11); GAP-P12D-88 — the two tooling tickets (R16/F4); GAP-P12D-65 — the leakage remainders (R12, R14, R15); GAP-P12D-82 — F1's entry side (R13).
- Linked: [[GAP-P12D-64]], [[GAP-P12D-65]], [[GAP-P12D-82]], [[GAP-P12D-72]]

## GAP-P12D-81: lot-step rounding can orphan one leg of a pair group, leaving a naked directional position — on the BUILDER-3 branch, looser than main
- Severity: high · Likelihood: medium
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). `submit_group` sends all legs or none, and a pair leg sent alone is refused; the lead re-ran `r9`: the 1,500/900 pair leaves the venue FLAT)
- Area: the BUILDER-3 branch (lot rounding in execution); core/governor/capital_governor.py (atomic groups, §5.5 both-or-neither at min-leg); core/execution/orchestrator.py
- Description: the new per-order lot rounding and minimum-lot refusal act on each leg independently. A pair group whose smaller leg rounds below the minimum loses that leg, and the surviving leg is a directional position the strategy never intended. That breaks master §5.5's atomic-group law (both legs or neither).
- Justification: open and BLOCKING for the merge. FIX: group atomicity in execution. Rounding and minimum-lot checks run over the WHOLE group before any leg is sent, and if any leg would be refused or rounded to zero, the whole group is refused. Proof: a regression test mirroring the reproduction, falsified.
- Proof: `test_a_leg_below_the_minimum_refuses_the_whole_group`, `test_a_pair_leg_sent_alone_is_refused`, `test_a_group_the_venue_can_take_opens_both_legs`, `test_a_group_is_refused_when_the_budget_cannot_send_both_legs`.
- Residual: none — group atomicity is enforced in execution and pinned.
- Linked: [[GAP-P12D-57]], [[GAP-P12D-77]], [[GAP-0049]]

## GAP-P12D-80: PRE-EXISTING ON MAIN — the engine's daily-loss session halt fires at most once per process; the Guardrails latch is reset only by a human resume
- Severity: critical · Likelihood: high
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). The session latch re-arms at the session boundary; the lead re-ran `r2b`: an in-process day-3 breach gives `drawdown_halt`, where main gave `formula`)
- Area: core/risk/guardrails.py (`_session_halted`, reset only in `rearm()`, which is called on a human resume); master §8 (the daily-loss limit is SESSION-scoped and auto-clears at the boundary); ACIS-07
- Description:
  - **The latch outlives the halt.** The Governor's session halt auto-clears at the next session boundary, as §8 intends. But the Guardrails latch `_session_halted`, which stops the monitor from re-issuing, stays set until a human resume.
  - **So in one process only the FIRST daily-loss breach ever halts.** Every later day's breach is silently ignored.
  - **It is a guardrail that works once per process lifetime.** It went unseen because every test exercises a single breach, and the production runtime does not exist yet. It sits on main now, and the backtest harness's risk path would inherit it.
  - **It is the root of the branch's [[GAP-P12D-78]].**
- Justification: open and BLOCKING (a guardrail defect). The fix RESTORES the spec's own semantics and is tightening-only: the guard fires again on every day it is breached. **DELEGATED:** it is fixed on the BUILDER-3 branch, and raised to the owner as a HALT-semantics item: the session latch re-arms at the session boundary, exactly when the Governor's session halt auto-clears. Proof: an in-process multi-day breach test and a restart variant, falsified.
- Proof: `test_a_breach_on_a_later_day_halts_again_in_one_process`, `test_after_a_restart_the_next_day_a_fresh_breach_halts`.
- Residual: none — the pre-existing main defect is fixed at its root and pinned in-process and across restarts.
- Linked: [[GAP-P12D-78]], [[GAP-P12D-77]], [[GAP-P12D-59]]

## GAP-P12D-79: on the BUILDER-3 branch, one failed halt-ledger write during an equity-floor breach loses the equity breaker entirely — no halt, no freeze, never re-issued
- Severity: critical · Likelihood: low
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). The guard acts first and the ledger write follows, retried and alarmed; a latch is set only after success; the lead re-ran `r2`: with the write failing, entries are `halt`, the orchestrator is frozen, and both rows persist)
- Area: the BUILDER-3 branch (the persistent halt sink and restore_on_boot); core/risk/guardrails.py (latch set before the sink call); master §8 (the equity breaker is unthrottleable and first)
- Description:
  - **Two ordering choices combine.** The Guardrails latch `_equity_flattened` is set BEFORE the sink call. The new persistent sink writes the ledger BEFORE it forwards to the Governor or execution. So any store failure (a lock from a second process such as the MCP plane, a full disk, an I/O error) swallows the flatten and the HALT, and the latch prevents any retry.
  - **Why it is critical.** It is a NEW failure mode relative to main, on the single most important guard. The likelihood is low; the severity is that the guard silently does not fire.
- Justification: open and BLOCKING for the merge.
  - **The fix principle: the guard acts first, and recording can never gate it.** Forward the halt or flatten to the Governor and execution FIRST, then persist. If persisting fails, retry and alarm, and keep the halt in force in memory; never swallow it. Set the latch only after the action succeeded.
  - **Proof:** regression tests that inject a store failure at each write and assert the halt and flatten still take effect, falsified per A16.
- Proof: `test_the_equity_breaker_holds_when_any_store_write_fails`, `test_an_edge_call_that_fails_is_reissued_not_latched`.
- Residual: none — the act-first order is pinned at four store write points.
- Linked: [[GAP-P12D-75]], [[GAP-P12D-77]], [[GAP-P12D-78]]

## GAP-P12D-78: on the BUILDER-3 branch, a stale restored session-halt row latches the breaker, so after a restart the next day's 2% breach no longer halts — LOOSER than main
- Severity: high · Likelihood: medium
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). A lapsed session row closes as `auto:session_boundary` and is never re-latched; the lead re-ran `r1`: a day-2 fresh breach gives `drawdown_halt`, and after recovery still `drawdown_halt`, matching base)
  - **base:** day-2 fresh 2% breach → `drawdown_halt`; still `drawdown_halt` after an in-session recovery.
  - **branch:** → `formula_zero`, then `formula` (TRADING) after the recovery; the day-1 session row is still open)
- Area: the BUILDER-3 branch (restore_on_boot, the persistent halt sink); core/risk/guardrails.py `_session_halted`; master §8 (the daily loss is session-scoped and auto-clears at the boundary)
- Description:
  - **The mechanism.** A SESSION halt auto-clears at the next session boundary in the Governor, but the branch's halt ledger keeps its row "uncleared", because only a human resume clears rows. At boot the row is restored, and Guardrails' `_session_halted` latch is set again. A NEW breach on a later day then finds the latch already set and issues no session halt.
  - **The effect.** After a restart, a fresh daily-loss breach does not halt, and entries resume as soon as the taper allows.
  - **Why it matters.** It breaks the tightening-only claim. The branch is looser than main in exactly the "restart" case it was built to harden.
- Justification: open and BLOCKING for the merge.
  - **The fix:** session-scoped halts must be restored WITH their expiry. A row whose session boundary has passed is closed as auto-expired, never re-latched. The restore must re-arm the Guardrails latches consistently with the restored state.
  - **Proof:** a regression test mirroring the reproduction (restart the next trading day; a fresh breach halts; the halt survives an in-session recovery), falsified.
- Proof: `test_after_a_restart_the_next_day_a_fresh_breach_halts`, `test_a_session_halt_lifts_at_its_own_boundary_after_a_restart`, `test_a_restart_inside_the_session_keeps_the_halt_until_its_boundary`.
- Residual: none — the latch semantics are restored and pinned; production wiring belongs to GAP-0091b.
- Linked: [[GAP-P12D-75]], [[GAP-P12D-77]], [[GAP-P12D-79]], [[GAP-P12D-59]]

## GAP-P12D-77: the dual audit of the BUILDER-3 branch — findings and triage
- Severity: high · Likelihood: high
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros); the specs are amended in the same merge: master v2.20, ACIS-05 v1.5, ACIS-06 v1.3, ACIS-07 v1.2)
- Area: the BUILDER-3 branch `worktree-agent-a9e00713d15bb5082` (head `d8361a7`)
- Description: triage of the EXTERNAL findings.
  - **Each has its own entry:**
    - X1 → [[GAP-P12D-78]], looser than main, blocking;
    - X2 → [[GAP-P12D-79]], the equity breaker lost on a store failure, blocking.
  - **X3 (HIGH; not looser than main, which doubled):** "reduce-only" is check-then-act in the engine, and the venue receives a plain opposite-side order. A stop filling in between, or two racing closes, leaves an unprotected opposite position. Real venues close atomically:
    - cTrader `ProtoOAClosePositionReq` ("The unique ID of the position to close");
    - OANDA `REDUCE_ONLY`;
    - FIX PositionEffect(77)=C.

    FIX: carry the close intent across the face boundary. The `ExecutionFace` contract gains a close-position operation (or a reduce-only flag) that the adapter maps to the venue's atomic close. That is an ACIS-06 amendment; fold it into the ACIS-13 review with [[GAP-P12D-70]]. The mock face must implement it atomically.
  - **X4 (MED-HIGH):** the risk and fill stores run in the default rollback journal with `synchronous=FULL`, which SQLite documents as "not necessarily durable across a power loss". FIX: WAL + FULL via the existing `core/data/sqlite_wal.py` helper. It is live because of [[GAP-P12D-76]].
  - **X5 (MEDIUM, reproduced by the auditor):** the pre-close ban and weekend flatten key only on the Friday close. FTMO binds at ANY closure of two hours or more (it closed FX on Dec 25 and Jan 1 in 2025). FIX: key on the calendar's next ≥2 h closure, holidays included ([[GAP-P12D-58]]).
  - **Lower findings:**
    - X6: failing closes are re-sent every tick with no backoff, though FTMO counts closes toward its request cap. FIX: backoff plus a close ceiling.
    - X7: FTMO 1-Step's end-of-day trailing max loss has no safe encoding. RECORD: the rule type is owed before any 1-Step account.
    - X8: stale FTMO page date. FIX the citation.
    - X9: the resume fingerprint is 48 bits of unsalted SHA-256, an offline guessing oracle for a human-chosen token. FIX: HMAC or salted, and never a weaker form than the existing verifier ([[GAP-P10E-03]]).
  - **Honest negatives, from the auditor:**
    - FTMO 2-Step reproduces exactly (95k, 97k, 96k; static 90k);
    - the Prague DST day boundaries fall while FX is closed (2025–27);
    - the rolling 24-hour budget is at least as strict as a calendar cap;
    - lot rounding is down-only;
    - no guard, rulebook, spec or ledger file is touched.
  - **Unconfirmed:** E8's rules (its help centre returned 403).
- **INTERNAL lens IN (2026-09-25; archive/AUDIT_BUILDER3_BRANCH_INTERNAL_2026-09-25.md): the branch is NOT tightening-only.** Its F0 is X2, and its F1 is X1.
  - **New entries, reproduced by the lead:**
    - [[GAP-P12D-80]] (F2): PRE-EXISTING ON MAIN, the daily-loss halt fires once per process;
    - [[GAP-P12D-81]] (F11): lot rounding orphans a pair leg.
  - **F4:** the reduce-only close race. It confirms X3: two concurrent closes leave the venue SHORT 100k, and a hedging venue ends net short 200k. It is a BLOCKER before any demo or live attach.
  - **F3 (DELEGATED DECISION):** a restart while the account is up now reads a later loss LOWER than main, because main re-anchors at the post-restart equity by accident. The branch is RESTART-INVARIANT and faithful to the firm's static rule, which anchors on initial capital. The lead ACCEPTS restart-invariance as the property, and the branch's claim is corrected from "tightening-only" to "restart-invariant; tightening elsewhere".
  - **F6:** an `initial_capital` typo can disable the static rule. FIX: schema validation plus a test.
  - **F5:** re-emitted closes are unbounded, and a restart forgets attempts. FIX: backoff, a ceiling, and persisted attempts (with X6).
  - **F7:** restore-before-evaluate is only a convention. FIX: enforce it.
  - **F8:** a Governor-only resume re-halts at the next restart. FIX: one human-resume path that clears the ledger rows.
  - **F9, F10, F12 (Low):** fix them. F10 is the same as X9.
  - **Honest negatives:**
    - no halt clears without a non-blank token;
    - rounding never rounds up;
    - sequential closes on a netting venue never grow a position;
    - with no restore or declared capital, the drawdown series matches base exactly;
    - corrupt anchors fail closed;
    - 20 of 21 mutants were killed.
- Justification: open. ONE consolidated fix list went back to BUILDER-3 on 2026-09-25. The merge needs [[GAP-P12D-78]], [[GAP-P12D-79]], [[GAP-P12D-80]] and [[GAP-P12D-81]] fixed with regression tests and verified by the lead, X3/F4 fixed or filed as an attach blocker, and the owner's go. The merge needs [[GAP-P12D-78]] and [[GAP-P12D-79]] fixed and verified by the lead, plus the owner's go.
- **FIXES LANDED on the branch (2026-09-25, head `b7da5f0`, all 12 items, each falsified). The LEAD RE-RAN the auditors' own reproductions against the fixed head:**
  - X1 ([[GAP-P12D-78]]): the day-2 fresh breach → `drawdown_halt`, and after recovery → `drawdown_halt`, matching base; the day-1 row closes at the boundary.
  - X2 ([[GAP-P12D-79]]): with the store write failing → entry `halt`, the orchestrator frozen, and both equity-floor rows persisted after the retry.
  - F2 ([[GAP-P12D-80]]): the in-process day-3 breach → `drawdown_halt`.
  - F11 ([[GAP-P12D-81]]): the 1,500/900 pair → the venue is FLAT.
  - F4/X3: two concurrent closes → FLAT. Checked on the venue's own state, one open plus three closes gives FILLED, REJECTED, REJECTED and a flat venue; the repro's hedging-subclass reading was an artifact of its private bookkeeping, which closes never touch.
  The adapted repro copies, which add the new required `logger` argument and the boot restore that F7 now enforces, are in the session scratchpad under lead/. No guardrail, rulebook, spec, ledger or baseline file was touched; the config gains schema only (the Europe/Prague zone, FX holidays, and a split-out rulebook schema module).
- Proof: the proofs under GAP-P12D-55, -57, -58, -74, -75, -78, -79, -80 and -81, plus `test_the_risk_store_is_wal_with_full_sync` (X4) and `test_a_typo_in_initial_capital_is_fatal_at_load` (F6).
- Residual: GAP-P12D-54 — the `ftmo`/`e8` rulebook VALUES still need the owner's commit (drafts in archive/BUILDER3_REPORT_2026-09-24.md), and the FTMO 1-Step rule type (X7) is not built. The production wiring of halts, the flatten and the restore belongs to GAP-0091b.
- Linked: [[GAP-P12D-78]], [[GAP-P12D-79]], [[GAP-P12D-74]], [[GAP-P12D-75]], [[GAP-P12D-58]], [[GAP-P12D-76]], [[GAP-P12D-70]]

## GAP-P12D-76: the development laptop keeps losing power abruptly — four hard power-offs in 13 days — so it cannot host the demo engine
- Severity: high · Likelihood: high
- Status: open (2026-09-25 — measured by the lead from the Windows System log, read-only. The latest: an "unexpected" shutdown at 00:40:22 on 2026-09-25 (event 6008) and a reboot at 04:48 (Kernel-Power 41). Every event-41 record reads `BugcheckCode=0`, `PowerButtonTimestamp=0`, `LongPowerButtonPressDetected=false`: no crash, no button, a straight loss of power. Earlier ones: 2026-09-23 08:20, 2026-09-23 16:28 (during sleep), and 2026-09-12 23:51 (recorded in TODO.md). The battery now reads 100% on AC, which suggests mains drops that the battery cannot carry)
- Area: infrastructure. The laptop holds the ONLY copy of the tick set ([[GAP-P12D-50]]) and is the only machine running ACIS work; the demo engine (Track A) needs an always-on host
- Description:
  - **The pattern.** The laptop drops power without warning roughly every few days. Last night it killed three running build agents mid-stage, leaving uncommitted, possibly truncated, files in their worktrees. They were resumed and told to verify file integrity first.
  - **Why the demo cannot run here.** For a trading engine a power drop means: the fast loop and the §8.6 watchdog die TOGETHER, which defeats the watchdog's purpose; the feed goes stale; and a restart must reconcile against the venue. [[GAP-P12D-55]] and [[GAP-P12D-75]] exist because restarts are dangerous. Server-side stops still protect open positions, but a host that dies every few days makes every restart path a routine event, not an exception.
  - **The data is at risk too.** Repeated hard power-offs also threaten the single copy of the 12 GB tick set.
- Justification: open, owner-owned (hardware, and spend).
  - **Recommendation:** run the demo engine on a small Linux VPS OUTSIDE the US, which FTMO requires. That is what the deployment gate (Docker + systemd + watchdog) was built for. Keep the laptop for development.
  - **Also for the owner:** check the charger, the mains supply and the battery health (`powercfg /batteryreport` in an elevated shell). And make the second tick-set copy ([[GAP-P12D-50]]) sooner rather than later.
- Linked: [[GAP-P12D-50]], [[GAP-P12D-51]], [[GAP-P12D-55]], [[GAP-P12D-75]]

## GAP-P12D-75: a restart silently clears every explicit HALT — `halt_event` rows are written but never read back
- Severity: critical · Likelihood: high
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). Every uncleared halt is re-applied at boot through the same edge, with the same scope and reason, and a store-backed monitor refuses to evaluate before that; ACIS-07 v1.2)
- Area: core/risk/store.py, core/risk/monitor.py (restart restore), core/governor/capital_governor.py (halt state), the future three-loop runtime boot, master §8 ("halts are cheap; resumes are human-only")
- Description:
  - **What survives a restart and what doesn't.** Every HALT the engine issues is persisted, but the process that restarts starts with no halts at all.
  - **Why that is dangerous.** A HALT that only a human token may clear (equity floor, platform drawdown breach, restart drift) is therefore cleared by any crash or restart. Under systemd supervision that is automatic.
  - **It breaks the guard-integrity law** (a restart is never a relaxation; halts are human-only to resume). It is the HALT-state twin of [[GAP-P12D-55]] (drawdown anchors).
- Justification: open and blocking for any runtime or demo attach.
  - **The fix is tightening-only:** restore every uncleared `halt_event` at boot, before the first evaluate, re-applying it through the same upward edge. **DELEGATED:** it is sent to BUILDER-3's branch.
  - **Proof:** regression tests in which a restart after a global HALT still refuses entries until a human resume, falsified per A16.
- Proof: `test_equity_floor_halt_survives_a_restart_until_a_human_resumes`, `test_an_agent_halt_is_reapplied_with_its_own_scope_and_reason`, `test_a_store_backed_monitor_refuses_to_evaluate_before_its_restore`.
- Residual: GAP-0091b — the production runtime must route every halt and MCP control through the halt-recording layer and call the restore at boot.
- Linked: [[GAP-P12D-55]], [[GAP-0050]], [[GAP-P12D-74]]

## GAP-P12D-74: a Governor "close" order ADDS to the position it means to close — close direction is unspecified between ACIS-05 and ACIS-06, and the execution freeze lets it through
- Severity: high · Likelihood: high
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). A close is REDUCE-ONLY and atomic through `ExecutionFace.close_position`, and the freeze admits only such closes; ACIS-05 v1.5 / ACIS-06 v1.3 C-EXE-7)
- Area: core/governor/capital_governor.py `check_group_exits` (GAP-0040), core/execution/orchestrator.py (submit; the freeze admits `action == "close"`), specs/ACIS-05 / ACIS-06 (the SizedOrder contract), tests/integration test coverage of the seam
- Description:
  - **The bug.** A close order carries the POSITION's direction, and execution treats every order as a trade in its direction. So executing a group exit doubles both legs instead of flattening them.
  - **The freeze makes it worse.** The post-flatten execution freeze admits any `action == "close"`, so a group exit during a freeze would ADD exposure.
  - **Why nothing caught it.** The seam has never run (no runtime exists), and the freeze test submits a close into a flat venue and checks only that it FILLED.
  - **What it blocks:** the weekend flatten, and every Governor-originated close.
- Justification: open.
  - **DELEGATED DECISION (the lead's recommendation):** REDUCE-ONLY close semantics, enforced in execution next to the venue.
    - A `close` identifies the position to close.
    - The orchestrator converts it into the opposing trade, and REFUSES any close that would not reduce |position| at the venue: a closing trade against a flat or same-side venue is a REJECTED FillReport.
    - The freeze admits only such reduce-only closes.
    - This is tightening-only. The closes-allowed-under-freeze law survives, and adding exposure under a freeze becomes impossible.
    - The Governor's current `direction = leg.direction` stays as the position identifier.
    - ACIS-05/06 get the convention stated in a versioned amendment.
  - **Proof:** a seam test that asserts the venue is FLAT after a group exit, and that the freeze refuses an exposure-increasing "close". The fix is sent to BUILDER-3's branch.
- Proof: `test_governor_pair_exit_leaves_the_venue_flat`, `test_two_concurrent_closes_never_flip_the_position`, `test_a_venue_stop_between_read_and_close_opens_nothing`, `test_a_hedging_venue_never_ends_net_opposite`, `test_close_position_is_reduce_only_on_the_shipped_mock`.
- Residual: GAP-P12D-70 — venue-initiated fills (a server-side stop firing) still have no path into ACIS; every real adapter must implement `close_position` as the venue's atomic close (ACIS-13).
- Linked: [[GAP-0040]], [[GAP-P12D-75]], [[GAP-P12D-58]], [[GAP-P12D-70]]

## GAP-P12D-73: the plateau law shrinks the Deflated-Sharpe trial set — a champion refused after the holdout gate drops out of the trials, which loosens a ratified gate
- Severity: high · Likelihood: high
- Status: fixed (2026-09-25 — MERGED. `QIEA.evolve_outcome` returns the holdout-passed candidate whether or not the plateau law stages it, and `evolve_fold` counts every candidate as a trial. The lead re-ran the auditor's `trial_set.py` on the fixed head: 23 trial Sharpes, the same as base, where the defective head gave 18)
- Area: the BUILDER branch — core/optimizer/qiea.py (the order of the plateau and holdout gates), tests/backtest/evolve_step.py (trial assembly), tests/backtest/report.py (the owner-ratified DSR gate, C-BT-11)
- Description:
  - **How it happens.** The plateau check runs AFTER the holdout gate. A champion that clears the holdout and is then refused for plateau reasons is silently removed from the trial set that the DSR deflates by.
  - **Why it matters.** Fewer, more alike trials mean a lower SR0 and an easier gate: the same inversion class as [[GAP-P12D-33]]. A spec-mandated anti-overfitting law must never loosen the multiple-testing correction.
- Justification: open and blocking for the merge.
  - **Required fix:** a refused champion is still a trial (it was evaluated and selected), so it stays counted.
  - **Regression test:** base and head count the same trials.
  - **Proof it can fail (A16):** the test must be falsified.
- Proof: `test_a_plateau_refused_candidate_stays_a_deflated_sharpe_trial`, `test_every_candidate_champion_with_a_sharpe_is_a_trial`.
- Residual: none — the trial count is restored exactly, and the gate itself belongs to GAP-P12D-33.
- Linked: [[GAP-P12D-34]], [[GAP-P12D-33]], [[GAP-P12D-72]]

## GAP-P12D-72: the dual audit of the BUILDER branch — findings and triage
- Severity: medium · Likelihood: high
- Status: fixed (2026-09-25 — every finding of the BUILDER-branch dual audit is fixed on the branch, committed separately, falsified, and MERGED to main. The lead verified the branch suite at 847 passed, 6 skipped, and the F3 trial count at 23 = base. The merge-time items are done: F7, ACIS-03 v1.5; F8, the report is relocated to archive/)
- Area: the BUILDER branch `worktree-agent-a128ab904780ce593`, as for [[GAP-P12D-37]] / [[GAP-P12D-34]] / [[GAP-P12D-38]] / [[GAP-P12D-33]]
- Description: triage, one line each. The gate-affecting F3 has its own entry, [[GAP-P12D-73]].
  - **FIX on the branch:**
    - F1/E1: the oracle control is saturated. It passes at 1/15 of the drift and with 35% of signs wrong, and no test catches a 4-hour duration mutant. Add graded-strength rungs, and a fast full-scale test.
    - F2: stage 1 always voids on weekend-flat accounts. The oracle must obey the account's rules.
    - E3/F4: `--kinds` without planted still reports a verdict. It must refuse.
    - E2: a planted failure caused only by the gate must be reported as GATE-LIMITED, not blamed on the engine.
    - E4: "oracle DSR 0.000" is not a faithful Deflated Sharpe, because the oracle is not one of the trials. Remove it and report the SR0 hurdle instead. The lead also corrects its own notes, below.
    - E6: a plateau step of ±10% of value is inconsistent across genes; `rsi_overbought` moves 44.5% of its range. **DELEGATED DECISION: the step becomes ±10% of the gene's declared range.**
    - F5: log each neighbour's direction after repair.
    - F9: the registry must include the plateau neighbours.
    - F6/E7: no bare NaN in any JSON output; write null, per RFC 8259.
    - E9: size the oracle so its notional is a fraction of NAV.
  - **AT MERGE (lead):**
    - F7: apply the ACIS-03 v1.5 amendment;
    - F8: relocate the root report and its PARTIAL references.
  - **ACCEPTED as a design note:** E8. The registry cannot feed PBO, which needs synchronous per-period P&L; that belongs in the research simulator's design ([[GAP-P12D-68]] item 6).
  - **SEPARATE:** E5, a pre-existing TSMOM finding outside the diff: [[GAP-P12D-71]].
  - **Honest negatives, reproduced by both lenses:**
    - the synthetic tapes are byte-identical before and after;
    - the oracle has no foresight;
    - `non_dsr_failures` mirrors `passed` exactly;
    - the plateau check is deterministic and costs ~3–4%;
    - `repair_invariants` was moved verbatim;
    - the registry is logging only;
    - the suite gives 828 passed, 6 skipped;
    - the BUILDER's oracle figures reproduce exactly;
    - its account of MOP's method matches the paper.
- **FIXES LANDED (2026-09-25; BUILDER head `5d108de`), each committed separately and falsified:**
  - F3 `6c8bb50`: **lead-verified**; the auditor's `trial_set.py` on the new head gives 23 trial Sharpes, the same as base;
  - E6 `b842214`: a range-based step;
  - F5+F9 `bb18730`;
  - E9 `039a687`;
  - F2 `3412f54`: the oracle obeys weekend-flat and minimum-hold rules;
  - F1+E1 `9dd274d`: graded rungs, with profit factor 1.4 as the binding cut, and a full-scale test that kills the 4-hour duration mutant;
  - E3+F4 `7d1d972`: NO VERDICT, exit 5;
  - E2 `11fbe54`: GATE-LIMITED, exit 6;
  - E4 `4b1e723`: an SR0 hurdle instead of the DSR claim;
  - F6+E7 `76f2ce7`: strict JSON.
  **What it surfaced:**
  - a new finding, [[GAP-P12D-85]];
  - an OWNER NOTE on E6: the range step moves period genes near their floor by large ratios (`ema_fast` 6 → 10). The delegated range-step decision trades one inconsistency (RSI moving 44% of its range) for another (small periods moving by large ratios). A grid-step neighbour, the external referent, is the refinement if it matters.
- Justification: open until the lead verifies the full suite on the branch head, and the branch merges on the owner's go with the merge-time items applied: F7 (the ACIS-03 v1.5 text) and F8 (relocate BUILDER_REPORT and PARTIAL_BUILDER to archive/, and fix the link at plateau.py:5).
- Proof: `test_strict_json_writes_every_non_finite_float_as_null`, `test_the_plateau_neighbours_are_recorded_too`, `test_the_oracle_sizes_one_nav_of_notional_on_every_instrument`, `test_on_a_weekend_flat_min_hold_account_the_oracle_keeps_the_rules_and_the_grade_decides`, plus the proofs under GAP-P12D-37, -34 and -73.
- Residual: GAP-P12D-85 — the fold-end weekend-holding artifact the BUILDER found while fixing F2; E8 (the registry cannot feed PBO) is owned by GAP-P12D-68 item 6; E5 is GAP-P12D-71.
- Linked: [[GAP-P12D-73]], [[GAP-P12D-37]], [[GAP-P12D-34]], [[GAP-P12D-38]], [[GAP-P12D-33]], [[GAP-P12D-71]]

## GAP-P12D-71: TSMOM's declared "raw returns, not excess returns" deviation rests on a false premise — for FX it drops carry, and the vote flips on 2–10% of days
- Severity: medium · Likelihood: high
- Status: open (2026-09-25 — found by AUDIT-EXTERNAL, E5, while auditing the BUILDER branch; it is pre-existing and outside the diff. The lead VERIFIED the declaration exists at core/signals/canonical.py: "signs RAW price returns, not excess-over-risk-free returns as in MOP 2012 (immaterial at 3-12m FX horizons) — GAP-0073". The auditor's measurement is not re-run by the lead)
- Area: core/signals/canonical.py (TSMOM's `declared_deviations`), core/signals/agon.py `_tsmom`, the closed [[GAP-0073]]
- Description: the deviation is declared, so the BUILDER's "undeclared" claim was wrong. But the declaration's justification is wrong about the world. For currencies, Moskowitz–Ooi–Pedersen build returns from "spot and forward interest rates" (Appendix A.3), which includes carry. On the repo's own dated overnight-rates data, the 3/6/12-month vote computed on excess returns differs in direction from the raw-return vote on 2.1–10.4% of days in 2013–2025, and on 42% of days for USD/CHF in 2019. So "immaterial" is false.
- Justification: open.
  - **Where it gets fixed:** in the TSMOM rebuild ([[GAP-P12D-68]] item 2: a faithful slow sleeve), which should use excess, carry-inclusive returns.
  - **Until then:** correct the declaration's wording, because a false justification is dishonest provenance under §5.6.
- **Progress 2026-09-25 (R-1, R1-D3 RATIFIED):** TSMOM is no longer required canonical; it is a registered member of the TREND family (master v2.21 §5.6, ACIS-04 v1.3). Carry enters as the venue's swap in C8 ([[GAP-P12D-93]]), not as a return omission. The build is R1.3.
- Linked: [[GAP-P12D-49]], [[GAP-P12D-68]], [[GAP-0073]], [[GAP-P12D-53]]

## GAP-P12D-70: fills the venue makes on its own — a server-side stop firing, a broker close — have no path into ACIS; the position view goes stale until a restart calls it drift and halts
- Severity: high · Likelihood: high
- Status: open (2026-09-25 — raised as OQ-03a by the SPEC-AUTHOR drafting ACIS-13. The lead VERIFIED it by absence: no unsolicited, venue-initiated or stop-trigger handling exists in specs/ACIS-06, specs/ACIS-07, core/execution or core/risk/monitor.py, and `reconcile_on_restart` is called only by tests)
- Area: specs/ACIS-06 (the FillReport contract; `ExecutionFace`), core/risk/monitor.py (position accounting from FillReports), the three-loop runtime ([[GAP-0091b]]/[[GAP-0075]]), specs/ACIS-13 (draft)
- Description: the Risk Monitor builds its view of open positions only from FillReports for orders ACIS itself sent. Several things close a position without that:
  - a protective stop resting on the venue's server (master §279), which cTrader keeps "active after your session ends" (ACIS-13 draft F-16);
  - a firm's liquidation;
  - a manual close.

  None of these produces a FillReport through the orchestrator. The internal view therefore keeps the position open, and VaR, exposure, drawdown and re-entry gating all read a phantom. The only reconciliation in the code runs at restart, and it treats any difference as drift and halts. So the first stop that ever fires correctly would, on the next restart, look like a fault.
- Justification: open.
  - **[spec]:** an ACIS-06 amendment, a locked-spec version bump, for venue-initiated FillReports (execution events the venue pushes, mapped to the position they closed), plus periodic RUNTIME reconciliation against the venue, not just at restart.
  - **[impl]:** that path, in the adapter and the monitor.
  - **Where it gets decided:** in the ACIS-13 review pass together with the other ACIS-06 amendments (a)–(d) the draft lists.
  - **It blocks** any live or demo attach that relies on server-side stops, which is all of them.
- Linked: [[GAP-P12D-69]], [[GAP-0075]], [[GAP-0091b]], [[GAP-P12D-55]], [[GAP-0018]]

## GAP-P12D-69: the spec has no lawful mode for a demo account — paper mode may never send an order, and live mode needs §14 plus human sign-off
- Severity: high · Likelihood: high
- Status: open (2026-09-25 — raised as OQ-01 by the SPEC-AUTHOR drafting ACIS-13. The lead VERIFIED it in the master spec: `acis_set_mode(backtest|paper|live)` offers only three modes, and the GAP-0018 attach law reads "paper mode never gains a real-order path", while §15 orders "OANDA practice account first" before live)
- Area: ACIS_SPEC.md §7.5 (the attach law, GAP-0018), §12 (modes, `acis_set_mode`, the human token), §15 (phase 12), monitoring/mode.py, specs/ACIS-08, specs/ACIS-13 (draft)
- Description: the owner's top priority is to see ACIS trade a demo account, and a demo trade is an order sent to a venue.
  - **In paper mode** it is forbidden by construction.
  - **In live mode** it would need the §14 minimums out-of-sample, plus human sign-off and the dual-hash acknowledgement. A demo is exactly what must come BEFORE those can be met.
  - **So a demo run has no lawful mode as written.** This is a real contradiction inside the spec, and it has to be ruled before any adapter attaches.
- Justification: open.
  - **The lead's recommendation, adopted in direction under the owner's delegation:** add a fourth mode, `practice`, with these properties:
    - Orders go ONLY to a venue the attach protocol has verified to be a simulated or practice environment. The adapter proves it structurally: the demo host, and the platform's own is-live flag set to false. If the venue cannot prove it, attach is refused.
    - Every guardrail, HALT and §9.5 rulebook stays active and unchanged.
    - Entering practice mode needs the human token, as `live` does, but NOT §14. The venue holds no real money, so §14 has nothing to certify.
    - Paper mode keeps its "never an order path" law untouched.
  - **Why it is safe:** it adds an order path only where no real money exists. It must land in master §7.5/§12 and ACIS-08 as spec text, with tests proving that a live-flagged venue is refused in practice mode.
  - **When the text lands:** in the ACIS-13 review pass. The SPEC-AUTHOR drafted wording for this in the draft's Appendix B.
- Linked: [[GAP-P12D-70]], [[GAP-P12D-43]], [[GAP-0018]], [[GAP-P12D-52]]

## GAP-P12D-68: the strategy-layer redesign — the coupled owner decisions the five-agent pass produced
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — the triage home for the design proposals from [[GAP-P12D-52]] that are not defects of the existing code. Each item gets its own ID when the owner rules on it and work starts. They share this entry because they are one coupled redesign that the evidence argues for together, and because each depends on the validation protocol ([[GAP-P12D-33]]) and on the objective ([[GAP-P12D-62]]))
- Area: master §2 (the conflict table), §3.7 (instruments), §4 (NVMA), §5 (QIEA), §5.5–5.7 (AGON modules, provenance, lifecycle), §14; specs/ACIS-02/-03/-04/-05; config/instruments.yaml
- Description: the proposals, with where each came from and what it needs:
  1. **Position policy:** sleeve TARGET positions, a no-trade band and cross-sleeve netting, replacing per-tick event orders and the §2 "opposite ⇒ both die" row. **[spec]**, critical.
     - The ARCHITECT proposes it, and the 2026-09-16 signal-to-position research backs it.
     - It is the real fix for [[GAP-0075]], and a precondition for any venue ([[GAP-P12D-57]]).
  2. **Module set v2.** **[spec]**. From the ARCHITECT; supported by [[GAP-P12D-49]], [[GAP-P12D-40]] and [[GAP-P12D-63]], and by the BUILDER's finding that TSMOM vetoes other modules' opposite signals.
     - **Retire** to the graveyard, with revival conditions: MOMENTUM_SCALP, the 1-minute MEAN_REVERSION, PAIR_DIVERGENCE (EURUSD/USDJPY is an identity, log EUR/JPY), and the 1-minute FX TREND/BREAKOUT.
     - **Rebuild** TSMOM as a faithful slow sleeve; see [[GAP-P12D-53]].
     - **Add** INTRADAY_MOMENTUM, SCHEDULED_WINDOW (fixes and flows) and INDEX_REVERSAL.
  3. **Demote NVMA to a safety veto.** `RegimeType` would stop routing modules and keying parameters, and the regime factor would leave sizing. **[spec]**. The evidence: the label recovers 3.7% of the planted signal ([[GAP-P12D-32]] code-grounded report), and [[GAP-P12D-39]].
  4. **Retire per-regime QIEA from the live parameter path.** Parameters would be literature-fixed and pooled, and "evolution" would become the §5.7 hypothesis lifecycle. **[spec]**. The per-regime sample fragmentation is in the 2026-09-16 statistics report.
  5. **Declare index CFDs and energies** (US500, US100, GER40, XTI) with exchange-anchored calendars. That is where the strongest prop-compatible evidence lives: intraday momentum, which holds "everywhere" (Baltussen et al. 2021). **[impl]** for config, but with the owner's go (the diversification-basket precedent).
  6. **RSIM:** a fast bar-level, target-position research simulator. It imports the SAME C8 `CostModel`, financing and calendars and includes a prop-rules engine, and it carries the reconciliation test with the tick harness that the VALIDATOR specified. **[impl]**.
  7. **A hypothesis registry with pre-registration and a look budget.** It records origin, numeric falsifiers and data-segment looks, and extends the existing provenance store. **[impl]** plus **[spec]**, with the replication/discovery standards: t ≥ 2 after publication for published priors; t ≥ 3 plus honest-N DSR/PBO for novel ideas.
  8. **A cost-robustness gate:** gross/cost ≥ 3 at registration, and net > 0 at 2× cost at validation. **[spec]**.
  9. **Track A demo scope.** Run ONE minimal pre-registered sleeve at minimum size, not the six-module engine, so the demo doubles as forward incubation, the only uncontaminated test ([[GAP-P12D-66]]). **[owner decision]**.
  10. **TSMOM account fit.** FTMO Standard funded accounts ban weekend holds, so the choice is Swing or a declared Friday-flat variant. **[spec]**.

  The ARCHITECT's 13-hypothesis pre-registered slate (archive/RESEARCH_EDGE_FACTORY_2026-09-24.md §4) is the first input to item 7. It was selected WITH LLM help, so under [[GAP-P12D-66]] it can be falsified on history but certified only forward.
- Justification: open, owner-owned. Nothing here is built, and nothing is a defect of existing code; each item changes a ratified design. Recommended order:
  1. First, the validation protocol ([[GAP-P12D-33]]), the look register ([[GAP-P12D-64]]) and the leakage suite ([[GAP-P12D-65]]), so that any redesign is graded honestly.
  2. Then the position policy (item 1), which is also a Track A blocker.
  3. Then the module set and instruments (items 2 and 5) together with RSIM (item 6).
- **Progress 2026-09-25:** the redesign's direction is RATIFIED (R-1) and its specifics too (R1-D1..D14, master v2.21). What remains is the build, R1.0–R1.7 (TODO START HERE).
- Linked: [[GAP-P12D-52]], [[GAP-0075]], [[GAP-P12D-49]], [[GAP-P12D-62]], [[GAP-P12D-33]], [[GAP-P12D-66]], [[GAP-P12D-39]]

## GAP-P12D-67: the ratified 2-year rolling train window throws a real edge away — it realises Sharpe 0.15 from a true 0.44
- Severity: high · Likelihood: medium
- Status: open (2026-09-24 — measured by the VALIDATOR in [[GAP-P12D-52]] on synthetic data: 60 configurations, 12 development years. Not re-run by the lead; the scripts are in the session scratchpad under validator/)
- Area: tests/backtest/OOS_VALIDATION.md (walk-forward design RATIFIED 2026-07-21: 2-year train / 1-year test / 1-year step), tests/backtest/oos_plan.py
- Description: selecting on a 2-year rolling train window is so noisy that most of a genuine edge is lost to selection error. With a true best-config Sharpe of 0.44, the realised out-of-sample Sharpe is only 0.15. Training on all prior years instead (an expanding window) lifts detection power from 66% to 74% at a true 0.94.
- Justification: open, owner-owned, because the fold design is ratified. It bears directly on "iterate until we find the edge": a design that discards most of a real edge makes a true negative likelier, and pushes the iterator to keep revising, which is the false-positive channel in [[GAP-P12D-64]]. Proposal: an expanding train window, or CPCV per the VALIDATOR's option C ([[GAP-P12D-33]]).
- **Progress 2026-09-25 (R-1, R1-D1 RATIFIED):** the expanding window is now the spec (ACIS-09 v1.7; OOS_VALIDATION.md amended). Fixed families need only their lookback warm. The code change (`oos_plan.py`) is the remaining [impl].
- Linked: [[GAP-P12D-52]], [[GAP-P12D-33]], [[GAP-P12D-64]]

## GAP-P12D-66: an LLM-originated hypothesis cannot be certified on any history the model was trained on — for this session that is ALL of 2012–2025, the holdout included
- Severity: high · Likelihood: high
- Status: mitigated (2026-09-24: the rule is now LAW, master v2.19 §5.6 "LLM-contamination law", adopted under the owner's in-chat delegation. The enforcement is NOT built yet: an origin/cutoff field in the attempt registry, and a grader that refuses a pass on pre-cutoff data for LLM-origin hypotheses. It is owned by [[GAP-P12D-68]] item 7). Originally proposed by the VALIDATOR and the ARCHITECT in [[GAP-P12D-52]]. The lead verified the anchor source: Gençay, arXiv 2608.27734 (27 Aug 2026) "rejects every LLM-discovered strategy (across two frontier models, search budgets up to one hundred candidates, and five repeated runs)". The VALIDATOR quotes five more 2023–2026 papers on LLM memorisation and look-ahead)
- Area: master §5.6/§5.7 (provenance, the hypothesis lifecycle), specs/ACIS-11 (the attempt registry), the research factory ([[GAP-P12D-68]] item 7), the §14 grading
- Description: LLMs reproduce financial history from before their cutoff. So when an LLM helps generate or refine a strategy hypothesis — this session's agents included — a backtest over the model's training window tests the model's memory, not the market. This session's model cutoff is June 2026, which covers the entire Dukascopy set (2012–2025) AND the locked 2024–25 holdout. The ARCHITECT's slate was selected with LLM help. Proposed rule, for the owner to ratify:
  - record each hypothesis's origin and the generating model's cutoff;
  - an LLM-originated or LLM-refined hypothesis may be KILLED on any history, but counts toward a pass only on data after that cutoff, i.e. forward on the demo;
  - hypotheses fully specified by a dated paper are exempt.
- Justification: open, owner-owned (§5.6/§5.7 are master-spec text). It makes forward incubation on the demo account the certifying stage, not a formality, which aligns Track B with the owner's demo priority.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-68]], [[GAP-P12D-65]], [[GAP-P12D-62]]

## GAP-P12D-65: look-ahead leakage passes every statistical gate — only a structural future-scramble test over EVERY decision day catches it, and ACIS has no such test
- Severity: critical · Likelihood: medium
- Status: open (2026-09-24 — found by the VALIDATOR in [[GAP-P12D-52]] and reproduced by the lead. **Progress 2026-09-25, merge 3:** T1 truncation, T2 future-perturbation at EVERY decision point, the T7 controls that bite, and T6 gap-through exits are MERGED, with the auditors' leak classes as standing controls. Still open: T3, T4 (config provenance), T5 and T8 (the decision-time accessor, the by-construction guard); R12 (AGON's code is certified only through its callbacks); R14 (in-process component sweeps can still share a memo keyed on something other than the name); R15 (no threshold-flip or re-stamp control beyond X2; non-price channels are constant on the synthetic tape; the labeller tape is too short for F3))
- Area: tests/backtest/harness.py `refuse_lookahead`, tests/backtest/test_lookahead_canary.py, the whole grading path, and any future research simulator ([[GAP-P12D-68]] item 6)
- Description: statistics cannot deflate a leak away. A leaky strategy's advantage is real in-sample and out-of-sample alike, so DSR, PBO and CPCV all pass it. Gençay (arXiv 2608.27734) reports the same: a leaky oracle with Sharpe 35 "survives Deflated Sharpe and probability-of-backtest-overfitting testing". Only STRUCTURAL tests catch it. The core one scrambles every price after time t and asserts that no decision at or before t changes, and it must cover every decision day: sampling a few catches only 15–67% (VALIDATOR), 19 of 20 at 30 samples (lead). ACIS's only look-ahead defence, `refuse_lookahead`, checks that evolution records cite no bar past the train end. It cannot see a leak inside a module, the labeller or the bar builder.
- Justification: open. **[impl]:** build the VALIDATOR's structural leakage suite (eight tests listed in archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md) as a standing gate, run over every decision day. It needs no ratification, because it is a test that tightens only.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-28]], [[GAP-P12D-33]], [[GAP-P12D-66]]

## GAP-P12D-64: re-scoring pipeline revisions on the same history is the real false-positive channel, and ACIS counts none of them
- Severity: critical · Likelihood: high
- Status: mitigated (2026-09-25 — the [impl] half is MERGED with merge 3: the look register. Every real-data grade writes a hash-chained line first in ONE canonical register; the tier comes from the source object; one line is one grade; each outcome is recorded; `run_walk_forward` refuses without it)
- Area: the research process itself; the attempt registry (specs/ACIS-11); tests/backtest/report.py; the owner's "iterate until we find the edge"
- Description: every time the pipeline, gene ranges, regime definitions, fitness weights or cost model change and are re-scored against 2012–2023, that is another trial. Nothing counts it. On pure noise:
  - keeping the best of 5 uncounted revisions passes 9–19% of the time;
  - the best of 20 passes 21–37%;
  - at 24 years of data it is still 26%.

  The honest single-look tests (walk-forward + PSR, one pre-registered configuration, the 2-year holdout) stay at 2–6% false positives. It is the ITERATION that manufactures the false pass. The iteration the owner asked for is exactly what this entry guards. At our data length, also: no protocol reliably detects a Sharpe near 0.5 in 12 years (power 25% at a true 0.44), so "no pass" is the NORMAL outcome even when an edge exists. That is a limit of the data, not a verdict on the engine.
- Justification: mitigated — the register counts every look, so an uncounted revision is now structurally impossible through `run_walk_forward`; turning the count into a verdict is owned by the residuals.
  - **[impl], no ratification needed:** a look register, written BEFORE every grade (BUILT, merge 3).
  - **[spec]:** raise the gate's threshold for every recorded look. That is part of the VALIDATOR's option C in [[GAP-P12D-33]], the owner's decision.
  - **Until the register exists,** read any real-data pass after more than one revision as unproven.
- Proof: `test_the_grade_refuses_before_any_compute_without_its_own_line`, `test_one_line_is_one_grade`, `test_forged_deleted_or_edited_lines_break_the_chain_and_the_register_fails_closed`.
- Residual: GAP-P12D-89 — the verdict computed OVER the register (declared, hashed search spaces; fixed combinations); GAP-P12D-98 — the daily return vector per grade; GAP-P12D-86 — durability. The [spec] half is PLAN_R1's A2 (R1-D2), awaiting the owner.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-33]], [[GAP-P12D-67]], [[GAP-P12D-68]]

## GAP-P12D-63: MOMENTUM_SCALP can never fire on the synthetic falsification markets, so no falsification run has ever tested it
- Severity: medium · Likelihood: high
- Status: open (2026-09-24 — found by the BUILDER agent in [[GAP-P12D-52]] while refuting [[GAP-P12D-38]]. The lead VERIFIED the consequence: zero MOMENTUM_SCALP trades in every ladder rung's per-strategy attribution)
- Area: tests/backtest/synthetic_market.py (uniform 20-second tick cadence), core/signals/agon.py `_momentum_scalp` (tick-velocity surge gate), scripts/falsify_engine.py
- Description: the synthetic markets emit ticks on a uniform 20-second clock, so tick velocity always equals its session median. The scalp's surge gate therefore never opens. At a ratio of 1.0 its conviction (0.333) also sits under the 0.45 discard floor, so the module is doubly dead. The consequences:
  - the positive and negative controls say nothing about MOMENTUM_SCALP;
  - the §14 scalp duration carve-out is empty in every synthetic run;
  - the 1-minute scalp is untested end to end, and live trading would be its first exercise.
- Justification: open. Two routes:
  - add a synthetic tape with realistic tick-rate variation, so the module can be exercised and falsified;
  - or retire MOMENTUM_SCALP. The ARCHITECT recommends retiring it ([[GAP-P12D-52]] slate: the prop playbook and the cost–horizon identity argue against a 1-minute scalp), and the ECONOMIST's paid-minority evidence says slow trading.

  That choice is part of the owner's module-set decision.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-38]], [[GAP-P12D-47]], [[GAP-SP12I-03]]

## GAP-P12D-62: §14 cannot tell skill from luck on a prop account — a disciplined ZERO-edge strategy is already +EV there, so a pass, a payout or a positive EV proves nothing
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — found independently by the ECONOMIST and the ARCHITECT in [[GAP-P12D-52]]. The lead VERIFIED the core identity by reasoning: optional stopping on a zero-drift process stopped at a static floor, withdrawing everything above it, gives E[lifetime withdrawals] = the loss buffer. The ECONOMIST's simulation measured 0.1013 against 0.1000. The two agents' Monte Carlo figures agree on the ARCHITECT's shared cells: zero-edge pass rate 0.25 vs 0.28; Sharpe 1.0 at 0.6%/day, P(pass) 0.73 vs 0.78, median days 259 vs 271)
- Area: ACIS_SPEC.md §14 (targets) and §17 (non-goals); ACIS-09 grading (tests/backtest/report.py); the owner's reading of any demo or prop result
- Description:
  - **The account is an option.** On a static-floor funded account the fee caps the downside, so the account is an option on the trader's P&L. A disciplined strategy with NO edge is therefore +EV: its expected lifetime withdrawals equal the max-loss buffer, and the trader keeps the split share of that, less the fee.
  - **Luck passes often.** A zero-edge strategy passes an FTMO 2-Step about 25–28% of the time.
  - **So none of these is evidence of skill:** a pass, a payout, or EV > 0.
  - **§14 grades the wrong thing for this route.** It asks Sharpe > 1.5, PF > 1.4, > 70% positive months and a win rate, and measures none of P(pass), time to pass, P(breach), EV net of fees, or the comparison with a zero-edge control.
  - **The data cannot certify the realistic band.** Two out-of-sample years cannot certify any Sharpe in the realistic 0.3–0.7 band: the standard error is ≈0.75 (Lo 2002), so certifying 0.5 at one-sided 95% takes ≈12 years.
  - **The duration row works against the cost identity.** §14's 30 min–48 h row excludes the multi-day holds that clear costs: the per-trade hurdle is 0.010 IR for a 5-day hold against 0.239 for a 13-minute hold at 1 bp.
- Justification: open, owner-owned, because §14 and §17 are master-spec text.
  - **The ECONOMIST's proposal, "PropEV"** (archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md §3.1). For rule-restricted accounts, add it beside §14 or replace its Sharpe, positive-months and win-rate rows with it. It reports EV net of fees (90% interval), P(pass within 60/126 days), P(breach within 6 months), payouts per year, and **ΔEV against a zero-edge control run through the identical rules**. It is fed by a stationary block bootstrap of out-of-sample daily P&L, costed at the firm's schedule.
  - **Its gates:**
    - G1 (the skill test): EV beats the zero-edge control at the lower 90% bound;
    - G2: EV > 0 at the lower bound after a 25% payout haircut;
    - G3: P(breach within 6 months) ≤ 0.25;
    - G4: the order and request profile fits the firm's caps.
  - **Anti-playbook as a §17 extension.** The EV-maximising risk at zero edge is "bold play", variance harvesting that firms police. ACIS must never size up because its edge is weak.
  - **The VALIDATOR's prop-gate design (2026-09-24).** Under illustrative rules, a zero-edge strategy passes 49.7% of challenges and Sharpe 1.0 passes 74.9%, so position size matters more than edge. Estimates of P(pass) from records of two years or less swing by 10–40 points, and their 95% bands cover the truth only 75–92% of the time. So gate on EV and breach risk computed at the LOWER confidence bound of the Sharpe, next to a zero-edge baseline at the same size. That agrees with the ECONOMIST's G1.
  - **The §14 "Sharpe > 1.5" row, measured:** it detects a true Sharpe of 0.94 only 1.5% of the time, yet lets noise through 7–11% of the time on 2-year windows under continued iteration.
  - **Until the owner rules,** read any prop or demo pass as an option paying out, never as evidence of edge.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-61]], [[GAP-P12D-33]], [[GAP-P12D-37]], [[GAP-P12D-44]]

## GAP-P12D-61: ACIS's realised risk is ~0.04% of NAV a day — 20–30× below what a prop account needs — because the Governor sizes a fixed notional, not a loss budget
- Severity: critical · Likelihood: high
- Status: open (2026-09-24 — found by the ECONOMIST in [[GAP-P12D-52]]. The lead VERIFIED the arithmetic: the ladder's 1x rung lost $147.84 over 2.05 graded years at Sharpe −1.12 on the harness's $10,000 NAV (tests/backtest/harness.py `nav: Decimal = Decimal("10000")`). That is −0.72%/yr at 0.644% annual volatility, i.e. **0.0406% a day**)
- Area: core/governor/capital_governor.py (notional sizing from `base_unit_usd`), config/system_config.yaml (`base_unit_usd: 1000.0`), specs/ACIS-05 (sizing contract), master §6 and §9.5 (taper), tests/backtest/metrics.py (no realised-risk metric)
- Description:
  - **Risk is far too small.** The Governor sizes `base_unit_usd` (a fixed $1,000 notional) times dampening factors, so ACIS carries about 0.04% of NAV in daily P&L volatility. The ECONOMIST's EV-maximising band for a funded account is 0.75–1.5%/day in the challenge. When funded it is ~10% of the cushion to the binding floor per day, capped near 1%/day, withdrawing everything at each payout date.
  - **What that costs.** At 0.04%/day, the closed form gives EV = −fee for EVERY Sharpe ≤ 1.0: the challenge would take decades, so the fee is lost to time.
  - **Two further contradictions with the evidence:**
    - The §9.5 taper keeps full size until 60% of a limit is consumed, whereas the optimum shrinks in proportion to the cushion from the start. That refinement stays inside the law: it only tightens.
    - Realised risk is not a reported metric, which is why this went unseen.
  - **Link:** [[GAP-P12D-57]] (orders below the minimum lot) is the same fact seen from the execution side.
- Justification: open, owner-owned (ACIS-05 sizing contract).
  - **[spec]:** replace the fixed notional unit with a daily loss budget, as a fraction of the account's declared initial balance. Make it proportional to the cushion to the binding platform floor, composed by min() with the §9.5 taper and C16. Add a withdrawal policy: the funded stage is a de Finetti-style barrier problem.
  - **[impl], needs no ratification:** report daily P&L volatility as a % of initial NAV in every grading run.
  - **SEQUENCING WARNING:** raising risk on a strategy with no edge ([[GAP-P12D-49]]) only loses the account faster. Sizing is fixed together with, never ahead of, the edge work.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-57]], [[GAP-P12D-62]], [[GAP-P12D-49]], [[GAP-P12D-56]]

## GAP-P12D-60: the non-FTMO prop rulebooks are wrong about their firms, and two rulebook fields are enforced nowhere
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — found by the SCOUT agent in [[GAP-P12D-52]], quoting each firm's own pages, grade (a). The lead checked the FundedNext quote against the firm's help centre; the rest rest on the SCOUT's quotes in archive/RESEARCH_PROP_VENUES_2026-09-24.md §8.2. The rulebook is human-committed, so this is RAISED, not changed)
- Area: config/platform_rules.yaml (`fundednext`, `the5ers`, `atlas_funded`); config/account_doctrine.py; master §9.5 / C-BT-7
- Description: three entries contradict their firms. Each is a separate policy value with its own disposition; they share one entry only because retiring unused firms is one owner decision.
  1. **`fundednext`** names `platform: ctrader` with "EAs on all programs". FundedNext "does not allow the use of EAs or automated trading on the cTrader and Match-Trader platforms regardless of account size". Automation there is MT4/MT5 only, as paid add-ons, which means a Windows terminal.
  2. **`the5ers`** names `platform: ctrader`; per the SCOUT, The5ers is MT5-only. It also bans "Bulk trading, is when multiple trades are open simultaneously", and says "no Automated Trading Software may be used unless the Company has given prior written approval". The entry models neither.
  3. **`atlas_funded`** sets `min_hold_seconds: 0`, but Atlas bans trades held under 3 minutes (expressible as `min_hold_seconds: 180`).

  Separately, two rulebook fields have no consumer in `core/`, `tests/backtest/` or `scripts/`: `consistency_max_day_profit_pct` and `min_trading_days`. Only config/account_doctrine.py carries them. `min_hold_seconds` is graded after the fact in the backtest and gates scalp eligibility, but nothing enforces it at run time.
- Justification: open and RAISED.
  - **Owner decision:** correct each entry, or retire firms ACIS will not use. The SCOUT ranks FundedNext third (Windows MT5 only), The5ers fourth (written approval needed) and Atlas fifth (Kenya eligibility unconfirmed).
  - **The unenforced fields** are a C-BT-7 honesty gap for whichever firm is chosen, and belong with [[GAP-P11I-02]]'s residual.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-54]], [[GAP-P11I-02]], [[GAP-P12D-43]]

## GAP-P12D-59: the engine's daily limit is a session halt that clears at the next session open, its day is not the firm's day, and no platform breach flattens
- Severity: high · Likelihood: medium
- Status: open (2026-09-24 — found by the SCOUT agent in [[GAP-P12D-52]]. The lead verified the code paths: core/risk/guardrails.py routes an `engine:daily` breach to `_issue_session_halt` and every platform breach to `_issue_halt("all", …)` with no flatten; core/governor/capital_governor.py `apply_session_halt` clears at `next_boundary(now, self._boundaries)`. Guardrail semantics, so RAISED)
- Area: core/risk/guardrails.py; core/governor/capital_governor.py; master §8 (daily loss) and §9.5 ("Open positions and their stops are untouched"); config/platform_rules.yaml
- Description: three things combine into a breach path at firms with tight daily limits.
  1. **The engine's 2% daily breach is a SESSION halt.** It auto-clears at the next session boundary, which can be the Tokyo, London or New York open, not the next trading day.
  2. **The engine's day is not the firm's day.** The engine day starts at 17:00 New York. FTMO's starts at 00:00 CE(S)T, one hour later for most of the year and two hours later in the weeks when US and EU daylight saving are out of step. So one firm-day can hold the tail of one engine day and the head of the next: up to two 2% engine budgets, plus whatever open positions lose after the halt.
  3. **A platform-limit breach HALTs entries but never flattens.** This is per master §9.5, so open positions keep losing past the firm's line.

  Against FTMO 2-Step's 5% daily limit this is tight but inside. Against FTMO 1-Step's 3%, E8 One's 3%, E8 Pro's 2.5% and The5ers Hyper Growth's 3%, a breach path exists. [[GAP-P12D-54]] point 4 adds a second route: carried floating losses, when the firm anchors on balance and the engine on equity.
- Justification: open and RAISED; owner-owned.
  - **What the fix needs:** a per-account daily boundary in the firm's zone; a pre-breach FLATTEN on platform limits, which changes the §9.5 sentence above; and deciding whether the engine's daily halt should last until the next trading day rather than the next session.
  - **Why it is raised, not fixed:** all of these are HALT/veto semantics, which are human-only.
- **Progress 2026-09-25 (BUILDER-3 merge):** fixed parts: the session latch re-arms each day (GAP-P12D-80), and per-account daily rules reset in the FIRM's zone (Europe/Prague for FTMO). The pre-breach FLATTEN on platform limits remains [spec]: master §9.5 still says "open positions and their stops are untouched". That stays an owner decision.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-54]], [[GAP-P12D-55]], [[GAP-0010]]

## GAP-P12D-58: FTMO forbids "gap trading" on every account, and ACIS's pre-close entry ban switches off whenever weekend holding is allowed
- Severity: high · Likelihood: high
- Status: mitigated (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). The pre-close entry ban binds EVERY account, the no-holding flatten runs before the weekend and before every declared FX holiday closure, and Dec 25 / Jan 1 for 2025–2027 are declared; ACIS-05 v1.5 / master v2.20)
- Area: core/governor/capital_governor.py (entry gates); config/platform_rules.yaml; master §9.5; [[GAP-P12D-03]] (the event calendar)
- Description: FTMO's forbidden practices include "gap trading", defined as opening trades "two hours or less before a relevant financial market is closed for at least two hours" and "when major global news, macroeconomic events, or corporate reports or earnings are scheduled". The page limits this to no account type, so it covers Swing accounts too.
  - **ACIS's gate is tied to the wrong flag.** Its 2-hour pre-close entry ban (`weekend_entry_buffer_s`) runs only when `weekend_holding_allowed` is false. On an FTMO Swing account (weekend holding allowed), ACIS would open trades in the last two hours before the Friday close, which is a forbidden practice.
  - **The event calendar is needed after all.** The news half of the clause refutes the prior venue pass's claim that a Swing account removes the need for the event calendar ([[GAP-P12D-03]]).
  - **Spec and code disagree.** Master §9.5 says weekend bans mean "positions flattened before the ban window by policy", but nothing in `core/` flattens before a weekend; only entries are banned.
- Justification: open.
  - **[impl]:** decouple the pre-close entry ban from the weekend-holding flag.
  - **[spec]:** a rulebook field for "pre-close entry ban" and a scheduled-news entry blackout, independent of the news-restricted flag; plus the missing weekend flatten, or amending §9.5's sentence.
  - **Precondition for Track A:** this is a hard precondition before pointing ACIS at any FTMO account, the free trial included, because the trial runs the same rules.
- Proof: `test_swing_account_refuses_an_entry_an_hour_before_the_friday_close`, `test_no_entry_opens_in_the_two_hours_before_a_holiday_closure`, `test_a_no_holding_account_is_flattened_before_a_holiday_closure`, `test_flatten_starts_with_the_entry_ban_and_names_each_position`.
- Justification: mitigated. Two things remain. The NEWS half of FTMO's gap-trading clause needs the historical and live event calendar, GAP-P12D-03. The holiday list is an ANNUAL obligation, to re-verify against the firm's table each December; non-FX calendars are not declared yet.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-03]], [[GAP-P12D-54]]

## GAP-P12D-57: the execution path ignores the venue's quantity and request limits — sub-minimum orders, no lot-step rounding, no daily request budget
- Severity: high · Likelihood: high
- Status: mitigated (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). Lot-step round-down and the minimum-lot refusal, the rolling venue request budget (1,000 a day, surviving restarts) and close pacing are enforced; ACIS-06 v1.3 C-EXE-6/8)
- Area: core/execution/orchestrator.py, core/execution/venue.py, core/governor/capital_governor.py (sizing quantised to 0.01 units), config/system_config.yaml (`base_unit_usd: 1000.0`, `fragment_threshold_lots: 1.0`); [[GAP-0075]]
- Description:
  1. **Orders are below the venue minimum, and nothing rounds them.** The Governor sizes `base_unit × conviction × liquidity × correlation × regime × marginal_alpha × vol_norm × taper` and quantises to 0.01 units, not to the venue's lot step. The SCOUT's arithmetic gives a typical EUR/USD order of about 332 units (≈0.0033 lot) and a neutral one of 926 units, against a common 0.01-lot minimum of 1,000 units (FTMO's and E8's own values are unverified). Most orders are un-placeable. The honest fix rounds DOWN, which makes most orders zero, because rounding up would break the Governor's clamp-only-downward law. Sizing therefore has to become NAV-relative for a prop account, and that is a spec decision.
  2. **Nothing enforces a request budget.** FTMO and E8 cap an account at 2,000 server requests a day, plus 200/100 open orders. The composed loop sized about 2,700 decisions per trading day on the planted falsification run, so without a position-aware gate ([[GAP-0075]]) the cap breaks on day one. Fragmentation above `fragment_threshold_lots` adds a request per fragment.
- Justification: open.
  - **[impl]:** lot-step and minimum-lot enforcement in the adapter/orchestrator (a missing capability is a refusal, never silent rounding up), and a hard adapter-level daily request counter. The SCOUT suggests holding it at ≤1,000 a day, half the cap.
  - **[spec — owner ratification]:** NAV-relative prop sizing.
  - **Precondition for Track A:** both are preconditions before ACIS is pointed at any venue.
- Proof: `test_quantity_rounds_down_to_whole_steps_and_refuses_below_the_minimum`, `test_request_budget_is_a_rolling_24_hours`, `test_a_close_is_admitted_and_counted_past_the_budget`, `test_a_refused_close_is_paced_not_resent_every_tick`, `test_the_pace_survives_a_restart`.
- Justification: mitigated, not closed. With lot steps enforced, most of today's orders (about 330 units) now round to ZERO: correct and safe, but the engine cannot trade a prop account until sizing becomes NAV-relative, which is owned by GAP-P12D-61 [spec].
- Linked: [[GAP-P12D-52]], [[GAP-0075]], [[GAP-P12D-56]], [[GAP-P12D-27]]

## GAP-P12D-56: the equity floor is an absolute $9,000 sized for a $10k paper account — it halts any smaller account at start-up and gives no warning on a $10k prop account
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — found by the SCOUT agent in [[GAP-P12D-52]]. The lead VERIFIED config/guardrail_limits.yaml (`equity_floor_usd: 9000.0  # dev/paper account assumed 10k start — human-owned`) and core/risk/guardrails.py `check`, which flattens everything and issues a global HALT, human-only resume, the moment equity < floor. The equity floor is on CLAUDE.md's never-touch-without-a-human list, so this is RAISED only)
- Area: config/guardrail_limits.yaml `equity_floor_usd`; core/risk/guardrails.py (the equity breaker); master §8; the scenario-replay ceilings calibrated at $10k (ACIS-12)
- Description: the floor is an absolute dollar figure, not a fraction of the account.
  - **Any account under $9,000** (FundedNext $6K, E8 or The5ers $5k, the owner's ~$6k target) flattens and HALTs at its first evaluation, so the engine cannot trade at all.
  - **On FTMO 2-Step $10k,** the floor sits exactly on FTMO's max-loss line ($9,000). By the time ACIS flattens, FTMO has already failed the account.
  - **On E8 Pro $10k** (8% static, a line at $9,200), E8 fails the account first.
  - **On a large demo account** (free trials are often $100k or more), the floor never fires.
- Justification: open, owner-owned. Before any demo or prop account is attached, the owner must set the floor for that account (the ratified guardrail law allows only a human commit). A value below the firm's max-loss line is useless; above it but below the start is the only range that protects. The scenario-replay ceilings and Governor caps calibrated at $10k need the same re-check (the TODO "What the decision re-aims" item 3). A floor defined relative to declared initial capital would stop this recurring per account, but that is a guardrail-shape change for the owner.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-55]], [[GAP-P12D-57]], [[GAP-0108]]

## GAP-P12D-55: a process restart relaxes every drawdown limit — the anchors live only in memory and re-base at the first equity seen after boot
- Severity: critical · Likelihood: high
- Status: fixed (MERGED 2026-09-25 (BUILDER-3 branch, owner's explicit go; the constitution's two audits GAP-P12D-77, every finding fixed and the blockers re-verified by the lead on the auditors' own repros). The drawdown anchors and the day-open anchor persist and are restored before the first evaluate; ACIS-07 v1.2)
- Area: core/risk/guardrails.py (`DrawdownSeries._anchors`, `_RuleAnchor`); core/risk/store.py (`save_restrictive_state`); core/risk/monitor.py (`restore_restrictive_state`); deploy/systemd (`Restart=` supervision); master §8/§9.5; ACIS-07
- Description:
  - **Nothing on disk remembers where the account started.** `DrawdownSeries._anchors` is an in-memory dict. The static inception anchor, the trailing high-water mark and the engine's daily day-open anchor are never persisted. The static anchor is also "the first observed basis", not a declared initial capital. So after any restart, every drawdown measure re-bases to the current equity or balance and reads 0%.
  - **Example:** on an FTMO $10k account at −6%, a restart hands ACIS a fresh 10% budget while FTMO has 4% left.
  - **The persisted taper is never used.** `save_restrictive_state` persists `taper_factor`, but `restore_restrictive_state` restores only `alpha_armed`. Nothing in `core/` reads the saved taper back.
  - **It breaks a principle the risk layer already declared.** Its own principle is "a restart is never a relaxation" ([[GAP-0050]]). [[GAP-P9E-01]] fixed only the calendar reset of the trailing anchor.
  - **Supervision makes it worse.** Under systemd, whose job is to restart a crashed engine, a crash loop resets the budget on every restart.
- Justification: open and RAISED; blocks Track A before any account is attached. The fix restores strictness rather than weakening anything, but it touches HALT/guardrail state, so it goes to the owner.
  - **Candidate fix:**
    - declare each account's initial capital in the rulebook, and anchor static rules on it;
    - persist the trailing high-water mark and the day-open anchors, or reconstruct them from the broker's balance history at boot;
    - restore the saved taper;
    - regression tests for restart at a drawdown, falsified per A16.
  - **Interlock:** it interlocks with [[GAP-P12D-54]]'s schema change (daily limits anchored on the balance at a named reset instant).
- Proof: `test_restart_at_a_drawdown_still_reads_it_on_every_rule`, `test_restart_across_a_trading_day_boundary_reanchors_the_daily_rule`, `test_a_loss_taken_while_the_engine_was_down_is_not_forgotten`, `test_restore_refuses_a_corrupt_anchor_and_skips_a_retired_rule`.
- Residual: GAP-0091b — the production three-loop runtime must call the restore at boot (the runtime does not exist yet).
- Linked: [[GAP-P12D-52]], [[GAP-P12D-54]], [[GAP-P12D-56]], [[GAP-0050]], [[GAP-P9E-01]], [[GAP-0102]]

## GAP-P12D-54: the `ftmo` rulebook contradicts FTMO's published rules in both directions, and the §9.5 schema cannot express FTMO's daily loss
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — found by the ARCHITECT agent in [[GAP-P12D-52]]. VERIFIED by the lead against FTMO's Trading Objectives page (ftmo.com/en/trading-objectives, modified 2026-05-13) and against core/risk/guardrails.py. Guardrail-adjacent, and the rulebook is human-committed, so it is RAISED, not changed)
- Area: config/platform_rules.yaml `ftmo`, and every rulebook drafted on the same `prop_demo` pattern; core/risk/guardrails.py `_RuleAnchor` / `build_drawdown_series`; config/schemas.py `DrawdownRule`; master §9.5
- Description: FTMO's 2-Step rules, quoted from its page:
  - **Maximum Daily Loss:** a limit "below which your account equity … cannot drop". It equals "the account balance recorded at 00:00 CE(S)T of the current day" minus "5% of the Initial Simulated Capital". Equity is "Balance + Open Positions P/L ± Swaps – Commissions".
  - **Maximum Loss:** "a static limit … below which your account equity … cannot drop", set at initial capital minus 10%.

  The rulebook models neither correctly:
  1. **Max loss is modelled on BALANCE** (`type: static`, `basis: balance`). `guardrails.py:96` measures such a rule on the closed balance only, so floating losses on open positions are invisible to it. That is LOOSER than FTMO, which measures equity.
  2. **The "daily" rule is not daily in code.**
     - `type: trailing, basis: equity` becomes a high-water mark since INCEPTION that "NEVER resets" (the `_RuleAnchor` docstring). `build_drawdown_series` also marks every platform rule as never resetting daily.
     - So ACIS actually enforces a LIFETIME 5% trailing drawdown from peak equity.
     - Under the ratified taper, it starts cutting size 3% below the peak and stops new entries at 4%. For a strategy running at 0.5–0.7%/day, those are ordinary swings. That is far STRICTER than FTMO, and on its own it makes a +10% target hard to reach.
     - It is occasionally LOOSER as well. FTMO anchors on the midnight BALANCE, so when realised gains sit beside floating losses (balance above the equity high-water mark), FTMO's floor is the higher of the two.
  3. **The schema cannot say what FTMO says.**
     - `DrawdownRule` has only type / anchor / basis / limit_pct. It cannot express a limit anchored on the balance at a named reset instant in a named timezone, sized as a percentage of INITIAL capital.
     - The rulebook carries no reset instant at all.
     - FTMO's 1-Step product (3% daily; an end-of-day trailing max loss that resets on withdrawal) and its Best Day rule are also unmodelled.
  4. **The config header's claim is false when positions carry floating losses across the day boundary.** The header says "ACIS's own 2% daily guardrail is far inside every prop 5% daily, so ACIS essentially cannot breach a prop daily limit". But the engine's daily limit (`daily_drawdown_pct: 2.0`) anchors on EQUITY at the 17:00 New York rollover, while FTMO anchors on BALANCE at 00:00 CE(S)T. Worked example on a $6,000 account:
     - At the rollover the balance is 6,000, with a −240 floating loss, so the engine's anchor is 5,760 and its daily halt comes at 5,644.80.
     - FTMO's floor is 6,000 − 300 = 5,700.
     - FTMO is breached 55.20 before the engine's daily guard fires.
- Justification: open and RAISED.
  - **Why it matters.** Two things read the account doctrine: §14 grading (C-BT-7, rules active during the run) and live halts. A rulebook that is wrong about the firm therefore corrupts the backtest and the account at once, in both directions.
  - **What fixing it needs:**
    - (a) a human config commit;
    - (b) probably an extension to the schema and to `_RuleAnchor`, adding balance-at-reset anchors in a named timezone with limits as a percentage of initial capital. That is a §9.5 / ACIS-07 change for owner ratification.
  - **Coming next.** The SCOUT agent is verifying every firm's rules, and its corrections list lands here.
  - **Until then**, no backtest or demo on an FTMO account may be read as faithful to FTMO's rules.
- **Progress 2026-09-25 (BUILDER-3 merge):** the schema CAN now express FTMO's daily loss (a `daily` rule type with `reset: {zone, at}`, `reset_basis`, and limits as a % of `initial_capital`), and the tests reproduce FTMO's own worked examples (`test_ftmo_day1_floor_is_95000_on_equity`, `test_ftmo_day2_floor_is_97000_after_a_102000_close`). What remains is OWNER-ONLY: committing the corrected `ftmo` entry, and an `e8` entry once E8's server time zone is verified (drafts in archive/BUILDER3_REPORT_2026-09-24.md §4), plus the FTMO 1-Step rule type (audit X7, not built).
- Linked: [[GAP-P12D-52]], [[GAP-P11I-02]], [[GAP-0102]], [[GAP-P12D-44]]

## GAP-P12D-53: master §5.6 misstates the century trend-following evidence, and the figure it quotes is the per-market one
- Severity: medium · Likelihood: high
- Status: fixed (2026-09-24, master v2.19 §5.6, applied under the owner's in-chat delegation; see TODO.md's night-run block). Originally open: found by the ARCHITECT agent in [[GAP-P12D-52]]. VERIFIED by the lead from the paper's own Exhibit 1, with the text extracted from a fresh download of Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing")
- Area: ACIS_SPEC.md §5.6, the verified-benchmark law; the expectations placed on the TSMOM module in specs/ACIS-04; and the FX-methods research report, which repeats "~0.4 in every decade"
- Description: §5.6 says the century study (1880–2016) shows "Sharpe ≈ 0.4 *every decade*". The paper's Exhibit 1 says otherwise.
  - **The full sample:** "Full Sample Jan 1880-Dec 2016 18.0% 11.0% 7.3% 9.7% 0.76". The columns are the gross excess return, net of cost, net of cost and 2/20 fees, volatility, and the net Sharpe.
  - **By decade**, the net Sharpe ratios are: 0.27, 0.73, 0.34, 0.13, 1.09, 0.74, 0.99, 1.45, 0.56, 1.70, 0.96, 0.98, 0.61 and 0.41 (2010–2016).
  - **Where "≈0.4" really comes from.** It is a different statistic: the paper reports "an average Sharpe ratio of approximately 0.4" for each INDIVIDUAL market, gross of fees and costs, across its 67 markets.
  - **The correction cuts against ACIS twice.** The canon's strong number (0.76) is a 67-market portfolio result that a 2-instrument TSMOM cannot borrow. And the number that does transfer, ~0.4 for a single market, is measured before costs.
- Justification: open and owner-owned, because §5.6 is master-spec text (v2.9, owner-directed).
  - **Proposed correction:** state the full-sample net Sharpe of 0.76 over 67 markets, the decade range of 0.13–1.70, and the per-market ~0.4 gross. Say plainly that the evidence is breadth at the portfolio level.
  - **Scope:** it changes no code and no threshold. It changes what a reader would expect of a 2-instrument TSMOM.
- Proof: ACIS_SPEC.md §5.6 now states the full-sample 0.76 over 67 markets, the decade range 0.13–1.70, and the per-market ≈0.4 gross; the v2.19 changelog records it.
- Residual: GAP-P12D-68 — what TSMOM should become in light of the corrected evidence (item 2: rebuild it as a faithful slow, broad sleeve). The archived 2026-09-16 FX-methods report still repeats the old figure; it is kept as history.
- Linked: [[GAP-P12D-52]], [[GAP-P12D-49]], [[GAP-P12D-32]]

## GAP-P12D-52: five-agent edge pass (2026-09-24) — findings and triage (5 of 5 in, triage complete)
- Severity: high · Likelihood: high
- Status: open (2026-09-24 — owner directive: five agents are to find out what the paid minority of prop-firm algo traders actually does, fix what is derailing ACIS, and find bleeding-edge ways to iterate to an edge without overfitting or poor backtesting producing "false encouragement". The pinned brief is `FIVE_AGENT_BRIEF_2026-09-24.md`. All five run on Opus, and each is a finder, not a clearer)
- Area: the venue (does it fit a fully automated prop engine, and which demo venue); the objective function for a prop account; the validation protocol ([[GAP-P12D-33]]/[[GAP-P12D-37]]); the strategy slate and research factory; the fixes that need no ratification ([[GAP-P12D-37]] oracle, [[GAP-P12D-38]], [[GAP-P12D-34]], TSMOM attribution)
- Description: the five agents and their deliverables:
  - SCOUT: prop-venue due diligence and the demo-venue recommendation. Report `RESEARCH_PROP_VENUES_2026-09-24.md`.
  - ECONOMIST: the paid-minority playbook and the expected-value mathematics of a prop account. Report `RESEARCH_PROP_ECONOMICS_2026-09-24.md`.
  - VALIDATOR: the measured false-positive rate and power of candidate validation protocols, a data budget, and a rule against LLM contamination. Report `RESEARCH_VALIDATION_FIREWALL_2026-09-24.md`.
  - ARCHITECT: a research factory, a pre-registered candidate slate, and how well ACIS's architecture fits it. It works blind first. Report `RESEARCH_EDGE_FACTORY_2026-09-24.md`.
  - BUILDER: works on a worktree branch and reports in `BUILDER_REPORT_2026-09-24.md`. Its work is BUILT — PENDING AUDIT.
  The four reports land in `archive/`, with interim checkpoints named `PARTIAL_<TOPIC>_2026-09-24.md`. One rule binds the whole pass: no agent backtests a strategy on real Dukascopy data, and nobody touches the 2024–25 holdout. Every look at real history is a trial against the scarcest resource.
- Leads from the lead's own reconnaissance. They are UNCONFIRMED (search snippets only, no primary quote yet); the SCOUT verifies them:
  1. Apex reportedly prohibits fully automated trading on funded PA accounts.
  2. Topstep reportedly permits its API but prohibits VPS or remote hosting and unattended automation. That would be incompatible with the server-hosted engine the deployment gate built.
  3. FundedNext reportedly prohibits automation on cTrader and Match-Trader: EAs are MT4/MT5 only, as a paid add-on. If confirmed, the `fundednext` entry in `config/platform_rules.yaml` ("cTrader + Match-Trader; EAs on all programs") is wrong about the world.
  4. The5ers lists bulk trading (trades open simultaneously) as prohibited, and requires prior written approval for automated software.
  5. FTMO prohibits more than 2,000 server requests per day. That is a hard budget the three-loop runtime must respect, and the per-tick behaviour in [[GAP-0075]] would breach it within minutes.
- Reports received so far:
  - **ARCHITECT** (2026-09-24): archive/RESEARCH_EDGE_FACTORY_2026-09-24.md, with its Stage 1 record in archive/PARTIAL_EDGE_FACTORY_2026-09-24.md, stamped before it opened any ACIS document.
    - **Headline, synthetic and derived by the agent — not yet cross-checked:**
      - The prop contract pays for variance. A zero-edge algorithm at ~1%/day passes both FTMO phases ~25% of the time, so passing is weak evidence of skill, and survival is what separates edge from luck.
      - Even a true net Sharpe of 1.0 at 0.6%/day needs a median of ~259 trading days to pass, then pays ~9.6% of initial capital a year while funded (~$575 on $6k).
      - The documented edges that suit a prop account are intraday flow and microstructure effects in index CFDs, gold and oil, and the FX fixings. Technical rules on FX majors are not among them.
    - It proposes 15 ledger items (its §9) and a 13-hypothesis pre-registered slate. Those are triaged after cross-checking against VALIDATOR, ECONOMIST and SCOUT.
    - Two findings were verified by the lead and filed now: [[GAP-P12D-53]] (spec misquote) and [[GAP-P12D-54]] (FTMO rulebook).
    - It disclosed three things:
      - Its Stage 1 was not fully blind, because the harness loaded CLAUDE.md and the memory index into its context.
      - One tiny run started with 835 MB free, below the brief's 1 GB rule.
      - It used 27 of its 40 WebSearch calls.
  - **SCOUT** (2026-09-24): archive/RESEARCH_PROP_VENUES_2026-09-24.md.
    - **Only two firms pass the hard filter** — a self-built, unattended engine on a funded account through an API that runs natively on Linux: **FTMO** and **E8 Markets**, both on cTrader via the Open API.
    - **Ranking:**
      1. FTMO 2-Step Swing $10k (€89, refundable).
      2. E8 Pro / E8 One.
      3. FundedNext, Windows MT5 only.
      4. The5ers, only with written approval.
      5. Atlas, blocked on Kenya eligibility.

      Apex, Topstep and Alpha Capital are out. Apex also geo-blocks Kenya. **Owner decision 2026-09-24: Apex was replaced by E8 Markets, so the shortlist is now FTMO, E8, FundedNext, The5ers.**
    - **All five of the lead's leads are CONFIRMED**, grade (a).
    - **Demo of record:** the FTMO Free Trial on cTrader. That is a §15 deviation; see [[GAP-P12D-43]].
    - **Verified and filed by the lead:**
      - [[GAP-P12D-55]]: a restart relaxes every drawdown limit. Reproduced; critical.
      - [[GAP-P12D-56]]: the $9,000 absolute equity floor.
      - [[GAP-P12D-57]]: sub-minimum orders, no lot-step rounding, no request budget.
      - [[GAP-P12D-58]]: FTMO gap trading vs a pre-close ban tied to the weekend flag.
      - [[GAP-P12D-59]]: the daily limit is a session halt; engine day ≠ firm day; no platform breach flattens.
      - [[GAP-P12D-60]]: the non-FTMO rulebooks are wrong, and two rulebook fields are enforced nowhere.
      - It also confirmed the `ftmo` basis finding in [[GAP-P12D-54]].
    - **Still pending cross-check:**
      - FTMO's 0.7% non-USD P&L adjustment: 4 of 8 declared instruments, 1 of the 2 enabled. It belongs in the C8 cost model once FTMO is chosen; [[GAP-P12D-46]] owns cost-model changes.
      - The report's draft rulebook entries for FTMO and E8.
      - Its draft emails to five firms (the owner sends them).
      - Its 16 proposed ledger items.
    - It used 21 of its 45 WebSearch calls.
  - **ECONOMIST** (2026-09-24): archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md. It was interrupted by the session limit and resumed.
    - **The paid-minority playbook, graded:**
      - (a) small, fixed risk tied to the distance to the floor;
      - (b) slow trading: payout rates fall from 34.8% to 3.9% going from 1 to 20 trades a day (Hall, arXiv 2609.14859, cited by the agent and not checked by the lead);
      - (a) the trader's own algorithm, never a commercial EA;
      - (b) withdraw every eligible profit;
      - (b) incubate before paying.
    - **Base rates:** Topstep's own 2025 disclosure (a) says 33% of funded traders were paid and 0.71% moved to live capital.
    - **Verified by the lead and filed:**
      - [[GAP-P12D-61]]: realised risk is 0.04%/day. Critical.
      - [[GAP-P12D-62]]: zero edge is +EV on prop accounts, so §14 cannot tell skill from luck. This agrees with the ARCHITECT's Monte Carlo.
    - **Corroborated rather than re-filed:**
      - [[GAP-P12D-54]]: the ftmo basis.
      - [[GAP-P12D-60]]: FundedNext's EAs come "with add-ons"; its Stellar 2-Step lists no consistency rule; its daily limit includes unrealised P&L; The5ers' daily limit uses the higher of midnight balance or equity.
      - [[GAP-P12D-59]]: a daily-limit guard is needed in each firm's own reference and timezone.
    - **Its numbers:**
      - EV per attempt at Sharpe 0.3–0.7 is small but positive: +$57 to +$292 at FundedNext $6K; +$193 to +$591 at FTMO $10k (closed form, before fat-tail and survival corrections).
      - Scale is the lever: fees fall from 1.0% of balance at $6K to 0.55% at $100K.
    - **Its judgement on LuxAlgo `prop-firm-sim`:** MIT-licensed TypeScript with no costs and affiliate-sourced rules. Use it as a cross-check only.
    - It used 21 of its 40 WebSearch calls.
  - **BUILDER** (2026-09-24): branch `worktree-agent-a128ab904780ce593` (8 commits on top of `7695ed0`; worktree under `.claude/worktrees/`), report `BUILDER_REPORT_2026-09-24.md` at the worktree root. It was interrupted by the session limit and resumed. All of it is **BUILT — PENDING AUDIT, NOT MERGED**:
    - the oracle positive control, as `falsify_engine`'s first stage ([[GAP-P12D-37]]);
    - [[GAP-P12D-38]] REFUTED, with the empty-population NaN fix; that also exposed [[GAP-P12D-63]];
    - the TSMOM attribution verdict ([[GAP-P12D-49]] note). Its per-trade bucketing is BLOCKED on memory;
    - the §5.6 plateau law ([[GAP-P12D-34]]); its reading of "dies" needs owner ratification;
    - logging of every QIEA evaluation ([[GAP-P12D-33]]).

    Its own count: 828 passed, 6 skipped. It reports 12 falsification mutants, all dead. One commit message is wrong (904b409 says 7 plateau tests; there are 5).

    **The lead reviewed** the diff (18 files, no config, guardrail, spec or ledger file touched) and the three seed/fold-index test changes, which are legitimate. The lead re-ran the full suite on the branch independently: **828 passed, 6 skipped** (275 s), which confirms the builder's count. **The merge needs:** the dual audit (A3), the owner's ratification of the plateau reading, and the owner's go.
  - **VALIDATOR** (2026-09-24): archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md. It was interrupted by the session limit and resumed. Everything is synthetic, and it used 5 of its 25 WebSearch calls.
    - **The calibrated gate options** are recorded under [[GAP-P12D-33]]. It recommends option C plus D.
    - **Filed by the lead:**
      - [[GAP-P12D-64]]: uncounted revisions are the false-positive channel;
      - [[GAP-P12D-65]]: leakage passes every statistical gate. The lead reproduced this with an independent seed;
      - [[GAP-P12D-66]]: the LLM-contamination rule. The lead verified the Gençay source at arXiv;
      - [[GAP-P12D-67]]: the 2-year train window discards edge.
    - **Notes added to existing entries:** the plateau law is a filter, not evidence ([[GAP-P12D-34]]); the prop-gate design and the power of the §14 Sharpe row ([[GAP-P12D-62]]).
- **TRIAGE COMPLETE (2026-09-24).** The lead verified every binding claim from the five reports (script, quote or code read) and filed each as its own entry: [[GAP-P12D-53]] to [[GAP-P12D-67]], plus notes on [[GAP-P12D-33]], -34, -37, -38, -43, -46 and -49. The design proposals that are not defects of existing code are collected, with their sources, in [[GAP-P12D-68]]. The owner's decisions are listed in TODO.md's START HERE block.
  - **Still owned here:** archiving the pinned brief, and the dual audit plus merge of the BUILDER branch (tracked under [[GAP-P12D-37]]).
  - **Web budget used across the pass:** lead ~22, SCOUT 21, ECONOMIST 21, ARCHITECT 27, VALIDATOR 5, about 96 of ~200.
- Justification: open until all five reports are in and every finding is triaged (A6). A finder's report is evidence, never an instruction (A9), and any recommendation that touches the spec needs owner ratification.
- Linked: [[GAP-P12D-32]], [[GAP-P12D-49]], [[GAP-P12D-33]], [[GAP-P12D-37]], [[GAP-P12D-38]], [[GAP-P12D-34]], [[GAP-0075]], [[GAP-P12D-43]], [[GAP-P12D-44]]

## GAP-P12D-50: the AWS second copy of the tick set was lost in the KYC hold — RESTORED from AWS's snapshot and sha256-verified 2026-09-29, but on a free-plan account that expires
- Severity: critical · Likelihood: high
- Status: mitigated (2026-09-29 — restored and verified file-for-file, see the 2026-09-29 finding below; the gone-copy state was verified 2026-09-23 by direct API inventory; account 565257597310, IAM user `acis-data`)
- Area: the phase-12 data layer's redundancy (master §13 provenance), OOS_VALIDATION.md, `data/dukascopy`
- Description: the AWS account was placed on hold 2026-09-15 for KYC verification and its resources were terminated before it was reinstated, exactly as the hold notice warned ("any resources currently running on your account are subject to termination and might not be recoverable"). Measured inventory after reinstatement, with permission errors surfaced rather than swallowed:
  - **EC2 instances: 0** across all 17 standard regions (`describe_instances` succeeds and returns empty — this is a real zero, not a denied call)
  - **EBS volumes: 0**, **snapshots: 0**, **Elastic/public IPv4: 0** — so the "kept disk" that held the second copy no longer exists
  - **S3: one bucket** `acis-transfer-565257597310`, **3 objects, 11.79 MB total**: `code/acis-72ac110.bundle` (943 KB git bundle), `server/manifest.jsonl` (10.85 MB — the download provenance record), `server/COMPLETE` (45 B). No tick data.
  - **RDS: NOT VERIFIABLE** — `describe_db_instances` is `AccessDenied` for this scoped IAM user, in every region. An RDS MySQL `db.t4g.micro` may still exist and still bill. Only the root user / console can confirm or delete it.
  The laptop copy is intact and complete: **12 GB, exactly 35,008 `.bi5` files**, all 8 instruments plus EUR_GBP, `COMPLETE` marker present (verified 2026-09-18). So nothing is lost — but the sha256-proven redundancy that master §13 leaned on is gone, and the archive that took days to download now has a single point of failure on one consumer laptop.
- Justification (2026-09-23, superseded by the 2026-09-29 one below): open. It does not block any current work (every labelling and ladder run since has read the laptop copy), but it converts a recorded two-copy guarantee in the read path into a false claim, and the read path has been corrected accordingly. A replacement second copy is an owner spending decision (S3 Glacier Deep Archive for ~12 GB is cents per month; an external disk is a one-off), so it is not taken unilaterally.
- Proof: `server/manifest.jsonl` in the bucket is the surviving provenance record of the original download and should NOT be deleted in any cost cleanup; the laptop-side count is reproducible with `find data/dukascopy -name "*.bi5" | wc -l` (35,008).
- Residual (2026-09-23, superseded by the 2026-09-29 one below): this entry owned (a) the owner's choice of a replacement second copy, and (b) correcting every read-path claim that asserts two copies.
- **Finding 2026-09-25 — the second copy may SURVIVE, in a snapshot.** A read-only inventory found `snap-0b6cc0700013b7ab1` in **eu-west-1**:
  - 60 GB, of volume `vol-01679d26401152fd4`, taken 2026-09-21 16:53 UTC;
  - described as "AWS EBS triggered volume snapshot" (AWS took it itself during the account hold);
  - standard tier, unencrypted, completed.

  It is very likely the data server's kept disk, which held the sha256-proven tick set. The 2026-09-24 inventory reported 0 snapshots and missed it.
  - **DO NOT DELETE IT.**
  - Its cost is at most ~$3 a month in the standard tier; the archive tier is about 75% less, with a 90-day minimum.
  - **To verify** (owner decision; a small cost): create a volume from it in eu-west-1, attach it to a temporary instance, and check the files against `server/manifest.jsonl` in the S3 bucket.
- **Confirmed 2026-09-25 from AWS's own emails** (the owner's Gmail, read at the owner's request):
  - **The timeline:** the account was placed on HOLD on 09-15, suspended on 09-16, **CLOSED on 09-21 05:29 UTC** ("AWS Account Closure Confirmation"), and reinstated on 09-23 ("removed the temporary hold").
  - **The 09-23 email says:** "we may have removed your resources … your EBS volumes may have been snapshot". So `snap-0b6cc0700013b7ab1` (09-21 16:53) is AWS's protective snapshot of the data server's volume. The second copy is very likely recoverable: restore the snapshot to a volume (AWS's restore guide; the owner decides).
  - **Never delete that snapshot.** A generic "delete orphaned snapshots" audit would destroy it.
- **Finding 2026-09-29 — RESTORED and VERIFIED** (the owner's go: "proceed … use those 2 cloud servers"):
  - **The restore.** `run-instances` c7i-flex.large `i-08cd48694bea9e3db` (Name `acis-data-restore`, Project=acis), with a gp3 volume from `snap-0b6cc0700013b7ab1` at `/dev/sdf`: `vol-0736f7bce03f2d489`, Name `acis-ticks-restored`, **DeleteOnTermination=false**. The stock bootstrap `deploy/aws/acis-data-server-userdata.sh` found the `acisdata` XFS label and mounted it at `/data` without formatting: 60 G, 12 G used, all nine instrument folders plus `COMPLETE`.
  - **The check.** Every record of the LAPTOP manifest (uploaded as `s3://acis-transfer-565257597310/laptop/manifest-2026-09-29.jsonl`) was re-hashed on the server. **35,008 of 35,008 match on size and sha256; 0 missing, 0 mismatched, 0 extra `.bi5` on disk; 2,792,567,873 ticks; 226 s** (the snapshot hydrating on first read). The result is `s3://acis-transfer-565257597310/restore/verify-2026-09-29.json`.
  - **The state left.** The instance is STOPPED; the volume stays attached as the AWS data server's disk (~$5/month of gp3 from the credits). The snapshot is kept too. The laptop is copy 1, this volume copy 2, the snapshot copy 3.
  - **What is still NOT durable.** The account is on AWS's **Free plan**. It closes when the plan ends (**2027-03-11**, from `freetier:GetAccountPlanState`) or when the credits run out ($197.97 on 2026-09-25), and AWS deletes the content 90 days after closure unless the owner upgrades to the Paid plan (the remaining credits carry over). The 2026-09-15 hold already showed what a lapse does.
- Justification: mitigated — two cloud copies exist again and one is proven identical to the laptop, but both live on a free-plan account with a fixed end date, so the single-point-of-failure risk is deferred, not removed.
- Residual: GAP-P12D-50 — this entry still owns (a) the owner's choice of a DURABLE copy before 2027-03-11 (upgrade AWS to the Paid plan, S3 Glacier Deep Archive at cents a month, or an external disk), and (b) correcting any read-path claim about the number of copies.
- Linked: [[GAP-P12D-14]], [[GAP-P12D-12]], [[GAP-0001]], [[GAP-P12D-76]], tests/backtest/OOS_VALIDATION.md

## GAP-P12D-51: the development laptop's clock is ~16 minutes slow and the Windows Time service is not running
- Severity: medium · Likelihood: high
- Status: open (measured 2026-09-23: AWS's own STS `Date` header read 19:48:52Z while the laptop read 19:33:03Z — a +949 s offset; `w32tm /query /status` reports "the service has not been started", and `Start-Service w32time` fails without elevation)
- Area: the host environment of every run — `core/data/jsonl_logging.py` timestamps, run-id generation in `scripts/*.py`, and any future paper/live session
- Description: the laptop that runs the engine is a quarter of an hour behind real time, with no time service to correct it. Consequences, in order of severity:
  1. **AWS API calls could not be signed at all** until a signing-time offset was applied — SigV4 rejects a signature outside a 15-minute window, and 949 s is just outside it. This is how the skew was discovered.
  2. **Every wall-clock timestamp this project has written is ~16 minutes early**, including JSONL event logs and the `%Y%m%dT%H%M%SZ` run-ids (e.g. the cost-stress run directory `20260917T083216Z`). Replay RESULTS are unaffected — the backtest takes its time base from tick and bar timestamps in the data, never from the wall clock — so no graded number is in question. What is affected is the ability to correlate a log line with an external event, which is exactly what the operational-referent audit will need from the first live fill.
  3. A 16-minute-wrong clock in live trading would misalign session boundaries, the 17:00-New-York rollover and any venue reconciliation. The §13 clock-skew glitch class is tested in code; this is the same defect in the host.
- Justification: open and NOT fixable by this agent — starting `w32time` needs administrator rights. The AWS work was unblocked by reading AWS's own clock and patching the signing timestamp only (a scratchpad helper; it changes no system setting and no AWS resource), which is a workaround for one tool, not a fix.
- Residual: GAP-P12D-51 — this entry owns the host fix (an elevated `net start w32time` plus `w32tm /resync`, and setting the service to Automatic so it does not recur) and a pre-live check that the engine refuses to start, or at least logs loudly, when host time is more than a few seconds off a reference.
- **Progress 2026-09-25:** the clock now reads **+2 s** against AWS's STS `Date` header (it was +949 s), so SigV4 signs without the workaround. But `w32time` is still **Stopped / Manual**, so the correction is not durable and drift will recur. The elevated fix is still owed: set Automatic, start, `w32tm /resync`.
- Linked: [[GAP-P12D-10]], [[GAP-P12D-07]], [[GAP-0001]]

## GAP-P12D-49: the cost question is SETTLED and it was never the problem — on the planted market the engine loses 89% of its money on DIRECTION, and TSMOM is the sink
- Severity: critical · Likelihood: high
- Status: open (2026-09-17/18 — the cost-stress ladder's first full run, `data/validation/cost_stress/20260917T083216Z`: planted market, 25 folds, 985 days, 2.05 graded years, 4 rungs, ~10.5 h. The FIRST engine-level grade on the harness fixed by [[GAP-P12D-35]]/[[GAP-P12D-36]])
- Area: core/signals/agon.py `_tsmom` (and its §14 duration carve-out), core/optimizer selection, specs/ACIS-04 module set; supersedes the module ranking in [[GAP-P12D-40]]
- Description: the ladder graded ONE market four times, changing nothing but the C8 cost map.
  | rung | trades | net PnL | Sharpe | PF | win rate | avg dur |
  |---|---|---|---|---|---|---|
  | 1x | 2,141 | **−147.84** | −1.12 | 0.787 | 0.392 | 771 s |
  | 2x | 1,880 | −170.62 | −1.29 | 0.755 | 0.429 | 738 s |
  | 3x | 1,973 | −183.77 | −1.39 | 0.743 | 0.389 | 826 s |
  | 5x | 1,784 | −214.25 | −1.61 | 0.707 | 0.369 | 693 s |
  Every §14 metric fails at every rung. Three findings, in order of consequence:
  **(1) The venue question is moot, and for a stronger reason than "the edge is fragile".** Net PnL is linear in the multiplier for a fixed trade set, so the least-squares slope over the rungs estimates the friction charged at 1x: **$16.15 per 1x, implying GROSS (pre-friction) PnL of −$131.69 at 1x**. Friction is ~11% of the loss; ~89% is direction. **At zero cost this still loses.** No cost calibration ([[GAP-P12D-41]]/[[GAP-P12D-46]]), no venue choice ([[GAP-P12D-43]]/[[GAP-P12D-45]]) and no spread overlay can rescue it. The 1.072-vs-1.5578 pip reconciliation is no longer on the critical path.
  **(2) This is the PLANTED market** — the positive control, whose only edge is 1–4 h trending episodes the fitness harness finds easily. The engine loses on it over two graded years. [[GAP-P12D-31]]'s failure therefore REPRODUCES on the fixed harness; it was not an artifact of the fold rewind or the uncharged spread.
  **(3) The module ranking of [[GAP-P12D-40]] is SUPERSEDED.** Per-strategy at 1x: **TSMOM −152.49** on 455 trades — the entire loss, since everything else nets +4.65 — then MEAN_REVERSION −10.05 (win rate 0.088), PAIR_DIVERGENCE −0.09, **BREAKOUT +1.66 (PF 1.855)**, **TREND +13.14 (PF 2.037)**. TREND and BREAKOUT do capture the planted edge. MEAN_REVERSION is still broken but is 15x smaller than TSMOM, so the owner's pending decision 3, framed around MEAN_REVERSION, is aimed at the wrong module.
  The genuine edges are thin: at 5x TREND flips to −15.19 and BREAKOUT to −1.11, while TSMOM barely moves (−152.49 → −175.41 for 4x more friction on 455 trades). TSMOM loses on direction, not cost — consistent with the owner's own earlier external review finding an unfaithful TSMOM.
  Duration ~771 s (12.8 min) at every rung, still under the §14 30-minute floor ([[GAP-P12D-38]] churn). Deflated Sharpe 0.00 over ~106 trials at every rung, uninformative while the Sharpe is negative ([[GAP-P12D-33]]).
- Caveats, stated so this is not over-read: it is ONE synthetic market (planted), two instruments, `financing=None`, and no event calendar — it is a statement about the engine's behaviour on a market with a known answer, NOT a §14 result on real data. The decomposition's linearity assumes a fixed trade set, and selection moves with cost (trade counts vary 1,784–2,141), so the 11% is an estimate, not an identity.
- Justification: open. It reframes the phase-12 critical path: the binding defect is the engine's directional behaviour (TSMOM first, then the regime gate that feeds MEAN_REVERSION), not the cost model, not the data source, and not the venue. Disabling or re-gating a module is a spec-level change to ACIS-04 and needs owner ratification — do not take it on one synthetic run.
- Proof: `data/validation/cost_stress/20260917T083216Z/ladder.json` (verdict + `cost_decomposition` + per-rung `per_strategy`); mechanism tests `test_the_decomposition_separates_friction_from_direction`, `test_a_ratio_of_two_losses_is_never_reported_as_a_fraction_kept`
- **TSMOM attribution, 2026-09-24** (BUILDER agent in [[GAP-P12D-52]]; the lead has NOT re-measured it; details in the branch's BUILDER_REPORT_2026-09-24.md):
  - **It holds straight through the edge.** The average hold is 53.4 h against 1–4 h planted episodes, so a 48 h trade crosses at least 11 episode boundaries, and ~96% of its loss is direction.
  - **Its vote has no edge at its own horizon.** On 16 synthetic paths its 63/126/252-day vote showed none on any market kind.
  - **It is NOT faithful to Moskowitz–Ooi–Pedersen:**
    - the backtest book caps every position at 48 h, so the "2.3-day hold" is that cap, not the paper's monthly hold;
    - spot rather than excess returns may be an undeclared deviation.
  - **It blocks other modules.** Because TSMOM emits on every tradeable tick, it vetoes every opposite-direction signal on its instrument (the §2 opposite-discard rule). All 360 promotion stalls begin on 2015-02-03, when TSMOM went live. So its damage exceeds its own P&L.
  - **The per-trade bucketing is BLOCKED:** memory was under 2 GB, and no per-trade records are on disk. The run spec is in the report.
  - **This moves the owner's module decision:** retire TSMOM from the 1-minute event loop, or rebuild it as a faithful slow sleeve ([[GAP-P12D-53]]: its evidence base is portfolio breadth).
- **RE-STATED 2026-09-29 on the C-BT-12 market** ([[GAP-P12D-124]]; nothing demeaned, compounded prices, planted oracle Sharpe 10 variance-matched at one weekday). The run: the Google compute server, code `daf7bd2`, 25 folds, 985 days, 4 rungs, 1 h 20 min. Results: `data/validation/cost_stress/20260929T114406Z-gce/` and `data/validation/falsification/20260929T114406Z-gce/` (the JSON reports; the engine stores and both logs are in `gs://acis-compute-0929-data/runs/20260929/`).
  - **The verdict HOLDS.** The engine loses at every rung:
    - 1x net −70.84, Sharpe −1.92, PF 0.67, 1,690 trades;
    - 2x −76.48; 3x −21.18; 5x −82.95.
    - The harness's own split: friction is ~2% of the 1x→2x loss, and the rest is DIRECTION (it was ~89% on the old market).
  - **The attribution CHANGED.** At a realistic edge, NO module captures the planted trend:
    - TSMOM −57.44 (446 trades, PF 0.68, average hold **55 h** against 1–4 h episodes): 81% of the loss;
    - TREND −10.44 (PF 0.64); BREAKOUT −2.65 (PF 0.60); MEAN_REVERSION −0.31.
    - On the old oracle-157 market, TREND (+13.14, PF 2.04) and BREAKOUT (+1.66) "captured the edge". That was an artifact of an edge ~16× too strong: an oracle Sharpe of ~157 against 10.
    - TREND, BREAKOUT and MEAN_REVERSION hold ~12 minutes on average, below §14's 30-minute floor (`avg_duration` fails at every rung).
  - **What this changes.** Nothing in the reframing above, except that "TREND and BREAKOUT genuinely work" is WITHDRAWN. The engine as built has no module that captures a planted intraday trend of a realistic strength. The R-1 direction (fixed, pooled, economically motivated rules graded on the daily lab) is where that gets rebuilt.
- Linked: [[GAP-P12D-46]], [[GAP-P12D-41]], [[GAP-P12D-45]], [[GAP-P12D-43]], [[GAP-P12D-31]], [[GAP-P12D-40]], [[GAP-P12D-38]], [[GAP-P12D-33]], [[GAP-0035]], [[GAP-P12D-124]]

## GAP-P12D-48: the labelled-bar cache key does not cover the synthetic MarketSpec — two different price paths under one source name would share labels silently
- Severity: medium · Likelihood: medium
- Status: mitigated 2026-09-17 (found while building the cost-stress ladder; the hazard is structural, the mitigation is conventional)
- Area: tests/backtest/regime_labels.py `LabelSpec.for_config`, tests/backtest/synthetic_grade.py, scripts/falsify_engine.py, scripts/cost_stress_ladder.py
- Description: `LabelSpec.key()` hashes the config, the calendars, the bar/cycle geometry and the labeller version — everything that can change a label given a price path. It does NOT hash the price path. Every synthetic market reports the same source name per kind (`synthetic-planted`), while its prices depend on the whole `MarketSpec`, `days` included: `_returns` draws `weekdays × ticks_per_day` samples and demeans over all of them, so a 247-day planted market and a 985-day planted market are DIFFERENT series under one name. Point two such runs at one labels directory and `cache.has()` returns True for the wrong labels — the engine would then evolve on one market's regimes and be graded on another's, with no error and no flag. It has not happened: `falsify_engine` has always given each run its own output root. But the guard is a convention in two scripts, not a property of the cache.
- Justification: mitigated, not fixed. The shared path is now ONE function (`synthetic_grade.market_cache`), which takes the run's own root, and the module's invariant block states the rule in the place a newcomer reads before using it. A real fix puts the MarketSpec (or any source's content hash) into `LabelSpec.inputs`, which is a one-line change to `for_config` plus a cache rebuild — deferred because nothing currently shares a root, and the rebuild costs ~15 min per instrument-year.
- Proof: the convention is exercised by every falsification and ladder run (`tests/backtest/synthetic_grade.py` docstring invariant 1); there is no test yet that a mismatched MarketSpec is refused — that test arrives with the fix.
- Residual: GAP-P12D-48 — this entry owns the real fix (hash the source's content into the label key) and the test that a mismatched market is refused.
- Linked: [[GAP-P12D-28]], [[GAP-P12D-46]], tests/backtest/regime_labels.py

## GAP-P12D-46: the cost model, not the data, is what must change — and the number GAP-P12D-41 was built on is probably wrong by ~45%
- Severity: critical · Likelihood: high
- Status: open (2026-09-17 — data/venue-architecture research agent, from live API probing of OANDA's own spread endpoint; NOT re-verified by the author, who had no search budget). **The cheapest decisive test is now BUILT and RUNNING: `scripts/cost_stress_ladder.py`, commit 67330fb.**
- Area: tests/backtest/book.py + core/optimizer/costs.py (the cost model), master §13 (data provenance), [[GAP-P12D-41]], [[GAP-P12D-36]]
- Description: the agent's verdict on the data question is **keep Dukascopy as the price path and replace the cost model**: every 2012-2025 tick alternative is worse (HistData), effectively gone (TrueFX free tier now institutionally priced), the same archive repackaged (Tickstory), or institutional (dxFeed / LSEG / EBS). The defect was never the archive; it is that the archive's cost LEVEL was used as if it were the destination's.
  **The blocking discrepancy:** it measured OANDA's own unauthenticated spread endpoint (15-minute granularity, back to 2022-06-17, ~4.25 years) and got EUR/USD **avg-series mean 1.072 pips, median 0.960, p95 1.42**, while the **max**-series mean is **1.524**. [[GAP-P12D-41]]'s headline 1.5578 figure is almost exactly that max-series mean, so it is most likely a max-vs-average confusion or a different division — a ~45% error in the single input that entry exists to correct. **Reconcile before any calibration is ratified.**
  **Design, if a hybrid is used:** a per-instrument x per-session x per-state overlay, forward-sampled and floored — `s_dest = max(floor, base[session] + g(state), s_source)` — and **never a flat multiplier**, because a B-book markup is typically additive while an ECN blows out multiplicatively. The measured tail is the argument: median 0.96 against worst 15-minute buckets of 9.40, so any single number in the 0.96-1.42 range understates stress by 3-10x.
- **The hybrid's premise is an ASSUMPTION, not a finding.** The agent could not locate any published measurement of retail-market-maker or prop mid versus ECN mid at 1-minute granularity and doubts one exists; the literature compares wholesale venues only. Two primary sources cut against the assumption: FX Global Code Principle 17 permits price updates during the last-look window, so a last-look destination's REJECTED set is adverse-selected and a symmetric spread overlay structurally cannot represent it; and a JFM 2010 study warns specifically that mixing one venue's price series with another's quote mid manufactures spurious divergence. Treat the hybrid as a hypothesis with a named falsifier, not as settled.
- **Cheapest decisive test, to run FIRST (free, uses data already on disk): the cost-stress ladder.** Re-run the walk-forward at 1x, 2x, 3x and 5x the overlay, plus its p95 as a constant. **Pass = meets §14 out-of-sample at 2x.** A real edge over a 30 min-48 h hold should survive 2x comfortably. If the edge exists only at 1x, the entire venue question is moot and that is a larger finding than the data-source one — and it can be run before any account is opened.
- For the decided prop route: **multi-year destination spread history does not exist.** cTrader's Open API has the right schema (bid and ask tick series can be pulled separately, no documented range cap) but serves only that broker's own retained history, so a firm founded in 2023 has no 2012 quotes and its challenge feed may differ from its funded feed. DXtrade / Match-Trader / TradeLocker: no public historical market-data API found. IBKR: ruled out on primary docs (sub-30-second bars unavailable beyond six months). **So calibration must be forward-sampled, and the sampling window has to start the day an account is opened.**
- **Ladder built 2026-09-17** (does NOT close this entry — the calibration question and the 1.072-vs-1.5578 reconciliation both remain open):
  - `CostModel` carries `stress` (a multiplier on the WHOLE per-side cost) and `spread_floor` as RUN properties, never instrument properties. The type refuses `stress < 1.0`: a knob that could price the world cheaper than declared could flatter a run into a §14 pass, so the asymmetry is enforced in `__post_init__`, not in caller discipline.
  - `run_walk_forward` now builds ONE cost map and hands the SAME instances to selection (QIEA, via `evolve_fold`) and to the graded book. `evolve_fold` no longer derives its own from cfg. The [[GAP-P12D-36]] defect class — select cheap, grade expensive — is therefore structurally excluded, not merely fixed once.
  - A stressed run states so in its `fidelity_caveats`, so its §14 numbers can never be read as declared-cost ones, and the caveat says in words that a flat ladder is NOT the additive per-session overlay this entry describes as a calibration.
  - The p95-as-a-constant rung is implemented (`spread_floor`, applied as a floor so it can never charge less than the tape did) but is INERT on a synthetic market, whose spread is constant by construction. It is the rung that will matter on a real tape.
  - Shape run (32 days, 2 rungs): 21 trades and net +0.19 at 1x; 7 trades and net −0.10 at 3x. The mechanism works — stress changes selection as well as the charge.
- Justification: open. It supersedes the arithmetic in [[GAP-P12D-41]] without contradicting its direction — the harness still under-charges — and it makes the cheap test available before any venue is chosen or any money spent.
- Proof (the ladder mechanism only, not the calibration): `test_stress_multiplies_the_whole_per_side_cost`, `test_a_cheaper_than_declared_world_is_refused`, `test_the_spread_floor_only_ever_raises_the_spread`, `test_the_book_charges_exactly_the_stressed_friction`, `test_selection_and_grading_hold_the_same_stressed_cost_map`, `test_a_stressed_run_declares_itself_and_a_declared_run_stays_silent`, `test_the_ladder_verdict_separates_no_edge_from_fragile_from_survives`
- **2026-09-24, a cost term for FTMO** (SCOUT agent in [[GAP-P12D-52]], grade (a), FTMO T&C). FTMO applies a 0.7% adjustment to realised P&L on non-USD instruments, and it cuts both ways. It hits 4 of the 8 declared instruments and 1 of the 2 enabled (USD_JPY); the prior pass said 5, which was wrong. The share of expectancy it removes is 0.007·(PF+1)/(PF−1): 3.5% at PF 1.5, 7.7% at PF 1.2, 14.7% at PF 1.1. It belongs in the C8 model as a per-instrument, per-account term, not as a spread, once FTMO is the chosen account.
- Linked: [[GAP-P12D-41]], [[GAP-P12D-43]], [[GAP-P12D-45]], [[GAP-P12D-36]], [[GAP-P12D-48]], [[GAP-0001]]

## GAP-P12D-47: Dukascopy tick volume is SWFX volume only — two modules read it as if it were market volume
- Severity: medium · Likelihood: high
- Status: open (2026-09-17 — external-referent finding that fell out of the data/venue research; independent of the venue decision)
- Area: core/signals/agon.py `_breakout` (volume confirmation) and `_momentum_scalp` (tick-velocity surge), core/data/normaliser.py `volume` / `tick_velocity`, master §16 naming law
- Description: the `volume` on a Dukascopy tick is **that one venue's participation**, not the market's — FX has no consolidated tape. The Breakout module's volume confirmation and Momentum Scalp's tick-velocity surge therefore measure something other than what their names imply, and the measurement changes with Dukascopy's own market share over a 14-year window. Tick COUNT per interval is reported as a far more robust activity proxy. This is exactly the §16 naming-law class of defect the external-referent audit exists to find: a quantity wearing a name whose standard meaning it does not carry.
- Justification: open, and it must be declared or corrected before either module's signal is trusted in a graded run. Cheap to fix (switch to tick count, or declare the deviation in the module's `declared_deviations`); cheap to test (compare the two proxies on the archive already on disk).
- Linked: [[GAP-0035]], [[GAP-P12D-40]], [[GAP-SP12I-03]]

## GAP-P12D-43: the spec's primary execution adapter (OANDA v20) is not available to the owner's entity, and the MT5 fallback breaks the deployment gate
- Severity: critical · Likelihood: high
- Status: open (2026-09-17 — found by the venue-choice research agent from OANDA's own developer and BVI-division pages, read directly; NOT re-verified by the author, who had no search budget when it landed — verify before acting)
- Area: master §3 (OANDA as the execution feed), §7.5 adapter contract, specs/ACIS-06 §7.5, `Dockerfile` / `deploy/` (phase-12 deployment gate), future ACIS-13
- Description: OANDA's v20 REST/streaming API is documented as available to all divisions **except OANDA Global Markets Ltd (BVI)** — which is the division a Kenyan resident onboards to. If that holds, the execution adapter the spec names first cannot be built for this owner at all: his OANDA route is MT5, whose `MetaTrader5` PyPI package ships **Windows-only wheels** against our `python:3.11-slim` container, so it also breaks the phase-12 deployment gate's platform assumption. Two further regressions reported against the same division: the minimum ticket is **0.01 lots (1,000 units)**, not the 1-unit granularity the Governor's risk-based sizing assumes, and the terms state "all negative balances are payable" — i.e. **no negative-balance protection**, which contradicts the assumption behind the GAP-0108 CHF-gap work that losses stop at the equity floor. The agent also reports OGM's terms name "automated or mass data entry system" and "Scalping" as Events of Default actionable without notice — an `OPERATIONS_LEDGER.md` item before any first live fill.
- Consequence for [[GAP-P12D-41]]: its 1.5578 pip / 1.44 bps figure came from OANDA's **US** division series; the BVI division publishes 1.0 pip and its own spread endpoint returns HTTP 500, so no measured series exists for the division we would actually trade. The optimism ratio is reported as ~2.5x, not 3.9x. Do not calibrate to the earlier number.
- Justification: open, spec-level, and it lands AFTER the owner chose the prop-firm route (2026-09-17), so OANDA may be moot for execution anyway. It is filed because master §3 still names OANDA as the execution feed and §13 leans on it for cost calibration — whichever venue wins, the spec text must stop asserting an adapter the owner cannot use.
- **Re-verified 2026-09-24** (SCOUT agent, [[GAP-P12D-52]]; grade (a) quotes in archive/RESEARCH_PROP_VENUES_2026-09-24.md §4 and §7). v20 is "available to all divisions except OANDA Global Markets". A Kenyan visitor is routed to OANDA Global Markets, whose demo is an MT5 demo. The legacy v20 demo sign-up gate returned HTTP 523. So a NEW OANDA practice account with v20 access is very likely unobtainable for the owner. Two things stay open:
  - Whether an EXISTING legacy practice token still answers. That is TODO Track A step 1, one call, and only the owner can run it.
  - The SCOUT's recommended demo of record: the FTMO Free Trial on cTrader via the Open API. That is a SPEC §15 deviation, and the draft amendment text is in the report's §7.

  Side note, grade (a): FTMO has owned OANDA Global Corporation since 1 Dec 2025.
- Linked: [[GAP-P12D-41]], [[GAP-0108]], [[GAP-0001]], [[GAP-0109]]

## GAP-P12D-44: a prop account is a SIMULATED environment — guard 2 and the operational-referent audit lose their external referent there
- Severity: high · Likelihood: high
- Status: open (2026-09-17 — raised by the venue-choice research agent, quoting FTMO T&C 5.2 "No actual trading is taking place"; NOT re-verified by the author)
- Area: CLAUDE.md "Operational correctness — three independent guards", the standing operational-referent audit, `OPERATIONS_LEDGER.md`, [[GAP-0001]]
- Description: the shortlisted prop firms describe their accounts, in their own terms, as simulated environments with no real execution and no named liquidity provider. Our correctness model assumes that once real fills exist they can be compared against the modelled cost, carry, slippage and fill behaviour — that is guard 3's whole purpose and the standing operational-referent pass's only evidence base. **On a simulated prop account there are no real fills to compare against.** The firm's own simulated fills become the referent, which is a different and weaker claim: it tests conformance to the firm's simulator, not to a market.
- Justification: open and owner-owned. It does not argue against the prop route — prop is a way to trade size without capital, and the owner has decided it — but it means the three-guard model needs an explicit answer for the prop phase: either accept that guard 3 is deferred until real-money execution, or pair the prop account with a small live account elsewhere as the referent. That is a judgement about how much the family's audit doctrine is willing to soften, so it is raised, not decided.
- Linked: [[GAP-0001]], [[GAP-P12D-43]], [[GAP-P12D-41]]

## GAP-P12D-45: venue cost is noise at this size — turnover is the decision, and at the prototype's churn it is ~33% of NAV per year
- Severity: critical · Likelihood: high
- Status: open (2026-09-17 — venue-choice research agent's arithmetic; consistent with the independent cost-horizon finding in [[GAP-P12D-32]], which is why it is filed rather than parked)
- Area: the whole strategy design — holding horizon, trade frequency, [[GAP-P12D-30]], [[GAP-0075]], master §14
- Description: measured across the venues examined, the all-in cost difference between OANDA's BVI division and Dukascopy at a $10k account is about **0.04 bps per round trip** — roughly 0.14% of NAV per year even at the prototype's churn, i.e. it cannot decide anything. At ~1,800 round trips per year and modest leverage, modelled cost is about **33% of NAV per year at EVERY venue examined**. A prop account does not improve that; it adds a terminal 4—5% daily kill-switch on top, so the same turnover that merely bleeds a personal account can END a prop account.
- Justification: open. This says the venue debate, the OANDA-vs-Dukascopy question and even the GAP-P12D-41 calibration are second-order against the holding-horizon problem already identified independently. The engine's realised ~8-minute trades are the defect that matters; fixing the horizon changes the outcome by two orders of magnitude more than picking a broker. Sequence the work accordingly.
- Linked: [[GAP-P12D-32]], [[GAP-P12D-30]], [[GAP-P12D-40]], [[GAP-0075]], [[GAP-P12D-41]]

## GAP-P12D-41: the backtest is priced on a different firm's book — Dukascopy ECN spreads for a venue that quotes ~4x wider
- Severity: critical · Likelihood: high
- Status: open (2026-09-17 — measured by the execution-cost and fill-fidelity research agents from OANDA's live API and published terms; NOT independently re-measured by the author, so the ratio is the agents' figure)
- Area: tests/backtest/book.py (fills at the Dukascopy tick's own prices), config/instruments.yaml `costs:`, core/optimizer/costs.py, master §13 (data provenance) vs §3 (OANDA as the execution venue), specs/ACIS-09 C-BT-5
- Description: we backtest on Dukascopy SWFX, a real ECN, and intend to trade at OANDA, a principal market maker that sets its own prices. Measured OANDA time-weighted average spread on EUR/USD is **1.5578 pips business-hours = 1.44 bps round trip**, against the harness's **0.367 bps** even after the [[GAP-P12D-36]] fix — about **3.9x optimistic**, and up to ~3.4 bps on NZD/USD. OANDA's own terms state it "ESTABLISHES THE PRICES" and that they "MIGHT NOT BE THE BEST PRICES AVAILABLE". At 500 round trips per year that is roughly 4-11% of notional per year of cost the backtest never charges; at the ~900 trades/year this engine currently produces, more than its entire gross edge. The GAP-P12D-36 fix charges the SOURCE data's spread; the honest model charges the DESTINATION venue's spread around the source's mid.
- Justification: open and spec-level. Master §13 names Dukascopy as the tick source and §3 names OANDA as the execution feed; nothing binds the cost model to the venue actually being traded. Any §14 number produced before this is resolved overstates net performance by more than the margin most §14 targets are decided by, so it belongs on the pre-training list, not after it. It is NOT an instance of [[GAP-0001]]: that entry accepts an irreducible microstructure gap, and a systematically wrong spread level is not irreducible.
- Linked: [[GAP-P12D-36]], [[GAP-0001]], [[GAP-P12D-32]], [[GAP-P12D-03]], [[GAP-0004]]

## GAP-P12D-42: a `priceBound` on a protective stop is CANCELLED, not filled, when the market gaps through it
- Severity: high · Likelihood: medium
- Status: open (2026-09-17 — found by the fill-fidelity research agent in OANDA v20 API documentation; guardrail-adjacent, so raised and not acted on)
- Area: core/execution/venue.py `submit_order(stop_loss=)` and the server-side-stop conformance suite, master §279 (per-adapter server-side stops), specs/ACIS-06 §7.5, future ACIS-13
- Description: master §279 requires every protective stop to rest server-side at the venue, and the phase-12 gate verified that it does. The agent reports that on OANDA v20 a StopOrder carrying a `priceBound` is **cancelled rather than filled** if the market gaps through both the trigger and the bound — so in exactly the weekend-gap or news-gap scenario the stop exists for, the protection disappears instead of filling worse. Our adapters do not set `priceBound` today, so this is a trap to forbid rather than a live defect, but it is the kind of assumption that must be pinned by a conformance test before any real adapter ships.
- Justification: open. Guardrail-adjacent (it decides whether a guard holds under stress), so it is raised for the owner and for ACIS-13 rather than changed by an agent. The action is a conformance assertion — a stop-bearing order must never carry a bound that can void it — plus a §13 glitch-class test for gap-through fills, which the harness cannot express today because it books stops AT the stop price.
- Linked: [[GAP-P12D-41]], [[GAP-0001]], [[GAP-0109]], [[GAP-P11I-02]]

## GAP-P12D-40: MEAN_REVERSION cancels the edge TREND and BREAKOUT capture - the attribution run names the mechanism
- Severity: critical - Likelihood: high
- Status: open (2026-09-17 - measured by the attribution diagnostic `data/validation/falsification/20260916T185248Z`, the run built for exactly this question after GAP-P12D-31 could not say which module lost the money; independently predicted in advance by BOTH the code-grounded and the blind research agents, which is the strongest corroboration available)
- Area: core/signals/agon.py `_mean_reversion` and `_module_gate`, core/regime/nvma.py (the RANGING_TIGHT classification that routes to it), specs/ACIS-04
- Description: per-strategy attribution on the planted market (a market whose only edge is 1-4 h trending episodes) versus the null market:
  - **TREND** 268 trades, net **+6.64**, win 54.1%, PF **2.21** (null: 520 trades, -3.07, PF 0.81)
  - **BREAKOUT** 244 trades, net **+1.72**, win 64.3%, PF **2.48** (null: 74 trades, -0.36, PF 0.57)
  - **MEAN_REVERSION** 430 trades, net **-6.63**, win **6.3%**, PF **0.15** (null: 307 trades, -0.23, PF 0.97)
  The engine is NOT edge-blind: its two directional modules capture the planted edge cleanly and lose on noise, which is correct behaviour in both directions. MEAN_REVERSION then gives back almost exactly what TREND earns (-6.63 against +6.64), fires the most often of any module, and does so with a 6.3% win rate - four to eight times worse on the market that HAS an edge than on the one that does not, because a mean-reversion entry in a trend is a bet against the drift. By regime the damage is concentrated in RANGING_TIGHT (292 trades, -5.54, win 6.8%) and RANGING_WIDE (140 trades, -1.05, win 6.4%): the classifier labels a wall-to-wall trending market as ranging often enough to feed 432 losing trades to the one module guaranteed to lose there.
  Whole-run effect: planted annual Sharpe **+1.11** against null **-2.77** - a 3.9-Sharpe separation. The earlier contaminated full run put all three markets inside a 0.4-Sharpe band ([[GAP-P12D-31]], verdict already withdrawn under [[GAP-P12D-37]]); that band was an artifact, and this run supersedes it as the engine's measured behaviour.
- Caveats on this run, stated so it is not over-read: it still carries the [[GAP-P12D-35]] fold-plan rewind and the [[GAP-P12D-36]] uncharged spread, so the magnitudes are optimistic and the fold boundaries are unsound; it grades 180 days over 6 folds, which is below any §14 claim; and `passed=False` remains uninformative while [[GAP-P12D-37]]'s gate is unsatisfiable. What it establishes is the RANKING and the SIGN of each module's contribution, which no previous run could say at all. Note also that the zero-duration artifact population of [[GAP-P12D-38]] does NOT appear here (944 trades = 244+430+2+268, durations 333-2790 s), so that defect is specific to conditions this run did not reproduce.
- Justification: open. The obvious remedy - disable or re-gate MEAN_REVERSION - is a spec-level change to ACIS-04's module set and needs owner ratification, and it should not be taken on one synthetic run: the honest sequence is (1) fix the harness defects, (2) re-run with attribution, (3) confirm the ranking holds, (4) then propose the change with the evidence. The deeper question is not the module but the gate that feeds it: a classifier that calls a trending market "ranging" for 432 trades is the root cause, which is what [[GAP-P12D-39]] and the research agents' regime findings are about.
- **SUPERSEDED 2026-09-18 by [[GAP-P12D-49]] on the point of module ranking.** The full-scale run on the FIXED harness (25 folds, 2.05 graded years, spread charged, fold plan sound) puts TSMOM at −152.49 and MEAN_REVERSION at −10.05 — MEAN_REVERSION is still broken (win rate 0.088) but is 15x smaller than the real sink. This entry's other claims stand and are strengthened: TREND (+13.14, PF 2.04) and BREAKOUT (+1.66, PF 1.86) DO capture the planted edge. What changes is the remedy: re-gating MEAN_REVERSION alone would not have moved the result.
- Linked: [[GAP-P12D-31]], [[GAP-P12D-37]], [[GAP-P12D-39]], [[GAP-P12D-49]], [[GAP-0035]], [[GAP-P12D-35]], [[GAP-P12D-36]]

## GAP-P12D-37: the falsification VERDICT IS VOID - the pass gate was unsatisfiable before the first tick, and the suite has no positive control
- Severity: critical - Likelihood: high
- Status: fixed (2026-09-25 — the oracle positive control is MERGED to main from the BUILDER branch, after the constitution's two audits (GAP-P12D-72) with every finding fixed. It is the first stage of `scripts/falsify_engine.py`: the engine verdict is VOID (exit 4) unless the harness recognises planted on every non-DSR clause and refuses every control by a §14 row. Near-fail rungs prove the grader separates just-above from just-below; there is NO VERDICT (exit 5) without planted, and GATE-LIMITED (exit 6) when only the DSR or trial-count gate fails. Originally found 2026-09-16 by the BLIND agent)
- Area: scripts/falsify_engine.py `EXPECT_PASS`, tests/backtest/report.py `passed` (the DSR gate), tests/backtest/deflated_sharpe.py `sharpe_threshold`, the whole GAP-P12D-28 falsification design
- Description: `falsify_engine` asserts planted must PASS, where "pass" is the full 14 gate including `deflated_sharpe >= 0.95`. Feeding the run's OWN recorded trial Sharpe ratios back through the repo's own `sharpe_threshold` gives SR0 (per trade) of **2.430 planted / 0.617 null / 0.649 permuted**, which at each market's own trade count over the graded span demands an **annualised Sharpe above 76.2 / 18.6 / 20.8**. The section-14 target is 1.5. **Planted could not have passed under any engine behaviour whatsoever**, so "planted FAILED" carries no information about the engine. Worse, the hurdle is HIGHEST where the edge is real: the planted trial Sharpes have sd 0.936 against 0.248 on null, because genuine signal widens the dispersion the DSR deflates by - the gate tightens exactly when the strategy works. This is the sharper form of [[GAP-P12D-33]]: that entry documents the inversion with respect to trial COUNT; this one is with respect to trial DISPERSION, and it is why the falsification returned no usable answer.
- Also: the suite has **no positive control**. An oracle strategy replayed through the same harness (a rule with perfect knowledge of the planted drift sign) would have exposed both this and the 30-minute duration floor in minutes, before any 6-hour run. Nothing in the suite asserts that the harness can recognise a strategy known to be good.
- Consequence: [[GAP-P12D-31]]'s verdict is WITHDRAWN as a verdict. The engine may still be badly broken - independent evidence in [[GAP-P12D-39]] says it is - but this run did not establish it, and no further conclusion may be drawn from it.
- Justification: open and blocking. Build the positive control FIRST and make it the suite's first gate; fix or suspend the DSR gate for falsification purposes ([[GAP-P12D-33]] owns the gate itself, owner-ratified); then re-run. No paid compute until an oracle can pass this harness.
- **BUILT on a branch, 2026-09-24 — BUILT, PENDING AUDIT, NOT MERGED** (BUILDER agent in [[GAP-P12D-52]]; branch `worktree-agent-a128ab904780ce593`).
  - **What was built.** An oracle positive control that knows the planted drift sign perfectly, graded through the same harness, book, costs and metrics as the engine.
  - **Wiring.** It is now the first stage of `falsify_engine`: the engine verdict is VOID (exit 4) unless planted clears every non-DSR clause of `passed` while null and permuted clear none.
  - **Its grade on planted** (EUR_USD, the ladder's 25-fold plan, 2.53 graded years):
    - all seven §14 rows pass: Sharpe 10.2, drawdown 0.94%, PF 555, 100% positive months, average hold 7.1 h;
    - on null the same logic fails five rows.
  - ~~The ratified DSR gate refuses even perfect knowledge (oracle DSR 0.000)~~ **CORRECTED 2026-09-25 (AUDIT-EXTERNAL E4, [[GAP-P12D-72]]).** That was not a faithful Deflated Sharpe: the oracle is not in the trial set, and the trial Sharpes come from roughly 5-trade holdouts (sd 2.216, max 19.4). Against a like-for-like hurdle the oracle's DSR is 1.0. The valid facts are these:
    - the gate as fed demands a per-trade SR0 of 5.654 or 2.430, a hurdle no real record meets, because it mixes sample lengths ([[GAP-P12D-33]]);
    - the VALIDATOR's calibration shows it passes 0 of 1,200 planted edges.
    The gate itself was not touched.
  - **Lead review:** diff read; the lead re-ran the full suite on the branch (828 passed, 6 skipped). Close this entry when the branch merges, after audit and the owner's go.
- Proof: `test_a_failed_oracle_voids_the_verdict_before_any_engine_compute`, `test_a_near_fail_rung_the_harness_passes_voids_the_verdict`, `test_the_planted_oracle_clears_every_non_dsr_clause_at_full_fold_scale`, `test_the_harness_passes_a_rung_just_above_the_cut_offs_and_refuses_one_just_below`, `test_non_dsr_failures_is_every_clause_of_passed_but_the_trials`.
- Residual: GAP-P12D-33 — the ratified DSR gate itself (it mixes sample lengths and passes 0 of 1,200 planted edges); the owner's option C+D decision is pending.
- Linked: [[GAP-P12D-33]], [[GAP-P12D-31]], [[GAP-P12D-35]], [[GAP-P12D-36]], [[GAP-P12D-28]], [[GAP-P12D-16]]

## GAP-P12D-38: 79% of the graded "trades" are zero-duration artifacts, and they sit inside the section-14 ratios
- **REFUTED 2026-09-24.** The BUILDER agent found it in [[GAP-P12D-52]], and the lead VERIFIED it independently: THERE ARE NO ZERO-DURATION TRADES.
  - **The evidence.** In all four ladder rungs (data/validation/cost_stress/20260917T083216Z) the per-strategy attribution lists BREAKOUT, MEAN_REVERSION, PAIR_DIVERGENCE, TREND and TSMOM, with ZERO MOMENTUM_SCALP trades. Yet every report prints `scalp_avg_duration_s = 0.0`.
  - **What the 0.0 was.** An empty population's mean, not trades lasting zero seconds.
  - **Where the arithmetic went wrong.** The blind agent's reading was a reduced-fraction artifact: 477.5061425061425 = 194345/407 = 777380/1628. The planted run's band holds 1,628 trades: 2,018 total minus TSMOM's 390, since TSMOM's average has denominator 13.
  - **Why the scalp never fired.** On the uniform 20-second synthetic tape, tick velocity always equals its session median, and at ratio 1.0 the scalp's conviction (0.333) sits under the 0.45 discard floor. The module can never fire on a synthetic market: [[GAP-P12D-63]].
  - **The fix.** An empty population now reports NaN, not 0.0. It is BUILT, PENDING AUDIT, on branch `worktree-agent-a128ab904780ce593`, with a falsified regression test, and is not yet merged.
  - **When this closes.** Close it on merge, with a Residual pointing at [[GAP-P12D-63]]. The §14 win-rate and PF quotes that this entry barred are no longer barred for this reason; the other reasons still hold, notably [[GAP-P12D-37]] and [[GAP-P12D-33]].
- Severity: high - Likelihood: high
- Status: closed (2026-09-25 — REFUTED and MERGED. There were never any zero-duration trades: the "0.0" was an EMPTY population's mean, since MOMENTUM_SCALP never fires on the synthetic tape. An empty population now reports NaN, written as null in JSON, per GAP-P12D-72 F6/E7. Lead-verified against the ladder's per-strategy attribution)
- Area: tests/backtest/metrics.py (`win_rate`, `profit_factor`, `n_trades` include every closed trade), core/signals/agon.py `_momentum_scalp`, tests/backtest/book.py open/close on the same tick
- Description: planted reports `n_trades = 2018` and `avg_trade_duration_s = 477.5061425061425`, which is exactly 194345/407 - so only **407** trades are in the section-14 duration band. TSMOM contributes about 13. The remaining **~1,598 are MOMENTUM_SCALP trades whose durations sum to exactly zero** (`scalp_avg_duration_s = 0.0` with a non-zero scalp population). Same shape on null (733 of 1,864 in band) and permuted (1,717 of 2,111). These zero-duration trades carry non-zero PnL and are counted in `n_trades`, `win_rate` and `profit_factor` - the two section-14 ratios previously quoted as evidence describe a majority-artifact population. The mechanism (open and close on the same tick) is not yet established and is the first thing to reproduce.
- Justification: open. Until this is explained, no section-14 ratio from any run may be quoted, and the 30-trade floor ([[GAP-P11I-07]]) is not measuring what it was built to measure.
- Proof: `test_an_empty_carve_out_has_no_mean_duration_never_zero`, `test_momentum_scalp_can_never_fire_on_a_uniform_synthetic_tape`, `test_the_ladder_document_is_strict_json_even_when_the_duration_band_is_empty`.
- Residual: GAP-P12D-63 — MOMENTUM_SCALP is untested by every synthetic falsification run.
- Linked: [[GAP-P12D-37]], [[GAP-P12D-31]], [[GAP-SP12I-03]], [[GAP-0075]]

## GAP-P12D-39: `RegimeContext.trend_direction` is computed every cycle and read by nothing
- Severity: high - Likelihood: high
- Status: open (2026-09-16 - found by the blind adversarial agent; VERIFIED by the author: set at core/regime/nvma.py:236, validated in regime_types.py, referenced only in tests)
- Area: core/regime/nvma.py:236, core/regime/regime_types.py:52, every consumer of `RegimeContext` (core/signals/agon.py, core/governor/capital_governor.py)
- Description: the regime engine computes a directional call on every classification cycle and no production path reads it. The blind agent measured it as 71-78% accurate about the planted drift sign, with a conditional 8-minute forward return of +2.20 bp against 0.364 bp declared friction - a roughly 6:1 edge-to-cost ratio computed every 120 s and discarded (the author has NOT re-measured those figures; the dead-code fact is verified, the edge estimate is not). If it survives measurement on real data this is the cheapest potential improvement in the repo; if it does not, the field should be deleted rather than left as a validated-but-unused boundary field.
- Justification: open. Wiring an unvalidated directional signal into live sizing is a spec-level change (it alters what AGON and the Governor consume), so it is raised, not done. Measure first on real ticks, then propose.
- Linked: [[GAP-P12D-31]], [[GAP-0035]], [[GAP-P12D-37]]

## GAP-P12D-35: the falsification harness rewinds the clock 7 days at every fold boundary — the runs we drew conclusions from are contaminated
- Severity: critical · Likelihood: high
- Status: fixed (2026-09-17 — the plan now separates successive test windows by the embargo, exactly as the ratified `plan_folds` does, and the harness raises on any backwards replay instead of mis-managing positions silently)
- Area: scripts/falsify_engine.py `plan()` (lines 41-49), tests/backtest/harness.py `_replay` (warm-up ticks manage open positions), tests/backtest/oos_runner.py:108 (warm-up states stream from the train end to the test-window start)
- Description: `falsify_engine.plan()` lays test windows end-to-end and sets the train end one embargo before the test-window start, so each fold's warm-up window (train end -> test-window start) lies INSIDE the previous fold's graded test window. Verified for plan(60, 30, 6): fold 0 tests 2014-03-14 -> 2014-04-13, then fold 1 warms up from 2014-04-06 — a 7-day rewind, at each of the 24 fold boundaries of the full run. Warm-up ticks are not inert: `_replay` calls `_tick(trade=False)`, which still runs `maybe_close` on open positions, so `(st.timestamp - pos.entry_ts)` goes NEGATIVE and the `max_hold_s` cap is suspended; out-of-order timestamps also reach `book.equity`, the day anchor and the rollover marker, and the annual Sharpe is computed from that curve. Corroborating artifact evidence: the full run reports `tsmom_avg_duration_s = 197,739 s = 54.9 h`, which is impossible under the 48 h cap.
- **The ratified path is NOT affected** (author-verified): `tests/backtest/oos_plan.plan_folds(2014, 2018)` yields fold k's test ending exactly where fold k+1's warm-up begins (2015-01-01, warm-up to 2015-01-08, graded from 2015-01-08) — monotonic, no overlap. `scripts/run_oos_validation.py` uses that plan, so no §14 number is implicated; only the falsification runs are.
- Consequence: the evidence behind [[GAP-P12D-31]] (planted/null/permuted all losing within a 0.4-Sharpe band) came from contaminated runs and must be regenerated after this and [[GAP-P12D-36]] are fixed. The finding itself is not withdrawn — independent evidence still supports it (the fitness proxy finds the planted edge in isolation while the composed engine does not, and a clean 45-day real-loop replay by the research agent reproduces a losing MEAN_REVERSION module) — but the specific numbers must not be quoted again.
- Justification: an implementation change to the author's own test harness (no spec involvement), made because no further falsification run is believable without it.
- Fix: `scripts/falsify_engine.py::plan` steps each test window forward by its own length plus the embargo, so each fold's warm-up window is the embargo gap and never re-enters the previous graded window; `tests/backtest/harness.py::_replay` raises `ValueError` on any warm-up tick that predates the last observed tick.
- Proof: `test_falsification_folds_never_overlap`, `test_an_overlapping_fold_plan_raises_instead_of_replaying_backwards`
- Residual: GAP-P12D-28 — every falsification run before 2026-09-17 was produced under the defect and must be regenerated; the numbers quoted in [[GAP-P12D-31]] and [[GAP-P12D-40]] carry it.
- Linked: [[GAP-P12D-31]], [[GAP-P12D-36]], [[GAP-P12D-28]], [[GAP-SP12E-03]]

## GAP-P12D-36: the graded backtest book never charges the spread — a direct C8 violation that flatters every §14 number
- Severity: high · Likelihood: high
- Status: fixed (2026-09-17 — the book now charges the declared C8 `per_side_cost` on both sides; the residual venue gap is owned by GAP-P12D-41)
- Area: tests/backtest/book.py `close_at` (friction term), core/optimizer/costs.py `CostModel.per_side_cost`, master §5 C8, specs/ACIS-09
- Description: the declared C8 cost of one fill side is `spread/2 + commission_per_side + slippage_per_side` (`costs.py:32-36`). The graded backtest book computes `friction = (slippage_per_side * 2 + commission_per_side * 2) * size_units` and never touches `per_side_cost`, so **the spread is omitted from every graded trade** — while the optimizer's own fitness mini-backtest DOES charge `per_side_cost(bar.spread)`. Master §5 C8 binds them to the same model ("unit-tested identical in both places"), so this is a spec violation, and it also means the optimizer is scored against a stricter cost world than the engine is graded in. The research agent measured the shortfall at ~48% of declared cost on the synthetic tape and ~29% on real EUR/USD (not independently re-measured by the author).
- Justification: an implementation fix against existing spec law, not a design change. It moves every graded number in the pessimistic direction, which is the correct direction: the harness had been too generous, the opposite of the failure the falsification was hunting.
- Fix: `OpenPos` records the spread quoted at entry; `close_at` charges `cost.per_side_cost(entry_spread) + cost.per_side_cost(exit_spread)` — the same function the optimizer's fitness calls, so master §5 C8's "one model, both places" is now true in code rather than in prose.
- Proof: `test_the_book_charges_the_declared_c8_cost_including_the_spread`, `test_a_position_opened_through_the_book_remembers_its_entry_spread`
- Residual: GAP-P12D-41 — charging the DUKASCOPY spread closes only about a quarter of the real gap, because the intended execution venue quotes far wider; GAP-P12D-28 — every earlier run was graded without this cost.
- Linked: [[GAP-P12D-35]], [[GAP-0001]], [[GAP-P12D-31]], [[GAP-0035]]

## GAP-P12D-33: the Deflated Sharpe gate is INVERTED — recording fewer trials makes it easier to pass, and honest recording refuses every run
- Severity: critical · Likelihood: high
- Status: open (2026-09-16 — found by the statistical-methodology research agent, VERIFIED numerically by the author the same day; the gate itself is owner-ratified C-BT-11 / GAP-P12D-16, so the author changed nothing)
- Area: tests/backtest/deflated_sharpe.py `sharpe_threshold`, tests/backtest/report.py:44 `_MIN_TRIALS = 2` and the `passed` gate, tests/backtest/evolve_step.py:87 + harness.py:209 (how trials are assembled), specs/ACIS-09 C-BT-11
- Description: `passed` requires `deflated_sharpe >= 0.95` over >= 2 trials — our headline defence against a Sharpe inflated by selection. `sharpe_threshold` estimates the trial VARIANCE from the trial Sharpe ratios supplied, so the fewer and more alike the recorded trials, the smaller the variance, the lower SR0, and the easier the gate. `_MIN_TRIALS = 2` permits exactly the degenerate case. Author's numerical check on one fixed graded record (per-trade Sharpe 0.123 over 560 trades, i.e. a record that would meet §14): **2 near-identical trials => SR0 0.0000, DSR 0.9979, PASS; 180 honestly recorded trials (sd 0.20) => SR0 0.5465, DSR 0.0000, fail; the same 180 with N lifted to the ~108,000 configurations actually evaluated => DSR 0.0000, fail.** Both directions are wrong: under-recording is REWARDED, and honest recording refuses every run, because the trials are per-trade Sharpe ratios measured on holdouts of as few as `holdout_min_trades = 5` trades (sampling sd alone ~0.45) while the graded Sharpe is a per-trade figure over thousands of trades — the two are not draws from the same null, which is what the paper's SR0 assumes. The formula itself is faithful (`test_reproduces_the_papers_numerical_example` pins the paper's SR0 0.1132 / DSR 0.9004 at N=100); the INPUTS are wrong. Consistent with the observed runs: the failed falsification reported `dsr=0.0` at 88-121 trials.
- Secondary: the recorded trial count understates the true search by ~600x — `population_size 20 x generations 30` = 600 configurations are evaluated and maximised over per QIEA run, and only champions are recorded (gated-out runs record nothing at all, adding survivorship truncation). The multiple-testing exposure that actually threatens the final grade — the OUTER design loop, every pipeline/gene-range/fitness revision re-evaluated against the same history — is counted nowhere.
- Justification: open and RAISED, not fixed. The gate is owner-ratified (GAP-P12D-16), and a live §14 pass would currently rest on it. It is guardrail-adjacent in spirit: it is the gate that decides whether a result may be believed. Two candidate remedies, both needing owner ratification because they change a ratified gate: (a) make the trial basis commensurate (trials and graded record measured over comparable samples, e.g. `holdout_min_trades >= 30`, and a floor under the trial variance) and re-ratify the 0.95 threshold against it; (b) replace the DSR as primary gate with PBO via CSCV, which reuses evaluations already performed and tests the question actually posed by a search. Until then, treat any DSR-based pass as unproven and do not present one as evidence.
- **2026-09-24, two developments from the BUILDER agent in [[GAP-P12D-52]]. Both are BUILT, PENDING AUDIT, on branch `worktree-agent-a128ab904780ce593`, not merged:**
  1. ~~The gate refuses perfect knowledge (oracle DSR 0.000)~~ **CORRECTED 2026-09-25** by AUDIT-EXTERNAL E4 ([[GAP-P12D-72]]). The oracle is not one of the trials, so that comparison was not a DSR. The valid evidence that the gate is broken is the mixing of sample lengths, where 5-trade holdout Sharpes set the hurdle for a thousands-of-trades record, and the VALIDATOR's measured 0-of-1,200 pass rate on planted edges.
  2. **Every QIEA evaluation is now logged** (genes, fitness, holdout; gated-out runs included; ~45 KB per evolve call). That makes the true trial count, and PBO/CSCV, computable. It is logging only: no gate reads it.

  The gate decision is still the owner's.
- **2026-09-24, the VALIDATOR's calibrated options** ([[GAP-P12D-52]]; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md). The setting was synthetic: 60 configurations on 12 development + 2 holdout years; 4 edge-free market kinds × 300 runs; planted best-config Sharpes of 0.19, 0.44 and 0.94 × 200 runs. **The gate as built passes NOTHING:** 0 of 1,800 edge-free markets and 0 of 1,200 planted, even at a true Sharpe of 0.94. That agrees with the BUILDER's oracle scoring DSR 0.000. The owner chooses:
  - **A. Keep as built.** It passes nothing.
  - **B1. DSR on daily out-of-sample returns**, with N = recorded looks and the trial variance taken from theory. False positives 0.3–2.3%; power 9–14% at 0.44 and 58–62% at 0.94.
  - **B2. B1 with an effective N.** False positives 1.3–4.3%; power 14.5% and 73.5%.
  - **C (RECOMMENDED).** CPCV + PBO ≤ 0.20 on the research simulator, with the CPCV threshold raised for every recorded look. Then ONE confirmation run through the real engine, graded by B2. False positives 2.0–5.0% for one look and 3.0–5.5% after 20 looks. Power 25% at 0.44 and 87% at 0.94 (83% after 20 looks); at 24 years, 55% and 99%.
  - **D, needed under ANY option:** the oracle positive control ([[GAP-P12D-37]], built on a branch), a structural leakage suite ([[GAP-P12D-65]]), and a look register written before every grade ([[GAP-P12D-64]]).

  **Rejected as gates,** each with its measured false-positive rate:
  - Rademacher Anti-Serum: its bound costs ~4.6 of annual Sharpe, so it has no power.
  - "Random entries, same exits": 83–89%.
  - The ±10% plateau test: 93–99%.
  - PBO on its own: 96% on markets where every configuration loses.
  - The cross-instrument holdout passes noise 10–23% unless it is residualised on the development instruments' P&L; residualised, it passes 2.7–4.7%.

  The Masters permutation test is more powerful (43% / 96%, false positives 3–8%), but needs 60 full re-runs of the search, so it can run only on a fast research simulator.
- **Progress 2026-09-25 (R-1, R1-D2 RATIFIED):** C-BT-11 v2 (ACIS-09 v1.7) supersedes the DSR gate for `passed` with a register-aware verdict: fixed-sequence stage A, engine confirmation, kill-only stage C, forward e-processes. The DSR becomes informational. The as-built gate stays until the verdict module lands (R1.4); it is the stricter one.
- Linked: [[GAP-P12D-16]], [[GAP-P12D-32]], [[GAP-P12D-25]], [[GAP-SP12E-03]], [[GAP-P12D-31]], [[GAP-0035]]

## GAP-P12D-34: the §5.6 parameter-plateau law is spec-mandated and entirely unimplemented
- Severity: high · Likelihood: high
- Status: fixed (2026-09-25 — the §5.6 plateau law is MERGED as ACIS-03 v1.5 §6.4, after the constitution's two audits (GAP-P12D-72/73). It uses a range-based ±10% step, and "dies" = fails C9 on the train window, the lead's delegated decision D8, for the owner's review. A refused candidate stays a DSR trial)
- Area: ACIS_SPEC.md §5.6 anti-overfitting law, core/optimizer/qiea.py (selection), specs/ACIS-03 §6, specs/ACIS-11
- Description: master §5.6 binds: "Parameter plateaus required — a strategy that dies at +/-10% on any parameter fails." Nothing in the optimizer, the harness or the validation path computes or enforces this. QIEA selects the single best-scoring individual, which is the peak-picking the law exists to forbid. The spec also requires reported metrics to be read against an attempt registry; the registry exists for strategies but does not count parameter configurations (see GAP-P12D-33's secondary finding).
- Justification: open. This is the cheapest genuine anti-overfitting device available to us — perturb the champion's genes by +/-10% and require the neighbourhood to survive — and it is already law, so implementing it needs no ratification, only building. It directly attacks the failure mode the falsification exposed: parameters that score well in selection and do nothing in execution.
- **BUILT on a branch, 2026-09-24 — BUILT, PENDING AUDIT, NOT MERGED** (BUILDER agent in [[GAP-P12D-52]]; branch `worktree-agent-a128ab904780ce593`; the new `plateau.py` module under core/optimizer exists only on that branch until merge).
  - **The mechanism.** A neighbour moves ONE gene by ±10% (rounded as `decode_gene` rounds, clamped to GENE_SPECS, invariants repaired). It "dies" if it fails the C9 gate on the champion's own train window. ANY death refuses the champion, logging `EVOLUTION_REJECTED_PLATEAU`.
  - **OWNER RATIFICATION NEEDED** for this reading of "dies", since it interprets spec prose. The ACIS-03 v1.5 amendment is drafted in the branch's BUILDER_REPORT_2026-09-24.md only.
  - **Cost:** 2.6 s per champion, 3.4% of an evolution run.
  - **Effect:** it refuses 11–14 of 30 champions on the repo's zigzag fixtures. Its rate on the planted market is not yet measured.
  - **Existing tests:** three changed seed or fold index only. The lead reviewed them: each tests determinism or ID traceability, not plateau behaviour, and the refused seed's rejection is pinned by its own test.
  - **The gene search space is unchanged**, so no re-baseline.
  - **The plateau law is a filter, not evidence.** The VALIDATOR measured the ±10% plateau test as a GATE on its own: it passes noise 93–99% of the time ([[GAP-P12D-33]] options). The spec requires it, and it removes knife-edge champions, but a champion passing it proves nothing.
  - **Close** when it merges after audit.
- Proof: `test_every_gene_moves_ten_percent_of_its_range_each_way_and_nothing_else_moves`, `test_a_single_dead_neighbour_fails_the_champion_and_is_named`, `test_qiea_refuses_the_same_champion_once_its_neighbourhood_dies`, `test_a_knife_edge_champion_on_the_real_landscape_is_refused`, `test_a_plateau_refused_candidate_stays_a_deflated_sharpe_trial`.
- Residual: GAP-P12D-68 — whether per-regime QIEA survives the redesign (item 4), and the owner's review of the D8 "dies" reading and the E6 range step (small period genes move by large ratios, e.g. ema_fast 6 → 10; a grid-step neighbour is the refinement).
- Linked: [[GAP-P12D-33]], [[GAP-0035]], [[GAP-P12D-31]], [[GAP-0008]]

## GAP-P12D-32: external research pass — findings and triage (report 1 of 5 in)
- Severity: high · Likelihood: high
- Status: open (2026-09-16 — owner: "run an external research agent … lets make the AWS worth the cash"; the first of five agents has reported, four are still running; every item below is a FINDER's claim until verified, and spec-level items need owner ratification)
- Area: the whole strategy design — exit geometry, decision clock, §14 targets, optimiser methodology; report `archive/RESEARCH_FX_METHODS_2026-09-16.md` (~40 web searches, sources graded academic / practitioner / unverifiable)
- VERIFIED by the author against the code and arithmetic (2026-09-16):
  - **Holding-horizon mismatch — CONFIRMED, and larger than reported.** `core/optimizer/fitness.py:126` counts `max_holding_periods` (gene range 1–48) in 1-MINUTE bars, so every candidate is scored under a ≤48-minute hold, while `tests/backtest/harness.py:93` runs the engine at `max_hold_s = 48 h`. Selection and execution disagree on horizon by ~60×. The agent reported this as an engine cap; it is actually a proxy-vs-execution mismatch, which is worse — it compounds [[GAP-0035]].
  - **§14 internal inconsistency — CONFIRMED by arithmetic.** Under iid monthly returns, "positive months > 70%" implies annual Sharpe 1.82, stricter than the stated "Sharpe > 1.5" (which implies 66.7%). Positive-months is silently the binding constraint. Owner-owned: §14 is master-spec text.
  - **"Synthetic markets ~9× more volatile than real EUR/USD" — REFUTED.** Synthetic 1-min sd is 1.32 bps (daily_vol 0.005 over 4,320 steps/day) vs ~1.16 bps for real EUR/USD at 7% annualised: ratio 1.13×. The harness does not flatter the engine through volatility. The agent's cost-drag derivation assumed CONTINUOUS exposure; our positions are open <1% of the time, so its "9× off" figure does not follow. The underlying question — does realised cost drag match the trade count and sizes? — is still worth answering and is NOT yet answered.
- UNVERIFIED claims worth testing, in the agent's own priority order: exit barriers sit on the zero-profit isoquant (it derives break-even barrier width `d* = σ√(c/μ)` and argues our ~2×-1-min-ATR barrier yields ~+0.12 bp/trade versus ~+7.65 bp at 10 bps width); the decision clock should move from ticks/1-min bars to ≥4-hour or daily bars; positions are open ~0.7% of instrument-minutes while signals fire on ~60%, so book-level dedup is the de facto position policy ([[GAP-0075]]); regime classification should be demoted from a gate to a weight and collapsed to ≤3 states; per-regime × per-instrument fitting (≈132 free parameters per instrument) is sample-fragmenting; parameters should be POOLED across instruments; the EUR/USD × USD/JPY pair-divergence module is redundant because EUR/USD × USD/JPY = EUR/JPY exactly (config/instruments.yaml:157 configures exactly this pair, `pearson_log_returns`, expected_sign -1 — the redundancy claim is plausible and unverified); financing modelled from central-bank overnight rates is one-directionally optimistic versus broker markups; win-rate as a §14 target and as a 0.20 fitness component biases selection toward tight-TP/wide-SL geometry.
- TARGET REALISM (the external-referent question we cannot ask ourselves): the agent's sourced verdict is that a net out-of-sample Sharpe > 1.5 on 2–9 FX instruments at retail cost is not achievable, citing SG Trend Index ≈0.42, a century of trend-following ≈0.4 per decade, post-GFC FX carry ≈0.25, and an FX-only trend walk-forward on our exact majors at 0.43; it proposes 0.3–0.7 as the realistic band. Most on-point negative: Neely & Weller (JIMF 2003) ran genetic programming AND optimised linear forecasting on intraday FX and found no excess returns once realistic costs and trading hours were included — the closest published analogue to this architecture. NOT independently verified by the author; the citations must be checked before any §14 change is proposed to the owner.
- Justification: open. This is a finder's report, not a decision (CLAUDE.md audit law: a subordinate is a finder, never a clearer). Four more agents are running, one of them deliberately given no framing so it can attack premises this one accepted. Triage happens once they are all in, so the recommendations can be cross-checked against each other rather than adopted single-source.
- Linked: [[GAP-P12D-31]], [[GAP-0035]], [[GAP-0075]], [[GAP-P12D-30]], [[GAP-P12D-03]], [[GAP-0001]]

## GAP-P12D-31: engine-level falsification FAILED — the engine loses money on a market whose planted trend its own fitness code finds easily
- Severity: critical · Likelihood: high
- Status: open (2026-09-16 — the pre-registered answer was null FAIL, permuted FAIL, planted PASS; planted FAILED. Owner's standing rule for this case: "if planted fails, that is a finding (the engine cannot find a planted trend), not a reason to tune the test")
- Area: the composed loop end to end — core/regime labels → core/optimizer selection → core/signals (AGON modules) → core/governor sizing → tests/backtest book; run `data/validation/falsification/20260915T231127Z` (25 folds, 817 days, EUR_USD + USD_JPY)
- Description: on the planted market (trend episodes of 1–4 h, drift 0.15σ per step, an edge the fitness harness captures easily — 80–90 of 100 random ParamSets profitable on contiguous bars, median E_R +0.25/+0.39) the engine traded 2,018 times and LOST: annual Sharpe −0.65, profit factor 0.84, win rate 42.7%, 48% positive months. On the null market it lost about the same way: 1,864 trades, Sharpe −0.90, PF 0.83, win rate 38.6%. Almost nothing separates the two, so the pipeline's realised trading is near-independent of whether an edge exists. Permuted finished the same way: 2,111 trades, Sharpe -0.49, PF failed — correct for a scrambled market, but it lost no more than the market WITH the edge. The run's own verdict line is `FALSIFICATION FAILED — wrong answer on: planted` (exit 1): two of three markets answered correctly, and the one that had to pass did not. All three lose within a 0.4-Sharpe band of each other, which is the finding — realised trading is near-independent of whether an edge exists.
- Evidence, from the planted run's own logs and report:
  - **Horizon mismatch:** mean trade duration 477 s (~8 min) against an edge that only pays over 1–4 h. TSMOM, carved out of the §14 duration metric, held 2.3 days.
  - **Entry spam decides the trade set:** `SIGNAL_EMITTED` 1,425,326 and `SIZED` 1,425,326, versus 2,018 booked trades. Which signals become trades is an artifact of the book's dedup, not a designed entry/holding policy — [[GAP-0075]] at full scale.
  - **Sizing signal is inert:** `MARGINAL_ALPHA_PINNED` on all 1,425,326 sizings, so the C6 marginal-alpha term never varied.
  - **Promotion is the exception:** 91 `PARAM_STAGED` but only 39 `PARAM_PROMOTED`, with 11,638 `PARAM_PROMOTION_STALLED` — most evolved params never reach the fast loop ([[GAP-0002]]).
  - **Regime gate dominates:** `DISCARD_VETOED_REGIME` 2,221,512 against `VETO_APPLIED` 81,042.
  - **The report could not attribute:** `per_regime` was `{}` and there was no per-strategy breakdown, so this run cannot say which regime or module lost the money. **CLOSED 2026-09-16 (owner: "do the recommended next step"):** every closed trade now carries the regime active at entry, and the report gained `per_strategy` beside a populated `per_regime` (ACIS-09 v1.6). Both are `SliceStats` — trade count, net PnL, win rate, profit factor, average duration, gross win/loss — not `MetricBlock`s, because a subset of trades has no continuous equity curve and a fabricated one is what GAP-P11E-02 forbids; an unattributed trade groups under `UNATTRIBUTED` so the hole stays visible. Proof: `test_slice_by_regime_is_hand_worked`, `test_slice_by_strategy_splits_the_same_trades_differently`, `test_an_unattributed_trade_is_visible_never_dropped`, `test_real_engine_trades_carry_their_regime_and_the_report_attributes_them`; 800 green. The failed run itself predates this, so diagnosing it needs a fresh (short) run.
- Hypotheses to test in order (none applied — this entry is a finding, not a fix): (1) [[GAP-0035]] — QIEA selects on a dual-EMA proxy while AGON trades six different modules, so a champion's fitness need not transfer to what the engine actually does; (2) [[GAP-0075]] — with no position/holding policy the engine cannot hold a multi-hour trend, whatever it selected; (3) exit geometry — ATR-multiple SL/TP on 1-minute bars truncates a 1–4 h drift within minutes, which fits the 8-minute mean duration and the sub-1 profit factor on both markets.
- **VERDICT WITHDRAWN (2026-09-16), see [[GAP-P12D-37]]:** the pass gate was unsatisfiable before the run began (planted needed an annualised Sharpe above 76), so a planted failure says nothing about the engine. What survives is the weaker, still-serious observation that the composed engine did not convert an edge its own fitness proxy finds in isolation, plus the independent module-level evidence in [[GAP-P12D-39]].
- **EVIDENCE CONTAMINATED (2026-09-16):** the run these numbers come from rewound the clock 7 days at each of 24 fold boundaries ([[GAP-P12D-35]]) and never charged the spread ([[GAP-P12D-36]]). Do not quote the numbers above again; re-run after both are fixed. The FINDING stands on independent evidence — the fitness proxy finds the planted edge in isolation while the composed engine does not — but its magnitudes are unreliable.
- Justification: open and blocking. This is the guard-2 evidence bar (CLAUDE.md "Operational correctness"): until the engine can capture an edge that is provably present, a §14 grade on real data cannot mean anything, and no paid training run is justified. It does NOT invalidate the GAP-P12D-29 fix — champions and trades exist now, which is what made this failure visible at all.
- **RE-RUN 2026-09-29, the FULL falsification, on the C-BT-12 market** (the Google compute server, code `daf7bd2`, 25 folds, 985 days, ~1 h 25 min; `data/validation/cost_stress/20260929T114406Z-gce/` and `data/validation/falsification/20260929T114406Z-gce/` (the JSON reports; the engine stores and both logs are in `gs://acis-compute-0929-data/runs/20260929/`)).
  - **Stage 1, the grader's positive control, PASSED at full scale:**
    - the perfect oracle PF 1.853, Sharpe 9.02, and near-pass (0.18) Sharpe 5.64: every non-DSR clause met;
    - near-fail (0.19): refused by profit factor alone;
    - null and permuted: refused by §14 rows.
    So the verdict is not VOID.
  - **Stage 2, the engine, STILL FAILS:**
    - planted Sharpe −1.92 (1,690 trades): wrong answer;
    - null −1.19 and permuted −0.45: right answers.
    - "FALSIFICATION FAILED — wrong answer on: planted" (exit 1). The engine loses MORE on the market that holds an edge than on the two that hold none.
  - **This finding is now stronger than on 2026-09-16:** the grader is proven calibrated at full scale on a market that differs from its null in drift only. The attribution is in [[GAP-P12D-49]]'s 2026-09-29 re-statement.
- Linked: [[GAP-P12D-28]], [[GAP-P12D-29]], [[GAP-0035]], [[GAP-0075]], [[GAP-0002]], [[GAP-0091b]], [[GAP-P12D-124]]

## GAP-P12D-30: evolving on a time span costs far more compute than 500 bars — about 36 minutes per instrument per fold on one core
- Severity: medium · Likelihood: high
- Status: open (2026-09-15 — a measured consequence of the GAP-P12D-29 fix; not yet a blocker)
- Area: core/optimizer/fitness.py `simulate_trades`, tests/backtest/evolve_step.py `evolve_fold`, tests/backtest/regime_labels.py `LabelledBarCache.history`
- Description: fitness costs about 6 µs per bar per evaluation (166,480 bar-steps/s, measured on 72,179 synthetic bars). A 730-day span gives an instrument about 750k one-minute bars across its tradeable regimes, so one fold's evolution costs about 600 evaluations × 80% train × 750k bars × 6 µs ≈ 36 minutes per instrument: about 4.8 h for 8 instruments, and about 2 days over ~10 folds on one core. `history()` also re-reads each yearly label file once per regime (3.4 s for a synthetic year of 72k bars; a real year is several times larger).
- Justification: open, not urgent. The falsification runs use short synthetic spans, and the real walk-forward is already planned for the 16-core server, where instruments can evolve in parallel (about 6 h per run). Options when it binds: evolve instruments in parallel inside a fold, read each label year once per fold, or share indicator series across a generation. None of them changes what is selected.
- Linked: [[GAP-P12D-29]], [[GAP-P12D-12]], [[GAP-P12D-15]]

## GAP-P12D-29: per-regime evolution never stages a champion at 1-minute bars — the 500-bar window's 100-bar holdout almost never holds the 5 trades the gate demands, so the engine never trades
- Severity: high · Likelihood: high
- Status: fixed (2026-09-15 — found by the quick engine falsification run, GAP-P12D-28; the owner ratified option (a) in-chat the same day, "I ratify a"; master v2.18, ACIS-03 v1.4)
- Area: master §5 (fitness on the last 500 target-regime bars), specs/ACIS-03 §6 (`fitness_bars`, `holdout_fraction`, `holdout_min_trades`), config/system_config.yaml `optimizer:`, core/optimizer/qiea.py `evolve`, tests/backtest/evolve_step.py
- Description: the quick run `data/validation/falsification/20260915T092253Z-quick` (3 folds, 28-day train) staged 0 champions in 54 evolutions (9 regimes × 2 instruments × 3 folds) on each of null, planted and permuted (planted: 11 INSUFFICIENT_DATA, 32 REJECTED_TRAIN, 11 REJECTED_OOS). Every test tick was then vetoed NO_PARAMS_FOR_REGIME, and all three markets made 0 trades. An offline diagnosis on the same labels tried 300 random ParamSets per regime × instrument on the exact fold-0 windows. The share that clears both the train gate (≥ 10 trades and E_R > 0 on 400 bars) and the holdout gate (≥ 5 trades and E_R > 0 on the last 100 bars) is 0.0–0.3% on every market, with a median of 0–3 holdout trades. The window is capped in bars, not by train length, so the full two-year run would give the same 0 trades, and planted would fail for this already-known reason. The live QIEA cycle follows the same rule, so the live engine would almost never stage params either.
- The test itself is sound: on contiguous bars (regime ignored), the same dual-EMA fitness harness finds the planted edge. Of 100 random ParamSets with ≥ 30 trades each, median E_R is +0.25 (EUR/USD) and +0.39 (USD/JPY), with 80/100 and 90/100 positive. Null gives −0.24/−0.22 (1/100 and 0/100 positive) and permuted −0.24/−0.19 (0/100).
- Remedy probe (not applied): evolving on every target-regime bar inside the 28-day train window (926–6,276 bars) makes champions reachable, with 0–30% of random ParamSets clearing both gates. But null and permuted clear them too (up to 15% and 12%), so the evolution gates alone do not separate edge from noise. That job stays with the §14 out-of-sample grade and the Deflated Sharpe (GAP-P12D-16), which is exactly what the full falsification run then tests. On planted, the regime windows show strongly positive train E_R (median +0.30 to +1.22 in 12 of 14 windows), against mostly negative on null.
- Options for the owner: (a) master §5 + ACIS-03: evolve on all target-regime bars inside a time span (the fold's train span in the backtest, a declared recency span live), keeping the train and holdout gates — recommended, because a span keeps "never full history" and gives rare regimes their bars; (b) raise `fitness_bars` to a larger fixed count (e.g. 5,000) — a smaller edit, but a fixed count still starves rare regimes (MEAN_REVERTING had 314–672 bars in 28 days); (c) lower `holdout_min_trades` — not recommended, since a 1–2-trade holdout is no evidence.
- Justification: owner decision (a). `optimizer.fitness_bars: 500` became `fitness_span_days: 730`, the ratified 2-year walk-forward train window. `core/optimizer/qiea.py` `fitness_window(history, cfg, now)` keeps every target-regime bar that opens within the span before `now`; QIEA and the walk-forward's holdout re-evaluation (`evolve_step.holdout_pnls`) both read it, and `evolve_fold` requests every bar inside both the fold's train window and the span (`LabelledBarCache.history(..., n=None)`). The train and holdout gates, C8 and C9 are unchanged. No re-baseline was needed, because the gene search space did not change (BASELINE.md).
- Proof: `test_evolves_on_every_bar_inside_the_span_not_a_bar_count`, `test_fold_evolves_on_every_bar_in_the_span_not_the_last_500`, `test_history_without_n_returns_every_regime_bar_in_the_window`, former `test_uses_only_last_fitness_bars`; 796 green.
- Residual: GAP-P12D-28 — the falsification runs must now show champions and trades, with null and permuted failing and planted passing; GAP-P12D-30 — the compute cost of span windows.
- Reproduction: `data/validation/falsification/20260915T092253Z-quick/diagnosis/` (`diag_evolve.py` capped windows + contiguous check, `diag_uncapped.py` + `diag_uncapped.log`).
- Linked: [[GAP-P12D-28]], [[GAP-P12D-30]], [[GAP-0008]], [[GAP-0035]], [[GAP-P12D-16]], [[GAP-P12D-18]]

## GAP-P12D-28: the validator itself is unfalsified — no end-to-end run on data with a known answer, and the mutation gate has never actually run
- Severity: high · Likelihood: high
- Status: fixed (2026-09-29 — the full `falsify_engine.py` run completed on the C-BT-12 market and its stage 1 passed at full scale: the harness recognises a strategy known to be good, passes the rung just above the §14 cut-off, and refuses the rung just below it by that row alone. It refuses the same logic on null and permuted by §14 rows. Opened 2026-09-15, owner: "add those to the todo list")
- Area: the evolve-driver pipeline end to end (tick stream → labeller → per-fold evolution → harness → report and gates), `scripts/mutation_gate.py` (ACIS-09 §14 quality gate on core/optimizer/fitness.py, core/optimizer/costs.py, tests/backtest/metrics.py)
- Description: every component is unit-tested and audited, but nothing yet shows the WHOLE driver gives the right verdict when the right verdict is known, so a pipeline that always passes, never passes, or leaks the future would go unnoticed. And the ACIS-09 mutation gate was only configured (`--check` smoke in CI); a mutation campaign against the metrics and cost code has never run, so a surviving mutant in a graded metric is unknown.
- Justification: owner-directed falsification suite, cheap and local. (1) NULL: random-walk ticks or a no-edge strategy — the run must fail, with the Deflated Sharpe near chance. (2) PLANTED EDGE: synthetic data with a known tradeable pattern — the pipeline must find it and grade it sensibly (proves it can pass at all). (3) LOOK-AHEAD CANARY: deliberately leak future prices into evolution or labels — it must be caught by a guard, or produce an implausible result that a guard flags. (4) PERMUTATION: scramble the time order or the labels — any edge must disappear. Plus run `python scripts/mutation_gate.py` on its targets and triage every survivor. Both need the runner (GAP-P12D-23) to exist first.
- Progress (2026-09-15): (3) LOOK-AHEAD CANARY built — `refuse_lookahead` in harness.py refuses a fold whose evolution record cites a bar at or after its train end, and a deliberately leaky label cache serving future bars is caught. (1)+(2) at HARNESS level built — the real harness, book, metrics, SPX join, Deflated Sharpe and gates on scripted strategies: a planted consistent edge over two years passes EVERY gate (the pipeline can pass), and a coin flip fails (on its first run the coin flip "passed" because the test's losing exit 1.10−0.005 = 1.0950000000000002 never touched a 1.095 stop, leaving losers open until the flat max-hold exit — a test artifact, fixed, and a reminder that unclosed losers flatter a record). ENGINE-level probe (scratch, 70 synthetic days, 3 folds of 12-day tests, 5-minute ticks): the real runner made ZERO trades on all three markets — null, AR(1) momentum and its permutation — with zero champions per fold (null: every regime rejected by the train/holdout expectancy gates; momentum: 42 × `EVOLUTION_INSUFFICIENT_DATA`, i.e. under `fitness_min_bars` 300 one-minute bars per regime in a 28-day window at one tick per 5 minutes). Labelling took 53–83 s and replay 91–144 s per market. So a null that "fails" there proves nothing, and a real engine-level falsification needs denser ticks and more than two graded years per market — hours of compute, not a unit test. BUILT for it: `tests/backtest/synthetic_market.py` (null / planted trending episodes / planted-permuted, demeaned, 20-second weekday ticks, independent synthetic SPX; properties proven by former `test_only_the_planted_market_trends` and former `test_permuting_keeps_every_move_and_only_changes_their_order`, renamed 2026-09-29 when the generator was rebuilt under C-BT-12 (GAP-P12D-91)) and `scripts/falsify_engine.py` (labels, then grades each market through `run_walk_forward`; exit 0 only when null and permuted fail and planted passes; `--quick` is a shape check that never gives a verdict). The mutation gate's first launch crashed inside mutmut (it reads sources with the Windows cp1252 codec) and the gate script reported that crash as "surviving mutants"; fixed (`PYTHONUTF8=1`; mutmut's exit-code bit field read properly). The first complete run reported 272 of 630 mutants surviving (fitness 140, costs 12, metrics 97, Deflated Sharpe 23), but that count was NOT trustworthy: mutmut 2.5.1 records a mutant as killed only when the runner exits with code 1, and pytest exits 2 on a collection error — exactly what a mutant that breaks an import causes (CostModel `v = getattr(...)` → `v = None`: killed by hand, recorded as survived, twice). Fixed: mutmut now calls `mutation_gate.py --run-tests`, which reports every failing test run as 1 (`test_every_failing_test_run_counts_as_a_kill`). Genuine gaps the run exposed are closed with hand-worked tests: the Wilder RSI/ATR recursions, the EMA seed, the exact stop/target/max-hold/mark-to-close exits, the fitness components, the Sharpe/drawdown/month/VaR/SPX-join arithmetic and the Deflated Sharpe skew/kurtosis/sample-variance paths. One dead branch the gate found unreachable was removed (`metrics._avg_duration`'s all-trades branch). ACIS-09 v1.5. MUTATION GATE DONE: a clean run from an empty cache (shim, no bytecode, all new tests) — 626 mutants: 529 killed, 53 killed but slow, 44 survived, and every survivor is equivalent or tie-only per the triage record. The first `falsify_engine.py --quick` run crashed on its own bug: all three markets wrote labelled bars under one `labels/<instrument>/<year>` root, so parallel jobs collided on the same file (and run in sequence they would have silently overwritten each other's labels); each market now has its own label directory. Still to do: the quick, then the full, `falsify_engine.py` run (the full run must precede any paid or long real-data run).
- Mutation triage record (every survivor class, with the reason it is not a test gap): [archive/MUTATION_TRIAGE_P12D28.md](archive/MUTATION_TRIAGE_P12D28.md). The second run (shim in place) left 81 survivors; hand-applying each claimed-killable one showed 2 more false survivors — same-size mutants run from a stale `.pyc` — so the shim now writes no bytecode; the rest were real gaps (now tested) or equivalent / tie-only (recorded).
- Progress 2026-09-15 (quick engine run): `python scripts/falsify_engine.py --quick --workers 3` ran end to end (labels 221–286 s per instrument-year, grading 771–874 s per market) and exited 3 as designed, but made 0 trades on all three markets because no fold staged a champion — owned by GAP-P12D-29. The owner ratified GAP-P12D-29 option (a) the same day and it is built (master v2.18). The quick run on the fix (`20260915T222826Z-quick`, 2026-09-15) shows the pipeline working again: champions per fold null [2,3,2] / planted [2,6,1] / permuted [1,1,0], trades 122 / 250 / 14, Sharpe -4.42 / +0.92 / +1.93 — the planted edge earns, the no-edge market loses. It still exits 3 with no verdict (under two graded years, nothing can pass by design). The FULL run was launched detached 2026-09-15 23:11 UTC (PID 13656, log `data/validation/falsification/detached_full.log`): null and permuted must fail, planted must pass, and permuted's Deflated Sharpe must stay under the 0.95 gate (it reached 0.70 on 14 quick-run trades).
- Proof (so far): `test_evolution_fed_future_prices_is_caught`, `test_the_honest_path_is_not_flagged`, `test_a_planted_edge_passes_every_gate`, `test_a_coin_flip_strategy_fails`, `test_only_the_planted_market_carries_the_scheduled_drift`, `test_permuting_keeps_every_move_and_changes_order_and_sign`, `test_every_failing_test_run_counts_as_a_kill`, `test_the_verdict_reads_mutmuts_exit_bits`, `test_wilder_rsi_hand_worked_gains_first`, `test_wilder_atr_hand_worked`, `test_a_stop_touched_exactly_exits_at_the_stop_even_when_the_target_is_touched_too`, `test_a_cross_on_the_first_bar_after_warm_up_is_taken`, `test_a_cross_is_decided_without_the_next_bar`, `test_evaluate_fitness_hand_worked_below_the_clamps`, `test_spx_correlation_skips_a_zero_equity_base_and_needs_three_samples`, `test_rolling_var_breach_rate_second_breach_and_divisors`, `test_the_trial_variance_is_the_sample_variance`
- Result (2026-09-29): `data/validation/cost_stress/20260929T114406Z-gce/` and `data/validation/falsification/20260929T114406Z-gce/` (the JSON reports; the engine stores and both logs are in `gs://acis-compute-0929-data/runs/20260929/`); `oracle.RUNGS` re-calibrated to 0.18 / 0.19 ([[GAP-P12D-124]]).
- Residual: GAP-P12D-31 — the ENGINE fails the planted market, now against a calibrated grader; that is the engine's defect, not the validator's.
- Linked: [[GAP-P12D-23]], [[GAP-P12D-25]], [[GAP-SP12E-01]], [[GAP-P12D-124]]

## GAP-P12D-27: sizes and money assume FX lots of 100,000 units, a USD account, and fresh cross rates
- Severity: medium · Likelihood: medium
- Status: open (2026-09-15 — dual audit of 068f8b4, F-E5/F-E7/F-I9; nothing affected is enabled yet)
- Area: core/governor/capital_governor.py lot cap, core/execution/venue.py `UNITS_PER_LOT`, the orchestrator/fragmenter, core/governor/units.py (cross leg rate), config/platform_rules.yaml (account currency), ACIS-13
- Description: (1) 100,000 units per lot is hard-coded everywhere, but contract size is per symbol (gold is 100 oz and broker-dependent), so a prop `max_lots` cap on gold would never fire; `size_units` is never snapped to `lot_step`/`min_lot` or the broker's unit precision. (2) The account currency is assumed USD, while some drafted prop rulebooks may be EUR/GBP accounts. (3) A cross's USD rate comes from the last bar of its USD leg with no age check (a 30-day-old bar sizes silently), and the Risk Monitor has no cross route.
- Justification: open, not urgent. No cross, metal or non-USD account is enabled, so nothing sized today is affected. It must be fixed before XAU_USD or any cross is enabled (the diversification-onboarding TODO) and inside ACIS-13 (per-instrument contract size plus an adapter-side downward snap, rulebook `account_currency` validated at boot, a staleness bound on the conversion leg).
- Linked: [[GAP-P12D-22]], [[GAP-0092]], [[GAP-SP12E-01]]

## GAP-P12D-26: pair legs are balanced in base-currency units, not USD — a "relationship bet" keeps a directional USD residual
- Severity: medium · Likelihood: high
- Status: resolved (2026-09-15 — owner: "Balance in USD"; ACIS-05 → v1.4)
- Area: core/governor/capital_governor.py `allocate_group` (`balanced = min(leg_a.size_units, leg_b.size_units)`), specs/ACIS-05 §7 step 6, tests/unit/test_governor_units.py former `test_pair_legs_balance_without_the_yen_leg_shrinking_both`
- Description: after the base-unit fix, `min()` compares a EUR count with a USD count. On the configured EUR/USD–USD/JPY pair the legs carry $486.00 and $441.82, leaving a +$44.18 USD directional residual in the Governor's own delta accounting. For gold against AUD/USD the AUD leg is sized to $0.16 against $480 of gold. That contradicts §7.6's "one relationship bet, not two directional bets". The commit's own test pins unit equality, the wrong invariant.
- Justification: the fix balances in USD notional (take the smaller leg's USD value and convert it back to each leg's own units), with an ACIS-05 v1.4 wording change from "min(size_A, size_B)" to "min USD notional". Recommended; waiting for the owner.
- Resolution: `allocate_group` takes the smaller leg's USD notional and converts it back into each leg's own base units; the group caps use those per-leg USD notionals. ACIS-05 §7 step 6 now reads "the smaller leg's USD notional".
- Proof: `test_pair_legs_balance_in_usd_not_in_unit_counts`, `test_group_sizes_both_or_neither_balanced`, `test_gap0049_healthy_group_still_sizes`
- Residual: none — both legs of every pair now carry equal USD notional to within the 0.01-unit rounding, so no directional residual remains.
- Linked: [[GAP-P12D-22]], [[GAP-0049]]

## GAP-P12D-25: the ratified trial set does not make the gate the paper's Deflated Sharpe
- Severity: high · Likelihood: high
- Status: resolved (2026-09-15 — owner chose option (a), "Real selection set"; BUILT the same day: the trials are every candidate champion's holdout per-trade Sharpe, N adds the attempt registry, and the graded series is the out-of-sample per-trade return)
- Area: tests/backtest/harness.py (fold Sharpes as the variance, champions + registry as N), tests/backtest/deflated_sharpe.py (declared deviations now stale), specs/ACIS-09 C-BT-11
- Description: Bailey & López de Prado's SR0 uses the dispersion of the Sharpe ratios of the ALTERNATIVES selected among, on the same sample. As built, the variance is one strategy's per-fold out-of-sample Sharpe spread (variation over time), and N counts per-fold champions that are pieces of the graded curve, not alternatives to it. Two consequences, both reproduced. With ordinary fold dispersion and N ≈ 180–720, the gate needs an annualised OOS Sharpe of ~2.5–3.0, against §14's 1.5. Two folds that happen to agree make the dispersion ~0 and neutralise any N (DSR 1.0000 at N = 10⁶).
- Justification: options for the owner. (a) Use a real selection set: at each fold's selection, the candidate champions (every instrument × regime evolved), with their holdout Sharpe on a common per-period basis, give the variance and N. This is closest to the paper but needs a comparable per-period Sharpe for bar-level candidates. (b) Keep the ruled design, but declare it as a deviation, rename the statistic and set the gate level knowingly. (c) Gate on the Probabilistic Sharpe against 0 with an explicit trial-count haircut. Until decided, `passed` keeps the current gate, and deflated_sharpe.py's stale deviation note is corrected.
- Build: `evolve_fold` records `holdout_trade_sharpe` for each candidate champion and a fold-level `trial_sharpes`; `ClosedTrade.notional_usd` gives every out-of-sample trade a return; `Backtest.run` gates on `deflated_sharpe(trade_returns, trials, len(trials) + min_trials)`, and with fewer than 2 trial Sharpe ratios `trial_count` stays below 2, so the run cannot pass. Common basis chosen: PER TRADE (both sides dimensionless), because candidates are bar-level holdout simulations without calendar returns. Declared deviations (in deflated_sharpe.py, the report caveats and ACIS-09 C-BT-11): the per-trade basis, and that candidates are scored by QIEA's dual-EMA fitness harness rather than the full multi-strategy engine being graded (GAP-0035).
- Proof: `test_candidate_champion_sharpes_are_the_trials_and_the_registry_raises_n`, `test_fewer_than_two_trial_sharpes_cannot_claim_n`, `test_every_candidate_champion_with_a_sharpe_is_a_trial`, `test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read` (a candidate whose holdout trades have zero variance has no Sharpe and is not a trial)
- Residual: GAP-0035 — until the fitness harness exercises the engine's own modules, the candidate Sharpe ratios only approximate the alternatives the engine actually trades; GAP-P12D-28 — the falsification suite must show the gate fails on no edge and passes on a planted edge.
- Linked: [[GAP-P12D-16]], [[GAP-P12D-18]], [[GAP-SP12E-03]]

## GAP-P12D-24: dual audit of 068f8b4 (Governor base-unit sizing + evolve-driver steps 1–4) — triage
- Severity: medium · Likelihood: high
- Status: fixed (2026-09-15 — both lenses ran on Fable 5.1 before the Opus-5 auditor directive, 18 findings; every FIX-NOW item below is built and tested, 696 green; the owner items and later items are owned by their own entries)
- Area: core/governor, tests/backtest (harness, regime_labels, oos_plan, evolve_step), specs/ACIS-05
- Description: internal lens 11 findings (0 high, 5 medium, 6 low, 20 honest negatives, full suite 687 green) and external lens 7 findings (2 high, 3 medium, 2 low). Reports: archive/AUDIT_P12D22_INTERNAL.md and archive/AUDIT_P12D22_EXTERNAL.md; brief AUDIT_BRIEF_P12D22.md. Survived both: the base-unit sizing arithmetic (matches OANDA's 1 unit = 1 base currency), caps in USD on every path, the labeller has no look-ahead, the calendar-gate move is identical (32,916 instants across DST weeks), the DSR formula matches the paper, the fold plan matches the runbook, seeds reproduce.
- Justification: triage. OWNER: F-E1/F-I11 → GAP-P12D-25; F-E2/F-I1 → GAP-P12D-26. LATER: F-E5/F-E7/F-I9 → GAP-P12D-27. FIX NOW (owned here): F-E3 (cold engine — TSMOM can never fire in the first test year, nor in 2024 of a holdout run) and F-E4 (the embargo leaves a 7-day blind hole in engine state): an observe-only warm-up before each test window plus TSMOM daily-history seeding from bars before it. F-E6/F-I2 (the cache key omits data config, instrument spec, calendars, data start and a labeller version): hash them in. F-I3 (the CSV is replaced before the meta, so a crash can serve new labels under an old key): invalidate the meta first. F-I4 (`begin_final` writes the once-only marker before validating the plan): validate first, and give `Fold` a construction invariant. F-I5 (`history` filters on bar open and ignores `train_start`): require the bar to CLOSE by `end` and open on or after `train_start`, and record the span. F-I6 (a backtest without session boundaries never promotes, silently): refuse. F-I7 (the gap boundaries are swept before the carried position's max-hold close): close first, then sweep. F-I8 (ACIS-05 §5 calls `per_currency_delta` base-currency units): correct to USD notional. F-I10 (residuals pointed the runner at GAP-P12D-03): repointed to GAP-P12D-23.
- Proof: `test_warm_up_ticks_feed_the_engine_but_never_trade`, `test_a_position_closed_on_a_tick_frees_that_tick_s_boundary_sweep`, `test_staged_params_without_session_boundaries_are_refused`, `test_one_close_per_fx_trading_day_and_nothing_after_the_end`, `test_seeding_gives_tsmom_its_full_history`, `test_history_drops_straddling_bars_and_bars_before_the_train_start`, `test_history_refuses_a_window_with_an_uncached_year`, `test_the_key_changes_with_every_label_input`, `test_a_fold_must_be_ordered`, `test_the_holdout_is_graded_once`, `test_pair_legs_balance_in_usd_not_in_unit_counts`. The F-I3 commit order (meta unlinked before the CSV is replaced) is in `LabelledBarCache.write`; F-I8 is the ACIS-05 v1.4 §5 wording.
- Residual: GAP-P12D-23 — the runner must USE the warm-up (warm-up ticks from `train_end`, `seed_tsmom` before fold 0); GAP-P12D-25 — build the candidate-champion trial set; GAP-P12D-27 — per-instrument lot size, account currency, cross-rate staleness.
- Linked: [[GAP-P12D-22]], [[GAP-P12D-18]], [[GAP-P12D-23]], [[GAP-P12D-25]], [[GAP-P12D-26]], [[GAP-P12D-27]]

## GAP-P12D-23: the out-of-sample evolve-driver runner (step 5) is not built
- Severity: high · Likelihood: high
- Status: fixed (2026-09-15 — the runner is built and runs end to end on synthetic data; it has NOT yet run on real data)
- Area: a runner under scripts/ (to write), tests/backtest harness wiring
- Description: no command yet runs the walk-forward on real data. The runner owns: the real portfolio snapshot for the Governor's guardrails (GAP-P12D-21), strategy attribution on trades (GAP-P12D-20), the account rulebook, per-instrument cost models, the dated financing model and date-joined SPX closes, `min_trials` from the attempt registry, the holdout guard, the observe-only warm-up (GAP-P12D-24), and writing the report plus BACKTEST_RUN.
- Justification: the next build step; tracked on TODO.md.
- Fix: tests/backtest/oos_runner.py `run_walk_forward` (the account's universe, rulebook, per-instrument cost models, swap conventions, clusters and session boundaries; the real portfolio snapshot; TSMOM seeding plus per-fold warm-up; per-fold evolution; attempt-registry N; production guardrail hash; BACKTEST_RUN; report JSON) and scripts/run_oos_validation.py (the holdout guard, refusal when labels are missing, Dukascopy + SPX + dated financing, data/validation/oos/<run id>/report.json).
- Proof: `test_the_runner_grades_two_folds_end_to_end`
- Residual: GAP-P12D-28 — the pipeline must be falsified (null, planted edge, look-ahead canary, permutation) and the mutation gate run before any real or paid run; GAP-P12D-03 — no historical event calendar, so event risk is traded through (stated in every report).
- Linked: [[GAP-P12D-18]], [[GAP-P12D-20]], [[GAP-P12D-21]], [[GAP-P12D-24]], [[GAP-P12D-03]], [[GAP-P12D-28]]

## GAP-P12D-22: the Governor sizes every instrument as if USD were the quote currency — USD/JPY positions come out ~150× smaller than ACIS-05 defines
- Severity: high · Likelihood: high
- Status: fixed (2026-09-15 — owner: "fix the governor sizing and commit it"; ACIS-05 → v1.3; the dual audit of the change is launched after the commit)
- Area: core/governor/capital_governor.py `_allocate_one` (`size_units = raw_usd / entry_price`), `_exposure_breach` / `_delta_contributions` (notional = units × price), specs/ACIS-05 §4 (`size_units: base-currency units`) and §6 step 3
- Description: ACIS-05 defines `size_units` in BASE-currency units, with the USD raw size "converted to Decimal units at entry_price". The code divides the USD amount by the price for every instrument. That is right when USD is the quote currency (EUR/USD: $1,000 / 1.10 = 909 EUR). It is wrong when USD is the base (USD/JPY: $1,000 of exposure is 1,000 USD, but the code sizes 1,000 / 150 = 6.67 USD), so USD/JPY trades at about 1/150 of the intended risk. The exposure caps happen to compute the right USD notional (units × price = the original $1,000), which is why no cap test caught it. Crosses (EUR/GBP) and gold need the quote→USD rate in the conversion too. `test_governor` covers sizing on EUR/USD only.
- Justification: a backtest graded with this bug shows USD/JPY with almost no PnL, understating risk and return on half the enabled universe. The faithful fix converts the USD size to base units through the quote→USD rate (the same route as `tests/backtest/money.py`), with a units-per-instrument test for XXX_USD, USD_XXX, a cross and gold, then the dual audit. Raised, not fixed, because it changes audited sizing arithmetic.
- Fix: `core/governor/units.py` `usd_per_base_unit` gives the USD value of one base unit (price for USD-quote, 1 for USD-base, price × the quote leg's last bar close for a cross, None with no leg). `_allocate_one` divides the USD size by it, and a cross without a rate sizes zero (`no_usd_rate`). Order notional and each pair leg's notional use the same factor. The weekend and next-boundary calendar gates moved unchanged to `core/governor/calendar_gates.py`, taking capital_governor.py from 464 to 448 lines (ratchet lowered).
- Proof: `test_usd_base_instrument_is_sized_in_dollars_not_divided_by_the_yen_price`, `test_usd_quote_and_gold_divide_by_the_price`, `test_a_cross_converts_through_its_quote_leg_or_sizes_zero`, `test_usd_base_notional_meets_the_currency_cap_in_dollars`, `test_pair_legs_balance_in_usd_not_in_unit_counts`
- Residual: GAP-0092 — the Risk Monitor's own PnL view for non-USD-quoted instruments is a separate, already-tracked scale issue; the dual audit of this change runs after the commit.
- Linked: [[GAP-0092]], [[GAP-P12D-05]], [[GAP-P12D-21]]

## GAP-P12D-21: a backtest must hand the Governor a real portfolio snapshot — a NAV-only one silently switches off the cluster cap, the currency-delta cap and the daily-drawdown halt
- Severity: high · Likelihood: high
- Status: fixed (2026-09-15 — built with the OOS runner)
- Area: the evolve-driver runner's `portfolio_fn`, tests/backtest/book.py `BookState`, core/governor/capital_governor.py `_guards` / `_exposure_breach`
- Description: the Governor zeroes an order when `portfolio.daily_drawdown_pct` reaches the guardrail limit, and applies the cluster and single-currency caps to `per_cluster_exposure` and `per_currency_delta`. The phase-7 tests pass a flat snapshot (`flat_portfolio`: empty exposures, 0% drawdown). A real replay that did the same would trade through every one of those guardrails, and ACIS-09 §6 requires the production guardrails to be active. No production builder exists yet (the live runtime, GAP-0091b).
- Justification: the runner will derive the snapshot from the backtest book on every call: NAV; open positions; exposure and currency delta computed exactly as the Governor accumulates them (units × entry price per cluster, ± per base/quote currency); and the daily drawdown from the equity at the trading day's 17:00-New-York start (`fx_clock.trading_day`, as the Risk Monitor does). Tests pin the drawdown halt and caps firing inside a replay.
- Fix: tests/backtest/portfolio_view.py `build_portfolio_state`, exposed as `Backtest.portfolio_state()` and wired as the loop's `portfolio_fn` by the runner. The daily anchor is set at the first observation of each FX trading day, BEFORE that tick's decisions read the portfolio.
- Proof: `test_exposure_and_currency_delta_are_the_governors_usd_arithmetic`, `test_daily_drawdown_runs_from_the_trading_day_anchor`, `test_an_unattributed_position_is_refused`, `test_the_day_anchor_resets_at_the_new_york_rollover`
- Residual: GAP-0091b — the live runtime still needs its own portfolio accounting from broker state; the backtest one is test-side.
- Linked: [[GAP-P12D-22]], [[GAP-0091b]], [[GAP-P12D-18]]

## GAP-P12D-20: every trade the real engine makes is booked with strategy "UNKNOWN" — the §14 duration carve-outs never apply in a real backtest
- Severity: medium · Likelihood: high
- Status: fixed (2026-09-15 — built with the OOS runner)
- Area: tests/backtest/book.py `PositionModel.apply_order` (reads `factors_snapshot["strategy_type"]`), core/governor/capital_governor.py `factors_snapshot`, tests/integration/paper_loop.py `PaperBook`
- Description: the harness takes a trade's strategy from `order.factors_snapshot["strategy_type"]`. The Governor's snapshot has no such key (its keys are the sizing factors), so every real engine trade becomes "UNKNOWN". The C-BT-8 carve-out that excludes TSMOM and MOMENTUM_SCALP from the 30 min–48 h duration band therefore never applies, and per-strategy reporting is empty. The harness tests pass because their scripted orders put the key in by hand.
- Justification: the loop knows each order's signal. The fix records `order_id → strategy` in the paper book when the loop opens an order and has the harness read it there, falling back to the snapshot for scripted tests. A test must drive a real TSMOM order through the harness and see "TSMOM" on the closed trade.
- Fix: `PaperBook.open(order, strategy)` records `order_id → strategy` when the loop opens an order (singles and both group legs); the harness passes it to `PositionModel.apply_order`, and positions keep their param set and group for the portfolio snapshot.
- Proof: `test_real_engine_trades_carry_their_strategy`
- Residual: none — every order the real loop opens carries its signal's strategy, and the portfolio snapshot refuses any position without one.
- Linked: [[GAP-0055]], [[GAP-0009]], [[GAP-P12D-18]]

## GAP-P12D-19: the harness charged ONE cost model to every instrument — friction is in price units, so a multi-instrument run mispriced it by ~100×
- Severity: high · Likelihood: high
- Status: fixed (2026-09-15, found while building the evolve-driver)
- Area: tests/backtest/harness.py `Backtest(cost_model=…)` → tests/backtest/book.py `PositionModel(costs=…)`
- Description: `Backtest` took a single `CostModel` and applied its `slippage_per_side` to every closed trade. instruments.yaml declares friction per instrument in PRICE units (EUR/USD 0.00002, USD/JPY 0.002), so the EUR/USD model applied to USD/JPY charged 1% of the declared friction, and the reverse 100×. Every test ran on one instrument, so nothing caught it.
- Justification: the position model now takes a cost model per instrument and raises for an instrument without one (no silent zero cost). The book and fill/close model moved from harness.py to book.py.
- Proof: `test_each_instrument_pays_its_own_friction`
- Residual: none — every close now reads its own instrument's declared model; calibrating those declared values against OANDA spreads is the existing C8 calibration step (ACIS-09 §5).
- Linked: [[GAP-0001]], [[GAP-P12D-18]]

## GAP-P12D-18: evolve-driver design rulings — in-sample record, which instrument evolves each regime, and a computable trial set
- Severity: high · Likelihood: high
- Status: resolved (2026-09-15 — owner chose all three recommendations)
- Area: tests/backtest/harness.py, the evolve-driver (to build), specs/ACIS-09 §7 step 3, GAP-P12D-16's trial definition
- Description: three problems found while designing the evolve-driver. (1) The harness replayed each fold's 2-year TRAIN window through the same engine after the previous fold's TEST year. With real rolling folds that goes back in time (the engine refuses out-of-order ticks) and adds ~20 years of replay compute, for a block that is never graded. (2) ParamSets are per regime and shared by all instruments, but QIEA evolves on one instrument's bars (prices and costs differ), and ACIS-03 does not say which. (3) The ratified trial set ("attempt-registry configurations plus per-fold champions") cannot be computed: registry entries hold descriptions, not returns, so they have no daily Sharpe.
- Resolution: (1) no in-sample tick replay; the in-sample transparency record is each fold's evolution summary (`ValidationReport.in_sample_evolution`; `in_sample` carries a not-replayed block and a caveat). (2) Each regime evolves on EVERY enabled instrument, and the champion with the best holdout expectancy is staged; every per-instrument champion counts toward N. (3) The Deflated Sharpe variance comes from each fold's out-of-sample test-segment daily Sharpe; N = the larger of that count and `min_trials` (every champion evolved plus the attempt-registry entries for the enabled families). With fewer than 2 fold Sharpes no N may be claimed, so the run cannot pass.
- Proof: former `test_fold_sharpes_are_the_trials_and_min_trials_raises_n`, former `test_a_single_fold_cannot_claim_trials` (the trial set was replaced by GAP-P12D-25), `test_candidate_champion_sharpes_are_the_trials_and_the_registry_raises_n`, `test_fewer_than_two_trial_sharpes_cannot_claim_n`, `test_n_trials_can_raise_n_but_never_lower_it`, `test_promotion_sweeps_see_the_backtest_book_not_the_loop_order_list`
- Residual: GAP-P12D-23 — the runner (step 5); GAP-P12D-24 — the audit fixes to steps 1–4.
- Linked: [[GAP-P12D-16]], [[GAP-P12D-03]], [[GAP-SP12E-03]], [[GAP-0075]]

## GAP-P12D-17: `annual_sharpe` turned a constant non-zero return series into a Sharpe of ~1e16 — float dust could clear the §14 Sharpe gate
- Severity: medium · Likelihood: low
- Status: fixed (2026-09-15, found while building the Deflated Sharpe's moments)
- Area: tests/backtest/metrics.py `annual_sharpe`
- Description: the zero-variance guard compared `sd == 0.0`, but a plain `sum` over a long constant series leaves float dust. 50 × 0.01 gave sd ≈ 1e-18 and an annual Sharpe of 4.5e16; 252 × 0.001 gave 2.4e16; 500 × −0.0007 gave −3.8e15. The existing test used only 3 values, where the sum happens to be exact. Same hazard class as GAP-0076.
- Justification: `math.fsum` rounds the sum correctly, so a constant series has exactly zero variance and a Sharpe of 0.0, as the guard intended. The new Deflated Sharpe moments use `fsum` for the same reason.
- Proof: `test_constant_nonzero_returns_have_no_sharpe`, `test_no_sharpe_means_nan`
- Residual: none — a constant series now scores Sharpe 0.0, which fails §14 by itself, so float dust in the other metrics cannot turn such a series into a pass.
- Linked: [[GAP-0076]], [[GAP-SP12E-03]]

## GAP-P12D-16: the Deflated Sharpe is computed and reported but does not gate `passed` — the level, and what counts as a trial, are owner decisions
- Severity: medium · Likelihood: high
- Status: resolved (2026-09-15 — owner: "gate DSR at 0.95 as you recommended")
- Area: tests/backtest/report.py `build_report`, tests/backtest/harness.py `Backtest.run(trial_sharpes=…)`, specs/ACIS-09 §4/§13 (C-BT-11), OOS_VALIDATION.md
- Description: GAP-SP12E-03 required a Deflated Sharpe and a logged trial count before a §14 pass can gate live. Both are now in every `ValidationReport`, but `passed` ignores them, because neither master §14 nor ACIS-09 states a level or a trial definition. Without a gate, a report can pass on a raw Sharpe inflated by selection bias.
- Justification: two decisions. (1) Level: the paper's worked example uses 95% confidence (DSR ≥ 0.95); gating is a tightening, which the grader allows. (2) Trials: which Sharpe ratios count — the distinct configurations in the ACIS-11 attempt registry, each walk-forward fold's champion, or every QIEA candidate (thousands, highly correlated, which over-deflates). Recommendation: gate at DSR ≥ 0.95; count the attempt-registry configurations for the strategy family plus the per-fold champions, and record N in the report.
- Resolution: the recommendation is ratified and built. `build_report` now requires `deflated_sharpe >= DSR_MIN` (0.95) and `trial_count >= 2`, and a NaN DSR fails. Trials are the ACIS-11 attempt-registry configurations for the strategy family plus each walk-forward fold's champion. Because C-BT-2 requires more than one fold, a correctly recorded run always has at least 2 trials, so fewer means the selection went unrecorded and the run cannot pass; the harness caveat says so. ACIS-09 v1.4 (C-BT-11).
- Proof: `test_deflated_sharpe_below_095_cannot_pass`, `test_unrecorded_trials_cannot_pass`, `test_passing_report_passes`
- Amendment (2026-09-15, GAP-P12D-18): the registry entries have no returns, so the computable trial set is each fold's out-of-sample daily Sharpe (the variance), with N lifted to every champion evolved plus the attempt-registry count.
- Residual: GAP-P12D-23 — the runner must supply the trials and at least 2 folds, and GAP-P12D-25 replaces the trial set; until then no report can pass.
- Linked: [[GAP-SP12E-03]], [[GAP-SP12E-01]], tests/backtest/deflated_sharpe.py

## GAP-P12D-15: after the P12D-12 fixes the busy replay path is ~691 ticks/s — ATR recomputation and per-tick database lookups now dominate
- Severity: high · Likelihood: high
- Status: mitigated (2026-09-15 — owner go "do the speed fixes"; built, dual-audited by Fable 5.1 (10 findings, all triaged and fixed by a redesign) and proven identical on real ticks; GAP-0075 per-tick sizing, a quiet-machine and 8-instrument re-measure, and multi-core compute remain)
- Area: core/signals/indicators.py `wilder_atr` → core/optimizer/fitness.py `atr_series` (called from core/signals/agon.py `_tsmom` and the Governor's vol factor), core/optimizer/param_library.py `get_active` (SQLite query + JSON decode every tick), core/signals/provenance.py `entry_allowed` (SQLite per signal), tests/integration/paper_loop.py (GAP-0075 per-tick sizing repeats)
- Description: cProfile of 5,000 busy-path ticks (params promoted for every regime, 120 s regime cycle, replay logger; real Dukascopy EUR/USD 2025-01-07): 16.0 s total — AGON.generate 10.9 s, of which `atr_series` 6.7 s (42%, 7,185 full-window recomputes; daily-bar ATR for TSMOM changes once per day); sqlite `execute` 2.8 s (18%, 13,230 calls: `get_active` 2.2 s every tick, `entry_allowed` 1.9 s per signal); Governor `allocate` 1.9 s (12%); NVMA classify 0.36 s (2%). 3,139 orders sized in 5,000 ticks (GAP-0075 behaviour; the harness dedups positions but the work is spent). At ~691 ticks/s unprofiled the ≈2.79 B ticks are ≈47 single-core days.
- Justification: behaviour-preserving caches with explicit invalidation would remove most of it: ATR once per COMPLETED bar per instrument; active params held in memory and refreshed only on stage/promote; provenance entry verdicts cached per (module, UTC day) and cleared on lifecycle change; plus the GAP-0075 position-awareness decision. Each needs equivalence tests (identical signals/orders on real ticks with and without the cache) and the dual audit. Then parallel folds on the multi-core server (owner steps in TODO).
- Built (final, 2026-09-15): (1) `AtrMemo` (core/signals/indicators.py), used by AGON (per instrument, plus a separate daily key) and the Governor's vol factor. It returns a cached ATR only when the window holds the very same frozen Bar objects in the same order, so it is exact by construction; both audits confirmed this (48,192 differential fuzz checks). (2) The params and provenance stores open in **WAL journal mode** (core/data/sqlite_wal.py), where a keyed SELECT measured ~5–20 µs instead of ~150–220 µs under the default rollback journal on Windows. Every read still hits the database, so a promotion or a freeze committed through ANY connection is visible on the very next call. `entry_allowed` is back to its original uncached code. (3) `ParamLibrary.get_active` reuses the parsed set only while the row it reads is identical (the set is a pure function of the row).
- Superseded first design (2026-09-14): in-memory row caches keyed on `total_changes`, under a single-writer precondition justified by a cross-connection check that "cost as much as the query". Both audits refuted it. F-I1 and F-E1: a second connection's promotion or freeze stayed invisible, reproduced. F-E2: the cost was an artifact of the rollback journal; in WAL a cache hit (30.7 µs) was slower than the query (20.6 µs). Triage, all FIXED by the redesign: F-I1/F-E1 (writes from other connections now visible), F-E2 (claim corrected; WAL), F-E3 (the unowned GAP-0091b obligation is gone), F-E4 (the loop test now freezes a strategy through a second connection mid-run), F-E5/F-I5 (invariant stated once in sqlite_wal.py and in `get_active`), F-I2 (transaction-aware: a rolled-back write is not remembered), F-I3 (a corrupt row fails only its own strategy — original code), F-I4 (provenance.py diff is two lines, no compressed code). Reports: archive/AUDIT_P12D15_INTERNAL.md, archive/AUDIT_P12D15_EXTERNAL.md; brief archive/AUDIT_BRIEF_P12D15.md.
- Measured (2026-09-15, real Dukascopy ticks, params promoted for every regime, 120 s regime cycle, replay logger; the validation run and the full test suite were sharing the CPU, so re-measure on a quiet machine): EUR/USD 2025-01-07, 5,000 ticks: **536 → 1,615 ticks/s** with the same 2,624 orders, take-rate, skip counters and event counts; EUR/USD + USD/JPY merged, 40,000 ticks: **639 → 1,821 ticks/s**, identical 20,391 orders. Remaining profile: NVMA classify, Governor allocate, EMA recomputation in `_trend`, and the GAP-0075 sizing repeats (2,624 sizings per 5,000 ticks).
- Proof: `test_atr_memo_equals_wilder_atr_through_warmup_growth_and_eviction`, `test_atr_memo_recomputes_when_any_bar_differs_even_with_same_ends`, `test_both_stores_open_in_wal_mode`, `test_get_active_reuses_the_parse_only_while_the_row_is_unchanged`, `test_a_promotion_through_another_connection_is_seen_on_the_next_call`, `test_a_freeze_through_another_connection_is_seen_on_the_next_call`, `test_a_rolled_back_write_is_not_remembered`, `test_composed_loop_is_identical_with_and_without_the_memos`; first-design tests replaced: former `test_get_active_is_served_from_memory_and_sees_each_promotion_at_once`, former `test_entry_allowed_cache_still_freezes_instantly`, former `test_composed_loop_is_identical_with_and_without_the_caches`
- Residual: GAP-0075 — per-tick sizing repeats (owner decision); a quiet-machine and 8-instrument re-measure plus the fold-parallel multi-core design stay on the TODO 16-core item; the triage redesign has not had its own audit pass (verify at the next phase-12 audit).
- Linked: [[GAP-P12D-12]], [[GAP-0075]], [[GAP-SP12E-03]]

## GAP-P12D-12: the real engine replays ~26 ticks/s and logs ~583 bytes/tick — a 14-year tick walk-forward is infeasible as wired (≈3.6 compute-years, ≈1.75 TB of JSONL)
- Severity: high · Likelihood: high
- Status: mitigated (2026-09-13 — owner "just do all the steps"; fixes (a)(b)(c) built and measured; the remaining throughput gap is owned by GAP-P12D-15)
- Area: core/regime/nvma.py `bollinger_width_percentile` / `hurst_exponent` / spread sigma (`statistics.pstdev`), tests/integration/paper_loop.py `on_state` (medium loop run per tick), core/data/jsonl_logging.py (flush per event), the not-yet-built evolve/replay driver (GAP-SP12E-03), master §10 / §11 / §13
- Description: benchmark on 20,000 real Dukascopy EUR_USD ticks through the REAL path (`build_paper_loop` → `on_state`): read+decode 179,000 ticks/s, `MarketStateFactory.build` 5,125/s, **engine `on_state` 26.3/s**, harness Decimal mark 141,000/s; JSONL **583 bytes/tick**. The dataset is ≈2.99 billion ticks (manifest: 0.246 ticks per compressed byte), so one tick replay ≈ 3.6 years of compute and ≈1.75 TB of log on this machine (i5-8200Y 2C/4T, 7.9 GB RAM; downloads were sharing the CPU). cProfile of 2,000 steady-state ticks: 99% in `NVMA.classify`; 82% in `statistics.pstdev` (exact `Fraction` arithmetic, ~142 calls per tick — `bollinger_width_percentile` recomputes a 20-point pstdev at every window position every tick: 91 s of 163 s; `hurst_exponent` 49 s); AGON + Governor + harness ≈ 0.8 ms/tick together. JSONL: `VETO_APPLIED` 239 B/tick, `DISCARD_VETOED_REGIME` 192 B/tick, `REGIME_SHIFT` 94 B/tick (379 shifts in 2,000 ticks — flapping because the test loop classifies every tick, while §10 puts NVMA in Loop 2 at 60–300 s, config `regime.cycle_seconds: 120`); each event flushes twice.
- Justification: nothing is wrong with the data or the verdicts — the replay is just unaffordable. Options for the owner (estimates, to be re-measured after each): (a) float `math.fsum` pstdev (measured 6× on 201 values, |Δ| ≈ 1e-16) + an O(window) rolling Bollinger width, with equivalence tests pinning the degenerate cases (a constant series must stay σ = 0 exactly — GAP-0076's ILLIQUID float-dust hazard), then the dual audit; (b) the replay driver runs NVMA at the §10 Loop-2 cadence (`cycle_seconds`), not per tick — spec-faithful, and removes the per-tick shift flapping; (c) replay-mode logging: per-gate counters (§10 C15 surfaces stay exact) plus sampled/aggregated events instead of one JSONL line per veto — a §11 question; (d) QIEA evolves on a numpy 1-minute-bar cache (numpy is §16-declared; ~42 M bars ≈ 2 GB raw), keeping ticks for the graded replay only; (e) compute: even at an estimated ~1,000 ticks/s after (a)+(b), the ≈2.6 B graded ticks are ≈30 single-core days — plan a multi-core machine (the VPS gate) for the full run. Storage is NOT the constraint: compressed bi5 is 4.3 B/tick (≈13 GB total) and decodes at 179,000 ticks/s; an indexed SQLite table measured 62.8 B/tick (≈188 GB) with no faster reads — no tick database.
- Measured after the fixes (same 20,000 real EUR/USD ticks, 2026-09-13): (a) float `pstdev` (`core/regime/fast_stats.py`) alone → 264 ticks/s (10×); with (b) the §10 Loop-2 regime cycle (`PaperLoop(regime_cycle_s=cycle_seconds)`) and (c) `ReplayEventLogger` → 3,090 ticks/s and 5.5 B/tick on the veto-only path, and **691 ticks/s at 20.6 B/tick on the busy path** (all regimes' params promoted, 13,621 sizings per 20,000 ticks) vs 195 ticks/s / 926 B/tick for the same busy path before (b)(c). NVMA is now ~2% of replay time. At ~691 ticks/s the ≈2.79 B ticks are still ≈47 single-core days — see GAP-P12D-15.
- Proof: `test_matches_statistics_pstdev_on_price_like_data`, `test_constant_series_is_exactly_zero_like_the_exact_version`, `test_result_does_not_depend_on_order`, `test_regime_indicators_give_the_same_answers_as_the_exact_original`, `test_regime_is_classified_once_per_cycle_and_reused_between`, `test_default_still_classifies_every_tick`, `test_replay_logger_counts_everything_and_samples_only_chatter`, `test_replay_logger_plugs_into_the_real_loop`
- Residual: GAP-P12D-15 — the next hotspots (ATR recomputed per tick, SQLite param/provenance lookups per tick, per-tick sizing repeats) and multi-core compute.
- Linked: [[GAP-P12D-15]], [[GAP-SP12E-03]], [[GAP-0067]], [[GAP-0075]], [[GAP-P12D-03]], core/regime/nvma.py, tests/integration/paper_loop.py

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
- Status: fixed (2026-09-15 — both pieces BUILT: the embargo is enforced on real fold data, and `passed` requires a Deflated Sharpe ≥ 0.95 over ≥ 2 recorded trials, owner-ratified in GAP-P12D-16)
- Area: OOS_VALIDATION.md vs walk_forward.py `generate_folds` / report.py
- Description: `generate_folds` sets `test_start = train_end` (zero embargo/purge — boundary leakage not removed); no Deflated Sharpe / trial-count anywhere in code (grader applies raw `annual_sharpe>1.5`). These are the defences against the SP12E-01 overfit risk; the runbook cited them as its ground truth (López de Prado) while shipping neither.
- Justification: dual-nature (read-path truth + faithful-method). Runbook corrected now; the build (embargo gap in generate_folds + deflated_sharpe/trial_count in ValidationReport) is a REQUIRED pre-grade item on the evolve-driver build, elevated from "enhancement" to "load-bearing".
- Built (2026-09-15): `generate_folds` takes a required `embargo`, so `test_start = train_end + embargo`. `Backtest.run` refuses any fold whose real last-train → first-test tick gap is shorter than the max hold (`require_embargo`). tests/backtest/deflated_sharpe.py implements Bailey & López de Prado (2014) Eq. (2), with raw kurtosis, √(T−1) and per-period Sharpe ratios, and reproduces the paper's own numerical example (SR0 0.1132, DSR 0.9004 at N=100 and 0.9505 at N=46). `Backtest.run(trial_sharpes=…)` fills `ValidationReport.trial_count` and `deflated_sharpe`, and adds a caveat when fewer than 2 trials are supplied. ACIS-09 → v1.4 (C-BT-11).
- Proof: `test_generate_folds_leaves_the_embargo_gap`, `test_harness_refuses_a_fold_shorter_than_the_max_hold`, `test_reproduces_the_papers_numerical_example`, `test_more_trials_deflate_more`, `test_no_selection_means_a_zero_threshold`, `test_moments_of_a_known_series`, `test_no_sharpe_means_nan`, `test_deflated_sharpe_below_095_cannot_pass`, `test_unrecorded_trials_cannot_pass`
- Residual: GAP-P12D-23 — the runner supplies the embargoed folds; GAP-P12D-25 — the trial set the gate deflates by.
- Linked: OOS_VALIDATION.md, walk_forward.py:43, report.py, TODO.md phase-12 item (2), [[GAP-SP12E-01]], [[GAP-P12D-16]]

## GAP-SP12E-05: delta-normal + √t VaR is Gaussian-blind to the fat tails the 3% cap implicitly bounds
- Severity: low · Likelihood: medium
- Status: accepted-risk (2026-07-21 — the spec does NOT rely on VaR for tail bounding; the §8.5 scenario book + gap law carry tails, and VaR is labelled delta-normal + not-yet-wired-in-loop (GAP-0091b))
- Area: core/risk/monitor.py `_var_pct`, guardrail `var_cap_pct 3.0`
- Description: per-position delta-normal `z·σ` with σ scaled √(horizon/cadence) assumes iid-normal; a 2015-SNB-class gap (>10σ Gaussian) is assigned ≈0 probability. Residual: the 3% cap's calibration to a Gaussian 1-day horizon is unverified vs real FX kurtosis, and its only empirical check (`var_breach_frequency`) is a bare rate, not a significance test (SP12E-04).
- Justification: accepted because tails are carried structurally (scenario book/gap law), not by VaR. Recorded as a declared VaR limitation; the go-live operational-referent audit must use the Kupiec LR test (not a bare rate) for live VaR-breach frequency. → SPEC_AUDIT.md.
- Linked: core/risk/monitor.py `_var_pct`, [[GAP-SP12E-04]], [[gap-0091b]], master §8.5

## GAP-SP12E-06: spx_correlation zips returns by POSITION, not date — a false-clear risk for the §14 SPX-corr gate (CONFIRMED)
- Severity: low · Likelihood: medium
- Status: fixed (2026-09-15 — the positional zip is gone: the SPX correlation now joins by date, proven on a US-holiday fixture)
- Area: tests/backtest/metrics.py `spx_correlation`
- Description: `spx_correlation` zips positionally with no date-join; FX (~260 sessions/yr, trades some US holidays) and SPX (~252) calendars differ, so an un-joined positional zip silently correlates mismatched dates → a meaningless near-zero value → a FALSE CLEAR of the §14 <0.25 diversification gate. The current call sites pass flat `[0.0]*n` fixtures so the defect is inert today; the REAL OOS driver must date-join.
- Justification: minimum fix APPLIED (precondition made explicit + load-bearing in the docstring). The date-join + fixture land with the evolve-driver (the component that builds the real SPX series).
- Fix (2026-09-15): the harness marks equity at every 17:00-New-York rollover it crosses (tests/backtest/rollover_marks.py; DST-correct; a weekend yields Friday's mark only). `spx_correlation(marks, spx_closes)` pairs consecutive SPX session dates (p, d) with equity marks on both, so a US holiday or an FX-only day spans the same interval in both series. The declared deviation is the one-hour gap between the 17:00 FX mark and the 16:00 SPX close. Fewer than 3 joined samples returns NaN, which FAILS the §14 gate; the old code returned 0.0, which PASSED it. `Backtest.run` takes `spx_closes` (date → close) instead of a positional list. ACIS-09 → v1.4 (C-BT-11).
- Proof: `test_spx_correlation_joins_by_date_across_a_us_holiday`, `test_too_little_overlap_is_nan_and_fails_the_gate`, `test_rollover_marks_follow_new_york_time_across_dst_and_weekends`
- Residual: GAP-P12D-23 — the runner loads the downloaded SPX closes into `Backtest.run(spx_closes=…)`.
- Linked: metrics.py `spx_correlation`, TODO.md phase-12 item (2), [[GAP-P12D-03]]

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

## GAP-C09-01: SPEC_CONSTITUTION v0.9 adoption debt — the comment-shape baseline
- Severity: low · Likelihood: certain
- Status: open (owner-directed adoption 2026-09-16; closes when the baseline reaches zero)
- Area: repo-wide; `code-shape.baseline.json`, `scripts/governance_gate.py`; SPEC_CONSTITUTION A12/A14/A16
- Description: v0.9 discharged here before the pin moved from v0.5 (A14 requires that order — an undischarged pin bump reads as adoption and stops anyone looking). What changes for ACIS: **A12** adds a *comment-shape* check alongside the existing size ratchet — a comment cites an ID rather than quoting a rule (a verbatim twelve-word run shared with `ACIS_SPEC.md` is a finding), the mental-model header is one screen (<=20 lines), a later comment block over five lines is a finding, and no comment narrates history; today's 25 findings over 19 file/rule pairs are frozen in `code-shape.baseline.json`, the gate fails only on new ones, and a file a phase edits forfeits its allowance. SIZE stays with `tests/unit/test_module_budget.py`, which already ratchets it under GAP-P12M-01 — two mechanisms policing one rule would be the duplication A12 forbids. **A14** `python scripts/governance_gate.py --session` fails on a stale pin or a CLAUDE.md reference that no longer resolves. **A16** `falsify.cases.json` carries four cases over `core/risk/guardrails.py` — the taper asserted from both sides of its start and halt boundaries, the equity breaker flattening and halting, and the breaker being one-shot per armed cycle rather than per process — all four seen red for their stated reason on 2026-09-16, with every restore sha256-verified. **A3** the terminal milestone (the live-readiness gate) adds a practicality-and-code-efficiency lens run by Fable 5; if Fable is unavailable the lens still runs on the next superior tier and the report names what actually ran. This does not disturb the 2026-09-15 directive that ordinary audits run on Opus 5. **A13** per-phase cleanup is now audited rather than promised, and a spec's spent narrative retires under an "implemented is not spent" guard — the adoption-gate block still at the top of `CLAUDE.md` is a candidate once its step 2 is done. Minor: A1 ledgers an ambiguous requirement and proceeds, A6 gives wording-only corrections no ID, A9 names a subordinate agent's report as untrusted input, A15 requires a proof pointer to resolve to the *right* referent.
- Justification: the baseline is frozen rather than fixed because a gate red on the day it lands gets disabled, which is worse than none (A16), and the burn-down follows the work rather than a quota. `scripts/governance_gate.py` composes the family checks in one command because ACIS has no npm; the checks themselves live once in `../specs_constitution/checks/` rather than being copied here (A14 — forks drift).
- Residual: this entry owns the 19 frozen file/rule pairs. A15's closure check was already built (`scripts/ledger_check.py`, 166 entries green).
- **2026-09-25: the session gate is RED on main.** BUILDER-3 found it (F3), and the lead verified it with `python scripts/governance_gate.py --session`, which exits 1. The comment-shape ratchet flags NEW violations in core/optimizer/costs.py (HEADER 1, BLOCK 1) and scripts/cost_stress_ladder.py (HEADER 1, BLOCK 1), none allowed by the baseline. Both come from the 2026-09-17 cost-stress-ladder work ([[GAP-P12D-46]]), not from any agent branch. The gate also reports that core/data/feeds.py burned down one HISTORY violation, so the baseline can be lowered. The fix is comment-only; costs.py is in the mutation-gate scope, so no code line changes.
- Linked: TODO.md, [[GAP-P12M-01]], [[GAP-P12M-02]], ../specs_constitution/SPEC_CONSTITUTION.md A12/A14/A16
