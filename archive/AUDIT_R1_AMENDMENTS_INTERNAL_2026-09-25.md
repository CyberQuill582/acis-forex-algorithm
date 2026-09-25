# AUDIT — the R1 spec amendments (commit `271d8e0`), INTERNAL-CONSISTENCY lens — 2026-09-25

> **Brief:** `AUDIT_BRIEF_R1_AMENDMENTS_2026-09-25.md` (pinned at `c440b17`), INTERNAL lens plus the shared rules.
> **Under audit:** `271d8e0`: master v2.20 → v2.21, ACIS-03 v2.0, ACIS-04 v1.3, ACIS-09 v1.7, OOS_VALIDATION.md,
> BASELINE.md, CLAUDE.md rule 5, and ACIS-00-INDEX. The base for comparison is `271d8e0~1`.
> **Status:** COMPLETE. I am a finder, not a clearer (A5). This report is not a sign-off.

## Attestation
- **Fresh context.** The lead launched me cold, on the owner's explicit request. I had no prior session context. One
  session-limit interruption occurred, and I resumed from my own on-disk notes and scratch files.
- **Model.** Opus 5.5 (`claude-opus-5-5[1m]`), at or above the A2 floor.
- **Order of reading (A4).** I read the diff first and formed my own view (interim notes F-A..F-L, saved before
  anything else). Only then did I read `R1_LEAD_REVIEW_2026-09-25.md` and `CLOUD_AUDIT/reports/r1/PLAN_R1.md`.
