# AUDIT R1.2 — EXTERNAL-REFERENT LENS (2026-09-29)

- **Brief:** `AUDIT_BRIEF_R1_2_2026-09-29.md` (pinned; followed as written). **Audited state:** commit `192c1fa` against its parent `863e68e`, read with `git show 192c1fa:<path>`. The working tree was never trusted to equal `192c1fa`. Every run was on the Google compute server, in the external auditor's own checkout of `192c1fa` (`remote_audit_r12.sh external`).
- **Auditor:** Claude Opus 5.5 (`claude-opus-5-5[1m]`). The brief named Opus 5; this is an Opus-lineage model at or above the A2 floor. **Fresh context, finder not clearer (A5).** No subagents or agents were launched. There were no git writes and no edits other than this file.
- **Web budget:** 6 of the 20 allowed WebSearch calls were used. Every other source was fetched directly with WebFetch; PDFs were text-extracted locally with `pypdf`. All sources were accessed on **2026-09-29** and are listed in §6.
- **Probes:** `C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/688e2ed6-575e-479f-a856-d4e3a1e59865/scratchpad/audit_r12/external/probes/` (`_common.py`, `p1`–`p5`). They sit in the session scratchpad, not in the repo, and each runs as `python probes/<file>.py` on the server. Receipts are quoted inline.
- **Lens:** the implementation AND the design against the outside world: RFC 8785, the multiple-testing and data-snooping literature, the online-FWER literature, the LLM look-ahead literature, the vendor's own cutoff definitions and the tamper-evident-logging literature. Defects only.

## 1. Executive summary

**Eleven findings: 1 high, 2 medium-high, 4 medium, 1 low-medium and 3 low.**

The lead's three claims are true:
- 1057 passed and 6 skipped at `192c1fa` on the server;
- the 22 register tests pass;
- `ledger_check` is green (260 entries, 0 violations);
- `look_register.py` is 290 lines.

The mechanics that R1.2 tests are sound: hash determinism on the observed platforms, the chain's continuity across kinds, the byte-stable vector round trip, and the refusal of a same-origin repeat. The defects sit where the register meets the outside world:
- **whose memory a hypothesis carries** (the LLM-contamination law);
- **what must be fixed before data are seen** (serial gatekeeping, α-spending, pre-registration);
- **what the register proves to someone who does not trust its author** (tamper evidence).

None has caused harm yet. There is no canonical register on the laptop (`data/validation/looks` does not exist), so no real-data look has been registered. But the register is append-only. Every recording choice made now becomes permanent the first time a real-data look is written, and the verdict built in R1.4 cannot add a declaration later without losing its value as a pre-registration.

The three most serious:
1. **E-R12-01 (high). The contamination law can be laundered by relabelling the origin.** Once an LLM has registered a variant, the same variant registers again as `human` or `literature`, and its line records that origin. The proof test `test_an_llm_plan_that_repeats_a_registered_variant_is_refused` *asserts* this path works (`test_look_claims.py:89`). The script's documented invocation models `--origin human` for an engine that LLM agents designed and refined.
2. **E-R12-02 (medium-high). The recorded bound is the wrong date for the world the proposers live in.**
   - `Origin` stores one "knowledge cutoff". The vendor distinguishes a *reliable knowledge* cutoff from a broader *training data* cutoff.
   - The finance-LLM literature says tool and retrieval access leaks post-cutoff information, and that prompts, retrieved documents and tool outputs must be recorded.
   - Every proposer in this project is an agent with web search and repository access.
   - The register's "forward" tier is also one constant (2026-07-01) that ignores the claim's own recorded cutoff.
3. **E-R12-03 (medium-high). The claim omits the declarations the spec requires at registration and the literature requires up front:** the look budget k, the passive benchmark, fixed vs explored, the bootstrap block length, and the Holm set outside the chain. An append-only register cannot acquire them later without ceasing to be a pre-registration.

## 2. Findings

### E-R12-01 — An LLM-originated variant re-registers under a `human` or `literature` origin, and its line records the new origin: the contamination law is keyed on the registration, not the hypothesis
- **Severity:** high · **Likelihood:** medium-high. In this project nearly every hypothesis is LLM-generated or LLM-selected ([[GAP-P12D-66]]: "The ARCHITECT's slate was selected with LLM help"). The agent that runs the scripts is itself an LLM, and `operator` defaults to the OS user whoever runs it.
- **Where:**
  - `tests/backtest/look_claims.py:110-115`: `refuse_repeated_llm_variant` returns immediately unless the *new* claim's origin is `llm`.
  - `look_register.py:237-241`.
  - `tests/backtest/test_look_claims.py:89`: `_look(canonical, acis_config, claim=_claim(), changed="a human re-look that says what changed")` registers the LLM's variant as `human` and asserts it succeeds.
  - `scripts/run_oos_validation.py:3` (192c1fa): the usage line is `--origin human` for the engine.
