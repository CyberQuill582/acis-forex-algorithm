# AUDIT (external-referent lens): f0d9524..9f57a6f, before the AWS cutover (2026-10-03)

> Brief: `archive/AUDIT_BRIEF_PRECUTOVER_2026-10-03.md` at `35fd443`. Audited state read with `git show 9f57a6f:<path>`.
> Lens: the implementation AND the spec against their external referents (the cited papers' actual methods, the standard
> statistics, the facts of the world). Constitution A3; finder, not clearer (A5).

## Attestation
- **Model:** Claude Opus 5.5 (`claude-opus-5-5[1m]`), the external-referent role. **Context:** fresh; no memory of earlier audits beyond what the repository holds.
- **Search budget:** 9 WebSearch calls of the 20 allowed. Everything else came from WebFetch on known URLs, `curl` of public pages, or a read-only `gh api` call. No subagents.
- **Repository writes:** this file only. No git writes. Server runs went through the helper in my own checkout of `9f57a6f`. My probes are in the session scratchpad at `audit_pc/external/probes/`.
- **Look discipline:** I computed no strategy return on real data. The only real-data reads were P&L-blind: timestamps and spreads of 6 USD/JPY day files, the holiday CSV, the Treasury CSV's yields, and calendar pages from MUFG. I also re-read the STORED vectors of looks 000015/16/19 (their outcomes 000017/18/20), which the brief permits, and simulated no new variant. Every defect I demonstrate uses a synthetic counter-example.
- **I am a finder, not a clearer.** A clean item here is not a sign-off.

## Executive summary
- **No external finding blocks the cutover.**
  - Tier 1 holds against the outside world where I could check it. BIS's weekly cadence fits the 28-day limit. The Sydney DST rule matches IANA. The cTrader spot fields and timestamp opt-in match the adapter.
  - Pepperstone's commission is not in C8, but the round-trip cost is roughly offset elsewhere in C8 (PCE-05).
  - The feed watch's 240 s threshold could not be checked against cTrader's real quote cadence, which is undocumented. It fails closed: it only refuses entries.
- **GOTOBI's research result is faithful to its source on everything that moves the verdict.**
  - The day set, the holiday move, Tuesday–Friday, 03:00 → 09:55 JST and the spread at both sides all match Bessho et al.'s text.
  - The bank calendar matches the Banking Act enforcement order. It also matches MUFG's actual TTM publication record on 15 of 15 edge days, including the 2020-10-01 TSE outage.
  - The tick files are UTC.
  - The HAC t (6.51) is a correct Newey–West t and survives every lag from 0 to 100 (5.7–6.7). The Sharpe annualisation is standard and slightly conservative.
  - What fails against the world is the RECORD around the result, not the result:
    - departures from Bessho's method that are not declared (EBS data, the control, the H2 gate);
    - a misreading of Ito & Yamada;
    - the live draft's G-4 timing claim, which is false;
    - the draft's G-3 size, which ignores D-a;
    - swap on the demo venue, which the draft ignores.
  - The only independent post-2023 evidence I could find, weak as it is, points to the effect having faded (PCE-02).
- **The one medium integrity finding is the register's GitHub anchor (PCE-01).**
  - The anchor is an unprotected branch in a private free-plan repository: GitHub refuses branch protection there.
  - `anchored()` never asks the remote. A synthetic repository with no remote branch at all passes it.
  - So the anchor is not the external, append-only commitment that GAP-P12D-86 and ACIS-09 v1.10 claim.
- **Counts:** 0 blocking · 2 medium · 5 low · 1 info, plus 3 cross-lens observations for the internal lens.

## Findings (cutover-blocking first: none)

