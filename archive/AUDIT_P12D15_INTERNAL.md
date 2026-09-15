# GAP-P12D-15 replay caches — Lens 1 (internal consistency) adversarial audit

Auditor: Fable 5.1 (fresh context), 2026-09-15. Brief: `AUDIT_BRIEF_P12D15.md` (Lens 1 + "both lenses" items), scope = the uncommitted diff to `core/signals/indicators.py` (`AtrMemo`), `core/signals/agon.py`, `core/governor/capital_governor.py`, `core/optimizer/param_library.py` (`get_active` cache), `core/signals/provenance.py` (`entry_allowed` cache), new `tests/unit/test_replay_caches.py`. No repo file changed except this report. Environment: Python 3.11.9, SQLite 3.45.1, Windows 11, 2 cores.

**Result: 5 findings — 0 critical, 0 high, 1 medium, 4 low.** The core claim ("behaviour identical with and without the caches") survived every attack I could construct, including one the author's suite does not run (lifecycle events mid-run through the composed loop). The findings are about the *precondition* the caches rest on (unenforced, and owned by nothing a runtime builder will read), a transaction-awareness hole, an exception blast-radius change, and legibility/invariant-density debt.

Full suite: `python -m pytest -q -p no:cacheprovider` → **650 passed in 216.75 s** (log: session scratchpad `audit_full_suite.log`). `python scripts/ledger_check.py --summary` → exit 0. `tests/unit/test_module_budget.py` green.

**Data note:** `data/dukascopy` does not exist on this checkout (no `data/` directory at all), so `bench_replay.py` could not be re-run. Instead I compared the author's recorded fingerprints (see Honest negatives §4).

Reproduction scripts live in the session scratchpad `C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\6bb2e917-1bed-43cf-8358-14c555c361ab\scratchpad\` (`repro_second_writer.py`, `repro_writer_paths.py`, `repro_corrupt_rung.py`, `repro_atr_memo_fuzz.py`, `repro_loop_lifecycle.py`; `head_param_library.py` / `head_provenance.py` are `git show HEAD:` extracts used for differential runs). The load-bearing snippets are inlined below so the report stands alone.

---

## Findings

### F-I1 — The single-writer precondition is unenforced, and the entry that "owns" it does not know it (medium / likelihood medium at runtime-build time, low in the current tree)

**What changed.** Before the change, `ParamLibrary.get_active` and `ProvenanceStore.entry_allowed` hit SQLite on every call, so any writer — same connection or not — was visible on the next call. After the change both are cached and invalidated only by `self._db.total_changes`, i.e. only by writes made **through that same instance**. The fast loop's `ParamLibrary` instance never writes unless it also owns the boundary sweep; `AGON`'s `ProvenanceStore` instance never writes at all. So if any promotion/demotion/re-validation ever reaches the file through a *second* instance (same process or another), the fast loop trades on stale params and a "frozen" strategy keeps emitting entries **for the life of the process** — silently, because nothing moves the counter. ACIS-11 §7 "Instantly (same call): AGON's `entry_allowed()` returns False from this moment" is then false in exactly the risk-reducing direction it was written for.

**Failing input** (`repro_second_writer.py`; HEAD modules vs the change, two instances on one file):

```
[HEAD  ] B promoted ps-B; A.get_active -> ps-B   A.has_active -> True   A.active_snapshot -> ['ps-B']
[CHANGE] B promoted ps-B; A.get_active -> None   A.has_active -> False  A.active_snapshot -> ['ps-B']
[CHANGE] after A's own unrelated write: A.get_active -> ps-B

[HEAD  ] B demoted (instant freeze, ACIS-11 §7); A.entry_allowed -> False  A.snapshot entries_frozen -> True  A.rung_of -> PAPER
[CHANGE] B demoted (instant freeze, ACIS-11 §7); A.entry_allowed -> True   A.snapshot entries_frozen -> True  A.rung_of -> PAPER
[CHANGE] still after 3 more calls: A.entry_allowed -> True
```

Note the second block: **one instance's own read surfaces now disagree with each other** — `snapshot()` (what `acis://strategies/provenance` serves) says frozen, `entry_allowed()` (what AGON obeys) says allowed. `has_active` feeds NVMA's `has_params_for`, so a second-connection promotion also leaves the regime vetoed as `NO_PARAMS_FOR_REGIME` while `acis://params/active` shows the set as live.

