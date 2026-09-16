# External research: execution costs, financing, and fill fidelity for ACIS

**Date:** 2026-09-16
**Status:** research artifact, OUT of the orienting read path (`archive/`). Not a spec, not a ledger entry. **Nothing here binds until the owner ratifies it.**
**Author role:** trading-execution and market-microstructure analyst. Engine code was read (read-only); no code, config, spec or ledger was modified.
**Companion:** [`archive/RESEARCH_FX_METHODS_2026-09-16.md`](RESEARCH_FX_METHODS_2026-09-16.md) (same date, methods/statistics lens). Where the two overlap on the cost–horizon arithmetic they agree; §3 below explains why its "continuously exposed" drag figures and mine differ, and which applies to ACIS.

### Source grades used throughout

- **[ACADEMIC]** — peer-reviewed journal, NBER/BIS/central-bank working paper.
- **[BROKER-PRIMARY]** / **[REGULATORY]** — the venue's or the regulator's own published document.
- **[PRACTITIONER]** — a named practitioner or firm writing reproducibly under their own name.
- **[MEASURED HERE]** — computed by me from **this repo's own Dukascopy tick archive**. Scripts are in the session scratchpad; every number is reproducible from `data/dukascopy/`.
- **[DERIVED HERE]** — my arithmetic, inputs stated so you can check it.
- **[UNVERIFIABLE]** — broker marketing, review sites, forum claims. Used only where nothing better exists, and flagged.

---

## Executive summary — the findings that matter

> Three of these (F1, F6b, F6c) are **defects found by reading this repo's own code**, not research conclusions. They do not depend on any external source being right, and they are the cheapest things on the list to fix.

**F1 — The backtest harness charges no spread at all.** `tests/backtest/book.py::PositionModel.close_at` computes `friction = (slippage_per_side*2 + commission_per_side*2) * size`. The `spread` term that `core/optimizer/costs.py::CostModel.per_side_cost` exists to add is **never called from the harness** — only from `core/optimizer/fitness.py`. Entries are `state.mid` (every AGON module passes `state.mid` as `_Raw.entry`), exits are mid / stop / target, so the harness books a **mid-to-mid** trade. Realised round-trip friction in the graded harness is therefore **0.367 bps on EUR/USD and 0.267 bps on USD/JPY** [DERIVED HERE, from `config/instruments.yaml`]. The C8 comment in `costs.py` — *"the ACIS-09 backtest harness must import this same module … one module, one pinned-semantics test"* — is true of the import and false of the semantics. **This is a spec-conformance finding against two locked documents.** Master §5 **C8**: "fitness must apply the *same* spread + commission + swap/slippage cost model used by the §13 backtest harness" — the two paths are not the same model, and the harness is the cheaper of the two. And **`specs/ACIS-09-BACKTEST_VALIDATION.md` (v1.1, LOCKED) is explicit in the other direction**, verbatim:

> **Fidelity modelling (GAP-0001):** spread + slippage models are applied so backtest fills are **not naively at mid**; the report lists the models used…

with **C-BT-5** requiring "slippage/**spread** models documented". The harness fills naively at mid. **This is not a judgement call about how optimistic a cost assumption should be — it is a locked contract the code does not meet.**

**F2 — Even the fitness path is ~2.3× optimistic, and the harness path ~4× optimistic, versus a real OANDA account.** Measured Dukascopy median spread is 0.272 bps (EUR/USD) and 0.422 bps (USD/JPY) [MEASURED HERE]. OANDA's published typical spreads are **0.6 pips EUR/USD and 1.3 pips USD/JPY** [BROKER-PRIMARY], i.e. 0.55 and 0.87 bps round trip in spread alone; OANDA's core-pricing commission is **USD 0.70 per 10,000 units per leg** [BROKER-PRIMARY] = 1.28 bps round trip *before* spread. A realistic all-in retail round trip on EUR/USD is **1.0–2.3 bps, central ≈1.5 bps**. The harness models 0.37.

**F3 — That 4× understatement is almost certainly *why* evolution selected an 8-minute holding period.** Break-even information coefficient (expected gross edge ÷ per-trade standard deviation) at an 8-minute hold on EUR/USD is **0.091 at the modelled 0.37 bps** — reachable by an 11-gene search on in-sample data — and **0.371 at a realistic 1.5 bps**, which no retail FX system produces. The minimum viable holding period at a plausible IC of 0.05 moves from **27 minutes (modelled cost) to 7.3 hours (real cost)** [DERIVED HERE, §3]. The cost model is not a detail downstream of GAP-P12D-31; it is a plausible *cause* of it.

**F4 — Stops and targets are checked against `st.mid`, and fill at the exact level.** `PositionModel.maybe_close` compares `st.mid` to `pos.stop_loss`/`take_profit` and closes **at the stop or target price exactly**. Live, a long's stop triggers on the **bid** and fills at or through it; a target fills at the **bid** too. So every exit is optimistic by roughly half a spread *plus* whatever the stop slips — and a stop-out is precisely the moment slippage is worst. There is no gap-through model: a weekend or event gap that jumps the stop still books the stop price. **Measured weekend gaps are in §6.4.**

