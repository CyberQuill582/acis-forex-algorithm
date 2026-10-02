# RESEARCH — GATES: how much ACIS's risk layer keeps it out of the market, and what should replace it (2026-10-02)

**Author:** GATES, one of the five research agents the owner launched on 2026-10-02 (fresh context, Opus 5.5). **Status:** research findings for the lead to verify. Nothing here is a ledger entry, a ratification or a spec change. `config/guardrail_limits.yaml` was only READ. Every guardrail change below is a proposal to the owner.
**Evidence rules kept:**
- P&L appears only on the **synthetic lab** (C-BT-12: machinery, never edge).
- The **real candles** were read **P&L-blind**: positions, time in market, cap binding and VaR from price volatility. No return, P&L, Sharpe or win rate of any rule was computed on them (`REAL_LOOKS_OPEN = False`, asserted by the probe).
- Every measurement ran on `acis-compute-1`, in this agent's checkout of `de96a75`, with at most 4 worker processes (about 1 h 25 min of server time).

---

## 1. The answer, in plain language

**Today the risk layer behaves like a vault door, not like a risk manager.**

The test market is the synthetic lab with a planted trend: an oracle Sharpe of 1.0 per instrument and a 40-day half-life. The TREND family's D1 earns a Sharpe of about 0.9 there. On that market, the full gate stack as built, on a $10k live account, keeps **12% of the expected return**: 1.1%/yr instead of 8.8%/yr. It holds a position on **32% of instrument-days instead of 69%**.

**Five gates do almost all of that.** In order of harm:
1. the notional cluster cap;
2. refusing to add to a held position, which on a live book acts as a one-lot cap;
3. the currency-delta cap;
4. the undiversified VaR cap;
5. the alpha-decay throttle.

**None of the five earns its place.** Each one lowers the return earned per unit of drawdown below what the same book gets by simply trading smaller. They cut gains more than losses, so they starve the book rather than protect it.

**Three gates are inert or nearly free:**
- The engine's 2% daily halt never fires at this size: the book realises about 9% a year, about 0.56% a day.
- An instrument halt that clears itself costs about 0.06 pp a year.
- NVMA's veto at the 08:00 slot costs 0.03–0.18 pp a year, because a blocked entry retries the next day.

**Two gates are traps:**
- **The VaR cap and the Risk-side cluster check can raise a human-only global HALT.** Unattended, that ends trading for good. Added alone, the VaR gate did it in 32–40% of 10-year lab runs and the cluster check in 16–32%.
- **The alpha-decay throttle can lock a one-lot book out permanently.** At the end of 10 lab years it was still armed in 38–64% of runs of the demo configuration. A one-lot entry × 0.25 is zero, and only new closed trades can clear the throttle, so a flat book never recovers. No human path clears it either: `on_human_resume` only re-arms the halt latches.

**The proposed replacement** (§4) has six parts:
- Size every day to a **daily risk budget**: 1% of initial capital a day on a $10k challenge.
- Shrink that budget **in proportion to the cushion** left above the firm's lines (Grossman–Zhou).
- Cap the **whole book's forecast risk** instead of its notional.
- Round lots to the **nearest** lot instead of toward zero (as pysystemtrade does).
- Let every restriction **clear itself when its condition clears**.
- Judge the edge on a **shadow book**, never on trades the gate itself prevented.

**What it does in the same lab:**
- It keeps 95% of the gate-free book's return: 8.35%/yr at a Sharpe of 0.94, against 8.77% at 0.90.
- On the **no-edge null market**, it cuts the chance of ever touching the 10% max-loss line in ten years **from 72% to 4%**, and to 0% at a 0.6% budget.

That is "tight on losing, not stuck".

**Scale the budget down only, never up.** Using the budget as a target as well as a ceiling helped only the easiest market. It lowered the Sharpe in the correlated-trend and weak-trend markets and raised null failures from 4% to 18%.

**For the demo:**
- Your $100k-account ruling (GAP-P12D-142) was right. On the real candles (P&L-blind) it lifts time in market from 29% to 71%, and it removes the alphabetical cap bias: at $10k, GBP_USD was held on 2% of days and AUD_USD on 77%.
- What still starves the demo is the alpha-decay lock-in (a risk after about 3 years of trades) and, to a lesser degree, the regime veto at the slot.

**Caveats:**
- The lab plants the edge, and the real edge is unknown (GAP-P12D-49). Size scales an edge; it never creates one.
- Most of §4 changes guardrails or HALT semantics. Those are yours to ratify, after rung 1, as you ruled on 2026-10-02.

---

## 2. The friction census

Abbreviations: **TIM** = time in market (share of instrument-days holding a position); **NAV** = account equity; **RSIM** = the research simulator.

### 2.1 The R1.6 target path, synthetic lab (P&L allowed)

