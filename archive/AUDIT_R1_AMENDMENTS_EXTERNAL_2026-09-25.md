# AUDIT — R1 spec amendments (commit 271d8e0), EXTERNAL-REFERENT lens — 2026-09-25

> **Status: COMPLETE (finder report, not a sign-off — A5).** Brief: `AUDIT_BRIEF_R1_AMENDMENTS_2026-09-25.md`
> (pinned at c440b17), the EXTERNAL lens plus the shared rules.
> Scratch (every script and output, reproducible, seeded):
> `C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad\audit_r1_external\`
> — `stats_probes.py/.out` (P1–P6), `variance_horizon.py/.out`, `spot_vs_excess_sign.py/.out`,
> `sr_bound_size.py/.out`, `ftmo_symbols_live.json`, and text extracts of every PDF quoted below.

## Attestation
- **Auditor:** Claude Opus 5.5 (1M context). The owner launched it as the EXTERNAL-REFERENT lens (A3). It is at
  or above the A2 floor.
- **Fresh context:** this agent did not author, draft or review commit 271d8e0 or any R1 document. It is a
  finder, not a clearer (A5).
- **Interrupted once:** a session limit stopped the audit. It then resumed from the same context and the same
  scratch files; it was not relaunched.
- **No agents, one repo write:** no subagents and no grandchildren. The only repository write is this file.
- **Reading order (A4):** the brief, then the constitution A3–A6, then the diff `271d8e0` (master, ACIS-03/04/09,
  OOS_VALIDATION, BASELINE, CLAUDE.md, the index). Next, the attack list and the probes. Only then
  `R1_LEAD_REVIEW_2026-09-25.md` and `CLOUD_AUDIT/reports/r1/PLAN_R1.md`, to check the intended meanings.
- **Web budget:** 27 of the 30 allowed calls used. One site blocked the automated fetch (e8markets.com, HTTP 403);
  it was recorded and not bypassed.
- **External sources consulted (all fetched 2026-09-25):**
  - FTMO symbols API `https://ftmo.com/wp-json/ftmo/symbols` (10:47 UTC).
  - FTMO "Forbidden Trading Practices", `https://ftmo.com/en/forbidden-trading-practices/` (dateModified
    2026-02-02).
  - FTMO blog "What is a swap and for whom is it important?" (published 2021-07-30, modified 2026-02-18).
  - FTMO search results for symbols, trading updates and account specifications.
  - Carver, "Fast but not furious" (qoppac.blogspot.com, 1 Feb 2023).
  - Carver's reference implementation `robcarver17/pysystemtrade` (master, fetched 12:08 UTC):
    `systems/provided/futures_chapter15/futuresconfig.yaml`, `systems/provided/rules/ewmac.py`,
    `systems/provided/rules/breakout.py`, `sysdata/config/defaults.yaml` and `docs/backtesting.md`.
  - Moskowitz, Ooi & Pedersen, "Time series momentum", JFE 104 (2012) 228–250 (Pedersen's NYU copy).
  - FDA, *Multiple Endpoints in Clinical Trials — Guidance for Industry* (October 2022),
    `https://www.fda.gov/media/162416/download`.
  - Waudby-Smith & Ramdas, "Estimating means of bounded random variables by betting", arXiv 2010.09686
    (version of 29 Aug 2022).
  - Lo, "The Statistics of Sharpe Ratios", FAJ 58(4) 2002: the abstract at rpc.cfainstitute.org.
  - Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (revised Feb 2015,
    davidhbailey.com).
  - White, "A Reality Check for Data Snooping", Econometrica 68(5) 2000 (users.ssc.wisc.edu copy).
  - Broker help and blog pages on the 17:00 New York rollover (FOREX.com help, FXNX, FP Markets; secondary).

## Findings, ranked

### F1 — HIGH — E2 (the forward kill bettor) mixes units, so a literal build kills every family within days; σ* has no unit either
- **The text (ACIS-09 v1.7 C-BT-11 v2, stage D):**
  - E1 is "the daily net P&L as a fraction of equity, with W = the mean over λ … of Π(1 + λ·max(r/(6σ*), −1)),
    where σ* is the declared vol target".
  - E2 is "the same bettor on μ_claim − r, with μ_claim = SR̂_dev/2".
  - PLAN_R1 §3.4 states E2's null as "mean ≥ SR̂_dev/2".
- **The unit error.** SR̂_dev/2 is a Sharpe ratio (≈ 0.3), while r is a daily return (≈ ±1%). So μ_claim − r is
  positive on essentially every day, whatever the family earns.
- **Reproduced** (`stats_probes.py` P1, 200 paths): on a family whose TRUE annual Sharpe is 0.6, with
  SR̂_dev = 0.6, E2 reaches ≥ 20 (KILL) in **200/200 runs**. The median is day 24 if σ* is read as the annual
  target (0.20), and day 2 if σ* is read as a daily volatility.
- **The consistent claim** is the daily mean implied by half the development Sharpe at the vol target:
  μ_claim = (SR̂_dev/2)·σ*_annual/256, or equivalently (SR̂_dev/2)·σ*_daily/16. That is 0.000234 per day in the
  probe.
- **σ* has no unit.** E1's increments differ ~16× between the two readings, and so does its power. With σ*
  annual, E1 NEVER reaches 20 within 10 years, even at a true SR of 1.0 (P2: 0.00). With σ* daily, the
  probability within 10 years is 0.21 at SR 0.5 and 0.67 at SR 1.0.
- **Why it matters.** The error errs STRICT, so no guard is loosened. But rung 2 of the §14 claim ladder needs
  "E2 silent ≥ 3 months", so a literal build makes rung 2 unreachable. A build-time repair would then be an
  unregistered change to a kill rule.

### F2 — HIGH — Stage A controls family-wise error at ~2α, not α: the fixed-sequence chain and the "Holm among themselves" set each spend the full α
- **The text:** "The primary family is tested first at α = 0.05 … Each later family is tested only if every
  earlier one passed. Families outside the order are Holm-adjusted among themselves." No α is split between the
  chain and the Holm set, and the Holm set is not gated on the chain.
- **The referent** (FDA, *Multiple Endpoints in Clinical Trials*, Oct 2022, Appendix §5, lines 226–240):
  - A fixed-sequence procedure "tests endpoints in a predefined order, all at the same significance level alpha
    … requires (1) prospective specification of the testing sequence and (2) no further testing once the
    sequence breaks".
  - "Ignoring the first endpoint's result recreates the multiplicity problem and causes inflation of the overall
    Type I error rate."
- **The valid form is serial gatekeeping** (§7, lines 283–290): "If all endpoints in the primary family are
  statistically significant at the alpha level … the endpoints in the second family … can be tested at the
  overall alpha level by any prespecified acceptable method (e.g., Holm procedure …) … If, however, at least one
  of the null hypotheses of the primary family fails to be rejected, … the secondary endpoint family is not
  tested."
- **Reproduced** (`stats_probes.py` P6; 200,000 reps; all nulls true; one-sided tests):
  - a chain of 2 plus a Holm set of 3 gives FWER **0.096** at ρ = 0 and **0.081** at ρ = 0.5;
  - a chain of 1 plus a Holm set of 4 gives **0.096**.
  - The claim is 0.05.
- **The ledger's claim is only half true.** GAP-P12D-102 says the chain "controls family-wise error exactly as
  Holm does". That holds for the chain alone (honest negative), not for the chain plus a parallel Holm set.
- **Two further multiplicity leaks in the same stage:**
  - "≤ 3 registered looks per family" has no adjustment in stage A (stage B has Bonferroni over its ≤ 3 looks).
  - "≤ 5 families enter development per quarter" restarts α every quarter with no lifetime budget. An
    open-ended stream of tests needs α-spending or α-investing, or the lifetime FWER grows without bound.
- **By the brief's bar,** this makes the A2 replacement weaker than it claims.
- **Fix:** test the Holm set only after the whole chain passes (serial gatekeeping), or split α between the two.
  Also state how the ≤ 3 looks are adjusted, and set a lifetime α rule.

### F3 — MEDIUM-HIGH — C-BT-12's "variance-matched within 1 ± 0.05" names no horizon, and the defective generator it is meant to fix already satisfies it at its own step
- **The text:** "A planted market is variance-matched to its null within 1 ± 0.05, so a positive control differs
  from its null in drift only (GAP-P12D-90)."
- **Reproduced** (`variance_horizon.py`, the repo generator's defaults re-implemented: 20 s ticks, daily_vol
  0.005, drift 0.15σ per step, 1–4 h episodes):

  | Horizon | Planted/null variance ratio | Within 1 ± 0.05? |
  |---|---|---|
  | 20 s step | 1.023 | yes |
  | 1 hour | 4.52 | no |
  | 1 day | 14.7 (≈ 3.8× in sd, the GAP-P12D-90 confound) | no |

- **Why it matters.** Checked on native step returns, the current confounded market passes the new law. The
  horizon must be the graded rule's decision horizon (daily for TREND), or every horizon the lab's rules use.
- **Related:** fat-tailed returns make a realised-variance tolerance noisy per fold. Match by construction
  (common random numbers plus an exact rescale), not by a sampled tolerance.

### F4 — MEDIUM — Stage C's residualised held-out kill fires on ~31% of real factor-borne edges, exactly as often as on noise
- **The text:** "The held-out instruments are residualised on the explored set's class factor … Each kills at
  t < −0.5 (GAP-P12D-97)."
- **The mechanism.** If a family's edge reaches a held-out instrument through the class factor, the residual
  alpha is 0 by construction. So t ~ N(0,1), and P(t < −0.5) = 0.309 — the same as for a pure-noise family.
- **Reproduced** (`stats_probes.py` P3), kill rate of the residual-alpha test:
  - 0.308 with the edge all common;
  - 0.126 with 70% common;
  - 0.032 with 40% common.
  - The 2024–25 holdout (Y = 2) kills a true SR 0.5 edge 11.4% of the time, and SR 0.3 17.8%.
  - Worst case: a real SR-0.5 factor-borne edge dies at stage C ≈ 1 − 0.886·0.692 ≈ **39%** of the time.
- **What the literature says about the common share.** MOP 2012 §4.5 (p. 239): "The correlations are positive
  within each asset class, ranging from 0.37 to 0.38 for equities and fixed income futures to 0.10 and 0.07 for
  commodities and currencies." So for FX and commodities the common share is modest on average.
- **Where it bites.** Three of the seven held-out picks are near-duplicates of explored instruments: USOIL
  (WTI) against UKOIL (Brent), US100 against US500/US30, and GER40 against EU50. For them the common share is
  near 1 (magnitudes *unconfirmed* — no data on disk), so they carry no discriminating evidence into the
  residual.
- **Two narratives disagree with the kill mechanics.**
  - PLAN_R1 (table row "Residualising the held-out set") accepts that residualising strips a factor-borne edge,
    and says such an edge "can be credited only forward". But the kill fires on ~31% of these edges, so they
    are killed, not merely uncredited, and never reach stage D.
  - GAP-P12D-97's claim that t < −0.5 "spares most real ones" was argued for the raw statistic, not the
    residualised one.
- **Honest negative:** "a check that can only refuse spends no α" is true for size.
- **Fix:** state the residualised test's kill rate on a factor-borne real edge in the spec. Either (a) grade
  the held-out set raw, as a kill test whose upward leak only weakens it, or (b) keep the residual but exempt
  near-duplicates, or (c) re-draw the held-out set excluding near-duplicates. The last needs an owner ruling,
  since the salt is frozen.

### F5 — MEDIUM — The "cost ≤ ⅓ of pre-cost Sharpe" rule is attributed to Carver but departs from his speed limit in two ways
- **Carver** ("Fast but not furious", qoppac.blogspot.com, 1 Feb 2023):
  - "I have a trading speed limit concept which states that I don't want to allocate more than third of my
    expected pre-cost Sharpe Ratio towards trading costs."
  - "For an individual trading rule on a single instrument, that equates to a maximum of around 0.13 or 0.10
    SR annual units to be spent on costs, depending on which of my books you are reading."
  - "Annual cost, SR units = (forecast turnover + rolls per year) * cost per trade".
- **Departure 1: the swap.** Master §5.6 says "its cost, **including the venue's swap**". Carver's cost is
  turnover-driven trading cost. Swap is a holding cost that barely changes with speed: forecasts are scaled to
  an average |10| at every speed. So a speed filter that includes swap filters instruments, not speeds. And
  for FX, most of the swap is the interest differential, a carry RETURN whose sign flips with the position;
  only the broker's markup is a cost.
- **Departure 2: expected versus realised Sharpe.** Master §5.6 says "expected pre-cost Sharpe", but stage A
  says "its cost including swap is ≤ ⅓ of **its** pre-cost Sharpe". Carver's denominator is a fixed
  expectation (≈ 0.4, hence 0.13 SR). A realised per-instrument pre-cost Sharpe makes the "pre-registered cost
  filter" a data-dependent per-instrument selection. That is a look outside the register, and it strains
  "parameters are pooled across instruments".
- **Fix:**
  - Pin Carver's fixed cap on turnover cost in SR units (0.13 or 0.10, naming the book).
  - Check the swap MARKUP separately, as an instrument-level viability filter.
  - Record both as `declared_deviations`.

### F6 — MEDIUM — "The MOP-2012 12-month sign, the literature-fixed baseline variant" points to a rule that is not MOP's, and "immaterial" is measurably false
- **The pointer.** Master §5.6 v2.21 names "the MOP-2012 12-month sign, which is the literature-fixed
  **baseline variant**, run raw first (ACIS-04 §6.6)". ACIS-04 v1.3 §6.6 is a 3-horizon vote
  (63/126/252 days) on SPOT returns.
- **MOP 2012 itself:**
  - p. 230: "Each day, we compute the daily excess return of the most liquid futures contract".
  - §4: "we focus on the properties of the 12-month time series momentum strategy with a 1-month holding period
    (e.g., k=12 and h=1)".
  - eq. 5: r^TSMOM = sign(r_{t−12,t})·40%/σ_t·r_{t,t+1}, with σ an EWMA of squared daily returns (centre of
    mass 60 days, ×261; §2.4).
  - Appendix A.3: "We use spot and forward interest rates from Citigroup to calculate currency returns".
- **The provenance record is honest, but one claim fails.** `core/signals/canonical.py` declares both
  departures. It calls the spot-versus-excess one "immaterial at 3-12m FX horizons — GAP-0073".
- **Measured** (`spot_vs_excess_sign.py`, the repo's ECB reference rates and dated overnight rates,
  2013–2025, 3,326 days per pair): the 12-month SPOT sign differs from the 12-month EXCESS sign on **3.0–12.1%
  of days**.

  | Pair | Days with a different sign |
  |---|---|
  | EUR/AUD | 12.1% |
  | USD/CHF | 11.3% |
  | EUR/CHF | 10.8% |
  | CAD/JPY | 8.9% |
  | USD/JPY | 8.3% |

  For index CFDs the gap is financing minus dividends, several percent a year.
- **A new mismatch in v2.21.** C8 now books P&L net of swap, so the book is on an excess basis while the
  signal is on spot. MOP's construction avoids exactly that.
- **Fix:** make the baseline member faithful (the sign of the 12-month excess return, using the rates already
  on disk; one horizon; the declared vol scaling). Otherwise stop calling it "literature-fixed" and "the
  12-month sign", and re-open GAP-0073's "immaterial".

### F7 — MEDIUM — The ±1-sign permuted null has zero edge only in log units; the generator builds prices by exponentiating
- **The conditional-mean argument.** For a non-anticipating position p_t, E[p_t·s_t·r | F_{t−1}] = 0 exactly
  (honest negative in additive or log units).
- **The price problem.** `tests/backtest/synthetic_market.py` accumulates LOG returns, and price = exp(log
  mid). Price-unit P&L then has E[e^{s·r} − 1] = E[cosh r] − 1 ≈ σ²/2 > 0 per period, so a long-biased rule
  earns on the null.
- **Reproduced** (`stats_probes.py` P4; sign-flipped, shuffled t(4) returns; notional-sized always-long), SR
  on the null:
  - +0.03 at 0.5%/day (EUR/USD-like);
  - +0.09 at 1%/day (gold-like);
  - **+0.31 at 3.5%/day** (NATGAS-like, now in the 30-instrument universe).
- **The planned test would not catch it.** PLAN_R1's "add a martingale test" will pass on the log-price path
  while the book is booked in price.
- **Fix:** sign-flip ARITHMETIC increments, or add the antithetic (globally sign-flipped) path so every rule's
  long bias cancels. Grading the null in log units is not a fix, because it is not the book.

### F8 — MEDIUM — The "10% no-trade buffer" as worded is a dead zone around a zero forecast; Carver's buffer sits around the current position
- **The text** (master §2 and §5.5, CLAUDE.md rule 5): "A net forecast inside the no-trade buffer places no
  order."
- **Carver** (pysystemtrade `docs/backtesting.md`, "Buffering and position inertia"):
  - "we avoid trading if our optimal position changes only slightly by applying a 'no trade' buffer around the
    current position … We compare the current position to the optimal position. If it's not within 10% (the
    'buffer') then we trade".
  - Forecast buffering: "we take a proportion of the average absolute position (what we get with a forecast of
    10), and use that to size the buffer width … if outside the buffer we trade to the nearest edge".
