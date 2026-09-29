# R1.2 audit, the INTERNAL lens (spec against code, code against itself). 2026-09-29

- **Brief:** `AUDIT_BRIEF_R1_2_2026-09-29.md`, pinned before launch (A4).
- **Under audit:** commit `192c1fa` (R1.2, register v2) against its parent `863e68e`. The audited files (`look_claims.py`, `look_register.py`, `look_gate.py`, their tests, `run_oos_validation.py`, `oos_runner.py`, `harness.py`) are byte-identical at HEAD `355c27f`, so every finding below also holds at HEAD. C-BT-11 v2 step 1 and stage A's α text are unchanged in ACIS-09 v1.9.
- **Auditor:** Claude Opus 5.5 (`claude-opus-5-5[1m]`), fresh context, launched no agents. I am a **finder, not a clearer** (A5). A short list here is not a sign-off.
- **Method:** I read the audited state with `git show 192c1fa:<path>`. Every run went to the Google compute server (`acis-compute-1`, my own checkout of `192c1fa`, Python 3.11.2) through `remote_audit_r12.sh internal`, using the probe scripts `p1`–`p10` in the session scratchpad (`audit_r12/internal/probes/`). Each finding's reproduction is restated inline so it survives the scratchpad. Line numbers are at `192c1fa`.

## Executive summary

The lead's three claims hold:
- the full suite at `192c1fa` gives **1057 passed, 6 skipped** (66.5 s, `-n 8`);
- the eight proof tests named in GAP-P12D-98 all pass;
- `look_register.py` is **290 lines** (`look_claims.py` 159, `look_gate.py` 49), and the budget ratchet is green.

The `begin_grade` move is faithful: the body is identical modulo `lr.` and indentation. The hash chain is continuous across both line kinds.

But the register records **self-described text**, not what the plan is, and it binds that text to almost nothing. The eight proof tests are green, yet six hand mutants of the code they prove survive them.

**15 findings: 1 high, 9 medium, 5 low.**

The two that matter most:
1. **R12I-04 (high).** The cycle row's defining property is "written before any stage-A look of that cycle". It is **documented, not enforced**. A cycle can be registered after every one of its members was graded, with the winner first. Looks do not name their cycle, and the order's entries are not validated. The shipped proof test itself registers a cycle after its first member's look.
2. **R12I-01 + R12I-02 (medium).** The §5.6 / R1-D13 LLM-repeat refusal is laundered by cosmetic re-declaration. Reordering the instrument list, reordering the grid, writing 8 as 8.0, adding a space to the formula, changing case, relabelling the universe id or changing Unicode normalisation all pass as a "new" plan (9 of 9 reproduced). Relabelling the origin as `human` also passes, even with the LLM's own model id recorded on the line.

The other medium findings:
- **R12I-03:** the claim is not bound to the run it claims.
- **R12I-05:** the α-spending schedule is not enforced.
- **R12I-07:** the cost-map hash omits the swap/financing inputs.
- **R12I-08:** outcomes and daily vectors are not bound to their look.
- **R12I-10:** the proof tests are hollow on 6 mutants.
- **R12I-11:** R1-D13's graveyard-motif refusal, its declarative-plan shape and C-BT-11 v2's void rule are unbuilt AND unowned. `ledger_check.py` is green, but the spot-check fails.
- **R12I-12:** `Backtest.run` grades REAL data with no register line. Reproduced on the repo's real Dukascopy hour.

## Findings

### R12I-01: the LLM-repeat refusal is laundered by any cosmetic re-declaration of the same plan
- **Severity:** medium · **Likelihood:** high (an LLM re-proposing an idea rewords it by nature)
- **Where:**
  - `look_claims.py:87-91`: `variant_hash = canonical_hash([declared_space_hash, variant, universe_id])`.
  - `:38-39`: `canonical_hash` is `json.dumps(sort_keys=True)` over free-form Python values.
  - `:110-115`: the refusal compares those hashes.