**F5 — Trading through Tier-1 releases is not a rounding error for this engine; it is an adverse-selection trap.** [MEASURED HERE, 10 NFP releases, this repo's ticks] EUR/USD spread in the first 10 s after NFP is **5.3× baseline** (1.33 vs 0.25 bps) and USD/JPY is **7.0×**; the |1-minute move| averages **32 bps on EUR/USD**, against a normal-minute standard deviation of **1.43 bps** — a ~22σ minute. Breakout and momentum-scalp modules trigger on exactly that tail, so event minutes are *massively over-represented* among entries even though they are <1% of minutes. §5 works the arithmetic: on plausible assumptions ~15–25% of triggers originate in event windows, carrying 10–30 bps of unmodelled cost, i.e. **2–6 bps of average per-trade cost error — 5–16× the entire modelled cost**.

**F6 — Financing has the right *shape* and the wrong *inputs*, and is second-order for this engine today.** `tests/backtest/financing.py` applies `direction × (r_base − r_quote) − fee`, value × rate × 1/365 per rollover — which is OANDA's published method almost exactly. Real retail practice diverges in four ways (§2): the base is tom/next, not policy (cross-currency basis **EUR −32 / JPY −26 / CHF −27 / AUD +4 / NZD +11 bps** [ACADEMIC]); quarter- and year-end turns add 40–60 bps and more; the fee is **not flat** (OANDA's own weekly tables moved FX **+20 bps/side and gold +120 bps/side in six months** while the funding base moved 0.01 %) and **is not the whole markup** (IG's own worked example decomposes to **316 bps round trip against 160 implied by its published fee — 1.97×**, because the raw LP tom/next bid–offer of 60–130 bps/side sits underneath); and `XAU_USD` inherits the 1.00 % FX fee when the real gold markup is **1.80–3.00 % per side**. Materiality at a 48 h cap: **−0.84 bps/night EUR/USD long, −1.65 gold long, −4.94 on a triple Wednesday in gold** — i.e. **negligible below 4 hours (~0.08 bps at 2 h) and decisive at 24–48 h and in gold**. It is not where the money is today; it becomes urgent the moment R6 lengthens the horizon.

**F6b — GAP-0001 does not cover F1.** `KNOWN_GAPS.md` GAP-0001 ("Backtest fidelity vs live microstructure", **accepted-risk**) accepts that "tick-data backtests cannot fully reproduce live spread dynamics, slippage, and queue position." That is a statement about an *irreducible* gap, and it is a fair thing to accept. **Charging no spread at all is not irreducible** — the exact per-tick spread is sitting in `st.spread` at both the entry and the exit call sites. Reading GAP-0001 as covering F1 would be the ledger failure mode CLAUDE.md warns about: a closed label over unowned work. F1 wants its own entry.

**F6c — The holding-period gene is measured in bars (1–48 *minutes*), is read only by the fitness proxy, and never reaches the engine.** `max_holding_periods` has exactly one consumer in the entire codebase (`fitness.py:126`); the engine's only time exit is the harness's fixed `max_hold_s = 48 h`. So QIEA optimises a horizon the engine cannot express, over a range 60× shorter than the engine's own cap, and the realised 8-minute duration is an artifact of stop/target geometry and same-side dedup rather than any policy. This is adjacent to **GAP-0035** but not covered by it — GAP-0035 is that fitness does not *exercise* the momentum/breakout/mean-reversion genes; this is that a gene fitness *does* exercise never reaches the engine at all — and it is **GAP-0075 quantified**. It is the reason §4's target-position / no-trade-band machinery is the structural fix rather than a refinement. See §0.

**F6d — The graded backtest is not the engine, in more ways than the cost model.** ACIS-09 §7.2(c) (LOCKED) requires the test replay to run "through the real ACIS loops … honouring … **Execution fill modelling** … exactly as production" and §7.2(d) to "collect **FillReports**". In fact the harness imports nothing from `core/execution/`; the fill model, the position de-duplication that turns 1,425,326 sized orders into 2,018 trades, and the only time-based exit all live in `tests/backtest/`, not in `core/`. Meanwhile the live engine's primary event defence (`MACRO_EVENT` via `macro_events_imminent`) is inert in the backtest because there is no historical calendar. **Several behaviours that decide what the backtest trades are the harness's; several the live engine will run are missing from it.** Every §14 number inherits that.

**F7 — Ranked, the single highest-value change is not more research: it is charging the spread in `book.py` and re-running the falsification.** It is a few lines, it is spec-mandated by C8, and it changes the break-even IC at the engine's realised 8-minute horizon from 0.091 to 0.158 — before any of the harder modelling upgrades. Everything else in §7 is downstream of getting the headline number honest.

---

## 0. What the code actually does today (read, not assumed)

| Path | Where | Round-trip friction charged |
|---|---|---|
| **QIEA fitness mini-backtest** | `core/optimizer/fitness.py:129,148,158` calls `costs.per_side_cost(bar.spread)` | `spread + 2×slippage + 2×commission` |
| **ACIS-09 graded harness** | `tests/backtest/book.py::close_at` | `2×slippage + 2×commission` — **no spread term** |

Supporting facts, all read from the repo:

- **Entry price is the mid.** Every AGON module constructs `_Raw(..., state.mid, ...)` (`core/signals/agon.py:379,399,403,427,445,502`); `_pipeline` sets `entry_price=raw.entry`; the Governor carries it through to `SizedOrder.entry_price`; `PositionModel.apply_order` opens at `order.entry_price`. Nothing anywhere converts mid → ask for a buy or mid → bid for a sell.
- **Exit price is the mid, the stop, or the target.** `maybe_close` tests `st.mid` against the levels and closes *at the level*, or at `st.mid` on `max_hold`.
- **Declared per-instrument friction** (`config/instruments.yaml`): `EUR_USD slippage_per_side 0.00002`, `USD_JPY 0.002`, both `commission_per_side 0.0`. `XAU_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `EUR_GBP`, `USD_CHF` declare **no costs block at all** — correctly refused by `PositionModel.cost` (GAP-P12D-19) while disabled, but it means the diversification basket has **no calibrated cost numbers yet**.
- **The calibration helper is unused in the graded path.** `data_loader.calibrate_cost_model(observed_spreads, slippage_fraction_of_spread=0.25)` exists and implements the §13 v2.9 "OANDA practice-feed calibration", but `tests/backtest/oos_runner.py:87` builds cost models via `evolve_step.cost_model(cfg, i)`, which reads the **static YAML numbers**. So the calibration path the spec describes is built but not wired into the run that produces a §14 grade.
- **Financing is applied**, per business-day rollover, in quote currency, converted once at the close rate (`book.carry_quote` → `carry.financing_charge` → `financing.make_financing`), with the triple-swap convention handled per instrument (`tom_next` Wednesday, `financing_daily` Friday). This part is genuinely well built.

**A third finding, and the most consequential one in this section: the holding-period gene never reaches the engine, and its range is 1–48 *minutes*.**
`core/optimizer/param_types.py:28` declares `"max_holding_periods": (1, 48, True)` — an integer gene in **bars**. At 1-minute bars that is **1 to 48 minutes**. `grep`ping the whole of `core/` finds exactly one consumer: `core/optimizer/fitness.py:126` (`if exit_mid is None and bars_held >= params.max_holding_periods`). **No module in `core/signals/`, `core/governor/` or the live loop reads it.** The only time-based exit that exists downstream is the harness's own constant `max_hold_s: float = 48 * 3600` (`tests/backtest/harness.py:93`).

So:

| | horizon it can express |
|---|---|
| QIEA fitness gene `max_holding_periods` | **1–48 minutes** |
| Live engine / harness time exit | **48 hours**, fixed, not a gene |
| Spec's declared band | 30 min – 48 h |
| Realised mean trade duration | **8 minutes** |

The optimizer selects on a horizon gene **60× shorter at its ceiling than the engine's only time exit**, and the engine then ignores the gene entirely. The engine's 8-minute mean duration is therefore produced by **ATR-multiple stop/target geometry plus `apply_order`'s same-side dedup** — 1,425,326 sizings collapsing to 2,018 trades (GAP-P12D-31) — and by nothing that could be called a holding policy. This is the quantified mechanism behind **GAP-0075** ("no position/holding policy", still `mitigated` with the production wiring outstanding) and a sibling of **GAP-0035** ("QIEA selects on a dual-EMA proxy while AGON trades six different modules"): the horizon mismatch is not merely a proxy mismatch, it is a **60×–2880× unit mismatch that nothing in the pipeline can detect**, because the two ends of it never meet in the same expression. §4 is the literature on how to close it.

**And the de-duplication that actually shapes the trade set lives in the backtest, not the engine.** The Governor emits one `SizedOrder` per surviving `Signal` — 1,425,326 of them in the falsification run. What turns those into 2,018 positions is `PositionModel.apply_order`'s same-side check, which is **in `tests/backtest/book.py`**. GAP-0075's mitigation note says the production re-entry gate will be the Risk Monitor's `positions()` reconstruction, wired into the open-decision loop "at phase 10" — i.e. **the backtest and the live engine will de-duplicate by different mechanisms**, and the one that produced every number in the falsification report is the backtest's. This compounds §5.2b and §6.2 into a single theme worth stating plainly: **several of the behaviours that determine what the graded backtest trades are implemented in the harness rather than in the engine** (fills, dedup, the time exit), while several the live engine will run are absent from it (blackouts, execution-layer fills, rejects). "Replay `test` through the real ACIS loops … exactly as production" is the ACIS-09 §7 requirement; it is not yet what happens.

**A second, independent asymmetry between the two paths.** `fitness.simulate_trades` decides on bar `i` and enters at **`bars[i+1].open`** — a deliberate one-bar lag, and correct. The harness enters at **the mid of the very tick that generated the signal**: `loop.on_state(st)` emits the order inside `_tick`, and `apply_order(order, st, …)` books it at `order.entry_price`, which every AGON module set to `state.mid` of that same `st`. So the graded harness executes with **zero latency at the signalling price**, while the optimizer that selects the parameters executes with a one-bar lag. The graded path is the more optimistic of the two on *both* price and timing. (R1 and R9 below address these separately; R1 is worth ~5× more.)

**Conformance note.** Master §5 **C8** is explicit that the fitness mini-backtest must apply *the same* model as the §13 harness, "unit-tested identical in both places", and `tests/unit/test_fitness.py::test_cost_model_semantics` is cited as the proof. That test pins `CostModel`'s arithmetic; it does **not** assert that `book.py` calls it. The two paths diverge in the one term (spread) that dominates retail FX cost. Recorded here as a finding for the owner; **no change made**.

---

## 1. COST REALISM

### 1.1 What the Dukascopy ticks actually say (the cleanest evidence available)

Measured over 8 sampled trading days spanning 2013–2025 (all ticks, tick-weighted), from `data/dukascopy/`:

| Instrument | ticks | mean | median | p25 | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| EUR/USD | 770,149 | 0.310 | **0.272** | 0.181 | 0.384 | 0.618 | 0.846 | 6.59 |
| USD/JPY | 1,019,989 | 0.468 | **0.422** | 0.287 | 0.540 | 0.846 | 2.111 | 14.44 |
| XAU/USD | 1,437,073 | 1.844 | **1.794** | 1.588 | 2.038 | 2.502 | 2.981 | 16.60 |

*(all figures bps of mid; [MEASURED HERE])*

Median spread by UTC hour, EUR/USD: flat at **0.25–0.33 bps** from 00h to 19h, then **0.34 / 0.79 / 0.53 / 0.36** at 20h/21h/22h/23h. The 21:00-UTC spike is the 17:00-New-York rollover — spread roughly **3× baseline** for about an hour. USD/JPY is worse at the rollover: **1.94 bps median at 21h vs 0.36–0.50 through the day (≈4.5×)**. Gold is flatter (1.7–2.3 bps) because its spread is dominated by a fixed dealer markup rather than by session liquidity.

**Session/volatility-regime conclusion:** contrary to the usual retail folklore, EUR/USD's *quoted* spread on an ECN is remarkably stable intraday; the two places it is not stable are (a) the daily rollover hour and (b) scheduled events (§5). A backtest that charges a *constant* spread is therefore wrong in a specific, concentrated way — it is roughly right for 95 % of minutes and badly wrong for the 5 % where this engine does a disproportionate share of its trading.

### 1.2 What a retail broker actually charges

| Source | Instrument | Published figure | Grade |
|---|---|---|---|
| OANDA UK "Our Pricing" | EUR/USD | **0.6 pips** typical spread | [BROKER-PRIMARY] |
| OANDA UK "Our Pricing" | USD/JPY | **1.3 pips** typical spread | [BROKER-PRIMARY] |
| OANDA help centre, core pricing FAQ | all FX | **"A commission of 0.70 USD per 10,000 units is applied to each 'leg' of a trade"**; core spread example quoted at **0.2 pips**; "spreads as low as 0.0" on majors | [BROKER-PRIMARY] |
| OANDA "Spreads & margins" | all | "spreads could be wider than usual at certain times…"; "rate volatility and changes in global market liquidity can lead to **significant spread increases around market openings and closings, following news announcements**"; weekend "rates or 'gaps' may change significantly when trading resumes" | [BROKER-PRIMARY] |
| BrokerChooser / review aggregators | EUR/USD | OANDA standard account ≈ **0.9–1.4 pips**; ~0.6 pips is the 50-broker average | [UNVERIFIABLE] |

Converted to bps of notional, round trip (one full spread crossed per round trip):

| Model | EUR/USD round trip |
|---|---|
| **ACIS harness today** | **0.367 bps** |
| ACIS fitness path (Dukascopy median spread) | 0.639 bps |
| OANDA UK spread-only, 0.6 pips | 0.550 bps (spread only, **no slippage**) |
| OANDA US standard, ~1.4 pips | 1.284 bps (spread only) |
| OANDA core pricing (0.70/10k/leg + 0.2 pip spread) | **1.468 bps** before slippage |
| Realistic all-in central estimate | **≈1.5 bps** (range 1.0–2.3) |

**How optimistic are we?** The harness is **≈4×** optimistic (range 2.7–6.3×). The fitness path is **≈2.3×** optimistic. Both understatements are *multiplicative on the thing that decides viability*, which is why §3 matters more than the headline ratio.

**On "quoted versus effective spread":** the distinction that matters for ACIS is not the classical academic one (effective spread = 2×|trade price − mid|, which captures price improvement inside the quote). It is that (a) an ECN's top-of-book quote is for an indicative size that may be smaller than a retail order, and (b) a principal/market-maker broker's quote already embeds its markup, so its *quoted* spread **is** its effective spread and there is no price improvement to hope for. Practically: **do not model price improvement.** Model half the broker's quoted spread per side plus slippage, and treat the Dukascopy quote as the *raw* price that the broker marks up.

### 1.3 Slippage at retail size

This is the weakest-evidenced part of the whole picture and should be treated as such.

- OANDA publishes **no fill statistics**: their own education page on slippage gives one worked example ("a buy order placed at 1.1200 filled at 1.1203" = 3 pips) and describes the *mechanism* (upper/lower bound on web, "maximum deviation" on MT4, orders cancelled rather than filled beyond the bound) but **no default tolerance and no distribution** [BROKER-PRIMARY]. An explicit negative result: the disclosure a strategy of this cadence would need does not exist publicly.
- The **bounded-slippage mechanism itself changes the modelling problem**: with a deviation bound set, a market order in a fast market is **cancelled, not slipped**. A backtest that always fills is therefore wrong in *both* directions — too cheap when it fills, and too optimistic about having a position at all. §6 recommends modelling this as a reject probability rather than as extra slippage.
- The declared **0.2 bps per side** (0.00002 on EUR/USD) is defensible as a *median, calm-market* number: it is 0.7× the measured median half-spread, which is the right order for a small order hitting a firm quote. It is **not** defensible as an unconditional constant, because slippage is the classic fat-tailed quantity and the mean is dominated by the tail.

### 1.4 What this does to a few-bps edge

Take the engine's realised profile from the GAP-P12D-31 falsification run: **2,018 trades over ~817 days ≈ 900/year, mean duration 477 s (~8 min)**.

At an 8-minute hold, EUR/USD per-trade standard deviation is **1.43 × √8 = 4.04 bps** [MEASURED HERE + DERIVED HERE]. So:

- Modelled cost 0.37 bps = **9.1 %** of per-trade volatility.
- Realistic cost 1.5 bps = **37.1 %** of per-trade volatility.

An edge "of a few bps per trade" is, at this horizon, **an edge comparable to or larger than the trade's own standard deviation** — i.e. it does not exist. At an 8-minute horizon the available edge is a *fraction of a bp*, and the cost error of ~1.1 bps per round trip is several times the entire signal.

**How much Sharpe does the missing 1.1 bps cost?** The identity is exact:

```
ΔSharpe  =  Δc · √N / s        (s = per-trade PnL standard deviation, same units as c)
```

With N = 900 and Δc = 1.1 bps, ΔSharpe = `1.1 × 30 / s`. The honest difficulty is **s**: 4.04 bps is the *pure 8-minute price* standard deviation, but the run's duration distribution is heavily skewed (mean 477 s, with TSMOM holding 2.3 days), and per-trade PnL also picks up dispersion from Governor sizing. Using s = 4.04 gives ΔSharpe ≈ 8, which is implausibly large and is therefore evidence that the run's true per-trade PnL dispersion is several times higher — plausibly s ≈ 10–30 bps-equivalent, giving **ΔSharpe ≈ 1.1–3.3**.

**A second, independent estimate from the run's own report** (`data/validation/falsification/20260915T231127Z/planted.json`) [DERIVED HERE]: it reports `annual_sharpe −0.648`, `max_drawdown_pct 1.818`, `n_trades 2018`, `profit_factor 0.837` over 817 days (2.24 yr). A Sharpe of −0.648 sustained over 2.24 years with a near-monotone decline implies cumulative return ≈ −1.45σ_ann; matching that to the 1.82 % max drawdown gives **σ_ann ≈ 1.25 % of equity** and an annual loss of ≈ 0.8 %. If the modelled friction (900 trades/yr × 0.367 bps) accounts for most of that loss — which `PF 0.837` makes plausible — the implied average notional is ≈ **0.24 × equity per trade**. Scaling the missing 1.1 bps the same way: extra annual cost ≈ `900 × 1.1 bps × 0.24 = 2.4 %` of equity, against σ_ann of 1.25 % ⇒ **ΔSharpe ≈ 1.9**. Two routes, 1.1–3.3 and 1.9. They agree.

**Do not take either estimate — take the measurement.** `tests/backtest/metrics.py` already records every `ClosedTrade` with `pnl` and `notional_usd`; the run's own per-trade PnL standard deviation and notional make this exact, and it costs nothing to compute. What is safe to say without it: **the missing spread is worth at least one full Sharpe unit and possibly three**, against a falsification result whose entire signal was that planted, null and permuted sit "within a 0.4-Sharpe band" (GAP-P12D-31). **The cost error is larger than the effect the falsification run was trying to detect.** That is the finding.

---

## 2. FINANCING AND CARRY

### 2.1 What a retail broker actually computes

Spot FX settles **T+2**. A retail "spot" position held past the daily cut is not delivered — it is rolled by a one-day **tom/next** FX swap, and the price difference between the two legs is the charge. It is quoted in **points** rather than a rate because it *is* a forward-price difference, `(F − S) ≈ (r − r*) · S · t/360` [ACADEMIC, BIS *Covered interest parity lost*, https://bis.org/publ/qtrpdf/r_qt1609e.htm].

Published formulas [all BROKER-PRIMARY]:

| Broker | Formula | Markup |
|---|---|---|
| **OANDA** | "Financing cost or credit = position value × applicable funding rate × 1/365"; rates "based on a blend of underlying liquidity providers' **tom-next SWAP rates**, adjusted by the instrument-specific admin fee, and annualised" | admin fee **per side** (added to the rate for longs, subtracted for shorts) — "other pairs" **1.00 %** (US/BVI) but **0.75 %** (Singapore); TRY 4.00 %; indices 2.5 % |
| **IG** | FX: "(tom-next rate **including** annual admin fee) × trade size", with "annual admin fee = cash mid price × 0.8 %" | **0.8 % (US) / 1.0 % (AE) / 1.5 % (UK)** — same product, three numbers |
| **Pepperstone** | "nights held × (TomNext including funding fee) × trade size"; "Funding Fee is the TomNext rate **in points** multiplied by **3 %**" | 3 % **of the points**, not 3 % p.a. |
| **Saxo** | "OpenRate + Forward Price + Financing Interest = New Rate" | swap-point markup ±0.75 % (Classic), **plus ±2.00–2.50 % p.a. on unrealised P/L** |

**ACIS's model is the right architecture.** `financing.make_financing` computes `direction × (r_base − r_quote) − fee` and `carry.financing_charge` applies `value × rate/100/365 × multiplier` — that is OANDA's published method almost exactly, including the per-side fee sign and the 365 day count. The divergences are in the *inputs*, not the shape.

### 2.2 The four places the model's inputs are wrong

**(a) The base is tom/next, not the policy differential.** Tom/next prices off actual overnight funding (SOFR/ESTR/TONA/SARON) **plus the cross-currency basis**. Du, Tepper & Verdelhan, *Deviations from Covered Interest Rate Parity* (NBER w23170 / J. Finance 2018), Table 1 mean 3-month basis, **2010–2016** [ACADEMIC, https://www.nber.org/system/files/working_papers/w23170/w23170.pdf]:

| JPY | EUR | CHF | GBP | AUD | NZD |
|---|---|---|---|---|---|
| **−25.5 bps** | **−31.7** | **−26.7** | −10.9 | **+3.9** | **+11.4** |

Note the **sign flip** on AUD/NZD — a single signed constant cannot cover G10. The 5-year JPY basis reached **−62.0 bps** (near **−90 bps** end-2015), and crisis peaks hit **−200 bps**.

**(b) The turn.** Du–Tepper–Verdelhan: quarter-end one-week CIP deviation is "**10 to 22 basis points higher**" post-2007 and "another **30–40 basis points** on average since January 2015" — a combined **~40–60 bps p.a.** on the affected fixing. Month-end is +4–13 bps. Year-end is worse (BIS: US Treasury GC repo "jumped by **260 basis points**" on 31 Dec 2018). **Per-night materiality: a +50 bps turn is 0.14 bps of notional; a +600 bps year-end spike is 1.67 bps, or 5.0 bps if it lands on the triple Wednesday.**

**(c) The fee is neither flat nor the whole markup — this is the big one.** Decomposing a real published table as `carry = (long−short)/2`, `markup = −(long+short)/2` — a method validated by the fact that OANDA TMS's implied USD base recovers to **exactly −3.65 %/−3.66 %** across gold, JP225 and every crypto instrument simultaneously [BROKER-PRIMARY, OANDA TMS Brokers S.A. weekly swap-point tables, https://www.oanda.com/eu-en/sites/default/files/document_files/swap_points_tms_en_2026.03.30.pdf and `…2026.09.07.pdf`]:

| Instrument | Mar 2026 markup/side | Sep 2026 markup/side | change |
|---|---|---|---|
| EUR/USD | 0.79 % | **0.99 %** | +20 bps |
| USD/JPY | 0.76 % | **0.96 %** | +20 bps |
| GBP/USD | 0.77 % | 0.97 % | +20 bps |
| **XAU/USD** | 1.80 % | **3.00 %** | **+120 bps** |
| index / equity / crypto | 2.50 / 3.25 / 30.00 % | **unchanged to 2 d.p.** | 0 |

The gold markup **doubled in six months while the implied funding base moved by 0.01 %**. Index and crypto markups were bit-identical across the same six months, so the FX and gold moves were deliberate repricing, not noise. **The markup is a policy variable the broker changes unilaterally, weekly.**

And the published fee is not the whole markup, because the **raw LP tom/next bid–offer** sits underneath it. IG's own worked GBP/USD example decomposes cleanly: raw LP tom/next 0.27/−0.30 (a 0.57-point daily spread ≈ **78 bps/side**) *plus* admin fee 0.29 points ≈ **80 bps/side** ⇒ **316 bps p.a. round trip against the 160 bps a "flat 0.8 %" model would predict — a 1.97× understatement** [BROKER-PRIMARY]. Three independent sources converge on raw tom/next bid–offer ≈ **60–130 bps p.a. per side** (IG 78, Pepperstone/AUD-CAD 61, Afterprime implied 84–132). **ACIS's model omits this term entirely.**

The structural tell: **on the September OANDA TMS table, 14 of 43 FX pairs are negative on BOTH sides** (GBP/USD −1.93 %, AUD/USD −1.91 %, NZD/USD −1.96 %, …). Whenever |carry| < markup, both directions pay. **A policy-differential model can never produce that**, and `make_financing`'s `direction × (r_base − r_quote) − fee` in fact *can* — provided `fee` is large enough. At `OANDA_MAJOR_FEE_PCT = 1.00` it is roughly the right order for FX and **badly low for gold**.

**(d) Gold's base does not exist as free data.** LBMA discontinued GOFO after **30 January 2015** and **named no successor** [PRIMARY, https://www.lbma.org.uk/articles/discontinuation-of-gofo-wef-30-january-2015]; LBMA's current public prices page carries no forward or lease benchmark. `financing.py`'s `DEFAULT_GOLD_LEASE_PCT = 0.25` with a documented "run a 0–1 % sensitivity band" is therefore **the honest thing to do** and should stay. What should change is the **fee**: real gold markup is **1.80–3.00 % per side (360–600 bps round trip)**, i.e. **2–3× the FX markup at the same broker**, confirmed independently by Afterprime (1.803 %/side on 16 Sep 2026). `XAU_USD` currently inherits `OANDA_MAJOR_FEE_PCT = 1.00`.

### 2.3 Triple-swap: ACIS's convention table is right, and incomplete

`carry.py`'s `_TRIPLE_DAY = {"tom_next": Wed, "financing_daily": Fri}` matches the published conventions [BROKER-PRIMARY: OANDA "FX and metals (except copper) … Wednesdays"; IG "held through Wednesday 10pm UK … three days"; Pepperstone "CFD Equities and Index products … Friday"]. Three things it does not model:

1. **T+1 pairs shift.** OANDA, verbatim: *"**USD/CAD settles on a T+1 basis and therefore has its three-day financing applied on a Thursday**."* `USD_CAD` is in the declared diversification basket with `swap_convention: tom_next`, which would charge it on Wednesday. **That is a latent bug for the day USD/CAD is enabled** — cheap to fix now, and it is exactly the §13 "triple-swap Wednesday flipping carry math" glitch class.
2. **Settlement-centre holidays shift the day.** The value date must be good in both currencies' centres *and* in USD. A US holiday pushes the roll out; around New Year a single roll can carry **4–6 swap days**. `business_rollovers` uses Mon–Fri only.
3. **IG triples the tom/next on Wednesday but the admin fee on *Friday*** — verbatim: *"You'll only be charged one day of the IG admin fee on a Wednesday, however if you were to hold on a Friday you will pay three days of IG's admin fee."* Their arithmetic confirms it (`(3 × 0.27) − 0.29`). **A single `swap_multiplier` applied to the whole charge is wrong for IG on both days.** ACIS's single multiplier is right for OANDA and wrong for IG.

Also worth a note: **rollover time is not universally 17:00 New York.** IG charges at **22:00 UK**, which equals 17:00 NY only while UK and US DST are aligned — the ~1 week in October and ~3 weeks in March it is an hour out, and the *day boundary itself* moves. Saxo rolls **NZD at 07:00 New Zealand time**. Pepperstone's authoritative boundary is **MT4/5 server midnight**, and MT4 servers conventionally track *European* DST. ACIS already has the `{zone, at}` machinery from GAP-P12D-10; the financing clock needs the same treatment **per broker**, and it is not necessarily the same zone as the 17:00-New-York daily-loss clock.

Finally: **day count is platform-dependent, not broker-dependent.** OANDA, verbatim: *"DAYS for MT4 = 360 and for MT5 = 365."* Same account, same rate, **1.39 % different charge**. `carry._DAYS_PER_YEAR = 365` is right for OANDA v20 and wrong on MT4.

### 2.4 Materiality for a 30 min – 48 h system

The FX week has 120 trading hours containing 4 rollovers (Mon–Thu 17:00 NY) with multipliers 1,1,**3**,1 = **6 swap-days per week**. For uniformly-timed entries: `P(cross ≥1 rollover) ≈ H/30` and `E[swap-days] = H/20` [DERIVED]:

| hold | P(≥1 rollover) | E[swap-days] |
|---|---|---|
| 30 min | 1.7 % | 0.025 |
| 2 h | 6.7 % | 0.10 |
| 8 h | 26.7 % | 0.40 |
| 24 h | 80 % | 1.20 |
| **48 h** | **100 %** | **2.40** |

Note `E[swap-days] = 1.2 × days held`: **the Wednesday triple adds 20 % to expected financing even for a strategy that never deliberately holds over Wednesday.**

Cost of one night in bps of notional (Afterprime published table, 16 Sep 2026 [BROKER-PRIMARY]):

| | 1 night | triple Wed |
|---|---|---|
| EUR/USD long | **−0.842** | **−2.53** |
| USD/JPY short | **−1.095** | **−3.29** |
| **XAU/USD long** | **−1.647** | **−4.94** |

Against a 3 bps per-trade edge: at 2 h, financing is a **3–6 % haircut** — real but not decisive. At 48 h it is **67 % (EUR/USD long), 88 % (USD/JPY short), 132 % (gold long — the edge is gone)**. **A single triple-Wednesday gold long costs −4.94 bps, more than the entire assumed edge, in one event.**

### 2.5 Synthesis against ACIS's model

| | verdict |
|---|---|
| **Shape of the formula** | **correct** — matches OANDA's published method, per-side fee, 1/365, per-rollover |
| Base rate source (policy proxies) | **biased by the cross-currency basis**: EUR −32, JPY −26, CHF −27, GBP −11, AUD +4, NZD +11 bps. Fixable by adding a declared per-currency basis constant. |
| Turn premium | **missing**; +40–60 bps quarter-end, worse at year-end, on the affected fixing only. ~0.1–1.7 bps per night when it bites. |
| `OANDA_MAJOR_FEE_PCT = 1.00` for FX | **roughly right in level (real: 0.77–0.99 %/side), wrong in being constant** (+20 bps/side in six months) and wrong in omitting the raw LP bid–offer (60–130 bps/side). |
| Same fee applied to `XAU_USD` | **wrong by 80–200 bps/side.** Real gold markup 1.80–3.00 %/side. |
| `DEFAULT_GOLD_LEASE_PCT = 0.25` + declared sensitivity band | **the right call** — no free authoritative gold forward curve has existed since 30 Jan 2015. Keep, and keep the band. |
| Wednesday/Friday triple table | **right for OANDA**; misses T+1 USD/CAD (Thursday), settlement holidays, and IG's split multiplier. |
| 365 day count | right for OANDA v20, wrong on MT4 (360) |

**Bottom line for this engine.** For holds ≤ 4 hours — which is where the engine actually lives — **financing is second-order**: ~0.08 bps expected on a 2-hour EUR/USD trade, against a modelled round-trip cost of 0.37 bps and a *missing* cost of ~1.1 bps. §1 and §5 are where the money is. But the model is **materially wrong at the top of the declared band and on gold**, precisely the configuration §3 recommends moving toward — so fixing financing is not urgent *today* and becomes urgent the moment R6 is adopted.

**The cheapest possible falsification test for any financing model**, worth building whatever else is decided: assert on load that `long_rate + short_rate < 0` for every instrument, and record `−(long+short)/2` as the observed markup. It fails immediately against every real broker table, and `direction × (r_base − r_quote) − fee` passes it only if `fee` is honestly sized.

---

## 3. HOLDING HORIZON VERSUS COST

### 3.1 The right identity for ACIS

The companion research file gives the **continuous-exposure** identity, `drag_Sharpe = c·T/(σ_ann·h)`, which yields 66.9 Sharpe units of drag at h = 8 min. That identity is correct *for a system that is always in the market*. **ACIS is not:** 2,018 trades × 8 min over 817 days is a **duty cycle of ~1.7 %**. Applying the continuous formula to ACIS overstates the drag by ~60×, and — more importantly — points at the wrong lever. For a low-duty-cycle system, the binding constraint is not "cost per unit of calendar time"; it is **cost per trade against edge per trade**.

The correct form is:

```
per-trade gross edge      a   (bps)
per-trade sd              s = σ_1min · √h   (bps)
information coefficient   IC = a / s
round-trip cost           c   (bps)
trades per year           N

net annual Sharpe  =  (a − c) · √N / s  =  (IC − c/s) · √N
viability          ⇔  IC  >  c / (σ_1min · √h)
minimum hold       ⇔  h_min = ( c / (IC · σ_1min) )²
```

Both statements are consistent: `N = duty·T/h`, so substituting recovers the continuous identity when duty = 1.

### 3.2 Break-even IC by holding period (EUR/USD, σ₁ₘᵢₙ = 1.43 bps [MEASURED HERE])

| hold | per-trade sd | IC needed @ **0.37 bps** (harness) | @ 0.64 (fitness) | @ **1.5** (realistic) | @ 2.3 (bad) |
|---|---|---|---|---|---|
| **8 min** | 4.04 | **0.091** | 0.158 | **0.371** | 0.569 |
| 30 min | 7.83 | 0.047 | 0.082 | 0.192 | 0.294 |
| 1 h | 11.08 | 0.033 | 0.058 | 0.135 | 0.208 |
| 2 h | 15.66 | 0.024 | 0.041 | 0.096 | 0.147 |
| 4 h | 22.15 | 0.017 | 0.029 | 0.068 | 0.104 |
| 8 h | 31.33 | 0.012 | 0.020 | 0.048 | 0.073 |
| 24 h | 54.26 | 0.007 | 0.012 | 0.028 | 0.042 |
| **48 h** | 76.74 | 0.005 | 0.008 | **0.020** | 0.030 |

[DERIVED HERE]

Read the **8-minute row** against the **48-hour row**: the required IC falls by a factor of **18**. Nothing about the signal changed; only the horizon did.

### 3.3 Minimum viable holding period, `h_min = (c/(IC·σ₁ₘᵢₙ))²`

| plausible IC | c = 0.37 (harness) | c = 0.64 (fitness) | c = **1.5** (realistic) | c = 2.3 |
|---|---|---|---|---|
| 0.02 (weak but real) | 2.8 h | 8.3 h | **45.8 h** | 107.8 h |
| 0.03 | 1.2 h | 3.7 h | **20.4 h** | 47.9 h |
| 0.05 (good) | **27 min** | 1.3 h | **7.3 h** | 17.2 h |
| 0.10 (excellent) | 7 min | 20 min | 1.8 h | 4.3 h |
| 0.20 (HFT-grade) | 2 min | 5 min | 28 min | 1.1 h |

[DERIVED HERE]

**This table is the finding.** At the cost the harness charges and an optimistic-but-not-absurd IC of 0.05–0.10, the minimum viable hold is **7–27 minutes** — and the engine converged on 8 minutes. At a realistic 1.5 bps it is **1.8–7.3 hours**. The engine did not choose an 8-minute horizon because 8 minutes is where the edge is; it chose it because **the cost model made 8 minutes look free**. Fixing F1 alone (charge the spread) moves the modelled break-even hold from 27 min to 1.3 h at IC 0.05; fixing F2 as well moves it to 7.3 h, which lands inside the spec's declared 30 min – 48 h band **only at its upper end**.

### 3.3b The grader already knows

`tests/backtest/report.py` sets `DURATION_MIN_S = 30 * 60` and `DURATION_MAX_S = 48 * 3600` as graded §14 targets, with owner-ratified carve-outs for TSMOM and MOMENTUM_SCALP only. The falsification run's `avg_trade_duration_s` was **477.5** — **below the 30-minute floor by 3.8×**, on trades that are *not* carved out. So §14's own duration criterion already fails on this engine, independently of every cost argument in this document. **The horizon problem is not a hypothesis this research introduced; it is a graded target the engine is already missing, and §3.3 explains why fixing the cost model makes that target the binding one rather than an incidental one.**

### 3.4 Where a retail FX system stops being viable

Combining: at realistic cost and a realistic-good IC of 0.03–0.05, the viability frontier is at a **mean holding period of roughly 7–20 hours**, equivalently **~250–700 round trips per year per instrument** at a 100 % duty cycle, or a few hundred trades/year at ACIS's duty cycle. Below ~2 hours mean hold, a retail FX system requires an IC that is empirically the preserve of latency-advantaged market makers. **The engine's realised 900 trades/year at 8 minutes is on the wrong side of that frontier by a factor of roughly 50× in holding time.**

### 3.5 What edge the 8-minute regime requires, versus what is plausible

For **§14's Sharpe > 1.5** at N = 900–1,009 trades/year [DERIVED HERE]:

| configuration | gross edge needed | implied IC |
|---|---|---|
| 8 min hold, c = 0.37 | 0.56 bps | 0.139 |
| **8 min hold, c = 1.5** | **1.69 bps** | **0.418** |
| 1 h hold, c = 1.5 | 2.02 bps | 0.183 |
| 8 h hold, c = 1.5 | 2.98 bps | 0.095 |
| 48 h hold, N = 250, c = 1.5 | 8.78 bps | 0.114 |

An IC of 0.418 is not a hard target; it is a category error. An IC of 0.10 is the ceiling of what published systematic FX work supports, and even that only at multi-hour-to-multi-day horizons. **§14's Sharpe > 1.5 is unreachable at any horizon this engine currently trades, and only marginally arguable at the top of its declared band** — which is the same conclusion the companion file reached from the positive-months/profit-factor side, by a completely independent route. Two independent derivations agreeing is worth more than either alone.

---

## 4. SIGNAL-TO-POSITION MECHANICS

> **Source-confidence note.** The web-search budget was exhausted before this section (see Limitations). The pysystemtrade material below is **verified by direct fetch** of the repository's own documentation. The academic results are **cited from knowledge and not re-verified in this session** — they are standard, load-bearing results that any of the named papers will confirm, but treat the exact formulas as **[ACADEMIC, unverified citation]** and check them before implementing. The *structure* of the recommendation does not depend on any one of them.

### 4.1 The central design choice: target position vs event-based entry

**ACIS is event-based today, by omission rather than by decision.** Every AGON module emits a discrete `Signal`; the Governor sizes it; the book opens a position and holds it until a stop, a target, a reversal or a time cap. There is no representation anywhere of "the position I should be holding right now". Because there is no target, there is no way to ask the only question that controls cost: *is the position I hold close enough to the position I want that trading is not worth it?*

The production-systematic convention is the opposite. A target-position (state-based) system computes, each bar, a desired position from the combined forecast, compares it to what it holds, and trades the **difference** — or, more usually, trades the difference only when it is large enough to be worth the cost. The two designs differ in what they make easy:

| | event-based (ACIS today) | target-position |
|---|---|---|
| "should I be in this trade?" | answered once, at entry | re-answered every bar |
| turnover control | emerges from stop/target geometry and dedup | an explicit, tunable parameter |
| combining strategies | N signals → N positions | N forecasts → 1 position |
| cost modelling | per trade | per unit of position change |
| holding period | emergent (8 minutes) | a consequence of the band width, chosen |

**This is the structural answer to F6c.** The `max_holding_periods` gene cannot reach the engine because the engine has nothing to apply it to. A target-position layer is the thing that would give it somewhere to live.

### 4.2 No-trade bands: the theory, and the one number that matters

The foundational result is that **with proportional transaction costs, the optimal policy is not to track the optimal portfolio — it is to do nothing inside a band around it, and trade only to the band's edge when you leave it.** Constantinides (1986) established the band structure for a proportional-cost portfolio problem; Davis & Norman (1990) gave the rigorous singular-control treatment; Leland (2000) worked the practical rebalancing case. [ACADEMIC, unverified citations]

The result worth remembering is the **scaling**: band half-width grows roughly as the **cube root** of the proportional cost, `w ∝ (c/γσ²)^{1/3}` (Constantinides-type asymptotics). Two consequences for ACIS:

- **Costs matter less than linearly for band design.** Quadrupling the cost (§1's 0.37 → 1.5 bps) widens the optimal band by only `4^{1/3} ≈ 1.59×`. So the band width is *robust* to exactly the cost uncertainty this report is otherwise complaining about — which makes it a safe thing to adopt before the cost model is perfect.
- **But turnover is very sensitive to the band.** Widening a band by 1.6× typically cuts turnover by far more, because crossings of a wider band are rarer than linearly.

**Gârleanu & Pedersen (2013), "Dynamic Trading with Predictable Returns and Transaction Costs"** [ACADEMIC, unverified citation] is the version most directly applicable to a multi-signal system. Its two results:

1. **Partial adjustment toward an "aim portfolio".** The optimal position is a weighted average of where you are and where you want to be: `x_t = (1 − a)·x_{t−1} + a·aim_t`, with the trading rate `a ∈ (0,1]` **decreasing in transaction cost** and increasing in risk aversion. You never jump to the target; you always move a fixed fraction of the way.
2. **The aim portfolio overweights slow signals.** Because a fast-decaying signal's edge will be gone before you have finished trading into it, the aim shrinks each signal in proportion to its own decay rate. **A signal that decays faster than you can trade into it is worth approximately nothing after costs, no matter how strong it is.**

Result 2 is the formal statement of §3's conclusion and of the GAP-P12D-31 diagnosis ("horizon mismatch: mean trade duration 477 s against an edge that only pays over 1–4 h"). It also says something ACIS's optimizer cannot currently express: **the right response to a fast signal under high costs is not to trade it faster, it is to weight it down.**

The convex-optimisation formulation of the same idea — **Boyd et al., "Multi-Period Trading via Convex Optimization"** (the `cvxportfolio` library) [ACADEMIC/PRACTITIONER, unverified citation] — puts a turnover penalty directly in the objective rather than filtering trades afterwards. The general finding across this literature: **penalising turnover inside the objective dominates post-hoc trade filtering**, because the optimiser can then choose a *different, cheaper* position rather than being denied the expensive one.

### 4.3 What a production system actually implements — verified

**pysystemtrade** (Rob Carver's open-source production system) implements exactly the band, and its documentation is explicit [PRACTITIONER, VERIFIED by direct fetch of `docs/backtesting.md`]:

> *"Position inertia, or buffering, is a way of reducing trading costs. The idea is that we avoid trading if our optimal position changes only slightly by applying a 'no trade' buffer around the current position."*

Two methods, with his recommended settings quoted verbatim:

| method | rule | config |
|---|---|---|
| **position buffering** | *"We compare the current position to the optimal position. If it's not within 10% (the 'buffer') then we trade to the optimal position, otherwise we don't bother."* | `buffer_method: position`, `buffer_size: 0.10`, `buffer_trade_to_edge: False` |
| **forecast buffering** (his recommendation) | *"we take a proportion of the average absolute position … and use that to size the buffer width. This is more theoretically correct; since the buffer doesn't shrink as we get to zero. Secondly if outside the buffer we trade to the nearest edge of the buffer, rather than going to the optimal position. This further reduces transaction costs."* | `buffer_method: forecast`, `buffer_size: 0.10`, `buffer_trade_to_edge: True` |

Three details worth copying:

- **Trade to the edge, not to the target** — the direct implementation of the band result in §4.2, and the source of a second tranche of savings on top of the band itself.
- **The band is sized off *average* absolute position, not current position**, so it does not collapse to zero width as the position approaches flat. A band proportional to the current position has a degenerate region exactly where ACIS spends most of its time.
- **Buffering runs downstream of the model, against real held positions**: *"in a live trading system buffering is done downstream of the system module, in a process which can also see the actual current positions we hold."* That is the correct layer for it in ACIS too — it is a Governor-level concern (the only layer that sees total portfolio state), not a signal-level one.

pysystemtrade also **costs strategies in Sharpe-ratio terms as `SR cost × turnover`** (`get_SR_cost_given_turnover`, `use_SR_costs`) — independent practitioner confirmation of §3's identity, arrived at from the other direction.

The same system applies **forecast capping and thresholding** upstream of position sizing: forecasts are scaled to a target average absolute value and capped (`forecast_scalar`, `forecast_cap`), and a documented variant zeroes small forecasts entirely — *"If f<10 then g=0. If 10≤f≤20 then g=3(f−10). If f>20 then g=30"* [PRACTITIONER, VERIFIED, qoppac blog] — a dead-zone plus a linear ramp. ACIS has the first half of this already: AGON's `conviction_discard` threshold is a dead-zone on conviction. What it lacks is the *position* band downstream.

### 4.4 The techniques, ranked by cost reduction per unit of implementation risk

| technique | cost-drag reduction | risk of destroying the edge | ACIS status |
|---|---|---|---|
| **1. Position netting across strategies/instruments before execution** | Large and essentially free — two modules wanting opposite positions currently produce two round trips and one flat book | **None.** It is an identity, not a model change | **Absent.** Governor emits one `SizedOrder` per `Signal`; nothing nets them |
| **2. No-trade band / buffering with trade-to-edge** | Large; this is the main lever | Low, and *quantifiable* — the band's width is one number you can sweep | **Absent** |
| **3. Target-position representation** | Prerequisite for 1, 2 and 5 | Low; it changes plumbing, not signals | **Absent** |
| **4. Minimum holding time / trade throttle** | Moderate | **Moderate — this is the risky one.** A hard min-hold prevents a *correct* exit, which is a different thing from preventing an unnecessary entry. Prefer the band | §9.5 supports a platform min-hold as a *constraint*; not a cost tool |
| **5. Turnover penalty inside the fitness objective** | Moderate-to-large, and it changes *what gets selected* rather than filtering afterwards | Low | **Absent** — C8 charges cost per simulated trade, which is not the same as penalising turnover in the objective |
| **6. Signal smoothing / hysteresis (EWMA the forecast; Schmitt-trigger entry/exit thresholds)** | Moderate | Moderate — smoothing adds lag, which costs edge on a fast signal and costs nothing on a slow one | Partially present: `conviction_discard` is a one-sided threshold, not hysteresis |
| **7. Half-life matching (weight each signal by its decay rate)** | Large *for the right reason* — it removes signals that were never affordable | Low; it is the Gârleanu-Pedersen aim-portfolio result | **Absent**, and it is the direct fix for the horizon mismatch in GAP-P12D-31 |

### 4.5 What this means concretely for ACIS

The smallest change that would make the biggest difference is **not** a min-hold rule. It is:

1. Give the Governor a **target position per instrument** derived from the combined, netted conviction of all live signals for that instrument, instead of one order per signal.
2. Put a **no-trade band** around the currently-held position, sized as a fraction of the instrument's *average* absolute position (not the current one), and **trade only to the band's edge**.
3. Let the **band width**, not a stop/target geometry accident, set the holding period — then `max_holding_periods` (F6c) has somewhere real to apply, and the horizon the optimizer selects is the horizon the engine trades.

That sequence would address GAP-0075 (no position/holding policy), the F6c unit mismatch, the §14 duration-floor failure in §3.3b, and the cost drag in §1 — with one mechanism, at the layer the Layer Communication Law already assigns to it. **It is a spec-level change (ACIS-05 and master §6 describe signal→SizedOrder sizing, not target-position management) and therefore requires owner ratification before anyone writes it.**

---

## 5. EVENT RISK

### 5.1 What our own ticks say (10 NFP releases, 2015–2025)

[MEASURED HERE] Baseline = mean spread over T−60 min to T−30 min. Release instant T = 08:30 New York, DST-correct.

| window | EUR/USD | USD/JPY | XAU/USD |
|---|---|---|---|
| baseline spread | 0.252 bps | 0.331 bps | 1.878 bps |
| T−5 m … T−1 m | 0.320 (**1.27×**) | 0.455 (1.38×) | 2.076 (1.11×) |
| **T … T+10 s** | **1.331 (5.27×)** | **2.298 (6.95×)** | **5.317 (2.83×)** |
| T+10 s … T+1 m | 0.551 (2.18×) | 0.917 (2.77×) | 3.135 (1.67×) |
| T+1 m … T+5 m | 0.349 (1.38×) | 0.520 (1.57×) | 2.240 (1.19×) |
| T+5 m … T+30 m | 0.283 (1.12×) | 0.387 (1.17×) | 2.018 (1.07×) |
| worst single event, T…T+10 s | 2.23 bps | 4.17 bps | 11.18 bps |

Price displacement from the last pre-release mid:

| horizon | EUR/USD \|move\| | USD/JPY | XAU/USD |
|---|---|---|---|
| 10 s | mean 28.3, median 16.2, max 100.6 bps | 30.7 / 32.2 / 68.8 | 37.4 / 33.9 / 68.1 |
| 1 min | mean 32.2, median 15.2, max 128.4 | 34.6 / 23.0 / 89.7 | 38.2 / 38.3 / 69.6 |
| 5 min | mean 32.7, median 22.9, max 117.7 | 43.7 / 37.4 / 121.9 | 43.1 / 49.6 / 88.9 |

**Context:** a normal EUR/USD minute has a standard deviation of **1.43 bps**. The NFP minute averages **32 bps**, i.e. **≈22σ**, and the spread multiple (5.3×) is real but *second-order* next to the price multiple (22×). **The cost of trading a release is not mainly the spread; it is that the price moves 20σ while your order is in flight.** And note this is Dukascopy ECN data — a principal broker's spread widening in the same window is materially worse, and its slippage is the part nobody publishes.

### 5.2 Why this is adverse selection, not noise, for *this* engine

`core/signals/agon.py` fires `BREAKOUT` when the mid exceeds a channel edge by an ATR-scaled threshold, and `MOMENTUM_SCALP` on EMA slope with a velocity ratio. Both are **triggered by large moves**. Event minutes are therefore not sampled at their share of the clock; they are sampled at their share of the *tail*.

[DERIVED HERE, assumptions stated] For a 7-major + gold universe, Tier-1 releases (NFP, CPI, FOMC, ECB, BoE, BoJ, GDP, and the main national prints) number roughly **100–150 per year**. Take a ±15-minute window: 150 × 30 min = 4,500 minutes out of ~374,400 = **1.2 % of minutes**. Now suppose a breakout trigger requires a ~3σ minute:

- baseline: P(3σ) ≈ 0.3 % of minutes under a normal, and realistically ~1–2 % under fat tails.
- event window: the release minute is ~22σ and the surrounding ±15 min are elevated several-fold, so trigger probability in that window is effectively **1.0** for the release minute and high for several neighbours — call it an average of 0.3 over the window, i.e. **15–30× the baseline rate**.

Then the event-window share of all triggers is `1.2 %×25 / (1.2 %×25 + 98.8 %×1) ≈ 23 %`. Even with the conservative end of every assumption it does not fall below ~10 %.

**Cost consequence.** If 15–25 % of trades are entered in windows where realistic execution cost is 10–30 bps (spread widening + in-flight displacement + bounded-slippage rejects on the fills you *wanted*), the error in mean per-trade cost is `0.20 × 20 bps = 4 bps` — against a modelled total cost of **0.37 bps**. That is a **~10× error on the cost of the average trade**, concentrated in the trades most likely to be the strategy's apparent winners in a mid-fill backtest.

**This is the single most likely reason a backtest of this engine would look better than reality, after F1.**

### 5.2b What the engine's existing defences do and do not catch (fair reading)

Two mechanisms already stand between the engine and an event window, and it is worth being precise about their reach.

1. **NVMA's `SPREAD_VETO`** (`core/regime/nvma.py:259`) fires when `state.spread > spread_veto_mult × session-median spread`, with `spread_veto_mult: 3.0` in `config/system_config.yaml`. Measured against §5.1: the **T…T+10 s** bucket is 5.27× (EUR/USD) and 6.95× (USD/JPY) — **the veto fires**. But **T+10 s…T+1 m is 2.18×/2.77×** and **T+1 m…T+5 m is 1.38×/1.57×** — **the veto does not fire**, and those windows still carry essentially the whole 32 bps displacement (|move| at 1 min ≈ |move| at 10 s ≈ |move| at 5 min, per §5.1). So the veto covers the ten seconds where the spread is obviously broken and leaves open the minutes where the *price* is doing something 20σ unusual at only a 2× spread. **It is a spread guard, not an event guard** — and the measured evidence is that at a release the price anomaly is ~4× larger in σ terms than the spread anomaly.
2. **The `MACRO_EVENT` regime** has precedence over everything (`nvma.py:268`) — but it is gated on `state.macro_events_imminent` or a Tier-G flag. In the backtest, with no historical calendar, `macro_events_imminent` is never true. **The live engine's primary event defence is simply absent from the graded run**, which is the §5.3(1) point stated structurally: the backtest grades a different engine.

Both observations *strengthen* R5 rather than weaken it, and they add a cheap interim measure: until the calendar exists, the honest thing is to report what fraction of backtest trades were entered within N minutes of a known release date-time, even a coarse one.

### 5.3 What to do about it

There are three defensible policies and the spec already mandates the machinery for the first:

1. **Blackout windows.** Master §3.5 already builds this for *live* (`events.py` → Governor hard override; observed prop-firm windows ~2–5 min either side of Tier-1). The gap is that **the backtest has no historical calendar**, so the backtest grades a policy the live engine will not run. That is a validity defect in its own right, independent of cost: *the thing being graded is not the thing that will trade.*
2. **Size reduction / caution multiplier** rather than full avoidance, for accounts whose rulebook permits news trading. The §3.5 dampen-only caution multiplier is the existing mechanism.
3. **Deliberate news trading** — out of scope here and forbidden on rule-restricted accounts; not recommended on the evidence, because the edge such systems chase lives in the first seconds where retail latency and bounded-slippage rejects are decisive.

The honest minimum for §14 credibility is: **build the historical calendar, and grade the engine twice — once with the live blackout policy applied and once without — and report both.** The difference *is* the measurement of how much of the backtest's PnL came from minutes the live engine will not be allowed to trade.

### 5.4 Historical calendar sources, with licensing checked

**The requirement is narrower than "an economic calendar".** For a backtest you need, per event: the **release instant to the minute, in a named timezone, DST-correct**, for a small Tier-1 set, covering 2012–2025. You do **not** need consensus/actual/previous — the master §3.5 Tier-1 taxonomy (NFP, CPI, central-bank rate decisions/FOMC, GDP) drives blackout *windows*, and a window needs only a timestamp. That distinction eliminates most of the difficulty: the commercial calendars are valuable for forecast/actual data, and ACIS needs the one field the free official sources publish best.

**What I verified by direct fetch:**

| source | coverage | gives a TIME? | licence | verdict |
|---|---|---|---|---|
| **BLS release schedules** (`bls.gov/schedule/<YEAR>/home.htm`, archive index `bls.gov/bls/archived_sched.htm`) | **2000–2025 as web pages; 1957–2000 as one PDF**; ~135 releases/year | **YES** — e.g. *"Friday, January 09, 2015 \| 08:30 AM \| Employment Situation for December 2014"*, and the page states *"All times on calendar are Eastern Time"* | **Public domain.** BLS: *"everything that we publish … is in the public domain"*; *"You are free to use our public domain material without specific permission, although we do ask that you cite the Bureau of Labor Statistics as the source."* | **Best source for the US prints that matter** — NFP, CPI, PPI, JOLTS, ECI, import/export prices. Authoritative timestamp, clean licence, full history. |
| **Federal Reserve FOMC calendars** (`federalreserve.gov/monetarypolicy/fomccalendars.htm`, historical index `fomc_historical_year.htm`) | current page 2021–2027; **historical materials back to 1936** | meeting **dates** yes; statement **time** is not on the calendar page (it is 14:00 ET in the modern era, earlier historically — verify per year) | US Government work | **Use for dates; source the statement time separately and declare it.** |
| **FRED `releases/dates` API** (`fred.stlouisfed.org/docs/api/fred/releases_dates.html`) | all FRED releases | **NO — date only, `YYYY-MM-DD`, no time of day** | API key required; terms link present | **Not sufficient alone.** Excellent for *which day*, useless for a ±2-minute blackout window. Good as a cross-check against BLS (the §3.5 "≥2 sources, earlier time wins" rule). |
| **ECB Governing Council calendar** (`ecb.europa.eu/press/calendars/mgcgc/…`) | the public page shows **forward dates only** (Sep 2026 → Dec 2028) | **NO times**, no iCal/JSON | "Copyright 2026, European Central Bank" — reuse terms need checking | **Insufficient as fetched.** ECB historical decision dates must come from the press-release archive instead; the 13:45/14:15 CET decision/press-conference convention changed in 2022 and must be handled per era. |
| **BLS iCal feed** (`bls.gov/schedule/news_release/bls.ics`) | — | would carry tz-aware timestamps | **Blocked.** A plain `curl` returns *"Access Denied … Automated retrieval programs (commonly called 'robots' or 'bots') can cause delays … bot activity that doesn't conform to BLS usage policy is prohibited."* | The **data** is public domain; the **access method** is policed. Fetch politely, cache, and never hammer. |
| **Forex Factory** | 2007→ , all countries, tiered | yes | — | **`forexfactory.com/legal` returned HTTP 403 to an automated fetch.** That is itself the answer about automated access. Treat FF as **not licence-clean for programmatic use** absent a written permission. |

**Not verified in this session** (search budget exhausted) and therefore **[UNVERIFIABLE — check before use]**: FXStreet's API terms, Trading Economics' free-tier limits and licence, Investing.com's ToS, the `investpy`/`tradingeconomics` Python packages' current status, and any Kaggle/HuggingFace historical-release-timestamp dataset. The 2021 `investpy` breakage is well known in the community, so assume nothing in that family is stable.

**Recommended build, in order:**

1. **US Tier-1 from BLS + Fed.** BLS gives NFP and CPI with authoritative ET timestamps for the whole 2012–2025 window, public domain. FOMC dates from the Fed, statement time declared per era. That is the large majority of what actually moves EUR/USD, USD/JPY and gold in the measurements in §5.1.
2. **Non-US Tier-1 from each central bank's and statistical agency's own release archive** (ECB, BoE, BoJ, ONS, Eurostat, StatCan, ABS). More work, same licence cleanliness, same authority.
3. **Cross-check with FRED `releases/dates`** for the date, applying master §3.5's existing rule: *"Tier-1 event times cross-checked against ≥2 sources; disagreement ⇒ take the earlier time and log `CALENDAR_DISAGREEMENT`."* The machinery for this is already specified.
4. **Store as `{zone, at}`**, never as fixed UTC — BLS publishes in **Eastern Time**, which is a wall clock that moves with DST. This is exactly the GAP-P12D-10 pattern already adopted for market times, and the §13 "calendar DST shift" glitch class exists precisely for the failure it prevents.

**Effort estimate, honestly:** step 1 is a few hundred lines of a polite scraper over 26 archived BLS pages plus the Fed's calendars, and it gets you the events that produced every number in §5.1. Steps 2–3 are the long tail. **Do step 1 first and measure the §5.3 with/without-blackout difference on US events alone** — if that difference is already large, the case for steps 2–3 makes itself, and if it is small, that is a finding too.

---

## 6. DATA AND FILL FIDELITY

### 6.1 What the harness assumes versus what happens

| harness assumption | reality | direction of error |
|---|---|---|
| fill at `state.mid` | buy at ask, sell at bid | optimistic by ½ spread **per side** |
| fill at the tick concurrent with the signal | order arrives 30–300 ms later | optimistic; grows with volatility |
| always fills | bounded-slippage cancels; MM rejects | **both** — cheaper fills, and phantom positions |
| stop fills exactly at `stop_loss`, tested on mid | triggers on bid, fills at or through | optimistic, worst exactly when it matters |
| no gap-through | weekend and event gaps jump the level | optimistic in the tail |
| no partial fills | partials at size/in fast markets | small at retail size |
| constant per-instrument slippage | fat-tailed, volatility-conditional | understates the mean badly |

### 6.2 The graded backtest never touches the execution layer

**This is also a locked-spec contract violation, not just a modelling choice.** `specs/ACIS-09-BACKTEST_VALIDATION.md` §7 step 2(c) requires the fold test replay to run "through the real ACIS loops in accelerated time, honouring session-boundary promotion, NVMA veto, Governor sizing, **Execution fill modelling**, Risk HALTs/equity breaker, AND the account's §9.5 platform rules exactly as production", and step 2(d) to "collect **FillReports**/RiskSnapshots". Neither happens.

`tests/backtest/harness.py` imports `core.data`, `core.optimizer`, `core.governor` and the local `tests/backtest/*` modules. It imports **nothing** from `core/execution/`. So the run that produces a §14 grade bypasses `ExecutionOrchestrator`, `plan()`/`Fragment`, `ExecutionFace`, `FillReport` and `FillStatus` entirely — and with them the whole partial-fill / rejection / reroute path (`MAX_REMAINDER_RETRIES = 2`, `MAX_REROUTES = 1`) that phase 7 built and phase 13 will attach to a real venue. Consequences:

- **Partial fills and rejections cannot appear in a graded backtest**, even though §13 lists them as required glitch classes and `core/execution/` implements them. They are unit-tested; they are not *graded*.
- The stop-loss that master §279 requires to sit **at the broker** is, in the backtest, a number compared against `st.mid` in Python. the outstanding three-loop-runtime work (GAP-0091b/0099/0075 — CLAUDE.md: it "threads `SizedOrder.stop_loss` to the venue stop") therefore has no backtest that would notice if it were wrong.
- The Governor's `size_units` is booked verbatim; no lot-step snapping, no venue minimum, no capability-descriptor rejection (this compounds GAP-P12D-27).

This is not the same finding as F1 — F1 is about *price*, this is about *whether the order happened*. Both push the same way: the backtest's book is the book of a frictionless, always-filled, infinitely-divisible venue.

**Credit where due, and one wording repair.** `harness.py:213` builds a real, populated `fidelity_caveats` tuple on every report — GAP-0001, the financing basis, the quote→USD conversion, the un-replayed in-sample block, and the Deflated-Sharpe trial provenance are all declared. That is good practice and rare. One line in it needs repair: *"fills modelled at order price ± each instrument's declared C8 friction"* is **literally true and materially misleading**, because master §5 C8 defines that friction as "the same **spread** + commission + swap/slippage cost model", and the spread is the one term not applied. A reader who knows the spec will read the caveat as stronger than it is. If R1 is taken the wording becomes true; if it is not, the caveat should say **"at the mid, plus declared slippage only — no spread is charged"**. The list should also gain a line for §6.2 (execution layer not exercised) and one for §5 (no event calendar; blackout policy not applied).

### 6.3 Latency: how much does the price move before your order lands?

[MEASURED HERE] Mean unsigned mid displacement from a randomly-chosen tick, over 4 sampled days × ~2,000 sample points per day per instrument:

| delay | EUR/USD mean / median / p95 / p99 | USD/JPY | XAU/USD |
|---|---|---|---|
| 50 ms | 0.092 / 0.046 / 0.265 / 0.486 | 0.087 / 0.046 / 0.260 / 0.530 | 0.113 / 0.067 / 0.370 / 0.639 |
| 150 ms | 0.108 / 0.046 / 0.352 / 0.619 | 0.107 / 0.067 / 0.366 / 0.690 | 0.145 / 0.077 / 0.469 / 0.834 |
| **300 ms** | **0.126 / 0.088 / 0.410 / 0.797** | 0.125 / 0.067 / 0.446 / 0.889 | 0.174 / 0.098 / 0.592 / 1.014 |
| 1 s | 0.193 / 0.091 / 0.704 / 1.320 | 0.192 / 0.092 / 0.674 / 1.340 | 0.266 / 0.148 / 0.908 / 1.636 |
| 5 s | 0.406 / 0.221 / 1.378 / 2.741 | 0.423 / 0.204 / 1.465 / 2.961 | 0.561 / 0.347 / 1.785 / 3.326 |

*(bps of mid, calm-market unconditional sample)*

**Honest reading.** At a realistic retail REST/streaming round trip of 100–300 ms, the *unsigned* displacement is ~0.10–0.13 bps, and only part of it is adverse. For a **momentum- or breakout-triggered** order it is systematically adverse (you are chasing), so budget roughly the full figure as cost; for a mean-reversion entry it is partly favourable. Either way the calm-market latency cost is **~0.1 bps per side**, i.e. **smaller than the spread term the harness is currently missing entirely**. That is a useful negative result: **latency modelling is not where the money is** — it belongs at rank 5, not rank 1. Its importance is concentrated in event windows, where the same 300 ms spans a fraction of a 32 bps move.

### 6.4 Weekend gaps measured from our own ticks

[MEASURED HERE] Last Friday mid before the close vs first Sunday mid at the reopen, 76 weekends sampled across 2013–2025 (≈6 per year):

| instrument | weekends | mean \|gap\| | median | p90 | p95 | max |
|---|---|---|---|---|---|---|
| EUR/USD | 76 | 8.93 bps | 3.88 | 20.72 | 47.13 | **59.4** |
| USD/JPY | 76 | 12.15 bps | 6.19 | 25.49 | 56.01 | **104.1** |
| XAU/USD | 76 | 14.48 bps | 6.03 | 25.30 | 69.02 | **155.5** |

**Why this matters more than its size suggests.** `PositionModel.maybe_close` books a stop at the stop price. A 47 bps EUR/USD weekend gap through a stop that sits, say, 15 bps away books a **15 bps loss in the backtest and a 47 bps loss live** — a 3× understatement of the tail loss, on the tail that the §14 max-drawdown target is supposed to measure. The harness has `holds_through_weekend` (`core/data/fx_clock`) and the §9.5 weekend-ban rule check, so it knows *which* trades are exposed; it simply does not price the gap. Note also that the median gap (3.9–6.2 bps) is already **10–17× the modelled round-trip cost** — for a system whose declared maximum hold is 48 h, weekend exposure is not an edge case.

*Caveat:* the "first Sunday tick" is the reopen print and is itself wide; the true executable gap for a stop is between that and the first few seconds of two-sided quoting. Treat these as an upper bound on the *quote* gap and a reasonable proxy for the *fill* gap.

### 6.5 Broker model, last look, and what the backtest's data actually represents

**Dukascopy is an ECN/bank feed, not a retail principal quote.** Its SWFX top-of-book bid/ask is what *its* liquidity providers show, at an indicative top-of-book size. Three consequences for a backtest built on it:

1. **The quote is raw, not marked up.** §1.1's measured 0.272 bps EUR/USD median against OANDA's published 0.6-pip typical is the markup, made visible. R3 is the fix.
2. **Top-of-book size is not your size.** A $100k–$500k retail order is small in interbank terms and will usually be inside top-of-book — but "usually" is doing work, and the exact indicative size behind a Dukascopy quote is **[UNVERIFIABLE]** from public documentation. This matters far more for gold (1.79 bps median spread, materially thinner book) than for EUR/USD.
3. **An ECN quote carries no last-look reject.** A retail principal broker's does, and this is the structural difference between the two venue models.

**Last look, from the authority that defines it.** The **FX Global Code, Principle 17** [REGULATORY/PRIMARY, verified by direct extraction of `globalfxc.org/docs/fx_global.pdf`]:

> *"Market Participants employing last look should be transparent regarding its use and provide appropriate disclosures to Clients. Last look is a practice utilised in Electronic Trading Activities whereby a Market Participant receiving a trade request has a **final opportunity to accept or reject the request against its quoted price**."*

The Code requires the provider to disclose "*whether, and if so how, changes to price in either direction may impact the decision to accept or reject the trade, the **expected or typical period of time** for making that decision, and more broadly the purpose for using last look*", and restricts its use:

> *"Last look should **not** be used for purposes of information gathering with no intention to accept the Client's request to trade."*
> *"Market Participants **should not conduct trading activity that utilises the information from the Client's trade request during the last look window**. Such trading activity would include (1) any pricing activity on FX E-Trading Platforms that incorporates information from the trade request and (2) any hedging activity that incorporates information from the trade request."*

The Code's own worked examples make the mechanism concrete and are worth reading as a description of the failure mode: a provider that *"places buy orders at levels below the 13 price [during the window]. If these buy orders are filled, the liquidity provider confirms and fills the Market Participant's trade request, but when these orders are not filled, neither is the Market Participant's trade request"* — the Code labels this a misuse. And on partial rejection: a bank that trades 50 million during the window but fills the client only 45 million, keeping the favourable 5 million — *"Market Participants that utilise the information from trade requests … should always pass on to their Client all volume that is traded in that period."*

**Why this matters to ACIS specifically, and it is not the obvious reason.** The asymmetry is not that you sometimes get rejected; it is *which* requests get rejected. A last-look price check rejects when the market has moved **against the provider** in the window — i.e. **in your favour**. So the fills you keep are systematically the ones where the market moved against you. **A backtest that always fills is not merely optimistic by the average reject rate; it is optimistic by the conditional mean of the fills it wrongly keeps.** That is exactly the structure of §5's adverse selection, arriving by a different route, and it bites hardest in the same windows — fast markets, releases, and the moments a breakout module wants to trade.

Quantified reject rates and the implicit bps cost to the taker are **[UNVERIFIABLE in this session]** — the academic work on this (Oomen's papers on last look and aggregator execution; Cartea & Jaimungal) was not retrievable within the remaining budget, and OANDA publishes no fill statistics (§1.3). What *is* established from primary sources: the practice exists, the Code obliges disclosure of typical hold time and purpose, and its documented misuses are all mechanisms for asymmetric outcomes against the client.

**OANDA's own model sits in between.** It is a principal/market maker, so its quote embeds its markup and there is no price improvement to model (§1.2). Its published mechanism is a **bounded-slippage** one — upper/lower bound on the web platform, "maximum deviation" on MT4, with the order **cancelled** rather than filled beyond the bound [BROKER-PRIMARY]. Functionally that is a client-controlled version of the same thing: in a fast market you get **no fill** rather than a bad fill. For ACIS this is the more important modelling object than slippage, because a cancelled entry is a *position you do not have*, and the backtest currently has it.

**What narrows the gap, ranked** (this is the evidence behind R1/R4/R7/R9/R10):

| change | what it fixes | share of the gap closed | evidence |
|---|---|---|---|
| **(a) fill at bid/ask, stops triggered on the executable side** | the half-spread per side, and the stop-trigger optimism | **largest** — it is the whole of F1 | §1.1 measured spreads; ACIS-09 C-BT-5 requires it |
| **(b) broker markup on the raw ECN spread** | ECN-vs-principal quote difference | large — the remaining ~2.3× | §1.2 OANDA published typicals |
| **(c) stops fill at the worse of the level and the next price (gap-through)** | the tail, which is where drawdown lives | large in the tail, nil in the median | §6.4 measured gaps: median 3.9 bps, p95 47 bps, max 59 bps EUR/USD |
| **(d) reject probability conditioned on short-horizon volatility** | last look / bounded-slippage cancellation, and its adverse selection | moderate, concentrated in fast markets | FX Global Code P17; OANDA bounded-slippage policy |
| **(e) fat-tailed, volatility-conditional slippage** | the p99 the constant has no representation of | moderate | §1.3 — but note the *median* is already roughly right |
| **(f) latency delay before the fill price is taken** | signal-to-fill drift | **small in calm markets** — 0.09–0.13 bps at 50–300 ms | §6.3 measured |
| **(g) session/volatility-dependent spread instead of the raw quote** | **unnecessary** — the raw tick spread already carries this | nil | §1.1: using `st.spread` per tick (change (a)) gets it for free |

Note (g): a synthetic spread model would be a step *backwards*. The tick archive already contains the true per-tick spread, including the rollover spike and the NFP widening measured in §1.1 and §5.1. **Change (a) picks all of that up at no modelling cost** — which is a large part of why R1 ranks first.

---

## 7. RECOMMENDATIONS, ranked by value-for-effort

Tags: **[implementation]** = a code/test change inside existing spec authority. **[spec-level]** = changes a declared rule, a config schema, or a §14 claim, and therefore **requires owner ratification** before anyone writes it.

### Tier 1 — do these before any paid run or any further falsification attempt

**R1. [implementation] Fill at the executable side of the book, not the mid.** *Effort: ~20 lines + tests. Value: decisive.*
In `tests/backtest/book.py`: open at `st.ask` for a long and `st.bid` for a short; close at the opposite side; trigger a long's stop on `st.bid` and its target on `st.bid` (mirror for shorts). `apply_order` and `maybe_close` already receive the full `MarketState`, so `bid`/`ask`/`spread` are in hand — no plumbing needed. This makes the spread **structural** rather than an added term, uses the *actual* tick spread (so event-window and rollover widening are priced automatically), and simultaneously fixes F4's stop optimism. Keep `slippage_per_side` as the residual friction on top.
*Measured effect:* EUR/USD round trip moves from 0.367 → ~0.64 bps at the median and considerably more in the 5 % of minutes that matter. Break-even IC at the engine's realised 8-minute hold moves 0.091 → 0.158.
*Note:* this is the **C8-conformant** version. Do **not** also call `per_side_cost(spread)` on top, or the spread is charged twice.
*Authority:* R1 needs no ratification. `specs/ACIS-09-BACKTEST_VALIDATION.md` v1.1 (LOCKED) already **requires** it — "spread + slippage models are applied so backtest fills are **not naively at mid**", C-BT-5 — and master §5 C8 requires the harness and the fitness path to share one model. R1 brings the code into conformance with locked specs; it does not change them.

**R2. [implementation] Re-run the GAP-P12D-28 falsification suite after R1, unchanged in every other respect.** *Effort: a re-run. Value: decisive.*
The planted/null/permuted verdict is currently the project's single most important open result (GAP-P12D-31). It was produced under a cost model that is ~4× optimistic. Whatever the verdict becomes, it will mean something different — and if planted still fails at a higher cost, the diagnosis in GAP-P12D-31 (horizon mismatch, exit geometry, entry spam) is confirmed rather than confounded.

**R3. [spec-level] Declare a per-instrument broker markup on top of the raw ECN spread, and wire `calibrate_cost_model` into the graded path.** *Effort: one config key + schema + wiring. Value: high.*
Dukascopy is an ECN top-of-book; ACIS will trade a principal broker. Calibrating from the published typicals: EUR/USD 0.272 bps measured vs 0.55 bps OANDA-typical ⇒ **×2.0**; USD/JPY 0.422 vs 0.87 ⇒ **×2.1**. A declared `broker_spread_multiplier` (or an additive markup in price units) per instrument, applied in the harness, closes the remaining ~2.3× gap in F2. This is spec-level because C8 and §13 v2.9 describe the calibration and a new declared term changes them. Related: `data_loader.calibrate_cost_model` already exists and is **not used** by `oos_runner`; either wire it or retire it (§18 lean-build law).

**R4. [implementation] Stops fill at the worse of the stop level and the next observed executable price (gap-through).** *Effort: ~10 lines + a glitch test. Value: high, concentrated in the tail.*
§13 already lists "weekend gap through a stop level" as a required glitch class; `holds_through_weekend` exists in the harness. What is missing is that the *fill price* still assumes the level. Measured weekend gaps are in §6.4 — this is the difference between a modelled and a real worst case.

**R5. [spec-level] Build the historical Tier-1 event calendar and grade the engine twice — with and without the live blackout policy.** *Effort: significant (see §5.4 for sources). Value: high, and it is a validity issue, not only a cost issue.*
Today the backtest grades a policy the live engine will not run (master §3.5 blackout is a live-only gate). The difference between the two grades **is** the measurement of how much backtest PnL comes from minutes the live engine is forbidden to trade. On §5.2's arithmetic that share is plausibly 15–25 % of trades.

### Tier 2 — do these before live, after Tier 1 has changed the numbers

**R6. [spec-level] Give the Governor a target position with a no-trade band, and let the band set the holding period.** *Effort: substantial. Value: the highest of anything in Tier 2, and it subsumes three open gaps.*
This is §4.5 in full. Summary: (a) one **target position per instrument**, netted across all live signals, instead of one `SizedOrder` per `Signal`; (b) a **no-trade band** around the held position, sized off the instrument's *average* absolute position rather than its current one, trading **to the band's edge** rather than to the target; (c) the band width — not stop/target geometry and not `apply_order`'s dedup — sets the holding period.
*Why this one and not a minimum-hold rule:* a hard min-hold blocks a *correct* exit, which is a different and worse thing than declining an unnecessary entry; the band declines the entry. Carver's production system uses `buffer_size: 0.10` with `buffer_trade_to_edge: True` [PRACTITIONER, verified], and the band-width result is robust to cost uncertainty (`w ∝ c^{1/3}`: quadrupling the cost widens the band only 1.59×), so it can be adopted *before* the cost model is perfect.
*What it closes:* GAP-0075 (no position/holding policy), the F6c unit mismatch (`max_holding_periods` finally has somewhere to apply), the §14 duration-floor failure in §3.3b, and a large share of §1's cost drag — with one mechanism, at the layer §2's Layer Communication Law already assigns to it.
**Requires ratification:** ACIS-05 and master §6 describe signal→`SizedOrder` sizing, not target-position management.

**R6b. [implementation, inside R6 or before it] Net positions across signals before they become orders.** *Effort: small. Value: free.*
The Governor currently emits one order per surviving signal; nothing nets two modules that want opposite positions in the same instrument, so they produce two round trips and a flat book. Netting before execution is an identity, not a model change — it cannot destroy an edge — and it is the cheapest item in §4.4. It can be done independently of the full target-position rework.

**R7. [implementation] Model rejection, not just slippage.** OANDA's bounded-slippage mechanism **cancels** rather than slips in a fast market [BROKER-PRIMARY]. A backtest that always fills is optimistic about *having the position* in exactly the conditions where a breakout module wants one. A declared per-instrument reject probability conditioned on realised short-horizon volatility is a closer model than any slippage constant.

**R8. [implementation] Route the graded replay through `core/execution/` — this is spec-required, not optional.** *Effort: moderate. Value: high; it is a locked-contract gap.*
`specs/ACIS-09-BACKTEST_VALIDATION.md` §7.2(c) requires the replay to honour "**Execution fill modelling**" and §7.2(d) to "collect **FillReports**". `harness.py` imports nothing from `core/execution/` (§6.2). Until the replay actually runs through `ExecutionOrchestrator`, partials, rejections and reroutes cannot appear in any graded run, and the outstanding server-side-stop threading (GAP-0091b/0099/0075) has no backtest that would catch a regression. If routing it is deferred, the deviation must be added to `fidelity_caveats` **and** to `KNOWN_GAPS.md` — an undeclared departure from a locked spec is the finding, whichever way it is resolved. (Note: R8 and R1 are independent. R1 is 20 lines and fixes the *price*; R8 is larger and fixes *whether the order happened*.)

**R9. [implementation] Add a latency delay to fills.** Take the fill from the first tick ≥ N ms after the signal tick. §6.3 measures the cost at ~0.1 bps per side calm-market — real, but an order of magnitude below R1. Its value is in event windows.

**R10. [implementation] Volatility-conditional, fat-tailed slippage instead of a constant.** The constant 0.2 bps is a defensible median and an indefensible mean. Draw from a distribution conditioned on realised volatility over the preceding minute; the p99 is what kills accounts, and the current model has no p99.

### Tier 3 — cheap, do when convenient

**R11. [implementation] Calibrate and declare costs for the diversification basket before enabling any of it.** `GBP_USD`, `AUD_USD`, `USD_CAD`, `EUR_GBP`, `USD_CHF`, `XAU_USD` currently declare **no** `costs` block. `PositionModel.cost` correctly refuses them, so nothing is silently free — but the onboarding step is unfinished, and gold's measured spread (1.79 bps median, ~6× EUR/USD) means a cost constant copied from a major would be badly wrong.

**R11b. [implementation] Fix the USD/CAD triple-swap day before `USD_CAD` is enabled.** *Effort: one config/table entry + a test. Value: small but it is a latent bug with a named §13 glitch class.*
OANDA, verbatim: *"USD/CAD settles on a T+1 basis and therefore has its three-day financing applied on a **Thursday**."* `config/instruments.yaml` declares `USD_CAD: swap_convention: tom_next`, and `carry._TRIPLE_DAY["tom_next"] = 2` (Wednesday). Nothing is wrong today because `USD_CAD` is disabled — but §13 lists "triple-swap Wednesday flipping carry math in backtests" as a required glitch class, and this is that class, pre-loaded. The same table should grow entries for settlement-centre holidays (a US holiday on the value date adds a day; the New Year cluster can carry 4–6 swap-days in one roll) and for brokers like IG that triple the tom/next on Wednesday and the **admin fee on Friday** — a single multiplier over the whole charge cannot express that.

**R12. [implementation] Bound the financing model with a sensitivity band rather than chase exact swap tables.** At ≤48 h, financing is 0.27–1.1 bps per night (§2). Running the graded backtest at the model rate ±X and reporting the spread of outcomes is cheaper and more honest than reverse-engineering a broker's weekly-repriced table, and it is the only approach that survives the broker changing the table.

**R13. [documentation] Record the C8 divergence (F1) as a ledger entry regardless of whether R1 is taken.** Master §5 C8 says the two paths use the same model and `test_cost_model_semantics` is cited as proof; the test pins `CostModel`'s arithmetic but never asserts that `book.py` calls it. That is a live claim in the read path that the code contradicts.

### Limitations of this report — what I could NOT verify

Recorded so nobody treats a gap as a clean bill of health:

- **OANDA publishes no fill or slippage statistics.** Their education page gives one worked example (3 pips) and the bounded-slippage mechanism, and no distribution. §1.3's slippage numbers are therefore the **weakest-evidenced** part of the report, and the declared 0.2 bps/side is defended only as a *median calm-market* figure, never as a mean.
- **Interactive Brokers' primary pricing pages returned HTTP 403** throughout; the "honest benchmark" tier table in §2 is [PRACTITIONER]-graded and should be re-verified before it is relied on.
- **No authoritative free gold forward/lease curve exists** post-30-Jan-2015 (§2.2d). `DEFAULT_GOLD_LEASE_PCT = 0.25` with a declared sensitivity band remains the honest treatment.
- **The web-search budget for this session was exhausted** partway through. The gap was filled with direct fetches of known primary URLs and — more valuably — with measurements taken from this repo's own tick archive, which is stronger evidence than any of the secondary sources would have been. Where a claim rests only on a review aggregator it is tagged [UNVERIFIABLE].
- **All [MEASURED HERE] figures are from a *sample*** — 8 trading days for spreads and volatility, 10 NFP releases, 76 weekends, 4 days for latency — chosen to span 2013–2025. They are the right order of magnitude and should not be treated as precise. The full archive (35,008 day files) is on disk; re-running the same scripts over all of it is cheap and would make every table exact.
- **The information-coefficient values in §3 are illustrative**, not measured. The *structure* of §3.2/§3.3 (break-even IC = c/(σ·√h), h_min = (c/(IC·σ))²) is exact arithmetic; the choice of "plausible IC = 0.03–0.05" is a judgement informed by published systematic-FX results, and a reader who disagrees should substitute their own and re-read the tables — the conclusion that the modelled cost makes an 8-minute horizon look viable and the real cost does not is robust across the whole plausible range.

### What I would *not* do

- **Do not chase exact broker swap tables** before Tier 1. It is the most research-intensive and least material item on this list for a ≤48 h system — and §2.2(c) shows it is *unstable* anyway: OANDA's own published markup moved 20 bps/side on FX and 120 bps/side on gold in six months. A model calibrated to last quarter's table is wrong by next quarter. The cheap substitute is the assertion in §2.5 (`long + short < 0`, record the implied markup) plus a sensitivity band.
- **Do not add price improvement to the fill model.** A principal broker's quote is its markup; there is nothing to improve on.
- **Do not tune the cost constants to make the falsification pass.** The owner's standing rule on GAP-P12D-31 ("if planted fails, that is a finding, not a reason to tune the test") applies with equal force in the other direction: making costs honest is a fix; making them flattering is not.

---

## Appendix A — how to reproduce every [MEASURED HERE] number

All four measurements read `data/dukascopy/<INSTR>/<YYYY>/<MM0>/<DD>_ticks.bi5` through the repo's own decoder, `tests.backtest.bi5.decode(raw, instrument, period_start_utc)`. They are read-only, single-threaded, and need no engine run.

| § | measurement | sample | method |
|---|---|---|---|
| 1.1 | spread distribution, bps of mid | 8 days: 2013-03-14, 2015-06-10, 2017-09-13, 2019-11-06, 2021-02-10, 2023-05-10, 2024-09-11, 2025-03-12 | every tick; `(ask−bid)/mid × 1e4`; percentiles tick-weighted; hourly medians bucketed on `ts.hour` (UTC) |
| 3.2, 6.3 | 1-minute σ and annualised vol | same 8 days | last tick per minute → `log(m[t+1]/m[t])` for **consecutive** minutes only; `σ_ann = σ₁ₘ·√(1440×260)` |
| 5.1 | NFP spread and displacement | 10 first-Friday releases 2015–2025, DST-correct 08:30 ET | baseline = mean spread T−60 m…T−30 m; buckets at T−5 m…T−1 m, T…T+10 s, +10 s…+1 m, +1 m…+5 m, +5 m…+30 m; displacement = \|last mid ≤ T+h − last mid < T\| |
| 6.3 | latency displacement | 4 days, ~2,000 evenly-spaced sample ticks/day | `bisect` the first tick at ≥ t+L; `\|Δmid\|/mid × 1e4` for L ∈ {50, 150, 300, 1000, 5000} ms |
| 6.4 | weekend gap | 76 weekends, ~6/year 2013–2025 | last Friday mid vs first Sunday mid, same instrument |

Caveats that apply to all of them: **tick-weighted, not time-weighted** (so busy hours are over-weighted — this makes the spread figures *conservative*, since quiet hours are wider); the 24 h × 260 d annualisation overstates FX vol modestly; and the 8-day sample was chosen to span the period, not at random.

**Two of these are worth promoting into the test suite rather than leaving in a research file:** the NFP spread/displacement measurement is a ready-made §13 glitch-class fixture, and the weekend-gap distribution is the empirical input R4 needs.

---