- **The difference.**
  - Under Carver, if an open position is long at |f| = 8 and forecasts come to cancel (net ≈ 0), the optimal
    position leaves the band and the book trades down to its edge, near flat.
  - Under the spec's dead-zone wording, "no order" is placed, so the position is KEPT while forecasts are
    ambiguous.
- **Guard check.** This is not looser than v2.20 on entries: DISCARD_OPPOSITE also left open positions to their
  own exits. So it breaks no guard claim. But it misstates the cited method and inverts the intent of
  "ambiguity = no trade" for holdings.
- **Fix:** define the buffer as Carver's (band = 10% of the forecast-10 position, around the current position;
  trade to the edge), and restate the conflict row accordingly.

### F9 — MEDIUM-LOW — PBO ≤ 0.20 is four times looser than the cited paper's customary level, and undeclared
- **The source** (Bailey, Borwein, López de Prado & Zhu, revised Feb 2015, §3.1): "In accordance with standard
  applications of the Neyman-Pearson framework, a customary approach would be to reject models for which PBO
  is estimated to be greater than 0.05."
- **The departure.** The spec uses PBO ≤ 0.20 for explored families. With ≤ 9 highly correlated grid members,
  CSCV's rank logits are coarse. The paper's worked choice is S = 16 (quarterly) partitions.
