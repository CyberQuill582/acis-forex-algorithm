# R1.6 amendment — the target-position path (DRAFT for owner ratification, 2026-10-02)

**Status:** DRAFT. Nothing here binds until the owner ratifies it. On ratification it is applied as **ACIS-04 v1.6** (the interface; §4's `Signal` successor, "specified HERE before R1.6 builds it"), **ACIS-05 v1.7** (the Governor's target sizing, band and caps) and **ACIS-03 v2.2** (flatten-then-promote), with the master §5.5 cross-references updated. Then R1.6 is built against it.

**Why now:** the owner's 2026-10-02 ruling, "R1.6 interleaved with R1.4": the demo moves from one evolved QIEA champion to the TREND family at one minimum lot per instrument (master §5 D-a), so its forward record starts weeks earlier (PACE, `archive/RESEARCH_PACE_AND_CREDITS_2026-10-01.md` §4.1 P1/P2).

**Unchanged (and unreachable by anything here):** `config/guardrail_limits.yaml`, the equity floor, HALT/veto/resume semantics, the NVMA `tradeable=False` veto, the live gate (rung 2 + human sign-off), the reduce-only close (ACIS-06 C-EXE-7), the one lot rule (`target_on_lots`). Every size this path produces is judged by every hard limit afterwards and can only shrink there.

---

## 1. What the ratified master already fixes (restated, not changed)

Master §5.5 v2.21–v2.26: families emit **forecasts**; per instrument AGON combines them (fixed weights, equal within a family then equal risk across families) × FDM (≤ 2.5), capped at ±20, into **one target position**; the no-trade band is Carver's, ±10% of the average position around the TARGET, owned by the Governor; orders execute on the pre-registered per-symbol clock; reductions go through the reduce-only atomic close; regimes no longer gate families. Master §5 D-a: in paper and practice modes a registered, B0-passed family trades at **at most one venue minimum lot per instrument**, on live-eligible instruments only.

## 2. The daily decision (new; ACIS-04 §8)

- **Clock.** One decision per New York weekday at **17:00 America/New_York** (the FX rollover), as RSIM decides (`tests/backtest/rsim_real.py`). The runtime's slow loop owns it; the fast loop is untouched.
- **Inputs per instrument:** the daily mid closes (the last traded hour ending at or before 17:00 New York, within 4 days), and the **excess-return price** the registered family reads: closes compounded with the dated overnight carry differential (`trend_d1_v1`'s declared deviation). The engine therefore needs the rate table at runtime.
- **Data seeding.** At boot, each instrument's D1 history comes from the venue's own trendbars (cTrader `ProtoOAGetTrendbarsReq`, the mechanism GAP-P12D-131 (b) needs for TSMOM), at least 3 years, cached locally and appended at every decision. A history shorter than the family's warm-up (260 decisions plus the normaliser's) gives no forecast: flat.
- **Freshness (proposed ruling R6-1).** If the rate table is more than 10 days stale, or an instrument's last close is older than 4 days, that instrument's forecast is NaN: no new target, existing positions kept (reductions only through the band or a halt).

## 3. The interface (ACIS-04 §4 successor; `Signal` stays for the legacy modules until R1.7)

```python
@dataclass(frozen=True)
class Forecast:                  # AGON -> Governor; AGON knows no capital, no positions
    instrument: str
    value: float                 # combined, FDM-scaled, capped: finite, |value| <= 20; NaN never crosses (no forecast = no object)
    family_ids: tuple[str, ...]  # the registered family-versions netted into it (provenance ids, e.g. "trend_d1_v1")
    decision_day: date           # the New York date of the 17:00 decision
    decided_at: datetime         # tz-aware
    price_basis: float           # the decision close (sizing's `close`)
    pct_vol: float               # the family's sizing vol (Carver's normaliser / close), > 0
    inputs_hash: str             # sha256 of the closes, rates and parameters read: replay parity (B0(d))
```

Validation on construction (`DataQualityError`): finite fields, |value| ≤ 20, pct_vol > 0, tz-aware time, a non-empty family tuple whose ids are registered in the provenance store at emission.

## 4. The Governor's target (ACIS-05 §6–§7 additions)