- **No subagents, and no web calls** (0 of the 5 allowed).
- **Repository untouched.** This file is my only write to the repo.
- **Scratch.** `%TEMP%\claude\…\scratchpad\audit_r1_internal\`. It holds the old and new trees (`git archive`) and these
  reproduction scripts with their outputs:
  - `holdout_draw_mine.py`, `holdout_metals.py`
  - `eprocess_sim.py` → `.out`
  - `e2_reconcile.py`, `e2_reconcile2.py` → `e2_reconcile.out`
  - `stageA_fwer.py` → `.out`
  - `netting_pair.py` → `.out`
  - `rounding.py` → `.out`

## Summary
The claim that the guard *values* did not change holds:
- no `config/` file is touched;
- §6–§7 and §8–§9.5 are byte-identical;
- the confidence < 0.55 veto is kept.

The amendment does NOT hold on three other claims.

**1. "No HALT/veto semantic changed."**
- The machine live gate reads `ValidationReport.passed`. C-BT-11 v2 redefines `passed` without the Max DD and SPX
  gates, and a literal reading also drops the C-BT-2/4/7 conditions.
- One NVMA `tradeable=False` trigger (NO_PARAMS_FOR_REGIME) was replaced by an **undefined** predicate ("validated").

**2. Loosening beyond what was ratified.**
- The ratified A6 draft made rung 1 = B0–B5. The applied text drops **B0** ("machinery proven first").
- The applied §4 sentence "NVMA's one effect on trading is the veto" silently licenses removing a dampen-only sizing
  factor. §6 was not amended.
- The spec schedules its retirements by a phase name ("R1.7") that is defined only in PLAN_R1. That phase also
  retires the §6 anti-greed floor.

**3. "Stricter meanwhile."** This is false as a universal claim. The staging rule, which the text calls binding and
"unchanged", has its only implementation scheduled for `git mv`.

---

## Findings, ranked

### F1 — HIGH (likelihood medium): C-BT-11 v2 redefines `passed`, the field the machine live gate reads, without the §14 Max DD and SPX gates. A literal reading also drops the C-BT-2/4/7 safety conditions.
**The new definition.** `specs/ACIS-09-BACKTEST_VALIDATION.md:178` (new):

> "`passed` = stage A and stage B passed, and stage C did not kill."

**How it interacts with the ladder.** Master §14 rung 1 (ACIS_SPEC.md:406): "= ACIS-09 C-BT-11 v2 `passed` (stages
A–C), **plus** the two gates above". So `passed` excludes Max DD < 15% and SPX < 0.25 by construction.

**The live gate is unchanged.** ACIS-09:198:

> "phase 12 (live broker) is permitted only when a persisted per-account `ValidationReport.passed == True` … and a
> human sign-off record exist; ACIS-08's `acis_set_mode(live)` checks both"

The code path is `monitoring/mode.py:63` (`if not self._validation_ok()`).

**What the as-built `passed` contains today.** `tests/backtest/report.py:115-124`:
- every §14 row, including `max_drawdown` and `spx_correlation`;
- ≥ 2 years and ≥ 2 folds (C-BT-2);
- ≥ 30 trades;
- the trial count and the DSR;
- `not rule_violations` (C-BT-7, the §9.5 account rules);
- `guardrails_ok` (C-BT-4: "a relaxed-limit run cannot gate live").

**The failing case.** Build C-BT-11 v2 as written at R1.4. A record with a 30% OOS drawdown, an SPX correlation of 0.6,
or a `guardrail_hash` mismatch gets `passed == True`, and `acis_set_mode(live)` then accepts it with a human token.

The only barrier left is the human's reading of a field named `passed`. The master's "§14 minimums means rung 2"
(ACIS_SPEC.md:410) is enforced by nothing mechanical. ACIS-09's live-gate paragraph still says `passed`, and ACIS-08
still says "§14 minimums were met (validation record)".

**Why this is beyond what was ratified.** A2 ratified replacing the **DSR** clause. It did not ratify removing the
drawdown, SPX, guardrail-hash or rule-violation conditions from the machine gate. Whether C-BT-2/4/7 still apply is
contradictory:
- C-BT-2/4/7 each still say "`passed` requires / forces `passed=False`";
- the v2 sentence is an equality.

A builder must guess which one wins.

**Proposed ledger entry:** severity high · likelihood medium · open [spec].
- Define `passed` as the conjunction of the C-BT-11 v2 verdict, the §14 gates (Max DD, SPX), C-BT-2, C-BT-4 and C-BT-7.
  Alternatively, re-point the ACIS-09/ACIS-08 live gate to a named `rung2_met` that includes them.
- Amend the ACIS-09 "The live gate" paragraph to "rung 2".
- Pin it with tests: a drawdown-failing verdict and a guardrail-hash-mismatched verdict must each be refused by
  `set_mode(live)`.

### F2 — HIGH (likelihood medium): the applied claim ladder drops B0, "machinery proven first", which the ratified A6 draft required for rung 1
**What was ratified.** R1_LEAD_REVIEW A6 NEW (ratified as R1-D7), R1_LEAD_REVIEW:319:

> "**'Validated on history (kill-tested)'** = B0–B5."

PLAN_R1 §6 B0 reads: "planted detected within 2 se of theory power; null false-detect ≤ 5% + 2 se; leaky oracle refused
by structure; RSIM ≡ engine (R1–R6); … planted/null variance ratio within 1 ± 0.05 | all pass at `recon_commit`". It
protects against "a grader that is itself wrong (GAP-P12D-37…)".

**What was applied.** ACIS_SPEC.md:406: rung 1 = "C-BT-11 v2 `passed` (stages A–C), plus the two gates".
- C-BT-11 v2 carries B1–B5: registration, stage A = B2 + B3, stage B = B4, stage C = B5.
- It has **no machinery-calibration precondition**.
- C-BT-12 says "synthetic markets grade MACHINERY", but it makes no calibration a precondition of any verdict.
- A grep for "machinery", "B0" and "positive control" finds no binding precondition in master or ACIS-09.

**The failing case.** A verdict is issued before the lab has shown the verdict's false-positive rate ≤ 5% + 2 se, and
it is still called "Validated on history". That is the GAP-P12D-37 class (critical): a grader that is itself wrong.

This loosens beyond the ratified text. Rung 2 inherits the omission.

**Proposed ledger entry:** severity high · likelihood medium · open [spec]. Add B0 to rung 1 and to C-BT-11 v2 as a
precondition: no real-data verdict unless the lab calibration at the same `recon_commit` passes. It is tightening
only, and it restores the ratified text.

### F3 — HIGH (likelihood high): the new `tradeable=False` trigger rests on an undefined predicate, "validated". Under its natural reading an LLM-originated family can never trade, and the as-built demo is looser than the spec.
**Where the predicate appears.**
- ACIS_SPEC.md:93: "| Instrument has no registered, validated rule set | `tradeable=False` |".
- ACIS-03 v2.0 lines 22 and 27.
- CLAUDE.md rule 5.

"Validated" is defined nowhere. I grepped the master, all specs, CLAUDE.md and OOS_VALIDATION.md for any definition.

**Reading 1: validated = rung 1, "Validated on history".**
- **(a) Deadlock.** ACIS-09:176: "For an LLM-originated family …, stage D is the only stage that can credit a pass",
  while `passed` requires stages A and B. So an LLM-originated family never becomes validated. It is then
  `tradeable=False` everywhere, including paper and demo, and it can never build the forward record that stage D needs.
- **(b) The interim is looser, not stricter.** The as-built NVMA vetoes only NO_PARAMS_FOR_REGIME
  (`core/regime/nvma.py:350`). QIEA always stages some champion. So the as-built engine, and the Track A demo, trade
  parameter sets that nobody validated in the v2.21 sense. On a *veto*, the as-built engine is **looser** than the
  amended spec.

**Reading 2: validated = registered plus provenance-cleared.** Then the veto is nearly vacuous, since every running
module is registered.

**The failing case.** Either reading breaks something. A16 applies: a veto predicate that no test can move is
decoration.

**Proposed ledger entry:** severity high · likelihood high · open [spec, owner — veto semantics].
- Define "validated" precisely: which rung, per account or per family, and in which modes.
- Resolve the LLM-origin deadlock, for example by letting a registered LLM family trade in a practice mode only, at
  minimum size.
- Record that until then the as-built demo trades unvalidated sets. That is honest, not stricter.

### F4 — HIGH (likelihood medium): the staging rule is called binding and "unchanged", but its only implementation is scheduled for `git mv`, with no successor named
**The amended ACIS-03 contradicts itself.**
- ACIS-03 v2.0:25: "The staging rule (§7–§8) binds every parameter change, unchanged".
- ACIS-03 v2.0:28: "**Legacy until R1.7:** the QIEA purpose and **every QIEA section below** … R1.7 retires it by
  `git mv`: `qiea.py`, `evolve_step.py`, `fitness.py` …, **the ParamLibrary staging** and the genome."
- §7–§8, the staging rule, are among "the QIEA sections below".

**The staging rule's entire implementation is the thing being retired.** It lives in `core/optimizer/param_library.py`:
- `PromotionForbiddenError` at line 28;
- the `PositionGate` protocol at line 32;
- `ParamLibrary.stage`, `promote` and `on_boundary` at lines 112, 133 and 183.

Its tests are also in scope: `tests/unit/test_param_library.py::test_promote_mid_session_raises_even_close_looking`,
`::test_promote_with_open_positions_raises` and `::test_position_close_is_not_a_promotion_trigger`.

**An unledgered dependency.** `core/signals/provenance.py:22` does `from core.optimizer.param_library import
PromotionForbiddenError`; this is the §5.7 rung-ladder gate. It is the same class as GAP-P12D-99 (the indicators),
which *was* ledgered. This one is not.

**The test contract has the same dependency.** Master §13 phrases the staging test as "QIEA respects session-boundary
rule (attempt mid-session promotion → must raise)", so it is QIEA-bound too.

**The failing case.** R1.7 executes the listed `git mv`. The "critical deployment rule (non-overridable)", which
CLAUDE.md rule 5 calls law, is left with no code and no test, while the spec still says it binds.

**Proposed ledger entry:** severity high · likelihood medium · open [spec + impl].
- Name the staging rule's successor home, for example a `rule_registry` stage/promote that keeps
  `PromotionForbiddenError` and the `PositionGate`.
- Carve §7–§8 and C1/C2 out of the legacy scope explicitly.
- Move `PromotionForbiddenError` before R1.7, as GAP-P12D-99 does for the indicators.
- Re-home the §13 staging test.

### F5 — HIGH (likelihood high): §4's "NVMA's one effect on trading is the veto" contradicts unamended §6, C4, §3.6 and ACIS-02, and licenses an unannounced size-up. "Every trigger stays" is false.
**The new text.** ACIS_SPEC.md:167: "regimes no longer gate rule families or key their parameters, and **NVMA's one
effect on trading is the `tradeable=False` veto above, which is UNCHANGED (every trigger stays…)**".

**Unamended text it contradicts:**
- **§6:261-263.** `raw_size = BASE_UNIT_USD × conviction × … × (regime_stability × regime_confidence) × …`. The code
  is `core/governor/capital_governor.py:292` `regime_f = regime.regime_stability_score * regime.confidence`, used in
  line 303. Here regime_f ∈ [0,1]: stability is in 0..1 (`regime_types.py:56`), and confidence is ≥ 0.55 when
  tradeable.
- **§5.5 C4:215.** The MEDIUM-vol ×0.85 discount (`core/signals/agon.py:272`). And "LOW-volatility ranging → Trend
  Following and Breakout modules **disabled entirely**", which contradicts "Regimes no longer gate families".
- **§3.6:130.** "raise the effective volatility class" as a conservative lever.
- **ACIS-02 v1.2, unamended.**
  - Line 98 step 8, "if none exists for the new regime → force `tradeable=False` until QIEA evolution completes".
  - Line 150, C-REG-6, which "owns conflict-table row 'regime shift + no evolved params'". That row no longer exists
    in master §2.
  - Line 160: "QIEA keys its param library by `regime`; AGON gates its strategy modules by `regime` +
    `volatility_class`".
- **The import-contract rationale.** `tests/unit/test_import_contract.py:12-13` cites "§6's sizing formula consumes
  regime factors (governor→regime)".

**The failing case (size-up).** Build R1.6 from §4 as written, so that NVMA has no effect beyond the veto. `regime_f`
leaves sizing, and every order grows by 1/regime_f: 3.3× at stability 0.5 and confidence 0.6. This matches
GAP-P12D-68 item 3's intent ("the regime factor would leave sizing").
- The owner ratified "NVMA keeps only its safety veto" (the A7 draft).
- Neither the A7 draft nor §6 says that this is a **size increase**.
- The commit and changelog say "No … HALT/veto semantic changes".

**The veto trigger claim is false.** The NO_PARAMS_FOR_REGIME trigger (`nvma.py:350`, ACIS-02 C-REG-6) was replaced
by a different, per-instrument, undefined predicate (F3). So "every trigger stays" does not hold for it. That change
was ratified (the A4 §2 row), but the receipt names the wrong mechanism: A16 ("a receipt naming the wrong mechanism is
worse than a missing one").

**Proposed ledger entry:** severity high · likelihood high · open [spec, owner].
- Amend §6, C4, §3.6 and ACIS-02 to match §4, or narrow §4's sentence.
- Put the regime_f removal to the owner explicitly, as a size-up.
- Correct the v2.21 changelog, the commit claims and the §4 wording: one veto trigger was *replaced*, not kept.

### F6 — MEDIUM-HIGH (likelihood high): the stage-D bettors are mis-specified as written, and E2 is not a kill. Rung 2's "E2 silent ≥ 3 months" is met by 99.8% of dead strategies.
The text is ACIS-09:172-175 (new). Every figure below is reproduced in `eprocess_sim.py`, `e2_reconcile*.py`.

**(a) Units.** "E2 (kill): the same bettor on μ_claim − r, with μ_claim = SR̂_dev/2" subtracts a Sharpe ratio from a
daily return fraction. Implemented literally, it kills every family on **day 1** (σ* read as daily) or **day 10** (σ*
read as annual), even at a true SR of 0.

**(b) σ\* units.** "σ* is the declared vol target". A vol target is conventionally annual; GAP-P12D-101 speaks of "a
10% vol target". With an annual σ*, E1's power at a true SR of 1.0 is **0.00 in 20 years**. The plan's own timings
need σ* read as the *daily* vol.

**(c) Self-contradiction.** The formula clips, `max(r/(6σ*), −1)`, but the next bullet says "A day beyond −6σ* … is a
tripwire … and is **never clipped**."

**(d) Power, under the favourable daily-σ\* reading.**
- **A dead strategy** (true SR 0), claims SR̂_dev/2 = 0.25–0.6:
  - kill (W ≥ 20) by 1 year: **1%**;
  - by 3 years: 3–9%;
  - P(E2 silent for the first 3 months) = **0.998**.
- **A losing strategy** (true SR −0.5; claim 0.4): kill by 1 year 3%, by 3 years 20%.
- **E1**, the edge shown: at SR 0.5, 22% within 10 years; at SR 1.0, 40% within 5 years.
- **The plan's figure does not match its label.** PLAN_R1 §1 claims "Killing a false claim: 25% by 1 year, median 3.1
  years (claim 1.0, truth 0)". That reproduces only at the **freeze** threshold W ≥ 5 (18% by 1 year, median 3.1
  years). At the **kill** threshold W ≥ 20 it is 4% by 1 year and a median of 6.6 years.

**The consequence.** The rung-2 condition "E2 silent ≥ 3 months" carries almost no evidence, and the forward kill is
far slower than the evidence behind the ratification stated.

**Proposed ledger entry:** severity medium-high · likelihood high · open [spec].
- Define μ_claim in return units: (SR̂_dev/2)·σ_daily.
- Define σ* as the declared daily vol, σ_ann/√252.
- Resolve the clip/tripwire contradiction.
- Restate what "E2 silent ≥ 3 months" certifies.
- Correct PLAN_R1's kill figure, which is the freeze figure.

### F7 — MEDIUM-HIGH (likelihood high): §14's per-account law and C-BT-7 conflict with the family-level, research-universe verdict, so the graded book is not the tradeable book
**The unamended per-account law.**
- ACIS_SPEC.md:412: "Targets are evaluated **per attached account** on that account's enabled universe … the §9.5
  platform limits apply *during* the evaluation run".
- C-BT-7 (ACIS-09:147) says the same.

**The new verdict grades something else.** C-BT-11 v2 grades a family's research-universe portfolio (23 explored
instruments, RSIM) with no account and no rules active.

**What an account can actually hold.** The new live-eligibility rule (OOS_VALIDATION.md) removes most of that
universe on small accounts: 15 of 23 instruments can never hold a lot at $6k (GAP-P12D-101).
- ACIS-05 step 9 flattens a weekend-flat account weekly.
- The pre-close bans apply on every account.

So the validated portfolio, with its N_eff and IDM from 23 instruments, is not what the account trades.

**The C8 claim does not hold.** C8's new sentence (ACIS_SPEC.md:192), "so the graded book is the tradeable book", is
false wherever live-eligibility, the weekend flatten or the pre-close bans bind. The spec does not say which grade
rung 1 uses.

**Proposed ledger entry:** severity medium-high · likelihood high · open [spec].
- Rung 1 must also hold per account: re-grade on the account's live-eligible universe with its rules active.
- Or state that §14's per-account paragraph is superseded, which would be an owner-only loosening.

### F8 — MEDIUM-HIGH (likelihood low-medium): the spec schedules retirements by "R1.7", a phase defined only in PLAN_R1 (finder evidence). That definition also retires master-§6/§7 laws that v2.21 did not amend.
**Where the phase name appears.** ACIS_SPEC.md:178 and :188, and ACIS-03 v2.0:28, retire things "at R1.7". No spec
document defines R1.7.

**The only definition.** PLAN_R1 §2, R1.7 row. It retires `qiea.py`, … and also:
- `marginal_alpha.py`: master §6, "If marginal ≤ 0 → factor floors at 0.25 (**scaling down is mandatory when edge
  shrinks**)", in `core/governor/marginal_alpha.py:17` `FLOOR, NEUTRAL, CAP = 0.25, 1.0, 1.5`;
- the fragmenter and VenueQuality (§7);
- "the conviction pipeline" (C4);
- MR, SCALP and PAIR.

`diff` of master §6–§7, old against new, shows them UNCHANGED.

**What was ratified.** R1-D4 covers the review's list only: qiea, evolve_step, fitness, ParamLibrary staging and the
genome. The review places it "after R1.6"; the spec says "at R1.7".

**The failing case.** A builder executes "R1.7" from its only definition. The §6 anti-greed floor goes, which is up to
a 4× size-up in a shrinking-edge state, and nothing in v2.21 authorised it.

**Proposed ledger entry:** severity medium-high · likelihood low-medium · open [spec].
- Define R1.7's scope in the spec, or replace the phase name with an explicit retirement list.
- State that marginal-alpha, the fragmenter and C4 are retired only by their own master amendment.

### F9 — MEDIUM (likelihood certain): rung 2, which is the §15 live gate, is circular until a practice mode exists (GAP-P12D-69 is open)
Rung 2 (ACIS_SPEC.md:407) needs three things:
- "live = replay on the demo feed";
- E3 certified from real fills;
- "E2 silent ≥ 3 months".

All three need orders on a demo venue.
- Paper mode "never gains a real-order path" (§7.5).
- Live mode needs "§14 minimums", which is now rung 2 (ACIS_SPEC.md:410).

So the live gate requires evidence that only the live gate can unlock. v2.21 makes GAP-P12D-69's `practice` mode a
precondition of the live gate itself, but neither side references the other.

**Proposed ledger entry:** severity medium · likelihood certain · open [spec]. Link rung 2 to the GAP-P12D-69 practice
mode and land that mode's text before rung 2 is relied on.

### F10 — MEDIUM (likelihood high): the "no-trade buffer" is defined two incompatible ways, and either way it needs portfolio state that §5.5 says AGON lacks
**The two definitions.**
- **(A) A forecast deadband.** §2:94, CLAUDE.md rule 5, and ACIS-04 C-ALP-4:167: "a net forecast inside the no-trade
  buffer places no order".
- **(B) A position buffer (Carver).** §5.5:207 and ACIS-04 v1.3: "one target position per instrument, with a 10%
  no-trade buffer".

**The failing case.** Take an open long whose families now net to about 0.
- Under (A): "no order", so the full position stays open with no exit except the broker disaster stop.
- Under (B): the position is reduced to about 0.

**Where the buffer must live.** Either form compares against the current position. §5.5:202 says "AGON does NOT know …
portfolio state", and the import contract forbids it (`signals → {optimizer, regime, data}`,
`test_import_contract.py:39`). Yet the text places the buffer in AGON's section.

**Proposed ledger entry:** severity medium · likelihood high · open [spec, with the ACIS-04 interface amendment].
- Pick one definition. Carver's is (B).
- Put the buffer in the Governor.
- Reword §2, CLAUDE rule 5 and C-ALP-4.

### F11 — MEDIUM (likelihood medium): netting plus the ±20 cap turns a pair trade into a single naked leg, which the pair laws forbid
**The construction** (`netting_pair.out`; FDM 1.5, equal family weights, buffer = 1 forecast unit):
- EURUSD is capped at +20, so pair entry and exit move its target by **0.00**: no order.
- USDCHF moves by 2.5: an order.

**What the pair laws say.** §5.5 (the legacy pair text), C-ALP-7 and the §13 "pair leg orphaned" glitch class all
forbid a half-group. "Pair groups stay all-or-none (C-EXE-8)" cannot bind, because the capped leg produces no order to
group.

**Proposed ledger entry:** severity medium · likelihood medium · open [spec, the ACIS-04 interface]. Define how a pair
family's legs survive netting (for example, a pair family is exempt from per-instrument netting, or it is refused
while either leg is capped), with a test.

### F12 — MEDIUM (likelihood high): the staging rule combined with continuous target positions is a permanent promotion deadlock, and §5.7 demotion is undefined under netting
**Why promotion never happens.**
- `promote()` requires `open_position_count() == 0`, book-wide (ACIS-03 §7 step 3; `param_library.py:32-35`).
- v2.21 makes the rule bind "a newly registered rule set" too (ACIS_SPEC.md:182).
- A pooled trend book on N instruments is essentially never flat.

So after the first registration nothing new can be promoted, except on weekend-flat accounts, which ACIS-05 step 9
flattens weekly.

**Why demotion is undefined.** §5.7:251 and ACIS-11's GAP-0019 transition stage removal "at the next session boundary
at which **that strategy** holds no open positions". Under netting, positions belong to the instrument's net target,
not to a family.

This is the conservative direction, but it will force a later loosening.

**Proposed ledger entry:** severity medium · likelihood high · open [spec]. Re-state the staging and demotion
conditions for netted target positions, for example "at a boundary, with the family's forecast contribution
phased", preserving never-mid-session, and decide it now while the rule's home is being re-written (F4).

### F13 — MEDIUM (likelihood medium): stage A's error budget, look correction and order registration are unstated
The figures are reproduced in `stageA_fwer.out`.

**No α split.** ACIS-09:154-164 has fixed-sequence at α = 0.05, plus "Families outside the order are Holm-adjusted
among themselves", with no split of α. The union FWER is **0.098** for independent sets.

**No look correction.** "≤ 3 registered looks per family" has no stage-A correction, while stage B states "Bonferroni
over ≤ 3 registered engine looks". At α = 0.05 per look, P(any of 3 looks passes | null) is 0.07–0.14, for look
correlations from 0.95 down to 0.

**The order is not pinned.** The text names no primary family (the review intends pooled trend). It does not say who
registers the order, where, or before which look, and it does not forbid a family being looked at before it is placed
in the sequence. Fixed-sequence control needs an order fixed before any look.

**Proposed ledger entry:** severity medium · likelihood medium · open [spec].
- State the total α and its split.
- State how the ≤ 3 stage-A looks are corrected.
- Name the primary family and require the order as a register row written before any stage-A look.

### F14 — MEDIUM (likelihood high): "the as-built code keeps the stricter path meanwhile" is false as a universal claim
The claim appears in ACIS-09:151 ("it is the stricter one"), ACIS-04:29 ("discard-both trades less than netting") and
the commit message.

**Counterexamples: the as-built path is looser in these places.**
- **(i) The verdict conditions.** `report.py:115-124` has no 2×-cost, ⅓-cost, passive-benchmark, held-out-kill or
  register condition. `look` is "Informational: no clause of `passed` reads it" (`report.py:82-83`). GAP-P12D-33 shows
  the DSR clause passing on 2 near-identical trials (DSR 0.9979).
- **(ii) The execution clock.** The as-built engine can execute inside the 17:00 New York rollover window, which v2.21
  forbids. `grep -i rollover core/governor core/execution` finds no ban, and TSMOM's daily bar closes at the rollover
  (`core/data/bars.py:102-112`).
- **(iii) Unvalidated rule sets.** The as-built engine trades them (F3).
- **(iv) Netting.** A lone as-built signal trades where equal-weight netting would dilute it into the buffer.

**What this does and does not mean.** The as-built code is v2.20 behaviour, so there is **no new risk versus v2.20
today**. The defects are two:
- the false receipt;
- the unexamined risk of *hybrid* states when R1.x lands piecemeal. For example, the R1.4 verdict landing before the
  R1.6 execution clock and lot rules would be looser than both designs.

**Proposed ledger entry:** severity medium · likelihood high · open [spec].
- Replace "stricter" with "the as-built v2.20 path, not uniformly stricter", and list the axes.
- Require each R1.x landing to state which v2.21 rules become live, and forbid landing the verdict (R1.4) before the
  rules it assumes.

### F15 — LOW-MEDIUM: C8's "positions round down exactly as execution does" is not what execution does, because C-EXE-6 rounds ORDERS down
The figures are in `rounding.out` (lot step 0.01).
- Current 0.10, target 0.057: RSIM holds 0.05, but execution sends 0.04 and holds **0.06**.
- The same happens on the short side.

On every reduction the executed book keeps more exposure than the graded one. "So the graded book is the tradeable
book" (ACIS_SPEC.md:192) fails on reductions.

**Proposed ledger entry:** severity low-medium · likelihood certain · open [spec + impl]. Define one rounding rule for
target deltas, shared by RSIM and C-EXE-6.

### F16 — LOW-MEDIUM: the embargo and walk-forward config do not fit a fixed family with continuous positions
- **The embargo.** It is "≥ max(7 days, the 95th percentile of the rule set's holding period)" (ACIS-09:178;
  OOS_VALIDATION.md). A holding period is undefined for a continuously adjusted target position.
- **The effect on the bar.** If the embargo is applied at every fold boundary of a *fixed* family (which has no training
  step, so nothing leaks), it deletes OOS days every year. Y then falls below 11, and the stage-A bar rises above the
  0.50 that GAP-P12D-102 derived.
- **The config.** ACIS-09 §5 still lists `train_window` as required and schema-fatal, and an expanding plan has no
  such key.

This is *unconfirmed* numerically; it is textual.

**Proposed ledger entry:** severity low-medium · likelihood medium · open [spec]. Define the holding period for target
positions, exempt fixed families from the per-fold embargo, and amend the §5 config keys.

### F17 — LOW-MEDIUM: C9 per member and the fixed-family plateau check cannot be computed as written
**C9 per member.** Master C9 (ACIS_SPEC.md:194) and ACIS-03 v2.0 §6.4 say "a member at E ≤ 0 over the development
span refuses the family". A member of a netted combination holds no positions or trades of its own, so its
E = winRate·avgWin − lossRate·avgLoss needs a standalone-simulation convention that is not stated: per instrument or
pooled, and before or after the ⅓-cost speed filter.

**The plateau check.** "±10% on any parameter" is undefined for a 3-speed family with fixed speed ratios.

**Proposed ledger entry:** severity low-medium · likelihood high · open [spec]. State the member-evaluation convention
and the family's plateau parameterisation.

### F18 — LOW: the held-out draw reproduces only under an unstated symbol spelling
My own code (`holdout_draw_mine.py`, `holdout_metals.py`) reproduces the stated set exactly when:
- symbols are hashed as "AUD/NZD", "XCU/USD", "GER40";
- the 8 on-disk instruments are excluded first.

**The spelling matters.**
- OOS_VALIDATION.md's own class list spells metals "XAU, XAG, XCU". Under that spelling the draw holds out **XAG**, not
  XCU.
- "EURUSD" and "EUR_USD" give different FX sets.

The set is frozen by being listed, so the impact is low. But the text claims a procedure that the text alone does not
reproduce.

**Proposed ledger entry:** severity low · likelihood certain · open [spec, editorial-plus]. Pin the exact hash-input
spelling, or cite the probe script.

### F19 — LOW (batched; one-clause dispositions): read-path and cross-spec residue
- **ACIS-11 v1.1 is unamended.** It keeps its own append-only attempt registry (`provenance.py` `attempts` table,
  C-PRV-4), while master now says "the attempt registry IS the look register". There are two registries in code, and
  it is not stated which is authoritative. → amend ACIS-11.
- **The review and the spec disagree on timing.** The review's A4 says retirements come "after R1.6"; the spec says
  "at R1.7". → align (see F8).
- **ACIS-00-INDEX.** §5 invariant 7 still reads "QIEA staging rule", and the ACIS-11 row reads "TO AUTHOR" although
  ACIS-11 is v1.1 LOCKED. The second is pre-existing, but it sits in the read path. → fix.
- **OOS_VALIDATION.md:62-63** still states the DSR ≥ 0.95 gate with no superseded mark. → mark it.
- **ACIS-09 C-BT-8** still carves outliers out of an average-duration row that is no longer gated, and ACIS-09 §5's split
  still says "QIEA may evolve here". → annotate as legacy.
- **Master §10.** Loop 1 is still "QIEA evolution …", so after R1.7 the slow loop has no stated job. → amend with F4.
- **Undefined constraints.** "At minimum size" (the rung-2 name) and "freezes scaling" (E2) are defined nowhere as
  sizing constraints. → define them, or drop them.
- **The test count.** README says "1002 tests passing"; the commit says "Suite 1008 passed". → refresh.

---

## Honest negatives (checked, and the claim held)
- **No guard value moved.** `git show --stat 271d8e0` touches no `config/` file, so `guardrail_limits.yaml` and the
  equity floor are unchanged. Master §6–§7 and §8–§9.5 are byte-identical old against new (the §6–§7 `diff` is empty).
- **The NVMA organic vetoes are kept.**
  - confidence < 0.55 (ACIS_SPEC.md:165, and the Governor's `low_confidence` override at `capital_governor.py:361`);
  - spread > 3×;
  - the dead market;
  - MACRO_EVENT, ILLIQUID and UNCLASSIFIED.

  The applied text is *stricter* than the ratified A7 draft, which omitted confidence.
- **The stage-A bar.** z₀.₉₅/√Y = **0.496** at Y = 11 and **0.520** at Y = 10, so "0.50–0.52" is correct.
- **The held-out draw** reproduces exactly, independently of the plan's probe, under the slash spelling (see F18 for the
  caveat).
- **The holdout kill.** t < −0.5 at Y = 2 is SR̂ < −0.354, which matches the plan's "SR̂ < −0.35".
- **E1's validity.** Clipping at −1 is anti-conservative in theory, since E[max(X,−1)] ≥ E[X]. Empirically, with daily
  σ*, P(sup W ≥ 20 | H0) over 10 years is 0.020 (normal), 0.028 (t3) and 0.029 (t2.2), all within Ville's 0.05. The
  clip binds about 2 days per path in 10 years.
- **W ≥ 20 matches α = 0.05** under Ville's inequality.
- **The alpha-decay guard is NOT made inert by continuous positions.** My hypothesis was refuted: `core/risk/monitor.py`
  `_apply_fill` books a `Trade` on every reducing fill (lines 107-113), so partial reductions feed the 50-trade windows.
- **The ledger check.** `python scripts/ledger_check.py` on the audited tree: "238 entries checked; 0 violation(s)".
- **The A6 rows.** The applied §14 retires exactly the five rows ratified (Sharpe, win rate, profit factor, positive
  months, duration) and keeps Max DD and SPX. The loosenings are elsewhere (F1, F2).
- **The new ledger pointers** GAP-P12D-86..102 all exist in KNOWN_GAPS.md, and ACIS-06 C-EXE-6/7/8 and ACIS-04 §6.6
  resolve.

## What I could not check
- **Whether the owner saw regime_f leaving sizing** when he ratified R1-D8 (F5). The drafts do not say so; only the
  owner can answer.
- **Lot rounding in the QIEA fitness and harness research path today.** I did not open `fitness.py` or `book.py` for
  lot steps, so any claim that research is looser than execution on lot rounding is *unconfirmed* and was left out of
  F14.
- **F16's Y reduction** is argued from the text; I did not simulate EWMAC holding periods.
- **The plan's other forward timings.** I reproduced E2 only; E1's plan figures agree with my simulation under the daily
  σ* reading. E3's certification speed was not simulated.
- **External facts** (Carver, FTMO, E8, the literature) are the EXTERNAL lens's scope, and I made no web calls.
