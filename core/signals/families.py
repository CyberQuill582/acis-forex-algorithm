"""The TREND family's provenance records (master §5.6 v2.22; ACIS-11; GAP-P12D-116/122).

The records the look register's hypothesis cards cite (R1.4) and AGON registers once the family
trades (R1.6). Each pins its source to a commit or an equation and declares EVERY departure from
it (the declared-deviations law): an undeclared departure found later is dishonest provenance.

Origin (master v2.24 §5.6): every member is a literature rule SELECTED by an LLM (the R1 plan), so
it counts as LLM-selected: it may be killed on any history, and credited only forward.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.signals.provenance import ProvenanceRecord, ProvenanceStore
from core.signals.rules import SOURCES

REGISTERED = datetime(2026, 10, 1, tzinfo=timezone.utc)

_SHARED = (
    "reads the instrument's multiplicative EXCESS-return price (spot compounded with the dated "
    "carry differential), not an additive back-adjusted futures price: spot FX and CFDs have no "
    "futures roll (GAP-P12D-71)",
    "decides on each weekday's 17:00 New York close and fills on a pre-registered per-symbol "
    "execution clock after it (GAP-P12D-95); on the daily lab the fill is at the decision close",
    "sizing: the book's declared capital and vol target (R1-D14), class-equal then equal instrument "
    "weights, IDM = sqrt(N_eff) capped at 2.5, all fixed before any real-data look",
    "positions round TOWARD ZERO to the venue's lot step (master §5 C8 v2.22), not to the nearest "
    "contract",
    "admission per instrument by master §5.6's two cost filters (turnover cost <= 0.10 SR, the "
    "stricter of Carver's two figures; swap markup <= 0.10 SR), against fixed expectations",
)

_TREND_INEFFICIENCY = ("time-series momentum: past excess returns predict future ones across asset "
                       "classes at 1-12-month horizons")
_TREND_PERSISTS = ("slow diffusion of information, hedging pressure and risk-transfer premia "
                   "(Moskowitz-Ooi-Pedersen 2012; Hurst-Ooi-Pedersen 2017, 67 markets)")
_STAGE_A = ("falsified if, on its portfolio daily series, the expanding walk-forward OOS Sharpe's "
            "one-sided HAC lower bound is <= 0, its paired excess over the passive benchmark is <= 0, "
            "or it is net <= 0 at 2x modelled cost incl. swap (ACIS-09 C-BT-11 v2 stage A); forward, "
            "if the kill bettor E2 reaches 20 (stage D)")

RECORDS: dict[str, ProvenanceRecord] = {
    "trend_d1_v1": ProvenanceRecord(
        strategy_id="trend_d1_v1",
        citation=(f"Carver, Systematic Trading (2015) and {SOURCES['carver']}: `ewmac` with "
                  "`rawdata.daily_returns_volatility` (defaults.yaml `mixed_vol_calc`), forecast "
                  "scalars 3.75/2.65/1.87 (futures_chapter15/futuresconfig.yaml), cap 20, "
                  "buffer_method forecast 0.10 traded to the edge"),
        claimed_inefficiency=_TREND_INEFFICIENCY, why_it_persists=_TREND_PERSISTS, falsifier=_STAGE_A,
        registered_at=REGISTERED,
        declared_deviations=_SHARED + (
            "three speeds at EQUAL weight with no carry rule (Carver's chapter-15 set weights "
            "0.21/0.08/0.21 and carry 0.50): at the venue, carry is a cost term, not a return source",
            "FDM fixed at 1.09 from null position correlations (0.87 adjacent, 0.58 outer), not "
            "estimated on data",
        )),
    "trend_breakout_v1": ProvenanceRecord(
        strategy_id="trend_breakout_v1",
        citation=(f"{SOURCES['carver']}: `breakout` (lookbacks 40/80/160, smooth = lookback/4), "
                  "scalars 0.7037/0.7263/0.7388 from rob_system/config.yaml `forecast_scalars`, cap 20"),
        claimed_inefficiency=_TREND_INEFFICIENCY, why_it_persists=_TREND_PERSISTS, falsifier=_STAGE_A,
        registered_at=REGISTERED,
        declared_deviations=_SHARED + (
            "the rolling window's minimum count is ceil(lookback/2) whatever the series length "
            "(Carver: min(len, ceil(lookback/2))), so a growing history and a full one agree; "
            "identical once ceil(lookback/2) closes exist",
        )),
    "trend_mop12_v1": ProvenanceRecord(
        strategy_id="trend_mop12_v1",
        citation=SOURCES["mop"] + ": the sign of the 12-month excess return, held one month, "
                 "scaled by the ex-ante volatility (centre of mass 60 days, 261 days a year)",
        claimed_inefficiency=_TREND_INEFFICIENCY, why_it_persists=_TREND_PERSISTS, falsifier=_STAGE_A,
        registered_at=REGISTERED,
        declared_deviations=_SHARED + (
            "the excess return is spot plus the dated overnight carry differential from the rates on "
            "disk, compounded daily (MOP use futures and currency-forward excess returns)",
            "decided at each month's last weekday close (a calendar fact), the 17:00 New York close",
            "the ex-ante variance is an ADJUSTED exponential average (span 121, centre of mass 60) "
            "of daily returns, not MOP's infinite-history weights; the position is scaled to the "
            "book's vol target, not MOP's 40% per instrument",
            "a 12-month excess return of exactly zero is flat (MOP leave the sign undefined)",
        )),
}


def register_family(store: ProvenanceStore) -> list[str]:
    """Register whichever TREND records are missing; idempotent by boot, like the canon."""
    added = []
    for sid, record in RECORDS.items():
        if not store.is_registered(sid):
            store.register(record)
            added.append(sid)
    return added

