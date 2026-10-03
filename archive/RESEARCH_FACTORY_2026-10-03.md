# FACTORY: cost-viable daily-clock candidates, one kill-only look each (2026-10-03 UTC / 10-04 local)

- **Who and why.** FACTORY, one of the three edge agents the owner launched on 2026-10-03 ("run agents to fix our edge problems … we need to find the edge"), under the owner's pre-authorisation in [[GAP-P12D-158]]: one pre-declared version per candidate, no tuning, a P&L-blind dry check, and one kill-only look on 2012-02..2023-12, killed at HAC t < −0.5. No stage C. Survivors go only to the forward tournament, never live.
- **Status.** This is a finder's report. Nothing in it binds until the lead triages it. Every candidate is literature SELECTED by an LLM (claude-opus-5-5, web; certifying boundary 2026-10-04), so history can only kill: **a survival credits nothing and nothing here is an edge.**
- **Discipline kept.**
  - All five versions were written, dry-checked and committed in ONE commit (`00b9d3c`) before the first look. No script changed between looks.
  - The looks ran in the ranking rule's order: forced flow (HEDGEP, IREV), then risk premia (FXVALUE, DCARRY), then pattern (HALLOWEEN).
  - Nothing was re-run, re-versioned or tweaked.
  - Every look ran from the clean tree at `00b9d3c`. Each was anchored on GitHub `look-anchor` (head at `000054`), and the register was copied to `gs://acis-compute-0929-data/validation/2026-10-03h/looks` after every look.
  - The inputs (`fx_value/`, `cot/`) and the five outcome JSONs are in the same bucket folder.

## Summary

| Candidate (family id) | Source | Class | Ex-ante gate | Look / outcome | Net Sharpe | HAC t | 2× cost | Verdict | ρ D1 / REBAL / GOTOBI |
|---|---|---|---|---|---|---|---|---|---|
| HEDGEP (`hedgep_v1_gold`) | Kang, Rouwenhorst & Tang, JF 2020 | forced flow (liquidity provision) | gold 9.4×, silver 1.1× (out) | `000045` / `000046` | +0.14 | +0.49 | +0.08 | survived | −0.07 / −0.03 / +0.01 |
| IREV (`irev_v1_mac5`) | Baltussen, van Bekkum & Da, JFE 2019 | forced flow (index arbitrage) | US500 4.1×, UK100 4.9×, JP225 3.05×; EU50 1.6×, AUS200 2.7× (out) | `000047` / `000048` | −0.21 | −0.70 | −0.41 | **KILLED** | +0.05 / **+0.30** / +0.03 |
| FXVALUE (`fxvalue_v1_ppp`) | Asness, Moskowitz & Pedersen, JF 2013 | risk premium (value) | cost ≈ 0.001 SR (monthly) | `000049` / `000050` | +0.07 | +0.21 | +0.06 | survived | **−0.28** / −0.02 / −0.01 |
| DCARRY (`dcarry_v1_spot`) | Lustig, Roussanov & Verdelhan, JFE 2014 | risk premium (dollar carry, spot) | one sign flip in 12 years | `000051` / `000052` | −0.31 | −1.12 | −0.31 | **KILLED** | +0.04 / +0.01 / −0.01 |
| HALLOWEEN (`halloween_v1_contrast`) | Bouman & Jacobsen, AER 2002; Andrade et al., FAJ 2013 | pattern with out-of-sample survival | ~100× (2 switches a year) | `000053` / `000054` | +0.26 | +0.77 | +0.25 | survived | −0.03 / +0.15 / +0.03 |

- **Correlations among the five** (stored vectors, common dates) are all |ρ| ≤ 0.24. The largest are FXVALUE–DCARRY −0.24 and IREV–HALLOWEEN +0.14.
- **An equal-risk book of the three survivors** earns 0.28 over 2012–2023 (context only, never a selection).

## Survivors for the forward tournament (forward evidence only; each kill-only and LLM-selected)

1. **`halloween_v1_contrast`** (look `000053`): 0.26, t 0.77, and 0.28 on 2013–2023, after both papers' samples. Caveats:
   - It is **0.00 without its 10 best days**, and 2023 alone is 2.20.
   - It has only 2 position changes a year, so the forward clock judges it slowly: about two seasons a year.
   - ρ with REBAL is +0.15 (both are short US500 at times).
2. **`hedgep_v1_gold`** (look `000045`): 0.14, t 0.49. Caveats:
   - The seen years (2012–2014) earned −0.32 and the post-sample years (2014-12..2023) +0.29.
   - It is −0.17 without its 10 best days.
   - It trades one market, and its passive long gold earned 0.19.
