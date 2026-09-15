# Pinned dual-audit brief — GAP-P12D-15 replay caches (A4)

Pinned 2026-09-14. **Status: ON HOLD** — the Fable 5.1 launch failed on quota the same day (owner: "put that on hold", quota back in ~17 h). Relaunch both lenses in fresh context, in parallel, on Fable 5.1 (recommended) or Opus 4.8 (the floor), never Sonnet or Haiku. Auditors change no repo file except their report, cite existing IDs only (findings labelled F-I1… / F-E1…), and write to `scratchpad/audit_p12d15_internal.md` and `scratchpad/audit_p12d15_external.md`. The author triages every finding into `KNOWN_GAPS.md`; then `git mv` this brief to `archive/`.

**Scope:** the uncommitted GAP-P12D-15 change (read that entry first): `AtrMemo` in core/signals/indicators.py and its use in core/signals/agon.py and core/governor/capital_governor.py; the `total_changes`-keyed caches in core/optimizer/param_library.py `get_active` and core/signals/provenance.py `entry_allowed`; tests/unit/test_replay_caches.py.

## Lens 1 — internal consistency
1. Behaviour identical with and without the caches for every reachable input, not just the tested ones.
2. `AtrMemo` can never differ from `wilder_atr(bars, period)`.
3. A promotion, freeze, demotion, revalidation, retirement or revival is visible on the very next `get_active` / `has_active` / `entry_allowed` call (ACIS-11 §7 "instantly"). Hunt write paths that do not move `total_changes`, reads that now raise differently, half-filled caches after an exception, and callers mutating returned objects.
4. Single-writer precondition: find every constructor of or writer to these stores, and any spec design (master §12 MCP plane, ACIS-03 §7, ACIS-11 §3/§7, ACIS-08) where another connection or process writes them.
5. Drift from ACIS_SPEC.md and the locked ACIS-03/04/05/11; guardrail, HALT and veto semantics untouched.

## Lens 2 — external referent
1. SQLite and CPython semantics of `sqlite3.Connection.total_changes`: upserts, `with conn:` transactions, rollbacks, triggers, failed statements, the truncate optimisation, REPLACE, DDL, `executescript`, other connections, counter width; check `sqlite3.sqlite_version`.
2. The measured cost of `PRAGMA data_version`, `os.stat` and a keyed SELECT on the Windows laptop (~157–205 µs per call), and whether a cheap EXACT cross-connection alternative was missed (open read transaction, update hook, WAL, `locking_mode=EXCLUSIVE`).
3. Frozen-dataclass guarantees for `Bar` and identity comparison as an exact memo key (id reuse is closed because the memo holds the bars).
4. Benchmark methodology: does the real-tick fingerprint (orders minus ids, take-rate, skip counters, event counts) detect stale-cache behaviour when no demotion or re-promotion happens mid-run? The bench script is recorded in the GAP-P12D-15 entry.
5. Cache bug classes in trading engines (stale state after lifecycle changes, restart, multi-process deployment: deploy/, master §12, Phronesis out-of-band).

## Both lenses also cover
Module legibility (GAP-P12M-01, `tests/unit/test_module_budget.py`), invariant density (GAP-P12M-02), and ledger closure (`python scripts/ledger_check.py` green; is the GAP-P12D-15 Residual honest?).
