# _SPEC_REVIEW_PASS.md — the review pass is DONE. Next step: BUILD.

> **STATUS (2026-07-05): the verification pass is complete.** The full ACIS specification is built — master `ACIS_SPEC.md` v2.1, the nine deep layer specs in `specs/`, the audit register `SPEC_AUDIT.md`, and the skeleton directory architecture are all in place and reconciled. **You are not being asked to do another pass.** Since you can see the project spec is already built, it is time to **build the engine**, not re-review it.
>
> **Start building** per `ACIS_SPEC.md` §15 (strict phase order): Data layer → NVMA → QIEA → Alpha Arena → Governor → paper integration → Execution → Risk + guardrails → `monitoring/` MCP → backtest/§14 validation → live (only after §14 out-of-sample minimums + human sign-off). Build only into the `[DIR:...]`-tagged directory for each section; do not start a phase before the previous phase's tests pass; land the downward-only import-linter contract test before Layer 2. Honour every rule in `CLAUDE.md` and `specs/ACIS-00-INDEX.md` §5. The guardrail/HALT/equity-floor items in `SPEC_AUDIT.md` §D and `KNOWN_GAPS.md` remain human-only — implement them as specified, and do not resolve the OPEN human-decision items yourself.

---

**The material below is retained as the record of how the pass was run** — use it only if a *new* layer is added later via a master-spec edit and needs its own verification, or to re-verify a specific area before building it. It is no longer a standing instruction to re-review the whole set.

---

## 0. Ground rules (do not violate)
- **The spec is the build authority.** If code (when it exists) and spec disagree, the spec wins. If you think the spec is wrong, **stop and raise it** — do not silently deviate (CLAUDE.md).
- **Guardrails are human-only.** You may **not** change `config/guardrail_limits.yaml`, the equity floor, or HALT/veto semantics — not via a fix, a flag, or a "temporary" hook. There is no force flag. Anything touching them is *raised*, never *applied*. See the OPEN items in `SPEC_AUDIT.md` §D and `KNOWN_GAPS.md` GAP-0002/0003/0004.
- **Stay in ACIS only.** Do not touch or reference AXIS / Phronesis / Skopos / any cyber project. Confirm source curation (below) before trusting any Drive file.
- **Any clarifying fix you apply must be transparent:** update the relevant CHANGELOG, add/adjust the correction ID, and cross-reference `SPEC_AUDIT.md`. No silent edits.

## 1. Source curation — confirm before using anything from Drive
The ACIS specification sources are **exactly three** (verified this pass):
- `ACIS_Agent_Prompt.md` — Drive id `1L6pYHwav7pyXGrk6LEXaLL-sRrcYpgdo` (primary build prompt, S1)
- `Super_Forex_Agent.html` — Drive id `1I3gh3Sn39pWtHQXK1LgYRDyaIWhhncOa` (architecture brief, S2)
- "System Engineering Specs & Architecture: Phronesis, AXIS, ACIS" — id `1ExKEKYcVRXJJ9qP1ETrrlrpNayX81Lsfrs4RwKXoxa4` (master doc, S3)

**Excluded (do not treat as ACIS):** `Grok updated Architectural flow.txt` (a "Super-Agent DAO / Genesis Protocol" — forex is only an example wedge), the cyber-execution `.txt` files, `Autodev.txt`, `Gemini.txt`, the OpenHands/echo-server files. If new Drive files appear, classify them before ingesting — an ACIS source must be about the QIEA/NVMA/Alpha-Arena/Governor/Execution/Risk engine, not a general agent framework.

## 2. Read order for the pass (all `.md` files + skeleton)
1. `ACIS_SPEC.md` (master, currently **v2.1**) — the constitution. Read the CHANGELOG first to see C1–C7 and the raised-not-applied items.
2. `CLAUDE.md` — operating rules. Confirm the specs make its rules structurally enforceable (no LLM in fast loop, downward-only, human-only guardrails).
3. `specs/ACIS-00-INDEX.md` — the deep-spec map + dependency law + shared vocabulary + audit-correction assignments.
4. `specs/ACIS-01 … ACIS-09` — the nine layer specs, in order. Each follows the 15-section template in `_SPEC_AUTHORING_GUIDE.md` §6.
5. `SPEC_AUDIT.md` — the findings register (F1–F18, dispositions).
6. `KNOWN_GAPS.md` — GAP-0001…0005.
7. `README.md`, `_SPEC_AUTHORING_GUIDE.md`, this file.
8. **Skeleton directory architecture** — walk `core/{data,regime,optimizer,signals,governor,execution,risk}/`, `monitoring/`, `config/`, `tests/{unit,integration,backtest}/`, `scripts/`, `logs/`, `specs/`. Each `core/*` and `monitoring/` dir has a `README.md` marker.

## 3. The verification checklist (this is the pass)

