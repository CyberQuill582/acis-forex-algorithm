# `[DIR:core/governor]` — Layer 5 · Capital Governor (sovereign allocation)

**Implemented (phase 6, 2026-07-16).** Deep spec: `../../specs/ACIS-05-CAPITAL_GOVERNOR.md` v1.1 (LOCKED) · Master: `../../ACIS_SPEC.md` §6/§9.5.

- **Consumes:** `Signal` + `PortfolioState` + `RegimeContext` + the risk-restrictive upward edge · **Emits:** `SizedOrder` (Decimal, F17) → Execution
- **Files:** `portfolio_types.py` (frozen Decimal accounting types), `marginal_alpha.py` (GAP-0005 exact `g()` + median-bucket estimator, cold-start pin), `factors.py` (liquidity/correlation/C16 vol-norm), `capital_governor.py` (guards + formula + hard limits + atomic pair groups + group-exit registry + halt state)
- **The formula:** base × conviction × liquidity × correlation × regime × marginal-alpha × vol-norm × taper — then hard limits that only clamp downward. Every decision carries its full `factors_snapshot`.
- **Non-negotiable:** the upward edge rejects anything expansive; blackout on a restricted account is `BLACKOUT_OVERRIDE_ENFORCED`, no exception; cluster/delta/lot breaches zero, never split/clamp; groups size both-or-neither and exit whole; resume is human-token-only.
- **Owns corrections:** C-GOV-1..10 (ACIS-05 §13).
