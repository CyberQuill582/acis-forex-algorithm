"""The target-position path's sizing (ACIS-05 v1.7 §6.4; master §5.5 v2.26, §5 C8 and D-a; R1.6).

ONE implementation for the research simulator and the Governor, so the book RSIM grades and the
book the engine trades cannot size differently (B0(d) by identity, the GAP-P12D-36 lesson).

Mental model:
  * AVERAGE POSITION (Carver), in units: A = cash_vol / (pct_vol · close · q) · weight · IDM, with
    cash_vol = capital_ref · vol_target / 16. The OPTIMUM is forecast / 10 · A.
  * THE BAND: a current position inside optimum ± buffer·A is kept; one outside trades to the
    band's nearest edge (pysystemtrade `buffer_method: forecast`, `buffer_trade_to_edge`).
  * THE ONE LOT RULE: the banded target rounds TOWARD zero to whole lot steps, and a size below
    the venue minimum is flat (master §5 C8 v2.22, GAP-P12D-101/123).
  * THE MODE CAP (paper and practice, master §5 D-a): |target| <= `cap` units, sign kept. A cap
    never raises a target, so a flat target stays flat.
  * No forecast (NaN) or no positive vol targets flat. Hard limits run afterwards and only shrink.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

VOL_DAYS = 16.0                      # Carver: annual vol / 16 = daily (256 business days)
IDM_CAP = 2.5                        # master §5.5


def target_on_lots(target_units: Decimal, step_units: Decimal, min_units: Decimal) -> Decimal:
    """The one lot rule (master §5 C8 v2.22, GAP-P12D-101/123), for research and execution
    alike: a TARGET position rounded toward zero to whole lot steps; a target whose size is
    below the venue minimum is flat. The order is then this minus the current position."""
    if step_units <= 0 or min_units < step_units:
        raise ValueError(f"need 0 < step ({step_units}) <= minimum ({min_units})")
    size = (abs(target_units) / step_units).to_integral_value(rounding=ROUND_FLOOR) * step_units
    if size < min_units:
        return Decimal("0")
    return size if target_units > 0 else -size


def buffered(current: float, optimum: float, band: float) -> float:
    """Carver's buffer: inside optimum ± band, keep; outside, trade to the nearest edge."""
    lo, hi = optimum - band, optimum + band
    return lo if current < lo else hi if current > hi else current


def optimum_units(forecast: float, pct_vol: float, close: float, q: float, *, cash_vol: float, weight: float,
                  idm: float) -> float:
    """Carver's continuous position in units: forecast/10 x the average position; no band, lot or cap.
    It is the SHADOW book's position (the forward record's uncapped twin, master v2.33 TODO)."""
    if forecast != forecast or pct_vol != pct_vol or pct_vol <= 0:
        return 0.0
    return forecast / 10.0 * cash_vol / (pct_vol * close * q) * weight * idm


def banded_target(current: float, forecast: float, pct_vol: float, close: float, q: float, *,
                  cash_vol: float, weight: float, idm: float, buffer: float,
                  step: Decimal, minimum: Decimal, cap: Decimal | None = None) -> Decimal:
    """The position the book should hold after this decision, in units (see the mental model)."""
    if not (0 < idm <= IDM_CAP) or cash_vol <= 0 or weight < 0 or buffer < 0:
        raise ValueError("need 0 < idm <= 2.5, cash_vol > 0, weight >= 0, buffer >= 0")
    if forecast != forecast or pct_vol != pct_vol or pct_vol <= 0:
        optimum, band = 0.0, 0.0
    else:
        average = cash_vol / (pct_vol * close * q) * weight * idm
        optimum, band = forecast / 10.0 * average, buffer * average
    target = target_on_lots(Decimal(str(float(buffered(current, optimum, band)))), step, minimum)
    if cap is not None and abs(target) > cap:
        return cap if target > 0 else -cap
    return target
