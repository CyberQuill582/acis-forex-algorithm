"""The venue's hourly trendbars (ACIS-04 v1.6 §4b seeding; ACIS-13 §3.1 `ProtoOAGetTrendbarsReq`).

The target-position path's daily history comes from the venue's own bars, so the engine decides on
the prices it trades. One H1 request per window; nothing here is held between calls.

Mental model:
  * A bar is the venue's H1 trendbar as the engine's `Bar` (duration 3,600 s, spread 0: a trendbar
    carries none): `low` and the deltas are in 1/100,000 of a price unit (F-13), `open/high/close =
    low + delta`, rounded to the symbol's digits. Its hour is `utcTimestampInMinutes` floored to the
    hour (the proto calls it "the timestamp of the open tick"); it covers [hour, hour + 1 h). cTrader bars are built from BID prices: a declared deviation from RSIM's
    Dukascopy MID closes (`OQ_TRENDBARS_BID`, verified at the first seeding).
  * A fetch walks BACKWARD from `end` in windows of at most `window`: the venue caps a response
    (14,000 bars, Spotware on its forum) and limits each period's range (undocumented). A response
    with `hasMore` is truncated back from `toTimestamp`, so the walk continues below its earliest
    bar. A venue error other than rate limiting halves the window, down to `MIN_WINDOW`, then raises.
  * Only COMPLETE bars inside [start, end) are kept (a bar ending after `end` is still forming), one
    per hour, sorted. Every request is a metered `query`: refused inside the close reserve, so
    history can never spend the exits' budget (C-VEN-4), and paced as history (pacing.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.data.bars import Bar
from core.data.ctrader.schema import PRICE_SCALE, PT, TrendbarPeriod, enum_value, field
from core.data.ctrader.wire import VenueError
from core.data.errors import DataQualityError

HOUR = timedelta(hours=1)
WINDOW = timedelta(days=365)        # ~6,240 FX hours, well under the 14,000-bar cap
MIN_WINDOW = timedelta(days=7)
RATE_LIMITED = frozenset({"REQUEST_FREQUENCY_EXCEEDED", "BLOCKED_PAYLOAD_TYPE"})
OQ_TRENDBARS_BID = "cTrader trendbars are bid bars (chart convention); confirm against live bids"


def end_of(bar: Bar) -> datetime:
    return bar.ts_open + timedelta(seconds=bar.duration_s)


def decode_bar(raw, digits: int) -> Bar:
    """One `ProtoOATrendbar` of an H1 response."""
    if "period" in raw and enum_value(TrendbarPeriod, raw["period"]) is not TrendbarPeriod.H1:
        raise DataQualityError("period", raw["period"], "an H1 response carries H1 bars")
    if "low" not in raw or "utcTimestampInMinutes" not in raw:
        raise DataQualityError("trendbar", sorted(raw), "a bar needs its low and its time")
    low = int(raw["low"])
    price = lambda delta: round((low + int(raw.get(delta, 0))) / PRICE_SCALE, digits)   # noqa: E731
    minutes = int(raw["utcTimestampInMinutes"])
    start = datetime.fromtimestamp(minutes // 60 * 3600, timezone.utc)
    return Bar(ts_open=start, open=price("deltaOpen"), high=price("deltaHigh"),
               low=round(low / PRICE_SCALE, digits), close=price("deltaClose"), spread=0.0, duration_s=3600)


def _ms(t: datetime) -> int:
    return int(t.timestamp() * 1000)


async def hourly_bars(session, symbol_id: int, digits: int, start: datetime, end: datetime, *,
                      logger, window: timedelta = WINDOW) -> list[Bar]:
    """The complete H1 bars in [start, end), oldest first (see the mental model)."""
    if start.tzinfo is None or end.tzinfo is None:
        raise DataQualityError("start/end", (start, end), "must be tz-aware")
    out: dict[datetime, Bar] = {}
    hi, span = end, window
    while hi > start:
        lo = max(start, hi - span)
        try:
            res = await session.request(PT.GET_TRENDBARS_REQ, {
                "fromTimestamp": _ms(lo), "toTimestamp": _ms(hi), "period": int(TrendbarPeriod.H1),
                "symbolId": symbol_id}, req_class="query")
        except VenueError as err:
            if err.code in RATE_LIMITED or span / 2 < MIN_WINDOW:
                raise
            span /= 2
            logger.event("TRENDBARS_WINDOW_HALVED", symbol_id=symbol_id, code=err.code,
                         window_days=span.total_seconds() / 86400)
            continue
        bars = [decode_bar(b, digits) for b in res.payload.get("trendbar", ())]
        for bar in bars:
            if start <= bar.ts_open and end_of(bar) <= end:
                out[bar.ts_open] = bar
        earliest = min((b.ts_open for b in bars), default=lo)
        hi = earliest if field(res.payload, "hasMore") and lo < earliest < hi else lo   # always progresses
    logger.event("TRENDBARS_FETCHED", symbol_id=symbol_id, bars=len(out),
                 start=start.isoformat(), end=end.isoformat())
    return [out[k] for k in sorted(out)]
