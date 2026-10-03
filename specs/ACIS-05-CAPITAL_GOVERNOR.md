# ACIS-05 — Capital Governor — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-GOV-005` |
| **Version** | 1.8 (LOCKED — 2026-10-02, owner-ratified: the demo's sizing reference re-ruled to $10k at 20%, in a $100k demo account, on J1's evidence; GAP-P12D-101/142) · 1.7 (LOCKED — 2026-10-02, owner-ratified, master v2.27: §6.4 target positions (R1.6) and §7 step 4's entry headroom (G-5)) · 1.6 (LOCKED — 2026-09-30: §7 step 3b, the paper/practice minimum size, applying master §5 v2.22 on the owner's ruling, GAP-P12D-129) · 1.5 (LOCKED — 2026-09-25 prop-safety amendments: pre-close ban on every account, weekend/holiday flatten, the reduce-only close convention, one human-resume path; earlier: v1.3/v1.4 base-currency sizing and USD-balanced pair legs, GAP-P12D-22/26) |
| **Layer / DIR** | Layer 5 · `[DIR:core/governor]` · **sovereign allocation** |
| **Consumes** | `Signal` (ACIS-04) + `PortfolioState` + `RegimeContext` + risk-restrictive state (from Risk, ACIS-07, single upward edge) + blackout/account doctrine (§3.5/§9.5) |
| **Emits** | `SizedOrder` (frozen) → Execution (ACIS-06) |
| **Depends On** | `../ACIS_SPEC.md` §6, §2, §8, §9.5 · `ACIS-04`, `ACIS-10`, `ACIS-00` |
| **Blocks** | ACIS-06 |
| **Corrections applied** | C6/F14 (marginal-alpha contract), F15 (cold-start/bucketing), C3/F7 (half-life decision), C7 (clusters) · **v1.1:** GAP-0005 exact `g()` (closes it), C16 exact vol-norm fn (v2.9), §9.5 taper consumption + blackout override + `BLACKOUT_OVERRIDE_ENFORCED` (v2.7), §5.5 atomic pair groups + GAP-0040 group-exit path, GAP-0014 risk-restrictive-only upward edge |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Sizing formula & config · 7. Core logic · 8. State machine · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Decide *how much*. The Governor is the only layer that sees total portfolio state; it turns a `Signal` (or a linked pair group) into `SizedOrder`s (possibly of size 0) by multiplying independent risk factors and then clamping with non-negotiable hard limits. It is the sole recipient of the Risk Monitor's upward edge (HALT / alpha-decay cut / pre-limit taper — **risk-restrictive only, never a size increase**, GAP-0014).

**IS:** position sizing via the marginal-alpha-governed formula; C16 dampen-only vol normalisation; correlation-cluster caps; single-currency net-delta cap; §3.5/§9.5 blackout + account-rule hard overrides; §9.5 pre-limit taper consumption; atomic pair-group sizing + the open-group registry and group-exit path (GAP-0040); expiry-drop of stale signals; HALT/alpha-decay application.

**IS NOT:** it does not decide *how/where* to execute (ACIS-06); it does not generate signals or classify regimes. It never *raises* the guardrail limits — those are human-only (`guardrail_limits.yaml`, master §9). It can only ever reduce risk relative to the formula, never expand it past a hard cap.

**Done-when:** each sizing factor is isolatable and tested; every hard override zeroes size provably; `g()` and `vol_norm()` meet their contracts with defined cold-starts; the taper multiplies before the overrides and can never exceed 1.0; pair groups size both-or-neither and exit whole; expired signals never become orders; a HALT zeroes new sizing until human resume; §14 tests pass.

## 2. Entry contract

**Entry points:** `core/governor/capital_governor.py::CapitalGovernor.allocate(signal, portfolio, regime, now) -> SizedOrder` and `allocate_group(signals: tuple[Signal, Signal], portfolio, regime, now) -> tuple[SizedOrder, SizedOrder]` (§5.5); `check_group_exits(coupling_state, now) -> tuple[SizedOrder, ...]` (GAP-0040); the upward-edge interface `apply_risk_state(...)` and `apply_halt(scope, reason)` / `resume(human_token)`.

**Inputs:** a `Signal`; the `PortfolioState` (frozen, Decimal accounting — F17); the current `RegimeContext`; the risk-restrictive state; blackout truth via a provider callable (`blackout(instrument, now) -> bool`, from the phase-2 events layer + account doctrine); the active `AccountRulebook` (§9.5); config `governor:` + `guardrail_limits.yaml` (read-only). All clock reads are the explicit `now`.

