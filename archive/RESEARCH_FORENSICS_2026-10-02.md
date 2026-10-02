# RESEARCH — FORENSICS: why the engine has lost, mechanism by mechanism (2026-10-02)

- **Who asked.** The owner, 2026-10-02: *"deduce what might be causing our engine to be losing thus far ... could it be that our internal mechanisms like QIEA, NVMA, e.t.c are causing the friction that is derailing the win rate? ... tight on losing but not stuck without making trades and making money."*
- **Status.** This is a finder's report (constitution A5). It is evidence for the lead to verify (A6), never an instruction (A9). Every number below was produced by a probe the lead can re-run (§8). Nothing here touches a guardrail, the spec, the ledger or the code. I launched no agents and used no web access.
- **Data law.** Everything is synthetic: the C-BT-12 tick generator (`tests/backtest/synthetic_market.py`), three stronger diagnostic variants of it, and the R1 lab (`tests/backtest/lab_*.py`). No real candle was read for P&L or for anything else (`REAL_LOOKS_OPEN = False` respected).
- **Where it ran.** acis-compute-1, checkout `/opt/acis/research-forensics` at `de96a75`, at most 4 worker processes, about 2 h 20 min of wall time (16:47–19:08 UTC). The server was left idle. A copy of every output except `trades.jsonl` is in the session scratchpad `research/forensics/forensics_bundle.tgz`. The run directories are `/opt/acis/research-forensics/data/forensics/runs/<name>/`, each holding `report.json`, `summary.json`, `trades.jsonl` and `analysis.json`.

---

## 0. The answer in plain language (for the owner)

**Short answer.** Yes, the engine's own mechanisms produced the loss. It is not "friction from QIEA and NVMA" in the sense of fees. The loss comes from one design choice that every other mechanism then amplified or failed to fix: **the legacy engine decides on one-minute bars and exits on stops and targets one to five one-minute ATRs away, so it holds a position for about 6–9 minutes.**

**What the trades actually do.** On every synthetic market I tested, the engine's entries point the right way slightly more often than a coin:
- TREND is right 52–55% of the time and BREAKOUT 53–60% (on the planted and the beatable intraday markets);
- the best possible rule that sees only the past reaches 54% on the planted market and 62% on a market three times stronger.

So the entries are not the problem. The problem is the hold. In 6–9 minutes a planted trend moves about 0.01–0.1 basis points (bps), while every round trip costs 0.79 bps in declared costs plus about 0.17 bps of fill asymmetry in the tick book. **Each trade pays roughly 1 bp to earn roughly 0.01–0.1 bp.** That is the whole loss of the intraday modules, measured trade by trade against the known truth.

**How the other mechanisms enter.**
- **NVMA does not pick good trades.** Its direction is right 51% of the time against the planted truth. Its label changes on 45% of its 2-minute classifications. It blocks trading 39–46% of the time, 27.5 points of it from a quirk of the synthetic tape.
- **NVMA's real effect is to ration losses.** With its gate and routing switched off, the engine traded 6.8× more and lost 7.2× more.
- **QIEA does the same.** It chooses parameters on holdouts of about 7 trades, and its winners change wildly from fold to fold. It earns nothing per trade over fixed textbook parameters (−$0.0102 against −$0.0099 a trade). It only trades 40–67% less, because regimes without a champion are vetoed.
- **The Governor's factor sizing** shrinks each position 4–18× through a "regime stability" number that has zero correlation with the trade's outcome. It scales the loss but neither causes nor prevents it, with one exception: when modules differ in edge, the factors move money toward the WRONG module. On the best repaired run they turn a constant-size book that earns into one that loses.
- **TSMOM** was 81% of the loss in the published verdict, yet it has no edge on these markets by construction: they plant only 1–4 hour trends, and it votes on 63–252-day returns. The engine-free TSMOM rule loses −$24 to −$42 on the very same price path. So its −$57 is mostly a bad draw of the random path (planted and null share their noise), not an engine bug. Its structural damage is real all the same:
  - it holds 48-hour positions that dominate the book's variance;
  - it locks instruments, cutting the other modules' trades by 69%;
  - it makes the Governor zero 31,680 orders at weekend bans.

**Two findings change how the record should be read.**
1. **The planted "positive control" the engine failed cannot be passed by any rule that sees only the past.** A near-optimal Bayesian detector nets a Sharpe of 0.15–0.34 there, against −0.38 to −0.08 on the null. "The engine fails its own positive control" was never a fair test of the engine; the oracle control only proves that the grader works.
2. **On a market where a good causal rule nets a Sharpe of about 4.5, the legacy engine still loses.**
   - With its ATR brackets: Sharpe −10.0, gross −$3.96.
   - Removing the take-profit and widening the stop, so trades end on the opposite signal: gross turns to +$5.52, the trend drift captured per trade rises 15–19×, the Sharpe rises to −1.15, and BREAKOUT turns net-profitable.
   - Removing MEAN_REVERSION as well: gross +$9.08, Sharpe −0.67. The same trades at a constant size net **+$15.23**.

   **The bracket exit is where an edge was being converted into friction.** It is not the whole story, though. On a market whose trends last 1–4 days, the same fix does not help, because a one-minute signal cannot see a multi-day trend (direction 48–50%). That is a decision-clock problem, and R1.6's daily D1 is the right tool for it.

**For the new R1.6 path.** It drops nearly all of this: TSMOM-on-ticks, QIEA, the factor sizing, the brackets and the 48-hour cap. Its costs are about 0.09% a year in the lab. **It still inherits one legacy mechanism:** every entry at the 08:00 New York slot must pass NVMA's tick-level "tradeable" and confidence checks. On the R1 lab's own intraday tape, that refuses **22.7% of slot entries** (16.6% low confidence, 6.1% illiquid). A refused entry loses the day. RSIM and the B0(d) parity test model none of it, so the demo's forward record will drift from the graded book.

