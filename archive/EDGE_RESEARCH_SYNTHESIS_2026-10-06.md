# Edge research synthesis — lead triage of agents A and B (2026-10-06)

Ledger: [[GAP-P12D-161]]. Brief: `archive/EDGE_RESEARCH_BRIEF_2026-10-05.md`. Reports: `archive/EDGE_RESEARCH_A_SUPPLY_2026-10-05.md` (what to trade), `archive/EDGE_RESEARCH_B_FACTORY_2026-10-05.md` (how to keep finding, checking and retiring edges). Both ran as Fable 5.1 in a fresh context. Everything they propose is LLM-origin (§5.6): history can only kill it, and credit comes only from the forward record.

## Where the two agents agree (two angles, one answer)
1. **The supply of single published anomalies is used up for this venue.** Every family we tested paid 1–20 bp a trade against a 2–4 bp CFD round trip, and its payer could reprice. The four holdout results that showed no edge were really one event: 2024–25 was a strong rally and a bad year for trend.
2. **Breadth is the only lever, and equal risk is the right way to combine.** Neither a bandit nor an optimiser nor regime weighting beat equal risk in B's simulation (Thompson sampling 0.22 against equal risk 0.38).
3. **Six months of forward data cannot certify an edge.** A true Sharpe of 0.5 needs about 25 years for 80% power. Milestone D lets a dead strategy pass 36% of the time. The 2027-04 review can only decide "killed", "not killed", or "spend, accepting the luck odds".
4. **Decay cannot be detected fast at this signal-to-noise.** The fast guards are the plumbing checks, the tripwire and E3 (the cost check on real fills: specified in ACIS-09 step 7 and **never built**).
5. **What would change the picture:** rules of the owner's own (human origin, so history can certify them), a funded notional of $100k or more (so breadth is real: at that size D1 can hold all 21 CFDs), a rates sleeve, and forward data rather than more history.
6. **Honest odds:** A puts a lasting forward net Sharpe of 0.5 or more by end-2027 at about 20–25%, and 0.65–0.85 at under 10%. A book of about 0.3–0.45 is the realistic ceiling of what we have.

## Lead verification (closed form, `statistics.NormalDist`)
| Claim | Agent | Closed form | Verdict |
|---|---|---|---|
| A true Sharpe of 0.4 prints ≤ 0 over 2 years 29% of the time | A | 0.29 | holds |
| 6 streams at 0.2 with ρ 0.1 → 0.40 | A | 0.40 | holds |
| A Sharpe of 0.5 needs about 25 years for 80% power | B | 24.7 (one-sided, α 0.05) | holds |
| Milestone D passes dead 36%, 0.5 49%, 1.0 63% | B | 0.36 / 0.50 / 0.64 | holds |
| Stage C kills dead 31%, live-at-0.5 11% | B | 0.31 / 0.11 | holds |
| 10×0.3 → 0.95 (~10 y); 6×0.5 → 1.22 (~6 y) | B | 0.95 (6.9 y); 1.22 (4.1 y) | Sharpe holds. B's years are ~1.5× longer (its fat-tailed simulation or a stricter α); conservative, and the conclusion stands |

Not verified by the lead: the CUSUM detection rates and the Thompson-sampling result (B's script `power_math.py` on the stopped VM `/opt/acis/edge-B/`, also in the session scratchpad); the literature citations (Gençay 2026, Falck–Rej–Thesmar 2022, Chordia et al. 2020; the CUSUM "40 months" figure is grade (b), taken from search summaries); E8 One's fee (UNCONFIRMED).

## Where the lead disagrees
- **A's C2 TREND-BREADTH (D1 on all 21 instruments, expected 0.15–0.30) is not supported by our own record.** That exact family scored **−0.12 (t −0.40)** on 2012–2023 and was shelved; it survived only because the kill line is t < −0.5. Lead: do not forward it unless the owner wants it as a breadth bet at prop notional, knowing it has a negative history.
- **B's "pooled book as the PRIMARY endpoint at full α" is a spec change [SPEC].** The owner's plan item 2 (one equal-risk combined-book entry, registered before its first exposure) needs no spec change and gets most of the benefit now.

## Corrections to earlier files (from A, accepted as stated, not independently re-fetched)
- The rule that "accounts of $50,000 and above must trade fully manually" in `RESEARCH_PROP_VENUES_2026-09-24.md` is **FundedNext's, not E8's**. E8 One allows EAs at $50k/$100k/$150k (one strategy per user).
- Pepperstone's CFD forwards cover only Brent, WTI, gold and silver, so commodity carry has two usable instruments at most.

## Gaps B found in the machinery (verified by B in the repo)
E3 is specified but not built. The forward record grades Dukascopy-simulated P&L, never fills. The event book shapes have no lab-calibration requirement. No pooled-book entry exists yet. The weekly report prints the luck odds but no evidence-weight line. FXVALUE (0.07) sits in the record as its own entry.

## Decisions for the owner (lead's recommendation first)
1. **Combined book:** register the equal-risk combined book as one forward entry now (plan item 2, no spec change). The PRIMARY-endpoint rule waits for the next spec version.
2. **RATES (A's C3, EWMAC on the 2/5/10/30-year par yields):** one pre-registered kill-only look. The yields are already on disk and the look needs no venue. Expected net 0.20–0.35 if alive.
3. **Cheap report-only builds after the cutover:** B2 (an evidence-weight line beside the luck odds) and B3 (per-entry CUSUM decay flags, report-only, so no spec change). Then B5 = E3 once real fills exist.
4. **TREND-BREADTH:** hold (see above).
5. **Admission card (B4) and the 2027-04 review as a kill review with a decision table (B8):** draft for the next spec version.
