# R1.6 audit: the external-referent lens (constitution A3, lens 2), 2026-10-02

- **Auditor:** Claude Opus 5.5, fresh context, launched by the lead on the owner's go ("Launch both now (Recommended)"). **I am a finder, not a clearer (A5).** No finding below is binding until the lead triages it and it survives refutation (A6). A clean area here is not a sign-off.
- **Brief:** `AUDIT_BRIEF_R1_6_2026-10-02.md` (pinned at `9076742`). **Audited commit:** `de96a75`. Every file was read with `git show de96a75:<path>`, and every probe ran on acis-compute-1 in this lens's own checkout of `de96a75`, through `remote_audit_r16.sh external`.
- **Probes:** in the session scratchpad, `…/scratchpad/audit_r16/external/probes/`: `rates_window_vs_cache.py`, `aud_rate_staleness.py` (with `bis_cbpol_2026-10-02.csv`, the BIS file as fetched today), `live_rates_fresh.py`, `trendbar_range.py` and `bid_vs_mid_slowvol.py`. They are synthetic, except two:
  - `bid_vs_mid_slowvol.py` reads spreads and volatility only. It covers the explored FX, 2012–2023, the development tier.
  - `live_rates_fresh.py` reads rates only.
  - **No forecast, return, P&L or Sharpe was computed on real candles** (`REAL_LOOKS_OPEN` respected).
- **Web budget:** 8 of the 20 WebSearch calls I was allowed, plus WebFetch and direct `curl` reads of primary files. Every source is listed at the end with its URL, the date it was read (all 2026-10-02) and a grade.
- **Not re-run by this lens:** the full suite and the lead's other internal claims (1330 passed; B0(d); the 300-line budget; `ledger_check.py`). Those belong to the internal lens.

## Executive summary

On Carver, the TREND D1 sizing and estimators faithfully reproduce pysystemtrade at `a62269d2`. I checked them line by line against Carver's own files:
- `mixed_vol_calc` with `span=` and `defaults.yaml`'s 10 years and 0.3;
- the `ewmac` normaliser;
- the chapter-15 scalars 3.75/2.65/1.87;
- `buffer_method: forecast` at 0.10, traded to the edge;
- the vol scalar × weight × IDM;
- ROOT_BDAYS_INYEAR = 16;
- `dm_max` 2.5.

Wilder's ATR is Wilder's. The cTrader trendbar decoding matches Spotware's proto and the forum's worked example.

The outside world nonetheless breaks R1.6 in three places. Two are certain, and both are deterministic in the shipped code:

1. **R16E-01 (high, certain): the target path stops for good about 101 days after its first seed.**
   - `download_macro.py --live` keeps a *rolling* 1,200-day rate window.
   - The bar cache is never trimmed, and `decide()` needs a rate for *every* cached decision day.
   - With a seed on 2026-10-16, every instrument returns `no_target:stale_rates` from **2027-01-25** onward. Positions are frozen, not closed.