- **Average position** (Carver), in units: `A = capital_ref × (vol_target / 16) / (pct_vol × price_basis × q) × weight × IDM`, the formula RSIM grades (`tests/backtest/rsim.py`). `capital_ref` is the account's **declared initial capital** from its rulebook (prop practice measures risk against initial capital; GAP-P12D-61's NAV-relative sizing), `vol_target` the account's declared annual target, `weight` equal across the account's instruments in the family's class-equal scheme, `IDM = min(√N_eff, 2.5)` fixed at registration.
- **Optimum** `= value / 10 × A`. **Band:** the current position inside [optimum − 0.1·A, optimum + 0.1·A] places no order; outside, the target is the band's nearest edge (Carver, master v2.26).
- **Mode caps, in this order:**
  1. the one lot rule onto the venue's step and minimum (round TOWARD zero);
  2. **paper and practice: |target| ≤ one venue minimum lot**, sign kept (master §5 D-a; replaces v1.6 step 3b's "a formula size above zero becomes one lot" for this path);
  3. live: rung-1 families only, at the account's risk budget (the guardrail-profile amendment, drafted separately; until it is ratified, live stays closed as today).
- **Then every hard limit**, exactly as for any order: the tradeable veto, blackout/§9.5 doctrine, the taper, entry halts, cluster/currency caps, VaR. An increase is an ENTRY (all entry gates apply); a reduction is never blocked (C-EXE-7).
- **Orders.** `delta = target − current` becomes `SizedOrder`s: a reduction (or a flip's closing leg) through the reduce-only close, then any opening leg as a new entry. Each opening order carries a broker-side **disaster stop** (§8.6 law) at `k × daily ATR` from the fill (proposed ruling R6-2: `k = tsmom_disaster_stop_atr = 10`, the value TSMOM already declares). A position closed by its disaster stop is not re-entered before the next decision (no same-day re-entry). The stop is a declared deviation in every TREND provenance record (Carver uses none).
- **Execution clock.** Orders from day d's decision execute at the instrument's slot (`rsim_real.SLOTS`: FX and metals 08:00 New York, US indices 10:00 New York, UK100 09:00 London, EU50 09:00 Frankfurt, JP225 10:00 Tokyo, AUS200 11:00 Sydney) on the first session after 17:00. A slot the market or a blackout closes is skipped, never caught up: the next decision supersedes it.

## 5. Coexistence with the legacy modules (proposed ruling R6-3)

**One path per instrument.** An instrument in a family's live universe is traded only by the target path; the legacy AGON modules emit nothing on it. In practice mode on the demo, the legacy modules are switched off entirely (the QIEA champion retires from the demo; the code stays frozen as BASELINE.md's untrained baseline until R1.7). Rationale: two paths on one instrument would net nothing and double the order flow; the legacy path loses on its own positive control (GAP-P12D-49).

## 6. Universe (proposed ruling R6-4)

The demo's TREND universe = the **21 explored non-energy instruments** (all admitted swap-free by the 2026-10-02 admission run, GAP-P12D-94) ∩ the venue's live-eligible symbols. The 7 held-out instruments are not traded (their role is the stage-C history grade; trading them forward would not contaminate history, but keeping them out keeps the held-out set's meaning simple). Energy waits for GAP-P12D-137.

## 7. Flatten-then-promote (ACIS-03 v2.2; D-c, GAP-P12D-108)

A new family-version (or a parameter change) is staged, never applied mid-position: at the next valid session boundary the affected instruments are flattened through the reduce-only close, and only when they are flat is the new version promoted (`PositionGate` and `on_boundary` re-homed as the rule registry's staging, master §5). A promotion whose flatten fails (a halt, a closed market) waits for the next boundary; it is never forced.

## 8. Parity and tests (B0(d); ACIS-09 C-BT-11 v2 step 0)

- **Parity:** on the same lab tape, RSIM's practice-mode book (the min-lot cap applied in RSIM too) and the engine's target sequence agree decision by decision (targets, band outcomes, order deltas). This is B0(d) for the target path.
- **Unit tests (postcondition):** the band places no order inside and trades to the nearest edge outside; the min-lot cap never exceeds one lot and keeps the sign; the one lot rule rounds toward zero first; an increase blocked by a veto/halt places nothing while a reduction still executes; a stale rate table or close gives no target; a disaster stop fires and the instrument stays flat until the next decision; flatten-then-promote never promotes a non-flat instrument; a `Forecast` with an unregistered family id is refused; the slot is never before the decision.
- **Glitch classes (master §13):** DST boundaries at 17:00 New York and at each slot's local hour; a weekend/holiday decision skipped; restart mid-day re-derives the same target (idempotent by `inputs_hash`); a reconnect between the decision and the slot executes once.

## 9. Proposed rulings (the owner rules each; the lead's recommendation first)

| ID | Question | Recommended |
|---|---|---|
| R6-1 | Stale inputs | No new target if rates > 10 days or a close > 4 days stale; positions kept |
| R6-2 | Disaster stop | k = 10 × daily ATR (TSMOM's declared value); no same-day re-entry |
| R6-3 | Legacy modules | One path per instrument; legacy modules off on the demo |
| R6-4 | Demo universe | The 21 explored non-energy instruments the venue offers; held-out not traded |
| R6-5 | Demo sizing reference | capital_ref = the demo's $10k, vol_target 10%, so A is real; the min-lot cap then binds |
