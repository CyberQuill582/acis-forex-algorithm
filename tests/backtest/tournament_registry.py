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
  * POOLS (GAP-P12D-161, owner ruling 2026-10-06): the equal-risk combined book is one more entry over
    registered books, no look of its own (so it is outside the register's variant-hash pin), its weights
    the development looks' daily sd, declared before its first exposure; a component change is RULE DRIFT.
  * Adding a survivor is one `Strategy(...)` built on a `tournament_books` shape: FACTORY's three (each
    present once its kill script is on the branch) and, the same way, the owner's `hypotheses/` rules with
    `Origin("human")` (no boundary). FXHEDGE was killed and AUCTION not forwarded, so they are absent.
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
from tests.backtest.tournament_books import (close_book, d1_forecast, gotobi_tue_fri, kill_script, pool_book,
                                             rebal_position, rsim_book, window_book)
import tests.backtest.tournament_factory as tf
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
    history_worst_sigmas: float | None = None   # P-5: a NEW entry declares its worst history day in sigma*

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
                "params": self.params,
                **({} if self.history_worst_sigmas is None else {"history_worst_sigmas": self.history_worst_sigmas})}

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
                    rsim_book(d1_forecast(rules.d1), FX13, date(2012, 1, 2), idm=1.5, buffer=0.10))


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


FACTORY_START = date(2026, 10, 6)                  # FACTORY's survivors: the first trading day after their review


def _factory() -> tuple[Strategy, ...]:
    """FACTORY's three survivors (looks 000045/000049/000053, all kill-only and weak), each present once its
    kill script is on the branch; caveats from its report are part of the hashed declaration."""
    out, ny = [], "America/New_York"
    k = kill_script("r1_halloween_kill_test")
    if k is not None:
        out.append(Strategy("HALLOWEEN-v1", k.FAMILY, k.UNIVERSE, ("000053",), "home_cash_closes", k.NAMES, k.FORMULA,
                            k.ORIGIN, FACTORY_START, (time(16, 0), "Australia/Sydney"), 0.04144645, 0.2579,
                            "28bc253267bc23585203796fe4ef070ff374fe2dd3ac194627110396b968e6b8",
                            {"market_from": k.START.isoformat(), "next_session": "the next weekday",
                             "caveats": "0.00 without its 10 best days; 2023 alone 2.20; two switches a year, so "
                                        "about two seasons of evidence a year; rho +0.15 with REBAL"},
                            tf.halloween_book(k.NAMES, k.START)))
    k = kill_script("r1_hedgep_kill_test")
    if k is not None:
        out.append(Strategy("HEDGEP-gold", k.FAMILY, k.UNIVERSE, ("000045",), "rsim_17ny", k.NAMES, k.FORMULA, k.ORIGIN,
                            FACTORY_START, (time(17, 0), ny), 0.20 / math.sqrt(252), 0.1414,
                            "b5522ca5a549f5d4a20496e746830c31795e1425b5b2ac6cd31ac62e741e7dde",
                            {"market_from": k.START.isoformat(), "capital": 1_000_000.0, "vol_target": 0.20,
                             "idm": 1.0, "buffer": 0.10, "world": "swap_free", "report": "CFTC legacy COMEX gold",
                             "caveats": "seen years 2012-2014 -0.32, post-sample +0.29; -0.17 without its 10 best "
                                        "days; one market; passive long gold earned 0.19"},
                            rsim_book(tf.hedgep_forecast, k.NAMES, k.START, idm=1.0, buffer=0.10,
                                      input_end=tf.hedgep_end)))
    k = kill_script("r1_fxvalue_kill_test")
    if k is not None:
        out.append(Strategy("FXVALUE-ppp", k.FAMILY, k.UNIVERSE, ("000049",), "rsim_17ny", k.NAMES, k.FORMULA, k.ORIGIN,
                            FACTORY_START, (time(17, 0), ny), 0.20 / math.sqrt(252), 0.0657,
                            "aa7b5ba758725efd76724e1c78a0a99996e1c3a72c85cb3b08be235ef8919091",
                            {"market_from": k.START.isoformat(), "capital": 1_000_000.0, "vol_target": 0.20,
                             "idm": 1.0, "buffer": 0.10, "world": "swap_free", "first_rank_month": list(k.FIRST),
                             "caveats": "flat (0.07, t 0.21); clean segment 2021-2023 -0.25; -0.18 without its 10 "
                                        "best days; its one merit is rho -0.28 with D1-FX13; the lead may decline it"},
                            rsim_book(tf.fxvalue_forecast, k.NAMES, k.START, idm=1.0, buffer=0.10,
                                      input_end=tf.fxvalue_end)))
    return tuple(out)


POOL_START = date(2026, 10, 7)                     # the first trading day after the owner's 2026-10-06 ruling
POOL_SD = {"D1-FX13": 0.0104699, "REBAL-v1a": 0.0047064, "GOTOBI-v1a": 0.0011293, "HALLOWEEN-v1": 0.0420577,
           "HEDGEP-gold": 0.0112712}                # each development vector's daily sd, NY weekdays 2012-12-31..2023-12-29


def _pool(registry: tuple[Strategy, ...]) -> Strategy:
    """POOL-5: D1 + REBAL + GOTOBI + HALLOWEEN + HEDGEP at equal risk (FXVALUE left out by the owner's ruling).
    Its development numbers are the same combination of those five looks' vectors: a selected set's history,
    so biased upward; all three components graded on 2024-25 earned <= 0 there."""
    parts = tuple(s for s in registry if s.sid in POOL_SD)
    unit = 0.20 / math.sqrt(252)
    names = tuple(sorted({n for s in parts for n in s.instruments}))
    return Strategy("POOL-5", "pool_eqrisk_v1", "POOL-5", tuple(sorted({k for s in parts for k in s.kill_looks})),
                    "pool_daily", names, "mean_i(net_i * unit / sd_i), unit = 0.20/sqrt(252); flat where a component "
                    "has no row; settled through the earliest component horizon",
                    Origin("llm", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                           exposure="repository"),
                    POOL_START, (time(3, 0), "Asia/Tokyo"), 0.0056874, 1.2917, POOL_COST_MAP,
                    {"components": {s.sid: s.entry()["spec_hash"] for s in parts}, "sd": POOL_SD, "unit": unit,
                     "weights": "equal risk, fixed; never re-composed (a new composition is a new entry)",
                     "caveats": "history Sharpe 1.29 is the five selected survivors' 2013-2023; GOTOBI dominates it "
                                "and faded; D1, REBAL and GOTOBI each earned <= 0 on the 2024-25 holdout"},
                    pool_book(tuple((s.book, unit / POOL_SD[s.sid]) for s in parts)), history_worst_sigmas=8.43)


POOL_COST_MAP = "e403f60154c2dedcb5791cfd1b417571281b29e6fcad0d7aba650cf828ead9f8"   # the union's C8 costs today
REGISTRY: tuple[Strategy, ...] = (_d1(), _rebal(), _gotobi(), *_factory())
POOLS: tuple[Strategy, ...] = (_pool(REGISTRY),)
ENTRIES: tuple[Strategy, ...] = REGISTRY + POOLS
BY_ID = {s.sid: s for s in ENTRIES}
