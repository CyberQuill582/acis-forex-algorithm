# ACIS-07 — Risk Monitor & Guardrails — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-RISK-007` |
| **Version** | 1.0 (DRAFT) |
| **Layer / DIR** | Layer 7 · `[DIR:core/risk]` · **the only upward channel** |
| **Consumes** | `FillReport` (ACIS-06) + all stores (regime, governor, portfolio) |
| **Emits** | `RiskSnapshot`; **HALT / flatten → Capital Governor ONLY** (single upward edge) |
| **Depends On** | `../ACIS_SPEC.md` §8, §2, §9 (`guardrail_limits.yaml`) · `ACIS-06`, `ACIS-00` |
| **Blocks** | — (bottom of the data chain; the upward HALT edge closes the loop) |
| **Corrections applied** | C5/F13 (alpha-decay baseline validity + NaN-safe Sharpe), F9 (drawdown buffer — raised), equity breaker, racing HALTs, restart reconciliation |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Guardrail config & limits · 7. Core logic · 8. State machine · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Watch everything, size nothing, and be the one component allowed to say *stop*. The Risk Monitor consumes `FillReport`s and portfolio truth, computes continuous risk metrics, and issues HALT/flatten to the Capital Governor — the **single upward edge** in the entire system (master §2/§8). Its limits live in `guardrail_limits.yaml` and are human-only.

**IS:** maintain `PortfolioState`/PnL/drawdown from FillReports; compute `RiskSnapshot` (VaR, cluster %, rolling Sharpe/win-rate, alpha-decay, slippage slope); enforce every HALT condition + the equity circuit breaker; detect alpha decay and instruct the Governor to throttle to 25%; own restart reconciliation.

**IS NOT:** it does not size, signal, classify, or execute; it never *raises* a guardrail (human-only); it has no downward data edge except the sanctioned HALT-to-Governor call; it cannot resume itself. There is **no force flag** anywhere in this layer (CLAUDE.md).

**Done-when:** every HALT condition + the equity breaker has an isolated, provable test; alpha-decay fires only on a valid baseline (C5) and never on NaN; racing HALTs resolve deterministically; restart reconciles against the broker; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/risk/monitor.py::RiskMonitor.ingest(fill: FillReport) -> None` (updates state) and `RiskMonitor.evaluate() -> RiskSnapshot` (periodic), which may call `guardrails.py` → `governor.apply_halt(...)` / `governor.flatten(...)`.

**Inputs:** `FillReport` stream (ACIS-06); read access to regime/governor stores for context; `guardrail_limits.yaml` (read-only, the human-owned limits); config `risk:`. **Boot:** the equity floor and all HALT limits must load from `guardrail_limits.yaml`; a missing limit is fatal (master §9 — no default for a risk limit).

## 3. Architecture & responsibility

Units: `monitor.py` (metrics + snapshot + ingest), `guardrails.py` (limit checks + HALT/flatten issuance + equity breaker), `alpha_decay.py` (rolling-Sharpe decay detector). Single responsibility: **risk observation + the stop authority.** The upward edge is realised as a call from `guardrails.py` into the Governor's `apply_halt`/`flatten` interface — Risk does **not** import the Governor's internals; it holds a narrow injected halt-sink. This preserves the "single upward edge to the Governor ONLY" law (master §2).

## 4. Output contract — `RiskSnapshot` (locked)

```python
@dataclass(frozen=True)
class RiskSnapshot:
    timestamp: datetime
    daily_pnl: Decimal
    daily_drawdown_pct: float
    open_drawdown_pct: float
    total_drawdown_pct: float          # daily + open
    portfolio_var_1pct: float          # 1% VaR as % NAV
    max_correlated_cluster_pct: float
    rolling_sharpe_50t: float
    rolling_win_rate_50t: float
    alpha_decay_flag: bool
    alpha_decay_state: str             # inactive_warming | active | flagged  (C5)
    slippage_slope_alert: bool
    equity: Decimal
    equity_floor_breached: bool
    instruments_halted: tuple[str, ...]
    session_id: str
