# PARTIAL R1-B — EDGE AND BREADTH (checkpoint 1, ~30 min)

- **Lane:** R1-B, edge and breadth. Model: the system prompt names `claude-opus-5-5` (Opus 5.5); effort is not observable from inside the session (the brief says xhigh).
- **Fresh context:** yes; I launched no subagents. BASE `974dbda` (read-only tree `/tmp/review-acis`). Date 2026-09-25, started 08:00 UTC.
- **Web used so far:** 1 WebFetch + 3 direct HTTP GETs of FTMO's own pages and data endpoint = **4 of 40**.
- **Status:** a finder's checkpoint (A5). Evidence to weigh, not instruction (A9).

## First findings

1. **FTMO publishes its whole symbol specification as machine-readable JSON, and it settles the carry question for this venue. Grade (a): the firm's own primary document.**
   - The `https://ftmo.com/en/symbols/` page (modified 2026-09-02) renders from `https://ftmo.com/wp-json/ftmo/symbols`, fetched 2026-09-25.
   - Each record carries `swapLong`, `swapShort`, `swapType: "points"`, `commission`, `commissionType`, `contractSize`, `leverageSwing` and a week of `tradingHours`. For example, EUR/USD reads `"swapLong":-9.49,"swapShort":0.36,"swapType":"points" … "commission":5,"commissionType":"flat_USD"`.
   - It lists 166 active symbols: 28 Forex, 15 Exotics, 9 Metals CFDs, 25 Cash CFDs (indices, energies and softs), 59 equities and 30 crypto.
   - The receipt `evidence/R1B/probe_ftmo_swap_carry.py` splits each symbol's swap pair into a fair carry *d* and a per-side markup *m* (L = d − m, S = −d − m). It needs no price level.
   - **Result: on the 28 G10 pairs, the positive-carry side keeps a median of 21% of fair carry, and 21% of pairs (6 of 28) have no positive side left at all.**
     - EUR/USD short keeps 7%.
     - USD/JPY long keeps 26%.
     - NZD/USD keeps 2%.
     - AUD/USD, GBP/USD and EUR/NZD pay on both sides.
   - **Consequence (derived):** FX carry as a *return* source is mostly confiscated at FTMO. Carry survives only as a *cost to avoid*, that is a holding-cost filter. It extends the 2026-09-16 FX-methods report's (c)-graded "broker markup eats carry" claim with the firm's own numbers.
