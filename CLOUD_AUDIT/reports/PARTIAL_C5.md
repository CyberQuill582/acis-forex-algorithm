# PARTIAL — C5 MONEY-PATH SAFETY (run 2), checkpoint 1 (~18:08 UTC)

Lane C5, Opus 5.5 (model id claude-opus-5-5; effort not observable), fresh context, BASE 7695ed04, 2026-09-24.
Status: reading done for core/execution, core/risk, governor halt surface, monitoring tools/auth/mode, watchdog, systemd units.
Reproductions in progress under `evidence/C5/`. The final replaces this file.

Candidate findings (code-read, reproductions pending):
1. `core/execution/orchestrator.py:211-215` never passes `stop_loss` to `face.submit_order` — the master §279 server-side stop is never placed by the only production dispatch path (TODO Track A step 4 names this; blocker before the first demo order).
2. `orchestrator.py:216-224`: on ConnectionError the "reconcile" only LOGS broker positions, then resubmits; after two failures it books a synthetic REJECT (0 filled). An ack-lost fill becomes an orphan the Risk Monitor never sees; the heartbeat then reports 0 positions, so the watchdog would only alert, never flatten.
3. Governor halts (`capital_governor.py` `_halts`) are in-memory only; `RiskStore.record_halt`/`save_restrictive_state` have no production caller. A process restart (systemd `Restart=always`) silently clears MCP/platform/VaR/cluster halts — a restart is a relaxation [owner decision: HALT semantics].
4. The execution freeze is checked once per order (`orchestrator.py:90`), not per fragment: a HALT/flatten arriving while a fragmented/scheduled order sleeps between fragments does not stop the remaining open fragments.
5. `monitor.py:366-373` adopts unknown broker positions at avg_price 1.0 → fake P&L (USD_JPY: ~±$990 per 1,000 units).
6. Watchdog flatten has no fence to the engine: a hung (not dead) engine that recovers keeps its stale position view; on a netting venue its next "close" opens a reverse position.
7. `mode` (paper/live) is consumed by no trading code — the live gate is a label, not bound to which account the face trades.
8. A 16-min-slow host clock makes the normaliser raise on every live tick (`normaliser.py:194-198`) — fails safe but the engine cannot trade; nothing checks host-vs-broker time at start.
