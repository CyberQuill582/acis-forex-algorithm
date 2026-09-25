# AUDIT BRIEF — the R1 spec amendments, master v2.21 (pinned 2026-09-25)

> **Pinned before launch (A4).** These are the constitution's TWO lenses, and ONLY those two (owner directive
> 2026-09-24). The owner launched them explicitly on 2026-09-25.
>
> **What is under audit:** commit `271d8e0` on `main`. It is a SPEC change: master v2.20 → v2.21, ACIS-03
> v1.5 → v2.0, ACIS-04 v1.2 → v1.3, ACIS-09 v1.6 → v1.7, `tests/backtest/OOS_VALIDATION.md`, `BASELINE.md`
> (a re-baseline entry), CLAUDE.md engineering rule 5, and `specs/ACIS-00-INDEX.md`. It changes no code.
> Get the exact change with `git -C <repo> show 271d8e0 -- ACIS_SPEC.md specs/ tests/backtest/OOS_VALIDATION.md
> BASELINE.md CLAUDE.md`.
>
> **Where it came from:**
> - the owner ratified the R-1 DIRECTION, then every recommendation R1-D1..D14 ("i ratify all your
>   recommendations for R1-D1 to D14");
> - the drafts, the lead's verification and its seven disagreements (X1–X7) are in
>   `R1_LEAD_REVIEW_2026-09-25.md`;
> - the source proposal is the cloud's `CLOUD_AUDIT/reports/r1/PLAN_R1.md` (finder evidence, same model lineage);
> - the lanes' evidence is in `CLOUD_AUDIT/reports/r1/`.
>
> Read the diff FIRST. Read the review and the plan only after you have formed your own view (A4).
>
> **Ledger:** GAP-P12D-86..102 and GAP-P12D-33/64/67/68/71, in `KNOWN_GAPS.md`.

## The law (the finding bar)
- **Guard integrity (CLAUDE.md).** No guardrail value, equity floor, or HALT/veto semantic may change. The
  amendment claims it changes none, and that it keeps the NVMA `tradeable=False` veto whole, including
  `confidence < 0.55`, which the plan's A7 list dropped. **Try to break that claim first:** find any text under
  which a trade now passes that v2.20 refused for SAFETY reasons, as opposed to validation reasons.
- **Two deliberate loosenings were owner-ratified, and they are NOT findings by themselves:**
  - A6: §14's Sharpe, win-rate, profit-factor, positive-months and duration rows are reported, not gated;
  - A2: the DSR ≥ 0.95 `passed` gate is replaced by the register-aware verdict.

  A finding is where they loosen MORE than ratified, or where the replacement is weaker than it claims.
- **"The as-built code keeps the stricter path until each build phase lands."** Check that every spec rule
  the code does not yet implement really leaves the code stricter, never looser, in the meantime.

## Rules for both auditors
- **Fresh context and model.** You run in fresh context on Opus, as a finder, not a clearer (A5). Attest to
  both. No subagents, and no grandchildren.
- **Never modify the repo.** Work in `SCRATCH/<your-name>/`, where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
  Export trees with `git -C <repo> archive <rev> | tar -x -C <dir>`. The base for comparison is `271d8e0~1`.
- **Refutation (A6).** Reproduce every finding with a script or an exact quote (internal), or quote it with a
  dated URL (external). Mark unreproduced claims *unconfirmed*. Honest negatives are first-class.
- **Web budget:** ≤ 30 WebSearch/WebFetch calls for EXTERNAL, ≤ 5 for INTERNAL. This budget is shared with
  every agent in the session.
- **Laptop.** This laptop loses power without warning (GAP-P12D-76), so write your report early and keep
  updating it.
- **Your ONLY repo write** is your report: `archive/AUDIT_R1_AMENDMENTS_{INTERNAL,EXTERNAL}_2026-09-25.md`.
  Rank findings by severity, and propose a ledger entry for each (no IDs: the lead mints them).

## INTERNAL lens — is the amended spec consistent with itself and with the code?
1. **Contradictions.** Does any amended text contradict text that was not amended? Check master §2 (the table and
   the priority list), §4, §5, §5.5, §5.6, §5.7, §9.5, §13, §14 and §15; ACIS-02/03/04/05/06/09/11; CLAUDE.md;
   BASELINE.md; OOS_VALIDATION.md. In particular:
   - the §2 diagram and the import contract (`tests/unit/test_import_contract.py`) against "RULE PARAMETERS";
   - C1/C2 staging language against the "legacy until R1.7" framing;
   - §5.7's lifecycle against "no evolutionary search";
   - ACIS-11's attempt registry against the look register;
   - the §15 live gate ("§14 minimums") against the claim ladder.
2. **"Stricter meanwhile."** For every rule the code does not yet implement, show the as-built behaviour is
   stricter or equal, or construct the case where it is looser. Examples: `report.py` gates; DISCARD_OPPOSITE
   against netting; the 2-year window against expanding; lot rounding in the research path.
3. **Testability.** Is every new invariant (C-BT-11 v2 stages A–D, C-BT-12, the kill-only plateau, the
   live-eligibility rule, the execution clock) stated precisely enough to test? Find the ambiguous ones.
   Examples: which family is "primary" in the fixed-sequence order, and who registers the order; how σ* is
   declared; what "the development span" is for a fixed family's plateau check.
4. **Numbers.** Re-derive the numbers the text states from their stated inputs: the fixed-sequence bar
   0.50–0.52; the held-out draw from the salt, using `CLOUD_AUDIT/reports/r1/evidence/R1B/probe_holdout_draw.py`
   or your own code; the e-process definitions.
5. **Constitution items:** `python scripts/ledger_check.py` green; the read path contains no claim the new text
   contradicts (README → STATUS → TODO → CLAUDE → ACIS_SPEC → specs/ACIS-00-INDEX → KNOWN_GAPS); every pointer
   the change added resolves; no spent narrative was left in the live read path.

## EXTERNAL lens — is the amended spec true to the world and to its cited sources?
1. **The trend family.**
   - EWMAC (16,64)/(32,128)/(64,256) and the breakout form: is the text faithful to Carver (*Systematic Trading*,
     2015; *Leveraged Trading*, 2019) and to his published forecast scalars and FDM?
   - The MOP-2012 12-month sign: faithful to Moskowitz–Ooi–Pedersen 2012?
   - The "cost ≤ ⅓ of pre-cost Sharpe" speed limit: faithful to Carver?
   - Is the 17:00 New York decision time right for the instruments named?
2. **The statistics.**
   - Fixed-sequence (gatekeeping) vs Holm: is FWER control as claimed, under the dependence among families?
   - The Sharpe lower bound SR̂ > z/√Y: is its se approximation acceptable for daily returns with fat tails and
     autocorrelation (Lo 2002)?
   - PBO ≤ 0.20 (Bailey et al.); max-t over a declared grid (White / Romano–Wolf);
   - Is the e-process construction (E1/E2/E3) a valid test martingale as written (Ramdas et al.; Shafer–Vovk)?
     Check the clipping at −1, and σ* declared in advance.
   - Is "residualise the held-out instruments, kill-only at t < −0.5" sound?
3. **The venue facts the text relies on.**
   - FTMO's gap-trading clause and trading hours;
   - FTMO's swap table (`https://ftmo.com/wp-json/ftmo/symbols`) and contract sizes;
   - the minimum lot;
   - E8 One/Pro swap-free;
   - the 17:00 New York rollover spread.

   Re-fetch; do not trust the review's quotes.
4. **The synthetic-lab law.**
   - Is "a demeaned random walk is a bridge that plants mean reversion" correct?
   - Does the ±1-sign fix make every non-anticipating rule's expected gross P&L exactly zero?
   - Is "variance-matched within 1 ± 0.05" the right control?
5. **A spec that is wrong about the world is a finding,** even where the text is faithful to the plan.

Report sections for both lenses:
- attestation;
- findings, ranked;
- honest negatives;
- what you could not check;
- proposed ledger entries.
