# Passive-first execution at ACIS's slots: what it saves (EXECUTION agent, 2026-10-03/04)

The owner launched three agents on 2026-10-03 ("run agents to fix our edge problems … we want this machine trading
money"). This is EXECUTION's report; the proposal is `archive/EXECUTION_PROPOSAL_2026-10-03.md`. A finder, not a
clearer: nothing here changes the engine, a guardrail, the register or the ledger. No look was run, no family's
P&L was read, and nothing after 2023-12-31 was touched. Written by claude-opus-5-5. Sources are graded a
(primary or our own data), b (secondary) or c (unverified).

## 0. The answer

**Passive-first saves nothing at ACIS's slots on a CFD venue. It adds cost.** On five years of Dukascopy ticks,
and on the demo's own Pepperstone ticks, a limit order resting at the touch or the mid, with a market fallback,
is worse than an immediate market order at every daytime slot measured.
- At D1's 08:00 New York slot it costs 0.11–0.21 bp more per side on EUR/USD, USD/JPY, GBP/USD and gold.
  AUD/USD saves +0.07 ± 0.06, which is not significant.
- At FXHEDGE's 15:00 London slot (10:00 New York, a US-data minute) it costs 0.56–0.86 bp more.
- On US500 at IMOM's 15:30 and 16:00 ET it costs 0.34–1.34 bp more.
- Carver's own rule, which crosses the spread as soon as the market moves away, shows a small saving only if it
  can react within the same tick. At the demo's measured round trip of about 0.5 s that saving is gone: −0.06 to
  +0.05 bp per side at D1's, the 15:59 and GOLD-EW's slots, −0.22 to −0.37 at 15:00 London, and −0.33 / −0.60 on
  US500.

**Why.** The practitioners' "earn the spread" (Carver: a tenth of the spread on futures through IB) needs a
queue: an exchange where a resting bid fills when someone sells to it. Pepperstone is the sole counterparty. A
buy limit is executed at the venue's ask once that ask reaches the limit, and limits are "triggered as market
orders" (§1).
- That makes a CFD limit a timing option on the venue's own quote.
- On a martingale, such an option is worth exactly zero (optional stopping:
  `test_on_a_martingale_the_venues_touch_rule_saves_nothing_and_one_tick_through_loses`).
- At ACIS's slots, quotes keep moving after they touch the limit (adverse selection), so the option is worth
  less than zero.
- On the venue the EUR/USD spread is 0.0 on 86% of ticks, so there is no spread left to save. Its round trip is
  the $6-a-lot commission, which no order type avoids.

**Consequence.** No killed family clears costs through passive execution. One family's arithmetic does change,
because of the venue's market-order cost rather than its order type. GOLD-EW was dropped ex ante on a C8 gold
round trip of about 3.3–3.7 bp. Pepperstone publishes an average gold spread of $0.18, plus a $0.07 round-trip
commission per ounce: about 1.0–1.4 bp, roughly 2.4× cheaper than C8 (§5). That revival is a new family for the
lead to weigh, and only after the venue's gold spread is measured at 02:00 and 11:00 New York.

## 1. Venue facts

**Pepperstone, cTrader Razor (the demo venue)**

| Fact | Value | Grade, source |
|---|---|---|
| Commission | FX $6 and XAU/USD $7 per lot round trip, fixed | a: pepperstone.com support, "What commissions do I pay on trades" |
| Commission, as the venue sends it | EURUSD and USDJPY: `preciseTradingCommissionRate` 300000000 (3.00), `commissionType` 2 (USD per lot), so $3 a lot a side. This is 0.27 bp a side on EUR/USD at 1.12 and 0.30 bp on USD/JPY. | a: the demo's symbol frames, `logs/ctrader_probe_20261001T104403Z.json` on acis-demo-1 |
| Minimum distance | `slDistance` 0, `tpDistance` 0 (`distanceSetIn` 1, points). The policy also lists no "level restrictions on stop & limit orders" for cTrader. | a: the same frames, and the policy's Appendix II |
| Lots | 0.01-lot minimum and step (`minVolume` = `stepVolume` = 100000 cents); 100,000 units a lot | a: the same frames |
| Who fills | "we act as principal at all times and not as agent … Pepperstone Markets is the sole counterparty … the sole Execution Venue" | a: Pepperstone SCB Order Execution Policy (ROW), October 2022, §10.1. The Kenyan entity's own policy was not fetched, so its applicability is b. |
| How a limit fills | "Limit Orders: … once the price of an instrument reaches a pre-set level … triggered as market orders." "'Buy Limit' … executed at the Ask price; 'Sell Limit' … at the Bid price." For cTrader limit orders, Appendix II gives: Execution: Market Order; Slippage: "Yes (positive, or negative); or No slippage"; Partial fills: Yes. | a: the same policy, §5.2 and Appendices I–II |
| Gaps | "it may not be possible for us to execute pending orders at the Declared Price … we reserve the right to … provide the next best price" | a: the same policy |
| Expiry | GTC; GTD for cTrader pending orders ("deleted by the system" when not triggered in time) | a: the same policy |
| cTrader's rule | a buy limit enters "only if the ask drops to that level (or lower)" | a: help.ctrader.com, "Orders" |
| Published spreads | XAUUSD Razor average 0.18 and minimum 0.05, from July 2024 data. The page labels these "pip"; they are read as dollars an ounce, the only plausible reading against a 0.05 minimum. The same page says "no commissions" on gold, which contradicts the support page; the $7 is used here. US500 average 0.4 points, no index commission. | b: pepperstone.com/en/go/gold-spread-cut. c: US500, a search rendering of Pepperstone's pricing via tradingbeasts.com. |

**Measured on the demo's own feed** (a). These are the old engine's `MARKET_STATE` ticks: 402,469 of them,
2026-10-01 11:55 to 10-02 20:55 UTC, read-only from `data_log.jsonl`.

| | EUR/USD | USD/JPY |
|---|---|---|
| Median spread, each daytime hour 00–19 UTC | **0.000 bp** (the mean is 0.004–0.058 bp) | 0.127–0.190 bp |
| Ticks quoting a 0.0 spread | 138,752 of 161,129 (86%); 78–97% in each daytime hour | 4,074 of 241,340 (2%) |
| 21:00 UTC (17:00 New York, the rollover) | median **3.7 bp**, p90 6.7 | median **1.96 bp**, p90 5.9 |

The old engine's 17 market fills (0.01 lot, `system_log.jsonl`):
- Submit to fill took 0.30–0.55 s in 9 cases and about 3.4 s in 8. The 3.4 s cases are probably the open
  waiting for its stop's confirmation (`stop_confirm_timeout_s: 3`; not verified).
- The 13 daytime fills' slippage against the engine's requested price averaged **+0.007 bp** (range −0.22 to +0.32).
- The 4 fills at 21:07–21:19 UTC paid **1.78–2.98 bp** (mean 2.39): the rollover.

**The prop targets**
- **FTMO:** forex $5 a lot, metals 0.0014% of volume, indices no commission (c: investing.com's FTMO review; the
  ctrader.com prop page says the same). Whether the $5 is per side or round trip was not confirmed on FTMO's own
  page, whose symbol table loads dynamically. Its accounts are simulated, so fills follow the same CFD rule.
- **E8 Markets:** two pricing options, spread-only or raw spread plus $5 a lot, with swap-free available on E8 One
  (c: proptradingvibes.com, propfirmmatch.com). The spread-only example is EUR/USD at 1.2 pips, about 1.0 bp per
  round trip, roughly twice Pepperstone's all-in cost. On a spread-only principal venue the spread is the whole
  cost, and a CFD limit still cannot capture it, for the reason in §4.

## 2. Method

**The model** is `tests/backtest/passive_fill.py`, with 11 tests in `tests/backtest/test_passive_fill.py`.
- A buy arriving at t0 rests a limit at the bid ("touch") or at the mid, rounded onto the venue's tick grid away
  from the market.
- It fills at its limit, never better, at the first quote in (t0, t0 + window] whose ask is at or below it. That
  is the venue's rule, `through 0`. The stricter variant requires the ask one tick below it (`through 1`),
  allowing for the venue's feed not being Dukascopy's.
- If it has not filled by the deadline, it pays the deadline's ask.
- A sell mirrors the buy.
- **The rules tested:**
  - **chase** is Carver's adverse-move rule: cross as soon as the near quote moves away. Its market order lands
    `react_ms` later: 0, 0.5 s as on the demo, or 3 s stressed.
  - **delay** rests nothing. It is the deadline's market order alone, a control that separates spread timing
    from the limit.

**The saving** is side × (market price at the benchmark − price paid), in bp of the arrival mid.
- This is the whole P&L difference at any common mark after the deadline, because both orders then hold the
  same position. The post-fill drift is therefore a diagnostic of adverse selection, not an extra cost.
- An entry is benchmarked against the market order at its slot.
- An exit rests one window before its deadline and is benchmarked against the market order at the deadline.

**P&L-blind.** Every slot of every day runs a buy AND a sell, so the market's drift cancels and no family's
direction is read. A real signal adds one more cost, its own drift times the expected wait (optional stopping).
That cost is negligible for a daily rule and about 0.06 bp a trade for IMOM (§5).

**Uncertainty.** The day is the unit (its buy and sell averaged), and ± is one standard error across days. Each
cell is also reported by year (the JSON's `by_year`). On the demo feed the unit is the clock hour.

**The slots:**
- D1: 08:00 New York (FX and gold).
- FXHEDGE: 15:00 London entry and 15:59 London exit.
- GOLD-EW: 02:00 and 11:00 New York, each as an entry and as an exit.
- IMOM: 15:30 ET entry and 16:00 ET exit, on US500.
- 17:00 New York, as a diagnostic: D1 decides at 17:02 but executes at 08:00.

**The data:**
- Dukascopy ticks: EUR_USD, USD_JPY and XAU_USD for 2019–2023; GBP_USD and AUD_USD for 2021–2023. That is 2.8 GB
  uploaded, and only these subsets.
- Dukascopy 1-minute BID/ASK candles for US500, 2019–2023, with the owner's quoted-minute rule. The order of
  events inside a minute is unknown, so a fill is stamped at the minute's end, and a chase whose trigger shares
  a minute with a fill counts as the trigger.
- The demo extract above, run at the same slots plus an arrival every minute ("demo_day", outside 20:00–23:00
  UTC).

## 3. Results (saving per side, bp; positive means cheaper than a market order at the slot)

Run `study_2019_2023_4a9e9b1.json` (commit `4a9e9b1`, 2,503,490 simulated orders, 1,540 cells; sha256 `43be1506…ad5cf996`).
The columns: the resting touch for 5 minutes under the venue's rule and one tick through, the mid, Carver's chase
at the demo's 0.5 s, and the delay control.

| Slot | Instrument | Days | Median spread | Touch 5 min | Touch 5 min, 1 tick | Mid 5 min, 1 tick | Chase 5 min @0.5 s | Chase @0.5 s, 1 tick | Delay 5 min | Delay 30 min |
|---|---|---|---|---|---|---|---|---|---|---|
| **D1 08:00 NY** | EUR_USD | 1,298 | 0.27 | −0.12 ± 0.03 | −0.17 ± 0.03 | −0.21 ± 0.03 | −0.04 ± 0.00 | −0.06 ± 0.00 | 0.00 | −0.13 ± 0.01 |
| | USD_JPY | 1,298 | 0.28 | −0.14 ± 0.03 | −0.22 ± 0.03 | −0.23 ± 0.03 | −0.02 ± 0.00 | −0.04 ± 0.00 | 0.00 | −0.20 ± 0.01 |
| | GBP_USD | 779 | 0.66 | −0.11 ± 0.06 | −0.17 ± 0.06 | −0.21 ± 0.06 | −0.01 ± 0.01 | −0.02 ± 0.01 | +0.01 | −0.23 ± 0.02 |
| | AUD_USD | 779 | 1.53 | +0.07 ± 0.06 | −0.03 ± 0.06 | −0.11 ± 0.05 | +0.00 ± 0.02 | −0.03 ± 0.02 | −0.01 | −0.31 ± 0.02 |
| | XAU_USD | 1,289 | 1.91 | −0.21 ± 0.09 | −0.24 ± 0.09 | −0.36 ± 0.08 | −0.03 ± 0.02 | −0.04 ± 0.02 | +0.01 | −0.24 ± 0.01 |
| **FXHEDGE 15:00 LDN** | EUR_USD | 1,297 | 0.28 | −0.56 ± 0.07 | −0.64 ± 0.07 | −0.65 ± 0.07 | −0.23 ± 0.03 | −0.25 ± 0.03 | +0.03 | +0.03 |
| | USD_JPY | 1,297 | 0.37 | −0.77 ± 0.08 | −0.82 ± 0.08 | −0.86 ± 0.08 | −0.32 ± 0.04 | −0.33 ± 0.04 | +0.06 | +0.07 |
| | GBP_USD | 778 | 0.72 | −0.56 ± 0.11 | −0.62 ± 0.11 | −0.65 ± 0.10 | −0.22 ± 0.04 | −0.22 ± 0.04 | +0.08 | +0.08 |
| | AUD_USD | 778 | 1.60 | −0.63 ± 0.14 | −0.75 ± 0.14 | −0.85 ± 0.13 | −0.35 ± 0.06 | −0.37 ± 0.06 | +0.11 | +0.13 |
| **FXHEDGE 15:59 exit** | EUR_USD | 1,298 | 0.27 | −0.20 ± 0.04 | −0.25 ± 0.04 | −0.28 ± 0.04 | −0.04 ± 0.00 | −0.06 ± 0.00 | 0 | 0 |
| | USD_JPY | 1,298 | 0.28 | −0.19 ± 0.04 | −0.25 ± 0.04 | −0.27 ± 0.04 | −0.04 ± 0.00 | −0.05 ± 0.00 | 0 | 0 |
| | GBP_USD | 779 | 0.65 | −0.16 ± 0.07 | −0.23 ± 0.07 | −0.20 ± 0.05 | −0.04 ± 0.01 | −0.06 ± 0.01 | 0 | 0 |
| | AUD_USD | 779 | 1.50 | −0.22 ± 0.09 | −0.36 ± 0.09 | −0.35 ± 0.08 | −0.02 ± 0.02 | −0.04 ± 0.02 | 0 | 0 |
| **GOLD-EW 02:00 NY** entry | XAU_USD | 1,290 | 2.06 | −0.08 ± 0.06 | −0.12 ± 0.06 | −0.24 ± 0.06 | +0.00 ± 0.01 | −0.00 ± 0.01 | +0.02 | +0.05 |
| 02:00 exit | | 1,290 | 2.02 | −0.00 ± 0.05 | −0.03 ± 0.04 | −0.08 ± 0.04 | +0.05 ± 0.02 | +0.04 ± 0.02 | 0 | 0 |
| **11:00 NY** entry | | 1,289 | 1.91 | −0.10 ± 0.08 | −0.16 ± 0.08 | −0.29 ± 0.08 | +0.01 ± 0.02 | +0.00 ± 0.02 | 0.00 | +0.01 |
| 11:00 exit | | 1,289 | 1.90 | −0.05 ± 0.08 | −0.07 ± 0.08 | −0.14 ± 0.06 | +0.00 ± 0.02 | −0.00 ± 0.02 | 0 | 0 |
| **IMOM 15:30 ET** entry | US500 (candles) | 1,249 | 1.30 | −0.34 ± 0.10 | −0.62 ± 0.10 | −0.66 ± 0.09 | −0.33 ± 0.04 | −0.34 ± 0.04 | 0.00 | −0.01 |
| 16:00 ET exit | | 1,249 | 1.30 | −1.01 ± 0.14 | −1.34 ± 0.15 | −1.25 ± 0.13 | −0.60 ± 0.05 | −0.60 ± 0.05 | 0 | 0 |
| Rollover 17:00 NY (diagnostic) | EUR_USD | 1,035 | 1.59 | −0.03 ± 0.03 | −0.05 ± 0.03 | −0.11 ± 0.03 | −0.29 ± 0.03 | −0.30 ± 0.03 | −0.12 | **+0.21 ± 0.02** |
| | USD_JPY | 1,029 | 2.00 | −0.35 ± 0.04 | −0.36 ± 0.04 | −0.42 ± 0.04 | −0.38 ± 0.03 | −0.39 ± 0.03 | −0.37 | **+0.26 ± 0.03** |
| **Demo feed (Pepperstone)**, every minute outside 20–23 UTC | EUR_USD | 29 hours | 0.00 | −0.07 ± 0.02 | −0.12 ± 0.02 | −0.13 ± 0.02 | −0.06 ± 0.00 | −0.06 ± 0.00 | 0.00 | 0.00 |
| | USD_JPY | 29 hours | 0.19 | −0.06 ± 0.02 | −0.14 ± 0.02 | −0.12 ± 0.02 | −0.01 ± 0.00 | −0.03 ± 0.00 | 0.00 | 0.00 |

**Readings:**
- **Fill rates are high and still lose.** A 5-minute touch fills 50–91% of the time at the daytime slots. Its
  fills are followed by adverse moves: the mean post-fill drift at 08:00 New York is −0.02 to −0.30 bp within a
  minute, and −0.45 to −0.67 bp at 15:00 London. Its misses pay the move away.
- **Stable by year.**
  - At D1's slot, EUR/USD's touch was negative in all five years (−0.06 to −0.19).
  - USD/JPY's touch was negative in four of five (−0.15 to −0.23; 2023 was +0.02).
  - The chase at 0.5 s and one tick through was negative in every year on EUR/USD, USD/JPY, GBP/USD and AUD/USD.
- **The best of 40 policies is selection-biased upward and still small.** At D1's slot, a zero-latency chase
  reaches +0.03 to +0.04 bp on EUR/USD and USD/JPY, +0.09 on GBP/USD, +0.14 on AUD/USD and +0.15 on gold. Every
  one of these is gone at the 0.5 s the demo measured. The edge exists only for a reaction inside one Dukascopy
  tick, which no retail order path achieves.
- **Waiting helps only at the rollover.** There a 30-minute touch saves +0.51 to +0.83 bp, and the plain 30-minute
  delay +0.05 to +0.26. That is spread timing at a 3–5× spread, which the target path already avoids by
  executing at 08:00 New York.
- **The demo's own D1 slot.** Two days per pair, too few to read alone. The every-minute arrivals agree with
  Dukascopy: EUR/USD loses even at the venue's own rule, because its quoted spread is zero.

## 4. Why a CFD limit cannot earn the spread

- **The venue is the counterparty.** A buy limit fills when the venue's ask reaches it. Its expected price is
  therefore the venue's ask at a stopping time.
- **On a martingale that is the arrival ask** (optional stopping), so the saving is 0, whatever the stopping
  rule: touch, mid or chase. The unit test pins this for the touch and the chase.
- **A saving needs one of three things:** a mid that mean-reverts on the window's scale, a spread at arrival
  wider than at the fill, or avoided slippage.
- **At ACIS's slots the mid trends after a touch.** 08:00 New York sits before the 08:30 releases, and 15:00
  London is 10:00 New York, so the first effect is negative. The second appears only at the rollover. The third
  is about 0 on Pepperstone: the old engine's daytime fills averaged +0.007 bp.
- **Carver's 80% cut is real but belongs to another market structure:** futures through IB, a resting order in a
  queue, plus an order-book imbalance rule we cannot run (we have no depth data). It transfers only if ACIS ever
  trades an exchange venue (Lever 2).

## 5. Ex-ante family economics (P&L-blind; the ledger's grosses plus these costs)

These use the ledger's own numbers (GAP-P12D-158). IMOM's gross per trade comes from its 1× and 2× results:
1.265 Sharpe per 2.1 bp, so 1 bp ≈ 0.60 Sharpe, and a gross of +0.55 Sharpe ≈ 0.91 bp a trade. The paper's
2.7 bp, halved for publication, is 1.35 bp.

| Family | Its cost problem | With passive (measured) | With the venue's market-order cost | Clears ex ante? |
|---|---|---|---|---|
| **IMOM** (killed −0.72) | C8 round trip 2.1 bp (1.86 at 2019–23 prices) against ~0.9 bp gross | **Worse.** Entry −0.34, exit −1.01 (touch) or −0.33 / −0.60 (chase), which adds 0.9–1.35 bp. Its momentum drift costs another ~0.06 bp over a ~2-minute wait. | A 0.4-pt spread, no commission. At the 2019–23 level (~3,900): 1.0 bp + C8 slippage 0–0.56 bp, so net −0.7 to −0.1 bp a trade (history gross) or −0.2 to +0.3 (half the paper's). At today's ~6,800: 0.59 bp + 0–0.32, so net 0.0 to +0.3 (Sharpe ≈ 0 to +0.2) or +0.4 to +0.8 (≈ +0.25 to +0.45). | **No.** Below the 0.5 "first win" at best, and not through execution. |
| **GOLD-EW** (dropped ex ante, no look) | Combo trades ~1,008 sides a year; C8 ≈ 1.7–1.9 bp a side, ~18.8%/yr, against a gross that had decayed (22.4%/yr 2013–18; 2017 +5.1%; 2018 −4.3%) | **No help.** Touch −0.0 to −0.24 a side (adds 0–2.4%/yr); chase @0.5 s −0.00 to +0.05 (±0.5%/yr). | Pepperstone's published $0.18 spread + $0.07 commission ≈ $0.125 an ounce a side: 0.71 bp at $1,750 (7.2%/yr), 0.52 bp at $2,400 (5.3%/yr). Net against the halved thesis gross (11.2%): about +4 to +6%/yr, Sharpe ~0.3–0.4 at gold's ~15% volatility (approximate). It is negative against the thesis's own last two years. | **Not through passive.** Cost alone no longer kills it ex ante at the venue's published price, but decay may. A revival is a NEW family, kill-only on 2019–2023 (the ledger's clean window), and only after measuring the venue's gold spread at 02:00 and 11:00 New York (proposal M4). |
| **FXHEDGE** (killed −0.35 on the holdout) | Not cost: cost took 22% of the expected gross | **Worse.** −0.56 to −0.77 at 15:00 London, the US 10:00 releases | Venue commission adds 0.5–0.6 bp a round trip to C8's 0.6–0.95 | No |
| **D1-FX13** (the demo's family) | Not binding (0.165 at 1×, 0.156 at 2×) | Worse: −0.11 to −0.14 a side (touch), −0.02 to −0.04 (chase @0.5 s) | ≈ C8 on EUR/USD (0.55–0.6 bp against 0.62), above it on USD/JPY (0.73–0.79 against 0.61) | — keep market orders |
| GOTOBI (shadow) | Not binding (1.54 at 2×) | Not measured: its 03:00 and 09:54 JST slots were outside this brief | — | — |

## 6. Other findings for the lead (each to be verified before it binds)

1. **`VENUE_COSTS` is specified but never emitted.**
   - ACIS-13 §4 ("Venue costs are not a `FillReport` field"), §7.3 step 7 and §9 (`trade_log`) require each
     deal's commission and swap to be logged as `VENUE_COSTS`.
   - No code in `core/`, `scripts/` or `monitoring/` writes that event: `grep -rln VENUE_COSTS core scripts
     monitoring tests` returns nothing. The only commission code is `ctrader_account.py`'s equity haircut.
   - The forward cost check that GAP-P12D-141 and GAP-P12D-159 PCE-05 own needs those numbers from the
     cutover's first deal.
2. **C8's FX totals are about right; their split is not.**
   - At 08:00 New York, C8 charges about 0.62 bp a round trip on EUR/USD and USD/JPY: the Dukascopy spread
     plus 2 × 0.17–0.18 bp of slippage, with 0 commission.
   - Pepperstone charges ~0.55–0.6 bp on EUR/USD and ~0.75 bp on USD/JPY, mostly commission, with fills at the
     quote.
   - Gold and US500 are another matter: C8 is about 2.4× and 1.8× the venue's published averages at 2019–23
     prices (§1).
3. **The data_log at sample rate 1 on 13 pairs.**
   - The demo wrote about 175 MB in 33 trading hours for 2 pairs.
   - At 13 pairs that is ~0.5–0.8 GB a day, 2–3× GAP-P12D-138's 0.26 GB a day.
   - The 30 GB AWS disk could then fill in about 5–8 weeks after the cutover, not two months.
   - The measurement plan below relies on these logs, so rotation (archive, never delete) comes first.
4. **GAP-P12D-148 T4 ("passive-first … cost −25 to −40%") does not hold on this venue class.** Record it as
   rejected for CFD venues and valid only for an exchange queue.

## 7. Limits and what could overturn this

- **The demo feed is short** (33 hours, 2 pairs), and only 2 of its days include an 08:00 New York slot. The
  post-cutover data (13 pairs) answers this (proposal M2).
- **Dukascopy is not the venue's feed.** The venue rule (`through 0`) and the conservative rule (`through 1`)
  bracket the mismatch, and both lose.
- **The fills are, if anything, optimistic for the venue.** The model fills at the limit, never worse, but
  Pepperstone's cTrader limits can slip negatively. A chase's cancel request and a fill racing it are not
  modelled.
- **US500 uses 1-minute candles.** Within-minute order is unknown and a fill is stamped at the minute's end. A
  tick test on US500 would sharpen the IMOM row; it cannot turn the 15:30 sign, which is negative under every
  policy.
- **GBP/USD and AUD/USD cover 2021–2023 only.**
- **No signal was read.** For a signal-driven order, a resting limit also pays the signal's drift during the
  wait. That cost is small at these waits (seconds to ~2 minutes) and only adds to the loss.

## 8. Reproduce

- **Code** (branch `worktree-agent-ab9b420454c98800c`):
  - `tests/backtest/passive_fill.py` (151 lines),
  - `scripts/execution_passive_study.py` (234 lines),
  - and their 17 tests, all passing on acis-compute-1 together with the A12 module-budget ratchet.
- **Command** (30–60 s on 16 vCPU): `python scripts/execution_passive_study.py --ticks <ticks> --minutes
  <minutes> --demo exec_ticks.csv.gz --demo-every-minute --start 2019-01-01 --end 2023-12-31 --workers 16
  --out <json>`.
  - `--end` past 2023-12-31 is refused (`test_the_study_refuses_to_read_the_sealed_holdout`).
  - The run above was made at `4a9e9b1`, where the every-minute arrivals were always on. The later commit
    only adds the flag and the `data_log.jsonl` reader.
- **Inputs and outputs:**
  - `gs://acis-compute-0929-data/agents/execution/`: `ticks/` (the subsets in §2), `minutes/USA500IDXUSD/`,
    `demo/exec_ticks.csv.gz` and `demo/exec_fills.json` (read-only extracts of the demo's logs: bid, ask, time;
    fills; no secrets), and `out/study_2019_2023_4a9e9b1.json`.
  - The same files are on acis-compute-1 at `/opt/acis/xdata`.
- **The demo host.** It was only read: four small scripts in `/tmp` were run, and they and their outputs were
  removed. The engine, its tmux session and its secrets were not touched. Its heartbeat was fresh at 21:33 UTC
  on 2026-10-03 (`practice`, 0 positions).
