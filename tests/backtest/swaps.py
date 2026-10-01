"""The venue's swap table as C8 data (GAP-P12D-93/94; master §5 C8 v2.22; RSIM's "markup" world).

Mental model:
  * A table is a DATED snapshot of the venue's published per-symbol swaps, never edited: a
    re-fetch is a new dated file (markups drift). FTMO publishes points per lot per night for
    the long and the short side, positive = credit; a point is 10^-digits of the price.
  * The fair rate differential cancels in the sum of the two sides: long + short = −(markup_long
    + markup_short). Assuming the venue's markup is the same on both sides (DECLARED), the
    markup is m = −(long + short)/2 points per unit per night, rate-free, so it applies to any
    history while the fair part comes from the dated rates (RSIM's `carry`).
  * As RSIM's annual % of value: m · point · 365 / price · 100, at a price the caller states.
  * The charge calendar is per asset class: the weekday whose rollover is charged three times,
    with its source. A class with no verified source is REFUSED, never guessed: FTMO's blog
    states Wednesday→Thursday for forex (EURUSD example); its CFD classes are unverified here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent / "swap_tables"
FTMO_2026_09_25 = HERE / "ftmo_2026-09-25.json"
FTMO_CALENDAR = {   # asset class -> (weekday charged x3, Mon=0, its source)
    "Forex": (2, "ftmo.com/en/blog/what-is-a-swap-and-for-whom-is-it-important (read 2026-10-01): "
                 "the triple swap is charged overnight from Wednesday to Thursday"),
}


class UnverifiedCalendar(Exception):
    """An asset class whose triple-swap day no cited source states."""


@dataclass(frozen=True)
class SwapEntry:
    code: str
    asset_class: str
    swap_long: float          # points per unit per night (per lot / contract size is the same number)
    swap_short: float
    digits: int

    @property
    def point(self) -> float:
        return 10.0 ** -self.digits

    @property
    def markup_points(self) -> float:
        """The symmetric-markup reading: −(long + short)/2 points a night (declared)."""
        return -(self.swap_long + self.swap_short) / 2.0

    def markup_pct(self, price: float) -> float:
        """The markup as an annual % of the position's value at `price`."""
        if not price > 0:
            raise ValueError(f"price must be > 0, got {price}")
        return self.markup_points * self.point * 365.0 / price * 100.0


@dataclass(frozen=True)
class SwapTable:
    venue: str
    fetched: date
    entries: dict[str, SwapEntry]
    calendar: dict[str, tuple[int, str]]

    def entry(self, name: str) -> SwapEntry:
        return self.entries[name]

    def nights(self, name: str, rollover: date) -> int:
        """Days of swap the rollover on business day `rollover` charges for `name`."""
        cls = self.entries[name].asset_class
        if cls not in self.calendar:
            raise UnverifiedCalendar(f"{self.venue} {cls}: no cited source states its triple-swap day")
        if rollover.weekday() >= 5:
            raise ValueError(f"{rollover} is a weekend day: no rollover")
        return 3 if rollover.weekday() == self.calendar[cls][0] else 1


def acis_name(code: str) -> str:
    """FTMO 'EUR/USD' -> 'EUR_USD'; 'US500.cash' -> 'US500'."""
    return code.replace("/", "_").removesuffix(".cash")


def load_ftmo(path: Path = FTMO_2026_09_25) -> SwapTable:
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = {}
    for s in doc["data"]["symbols"]:
        if s["swapType"] != "points":
            continue                                   # crypto's percentage swaps: out of scope
        entries[acis_name(s["code"])] = SwapEntry(code=s["code"], asset_class=s["assetClass"],
                                                  swap_long=float(s["swapLong"]),
                                                  swap_short=float(s["swapShort"]), digits=int(s["digits"]))
    fetched = date.fromisoformat(path.stem.rsplit("_", 1)[-1])
    return SwapTable(venue="ftmo", fetched=fetched, entries=entries, calendar=dict(FTMO_CALENDAR))