**Setup** (probe `target_gates_lab.py`):
- 13 lab instruments carrying the 13 explored FX names, clusters and currency legs. Mids are scaled to each pair's USD-per-base value, so one lot ≈ $660–$1,270.
- 10 graded lab years per seed, 50 seeds per market.
- The sizing is THE engine function, `core/governor/target.py` `banded_target`, at $10k capital_ref, a 20% vol target, IDM 1.5, a 10% buffer and 1,000-unit lots.
- The forecast is the registered D1 (`core/signals/rules.py`), the costs are the lab's C8 template, the venue is swap-free, and the alpha-decay throttle is the production `AlphaDecayDetector`.
- The gate arithmetic is restated from `target_gate.py`, `guards.py`, `exposure.py`, `guardrails.py` and `drawdown_series.py`. Declared approximations are in §7.

**The configurations:**
- **REF_lots** is the target book with the one lot rule only.
- **FULL_B** is every gate as built, on a $10k live account: adds refused, cluster and currency caps with G-5 headroom, the VaR taper and halt, the sticky instrument halt, the 2% daily taper and halt, alpha decay, and NVMA's slot veto at p = 0.43.
- **FULL_A** is the demo as ruled: $100k NAV, $10k sizing at 20%, the one-lot cap and every gate.

**Census on the trend market t10h40.** Attempts are counted per year; a blocked entry is re-attempted at every decision, so attempt counts are inflated and TIM is the clean measure.

| Gate | Where it acts | FULL_B: zeroes / yr | FULL_A demo: zeroes / yr | TIM it removes, added alone to REF_lots |
|---|---|---|---|---|
| Cluster cap (20% NAV gross, 90% headroom) | entry, §7.4 | 552 | 0 (NAV $100k) | **−40.6 pp** (+ global halt in 32% of runs) |
| Adds refused (`add_unsupported`) | increase | 733 refused | n/a (capped) | +4.0 pp (positions stay one lot; see note 1) |
| One-lot cap (practice, D-a) | target | n/a | binds | +4.0 pp (note 1) |
| VaR taper/halt (3% undiversified) | entry + global halt | 99 halt-blocked (all sources) | 0 | **−20.0 pp** (global halt in 32% of runs) |
| Currency net-delta cap (30%, 90%) | entry | 2 | 0 | −9.9 pp |
| Instrument halt, sticky (1% NAV open loss) | entry, per instrument | 24 | 0 | −10.4 pp (0.28 halts/yr) |
| Instrument halt that clears (ACIS-07 §8 reading) | entry | — | — | −0.1 pp |
| Alpha decay (×0.25, then re-lotted) | entry | 26 | **105** | −9.3 pp (armed 41% of days on a true edge) |
| NVMA slot veto, p = 0.43 (as measured, §2.3) | entry | 538 | 96 | −0.7 pp |
| NVMA slot veto, p = 0.11 (LOW_CONFIDENCE only) | entry | — | — | −0.1 pp |
| Engine daily drawdown 2% (taper 60–80%, session halt) | entry | 0 | 0 | 0.0 pp (never binds: realised vol ≈ 9%/yr) |
| Weekend ban (2 h before close) | entry | 0 by construction: FX slots are 08:00 NY, the ban starts 15:00 NY Friday | 0 | 0 |
| Blackout | entry | 0: `pepperstone_demo` has `news.restricted: false`, and no event calendar exists (GAP-P12D-03) | 0 | 0 |
| Equity floor $9,000 (= a 10% max loss) | flatten + halt | REF_lots dies in 6% of t10h40 runs and 72% of null runs in 10 years | 0 (NAV $100k) | — |
| **Resulting TIM** | | **32.3%** (REF_lots 69.4%; continuous 94.4%) | **66.6%** | |

Note 1: in this lab, a one-lot book (or one that refuses adds) holds a position slightly more often than the uncapped lot book: TIM 73.4% against 69.4%. I did not find the mechanism. It does not affect the return or cost results.

**Source:** `lab_agg.txt`, built from `/opt/acis/gates_out/lab_{t10h40,…}.json`. The same census on the other markets (t05h160, f10h40, null) is in that file; the gate ordering is the same in every market.

### 2.2 The R1.6 target path, REAL candles, P&L-blind

**Setup** (probe `real_census.py`):
- The 13 explored FX pairs, development tier, decisions 2012-12-31..2023-12-29 after warm-up: 2,867 decision days.
- D1 forecasts and banded targets are computed day by day. NAV is held fixed, because no P&L may move it.
- Only position-based gates are measured.
- **Not measured on real data** (they need P&L or ticks): the daily drawdown, the instrument halt, alpha decay, the equity floor and NVMA.

| Scenario | TIM | Mean positions | Gross / NAV | What zeroes entries | Undiversified VaR, median / p95 |
|---|---|---|---|---|---|
| **Demo as ruled** ($100k NAV, $10k sizing at 20%, one lot) | **70.9%** | 9.2 | 0.10 | nothing | 0.12% / 0.17% |
| Demo at 10% (the pre-ruling R6-5) | 43.9% | 5.7 | 0.06 | nothing | 0.07% / 0.13% |
| One lot on a $10k NAV | **29.0%** | 3.8 | 0.37 | cluster cap: 98% of attempts | 0.43% / 0.62% |
| Live as built, $10k (adds refused) | 27.5% | 3.6 | 0.35 | cluster 98.8%; 5,594 adds refused | 0.41% / 0.62% |
| Live, $10k, adds gated as entries | 27.2% | 3.5 | 0.38 | cluster 98.4% | 0.45% / 0.68% |
| No notional caps, toward-zero lots, $10k / 20% | 70.9% | 9.2 | 2.22 | — | **2.36% / 4.17%** (VaR taper zone on 70% of days) |
| No caps, nearest lots | 84.7% | 11.0 | 2.86 | — | 3.17% / 4.97% (taper zone 91%) |
| No caps, 10% vol | 43.9% | 5.7 | 0.82 | — | 0.82% / 1.72% |
| Continuous reference (no lots) | 100% | 13.0 | 2.88 | — | 3.18% / 5.02% |