**"Tight on losing but not stuck" therefore means three things:**
- take risk control from sizing (vol target, caps) and from trading only when the expected move over the hold beats the cost, not from tight stops on one-minute noise;
- gate on data integrity, not on a label that carries no information;
- never pay a round trip for a hold that cannot earn it.

---

## 1. Method

| What | How (probe in §8) |
|---|---|
| **Replication** | The 2026-09-29 ladder's 1x rung, reproduced exactly at `de96a75`. **1,690 trades, net −70.84, friction 15.65, direction −55.19: identical to GAP-P12D-49's exact split.** Then one mechanism changed at a time. |
| **Per-trade truth** | The synthetic path and its episode schedule are deterministic. So every closed trade is split exactly into the planted DRIFT it captured over its hold, the NOISE, the book's fill effects and the declared C8 friction, and its entry side is scored against the episode in force. |
| **Ceilings** | A near-optimal causal detector, a two-state Bayes filter with the market's own switching hazard, graded with hysteresis policies at the declared cost. It answers "what could ANY non-anticipating rule earn here?" |
| **Ablations** | Monkeypatch switches in a probe process; nothing in the repo is edited. TSMOM off; MEAN_REVERSION off; QIEA replaced by one fixed ParamSet for every regime (gene-range centres: EMA 20/100, RSI 14 70/30, SL 2 ATR, TP 3 ATR, lookback 20, breakout 1.0, z 2.0); NVMA's tradeability vetoes and its module routing off (`nvma_off`); no take-profit with a stop 5× wider (`notp`, so exits come from the opposite signal or the 48 h hold). |
| **Offline counterfactuals** | Exact given the trade set: constant $1,000 notional instead of the factor product, and fixed-horizon exits (15 m / 1 h / 4 h / 24 h at the mid, both sides' cost). Both ignore the knock-on effect on later entries, which is stated where it matters. |

Markets (all EUR_USD + USD_JPY, seed 7, 20-second ticks, `daily_vol` 0.005):

| name | what | oracle Sharpe | episodes | folds | graded span |
|---|---|---|---|---|---|
| **p10** | THE C-BT-12 planted market of GAP-P12D-49/31 | 10 | 1–4 h | 25 × 30 d | 2014-03-07..2016-09-16 (2.53 y) |
| **m30** | diagnostic: a beatable intraday trend | 30 | 1–4 h | 12 × 30 d | 2014-03-07..2015-05-22 (1.2 y) |
| **l10** | diagnostic: multi-day trends | 10 | 24–96 h | 12 × 30 d | same |

**Read the Sharpes with care.** A book of 6–9-minute trades has very little daily P&L variance, so a steady friction drag shows up as a huge negative Sharpe (−10, −20). Compare net, gross and per-trade numbers, not Sharpe magnitudes, across rows.

---

## 2. Findings with numbers

### F1. The C-BT-12 planted market is beyond every causal rule, net of cost

Probe `ceiling.py`. These are the 985-day paths the ladder graded (EUR_USD / USD_JPY).

| | planted | null (same noise) |
|---|---|---|
| oracle, episode in force, frictionless | **9.62 / 9.50** | 0 / −0.38 |
| Bayes-filter direction accuracy vs truth | **54.1% / 54.2%** | 49.7% / 49.8% |
| filter, always in, frictionless Sharpe | 1.41 / 1.34 | 0.63 / 1.07 (noise level) |
| **best filter policy NET of the 0.76 bps round trip** (EUR_USD's declared C8 cost; the book's measured average is 0.79) | **0.15 / 0.34** (hysteresis b=0.5, ~21.6 h holds, 1.2–1.8 bps gross per round trip) | −0.38 / −0.08 |
| fixed-horizon momentum (sign of the last block, held one block), 15 min–8 h | net negative at every hold; at 24 h −1.15 / +0.64 | net negative; at 24 h −1.21 / +0.29 (noise) |

- **The arithmetic.** The planted drift is 0.0096 σ per 20-second step. An episode's drift-to-noise ratio is about 0.2, so no detector can be sure of the sign before the episode ends.
- **The consequence.** §14 asks for a Sharpe of 1.5. The best causal rule nets about 0.2, within one standard error of the null on a single path.
- **What stays true and what falls.** The oracle control (GAP-P12D-37) still proves the grader. But "planted must PASS" is unattainable for any engine on this market, so GAP-P12D-31's engine verdict measures friction and variance, not the ability to capture a trend.

Stronger markets, same probe (best causal net Sharpe; filter accuracy):
- oracle 20: 1.51 (58%);
- **oracle 30: 4.51 / 4.67 (62.5%, holds 1.3–4.9 h)**;
- oracle 40: 7.9–8.5;
- **oracle 10 with 24–96 h episodes: 3.69 / 4.64 (69%, holds 18–24 h)**.

These two (bolded) are the diagnostic markets m30 and l10.

### F2. Replication and the whole ablation table (p10, the ladder's market)

| run | change from the shipped legacy engine | trades | net $ | friction $ | gross $ | Sharpe |
|---|---|---|---|---|---|---|
| `p10_base` (V0) | none (the ladder's 1x rung, reproduced) | 1,690 | −70.84 | 15.65 | −55.19 | −1.92 |
| `p10_tsoff` (V1) | TSMOM off | 3,975 | −40.38 | 36.37 | −4.00 | −5.78 |
| `p10_tsoff_fixed` (V2) | + QIEA → fixed params | 6,690 | −65.95 | 52.51 | −13.43 | −9.84 |
| `p10_tsoff_fixed_nvmaoff` (V3) | + NVMA gate and routing off | 45,485 | −477.45 | 405.07 | −72.38 | −20.40 |
| `p10_repaired` (V4) | TSMOM off, MR off, fixed params, `notp` exits | 4,434 | −56.25 | 35.69 | −20.56 | −2.08 |

The same on the beatable m30 market (best causal net Sharpe about 4.5):

| run | change | trades | net $ | friction $ | gross $ | Sharpe |
|---|---|---|---|---|---|---|
| `m30_tsoff` | TSMOM off, QIEA on | 1,081 | −9.59 | 9.45 | −0.14 | −4.38 |
| `m30_tsoff_fixed` | TSMOM off, fixed params | 3,269 | −30.13 | 26.17 | −3.96 | −10.05 |
| `m30_tsoff_fixed_notp` | + `notp` exits | 2,330 | −13.07 | 18.59 | **+5.52** | −1.15 |
| `m30_repaired` | + MR off | 2,091 | −8.01 | 17.09 | **+9.08** | −0.67 |

And on l10 (1–4-day trends):
- `l10_tsoff_fixed`: 3,333 trades, net −32.03, friction 26.49, gross −5.54, Sharpe −10.64;
- `l10_tsoff_fixed_notp`: 2,430 trades, net −28.66, friction 19.23, gross −9.43, Sharpe −2.22.

**V4 on p10 is the control for the repairs:** p10 has nothing to capture (F1), so the repaired engine must still lose there, and it does: −$56.25.
- Signal exits raise the drift captured per TREND trade from 0.0075 to 0.218 bps (29×), and per BREAKOUT trade to 0.35 bps.
- That is still a quarter to a third of the 0.79 bps of friction.
- BREAKOUT is about break-even: gross +$4.17, net −$0.33. TREND loses −$55.93.
- The repairs therefore do not manufacture P&L on a market with none, which is the honest check that the m30 gains are captured drift, not an artifact.

### F3. AGON's intraday modules: right side slightly more often than chance, but a hold too short to earn the cost

Per trade, in bps of notional (probe `analyse.py`). "Gross at the exit mid" is the trade valued at the true mid when it closed: on a martingale it equals the drift captured, and it does.

| run · module | n | side right at entry | drift captured | gross at exit mid (±1 se) | book's target forfeit | declared C8 friction | net | median hold |
|---|---|---|---|---|---|---|---|---|
| p10 V2 · TREND | 4,005 | 52.2% | +0.0075 | +0.005 ± 0.060 | −0.175 | −0.788 | ≈ −0.96 | 6.3 min |
| p10 V2 · BREAKOUT | 2,126 | 54.4% | +0.0195 | −0.025 ± 0.086 | −0.175 | −0.788 | ≈ −0.99 | 6.7 min |
| p10 V2 · MEAN_REV | 559 | 41.0% | −0.025 | −0.033 ± 0.163 | −0.165 | −0.788 | ≈ −0.99 | 6.7 min |
| p10 V1 · TREND (QIEA) | 2,514 | 52.2% | +0.013 | +0.137 ± 0.092 | −0.197 | −0.789 | ≈ −0.85 | 9.3 min |
| m30 · TREND | 1,882 | 54.8% | +0.054 | +0.089 ± 0.076 | −0.154 | −0.790 | ≈ −0.86 | 6.3 min |
| m30 · BREAKOUT | 1,091 | **59.7%** | +0.110 | +0.003 ± 0.104 | −0.155 | −0.790 | ≈ −0.94 | 6.3 min |
| m30 `notp` · TREND | 1,397 | 54.1% | **+1.026** | +0.60 ± 0.47 | 0 | −0.790 | ≈ −0.19 | 107 min |
| m30 `notp` · BREAKOUT | 701 | 57.9% | **+1.600** | +1.00 ± 0.72 | 0 | −0.790 | ≈ +0.21 | 128 min |
| l10 `notp` · TREND | 1,513 | 48.4% | +0.554 | −0.41 ± 0.44 | 0 | −0.804 | ≈ −1.21 | 94 min |

What the table says:
1. **Entry direction is not the defect.** BREAKOUT reaches 54% on p10, where the causal optimum is 54%, and 60% on m30, where it is 62.5%.
2. **The hold is.** A 6–9-minute hold captures 0.01–0.11 bps of drift against 0.79 bps of declared friction: 1/7 to 1/100 of the cost. GAP-P12D-49's "short-hold modules friction-bound" is confirmed and now measured per trade.
3. **The tick book adds about 0.15–0.21 bps a bracket trade** (the "target forfeit"). On the 20-second grid a target fills at its level while the mid has already moved past it (mean 0.43 bps per target hit), and a stop fills at the mid beyond it (mean 0.43 bps of overshoot per stop). Against fair value at the exit tick, the target side is the bias. This is a harness-fidelity effect of the synthetic 20 s tape. Real sub-second ticks would show much less of it, so on synthetic runs it adds about 20–25% to the declared cost of every short bracket trade.
4. **No exit rescues the p10 entries** (offline, same entries; ± is 1 se). TREND holding 15 m / 1 h / 4 h / 24 h nets −0.78 ± 0.08, −0.90 ± 0.16, −0.68 ± 0.33 and −0.66 ± 0.78 bps. BREAKOUT nets −0.71, −0.55, −0.82 and −0.94. On p10 nothing can earn (F1).

### F4. Exits: the ATR bracket is where a capturable edge becomes friction

The exits are ATR(1-minute) multiples: SL 1.0–3.5 and TP 1.5–5.0 (`GENE_SPECS`).
- **What one ATR is.** On the 20 s tape a one-minute ATR is about 1.5–2 bps, so the stop distance IS the holding period: a median of 6–9 minutes. That is the first-passage time of a random walk to about ±3 bps.
- **What happens per losing trade.** It loses its 2-ATR stop (about 3–4 bps, approximate), plus about 0.43 bps of overshoot (measured), plus 0.79 bps of friction (declared). **About 35% on top of the stop distance itself.**
- **On m30 (beatable).** `notp` (no TP, stop 5× wider) moves the median hold from 6 to 107–128 minutes. It raises the drift captured per trade 19× (TREND) and 15× (BREAKOUT), turns gross from −$3.96 to +$5.52, the Sharpe from −10.05 to −1.15 and PF from 0.555 to 0.914, and makes BREAKOUT net-positive (+$1.34). MEAN_REVERSION still loses: −$4.37, with its side right at entry only 31–33% of the time, a bet against the drift.
- **Removing MEAN_REVERSION as well (`m30_repaired`)** gives 2,091 trades, gross +$9.08, net −$8.01, Sharpe −0.67, PF 0.943. Per trade, TREND makes +0.77 ± 0.49 bps gross and BREAKOUT +1.05 ± 0.77, against 0.79 of friction. The near-optimal causal rule on the same market makes 2.1–3.5 bps gross per round trip at similar 1.3–4.9 h holds (F1). The repaired legacy entries therefore earn about a third of what is available, which is why it still nets slightly negative where a good rule nets a Sharpe of about 4.5. At constant size this same run nets **+$15.23** (F7).
- **On l10 (1–4-day trends) the same fix does not help.** Gross goes −5.54 → −9.43, because the 1-minute entry/exit signals are right only 48–50% of the time against a multi-day trend; drift captured rises to 0.55 bps a trade, but the noise swamps it. **When the trend lives on a slower clock than the signal, longer exits cannot fix a one-minute signal.** That is the case for daily decisions (R1.6) over patching the legacy stack.

### F5. NVMA: a rationing gate, not a selector

From the instrumented runs on the 930,180 two-minute classifications of p10. Probe `frun.py` counts every `NVMAEngine.classify`.
- **Untradeable 39.4% of the time (V2), 46.1% with QIEA (V0/V1):**
  - ILLIQUID 27.5%;
  - LOW_CONFIDENCE veto 11.9%;
  - NO_PARAMS_FOR_REGIME 10.5% of classifications in V0/V1 (31 champions over 25 folds × 9 regimes);
  - warming 108 classifications.
- **The labels are unstable.** REGIME_SHIFT fired 415,094 times: the label changes on 44.6% of classifications, about every 4–5 minutes against 1–4 h episodes.
- **The label carries no direction.** `trend_direction` agrees with the planted episode 51.3% of the time (213,957 / 416,885), against the filter's 54%. On m30 it agrees 54.4% (107,938 / 198,413), against 62.5% possible. So GAP-P12D-39's "71–78%" (old oracle-157 market) does not hold at realistic strength.
- **Switching NVMA's gate and routing off (V3)** multiplies trades 6.8× and friction 7.7×, and the loss 7.2× (net −65.95 → −477.45). With routing off, BREAKOUT fires in every regime: 39,580 trades. **What NVMA does for this engine is throttle how often it pays a round trip.** It does not pick better trades: per-trade net is about the same with and without it.
- **The ILLIQUID quirk is an artifact of the synthetic tape, not of the market:**
  - `SyntheticMarket` quotes a spread exactly proportional to the mid (`spread_frac × mid`);
  - NVMA calls a state ILLIQUID when `spread − session_median > 2 × pstdev(window spreads)`;
  - with a proportional spread that reduces to "the mid is more than 2 window-σ above its session median", which is an UP-MOVE detector;
  - the result is that 27.5% of the tape is blocked, up-trends only (STRONG_TREND_UP 139,343 classifications against DOWN 178,283; WEAK UP 44,422 against DOWN 50,604);
  - on the R1 lab tape, with an independent spread, ILLIQUID falls to 6.1% (F9).

  It censors exactly the up-episodes the positive control plants, and it biases every synthetic engine run made on that tape.

### F6. QIEA: selection on noise; it trades less, not better

- **From the ladder's own evolution records** (`rung_1x.json`, 25 folds):
  - 450 evolutions; 81 passed the holdout (18%); 31 champions after the plateau law; 29 promoted;
  - the holdout gate decides on a **median of 7 trades** (73% of decisions on fewer than 10);
  - **winners are unstable:** STRONG_TREND_UP's 8 promoted champions span ema_fast 23–46 and ema_slow 108–197;
  - **about 10 of the 29 promoted champions sit exactly on the repair boundary TP = SL + 0.1.** Selection pushes toward TP ≤ SL, the tight-target / wide-stop geometry that the fitness's 0.20 win-rate weight rewards (GAP-P12D-32's claim, now seen in the champions).
- **QIEA against fixed textbook parameters** (TSMOM off):
  - p10: 3,975 against 6,690 trades, net −40.38 against −65.95. **Per trade: −$0.0102 against −$0.0099.** The gross at the exit mid, TREND, differs by +0.13 ± 0.11 bps: not significant.
  - m30: 1,081 against 3,269 trades, net −9.59 against −30.13. Per trade: −$0.0089 against −$0.0092.
  - **QIEA's whole effect is fewer trades through the NO_PARAMS veto.**
- **QIEA did not find m30's capturable edge either.** Its fitness scores a dual-EMA rule with `max_holding_periods` of 1–48 ONE-MINUTE bars and brackets at fixed levels, so it can only select minute-scale holds. Those cannot capture any edge (F3), while the engine runs a 48 h cap (GAP-P12D-32's 60× horizon mismatch).
- **A further mismatch, new here.** The fitness fills brackets at their levels intrabar (`fitness.trade_path`), while the tick book forfeits about 0.17 bps a target trade (F3). Selection scores a slightly cheaper world than the one graded, the GAP-P12D-36 class.