- **Fix:** record 0.20 as a declared deviation with its reason (max-t carries the α; PBO is a secondary kill),
  and pin S.

### F10 — MEDIUM-LOW — "Max-t over the declared grid" does not say how the null distribution of the maximum is obtained
- **The source** (White, Econometrica 2000, p. 1104): "To handle time-series data, we require a resampling
  procedure applicable to dependent processes … we apply and analyze the stationary bootstrap of Politis and
  Romano".
- **The gap.** Using independent-normal critical values for a max over ≤ 9 highly correlated members would be
  conservative. A naive i.i.d. bootstrap ignores the daily autocorrelation and the volatility clustering.
- **Fix:** name the procedure: a stationary or block bootstrap of the member daily series jointly, recentred
  (White; Romano–Wolf for step-down), with the block length pre-registered.

### F11 — LOW-MEDIUM — The stage-A bar SR̂ > z/√Y is robust to fat tails but not to autocorrelation (Lo 2002)
- **Lo 2002 abstract (CFA Institute):** "Monthly Sharpe ratios cannot be annualized by multiplying by √12
  except under very special circumstances" and "the annual Sharpe ratio for a hedge fund can be overstated by
  as much as 65 percent because of the presence of serial correlation".
- **Reproduced** (`sr_bound_size.py`; true mean 0; Y = 11; bar 0.496), size of the test (nominal 0.05):

  | Return process | Size |
  |---|---|
  | i.i.d. normal | 0.047 |
  | i.i.d. t(3) | 0.048 |
  | GARCH-t(5) | 0.050 |
  | AR(1), ρ = 0.05 | **0.063** |
  | AR(1), ρ = 0.10 | **0.072** |

