# Execution policy for the target path: a proposal (EXECUTION agent, 2026-10-03/04)

**Status: a proposal for the owner and the lead. Nothing is built into the engine; any change below needs the
owner's ratification.** The evidence is `archive/EXECUTION_REPORT_2026-10-03.md` (run `4a9e9b1`). Written by
claude-opus-5-5.

## 1. The policy: market at the slot, priced honestly, measured forward

The brief asked for "passive-first with a deadline, then market". The measurement says no: on a CFD venue that
policy costs money at every daytime slot ACIS uses. The proposal is therefore:

| # | Policy | Owner action? |
|---|---|---|
| **E-1** | **Keep the market IOC order at the slot**, as built (ACIS-05 §6.4 "Execution clock"; ACIS-13 §7.3, `order_types = {"market"}`). Do not build resting limits, the mid, or Carver's chase on the CFD target path. | Confirm. No spec change. |
| **E-2** | **Record GAP-P12D-148 T4 ("passive-first … cost −25 to −40%") as rejected for CFD venues.** Carver's cut is real on an exchange queue (futures via IB). On a principal CFD venue a limit is a conditional market order on the venue's own quote. Reopen T4 only for an exchange venue (Lever 2), re-studied on trade-and-quote data. | Lead records. |
| **E-3** | **Never execute in the rollover window** (16:55–17:30 New York). The target path already decides at 17:02 and executes at 08:00, and the feed watch's `wide_spread` refuses it. The rollover costs 1.6–5.3 bp of spread on Dukascopy and 2–3.7 bp on the demo; the old engine's four fills there paid 1.78–2.98 bp. | None: already so. Keep it in mind for any new family's slot. |
| **E-4** | **Price the venue honestly in C8.** Add Pepperstone's commission: FX $3 a lot a side (0.27–0.30 bp; C8 declares 0) and gold $3.50. Re-estimate the slippage constant from the demo's own fills after 4 weeks (the old engine's 13 daytime fills averaged +0.007 bp against C8's 0.17–0.18 bp a side). C8 must never fall below the venue, and the stress knob still only adds. For gold and US500, measure the venue before trusting C8: it is about 2.4× and 1.8× their published averages. | Owner: it changes `cost_map_hash` for every later look (master §5 C8; ACIS-03 §5). |
| **E-5** | **Measure forward, with no orders** (§3). | Owner: M4 needs the app credentials. |

## 2. Expected savings, with uncertainty

