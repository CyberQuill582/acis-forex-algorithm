# Per-account guardrail profiles and the daily risk budget (DRAFT, 2026-10-02)

**Status:** DRAFT for owner ratification. **Applied only after a family holds rung 1** (owner ruling 2026-10-02, "Draft now, apply after an edge"). `config/guardrail_limits.yaml` is human-commit-only: nothing here changes it, and no code path, flag or MCP tool may. On ratification and after rung 1, the owner commits the profile values; the lead builds the schema and the Governor/Risk Monitor reading them.

**Evidence:** `archive/RESEARCH_SIZING_AGGRESSION_2026-10-01.md`, its simulator re-run and verified by the lead (GAP-P12D-61): today's notional caps (cluster 20% of NAV, single-currency delta 30%) hold the traded book at ~0.15–0.16% of NAV a day at any account size, 4–8× below the book R1 grades; at that ceiling an FTMO-style 2-Step passes within two years 0.07% of the time at a true Sharpe of 0.5. At 1%/day the same account is worth +$3,946 per $100k attempt at Sharpe 0.5 (1-day holds) and +$2,913 with 20-day holds under the daily-room guard below; the zero-edge control earns +$1,493 / +$895, the option value, which is never skill.

**The line this draft holds:** size scales an edge; it never creates one. Nothing here may apply before rung 1, and the personal-account profile keeps today's values.

---

## 1. The risk unit: a daily P&L-volatility budget per account and stage

Each account's rulebook (`platform_rules.yaml`) declares `profile` and `daily_vol_budget_pct` (% of its declared initial capital):

| Profile | Budget | Why |
|---|---|---|
| `personal` | 0.25%/day (≤ 0.5% only after ≥ 2 years of forward record) | Kelly under parameter uncertainty; ruin is real money |
| `prop_challenge` | 1.0%/day (SIZING's band 1.0–1.25) | the fee caps the loss; edge uncertainty argues for more risk here, not less |
| `prop_funded` | min(1.0%/day, 0.10 × the cushion to the binding firm floor) | best value with ~1.5% 126-day breach at Sharpe 0.5 (SIZING EXP3/4b) |

The family's book is sized to the budget (ACIS-05: `vol_target = budget × 16`), not to a fixed notional.

## 2. Per-account guardrail profiles (the notional caps)

- **`personal`:** keep `cluster_cap_pct: 20` and `single_currency_delta_cap_pct: 30` exactly. They bound the scenario book's CHF case at 7% of NAV (20% notional × a 35% gap).
- **`prop_*`:** replace them with risk caps: a cluster ≤ 50% of the daily budget, a currency's net ≤ 60% of it, plus a hard **gross-notional ceiling** as the bug-catcher: ≤ 5× NAV for FX, ≤ 2× for indices and metals (inside the venue's leverage).
- **The risk, stated:** a 3× FX book through a 35% CHF-style gap loses ~105% of NAV. On a personal account that is ruin; on a prop account it is the fee plus the lost record, and the firm absorbs the rest. The scenario-replay ceilings (`scenario_book.yaml`) become per-profile (GAP-P11I-10).

## 3. The daily-room guard (inside the guardrails: it only shrinks)

Daily budget ≤ room / 4, where room = min(equity − the firm's daily floor, equity − its static floor), both in the firm's own semantics (the daily floor from the 00:00 balance, tested on equity). It composes by min() with the §9.5 taper. Verified value: with 20-day holds at 1%/day it lifts the EV per $100k attempt from +$723 to +$2,913 and cuts daily-limit deaths from 95% to 23% of failures.

## 4. The VaR cap and the instrument halt

- **VaR:** keep 3% undiversified as a REPORT; on prop profiles gate on a diversified figure consistent with the budget (≈ 2.326 × budget × the diversification ratio), estimated from daily returns, not 10-second marks × √8640.
- **The instrument halt** is GAP-P12D-139's ruling (spec vs code); on prop profiles express it as a budget share (≤ 1% of NAV of open loss for a sleeve sized ≤ 0.1%/day) so a multi-week hold does not halt about a third of the time.

## 5. Headroom (inside the guardrails, buildable before rung 1)

The Governor admits orders only to ≤ 90% of the cluster and currency caps and ≤ 80% of the VaR cap, so mark drift alone cannot trip a human-only global halt. Regression first: admit at 19.9% of NAV, move the mark +1%, assert no global HALT.

## 6. What this draft does NOT do

No catch-up or martingale sizing; no equity-curve filters; no risk above 1.25%/day on a challenge; no change that makes any guardrail reachable by code; no application before rung 1.

## 7. Proposed rulings

| ID | Question | Recommended |
|---|---|---|
| G-1 | Budgets per profile | personal 0.25%, challenge 1.0%, funded min(1%, 0.10 × cushion) |
| G-2 | Notional caps | keep 20/30 for personal; risk caps + gross ceiling for prop |
| G-3 | Daily-room guard | z = 4, firm semantics |
| G-4 | VaR on prop | diversified, daily-return σ; undiversified kept as a report |
| G-5 | Headroom | 90% of notional caps, 80% of VaR: build now (it only shrinks) |
