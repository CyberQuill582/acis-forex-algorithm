"""The Governor's hard exposure caps (ACIS-05 §7 step 4; master §6), moved unchanged out of
capital_governor.py (legibility budget, GAP-P12M-01). Invariants:
  * A cluster cap or single-currency net-delta cap breach sizes the order to ZERO, never
    a split and never a clamp (master §6: "Breach → size to zero, never split").
  * GAP-0051: an order that REDUCES an existing |delta| breach is never blocked by it —
    the layer may only ever reduce risk.
  * Deltas are signed USD notional: +notional on the base currency, −notional on the quote.
  * HEADROOM (G-5, owner-ratified 2026-10-02): an entry is admitted only up to ENTRY_HEADROOM
    (90%) of each cap, so mark drift alone cannot carry the book past the Risk Monitor's cap,
    whose breach is a human-only global HALT. It can only shrink an order, never grow one.
"""

from __future__ import annotations

from decimal import Decimal

from config.schemas import GuardrailLimits
from core.governor.portfolio_types import PortfolioState
from core.signals.signal_types import Signal

ENTRY_HEADROOM = Decimal("0.90")     # of each hard cap; stricter allowed, never above 0.90


def delta_contributions(signal: Signal, notional: Decimal) -> dict[str, Decimal]:
    base, _, quote = signal.instrument.partition("_")
    d = Decimal(signal.direction)
    return {base: d * notional, quote: -d * notional}


def exposure_breach(limits: GuardrailLimits, portfolio: PortfolioState,
                    cluster_notional: dict[str, Decimal],
                    delta_contributions: dict[str, Decimal], instrument: str,
                    log) -> str | None:
    """Cluster + net-currency-delta hard caps over the given contributions."""
    cap = ENTRY_HEADROOM * Decimal(str(limits.cluster_cap_pct / 100.0)) * portfolio.nav
    for cluster, notional in cluster_notional.items():
        exposure = portfolio.per_cluster_exposure.get(cluster, Decimal("0"))
        if exposure + notional > cap:
            log.event("CLUSTER_CAP_ZERO", instrument=instrument, cluster=cluster)
            return "cluster_cap"
    delta_cap = ENTRY_HEADROOM * Decimal(str(limits.single_currency_delta_cap_pct / 100.0)) * portfolio.nav
    for ccy, contribution in delta_contributions.items():
        old = portfolio.per_currency_delta.get(ccy, Decimal("0"))
        new = old + contribution
        if abs(new) > delta_cap and abs(new) > abs(old):
            log.event("CURRENCY_DELTA_ZERO", instrument=instrument, currency=ccy)
            return "currency_delta_cap"
    return None
