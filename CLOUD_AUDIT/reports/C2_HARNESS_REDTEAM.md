# C2 — HARNESS RED TEAM: how the ACIS backtest can report profit the market would not pay

- **Lane:** C2 FALSE-ENCOURAGEMENT HUNTER, cloud review run 2.
- **Model:** Opus 5.5 (`claude-opus-5-5`). Effort is not observable from inside the session.
- **Context:** fresh. I launched no subagents.
- **Reviewed commit (BASE):** `7695ed04`, read-only at `/tmp/review-acis`.
- **Date:** 2026-09-24. The work ran from 18:04 to about 18:20 UTC by `date -u`.
- **Web use:** 1 search and 1 fetch, both on the FTMO commission. The budget was 10.
- **Data:** synthetic only. I read no `.bi5` prices and ran no download or data script.
- **Evidence:** everything is under `reports/evidence/C2/`.
  - Six scripts: `repro_stop_fills.py`, `sim_stop_rules.py`, `repro_fitness_stitch.py`, `repro_pair_leg_spread.py`, `repro_gate_blindspots.py` and `repro_canary_bypass.py`.
  - Each script's output is saved beside it as `out_*.txt`.
  - Every `repro_*` script runs from the review tree as `cd /tmp/review-acis && python <script>`. `sim_stop_rules.py` imports no ACIS code, so it runs from anywhere with `python sim_stop_rules.py`.
  - Each run takes under 5 s on one core.
- **Labelling:** every mechanism below is reproduced in code. Every magnitude comes from a synthetic tape, so it is an estimate for real data, not a measurement. The fixes and the regression tests I propose are **LLM-originated**.

## 1. Executive summary (graded; [code] = shown in code at BASE, [sim] = synthetic measurement)

1. **The GRADED tick book fills every protective stop AT the stop price, and triggers it on the MID.** [code + sim]
   - This holds however far the market has gapped through the stop (`tests/backtest/book.py:115-121`).
   - Reproduced through the real `Backtest.run`:
     - a Friday-to-Sunday gap is booked at −$74 where a broker stop fills at −$524;
     - a bid through the stop while the mid is not turns a −$84 loser into a +$281 winner.
   - On a synthetic 20-second tape, the stop rules alone flatter a trade by **+0.31 to +0.47 pips on average** (95% CI about ±0.1). Single trades are flattered by up to **85 pips**.
   - This is the same flaw as the `fitness.py:115-125` seed, but in the harness that GRADES the run.
   - The local VALIDATOR's §7.2 says "the tick book correctly exits at the gapped tick". **That statement is false at BASE.**
2. **The loader DROPS every tick whose spread exceeds `max_plausible_spread`.** [code + repro]
   - The limit is 5 pips on EUR_USD and 5 pips on USD_JPY (`tests/backtest/data_loader.py:82-83`).
   - So a stop never fires during a rollover or news spread spike, and the backtest never sees the moments a broker's stop is most likely to be hit.
   - Reproduced: a 20-pip rollover spike with the bid 10 pips through the stop books as **+$281 instead of −$164**.
   - Live, the normaliser only FLAGS such ticks (`core/data/normaliser.py:226-228`), and a server-side stop would still fire on them. That is a backtest/live parity break.
3. **QIEA's fitness sim scores a STITCHED series.** [code + sim]
   - It reads only the bars of one regime, concatenated (`regime_labels.py:165-181`, `qiea.py:69-76`). Positions and indicators carry across jumps of hours or days, and a jump through the stop is booked at the stop.
   - On a driftless walk:
     - the stitch adds **+0.22 to +0.38 pips/trade** against episode-by-episode scoring;
     - the gap cap alone adds **+0.59 to +0.90 pips/trade on average, and up to +3.4 on individual ParamSets.** Selection picks maxima.
   - This is not in the ledger.
