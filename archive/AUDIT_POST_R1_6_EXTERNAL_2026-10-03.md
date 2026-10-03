# AUDIT — post-R1.6 changes (de96a75 → f0d9524), EXTERNAL-REFERENT lens (A3 lens 2), 2026-10-03

> **How this audit ran.** One agent in fresh context on Opus (claude-opus-5-5), under the pinned brief
> `archive/AUDIT_BRIEF_POST_R1_6_2026-10-03.md`. I am a finder, not a clearer: a clean item here is not a sign-off.
> No subagents. The repo was read at `f0d9524` (`git show` / `git diff de96a75 f0d9524`). This file is my only repo write.
> Every run went to the Google compute server through `remote_audit_p16.sh external`. The probes are in the session
> scratchpad, `audit_p16/external/probes/`: `alpha_false_alarm.py`, `alpha_alt.py`, `rates_cadence.py`, `macro_slot.py`.
> WebSearch calls: 5 of the 15 allowed. Everything after that used WebFetch or a direct fetch. All external sources
> below were fetched on 2026-10-03.

## Executive summary

There are four findings: one medium, two low and one latent low. None of them reaches a guardrail VALUE, the equity floor or the HALT semantics.

- **PR16E-01 (medium): the alpha-decay test does not measure decay.** It flags noise. I ran it on a process that never
  decays, using the shipped values and a per-trade mean/σ of 0.05–0.3 (GATES puts this book near 0.16). The throttle
  arms within the first 100 trades after its 100-trade warm-up in 75–91% of paths, and within 300 trades in 86–99%.
  After a human resume, the fresh-evidence window falsely re-arms it within 30–49 trades in 25–53% of resumes.
  GAP-P12D-145's fix therefore turns a permanent lock-out into a recurring one. The external evidence agrees:
  Carver (2015) calls an equity-curve filter on a trend follower "an unmitigated disaster", and Lo (2002) puts the
  sampling error of a 30–50-trade mean/σ at 0.14–0.19, which is larger than the effect being tested. The test also
  needs 100 closed trades in one process lifetime, because the history is in memory. At GATES's ~25 closes a year
  that is ~4 years without a restart, so on the demo the guard is mostly dormant, and noise once it wakes.
- **PR16E-02 (low): 21 days is not enough at BIS's year-end gap.** BIS's own calendar has a 16-day gap between the
  2025-12-23 and 2026-01-08 releases. With the observed 7-day publication lag, AUD reaches 22 days on 2026-01-07,
  which gives `no_target:stale_rates` on AUD_USD, AUD_JPY and EUR_AUD. The 2026/27 outcome depends on BIS's 2027
  calendar, which is not yet published. The RBA holds no January meeting, so a stale AUD rate in that window cannot
  be wrong.
- **PR16E-03 (low): the `--live` downloader still requires every series to be at most 10 days old.** On BIS's cadence
  it rejects `bis_policy` on 3 of every 5 weekdays (Mon–Wed), so `acis-macro.service` exits 1 on ~60% of weekdays.
  A fresh host whose first run falls on a Mon–Wed has no AUD file until Thursday. The deploy comments still say
  "1,200 days" and "10 days".
- **PR16E-04 (low, latent): the 08:00 New York slot collides with the release clock.** The FX and metals slot is
  08:00 New York, MACRO_EVENT's lookahead is an inclusive 30 minutes, and v2.30 keeps MACRO_EVENT as a gate on
  target entries. Once a live calendar is wired (GAP-P12D-03), every 08:30 ET US CPI, NFP or GDP release refuses
  the target entry on 6 of 13 pairs. Every 14:15 CET ECB decision (08:15 New York) refuses it on 5 of 13. The
  refusal still holds at slot + 299 s, and the slot is not retried. Today this is inert: `wiring.py:168` passes
  `macro_imminent=False`.