### F7. The Governor's factor sizing: noise weights that can move size to the wrong module

- **The product.** Size = $1,000 × conviction × liquidity (0.8 on synthetic ticks) × correlation × regime_f × marginal_alpha (pinned 1.0 on every one of 1,717,512 sizings in V0) × vol_norm × taper.
- **regime_f, stability × confidence, is the dominant shrinker.** Its median by module:
  - TREND 0.25–0.30 (p10–p90 0.07–0.45);
  - BREAKOUT 0.056–0.098;
  - MEAN_REVERSION 0.115.

  So the mean notional is $40–160 on a $10,000 book.
- **Within a module it carries no information:** corr(notional, gross return) is within ±0.05 for every module with more than 500 trades, in every run.
- **Constant $1,000 notional, same trades** (offline; exact for P&L, since size changes no entry or exit here): p10 V2 gives −$649 against −$65.95 actual, the same per-dollar result scaled ~10×. On an edgeless book the factors only make it smaller.
- **Across modules they can do harm.** regime_f gives BREAKOUT a median of 0.058 and TREND 0.30, because BREAKOUT_IMMINENT labels are short-lived and low-confidence. On `m30_repaired`, where BREAKOUT is the module with the edge:
  - the factor product books **−$8.01** (−0.37 bps per dollar of notional; BREAKOUT +$1.18, TREND −$9.19);
  - the same trades at a constant $1,000 book **+$15.23** (+0.07 bps per dollar; BREAKOUT +$18.04, TREND −$2.81).

  **The sizing turned a book that earns into one that loses**, by underweighting the module with the edge 2.3× relative to the one without (mean notional $42 against $133). This is GAP-P12D-61's sizing finding seen from the inside: the factors are not a risk control, they are an unvalidated reallocation.