4. **A pair's second leg is charged the FIRST leg's spread.** [code + repro]
   - `apply_order(order, st)` stores `st.spread` from the anchor's tick (`book.py:110`, `harness.py:170-172`).
   - On the configured `[EUR_USD, USD_JPY]` pair, the JPY leg's entry half-spread is under-charged by about 100×: **$3.97 per 100k leg entry**.
   - Both legs are also priced at the last *joint-bar* close (`agon.py:476-479`), which is a stale quote.
5. **`passed` reads neither `var_breach_frequency` nor any fidelity caveat.** [code + repro]
   - A report with a **20% VaR breach rate** and "NO overnight financing modelled" still returns `passed=True` (`report.py:265-274`).
   - The synthetic grader always runs with `financing=None` (`synthetic_grade.py:96`).
6. **The Deflated Sharpe counts TRADES as independent observations.** [code + repro]
   - Booking the same decisions twice leaves the Sharpe unchanged and moves the DSR from **0.838 to 0.919**. Four times moves it to **0.976**, past the 0.95 gate.
   - Pair legs are exactly this case; trades on correlated instruments are a milder version.
7. **The look-ahead canary has a blind channel: the regime LABELS.** [repro]
   - Labels chosen with future prices pass `refuse_lookahead`, because every timestamp is honest.
   - On a null walk they lift the share of ParamSets with positive E_R from **2/60 to 21/60**.
   - This extends VALIDATOR's T1/T2: those two tests must cover the label cache, not only orders.
8. **Configuration and venue look-ahead or mismatch.** [code + (b) source]
   - `commission_per_side: 0.0` for both enabled pairs, while the chosen venue (FTMO) is listed at **"$5 per lot"** on cTrader (ctrader.com, (b)).
   - The cost values carry no calibration window.
   - The diversification basket is to be calibrated on the whole 2012–2025 archive, which overlaps the holdout (`instruments.yaml:98-101`).
   - The "graded once" holdout marker is **gitignored** (`/data/` in `.gitignore`), so it binds one disk only.
9. **Equity, drawdown and the Governor's NAV mark open positions at the mid with ZERO exit friction.** [code + repro]
   - A flat one-lot EUR_USD position marks at $0.00 but books −$14.00 when closed (`book.py:158-167`).
   - A prop account's daily-loss rule is measured on equity net of those costs.
10. **The synthetic tape cannot expose findings 1–4.** [code]
    - Its spread is a constant 0.4 bp, it has no weekend gap and no spread spike, and it has no cross-instrument correlation. So PAIR_DIVERGENCE can clear its 0.40 stability floor only by chance.
    - The cost-stress ladder multiplies only the per-side C8 cost. The positive TREND and BREAKOUT numbers in GAP-P12D-49 are therefore measured inside this optimism, not outside it.

---

## 2. Body — every attack class, marked

Legend: **HOLE** = a confirmed false-encouragement path, reproduced. **CAUGHT** = the harness handles it; the evidence is cited. **N/A** = no such path exists at BASE.

### 2.1 Look-ahead

