"""Quote-currency → USD factor for Risk accounting (GAP-P9E-04 / rescoped GAP-0092).

Moved unchanged out of core/risk/monitor.py (legibility budget, GAP-P12M-01).
Invariant: a factor is returned only where it is derivable from the instrument's own
price — XXX_USD → 1.0, USD_XXX → 1/price. A true cross (neither side USD) returns None
and the caller must say so (CONVERSION_UNAVAILABLE); a rate is never guessed.
"""

from __future__ import annotations


def usd_factor(instrument: str, price: float) -> float | None:
    """Convert a QUOTE-currency amount for `instrument` to USD at `price`.
    XXX_USD (quote is USD) → 1.0; USD_XXX (USD base) → 1/price (the quote
    YYY→USD rate is 1/(USD_YYY)). A true CROSS pair (neither side USD) has
    no derivable rate here → None; the caller falls back to quote-ccy and
    logs CONVERSION_UNAVAILABLE (a phase-11 FX-rate-table job). This covers
    the entire enabled universe (EUR_USD, USD_JPY) exactly, so the
    per-instrument DD HALT/taper, VaR, and cluster caps are no longer
    contaminated by a quote-vs-account currency mismatch."""
    base, _, quote = instrument.partition("_")
    if quote == "USD":
        return 1.0
    if base == "USD":
        return (1.0 / price) if price else 1.0
    return None