### F8. TSMOM: no edge by construction here; a bad path, plus real structural damage

- **The baseline TSMOM book** (V0, `analyse.py`): 446 trades, gross −$52.93, mean notional $127.6. Exits: 399 at the 48 h max hold (−$34.26) and 47 by reversal, its own vote flipping (−$23.19).
- **Per trade.** Drift captured −0.07 bps: zero, as it must be for a 63–252-day vote on 1–4 h episodes. Noise −8.9 ± 3.0 bps.
- **A sign test over its 69 same-direction stretches** gives z = −3.25.
- **Is it the engine or the path?** I ran the engine-free rule on the exact same path (`tsmom_path.py`): the vote at the 21:00 UTC close, 2-weekday holds, from TSMOM's first live day 2015-02-03.
  - **On planted it loses −$41.95 (one 2-day phase) and −$23.93 (the other).**
  - On the common-noise null it loses −$31.02 and −$21.47.
  - Across 400 fresh seeds of the same model (`tsmom_null.py`), the rule's total is −$2.2 ± $13.4 on planted and −$1.8 ± $13.3 on null (Sharpe −0.12 ± 0.76).

  **So this path is a roughly 2–3σ bad draw for TSMOM's rule, with or without the engine.** The engine's extra −$11 to −$29 sits inside the 18-dollar spread between the two phases.