- **The authority:** master §5.6 R1-D13 says a plan is "a rule id, ≤ 3 literature-fixed parameters, a fixed combination and a universe id", and "a plan that duplicates … a registered `variant_hash` is refused". The docstring (`:89-90`) claims the hash is "what the plan IS, not what it is called". It is what the plan is **written as**: a free-text formula, a free-text universe label and an ordered instrument list.
- **Reproduction (p1 §1 and §3).**
  - Setup: register an LLM claim over `SPACE = {grid: {fast: [8,16,32]}, formula: "sign(ewmac fast/4fast)", instruments: [EUR_USD, USD_JPY]}`, universe `R1-23`, variant `fixed`. The control (same plan, renamed family) is correctly REFUSED.
  - Then the same plan re-registered under a new family was **ACCEPTED** 9 of 9 times:
    - instrument list reversed;
    - grid `[32,16,8]`;
    - grid `[8.0,16.0,32.0]`;
    - formula with a doubled space;
    - formula upper-cased;
    - universe `r1-23`;
    - universe relabelled `R1-23-bis` (same instruments);
    - variant `Fixed`;
    - formula in NFD instead of NFC Unicode.
  - Each got a new look id. Equal as they should be: dict key order, tuple vs list, `0.1` vs `0.10`.
- **Proposed fix:**
  - Hash a canonical STRUCTURE, not prose. Use a typed plan with the rule id drawn from a closed registry, and named parameters with normalised numeric values (reject or normalise an int/float mix).
  - Treat the combination and the instruments as sorted, de-duplicated SETS, and resolve `universe_id` to its instrument set through a universe table.
  - NFC-normalise and case-fold identifiers.
  - Keep the formula text as an annotation outside `variant_hash`.
  - Pin it with a property test in which each cosmetic variant above hashes equal.

### R12I-02: an LLM-registered variant re-registers as "human", even carrying the LLM's model id
- **Severity:** medium · **Likelihood:** medium
- **Where:** `look_claims.py:110-112` (`if claim.origin.kind != "llm": return`) and `:50-59` (the Origin accepts `model_id` / `model_cutoff` on any kind).
- **The authority:** master §5.6 applies the contamination law to hypotheses "LLM-originated or LLM-refined". That is a property of the hypothesis, and the chain already records it.
- **Reproduction (p1 §4).** Register an LLM plan (000001). Then:
  - the same variant with `Origin("human")` under a new family is **ACCEPTED** (000002);
  - the same variant with `Origin("human", model_id="claude-opus-5-5", model_cutoff="2026-06-01")` is **ACCEPTED** (000003).

  The chain now shows origins `llm, human, human` for one `variant_hash`. A verdict that reads the line's origin would credit 000002/3 on pre-cutoff data.
- **Proposed fix:**
  - Make origin sticky per `variant_hash`: refuse a registration whose variant was ever registered with an LLM origin unless it declares LLM too.
  - Refuse model fields on non-LLM origins.
  - Have the verdict (R1.4) read the earliest origin per `variant_hash`.

### R12I-03: the claim is not bound to the run it claims, and the gate never reads it
- **Severity:** medium · **Likelihood:** medium
- **Where:**
  - `look_register.py:225-233`: only the claim's presence and family are checked.
  - `look_gate.py:36-42`: the run tuple has no claim field.
  - `run_oos_validation.py:63-64`: the engine claim's grid is `config_hash` only.
- **Reproduction (p2 §1-§3; p9 §2).**
  - A claim declaring `instruments: ["EUR_USD"]`, universe `EUR-only` and simulator `rsim` registers on a look that grades both enabled instruments (`['EUR_USD','USD_JPY']`). `begin_grade` then **consumes it** for the engine run.
  - Two looks grading different instrument sets (`('EUR_USD',)` vs both) carry **one** `variant_hash`.
  - The string `claim` does not occur in `begin_grade`.
  - The script's engine claim gives the same `variant_hash` at recon_commit `1111111` and `2222222` with the config unchanged. So an LLM-proposed engine CODE change is refused as a "repeat" of the old code, while R12I-01's cosmetic edits pass.
