# ACIS-07 — Risk Monitor & Guardrails — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-RISK-007` |
| **Version** | 1.3 (**LOCKED** 2026-10-02 — G-5: VaR as a taper input, owner-ratified, master v2.27) · 1.2 (**LOCKED** 2026-09-25 — halt ledger act-first + restore, persisted drawdown anchors, daily-reset platform rules, session-latch re-arm; v1.1 2026-07-17 phase-9 start) |
| **Layer / DIR** | Layer 7 · `[DIR:core/risk]` · **the only upward channel** |
| **Consumes** | `FillReport` (ACIS-06) + broker account state (§7.5 execution face) + all stores (regime, governor, portfolio) + Tier-G flatten conditions (ACIS-10) |
| **Emits** | `RiskSnapshot`; **HALT / flatten / taper / alpha-decay → Capital Governor ONLY** (single upward edge, risk-restrictive-only per GAP-0014); the §8.6 engine heartbeat |
| **Depends On** | `../ACIS_SPEC.md` §8, §8.5–8.6, §9, §9.5, §2 · `ACIS-06`, `ACIS-10`, `ACIS-12`, `ACIS-00` |
| **Blocks** | — (bottom of the data chain; the upward HALT edge closes the loop) |
| **Corrections applied** | C5/F13 (alpha-decay baseline validity + NaN-safe Sharpe), equity breaker, racing HALTs, restart reconciliation · v1.1: §9.5 platform-measured drawdown series + stricter-of (C11/GAP-0014), the RATIFIED pre-limit taper computed here (GAP-0010 — F9's raise is resolved), GAP-0050 explicit set/clear on the upward edge, Tier-G flatten execution (GAP-0011), §8.6 heartbeat writer (v2.10/ACIS-12), shipped guardrail key names |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Guardrail config & limits · 7. Core logic · 8. State machine · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Watch everything, size nothing, and be the one component allowed to say *stop*. The Risk Monitor consumes `FillReport`s and portfolio truth, computes continuous risk metrics, and issues HALT/flatten to the Capital Governor — the **single upward edge** in the entire system (master §2/§8). Its limits live in `guardrail_limits.yaml` and are human-only.

**IS:** maintain `PortfolioState`/PnL/drawdown from FillReports; track **platform-measured drawdown per rule under the platform's own semantics** (§9.5 — static/trailing, intraday/EOD, balance/equity, from the §7.5 execution face's account state, never approximated by the internal measure); compute `RiskSnapshot` (VaR, cluster %, rolling Sharpe/win-rate, alpha-decay, slippage slope, distance-to-limit + taper per limit); compute the **ratified §9.5 pre-limit taper** and deliver it over the upward edge; enforce every HALT condition + the equity circuit breaker + the **Tier-G flatten** (GAP-0011, condition computed by ACIS-10); detect alpha decay and instruct the Governor to throttle to 25% with **explicit set/clear only** (GAP-0050); write the **§8.6 heartbeat** the watchdog consumes (ACIS-12 contract); own restart reconciliation.

**IS NOT:** it does not size, signal, classify, or execute; it never *raises* a guardrail (human-only); it has no downward data edge except the sanctioned HALT-to-Governor call; it cannot resume itself. There is **no force flag** anywhere in this layer (CLAUDE.md).

