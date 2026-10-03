# GOTOBI v1 live: the forward path (DRAFT for owner ratification, 2026-10-03)

**Status:** DRAFT. Nothing here binds until the owner ratifies it at build time, AFTER the 2026-10-15..17 AWS cutover. Owner rulings 2026-10-03: "Draft now, build after cutover" and "GOTOBI first", before REBAL. On ratification it is applied as one master version and then built. That version touches ACIS-04 §4b (a second, intraday decision clock), ACIS-05 §6.4 (the sleeve's sizing and its netting with D1) and ACIS-13 (the sleeve's orders). The build is audited at that milestone.

**Why:** GOTOBI survived every kill-only look it was given (GAP-P12D-158):

| Look | Rule | Net Sharpe | HAC t |
|---|---|---|---|
| v1a | USD/JPY long 03:00 → 09:55 JST on Tue–Fri gotobi bank days | 1.81 | 6.51 |
| v1b | v1a, plus Bessho's gated short 09:55 → 12:00 | 1.96 | 7.12 |
| v1c | v1a, leaving at 09:54 | 1.79 | 6.49 |

Its correlation with D1 is about 0, and with REBAL about 0.03. It is decaying: 2.21 in 2012–17, 1.30 in 2018–23, and −0.51 in 2023. It is LLM-selected, so only forward data can credit it (§5.6). USD/JPY is already in the demo's FX13 universe, so the sleeve needs no onboarding.

**Unchanged (and unreachable by anything here):** `config/guardrail_limits.yaml`, the equity floor, HALT/veto/resume semantics, the live gate (rung 2 + human sign-off), and D1's 17:00 New York decision.

---

## 1. What the registered family fixes (restated)

- The day set is Bessho's: 5, 10, 15, 20, 25 and 30 (or the month's last day when it is shorter), moved to the previous Japanese bank day, Tuesday to Friday JST.
- Bank days are taken from the Cabinet Office's holiday list plus the 31 Dec – 3 Jan bank closure (`tests/backtest/jp_days.py`).
- The position is long from 03:00 JST to the fix, priced at Dukascopy ticks under the C8 costs, and flat otherwise.
- v1c shows the edge does not need the fix-second print.

## 2. The live departures (each a proposed ruling)

- **G-1 The clock.** Two fixed instants per gotobi bank day, both in Asia/Tokyo with no DST:
  - Open at 03:00 JST.
  - Close by 09:54 JST, as a market order, the registered v1c timing.
  - A missed open skips the day; it is never caught up late. A close that cannot fire by 09:55 fires at the first moment the market allows, and the miss is logged.
- **G-2 The calendar on the host.** `jp_days` moves into core (the runtime cannot import tests).
  - The holiday file is fetched from the Cabinet Office by a yearly timer and checked as the downloader checks it.
  - The runtime refuses to trade a gotobi day whose year the file does not cover, the same refusal as `CalendarRefused`.
- **G-3 Size.** A fixed USD notional per trade, a multiple of `capital_ref` ($10k on the demo), set so the sleeve's ex-ante annual volatility is a declared target.
  - The window's per-trade sd was about 22 bp on history, so 1× notional gives about 1.7% a year; a 10% sleeve target is about 6× `capital_ref`.
  - Proposed: **a 10% sleeve volatility target, held fixed and re-estimated yearly** from the venue's own history. Every existing guard applies: currency and cluster caps with G-5 headroom, VaR, the daily loss, halts. So does the 10 × daily-ATR disaster stop (R6-2).
  - **Conflict to rule (audit PCE-06, 2026-10-03):** about 6× `capital_ref` is about 0.6 lot on the demo, but D-a caps every target position at ONE minimum lot in paper and practice. On the demo the sleeve therefore trades one minimum lot unless the owner rules otherwise; the 10% target applies only after rung 1.
- **G-4 Netting with D1.** D1 may hold USD/JPY at the same time. The account's USD/JPY target is D1's target plus the sleeve's units, so the guards see one position.
  - The sleeve's open and close are deltas on top of D1's target.
  - **Where the clocks meet (corrected by the audit, PCE-06).** 03:00–09:54 JST is 14:00–20:54 New York in summer and 13:00–19:54 in winter. D1's 17:00 DECISION falls inside every sleeve hold; its FX SLOT (08:00 New York, 21:00–22:00 JST) does not.
  - So the netting belongs at the decision. D1 records the position it decided against; if that includes the sleeve's units, the slot finds a different position and skips with `position_changed`, on every gotobi day. D1's decision must therefore read the position MINUS the sleeve's open units, and its slot must compare against the same.
  - The sleeve's units are persisted, as the day's decision is, so a restart re-derives them. A test must cover a D1 slot inside a sleeve hold, in both directions.
  - D1's no-trade band does not apply to the sleeve's deltas.
- **G-5 Version.** v1a/v1c (H1 only) is forwarded. v1b's short leg after the fix (+0.15 Sharpe on history) waits until H1's forward record exists: one mechanism at a time.
- **G-6 The record.** The forward record is graded against a replay of the SAME live rule (stage D: G-1's clock on the venue's own ticks or M1). The shadow book and `scripts/demo_report.py` report the sleeve beside D1. The pre-declared cost check uses the demo's own USD/JPY spreads at 03:00 and 09:54 JST, **plus the venue's commission** (Pepperstone cTrader: $6 per lot round trip on FX, PCE-05; C8 declares 0) **and the swap**: every sleeve hold crosses the 17:00 New York rollover, so the demo account pays or earns USD/JPY's tom-next swap, triple on Wednesdays (sign unverified, PCE-06). A swap-free venue removes it; the history assumed none.

## 3. Before the build (P&L-blind)

- Measure the demo's USD/JPY spread at 03:00 and 09:54 JST for two weeks after the cutover; history assumed Dukascopy's median 0.34–0.36 bp.
- Confirm the venue's market-order behaviour in the minute before the Tokyo fix: fill latency and slippage on the demo.
- Move `jp_days` and the holiday fetch into core with their tests, and add the yearly timer to the AWS host.

## 4. Rulings to ratify at build time

- G-1: open at 03:00 JST, close by 09:54 JST, never caught up.
- G-2: the calendar in core, the yearly fetch, refusal past its coverage.
- G-3: a 10% sleeve volatility target on `capital_ref`, every guard applying.
- G-4: additive netting with D1's target.
- G-5: H1 only.
- G-6: stage D on the live rule, plus the demo-spread cost check.