**What held up:** the weekly classification of BIS and the SNB cube (21 days is right for normal weeks); 10 days for the daily sources;
the cTrader DEPOSIT_WITHDRAW handling; the direction of the GAP-P12D-147 split (it matches Carver's own production practice);
`ledger_check.py` (286 entries, 0 violations); and the lens-relevant tests (29 passed at f0d9524; the new 146/147 tests fail on de96a75).

---

## Findings

### PR16E-01 — The alpha-decay throttle mostly detects noise. GAP-P12D-145's fresh-evidence re-arm repeats that noise after every resume.
- **Severity: medium. Likelihood:** near zero on the demo's horizon (it needs 100 closed trades in one process lifetime).
  Near-certain within ~200–300 closed trades once it can evaluate.
- **Where (f0d9524):** `core/risk/alpha_decay.py:105-147` (`evaluate`: recent `trades[-50:]`, baseline `trades[-200:-50]`
  ≥ 50, flag `s_recent < 0.5·s_baseline` at :131; fresh window at :109); `core/risk/alpha_throttle.py`;
  `core/risk/monitor.py:63` (`self._trades` in memory, so a restart empties it), :302; config `alpha_decay_sharpe_mult: 0.5`
  (guardrail_limits.yaml), `alpha_decay_recent_window 50`, `min_trades 30`, `baseline_min_trades 50`, `recovery 20 @ 0.8`.
  Spec: master §8; ACIS-07 v1.4 §7.
- **Reproduction (server, `probes/alpha_false_alarm.py`).** Part A checks a vectorised replica against the REAL
  `AlphaDecayDetector` at f0d9524: identical on 40/40 paths. Part B uses iid per-trade returns with a constant true
  mean/σ S, so nothing decays. It reports the probability that the throttle has armed within K closed trades:

  | S (per trade) | K=150 | K=200 | K=300 | K=500 | median first arm |
  |---|---|---|---|---|---|
  | 0.05 normal | 74.9% | 86.9% | 97.7% | 99.9% | trade 109 |
  | 0.10 normal | 77.9% | 91.1% | 98.8% | 100% | 110 |
  | 0.15 normal | 75.8% | 90.8% | 99.2% | 100% | 113 |
  | 0.20 normal | 69.5% | 86.5% | 98.7% | 100% | 120 |
  | 0.30 normal | 55.7% | 75.0% | 93.8% | 99.8% | 140 |
  | 0.10 / 0.20 / 0.30 skewed (trend-like, skew 2) | 76.8 / 66.1 / 45.0% | 91.7 / 85.4 / 64.2% | 99.1 / 98.1 / 86.4% | 100 / 100 / 98.3% | 111 / 124 / 159 |

  The first evaluation is possible at trade 100, and the median first arm is within 10–60 trades of it. A one-lot
  target entry × 0.25 is zero (GAP-P12D-145), so each first arm is a lock-out until a human resumes.
  **Part C, the post-resume fresh window.** The baseline is frozen at the resume and the throttle may flag at any
  post-resume count from 30 to 49. It falsely re-arms in **52.2% / 43.8% / 32.0%** of resumes (normal, S = 0.1 / 0.2 / 0.3)
  and **53.4% / 40.6% / 25.4%** (skewed). The fresh window judges as few as 30 trades, which is noisier than the
  standard 50-trade window: Part D measures the sd of the sample mean/σ at 0.192 for n = 30, 0.144 for n = 50 and
  0.082 for n = 150.
  **`probes/alpha_alt.py` (context for the fix), at S = 0.2.** The shipped rule locks out 100% of no-decay paths
  within 500 trades. A variance-aware rule on the same windows, flagging when `(s_b − s_r) > z·√(1/n_r + 1/n_b)`,
  gives these trade-offs:

  | z | false lock-out | catches a TRUE total decay within 100 trades | within 300 trades |
  |---|---|---|---|
  | 2.0 | 65.5% | 68.8% | 87.7% |
  | 2.5 | 30.8% | 41.4% | 58.0% |
  | 3.0 | 10.1% | 20.1% | 28.8% |

  No per-trade rule on these windows reaches both low false alarms and useful power.
- **External referents.**
  - Lo, "The Statistics of Sharpe Ratios", *Financial Analysts Journal* 58(4), 2002,
    https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf (fetched 2026-10-03). The paper
    "derive[s] explicit expressions for the statistical distribution of the Sharpe ratio using standard asymptotic theory
    under … independently and identically distributed returns". Its IID asymptotic variance (eq. 8, 1 + SR²/2) gives an
    SE of ≈ 1/√n per window, about 0.14 at 50 trades and 0.18 at 30. That is larger than the 50% erosion of a ~0.16 S
    the rule tests for. Part D reproduces these values numerically.
  - Carver, "Random data: Evaluating 'Trading the equity curve'", 10 Nov 2015,
    https://qoppac.blogspot.com/2015/11/random-data-evaluating-trading-equity.html (fetched 2026-10-03):
    "The idea that you can easily improve a profitable equity curve by adding a simple moving average filter is,
    probably, wrong", and "if your strategy is a trend following strategy, then it probably has negative autocorrelation,
    and applying the filter will be an unmitigated disaster." The throttle is a performance-conditioned size cut, that
    is, an equity-curve filter, applied to the TREND family (Carver's own rules).
  - Internal corroboration: GATES (`archive/RESEARCH_GATES_2026-10-02.md` R8) estimated "close to a coin flip" and the
    lab "armed it on 41% of days on a TRUE Sharpe-0.9 edge". This probe adds the zero-change false-alarm rate and the
    post-resume re-arm rate that the brief asked for. Neither is in the ledger.
- **Why it matters now.** GAP-P12D-145 is marked `fixed` and the spec (ACIS-07 v1.4 §7) presents the fresh-evidence
  re-arm as re-arming "only when … post-resume trades show the decay". On a book that has not decayed, a resume is
  followed by another false lock-out in roughly a third to a half of cycles. The residual pointer (GAP-P12D-61, R8)
  owns the replacement, but not this quantified behaviour in the meantime. Separately, the history lives in memory
  (`monitor.py:63`), so the detector needs 100 closed trades without a restart. At ~25 closes a year (GATES) the guard
  is effectively dormant on the demo, so its protection is mostly nominal until R8 lands.
- **Proposed fix (owner decision: `alpha_decay_sharpe_mult` is a guardrail value and the restrictive-state semantics
  are ACIS-07's):**
  - (a) Record these rates in GAP-P12D-145/61 so "fixed" is not read as "sound".
  - (b) Bring R8 forward: a shadow-book daily-P&L monitor with a declared false-alarm budget. Examples are a CUSUM
    with an in-control ARL of ≥ 1,000 days, or a one-sided test of the registered Sharpe prior. The daily series has
    ~250 observations a year, against ~25 closed trades.
  - (c) Until then, any per-trade rule should be variance-aware, with its threshold set from a stated false-alarm rate
    rather than a fixed 0.5× ratio.
  - (d) If the per-trade detector stays, persist the trade history or count only the post-restart window explicitly,
    so "dormant" is a declared state.

### PR16E-02 — 21 days (the schema ceiling) does not cover BIS's year-end gap. AUD pairs go false-stale around early January.
- **Severity: low. Likelihood:** about 1 decision day a year on the 2025/26 schedule. 0–5 days in 2026/27, depending
  on the unpublished 2027 calendar.
- **Where:** `core/data/rates.py:40,70`; `config/system_config.yaml` `rate_max_stale_days_weekly: 21`;
  `config/targets_schema.py` (`le=21`); ACIS-04 v1.7 §4b R6-1.
- **External referents (fetched 2026-10-03):**
  - BIS CBPOL topic page, https://data.bis.org/topics/CBPOL: "Daily data are released around mid-week"; "Last update
    1 October 2026"; "Next release 8 October 2026".
  - BIS release calendar, https://data.bis.org/release-calendar (its embedded JSON lists every CBPOL release from
    2024-04-04 to 2026-12-23). Releases are weekly, mostly Thursdays. The year-end gaps are
    **2024-12-19 → 2025-01-03 (15 d)** and **2025-12-23 → 2026-01-08 (16 d)**, and the published calendar ends at
    2026-12-23.
  - BIS API, https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.AU?startPeriod=2026-08-15&format=csv: on
    2026-10-03 the last AU observation is 2026-09-24, so the 2026-10-01 release lags 7 days (as GAP-P12D-146 states).
  - RBA, https://www.rba.gov.au/schedules-events/board-meeting-schedules.html: the 2026 and 2027 Monetary Policy Board
    meetings fall in Feb, Mar, May, Jun, Aug, Sep, Nov and Dec, never in January. The BIS AU series moves only on the
    day after a meeting (e.g. 2026-03-18 and 2026-05-06 in the data).
- **Reproduction (server, `probes/rates_cadence.py`, real `RateTable` and the shipped limits):**
  - Normal weeks (2026-09-07..10-16): 0 stale days.
  - 2024/25: 0 stale days (the maximum age is exactly 21).
  - **2025/26, lag 7: stale on 2026-01-07 (age 22).** With a lag of 5 for the Tuesday 12-23 release: 0 stale days.
  - 2026/27, if the next release is 2027-01-07: 0. If 2027-01-08: 1 (01-07, age 22). If 2027-01-14: 5 (01-07..01-13,
    ages 22–28).
  - The schema ceiling `Le(le=21)` was confirmed, so config alone cannot widen the limit.
- **Impact.** AUD_USD, AUD_JPY and EUR_AUD get `no_target:stale_rates`. That is safe, since positions are kept, but it
  reintroduces the undeclared B0(d) divergence from RSIM that GAP-P12D-146 was meant to remove. RSIM decides with
  complete rates.
- **Proposed fix (owner decision; R6-1 is ruled):** either size the weekly limit to the cadence's worst case
  (longest published gap 16 d + 7 d lag ⇒ 23–24 d, re-checked when BIS publishes each year's calendar in November),
  or adopt GAP-P12D-146's option (a) for policy-rate sources (fresh until the next scheduled meeting; the RBA has no
  January meeting). At minimum, declare the year-end days in GAP-P12D-141.

### PR16E-03 — The `--live` downloader still holds the weekly sources to 10 days. It contradicts GAP-P12D-146 and fails the unit ~60% of weekdays.
- **Severity: low. Likelihood: certain** (on BIS's published cadence).
- **Where:** `scripts/download_macro.py:252` (`ends_by = today - timedelta(days=10)` for every live series) and :231
  (reject if the last date is earlier than `ends_by`). Stale text: `deploy/systemd/acis-macro.service:2-4` ("fetches the
  last 1,200 days … if they age past 10 days the engine makes no new targets") and `deploy/README.md:117-121` ("If they
  age past 10 days …"). The code fetches from 2011 (R16I-01) and allows 21 days for BIS and the SNB cube (GAP-P12D-146).
- **Reproduction (server, `probes/rates_cadence.py`, real `validate()` with the live arguments):**
  - On the BIS cadence above (releases on Thursdays, 7-day lag), `bis_policy` is REJECTED on **18 of 30 weekdays
    (every Mon, Tue and Wed)** between 2026-09-07 and 2026-10-16.
  - Around the year-end it is rejected on 12–14 of 20 weekdays, Thursdays and Fridays included.
  - `main()` then returns 1, so `acis-macro.service` (Type=oneshot, started daily by `acis-macro.timer` at 12:00 UTC)
    ends `failed` 3 days a week.
- **Impact.**
  - No release is lost: each one is accepted on its release day, and a rejected fetch keeps the last good file
    (write_atomic only on success).
  - (i) A unit that fails most weekdays is alarm noise that masks a real failure, such as a central bank changing its
    API.
  - (ii) On a fresh host, `acis-demo-prepare.sh:44` runs the service once and tolerates a failure. If that first run
    falls on a Mon–Wed, `bis_policy.csv` never exists, so `load_rate_table` skips AUD (R16I-08) and the three AUD pairs
    get `no_target` until Thursday's release.
  - (iii) The deploy text in the read path misstates both the window and the limit (A13).
- **Proposed fix:**
  - Give `validate` the per-source cadence: `ends_by = today − 21` for the ids in `core/data/rates.WEEKLY_SOURCES`,
    and `today − 10` otherwise. Import the constant so the downloader and the runtime cannot drift apart again.
  - Add a regression test that a BIS series 12 days old is accepted in live mode.
  - Correct the two deploy texts.

### PR16E-04 (latent) — The 08:00 New York slot sits inside MACRO_EVENT's 30-minute lookahead of the 08:30 ET US releases and the 08:15 ET ECB decision. The target entry is refused and not retried.
- **Severity: low. Likelihood:** none today (`core/runtime/wiring.py:168` passes `macro_imminent=lambda …: False`,
  "no live calendar yet"). **Certain** once GAP-P12D-03's live calendar is wired: E8 One's news rule makes the calendar
  a precondition of the funded account (GAP-P12D-148 item 5).
- **Where:**
  - `core/signals/daily.py:33` (`SLOTS["fx"] = ("America/New_York", 8)`, metals the same).
  - `core/data/events.py:280` (`timedelta(0) <= (when - ts) <= self._lookahead`, inclusive).
  - `config/system_config.yaml` `macro_lookahead_min: 30`.
  - `config/event_sources.yaml` `tier1_events: [NFP, CPI, RATE_DECISION, GDP]`.
  - `core/regime/nvma.py:268` (MACRO_EVENT has top precedence).
  - `core/regime/regime_types.py:81` (`integrity_tradeable()` is False for MACRO_EVENT, kept as an integrity gate by
    master v2.30 §4 / ACIS-05 v1.9 §6.4).
  - `core/runtime/target_loop.py:202` (`pending.pop`: one attempt per slot, never caught up).
- **External referents (fetched 2026-10-03):**
  - BLS CPI schedule, https://www.bls.gov/schedule/news_release/cpi.htm: release time "08:30 AM"; 2026 dates include
    Oct 14, Nov 10 and Dec 10. NFP (Employment Situation) and BEA's GDP also release at 08:30 ET.
  - ECB press release of 27 Jun 2022,
    https://www.ecb.europa.eu/press/pr/date/2022/html/ecb.pr220627~73acedf868.en.html: "Starting from 21 July,
    monetary policy decisions will be published at 14:15 CET (instead of 13:45)." That is 08:15 New York outside the
    spring and autumn DST-mismatch weeks.
  - ECB meeting calendar, https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html: decisions on 29 Oct and
    17 Dec 2026, then 8 dates in 2027.
- **Reproduction (server, `probes/macro_slot.py`, the shipped config and real `EventService`, `slot_after` and
  `RegimeContext`):**
  - **CPI 2026-10-14 08:30 ET:** the 08:00 slot reads MACRO imminent for **6/13**: AUD_USD, EUR_USD, GBP_USD,
    USD_CAD, USD_CHF, USD_JPY. Still 6 at slot + 299 s, the end of `slot_grace_s`.
  - **NFP 2026-11-06 and GDP 2026-10-29:** 6/13 each.
  - **ECB 2026-12-17 and 2026-09-10 at 14:15 CET:** **5/13**: EUR_AUD, EUR_CHF, EUR_GBP, EUR_JPY, EUR_USD.
  - **ECB 2026-10-29:** 0/13. That date falls in the DST-mismatch week, when 14:15 CET is 09:15 New York.
  - A MACRO_EVENT context gives `integrity_tradeable() → False`, so the target gate returns `veto`.
- **Impact.** The demo trades 13 FX pairs. Once a calendar is wired, ~36 US release days a year (CPI, NFP, GDP) refuse
  that day's entries on 6 pairs, and 8 ECB days refuse them on 5. Each refusal is systematic, not random, and
  calendar-aligned, so RSIM (which models no entry guard, GAP-P12D-141 (10)) and the engine would diverge on exactly
  the days with the largest moves. GATES's lab cost for a random 42% veto rate was small (−0.03 to −0.18 pp/yr),
  because the entry recurs the next day. A calendar-aligned skip of release days has not been measured.
- **Proposed fix (for GAP-P12D-03's build list, owner decision since it touches the veto):** for target entries, treat
  MACRO_EVENT as a *delay*: retry the pending slot after the event plus `window_after_s`, within a bounded window (GATES
  R9's direction). Alternatively, move the FX/metals slot clear of the 08:15–08:30 ET cluster. GATES's suggested
  08:05 does NOT clear it, because 08:30 is then 25 minutes ahead. Also add a test that pins the slot against an
  08:30 ET Tier-1 event.

---

## Honest negatives (checked, no defect found)

1. **BIS is weekly, and 21 days fixes the normal-week false-stale.** BIS states "around mid-week". The release
   calendar shows weekly Thursdays, and the 7-day lag was measured. Under 10 days, Mon–Wed decisions were stale
   (GAP-P12D-146's "3 of 5", reproduced). Under 21 days, normal weeks show 0 stale days (probe A).
2. **The SNB cube is weekly, so the classification is right.**
   https://data.snb.ch/api/cube/snbgwdzid/data/csv/en?fromDate=2026-08-20&toDate=2026-10-03 returns
   `"PublishingDate";"2026-09-28 10:00"` (a Monday) with the last SARON row on 2026-09-25 (Friday). The dimension list
   names it "SARON fixing at the close of the trading day". At a 17:02 New York decision the maximum age in a normal
   week is ~7 days, so 21 days is generous but harmless for a policy-driven rate. I could not verify the SNB's
   year-end publishing.
3. **10 days is sound for the daily sources.** On Sat 2026-10-03 the latest observations were:
   - EFFR (NY Fed API): 10-01.
   - ECB DFR: a calendar-daily series through 10-03, never stale while the fetch works.
   - SONIA (BoE IADB): 09-30.
   - TONA (BoJ stat-search, LAST_UPDATE 20261002): 09-30.
   - CORRA (BoC Valet): 10-01; 09-30 is a Canadian federal holiday, with no print.

   Holiday maxima (Golden Week, the Japanese New Year, UK Christmas plus Boxing Day, US and Canadian holidays) come to
   ~6–8 days including the publication lag. A daily source that stops publishing fails safe (no target).
4. **There is no race between the macro timer and the decision.** The timer runs at 12:00 UTC ± 10 min, the decision
   at 17:02 New York (21:02/22:02 UTC), and files are replaced atomically (`write_atomic` → `os.replace`). GAP-P12D-141
   (8) already declares the restart re-derivation's one-day carry difference.
5. **The deposit-safety claim (GAP-P12D-142) matches the venue referent.** Spotware's ProtoOAExecutionType
   (https://help.ctrader.com/open-api/model-messages/, fetched 2026-10-03) lists `DEPOSIT_WITHDRAW = 10`, "Type
   related to event of deposit or withdrawal cash flow operation". `core/data/ctrader/schema.py:97-108` mirrors the
   enum exactly, and `core/execution/ctrader_events.py:29,120` routes only ORDER_FILLED/ORDER_PARTIAL_FILL deals. A
   deposit carries no position and is dropped. A withdrawal would show as an equity fall, which fails in the safe
   direction (a guard trips).
6. **The GAP-P12D-147 split matches practice.** Carver's production system (pysystemtrade
   `docs/production.md`, https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/docs/production.md,
   fetched 2026-10-03) gates execution on trading hours, locks and liquidity, and applies no regime or confidence
   veto: "Resize the order depending on the current liquidity (level 1 volume at the top of the order book …)". So
   exempting a daily trend entry from NVMA's 1-minute confidence and label vetoes while keeping spread and
   liquidity checks follows the referent. The one departure is that pysystemtrade keeps an order on the stack and
   works it through the day ("at the end of the day it will be cleared from the order stack"), where ACIS gives the
   slot one attempt. That departure is declared (GAP-P12D-141 (10)) and owned by GAP-P12D-147's demo measurement.
   PR16E-04 is where it becomes systematic.
7. **`NO_PARAMS_FOR_REGIME` skipped for target entries** is consistent with master §2's rule-set row, since the target
   loop refuses an unregistered family on its own. I found no external referent that contradicts dropping a
   regime-keyed parameter check for a family that regimes no longer gate (master §4 v2.21/v2.22).
8. **Lead claims checked inside my lens:**
   - `python scripts/ledger_check.py` gives "286 entries checked; 0 violation(s)" (server, f0d9524).
   - `test_target_path.py`, `test_download_macro_live.py` and `test_risk_monitor.py`: 29 passed at f0d9524.
   - `test_a_weekly_source_stays_fresh_for_21_days_and_a_daily_one_for_10` and
     `test_a_target_entry_ignores_the_confidence_vetoes_but_not_the_integrity_gates` both FAIL when copied onto de96a75
     (A16 holds for these two).
   - RSIM's and the harness's rate callers (`tests/backtest/financing.py`, `scripts/run_oos_validation.py`,
     `scripts/r1_admission.py`) pass no weekly limit, so the single 10-day rule is unchanged for them.
   - I did not re-run the full suite; the internal lens covers it.

## What I could not verify

- **The real-tick rate of the integrity gates kept at the 08:00 New York slot** (SPREAD_VETO, DEAD_MARKET, ILLIQUID with
  its window-σ test, STALE_STATE). The compute server holds only Dukascopy candles, not ticks, so this stays with the
  demo's `TARGET_ENTRY_ZERO` count (GAP-P12D-147 residual). Note that the "session median" is the last 500 ticks seen
  in that session name (`core/data/normaliser.py:173-180,271-273`). At 08:00 New York it therefore starts from the
  previous day's last NY ticks, near the 17:00 rollover.
- **The cut-off date of BIS's Tuesday 2025-12-23 release** (past vintages are not queryable), and **BIS's 2027 calendar**,
  which BIS publishes each November. PR16E-02's year-end counts are shown under both lag scenarios and three next-release
  dates.
- **The SNB's year-end publication dates.**
- **The R1.6 book's closed-trade rate.** PR16E-01 converts trades to years with GATES's ~25 closes a year for a one-lot
  book. The probabilities themselves are stated per closed trade and do not depend on it.
- **The full text of Lo's eq. 8.** The PDF's equations are images. The 1 + SR²/2 form is the paper's well-known IID
  result, and the probe reproduces the resulting SE numerically.

## Residual risk

- The alpha-decay guard is a ratified human-only value (`alpha_decay_sharpe_mult`). Until R8 replaces it, the target
  path carries a guard that is dormant for years and then mostly noise. Each false lock-out costs a human resume, and
  each resume is a moment when other halts are also cleared in the same act (`on_human_resume` clears halts, re-arms
  latches and clears the throttle together).
- R6-1's limits are sized to today's publication calendars. A central bank or BIS changing cadence, or skipping a
  holiday week, moves the false-stale days. The engine fails safe (no target), but RSIM parity silently degrades on
  those days unless someone counts `no_target:stale_rates` by currency.
- When the live event calendar is built, the slot-versus-release collision (PR16E-04) has to be designed in. The
  current gate semantics would otherwise make release days systematic no-entry days for half the FX universe.