- **Proposed fix:**
  - In `register`, refuse unless `set(claim.declared_space["instruments"]) == set(instruments)`, and unless `universe_id` resolves to that set.
  - Refuse a `simulator` other than the grader's. `run_walk_forward` is `engine`.
  - Re-check both in `begin_grade`.
  - Include the code identity (commit or rule-module hash) in the engine's declared space.

### R12I-04: the cycle's testing order is not bound to "before any stage-A look". Post-hoc orders are accepted, and the entries are unvalidated
- **Severity:** high · **Likelihood:** medium
- **Where:**
  - `look_claims.py:118-133` (`cycle_line`) never reads the looks.
  - `look_register.py:94-95`: a look has no cycle field.
  - The mental model at `look_claims.py:15-16` asserts "written before any stage-A look of that cycle".
- **The authority:** C-BT-11 v2 step 1: "Each cycle's testing order is itself a register row, written before any stage-A look of that cycle". Step 3 then tests the families "in their registered order … testing stops at the first failure". Fixed-sequence FWER control holds only if the order is fixed before outcomes are seen.
- **Reproduction (p3 §1-§2).**
  - Grade `fam-a` (000001) and `fam-b` (000002), then register a cycle ordering `[b, a]`: **ACCEPTED** (000003). No look line names a cycle.
  - `order=["not-a-hash","also-not"]` is ACCEPTED.
  - `order="abc"` is ACCEPTED as `['a','b','c']`: a bare `str` is iterated.
  - `order=[h, h.upper()]` is ACCEPTED as 2 "distinct" family-versions.
  - The proof test does the post-hoc pattern itself: `test_look_claims.py:101-103` registers a look for `_claim()`, then a cycle whose first entry is that claim's `variant_hash`.
- **Ownership:** GAP-P12D-111 (open, R1.4) names "the order registered before any look". But GAP-P12D-98 and the module docstring present the row as built with that property.
- **Proposed fix:**
  - In `cycle_line`, refuse any entry that already has a real-data look on the chain (the chain order is the evidence).
  - Require entries to be 64-hex lower-case, and `order` to be a list or tuple, never a `str`.
  - Give each stage-A look its `cycle_id`, and refuse a stage-A look whose variant is in no earlier cycle row.
  - Replace the test's post-hoc sequence with a refusal test.

### R12I-05: the α budget is not the spec's α-spending schedule. Three cycles at 0.05 register a lifetime 0.15
- **Severity:** medium · **Likelihood:** medium
- **Where:** `look_claims.py:123-124` accepts any `0 < α ≤ 0.05` on every cycle.
- **The authority:** C-BT-11 v2 stage A (D-d): "Cycle 1 spends α = 0.03. Every later cycle spends half of the lifetime budget still unspent (0.01, 0.005, …), so lifetime family-wise error stays ≤ 0.05".
- **Reproduction (p3 §3).** Three `cycle_line` calls in successive quarters at α = 0.05 are all ACCEPTED, where the spec gives 0.03, 0.01 and 0.005. The registered lifetime α is 0.15.
- **Ownership:** GAP-P12D-111 owns α-spending for R1.4. But "a verdict is a pure function of the register", and the register today stores an α that contradicts the spec.
- **Proposed fix:** derive the α from the cycle's index on the chain inside `cycle_line`, and refuse any other value (or write it rather than accept it).