**Why this is a finding and not just the declared precondition.** The author declares it (method docstring + ledger). But:
1. *Nothing enforces it.* A second `ParamLibrary`/`ProvenanceStore` on the same path in the same process is a plain constructor call; nothing refuses it, no test asserts against it. The precondition holds in the current tree only by inspection (see Honest negatives §8).
2. *The runtime that must honour it has not been built, and the ledger entry that "owns" it does not mention it.* The P12D-15 Residual says "GAP-0091b — the production runtime must open each SQLite store once per process", but GAP-0091b's own text (KNOWN_GAPS.md L415–422) is about VaR marks; a builder starting from GAP-0091b or the TODO runtime item never sees the obligation. `ledger_check.py` L2 only checks the ID resolves.
3. *The master spec is ambiguous in the dangerous direction.* §10: "Three independent asyncio loops **sharing read access to stores**" and "Loop 1 SLOW: QIEA evolution … stages, never promotes mid-session". Read literally, each loop may hold its own connection; if Loop 1 (or whoever runs `on_boundary`) promotes through its own `ParamLibrary`, Loop 3's cached `get_active` never updates. ACIS-11 §11 does pin provenance verdicts "in-process", but "in-process" ≠ "same instance".

**Minimal fix.**
- (a) Machine-enforce the in-process half now: a module-level registry of open resolved paths in both constructors that raises `DataQualityError` on a second live instance until `close()`; regression test `test_second_live_store_on_the_same_file_is_refused`. Cross-process stays a deployment rule (deploy/README + systemd single unit).
- (b) Write the obligation into GAP-0091b's entry (Area/Justification) and the TODO runtime item, or open a dedicated runtime-owned GAP; state in master §10 (or the runtime deep spec) that all three loops share **one instance** of each store.
- (c) Optionally, on the read path: since `active_snapshot()`/`snapshot()` stay uncached, the MCP surfaces are the only place this failure is visible — record that as the detection path in the operational ledger design.

### F-I2 — The caches are not transaction-aware: a read inside a same-connection transaction that later rolls back caches the rolled-back value (low / low)

`total_changes` is monotone and never decremented by ROLLBACK (verified: after a rolled-back INSERT, `total_changes` 1 → 2, rows still 1). The cache token therefore moves *on the write*, and a read between the write and the rollback caches uncommitted state that the rollback then erases — while the token stays at the post-write value, so nothing ever re-reads.

**Failing input** (`repro_writer_paths.py`):

```python
with s._db:
    s._db.execute("UPDATE rung_state SET entries_frozen=1 WHERE strategy_id='s2'")
    inside = s.entry_allowed("s2", T0)      # caches False (uncommitted)
    raise RuntimeError("boom")              # rollback
after = s.entry_allowed("s2", T0)
```
Output: `read-inside-rolled-back-txn: inside=False after_rollback=False db=True  -> STALE (cache holds the rolled-back value)`

The same construction applies to `get_active` (token is taken before `_read_active`). **No declared method reads its own cache inside its own transaction today** (checked every `with self._db:` block in both modules), and the ACIS-03 promotion sweep only reads `param_pending`, so this is not reachable through the public API — it is an invariant hole that the next method to read-then-write-then-fail would open silently (e.g. a future `apply_revalidation` consulting `entry_allowed` while its UPDATE is pending).

**Minimal fix.** Bypass the cache while `self._db.in_transaction` (measured 187 ns/attr; it reads False after both commit and rollback): `if self._db.in_transaction: return self._read_active(regime)` and the equivalent uncached row read in `entry_allowed`; regression test that reproduces the block above and asserts `after == db`.