- **Fix:** state the standard-error estimator: Newey–West/HAC or Lo's correction on the daily portfolio
  series. The fat-tail robustness is an honest negative.

### F12 — LOW-MEDIUM — Forecast scalars: null-fixed values sit ~24% above Carver's published ones, and the (scalar, normaliser, EWMA convention) triple is not pinned
- **Carver's published values** (pysystemtrade `futuresconfig.yaml`, the Systematic Trading chapter-15
  system): ewmac16_64 **3.75**, ewmac32_128 **2.65**, ewmac64_256 **1.87**; `forecast_cap: 20.0`.
  `ewmac.py` uses `price.ewm(span=Lfast)` and divides by "The daily price unit volatility (NOT % vol)".
- **The plan's values.** PLAN_R1 fixes scalars "on the synthetic null (4.66 / 3.26 / 2.28)": ratios 1.24,
  1.23, 1.22.
- **The consequence.** On trending real data, the null-fixed scalars give an average |forecast| of about 12
  instead of 10. Positions then carry ~20%+ more risk than σ* declares, which feeds F1's σ*-scaled bettors and
  the prop drawdown limits. The magnitude is inferred from the published scalars and is *unconfirmed* on
  ACIS's own data.
- **The spec's gap.** v2.21 allows "literature values or on the synthetic null" without choosing, and without
  pinning the normaliser and the span-versus-centre-of-mass convention. Confusing EWMA span, centre of mass and
  half-life is a known bug class in this kind of code.
