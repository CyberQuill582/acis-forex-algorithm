# ACIS-12 — Scenario Book, Gap-Law Replay & the Watchdog — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-SWAN-012` |
| **Version** | 1.0 (LOCKED, authored 2026-07-17 at phase-9 start) |
| **Layer / DIR** | `[DIR:core/risk]` (replay engine) + `[DIR:tests/backtest]` (release-gate runner) + `[DIR:scripts]` (watchdog process) + `[DIR:config]` (`scenario_book.yaml`, `watchdog` block) |
| **Consumes** | `scenario_book.yaml`, `guardrail_limits.yaml` (read-only), `instruments.yaml`, engine heartbeat |
| **Emits** | per-scenario replay **verdicts** (release gate), `WATCHDOG_FLATTEN`/`WATCHDOG_ALERT` events |
| **Depends On** | `../ACIS_SPEC.md` §8.5, §8.6 (v2.10), §9, §13 · ACIS-07 (consumes its flatten semantics) |
| **Corrections applied** | v2.10 owner ratification (watchdog: flatten-only, outside the blast radius, no kernel module); gap law made computable (worst-legal-book construction + per-scenario ceilings) |

## 1. Executive purpose & scope
Two independent survival mechanisms that live OUTSIDE the trading decision path:
(a) **Gap-law replay** — prove, before any build ships, that the guardrail limits and sizing rules bound the loss of every catalogued shock even when stops fill where liquidity reappears, not at their levels; (b) **the watchdog** — a separate minimal OS process that flattens via the broker when the engine's heartbeat goes silent with open positions, so the breaker cannot die with the loop.

**IS:** deterministic replay of `scenario_book.yaml` against the worst book the Governor could legally build; per-scenario max-loss verdicts as a standing release gate in `tests/backtest`; the heartbeat file contract (engine-side writer, ACIS-07) and the watchdog consumer (flatten-only, own interpreter, zero `core/` imports).
**IS NOT (hard walls):** no prediction, no scenario probability weighting, no sizing decisions (replay only *verifies* limits; it changes nothing); the watchdog never sizes, never resumes, never writes config, never reads strategy state — it can only ever flatten/halt (§8.6 guard-integrity); no kernel/HFT machinery (lean-build: the failure mode is a hung Python process).

## 2. Boot/entry contract & inputs
`core/risk/scenario_replay.py::ScenarioReplay(book, guardrails, instruments, logger)`. `scenario_book.yaml` is schema-validated at load (§9 discipline: bad/missing book = fatal): each scenario carries `name`, `kind ∈ {gap_through_stop, flash_crash, broker_outage, liquidity_vacuum}`, `description`, `params`, and (new, required) **`max_loss_pct_nav`** — the human-committed ceiling that scenario may ever cost. The book grows by human commit only; `halt-postmortem` (§12) proposes additions.

Watchdog: `scripts/acis_watchdog.py` + `config/watchdog.yaml` (`heartbeat_path`, `watchdog_timeout_s`, `poll_interval_s`, `platform`, `flatten_plugin`, credentials ref). The engine never writes `watchdog.yaml`; `acis_stage_config` rejects its path at the schema level exactly like a guardrail path (phase 10).

## 3. Architecture & responsibility
Replay = pure functions over config + synthetic paths (no feed, no stores, no RNG). Runner = `tests/backtest/test_scenario_replay.py`, part of every full suite run (cheap, synthetic) — a failed invariant FAILS THE BUILD; replay re-runs by construction whenever the book or the guardrails change (it reads both live). Watchdog = standalone script, **zero imports from `core/`** (enforced by an AST contract test), reading the heartbeat file and calling one flatten plugin; per-platform plugins are adapter-tier (§16 exception), mock plugin in v1, real ones land with ACIS-13 at phase 12.