### 3A. Cross-source consistency
- For every substantive rule in a layer spec, confirm it traces to S1/S2/S3 **or** to a documented correction (`Cn`/`F n`). A rule with no lineage is a red flag — either find its source or raise it.
- Re-run the reconciliations in `SPEC_AUDIT.md` §A (F1–F5) and §C (passed checks). Confirm none regressed: NVMA cadence still 60–300 s; cluster set still the 6-list; conviction still 0–1; layer priority still `Risk > NVMA > Governor > Alpha Arena > QIEA`.

### 3B. Every FIXED item is actually reflected (do not assume)
For C1–C7 and every `C-*-n` in the layer specs, open the named spec section and confirm the fix is present and unambiguous:
- **C1** session boundary defined in `system_config` and referenced identically by ACIS-01 (session tagging) and ACIS-03 (staging/promotion).
- **C2** QIEA staleness observable; the never-promote-mid-session rule is verbatim intact; position-close is **not** a trigger (F3).
- **C3** half-life advisory — confirm ACIS-05 §6 multiplies it by nothing and ACIS-02 marks it advisory.
- **C4** discount-then-discard order with the 0.50→0.425 test vector in ACIS-04.
- **C5** alpha-decay baseline validity + `alpha_decay_state` in ACIS-07.
- **C6** marginal-alpha normalisation contract in ACIS-05 (bounded/monotone/floor/neutral/cap/NaN-safe) — confirm it is a *contract*, and check whether the concrete function has since been chosen (GAP-0005).
- **C7** clusters may reference extension instruments; unknown symbol = config error.

### 3C. Every OPEN item is still tracked and still un-applied
- Confirm `SPEC_AUDIT.md` §D and `KNOWN_GAPS.md` GAP-0002/0003/0004/0005 are unchanged in intent and that **no** agent has applied a guardrail-adjacent change (F9 drawdown buffer, F10 slippage throttle, F8 force-promote). If any was applied, that is a violation — revert and re-raise.

### 3D. Structural invariant checks (logic-flaw hunting)
Walk the data-flow chain and verify each boundary object is: frozen, validated on construction, deep-immutable (F16), and consumed only by the layer directly below. Specifically re-derive these and confirm they still hold or are still tracked:
- **Downward-only law:** no layer spec references the internals of a layer above it; the import-linter contract test is required before ACIS-02 is built.
- **Single upward edge:** only Risk → Governor HALT; confirm no other stop path and no non-human resume of an equity/global HALT (ACIS-07 §15, ACIS-08 C-MCP-1).
- **Field-consumer completeness:** every field an object emits is consumed somewhere or explicitly declared advisory (this is how F7/half-life was caught). Sweep each dataclass in the INDEX §4 vocabulary for a dead field.
- **NaN boundary:** NaN cannot reach conviction (ACIS-02 C-REG-4 / ACIS-04 C-ALP-6) or a risk metric (ACIS-07 C-RSK-2).
- **Decimal boundary (F17):** every accounting quantity (size, PnL, NAV, equity) is Decimal; prices may be float.
- **Determinism:** fast-loop producers are deterministic; the only randomness is in Execution (seeded in tests).

### 3E. Skeleton ↔ spec agreement
- Every `[DIR:...]` tag in `ACIS_SPEC.md` §1 has a real directory on disk. ✔/✗ each.
- Every `core/*` + `monitoring/` marker README names the correct deep spec, inputs/outputs, and owned corrections, and matches the INDEX §3 table.
- No stray directories exist that the spec did not authorise (new top-level dirs require a spec edit first).
- `config/`, `tests/*`, `scripts/`, `logs/` exist (placeholder-kept).

### 3F. Template completeness
- Each `specs/ACIS-0N` has all 15 binding sections + metadata table + changelog, and its §13 Logic-Flaw Registry addresses the corrections assigned to it in INDEX §6. A missing section = the layer spec is not done.

## 4. What to produce at the end of the pass
1. A short **pass report** (append to `SPEC_AUDIT.md` under a dated "Review pass N" heading): what you re-verified, any new findings (as new `Fn`), any FIXED item that had regressed, and confirmation that OPEN/guardrail items remain un-applied.
2. Any **clarifying, non-guardrail fixes** applied inline with updated CHANGELOGs + correction IDs.
3. Any **new gaps** in `KNOWN_GAPS.md` (Severity/Likelihood/Status/Area/Description/Justification/Linked).
4. If you found nothing wrong, say so explicitly — "re-verified, no changes" is a valid and valuable result. Do not invent work.

## 5. What NOT to do
- Do not write engine `.py` code (this repo is spec + skeleton until a human starts the build phases; SPEC §15).
- Do not apply guardrail/HALT/sizing-semantics changes — raise them.
- Do not re-ingest the excluded Drive files or pull in AXIS/Phronesis material.
- Do not expand scope (SPEC §17 non-goals are hard walls: no dashboards, extra indicators, speculative abstractions).
- Do not present in-sample backtest numbers against §14 targets (there are no numbers yet — do not fabricate any).

---
*Companion docs: `_SPEC_AUTHORING_GUIDE.md` (how the deep specs were authored) · `SPEC_AUDIT.md` (findings) · `specs/ACIS-00-INDEX.md` (map).*