- **Also:** literature scalars were themselves fit on real data that overlaps 2012–2023. The book sample is not
  checked, so this is *unconfirmed*.

### F13 — LOW-MEDIUM — E1's formula clips at −1 while the text says the −6σ* day is "never clipped", and "voids the running certification" is ambiguous
- **The validity condition** (Waudby-Smith & Ramdas 2022, §2): a test supermartingale is "a nonnegative process
  adapted to F, M0 = 1, and E_P(M_t|F_{t−1}) ≤ M_{t−1}". §4's betting factor needs bounded observations so that
  "(1 + λ_t(m)·(X_t − m)) ∈ [0, ∞)". Ville then gives P(∃t: L_t ≥ 1/α) ≤ α.
- **The clip changes the null.** A clipped increment max(y, −1) ≥ y tests E[max(y, −1)] ≤ 0, which is weaker
  than E[r] ≤ 0. It can credit a negatively skewed book whose mean is below zero.
- **Validity for the stated null** therefore needs the −6σ* tripwire to set W to 0 (or permanently fail),
  never to reset it to 1 and resume. Each restart adds up to 1/20 of false-credit probability.
- **Fix:** say "void = W := 0 for the family-version", and delete the clip or say it can never bind.

### F14 — LOW — FTMO's gap clause has two prongs; a fixed per-symbol clock meets only the closure prong
- **FTMO** (Forbidden Trading Practices, modified 2026-02-02): gap trading is opening trades "when major global
  news, macroeconomic events, or corporate reports or earnings are scheduled and they might affect the relevant
  financial market …; or two hours or less before a relevant financial market is closed for at least two
  hours".