| Attack | Verdict | Evidence |
|---|---|---|
| A signal on an incomplete bar, or a close used before it exists | **CAUGHT** | `BarAggregator.add` (`core/data/bars.py:68-92`) returns a bar only when a tick arrives in a later bucket. AGON's modules read only completed bars and fill at the tick that completed the bar, which is the tick analogue of next-bar-open. The fitness sim enters at `bars[i+1].open` (`fitness.py:146-147`). |
| Rollover-anchored daily bars | **CAUGHT** (one minor defect, below) | `DailyBarAggregator` buckets by `trading_day` (`bars.py:100-112`). The TSMOM seed reads only bars that close by `train_end` (`warmup.py:22-28`). **Minor defect, not look-ahead:** `train_end` (00:00 UTC) falls inside a trading day, so the seed carries that day's *partial* close. The live aggregator then emits the same trading day again as its first completed bar, so one day is double-counted in the 63/126/252-day lookbacks. |
| Indicator warm-up | **CAUGHT** | Fitness warms up to `max(ema_slow, rsi+1, atr+1)` (`fitness.py:95`). The harness replays observe-only warm-up ticks through the embargo (`harness.py:132-138`). |
| Cross-instrument timestamp alignment (pair legs) | **HOLE (costs and prices, not direction)** | See finding 4 and §2.3. The joint samples themselves are causal (`agon.py:139-156`). |
| Fold-boundary siblings of GAP-P12D-35 | **CAUGHT**, with one reporting caveat | The rewind now raises (`harness.py:132-137`). `evolve_fn` runs before the fold's replay, and `train_end(k+1) == test_end(k)` in both `oos_plan.plan_folds` and `synthetic_grade.plan`, so nothing is staged ahead of the clock. `LabelledBarCache.history` excludes a bar that straddles `train_end` (`regime_labels.py:175`). **Caveat:** warm-up (embargo) ticks still append daily equity points (`harness.py:175-178`), and `period` is taken from that curve. The embargo days therefore count toward "≥ 2 years" although no decision is made on them. That is 7 of every 37 days in the synthetic plan: GAP-P12D-49's "2.05 graded years" contains roughly 0.39 years of observe-only time. The effect on Sharpe is conservative (zero-return days); the effect on the years gate is lenient. |
| The canary itself | **HOLE** | Finding 7. `repro_canary_bypass.py`: `refuse_lookahead` stays silent, and the positive-E_R share on a null walk goes from 2/60 to 21/60. |

### 2.2 Fills

**Seed confirmed, and the GRADED harness has the same flaw.**

- `fitness.py:117-125` books `exit_mid = sl` whenever `bar.low <= sl`, even when `bar.open` is already below it.
- `book.py:115-116` does the same on ticks: `if price <= pos.stop_loss: close_at(pos, pos.stop_loss, …)`, where `price = st.mid`.
- GAP-P12D-42 mentions that the harness "books stops AT the stop price", but only as the reason a glitch test cannot be written. Nobody has priced it, and the local VALIDATOR states the opposite.

`repro_stop_fills.py` drives the real `Backtest.run`, with the real loader filter and the real `MarketStateFactory`, on a 1-lot EUR_USD long with a 5.5-pip stop:

| Scenario | Harness books | Broker sell-stop | Flattered by |
|---|---|---|---|
| A. Weekend gap of −50 pips through the stop | −$74.00 (a loss at the stop) | −$524.00 | +$450 |
| B. Rollover spike to 20 pips, bid 10 pips through the stop; the tick is DROPPED, and price later reaches the target | **+$281.00, a WIN** | −$164.00 | +$445 |
| C. A 4-pip spread (so the tick is kept), bid through the stop, mid not | **+$281.00, a WIN** | −$84.00 | +$365 |

`sim_stop_rules.py` (no ACIS code) sizes the stop rules on random-entry trades with a 10-pip stop and a 15-pip target:

| Tape | Harness minus broker, pips/trade | Largest single trades |
|---|---|---|
| Weekend gaps (sd 30 pips) + rollover spike | **+0.365 ± 0.095** | 45, 54, 62 |
| No gaps, spike only | +0.427 ± 0.099 | 27–30 |
| Gaps only | +0.469 ± 0.108 | 51, 81, 85 |
| Neither (1-pip constant spread) | +0.307 ± 0.090 | 26 |

- **What the last row means:** even on a clean tape, the harness ignores the tick-to-tick overshoot past the stop. The mid moves about 0.8 pip per 20 s tick, and the bid lands *beyond* the stop, not on it.
- The declared `slippage_per_side` (0.2 pip on EUR_USD) is the same size as this average, but it is charged on every fill, and it cannot pay for the tails.
- The ACIS synthetic tape uses the same 20 s tick and daily volatility as this sim. So the within-tick overshoot part (~0.3 pip on each trade that involves a stop) plausibly applies to the GAP-P12D-49 planted run.
  - Its 1× friction was about $16 on 2,141 trades, while TREND plus BREAKOUT netted +$14.80.
  - I did not convert pips to that run's dollars, because its sizes are not in the report, so treat this as an **estimate**.
  - But the sign is clear: the thin positive modules are measured inside this optimism.