**What a book sized at $10k wants, before any gate:**
- At a 20% vol target the median optimum is **1.77 lots**. It is below one lot on 29% of instrument-days (rounded to flat toward zero) and below half a lot on 15%.
- The demo's one-lot cap binds on **71%** of instrument-days, and the optimum exceeds two lots on 44%.
- At a 10% vol target the median optimum is 0.89 lots, below one lot on 56% of instrument-days.

**The alphabetical cap bias** (GAP-P12D-142), now measured on real candles. With one-lot positions on a $10k NAV, the share of days each pair holds a position:

| Pair | $10k NAV, one lot | Demo ruling ($100k NAV) |
|---|---|---|
| AUD_USD | 77% | 82% |
| AUD_JPY | 55% | 72% |
| USD_CHF | 41% | 63% |
| CHF_JPY | 40% | 77% |
| EUR_USD | 7% | 78% |
| GBP_JPY | 3% | 62% |
| GBP_USD | 2% | 64% |

**Source:** `real_census.json`, `real_per_inst.py`.

### 2.3 NVMA at the target slot (synthetic ticks, P&L-free)

**Setup** (probe `nvma_slot_census.py`):
- The production `MarketStateFactory` and NVMA run on the C-BT-12 tick generator: EUR_USD and USD_JPY, 126 days, null and planted.
- Each instrument is classified at the runtime's 120 s cycle, with `has_params = True`, because the family's registration satisfies the no-params veto (D-a).

| | null | planted |
|---|---|---|
| Classifications tradeable | 63.8% | 63.9% |
| ILLIQUID regime / LOW_CONFIDENCE veto | 23.8% / 12.3% | 23.7% / 12.3% |
| **08:00 New York slots that would zero an entry** | **42% (73/174)**: ILLIQUID 58, LOW_CONFIDENCE 15 | **44% (77/174)**: ILLIQUID 58, LOW_CONFIDENCE 19 |
| Not-tradeable share at NY hours 7 / 8 / 9 | 0.32 / **0.42** / 0.32 | 0.32 / **0.43** / 0.33 |
| Legacy demo (one champion, WEAK_TREND_UP): classifications tradeable | **5.0%** (NO_PARAMS on 58.9%) | 5.0% |

**How to read it:**
- The ILLIQUID share is probably inflated by the generator's constant-fraction spread. NVMA's test is spread > session median + 2σ of the window's spreads, and a near-constant spread has a tiny σ.
- **The real-tick rate is unmeasured here**, because the tick set is not on this server. The demo's own logs can measure it with no P&L (§6, question 1).
- **The 08:00 NY slot sits exactly on a configured session boundary** (`session_boundaries` includes New York 08:00). The not-tradeable share is about 1.3× higher in that hour than in the hours either side.

### 2.4 The legacy path (QIEA champion → AGON → Governor)

| Gate | Evidence | Frequency |
|---|---|---|
| Regime-veto discards in AGON | 2026-09-29 ladder, rung 1x, real engine on the planted C-BT-12 market, 25 folds, 985 days (`REPLAY_LOG_SUMMARY` of `run_rung_1x.jsonl`) | 2,091,420 of 3,857,260 signal evaluations (**54.2%**); sub-threshold 0.3%, opposite 0.1%; 1,749,192 sized → 1,690 trades (one position per instrument) |
| NO_PARAMS veto with the demo's one champion | §2.3 | 58.9% of classifications; only **5.0%** tradeable |
| Factor product (conviction × liquidity × correlation × stability·confidence × marginal α × vol-norm × taper) | the first 200 `SIZED` samples of the same log (sampled log, warm-up-biased) | means 0.68 × 0.80 × 0.94 × 0.32 × 1.0 (pinned) × 1.0 (pinned) × 1.0 → the median order is **144 units**, about 14% of the $1,000 base unit |
| The minimum lot in live | code: `capital_governor.py` `_allocate_one`, C-EXE-6 | a 144-unit formula order is below the 1,000-unit minimum, so in live it rounds to zero (GAP-P12D-57) |
| Partial taper and alpha decay in paper/practice | code: `fixed_units` replaces the formula size after the multipliers | **No effect**: only a taper of exactly 0 zeroes (`formula_zero`). The target path zeroes a one-lot entry under ANY taper < 1 or decay. The same Risk edge acts differently on the two paths |
| Weekend ban | config: `weekend_entry_buffer_s: 7200` | 2 h of a ~120 h week (~1.7%) |

---

## 3. The expectancy cost of each gate (lab)