### R12I-06: "one cycle a quarter" is the registering machine's wall clock, bucketed by calendar quarter from the stamp's local fields
- **Severity:** low · **Likelihood:** low
- **Where:** `look_register.py:259` (`datetime.now(timezone.utc)`) and `look_claims.py:128-132`.
- **Reproduction (p3 §4).** All three are ACCEPTED:
  - a second cycle 2 s after `2026-12-31T23:59:59Z`, across the quarter boundary;
  - a chain-later cycle stamped `2026-09-29`, after a cycle stamped `2026-12-15`: no monotonicity check, and GAP-P12D-51 records this laptop's unsynchronised clock;
  - a prior stamp `2026-12-31T20:00:00-05:00` (= 2027-01-01 01:00 UTC), bucketed as Q4 2026 against a Q1 2027 `now`.
- **Proposed fix:**
  - State the rule (calendar quarter in UTC, or a rolling 91 days).
  - Refuse a line whose `registered_utc` precedes the previous line's.
  - Convert to UTC before bucketing.

### R12I-07: the cost-map hash omits the swap/financing inputs, so two grades priced differently share it
- **Severity:** medium · **Likelihood:** medium
- **Where:** `look_claims.py:101-107` takes `(cfg, instruments, cost_stress, spread_floor)` only. `look_gate.py:36-42` does not pin financing either.
- **The authority:** the mental model (`look_claims.py:12-13`) says "two grades priced differently never share it". C-BT-11 v2 stage A grades "net > 0 at 2× modelled cost **including swap**".
- **Reproduction (p2 §4).**
  - `RunInputs.financing` is a run input, and `run_oos_validation.py:106` builds it from `load_rate_table(data/macro)`.
  - `data/macro` is git-ignored (`.gitignore:12:/data/`), so neither `git_commit` nor `config_hash` pins it. The broker fee is a code default of `make_financing`.
  - No `Look` field mentions financing, rates or swap.
  - A run with dated swaps and one with `financing=None` record the identical `cost_map_hash` (`b1afc164a1e5568b…`).
- **Proposed fix:**
  - Add a financing fingerprint to the cost map and to `begin_grade`'s run tuple: the sha256 of the rate-table files read, the broker fee and lease, and on/off.
  - Or land R1.3's C8 swap table and hash it.

### R12I-08: `record_outcome` binds neither the outcome nor its daily vector to the look
- **Severity:** medium · **Likelihood:** low (today only `run_walk_forward` calls it, with its own look)
- **Where:** `look_register.py:275-280`: the file is named `self.root / f"{look.look_id}.outcome.json"`, with no check of `look.path`, the on-disk line, the `.graded` marker or the vector's dates.
- **The authority:** step 1: "A verdict is a pure function of the register".
- **Reproduction (p5 §2).**
  - An outcome with a 2024 (holdout) daily vector is ACCEPTED on a validation-tier look (registered span 2012→2016) that was **never graded** (no `.graded` marker).
  - `canonical.record_outcome(<a synthetic run's look 000001>)` is ACCEPTED. It writes `{"sharpe": 3.0, "source": "synthetic"}` as canonical `000001.outcome.json`, attached to the real `trend-v1` line.
- **Proposed fix:**
  - Verify `Path(look.path).parent == self.root`, the on-disk line equal to `asdict(look)` (as `begin_grade` does), and that the `.graded` marker exists.
  - Record the folds' test windows on the line, and refuse vector dates outside them.

### R12I-09: `store_vector` accepts datetimes, trusts any file already at the hash name, and shares one temp name without fsync
- **Severity:** low · **Likelihood:** low
- **Where:** `look_claims.py:136-152` and `:159`.
- **Reproduction (p5 §1, §3, §4).**
  - **Datetimes.** Two `datetime`s on 2024-01-02 (09:00 and 17:00) pass "strictly increasing" and are stored as a "daily" vector with a duplicate day. `load_vector` then raises `ValueError: Invalid isoformat string: '2024-01-02T09:00:00+00:00'`, so the stored vector is unreadable. `datetime` subclasses `date`, and Rule 2 forbids the silent acceptance.
  - **An existing file is trusted.** A zero-byte file already at `vectors/<hash>.json` (a crash; there is no fsync) makes `store_vector` return the digest without checking it. The outcome would record the digest, and `load_vector` fails forever with `JSONDecodeError`.
  - **One temp name.** Two writers of the same content (two zero-trade grades are identical vectors) collide on `<hash>.tmp`. Writer A gets `FileNotFoundError` after its look was consumed. This was reproduced by interleaving `Path.replace`, not by true concurrent processes.