**Stale quotes, and fills at the mid.**
- Ordinary orders fill at the decision tick's mid plus the declared half-spread: equivalent to the ask, with zero latency. Acceptable as declared.
- **Pair orders are the exception:** both legs are priced at `a_col[-1]` and `b_col[-1]`, the last *joint* bar closes (`agon.py:476-479`), not the current quote. When the second leg has not ticked, that price can be minutes old. **HOLE (stale quote).**

**Open and close on the same tick.** CAUGHT: a new position is first managed on the instrument's *next* tick (`harness.py:148-172`), and a reverse pays both spreads.

**Partial fills and latency.** N/A: they are not modelled. This is covered by the GAP-0001 caveat. There is zero latency; it is mildly optimistic and unmeasured, as VALIDATOR T5 says.

**Target side.** Not a hole. A long target is booked at TP − s/2 once the mid reaches it; that is a price a market order could get.

### 2.3 Costs

- **Rollover and news spread.** A HOLE, through the loader drop in finding 2.
  - Spikes above 5 pips are removed before the book sees them. Spikes under 5 pips are charged only when an order happens to fill on that tick.
  - The synthetic tape has neither. With no event calendar, news is also traded through (`NO_CALENDAR`, GAP-P12D-03).
  - **Cheap measurement for the local lead:** the loader already logs every drop as `BACKTEST_BAD_TICK`. Count them by NY hour-of-day over the real archive. That turns finding 2 from a mechanism into a number, without anyone here reading prices.
- **Commission.** A HOLE (venue mismatch).
  - `config/instruments.yaml:50-52` and `:67-69` set `commission_per_side: 0.0`.
  - The chosen venue family lists forex at **"$5 per lot"** for FTMO on cTrader (ctrader.com/prop-firms/ftmo, fetched 2026-09-24, (b)). The page does not say per side or per round turn.
  - That is 0.25–0.5 pip per side, the same order as the whole declared EUR_USD slippage.
  - GAP-P12D-41, GAP-P12D-45 and GAP-P12D-46 treat the spread *level*. None of them names the zero commission.
- **Slippage.** Declared per side, flat, and never a function of spread, volatility or gap. See §2.2.
- **Swap sign and triple Wednesday.** CAUGHT at the mechanism level.
  - `carry.py:26` puts the triple on Wednesday (tom_next) and Friday (financing_daily). `financing.py:98-103` charges `direction×(r_base−r_quote) − fee` to both sides, and `business_rollovers` counts Monday–Friday only.
  - **But:** the fee is OANDA's 1.00%, not the prop venue's swap table.
  - More importantly, every synthetic grade runs with `financing=None`, and `passed` ignores the "flattered" caveat (finding 5).
- **Pair second leg.** A HOLE (finding 4). `repro_pair_leg_spread.py`:
  - the USD_JPY leg booked on a EUR_USD tick stores `entry_spread = 0.00010`;
  - the charge is 0.00205 JPY/unit where 0.00800 is due, an under-charge of $3.97 per 100k per leg entry;
  - a cross-instrument reverse close has the same fault (`book.py:100-101`).
- **What the cost-stress ladder really covers.** It covers `stress × (max(spread, floor)/2 + commission + slippage)` per fill, and nothing else.
  - It does **not** touch: the stop-price fills (§2.2), the dropped spikes (finding 2), financing (`None` on synthetic), commission when that is declared 0 (×k of 0 is 0), the pair-leg spread mix-up, or latency.
  - Its `spread_floor` rung is inert on the constant-spread tape.
  - `decompose()` assumes a fixed trade set, which is a declared assumption.
  - So "friction is ~11% of the loss" (GAP-P12D-49) is 11% *of the friction the model can express*.

### 2.4 Configuration look-ahead

