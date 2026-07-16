# `[DIR:core/optimizer]` — Layer 3 · QIEA Optimizer & Parameter Library

**Implemented (phase 4, 2026-07-15).** Deep spec: `../../specs/ACIS-03-QIEA_OPTIMIZER.md` v1.1 (LOCKED) · Master: `../../ACIS_SPEC.md` §5.

- **Consumes:** `RegimeType` + regime-labelled **historical** bars only · **Emits:** `ActiveParamSet` (frozen) → AGON via `param_library`
- **Files:** `param_types.py` (frozen §4/§5 dataclasses, `GENE_SPECS` single range source), `costs.py` (**the C8 shared cost model — ACIS-09 must import this module, never re-implement it**), `fitness.py` (mini-backtest + C9 expectancy gate + holdout), `qiea.py` (stdlib Han–Kim QEA, seed-reproducible), `param_library.py` (SQLite active/pending stores, staging/promotion, stall observability)
- **Non-overridable rule:** never modify live params; never promote mid-session; promote only at a `session_boundaries_utc` instant with `open_positions == 0`. `promote()` off-gate **raises `PromotionForbiddenError`**.
- **Must not:** read live portfolio state (Loop 1 isolation) — only `PositionGate.open_position_count()`.
- **Owns corrections:** C-QIEA-1 (session-boundary def/C1 + the GAP-0025 ruling), C-QIEA-2 (staleness observable/C2), C-QIEA-3 (position-close not a trigger/F3), C-QIEA-4 (isolation), C-QIEA-5 (mid-session immutability), C-QIEA-6 (C8 net-of-costs), C-QIEA-7 (C9 exact expectancy, GAP-0006), C-QIEA-8 (chronological holdout, GAP-0008).