- **What follows.** "TSMOM is 81% of the loss and 92% direction" (GAP-P12D-49) is a correct accounting of THIS run. It is not evidence that TSMOM's rule or its implementation is broken, nor that TSMOM would lose on real data. It is a zero-edge, maximum-variance bet on a market built to contain no edge at its horizon. (A caution for the lead: I report the z = −3.25 honestly. A 2–3σ path is unusual, but not rare enough to rule out once you count that this run was singled out because it lost.)
- **Its structural damage is a mechanism, and it is measured:**
  - **It locks instruments.** TSMOM emits on every tradeable tick, so any opposite signal is discarded with it (the §2 rule) and same-side signals are de-duplicated. With TSMOM on, the other modules trade 1,244 times; with it off, 3,975 (−69%).
  - **It is the order firehose.** In V0, 1,749,192 signals were emitted and sized, 1,717,512 of them non-zero, and 31,680 orders were zeroed by the weekend ban, against 312 without TSMOM.
  - **It owns the variance.** Its 48 h holds at full volatility set the book's daily variance, so the engine's Sharpe is mostly TSMOM's path luck.
  - **The promotion freeze is gone.** It was cause 5 in the 2026-09-16 report: PARAM_PROMOTION_STALLED is 130 here, against 11,638 then, and 29 of 31 champions promoted.

### F9. R1.6's target path on the synthetic lab: what it inherits and what is new

**Not inherited, by construction (verified in the code):**
- R6-3 keeps the legacy AGON modules, the QIEA champion and the max-hold exit off the universe (`core/runtime/engine.py`);
- sizing is Carver's average position and band (`core/governor/target.py`), not the factor product;
- there is no take-profit, and the stop is 10 × the daily ATR;
- decisions are daily.

The R1 lab's RSIM run (`gs://…/runs/2026-10-01-r1-lab-rsim/summary.json`, 1,000 seeds) puts D1's costs at **0.09% a year** and its null net Sharpe at −0.03. D1 converts planted trends of 0.5 / 1.0 (half-life 40) into a net 0.29 / 1.16. Friction is no longer the story.

**Inherited, and NOT modelled by RSIM or B0(d): NVMA's tick-level gate on every entry.**
- **The mechanism.**
  - `target_gate._entry_size` calls `gov.guards.check(instrument, portfolio, regime, now)`.
  - Its first regime clauses refuse when `not regime.tradeable` ("veto") and when `regime.confidence < 0.55` ("low_confidence").
  - The runtime classifies every universe instrument on ticks every 120 s, with NO_PARAMS neutralised (`wiring.py`), so LOW_CONFIDENCE, ILLIQUID, SPREAD_VETO, DEAD_MARKET, STALE and warming all still bite.
  - ACIS-05 §6.4 ("an increase is an ENTRY and meets every entry gate") makes this spec-mandated.