```

`alpha_decay_state` (C5) makes "not enough data" a first-class, visible state distinct from "no decay" — surfaced on `acis://risk/snapshot`. `daily_pnl`/`equity` are Decimal (accounting boundary, F17).

## 5. Data schemas

- **`Trade`** (closed round-trip, reconstructed from FillReports): entry/exit price+time, direction, units, realised PnL (Decimal), instrument, `param_set_id`.
- **Rolling windows:** last-50-trade window (Sharpe, win-rate); baseline window `trades[-200:-50]`.
- **Config split:** *guardrail_limits.yaml (human-only):* `daily_drawdown_limit_pct:2.0`, `instrument_drawdown_limit_pct:1.0`, `alpha_decay_sharpe_threshold:0.5`, `max_portfolio_var_pct:3.0`, `correlation_cluster_cap_pct:20.0`, `slippage_alert_threshold_bps:8.0`, **`equity_floor`** (absolute). *system_config risk: (operational):* `alpha_decay_recent_window:50`, `alpha_decay_min_trades:30`, `alpha_decay_baseline_min_trades:50` (C5), `alpha_decay_recovery_trades:20`, `alpha_decay_recovery_mult:0.8`, `var_method`, `eval_cadence_s`.

## 6. Guardrail config & limits (human-only — never weakened by code)

Limits come from `guardrail_limits.yaml`, version-controlled, human-edited only (master §9, CLAUDE.md). The §12 control plane may **read** them (`acis://config/guardrails`) but never write them. No MCP tool, config flag, or test hook may lower a limit or add a bypass — there is no force flag. Changing a limit requires a human commit to the YAML + restart.

**HALT limits (master §8):** daily drawdown 2.0% → halt all new positions for session · per-instrument drawdown 1.0% → halt that instrument · alpha-decay Sharpe threshold 0.5× baseline → throttle to 25% · portfolio 1% VaR cap 3.0% NAV · cluster cap 20% · slippage alert 8.0 bps. **Equity circuit breaker (binding, master §8):** `equity < equity_floor` → **flatten-and-halt immediately; human required to restart.**

## 7. Core logic (step by step)

1. **Ingest** each `FillReport`: update positions, realised/unrealised PnL (Decimal), per-currency delta, per-cluster exposure, equity. Rebuild closed `Trade`s as round-trips complete.
2. **Evaluate** (every `eval_cadence_s`, and on each fill for the fast breakers):
   - **Equity breaker (highest):** `equity < equity_floor` → `governor.flatten("equity_floor")` then global HALT; requires human `acis_resume`. This is checked first and cannot be throttled away.
   - **Daily drawdown ≥ 2.0%** → `governor.apply_halt(all, "daily_drawdown")` for the session (auto-clears next session boundary).
   - **Per-instrument drawdown ≥ 1.0%** → `apply_halt(instrument, ...)`.
   - **VaR > 3.0% NAV** / **cluster > 20%** → HALT/throttle per policy.
   - **Slippage slope alert** (from Execution) → `slippage_slope_alert=True` (alert; auto-throttle only if human-enabled, F10).
   - **Alpha decay (C5):** see below.
3. **Emit** `RiskSnapshot` to `risk_store`; log every trigger.

**Alpha-decay detection (C5/F13 — the corrected version):**
```
recent   = trades[-alpha_decay_recent_window:]           # 50
baseline = trades[-200 : -alpha_decay_recent_window]      # up to 150 trades
if len(recent) < alpha_decay_min_trades (30):            state = inactive_warming; flag=False
elif count(baseline) < alpha_decay_baseline_min_trades (50): state = inactive_warming; flag=False   # (C5)
else:
    s_recent   = sharpe_nan_safe(recent)
    s_baseline = sharpe_nan_safe(baseline)               # NaN-safe: σ≈0 → defined sentinel, never div-by-0
    flag = s_recent < alpha_decay_sharpe_threshold (0.5) * s_baseline
    state = "flagged" if flag else "active"
```
On `flag`: set `alpha_decay_flag`, instruct `governor` to cut all allocations to 25% (throttle, not full halt), log `ALPHA_DECAY_DETECTED{s_recent, s_baseline, n}`. **Restore** only after a confirmed recovery: `alpha_decay_recovery_trades (20)` trades with rolling Sharpe > `alpha_decay_recovery_mult (0.8)` × baseline. The `inactive_warming` state is surfaced so "insufficient history" is never read as "healthy" (C5).