**Method:**
- Each gate is added alone to REF_lots, and the difference is paired by seed: mean [standard error], 50 seeds.
- "Protects" means the gate improves return per unit of maximum drawdown (the "ret/maxDD" column) or the Sharpe, against REF_lots.
- A gate that lowers ret/maxDD is **dominated by simply trading smaller**, which keeps ret/maxDD and the Sharpe unchanged: it cuts gains more than losses.
- The **null market has no edge**, so there every gate trivially "reduces" drawdown by reducing exposure. Read the null column for tail protection, not for return.

| Gate (added alone) | Δ return, t10h40 (pp/yr) | Δ Sharpe | Δ return, t05h160 | Δ return, f10h40 | Null: Δ max DD | t10h40 ret/maxDD (REF 0.54) | Verdict |
|---|---|---|---|---|---|---|---|
| Lot rounding toward zero (REF_lots vs continuous) | −1.77 [0.15] | −0.03 | +0.10 [0.40] | −0.93 [0.45] | — | 0.54 vs 0.56 | a physical constraint; costs exposure, not Sharpe |
| **Nearest rounding instead** (REF_nearest − REF_lots) | **+1.65 [0.18]** | +0.01 | +0.03 | +0.98 | +1.5 | 0.54 | recovers 93% of the rounding cost on t10h40 |
| Cluster cap at $10k | **−7.36 [0.56]** | **−0.31** | −3.82 | −6.38 | −13.6 | 0.28 | **starves** (worst) |
| One-lot cap / adds refused | −5.87 [0.48] | −0.05 | −2.97 | −4.66 | −10.5 | 0.45 | de-leverages (Sharpe kept), but ret/DD falls |
| Currency cap | −3.79 [0.42] | −0.11 | −1.84 | −2.93 | −5.0 | 0.41 | starves |
| VaR gate (3% undiversified; human-only halt) | −3.18 [0.48] | −0.18 | −1.63 | −3.05 | −5.7 | 0.43 | starves, and a trap (global halt in 32–40% of runs) |
| Alpha decay | −1.77 [0.17] | −0.08 | −0.62 | −1.77 | −3.0 | 0.48 | starves; armed 38–41% of days on a TRUE edge |
| Instrument halt, sticky | −1.61 [0.27] | −0.10 | −0.62 | −1.43 | −1.7 | 0.45 | starves |
| Instrument halt that clears | −0.06 [0.02] | −0.01 | −0.09 | −0.03 | −0.5 | 0.54 | ≈ free |
| NVMA slot veto, p = 0.43 | −0.18 [0.02] | −0.01 | −0.08 | −0.15 | −0.6 | 0.53 | a small delay cost |
| Daily drawdown 2% | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.54 | inert at this realised vol |
| **FULL_B, all gates as built** | **−7.68** (1.09 vs 8.77%/yr) | −0.32 | −3.85 (0.63 vs 4.48) | −6.47 (1.15 vs 7.62) | −15.1 | 0.26 | keeps 12–15% of the expectancy |
| FULL_A demo (one lot, NAV $100k) | −6.18 [0.49] | −0.10 | −3.15 | −5.33 | −10.7 | 0.42 | the one-lot rule (D-a) is most of it |
| **PROPOSED, b = 1%/day, nearest** (§4) | **−0.42 [0.13]** | **+0.03** | −0.63 | −1.18 | −2.1 | **0.55** | protects: null failure 72% → 4% |
| PROPOSED, b = 0.6%/day, nearest | −3.58 [0.35] | +0.07 | −1.86 | −3.03 | −6.8 | **0.56** | protects most: failure 0% in every market |
| PROPOSED, toward-zero lots, b = 1% | −1.93 [0.21] | +0.04 | −1.28 | −2.27 | −3.7 | 0.55 | |
| PROPOSED, scale UP to b = 1% (a target, not a ceiling) | +5.27 [0.46] | +0.09 | +1.29 (Sharpe −0.08) | −0.69 (Sharpe **−0.14**) | +4.0 | 0.57 | **rejected**: not robust; null failure 18% |

**Leave-one-out inside FULL_B** (the gain from removing one gate while every other stays):
- Removing the **cluster cap** is the only removal that matters: +1.15 pp/yr [0.11] and TIM +28 pp on t10h40.
- Every other single removal gains under 0.2 pp, because the cluster cap then binds in its place.
- Fixing the gates one at a time will look useless. **The stack has to be replaced as a whole.**

