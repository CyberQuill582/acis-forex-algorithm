# External-referent audit (Lens 2) — commit 068f8b4 "Governor base-unit sizing (GAP-P12D-22) + evolve-driver steps 1–4"

Auditor: Fable 5.1, fresh context, 2026-09-15. Brief: `AUDIT_BRIEF_P12D22.md` (Lens 2 + "Both lenses"). Finder, not clearer. No repo file changed except this report. Diff audited: `git diff 99eb9f0 068f8b4` (32 files). Referents quoted below were fetched today; reproductions ran with the repo's own modules (light scripts, no full suite).

Findings: **7** — high 2 (F-E1, F-E3), medium 3 (F-E2, F-E5, F-E6), low 2 (F-E4, F-E7). Two of the seven (F-E1, F-E2) attack owner-ratified rulings / locked spec text, so they are owner decisions, not author fixes.

| ID | Sev · Lik | One line |
|---|---|---|
| F-E1 | high · high | The "Deflated Sharpe" gate does not compute the paper's statistic: its variance is one strategy's per-fold OOS Sharpe dispersion, not the dispersion of the trials selected among; the construction demands an OOS annualised Sharpe of ~2.5–3.0 to pass (§14 minimum is 1.5). |
| F-E2 | medium · high | Pair legs are "balanced" in base-currency UNITS, not USD notional — the declared EUR/USD–USD/JPY pair carries a 9% USD residual; a gold or CFD leg would size its partner to ~0. |
| F-E3 | high · high | Dropping the in-sample replay removed the engine's only warm-up: TSMOM needs 260 daily bars, so it is inert for the whole first OOS year (2014) and, on a cold holdout run, for all of 2024 — half the locked holdout. |
| F-E4 | low · high | The 7-day "embargo" deletes TEST ticks from the replay; López de Prado's purge/embargo removes TRAINING observations. The engine goes blind 7 days a year and Dec-31 positions are booked at Jan-8 prices. |
| F-E5 | medium · medium | Lot semantics: 100,000 units/lot is hard-coded for every instrument (Governor lot cap, orchestrator, fragmenter); brokers define contract size per symbol (gold = 100 oz), and `size_units` is never snapped to `lot_step`/`min_lot`/`tradeUnitsPrecision`. |
| F-E6 | medium · medium | The labelled-bar cache key omits inputs that change a label (factory/session-median config, instrument calendar + spread filter, the macro/tier-G source), so stale labels serve silently once those change. |
| F-E7 | low · low | Account currency hard-coded to USD while the drafted prop rulebooks may be EUR/GBP accounts; a cross's USD rate is read from the last bar with no staleness check. |

---

## F-E1 — the DSR gate deflates by the wrong variance (fold OOS Sharpes are not "trials")

**Severity:** high · **Likelihood:** high (by construction, every run). **Owner-ratified** (GAP-P12D-18 resolution 3, amending GAP-P12D-16) — an owner decision to re-open, not an author fix.

**Where:** `tests/backtest/harness.py` `Backtest.run` (fold Sharpes → `deflated_sharpe(oos_returns, fold_sharpes, n_trials)`), `tests/backtest/deflated_sharpe.py` `sharpe_threshold(…, n_trials)`, `tests/backtest/report.py` `passed` (`DSR_MIN = 0.95`), KNOWN_GAPS GAP-P12D-18 / GAP-P12D-16 amendment.

**Referent** — Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, text extracted from https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf:
> "…the set of N independent backtests or track records associated with a particular strategy class (e.g., Discretionary Macro). Each element of the set is called a trial, and it is associated with a SR estimate … Suppose that these trials' {SR_n} follow a Normal distribution, with mean E[{SR_n}] and variance V[{SR_n}]. … the concept of 'strategy class' implies that the trials are bound by some common characteristic pattern."
> "Appendix 3 shows how N can be determined when the trials are not independent."
> "When an investor selects the best performing strategy over a large number of alternatives, she exposes herself to 'the winner's curse.' … DSR is a PSR where the rejection threshold is adjusted to reflect the multiplicity of trials."