- **The measurement** (`slot_gate.py`: production `MarketStateFactory` + `NVMAEngine` at the 120 s cycle, on the R1 lab's intraday tape with its hour-shaped spreads, rollover spikes and quote thinning; 2 instruments, 320 weekdays, 638 slots). **22.7% of 08:00 New York slots would refuse an entry: LOW_CONFIDENCE 16.6%, ILLIQUID 6.1%.** Over all classifications the refusal share is 20.8%. On the C-BT-12 tape, with its proportional-spread artifact, 39.4% of all classifications are refusals (F5).
- **The consequence.**
  - `target_loop.execute` pops the pending target, so a refused entry is not retried until the next 17:00 decision, which costs at least a day.
  - A refused flip leaves the book flat instead of reversed.
  - Exits are never refused (a reduction passes no guard), so the bias is toward being flat.
- **Still true of the working tree.** At report time the working tree held someone else's uncommitted R1.6 changes to `core/runtime/target_loop.py`, which I did not review. They leave this path as it was: `core/governor/` and `core/regime/` are unchanged, and `execute` still pops the pending target and passes `regime=e.regime_of(instrument)` to the gate.
- **Why the tests miss it.** B0(d) (`test_b0d_the_engines_decisions_equal_rsims_practice_book_on_a_lab_tape`) compares `decide()`'s targets and sets `held = target` every day. It never passes through the gate, so this departure is invisible to it.
- **What it means for the evidence.** The demo's forward record (master §5 D-a, the stage-D evidence) will measure a book that is flat on about 1 in 5 entry days where RSIM's is not. P&L-blind measurement on real ticks is owed (§6, question 1).

**New mechanisms, by design, that refuse trades:**
- **The one-lot practice cap and min-lot rounding.**
  - J1 (`runs/2026-10-02-j1`): at $10k / 20%, the demo's sizing (GAP-P12D-142), the book holds a position on 45–51% of days.
  - Stage A's pass rate on a trend of 0.5 (h40) falls from 0.192 (no lot) to 0.162, and for h160 from 0.641 to 0.555.
  - Rounding toward zero AFTER the band creates a crude hysteresis. My own illustrative arithmetic (EUR_USD, daily vol about 0.6%, weight 1/13, IDM 1.5, a 1,000-unit lot): enter above |forecast| ≈ 4.6, exit below about 3.5. That is acceptable for plumbing, but the forward record grades sign accuracy, not sizing.
- **No same-day re-entry after a disaster stop or a flatten (R6-2), and a slot missed by more than 300 s is skipped, never caught up.** Each costs a day. Both are rare at a 10 × ATR stop.
- **Stale rates for more than 10 days** give no target (R6-1). If `acis-macro.timer` fails, the path quietly stops opening; it keeps positions and does not churn, but it is a "stuck" route to monitor.
- **Not binding at one lot, but binding the day it is sized up:**
  - the per-instrument 1% open-loss halt clears only by human resume (GAP-P12D-139), a starvation path on multi-week holds;
  - weekend or holiday flattening on a no-weekend-holding prop rulebook would churn a weeks-long D1 book. The demo allows weekend holding; check E8's rule at purchase.

---

## 3. "Tight on losing, but not stuck": refusals and losses ranked by expected-value cost

**Legacy engine** (p10, TSMOM off, V2; per trade and over 6,690 trades):

| rank | source | EV cost | evidence |
|---|---|---|---|
| 1 | Declared C8 friction on 6–9 min holds | −0.79 bps a trade; **−$52.5, 80% of the loss** | F3, V2 |
| 2 | The tick book's bracket asymmetry on the 20 s grid (target forfeit) | −0.175 bps a trade; about −$11.7, 18% | F3 (harness fidelity, synthetic only) |
| 3 | Trade rate | each extra trade costs about $0.01 with zero edge; NVMA off ×6.8 trades = ×7.2 loss | F5, V3 |
| 4 | Drift captured (what the entries earn) | +0.0075 to +0.02 bps a trade; about +$0.45 | F3 |
| — | TSMOM (when on) | EV ≈ 0 by construction, dominant variance; −$52.93 realised (path luck) | F8 |
| — | Factor sizing | EV-neutral within a module (corr ≈ 0); scales everything ~6–25× down; across modules it can favour the losing one (F7) | F7 |
| — | NVMA's refusals | opportunity cost ≈ 0 on p10 (nothing to capture); on m30 it vetoed 39.7% of a capturable market (28.1 points of it the ILLIQUID artifact) | F5 |

**Per losing trade.** It loses its stop (about 3–4 bps), plus about 0.43 bps of overshoot, plus 0.79 bps of friction. Costs are about 35% of the loss per losing trade because the stops are a few one-minute ATRs. On the D1 path, with a 10 × daily ATR stop (several percent), the same costs are well under 1% of the stop distance.

**Where the legacy engine refuses when it should trade.** On p10 there is nothing to refuse. On m30, NVMA blocks 28.1% (ILLIQUID artifact) + 11.6% (LOW_CONFIDENCE), and the QIEA engine's NO_PARAMS veto cuts trades a further 67%. The demo's one-champion library made it untradeable on about 92% of bars (GAP-P12D-129: WEAK_TREND_UP is about 8% of 2022–23's bars). None of these refusals selects better trades (F5, F6).

**R1.6 path, ranked:**
1. The NVMA gate at the slot: about 23% of entry days lost on the lab tape; not graded.
2. The one-lot cap and rounding: flat on about 50% of days at $10k/20%; graded (J1).
3. Stale inputs and missed slots: rare; operational.
4. Friction: about 0.09% a year; negligible.

---

## 4. Ranked changes: keep, change or remove each mechanism

Ordered by expected effect on "make money without being stuck or reckless". Each carries the experiment that would confirm it.
- **[spec]** needs owner ratification.
- **[impl]** is buildable under existing law.
- **[harness]** is test-side only.

| # | Mechanism | Verdict | Expected effect | Confirming experiment |
|---|---|---|---|---|
| 1 | NVMA's tradeability and confidence gate on the **target path's entries** | **CHANGE [spec]**: keep only data-integrity refusals (stale/warming state, spread blow-out against an absolute or rolling floor, macro event, closed market), drop LOW_CONFIDENCE and the label from D1 entries; OR model the gate in RSIM and B0(d) so the graded book equals the traded one | Recovers about 17% of entry days on the lab tape (the LOW_CONFIDENCE share), up to 23% if the ILLIQUID rule is also repaired, and restores RSIM ≡ engine at execution, not only at decision | (a) `slot_gate.py` on 20+ lab seeds and on the AWS server's REAL ticks, P&L-blind, at 08:00 NY; (b) extend B0(d) to run decisions through `target_orders` with the runtime's NVMA on a lab intraday tape and count `TARGET_ENTRY_ZERO` by reason |
| 2 | Legacy AGON intraday modules (TREND/BREAKOUT/MR/SCALP/PAIR on 1-minute bars) | **REMOVE from every money path [spec; already off the universe by R6-3]**; keep them out of any future universe | Removes about 100% of the legacy friction loss; per trade they earn 1/7–1/100 of their cost | Done: V1/V2 here; per-trade drift vs friction (F3) |
| 3 | ATR(1-minute) bracket exits (TP/SL genes) | **REMOVE [spec]**; if an intraday rule is ever revived, exit on the opposite signal with a far disaster stop | Drift captured ×15–19 on a beatable intraday market; gross −3.96 → +5.52 (m30), +9.08 with MR off; no false P&L on p10 (V4 still loses) | `m30_tsoff_fixed_notp` and `m30_repaired` against `m30_tsoff_fixed`; `p10_repaired` as the control (§2) |
| 4 | The one-minute decision clock for trend capture | **REMOVE** for multi-day trends (D1 replaces it) | On 1–4-day trends 1-minute signals are right 48–50% of the time; no exit fixes it | `l10_tsoff_fixed(_notp)`; the next step is D1 on l10's daily closes through RSIM |
| 5 | TSMOM on the tick loop | **REMOVE [spec; R6-3 on the universe]** (its R1 successor is MOP_12M / `tsmom_slow_v2` on the daily clock) | Removes the instrument lock (+69% other-module trades), the order firehose (31,680 weekend zeroes) and the dominant variance | V0 against V1; `tsmom_path.py` |
| 6 | QIEA per-regime evolution | **REMOVE [spec; R1-D4 already retires it]** | No per-trade gain over fixed parameters; selection on 7-trade holdouts; a third of champions at the TP = SL + 0.1 boundary | V1 against V2, `m30_tsoff` against `m30_tsoff_fixed`; the ladder's evolution records |
| 7 | Factor sizing (regime_f = stability × confidence, liquidity 0.8, pinned marginal alpha) | **REMOVE [spec]** from any path that sizes (D1 already sizes by Carver) | Within a module, EV-neutral, shrinking risk 4–18×; across modules it moved size away from the module with the edge (m30_repaired: +$15.23 at constant size against −$8.01 as sized) | Offline constant-size counterfactual (F7) |
| 8 | NVMA as router, label and parameter key | **DEMOTE [spec]** to a data-quality gate; at most a sizing weight after it proves information | Its label is about 51% directional and flips every ~4–5 min | Measure label information against the truth on the lab before any use (`frun.py` `dir_acc`) |
| 9 | The synthetic tick tape's proportional spread (`spread_frac × mid`) | **CHANGE [harness]**: an independent, noisy or constant-in-price spread (as the lab tape has), or a floor under NVMA's window spread σ | Removes a 27.5% up-move-only ILLIQUID censor from every synthetic engine run | Re-run `p10_tsoff_fixed` with a constant spread and compare the UP/DOWN label counts |
| 10 | The engine-level positive control (C-BT-12 planted at oracle 10, 1–4 h) | **CHANGE [harness/spec]**: grade an ENGINE against a market whose CAUSAL ceiling clears the bar (`ceiling.py` gives it), or grade engine runs relative to that ceiling; keep the oracle control for the grader | Ends a verdict that no engine could pass | `ceiling.py` per candidate market before any engine run |
| 11 | The 20 s tick book's bracket fills | **DECLARE [harness]**: about 0.17 bps a bracket trade of discrete-monitoring forfeit, synthetic only | Honest attribution of short-hold losses | `analyse.py`'s `target_forfeit_bps_per_trade` |
| 12 | The one-lot practice cap, min-lot rounding, R6-2 no re-entry, slot grace | **KEEP** (they are the demo's design) but record that the forward record grades sign, not size, and is flat about 50% of days at $10k/20% | — | J1 (done) |
| 13 | C8 one cost model, oracle control, look register, the exact friction split | **KEEP** | They are what made this forensic exact | — |

---

## 5. What the evidence does not show (limits)

- Every result is synthetic. **None says anything about edge on real markets**, about TSMOM's or D1's real-data performance, or about NVMA's refusal rate on real ticks.
- The m30, l10 and repaired runs grade 1.2 years over 12 folds; p10 grades 2.53 years over 25 folds. Per-trade standard errors are given; Sharpe gaps between short runs are not significant on their own.
- The offline exit and constant-size counterfactuals ignore the knock-on effect on later entries (one position per instrument). The in-engine `notp` runs include it.
- The `nvma_off` switch removes LOW_CONFIDENCE and NO_PARAMS and the routing. ILLIQUID, MACRO and warming stay, because they are data-integrity categories.
- `slot_gate.py` uses one lab seed and 638 slots: a binomial se of about 1.7 points on the 22.7%.
- The planted market's ILLIQUID quirk biases every run on that tape, including the published ones. I did not re-run with a corrected spread.

---

## 6. Open questions for the lead or the owner

1. **[measure, P&L-blind]** On REAL ticks (the AWS data server holds the tick set; this server has hourly candles only), what share of 08:00 New York instants would NVMA refuse per instrument, and for what reason? The answer decides whether item 1 is about 5% or about 40% of entry days.
2. **[owner]** Should D1's entries be gated by NVMA at all? ACIS-05 §6.4 says every entry meets every gate. The confidence veto was KEPT in the R1 triage (TODO.md lists it as an optional owner item); this is new evidence for that question.
3. **[lead]** Is the TSMOM stretch z of −3.25 entirely path luck? A second seed of the full V0 run (seed 8, ~80 min) would settle it. I did not spend the budget on it.
4. **[harness]** Should engine-level falsification move to a market with a stated causal ceiling? For example m30 (ceiling about 4.5), with the null at the same noise.

---

## 7. Evidence index (claims → source)

- GAP-P12D-49's exact 1x split reproduced: `runs/p10_base/report.json` (1,690 / −70.84 / 15.65 / −55.19).
- Per-trade decompositions: `runs/<name>/analysis.json` (from `analyse.py`), and the printed summaries `data/forensics/show_<name>.out`.
- Ceilings: `data/forensics/ceiling_{planted,null,o20,o30,o40,o10long}.json`.
- TSMOM path and null: `data/forensics/tsmom_path.out`, `data/forensics/tsmom_null.out`.
- Slot gate: `data/forensics/slot_gate.out`.
- QIEA statistics: `gs://acis-compute-0929-data/runs/20260929-ladder2/validation/cost_stress/20260929T163844Z/rung_1x.json` (`in_sample_evolution`) and `.../engine/rung_1x/params.db` (`param_history`).
- J1 and the R1 lab: `gs://acis-compute-0929-data/runs/2026-10-02-j1/*/summary.json`, `gs://acis-compute-0929-data/runs/2026-10-01-r1-lab-rsim/summary.json`.
- Code facts:
  - the book's target fills at its level and its stop at the worse mid: `tests/backtest/book.py` `maybe_close`;
  - the fitness fills both at their levels: `core/optimizer/fitness.py` `trade_path`;
  - the gate on target entries: `core/governor/target_gate.py` `_entry_size` → `core/governor/guards.py` `check`;
  - the proportional spread: `tests/backtest/synthetic_market.py` `load`;
  - ILLIQUID: `core/regime/nvma.py` step 3;
  - regime_f: `core/governor/capital_governor.py` `_allocate_one`;
  - B0(d)'s scope: `tests/unit/test_target_path.py`.

---

## 8. Reproduce

All probes are in the session scratchpad, `research/forensics/probes/`, and are copied to the server checkout's `data/forensics/`. The helper is `remote_research.sh forensics "<cmd>"`. Its `git clean` spares `data/`, so run from the copies.

```bash
cp probes/* data/forensics/          # once per helper call: the helper re-ships probes/ and cleans it
# ceilings (seconds each)
python data/forensics/ceiling.py 985 planted > data/forensics/ceiling_planted.json
python data/forensics/ceiling.py 985 null    > data/forensics/ceiling_null.json
python data/forensics/ceiling.py 985 planted 30 1 4   > data/forensics/ceiling_o30.json
python data/forensics/ceiling.py 985 planted 10 24 96 > data/forensics/ceiling_o10long.json
# labels for p10 (shared by every QIEA run on that market; ~8 min on 3 workers)
python data/forensics/frun.py labels_p10 --label-only --workers 3
# engine runs (detached; ~13-80 min each)
bash data/forensics/launch.sh p10_base '' --labels-root data/forensics/runs/labels_p10
bash data/forensics/launch.sh p10_tsoff tsmom_off --labels-root data/forensics/runs/labels_p10
bash data/forensics/launch.sh p10_tsoff_fixed tsmom_off,fixed_params
bash data/forensics/launch.sh p10_tsoff_fixed_nvmaoff tsmom_off,fixed_params,nvma_off
bash data/forensics/launch.sh p10_repaired tsmom_off,mr_off,fixed_params,notp
bash data/forensics/launch.sh m30_tsoff tsmom_off --oracle 30 --folds 12 --workers 1
bash data/forensics/launch.sh m30_tsoff_fixed tsmom_off,fixed_params --oracle 30 --folds 12
bash data/forensics/launch.sh m30_tsoff_fixed_notp tsmom_off,fixed_params,notp --oracle 30 --folds 12
bash data/forensics/launch.sh m30_repaired tsmom_off,mr_off,fixed_params,notp --oracle 30 --folds 12
bash data/forensics/launch.sh l10_tsoff_fixed tsmom_off,fixed_params --oracle 10 --episode 24,96 --folds 12
bash data/forensics/launch.sh l10_tsoff_fixed_notp tsmom_off,fixed_params,notp --oracle 10 --episode 24,96 --folds 12
# per-trade attribution (after a run): writes runs/<name>/analysis.json
python data/forensics/analyse.py p10_base && python data/forensics/show_an.py p10_base
python data/forensics/table.py p10_base p10_tsoff p10_tsoff_fixed   # headline rows
# TSMOM: engine-free on the exact paths, and its 400-seed distribution
python data/forensics/tsmom_path.py 127.6026
python data/forensics/tsmom_null.py 127.6026 400
# R1.6 slot gate on the R1 lab tape (2 instruments, 320 weekdays, seed 3)
python data/forensics/slot_gate.py 2 320 3
```