- **Proposed fix:**
  - Require `type(d) is date` and unique calendar dates.
  - Write through `_write_new` (a uuid temp, fsync, exclusive link).
  - On `FileExistsError`, verify the existing file's content hash, and repair or refuse.

### R12I-10: the proof tests are hollow (A16). Six mutants of the proved code survive
- **Severity:** medium · **Likelihood:** high
- **Where:** `test_look_claims.py:92-97`, `:100-119`, `:72-81`.
- **Reproduction (p6: each mutant in its own process; the harness kills the kill-check mutants, a constant `cost_map_hash` and α ≤ 1.0).** Each of these stays green:
  1. **`cost_map_hash` ignores `spread_floor`.** `:96` chains `base != a != b`, which never compares `base` with the floor variant.
  2. **`cost_map_hash` drops every instrument's C8 block.** No test varies a cost block, a spread limit or a swap convention, although "priced differently" is the test's name.
  3. **`MAX_CYCLE = 100`.** `:113`'s `order * 3` is refused for its duplicates, not its length.
  4. **The α upper bound is 0.10.** Only 0.2 is tried (`:115`).
  5. **"One cycle a calendar YEAR" and "one cycle EVER".** The quarter rule is exercised only within one second (`:111-112`).
  6. **The look line records only `origin.kind`.** This survives `test_look_claims.py` and `test_look_register.py` together (22 passed): no test reads `model_id` / `model_cutoff` back from a line.
- **Proposed fix:**
  - Assert the cost-map inequalities pairwise, and add one test per C8 field.
  - Test six distinct entries, and α at 0, 0.05 and 0.0500001.
  - Test two consecutive quarters (accepted) and one quarter (refused) with an injected clock.
  - Assert that an LLM look's line carries its model and cutoff.

### R12I-11: three registration-time rules of the authority are unbuilt AND unowned (ledger-closure spot-check)
- **Severity:** medium · **Likelihood:** high
- **Where:** `look_claims.py` and `look_register.py` never read the graveyard or the `ProvenanceStore`. GAP-P12D-98's residual names only `evaluate()`.
- **The authority:**
  - master §5.6 R1-D13: an LLM plan is declarative ("a rule id, ≤ 3 literature-fixed parameters, a fixed combination and a universe id"), and "a plan that duplicates a **graveyard motif** … is refused at registration";
  - C-BT-11 v2 step 1: "A graded number without a register row voids its family's results since its last clean row" (PLAN_R1 K9).
- **Reproduction (p10).**
  - An LLM claim with 4 free parameters, a 10,000-point grid and the formula "argmax over the grid of in-sample Sharpe" is **ACCEPTED**.
  - An LLM plan naming the retired 1-minute MEAN_REVERSION is **ACCEPTED**. The graveyard exists (`core/signals/provenance.py:101`) but is never consulted.
  - No entry in `KNOWN_GAPS.md` or `TODO.md` mentions "graveyard motif" or the void rule. `ledger_check.py` is green, so the gap is in ownership, not in format.
- **Proposed fix:** extend GAP-P12D-98's residual, or open an entry, to own (a) the motif veto, (b) the declarative-plan schema for LLM origins and (c) the void rule, each with its phase (R1.3/R1.4).

### R12I-12: `Backtest.run` grades real data with no register line. Register-first holds one layer up, by caller diligence
- **Severity:** medium · **Likelihood:** low (no production caller does it today)
- **Where:**
  - `harness.py:200-254`: `run` builds `build_report` with no look.
  - `oos_runner.py:108` is the only gate.
  - `oracle.py:82-100` also calls `Backtest.run` directly (synthetic only).
  - `look_register.py:6-7` claims "Complete by construction, not by caller diligence".
