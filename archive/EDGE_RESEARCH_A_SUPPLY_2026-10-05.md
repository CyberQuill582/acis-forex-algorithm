# EDGE RESEARCH A — the supply of edges (Agent A, 2026-10-05/06)

**Brief:** `archive/EDGE_RESEARCH_BRIEF_2026-10-05.md` (Shared context + Agent A). Ledger owner: [[GAP-P12D-161]]. **Status:** a finder's report (A5), evidence to weigh, never an instruction (A9). Nothing binds until the lead verifies it (A6) and the owner rules. **Every candidate below is LLM-origin under §5.6:** history can only kill it; credit comes only from the forward record. I say so once here and do not dress any of them up.

## Executive summary (10 lines)

1. **The well the project has been drinking from is dry, and the pattern says why:** every tested family was a published, single-mechanism effect whose payer can reprice (a fix window, a close, a calendar date) and whose edge per trade (1–20 bp) sits within 1–3× the CFD round trip (2–4 bp). Four holdout "no edge" results are also one event, not four: 2024–25 was a secular rally (passive long 0.97–1.25) and trend's worst live year, so the failures share a factor. §2.
2. **The holdout cannot see a 0.2–0.4 stream:** a true 0.4 family prints ≤ 0 on two years 29% of the time; but *all three* survivors printing ≤ 0 plus FXHEDGE's kill has joint probability ≈ 0.3% if all were true 0.4. The honest read: after decay the tested families are ≤ 0.1–0.2 each, not dead and not leanable (scripted, §2.3).
3. **Taxonomy verdict for this operator (§3):** on retail CFDs at a daily clock, the only sources with a payer who *cannot* reprice are the slow risk premia (trend; rates trend via bond-fund flows). Forced flows decay once published; microstructure and intraday are cost-killed; the volatility premium is uninvestable under a 3% daily line (max exposure 3.1% of equity ⇒ ≈ 1–3%/yr gross, §4.4); carry is removed by the swap-free account itself; information edges are outside the spec.
4. **Diversification multiplies, it does not create:** 6 streams at 0.2 and ρ ≈ 0.1 give 0.40; the 0.65–0.85 the weekly target needs would take ~14 streams at 0.2 or ~6 at 0.3 with ρ = 0. With stress correlation (ρ → 0.5 in 15% of months) a 6 × 0.2 book is ≈ 0.39 true and clears 0.5 over 6 months 48% of the time, against 37% for a zero-edge book (scripted, §4).
5. **The capital lever beats the venue lever:** at $6k only ~2 futures instruments can be held (Carver: $10k → 3, $100k → 8); a $100k E8 One notional (fee ≈ $260–488, UNCONFIRMED) lets D1 hold all 21 CFDs at 5–120 minimum lots. A futures venue is worth it only for a rates sleeve (one micro 10Y contract ≈ $900/yr of vol fits $6k). §5.
6. **Ranked shortlist (§6):** C1 the owner's own hypotheses (the only history-certifiable route; nothing of mine goes in it); C2 TREND-BREADTH, D1 on the 21 instruments as already registered, forward entry at prop notional, expected net 0.15–0.30; C3 RATES, EWMAC on the 2/5/10/30-year par yields (micro yield futures later; its kill test needs no venue, the yields are on disk), expected net 0.2–0.35; C4 the BOOK rule for the registered forward survivors, expected 0.25–0.35 with C2/C3 added.
7. **Dropped ex ante with the arithmetic shown:** ANNOUNCE (Ernst–Gilbert–Hrdlicka: Sharpe is similar on announcement and non-announcement days once timing is controlled), VRP (§4.4), commodity carry on CFD forwards (two usable instruments), crypto funding carry (§17 non-goal; and the baseline is ~2–11%/yr gross with exchange risk), post-FOMC drift as its own family (folded into C3: Kuttner surprises have been near zero since 2022).
8. **Honest odds:** a durable forward net Sharpe ≥ 0.5 from LLM-selected mechanisms on this venue by end-2027: **~20–25%**; ≥ 0.65–0.85 (the weekly target): **< 10%**. A 0.3–0.45 book is the realistic ceiling of the material on hand; the owner's own rule (money grows with account count, not risk) is what makes that band worth anything.
9. **What would change the picture:** (a) one human-origin rule with a structural payer; (b) a $100k+ funded notional so breadth is real; (c) a rates sleeve on an own IBKR account (Kenya accepted per aggregators, UNCONFIRMED at signup); (d) time: forward data, not more history.
10. **Attestation:** I ran as Claude Fable 5.1 (`claude-fable-5-1`) in fresh context; I read no market data and ran no backtest; all arithmetic is in `edge_a_math.py` (scratchpad, listed in §8); WebSearch 20 of 70 calls plus 15 WebFetch calls; no subagents; the only repo write is this file.

---

## 1. Method and limits