## 4. Output contract
```python
@dataclass(frozen=True) class ReplayVerdict:
    scenario: str; kind: str; instrument: str | None
    worst_book_notional: Decimal      # the legally-buildable worst case
    loss_pct_nav: float               # gap-law loss, adverse fills
    ceiling_pct_nav: float            # scenario's max_loss_pct_nav
    equity_after: Decimal             # NAV − loss
    floor_survives: bool              # equity_after > equity_floor_usd
    passed: bool                      # loss ≤ ceiling AND floor_survives
```
Heartbeat (engine-side, ACIS-07 writes it): one JSON object, atomic write (temp+rename), `{ts_utc, session_id, mode, open_positions, fast_loop_seq}` every fast-loop health cycle (≤10 s cadence, §12). Watchdog events (own JSONL, §11 envelope): `WATCHDOG_STARTED`, `WATCHDOG_STALE{age_s}`, `WATCHDOG_FLATTEN{positions}`, `WATCHDOG_ALERT{reason}` (stale-but-flat: alert only), `WATCHDOG_FLATTEN_FAILED{error}` (retry with backoff — failure is loud, never silent).

## 5–7. Schemas, algorithms, core logic
- **Worst-legal-book construction (C-SWN-1, the gap law's honest input):** for the scenario's instrument, the largest exposure the Governor could ever legally hold positioned AGAINST the shock: `worst_notional = min(cluster_cap_pct, single_currency_delta_cap_pct) / 100 × NAV` (the binding §6 hard caps for a single instrument; NAV = the dev-account base, `equity_floor` context from `guardrail_limits.yaml`). No credit is taken for conviction/vol-norm/taper softening — those are formula factors a full-conviction book can max out.
- **Gap-through-stop (C-SWN-2):** stops are assumed to fill at the POST-GAP price: `loss = worst_notional × |gap_pct|/100` (+ declared vacuum spread cost when `spread_mult` present). Stop levels are irrelevant by law; guaranteed-stop assumptions are forbidden unless the platform contractually provides them (then modelled per-account, ACIS-13).
- **Flash crash (C-SWN-3):** fill at the bottom of the drop (`drop_pct`); the V-recovery earns nothing — the position is out. `loss = worst_notional × |drop_pct|/100`.
- **Broker outage (C-SWN-4):** price drifts unmanaged for `duration_s`; loss bound = broker-side stop distance at its worst legal geometry (max evolved SL multiplier from `GENE_SPECS['atr_multiplier_sl']` cap × the instrument's declared `vol_target_atr_frac` × price) **plus** the §8.5 gap allowance (stops can gap during the outage too: apply the book's worst same-instrument gap scenario on top). This prices the §8.6 layer-1 defence honestly instead of assuming it fills at level.
- **Liquidity vacuum (C-SWN-5):** forced exit cost = `spread_mult × max_plausible_spread × worst_notional / price`; asserts rollover-window exits stay inside the ceiling.
- **Invariants (the gate):** per scenario, `loss_pct_nav ≤ max_loss_pct_nav` AND `NAV − loss > equity_floor_usd`. Both must hold for every scenario; one failure fails the build. Verdicts are logged (JSONL) and returned; nothing is auto-adjusted — a failing invariant is a HUMAN problem (resize the caps or re-ratify the ceiling; both are guardrail-adjacent and human-only).
- **Watchdog loop (C-SWN-6):** every `poll_interval_s`: read heartbeat; `age = now − ts_utc`. If `age > watchdog_timeout_s` and last-good `open_positions > 0` → call the flatten plugin ONCE (idempotent flag file; retries with backoff only on plugin failure), record `WATCHDOG_FLATTEN`. Stale-but-flat → `WATCHDOG_ALERT` only. A malformed/missing heartbeat is treated as SILENCE (unknown never degrades to "alive"). The plugin surface is exactly `flatten_all(credentials) -> FlattenResult` — no other broker capability is linked into the process.

## 8. State & cadence
Replay: stateless, deterministic, runs in the suite. Watchdog: single-file state (last flatten marker); survives its own restart; its config is read once at start (re-arm = human restart — a watchdog an agent can reconfigure live is not a guard).

## 9–10. Persistence & logging
Replay verdicts → `risk_log` JSONL (`SCENARIO_REPLAY_VERDICT` per scenario, standard envelope) when invoked in-engine; the release gate asserts on returned verdicts (postconditions), not exit codes. Watchdog writes its own `logs/watchdog_log.jsonl` (same envelope; separate file — it must not share a handle with the process it watches). No DB tables (lean-build).

## 11. Interface/MCP
Replay verdicts surface via `acis://risk/snapshot` (latest run summary, phase 10). The watchdog has NO MCP surface — it is deliberately outside the control plane it backstops; its log file is readable via `acis://logs/tail/watchdog` (read-only) once phase 10 lands.

## 12. Error taxonomy
Missing/invalid scenario field or unknown `kind` → fatal at config load. Unknown instrument in a scenario → fatal (mirrors taxonomy rule, ACIS-10). Replay ceiling breach → failing verdict (build gate), never an exception swallowed. Watchdog: heartbeat unreadable/malformed = silence; flatten plugin error → bounded retries + `WATCHDOG_FLATTEN_FAILED`, keep trying on the next polls (positions may still be open) — never crash silently.

## 13. Logic-flaw registry
- **C-SWN-1** worst book is the LEGAL maximum, no softening credit — replay can never flatter sizing.
- **C-SWN-2** stops fill post-gap; guaranteed stops forbidden by default.
- **C-SWN-3** V-recovery earns nothing.
- **C-SWN-4** outage bound = stop geometry + gap allowance, never "fills at level".
- **C-SWN-5** vacuum exit priced at exploded spread.
- **C-SWN-6** watchdog: silence+positions ⇒ flatten once, idempotent; stale-but-flat ⇒ alert only; malformed heartbeat = silence; flatten-only surface; zero core imports (AST-tested).
- **C-SWN-7** invariants are verified, never auto-tuned — a breach is raised to the human.

## 14. Test contract (postcondition style)
Replay: every shipped scenario returns a verdict and ALL pass against the current guardrails (the release gate itself); a synthetic over-sized cap (test-local construction, never the real config) makes `chf_depeg_2015` fail its ceiling — the gate provably can fail; gap loss uses post-gap price (a stop 10 pips above the gap floor changes nothing); outage bound strictly greater than plain stop-distance loss (the gap allowance is real); vacuum cost scales with `spread_mult`; missing `max_loss_pct_nav` → config-fatal. Watchdog: fresh heartbeat ⇒ no action; stale+positions ⇒ exactly one flatten (idempotent across polls); stale+flat ⇒ alert only; malformed file ⇒ treated silent; plugin failure ⇒ retry + `WATCHDOG_FLATTEN_FAILED`; AST test proves zero `core/` imports; heartbeat writer emits atomically and monotonically (engine side, jointly with ACIS-07).

## 15. Integration gate
ACIS-07 (phase 9) owns the engine-side heartbeat writer and the flatten semantics the watchdog mirrors; ACIS-13 (phase 12) supplies real flatten plugins per platform, conformance-gated; the pre-phase-12 VPS gate deploys the watchdog beside the engine under process supervision. **Done-when (phase 9):** replay gate green in the full run against the shipped book + guardrails; watchdog tests green; heartbeat contract tested end-to-end with ACIS-07's writer.

## Changelog
- **1.0 (LOCKED, 2026-07-17)** — Authored at phase-9 start against master v2.11 (§8.5 gap law made computable: worst-legal-book construction C-SWN-1, per-scenario human-committed `max_loss_pct_nav` ceilings + equity-floor survival as the two invariants; §8.6 v2.10 watchdog: heartbeat file contract, flatten-only plugin surface, zero-core-imports law, silence semantics).