### F-I3 — `entry_allowed` now fails for *every* strategy when *any* rung row is corrupt, with a raw `ValueError` (low / low)

The reload parses the whole table: `{sid: Rung(r) in _ACTIVE_RUNGS and not f for sid, r, f in rows}`. One bad `rung` value (hand edit, foreign writer, partial migration) raises `ValueError` out of the comprehension — for every strategy, including the healthy ones — and, because `_gate_token` is only set after the dict is built, on every subsequent call too. Before the change the blast radius was the corrupt strategy alone.

**Failing input** (`repro_corrupt_rung.py`; `UPDATE rung_state SET rung='BOGUS' WHERE strategy_id='bad_v1'` through the store's own connection):

```
[HEAD  ] entry_allowed('good_v1') -> True
[HEAD  ] entry_allowed('bad_v1')  raised ValueError: 'BOGUS' is not a valid Rung
[CHANGE] entry_allowed('good_v1') raised ValueError: 'BOGUS' is not a valid Rung
[CHANGE] entry_allowed('bad_v1')  raised ValueError: 'BOGUS' is not a valid Rung
```

The raw `ValueError` (not `DataQualityError`) is pre-existing (ACIS-11 §12 taxonomy has no row for it), so the new part is the blast radius. Reachable only via a write outside the store's declared methods — which is the F-I1 failure class again.

**Minimal fix.** Wrap the reload: `except ValueError as exc: raise DataQualityError("rung", ..., "corrupt rung value in rung_state") from exc` (taxonomy, and a HALT-worthy signal rather than a stack trace); or parse rungs lazily per strategy so a bad row only poisons its own gate. Regression test with a corrupt row.

### F-I4 — Legibility ratchet satisfied by reformatting, and a wrong single-writer comment (low / high — it is in the tree now)

`core/signals/provenance.py` is grandfathered at **391** lines and is at exactly 391 after the change, which *adds* logic (the gate cache). The room was made by compressing two unrelated lines — `self._cadence, self._log = revalidation_cadence_days, logger` and a reflowed `is_registered` — i.e. `test_grandfathered_modules_only_shrink` passed by squeezing, not by shrinking. That is the letter of the ratchet, not its purpose (GAP-P12M-01: extract or justify). `agon.py` (506/506) and `capital_governor.py` (464/464) are net-zero by substitution, which is fine.

The inline comment in `entry_allowed` reads `# GAP-P12D-15: cached until THIS connection writes (single writer — ParamLibrary.get_active)` — it names the *other* module's method as this store's single writer (copy-paste from `param_library.py`). For the one invariant this change introduces, the one comment that states it is wrong.

**Minimal fix.** Correct the comment (the single writer is "this `ProvenanceStore` instance's declared methods"); move the gate reload into a small helper (or a 15-line `_GateCache`) so provenance.py actually shrinks; note the ratchet event in GAP-P12M-01.

### F-I5 — Invariant density: the new invariant is not in either module's one-screen mental model (low / high)

GAP-P12M-02 asks every invariant-bearing module to open with its invariants. The `AtrMemo` docstring is exemplary (states the identity invariant and why a wrong key is harmless). But the store caches' invariant — *"reads are served from memory and invalidated only by `total_changes`, therefore: one live instance per file, all writes through it, single-threaded (asyncio + sqlite3 `check_same_thread`)"* — appears only in `get_active`'s docstring and the (wrong, F-I4) inline comment; neither `param_library.py`'s nor `provenance.py`'s header docstring mentions a cache at all. A reader of the header model would still believe every read hits SQLite.

**Minimal fix.** One sentence in each header docstring naming the cache, the invalidation token, and the single-instance precondition (pointing at GAP-P12D-15 / the F-I1 owner).

---

## Honest negatives — what I attacked and how it survived

1. **`AtrMemo` ≡ `wilder_atr(bars, period)` (brief Lens 1 §2).** `repro_atr_memo_fuzz.py`: three seeds × ~16,000 equality checks (48,192 total, NaN-aware) over deque windows with `maxlen` eviction, restart-style window shrink, GAP-0065 out-of-order daily drops (window unchanged → hit), value-equal-but-distinct `Bar` objects (must recompute, same value), cross-window middle swaps with identical ends and length, `deque` vs fresh `list` arguments, shared keys (pair legs reuse the instrument key), and empty→one→empty windows. Zero mismatches. Structural argument holds: `Bar` is `frozen=True`, no `object.__setattr__`/`dataclasses.replace` on bars anywhere in `core/`, `atr_series` is a pure function of `high/low/close`, the memo compares full positional identity and holds the tuple so ids cannot be recycled.
2. **Every declared write path moves `total_changes` and the cache is right immediately after (§3).** `repro_writer_paths.py` walks 18 provenance transitions (register, attempt, promote, demote, stalled and flat `on_boundary`, PASS-unfreeze at DECAYED, DECAYED→PAPER, FAIL→demote, retire, flag_revival, revive, FAIL at INCUBATION, challenger, reading-list) and 7 param-library paths (fresh, stage, superseding stage, promote, stalled boundary, flat boundary, off-boundary refusal, rolled-back sweep) — all `OK` against a direct SQL truth read. Zero-row writes (`apply_revalidation('ghost','PASS')`) leave counter and DB unchanged. Rolled-back writes *outside* a read are conservative (counter moved → re-read → correct). Output: `ALL OK`.
3. **Composed-loop equivalence WITH lifecycle events mid-run** (the author's loop test has none). `repro_loop_lifecycle.py`: same 520 flat ticks through a cached loop and an every-cache-defeated loop; at tick 300 `promote_one_rung`+`demote(tsmom_slow_v1)`, at 360 `apply_revalidation PASS`, at 420 `flatten` + stage + `promote` of `ps-SUCCESSOR` at a real boundary. Result: `orders cached=196 plain=196 identical=True`, take-rate and skip counters identical, `entry_frozen: 52` skips, **0 orders sized in the freeze window**, 62 orders after promotion all on `ps-SUCCESSOR`. The events bit, and both loops agreed.
4. **Author's real-tick fingerprints.** With no data present I compared the recorded JSONs: `base_5k_a` vs `new2_5k` and `base_pair_40k` vs `new2_pair_40k` — orders (all fields incl. `factors_snapshot`, `stop_loss`, `take_profit`, `size_units`), take-rate, skip counters and event counts identical (2,624 and 20,391 orders); `base_5k_a` vs `base_5k_b` identical (the baseline is deterministic, so identity is meaningful). Whether that fingerprint can detect stale-cache behaviour without a mid-run lifecycle event is Lens 2 §4's question; my §3 above covers the gap for Lens 1.
5. **Half-filled caches after an exception.** Provenance builds the whole dict before assigning `_gates` and sets `_gate_token` last → a raising reload leaves the *old* dict and the *old* token (retry, never stale). ParamLibrary resets `_active = {}` before `_read_active` → a raising read leaves no entry; the next call re-reads. No stale state either way (F-I3 is about blast radius, not staleness).
6. **Callers mutating returned objects.** `get_active` now returns the same object each call; `ActiveParamSet`/`ParamSet` are `frozen=True` (`FrozenInstanceError` on setattr, verified), `gene_values()` returns a fresh dict, `regime` is an enum, `promoted_at` a datetime. `entry_allowed` returns a bool.
7. **Thread interleaving / racing writes.** Master §10 and the ACIS-08 §15 scope note define a single-process *asyncio* runtime; `sqlite3.connect` is used with default `check_same_thread=True`, so a second thread is refused with `ProgrammingError`, not raced. No lock is needed for the in-memory dicts under that model.
8. **Single-writer in the CURRENT tree (§4).** Constructors of `ParamLibrary`/`ProvenanceStore`: `tests/integration/paper_loop.py:210,219` (one each per loop), `tests/signals_fixtures.py:73`, `tests/unit/test_param_library.py:43`, `tests/unit/test_provenance.py:26,178`, `tests/integration/test_qiea_promotion_cycle.py:48,73`, `tests/integration/test_agon_pipeline.py:49`, `tests/unit/test_agon.py:235`. Every reopen on the same file closes the first (`test_provenance.py:177`, `test_qiea_promotion_cycle.py:72`); `test_replay_caches.py` uses distinct `cached/` and `plain/` dirs. `monitoring/` constructs neither store (only its own `McpAuditStore`); no script opens `params.db`/`provenance.db`; MCP snapshot sources (`active_snapshot`, `pending_snapshot`, `snapshot`) are uncached; ACIS-11 §11: "No MCP tool mutates provenance; verdicts arrive via the phase-11 harness in-process"; nothing in `tests/backtest/` calls `apply_revalidation`/`demote`. The precondition holds today — by inspection only (F-I1).
9. **Spec drift (§5).** ACIS-11 §7 "instantly, same call" holds on the writing instance (author's test + §2 above). ACIS-03 C-QIEA-5 byte-stability across `stage()` holds (stage invalidates → equal value re-read; only identity changes). Master §10 "Loop 3 cannot mutate params" is unaffected. ACIS-04's `entry_allowed` gate semantics unchanged. The diff touches no file under `core/risk/`, `config/guardrail_limits.yaml`, or any HALT/veto/resume path; the import-direction contract test is in the green full run.
10. **Restart.** New instance → `_active_token`/`_gate_token` are `None` → first call reads (author's `test_get_active_reads_fresh_after_a_restart`, and `test_restart_resumes_rungs_freezes_and_counters` asserts `entry_allowed` False after reopen).
11. **Warm-up / NaN edges.** `wilder_atr` returns NaN for `len(bars) <= period`; the memo caches and returns NaN identically (fuzz + author's warm-up test). The Governor's `len(bars) <= self._atr.period + 1` pin is the same comparison as before.
12. **Both-lenses items.** Module budget green (three grandfathered modules exactly at cap — see F-I4; `param_library.py` 276 < 300; `indicators.py` 115). `ledger_check.py` green. The P12D-15 Residual is *honest* about what remains (GAP-0075, multi-core, the audit) — its weakness is ownership, not honesty (F-I1(b)).

## Environment-integrity note (read before trusting the "650 passed")

While this audit ran, another session edited the working tree outside my scope: `git status` at the end shows 7 modified files under `tests/backtest/` (`harness.py`, `metrics.py`, `report.py`, `walk_forward.py`, three test files; +102/−56) and 4 new ones (`deflated_sharpe.py`, `rollover_marks.py`, `test_deflated_sharpe.py`, `test_oos_honesty.py`), all with mtimes 2026-09-15 03:25–03:28 — none of them mine, none present at session start. **The five scoped files are unchanged since I read them** (diff stats still 8/18/18/26/22 lines; mtimes 2026-09-14 07:45), so every finding and honest negative above stands. But the full-suite run (650 passed) was in flight during those edits and may have swept in in-progress work; the author should re-run `python -m pytest -q -p no:cacheprovider` on the committed P12D-15 change alone before citing a green count. I changed no repo file except this report.

## Notes (not findings)

- `entry_allowed(strategy_id, now)` ignores `now` — before and after; unchanged.
- AGON's `AtrMemo` pins `cfg.atr_period` at construction where `wilder_atr(bars, self._cfg.atr_period)` used to read it live. `_cfg` is assigned only in `__init__` across `core/` (grep), and the Governor already pinned its period, so this is a change only if a future config-apply mutates `agon._cfg` in place — nothing does.
- Invalidation granularity is coarse (any write to either file, including `record_attempt`/`record_source_disposition`, reloads the whole gate dict / clears all regimes). Correct and cheap; noted so nobody "optimises" it into per-table tokens without re-running §2.
- `total_changes` is a 32-bit counter in CPython 3.11's binding; a wrap-to-equal collision needs exactly 2^32 changes between two reads — Lens 2's counter-width item, not reachable.