- **The gap.** v2.21 says execution runs on "a pre-registered per-symbol clock outside the 17:00 New York
  rollover window and every gap-rule window". A fixed clock, such as GAP-P12D-95's example "FX 03:00–11:00 New
  York", contains 08:30 New York releases. So the news prong needs event-day skips, and RSIM must replay the
  same skips. That needs the historical event calendar (GAP-P12D-03), which GAP-P12D-58 already owns as
  "the NEWS half".
- **Fix:** add the pointer, so the clock text does not read as complete.

### F15 — LOW — "Effective breadth, IDM = √(N/(1+(N−1)ρ))" mislabels a square root, and drops Carver's cap
- **The label.** The algebra is Carver's IDM for equal weights and constant ρ. But effective breadth is
  N_eff = N/(1+(N−1)ρ), and IDM = √N_eff. A threshold written against one and computed as the other is off by
  a square.
- **The cap.** pysystemtrade `defaults.yaml` caps both multipliers (`dm_max: 2.5`). v2.21 names neither the FDM
  nor the IDM cap.

### F16 — LOW — Rung 3 ("edge shown forward", E1 ≥ 20) is decades away at a realistic Sharpe, and nothing records it
- **Measured** (P2): with the favourable σ* reading, the median time to E1 ≥ 20 is ~22 years at SR 0.5 and ~11
  years at SR 0.8. PLAN_R1 already says 2.4–3 years at SR 1.5.
- **Why it matters.** The text's "not yet, never failed" is honest. But the ladder should state the expected
  horizon beside rung 3, so "not yet" is never read as "soon".

### F17 — LOW — C8's swap "table as data" needs a charge calendar too
- **What the table lacks.** The live FTMO table has no field for the rollover weekday or the multiple (the keys
  were verified).
- **What FTMO says** (swap blog, modified 2026-02-18): "the triple swap being charged overnight from Wednesday to
  Thursday", because "most instruments need two days to settle a trade", and swap "is stated in points per
  lot".
- **Unchecked:** whether index and energy CFDs triple on another day (*unconfirmed*).
- **Fix:** C8 must carry the per-symbol charge calendar beside the table (the glitch class C-BT-10 already tests
  it for FX Wednesdays).

### F18 — LOW — The live-eligibility rule rests on an unverified minimum lot, and contract sizes drift
- **What the table lacks.** The FTMO JSON has `maxTradeVolume` but no minimum-volume field (keys verified).
  FTMO's FAQ defers to the platform's "Specification" window.
- **Contract sizes change.** FTMO changed `.cash` index contract sizes from 10 to 1 per lot in September–October
  2022 (FTMO trading updates, found by search).
- **Fix:** read the min volume and volume step from the platform at onboarding and store them dated, as
  GAP-P12D-93 already requires for the swap table.

