# The constitution adoption gate (placed in CLAUDE.md 2026-07-21; archived 2026-10-03)

Moved out of CLAUDE.md verbatim on 2026-10-03 by owner ruling ("Shrink it to a pointer"), as the block's own last line instructs. Steps 1 and 3 were done on 2026-07-21/22. Step 2, documentation hygiene, is still owed and is tracked in KNOWN_GAPS.md and TODO.md under GAP-P12D-155.

> ## ⛔ CONSTITUTION ADOPTION GATE — FIRST ACTION NEXT SESSION (placed 2026-07-21; self-retiring)
> **Do this before any build work continues** (before the `TODO.md` worklist), in order:
> 1. **Read `../specs_constitution/SPEC_CONSTITUTION.md` in full** (it is short) and hold ACIS to it.
> 2. **Documentation hygiene (A13 + A7).** Move every already-solved / `closed` ledger entry and any spent problem-tracking prose still in the live surface into `archive/` (or `KNOWN_GAPS_CLOSED.md`) — **`git mv`, never delete** — leaving the pointer-to-proof (gap ID / test name / spec §) live. Shrink the read path (`README → STATUS → TODO → CLAUDE → ACIS_SPEC → specs/00-INDEX → KNOWN_GAPS`) until it is short, current, and TRUE. **Never move anything an active phase still reads.**
> 3. **Audit the SPEC first (A3 + A4 + A6).** Launch the **two adversarial audits in fresh context (each agent Opus 4.8 or higher — never Sonnet/Haiku; A2 floor)** against **`ACIS_SPEC.md` (+ locked `specs/`) itself** — internal-consistency + external-referent — to catch spec flaws BEFORE auditing or writing more code. The external-referent auditor **uses Claude deep-research** to check the spec against real-world ground truth (definitions, market microstructure, the cited literature) and the known bug-classes of this kind of system. Pin the brief first (A4); triage every finding (A6 — a finding binds only after it survives refutation) before the build proceeds.
> 4. Only then resume the phase-12 worklist.
> **When this gate is fully done, `git mv` THIS block to `archive/` so the read path stays lean (A13).**
> **Status 2026-09-11:** steps 1 and 3 are DONE (2026-07-21/22 — both SPEC audits ran in fresh context, every finding triaged; their raised items are now mitigated or fixed). Step 2 (documentation hygiene) is the remainder; the build continued under explicit owner direction (VPS gate, data layer). Archive this block once step 2 is done.