**Precondition guards (checked before any formula):** signal not expired; `regime.tradeable`; no active HALT for the scope; daily drawdown within limit; `regime.confidence ≥ confidence_veto`; liquidity not ILLIQUID; not inside a restricted-account blackout. Any failing guard ⇒ `SizedOrder(size=0, reason=...)` — the formula is not even evaluated.

## 3. Architecture & responsibility

Units (lean): `portfolio_types.py` (frozen `PortfolioState`/`Position`, Decimal), `marginal_alpha.py` (estimator + the GAP-0005 `g()`), `factors.py` (liquidity, correlation, C16 vol-norm — three pure functions), `capital_governor.py` (guards + formula + hard limits + groups + halt state). Single responsibility: **sizing.** Downward-only imports; Risk *calls* the Governor's interfaces (no Risk import here).

## 4. Output contract — `SizedOrder` (locked)

```python
@dataclass(frozen=True)
class SizedOrder:
    order_id: str
    signal_id: str
    instrument: str
    direction: int             # +1 | -1
    size_units: Decimal        # base-currency units (F17 accounting boundary)
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str                # formula | expired | veto | halt | cluster_cap | ...
    factors_snapshot: Mapping  # every factor + guard that produced this size
    sized_at: datetime
    param_set_id: str
    group_id: str | None = None      # §5.5: pair-group legs carry their group
    action: Literal["open", "close"] = "open"   # v1.1: group EXIT orders are "close" (GAP-0040)
```

`size_units == 0` is a valid, common output (a decision, not an error). `factors_snapshot` records every factor value and every guard verdict so any allocation is reconstructable (master §11). *(v1.1: `group_id` + `action` added — required by the §5.5 group law and its GAP-0040 exit path; recorded as the master-schema extension of this layer.)*

## 5. Data schemas

