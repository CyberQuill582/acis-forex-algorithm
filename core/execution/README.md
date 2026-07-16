# `[DIR:core/execution]` — Layer 6 · Execution Orchestrator

**Blueprint only — no implementation yet.**

- **Deep spec:** `../../specs/ACIS-06-EXECUTION_ORCHESTRATOR.md` · **Master:** `../../ACIS_SPEC.md` §7
- **Consumes:** `SizedOrder` · **Emits:** `FillReport` (frozen) → Risk Monitor; order flow → broker/venue
- **Planned files:** `orchestrator.py` (submit + lifecycle), `fragmenter.py` (TWAP/VWAP + signature randomisation), `venue.py` (routing + quality score)
- **Must not:** change `size_units` (quantity is the Governor's final word); open anything sized to 0. Only upward output is `FillReport` → Risk.
- **Owns corrections:** C-EXE-1 (fragment exact-sum invariant), C-EXE-2 (jitter bounds), C-EXE-3 (slippage alert; auto-throttle OFF pending human/F10; dark-pool dropped), C-EXE-4 (partial/reject), C-EXE-5 (reconnect/restart reconcile vs broker), C-EXE-6 (no resize).