- **Seed confirmed.** `config/instruments.yaml:98-101` says the basket's costs and `vol_target_atr_frac` will be "calibrated from the real Dukascopy ticks". The archive runs 2012–2025, which contains the 2024–2025 holdout.
  - `data_loader.calibrate_cost_model` takes the median over whatever it is handed, and records no window.
- **Further instances:**
  - The enabled pairs' `costs` are commented "phase-11 OANDA calibration", with no window and no source file. That is unfalsifiable as written.
  - `max_plausible_spread` is a hand-set value that decides which ticks exist at all (finding 2).
  - `vol_target_atr_frac: 0.0008` has no provenance.
  - The regime thresholds were derived on synthetic random-walk and OU processes (`system_config.yaml:24-28`). That is *not* a real-data leak: an honest negative.
- **Holdout discipline.**
  - `HoldoutGuard` (`oos_plan.py:124-153`) enforces "graded once" with an exclusive-create file under `data/validation/`, and `/data/` is gitignored.
  - A second checkout, a re-download, or a deleted `data/` grades the holdout again with no trace.
  - `run_walk_forward` itself never calls the guard; only `scripts/run_oos_validation.py` does.

### 2.5 Selection look-ahead

- **Universe:** two FX majors, so survivorship is N/A. The module set and the regime set are fixed in config, and so far have been revised only on synthetic evidence. There is no real-data selection leak yet.
- **The live risk is the next step.** Every module and regime revision scored on the 2014–2023 development record is a look. The count belongs to C1's looks budget; I found no code that records it.
  - `min_trials` counts the attempt-registry entries (`oos_runner.py:139`), not pipeline revisions.

### 2.6 Accounting

- **Equity marks.** A HOLE (finding 9). `unrealised` is taken at the mid with no exit friction, and the same number feeds:
  - the intraday high-water mark and max drawdown (`harness.py:173-174`);
  - the daily-loss anchor (`harness.py:159-161`);
  - the Governor's NAV (`harness.py:117-122`).
  - Positions still open at the end of the run are never closed, so they never pay exit friction and never enter `trades`.
- **Drawdown measure.** Measured intraday on every tick, and more conservative than daily. Good, apart from the missing exit cost above.
- **Annualisation.** One point per UTC date, at that day's first tick, annualised with √252. On real FX that gives about 6 points a week (Sunday evening UTC), which *understates* Sharpe by about √(252/312). Conservative: an honest negative.
- **P&L currency (GAP-P12D-05).** CAUGHT: conversion happens once, at the close rate (`book.py:150-156`). A cross without its conversion leg raises.
- **Compounding.** Sizing reads the live NAV. N/A.
- **Trade counting.** A HOLE for the gates: pair legs are two `ClosedTrade`s, and they count twice toward:
  - the 30-trade floor;
  - the win rate and profit factor;
  - the DSR's T (finding 6).

### 2.7 The synthetic generator as a grader

`synthetic_market.py` has these properties:
- a constant spread (`spread_frac` 0.4 bp);
- continuous Friday→Monday prices, so no weekend gap exists;
- iid Gaussian noise with constant σ (no volatility clustering and no fat tails);
- independent instruments;
- uniform 20 s ticks;
- 1–4 h episodes only.