- **The authority:** step 1: "A graded number exists only if the look register wrote its line first". The brief asks whether another path grades real data without a line first. One does.
- **Reproduction (p7).** Booby-trap every register entry point (`register`, `register_cycle`, `scan`, `consume`, `record_outcome`, `_append`, `data_tier`, `begin_grade`). Then:
  - load the repo's real Dukascopy fixture hour (EUR/USD 2025-12-31 00h: the **holdout** tier) through `DukascopyTickSource` (provenance `real`) → `BacktestDataLoader` → `market_states`, giving 740 real states;
  - make two folds and run the real engine loop through `Backtest.run`.

  The result is a `ValidationReport` (`passed=False`, `n_folds=2`, 3 OOS trades, `annual_sharpe 0.0`, `look {}`), with the register entry points touched: **NONE**, and no holdout marker written.
- **Ownership:** GAP-P12D-98's residual ("the only producer of a graded number") will own the cure, but it does not name `Backtest.run` as today's ungated producer.
- **Proposed fix:** move the look check into `Backtest.run` (a required, verified, consumed-look token whose source/tier/folds it checks), or make `build_report` require it. Name the path in the residual until then.

### R12I-13: a well-chained line of an unknown kind crashes counting, after `begin_grade` has consumed the line
- **Severity:** low · **Likelihood:** low
- **Where:** "is a look" has three predicates: `looks()` at `look_register.py:189` excludes unknown kinds, while `family_counts` (`:194-196`) and `summary` (`:286`) count them. `look_gate.py:48-49` consumes, then calls `summary()`.
- **Reproduction (p4 §4).** Append `{"kind":"evaluate", "prev_hash": <head>}`, the shape a later register version's row could take. `scan.broken == []`, and `looks()` skips it. But `family_counts()` raises `KeyError: 'family'` and `summary()` raises `KeyError: 'tier_name'`.
- **Proposed fix:** one `_is_look` predicate everywhere. Fail closed at `scan` on an unknown kind, or count it explicitly.

### R12I-14: the Claim and Origin validate less at construction than the rules require (Rule 2)
- **Severity:** low · **Likelihood:** medium
- **Where:** `look_claims.py:50-59` and `:62-85`.
- **Reproduction (p1 §5-§7).**
  - `Origin("llm", model_id=" ", …)` and `Origin("literature", reference=" ", …)` are ACCEPTED: the Origin tests truthiness, while the Claim `.strip()`s.
  - The basic-ISO cutoff `"20260601"` is ACCEPTED and stored unnormalised.
  - A `Decimal`, a `set` or a NaN in the grid passes construction, then fails inside `register()` as `TypeError` / `ValueError`, not `LookRefused`.
  - The frozen Claim keeps the caller's mutable dict. Appending to its grid changes `variant_hash` after construction, and deleting `formula` leaves a "valid" claim without a required key.
- **Proposed fix:**
  - Strip the fields.
  - Normalise dates to `YYYY-MM-DD`.
  - Canonicalise the declared space once in `__post_init__` (store the canonical JSON string, and fail there).
  - Refuse fields foreign to the origin's kind.

### R12I-15: the script's documented commands no longer run (A13)
- **Severity:** low · **Likelihood:** high
- **Where:** the docstring of `run_oos_validation.py:4-6`. Line 3 was updated; lines 4-6 were not.
- **Reproduction (p9 §1).** Both documented invocations exit 2 with `error: the following arguments are required: --origin, --recon-commit`.
- **Proposed fix:** add the two flags to the examples.

