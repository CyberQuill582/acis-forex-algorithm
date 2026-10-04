# TOURNAMENT spec proposal: forward evidence for many families at once (2026-10-03/04)

**Status: a PROPOSAL for the owner.** Nothing here changes `ACIS_SPEC.md` or `specs/`. Each item below is either implemented as the code's pre-registered default (marked *default*) or is only raised (marked *ruling needed*). The lead triages it and batches any spec change into one master version.
**Context:** `archive/TOURNAMENT_REPORT_2026-10-03.md`. Ledger: GAP-P12D-158.

## P-1. Stage D needs a multiplicity clause when several families run forward together (*ruling needed*; code default = P-1a)

ACIS-09 C-BT-11 v2 step 7 makes E1 ≥ 20 "edge shown" **per family**. Six families now run forward in parallel, and the capacity is 20. With all of them null, a per-family E1 ≥ 20 gives a family-wise false "edge shown" rate of up to N × 5% (Ville's bound, applied N times).

- **P-1a (code default, `tests/backtest/tournament_rule.py`):** each entry gets α_i = 0.05 / capacity (0.0025). It is "eligible for owner review" only when **all** of these hold:
  - the milestone-D screen passes (P-4);
  - **either** a weighted Holm test across the capacity rejects, using one-sided Newey–West HAC p-values evaluated **only** at 126, 252 and 504 forward days, with Bonferroni over the three looks;
  - **or** E1 ≥ 1/α_i = 400 (e-Bonferroni, which stays valid however often anyone looks).
- **Why capacity and not the current count:** with the count, adding an entry would tighten the bar for the entries already there, and retiring one would loosen it. Fixing the family size in advance removes both effects. An entry's α is spent when it is registered and is never recycled.
- **What it costs in power (the bar a look must clear):**

| Look | Net annual Sharpe needed (P-1a) | One family alone, 3 looks |
|---|---|---|
| 126 days | 4.45 | 3.01 |
| 252 days | 3.14 | 2.13 |
| 504 days | 2.22 | 1.50 |

  No realistic edge (0.3–0.8) can be *certified* on two years of forward data, whichever correction is used. Master §14 already says that "edge shown forward" at a true Sharpe of 0.5 takes about two decades.
- **Alternatives the owner may prefer:**
  - **P-1b:** FDR control (e-BH, Wang & Ramdas 2022, at q = 0.10). This is more lenient: it accepts that about one in ten "eligible" entries is false.
  - **P-1c:** a smaller capacity (for example 10, which needs a Sharpe of 2.03 at 504 days).
  - **P-1d:** keep the per-family E1 ≥ 20 and state that it is not corrected for the tournament.

## P-2. E2's claim units (*default*, needs ratification of the reading)

The spec gives "μ_claim = (SR̂_dev/2)·σ*, a daily return". If SR̂_dev is the development look's **annual** Sharpe, μ_claim is too large by a factor of √252: for GOTOBI it would be a claimed mean of 0.9 × 0.11% per day. The code reads SR̂_dev as the **daily** Sharpe, SR_ann / √252, which keeps the units consistent. Ratify this reading or correct it.

## P-3. σ* for a family with no volatility target (*default*)

Stage D defines σ* as "the declared DAILY volatility target". The event books (REBAL, GOTOBI, HALLOWEEN) have no target. Each entry therefore declares, before its first forward day, the realised daily standard deviation of its development look's stored vector: REBAL 0.0045781, GOTOBI 0.00111398, HALLOWEEN 0.04144645. The RSIM families (D1, HEDGEP, FXVALUE) use 0.20/√252.

## P-4. Milestone D, made honest (*ruling needed*)

The owner ruled (2026-10-03) that the first win is a forward net Sharpe ≥ 0.5 over 6 months, with no paid challenge before it.

- **The problem:** over 126 days, a family with **zero** edge shows a net Sharpe ≥ 0.5 with probability 0.36. At least one of six does with probability 0.93.
- **Proposed reading:** D is a **spending gate**, never evidence. The code reports it as "Screen D (NOT evidence)", always beside its two luck numbers:
  - P(one zero-edge family looks this good);
  - P(at least one of N does).
- **Proposed rule:** a paid challenge needs D **plus** either P-1's significance, or the owner's explicit acceptance of the luck number shown that week.

## P-5. The tripwire as written may void every family (*ruling needed*)

"A day beyond −6σ* … W := 0 permanently." On the development vectors, measured against the same σ* conventions, the worst day was:

| Family | Worst day |
|---|---|
| REBAL | −8.5σ* |
| GOTOBI | −8.1σ* |
| D1 | −5.5σ* (σ* = vol target; −6.6σ against its realised sd) |

So with fat tails, the tripwire is likely to fire within a forward record's life and void E1 permanently. The code applies it **as written**.

- **Options:** keep it; set the multiple per family from its development tail (for example 1.5 × the development minimum); or make a tripwire freeze scaling instead of voiding.

## P-6. The look register cannot hold a stage-D look of an LLM variant (*ruling needed*; blocks registering forward looks)

`look_claims.admit_claim` refuses an LLM-origin claim that repeats a registered `variant_hash` on any tier except the holdout ("an LLM plan repeats registered variant", §5.6 R1-D13). Master v2.35 amended this for stage C only. A forward look of D1, REBAL, GOTOBI or the FACTORY three is therefore refused today.

**Proposed amendment (mirroring v2.35 (3)):** each registered variant may take its pre-registered forward looks (P-1's 126/252/504) on tier 4, kill-or-certify per stage D.

**Interface for the lead to register them:** the look line carries:
- the SAME claim as the kill look (family, variant, origin, universe, cost map);
- a source with `provenance = "real"` named `acis-forward-record`, plus the record's chain head at grading;
- one fold `[forward_start, the look's day]`, tier 4 by `look_tiers` (test window ≥ 2026-07-01);
- an outcome that stores the record's rows for that window as the daily vector.

The forward record is the evidence, and the look line is the act of grading it. The register stays FACTORY's/the lead's to write.

## P-7. Forward data source, declared (*default*)

- **Hourly candles:** the history looks used Dukascopy's monthly hourly files, which appear on the 2nd of the next month. From EPOCH (2026-10-01) the store builds hours from each UTC day's 1-minute files: the first minute's open, the last minute's close, traded if any volume. On September 2026 these matched the hourly file on 95.4% of EUR_USD's traded hours' closes and 95.8% of US500's; the rest differed by ≤ ~1.5 pips. The 2026 months before EPOCH use the monthly hourly files. Sources are never mixed within a period.
- **Point in time:** inputs freeze per date, and later prints are logged as revisions, never applied:
  - the overnight rates freeze at today − 2;
  - the S&P close, Treasury yield, ECB fixings and CFTC report freeze at their last print;
  - BIS CPI freezes at month − 5.

  This is the live engine's forward-fill rule, not the looks' final-data convention.

## P-8. Calendar and envelope facts the forward period needs (*default*; the lead ratifies)

- `jp_days` now vouches for 2026–2027, from the Cabinet Office list. It refuses 2028 until refreshed.
- `universe.py`: JP225's scale envelope is widened to 120,000; the Nikkei passed 60,000 in 2026-04. US500's ceiling of 8,000 and gold's of 9,000 will need the same review as prices rise.
- FXVALUE's registered rule is undefined when a CPI print is missing (the US skipped 2025-10). The forward book computes ranks only from its forward start. The same hole recurs at m − 64 = 2025-10 (decisions in 2031-03).
