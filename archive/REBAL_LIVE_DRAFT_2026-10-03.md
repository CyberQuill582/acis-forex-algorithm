# REBAL v1a live — the forward path (DRAFT for owner ratification, 2026-10-03)

**Status:** DRAFT. Nothing here binds until the owner ratifies it at build time, AFTER the 2026-10-15..17 AWS cutover (owner ruling 2026-10-03, "Spec now, build after cutover"). On ratification it is applied as one master version (ACIS-04 §4b's second decision clock, ACIS-05 §6.4's sizing for an index CFD, ACIS-13's US500 onboarding) and built, then audited at that milestone.

**Why:** REBAL v1a (the paper's 60/40 rebalancing position on US500) survived its kill-only look at a net Sharpe of 0.50 (HAC t 1.82), uncorrelated with D1 (−0.005) (GAP-P12D-157). It is LLM-selected, so only forward data can credit it (§5.6). v1b (minus the note) is not forwarded: 0.97 correlated with v1a, and only Pepperstone lists the note.

**Unchanged (and unreachable by anything here):** `config/guardrail_limits.yaml`, the equity floor, HALT/veto/resume semantics, the live gate (rung 2 + human sign-off), D1's 17:00 New York path.

---

## 1. What the registered family fixes (restated)

The paper's equations (`tests/backtest/rebal.py`): two simulated 60/40 portfolios (Threshold over δ = 0..2.5%, Calendar at month-end), the position mean(−Threshold/1.5%, Calendar term), held close to close on US500, swap-free. The graded look computed the signal from the same close it traded at: the paper's convention, and an idealization a live engine cannot meet.

## 2. The live departures (each a proposed ruling)

- **L-1 Decision clock.** One decision per NYSE session at **15:50 America/New_York** (12:50 on the NYSE's 13:00 half days), from live prices; the fill is a market order by **15:58**, never after the close. A missed window is skipped, never caught up (the target loop's rule).
- **L-2 Equity input.** The US500 CFD's mid at the decision, against the previous session's decision mid, replaces the S&P cash close-to-close return in the drift. The state is recomputed each decision from the last 260 sessions of the venue's own M1/H1 history, starting at 60/40 (a band resets within months, the Calendar portfolio monthly), so a restart re-derives the same position.
- **L-3 Bond input.** The latest published Treasury par 7-year yield (the issuer's file, fetched daily with the existing macro timer) gives the bond return. It lags one session, because the Treasury publishes after the close; the bond term moves the weight about a third as much as equities. Every venue can trade this version; no note CFD is needed.
- **L-4 Size.** The position × the account's `capital_ref` ($10k on the demo), in US500 lots at the venue's contract size and minimum lot (verified at attach, fatal on a stricter venue); the minimum lot is a natural no-trade band. All existing guards apply (cluster and currency caps with G-5 headroom, VaR, the daily loss, halts), plus the 10 × daily-ATR disaster stop (R6-2).
- **L-5 Weekends and gaps.** v1a holds over weekends like the graded book. Check the prop venue's weekend and gap rules before any prop account (GAP-P12D-58, GAP-P12D-95); the Pepperstone demo has no such rule.
- **L-6 The record.** The forward record is graded against a replay of the SAME live rule (stage D: L-1's clock on M1 history); the shadow book and `scripts/demo_report.py` report it beside D1.

## 3. Before the build (P&L-blind)

- Re-grade the live rule's timing on history once, as its own kill-only look, on 1-minute US500 candles (the download IMOM needs; GAP-P12D-158), so the forward version is a registered family-version, not the closing-print idealization.
- Onboard US500 on the demo: venue symbol, contract size and lot step at attach, the provisional C8 costs measured against the venue, the rulebook hash attested by the owner.
- The owner checks the demo's index contract size (the research's binding cost unknown for intraday sleeves, harmless at one decision a day).

## 4. Rulings to ratify at build time

L-1 (15:50 decision, fill by 15:58), L-2 (CFD mid as the equity input; 260-session recompute), L-3 (one-session-lagged Treasury 7-year yield), L-4 (one-lot sizing on `capital_ref`, every guard), L-5 (weekend holding; prop rules checked before any prop account), L-6 (stage D on the live rule). Plus: v1b is not forwarded.
