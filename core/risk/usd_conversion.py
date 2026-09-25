"""Quote-currency → USD factor for Risk accounting (GAP-P9E-04 / rescoped GAP-0092).

Moved unchanged out of core/risk/monitor.py (legibility budget, GAP-P12M-01).
Invariant: a factor is returned only where it is derivable from the instrument's own
price — XXX_USD → 1.0, USD_XXX → 1/price. A true cross (neither side USD) returns None
and the caller must say so (CONVERSION_UNAVAILABLE); a rate is never guessed.
"""

from __future__ import annotations


def usd_factor(instrument: str, price: float) -> float | None:
    """The factor converting a QUOTE-currency amount to USD at `price`; None for a
    cross (the caller logs CONVERSION_UNAVAILABLE — a phase-11 FX-rate-table job).
    Exact for the enabled universe (EUR_USD, USD_JPY), so per-instrument DD, VaR
    and cluster caps never mix quote and account currency."""
    base, _, quote = instrument.partition("_")
    if quote == "USD":
        return 1.0
    if base == "USD":
        return (1.0 / price) if price else 1.0
    return None