Per side, against the market order at the slot, in bp (± one standard error across days; Dukascopy 2019–2023, plus
the demo's own feed). "Realistic" means Carver's chase at the demo's measured 0.5 s round trip; the plain touch
is the textbook passive order.

| Slot | Plain touch, 5 min (venue rule / 1 tick) | Realistic chase, 5 min (0.5 s / and 1 tick) | Per round trip, as a share of the venue's cost |
|---|---|---|---|
| D1 08:00 NY, EUR/USD | −0.12 ± 0.03 / −0.17 | −0.04 / −0.06 | Adds 0.08–0.34 bp to ~0.55–0.6 bp: **+15% to +60%** |
| D1, USD/JPY | −0.14 ± 0.03 / −0.22 | −0.02 / −0.04 | Adds 0.04–0.44 bp to ~0.75 bp: **+5% to +60%** |
| D1, GBP/USD (2021–23) | −0.11 ± 0.06 / −0.17 | −0.01 / −0.02 | Adds 0.02–0.34 bp |
| D1, AUD/USD (2021–23) | +0.07 ± 0.06 / −0.03 | +0.00 / −0.03 | Saves at most ~0.14 bp (not significant) |
| D1, XAU/USD | −0.21 ± 0.09 / −0.24 | −0.03 / −0.04 | Adds 0.06–0.48 bp |
| FXHEDGE 15:00 LDN, 4 FX | −0.56 to −0.77 | −0.22 to −0.37 | Adds 0.4–1.5 bp |
| GOLD-EW 02:00 / 11:00 NY | −0.00 to −0.10 | −0.00 to +0.05 ± 0.02 | About ±0.1 bp: **±3% of C8, ~±10% of the venue's published cost** |
| IMOM 15:30 / 16:00 ET, US500 | −0.34 / −1.01 | −0.33 / −0.60 | Adds 0.9–1.35 bp to ~1.9 bp: **+50% to +70%** |
| Demo feed, every minute, EUR/USD and USD/JPY | −0.07 / −0.06 | −0.06 / −0.01 to −0.03 | Negative |

**Central estimate for the target path (D1-FX13 at 08:00 New York): passive-first adds about 0.05–0.15 bp a side.**
- On EUR/USD and USD/JPY, every realistic policy's 95% interval lies below zero: any resting order, and the chase
  at 0.5 s.
- Only a zero-latency chase shows a hair of saving, +0.03–0.04 bp, and no retail order path reacts inside one
  tick.
- Market orders stay.

## 3. How to measure it on the demo after the cutover (no orders, no engine change)

The runtime already logs every venue tick: `data_log.jsonl`, `MARKET_STATE`, `data.log_sample_rate: 1`. The study
script now reads that file directly.

- **M1 — what a market order really costs.**
  - For each `FILL`: side × (fill price − venue mid at the order's `SUBMIT`) / mid, taking the mid from the last
    `MARKET_STATE` at or before the submit, plus the deal's commission.
  - Expect about half the venue spread (0 on EUR/USD, ~0.08 bp on USD/JPY) plus slippage near 0, plus 0.27–0.30 bp
    of commission.
  - Weekly, by pair. It feeds E-4.
- **M2 — the shadow passive record.**
  - Weekly, on the compute server, from that week's `data_log.jsonl`: `python scripts/execution_passive_study.py
    --demo data_log.jsonl --out shadow_<week>.json`, reading the `pepperstone_demo / d1_0800ny` rows for all 13
    pairs.
  - The t3.small has 2 GB of RAM, too little for a 4-week tick load; one week is about 10 M ticks.
  - Four weeks give ~20 slots × 13 pairs.
  - **Pre-declared decision rule:** reopen passive-first only if the chase at 0.5 s and one tick through shows a
    mean saving of at least +0.05 bp a side, with its 95% interval above zero, over at least 8 weeks pooled across
    the 13 pairs. Otherwise E-1 stands for good.
- **M3 — the commission per deal.**
  - ACIS-13 §4, §7.3 step 7 and §9 specify a `VENUE_COSTS{commission, swap, …}` event, but no code emits it
    (report §6.1).
  - Lead: build it before or at the cutover, so the first deals' costs are on the record. Until then, M1 takes
    the commission from the venue's deal list at reconcile.
- **M4 — the venue's gold and US500 spreads.**
  - The target path streams only the 13 FX.
  - A read-only spot probe (in the style of `scripts/ctrader_probe.py`; owner-run, because it authenticates)
    for XAUUSD and US500 over 10 trading days would settle the venue's cost for gold. It would sample 02:00,
    08:00 and 11:00 New York for gold and 15:30 and 16:00 ET for US500.
  - This is the input any GOLD-EW revival needs (report §5).
- **M5 — keep the evidence.**
  - At 13 pairs the data_log grows ~0.5–0.8 GB a day, so the 30 GB AWS disk fills in ~5–8 weeks.
  - Rotate it (archive, never delete; GAP-P12D-138) before the measurement window starts.

## 4. Risks of passive-first, if it is ever reopened

- **Adverse selection.** Measured: fills are followed by moves against them, −0.02 to −0.30 bp within a minute at
  08:00 New York and −0.45 to −0.67 bp at 15:00 London. The order fills when it should not, and misses when it
  should fill.
- **Missed fills on trend days.** A miss pays the deadline's price. For a signal-driven entry the expected cost
  also includes the signal's own drift times the wait (optional stopping): small for D1, ~0.06 bp a trade for
  IMOM. A momentum family is hurt exactly on its best days.
- **Venue rules.**
  - Pepperstone fills a triggered limit "as a market order", with slippage either way.
  - cTrader limits can part-fill (the policy's Appendix II), which leaves a remainder to manage.
  - GTD expiry races the engine's own deadline.
  - In gaps the venue may give "the next best price".
- **Engineering.**
  - `LIMIT` is a new declared capability: ACIS-06 conformance says a declared capability must work.
  - Pending orders become state the venue holds across restarts: a new reconcile path and a new §13 glitch class.
  - The disaster stop must attach to a pending order. An absolute `stopLoss` is allowed on LIMIT, but the
    relative-stop path is MARKET-only today.
  - The `clientOrderId` and label mapping must cover pending orders.
- **Request budget.** A9 measured 4 requests a round trip. Rest, cancel or amend, then the fallback, add 2–3 a
  side, so `max_orders_per_day` would fall from 35 to about 20 at today's budget.
- **Prop rules.** None forbid limits. A sub-second cancel-and-replace pattern (the chase) could, however, read as
  latency-sensitive trading to FTMO's or E8's monitoring. Unverified.

## 5. Spec sections an adoption would amend (for completeness; not recommended)

- **Master §5 C8:** a passive fill pays no half-spread, but pays its selection. The single cost model would need
  a passive path, and the passive-fill model (`tests/backtest/passive_fill.py`) would become part of the graded
  world.
- **ACIS-05 §6.4, "Execution clock":** "orders execute at the instrument's slot" would become "rest from the slot
  for W, then market", plus the deadline rule.
- **ACIS-13:** §5's descriptor (`order_types` gains `"limit"`), §7.3 (the LIMIT open, GTD, `stopLoss`, partial-fill
  remainder), §6.5 A9 (requests per round trip), and §14's conformance cases.
- **ACIS-06:** conformance for the new capability.
- **Master §13:** pending orders across a restart, and a partially filled limit.
- **Master version:** the next amendment, v2.36.

**E-4 alone** (the venue commission in C8) amends `config/instruments.yaml`'s `costs` (not a guardrail file) and
changes the cost map's hash. The owner rules whether it applies to new looks only, which is the natural reading
of the register's sticky declarations.

## 6. Questions for the owner (one grouped ask, for the lead to raise)

1. **E-1 and E-2:** keep market orders and record passive-first as rejected for CFD venues? (Recommended.)
2. **E-4:** add Pepperstone's commission to C8 for FX ($3 a lot a side) and gold ($3.50), for new looks only, and
   re-estimate the slippage constant from the demo's fills after 4 weeks? (Recommended.)
3. **GOLD-EW at the venue's cost:** run M4 (a read-only spot probe with the app credentials, 10 trading days)?
   If the venue's gold spread at 02:00 and 11:00 New York is near its published $0.18, the lead could propose a
   new family "GOLD-EW at venue cost", kill-only on 2019–2023, with credit only forward. Its ex-ante Sharpe is
   ~0.3–0.4 against the halved thesis gross, and ≤ 0 against its own 2017–18 years.
4. **M3:** build the missing `VENUE_COSTS` log before the cutover? (Lead's call; it is ACIS-13 as written.)
5. **M5:** rotate the data_log before the cutover? (GAP-P12D-138's 0.26 GB a day was measured on 2 pairs; on 13
   it is ~2–3× that.)
6. **Lever 2:** passive execution pays only on an exchange queue. If the owner ever reopens a futures venue, this
   study should be re-run there on trade data.