**Done-when:** every HALT condition + the equity breaker has an isolated, provable test; alpha-decay fires only on a valid baseline (C5) and never on NaN; racing HALTs resolve deterministically; restart reconciles against the broker; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/risk/monitor.py::RiskMonitor.ingest(fill: FillReport) -> None` (updates state) and `RiskMonitor.evaluate() -> RiskSnapshot` (periodic), which may call `guardrails.py` → `governor.apply_halt(...)` / `governor.flatten(...)`.

**Inputs:** `FillReport` stream (ACIS-06); broker account state via the §7.5 execution face (`account_snapshot`/`open_positions` — the ONLY layer that reads it); the composed `EffectiveDoctrine` (ACIS-10 §7: engine limits ∪ platform `drawdown_rules`, each under its own semantics); Tier-G `flatten_condition` (ACIS-10); read access to regime/governor stores for context; `guardrail_limits.yaml` (read-only, the human-owned limits); config `risk:` (required block, schema-fatal if missing). **Boot:** the equity floor and all HALT limits must load from `guardrail_limits.yaml`; a missing limit is fatal (master §9 — no default for a risk limit); **boot calls `governor.rebuild_groups(portfolio)` before the first tick (GAP-0052, proven at phase 7).**

## 3. Architecture & responsibility

Units: `monitor.py` (metrics + snapshot + ingest + heartbeat writer), `guardrails.py` (limit checks + platform-drawdown series + taper computation + HALT/flatten issuance + equity breaker + Tier-G flatten), `alpha_decay.py` (rolling-Sharpe decay detector), `scenario_replay.py` (ACIS-12, gap-law release gate). Single responsibility: **risk observation + the stop authority.** The upward edge is realised as calls from `guardrails.py` into the Governor's existing phase-6 surface — `apply_halt(scope, reason)` / `apply_risk_state(taper_factor=…, alpha_decay=…)` (GAP-0050: `None` = unchanged, every relaxation explicit + audited) / the flatten path — Risk does **not** import the Governor's internals; it holds a narrow injected halt-sink. **The edge is risk-restrictive only (GAP-0014): halt, cut, taper, flatten — the schema of the sink cannot express a size increase.**

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
    rolling_mean_sigma_50t: float      # per-trade mean/σ — NOT an annualised Sharpe (GAP-P9E-05)
    rolling_win_rate_50t: float
    alpha_decay_flag: bool
    alpha_decay_state: str             # inactive_warming | active | flagged  (C5)
    slippage_slope_alert: bool
    equity: Decimal
    equity_floor_breached: bool
    instruments_halted: tuple[str, ...]
    platform_drawdown: tuple[PlatformDrawdownState, ...]   # §9.5 first-class series
    taper_factor: float                # min across limits; 1.0 = far from every wall
    session_id: str
```
```python
@dataclass(frozen=True)
class PlatformDrawdownState:           # one per rule in the stricter-of set (§9.5)
    rule_key: str                      # e.g. "prop_demo:trailing:intraday:equity"
    measured_pct: float                # under the PLATFORM's semantics
    limit_pct: float
    distance_fraction: float           # measured/limit ∈ [0, ∞)
    taper_factor: float                # this rule's §9.5 taper ∈ [0, 1]
```

`alpha_decay_state` (C5) makes "not enough data" a first-class, visible state distinct from "no decay" — surfaced on `acis://risk/snapshot`. `daily_pnl`/`equity` are Decimal (accounting boundary, F17). Trailing rules anchor to **intraday high-water equity** exactly as the platform measures it (the §13 trailing-anchor glitch test: an EOD approximation must fail).

## 5. Data schemas

- **`Trade`** (closed round-trip, reconstructed from FillReports): entry/exit price+time, direction, units, realised PnL (Decimal), instrument, `param_set_id`.
- **Rolling windows:** last-50-trade window (Sharpe, win-rate); baseline window `trades[-200:-50]`.
- **Config split (shipped key names):** *guardrail_limits.yaml (human-only, as committed):* `daily_drawdown_pct:2.0`, `per_instrument_drawdown_pct:1.0`, `alpha_decay_sharpe_mult:0.5`, `var_cap_pct:3.0`, `cluster_cap_pct:20.0`, `single_currency_delta_cap_pct:30.0`, `slippage_alert_bps:8.0`, **`equity_floor_usd`** (absolute), **`taper_start_fraction:0.60` / `entry_halt_fraction:0.80`** (the RATIFIED floor — schema rejects looser). *system_config `risk:` (operational, required):* `alpha_decay_recent_window:50`, `alpha_decay_min_trades:30`, `alpha_decay_baseline_min_trades:50` (C5), `alpha_decay_recovery_trades:20`, `alpha_decay_recovery_mult:0.8`, `var_method`, `var_window`, `var_horizon_seconds` (GAP-0103: the DECLARED VaR holding-period, σ scaled √(horizon/eval_cadence) to it), `slippage_window`, `eval_cadence_s`, `heartbeat_path`, `heartbeat_interval_s (≤10, §12)`.
- **§9.5 taper (ratified — computed HERE, consumed by the Governor):** per hard drawdown limit in the stricter-of set, with `d = measured/limit`: `taper(d) = 1.0` for `d ≤ taper_start_fraction`; linear down to `0.0` at `entry_halt_fraction`; `0.0` beyond. The delivered factor = **min across all limits** (engine daily + per-instrument + every platform rule, each measured under its own semantics). Delivered via `apply_risk_state(taper_factor=…)`; the limit itself keeps full HALT semantics at 1.0. Per-account stricter overrides come composed from ACIS-10 §7 (`min(engine, account)` — already schema-floored).
- **VaR as a taper input (v1.3, G-5, owner-ratified 2026-10-02, master v2.27):** `taper(var_pct / var_cap_pct)` joins the min across limits, with the same `taper_start_fraction` / `entry_halt_fraction`, so new entries shrink from 60% of the VaR cap and stop at 80%; `TAPER_UPDATED` names `var_cap` when it binds. The VaR HALT at 100% (a human-only global halt) is unchanged. Proof: `test_g5_var_tapers_entries_from_sixty_to_eighty_percent_of_its_cap_and_halts_only_at_it`.