3. **`fxvalue_v1_ppp`** (look `000049`): 0.07, t 0.21, essentially flat. Caveats:
   - Its only clean segment (2021–2023) earned −0.25, and it is −0.18 without its 10 best days.
   - Its one merit is ρ −0.28 with D1-FX13, a diversifier by construction (value against trend).
   - The lead may reasonably decline it.

The tournament's promotion rule must count all five looks (and their dropped siblings) in its multiple-testing correction. Each surviving rule is computable live on the daily clock:
- HALLOWEEN at each home cash close (the REBAL live draft's close slot);
- HEDGEP from Friday's CFTC release at the 17:00 New York decision;
- FXVALUE from month-end ECB fixings and published CPI.

## The candidates that got a look

### 1. HEDGEP: speculators pay hedgers for immediacy (gold)
- **Source, read in full** (KRT, JF 75(1) 2020; working version 2016-12). The sample is 26 commodities, CFTC legacy COT, 1994-01..2014-11.
  - Commodities that hedgers bought last week outperform those they sold.
  - The quintile spread is 0.21% in days 1–4 (before release), 0.30% in days 5–10 and 0.15% in days 11–20.
  - The panel slope with commodity fixed effects is 8.9 bp next week per 3.5% of open interest (Table 5).
  - Gold's mean |Q| is 5.06% and silver's 3.75% (Table 1).
- **Rule.**
  - Q = Δ(commercial long − short) / previous OI, and z = Q over the sd of the last 52 Q's.
  - The forecast is 10 × clip(z, −2, 2) from the report's release day: Friday, or the next Monday when a federal holiday or closure falls in the as-of week. This reproduces the CFTC's published 2026 schedule.
  - Shutdown reports (2013-10..11, 2018-12..2019-02) are never used, and a report over 14 days old means flat.
  - Graded by RSIM on XAU_USD: 17:00 New York decision, 08:00 New York fill, $1M, 20% vol, buffer 0.10, swap-free.
- **Declared departures:** a time-series rule on one market (the paper sorts 26), and the CFD spot for the front future.
- **Ex ante and dry check (P&L-blind):**
  - 621 reports, 19 of them from shutdowns, and 45 holiday-delayed.
  - The turnover is 0.92 A a week.
  - The gross per unit z is slope × 1.25 × the paper's mean |Q|. That is 16 bp a week for gold against a C8 cost of 1.7 bp a week (9.4×). Silver's spread gives 1.1×, so silver is out.
  - Window roles: 2012–2014 seen.
- **Result and verdict:** see the table: survived, with no evidence of the mechanism. The KRT premium is a cross-sectional transfer; one market's time series is a weak test of it.

### 2. IREV: trading against index serial dependence
- **Source, read** (BvBD, JFE 132(1) 2019, accepted manuscript; 20 indexes, sample to 2016-12).
  - Since about 2000, index autocorrelation is negative.
  - Trading against MAC(5), that is holding −(4r₁ + 3r₂ + 2r₃ + r₄), earns a Sharpe of 0.63 on all indexes and 0.67 on the S&P 500, gross, after 1999-03. The authors add: "perhaps … not exploitable … after … transaction costs".
- **Rule.**
  - Each index trades at its own cash-close anchor, holding −0.01/σ × clip(u, −2, 2) with u = (4z₀ + 3z₁ + 2z₂ + z₃)/√30, and σ the sd of the last 60 sessions.
  - One index per country; the Dow is left out, as in the paper.
  - The book is `event_multi.book` (REBAL's close-to-close book, generalised), with C8 costs on every change and swap-free.
- **Ex-ante cost gate (≥ 3×, from the paper's 0.63 at the book's risk):** US500 4.1×, UK100 4.9× and JP225 3.05× are admitted; EU50 (5.6 bp spread at the close, 1.6×) and AUS200 (2.7×) are out.
- **Result:** −0.21, t −0.70, **KILLED.**
  - Implied gross ≈ 0: the 1× and 2× results differ by the whole cost.
  - Its correlation with REBAL v1a is +0.30 (expected +0.2).
  - 2017–2023 earned −0.31. IREV leaves the pipeline.

### 3. FXVALUE: currency value against PPP
- **Source, read** (AMP, JF 68(3) 2013, sec. I.B, eq. 1, Table I). The currency value factor earned 3.9% a year at a Sharpe of 0.44, 1979–2011, on forward returns (interest included). Its correlation with currency momentum is −0.42.
- **Rule.**
  - Value = log(mean ECB USD-per-unit spot, months m−65..m−54 / the last fixing of m), minus the relative 5-year CPI change, with CPI read at m−4.
  - USD and the six currencies are ranked; the forecast is 5 × (rank − 4) on each dollar pair, held through m+1.
  - Graded by RSIM on the six dollar pairs.
- **Inputs (P&L-blind, sha256 in the outcome):** the ECB daily reference rates 2005–2025 and the BIS long CPI (`scripts/download_fx_value.py`). The ranks make sense: JPY was dearest in 2012-01 and cheapest in 2015 and 2023.
- **Dry check:**
  - The ranks changed in 83 of 143 months, with forecast turnover of 1.7 A a year.
  - The cost is about 0.001 SR per pair.
  - Window roles: 2012–2020 was seen by the century study the slate cites, so 2021–2023 is the clean segment.
- **Result:** see the table.

### 4. DCARRY: the dollar carry trade, spot only
- **Source, read** (LRV, NBER w16427 = JFE 111(3) 2014).
  - The developed basket earned 5.60% a year at a Sharpe of 0.66, 1983–2010.
  - The spot part was 3.77% (se 1.67%): about two thirds is spot, so the trade is expressible swap-free.
- **Rule.**
  - AFD = mean over EUR, JPY, GBP, AUD, CAD and CHF of (overnight rate − USD), read 3 days before month-end.
  - The forecast is ±10, long foreign when AFD > 0, on the six dollar pairs.
- **Dry check:** long foreign for 47 months and long USD for 96, with one flip (2015-12). Two dollar bets: low power, declared before the look.
- **Result:** −0.31, t −1.12, **KILLED** (2012–2017 −0.93, 2018–2023 +0.28). DCARRY leaves the pipeline.

### 5. HALLOWEEN: the "Sell in May" contrast
- **Source.**
  - Bouman & Jacobsen (AER 2002; 37 markets, 1970–1998).
  - Andrade, Chhaochharia & Fuerst (FAJ 69(4) 2013, out of sample 1998–2012): November–April beat May–October in all 37 markets, by about 10 percentage points. The FAJ paper's text was not fetched; the numbers are from its abstract and the CFA digest.
- **Rule.**
  - Long into November–April sessions and short into May–October, sized once a season at 0.01/σ.
  - US500, UK100, EU50, JP225 and AUS200, each at its own cash close.
  - The contrast shorts the summer instead of holding bills, so the equity premium nets out (OPEX's lesson).
- **Dry check:** 21–25 trades per index in 12 years, costing 0.05–0.16% a year against an ex-ante gross of about 9–13% (pre-decay). Window roles: 2012 seen.
- **Result:** see the table.

## Candidates DROPPED ex ante (no look spent)

| Candidate | Source | Why dropped |
|---|---|---|
| USLEAD (lagged US returns → non-US indices, monthly) | Rapach, Strauss & Zhou, JF 2013 | The source's own replication (Siliverstovs 2015, on RSZ's data and code) finds the predictability accrues almost only in NBER recessions, and 2012–2023 holds one two-month recession. The UK's out-of-sample R² was insignificant and Australia's negative. |
| VOLMAN (volatility-managed index exposure) | Moreira & Muir, JF 2017 | Cederburg, O'Doherty, Wang & Yan (JFE 2020): out of sample, vol-managed portfolios underperform in 72 of 103 strategies, with no systematic outperformance in direct comparisons. A long-only version is beta, and the honest contrast's expectation is about 0. |
| ANNOUNCE (macro announcement premium, NFP and CPI days, US500 contrast) | Savor & Wilson, JFQA 2013 | Data, not merit. BLS refuses scripted access (403 from both machines); FRED is unreachable from the laptop, and its release calendar is script-rendered on the server. A free FRED API key (ALFRED vintage dates) would make it buildable P&L-blind. The FOMC days are excluded (graveyard H9/H10). |
| SILVER leg of HEDGEP | KRT 2020 | Cost gate 1.1×: XAG's ~15 bp spread. |
| EU50 and AUS200 legs of IREV | BvBD 2019 | Cost gates 1.6× and 2.7×. |
| SEASON (same-month return seasonality) | Keloharju, Linnainmaa & Nyberg, JF 2016 | Data: its 20-year formation window needs index history before 2012, and no official source is on disk. |
| ECONMOM-FX (economic momentum) | Dahlquist & Hasseltoft, JFE 2020 | Data: five macro series × 7 countries are not on disk. A CPI-only version would not be the paper's rule. |
| XBOND (past bond returns → equities) | Pitkäjärvi, Suominen & Vaittinen, JFE 2020 | It reads the same bond-versus-equity information as REBAL (ρ expected positive) and is TSMOM-adjacent: a near-duplicate. |
| FX cross-sectional momentum | Menkhoff et al. 2012; AMP Table I | A near-duplicate of D1 (trend on the same currencies). |
| BoJ ETF afternoon purchases (JP225) | Barbon & Gianinazzi 2019 | The mechanism ended (purchases rare after 2021, stopped in 2024), so no forward value, and it is intraday. |
| Daily cross-asset lead-lag (US500 → AUD/JPY, Asian indices) | — | The CFDs trade concurrently for about 23 hours, so a cash-market lag is priced before any daily decision. No published predictive lag between concurrently traded instruments was found. |
| Equity-flow FX at a daily clock | Hau & Rey 2006 | A near-duplicate of FXHEDGE (the same hedging-flow mechanism). |
| Slow TSMOM on metals and indices | MOP 2012, D1's slow members | A near-duplicate of D1 on 21 instruments and TSMOM as built. GAP-P12D-151 flags the slow-member pick as a forking path. |
| Terms of trade (metals → AUD) | Chen, Rogoff & Rossi, QJE 2010 | The source finds the reverse direction: exchange rates predict commodity prices. |
| GSCI-roll front-running in metals | Mou 2010 | The flow moves the futures calendar spread, not the spot price a CFD tracks. |
| Index reconstitution flows | Greenwood & Sammon 2025 | It moves constituents against each other, not the index level a cash-index CFD holds. The inclusion effect has decayed to 0.3%. |

## For the lead (record or ask; FACTORY edited no ledger or read-path file)

1. **Record looks `000045`–`000054`** in [[GAP-P12D-158]]: five families, two KILLED (IREV, DCARRY) and three survived (HALLOWEEN, HEDGEP, FXVALUE). The register is anchored at `000054`. The TODO header still says looks `000001`–`000028`.
2. **Hand the three survivors to TOURNAMENT** with their caveats above. Each forward record needs its own live rule written down before it runs (as REBAL's and GOTOBI's drafts were).
3. **The brief listed GER40 and US100 as usable**, but they are R1-D5 held-out instruments (LOCKED, stage C only; `tests/backtest/universe.py`), so FACTORY did not touch them. Correct the brief template.
4. **ANNOUNCE needs data:** a free FRED API key (owner action) or BLS access. It is optional; if the owner wants it, it gets a version and a look like the others.
5. **[[GAP-P12D-156]] PC-I-10 is still open.** The new multi-index book uses `event_daily.quoted` (REBAL's moved-mid rule), as OPEX did; the shared-predicate unification is still owed.
6. **Tests.** Local runs: the new unit tests (12), the module budget, the import contracts and the ledger integrity test all pass, and code-shape finds no new violations. **The full suite was not run.** Run it on the server at the next start; commit `00b9d3c` adds three test files.
7. **Stage C (2024–25) for any survivor is the owner's call** and was not run. With HALLOWEEN's two switches a year, a two-year holdout is close to powerless (about four seasons).

## Method notes

- **Budget used:** web, 7 WebSearch calls; the rest were curl fetches of the papers and data issuers.
- **Compute:** the laptop only; the five looks took about 5 minutes together. The Google server was used only to probe FRED and BLS reachability.
- **Contamination.** The model knows market history to 2026-06. Expected correlations were written into each script before its look; the measured ones are in the table. The origin's `proposed` date is 2026-10-04 (local), a day after the UTC registration date, which only makes the claims' boundary later (stricter).
- **New code** (all in `00b9d3c`):
  - `tests/backtest/event_multi.py`, `irev.py`, `halloween.py`, `fx_value.py`, `dollar_carry.py`, `hedgep.py` and `factory_looks.py`;
  - the tests `test_factory_books.py`, `test_factory_fx.py` and `test_hedgep.py`;
  - `scripts/download_fx_value.py`, `download_cot.py` and `r1_{hedgep,irev,fxvalue,dcarry,halloween}_kill_test.py`.
  - No module exceeds 300 lines and every header is at most 20 lines. `config/instruments.yaml` was not touched.
- **Sources:**
  - BvBD: personal.eur.nl/vanbekkum (accepted manuscript).
  - KRT: uc.cl conference PDF (2016 version).
  - AMP: pages.stern.nyu.edu/~lpederse.
  - LRV: nber.org w16427.
  - Siliverstovs: ecomod.net.
  - CFTC: the release schedule and the `deacot` histories.
  - ECB: the data API (EXR).
  - BIS: WS_LONG_CPI.
  - Andrade et al.: via the CFA Institute abstract; Cederburg et al.: via the abstract and the search summary.