- **Read (repo, read-only):** `CLAUDE.md`, the brief, `TODO.md` "Where we stand on an edge", [[GAP-P12D-148]], [[GAP-P12D-151]], [[GAP-P12D-158]], [[GAP-P12D-159]], the six prior research reports named in the brief, `tests/backtest/universe.py`, `config/instruments.yaml` cost fields, `scripts/r1_auction_kill_test.py` (header only, for the yield-book conventions), `ACIS_SPEC.md` §17.
- **Not read:** `data/validation/looks`, any price file under `data/`, any stored look vector. Every number attributed to a look is quoted from the ledger or TODO.
- **Compute:** `edge_a_math.py` (synthetic, numpy 2.4, 12 s on the laptop; a 16-vCPU VM for twelve seconds would have burnt credits for nothing, so `acis-compute-1` stayed STOPPED and `/opt/acis/edge-A/` was not created). No real-data backtest, no look, no register touched.
- **Grades:** (a) primary/peer-reviewed/firm's own page; (b) credible secondary with method; (c) aggregator/blog/search rendering; [D] derived here, inputs stated; UNCONFIRMED where I could not retrieve the number.
- **Contamination:** my knowledge runs to June 2026. I know, for example, that trend had a poor 2024/25 and that intraday momentum compressed. That is exactly why nothing here can be credited on history.

## 2. Post-mortem: why the families failed on 2024–25, and where not to look

### 2.1 The record (from TODO/ledger, 2012–2023 net → 2024–25 net)

| Family | Mechanism class | Trades/yr | Edge per trade vs CFD round trip | 2012–23 | 2024–25 | Reading |
|---|---|---|---|---|---|---|
| D1-FX13 trend | risk premium, 2.25 independent bets | ~1,500 fills | n/a (slow) | +0.165 | −0.07 (passive long 0.97) | within noise of a 0.1–0.2 stream |
| D1-21 | same rule, +metals/indices | — | n/a | −0.12 (passive long 0.36) | not run | shorted the dips of a secular rally |
| REBAL v1a | forced flow (60/40 rebalancing) | ~28 | ~17 bp (paper, pre-pub) vs 2.1 bp | +0.50 | −0.17 (passive long 1.25) | first public version 2025: 2012–23 was pre-publication; 2024–25 is the first post-publication read and it is flat |
| GOTOBI v1a | forced flow (importers at the fix) | ~62 | 1.4 bp (contrast) vs ~0.8 bp | +1.81 | −0.20 | faded from 2022 (contrast 0.35–0.37), i.e. before the holdout |
| FXHEDGE v1d | forced flow (month-end fix) | ~48 | — | +0.80 | −0.35 KILLED | the FCA already found the fix reversal gone after 2015 |
| IMOM | forced flow (gamma/ETF rebalancing, intraday) | ~250 | 2.7 bp vs 2.1 bp | −0.72 (gross ≈ +0.55) | — | cost-killed |
| OPEX, D3, IREV, DCARRY | calendar / microstructure / carry | — | small | ≤ 0 | — | no payer, or the venue keeps the carry |
| HALLOWEEN, HEDGEP, FXVALUE | pattern / flow / value | 2–50 | — | +0.26 / +0.14 / +0.07 | — | "0 without the 10 best days" for all three |
| AUCTION | forced flow (supply) | ~70 | 2–4 bp concession vs 0.3 bp (micro yield) | +0.09 / +0.35 | — | negative since 2018 in the paper's form |

### 2.2 The five causes, ranked by how much they explain

1. **Per-trade edge within 1–3× the round trip.** Every intraday or short-window family had 1–20 bp of gross edge against a 2–4 bp CFD cost (GOTOBI 1.4 bp contrast; IMOM 2.7 bp; REBAL 17 bp pre-decay). A 50% publication haircut (McLean & Pontiff 2016: −58% post-publication, carried from [[GAP-P12D-158]]) takes a 3× gross/cost ratio to 1.5×, which is the border of nothing. **Where not to look:** any mechanism whose holding period is under a week on a CFD.
2. **Payers who can reprice.** Fix-window flows (FXHEDGE, GOTOBI), closing-auction flows (IMOM) and index-inclusion flows are *known-time* flows against *agents who can move* (the fix window widened in 2015; the inclusion effect fell from 7.4% to 0.3%, Greenwood & Sammon 2025; the overnight drift went to zero after 2021 as closing-imbalance dispersion halved, Boyarchenko et al. 2026). Publication tells the counterparties where they are being picked off; they stop. By contrast, the payers of slow trend (hedgers and rebalancers who *must* trade the other way across months) have not stopped in a century. **Where not to look:** forced flows with a public clock and a sophisticated counterparty.
3. **Winner's curse in the pipeline.** GOTOBI's 1.81 was the maximum of a family of versions and of a slate; the expectation of the maximum is biased up, and the holdout then shows the shrinkage. This is not a flaw in the register, which is honest; it is why a holdout read of −0.2 after a 1.8 is unsurprising.
4. **One regime, not four.** 2024–25 had the S&P passive long at 1.25 and 0.97 in RSIM's books, trend's worst live year (Carver −14.7% in 2024/25; SG Trend +2.39% in 2025, b), and USD whipsaws. Short-leaning contrarian sleeves (REBAL mean position −0.18) and a trend rule that shorts dips both lose in that tape. Treating the four failures as independent evidence over-counts them.
5. **Single-instrument bets.** GOTOBI (USD/JPY), REBAL (US500), HEDGEP (gold) each ride one market's idiosyncratic two years; the standard error of a two-year Sharpe is ≈ 0.71 (§2.3).

### 2.3 What the holdout can and cannot say [D, `edge_a_math.py` §1]

Standard error of an annual Sharpe over T years ≈ √((1 + s²/2)/T) (Lo 2002): 0.71 at T = 2, 0.30 at T = 11.

