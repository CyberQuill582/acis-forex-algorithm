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