2. **The financing model at BASE under-charges FTMO by a wide margin outside FX majors.**
   - `tests/backtest/financing.py:7-11` charges a flat 1.00% admin fee per side (OANDA's method), and an assumed gold lease of 0.25%.
   - Converted at *assumed* round price levels (unit conversion only, not data), FTMO's per-side markup is:
     - about 1.3–1.8%/yr on the majors, and 2.5% on AUD/USD;
     - about **4.8%/yr on XAU/USD**, so a gold long pays about 8.7%/yr;
     - about **3.6–5.0%/yr on index cash CFDs**, so a US500 long pays about 9.2%/yr and a US100 long about 10.5%/yr, while the short side receives roughly nothing.
   - A slow trend or TSMOM **long** in gold or indices held for months therefore pays about 0.5–0.9 Sharpe units a year of holding at 10–18% volatility.
   - **The C8 cost model must carry the venue's per-symbol swap table, not central-bank rates plus a 1% fee.** This extends ARC H8's "index longs pay about 7%/yr".
3. **Trading hours bite a daily-close design.** FTMO's gap-trading clause bars opening trades *"two hours or less before a relevant financial market is closed for at least two hours"* (SCO, (a)).
   - From the JSON's `tradingHours`, these symbols have a daily break of 2 hours or more: EU50 and FRA40 (10.1 h), UKOIL and DXY (3.25 h), AUS200 (3 h), XCU (2.1 h), CORN and WHEAT (5.75 h), COFFEE (14.8 h) and HK50 (6.3 h).
   - FX has a 0.17 h break. XAU, US500, US100, GER40, UK100, JP225, USOIL and NATGAS have 1.25 h.
   - **So a single 17:00 New York decision time works for about 20 symbols. The rest need a per-symbol execution time after their reopen, or they must be excluded.**
4. **Prior work already covers the family literature to 2016–2020** (RESEARCH_FX_METHODS §4 and §7; ARC H8). This lane adds the 2020–2026 out-of-sample record, the rule parameters, the combination scheme, the universe and the data plan.

## Plan for the next 45 minutes

- **Sources:** Carver (forecast scalars, FDM/IDM, handcrafting, his speed-limit table, his published live record); the trend record for 2017–2026; Koijen et al. on carry; Menkhoff et al. on currency value; McLean–Pontiff decay; Etula et al. on turn-of-month; and published correlation levels.
- **Universe:** Dukascopy's instrument list with its history start dates, and E8's symbols and swaps.
- **Then:** the draft "For PLAN_R1" section.

---

# Checkpoint 2 (08:38 UTC, moved forward at the lead's request) — DRAFT "For PLAN_R1"

**Web used: 7 of 40.** Every number below is a **DRAFT**. The literature values come from my knowledge and from the prior reports; the ones not yet re-fetched are marked **[to verify]**, and the final report will quote or correct them.

## New finding 5: at FTMO, the swap markup is the dominant cost of a slow rule, not the spread

**Grade (a) for the swap table.** The conversion uses round price and volatility assumptions, labelled as such in the receipt.

- **Receipt:** `evidence/R1B/probe_holding_cost_sr.py` (and its `.out`).
- **The markup per side,** as %/yr of notional, from FTMO's own swap points:

  | Instruments | Markup per side |
  |---|---|
  | EUR/USD | 1.45 |
  | USD/JPY | 1.80 |
  | GBP/USD | 1.34 |
  | AUD/USD | 2.54 |
  | USD/CHF | 2.62 |
  | EUR/JPY and CAD/JPY | 0.89 |
  | XAU | 4.76 |
  | XAG | 6.72 |
  | XPT | 11.45 |
  | US500 | 4.65 |
  | GER40 | 3.56 |
  | UK100 | 4.56 |

- **In Sharpe units per year of full-size holding** (m ÷ vol), the cost is **0.08–0.46 (median ≈ 0.21)**.
- Round-trip spread plus commission for an EWMAC(16,64)-speed rule on a major costs about **0.02 SR/yr**. **So holding cost is about 10× the trading cost.**
- **Carver's speed limit is (b):** cost ≤ ⅓ of the expected pre-cost SR. With a per-instrument pre-cost trend SR of about 0.3–0.5, the cost budget is 0.10–0.17 SR. **Full-time holding at FTMO's markup busts that budget on most instruments.**
  - Only low-markup/high-volatility symbols stay inside it: EUR/JPY 0.09, CAD/JPY 0.08, CHF/JPY 0.10, EUR/AUD 0.12, AUD/JPY 0.13, GBP/JPY 0.14 and NZD/USD 0.15.
- **Implications:**
  1. The speed limit must count **holding cost per year held**, not only turnover × spread.
  2. Prefer rules that are **flat part of the time** (a forecast threshold, or breakout rules that go to zero).
  3. Before committing the universe, ask FTMO or E8 about swap-free (Islamic) accounts and whether their swaps are stable.
- **Energy swaps are uninterpretable.** USOIL and UKOIL swap points imply implausible percentages under the point convention, so treat them as **unknown until FTMO answers**.

## For PLAN_R1 (DRAFT)

### P1. Rule families: at most 3 free parameters each, literature-fixed, pooled across all instruments

| # | Family | Minimal faithful rule (fixed values) | Coarse variants for the plateau grid | Literature gross SR (per diversified portfolio) and decay | Verdict |
|---|---|---|---|---|---|
| F1 | **Trend, EWMAC** | forecast = (EWMA_f − EWMA_s) ÷ σ_price, with σ from a 25-day EWMA of daily price changes. Speeds (f,s) = (16,64), (32,128), (64,256). Carver's scalars 3.75 / 2.65 / 1.87 [to verify]. Cap ±20. Equal weight across speeds, then FDM | Drop the fastest speed per instrument if cost > budget. ±1 speed step | Multi-asset CTA/trend: Hurst–Ooi–Pedersen **0.76 net 1880–2016, 0.41 in 2010–16** (ARC, (a)). SG Trend ≈ 0.4 (prior report, (b)). FX-only walk-forward 0.43 (c) | **ADOPT** as the core |
| F2 | **Trend, breakout** (Carver's form) | forecast = (P − mid_N) ÷ (max_N − min_N), smoothed with span N/4, with N = 40, 80, 160 days. Scalar [to verify]. Cap ±20 | N ×/÷ 2 | Highly correlated with F1 (≈0.8–0.9 [to verify]). It adds robustness, not breadth | **ADAPT**: one sleeve at most, combined inside the trend family |
| F3 | **TSMOM (MOP 2012)** | sign(12-month return), vol-scaled, monthly rebalance with a 10% buffer | 1/3/12-month equal weight (ARC H8) | MOP ≈ 1.1 gross (a). Huang et al. 2020: "little evidence" asset by asset (a) | **REJECT as a separate family.** It is F1 at its slowest speed, and a separate family doubles the trial count. Keep it as F1's (64,256) speed for canonical continuity (ACIS-04 §6.6 amendment) |
| F4 | **Carry** | forecast = the venue's net annual swap for the side ÷ σ | none | HML-FX 0.76 full sample; **post-GFC ≈ 0.25** (a, prior report) | **REJECT as a return source at FTMO**, where median 79% of G10 carry is confiscated. **ADOPT as a cost term** (swap table in C8) and as a hold-cost tie-breaker only |
| F5 | **FX value** (5-year PPP/REER reversal) | Needs CPI data | — | Low Sharpe, about 7 currency bets | **REJECT for R1** (a data dependency for little breadth). Revisit later |
| F6 | **Cross-sectional FX momentum** | — | — | Menkhoff et al. 2012: needs about 48 currencies and is "fairly sensitive to transaction costs" (a) | **REJECT standalone.** At most, a within-asset-class relative-momentum variant of F1 [to verify] |
| F7 | **Turn-of-month equity index long** | long US500/US30/GER40/UK100 from the close of T−1 to the close of T+3; fixed | T−2..T+3 | Lakonishok–Smidt 1988, McConnell–Xu 2008, Etula et al. 2020 [to verify] | **ADAPT**: daily-horizon slate D3 |

**Combination (P2).**
- Fixed equal weights within each family, then equal risk across families (handcrafting).
- No fitted weights: the 1/N and forecast-combination-puzzle evidence is [to verify].
- Forecast diversification multiplier from the correlation *assumed a priori* (0.8 within trend speeds, giving FDM ≈ 1.1 [to verify]).
- Instrument diversification multiplier (IDM) from Carver's table [to verify].
- Position = capital × vol target × combined forecast ÷ 10 ÷ instrument σ. The vol target and floor are ECO's.
- A 10% no-trade buffer. Execution happens once per day.
- **Per-instrument deviation is allowed only by cost,** meaning dropping speeds that bust the budget. Pooled gross, per-instrument cost (Carver's "pool gross returns, then apply the costs for each individual instrument", (b), fetched).

### P3. Universe: 30 instruments. All are on FTMO. Dukascopy history back to 2012 is to be verified per symbol

| Class | Primary (explored) | Held-out (locked) |
|---|---|---|
| FX (16) | EUR/USD, USD/JPY, GBP/USD, NZD/USD, USD/CAD, USD/CHF, EUR/JPY, GBP/JPY, AUD/JPY, EUR/CHF, EUR/AUD, CAD/JPY, CHF/JPY | **AUD/USD, AUD/NZD, EUR/GBP** |
| Metals (3) | XAU/USD, XPT/USD | **XAG/USD** |
| Indices (8) | US500, US30, US2000, UK100, JP225, EU50 (EU50 is executed after its 06:05 UTC reopen) | **GER40, US100** |
| Energies (3) | UKOIL, NATGAS (pending the swap answer) | **USOIL** |

- **The held-out draw is mechanical, so nobody chooses it:** sort each class by SHA-256(`"ACIS-R1-holdout-2026-09-25|" + symbol`) and hold out the first k (FX 3, metal 1, index 2, energy 1).
  - This salt is pre-registered by this commit.
  - The lead may re-salt only before any data look, and must record that it did.
  - Already-touched instruments (EUR_USD, USD_JPY) are forced into the primary set.
- **Excluded:**
  - ags and softs (`leverageSwing: 1`, so full margin at $6k);
  - exotics (markups of 10–135 points);
  - crypto and single stocks;
  - FRA40, AUS200, HK50, SPN35 and N25 (redundant, or breaks of 2 h or more).
- **Effective breadth.** FX shares the dollar factor, and indices share the equity factor. The effective count is about 10–14 independent bets [to verify against published correlation levels].
- **Held-out analysis must residualise** on the common factor, per VAL §2.6.

### P4. Data plan (DRAFT estimates; the owner measures one file first)

- **Signals need only hourly bid and ask bars.** 17:00 New York is always a whole UTC hour (21:00 in EDT, 22:00 in EST), so hourly candles give exact New York closes and the spread at execution.
  - Dukascopy's public feed serves pre-aggregated candles per instrument: 1-minute per day, hourly per month, daily per year [to verify: file layout and sizes].
  - **Estimate:** hourly bid+ask for 30 instruments × 14 years is 30 × 14 × 12 × 2 = **10,080 files, about 0.1–0.3 GB, a few hours** on a residential link.
  - One-minute bid+ask candles are optional: about 250k files, **about 2–5 GB, 1–3 days**.
- **Do not download ticks for the new 22 instruments for R1.**
  - Extrapolating ACIS's record (8 instruments, 12 GB, 35,008 files, about 2.99 B ticks, "days" to download) to 30 instruments gives about **45 GB, about 130k files, and 1–2 weeks** on the same link.
  - It is not needed for daily rules. Ticks stay for the 8-instrument reconciliation of RSIM against the tick harness (VAL R1–R6).
- **Also needed:** dated swap history. FTMO publishes today's table only, so the model is central-bank rates plus a *firm-calibrated* markup per symbol from the table above, not a flat 1%.

### P5. Daily-horizon slate (LLM-originated; extends ARC §4; replication standard t ≥ 2, discovery standard t ≥ 3)

Gates follow ARC §5.5: E = 2012–19, V = 2020–23, H = 2024–25 once, F = forward demo.

| ID | Hypothesis | Instruments | Expected gross/cost | Falsifiers |
|---|---|---|---|---|
| D1 | Pooled multi-speed EWMAC trend (F1) | all 23 primary | ≈ 1.5–3 on FX crosses, **≈ 1 or less on indices and metals if held full-time** (swap) | G2: pooled net SR ≤ 0 on E, or the gross/cost measured on E is below 2 → kill. G3: pooled net SR on V below 0 at 1× cost, or below −0.1 at 2× cost → kill. G5: 60 trades or 3 months with the per-trade mean below V's 10th percentile → kill |
| D2 | D1 with a forecast threshold (flat while \|f\| < 5): cuts holding cost about 30–40% [to verify by synthetic] | same | +30–50% on D1 | G2: must beat D1 net on E by ≥ 0.05 SR, or it is dropped (a registered variant of D1's family) |
| D3 | Turn-of-month index long (F7) | US500, US30, UK100, JP225, EU50 | ≈ 3–5 (4 nights of swap ≈ 0.05%) [to verify] | G2: the TOM-window mean is not > the non-TOM mean on E → kill. G3: t < 2 on V (post-publication replication) → kill |
| D4 | Breakout sleeve (F2) inside the trend family | all | as D1 | Counts as a D1 family variant. Kept only if the combination's net SR on E is ≥ D1's |

**This slate ranks alongside ARC's:** D1 sits between H3 and H4 on evidence, and below H1 and H5 on prop fit, because of the swap and the 10% static max loss. D3 is comparable to H5.