2. **R16E-02 (medium, certain on today's data): the AUD rate source cannot meet R6-1's 10-day freshness rule.**
   - AUD comes from BIS WS_CBPOL, which BIS releases weekly ("around mid-week"). The 2026-10-01 release carried AU only through 2026-09-24.
   - AUD_USD, AUD_JPY and EUR_AUD therefore get `no_target:stale_rates` on about 3 of every 5 decision days. Reproduced from **2026-10-05** with the real BIS file and the shipped `decide()`.
3. **R16E-03 (medium; likelihood unknown until the first seeding): the H1 history walk was built on a false premise.**
   - The walk asks for 365-day windows and assumes the per-request range limit is "undocumented".
   - Spotware *documented* it at 35 weeks for H1 until proto release 88 (2023-09-26). Spotware's error enum still names a "too large" period.
   - If the server refuses an over-long range, the seed costs about 8 requests per instrument, not ACIS-13's "~4".
   - If it truncates silently, which is the behaviour on record on Spotware's forum, the seed gets three ~120-day holes. The holes vanish from the decision calendar without any log, and the cache keeps them forever.

Three low findings follow:
- **R16E-04:** the 10 × ATR stop is *not* in `trend_d1_v1`'s declared deviations, although ACIS-05 §6.4 says it is. The warm-up mask, the bid basis and the practice cap are also undeclared.
- **R16E-05:** the carry calendar's tom-next simplifications are undeclared: USD/CAD settles T+1, holiday rolls are ignored, and ACT/360 rates are divided by 365.
- **R16E-06:** GAP-P12D-141 (3)'s "a few percent" is measured here at up to −13% / +11% on the normaliser.

## Findings

### R16E-01: the live rate files cover a rolling 1,200 days while the cache grows, so every target stops about 101 days after the first seed
- **Severity:** high · **Likelihood:** certain (deterministic; this is an internal defect, found while checking the rate sources)
- **What the code does, at `de96a75`:**
  - `scripts/download_macro.py:251`: `--live` fetches `series(today - timedelta(days=1200), today)`, and the timer (`deploy/systemd/acis-macro.service`) rewrites `data/macro_live` from it every day.
  - `core/runtime/history_store.py:8`: the cache is "append-mostly and never trimmed".
  - `core/runtime/target_loop.py:132-134`: the decision builds `decision_days` from the *first cached bar*.
  - `core/runtime/target_decision.py:98-101`: `accruals = [accrual(...) for d in s.days]` over every cached day, and a `StaleRateError` becomes `no_target:stale_rates`.
  - `core/data/rates.py:61-62`: a day before a series starts raises `StaleRateError`.
  - So once `today − 1200 d` passes the cache's first day (seed − 1100 d), *every* instrument's decision fails. That happens 101 days after the seed.
- **Reproduction:** `probes/rates_window_vs_cache.py`, on the server. It feeds the shipped `decide()` with a rate table shaped exactly like `--live`'s window on each day:
  ```
  seed 2026-10-16, cache starts 2023-10-12; the rate files hold [today - 1200 d, today - 1 d]
  2026-10-16  (+0 days after the seed)  decide -> target
  2027-01-25  (+101 days after the seed)  decide -> no_target:stale_rates
  ... and on 2027-06-30: no_target:stale_rates
  ```
- **Consequence:**
  - R6-1 keeps positions on "no target", so the whole universe freezes, holding whatever it held, with only the disaster stops acting.
  - The log reason (`stale_rates`) points the operator at the rate download, which is succeeding.
  - B0(d) on a lab tape cannot see this: it needs a deployment older than 100 days.
- **Proposed fix:**
  - Give `--live` a fixed start that predates any cache, for example the archive's 2011-01-01, or the cache's first decision day minus a margin. Or merge new rows into the existing file instead of replacing it.
  - Make `decide()` log a distinct reason (`rates_window_short`) when a rate series starts after the series' first day.
  - Add a regression test: a decision a year after the seed, with a `--live`-shaped table, still makes a target.

### R16E-02: AUD's rate source is released weekly with a 7-day lag, so R6-1's 10-day rule stops the three AUD pairs most weekdays
- **Severity:** medium · **Likelihood:** certain on the observed cadence (each week while the AU lag stays at 4 days or more)
- **The source (BIS, read 2026-10-02, grade a):** "How often and when are the policy rate series updated? **Daily data are released around mid-week.**" … "Next release date 8 October 2026 · Last release date 1 October 2026" (https://www.bis.org/statistics/cbpol.htm).
  - The BIS API, queried today (`stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.AU+…`), shows each area's last observation: **AU 2026-09-24**, CA/GB/US 09-28, CH/JP/XM 09-29.
- **What the code and spec do:**
  - `core/data/rates.py:33`: AUD = `("bis_policy", "AU")`.
  - ACIS-04 v1.6 §4b (line 97) and R6-1: "A rate table more than 10 days stale … gives that instrument no forecast".
  - `config/system_config.yaml:170`: `rate_max_stale_days: 10`.
  - `scripts/download_macro.py:217-231, 250`: `--live` rejects the *whole* `bis_policy` file when *any* of its 7 areas ends before today − 10, so a lagging area the engine never reads also blocks AU's update.
- **Reproduction:**
  - `probes/aud_rate_staleness.py` uses the real BIS file and the shipped `parse_bis`/`validate`/`RateTable`/`decide`. AUD is fresh through 10-02. From **2026-10-05**, `rate('AUD')` → STALE, `validate` → "AU: ends 2026-09-24, expected by 2026-09-25", and `decide('AUD_USD')` → `no_target:stale_rates`.
  - `probes/live_rates_fresh.py` ran on the files that `download_macro.py --live` wrote on the Linux server today (7/7 valid). AUD is STALE from 10-05.
  - With a weekly release and an AU lag of L days, the staleness is L+4 on Mondays and L+6 on Wednesdays. At L = 7, Monday through Wednesday are stale every week, and Thursday too if BIS releases after the 12:00 UTC timer.
- **Consequence:**
  - AUD_USD, AUD_JPY and EUR_AUD act on about 1–2 decisions a week. RSIM, which has complete rates, acts on all 5.
  - This is a systematic, undeclared B0(d) divergence in 3 of the 13 instruments.
- **Secondary (a near miss, not yet a defect):** CHF comes from the SNB cube `snbgwdzid`.
  - Today's file says `"PublishingDate";"2026-09-28 10:00"`, with data through 2026-09-25 and nothing newer on 10-02. The cube is published weekly, on Monday, carrying the previous Friday.
  - Routine staleness reaches 7 days, and 10 when a Swiss holiday Monday moves the publication to Tuesday. That leaves one day of margin under R6-1.
- **Proposed fix (an owner ruling, since R6-1 is ratified):**
  - (a) A freshness rule that knows the source's kind. A central-bank policy *target* is exact between the bank's scheduled meetings, so it stays valid until the next scheduled RBA decision. Keep the 10 days for traded overnight rates.
  - (b) A per-source stale limit sized to its publication cadence, e.g. 21 days for weekly sources.
  - (c) A daily AUD source. The RBA's F1.1 CSV answered 403 to scripted fetches from both the laptop and the server today, so this is not a drop-in.
  - In any case, validate only the BIS area(s) the engine reads.

### R16E-03: the H1 walk exceeds Spotware's documented 35-week range, and on a silent truncation it seeds holes it never repairs
- **Severity:** medium · **Likelihood:** unknown. It depends on today's server behaviour, which the first seeding answers; a design-premise defect either way.
- **The sources:**
  - Spotware `openapi-proto-messages` at **`7548df70ce229c8b0eaaf2ae7a93c8a631d12481`** ("88 Release", 2023-09-26), `OpenApiMessages.proto` line 523, `ProtoOAGetTrendbarsReq.fromTimestamp`: "Validation: toTimestamp - fromTimestamp <= X, where X depends on series period: M1, M2, M3, M4, M5: 3024000000 (5 weeks); **M10, M15, M30, H1: 21168000000 (35 weeks)**, H4, H12, D1: 31622400000 (1 year); W1, MN1: 158112000000 (5 years)." (grade a)
  - Release 89 (**`36d5001401fc0cf5ae19d22582458d273e182b84`**, 2024-01-29) deleted that sentence, made `fromTimestamp` optional and added `hasMore` to `ProtoOAGetTrendbarsRes` (grade a).
  - At the pinned **`3fd8bddf…`**, `OpenApiModelMessages.proto:662` still reads "`INCORRECT_BOUNDARIES = 35; // When requested period (from,to) is too large or invalid values are set to from/to.`" (grade a).
  - Spotware forum 24731 (14 Sep 2020), a user: "If (toTimestamp - fromTimestamp) is more then the mentioned <2 weeks it just strips everything 'before' the latest possible timestamp … I do not receive any error response in case of 'wrong' timestamp ranges!" Spotware (P. Charalampous): "There is a hard limit of 14000 bars … you will need to detect the missing timespan and request again." (https://community.ctrader.com/forum/connect-api-support/24731/, grade b/c)
- **What the code and spec do:**
  - `core/data/ctrader/history.py:13` says the range limit is "(undocumented)".
  - `:31` sets `WINDOW = 365 days`, 49% over the last documented H1 limit.
  - `:73-77` halves only on a `VenueError`.
  - `:84`: without `hasMore`, `hi = lo`. A response that silently lacks its older part is taken as complete.
  - `core/runtime/target_loop.py:164` refreshes only from `last_end`, so an interior hole is never back-filled.
  - `core/signals/daily.py:48-60`: a span where *no* instrument has hours is not a decision day. All 13 instruments get the same truncation, so the hole disappears instead of showing as stale days.
  - The ledger and the spec repeat the premise: GAP-P12D-141 (2) says "undocumented", and ACIS-13 §6.5 (line 315) says "a one-time ~4 requests per instrument".
- **Reproduction:** `probes/trendbar_range.py`. A `FakeVenue` subclass enforces the 35-week H1 limit both ways, and the shipped `hourly_bars` walks a 1,100-day synthetic FX history with the default `WINDOW`:
  ```
  refuse : 8 requests (1 refused, halved to 182.5 d); 18707/18707 bars; no gaps
  silent : 4 requests; 12602/18707 bars; holes 2023-09-29→2024-01-28, 2024-09-27→2025-01-27,
           2025-09-29→2026-01-27 (~120 d each); decision days 531 vs 786;
           largest one-day move 5.60% vs 1.98% (median 0.40%); D1 forecast −2.856 vs −3.320 (−14%); pct_vol +3%
  ```
  No event or warning is logged in the silent case.
- **Proposed fix:**
  - `WINDOW` ≤ 35 weeks (e.g. 240 days): 5 requests per 1,100-day seed and no refusal.
  - Judge a response's coverage at **both** ends, independent of `hasMore`, whose chunk order Spotware leaves undocumented. If the earliest bar is more than ~3 days after `lo`, or the latest more than ~3 days before `hi`, inside open sessions, keep walking that part.
  - After the seed, check bars per week and refuse to decide (with a reason) on a history with an interior hole.
  - Correct the "(undocumented)" claim, GAP-P12D-141 (2) and ACIS-13 §6.5's seed count.
  - Add a fake-venue test for silent truncation.

### R16E-04: `trend_d1_v1`'s declared deviations omit the disaster stop (which ACIS-05 says is declared there), the warm-up mask, the bid basis and the practice cap
- **Severity:** low · **Likelihood:** certain
- **What the spec and code say:**
  - `specs/ACIS-05-CAPITAL_GOVERNOR.md:117` (§6.4): "a broker-side **disaster stop** at `10 x daily ATR` … a declared deviation in the TREND provenance records, since Carver uses none".
  - `core/governor/target_gate.py:13-14`: "Carver uses neither; the stop is a declared deviation."
  - But `core/signals/families.py:20-57` (`_SHARED` + `trend_d1_v1`) contains no stop at all (`grep -i stop` finds nothing). Compare `core/signals/canonical.py:102`, where TSMOM's stop *is* declared.
- **Other departures from Carver's actual method that are not declared:**
  1. The 260-decision warm-up mask (`core/signals/forecast.py:31`, `rsim_real.masked`). Carver's code forecasts once `min_periods` allows: `ewmac` `min_periods=1`, vol `min_periods=10` (pysystemtrade `a62269d2`, `sysquant/estimators/vol.py:184-190`).
  2. In the engine, the decision close is the venue's **bid** (`history.py:10`); Carver's prices are settlement prices.
  3. The paper/practice one-lot cap (master §5 D-a). It makes the traded book a capped sign book, not Carver's continuous position.
  - Item 3 may be viewed as an execution constraint rather than part of the rule's method, but the declared-deviations law asks for every departure.
- **Proposed fix:** add the four to `trend_d1_v1.declared_deviations`. The stop also belongs on the two members, or in `_SHARED`. Alternatively, correct ACIS-05 §6.4's claim.

### R16E-05: the excess-return price's tom-next calendar departs from the market's, undeclared
- **Severity:** low · **Likelihood:** certain
- **Impact:** immaterial to D1 (the carry is about 1e-4 a day, and its timing moves by a day or two). RSIM shares it, so there is no parity effect.
- **The sources:**
  - "The settlement date for USD/CAD is one business day later than the transaction date or T+1" (CIRO guidance, via search snippet: https://www.ciro.ca/news-room/publications/regular-settlement-date-be-used-certain-foreign-exchange-hedge-trades-0; the page answered 403 to direct reads; grade b at snippet level).
  - "For USDCAD, with its T+1 settlement date, the 3-day swap occurs on Thursday" (https://fxnx.com/en/blog/triple-swap-wednesday-which-symbols-charge-3x-when, grade c).
  - Money-market day counts are a standard fact, not separately sourced here: USD (EFFR), EUR (€STR/DFR) and CHF (SARON) are ACT/360.
- **What the code does:**
  - `core/data/rates.py:81-94`: `tom_next` charges the **Wednesday** roll 3 days for every FX pair, USD_CAD included.
  - `:112`: every rate is divided by 365.
  - A holiday on either currency's value date adds no days.
  - None of this is declared. The docstring says "tom_next (spot FX, T+2)", but USD_CAD is T+1.
- **Proposed fix:** declare it in `rates.py` and in the provenance `_SHARED` line on the excess-return price. Optionally, give USD_CAD Thursday.

### R16E-06: GAP-P12D-141 (3)'s "a few percent" understates the short-history normaliser difference at the tails
- **Severity:** low · **Likelihood:** certain
- **Measurement (P&L-blind):** `probes/bid_vs_mid_slowvol.py` uses Dukascopy mid decision closes, 2012–2023, the 13 FX pairs. At each year end 2015–2023 it compares Carver's `mixed_vol` on the last 786 decision days (the engine's seed) with the whole history.
  - Median ratio 0.98–1.01.
  - Range **0.869 (CHF_JPY) to 1.109 (EUR_CHF)**.
  - The forecast scales inversely, so it differs by up to about 13% at the tails. Under the one-lot cap this moves the dead zone and the band edges.
- **Proposed fix:** restate (3) with the measured range. Or seed the slow component from a longer history: the archive's mid closes are not the venue's, but the slow vol is a level, not a price.

## Honest negatives (checked against the referent; no defect found)
- **Carver's estimator.** `core/signals/ewm.py` `mixed_vol` matches `sysquant/estimators/vol.py:167-181` at `a62269d2`:
  - `long_vol = vol.ewm(span=slow_vol_days).mean()`, span not com;
  - `defaults.yaml:112-120`: `slow_vol_years: 10`, `proportion_of_slow_vol: 0.3`, `days 35`, `min_periods 10`, no backfill;
  - `BUSINESS_DAYS_IN_YEAR = 256.0`.
  - The repo's `tests/reference/carver/generate.py` copy matches the source.
- **Carver's rule and scalars.** `ewmac`'s data inputs are `rawdata.get_daily_prices` + `rawdata.daily_returns_volatility`, with scalars 3.75/2.65/1.87 and cap 20 (`futures_chapter15/futuresconfig.yaml:37-71`). The chapter-15 weights 0.21/0.08/0.21 + carry 0.50 and FDM 1.31 are departures ACIS *does* declare.
- **Carver's sizing.** `banded_target`'s average position equals pysystemtrade's:
  - `vol_scalar = (capital × %target/100)/ROOT_BDAYS_INYEAR ÷ (price × pct_vol × fx)`, × weight × IDM (`systems/positionsizing.py:199-243, 480-492`; `rawdata.py:243-270`: % vol = price-unit vol ÷ the current price);
  - the buffer = `abs(vol_scalar × weight × idm) × buffer_size` (`systems/buffering.py:146-173`), traded to the edge (`account_buffering_subsystem.py:167-215`);
  - `buffer_size 0.10`, `buffer_trade_to_edge: True`, `dm_max: 2.5`, `floor_at_zero: True` (`defaults.yaml`).
  - The IDM prior: sqrt(13/(1+12·0.4)) = 1.497, Carver's formula with equal weights.
  - Two departures, each declared or harmless: Carver rounds the band's edges to the nearest contract where ACIS rounds toward zero (declared); and Carver keeps the last position on a NaN forecast where RSIM goes flat, which cannot bite because NaN occurs only during the masked warm-up.
- **Wilder's ATR.** `core/optimizer/fitness.py:61-75`: the true range with the prior close, an SMA seed over the first n, then (n−1)/n smoothing, on daily NY-close bars. That is Wilder (1978). `atr_period: 14`.
- **cTrader trendbars.** The decoding is right:
  - prices are 1/100,000 of a unit and open/high/close are low + delta (proto `ProtoOATrendbar`; the forum 42209 example: NAS100 `low 1427670000` = 14,276.70);
  - `utcTimestampInMinutes` is "the timestamp of the open tick", floored to the hour (correct);
  - bars are BID-based (forum 41268, 2023: "It is not possible to get trendbars based on ask prices"), as declared;
  - the 14,000-bar cap holds (forum 24731);
  - truncation keeps the newest bars (`count`: "Limit number of trend bars in response back from toTimestamp"; forum 42209: `count 10` returned the latest 10);
  - history pacing is 2/s, under the documented 5/s.
- **Bid vs mid (GAP-P12D-141 (1)).** On Dukascopy, the decision-hour close's half-spread is a median 0.6–2.8 bps (p95 2.8–7.0) against a daily sd of 46–73 bps. The bid basis changes the variance of daily changes by −0.4% to +0.9%. The declared departure is small. Pepperstone's own rollover spreads are not measured.
- **Pepperstone.**
  - The cTrader demo expires only after 90 days without a login or trade, already tracked (ACIS-13 F-43). Source: https://pepperstone.com/en-af/help-and-support/opening-an-account/how-long-do-demo-accounts-last/, "cTrader demo accounts will not expire if they are logged into at least once every 90 days", grade a.
  - EURUSD/USDJPY `minVolume` is 1,000 units (0.01 lot) on the demo (OPERATIONS_LEDGER OQ-17).
  - FX trades 00:01–23:59 server time (GMT+3/+2), i.e. 17:01–16:59 New York, and closes 5 minutes early on Fridays (https://pepperstone.com/en/trading/trading-hours/, grade a). So the 16:00 NY H1 bar is complete when the 17:02 decision fetches it, and the 08:00 NY slot is inside the session.
- **G-5 caps on the $100k account.** At most 13 one-lot FX positions is at most about $17k of USD delta, below the 90% × 30% × $100k = $27k currency headroom and the $18k cluster headroom. They cannot bind or order-bias the book there. On the $10k account they do (GAP-P12D-142, declared).
- **SNB TLS on Linux.** `download_macro.py --live` ran on the Debian server today (curl 7.88/OpenSSL 3.0) and wrote 7/7 valid series, `chf_saron` included.

## What I could not verify
- **Today's server behaviour for an over-range H1 request:** INCORRECT_BOUNDARIES, silent truncation, or no limit since release 89. This decides R16E-03's likelihood. Answer it at the first seeding by comparing `TRENDBARS_FETCHED.bars` with the expected ~6,240 a year.
- **`registrationTimestamp`.** `ProtoOATrader.registrationTimestamp` (proto `3fd8bdd`, `OpenApiModelMessages.proto:276`): "Should be used as minimal date in historical data requests." If the trendbar service honours it, a **new** $100k demo account (GAP-P12D-142's owner step) would get no H1 history before its registration, so the family would warm up for ~260 decisions (about a year) before any target. I believe it applies to deal and cash-flow history, not symbol bars, but did not verify it. Include a 3-year H1 fetch in the pre-cutover read-only probe (TODO START HERE item 4).
- Pepperstone's H1 history depth and its rollover spreads; the 11 newly enabled pairs' contract values (checked at attach).
- Whether Pepperstone lets a cTrader demo be reset or topped up to $100,000. A search summary of Pepperstone's demo page says virtual funds can be topped up in cTrader; the page was not readable here. A top-up arrives as a balance change, so the internal lens should check how a deposit reads to the equity breaker.
- Carver's *Leveraged Trading* text on the minimum-exposure problem. There was no primary access; ACIS attributes its toward-zero lot rule to its own master C8, not to Carver, so no misattribution was found.
- A primary source for USD/CAD T+1: the CME/EBS value-date calendar and the CIRO page both refused scripted reads.
- Whether the 16:00 NY H1 bar is final at 17:02 (`settle_s: 120`) on Pepperstone's trendbar service.

## Residual risk
- **R16E-01 is a time bomb with a date.** A cutover seed on 2026-10-15..17 stalls every target on about 2027-01-24..26. Nothing in the shipped tests or in B0(d) runs long enough to see it.
- **R16E-02 starts the first Monday after the cutover**, so the forward record's AUD pairs diverge from RSIM from day 1.
- **R16E-03 is invisible by construction if the server truncates silently.** Only a coverage check, or a human comparing bar counts, would see it.
- **Shared-premise seam:** the AUD source, the 10-day rule and the rolling `--live` window were each reasonable alone. Only the world's cadences (BIS weekly; caches outliving 1,200 days) expose the conflict. The operational-referent pass should read `TARGET_DECIDED.reason` counts per instrument from the first week.

## Sources (all read 2026-10-02)
| # | Source | Grade |
|---|---|---|
| S1 | pysystemtrade `a62269d27707806ba61f516791b71a9cd14cf268`: `sysquant/estimators/vol.py`, `sysdata/config/defaults.yaml`, `systems/positionsizing.py`, `systems/portfolio.py`, `systems/rawdata.py`, `systems/buffering.py`, `systems/accounts/account_buffering_subsystem.py`, `systems/provided/futures_chapter15/futuresconfig.yaml`, `syscore/dateutils.py` (raw.githubusercontent.com/robcarver17/pysystemtrade/<commit>/…) | a |
| S2 | Spotware openapi-proto-messages `3fd8bddf…` (pinned), `7548df70…` (release 88), `36d50014…` (release 89): `OpenApiMessages.proto`, `OpenApiModelMessages.proto` (github.com/spotware/openapi-proto-messages) | a |
| S3 | https://help.ctrader.com/open-api/messages/ (ProtoOAGetTrendbarsReq/Res) | a |
| S4 | https://community.ctrader.com/forum/connect-api-support/24731/ (14,000-bar cap; silent stripping, 2020) | b/c |
| S5 | https://community.ctrader.com/forum/connect-api-support/41268 (bid-only trendbars, 2023) | c |
| S6 | https://community.ctrader.com/forum/connect-api-support/42209/ (worked example: scaling, `count`) | c |
| S7 | https://www.bis.org/statistics/cbpol.htm (release cadence; next/last release dates) | a |
| S8 | https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.AU+US+XM+JP+GB+CH+CA?startPeriod=2026-08-15&format=csv (last observation per area) | a |
| S9 | https://data.snb.ch/api/cube/snbgwdzid/data/csv/en (PublishingDate 2026-09-28, data through 09-25) | a |
| S10 | https://pepperstone.com/en-af/help-and-support/opening-an-account/how-long-do-demo-accounts-last/ | a |
| S11 | https://pepperstone.com/en/trading/trading-hours/ | a |
| S12 | CIRO, USD/CAD T+1 (search snippet; page 403) https://www.ciro.ca/news-room/publications/regular-settlement-date-be-used-certain-foreign-exchange-hedge-trades-0 | b (snippet) |
| S13 | https://fxnx.com/en/blog/triple-swap-wednesday-which-symbols-charge-3x-when | c |
