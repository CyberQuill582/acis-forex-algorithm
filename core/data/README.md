# `[DIR:core/data]` — Layer 1 · Data Ingestion & Normalisation

**Blueprint only — no implementation yet.** Build here strictly per the spec; do not start until the phase-1 gate is planned.

- **Deep spec:** `../../specs/ACIS-01-DATA_INGESTION.md` · **Master:** `../../ACIS_SPEC.md` §3
- **Consumes:** raw broker/feed payloads (external) · **Emits:** `MarketState` (frozen) → NVMA
- **Planned files:** `ingestion.py` (feed→raw), `normaliser.py` (`MarketStateFactory`), `feeds.py` (OANDA v20 primary, MT5, IBKR, mock paper feed)
- **Must not import:** any layer below (regime/optimizer/signals/governor/execution/risk). Enforced by the import-linter contract in `tests/unit/`.
- **Owns corrections:** C-DATA-1 (deep-immutable `raw`), C-DATA-2 (Decimal boundary), C-DATA-3 (session tagging/C1), C-DATA-4 (session-median cache/F18), C-DATA-5 (dup/reorder/reconnect flags).