**Racing HALTs (glitch class):** HALT/flatten issuance is idempotent and serialized — two conditions firing "simultaneously" resolve to a single halt state; the most severe scope wins (global flatten > session halt > instrument halt); re-issuing a HALT already in effect is a no-op logged once. A resume clears exactly the scope it names and nothing more.

**Restart reconciliation (glitch class):** on startup with (possibly) open positions, the Risk Monitor treats the **broker as authoritative**: it queries broker positions/orders, reconciles against the last persisted `PortfolioState`, logs any drift (`RESTART_RECONCILE{drift}`), and — if drift or an in-flight HALT is detected — starts in a **halted** state requiring human review before trading resumes. It never assumes the persisted state is correct over the broker.

## 8. State machine

Global: `NORMAL → THROTTLED(alpha_decay) → HALTED(session|instrument|global) → FLATTENED(equity_floor)`. Session-drawdown halt auto-clears at the next session boundary; instrument halt clears when its condition clears *or* by human resume per policy; **equity-floor flatten and explicit global HALT clear only by human `acis_resume`** (master §12 asymmetry: any agent may halt; only a human resumes). Alpha-decay throttle clears only on confirmed recovery. Evaluated on the medium/fast cadence with the equity breaker on the fast path.

## 9. Persistence & logging

`risk_log` + `alpha_decay_log` (JSONL, master §11): every guardrail trigger, HALT, flatten, throttle, recovery, equity-breaker fire, reconcile, and every `RiskSnapshot` (or a sampled cadence with all triggers unsampled). Events: `HALT{scope,reason}`, `FLATTEN{reason}`, `EQUITY_FLOOR_BREACH`, `ALPHA_DECAY_DETECTED`, `ALPHA_DECAY_RECOVERED`, `VAR_BREACH`, `CLUSTER_BREACH`, `SLIPPAGE_ALERT`, `RESTART_RECONCILE`, `HALT_RACE_COALESCED`. HALTs are the audit spine — every one is traceable to the metric that caused it.

## 10. Store schema (DDL)

```sql
CREATE TABLE risk_snapshot (
    ts TIMESTAMPTZ NOT NULL,
    daily_pnl NUMERIC NOT NULL, daily_dd_pct DOUBLE PRECISION NOT NULL,
    open_dd_pct DOUBLE PRECISION NOT NULL, total_dd_pct DOUBLE PRECISION NOT NULL,
    var_1pct DOUBLE PRECISION NOT NULL, max_cluster_pct DOUBLE PRECISION NOT NULL,
    sharpe_50t DOUBLE PRECISION NOT NULL, win_rate_50t DOUBLE PRECISION NOT NULL,
    alpha_decay_flag BOOLEAN NOT NULL, alpha_decay_state TEXT NOT NULL,
    slippage_alert BOOLEAN NOT NULL, equity NUMERIC NOT NULL,
    equity_floor_breached BOOLEAN NOT NULL, instruments_halted JSONB NOT NULL,
    session_id TEXT NOT NULL, PRIMARY KEY (ts)
);
CREATE TABLE halt_event (
    halt_id TEXT PRIMARY KEY, ts TIMESTAMPTZ NOT NULL, scope TEXT NOT NULL,
    reason TEXT NOT NULL, cleared_at TIMESTAMPTZ, cleared_by TEXT   -- 'human:<token>' only
);
```
`halt_event.cleared_by` records that a resume was human — a machine can never populate it (enforced in ACIS-08).

## 11. MCP contract

