# `[DIR:core/signals]` — Layer 4 · AGON Signal Engine + Strategy Provenance

**Implemented (phase 5, 2026-07-16).** Deep specs: `../../specs/ACIS-04-ALPHA_ARENA.md` v1.1 (LOCKED) + `../../specs/ACIS-11-STRATEGY_PROVENANCE.md` v1.0 (LOCKED) · Master: `../../ACIS_SPEC.md` §5.5–5.7.

- **Consumes:** `RegimeContext` + `ActiveParamSet` + `MarketState` · **Emits:** frozen `Signal`s (linked groups for pair legs) → Capital Governor
- **Files:** `signal_types.py` (Signal contract, conviction ∈ [0.45,1] emitted, `group_id` iff PAIR_DIVERGENCE), `indicators.py` (reuses phase-3/4 proven TA + Bollinger z / rolling correlation / pair-spread z), `agon.py` (six regime-gated modules + C4 pipeline + §2 conflict table + GAP-0007 budget), `provenance.py` (ACIS-11: falsifier-gated registration, rung ladder, GAP-0019 demotion, graveyard, attempt registry), `canonical.py` (the v1 module provenance/reading list in code)
- **The reflex law (v2.8):** no voting, no consensus, no negotiation in the signal path — conviction is per-module arithmetic; opposite directions discard both; pair groups emit whole or die whole.
- **Modules:** Trend (EMA cross + RSI, ADX conviction) · Breakout (channel + close-beyond filter) · Mean Reversion (Bollinger z, RSI-divergence gate) · Momentum Scalp (velocity surge, 1-minute bars per GAP-0009) · Pair Divergence (§5.5 declared relationships, atomic groups) · Slow TSMOM (v2.9 canonical, 63/126/252-day agreement)
- **Must not:** know capital/portfolio/execution; override the NVMA veto; emit when `tradeable=False`; run an unregistered or entry-frozen strategy.
- **Owns corrections:** C-ALP-1..10 (ACIS-04 §13), C-PRV-1..6 (ACIS-11 §13).
- **Conflict-table row owned:** "two strategies opposite directions, same instrument → discard both".