- **Authority:** master §5.6 (v2.19): "a hypothesis that an LLM **generated, selected or refined** is graded partly on the model's memory … An LLM-originated or LLM-refined hypothesis may be *falsified* on any history. It counts toward a *pass* only on data after the generating model's cutoff." Provenance is a property of the hypothesis. A later registrant's label does not change what the model remembered when it produced the plan.
- **External referent:** Sarkar & Vafa (ICML 2025 workshop abstract, fetched 2026-09-29, https://icml.cc/virtual/2025/51018): "This bias arises when a language model's pretraining data contains information about the future, which then leaks into analysis that should only use information from the past … The issues we raise can be addressed by using models whose pretraining data is free of survivorship bias and contains only language produced prior to the analysis period of interest." The leak lives in the model that produced the plan. Re-typing the plan under another name does not remove it.
- **Reproduction** (`probes/p2_origin_laundering.py`):
  ```
  look 1 origin: llm variant 26ada41b1774
  REFUSED   same variant, origin llm (the R1-D13 refusal) -> LookRefused: an LLM plan repeats registered variant 26ada41b1774
  ACCEPTED  same variant, origin HUMAN -> Look(look_id='000002', ... tier_name='validation', ... 'origin': {'kind': 'human', ...})
  ACCEPTED  same variant, origin LITERATURE (dated ref) -> Look(look_id='000003', ... 'origin': {'kind': 'literature', ... 'published': '2012-05-01'})
    line 000002: variant 26ada41b1774 origin=human tier=validation
    line 000003: variant 26ada41b1774 origin=literature tier=validation
  ```
  The two later lines are real-data (tier 2) looks of the SAME `variant_hash`. They carry origins under which the R1.4 verdict, applying §5.6 line by line, would allow a pre-cutoff pass. The literature line is the worst case, because §5.6 exempts a literature origin on post-publication data (2012-05 onward, here).
- **Proposed fix:**
  - Make origin sticky per `variant_hash`. If any earlier line with that variant has an `llm` origin, refuse a non-`llm` origin: "origin is a property of the variant (§5.6)". Alternatively, record an `effective_origin` = llm that the verdict must read.
  - Invert `test_look_claims.py:89`: a human re-look of an LLM variant must be refused, or recorded as LLM-originated.
  - Change the script's documented invocation so it does not model `--origin human` for the LLM-built engine.

### E-R12-02 — `Origin` records a single "knowledge cutoff", but the world has a later training-data cutoff and tool, retrieval and in-context exposure, and the register's "forward" tier ignores the recorded cutoff entirely
- **Severity:** medium-high · **Likelihood:** high. Every ACIS proposer (the lead, the research agents) runs with WebSearch/WebFetch and reads repository reports of results. **Spec-vs-world:** master §5.6 and C-BT-11 v2 step 1 say "model cutoff" / "that model's knowledge cutoff". The code faithfully implements a bound that is wrong about the world.
- **Where:**
  - `look_claims.py:46` (`model_cutoff: str = ""  # llm: its knowledge cutoff, ISO date`).
  - `look_claims.py:43-59`: `Origin` has no generation date, no exposure field, and no way to say "a literature rule SELECTED by an LLM", because `kind` is exclusive.
  - `look_register.py:57` and `:63-64`: `FORWARD_START` is one constant, and `data_tier` never reads the claim.
- **External referents:**
  1. **The vendor's own two dates** (Anthropic, *Models overview*, fetched 2026-09-29, https://platform.claude.com/docs/en/about-claude/models/overview): "**Reliable knowledge cutoff:** The date through which the model's knowledge is most extensive and reliable. Training data cutoff (under Additional details) is the broader range of data used." The same table lists Claude Haiku 4.5 at "Reliable knowledge cutoff … Feb 2025" but "Training data cutoff … Jul 2025", five months apart. A field documented as the "knowledge cutoff" records the EARLIER of the two dates, while contamination is bounded by the later one. The current Opus 5.5, Sonnet 5.5 and Fable 5.1 happen to show Jun 2026 for both, so the gap is latent today and structural in the schema.
  2. **Effective vs reported cutoffs** (Cheng et al., *Dated Data*, arXiv:2403.12958, fetched 2026-09-29): "we find that effective cutoffs often differ from reported cutoffs." Honest note: their mechanism, old data in new crawls, mostly makes effective cutoffs EARLIER, which is conservative here. It still means a single self-reported date is not a verified property.
  3. **Tool and retrieval leakage, and what must be recorded** (Kong, Lee, Hwang, Lopez-Lira, Levy, Mehta, Wen, Choi, Lee & Zohren, *Evaluating LLMs in Finance Requires Explicit Bias Consideration*, arXiv:2602.14233v1, 15 Feb 2026, fetched 2026-09-29, https://arxiv.org/html/2602.14233v1):
     - "A second source of look-ahead bias arises when a system M uses an external knowledge base K through retrieval-augmented generation … This formulation assumes that the retriever returns only information available at time t. In practice, this assumption often fails."
     - "The problem becomes more severe when retrieval relies on live search engines."
     - "We mandate that authors disclose the latest calendar date represented used for pre-training … Evaluations should record prompts, retrieved documents or identifiers, tool outputs, and decision timestamps."
  4. **Postdiction vs prediction** (Nosek, Ebersole, DeHaven & Mellor 2018, abstract via RePEc, fetched 2026-09-29, https://ideas.repec.org/p/osf/osfxxx/2dxu5.html): "Progress in science relies on generating hypotheses with existing observations and testing hypotheses with new observations."
- **What this means here:**
  - An agent that proposes a plan on 2026-09-29 with web access can read FX history for 2026-07..09. Yet `FORWARD_START = 2026-07-01` labels that window **tier 4 "forward"**.
  - For a tool-using proposer, the information horizon is the proposal date, not the training cutoff. `Origin` records neither the proposal date nor the exposure.
  - An LLM that *selects* a published rule (GAP-P12D-66's ARCHITECT slate) can only be recorded as `literature` (exempt after publication) or as `llm` (losing the reference). There is no way to record "literature, selected by model X", which §5.6's "selected" requires.
- **Reproduction** (`probes/p2_origin_laundering.py`):
  ```
  ACCEPTED  LLM cutoff 2026-12-31 graded on 2026-07-22..2026-09-01 -> Look(... tier=4, tier_name='forward', ... 'origin': {'kind': 'llm', 'model_id': 'future-model', 'model_cutoff': '2026-12-31', ...})
    recorded tier_name='forward' although every test day precedes that model's cutoff
  Origin fields: ['kind', 'model_id', 'model_cutoff', 'reference', 'published']
  ```
- **Ledger note:** GAP-P12D-66's R1.4 half names only "a grader that refuses a pass on pre-cutoff data for an LLM origin". Nothing owns the literature-origin check ("graded on data after that publication date"), and nothing owns the tool-exposure horizon.
- **Proposed fix (master §5.6 text, so the owner decides):**
  - `Origin` gains `training_data_cutoff` (the vendor's broader date, or the only date published), `proposed_utc` (when the plan was generated) and `exposure` ∈ {none, retrieval/web, repository-results}.
  - The certifying boundary becomes max(training_data_cutoff, proposed_utc if exposure ≠ none).
  - A literature origin may carry `selected_by: Origin(llm, …)`, which makes it LLM-selected.
  - The register records per look whether its test window lies wholly after that boundary, instead of a global `FORWARD_START` tier name.
  - Record the owner of the literature-date check in GAP-P12D-66.

### E-R12-03 — The claim omits the declarations C-BT-11 v2 requires AT REGISTRATION (look budget k, passive benchmark, fixed/explored kind, bootstrap block length, the Holm set), and an append-only register cannot add them later
- **Severity:** medium-high · **Likelihood:** medium. `run_oos_validation.py` can write a tier-2 look today, and each such line is permanent.
- **Where:** `look_claims.py:62-98`. The Claim fields are `family, variant, declared_space, universe_id, origin, simulator, recon_commit`, confirmed by `probes/p3_cycles.py`: `Claim fields: ['family', 'variant', 'declared_space', 'universe_id', 'origin', 'simulator', 'recon_commit']`. The cycle row (`look_claims.py:118-133`) carries only `order` and `alpha`.
- **Authority:** ACIS-09 v1.8 C-BT-11 v2 step 3:
  - "**Each family declares a look budget k ∈ {1, 2, 3} at registration.** Each of its looks is tested at α/k";
  - "its paired excess over the **registered passive benchmark** is > 0";
  - explored families: "a stationary bootstrap … with the **block length pre-registered**";
  - "Families outside the chain are tested only if the whole chain passed, Holm-adjusted among themselves". That set is never registered anywhere.
- **External referents:**
  - FDA, *Multiple Endpoints in Clinical Trials* (Oct 2022), §II.C, pp. 5–6 (https://www.fda.gov/media/162416/download, fetched 2026-09-29): "an important principle is to first prospectively specify all planned endpoints, time points, analysis populations, doses, and analyses; then, once these factors are specified, appropriate adjustments for multiple endpoints and analyses can be selected, prespecified, and applied … The statistical analysis plan should not be changed after unmasking of treatment assignments and performing statistical analyses."
  - White (2000), *A Reality Check for Data Snooping*, Econometrica 68(5), p. 1110 (https://users.ssc.wisc.edu/~behansen/718/White2000.pdf, fetched 2026-09-29), on continuing a search validly: "Some cooperation is nevertheless required, as R, T, q, N, the RNG, the RNG seed, and V … must still be shared, along with the data and the specification and estimation method for the benchmark model." The benchmark's specification and the bootstrap's q (the stationary bootstrap's block parameter) and seed are part of what must be pinned.
- **Why it cannot wait for R1.4:** a k, benchmark or block length chosen after the first look is a post-hoc choice. The Bonferroni divisor α/k is exactly the kind of number that is picked after seeing whether a look clears α or α/2. A field added later reads identically to one declared before, so the register loses its evidentiary value for every look written in the gap.
- **Proposed fix:**
  - Add to `Claim`, required for tier ≥ 2: `kind` ∈ {fixed, explored}; `look_budget` ∈ {1, 2, 3}; `benchmark` (an id plus its own declared-space hash); and, for explored families, `block_length` and `bootstrap_seed`. Hash them into the claim line.
  - Add the Holm set to the cycle row.
  - Alternatively, refuse tier-2 looks until R1.4 lands, and say so in GAP-P12D-98's residual. At present GAP-P12D-111 owns only the *verdict* use of k.

### E-R12-04 — The cycle row accepts any α in (0, 0.05] per cycle, so it is not an α-spending sequence: three quarters of α = 0.05 register a lifetime 0.15 against the spec's 0.05
- **Severity:** medium · **Likelihood:** medium.
- **Where:** `look_claims.py:123-124` (`if not 0.0 < alpha <= 0.05`); `look_register.py:256-266` (the caller supplies α).
- **Authority:** C-BT-11 v2 step 3, decision D-d: "Cycle 1 spends α = 0.03. Every later cycle spends half of the lifetime budget still unspent (0.01, 0.005, …), so lifetime family-wise error stays ≤ 0.05." The mental model at `look_claims.py:15-16` presents the row as enforcing serial gatekeeping's registration rules.
- **External referents:**
  - Tian & Ramdas, *Online control of the familywise error rate*, arXiv:1910.04900, §2 (fetched 2026-09-29): "Specifically, for FWER level α, given an infinite nonnegative sequence {γi} that sums to one, the Alpha-Spending tests individual hypothesis Hi at level αi := αγi." FWER control across an unbounded stream comes from Σαi ≤ α. A per-stage cap without a running sum controls nothing lifetime-wide.
  - Javanmard & Montanari, arXiv:1603.09000 (fetched 2026-09-29), on the alternative: "any rule in this class controls online FDR, provided p-values corresponding to true nulls are independent from the other p-values. (Earlier work only established mFDR control.)"
- **Reproduction** (`probes/p3_cycles.py`, with the clock stepped one quarter at a time):
  ```
  ACCEPTED  cycle 1 at alpha 0.05 (spec: 0.03) -> 0.05
  ACCEPTED  cycle 2 at alpha 0.05 (spec: 0.01) -> 0.05
  ACCEPTED  cycle 3 at alpha 0.05 (spec: 0.005) -> 0.05
    lifetime alpha registered = 0.150 (spec lifetime budget 0.05)
  ```
- **Proposed fix:** `cycle_line` derives α itself as 0.05·γn from the count of prior cycle rows (γ = 0.6, 0.2, 0.1, …, i.e. 0.03 then half the unspent) and refuses, or drops, a caller-supplied α. Otherwise the R1.4 verdict must override the registered α, and the row then records a number that is not the one used.

### E-R12-05 — The testing order is not prospective: a cycle may be registered after its members' looks, its members are free text, and no look says which cycle it belongs to
- **Severity:** medium · **Likelihood:** medium.
- **Where:** `look_claims.py:118-133`. The row validates count, distinctness, α, uniqueness and quarter, but not that members are registered variant hashes, nor that none has already had a real-data look. `Look` (`look_register.py:71-95`) has no `cycle_id` and no look index j ≤ k. The mental-model line "written before any stage-A look of that cycle" (`look_claims.py:16`) is documented, not enforced. The proof test itself registers a look of `_claim()` and only then a cycle whose first member is that variant (`test_look_claims.py:101-103`).
- **External referent:** FDA *Multiple Endpoints* (2022), Appendix §5 "The Fixed-Sequence Method", pp. 20–21 (fetched 2026-09-29): "Such a testing procedure requires (1) prospective specification of the testing sequence and (2) no further testing once the sequence breaks … Ignoring the first endpoint's result recreates the multiplicity problem and causes inflation of the overall Type I error rate."
- **Reproduction** (`probes/p3_cycles.py`):
  ```
  ACCEPTED  cycle whose first member already had a real-data look -> 26ada41b1774
  ACCEPTED  cycle ordering free text -> ['best one', 'whatever']
  ```
  and `probes/p5_rollback_reorder.py`, which shows the order can be rewritten after a failed first look (see E-R12-07):
  ```
  before rollback: cycles ['2026Q3'] | looks 1 | head 435c530cdb29
  after rollback : broken () | cycles [] | looks 0
  re-registered  : 2026Q3 order ['dc326310', '26ada41b'] | broken ()
  ```
- **Proposed fix:**
  - Register each member's full claim IN the cycle row (so the order names registered family-versions).
  - Refuse a member `variant_hash` that already has a tier ≥ 2 look.
  - Make each stage-A look carry `cycle_id` and its look index, refusing a look outside a registered cycle or beyond the member's k.
  - The rollback case needs E-R12-07's anchor.

### E-R12-06 — The verdict's inputs (the outcome and its daily-vector pointer) sit outside the hash chain: rewriting or deleting them leaves `scan().broken` empty
- **Severity:** medium · **Likelihood:** low-medium (it needs a write to `data/`, but so does everything GAP-P12D-86 guards).
- **Where:**
  - `look_register.py:275-280`: `record_outcome` writes `<N>.outcome.json` with `_write_new` but no chained line.
  - `look_register.py:183-185`: `scan` only checks that a marker's number has a line, never the marker's bytes.
  - `look_claims.py:17-18` and C-BT-11 v2 step 1: "the outcome carries the hash, so a verdict is a pure function of the register."
- **External referents:**
  - Bailey & López de Prado, *The Deflated Sharpe Ratio* (2014), pp. 3–4 (https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf, fetched 2026-09-29): "Analysts who do not report the full extent of the experiments conducted ('file drawer effect') … What all these phenomena have in common is that critical information is hidden from the decision-maker, with the effect of a much larger than anticipated Type I Error probability." The DSR needs "the variance across the trials' estimated SR" (p. 8). A look whose outcome vanishes still counts in N, but its Sharpe drops out of V[{SR_n}]: the file drawer, for the variance.
  - Crosby & Wallach 2009 (quoted in E-R12-07).
- **Reproduction** (`probes/p4_outcome_outside_chain.py`):
  ```
  recorded : {'annual_sharpe': -1.3, 'daily_vector': '0fde0d8a…'}
  rewritten: {'annual_sharpe': 2.9, 'daily_vector': '3e9ea6a5…'} | load_vector ok: [0.004, 0.002, 0.003, 0.001, 0.002]
  scan().broken after rewriting the outcome: ()
  scan().broken after deleting the outcome : () | chain head unchanged: 5026988365ea
  ```
  The content-addressed vector is tamper-evident only for its bytes. The reference to it is not authenticated. In git's Merkle design, by contrast, the reference is itself part of a hashed tree.
- **Proposed fix:**
  - Record each outcome as a chained line through `_append` (`kind: "outcome"`, `look_id`, the sha256 of the outcome bytes, `daily_vector`), skipped by counting like cycle rows.
  - `scan` verifies each `<N>.outcome.json` against its chained digest, and a graded look with no outcome line is reported.

### E-R12-07 — To an outside reader the register is not tamper-evident: nothing leaves the author's machine, and R1.2 makes it the sole input to the α budget, the cycle order and the LLM refusal. GAP-P12D-86's "medium · low" now understates it
- **Severity:** medium (ledger accuracy and requirement) · **Likelihood:** medium.
- **Where:**
  - `.gitignore` at 192c1fa has `/data/`, so `data/validation/looks`, the report carrying `chain_head` and the vectors are all untracked, on one machine.
  - `register_cycle`, `refuse_repeated_llm_variant` and the C-BT-11 v2 verdict all read only the chain.
  - GAP-P12D-86 (open, owner decision) covers tail deletion and the unsigned chain, rated medium/low before R1.2 made the register decision-bearing.
- **External referents:**
  - Crosby & Wallach, *Efficient Data Structures for Tamper-Evident Logging*, USENIX Security 2009, §1 and §2.1–2.2 (https://www.usenix.org/legacy/event/sec09/tech/full_papers/crosby.pdf, fetched 2026-09-29):
    - "If an untrusted logger knows that a just-added event or returned commitment will not be audited, then any tampering with the added event or the events fixed by that commitment will be undiscovered, and, by definition, the log is not tamper-evident."
    - "A dishonest logger may attempt to tamper with its history by rolling back the log, creating a new fork on which it inserts new events, and abandoning the old fork."
    - "the logger may publish its commitment in a public fashion so that all auditors receive the same commitment."
  - RFC 3161 §1 (https://www.rfc-editor.org/rfc/rfc3161, fetched 2026-09-29): "A time-stamping service supports assertions of proof that a datum existed before a particular time." Ordering inside a self-held chain is not proof of time to a third party.
- **Reproduction:** `probes/p5_rollback_reorder.py` (above). A cycle row and the first stage-A look are rolled back, and the same cycle id is re-registered in the same quarter with the order flipped. `broken ()` throughout.
- **What the register proves to an outside reader today:**
  - that the copy shown is internally consistent;
  - NOT that it is complete (tail rollback or whole-chain rewrite);
  - NOT when any line was written (self-asserted clocks, E-R12-10);
  - NOT that any origin is true (self-declared, E-R12-01/02).
- **Proposed fix:**
  - Raise GAP-P12D-86 to high and make an external commitment a precondition of any tier ≥ 2 look. The cheapest: after each append, commit the chain head and the outcome digests to a TRACKED file and push to GitHub, a third party that holds the timestamps. Alternatively, RFC 3161-timestamp each head.
  - Record in GAP-P12D-98 that "a verdict is a pure function of the register" holds only relative to that anchor.

### E-R12-08 — `variant_hash` is an identity of spelling, not of "what the plan IS": integer vs float, −0.0, instrument order, free labels, extra keys, whitespace and Unicode form each make a new variant, and the serialisation is not RFC 8785 despite the "canonical JSON" name
- **Severity:** low-medium · **Likelihood:** medium. **Impact is bounded:** every respelled repeat is still a counted look, so N is not understated. What fails is R1-D13's refusal ("A plan that duplicates … a registered `variant_hash` is refused"), and any verdict that dedups by `variant_hash`.
- **Where:**
  - `look_claims.py:38-39`: `json.dumps(payload, sort_keys=True, allow_nan=False)`, with default separators and `ensure_ascii`.
  - `look_claims.py:87-91`: the variant hash is `[declared_space_hash, variant, universe_id]`, two free-text labels included.
  - `look_claims.py:79-81`: extra keys in `declared_space` are accepted and hashed.
  - `look_claims.py:10-11`: "Every hash is sha256 of canonical JSON".
- **External referents:**
  - RFC 8785 (JCS), fetched 2026-09-29 (https://www.rfc-editor.org/rfc/rfc8785):
    - §1.1: "Cryptographic operations like hashing and signing need the data to be expressed in an invariant format so that the operations are reliably repeatable."
    - §3.2.2.3: numbers "MUST be serialized according to Section 7.1.12.1 of [ECMA-262]". Appendix B shows `4.50` → `4.5` and minus zero → `0`. The number's IEEE value, not its spelling, decides the bytes, so `8` and `8.0` are both `8`.
    - §3.2.1: "Whitespace between JSON tokens MUST NOT be emitted."
    - §3.2.3: properties are sorted as "arrays of UTF-16 code units".
  - Python `json` docs (https://docs.python.org/3/library/json.html, fetched 2026-09-29): separators default to "`(', ', ': ')` if *indent* is `None`", and with `ensure_ascii` "all incoming non-ASCII … characters escaped". Python's bytes are therefore not JCS bytes, and an outside verifier using a JCS library cannot reproduce a single hash.
- **Reproduction** (`probes/p1_hash_identity.py`, each row the same plan):
  ```
  grid ints -> floats (8 vs 8.0; JCS: both '8')           distinct_hash=True
  instrument list reordered (a set for a pooled family)   distinct_hash=True
  universe_id relabelled only ('R1-23' -> 'r1-23')        distinct_hash=True
  variant label case ('fixed' -> 'Fixed')                 distinct_hash=True
  extra free key in declared_space ({'note': 'v2'})       distinct_hash=True
  formula whitespace only                                 distinct_hash=True
  formula NFC vs NFD (e-acute)                            distinct_hash=True
  zero: canonical_hash(0.0) != canonical_hash(-0.0): True
  python json bytes : {"a": 1.0, "b": 1e+16, "c": 1e-07, "d": "\u00e9"}
  RFC 8785 JCS bytes: {"a":1,"b":10000000000000000,"c":1e-7,"d":"é"}
  ```
  The declared choice "`variant_hash` excludes the family's NAME, so renaming a family cannot launder a repeat" holds for the family name, but two other free names (`variant`, `universe_id`) remain inside the hash. An LLM plan emitted as JSON with `8.0` where the registered plan had `8` is a new variant.
- **Proposed fix:**
  - Normalise before hashing:
    - integral floats → int and −0.0 → 0, or a JCS number formatter;
    - `instruments` sorted and deduplicated (or a mapping instrument → weight, where order is not meaningful);
    - `declared_space` restricted to its schema keys;
    - strings NFC-normalised and stripped;
    - `variant` and `universe_id` case-folded, or dropped from the variant hash (the universe's content is already in `instruments`).
  - Either adopt RFC 8785, or rename the mental model's "canonical JSON" to the exact definition: "Python `json.dumps(sort_keys=True, allow_nan=False)`, default separators, ASCII-escaped".

### E-R12-09 — The "daily" vector has no declared day convention and accepts intraday stamps, weekend days and two stamps on one calendar day. A datetime-keyed vector stores successfully and then cannot be loaded
- **Severity:** low · **Likelihood:** low (R1.3's `evaluate` will be the producer, and it can pass `date`s).
- **Where:** `look_claims.py:136-152` (`store_vector` checks strict increase and finiteness only); `look_claims.py:155-159` (`load_vector` parses with `date.fromisoformat`).
- **Reproduction** (`probes/p4_outcome_outside_chain.py`, Python 3.11.2 on the server):
  ```
  two stamps on ONE calendar day + a Saturday + a Sunday stored as a 'daily' vector: 375e7da7bef3
  stamps: ValueError Invalid isoformat string: '2024-01-01T00:00:00'
  ```
  The vector is written and its digest returned, and it can never be read back. A verdict that is "a pure function of the register" then has an unreadable input.
- **Referent:** the project's own FX day is the 17:00 New York rollover (master §3/§13, GAP-P12D-10). An annualised Sharpe on a daily series (C-BT-11 v2 cites Lo 2002 for its standard error) depends on what one observation is. Weekend zero-days and duplicate days change the observation count, and so the √q annualisation.
- **Proposed fix:**
  - `store_vector` requires `type(d) is date` and records a declared day convention (for example `fx_trade_date_ny17`).
  - It refuses weekend dates for an FX book unless declared.
  - It self-checks by `load_vector` before returning the digest.

### E-R12-10 — "One cycle a calendar quarter" runs on the registering machine's self-asserted clock: two cycles one second apart at a quarter boundary are accepted, and so is a timestamp earlier than the line before it
- **Severity:** low · **Likelihood:** low. The owner's laptop clock is known to be unsynchronised (GAP-P12D-51). **Impact is bounded:** under a correctly enforced spending sequence (E-R12-04) the quarter rule controls no error rate (Tian & Ramdas: FWER comes from Σαi alone). It only paces how fast the geometric budget is spent.
- **Where:** `look_claims.py:128-132` (calendar quarter of `now`, compared only with other cycle rows); `look_register.py:259` (`datetime.now(timezone.utc)`). No line is checked for monotonic time against its predecessor.
- **Reproduction** (`probes/p3_cycles.py`):
  ```
  ACCEPTED  cycle at 2026-09-30T23:59:59Z -> q3
  ACCEPTED  cycle one second later, 2026-10-01T00:00:00Z -> q4
  ACCEPTED  cycle stamped 2026-06-01 AFTER the 2026-10-01 line (clock set back) -> 2026-06-01T00:00:00+00:00
    broken: () | cycles: ['q3', 'q4', 'q2']
  ```
- **Referent:** RFC 3161 §1 (quoted in E-R12-07). A self-issued timestamp is not evidence of time.
- **Proposed fix:**
  - Refuse any line whose `registered_utc` precedes the previous line's.
  - If pacing is the intent, state it as "≥ 90 days since the previous cycle row" rather than a calendar quarter.
  - Time evidence comes from E-R12-07's external anchor.

### E-R12-11 — A13: the read path says R1.2 is next and the suite is 1050 while `192c1fa` built R1.2 at 1057
- **Severity:** low · **Likelihood:** certain.
- **Where** (at `192c1fa`, unchanged at HEAD `355c27f`):
  - `README.md:5`: "with 1050 tests passing … its two constitution audits and then R1.2 are next";
  - `STATUS.md:13`: "**Next:** the constitution's two audits of R1.1 (owner's go), then R1.2 (register v2)."
  - Against both: `TODO.md:46` "**BUILT 2026-09-29** … Full suite 1057 passed", and the commit itself.
- **Proposed fix:** update README, STATUS and the CLAUDE.md status line for R1.2 built, 1057 passed and 6 skipped, and the R1.1 audit triaged.

## 3. Honest negatives (checked and found sound)
- **The lead's claims reproduce.** On the server at `192c1fa`:
  - `1057 passed, 6 skipped in 66.40s`;
  - the register tests `22 passed`;
  - `scripts/ledger_check.py`: `260 entries checked; 0 violation(s)`;
  - `wc -l`: `look_register.py` 290, `look_claims.py` 159, `look_gate.py` 49.
  - The eight proof tests named in GAP-P12D-98 exist and pass. Their assertions match their names, except that one of them locks in E-R12-01's bypass (`test_look_claims.py:89`).
- **The spec's D-d schedule is a valid Alpha-Spending sequence.** 0.03 then half the unspent is γ = (0.6, 0.2, 0.1, …), which sums to 1, so it controls lifetime FWER ≤ 0.05 by Tian & Ramdas's construction. Because it is a Bonferroni-type bound, it holds under arbitrary dependence. That makes it the right choice over α-investing: Javanmard & Montanari's FDR guarantee needs null p-values "independent from the other p-values", and every ACIS cycle re-tests on the same 2012–2023 history. The defect is only that the code does not enforce the schedule (E-R12-04).
- **Re-testing the same family-version in a later cycle is valid** under alpha-spending: each test spends its own αi, and the union bound covers repeats.
- **Float serialisation is byte-stable on both platforms observed.** The laptop runs Python 3.11.9 and the server 3.11.2, both `sys.float_repr_style == 'short'` (Python 3.1's shortest-round-trip repr), so a stored vector re-hashes identically after `json.loads`. Python's docs note a fallback to the legacy algorithm "if the required features are not found" (https://docs.python.org/3/whatsnew/3.1.html, fetched 2026-09-29), so this is a platform property worth an assertion, not a guarantee.
- **The vector cannot be swapped under its hash.** `load_vector` re-hashes the parsed content, so a different file under the same name is refused (and the proof test edits a byte and is refused). Finding content matching a given sha256 is infeasible. NaN and inf are refused in vectors (`store_vector`) and in declared spaces (`json.dumps(allow_nan=False)` at hash time).
- **Domain collisions between hash uses are impossible in practice.** A vector payload, a declared space (a dict with required keys), a variant tuple (a JSON array) and a cost map have disjoint JSON shapes.
- **The declared choices that hold:**
  - renaming the FAMILY does not launder a repeat (`variant_hash` excludes it);
  - a different `model_id` does not launder a repeat (`variant_hash` excludes the origin);
  - the refusal reads every look line of every family and every origin, and tolerates pre-v2 lines that have no `claim`;
  - cycle rows chain continuously with looks (`prev_hash` across kinds, `broken ()` over interleaved rows in `p3`) and are skipped by `family_counts`, `summary` tier totals and `looks()`.
- **Register-first, in the repository.**
  - The only real-provenance grade path at `192c1fa` is `scripts/run_oos_validation.py` → `run_walk_forward` → `look_gate.begin_grade`.
  - `cost_stress_ladder.py`, `falsify_engine.py` and `synthetic_grade.py` grade synthetic sources, and still write a tier-0 line first.
  - The lab modules are structurally barred from real data (`test_lab_hygiene.py`).
  - `--origin` and `--recon-commit` are `required=True`, so the script never writes an origin the operator did not state (its documented example is a separate matter, E-R12-01).
- **The literature exemption is consistent with the multiple-testing literature in spirit.** Harvey, Liu & Zhu (NBER w20592, abstract fetched 2026-09-29): "Given this extensive data mining, it does not make any economic or statistical sense to use the usual significance criteria for a newly discovered factor." A published rule is itself a product of field-wide search, and §5.6 credits it only on post-publication data. (The register does not yet check that window; see E-R12-02's ledger note.)

## 4. What I could not verify
- **Sarkar & Vafa's full text.** SSRN returned 403 and OpenReview a bot wall; only the ICML 2025 abstract was read.
- **Nosek et al.'s full text.** PNAS returned 403, PMC a reCAPTCHA, Europe PMC a 500; only the RePEc abstract was read, so its "pre-existing data" section is not quoted.
- **Foster & Stine's abstract** (publisher and repository blocked). α-investing is characterised through Tian & Ramdas's and Javanmard & Montanari's descriptions of it.
- **Not consulted:** Hansen (2005) SPA; Anthropic's Transparency Hub page (the models-overview table was sufficient).
- **Gençay, arXiv 2608.27734**, which GAP-P12D-66 cites, was not fetched.
- **Whether any real-data grade was ever computed outside the repository** (scratch scripts, notebooks) cannot be seen from the code. The canonical register does not exist on the laptop, so no *registered* real-data look exists.
- **The HistData source** (`sources.py:69`, `provenance = "real"`) was not exercised; the probes used a stand-in `DukascopyTickSource`.

## 5. Residual risk
- **Even with every fix, the register is self-authored.** Its value as evidence to anyone but its author rests on an externally held commitment (E-R12-07 / GAP-P12D-86). Until one exists, "pre-registered" means "written before, by the author's own account".
- **Contamination through the repository itself.** Every agent session reads research reports and, soon, real-data outcomes. In a project where LLM agents originate nearly every hypothesis, a `human` origin is an attestation no code can check. The only structural protection is forward data, which is what §5.6 already says. E-R12-01/02 are about not letting the register's labels erode it.
- **Power decays geometrically under the ratified spending schedule:** α8 = 0.05·0.4·0.5⁶ ≈ 0.0003 after two years of quarterly cycles. That is correct by construction, and it means later cycles can confirm almost nothing on the same history.
- **The verdict (R1.4) is where these recording gaps bite.** Recording choices are append-only, so the fixes to E-R12-01, 02, 03 and 06 belong before the first tier-2 look, not with R1.4.

## 6. Sources (all accessed 2026-09-29)
1. RFC 8785, *JSON Canonicalization Scheme* — https://www.rfc-editor.org/rfc/rfc8785 (§1.1, §3.2.1, §3.2.2.3, §3.2.3, Appendix B).
2. Python `json` documentation — https://docs.python.org/3/library/json.html
3. Python 3.1 "What's New" (float repr) — https://docs.python.org/3/whatsnew/3.1.html
4. Bailey & López de Prado (2014), *The Deflated Sharpe Ratio* — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf (pp. 3–4, 8–9, 14; appendix A.3)
5. Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns*, NBER w20592 — https://www.nber.org/papers/w20592
6. White (2000), *A Reality Check for Data Snooping*, Econometrica 68(5) — https://users.ssc.wisc.edu/~behansen/718/White2000.pdf (pp. 1097–1099, 1110)
7. Tian & Ramdas, *Online control of the familywise error rate*, arXiv:1910.04900 (§2) — https://arxiv.org/pdf/1910.04900
8. Javanmard & Montanari, *Online Rules for Control of FDR and FDX*, arXiv:1603.09000 — https://arxiv.org/abs/1603.09000
9. FDA, *Multiple Endpoints in Clinical Trials, Guidance for Industry* (Oct 2022) — https://www.fda.gov/media/162416/download (§II.C pp. 5–6; Appendix §5 pp. 20–21)
10. Sarkar & Vafa, *Lookahead Bias in Pretrained Language Models* (ICML 2025 workshop abstract) — https://icml.cc/virtual/2025/51018
11. Glasserman & Lin (2023), *Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis*, arXiv:2309.17322 — https://arxiv.org/abs/2309.17322 (abstract: "backtesting produces biased results if the training and backtesting periods overlap"; it corroborates the law's premise and is not the basis of a finding)
12. Cheng et al. (2024), *Dated Data: Tracing Knowledge Cutoffs in Large Language Models*, arXiv:2403.12958 — https://arxiv.org/abs/2403.12958
13. Kong et al. (2026), *Evaluating LLMs in Finance Requires Explicit Bias Consideration*, arXiv:2602.14233v1 — https://arxiv.org/html/2602.14233v1
14. Anthropic, *Models overview* (reliable-knowledge vs training-data cutoffs) — https://platform.claude.com/docs/en/about-claude/models/overview
15. Nosek, Ebersole, DeHaven & Mellor (2018), *The Preregistration Revolution* (abstract) — https://ideas.repec.org/p/osf/osfxxx/2dxu5.html
16. Crosby & Wallach (2009), *Efficient Data Structures for Tamper-Evident Logging*, USENIX Security — https://www.usenix.org/legacy/event/sec09/tech/full_papers/crosby.pdf (§1, §2.1–2.2)
17. RFC 3161, *Time-Stamp Protocol (TSP)* — https://www.rfc-editor.org/rfc/rfc3161 (§1, §2.2)