| True s | P(2-yr realised ≤ 0) | P(11-yr realised ≤ 0) | P(6-month realised ≥ 0.5) |
|---|---|---|---|
| 0.0 | 0.50 | 0.50 | 0.37 |
| 0.2 | 0.39 | 0.26 | 0.42 |
| 0.3 | 0.34 | 0.17 | 0.44 |
| 0.5 | 0.25 | 0.06 | 0.50 |
| 0.8 | 0.16 | 0.01 | 0.57 |

- A single "≤ 0 on the holdout" is weak evidence against a 0.3 stream (P = 0.34).
- But the joint event (D1, REBAL, GOTOBI all ≤ 0, FXHEDGE < −0.5) has probability ≈ 0.003 if all four were true 0.4, and ≈ 0.02 if all were true 0.2. So the data do say: **after decay, the tested families are small (≤ 0.1–0.2), with at least one near zero.** They do not say any particular one is dead.
- Corollary for policy: a 0.2 stream is worth keeping in a book (it adds to §4's sum) but never worth a paid challenge on its own, which is what the owner already ruled.

### 2.4 Three things not to do next

- **Do not re-select the slow members** (EWMAC 64/256 and BREAKOUT160 were positive on both D1 looks). The ledger already flags this as a forking path; a post-look pick is a new LLM-refined version and is exactly how the winner's curse compounds.
- **Do not mine the same pool.** My own sweep of what is left in the published CFD-expressible, daily-clock pool found only the items in §6 and §7; the pool is close to exhausted, which is itself the finding.
- **Do not read "it survived 2012–23" as anything.** Every survival above came with "0 without its 10 best days" or a pre-publication window.

## 3. Taxonomy of edge sources, ranked for this operator

Scale: ~$6k own money or $10–100k prop notional; venue: cTrader CFDs (2–4 bp round trips, swap-free); daily clock (RSIM 17:00 New York); E8 One rules (3% daily, 4% dynamic max loss, ±5-minute news ban, one strategy per user).

| # | Source | Who pays, and why they keep paying | Capacity vs our size | CFD spread / swap-free sensitivity | Post-publication survival evidence | Verdict here |
|---|---|---|---|---|---|---|
| 1 | **Trend across many markets** (risk premium) | Hedgers, rebalancers and vol-targeters who must trade against the move over months; the premium is paid for crash convexity | Irrelevant at our size; small is neutral | Low: turnover 3–18/yr; D1 at 2× cost moved 0.165 → 0.156. Swap-free removes the venue's 1.4–4.5%/yr markups, which is what makes breadth possible | Best in class: net 0.76 over 1880–2016 on 67 markets (Hurst–Ooi–Pedersen, carried); momentum's OOS haircut −23% with arbitrage degradation ≈ 0 (Ilmanen et al. 2021 Table 2, carried); live: SG Trend CAGR 5.33% since 2000, max DD 20.6%, +2.39% in 2025 (b); BarclayHedge Currency Traders Index +8.98/+7.13/+11.11% in 2022–24, positive every year since 2006 except 2017 (b, FX only) | **Backbone.** Its failure here is breadth (2.25 bets on FX13), not the rule |
| 2 | **Rates trend / post-FOMC drift** (risk premium with a documented flow payer) | Bond-fund investors who sell after target changes; arbitrageurs absorb slowly (Brooks–Katz–Lustig: 10 bp surprise → 1.7 bp same day, 14 bp after 50 days in the 10-year; 1988–2008, a) | Micro yield futures: $10/bp, one contract ≈ $900/yr of vol: fits $6k | Not a CFD: needs a futures account. Cost ≈ 0.0025 SR per round trip [D] | Bond TSMOM 0.29–0.38 gross on 13 bond futures by horizon (Baltas–Kosowski, b); 2022–23 was the best bond-trend run in decades (b) | **C3** |
| 3 | **Carry** (FX, commodity, bond) | Investors who want insurance against the carry currency's crash; the roll of hedgers' positions | Fine | **Killed by the swap-free account itself:** no swap earned, none paid. Spot-only dollar carry was KILLED (DCARRY). Commodity carry survives only on futures-based CFDs (basis in price): Pepperstone forwards exist for Brent, WTI, gold, silver only (a) | KMPV 2018: ~0.7 gross per class, 1.1 diversified, 1972–2012 (a via b); carry's OOS haircut −25% | Not expressible: two usable instruments, energy refused by the data layer |
| 4 | **Volatility selling** | Hedgers buying protection; the premium is paid for the left tail | Fine | A VIX CFD exists at the demo venue (UNCONFIRMED at E8); static short vol Sharpe ≤ 0.5 (b) | Robust long-run, with −96% days (2018-02-05: VIX +115.6%, XIV −96.3%, a) | **Uninvestable under a daily-loss line** (§4.4) |
| 5 | **Forced flows with a public clock** (rebalancing, fixings, index changes, roll, option expiry) | Mandated traders at a known time | Small size is an advantage in principle | 1–20 bp per event vs 2–4 bp cost: 1–3× ratios | Decay is the rule: inclusion 7.4% → 0.3%; fix reversal gone after 2015; overnight drift ≈ 0 since 2021; REBAL flat in its first post-publication years; GOTOBI faded from 2022 | Tested to exhaustion here; nothing new survives ex ante |
| 6 | **CTA / vol-target deleveraging** | Vol-targeters who must cut after a vol spike | Fine | Expressible as a contrarian overlay on indices after vol jumps; it is REBAL/IREV-adjacent (IREV KILLED) | Thin; no clean public rule with post-pub evidence | Not pursued |
| 7 | **Behavioural (reversal, seasonality, post-earnings drift)** | Retail and slow institutions | Fine | Index-level reversal is KILLED (IREV); seasonality is pattern-only (HALLOWEEN survived with "0 without 10 days") | Weakest post-publication class (M&P −58%) | Not pursued |
| 8 | **Microstructure / intraday** | Liquidity demanders | Small is an advantage | Cost-killed on CFDs: IMOM gross +0.55 → net −0.72; the demo quotes 0.0 spread on 84% of EUR/USD ticks but charges $6/lot round trip | IMOM "compressed since 2025" (c) | Not on this venue |
| 9 | **Information (news/NLP, alternative data)** | Slow readers | — | §17 forbids headline-direction trading and any LLM in the loop; out-of-band narrative lands only as staged config | — | Out of scope by law |
| 10 | **Execution edges** (passive fills, spread capture) | Aggressive traders paying the spread | Small is an advantage on an exchange | A CFD limit order fills at the venue's own quote; there is no book to post into, so no spread is captured. On futures a resting order can earn the tick | Real on exchanges; nil on CFDs | Only with a futures venue; not a strategy, a cost reduction (~1 tick) |

**Ranking for this operator:** 1 ≫ 2 > (5 only if a new payer appears) > the rest. Two of ten classes are live; both are slow risk premia with payers who cannot reprice.

## 4. Diversification as the edge: the arithmetic [D, `edge_a_math.py` §2]

### 4.1 Closed form, equal risk: SR_p = s·√(N/(1+(N−1)ρ))

| s per stream | ρ | N=2 | N=3 | N=4 | N=6 | N=8 | N=10 |
|---|---|---|---|---|---|---|---|
| 0.15 | 0 / 0.1 / 0.3 | 0.21/0.20/0.19 | 0.26/0.24/0.21 | 0.30/0.26/0.22 | 0.37/0.30/0.23 | 0.42/0.33/0.24 | 0.47/0.34/0.25 |
| 0.20 | 0 / 0.1 / 0.3 | 0.28/0.27/0.25 | 0.35/0.32/0.27 | 0.40/0.35/0.29 | 0.49/0.40/0.31 | 0.57/0.43/0.32 | 0.63/0.46/0.33 |
| 0.30 | 0 / 0.1 / 0.3 | 0.42/0.40/0.37 | 0.52/0.47/0.41 | 0.60/0.53/0.44 | 0.73/0.60/0.46 | 0.85/0.65/0.48 | 0.95/0.69/0.49 |

Streams needed at ρ = 0: for 0.5, 11 at s = 0.15, 6 at 0.2, 3 at 0.3; for 0.75, 25 / 14 / 6. **The binding term is s, then ρ; N is the cheap one.** At ρ = 0.3 nothing passes ~1.7·s however many streams there are.

### 4.2 What is realistically available (measured ρ from the ledger, all |ρ| ≤ 0.3)

| Stream | Prior s after decay [D] | ρ with D1 / REBAL / GOTOBI (measured on history, ledger) | Status |
|---|---|---|---|
| D1-FX13 | 0.10–0.20 | 1 / −0.005 / ≈ 0 | forward, trades the demo |
| REBAL v1a | 0.10–0.20 | — / 1 / ≈ 0 | forward, shadow |
| GOTOBI v1a | 0.00–0.10 (faded) | ≈ 0 | forward, shadow |
| HALLOWEEN | 0.05–0.15 | −0.03 / +0.15 / +0.03 | forward |
| HEDGEP gold | 0.00–0.10 | −0.07 / −0.03 / +0.01 | forward |
| FXVALUE | ≈ 0 (ρ −0.28 with D1 is its only merit) | −0.28 / −0.02 / −0.01 | forward, declinable |
| **C2 D1-21 breadth** | 0.15–0.30 | ≈ 0.6 with D1-FX13 (same rule, shared FX) | proposed |
| **C3 RATES** | 0.20–0.35 | +0.1 to +0.2 with D1 (USD rates drive USD pairs) | proposed |

- The six registered streams at s ≈ 0.12 average and ρ̄ ≈ 0.05: SR_book ≈ 0.12·√(6/1.25) ≈ **0.26**.
- Replace D1-FX13 by C2 and add C3 (seven streams, s̄ ≈ 0.16, ρ̄ ≈ 0.08): ≈ 0.16·√(7/1.5) ≈ **0.35**.
- Optimistic (every stream at the top of its range, s̄ ≈ 0.25): ≈ **0.5**. That is the ceiling of the material on hand.

### 4.3 Stress correlation (two-state Monte Carlo, 6 streams, normal ρ = 0.05, stress ρ = 0.5 in 15% of months with 1.4× vol)

| s per stream | Book true SR | Median realised, 6 months | P(6-month ≥ 0.5) | P(6-month ≤ 0) | P(12-month ≥ 0.5) |
|---|---|---|---|---|---|
| 0.0 | 0.00 | −0.01 | 0.37 | 0.50 | 0.32 |
| 0.2 | 0.39 | 0.43 | 0.48 | 0.38 | 0.46 |
| 0.3 | 0.58 | 0.69 | 0.54 | 0.34 | 0.54 |

Stress correlation costs about 0.05–0.1 of book Sharpe (0.49 → 0.39 at s = 0.2) and, more important for a prop account, concentrates the drawdown into the stress months when the daily-loss line is nearest. The 2024–25 holdout was one such episode for short-leaning sleeves. **Which combinations are least correlated in stress:** trend (long vol by construction) against the flow sleeves (short vol in effect); that is the only pair whose stress correlation is plausibly negative, which is a second reason C2/C3 belong in the book.

### 4.4 The volatility premium, killed by sizing [D, `edge_a_math.py` §4]

A short front-month VIX position must survive 2018-02-05 (front future ≈ +96%, VIX +115.6%, a) inside the 3% daily-loss line: max exposure = 3%/0.96 = **3.1% of equity**. At a roll yield of 36–96%/yr (3–8%/month contango, UNCONFIRMED range) that exposure earns **1.1–3.0%/yr gross**, before the backwardation months in which it loses. On the 8% option: 8.3% exposure, 3–8%/yr gross, with the whole year's carry gone in one day every few years. Not a candidate at any prop firm; on own money it is a small, negative-skew diversifier the owner has no reason to want.

## 5. Venue and instrument changes

| Option | What it unlocks | Cost / constraint | Kenyan-operator reality | Verdict |
|---|---|---|---|---|
| **Prop notional ($100k E8 One, swap-free)** | Breadth for trend: at $100k / 20% vol, one minimum lot is 5–125× smaller than the per-instrument budget for all 21 CFDs (table below); at $6k, gold/US500/UK100 cannot hold one lot | Fee ≈ $260–488 for $100k (c, two aggregators disagree; the $10k is ≈ $68, a); swap-free +10%; 3% daily / 4% dynamic max loss (8% option exists); ±5-min news ban; one strategy per user (all ACIS sleeves are one EA); funded max $500k (c) | Accepted (a, prior pass) | **The real lever.** The money is in notional, not edge per dollar, which the owner's own rule already says |
| **Micro futures on an own IBKR account** | Rates sleeve (C3): one micro 10Y ≈ $900/yr vol; M6E/M6B/M6A FX micros; micro gold/oil for later | Carver (b): $10k holds ~3 instruments, $100k ~8; so at $6k this is a 1–2 instrument venue. Needs an IBKR/TWS adapter (ACIS-13 pattern) and an owner ruling outside R1-D9. Micro 10Y liquidity today UNCONFIRMED (CME page timed out twice; 27,819 contracts in launch week 2021, b) | IBKR accepts Kenyan residents per aggregators (c; verify at signup); Topstep/Apex exclude Kenya or VPS (a, prior pass) | **Worth it for C3 only** |
| **Lower-spread CFD venue** | ~0.4–0.6 bp index spreads already at Pepperstone Razor; the binding cost is commission ($6/lot FX round trip) and E8's unknown index contract size | A venue change buys at most ~1 bp; IMOM needed ~1.5 bp | — | Not worth a build |
| **Crypto perps (funding carry, cash-and-carry)** | A structural payer (leveraged longs pay shorts); delta-neutral; capacity irrelevant | §17: "no crypto … in v1" (a, spec). Funding baseline 0.01%/8h ≈ 11%/yr (BitMEX 2025Q3, b) but the cross-exchange average on 2026-09-25 was ≈ 2.2%/yr (c); basis trades quoted at 19–22% "in favorable conditions" (c); fees, spot custody and exchange failure (FTX) are the tail | Exchanges serve Kenya widely (UNCONFIRMED per venue) | A spec change and a different engine; the return is cyclical (near zero now). Not recommended |
| **Options** | Defined-risk vol selling | Not on cTrader/E8; IBKR only; the tail logic of §4.4 still applies | — | No |

**Prop-notional sizing [D, `edge_a_math.py` §3]** (20% vol, 4.8 independent bets across 21 instruments → per-instrument $ vol budget ≈ 0.2·E/√4.8):

| Equity | Per-instrument vol budget | EUR/USD 0.01 lot ($81/yr vol) | XAU 0.01 lot ($672) | US500 1 unit ($1,156) | UK100 1 unit ($1,729) |
|---|---|---|---|---|---|
| $6k | $548 | 6.7 lots | 0.8 | 0.5 | 0.3 |
| $10k | $913 | 11.2 | 1.4 | 0.8 | 0.5 |
| $100k | $9,129 | 112 | 13.6 | 7.9 | 5.3 |

At $6–10k the index and metal legs round to 0 or 1 lot (the one-lot cap in [[GAP-P12D-142]] is doing the right thing); at $100k the breadth is real. Vol inputs are typical annual values, not measured.

## 6. The shortlist (≤ 8; four survive my own attack)

Common to C2–C4: LLM-origin; kill-only on history (HAC t < −0.5 on the registered line); credit only forward (`scripts/tournament_daily.py`, capacity 20, α never recycled); one kill-only stage C per variant (master v2.35 R1-D13); C8 costs from `cfg`; never a guardrail change. Each spec is a draft for the owner to approve; the lead registers both versions before either grade.

### C1. The owner's own hypotheses (rank 1; not mine)
- **Why first:** §5.6 makes a human-origin rule the only one history can certify (stage A, α 0.03). Everything else in this report waits 6–12 months for forward data. The intake exists (`hypotheses/README.md`; `Origin("human")` in `tournament_registry.py`).
- **What I will not do:** suggest or refine one. The post-mortem's only transferable lesson is the *shape* that survives costs here: decided daily, held days to months, with a payer who cannot reprice.
- **Odds:** unknowable from here; the one route whose odds are not already discounted by publication.

### C2. TREND-BREADTH: D1 on the 21 explored non-energy instruments, forward at prop notional
- **Mechanism and who pays:** as D1 (EWMAC 16/64, 32/128, 64/256; pysystemtrade `a62269d2`); the payers are hedgers and rebalancers on the other side of multi-month moves. Breadth from 2.25 to ≈ 4.8 independent bets (GAP-P12D-148 (6)).
- **Expected net Sharpe [D]:** per-instrument 0.15 (Carver's median, backtest, b) × √4.8 = 0.33 gross-of-decay; momentum haircut −23% → 0.25; cost ≈ 0.01 SR at this turnover (D1 at 2× cost: 0.165 → 0.156) → **≈ 0.25**, range **0.15–0.30**. The 2013–23 look (−0.12, se ≈ 0.30) sits 1.2σ below that prior; the prior-weighted point is ≈ 0.15.
- **Data:** on disk (hourly candles); the look is spent (`000003`/`000004`), so **no new look**: this is a forward entry.
- **Draft pre-registration:** rule = `scripts/r1_d1_kill_test.py --universe r21` at `ce6c598`, class-equal weights (each FX 1/39, metals 1/6, indices 1/18), unchanged; versions: v1 only (no slow-member variant: §2.4); window: forward from the entry's first exposure, no history credit; cost model: the registered C8 map (hash pinned); kill: stage D E2 and the −6σ* tripwire as coded; eligibility: milestone D plus the tournament's corrected significance, never live before an owner ruling; venue for any live sleeve: a funded notional ≥ $50k, swap-free, so every instrument holds ≥ 3 lots at a full forecast (§5 table), which also needs [[GAP-P12D-27]]'s onboarding of metals and indices.
- **Strongest reason it fails:** the 2013–23 look is a fair sample of what this rule does when indices and gold rally for a decade (it shorts the dips); if the equity regime continues, the forward record repeats −0.1. Second: its ρ with D1-FX13 is high (same rule, shared pairs), so it adds less than a new mechanism.

### C3. RATES: trend on the Treasury par curve (micro yield futures), with the post-FOMC drift as the documented payer
- **Mechanism and who pays:** Brooks–Katz–Lustig (NBER w25127, a): after a target change, bond-fund investors sell for months and arbitrageurs absorb slowly, so long yields drift (14 bp after 50 days per 10 bp surprise, 1988–2008); they name this as a cause of bond TSMOM. The generic form (trend on yields) does not need a surprise, which matters because Kuttner surprises have been near zero since forward guidance.
- **Expected net Sharpe [D]:** bond TSMOM 0.29–0.38 gross on 13 bond futures (Baltas–Kosowski, b), take 0.33; haircut −23% → 0.25; four tenors ≈ 1.5 independent bets (PC1 dominates) → 0.25·√1.5 ≈ 0.31; cost 0.05 SR at 20 round trips a year ($2.24 per round trip on $900/yr vol, `edge_a_math.py` §5) → **≈ 0.25**, range **0.20–0.35**.
- **Data and venue:** the kill test needs **no venue**: `data/r1_real/treasury/ust_par.csv` (the CMT par yields AUCTION used) is on disk; the forward sleeve needs an IBKR micro-yield adapter and an own-money account (Kenya UNCONFIRMED at signup), or stays a shadow record. One 10Y contract ≈ 1.3 contracts of budget at $6k: the sleeve is one to two contracts.
- **Draft pre-registration:** instruments UST2Y, UST5Y, UST10Y, UST30Y par yields (research-only legs as `r1_auction_kill_test.py` declares them, never in `config/instruments.yaml`); forecast = D1's three EWMACs on the yield series, sign flipped to price terms (yield up ⇒ long yield ⇒ short price), Carver sizing 0.01/σ with σ the 36-day yield vol in bp, class-equal weights across tenors; v1a = the three EWMACs at equal weight, v1b = MOP's 12-month sign on the yield, both registered before either grade; window 2012-02-01..2023-12-29 graded daily at the Treasury's close (RSIM's 17:00 New York decision; fill at the next close, declared: no intraday futures data on disk), warm-up from the file's first date; cost = AUCTION's MICRO map ($0.62 fees + half a $1 tick per side, per unit DV01); benchmark = flat and the passive long-duration control; kill at HAC t < −0.5; declared departures: par yields for the micro contract's BrokerTec benchmark (no roll treatment: the contract settles to the current on-the-run, which the CMT series tracks by construction), 2012–23 is one rate regime; stage C: one kill-only look on 2024–25 only if the owner rules it; expected ρ with D1-FX13 +0.1 to +0.2, written here before any look.
- **Strongest reason it fails:** the whole 2012–23 sample is ZIRP, taper, one hiking cycle and a pandemic: two or three trends. A survival is one or two bets, and the forward sleeve needs a venue build the owner has so far ruled "not now" (R1-D9). Second: micro-yield liquidity in 2026 is unverified; if the book is thin the half-tick slippage assumption is wrong.

### C4. The BOOK: a declared combination rule for the registered forward survivors (no look)
- **Mechanism:** §4's sum. Nothing new is traded; the rule that combines D1-FX13, REBAL v1a, GOTOBI v1a, HALLOWEEN, HEDGEP (FXVALUE at the lead's discretion), plus C2/C3 if registered, is written down before the book has a forward day, so its forward record is itself registrable and the weights are not chosen after seeing which sleeve won.
- **Expected net Sharpe [D]:** 0.26 for the six at s̄ 0.12 and ρ̄ 0.05; 0.35 with C2 and C3 at their priors; 0.5 if every stream is at the top of its range. **Not the 0.65–0.85 the weekly target needs.**
- **Draft pre-registration:** equal risk weights per stream, each stream scaled to a 20%-vol unit on its own trailing 36-day realised vol, weights frozen (no performance-based re-weighting: that is Agent B's lane and I only note that any adaptive weight must itself be pre-registered); a stream killed by E2 drops to zero weight and the others do not inflate; the book's own E2 and −6σ* tripwire as coded; the daily-loss and max-loss gates unchanged. This is a tournament entry of kind `book`, which does not exist yet (**a spec change: P-6's forward-look amendment covers a strategy, not a book**).
- **Strongest reason it fails:** s is the binding term; six streams at 0.1 give 0.22 whatever the weights, and the measured correlations are history-measured on short, lucky windows (HALLOWEEN has 2 switches a year), so ρ̄ in stress may be 0.3, which caps the book near 0.3.

### Dropped ex ante (no look spent), with the reason

| Candidate | Why dropped |
|---|---|
| **ANNOUNCE** (long US500 on FOMC/CPI/NFP days; Savor & Wilson 2013, 11.4 vs 1.1 bp/day 1958–2009) | Ernst, Gilbert & Hrdlicka 2021 (b): once the full release calendar and day-of-month fixed effects are in, announcements explain about half the equity premium over more days and **Sharpe is similar on announcement and non-announcement days**; the contrast is then beta. The pre-FOMC drift sibling died after 2015 (carried). The E8 ±5-minute ban also sits on the entry. |
| **VRP** (short VIX) | §4.4: 3.1% max exposure ⇒ 1–3%/yr. |
| **Post-FOMC drift as its own family** | Folded into C3; the surprise series has been ≈ 0 since forward guidance, so the conditional version would have a handful of events in 2012–23. |
| **Commodity carry on CFD forwards** | Pepperstone forwards exist for Brent, WTI, gold and silver only (a); precious-metal basis is a constant contango (a permanent short, not carry); energy is refused by the data layer (GAP-P12D-137); E8's forward list is UNCONFIRMED. Two instruments is not a carry strategy. |
| **Crypto funding carry** | §17 non-goal; baseline funding ≈ 11%/yr in 2024–25 (b) but ≈ 2.2%/yr on the 2026-09-25 snapshot (c); exchange counterparty tail; a different engine. |
| **Slow-member D1** | §2.4: a post-look selection. |
| **Country-index cross-sectional momentum, FX cross-sectional momentum, lead-lag, local-hours, FOMC-USD, fixings in other currencies, seasonality, vol-managed exposure** | Already dropped or killed in the prior passes for reasons I checked and agree with (FACTORY's table, SHARPEN §2). |

## 7. Honest negatives and what would change them

- **"A durable 0.5+ net Sharpe from the published pool, on this venue, at this scale" is unlikely:** ~20–25% by end-2027 on my reading; the 0.65–0.85 band is < 10%. The reasons are structural (cost floor, repricing payers, single-asset-class breadth), not fixable by more history.
- **What changes it:** a human-origin rule with a structural payer (C1); a $100k+ funded notional so trend breadth is real (C2); a rates sleeve on an own futures account (C3); and the forward clock. None of these is a new idea; they are the three the owner's own rulings already point at.
- **What "working good" can mean here:** a 0.3–0.45 book, scaled by account count under the owner's rule, with the kills arriving fast. That is what live diversified trend managers earn (SG Trend 0.38 over five years, b); nobody at this venue has shown more on record.

## 8. Bearing on Agent B (the factory)

- The holdout power table (§2.3) and the Monte Carlo (§4.3) say a 6-month ≥ 0.5 screen fires on noise 37% of the time and on a true 0.39 book 48%: the factory's stage D is a spending gate, as ruled, and nothing in the supply side can make it a certifier.
- Tripwires should be per-mechanism, not per-instrument, and should expect stress-month correlation (§4.3), or they will kill healthy sleeves together in one episode as 2024–25 did.
- The supply side's recommendation to the factory: **count mechanisms, not candidates.** Of ten edge classes, two are live on this venue. A generator that keeps emitting class-5 candidates (public-clock forced flows) will keep producing survivals that are "0 without the 10 best days".

## 9. Sources

Repo (a): `TODO.md` "Where we stand on an edge"; `KNOWN_GAPS.md` [[GAP-P12D-148]], [[GAP-P12D-151]], [[GAP-P12D-158]], [[GAP-P12D-159]]; `ACIS_SPEC.md` §17 (line 486: "no crypto/cash-equities in v1"); `archive/RESEARCH_EDGE_SHARPEN_2026-10-01.md` (§4 FTMO/Pepperstone costs, §5 breadth table); `archive/RESEARCH_FACTORY_2026-10-03.md`; `archive/RESEARCH_LEVER2_FUTURES_2026-10-03.md`; `archive/LEVER3_MEMO_2026-10-03.md`; `archive/TOURNAMENT_REPORT_2026-10-03.md`; `archive/RESEARCH_PROP_RETURNS_2026-10-02.md`; `archive/RESEARCH_PROP_VENUES_2026-09-24.md` (note: the "accounts of $50,000 and above must trade fully manually" rule is FundedNext's, §2.3 there, not E8's); `scripts/r1_auction_kill_test.py` header (MICRO cost map); `tests/backtest/universe.py`.

Web, all accessed 2026-10-06:
- Brooks, Katz & Lustig, "Post-FOMC Announcement Drift in U.S. Bond Markets", NBER w25127 (a): https://www.nber.org/papers/w25127 ; slides (numbers extracted with pypdf): https://conference.nber.org/conf_papers/f119121/f119121.slides.pdf
- Ernst, Gilbert & Hrdlicka, "More than 100% of the equity premium…", 2021 (b, via the AEA listing and search rendering): https://aeaweb.org/conference/2022/preliminary/paper/ktNibY2Y
- Wachter & Zhu, "The Macroeconomic Announcement Premium", NBER w24432 (a): https://www.nber.org/papers/w24432
- Hu, Pan, Wang & Zhu, pre-announcement returns (b): https://www.nber.org/papers/w25817
- SG Trend Index, December 2025 report (b): https://www.toptradersunplugged.com/?p=20381
- BarclayHedge Currency Traders Index 2022–2024 (b): https://thefullfx.com/currency-traders-end-year-on-strong-note/
- BIS Quarterly Review, 5 February 2018 (a): https://www.bis.org/publ/qtrpdf/r_qt1803t.htm ; XIV −96.3% (b): https://www.etf.com/sections/news/inverse-vix-etn-shuts-down
- Static short-vol Sharpe ≤ 0.5 (b, Journal of Investment Strategies via search): https://www.risk.net/node/5460971
- Koijen, Moskowitz, Pedersen & Vrugt, "Carry" (a; numbers via b): https://repec.cepr.org/repec/cpr/ceprdp/DP9771.pdf ; https://www.cxoadvisory.com/big-ideas/unified-carry-trade-theory/
- Baltas & Kosowski bond TSMOM by horizon (b): https://www.cxoadvisory.com/momentum-investing/intrinsic-momentum-diversified-across-futures/
- Carver, "Diversification and small account size" (b): https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html
- CME micro yield futures (b): https://www.marketsmedia.com/cme-micro-treasury-yield-futures-surpass-30000-contracts-traded ; CME contract page (timed out twice; liquidity UNCONFIRMED): https://www.cmegroup.com/markets/interest-rates/us-treasury/micro-10-year-yield.html
- IBKR and Kenya (c): https://comparebroker.io/brokers/is-interactive-brokers-legal-in-kenya ; https://www.alexontrading.com/faq/availability/brokers/interactive-brokers-kenya
- E8 One terms (c): https://thegodfunded.com/es/firms/e8 ; $100k fee (c, conflicting): https://propfirmmap.com/firms/e8-markets ; https://propfirmsfinder.com/prop-firm/e8-markets/history/ ; e8markets.com returned 403
- Pepperstone CFD forwards (a): https://pepperstone.com/en/markets/cfd-forwards/
- Harvey, Mazzoleni & Melone (b; the "0.94 out of sample" figure seen only in a search rendering: UNCONFIRMED): https://www.nber.org/papers/w33554
- BTC funding baseline (b): https://blog.bitmex.com/2025q3-derivatives-report ; snapshot 2026-09-25 (c): https://defirate.com/perp/bitcoin/snapshot/2026-09-25T2330/
- Carried from the prior ACIS reports, not re-fetched: McLean & Pontiff 2016; Ilmanen et al. 2021 Table 2; Greenwood & Sammon 2025; FCA OP46; Boyarchenko, Larsen & Whelan 2026; Hurst, Ooi & Pedersen 2017; Lo 2002 (the Sharpe standard error).

## Method note
- WebSearch: 20 of 70 calls; WebFetch: 15 (3 failed: 404, 403, two timeouts on CME). No fetched page contained instructions I acted on; all web content was treated as data.
- Script: `edge_a_math.py` in the session scratchpad (`C:\Users\USER\AppData\Local\Temp\claude\…\d213ec7f-…\scratchpad\`), 12 s on the laptop, synthetic only; its output is reproduced in §2.3, §4, §5. One bug (a monthly mean scaled by √12 instead of 12) was found by the closed form and fixed before any number was quoted.
- Repo: this file is the only write; no git command; no subagent; the VM was not started.

---
**Summary (repeated):** the published, CFD-expressible pool is near exhausted and its failures share a shape (sub-weekly holds, repricing payers, single instruments, one regime); the holdout says the tested families are small, not dead; only slow risk premia have payers who cannot reprice; diversification multiplies s and needs ~14 streams at 0.2 for 0.75; the capital lever (a $100k notional) beats any venue change except a futures account for a rates sleeve; the shortlist is C1 the owner's own rules, C2 trend breadth forward at prop notional (0.15–0.30), C3 rates trend on the par curve (0.20–0.35, kill test on disk), C4 a pre-declared book (0.25–0.35); ANNOUNCE, VRP, commodity carry, crypto carry and post-hoc slow members are dropped with the arithmetic shown; odds of a durable ≥ 0.5 forward by end-2027 ≈ 20–25%, of 0.65–0.85 < 10%; what changes it is a human-origin rule, real notional, a rates venue, and time. Ran as Claude Fable 5.1, fresh context, no market data read.
