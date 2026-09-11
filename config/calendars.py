"""Market calendars and session boundaries, declared in LOCAL time (GAP-P12D-10).

Every market time is a wall time in its centre's own zone (London opens 08:00
London time all year); `core/data/fx_clock.py` resolves it to UTC per date. A
fixed-UTC declaration is an hour wrong for half of every year, so the schema has
no UTC field to put one in. Split out of `config/schemas.py` (legibility budget,
GAP-P12M-01); `schemas.py` re-exports these names.
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The zones fx_clock models (parity-tested against its rule table).
Zone = Literal["UTC", "Asia/Tokyo", "Europe/London", "America/New_York", "America/Chicago"]

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def parse_hhmm(value: str, field: str) -> time:
    if not isinstance(value, str) or not _HHMM.match(value):
        raise ValueError(f"{field}: {value!r} is not HH:MM local time")
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


class ZonedTime(_Strict):
    """A daily wall-clock instant in one market centre, e.g. 17:00 New York."""
    zone: Zone
    at: str

    @model_validator(mode="after")
    def _time(self) -> "ZonedTime":
        parse_hhmm(self.at, f"{self.zone} time")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.zone, self.at)


class Session(_Strict):
    """open→close in one centre's local time; or, with `close_zone`, from the open in
    `zone` to the next `close` in another centre (e.g. the New York close → the Tokyo
    open), which may cross midnight."""
    zone: Zone
    open: str
    close: str
    close_zone: Zone | None = None

    @model_validator(mode="after")
    def _times(self) -> "Session":
        o, c = parse_hhmm(self.open, "open"), parse_hhmm(self.close, "close")
        if self.close_zone is None and o >= c:
            raise ValueError("session open must precede close in local time "
                             "(declare close_zone for a session that ends in another centre)")
        return self


class FxCalendar(_Strict):
    """A 24/5 over-the-counter market (spot FX, spot metals): open from the Sunday
    `week_open` to the Friday `week_close`, tagged by the centre sessions, closed
    inside an optional `daily_break` (spot gold's daily hour — master §3.7)."""
    type: Literal["fx"]
    sessions: dict[str, Session] = Field(min_length=1)
    week_close: ZonedTime   # Friday, local
    week_open: ZonedTime    # Sunday, local
    daily_break: Session | None = None


class ExchangeCalendar(_Strict):
    type: Literal["exchange"]
    zone: Zone
    open: str
    close: str
    days: list[int] = Field(min_length=1)  # ISO weekday numbers 1=Mon .. 7=Sun, local
    holidays: list[date] = Field(default_factory=list)
    half_days: dict[date, str] = Field(default_factory=dict)  # date -> early close, local

    @model_validator(mode="after")
    def _times(self) -> "ExchangeCalendar":
        o, c = parse_hhmm(self.open, "open"), parse_hhmm(self.close, "close")
        if o >= c:
            raise ValueError("open must precede close (no wrap)")
        if any(d < 1 or d > 7 for d in self.days):
            raise ValueError("days: ISO weekday 1..7")
        for d, early in self.half_days.items():
            if not (o < parse_hhmm(early, f"half_days[{d}]") < c):
                raise ValueError(f"half_days[{d}]: early close must fall inside the session")
        return self


def check_boundaries(boundaries: list[ZonedTime],
                     calendars: dict[str, FxCalendar | ExchangeCalendar]) -> None:
    """C1 single-source cross-check, compared as (zone, local time) pairs.
    GAP-0025: every staging boundary is a declared fx session open or the week
    close/rollover. GAP-0033 (bidirectional): every fx session open is itself a
    boundary, so a session-name transition never happens off a staging boundary."""
    keys = [b.key for b in boundaries]
    if len(set(keys)) != len(keys):
        raise ValueError("session_boundaries: duplicate boundary")
    edges: set[tuple[str, str]] = set()
    for cal_name, cal in calendars.items():
        if not isinstance(cal, FxCalendar):
            continue
        edges.add(cal.week_close.key)
        for name, s in cal.sessions.items():
            edges.add((s.zone, s.open))
            if (s.zone, s.open) not in keys:
                raise ValueError(
                    f"fx calendar {cal_name!r} session {name!r} opens at {s.open} {s.zone}, "
                    "which is not in session_boundaries (C1 bidirectional, GAP-0033)")
    for zone, at in keys:
        if (zone, at) not in edges:
            raise ValueError(f"session boundary {at} {zone} matches no fx session open or "
                             "week close (C1 single-source cross-check, GAP-0025)")