Surfaces `acis://risk/snapshot` (latest `RiskSnapshot` incl. `alpha_decay_state`), `acis://config/guardrails` (read-only view). The control tools that *reach* this layer's authority are exposed by ACIS-08 and mapped to the Governor: `acis_halt`/`acis_flatten` are agent-callable (any agent may stop trading); `acis_resume`/`acis_set_mode(live)` require a **human token**. The Risk Monitor validates that a resume clearing an equity-floor/global HALT carries a human token; a non-human resume of such a HALT is rejected and logged. `daily-performance-brief` and `halt-postmortem` prompts (ACIS-08) read this layer's logs.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| `equity < equity_floor` | flatten + global HALT, human-only resume (highest priority, unthrottleable) |
| drawdown/VaR/cluster breach | scoped HALT/throttle per §6 |
| alpha-decay on insufficient data | `inactive_warming`, no flag (C5) |
| Sharpe with σ≈0 | NaN-safe sentinel, never div-by-0 |
| racing HALTs | coalesced, most-severe scope wins, idempotent |
| restart with open positions | reconcile vs broker (authoritative); start halted on drift |
| missing guardrail limit at boot | fatal — refuse to start |
| attempt to write a guardrail limit | impossible (read-only); attempt is a caught bug |

## 13. Logic-flaw registry
- **C-RSK-1 (C5/F13):** alpha-decay requires `alpha_decay_baseline_min_trades` in the baseline window; `inactive_warming` surfaced; test with 40 baseline trades → never flags; with 60 → can flag.
- **C-RSK-2 (NaN-safe Sharpe):** σ≈0 baseline → defined sentinel, no divide-by-zero, no spurious flag; injected test.
- **C-RSK-3 (equity breaker):** `equity < floor` → flatten+HALT, human-only resume; isolated test; unthrottleable (cannot be masked by alpha-decay throttle).
- **C-RSK-4 (racing HALTs):** two simultaneous conditions → single coalesced halt, most-severe scope; deterministic test.
- **C-RSK-5 (restart reconciliation):** broker authoritative; drift → start halted; test with persisted≠broker positions.
- **C-RSK-6 (F9 — drawdown buffer raised):** the drawdown pre-limit buffer/taper is **not** implemented here; it is logged as OPEN — human decision. A test asserts current behaviour halts *at* the limit (documenting the status quo), and `KNOWN_GAPS.md` tracks the pending decision.
- **C-RSK-7 (human-only resume):** a machine token cannot clear an equity/global HALT; `halt_event.cleared_by` always `human:*` for those; test asserts rejection of a non-human resume.

## 14. Test contract (postcondition-style)

**Unit:** every HALT condition fires at exactly its limit and issues the correct scope (assert the Governor received the halt + a `halt_event` row, not a return code); equity breaker fires below floor and flattens; alpha-decay fires only with a valid baseline and throttles to 25% (assert Governor allocations ×0.25), recovers only after 20 trades > 0.8× baseline; NaN-safe Sharpe; `alpha_decay_state` transitions; slippage alert sets the flag.

**Integration (with ACIS-05/06/08):** drawdown breach ⇒ zero new orders post-breach for the session (jointly with ACIS-05); equity floor breach ⇒ all positions flattened (jointly with ACIS-06) and resume rejected without a human token (jointly with ACIS-08); two HALTs racing ⇒ one coalesced halt; restart with open positions ⇒ reconcile vs broker, start halted on drift; weekend-gap through a stop ⇒ realised loss booked at gap price, drawdown updated correctly (jointly with ACIS-06).

## 15. Integration gate

**The upward edge:** Risk → Governor HALT/flatten is the only upward call in the system; it must be the sole path by which trading stops, and it must be irreversible without a human for equity/global scope. **Owns conflict-table rows:** "daily drawdown limit hit → halt new positions for session"; and conflict-priority #1 (Risk HALT beats everything). **Done-when (phase 8, master §15):** every regime/veto/override/HALT and the equity breaker has an isolated test (CLAUDE.md testing bar); all glitch-class tests present; import contract passing; the upward edge proven to be the *only* one (a test asserts no other module can stop trading and no non-human path resumes an equity/global HALT).

## Changelog
- **1.0 (DRAFT)** — From master §8 + `ACIS_Agent_Prompt.md` §3.7 + S3 equity breaker + S2 layer-7 card; C5/F13 corrected alpha-decay baseline validity + NaN-safe Sharpe; F9 drawdown buffer explicitly raised-not-applied; racing-HALT and restart-reconciliation glitch classes specified.