## Honest negatives
- **Guard integrity (the brief's first attack):**
  - I found no v2.21 text under which a trade passes that v2.20 refused for SAFETY reasons.
  - The NVMA veto line (master §4, "confidence < 0.55; spread > 3× session median; tick velocity < 0.5×") is
    untouched by the diff, and §4 now says every trigger stays.
  - F8 is the closest case: holdings under ambiguity. But v2.20 also left open positions to their own exits.
  - Lot rounding DOWN is stricter than Carver's round-to-nearest. It is conservative.
- **The fixed-sequence chain alone** controls FWER at α under any dependence (FDA 2022 §5). F2 concerns only the
  parallel Holm set.
- **"A check that can only refuse spends no α"** is true for size. Its cost is power (F4).
- **"A demeaned random walk is a bridge that plants mean reversion"** is TRUE. Reproduced (`stats_probes.py` P5):
  a 252-day sign-trend rule has mean t −0.59 on 3-year and −0.26 on 12-year demeaned paths (theory
  −√(2L/πn) = −0.46 / −0.23), and 0 when the path is not demeaned.
- **The ±1-sign fix** makes every non-anticipating rule's expected P&L exactly zero in additive or log units
  (the conditional-mean argument above). F7 is about price units only.
- **Stage-A bar and holdout threshold:**
  - The bar 0.496 at Y = 11 re-derives the stated "0.50".
  - The test's size is 4.7–5.0% under i.i.d. normal, t(3) and GARCH-t (fat tails do not break it; F11 is
    about autocorrelation).
  - The holdout threshold t < −0.5 at Y = 2 is SR̂ < −0.354, matching PLAN_R1 B5.
- **The e-process machinery:**
  - A mean over a FIXED λ grid of product bettors, with increments ≥ −1 and λ ≤ 1, is a valid test
    martingale (Waudby-Smith & Ramdas §2 and §4, plus Ville). "Valid under daily looks" holds.
  - E3's certification by two one-sided nulls both at W ≥ 20 is valid by intersection–union (my reasoning; no
    source fetched).
- **The trend family matches Carver on these points:**
  - EWMAC speeds (16,64)/(32,128)/(64,256) and the ±20 cap are Carver's (pysystemtrade `futuresconfig.yaml`).
  - The breakout form is Carver's: `40.0 * ((price - roll_mean) / (roll_max - roll_min))`, smoothed by an EWMA
    of span lookback/4 (`rules/breakout.py`). The spec should still write the formula into the provenance
    record.
- **Venue facts confirmed:**
  - All 30 research instruments are quoted and `active` on FTMO (live API, 2026-09-25 10:47 UTC).
  - The lead's snapshot `archive/r1_lead_probes/ftmo_symbols_2026-09-25.json` parses IDENTICAL to the live
    table.
  - Contract sizes: FX 100,000; XAU 100; XAG 5,000; XCU 100; index `.cash` 1 (JP225 10); oils 100;
    NATGAS 1,000.
- **FTMO's gap clause** is quoted exactly, closure prong "two hours or less before … closed for at least two
  hours". GAP-P12D-58 is right that no account type is exempt: the page limits it to none.
- **The 17:00 New York rollover** is a wide-spread window: FOREX.com help (rollover at 5 pm New York) and
  secondary broker notes. The repo's own Dukascopy probe (`archive/r1_lead_probes/rollover_spread.out`) measures
  2.2–2.4 pips against 0.3. Deciding on the 17:00 close and executing outside that window is sound.
- **The 17:00 New York decision time** suits every named instrument as a common daily snapshot. Where a CFD is
  in its daily break or closed at 17:00 New York, the snapshot is the last price before the break, which is
  consistent across days.

## What I could not check
- **E8 One/Pro swap-free:** `https://e8markets.com/e8-pro` returned HTTP 403 and was not bypassed. Only
  third-party summaries (search result, 2026-09-25) say swap-free is offered at +10%. *Unconfirmed first-hand.*
- **FTMO daily trading hours and break times:** the symbols page lists none and defers to the platform. The
  ledger's "20:50–22:05 UTC" index, metal and oil break is *unconfirmed*.
- **FTMO's minimum lot and volume step:** 0.01 is *unconfirmed*. The triple-swap day for index and energy CFDs
  is *unconfirmed*.
- **Carver's printed books:** Systematic Trading and Leveraged Trading were not accessed. I relied on his
  2023 blog and his reference implementation, and did not check book page citations for the scalars, the
  buffer or the IDM cap.
- **Primary papers not read:** Romano–Wolf's step-down, Shafer–Vovk, and Ramdas et al. 2023 (*Statistical
  Science*). I used Waudby-Smith & Ramdas instead.
- **Instrument-level numbers:**
  - Dukascopy history start dates for the 22 instruments new to the universe; the spec defers this to the
    owner's `check`.
  - How closely the near-duplicate held-out picks track their explored counterparts (F4); no data is on disk.