## 6. Guardrail config & limits (human-only — never weakened by code)

Limits come from `guardrail_limits.yaml`, version-controlled, human-edited only (master §9, CLAUDE.md). The §12 control plane may **read** them (`acis://config/guardrails`) but never write them. No MCP tool, config flag, or test hook may lower a limit or add a bypass — there is no force flag. Changing a limit requires a human commit to the YAML + restart.

**HALT limits (master §8):** daily drawdown 2.0% → halt all new positions for session · per-instrument drawdown 1.0% → halt that instrument · alpha-decay Sharpe threshold 0.5× baseline → throttle to 25% · portfolio 1% VaR cap 3.0% NAV · cluster cap 20% · slippage alert 8.0 bps. **Equity circuit breaker (binding, master §8):** `equity < equity_floor` → **flatten-and-halt immediately; human required to restart.**

## 7. Core logic (step by step)

1. **Ingest** each `FillReport`: update positions, realised/unrealised PnL (Decimal), per-currency delta, per-cluster exposure, equity. Rebuild closed `Trade`s as round-trips complete.
2. **Evaluate** (every `eval_cadence_s`, and on each fill for the fast breakers):
   - **Equity breaker (highest):** `equity < equity_floor_usd` → `governor.flatten("equity_floor")` then global HALT; requires human `acis_resume`. This is checked first and cannot be throttled away.
   - **Platform drawdown (§9.5, stricter-of):** each platform rule measured under ITS semantics from broker account state; a platform limit at 1.0 → scoped HALT exactly like an engine limit (the account's rule IS a guardrail).
   - **Daily drawdown ≥ 2.0%** → `governor.apply_halt(all, "daily_drawdown")` for the session (auto-clears next session boundary).
   - **Per-instrument drawdown ≥ 1.0%** → `apply_halt(instrument, ...)`.
   - **§9.5 taper:** compute per-limit tapers (see §5), deliver `min` via `apply_risk_state(taper_factor=…)` — every change logged with the binding limit named (`TAPER_UPDATED{rule_key, factor}`).
   - **Tier-G flatten (GAP-0011):** ACIS-10 `flatten_condition(instrument, ts)` non-None → flatten that instrument's positions + `apply_halt(instrument, "tierg_flatten")`; resume human-only; log `TIERG_FLATTEN{class, sources}`.
   - **VaR > 3.0% NAV** / **cluster > 20%** → HALT/throttle per policy.
   - **Slippage slope alert** (from Execution) → `slippage_slope_alert=True` (alert; GAP-0004 accepted-risk: alert-only interim, no auto-throttle exists).
   - **Alpha decay (C5):** see below.
3. **Emit** `RiskSnapshot` to `risk_store`; write the **§8.6 heartbeat** (ACIS-12 contract: atomic temp+rename, `{ts_utc, session_id, mode, open_positions, fast_loop_seq}`, cadence ≤ `heartbeat_interval_s`); log every trigger.

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
On `flag`: set `alpha_decay_flag`, instruct the Governor via `apply_risk_state(alpha_decay=True)` (throttle to 25%, not full halt), log `ALPHA_DECAY_DETECTED{s_recent, s_baseline, n}`. **Restore (the GAP-0050 contract — when Risk may legitimately clear the throttle):** ONLY after a confirmed recovery — `alpha_decay_recovery_trades (20)` trades with rolling Sharpe > `alpha_decay_recovery_mult (0.8)` × baseline — Risk sends the **explicit** `apply_risk_state(alpha_decay=False)`; the Governor logs `ALPHA_DECAY_CLEARED` (already shipped, phase 6). No other call may clear it: taper-only updates pass `alpha_decay=None` (unchanged), and `inactive_warming` after a restart does NOT clear an active throttle — a restart restores the persisted throttle state first (see restart reconciliation). The `inactive_warming` state is surfaced so "insufficient history" is never read as "healthy" (C5).

**Racing HALTs (glitch class):** HALT/flatten issuance is idempotent and serialized — two conditions firing "simultaneously" resolve to a single halt state; the most severe scope wins (global flatten > session halt > instrument halt); re-issuing a HALT already in effect is a no-op logged once. A resume clears exactly the scope it names and nothing more.

**Restart reconciliation (glitch class):** on startup with (possibly) open positions, the Risk Monitor treats the **broker as authoritative**: it queries broker positions/orders, reconciles against the last persisted `PortfolioState`, logs any drift (`RESTART_RECONCILE{drift}`), and — if drift or an in-flight HALT is detected — starts in a **halted** state requiring human review before trading resumes. It never assumes the persisted state is correct over the broker. **Persisted risk-restrictive state (active halts, an armed alpha-decay throttle, the last taper) is RESTORED before the first evaluate — a restart is never a relaxation (GAP-0050).** Boot then calls `governor.rebuild_groups(portfolio)` (GAP-0052).

## 8. State machine

Global: `NORMAL → THROTTLED(alpha_decay) → HALTED(session|instrument|global) → FLATTENED(equity_floor)`. Session-drawdown halt auto-clears at the next session boundary, **and its latch re-arms there: a breach after that boundary halts again** (v1.2, GAP-P12D-80 — the code had latched for the process's life); instrument halt clears when its condition clears *or* by human resume per policy; **equity-floor flatten and explicit global HALT clear only by human `acis_resume`** (master §12 asymmetry: any agent may halt; only a human resumes). Alpha-decay throttle clears only on confirmed recovery. Evaluated on the medium/fast cadence with the equity breaker on the fast path.

## 9. Persistence & logging

`risk_log` + `alpha_decay_log` (JSONL, master §11): every guardrail trigger, HALT, flatten, throttle, recovery, equity-breaker fire, reconcile, and every `RiskSnapshot` (or a sampled cadence with all triggers unsampled). Events: `HALT{scope,reason}`, `FLATTEN{reason}`, `EQUITY_FLOOR_BREACH`, `ALPHA_DECAY_DETECTED`, `ALPHA_DECAY_RECOVERED`, `TAPER_UPDATED{rule_key,factor}`, `PLATFORM_DD_BREACH{rule_key}`, `TIERG_FLATTEN{class,sources}`, `VAR_BREACH`, `CLUSTER_BREACH`, `SLIPPAGE_ALERT`, `RESTART_RECONCILE`, `HALT_RACE_COALESCED`. HALTs are the audit spine — every one is traceable to the metric that caused it.

## 10. Store schema (DDL)

```sql
CREATE TABLE risk_snapshot (
    ts TIMESTAMPTZ NOT NULL,
    daily_pnl NUMERIC NOT NULL, daily_dd_pct DOUBLE PRECISION NOT NULL,
    open_dd_pct DOUBLE PRECISION NOT NULL, total_dd_pct DOUBLE PRECISION NOT NULL,
    var_1pct DOUBLE PRECISION NOT NULL, max_cluster_pct DOUBLE PRECISION NOT NULL,
    mean_sigma_50t DOUBLE PRECISION NOT NULL, win_rate_50t DOUBLE PRECISION NOT NULL,
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
`halt_event.cleared_by` records that a resume was human — a machine can never populate it (enforced in ACIS-08). **v1.2:** `cleared_by` is `human:<random resume id>` (no bit derived from the token) or `auto:session_boundary` (a session halt that lapsed at its own boundary); the opaque `halt_id` is `<kind>|ts|scope|reason|<random>`. The risk store opens in WAL with `synchronous=FULL`, so a power loss cannot drop a committed halt (audit X4, GAP-P12D-76).

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
- **C-RSK-1 (C5/F13):** alpha-decay requires `alpha_decay_baseline_min_trades` in the baseline window; `inactive_warming` surfaced; test with 40 baseline trades → never flags; with 60 → can flag. **(GAP-0093 correction, 2026-07-18):** the master-§8 formula `s_recent < mult·s_baseline` is only meaningful for a POSITIVE baseline — it inverts when `s_baseline ≤ 0` (an improving-but-still-negative recent would wrongly flag). Decay is erosion of a positive edge, so the flag additionally requires `s_baseline > 0`; a strategy with no positive edge cannot "decay". The compared quantity is a per-trade mean/σ (`mean_sigma`), NOT an annualised Sharpe (GAP-0105 naming law) — used only as a same-units ratio, so the missing annualisation/rf cancels.
- **C-RSK-2 (NaN-safe Sharpe):** σ≈0 baseline → defined sentinel, no divide-by-zero, no spurious flag; injected test.
- **C-RSK-3 (equity breaker):** `equity < floor` → flatten+HALT, human-only resume; isolated test; unthrottleable (cannot be masked by alpha-decay throttle).
- **C-RSK-4 (racing HALTs):** two simultaneous conditions → single coalesced halt, most-severe scope; deterministic test.
- **C-RSK-5 (restart reconciliation):** broker authoritative; drift → start halted; test with persisted≠broker positions.
- **C-RSK-6 (F9 RESOLVED by ratification — the §9.5 taper):** the pre-limit taper was owner-ratified 2026-07-15 (GAP-0010, subsuming GAP-0003/F9) and is implemented HERE: exact piecewise `taper(d)` per limit, min across limits, delivered over the upward edge; fractions from `guardrail_limits.yaml` under the schema-enforced ratified floor. Tests: `taper(0.60)=1.0`, `taper(0.70)=0.5`, `taper(0.80)=0.0` exactly; min-across-limits binds to the nearest wall; the limit still HALTs at 1.0 unchanged.
- **C-RSK-8 (§9.5 platform series):** platform drawdown measured under the platform's declared semantics from broker account state — the trailing/intraday/equity fixture must FAIL if approximated by EOD or balance; never merged numerically with engine measures.
- **C-RSK-9 (GAP-0050):** the upward edge carries explicit instructions only — `None` is "unchanged"; a taper update can never silently clear an alpha-decay throttle; clearing requires the recovery condition + the explicit False; test proves a taper-only call leaves the throttle armed.
- **C-RSK-10 (Tier-G flatten, GAP-0011):** flatten fires ONLY on eligible+`≥2`-source-confirmed+open-positions (condition computed by ACIS-10); anything less stays veto-only; resume human-only; test both branches.
- **C-RSK-11 (§8.6 heartbeat):** written atomically on the evaluate cadence; `open_positions` in the beat is from broker-truth reconciled state; a wedged evaluate loop stops the beat (that is the point — the watchdog sees silence).
- **C-RSK-7 (human-only resume):** a machine token cannot clear an equity/global HALT; `halt_event.cleared_by` always `human:*` for those; test asserts rejection of a non-human resume.

## 14. Test contract (postcondition-style)

**Unit:** every HALT condition fires at exactly its limit and issues the correct scope (assert the Governor received the halt + a `halt_event` row, not a return code); equity breaker fires below floor and flattens; alpha-decay fires only with a valid baseline and throttles to 25% (assert Governor allocations ×0.25), recovers only after 20 trades > 0.8× baseline, and the GAP-0050 None-vs-False semantics are proven (taper-only call leaves the throttle armed); taper hand-vectors (0.60→1.0, 0.70→0.5, 0.80→0.0) + min-across-limits + per-account stricter fractions; platform trailing-intraday-equity drawdown against a fixture equity path (EOD approximation provably fails); Tier-G flatten both branches (eligible+confirmed+open ⇒ flatten+halt; single-source ⇒ nothing); heartbeat atomic write + cadence + open-positions truth; NaN-safe Sharpe; `alpha_decay_state` transitions; slippage alert sets the flag.

**Integration (with ACIS-05/06/08):** drawdown breach ⇒ zero new orders post-breach for the session (jointly with ACIS-05); equity floor breach ⇒ all positions flattened (jointly with ACIS-06) and resume rejected without a human token (jointly with ACIS-08); two HALTs racing ⇒ one coalesced halt; restart with open positions ⇒ reconcile vs broker, start halted on drift; weekend-gap through a stop ⇒ realised loss booked at gap price, drawdown updated correctly (jointly with ACIS-06).

## 15. Integration gate

**The upward edge:** Risk → Governor HALT/flatten/taper/decay is the only upward call in the system; it must be the sole path by which trading stops, and it must be irreversible without a human for equity/global scope. **Owns conflict-table rows:** "daily drawdown limit hit → halt new positions for session"; and conflict-priority #1 (Risk HALT beats everything). **Done-when (phase 9, master §15):** every regime/veto/override/HALT and the equity breaker has an isolated test (CLAUDE.md testing bar); all phase-9 glitch-class tests present (racing HALTs, restart reconciliation, trailing-anchor, weekend-gap-through-stop with ACIS-06, Tier-G-during-blackout stricter-outcome); the ACIS-12 scenario-replay gate green against the shipped book; the watchdog tests green end-to-end with this layer's heartbeat writer; import contract passing; the upward edge proven to be the *only* one (a test asserts no other module can stop trading and no non-human path resumes an equity/global HALT).

## Changelog
- **1.3 (LOCKED, 2026-10-02)** — G-5 (owner-ratified, master v2.27): VaR joins the §9.5 taper; entries stop at 80% of the VaR cap, the HALT stays at 100%. Only shrinks sizes.
- **1.2 (LOCKED, 2026-09-25)** — merged 2026-09-25 from the BUILDER-3 branch on the owner's explicit go, after the constitution's two audits (GAP-P12D-77..81, every finding fixed and lead-verified); amendment text applied under the owner's delegation; tightening only, no guardrail VALUE changed:
  - **Act first, then persist (GAP-P12D-79):** every halt, session halt and flatten crossing the upward edge is APPLIED FIRST and then persisted in `halt_event`; a failed write is retried and alarmed (`HALT_LEDGER_WRITE_FAILED`) and never undoes or delays the halt; a latch is set only after the action succeeded.
  - **Restore at boot (GAP-P12D-75/78, fulfilling this spec's existing "active halts … RESTORED before the first evaluate"):** a store-backed monitor REFUSES to evaluate until restored; every open row is re-applied through the same edge with the same scope and reason; a session halt is restored with its original instant and lapses at its own boundary, a row whose boundary already passed is closed `auto:session_boundary` and never re-applied; only a human resume clears any other row.
  - **Drawdown anchors survive a restart (GAP-P12D-55):** the static inception anchor, the trailing high-water mark and the daily day-open anchor (with its day) join the persisted restrictive state; a rollover missed while down is bracketed by the observations either side.
  - **Platform `daily` rules (GAP-P12D-54/59):** a rule may reset at a declared local instant (`reset: {zone, at}`, e.g. `Europe/Prague` 00:00 for FTMO) with its anchor's basis captured there (`balance | equity | max`), and a limit expressed as a percentage of the account's declared `initial_capital` (finite, > 0, fatal if malformed); a declared `initial_capital` anchors static rules and seeds trailing ones. Reproduces FTMO's published worked examples.
  - **Session latch re-arms at the boundary (GAP-P12D-80).**
- **1.1 (LOCKED, 2026-07-17 — phase-9 start consistency update, master v2.5→v2.11)** — §9.5 account doctrine folded in (C11/GAP-0014): platform-measured drawdown as a first-class `PlatformDrawdownState` series under each rule's own semantics, sourced from the §7.5 execution face, HALTing like engine limits at 1.0; the RATIFIED pre-limit taper (GAP-0010 — F9's raise resolved by the owner 2026-07-15) computed here with exact piecewise hand-vectors and min-across-limits, delivered over the upward edge; the edge declared risk-restrictive-only with GAP-0050 explicit set/clear semantics (None = unchanged; recovery-gated explicit False is the only legitimate clear; restart restores a persisted throttle); Tier-G flatten execution (GAP-0011, condition from ACIS-10, resume human-only); §8.6 heartbeat writer per the ACIS-12 contract; `scenario_replay.py` registered in this layer's units (ACIS-12 owns its spec); GAP-0052 boot `rebuild_groups` made a boot-contract line; config keys aligned to the shipped `guardrail_limits.yaml` names incl. the schema-floored taper fractions; `risk:` block required/schema-fatal; done-when renumbered to phase 9 with the ACIS-12 gates included. New registry entries C-RSK-8..11; C-RSK-6 rewritten from "raised" to "ratified + implemented". No guardrail value, HALT, veto, or resume semantics changed — this pass only *adds* the ratified and constitutional machinery around them.
- **1.0 (DRAFT)** — From master §8 + `ACIS_Agent_Prompt.md` §3.7 + S3 equity breaker + S2 layer-7 card; C5/F13 corrected alpha-decay baseline validity + NaN-safe Sharpe; F9 drawdown buffer explicitly raised-not-applied; racing-HALT and restart-reconciliation glitch classes specified.
