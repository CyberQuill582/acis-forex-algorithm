# `[DIR:core/regime]` — Layer 2 · NVMA Regime Engine (sovereign gatekeeper)

**Blueprint only — no implementation yet.**

- **Deep spec:** `../../specs/ACIS-02-NVMA_REGIME.md` · **Master:** `../../ACIS_SPEC.md` §4
- **Consumes:** `MarketState` (+ session-median cache) · **Emits:** `RegimeContext` (frozen) → QIEA & Alpha Arena via `regime_store`
- **Planned files:** `nvma.py` (classifier + veto), `regime_types.py` (`RegimeType` enum + `RegimeContext`), `stability.py` (stability score + half-life)
- **Must not import:** any layer below; never triggers execution (Loop 2 isolation).
- **Owns corrections:** C-REG-1 (cadence 60–300s/F1), C-REG-2 (session-median cold-start/F18), C-REG-3 (half-life advisory/C3), C-REG-4 (NaN veto), C-REG-5 (determinism), C-REG-6 (shift + no params → veto).
- **Conflict-table rows owned:** "NVMA no-trade + high-conviction → discard"; "regime shift + no evolved params → tradeable=False".