## Honest negatives (verified, not found wanting)
- **The suite.** 1057 passed, 6 skipped at `192c1fa` on the server; the 8 proof tests pass by name.
- **Module sizes.** `look_register.py` 290, `look_claims.py` 159 and `look_gate.py` 49 lines; `test_module_budget.py` and `test_ledger_integrity.py` are green.
- **The ledger.** `scripts/ledger_check.py`: 260 entries, 0 violations.
- **The `begin_grade` move** is faithful:
  - the body is identical to `863e68e`'s modulo `lr.` and one line's indentation;
  - there is one definition, and `oos_runner.py:44` and the tests import it from `look_gate`;
  - `lr.CANONICAL` / `lr.git_state` resolve at call time, so the test patch point serves both.
- **Renames and model ids do not launder.** Renaming a family does not launder an LLM repeat (the control is refused), and a changed model id does not either (origin is outside `variant_hash`).
- **Equal representations hash equal.** Dict key order, tuple vs list, and `0.1` vs `0.10`.
- **The chain across kinds:**
  - `prev_hash` is continuous over look→cycle→look→cycle→look (5 lines, all chaining, `scan.broken` empty);
  - a torn last line followed by a cycle row and a look is handled;
  - two concurrent `register_cycle` calls in one quarter produce exactly one row;
  - cycle rows are skipped by `looks()`, `family_counts` and `tier_totals`.
- **The vector's input checks.** `store_vector` refuses NaN, inf, a length mismatch, unsorted dates, a duplicate `date` and an empty vector. `load_vector` detects an edited value.
- **The claim requirement:**
  - a real-data look without a claim is refused, as is a claim for another family, and a blank family is refused before any claim;
  - `run_oos_validation.py` has no default origin (required, `choices`) and no default `recon_commit`, and it refuses a bad origin with exit 2 before writing anything.
- **Register-first on the real-data path is unchanged.** `run_walk_forward` consumes its line before compute (`oos_runner.py:108`). The other register users (`synthetic_grade.py:118`, `leakage_engine.py:128`) are tier 0, and no `provenance = "synthetic"` source in the repo wraps real bytes (`LabTickSource`, `SyntheticMarket`, `PerturbedMarket`).
- **No old-format real line exists yet.** `data/validation/looks` does not exist on the laptop. The v1-line blind spot (p4 §3: a v1 line has no `variant_hash`, so an LLM repeat of a pre-v2 grade is not refused) has no instance today.
- **The daily vector's residual is honest.** Today's only real-data path records no daily vector (`oos_runner.py:154-158` passes no `daily=`), and GAP-P12D-98's residual owns this explicitly through `evaluate()`.

## What I could not verify
- **The governance gate.** `python scripts/governance_gate.py --session` stops on the server with "node is not on PATH". It was not run on the laptop (owner directive).
- **Cross-platform byte stability.** `canonical_hash` and the vector files were exercised on Linux only. The hash is taken over the parsed payload, so CRLF or whitespace in a file cannot move it, but a Windows run was not made.
- **True concurrency.** The `store_vector` temp-name collision was reproduced by deterministic interleaving, not by two OS processes; `os.link` semantics on NTFS were not exercised.
- **How R1.4 will read the register.** Whether the verdict will take α from the cycle row or recompute it, and whether it will read the earliest origin per `variant_hash`, cannot be tested until that code exists. Several severities above (R12I-02, -04, -05) fall if R1.4 recomputes from the chain.

## Residual risk
- **The inputs are the operator's own word.** Origin, universe, formula text and a source class's `provenance` attribute are all self-declared, and the chain is unsigned (GAP-P12D-86). The register gives tamper EVIDENCE of edits, not resistance to a dishonest or careless registrant. R12I-01/02/03 widen that gap: honest re-wording alone defeats the one refusal R1.2 added.
- **R1.4 inherits the unnormalised fields.** R1.4's verdict will be "a pure function of the register". Unless R12I-01/03/04/05/07 are fixed first, that function will read unnormalised identities, unbound claims, a post-hoc order and an unscheduled α.
- **A second grader exists.** Until `evaluate()` exists and `Backtest.run` is gated (R12I-12), register-first is a property of one caller, not of the grader.