- **`PortfolioState`** (frozen, read): `nav: Decimal`, `open_positions: tuple[Position, ...]`, `per_currency_delta: Mapping[str, Decimal]` (signed, USD notional — v1.4 correction, GAP-P12D-24), `per_cluster_exposure: Mapping[str, Decimal]`, `daily_drawdown_pct: float`, `as_of: datetime`, `stale: bool`. Written by portfolio accounting (phase 7+); the Governor reads it; `stale=True` ⇒ every allocation is size 0 (`PORTFOLIO_STALE`).
- **`Position`:** `instrument`, `direction`, `size_units: Decimal`, `entry_price`, `opened_at`, `group_id: str | None`, `strategy_type`.
- **Clusters (C7):** fixed lists from `instruments.yaml`; unknown symbol = config error at boot (already schema-gated, phase 0).
- **Config (`governor:`, all required):** `marginal_alpha_window: 50`, `marginal_alpha_min_trades: 20`, `marginal_alpha_min_bucket: 5`, `weekend_entry_buffer_s` (no new entries this close to the weekend close or to any declared ≥2 h market closure, on EVERY account, weekend holding allowed or not — v1.5, GAP-P12D-58; FTMO's "gap trading" rule binds Swing accounts too), `scalp_min_hold_conflict: true` (§9.5 min-hold vs MOMENTUM_SCALP horizon). **From `guardrail_limits.yaml` (read-only, human-commit):** `daily_drawdown_pct`, `cluster_cap_pct: 20`, `single_currency_delta_cap_pct: 30` *(v1.1: added to the guardrail file with the exact master-§6 ratified value; schema ceiling 30 — stricter allowed, looser rejected — mirroring the taper-floor pattern; flagged to the owner for veto)*. **From `instruments.yaml`:** per-instrument `vol_target_atr_frac` (the C16 declared target — required for enabled instruments, fatal if missing). **From `system_config`/regime:** `confidence_veto: 0.55`.

## 6. Sizing formula & config

```
raw_size = BASE_UNIT_USD
         × conviction_factor      # signal.conviction ∈ [0.45, 1]
         × liquidity_factor       # DEEP 1.0 · NORMAL 0.8 · THIN 0.4 · ILLIQUID 0 (also a guard)
         × correlation_factor     # clamp01(1 − max_cluster_fraction / cap_fraction)
         × regime_factor          # regime_stability × regime_confidence ∈ [0, 1]
         × marginal_alpha_factor  # g() ∈ [0.25, 1.5]   (§6.1)
         × vol_norm_factor        # C16 ∈ (0, 1]        (§6.2)
         × taper_factor           # §9.5 pre-limit taper from Risk ∈ [0, 1] (§6.3)
size     = apply_hard_limits(raw_size, signal, portfolio)   # clamp only downward, may zero
```

### 6.1 Marginal-alpha factor — exact function (closes GAP-0005)

**Estimator:** over the rolling `marginal_alpha_window` (50) closed trades (each records `size_units` and net `pnl`), split at the **median executed size** into buckets S (≤ median) and L (> median). The derivative estimate and its baseline:
`m = (mean(pnl_L) − mean(pnl_S)) / (mean(size_L) − mean(size_S))` (PnL per additional unit) · `b = mean(pnl_i / size_i)` over the window (the portfolio's average PnL per unit).

**Normalisation `g` (piecewise linear, x = m/b):**
- `b ≤ 0` (the whole window's edge is non-positive) ⇒ `g = 0.25` (anti-greed floor — scaling down is mandatory).
- `x ≤ 0` (marginal ≤ 0) ⇒ `g = 0.25`.
- `0 < x < 1` ⇒ `g = 0.25 + 0.75·x` (continuous ramp to neutral).
- `x = 1` (marginal ≈ baseline) ⇒ `g = 1.0` (neutral, exactly).
- `x > 1` ⇒ `g = min(1.5, 1.0 + 0.5·(x − 1))` (cap at 1.5 reached at x ≥ 2 — never more).

Properties (unit-tested, C-GOV-1): monotone non-decreasing; 0.25 for all m ≤ 0; 1.0 at neutral; ≤ 1.5 always; never NaN/inf for finite inputs. **Cold-start (F15):** fewer than `marginal_alpha_min_trades` trades, either bucket under `marginal_alpha_min_bucket`, or `mean(size_L) == mean(size_S)` ⇒ pinned to `1.0` + `MARGINAL_ALPHA_PINNED` logged. No artificial exploration trades, ever.

### 6.2 Vol-normalisation factor — exact function (C16, v2.9)

`v` = realized fractional volatility = `ATR(14) / mid` per instrument (from the Governor's own mid window, reusing the proven phase-3 ATR). Declared target `v*` = the instrument's `vol_target_atr_frac`.
**`vol_norm(v) = 1.0 if v ≤ v* else v*/v`** — the classic vol-targeting ratio, dampen-only. Properties (unit-tested): exactly 1.0 at/below target; strictly monotone decreasing in excess vol; never > 1.0; → 0 as v → ∞; never NaN/inf for finite v > 0. **Warm-up:** until the ATR window is warm ⇒ pinned `1.0` + `VOL_NORM_PINNED` logged.

### 6.3 Pre-limit taper consumption (§9.5, ratified)

The Risk Monitor delivers `taper_factor ∈ [0, 1]` over the single upward edge. The Governor multiplies `raw_size` by it **before** the hard overrides evaluate. **The edge is risk-restrictive only (GAP-0014): `apply_risk_state` rejects any taper > 1.0, any alpha-decay multiplier > 1.0, and any instruction that would raise a size — `DataQualityError`, logged.** Until Risk exists (phase 9) the taper defaults to 1.0 (no taper — the neutral, not a guess).

**Half-life (C3/F7):** `regime.estimated_half_life_seconds` is **not** a factor (folded into `regime_factor`) — recorded in `factors_snapshot`, multiplied by nothing.

### 6.4 Target positions (v1.7, R1.6; owner-ratified 2026-10-02, master v2.27)

The Governor turns each ACIS-04 §4b `Forecast` into orders:
- **Average position** (Carver), in units: `A = capital_ref x (vol_target / 16) / (pct_vol x price_basis x q) x weight x IDM`, the formula RSIM grades (`tests/backtest/rsim.py`). `capital_ref` is the account's declared initial capital (its rulebook), `vol_target` its declared annual target, `weight` equal across the account's instruments in the family's class-equal scheme, `IDM = min(sqrt(N_eff), 2.5)` fixed at registration. The demo: capital_ref $10k at a 20% vol target (R6-5, re-ruled 2026-10-02 on J1's evidence: at 10% the minimum lot keeps the book flat ~78% of days, GAP-P12D-101), held in a $100,000 demo account so the hard caps admit the book (GAP-P12D-142).
- **Optimum** `= value / 10 x A`. **Band (master §5.5 v2.26):** a current position inside [optimum − 0.1·A, optimum + 0.1·A] places no order; outside, the target is the band's nearest edge.
- **Mode caps, in order:** (1) the one lot rule onto the venue's step and minimum, TOWARD zero; (2) **paper and practice: |target| <= one venue minimum lot, sign kept** (master §5 D-a; for this path it replaces step 3b's "a formula size above zero becomes one lot"); (3) live: rung-1 families only, at the account's risk budget (the post-edge guardrail-profile plan; live stays closed until then).
- **Then every hard limit** (§7 steps 1 and 4, the taper, blackout/§9.5): an increase is an ENTRY and meets every entry gate; a reduction is never blocked (ACIS-06 C-EXE-7). **Except (v1.11, master v2.33, owner ruling "Replace before the cutover"):** a target entry is not gated by NVMA at all (no veto, confidence, ILLIQUID, dead-market or warm-up state) and not by §7.1's low-confidence guard; its data check is the runtime's feed watch (a tick within two NVMA cycles (120 s each) and not late, a spread within 3x the median of the instrument's last 600 quoted spreads, and no macro window (inert until the calendar is wired)), which refuses with `no_feed`, `stale_feed`, `feed_warming`, `wide_spread` or `macro_event`. It supersedes v1.9's veto split. The signal path is unchanged.
- **Orders.** `delta = target − current`: a reduction (or a flip's closing leg) through the reduce-only close, then any opening leg as a new entry. Each opening order carries a broker-side **disaster stop** at `10 x daily ATR` from the fill (R6-2; `tsmom_disaster_stop_atr`; a declared deviation in the TREND provenance records, since Carver uses none). A position its disaster stop closed is not re-entered before the next decision.
- **Execution clock.** Day d's orders execute at the instrument's slot (FX and metals 08:00 New York, US indices 10:00 New York, UK100 09:00 London, EU50 09:00 Frankfurt, JP225 10:00 Tokyo, AUS200 11:00 Sydney) in the first session after 17:00; a slot a closed market or a blackout removes is skipped, never caught up.
- **Universe (R6-4).** The demo trades the 21 explored non-energy instruments the venue offers; the 7 held-out instruments are not traded.

## 7. Core logic (step by step)

1. **Guards (pre-formula, each logged in `factors_snapshot`):** expired → `(0,"expired")`; `not regime.tradeable` → `(0,"veto")`; active HALT (all/instrument) → `(0,"halt")`; `daily_drawdown_pct ≥ daily_drawdown_pct limit` → `(0,"drawdown_halt")` + session halt state; `regime.confidence < 0.55` → `(0,"low_confidence")`; `liquidity_state == ILLIQUID` → `(0,"illiquid")`; `portfolio.stale` → `(0,"portfolio_stale")`; **blackout (§3.5/§9.5): instrument inside a restricted-account blackout window → `(0,"blackout")` + `BLACKOUT_OVERRIDE_ENFORCED` logged (v2.7 carry-forward) — no exception, ever**; **account rules (§9.5):** formula size above the account `max_lots` → `(0,"lot_cap")` (zero, never clamp-to-cap — master §6 overrides are zero-overrides); no-account (v1.5: every account) within `weekend_entry_buffer_s` of the weekend close or of a declared holiday closure, or inside the closed window → `(0,"weekend_ban")`; MOMENTUM_SCALP signal on an account whose `min_hold_seconds` exceeds the scalp horizon → `(0,"min_hold_conflict")`.
2. **Factors:** conviction, liquidity, correlation, regime, marginal-alpha (§6.1), vol-norm (§6.2), taper (§6.3) — each isolatable, all in `factors_snapshot`.
3. **raw_size** = product × `BASE_UNIT_USD`; converted to `Decimal` BASE-currency units by dividing by the USD value of one base unit (v1.3, GAP-P12D-22): the `entry_price` when USD is the quote (EUR/USD, XAU/USD); exactly 1 when USD is the base (USD/JPY); for a cross, `entry_price` × the quote currency's USD rate from its USD leg's last completed signal bar. A cross with no USD leg observed yet sizes zero (`no_usd_rate`) — never a guessed rate. The order's USD notional for the step-4 caps (and each pair leg's) is units × that same USD value (`core/governor/units.py`).
3b. **Minimum size (v1.6; master §5 v2.22, "validated" per mode; owner ruling 2026-09-30, GAP-P12D-129):** in paper and practice modes the wiring injects `fixed_units(instrument)` = one venue minimum lot. A formula size above zero becomes exactly that quantity (the formula's is kept as `formula_units` in `factors_snapshot`); a zero is never raised, so Risk's taper at 0 and every §7.1 guard still stop the order. Step 4 then judges the minimum-lot order itself, so a lot that breaches a cap or the account's `max_lots` is zeroed. A pair group rebalanced below a leg's minimum lot is refused whole at Execution (ACIS-06 §5.5 both-or-neither). In live mode nothing is injected and the formula size stands.
4. **Hard limits (clamp only downward):** cluster cap — adding the order pushes any of the instrument's clusters over `cluster_cap_pct × NAV` → **zero, never split**; single-currency net delta over `single_currency_delta_cap_pct × NAV` → zero; alpha-decay flag from Risk → all sizes × 0.25. **Entry headroom (v1.7, G-5, owner-ratified 2026-10-02):** an entry is admitted only up to 90% of each cap (`ENTRY_HEADROOM`), so mark drift alone cannot carry the book into the Risk Monitor's 100% breach, a human-only global HALT; a reduction is never blocked (GAP-0051). Proof: `test_g5_an_entry_is_admitted_only_to_ninety_percent_of_a_hard_cap`.
5. **Emit** `SizedOrder` (size possibly 0) with full `factors_snapshot` + `reason`; zero-size orders are still emitted + logged.
6. **Pair groups (§5.5):** `allocate_group` runs both legs through steps 1–4; **if either leg is zero for any reason, both are zero** (`reason="group_blocked:<leg-reason>"`); otherwise both legs take the SMALLER leg's USD notional, each expressed in its own base units (v1.4, GAP-P12D-26: unit counts are not comparable across base currencies) — balanced relationship exposure, one relationship bet, not two directional bets; the group registers ONCE in the open-group registry, counts once against its cluster, and its per-currency delta is the NET of both legs. 7. **Group exits (GAP-0040):** `check_group_exits(coupling_state, now)` — for each registry group whose relationship reports a coupling break or reconvergence (the AGON-side state, passed in as data), emit `action="close"` orders for BOTH legs (`reason="coupling_break"` / `"reconvergence"`), remove the group from the registry. Never one leg alone. Closing is risk-reducing: it needs no boundary and no human token.
8. **HALT handling:** Risk (or MCP via ACIS-08) calls `apply_halt(scope, reason)`; step 1 zeroes new sizing for that scope until **human** `resume(human_token)`. A blank token is refused (`PromotionForbiddenError` teeth-class). The session-drawdown halt auto-clears at the next session boundary (master §8 "for session"); explicit/equity HALTs never auto-clear. **v1.5 — one resume path:** `CapitalGovernor.resume(human_token)` is the ONLY resume; it runs the Risk Monitor's `on_human_resume` first, which clears the halt ledger (ACIS-07 v1.2), and if that raises nothing lifts. ACIS-08's resume maps to it and nothing else.
9. **Weekend/holiday flatten (v1.5, master §9.5):** on an account without weekend holding, from the start of the `weekend_entry_buffer_s` window until the market reopens, `weekend_flatten(portfolio, now)` emits an `action="close"` order for every open position (both legs of a pair; the group retired), every tick until flat; a position still open after the close logs `WEEKEND_FLATTEN_INCOMPLETE` for the human. The same applies before every declared ≥2 h holiday closure.
10. **Close convention (v1.5, GAP-P12D-74):** an `action="close"` order NAMES the position to close — `direction` is that position's side and `size_units` the quantity to take off it. The Governor never emits the trade's side for a close; Execution trades the opposite side, reduce-only (ACIS-06 v1.3).

**Determinism:** identical `(signal, portfolio, regime, risk_state, now)` ⇒ identical `SizedOrder` minus `order_id` (no randomness in this layer).

## 8. State machine

`NORMAL → THROTTLED(alpha_decay ×0.25) → HALTED(scope) → NORMAL(human resume only)`; plus the session-scoped drawdown halt (auto-clears at the next session boundary — distinguished from equity/explicit HALTs and tested as distinct, C-GOV-5).

## 9. Persistence & logging

`governor_log` (JSONL, master §11): every `allocate`/`allocate_group`/group-exit with the **full `factors_snapshot`** and `reason`. Events: `SIZED{order_id, size, reason}`, `CLUSTER_CAP_ZERO`, `CURRENCY_DELTA_ZERO`, `MARGINAL_ALPHA_PINNED`, `VOL_NORM_PINNED`, `BLACKOUT_OVERRIDE_ENFORCED{instrument, account}`, `GROUP_BLOCKED{group_id, leg_reason}`, `GROUP_EXIT{group_id, reason}`, `HALT_APPLIED{scope, reason}`, `HALT_RESUMED{by}`, `ALPHA_DECAY_THROTTLE`, `PORTFOLIO_STALE`, `RISK_STATE_REJECTED` (upward edge tried to be expansive). No decision is unlogged.

## 10. Store schema (SQLite, phase-1 discipline)

```sql
CREATE TABLE governor_decision (
    order_id     TEXT PRIMARY KEY,
    ts           TEXT NOT NULL,
    signal_id    TEXT NOT NULL,
    instrument   TEXT NOT NULL,
    direction    INTEGER NOT NULL,
    size_units   TEXT NOT NULL,        -- Decimal serialised as text, never float
    reason       TEXT NOT NULL,
    action       TEXT NOT NULL,
    group_id     TEXT,
    factors      TEXT NOT NULL,        -- factors_snapshot JSON
    param_set_id TEXT NOT NULL,
    session_id   TEXT NOT NULL
);
```

## 11. MCP contract

Sizing state contributes to `acis://status` and `acis://risk/snapshot`. Control tools (ACIS-08): `acis_halt` → `apply_halt`; `acis_flatten` → flatten then halt; `acis_resume` (**human-token only**) → `resume`. No tool raises a limit; `acis_stage_config` cannot touch guardrail paths (schema-rejected). Any agent may halt; only a human resumes.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| expired/veto/halt/drawdown/low-confidence/illiquid/blackout/lot-cap/weekend/min-hold/stale | `SizedOrder(size=0, reason)` — decision, not error |
| cluster or currency-delta breach | size 0 (`CLUSTER_CAP_ZERO` / `CURRENCY_DELTA_ZERO`), never split |
| marginal-alpha / vol-norm insufficient data | pin 1.0 (`MARGINAL_ALPHA_PINNED` / `VOL_NORM_PINNED`) |
| upward edge delivers an expansive instruction | `DataQualityError` + `RISK_STATE_REJECTED` — the edge is risk-restrictive-only |
| resume without a human token | `PromotionForbiddenError` — no self-resume |
| one pair leg blocked | both legs 0 (`GROUP_BLOCKED`), group not registered |
| group exit with an unknown group | no-op (already flat) — logged |

## 13. Logic-flaw registry
- **C-GOV-1 (C6/F14/GAP-0005):** `g()` implements + tests the five contract properties with the exact §6.1 piecewise form; hand-computed vectors (x = 0.5 ⇒ 0.625, x = 1 ⇒ 1.0, x = 2 ⇒ 1.5).
- **C-GOV-2 (F15):** cold-start pin to 1.0 until min-trades + both buckets populated; no synthetic exploration trades.
- **C-GOV-3 (C7):** cluster caps zero-not-split; a group counts once.
- **C-GOV-4 (hard overrides):** every guard in §7.1 individually zeroes size (isolated tests) — including blackout (with `BLACKOUT_OVERRIDE_ENFORCED`), lot cap, weekend ban, min-hold conflict.
- **C-GOV-5 (HALT):** HALT zeroes new sizing until human resume; blank token refused; session-drawdown halt auto-clears at the boundary, equity/explicit HALTs do not.
- **C-GOV-6 (C3/F7):** changing `estimated_half_life_seconds` alone never changes size.
- **C-GOV-7 (F17):** `size_units` is Decimal end-to-end; NAV/delta/exposure math is Decimal — no float accumulation.
- **C-GOV-8 (C16):** vol-norm exact fn: 1.0 at/below target, `v*/v` above, dampen-only, warm-up pinned — property-tested.
- **C-GOV-9 (§9.5 taper / GAP-0014):** taper multiplies before overrides; `apply_risk_state` rejects any factor > 1.0 (the upward edge can never raise a size) — tested.
- **C-GOV-10 (§5.5/GAP-0040):** groups size both-or-neither at min(leg sizes), count once, net their currency delta; a coupling break/reconvergence closes BOTH legs via `action="close"`; never one leg alone.

## 14. Test contract (postcondition-style)

**Unit:** each factor isolated (vary one, hold others); `g()` exact vectors + property sweep; cold-start pin events; vol-norm exact vectors (v = v* ⇒ 1.0; v = 2v* ⇒ 0.5) + warm-up pin; taper 0.5 halves size, taper 1.2 raises `DataQualityError` + `RISK_STATE_REJECTED`; every §7.1 guard zeroes size individually (incl. blackout logging `BLACKOUT_OVERRIDE_ENFORCED`, lot cap, weekend buffer, scalp-min-hold); cluster cap at exactly the limit ⇒ next correlated order 0; currency delta cap ⇒ 0; alpha-decay ⇒ ×0.25; expired ⇒ 0; HALT ⇒ 0, blank-token resume refused, human token resumes; session-drawdown halt clears at boundary while explicit halt survives it; half-life invariance; Decimal end-to-end; group both-or-neither + min-size balancing + single cluster count + net delta; group exit emits two `close` orders and empties the registry.

**Integration (with ACIS-04):** AGON emits on a trend fixture → Governor sizes it (non-zero) with full snapshot; the same signal under a vetoed regime never reaches sizing (AGON silent) and a manually crafted vetoed allocate is 0 (defense in depth); a pair group from AGON sizes atomically and a coupling break closes it; drawdown limit hit ⇒ zero new orders until the session boundary.

## 15. Integration gate

**What Execution (ACIS-06) consumes:** `SizedOrder` (size possibly 0; `action` open|close). Execution never re-sizes. **Owns conflict-table rows:** "correlation cap breach → size 0, don't split"; "daily drawdown limit → halt new positions for session"; disposition side of "NVMA no-trade". **Done-when (phase 6, master §15, paper allocation):** §14 green in a full run; import contract passing; `g()` and `vol_norm()` concrete and tested; GAP-0040 closed.

## Changelog
- **1.11 (LOCKED, 2026-10-03)** — §6.4: a target entry's data check is the runtime's feed watch, not NVMA (master v2.33, GAP-P12D-152). Proof: `test_a_target_entry_reads_the_feed_check_and_no_regime`, `test_each_refusal_reads_only_the_tick_feed`.
- **1.10 (LOCKED, 2026-10-03)** — §6.4: in paper and practice the alpha-decay ×0.25 is REPORTED, not applied, to target entries (the one-lot book; owner ruling "Report only on demo (Recommended)", PR16E-01, GAP-P12D-150; master v2.31): on returns that never decay the throttle arms within 200 trades in 70–93% of runs, and stage D's E2 is the forward decay test. Live applies it until GATES R8 replaces it with the post-edge plan. ILLIQUID stays an integrity gate (owner ruling "Keep it, measure"). Proof: `test_on_the_one_lot_demo_alpha_decay_is_reported_not_applied`.
- **1.9 (LOCKED, 2026-10-03)** — §6.4: target entries ignore NVMA's confidence and label vetoes and §7.1's low-confidence guard, and keep its data-integrity gates (GAP-P12D-147, owner ruling "Exempt confidence vetoes (Recommended)" 2026-10-02; master v2.30). The signal path keeps every veto; no guardrail VALUE, HALT or hard limit changed. Proof: former `test_a_target_entry_ignores_the_confidence_vetoes_but_not_the_integrity_gates` (superseded by v1.11).
- **1.8 (LOCKED, 2026-10-02)** — §6.4's demo sizing reference, owner-ratified in chat: "20% (Recommended)" (the vol target, R6-5 re-ruled on J1's evidence, GAP-P12D-101) and "$100k demo, $10k sizing (Recommended)" (GAP-P12D-142: at $10k NAV the hard caps admit about one one-lot position per cluster). Sizing still caps each position at one minimum lot; no guardrail value changed.
- **1.7 (LOCKED, 2026-10-02)** — §6.4 target positions (the average position, Carver's band, the paper/practice one-lot cap, the 10 x ATR disaster stop, the execution clock, the demo universe and sizing; rulings R6-2/4/5) and §7 step 4's entry headroom (G-5), both owner-ratified (master v2.27).
- **1.6 (LOCKED, 2026-09-30)** — §7 step 3b: in paper and practice modes an order the formula sizes above zero is traded at exactly one venue minimum lot, then judged by every hard limit. This applies master §5 v2.22's ratified "validated" per mode (paper and practice at minimum size, GAP-P12D-106) and the owner's 2026-09-30 ruling for the demo ("trade them at one minimum lot", GAP-P12D-129): the formula sizes a demo order at ~850 EUR, under the venue's 1,000-unit minimum, so without it every demo open is refused. A zero is never raised and no guardrail value, HALT/veto semantic or hard limit changes. Proof: `test_paper_and_practice_trade_exactly_one_minimum_lot`, `test_the_minimum_lot_never_raises_a_zero_and_meets_every_hard_limit`.
- **1.5 (LOCKED, 2026-09-25)** — prop-safety amendments, merged 2026-09-25 from the BUILDER-3 branch on the owner's explicit go, after the constitution's two audits (GAP-P12D-77..81, every finding fixed and lead-verified); amendment text applied under the owner's delegation; tightening only, no guardrail VALUE changed: `weekend_entry_buffer_s` binds every account and every declared holiday closure (GAP-P12D-58); step 9 the weekend/holiday flatten; step 10 the reduce-only close convention (GAP-P12D-74); one human-resume path that clears the halt ledger first. Version-history note: the header read 1.3 with a v1.4 amendment and the index read v1.2 — both corrected here.
- **1.4 (2026-09-15, owner: "Balance in USD")** — §7 step 6: pair legs take the smaller leg's USD notional, each in its own base units, not `min(size_A, size_B)`; after v1.3 a unit count of EUR and one of USD were not comparable, leaving a directional USD residual (GAP-P12D-26, from the dual audit of 068f8b4). §5: `per_currency_delta` is USD notional, matching the code and §7 step 3.
- **1.3 (2026-09-15, owner: "fix the governor sizing")** — §7 step 3 states the base-unit conversion the §4 contract already required: raw USD ÷ the USD value of one base unit (price for USD-quote, 1 for USD-base, price × the quote leg's USD rate for a cross; no rate ⇒ `no_usd_rate` zero). The code had divided by the price for every instrument, sizing USD/JPY ~150× small and shrinking any pair group with a yen leg (GAP-P12D-22). Exposure notional uses the same factor. No guardrail value or semantic changed.
- **1.2 (LOCKED, 2026-07-16)** — Phase-6 subordinate-audit triage (GAP-0049..0053, all fixed same-day with regression tests; suite 274 green): **GAP-0049 (HIGH)** §7.6 actually enforced — group legs defer exposure checks to `allocate_group`, which caps the AGGREGATE (balanced group notional once per union cluster; currency deltas netted across legs; blocked groups zero both legs and never register); **GAP-0050 (HIGH)** `apply_risk_state` None-sentinel parameters — None = unchanged, so a taper-only call can never implicitly clear an alpha-decay throttle; explicit clears logged `ALPHA_DECAY_CLEARED` (legitimacy conditions are ACIS-07's phase-9 contract); **GAP-0051** the delta cap blocks only breach-increasing orders — de-risking orders always pass; **GAP-0052** `rebuild_groups(portfolio)` restores the open-group registry after a restart (`Position` gained `stop_loss`/`take_profit`/`param_set_id`; single-leg orphans surfaced via `GROUP_REBUILD_ORPHAN`; the phase-7 loop owner MUST call it at boot); **GAP-0053** the weekend entry ban covers the entire closed window (pre-close buffer → Sunday open; `weekend_open_utc` added to the constructor). §9 event list gains `ALPHA_DECAY_CLEARED`, `LOT_CAP_ZERO`, `GROUP_EXIT_UNKNOWN`, `GROUP_REBUILT`, `GROUP_REBUILD_ORPHAN`. Every fix tightens or restores a declared invariant; no limit loosened.
- **1.1 (LOCKED, 2026-07-16)** — v2.5–v2.9 consistency pass at phase-6 start: **GAP-0005 closed** (exact piecewise `g()` with continuous ramp, bucket estimator, cold-start pin); **C16 exact vol-norm** (`v*/v` above the declared per-instrument target, dampen-only, warm-up pinned; `vol_target_atr_frac` required per enabled instrument); **§9.5 taper consumption** with the GAP-0014 risk-restrictive-only upward edge enforced at the interface (`RISK_STATE_REJECTED`); **v2.7 `BLACKOUT_OVERRIDE_ENFORCED`** logged on every fired blackout override; **§9.5 account-rule overrides** concretised (lot-cap zero-not-clamp, weekend entry buffer, scalp min-hold conflict); **§5.5 pair groups** — both-or-neither at min(leg), once-per-cluster, net delta, plus the **GAP-0040 group-exit path** (`action="close"`, registry, break/reconvergence — closes it); `single_currency_delta_cap_pct: 30` added to `guardrail_limits.yaml` at the exact master-§6 value with a ≤30 schema ceiling (stricter-only), flagged to the owner for veto; SQLite DDL; Decimal discipline (F17) begins here for sizing quantities. No limit was loosened anywhere; every new mechanism only reduces or refuses size.
- **1.0 (DRAFT)** — From master §6 + `ACIS_Agent_Prompt.md` §3.5 + S2 §05 Governor formula; C6/F14/F15 contracts declared.