**Prop-relevant tails over 10 lab years** (failed = equity below 90% of initial, or a firm-day loss over 5% in the firm's balance semantics):

| Configuration | t10h40 | t05h160 | f10h40 | null |
|---|---|---|---|---|
| REF_lots | 8% | 18% | 22% | 72% |
| FULL_B | 0% | 2% | 0% | 6% (it barely trades) |
| PROPOSED b = 1% | 4% | 0% | 2% | 4% |
| PROPOSED b = 0.6% | 0% | 0% | 0% | 0% |

- Breaches of the firm's 5% daily limit were at most 2% of runs in every configuration except the rejected scale-up (up to 10%). **The binding prop risk for a daily trend book is the static max-loss line, not the daily line.**
- **Sources:** `lab_agg.txt`, `lab_extra.txt`, `labP_agg.txt`.

---

## 4. The proposed risk design: expose capital when the math agrees

**Principle.** A restriction must either (a) shrink risk continuously and in proportion to how close the account is to a line it must not cross, or (b) be a bug-catcher that should never bind in normal operation. A restriction that blocks entries on a proxy (notional, a minutes-scale regime label, a low-power test on past trades) and then waits for a human is starvation, not protection. §3 measures exactly that: each such gate is dominated by trading smaller.

### 4.1 The rules, with numbers for a $10k prop account (daily loss 5%, max loss 10%)

Notation: C0 = $10,000 initial capital; firm daily floor = the firm's 00:00 balance − $500; static floor = $9,000.

**R1. The risk unit is a daily P&L-volatility budget.** b_base = 1.0% of C0 a day ($100, about 16%/yr) during a challenge, and 0.6% ($60) for a funded account or a personal account.
- The book is Carver's target with cash_vol = b_t (equivalently vol_target = 16 · b_t / C0), recomputed at every decision for the WHOLE book.
- Reductions are never blocked.
- Kelly reasoning: growth g(L) = L·μ − L²σ²/2 is maximised at a vol equal to the Sharpe ratio, and half-Kelly keeps 75% of the growth at half the vol.
  - At the EDGE agents' realistic portfolio Sharpe of 0.25–0.5, Kelly vol is 25–50%/yr.
  - 16% is therefore about ⅓–⅔ Kelly, and 9.6% about ⅕–⅖.
  - Fractional Kelly is the textbook answer to uncertainty about the Sharpe (MacLean, Thorp & Ziemba).
- The budget is a **ceiling, not a target** (R3).
- **Status:** RATIFIED by the owner on 2026-10-02 as the post-edge plan G-1 (`archive/GUARDRAIL_PROFILES_DRAFT_2026-10-02.md`). Owner: values only.

**R2. The cushion throttle** (Grossman–Zhou 1993; the draft's G-3). b_t = min(b_base, room_t / 4), with room_t = min(equity − firm daily floor, equity − static floor). It is measured in the firm's own day and semantics: the midnight balance, tested on equity.

Worked values, with C0 = $10k:

| Equity | Firm daily room | Static room | b_t | Book scale |
|---|---|---|---|---|
| $10,000 (start of day) | $500 | $1,000 | min($100, $125) = **$100** | 100% |
| $9,600 the same day | $100 | $600 | $25 | 25% |
| $9,300 at the next day's start (P&L closed, so balance = equity; a floating loss carried past midnight shrinks the daily room, in the firm's semantics) | $500 | $300 | $75 | 75% |
| $9,100 | — | $100 | $25 | 25% |

- Exposure falls in proportion to the cushion, positions included, and **returns by itself** as the cushion recovers. No human is needed and nothing is sticky.
- **This replaces the §9.5 taper** (full size to 60% of a limit, then a cliff to zero at 80%).
- Lab: null failure 72% → 4%, at −0.42 pp/yr on the trend market.
- **Owner:** the taper fractions are guardrail values ("stricter allowed, looser rejected"), and this is looser in parts. Ratified as the post-edge plan G-3; its interaction with the taper floor needs a ruling.

**R3. A forecast-risk ceiling replaces the notional caps and the undiversified VaR gate.**
- The ex-ante 1-day σ of the ROUNDED book must stay ≤ b_t. σ comes from a trailing 250-day covariance of daily returns, shrunk toward a constant correlation (the shrinkage is my proposal, untested). If σ is above b_t, scale every target by b_t/σ and re-round.
- Concentration: each cluster's risk contribution ≤ 50% of b_t, and each currency's net risk ≤ 60% of b_t (G-2). Risk contributions are Euler, in the risk-parity sense of Maillard, Roncalli & Teïletche.
- Bug-catcher: gross notional ≤ 5× NAV for FX and 2× for indices and metals.
- **Scale down only.** Scaling up to the budget helped one lab market and hurt the other two (§3). This matches Harvey et al. (2018): volatility targeting does not improve Sharpe for currencies; it reduces the tails. Cederburg et al. (2020) found volatility-managed portfolios underperform out of sample in 72 of 103 strategies.
- VaR is kept as a REPORT. If it gates at all, it is the diversified 2.326 × σ from daily returns. The current gate uses 50 ten-second marks × √8640; high-frequency σ is biased by microstructure noise (Hansen & Lunde 2006), and that bias is unmeasured here.
- **Owner:** YES. Guardrail values `cluster_cap_pct`, `single_currency_delta_cap_pct`, `var_cap_pct`; G-2 and G-4, ratified as the post-edge plan. The personal profile keeps 20/30, as the draft says.

**R4. Round lots to the NEAREST lot inside Carver's band**, with the R3 ceiling checking the rounded book.
- pysystemtrade rounds to nearest (`.round()`) when it rounds at all.
- Lab: +1.65 pp/yr at an unchanged Sharpe. Real candles (P&L-blind): TIM 70.9% → 84.7%.
- Next step: Carver's greedy minimum-tracking-error rounding. In his test it beat simple rounding (Sharpe 1.19 against 1.06 for simple rounding, 1.17 unrounded; $100k, 45 instruments).
- **Owner:** YES, a spec amendment. Master §5 C8, "the one lot rule", owner-ratified at v2.22. RSIM and the Governor share the function, so parity holds by identity.

**R5. No sticky per-instrument open-loss halt.**
- An instrument's risk is bounded ex ante: its share of b_t at |forecast| 20 is at most 25% (my proposal), plus the R6-2 disaster stop.
- If an instrument halt is kept, it clears when its condition clears, which is the ACIS-07 §8 reading. Lab: −0.06 pp against −1.61 pp for the sticky one.
- **Owner:** YES. HALT semantics (GAP-P12D-139) and `per_instrument_drawdown_pct`.

**R6. A firm-day loss stop that FLATTENS.** At an intraday loss of 60% of the firm's daily room ($300 of $500), measured from the firm's midnight balance on equity, flatten everything. Entries resume automatically the next firm day.
- The engine's 2% session halt is inert in the lab at the realised vol.
- The real failure path is GAP-P12D-59: the engine's day is not the firm's day, and a breach halts but never flattens.
- Not measured: the lab is daily.
- **Owner:** YES. HALT/flatten semantics, master §8/§9.5, and `daily_drawdown_pct`.

**R7. A relative equity floor.** For example 92% of declared initial capital on a 10%-static account: flatten and halt (human resume).
- With R2 it is rarely reached: 0–4% of 10-year lab runs.
- **Owner:** YES. `equity_floor_usd`, GAP-P12D-56.

**R8. An edge monitor on the SHADOW book replaces the alpha-decay ×0.25.**
- The target path decides its target every day whether or not it is traded, so the shadow target book's daily P&L always exists.
- If a one-sided test rejects the registered Sharpe prior (for example a CUSUM, or the rolling one-year Sharpe's t < −2 — my choice, uncalibrated), set b_base × 0.5.
- Recovery is read off the shadow book. It is **never zero, and never waits for trades the gate itself prevents**.
- Why: the current detector needs 80 closed trades. At about 25 closes a year (lab, one-lot book), that is about 3 years before it can fire. After that its comparison is close to a coin flip: the standard error of a per-trade Sharpe over 50 trades is about 1/√50 ≈ 0.14, while the effect it tests is about 0.08 per trade at an annual Sharpe of 0.9. The lab armed it on 41% of days on a TRUE Sharpe-0.9 edge.
- **Owner:** YES. `alpha_decay_sharpe_mult` is a guardrail value, and the restrictive-state semantics are ACIS-07's.

**R9. NVMA's slot veto on the target path.** A vetoed entry retries within the slot window, every 120 s cycle for up to 60 minutes (my proposal), instead of waiting a day.
- Only SPREAD_VETO, STALE_STATE and MACRO_EVENT should delay execution. The regime type and LOW_CONFIDENCE come from a ~200-state window: about 67 minutes on the synthetic generator, likely a few minutes on live ticks. That says nothing about a 6-week hold.
- Consider moving the slot off the 08:00 NY session boundary, for example to 08:05.
- Lab cost today: 0.03–0.18 pp/yr, so this is low priority but cheap.
- **Owner:** YES. "Ambiguity = no trade" and the veto semantics are law (CLAUDE.md rule 5); this is a spec ruling, not a guardrail value.

**R10. Build adds as gated entries.** ACIS-05 v1.7 §6.4 already says "an increase is an ENTRY and meets every entry gate". Today a live book that cannot add is a one-lot book: −5.87 pp/yr.
- **Owner:** no ratification needed (a build item), but it is dormant until live opens.

### 4.2 What this does NOT do

- No catch-up or martingale sizing.
- No equity-curve filters (R2 is a cushion rule, not a performance filter).
- No risk above 1.25%/day on a challenge.
- No change that makes a guardrail reachable by code: every value stays human-commit, and the engine only reads it.
- No application before rung 1, as you ruled.

### 4.3 What can be done now, with no ratification (implementation or measurement only)

1. **Report realised daily P&L vol** as a % of initial capital in every grading run (GAP-P12D-61 [impl]). The lab book realises about 9% a year at a 20% target (IDM 1.5, |forecast| < 10 on average), half the budget.
2. **Count every target-path zero by reason on the demo** (`TARGET_ENTRY_ZERO`, `nvma.veto_counters`) and publish the 08:00 slot veto rate on real Pepperstone ticks. This is P&L-free and answers §2.3's open number.
3. **Build the shadow-book daily P&L stream** that R8 needs, report-only.
4. **Build adds as gated entries** (R10), dormant.

---

## 5. Other findings for the lead (code-level; please verify)

1. **The alpha-decay throttle is an absorbing state on a one-lot book.**
   - `target_gate.py` `_entry_size`: size × 0.25, re-lotted toward zero, is 0 for one lot.
   - `alpha_decay.py` `evaluate`: once armed, it clears only on 20 new closed trades.
   - `monitor.py` `on_human_resume` → `guards.rearm()` does not touch `_alpha`, and `restore_restrictive_state` re-arms it at boot.
   - Lab, demo configuration: still armed at the end of 10 years in 38% (t10h40), 54% (t05h160), 64% (f10h40) and 42% (null) of runs.
2. **The Governor's `low_confidence` and `illiquid` guards cannot fire for contexts NVMA produces.** NVMA already marks `tradeable=False` for LOW_CONFIDENCE (the same 0.55 threshold) and for the ILLIQUID regime, so `guards.check` returns `veto` first. Dead branches (lean lens). They also blur the census, since every such zero is logged as `veto`.
3. **The two paths apply the same Risk edge differently.** On the legacy path in paper/practice, `fixed_units` overwrites the factor product after the taper and decay multipliers, so a partial taper or alpha decay has no effect. On the target path, any taper < 1 or a decay zeroes a one-lot entry.
4. **Global halts from mark drift.** The Risk monitor's cluster check uses marks; the Governor's uses entry notional with 90% headroom. In the lab, drift still pushed a capped book over 20% and raised a human-only global HALT in 16–32% of 10-year runs ("+cluster_cap" alone with adds gated as entries). With a human resuming after one day, FULL_B sees 0.35–1.04 global halts a year plus 0.26–0.38 instrument halts (`FULL_B_live10k_resume1d`); each one needs a person.
5. **The VaR cap is incompatible with the 20% book at $10k.** P&L-blind on real candles, an uncapped $10k/20% book's undiversified VaR is at a median of 2.36% of NAV, inside the taper zone on 70% of days, with a 95th percentile of 4.17%, above the 3% human-only HALT. The cap is consistent only with a one-lot book.
6. **The 08:00 New York slot coincides with a configured session boundary.** On synthetic ticks the veto rate is about 1.3× higher in that hour.
7. **J1 corroboration.** The demo's 10% → 20% vol ruling: real-candle TIM 43.9% → 70.9% (P&L-blind), in line with J1's 20–25% → 45–51% days-in-position at $10k. J1 measured whole-book days; this report measures instrument-days.

---

## 6. Open questions

1. **NVMA's real-tick slot veto rate.** P&L-free. Answerable from the demo's logs after the cutover, or by running `nvma_slot_census.py`'s logic on the laptop/AWS tick set.
2. **Intraday paths.** Every lab result uses daily closes, so it UNDER-states how often the instrument halt, the daily taper and the R6 flatten trigger. The R6 flatten threshold (60% of the firm's room) needs an intraday lab (`lab_intraday.py` bridges) before it is ratified.
3. **E8 One's real rules.** The archive (2026-09-24) records E8 One as 3% daily with a **4% dynamic drawdown**. For that account, R2's room is min(3% daily, 4% trailing), so b ≤ 0.75%/day at z = 4. The trailing line is exactly Grossman–Zhou's case: exposure ∝ (W − α·max W). Confirm at purchase (GAP-P12D-94).
4. **Correlation breaks and gaps** (CHF 2015). A trailing covariance under-states risk in a regime break. The gross-notional bug-catcher and per-profile scenario-replay ceilings (GAP-P11I-10) stay; their values are the owner's.
5. **The shrinkage, the per-instrument share (25%) and the R8 test** are my proposals and uncalibrated. R1–R4's numbers are the ones measured here.
6. **The one-lot TIM effect** (§2.1, note 1) is unexplained. It does not affect the cost conclusions.

---

## 7. How to reproduce

**Code under test.** Checkout `de96a75` at `/opt/acis/research-gates` on `acis-compute-1`, via the agent helper:
```
bash <scratchpad>/remote_research.sh gates "<command>"
```

**Probes.**
- Local: `<scratchpad>/research/gates/probes/`.
- Frozen on the server: `/opt/acis/gates_out/probes_final/`.
- The lab census ran `/opt/acis/gates_out/probes_snapshot/target_gates_lab.py`, sha256 `c3058ba9…60bd`.
- The PROPOSED-only variants ran `target_gates_lab_v2.py` = `probes_final/target_gates_lab.py`, sha256 `269b41cf…c1e`. It is v1 plus the scale-up configurations and the `ONLY` filter; the configurations both versions ran reproduce exactly.

**Commands** (run from the checkout):

| What | Command | Output in `/opt/acis/gates_out/` |
|---|---|---|
| NVMA slot census (synthetic ticks, P&L-free), ~150 s each | `python probes/nvma_slot_census.py {null,planted} 126 /opt/acis/gates_out/nvma_{kind}_126.json` | `nvma_{null,planted}_126.json` |
| Lab gate census (P&L, synthetic), ~16 s per seed | `python probes/target_gates_lab.py {null,t10h40,t05h160,f10h40} 1 50 2520 0.43 /opt/acis/gates_out/lab_{m}.json` | `lab_*.json` |
| Lab aggregate | `python probes/aggregate_lab.py /opt/acis/gates_out/lab_agg.json /opt/acis/gates_out/lab_{t10h40,t05h160,f10h40,null}.json` | `lab_agg.json`; local `<scratchpad>/research/gates/lab_agg.txt` |
| Lab extra columns | `python probes/extra_stats.py /opt/acis/gates_out/lab_agg.json` | local `lab_extra.txt` |
| Proposal variants | `ONLY=PROPOSED python probes/target_gates_lab.py {m} 1 50 2520 0.43 /opt/acis/gates_out/labP_{m}.json`, then `python probes/aggregate_prop.py /opt/acis/gates_out/labP_*.json` | `labP_*.json`; local `labP_agg.txt` |
| Real-candle census (P&L-blind), ~60 s | `python probes/real_census.py /opt/acis/data/dukascopy_candles /opt/acis/data/macro /opt/acis/gates_out/real_census.json`, then `python probes/real_per_inst.py /opt/acis/gates_out/real_census.json` | `real_census.json` |
| Legacy ladder counts | `python probes/inspect_log.py …/cost_stress/20260929T114406Z/logs/run_rung_1x.jsonl` and `python probes/inspect_sized.py <same>` (path under `/opt/acis/repo/data/validation/`) | stdout |

**The lab markets.** All are `LabSpec(n_inst=13, days=2520, seed=1..50)`:
- **null:** no effect.
- **t10h40:** `Effect(trend_sharpe=1.0, trend_halflife=40)`.
- **t05h160:** `Effect(0.5, 160)`.
- **f10h40:** a factor-scope trend, one shared trend factor.

**Declared approximations in the lab probe** (also in its `DECLARED` list):
- Fills happen at the decision close (rsim_lab's convention).
- The engine's daily drawdown at the slot is proxied by the held book's loss over the whole day.
- Instrument loss, VaR and cluster checks run once a day on closes.
- VaR σ is Carver's daily percentage vol.
- NVMA's slot veto is an independent Bernoulli(p), with p from §2.3.
- The notional per unit is the lab mid × a real pair's USD-per-base value, with q = 1.
- The venue is swap-free.
- Equity below $9,000 means the account is dead (flat forever).
- The 10 × ATR disaster stop is not modelled.
- Global halts never clear, except in the `_resume1d` variant.

---

## Sources (accessed 2026-10-02)

Grades: **(a)** primary source read directly; **(b)** primary source identified through a publisher or index listing or a search summary, not read in full; **(c)** recollection or derivation.

- Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." *Journal of Finance* 72(4), 1611–1644. Managed portfolios that take less risk when volatility is high raise Sharpe ratios for the market and several equity factors and for the currency carry trade. NBER WP 22208: https://www.nber.org/papers/22208 — **(b)**
- Harvey, C., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. & van Hemert, O. (2018). "The Impact of Volatility Targeting." *Journal of Portfolio Management* 45(1), 14–33, doi:10.3905/jpm.2018.45.1.014. It raises Sharpe only for risk assets (equity, credit); for bonds, FX and commodities the Sharpe effect is negligible; it reduces left tails everywhere. https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf — **(b)**
- Cederburg, S., O'Doherty, M., Wang, F. & Yan, X. (2020). "On the performance of volatility-managed portfolios." *Journal of Financial Economics* 138(1), 95–117. Out of sample, managed portfolios underperform in 72 of 103 strategies. https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html — **(b)**
- Grossman, S. & Zhou, Z. (1993). "Optimal Investment Strategies for Controlling Drawdowns." *Mathematical Finance* 3(3), 241–276. Risky investment ∝ the surplus W_t − α·M_t. https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html — **(b)**
- Kaminski, K. & Lo, A. (2014). "When do stop-loss rules stop losses?" *Journal of Financial Markets* 18, 234–254. Under a random walk, 0/1 stop-loss rules always lower expected return; with momentum they can add value. https://dspace.mit.edu/handle/1721.1/114876 — **(b)**
- MacLean, L., Thorp, E. & Ziemba, W. "Good and bad properties of the Kelly criterion" (Kelly and fractional Kelly). https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf — **(b)**. The half-Kelly arithmetic in R1 is a standard derivation — **(c)**.
- Maillard, S., Roncalli, T. & Teïletche, J. (2010). "The Properties of Equally Weighted Risk Contribution Portfolios." *Journal of Portfolio Management* 36(4), 60–70 — **(b)**, via search listing.
- Hansen, P. & Lunde, A. (2006). "Realized Variance and Market Microstructure Noise." *Journal of Business & Economic Statistics* 24, 127–161. https://ideas.repec.org/a/bes/jnlbes/v24y2006p127-161.html — **(b)**
- Carver, R. (1 Oct 2021). "Mr Greedy and the Tale of the Minimum Tracking Error Variance." Small-account integer positions; the greedy method's Sharpe of 1.19 against 1.06 for simple rounding and 1.17 unrounded ($100k, 45 instruments). https://qoppac.blogspot.com/2021/10/mr-greedy-and-tale-of-minimum-tracking.html — **(a)**
- pysystemtrade `systems/accounts/account_buffering_subsystem.py` `apply_buffer(..., roundpositions=False)`, which rounds with `.round()` (nearest) when enabled. https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/systems/accounts/account_buffering_subsystem.py — **(a)**
- Prop-firm daily and max-loss semantics (FTMO: 5% of initial from the 00:00 CE(S)T balance, tested on equity, 10% static; E8 One: 3% daily, 4% dynamic). Quoted from the firms' own pages in `archive/RESEARCH_PROP_VENUES_2026-09-24.md` lines 130–131, 186–187 and 275 — **(a) there; not re-verified today**.
- Repo: `archive/GUARDRAIL_PROFILES_DRAFT_2026-10-02.md` (G-1..G-5); KNOWN_GAPS GAP-P12D-56/59/61/101/139/142; the code cited inline.