### PCE-01 — The register's "outside anchor" is not outside and not append-only
- **Severity:** medium · **Likelihood:** low (it needs a deliberate actor with push rights) · **Tier:** 2
- **The claim.** `tests/backtest/look_anchor.py` (9f57a6f, lines 8–16) says the chain head is pushed to GitHub, "whose server-side push record is the external timestamp (Crosby & Wallach 2009)". It also says `anchored` "reads the REMOTE-TRACKING ref, which git updates only after a successful push". GAP-P12D-86 marks the durability gap **mitigated** on that basis.
- **The world, reproduced.**
  1. `gh repo view` → `{"nameWithOwner":"CyberQuill582/acis-forex-algorithm","visibility":"PRIVATE"}`.
     - `gh api repos/…/rules/branches/look-anchor` and `…/branches/look-anchor/protection` both return HTTP 403: "Upgrade to GitHub Pro or make this repository public to enable this feature." (doc URLs in the responses: https://docs.github.com/rest/repos/rules#get-rules-for-a-branch, https://docs.github.com/rest/branches/branch-protection#get-branch-protection; queried 2026-10-03).
     - `gh api repos/…/branches/look-anchor` gives `protected=false`, head `9f5bb3b7…`, equal to the local `refs/remotes/origin/look-anchor`.
     - So anyone with push access, including any agent session holding the owner's `gh` credentials, can force-push or delete the anchor. No third party sees the repository.
  2. Git updates a remote-tracking ref on `fetch` as well as on push, and `git update-ref` can set it locally. `anchored()` (line 71) reads only that local ref and never runs `ls-remote`.
     - Synthetic probe `probes/anchor_local_ref_probe.py`, run on the server at 9f57a6f: a temporary repository and bare remote, an anchor commit written with plumbing, then `update-ref refs/remotes/origin/look-anchor` with no push.
     - Output: `anchored() with a locally forged tracking ref: True` while `remote's look-anchor branch: ('', 1)` (no such branch).
- **Why it matters.** Real-data looks are now open, and the anchor is what makes deleting the register's tail detectable (master v2.32 (2); ACIS-09 v1.10/1.11).
  - As deployed, deleting the last line plus rewriting the anchor (a local `update-ref`, or a force-push to the unprotected branch) leaves no trace that any outside party holds.
  - GAP-P12D-86's residual names the unsigned chain and the honour-system family names, not this.
- **Proposed fix (owner decision where it costs money).**
  - (a) In `anchored()`, compare the local tracking ref with `git ls-remote origin refs/heads/look-anchor`, and refuse on a mismatch or a missing branch.
  - (b) Make the anchor append-only on the server: a public repository or GitHub Pro, with a ruleset that blocks force-push and deletion on `look-anchor`. Or add a third-party timestamp the operator cannot rewrite (an RFC 3161 TSA, OpenTimestamps).
  - (c) Until then, state the limit in GAP-P12D-86's residual and correct the docstring's "only after a successful push".

### PCE-02 — GOTOBI's forward premise: no outside evidence that the effect persists after 2020, and the one post-2023 measurement found points the other way
- **Severity:** medium (it bears on the ruled build order "GOTOBI first, before REBAL") · **Likelihood:** unknown · **Tier:** 3 (forward path)
- **What the sources say.**
  - Bessho et al. study only 2018–2020 (arXiv 2301.13204 §2: "analyzing the recent historical data of the USD/JPY rate during 2018 to 2020"). Their paper is itself about the anomaly becoming popular.
  - The repository's own stored vector (look 000017, per the ledger) decays: 2.21 in 2012–17, 1.30 in 2018–23, −0.51 in 2023.
  - The only independent post-2023 measurement I found is a personal blog (https://www.pondaichi-act2.tech/?p=7944, published 2026-09-16, updated 2026-09-24): "ゴトー日199回・それ以外465回、午前8時から10時までの変化…集計期間は2023年11月末〜2026年9月" and "ゴトー日の平均は-1.86pips（円高方向）、それ以外の日は+1.09pips"; data "ドル円1時間足…Yahoo Finance チャートAPI".
- **Grade: UNCONFIRMED.** The method is weak. Its 08:00→10:00 window spans the post-fix reversal that Bessho's Fig. 3 documents, and it reads hourly retail bars. It does not contradict the 2012–2023 kill-only survival. It is simply the only outside evidence after 2023, and it agrees with the repository's own 2023 number.
- **Proposed fix.**
  - Before the live build, pre-declare a forward kill rule for the sleeve (sample size and threshold).
  - Owner decision: a registered kill-only look on the 2024–2025 holdout tier. Under §5.6 it is still before the certifying boundary of 2026-10-01, so it is kill-only and spends no credit.
  - Weigh REBAL-first again with this in view.

### PCE-03 — Undeclared departures from Bessho et al.'s method in the GOTOBI record
- **Severity:** low · **Likelihood:** certain · **Tier:** 3
- **Source (arXiv 2301.13204, retrieved 2026-10-03):**
  - §1: "we use the order book information of the Electronic Broking System (EBS)".
  - §2: "non-Gotobi days were randomly selected for the same number of Gotobi days".
  - §3.2: "we verify the profitability of taking a sell position just after 9:55 and closing its position at 12:00 … this strategy is performed only when the profit obtained until 9:00 is more than 0".
  - §3: "In order to calculate the profit obtained by trading strategy, we subtracted the bid-ask spread when entering into the market and exiting from the market".
- **Departures not recorded anywhere** (`grep -ci EBS` gives 0 hits in `event_window.py`, `r1_gotobi_kill_test.py` and the live draft; the ledger's 9 hits are all unrelated):
  - (a) EBS 2018–2020 → Dukascopy SWFX ticks 2012–2023.
  - (b) `r1_gotobi_kill_test.py` line 14 calls the benchmark "the paper's control", but Bessho's control is a random sample of non-gotobi days equal in number to the gotobi days. ACIS uses all of them.
  - (c) `event_window.py` line 91 gates H2 on `mid(09:00) > mid(03:00)` and cites Bessho §3.2. Bessho's "profit … more than 0" is a profit net of the spread.
    - Synthetic probe `probes/h2_gate_probe.py` (server, 9f57a6f): mid +0.002 against a 0.004 spread. Output: `event_window traded legs: ['entry->fix', 'fix->noon'] | Bessho's net-profit reading would trade H2: False`.
  - (d) H2 enters at the last tick at or before 09:55:00, where Bessho says "just after 9:55".
- **Effect.** None of these can move the kill verdict (t 6.5 against −0.5). v1b is not forwarded (G-5). The control is context only.
- **Proposed fix.** List (a)–(d) as declared departures in the GOTOBI module docstring and in GAP-P12D-158. They become the §5.6 `declared_deviations` of the live family's provenance record when G-1..G-6 are built.

### PCE-04 — Ito & Yamada misread: their gotobi set is 5/10/15/20/25/30 plus the end-of-month trading day
- **Severity:** low · **Likelihood:** certain · **Tier:** 3 (record)
- **Source.** NBER w22820 (Nov 2016, the JIE 2017 paper's working version), https://www.nber.org/system/files/working_papers/w22820/w22820.pdf: "typically on the days of the 5th, 10th, 15th, 20th, 25th, and 30th, (hereafter 5th and 10th days) as well as the end-of-month trading day".
- **The repository says otherwise.**
  - GAP-P12D-158 says: "Ito & Yamada: the 5th and 10th days and the month's last trading day". That reads their shorthand label literally.
  - `jp_days.py` line 10 calls `last="month_end"` (the 31st in place of the 30th) "Ito & Yamada 2017's end-of-month effect". Their set is the UNION.
- **Consequence (P&L-blind count, `probes/gotobi_control_monthend.py`).** 43 of the 1,638 graded control days (2.6%) are I&Y end-of-month settlement days.
  - Context only. It slightly contaminates the control and does not touch the verdict.
- **Proposed fix.** Correct the two texts. If a month-end variant is ever wanted, define it as I&Y's union, as a new registered family-version.

### PCE-05 — C8 declares no FX commission; the demo venue charges $6 a round-trip lot on cTrader
- **Severity:** low · **Likelihood:** certain · **Tier:** 1 (the demo's FX13) and 3 (GOTOBI's declared cost)
- **The fee.** Pepperstone's FAQ (https://pepperstone.com/en-eu/support/what-commissions-do-i-pay-on-trades/, retrieved 2026-10-03): "cTrader commission is calculated as $6 USD for FX, $7 for XAU/USD roundtrip fixed per unit". That is $3 a side per 100k, about 0.3 bp a side on USD/JPY.
- **What C8 declares.** `config/instruments.yaml` (9f57a6f) has `commission_per_side: 0.0` on every FX pair. The XAU line does acknowledge a commission.
- **Rough offset.** A search summary of third-party data (compareforexbrokers.com, UNCONFIRMED) gives a Razor USD/JPY average of 0.19 pip. Pepperstone's round trip is then about 0.13 + 0.6 ≈ 0.7 bp. C8's is Dukascopy's 0.34–0.36 bp spread plus 2 × 0.002 JPY slippage ≈ 0.62–0.71 bp. So the totals are close.
- **Effect.** Nothing material: GOTOBI keeps 1.54 at 2× cost and D1-FX13 0.156. But C8 misstates the venue's fee structure, and the GOTOBI draft's G-6 cost check names spreads only.
- **Proposed fix.** Declare the commission in C8, or record that the slippage term stands in for it. Include the commission in G-6's pre-declared cost check.

### PCE-06 — The GOTOBI live draft is wrong about the clock (G-4), silent on D-a (G-3), and silent on the demo venue's swap
- **Severity:** low (a draft, not yet ratified) · **Likelihood:** certain · **Tier:** 3 (forward draft)
- (a) **G-4's timing is false.**
  - G-4 says "D1's 17:00 decision and its slot fall INSIDE every sleeve hold". The FX slot is 08:00 New York (`core/signals/daily.py` and `tests/backtest/rsim_real.py` `SLOTS["fx"] = ("America/New_York", 8)`), which is 21:00/22:00 JST, outside 03:00–09:54 JST.
  - Only the 17:00 DECISION falls inside a hold. There the band reads `held` (`target_decision.decide` → `banded_target(float(held), …)`), so the sleeve's units must be netted out at the decision, not at the slot.
- (b) **G-3 conflicts with D-a.** G-3 proposes about 6 × `capital_ref` notional (about 0.6 lot on the $10k demo). Master §5 D-a and ACIS-05 §6.4 line 115 say "paper and practice: |target| <= one venue minimum lot". The draft lists the guards that still apply but not this rule.
- (c) **Swap on the demo venue.** Every sleeve hold crosses the 17:00 New York rollover: 06:00/07:00 JST. Holds entered at 03:00 JST on a Thursday cross Wednesday's triple rollover (the repository's own `rates.swap_multiplier`, tom_next).
  - The demo venue is not swap-free. The research book is swap-free (R1-D9), and G-6's replay and cost check say nothing about swap.
- **Proposed fix.** Correct G-4 before ratification, put D-a in front of the owner with G-3, and add swap to G-6.

### PCE-07 — `jp_index_cash` declares a 15:00 Tokyo close; the TSE has closed at 15:30 since 2024-11-05
- **Severity:** low (the instrument is disabled) · **Likelihood:** certain · **Tier:** 1 config (`ce6c598`)
- **Source.** FX News Group, 2023-09-20, quoting the JPX release (https://fxnewsgroup.com/forex-news/exchanges/tse-to-extend-trading-hours-in-conjunction-with-launch-of-next-generation-trading-system/): "the closing time of the afternoon session for arrowhead trading will be extended by 30 minutes to 12:30 – 15:30", with "arrowhead 4.0 scheduled for November 5, 2024". JPX's own pages returned 403 to my fetch.
- **The config.** `config/instruments.yaml` calls these calendars "the home exchange's CASH hours" (declared provisional). `exchange_days.py` is correct and says so ("Tokyo closes at 15:00 until 2024-11-04, so the years stop at 2024-10").
- **Proposed fix.** Correct the hours, or narrow the label, before JP225 is enabled.

### PCE-08 — The "documented record-low 10-year close" is not the record low
- **Severity:** info · **Tier:** 3 (REBAL input, provenance text)
- **The repository says.** `scripts/download_treasury.py` lines 9–10 and 28, and GAP-P12D-157, call 0.54 on 2020-03-09 the record low.
- **The issuer's own file says.** The repository's copy (`data/r1_real/treasury/ust_par.csv`, from home.treasury.gov) holds 0.52 on 2020-08-04, the minimum of the series (0.54 was the low of that time).
- **Effect.** The check still validates a known value. Only the label is wrong.

## Cross-lens observations (for the internal lens; not counted)
- **X-1.** GOTOBI's looks register `Declaration("fixed", 1, "PASSIVE_LONG")` (`r1_gotobi_kill_test.py` line 123), and outcomes 000017/18/20 carry `"benchmark": "PASSIVE_LONG"`. The stored `benchmark_vector` is the cost-charged non-gotobi CONTROL (lines 139–140), not a passive long.
- **X-2.** The scope text does not name the books the GOTOBI and IMOM looks (000011–000020) actually used: the tick window `event_window` and the minute-candle `event_intraday`, both graded through `grade_event_look`.
  - Master v2.34 (1) says the event simulator is "`tests/backtest/event_sim.py`, graded only through `evaluate_events()`".
  - ACIS-09 v1.12 says "scheduled-window rules on hourly candles".
- **X-3.** The master's hard-override list still reads "instrument liquidity below ILLIQUID_THRESHOLD", with the target exception attached only to the veto and the confidence override. Yet §4 v2.33 and `guards.py` (`not target and … ILLIQUID`) exempt target entries from ILLIQUID.

## Honest negatives (checked at source and found right)
1. **GOTOBI's day set and book match Bessho** (arXiv 2301.13204).
   - §1: "5, 10, 15, 20, 25, and 30 of each month".
   - §2: "the previous business days were included if Gotobi days were holiday" and "we used daily data from Tuesday to Friday" ("because the world's FX markets are closed early in the morning on Mondays in Japan").
   - §3.1: "entering the market at 3:00 and exiting it at 9:55".
   - Spread charged at both sides. February: the paper is silent, so the declared choice stands.
   - Bessho's H1 (2018–20, N = 185, PF 1.46, W 0.60) is consistent with ACIS's stored per-trade record: +5.3 bp mean, 64% hit rate.
2. **The bank closure law.** 銀行法施行令 第五条 (e-Gov API, https://laws.e-gov.go.jp/api/1/lawdata/357CO0000000040, retrieved 2026-10-03): "一 国民の祝日に関する法律…に規定する休日 二 十二月三十一日から翌年の一月三日までの日（前号に掲げる日を除く。） 三 土曜日". Together with Sundays (Banking Act art. 15), this is exactly `jp_days.BANK_CLOSED` plus the Cabinet Office list.
3. **The calendar against MUFG's real TTM record.** MURC per-day pages, `https://www.murc-kawasesouba.jp/fx/past/index.php?id=YYMMDD` (a non-publication day falls back to the current day's page); `probes/murc_calendar_check.py`.
   - `jp_days.is_bank_day` agrees on 15 of 15 edge days: 2012-12-31, 2013-01-02/03/04, 2013-12-30, 2015-09-22 (citizens' holiday), 2018-12-31, 2019-04-26, 2019-04-30, 2019-05-02, 2020-07-24, **2020-10-01 (TSE outage: TTM published)**, 2021-08-09, 2022-01-04, 2023-12-29.
   - The MURC FAQ (https://www.murc-kawasesouba.jp/fx/faq/faq.pdf): rates are posted "銀行営業日の午前11時過ぎ", and a date with no data "は休日で公表相場は発表されていません".
   - Ito & Yamada: "The Tokyo fixing rates are not available on Japanese national holidays".
   - The fix at 9:55: Bessho §1 ("9:55 a.m. when TTM is decided"); Ito & Yamada ("the fixing time window around 9:55").
4. **The tick files are UTC** (P&L-blind, `probes/local_clock_check.py`, 6 local day files).
   - USD/JPY's last Friday tick: 20:59:56 UTC (2019-07-12) and 21:59:49 UTC (2019-01-11).
   - First Sunday tick: 21:00:04 / 22:00:04 UTC.
   - The rollover spread widens at 21:00 UTC in July and at 22:00 UTC in January, which is 17:00 New York both times.
5. **The HAC t is a correct Newey–West t.**
   - Bartlett weights 1 − l/(L+1), lag floor(4(n/100)^(2/9)) = 8 at n = 3,108. panelbox docs (https://panelbox.readthedocs.io/en/latest/inference/newey-west/): "The default bandwidth follows the Newey-West (1994) rule: m = ⌊4(n/100)^(2/9)⌋".
   - On the STORED vectors (`probes/stored_vector_stats.py`), v1a's t at lags 0/8/20/50/100 is 6.34/6.51/6.66/6.17/5.74, v1b's 6.90/7.12/7.16/7.01/6.79, v1c's 6.28/6.49/6.59/6.09/5.63.
   - Lag 1–5 autocorrelations are about −0.01. The per-trade iid t (6.47) is about the daily-vector t.
6. **The Sharpe of the sparse vector is standard** (constant capital, flat days are zero).
   - The vector has 261.0 marks a year, so √252 understates by 1.8% (1.806 against 1.838): conservative.
   - Booking a hold on the next 17:00 New York mark only relabels a date: the 740 non-zero marks equal the 740 trades, so no mark holds two trades and the mean, variance and HAC t cannot change.
   - Dividing the exit cost by the entry price is off by at most about 2% of about 0.36 bp.
7. **The kill rule t < −0.5 works as a one-sided screen, not a test.**
   - Under zero edge P(kill) = Φ(−0.5) = 31%. At a true Sharpe of −0.5 over 11.9 years, P(kill) ≈ Φ(1.22) ≈ 89%.
   - That fits "survival credits nothing".
8. **REBAL matches Harvey, Mazzoleni & Melone** (NBER w33554, revised January 2026, https://www.nber.org/system/files/working_papers/w33554/w33554.pdf).
   - B.1: "w_{t+1} = 60% if |w_t − 60%| ≥ δ". B.2: "60% if t is the last business day of the month". The signal is the drifted weight − 60%.
   - §4: "− Threshold Signal_t / 1.5%"; "sign(−Calendar Signal_t) if t falls within the last week of a month"; "on the first business day of a new month … sign(Calendar Signal_{−4})", days indexed −10…−1 (Fig. 3's axis).
   - "R^Strategy_{t+1} = (R^{S&P} − R^{10y}) · w_t".
   - `rebal.py` reproduces each, including the day-after resets and the −4 index (k − 4 with k − 1 the last day).
9. **IMOM matches Baltussen, Da, Lammers & Martens** (JFE 142 (2021), https://www3.nd.edu/~zda/intramom.pdf).
   - "ROD = ON + FH + M + SLH" ("from previous market close to the last 30 minutes"). Eq. 12 is the sign timing.
   - The S&P 500 index closes at 16:00 (Table 12, Panel A).
   - "we do not consider transaction costs", while "a positive net Sharpe ratio" at one tick for S&P futures.
10. **D3's window** is McConnell & Xu's: "the interval beginning with the last trading day of the month and ending three days later" (https://docs.lib.purdue.edu/ciberwp/43). That is close(T−2) → close(T+3).
11. **The 28-day weekly limit.** BIS (https://data.bis.org/topics/CBPOL, retrieved 2026-10-03): "Daily data are released around mid-week"; last release 1 Oct 2026, next 8 Oct 2026.
12. **`fx_clock.au_daylight_time`** equals IANA Australia/Sydney on all 16,070 business-hour instants from 2009 to 2030 (`probes/au_dst_check.py`).
13. **cTrader Open API** (https://help.ctrader.com/open-api/messages/, https://help.ctrader.com/open-api/connection/).
    - `bid`/`ask` are optional. `timestamp` is "The Unix time for spot", sent only with `subscribeToSpotTimestamp`.
    - "keep sending a heartbeat event … every 10 seconds".
    - This is consistent with the adapter (`core/data/ctrader/feed.py`: venue timestamp required, last known side kept).
14. **Governance.**
    - `python scripts/ledger_check.py` on the server reports 296 entries, 0 violations.
    - Every audited module is at most 300 lines (`look_register.py` 297, the closest).
    - 71 event, calendar, feed, clock and report tests pass at 9f57a6f.
    - Spot-checks of residuals: GAP-P12D-152 → 153 and GAP-P12D-154 → 156 own their remainders. GAP-P12D-86's does not (PCE-01).

## What I could not verify (UNCONFIRMED)
- **Dukascopy against EBS.** Dukascopy's USD/JPY quotes against EBS at 03:00 and 09:55 JST: I have no EBS access.
- **Pepperstone's spreads at the trade times.** Its USD/JPY spread at 03:00 and 09:54 JST: I found only a third-party 24-hour average (0.19 pip). The draft's two-week demo measurement is the right instrument.
- **cTrader's quote cadence.** Whether spot events are throttled or conflated is undocumented, so I cannot say whether the feed watch's 2 × 120 s ever trips at the 08:00 New York slot on the FX13. Since it fails closed, it cannot open a position.
- **Unread sources.**
  - Akiyama et al. (JAFEE 2021, in Japanese): I quote only Bessho's description of it ("as in our previous study").
  - The JIE 2017 published text of Ito & Yamada: I read the NBER working paper.
  - The CME 10-year note's deliverable range behind REBAL's 7-year par duration: not fetched.
  - The sign and size of Pepperstone's USD/JPY swap in 2026: not fetched.
- **Persistence after 2020.** Only the weak blog evidence in PCE-02.

## Residual risk
- **GOTOBI's history result** looks externally sound. Its risk is forward:
  - decay (PCE-02);
  - execution into the fix on a retail venue;
  - venue costs and swap that the research book idealises (PCE-05, PCE-06).
- **The register's integrity** against an insider still rests on trust (PCE-01).
- **The cutover code's external surface** is small, and its failure modes fail closed: no trade.
- **My lens shares one blind spot with the internal lens:** neither can see the demo venue's real behaviour until fills exist. That is the operational-referent pass's job, after go-live.