What follows from that:
- **Findings 1–4 are invisible to `falsify_engine.py` and to the ladder by construction.** The planted "positive control" is graded in a frictionless-tail world.
- MOMENTUM_SCALP cannot fire, because tick velocity is constant (the local BUILDER's point).
- PAIR_DIVERGENCE needs |corr| ≥ 0.40 with sign −1 between independent series, so it fires only by chance. It took −0.09 on its few trades in GAP-P12D-49.
- NVMA's velocity, spread and volatility-ratio inputs are all constant, so the regime router is exercised on one axis only.
- Multi-day edges are absent (C3's horizon test).

**What a faithful positive-control tape needs (LLM-originated):**
1. a spread process with a rollover spike and a news spike, some above `max_plausible_spread`;
2. Friday→Sunday gaps drawn from a fat-tailed distribution;
3. GARCH-t noise;
4. a common factor across instruments, with ρ matched to the pair's `expected_sign`;
5. Poisson tick arrivals with an intensity that follows the session;
6. planted episodes at *two* horizons (hours and days to weeks);
7. an oracle whose fills obey the broker rules of §2.2, so that the positive control grades itself under the same rules the market enforces.

### 2.8 BUILDER's `_avg_duration` fix (BRANCH.patch, `metrics.py` hunk)

- **Correct.** An empty population now returns NaN rather than 0.0. `grade_out_of_sample`'s band check `1800 <= nan <= 172800` is False, exactly as 0.0 was, so no gate outcome changes; only the report stops pretending.
- `MetricBlock.as_dict` maps NaN to `null`.
- **Two residuals:**
  - `synthetic_grade.grade` passes `avg_duration_s` through raw, so `ladder.json` will serialise a bare `NaN`, which is invalid strict JSON.
  - `slice_stats` still returns `0.0` for an empty list. That path is unreachable, because slices exist only when trades do.

---

## 3. What I could not verify

- **The real-tape magnitude of findings 1 and 2.** I read no prices, by rule. The `BACKTEST_BAD_TICK` hour-of-day count (§2.3) is the local measurement that settles it.
- **Whether FTMO's "$5 per lot" is per side or per round turn,** and what FTMO's swap table is. The cTrader listing did not say.
- **The pip-to-dollar conversion of the §2.2 estimate onto the GAP-P12D-49 run.** Its per-trade sizes are not in the ledger.
- **How often the real NVMA regime flips per day.** That frequency sets the size of the stitch bias (finding 3). My block-length sensitivity (30–400 bars against 10–120 bars) shows the bias grows as flips get more frequent.
- **Whether the pair module's stale joint-bar price is biased in a consistent direction.** I reproduced the mechanism, not the sign.

## 4. Residual risk

- Every hole here makes results *look better*, and none of them can be deflated away statistically. A run that clears §14 or the ladder at BASE is therefore still an upper bound.
- The largest structural risk is that **the only positive control, the planted tape, lives in the one world where these holes cost nothing.** A later "planted passes" will be read as validation of the harness, when it is validation of a harness with its failure modes switched off.

## 5. Proposed ledger items (no IDs)

Each row gives: the item; Severity / Likelihood / proposed Status; the tag; the value against the complexity cost; and **the regression test to write, in prose**.

1. **The graded book books gapped and mid-triggered stops at the stop price.**
   - critical / high / open. [impl]
   - *Value:* removes an average +0.3–0.5 pips/trade optimism and an unbounded tail. *Cost:* about 10 lines in `maybe_close`: trigger a long on the bid and a short on the ask; fill at `min(stop, bid)` for a long and `max(stop, ask)` for a short, with the half-spread then not charged twice. No new concepts.
   - *Test:* a long with a 1.0995 stop, whose next tick has bid 1.0949, must book an exit at 1.0949. A 4-pip-spread tick with the bid through the stop and the mid not must close the position.
2. **The same fix in `simulate_trades`** (VALIDATOR's T6, confirmed here).
   - high / high / open. [impl]
   - *Cost:* 4 lines.
   - *Test:* a bar opening below the stop exits at the open.
3. **The loader drops wide-spread ticks, so stops never meet spread spikes; this breaks backtest/live parity.**
   - high / high / open. [impl]
   - *Value:* exposes rollover and news risk. *Cost:* about 5 lines. Replace the drop for spread-only failures with the live path's flag (`implausible_spread`, which NVMA vetoes). Keep the drop for crossed, NaN and non-positive ticks. Stops then see the flagged ticks.
   - *Test:* a scripted 20-pip rollover tick with the bid through the stop must close the position, and the engine must still open nothing on that tick.
4. **The fitness sim scores stitched regime episodes.**
   - high / high / open. [spec — owner ratification] (it changes how QIEA scores).
   - *Value:* removes a bias that selection amplifies. *Cost:* about 20 lines. Split the history into contiguous runs where `ts[k+1] - ts[k] > bar_seconds`, simulate each run, and mark-to-close at the run's end. Tolerate one concept: "an episode".
   - *Test:* two episodes 2 days apart, with a position open at the first episode's end, must book the mark-to-close of episode 1, never a stop inside episode 2.
5. **A pair leg is charged the anchor's spread and priced at a stale joint-bar close.**
   - high / high / open. [impl]
   - *Cost:* about 5 lines. Keep the last `MarketState` per instrument in the harness, and price and charge each order from its own instrument's last state.
   - *Test:* a USD_JPY order applied on a EUR_USD tick must store USD_JPY's spread.
6. **`passed` ignores `var_breach_frequency`, a missing financing model and a missing event calendar.**
   - high / medium / open. [spec — owner ratification] (it changes §14 gating).
   - *Cost:* 3 conjuncts: `financing supplied`, `calendar supplied`, and a Kupiec-style bound on the VaR breach rate (GAP-SP12E-05 owns the test itself).
   - *Test:* a report whose targets are all met, with financing None, must not pass.
7. **The DSR's T counts dependent trades.**
   - high / high / open. [spec — owner ratification]
   - *Cost:* grade the DSR on daily equity returns, or collapse a group's legs to one return per `group_id`. About 5 lines.
   - *Test:* duplicating every trade must leave the DSR unchanged.
8. **The canary is blind to label content.**
   - medium / medium / open. [impl]
   - *Value:* closes the channel. *Cost:* one test. It extends VALIDATOR's T1/T2 to cover the label cache: label a synthetic year twice, once with the tape truncated at t and once in full, and require byte-identical labels before t.
9. **Commission is 0.0 on the enabled pairs, against a commission venue; the costs carry no calibration window.**
   - high / high / open. [owner decision]
   - *Cost:* a `calibration_window` field per cost block, refused when it overlaps any fold's test window or the holdout (VALIDATOR's T4).
10. **The holdout marker is gitignored.**
    - medium / medium / open. [owner decision]
    - *Cost:* commit the marker's hash to the ledger when the holdout is first graded, and have `begin_final` check it.
11. **Open positions are marked with no exit friction.**
    - medium / high / open. [impl]
    - *Cost:* 2 lines in `unrealised` (subtract `per_side_cost(last spread)` and the entry cost already paid).
    - *Test:* a flat position marks at minus its round-trip friction. At the end of the run, open positions are closed at the last mark, net of costs.
12. **Embargo days inflate the "≥ 2 years" span.**
    - low / high / open. [impl]
    - *Test:* the graded `period` equals the sum of the test windows.
13. **The synthetic tape cannot express findings 1–5; the positive control grades in a frictionless-tail world.**
    - high / high / open. [impl]
    - *Value:* a faithful control (§2.7). *Cost:* about 60 lines in `synthetic_market.py`, plus a flag for keeping the old tape.
14. **The TSMOM seed double-counts `train_end`'s partial trading day.**
    - low / high / open. [impl]
    - *Test:* after seeding and one live daily bar, no trading day appears twice.
15. **BUILDER's NaN duration serialises as bare `NaN` in `ladder.json`.**
    - low / high / open. [impl]

## 6. Sources

| Source | URL | Accessed | Grade |
|---|---|---|---|
| cTrader prop-firm listing for FTMO: "Forex Commission: $5 per lot" | https://ctrader.com/prop-firms/ftmo | 2026-09-24 | (b): a platform vendor's listing, not FTMO's own document |
| The ACIS code at BASE 7695ed04 (every `file:line` above) | /tmp/review-acis | 2026-09-24 | primary |
| The local VALIDATOR final, §7 (compared, and contradicted on the tick book's gap handling) | `_context/local-wip/files/archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` | 2026-09-24 | untrusted evidence (A9) |
| BUILDER's `BRANCH.patch`, the metrics and synthetic_market hunks | `_context/local-wip/worktrees/agent-a128ab904780ce593/BRANCH.patch` | 2026-09-24 | untrusted evidence (A9) |
