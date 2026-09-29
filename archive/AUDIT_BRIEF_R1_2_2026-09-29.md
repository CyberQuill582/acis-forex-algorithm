# AUDIT BRIEF — R1.2, the look register v2 (pinned 2026-09-29)

> **Pinned before launch (constitution A4).** The owner's go, in chat on 2026-09-29, answering the
> session's standalone ask: "Launch both now (Recommended)". This is the constitution's pair (A3),
> one agent per lens, on Opus 5 in fresh context.
>
> **What is under audit:** commit **`192c1fa`** on `main` (R1.2), against its parent `863e68e`:
> `git show 192c1fa`, `git diff 863e68e 192c1fa`. The register files are unchanged since then.
> - **The claim** (new): `tests/backtest/look_claims.py` — `Origin`, `Claim` (`declared_space_hash`,
>   `variant_hash`, `universe_id`, simulator, `recon_commit`), `canonical_hash`, `cost_map_hash`,
>   `refuse_repeated_llm_variant`, the cycle row (`cycle_line`), and the content-addressed daily vector
>   (`store_vector`, `load_vector`).
> - **The register** (changed): `tests/backtest/look_register.py` — a real-data look refuses to register
>   without its claim; one append path for looks and cycle rows (`_append`); `register_cycle`;
>   `record_outcome(..., daily=)`; counting skips cycle rows.
> - **The gate** (moved): `tests/backtest/look_gate.py` — `begin_grade`, moved out of the register for the
>   A12 budget.
> - **The callers:** `scripts/run_oos_validation.py` (new `--origin`, `--model-id`, `--model-cutoff`,
>   `--reference`, `--published`, `--recon-commit`) and `tests/backtest/oos_runner.py`.
> - **The tests:** `tests/backtest/test_look_claims.py` (new), `tests/backtest/test_look_register.py`.
>
> **The authority.**
> - The spec: `specs/ACIS-09-BACKTEST_VALIDATION.md` **C-BT-11 v2 step 1 (Registration)** and the parts of
>   steps 2–3 the register must support (the cycle's α budget, "at most one cycle a quarter", ≤ 5
>   family-versions); master `ACIS_SPEC.md` §5.6/§14 as v2.22 amends them (R1-D13, the LLM contamination law).
> - The design as FINDER evidence, not authority: `CLOUD_AUDIT/reports/r1/PLAN_R1.md` (the R1.2 row).
> - The ledger: `KNOWN_GAPS.md` GAP-P12D-98 (mitigated, R1.2's entry), 64, 66, 89, 100.
>
> **The lead's claims — re-verify them; they are not settled:**
> - the full suite at `192c1fa` gives 1057 passed, 6 skipped on the server;
> - the eight proof tests named in GAP-P12D-98 pass and test what their names say;
> - `look_register.py` is 290 lines, under the A12 budget.
>
> **Declared choices the lead made — attack them:**
> - `variant_hash` excludes the family's NAME, so renaming a family cannot launder a repeat;
> - the LLM-repeat refusal applies to LLM-origin plans only; a human plan may repeat a variant;
> - cycle rows sit in the same hash chain as looks and are skipped by counting;
> - "one cycle a calendar quarter" — by which clock and boundary;
> - the daily vector is stored once by its content hash; the outcome carries only the hash;
> - **the single `evaluate(plan, tier, span)` entry point is DEFERRED to R1.3** (GAP-P12D-98's residual), so
>   today a graded number reaches the register through `oos_runner` / `run_oos_validation.py` only —
>   is that true, or does another path grade real data without a register line first?

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit or run git commands that write. The lead works on the demo adapter in the same tree, so read the audited state with `git show 192c1fa:<path>`, or diff against it. Never trust the working tree to equal `192c1fa`.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite or any probe that does real work locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of `192c1fa`: `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/688e2ed6-575e-479f-a856-d4e3a1e59865/scratchpad/remote_audit_r12.sh" <internal|external> "<command>"`.
  - Put probe scripts in `…/scratchpad/audit_r12/<internal|external>/probes/` (they ship on each call) and run them as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - Reading files and quick `grep`s locally are fine.
- **Refutation (A6).** Every finding is reproduced by a script on the server and cites `file:line` at `192c1fa` (internal lens), or quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps against the spec, hollow or weakened tests (A16), A12 size and legibility (a module over 300 lines; a missing one-screen mental model in an invariant-bearing module), A13 hygiene (a read-path claim the code or the ledger contradicts; spent scaffolding), and ledger closure (`python scripts/ledger_check.py` green, plus a spot-check that GAP-P12D-98's residual honestly owns what is unbuilt). Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_R1_2_INTERNAL_2026-09-29.md`; EXTERNAL writes `archive/AUDIT_R1_2_EXTERNAL_2026-09-29.md`. That file is your ONLY repo write. Its shape: an executive summary; findings (ID, Severity/Likelihood, reproduction, proposed fix); honest negatives; what you could not verify; residual risk. The lead triages it into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **Hash determinism and collision.** Can the same plan hash two ways (float repr such as 0.1 vs 0.10, dict or list order, unicode, a Decimal vs a float, a tuple vs a list)? Can two different plans share a hash? Is the declared space's instrument list order-sensitive where it should not be, or order-blind where order matters?
2. **The LLM-repeat refusal.** Can a repeat be laundered: a changed universe id for the same instruments, a cosmetic parameter change, a human origin on an LLM plan, a different model id, a case change? Does the refusal read the whole chain, including lines written by an older register version?
3. **Cycle rows.** Are ≤ 5 distinct family-versions, α in (0, 0.05], a unique id and one cycle per quarter all enforced, and on which clock? Is "written before any stage-A look of that cycle" enforced, or only documented? Does anything other than counting read the chain and mis-handle a cycle line?
4. **The hash chain.** One `_append` path for both kinds: is `prev_hash` continuous across kinds? What does a truncated last line, a concurrent writer, or an old-format line do?
5. **The daily vector.** Stored once, refused if edited: are dates and returns aligned, sorted and unique? Are NaN or inf refused? Is the serialisation byte-stable across platforms? Can a vector be swapped for another with the same hash?
6. **The claim requirement.** Which looks count as "real data"? Can a real-data grade be registered as synthetic, or with a blank family, to skip the claim? Do `run_oos_validation.py`'s defaults ever write a claim the operator did not state (for example a default origin)?
7. **Register-first, repo-wide.** Enumerate every producer of a graded number on real data (`oos_runner`, `scripts/run_oos_validation.py`, the cost-stress ladder, `falsify_engine`, anything else) and check which write their register line BEFORE grading. C-BT-11 v2: "A graded number exists only if the look register wrote its line first."
8. **The move of `begin_grade`.** Is its behaviour unchanged? Are the tests still testing the moved code, not a stale copy?

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces 1, 2, 3, 4, 5 and 7.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch only):** the design and the implementation against the outside world.
  - Canonical JSON for hashing: RFC 8785 (JCS) and the known pitfalls of hashing floats serialised by Python's `json`.
  - Pre-registration and trial-counting in quantitative finance: Harvey, Liu & Zhu (2016); Bailey & López de Prado on the Deflated Sharpe Ratio (what "a trial" must include); White (2000) and Hansen (2005) on data snooping.
  - Look-ahead bias in LLM-generated research ideas: the LLM knowledge-cutoff contamination literature (for example Sarkar & Vafa 2024; Glasserman & Lin 2023). Does recording model id + cutoff actually support the contamination law as stated?
  - Budgeting α across sequential research cycles: alpha-spending and alpha-investing (Foster & Stine 2008; Javanmard & Montanari 2018). Is "≤ 5 families, α ≤ 0.05, one cycle a quarter" a controlled procedure, and what does it control?
  - Append-only, hash-chained logs as audit evidence (tamper evidence vs tamper resistance): what does this register actually prove to an outside reader?