Also https://metricgate.com/docs/deflated-johnson-sharpe-ratio/ : "N: number of independent strategy trials before selection." / "Use the count of independent strategy variants you actually evaluated before selecting the reported one."

**What the code does instead.** `V` is the sample variance of the *same* strategy's ten per-year out-of-sample Sharpe ratios (`fold_sharpes`), and `N` is lifted to `min_trials + Σ champions`. The ten fold Sharpes are sub-periods of ONE track record — nothing was selected among them; the graded OOS Sharpe is approximately their mean. So SR0 measures how much a single strategy's Sharpe wanders year to year, multiplied by the expected-max factor for N correlated champions (9 regimes × instruments × folds). That is not the paper's quantity in either factor: V is time-dispersion, not cross-trial dispersion; N counts per-fold in-sample winners that are *components* of the OOS curve, not alternatives it was picked from (and the paper's Appendix 3 warns the correlated count over-states N — the module's declared deviation (1) already says so, but it still describes N as "the number of trial Sharpe ratios supplied", which is no longer true since `n_trials` lifts it).

**Reproduction** (`scratchpad/repro_dsr_hurdle.py`, using the repo's `deflated_sharpe.py`; ten fold annual Sharpes drawn around 1.5 ± 0.8, an ordinary year-to-year spread; 2,520 normal daily OOS returns):
```
fold annual Sharpes: [2.53, 2.66, 1.55, 0.89, 0.63, 1.53, 0.68, 0.35, 1.66, 1.61]  (daily sd 0.0492)
  N=  10: SR0 daily 0.0775 = annualised 1.23
  N=  50: SR0 daily 0.1120 = annualised 1.78
  N= 180: SR0 daily 0.1344 = annualised 2.13
  N= 720: SR0 daily 0.1555 = annualised 2.47
  N=180: OOS annual Sharpe 1.5: DSR ~ 0.080     2.0: 0.342     2.5: 0.949     3.0: 0.990
  N=720: OOS annual Sharpe 1.5: DSR ~ 0.004     2.0: 0.081     2.5: 0.844     3.0: 0.962
```
With 9 tradeable regimes × 2 enabled instruments × 10 folds, N ≈ 180 + registry; with 8 instruments N ≈ 720+. A strategy that clears §14's `SHARPE_MIN = 1.5` by a full point fails the gate almost surely. The gate is therefore (a) not the cited statistic, and (b) a de-facto undeclared second Sharpe hurdle of ≈ 2.5–3.0 whose level depends on how *stable* the strategy is across years, not on how many things were tried. Conservative, yes — but "conservative" is not the same as "the DSR", and the report labels it `deflated_sharpe` and gates live on it.

**Minimal fix (author-side, regardless of the ruling):** add a third DECLARED DEVIATION to `deflated_sharpe.py` and to ACIS-09 C-BT-11 stating exactly what V and N are now (fold-Sharpe time-variance; N lifted by champions+registry), and update deviation (1)'s wording. **Owner decision:** either (i) compute V from an actual selection set that has returns — the per-fold, per-regime candidate champions' *holdout* Sharpe across instruments (`evolve_fold` already computes the holdout simulation for every candidate; the staged champion is selected among them by holdout E_R, which is a selection event), with N = those candidates + registry, and keep the OOS record undeflated by its own sub-periods; or (ii) keep the current construction but rename it (e.g. `fold_stability_psr`) so the read path does not claim a DSR, and record the ≈2.5–3.0 implied hurdle next to `SHARPE_MIN`.

---

## F-E2 — pair-group "balance" equalises units, not exposure

**Severity:** medium (9% residual on the only declared pair; latent ~100% mis-sizing for a gold/CFD leg) · **Likelihood:** high for the residual, medium for the catastrophic case (no such pair declared yet). ACIS-05 §7 step 6 is LOCKED text ("both legs take min(size_A, size_B)") → owner decision.

**Where:** `core/governor/capital_governor.py` `allocate_group` line 167 `balanced = min(leg_a.size_units, leg_b.size_units)` (units); the new lines 172–174 then convert that one unit count to two different USD notionals. Test `test_pair_legs_balance_without_the_yen_leg_shrinking_both` asserts unit equality and calls it balance; GAP-P12D-22 says "pair legs balance".

**Referent** — master `ACIS_SPEC.md` line 242: "leg sizes balanced so the intended relationship exposure (not two directional bets) is what's on the book"; the pairs-trading literature (Gatev, Goetzmann & Rouwenhorst 2006, RFS 19(3), "self-financing portfolios of pairs", https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615) and standard practice: "A dollar-neutral position means equal dollar amounts long and short" (https://www.dothefinancial.info/pairs-trading/dollar-neutrality.html). A relationship bet is sized in matched *notional* (or a hedge ratio), never in matched unit counts across instruments whose units are worth different amounts.

**Reproduction** (`scratchpad/repro_pair_notional.py`, real `CapitalGovernor` + the repo's `_pair_signals()`):
```
declared pair EUR_USD/USD_JPY: units 441.82 / 441.82
  USD notional leg A = 486.00, leg B = 441.82, ratio B/A = 0.909
  net currency deltas (USD): {'EUR': '-486.00', 'USD': '44.18', 'JPY': '441.82'}
hypothetical XAU_USD/AUD_USD: reasons formula:group / formula:group; units 0.24 / 0.24
  USD notional gold leg = 480.00, AUD leg = 0.16, ratio = 0.00032
```
The Governor's own delta accounting shows the "one relationship bet" leaves a 44.18 USD directional residual on a 486 USD group (the USD leg should net to zero for a synthetic EUR/JPY). With a gold leg the partner is sized to 16 cents. Before the fix the yen leg's 3.14 units shrank both legs ~140×; the fix restored the yen leg but kept the unit-equality rule that only looks right when both bases are worth ≈ $1.

**Minimal fix:** balance in USD notional — `balanced_usd = min(units_a·per_unit_a, units_b·per_unit_b)`; `units_leg = (balanced_usd / per_unit_leg).quantize(0.01)`; `group_notional = balanced_usd`; ACIS-05 v1.4 wording for §7 step 6 ("min of the two USD notionals, each leg converted back to its own base units"); the test should assert `units_a·per_unit_a == units_b·per_unit_b`, not `units_a == units_b`. Not owned by any live ledger entry.

---

## F-E3 — no in-sample replay ⇒ no engine warm-up ⇒ TSMOM dead for the first OOS year and half the holdout

**Severity:** high · **Likelihood:** high (certain on the ratified fold plan and on a cold holdout run).

**Where:** `tests/backtest/harness.py` `run` (evolve_fn, then `_replay` of test ticks only — the old `_replay(loop, fd.train_states, insample)` that fed two years of ticks through the engine before the first graded tick is gone); `core/signals/agon.py` lines 95–137 and 484–485 (`daily_capacity`, daily bars accumulate only from observed ticks; `tsmom_min_history_days: 260`, `tsmom_lookback_days: [63,126,252]`); `observe_daily_close` (line 158) is the seeding hook and is called only from tests/fixtures.

**Referent** — Moskowitz, Ooi & Pedersen (2012) time-series momentum uses a 12-month lookback (the config's 252-day leg); standard backtest practice is a non-trading warm-up before the first graded bar, e.g. QuantConnect docs (https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods): "Warm Up is a great way to prepare your algorithm and its indicators for trading." / "You can't place trades during the warm-up period because the data feed is replaying historical data for setting algorithm state."

**Arithmetic (no script needed):** fold 0 tests 2014-01-08 → 2015-01-01 ≈ 255 rollover-anchored daily bars < 260 required, so `_daily_bars` never reaches `tsmom_min_history_days` inside the year: TSMOM emits nothing in 2014 (1 of 10 development OOS years). The final run on the locked holdout (`plan_folds(2024, 2025)`) starts a fresh engine at 2024-01-08: TSMOM is inert for all of 2024, i.e. half of the once-only holdout grade. The other engine state (NVMA's 201-tick windows, session medians at 30 samples/session, the Governor's 15-bar ATR) warms within a day and is not the problem. The grade therefore describes a strategy without its slowest module for its first year — not the strategy that would go live with history.

**Minimal fix:** before the first graded tick of a run, replay ≥ `tsmom_min_history_days` trading days (plus a margin) of ticks through the loop with orders discarded and no equity sampling (a `warmup` flag in `_replay`, or seed `agon.observe_daily_close` from a daily-close series derived from the tick data / the labelled-bar cache); assert in a test that a TSMOM signal can fire on the first OOS day. Record the warm-up window in the report's caveats. Not owned by any live ledger entry (GAP-P12D-18's residual points only at the runner).

---

## F-E4 — the "embargo" removes test ticks, not training observations

**Severity:** low · **Likelihood:** high (every fold, every year). Owner-ratified "~1-week embargo" (OOS_VALIDATION.md line 36–38) — the ratification says "purge boundary leakage", which is what a purge does to the *training* set.

**Where:** `tests/backtest/oos_plan.py` `plan_folds` (`test_start = jan1 + 7 days`), `harness.py` `_replay` (`require_embargo(train_end, first_test_tick, max_hold)`), `walk_forward.py` `require_embargo` ("Refuse a fold whose real train→test data gap is shorter than the maximum hold").

**Referent** — López de Prado, *Advances in Financial Machine Learning* ch. 7, as summarised at https://quantmemo.com/concepts/purged-embargoed-cv: "Purge from the training set every observation whose label span overlaps the label span of any test observation." / "embargo a buffer: drop training observations that fall within a small window after the end of the test set." / "The embargo is one-sided, applied after the test block…". Both operations remove *training* rows; neither removes test data from the evaluation stream.

**What ACIS does:** QIEA's training labels are trade PnLs simulated inside `history(…, end=train_end)`; every simulated trade is closed at or before the last history bar, so no label span crosses into the test year — the purge condition is already satisfied with zero gap. The 7-day gap instead (a) drops 7 test days per year from the engine's tick stream (the engine never sees 1–8 January prices: NVMA windows, the daily-bar aggregator and the SPX rollover marks all see a hole), (b) leaves any position open on 31 December frozen, then closes it on the first 8-January tick by `max_hold` at that day's mid — a seven-day move booked as a 48-hour trade, filled at a level the market may have gapped through, and (c) removes ~1.9% of the OOS record. `require_embargo` then checks the *declared* `train_end` against the first *replayed* tick, conflating the training cut (where leakage lives) with the replay start (where it does not).

**Minimal fix:** keep the training cut at `train_end` (already leak-free); stream test ticks continuously from `train_end` and start *grading* (order acceptance + equity sampling) at `test_start`; make `require_embargo` compare the last training *bar* against the first *graded* tick. If the owner wants the hole kept, caveat it in the report.

---

## F-E5 — position size vs broker conventions: one contract size for everything, no step/precision snap

**Severity:** medium · **Likelihood:** medium (latent for FX because 100,000 happens to be right; wrong the day gold, a CFD or a futures contract is enabled; the `max_lots` prop rule is live now).

**Where:** `core/governor/capital_governor.py` line 297–298 `size_units / Decimal("100000") > max_lots`; `core/execution/venue.py` line 25 `UNITS_PER_LOT = Decimal("100000")` used by `orchestrator.py` line 99 and `fragmenter.py` lines 73/90; `size_units` quantised to 0.01 units (line 291) while `instruments.yaml` declares `lot_step: 0.01`, `min_lot: 0.01` that nothing in `core/` reads (grep: only `venue.py`'s own descriptor defaults).

**Referents** —
- OANDA: "One unit is equal to one of the base currency in a currency pair. For example, one unit of USD/CHF is equal to one dollar and one unit of EUR/USD is equal to one Euro." (https://help.oanda.com/us/en/faqs/micro-lots.htm). Instrument spec: "tradeUnitsPrecision: The amount of decimal places that may be provided when specifying the number of units traded for this instrument." / "minimumTradeSize: The smallest number of units allowed to be traded for this instrument." (https://developer.oanda.com/rest-live-v20/primitives-df/); currency pairs carry `tradeUnitsPrecision` 0 (whole units) per the v20 instrument listings (https://tessl.io/registry/tessl/npm-oanda--v20/3.0.3).
- MT4/MT5: "A standard lot in MetaTrader 5 equals 100,000 units of the base currency" (https://hw.online/faq/understanding-0-1-in-metatrader-5-lot-sizes-and-contract-specifications/); gold: "a standard XAUUSD CFD lot is commonly based on 100 troy ounces of gold" and "Broker specs can vary. Check contract size, tick size, tick value, minimum lot, lot step…" (https://forexvitals.com/articles/xauusd-lot-size). MT5 exposes the contract size per symbol (`SYMBOL_TRADE_CONTRACT_SIZE`); there is no platform-wide constant.

**Effect:** a prop account's `max_lots: 5.0` on XAU_USD means 500 oz ≈ $1M; ACIS would compare 0.24 oz / 100,000 = 0.0000024 "lots" and never fire the cap, and the orchestrator would route "0.0000024 lots" of gold. For FX the numbers are right only because every FX lot is 100,000 base units. Separately, 441.82 EUR units are not a valid OANDA order (precision 0) nor a valid MT5 volume (0.01-lot step = 1,000 units); the venue adapter (ACIS-13, unwritten) must snap, and no ledger entry owns that.

**Minimal fix:** per-instrument `contract_size` (units per lot) in `instruments.yaml` (100000 for FX, 100 for XAU on MT5/cTrader, 1 for OANDA-style CFD units) consumed by the lot cap, the orchestrator and the fragmenter; snap `size_units` down to the venue's `lot_step × contract_size` / `tradeUnitsPrecision` at the adapter boundary (downward only — zero if below `min_lot`), and ledger the adapter obligation under ACIS-13.

---

## F-E6 — labelled-bar cache key does not cover everything that changes a label

**Severity:** medium · **Likelihood:** medium (the event calendar is the next build; the 6 disabled instruments will be onboarded with calibrated `max_plausible_spread`). Overlaps Lens 1 item 3; reported here because it is the "leakage through cached features" bug class in Lens 2 item 4.

**Where:** `tests/backtest/regime_labels.py` `LabelSpec.key()` hashes `source, bar_seconds, cycle_s, regime config, warmup_s` only. Labels also depend on: `cfg.system.data` (`session_median_window`, `session_median_min_samples`, `stale_threshold_ms`, `tick_velocity_window_s` — these feed `factory.session_median` and `state.is_stale`/`tick_velocity`, i.e. the REGIME_WARMING, SPREAD_VETO, DEAD_MARKET and ILLIQUID branches in `nvma.py` lines 249–281); the instrument's `calendar` (session names key the medians; `session == "closed"` ⇒ ILLIQUID) and `max_plausible_spread` (tick filtering in `tick_stream.market_states`); `data_start`; and the macro/tier-G source (`build_nvma` pins `tierg_shock=False`, `build_factory` pins `macro_imminent=False` — once GAP-P12D-03's calendar exists, runtime regimes around events are MACRO_EVENT while the cache labels those bars as market regimes and QIEA trains on bars the engine will never trade).

**Referent:** the standard feature-store rule that a cached derived dataset is keyed by the full closure of its inputs (code version + every config that reaches the computation); the repo's own precedent is `guardrail_hash` / `config_hash` in `HoldoutGuard.begin_final`.

**Minimal fix:** fold `cfg.system.data.model_dump()`, the instrument spec (`calendar`, `max_plausible_spread`), `data_start`, and a `macro_source` identifier (e.g. "none" today, the calendar file hash later) into `LabelSpec`; the `has()` check then refuses stale years automatically.

---

## F-E7 — account currency hard-coded to USD; cross rate read without a staleness check

**Severity:** low · **Likelihood:** low.

**Where:** `core/governor/units.py` `ACCOUNT_CCY = "USD"`; `usd_per_base_unit` reads `bars[leg][-1].close` with no timestamp comparison; `config/platform_rules.yaml` rulebooks carry no account currency.

**Referent:** FTMO and The5ers offer EUR- and GBP-denominated accounts alongside USD (their published account options); the Governor's caps compare a USD notional to `portfolio.nav` in the account currency. Rate staleness: after the Friday close the last GBP_USD bar is ~48 h old at the Sunday open; a gap of 1% mis-sizes EUR_GBP by 1% — immaterial today, but "never guessed" (the module's stated invariant) should include "never stale beyond the signal's `valid_for_seconds`".

**Minimal fix:** an `account_currency` field in the rulebook schema, validated equal to `ACCOUNT_CCY` at boot until multi-currency accounts are supported; an `as_of` age check on the cross leg's bar (zero with reason `stale_usd_rate` beyond, say, one session). Not owned by any live entry.

---

## Honest negatives (claims that survived, with their referent)

1. **Base-unit sizing arithmetic (GAP-P12D-22) is right for every instrument shape.** 1 unit = 1 base currency (OANDA: "one unit of USD/CHF is equal to one dollar and one unit of EUR/USD is equal to one Euro"); so USD/JPY units = USD size ÷ 1, EUR/USD units = USD ÷ price, XAU/USD ounces = USD ÷ price, EUR/GBP units = USD ÷ (EUR/GBP × GBP/USD) — `usd_per_base_unit` implements exactly that, inverts a USD_XXX leg correctly, and returns None (⇒ zero, `no_usd_rate`) for a cross with no USD leg and for any non-`BASE_QUOTE` symbol (a futures ticker without an underscore sizes zero rather than guessing). USD-notional exposure and the currency-delta cap in dollars (`test_usd_base_notional_meets_the_currency_cap_in_dollars`) match the same referent.
2. **Per-instrument friction in price units (GAP-P12D-19)** — `(2·slippage + 2·commission) × units` is a quote-currency amount, converted once at the close rate: the correct treatment of spread-type costs declared in price units (`instruments.yaml`: EUR/USD 0.00002, USD/JPY 0.002). Caveat, not a finding: `commission_per_side` is 0.0 everywhere, so per-lot cash commissions (OANDA Core-pricing style) are unexercised; if ever declared they belong in account currency per lot, not price units — the C8 calibration step should say so.
3. **No look-ahead in the labeller.** The label is the regime classified *before* the tick that completed the bar (`label_bars` reads `regime_store` before `engine.observe(st)`), one tick more conservative than the runtime pairing in `PaperLoop.on_state` (classify, then AGON sees the completed bar); the classify cadence (first tick immediate, then ≥ `cycle_s` of event time per instrument) is textually the same rule as `PaperLoop._regime`.
4. **Warm-up length vs NVMA's windows is adequate.** `RegimeInputWindow` is per tick with `max_lookback = max(200, 200, 100) + 1 = 201` ticks; session medians need 30 samples per session; both fill within the first trading day, so `LABEL_WARMUP = 3 days` is ample (only 2012, the data start, labels cold). Year cut at UTC 1 January is applied identically by the labeller (`b.ts >= start`), `history(…, end)` and `plan_folds`, so no fold reads a bar at or after its `train_end`.
5. **DSR arithmetic itself matches the paper's Eq. (1)/(2):** per-period Sharpe, `sqrt(V)·((1−γ)Z⁻¹(1−1/N)+γZ⁻¹(1−1/(Ne)))`, `sqrt(T−1)`, skew and raw kurtosis; `test_reproduces_the_papers_numerical_example` pins SR0 0.1132 / DSR 0.9004 at N = 100. The defect in F-E1 is what is fed in, not the formula.
6. **Calendar folds match the ratified plan** (OOS_VALIDATION.md: 2-yr train / 1-yr test / 1-yr step over 2012→2024, 2024–2025 locked, graded once): `plan_folds(2014, 2023)` gives ten non-overlapping test years, `check_development` refuses any fold touching 2024, `begin_final` is an exclusive create.
7. **DST in session boundaries.** `BoundaryClock` and the moved `calendar_gates` resolve local wall times per date via `fx_clock.next_local`/`local_to_utc`; the test pins the 2025-03-09 US switch (Fri 22:00 UTC → Sun 21:00 UTC); the weekend filter in the loader is `fx_clock.in_weekend` (17:00 New York both ends). The moved gate bodies are textually identical to the removed methods.
8. **Seeds are reproducible** (`seed_for` = sha256(fold|regime|instrument)) and `test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read` shows 500 vs 600 available bars give identical records.
9. **Walk-forward efficiency is lost, but declared.** Pardo's WFE ("annualized_OOS_performance / annualized_IS_performance", https://www.luxalgo.com/library/concept/walk-forward-analysis/) cannot be computed once the in-sample block is not replayed; the report carries `in_sample = NOT_REPLAYED` and a caveat, so the read path is truthful. Noted, not a finding.

## Both-lenses items

- **Module legibility (GAP-P12M-01):** every new module is under budget — units.py 39, calendar_gates.py 34, book.py 160, harness.py 195, regime_labels.py 176, oos_plan.py 76, evolve_step.py 83, tick_stream.py 52, boundary_clock.py 41, build_labelled_bars.py 71; `capital_governor.py` 448 with the ratchet lowered 464 → 448; `tests/unit/test_module_budget.py` 3 passed (0.32 s).
- **Invariant density (GAP-P12M-02):** each new module opens with an invariants block. One stale mental model: `deflated_sharpe.py`'s DECLARED DEVIATIONS still say "N is the number of trial Sharpe ratios supplied" — false since `n_trials` lifts N — and do not declare the fold-variance construction (F-E1 fix).
- **Ledger closure:** `python scripts/ledger_check.py` → "157 entries checked; 0 violation(s)". Spot-audit of the new Residual lines: GAP-P12D-19 "Residual: none" is honest for friction (the commission-unit caveat above is outside its claim). GAP-P12D-22's residual names only GAP-0092; the unit-balanced pair rule (F-E2), the per-instrument contract size / lot semantics (F-E5) and the account-currency assumption (F-E7) are unowned by any live entry. GAP-P12D-18's residual names only GAP-P12D-03 (the runner); the warm-up loss (F-E3) and the test-tick embargo (F-E4) that its rulings created are unowned. These should become entries (or be added to the residual lines) at triage.

## Sources
- Bailey & López de Prado 2014, The Deflated Sharpe Ratio — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 ; https://metricgate.com/docs/deflated-johnson-sharpe-ratio/
- Purged/embargoed CV (AFML ch. 7) — https://quantmemo.com/concepts/purged-embargoed-cv
- Walk-forward efficiency (Pardo) — https://www.luxalgo.com/library/concept/walk-forward-analysis/
- Warm-up practice — https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods
- OANDA units — https://help.oanda.com/us/en/faqs/micro-lots.htm ; https://developer.oanda.com/rest-live-v20/order-df/ ; https://developer.oanda.com/rest-live-v20/primitives-df/ ; https://tessl.io/registry/tessl/npm-oanda--v20/3.0.3
- MT5 lots / gold contract size — https://hw.online/faq/understanding-0-1-in-metatrader-5-lot-sizes-and-contract-specifications/ ; https://forexvitals.com/articles/xauusd-lot-size
- Pairs trading dollar neutrality — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615 ; https://www.dothefinancial.info/pairs-trading/dollar-neutrality.html
- Reproductions: `scratchpad/repro_pair_notional.py`, `scratchpad/repro_dsr_hurdle.py` (session scratchpad; outputs quoted above).
