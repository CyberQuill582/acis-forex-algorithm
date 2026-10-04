"""The tournament's strategy registry (TOURNAMENT, 2026-10-04): the forward-eligible survivors, each a
frozen declaration plus a pure book from the input store to its forward daily net returns.

Mental model:
  * An entry IS its registered family-version: the look register's family and variant hash (rebuilt
    here from the kill script's own formula and origin, and pinned by test to the register's), its
    kill-only looks, its instruments, clock, origin, C8 cost map and the book's declared parameters.
    `spec_hash` covers all of them, and the daily job refuses to extend an entry that no longer matches.
  * Stage D's units are declared before the first forward day: sigma* is D1's 20% vol target / sqrt(252)
    (RSIM sizes to it); REBAL and GOTOBI have no target, so theirs is the realised daily sd of their
    development look's stored vector. sharpe_dev is that look's net annual Sharpe (E2's claim).
  * forward_start is the first trading day after registration; `first_exposure_utc` (the first instant
    the book could hold risk) must come after the entry is written, and the record refuses it otherwise.
  * Adding a survivor is one `Strategy(...)` in REGISTRY built on a `tournament_books` shape. FXHEDGE was
    killed and AUCTION not forwarded (GAP-P12D-158), so they are absent.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from core.signals import rules
from tests.backtest.look_claims import Claim, Origin, canonical_hash, cost_map_hash
from tests.backtest.look_declarations import Declaration
from tests.backtest.tournament_books import (close_book, gotobi_tue_fri, kill_script, rebal_position, rsim_book,
                                             window_book)
from tests.backtest.tournament_rule import PARAMS

FX13 = ("AUD_JPY", "AUD_USD", "CHF_JPY", "EUR_AUD", "EUR_CHF", "EUR_GBP", "EUR_JPY", "EUR_USD", "GBP_JPY",
        "GBP_USD", "USD_CAD", "USD_CHF", "USD_JPY")       # sorted(config targets.universe), pinned by test
ALPHA = PARAMS["alpha_total"] / PARAMS["capacity"]


@dataclass(frozen=True)
class Strategy:
    sid: str
    family: str
    universe_id: str
    kill_looks: tuple[str, ...]
    clock: str
    instruments: tuple[str, ...]
    formula: str
    origin: Origin
    forward_start: date
    first_exposure: tuple[time, str]          # local wall time and zone on the forward start
    sigma_daily: float
    sharpe_dev: float
    cost_map: str                             # the C8 cost map its looks registered (look_claims.cost_map_hash)
    params: dict = field(repr=False)
    book: Callable = field(repr=False, compare=False)

    @property
    def variant_hash(self) -> str:
        return Claim(family=self.family, variant="fixed", universe_id=self.universe_id, origin=self.origin,
                     simulator="rsim" if self.clock == "rsim_17ny" else "event", recon_commit="-",
                     declared_space={"grid": {}, "formula": self.formula, "instruments": list(self.instruments)},
                     declaration=Declaration("fixed", 1, "PASSIVE_LONG")).variant_hash

    def first_exposure_utc(self) -> datetime:
        t, zone = self.first_exposure
        return datetime.combine(self.forward_start, t, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)

    def spec(self) -> dict:
        return {"strategy": self.sid, "family": self.family, "variant_hash": self.variant_hash,
                "kill_looks": list(self.kill_looks), "clock": self.clock, "instruments": list(self.instruments),
                "formula": self.formula, "origin": asdict(self.origin),
                "certifying_boundary": (lambda b: b.isoformat() if b else None)(self.origin.boundary()),
                "forward_start": self.forward_start.isoformat(),
                "first_exposure_utc": self.first_exposure_utc().isoformat(timespec="seconds"),
                "sigma_daily": self.sigma_daily, "sharpe_dev": self.sharpe_dev, "cost_map_hash": self.cost_map,
                "params": self.params}

    def entry(self, alpha: float = ALPHA) -> dict:
        spec = self.spec()
        return {"kind": "entry", **spec, "alpha": alpha, "spec_hash": canonical_hash(spec)}

    def drift(self, cfg, entry: dict) -> str | None:
        """Why this strategy may not extend `entry` (its registered line), or None."""
        if self.entry(float(entry["alpha"]))["spec_hash"] != entry["spec_hash"]:
            return "RULE DRIFT: the registry no longer matches the registered entry"
        if cost_map_hash(cfg, self.instruments, 1.0, 0.0) != self.cost_map:
            return "COST DRIFT: the config's C8 costs are not the ones the entry registered"
        return None


def _d1() -> Strategy:
    k = kill_script("r1_d1_kill_test")
    return Strategy("D1-FX13", k.FAMILY, "R6-4-FX13", ("000001", "000027"), "rsim_17ny", FX13, k.FORMULA, k.ORIGIN,
                    date(2026, 10, 5), (time(17, 0), "America/New_York"), 0.20 / math.sqrt(252), 0.1650,
                    "1f3bded81e3f3a931d4c9df48ae81e00aac53c9cb1e3c9b39fa6fb7365a8231e",
                    {"market_from": "2012-01-02", "capital": 1_000_000.0, "vol_target": 0.20, "world": "swap_free",
                     "settled": "every instrument's next slot fill in the data", "weights": "class_equal",
                     "idm": 1.5, "buffer": 0.10},
                    rsim_book(rules.d1, FX13, date(2012, 1, 2), idm=1.5, buffer=0.10))


def _rebal() -> Strategy:
    k = kill_script("r1_rebal_kill_test")
    return Strategy("REBAL-v1a", "rebal_v1a_us500", "R1-REBAL-US500", ("000007", "000025"), "us_cash_close",
                    ("US500",), k.VERSIONS["rebal_v1a_us500"], k.ORIGIN, date(2026, 10, 5),
                    (time(16, 0), "America/New_York"), 0.0045781, 0.4951,
                    "849912618bde4e4441fdb1e43263cd1d0bc363720236e3c6dc825a6a334ec9ca",
                    {"signal_from": k.SIGNAL_FROM.isoformat(), "calendar_term": "NYSE published sessions"},
                    close_book("US500", rebal_position, k.SIGNAL_FROM))


def _gotobi() -> Strategy:
    k = kill_script("r1_gotobi_kill_test")
    return Strategy("GOTOBI-v1a", "gotobi_v1a_h1_usdjpy", "R1-GOTOBI-USDJPY", ("000015", "000021"), "jst_window",
                    (k.NAME,), k.CORE, k.ORIGIN, date(2026, 10, 6), (time(3, 0), k.ZONE), 0.00111398, 1.8058,
                    "d76029bb37c937b2c2e7104c195e68360eb47cee9eadba923c07530d836cef00",
                    {"legs": [[leg.entry, leg.exit, leg.side] for leg in (k.H1,)],
                     "times": {lbl: t.strftime("%H:%M") for lbl, t in k.TIMES.items()}, "zone": k.ZONE,
                     "days": "gotobi '30' rule, Tuesday-Friday JST bank days"},
                    window_book(k.NAME, (k.H1,), k.TIMES, k.ZONE, gotobi_tue_fri))


REGISTRY: tuple[Strategy, ...] = (_d1(), _rebal(), _gotobi())
BY_ID = {s.sid: s for s in REGISTRY}