- **Unchanged text:** Hurst–Ooi–Pedersen's figures in §5.6 are out of scope (the diff did not change them).
- **Real-data behaviour:** the daily P&L autocorrelation of the TREND family (F11), and the real-data average
  |forecast| under null-fixed scalars (F12). No real-data look is allowed at this stage.

## Proposed ledger entries (no IDs; the lead mints them)
1. **(F1, high/certain)** — the E2 null mixes a Sharpe ratio with a daily return, and σ* has no unit. A
   literal build kills every family within days (200/200 runs at a true SR of 0.6).
   - Fix: μ_claim = (SR̂_dev/2)·σ*_annual/256. Declare σ*'s unit. Add a lab test in which a true-SR family is
     not killed by E2 at the declared rate.
   - Owner: spec (ACIS-09 C-BT-11 v2 stage D).
2. **(F2, high/certain)** — stage A's FWER is ~2α: a fixed-sequence chain plus a parallel Holm set, each at α
   (FWER 0.081–0.096).
   - Fix: serial gatekeeping (Holm set only after the chain passes) or an α split. An adjustment for the ≤ 3
     looks per family. A lifetime α rule for the quarterly stream.
   - Guard surface: a gate rule, so never batched (A6).
3. **(F3, medium-high/certain)** — C-BT-12's variance match names no horizon. The GAP-P12D-90 generator already
   passes it at its 20 s step (1.023), while its daily ratio is 14.7.
   - Fix: match at the graded rule's decision horizon, by construction.
4. **(F4, medium/high)** — the stage-C residualised held-out kill fires on ~31% of real factor-borne edges,
   the same as on noise. Worst case ≈ 39% at stage C for an SR-0.5 edge.
   - The picks include near-duplicates (USOIL/UKOIL, US100/US500, GER40/EU50). GAP-P12D-97's calibration was
     for the raw statistic.
   - Fix: owner ruling on (a) raw kill, (b) exempt near-duplicates, or (c) a re-draw.
5. **(F5, medium/high)** — the "⅓ of pre-cost Sharpe" filter is not Carver's speed limit: it adds swap and
   uses a realised per-instrument Sharpe.
   - Fix: Carver's fixed SR-unit cap on turnover cost; a separate swap-markup filter; declared deviations.
6. **(F6, medium/certain)** — the "MOP-2012 12-month sign / literature-fixed baseline" resolves to a 3-horizon
   spot vote. GAP-0073's "immaterial" is false: sign disagreement is 3–12% of days on FX (EUR/AUD 12.1%).
   - Fix: a faithful excess-return 12-month sign, or relabel. Re-open GAP-0073.
7. **(F7, medium/certain)** — the ±1-sign null is zero-edge only in log units. The price-unit book earns σ²/2
   per day for long bias (SR +0.31 at NATGAS-like volatility).
   - Fix: flip arithmetic increments, or add antithetic paths. Add a price-unit null test.
8. **(F8, medium/high)** — the no-trade buffer is worded as a dead zone around a zero forecast, not Carver's
   band around the current position. It holds positions under ambiguity.
   - Fix: Carver's definition in ACIS-04 before R1.6.
9. **(F9 + F10, medium-low)** — PBO ≤ 0.20 against the paper's customary 0.05 (undeclared), and the max-t null
   procedure unspecified (White: a dependent-data bootstrap).
   - Fix: declare the deviation, pin S, and name the bootstrap and block length.
   - Guard surface (verdict rules), so not batched.
10. **(F11, low-medium)** — the SR lower-bound test inflates to 6.3–7.2% size at lag-1 autocorrelation of
    0.05–0.10.
    - Fix: a HAC or Lo-corrected standard error.
11. **(F12, low-medium)** — the scalar source is not chosen; null-fixed scalars run ~24% above Carver's. The
    (scalar, normaliser, EWMA convention) triple is not pinned.
    - Fix: pin all three; state the vol-target consequence.
12. **(F13, low-medium)** — E1's clip at −1 against "never clipped"; "void" is ambiguous.
    - Fix: void = W := 0; the clip never binds.
13. **(F14–F18, low; one batched row allowed under A6)**, one disposition each:
    - F14: add the pointer from the execution clock to GAP-P12D-58/-03 (the news prong).
    - F15: IDM equals √(effective breadth); name the 2.5 caps.
    - F16: record the expected time to rung 3.
    - F17: C8 carries a per-symbol swap charge calendar.
    - F18: read min volume and volume step from the platform, dated.
    - Residual: the owning implementation tickets.
