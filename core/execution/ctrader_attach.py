"""The cTrader attach (ACIS-13 §7.1 A1–A11, §5.3): from a human-committed binding to a verified face,
or a named refusal. Every step is logged `ATTACH_STEP`; nothing downstream starts before A11.

Invariants:
  * The rulebook is loaded first and must name this platform (A1); the account id is config, and 0
    ("not committed") is refused. The grant, the environment and `isLive` are checked by the session
    (A2–A3); here the trader must have full access, no limited-risk mode and a USD deposit (A4).
  * Every enabled instrument maps to exactly one venue symbol whose contract agrees with
    instruments.yaml (A5); the descriptor is derived from venue data, never declared by hand.
  * Flat-or-decide (A6, GAP-0018): a first attach onto an account holding ANY position or pending
    order halts for a human. A restart (A7) resolves its own orders first, then ingests missed deals.
  * The attach ALWAYS starts in paper (A11). The report says whether the account may take practice
    orders: a demo environment, `isLive` false, AND a rulebook declaring `account_class: practice`
    (master v2.23) — the one input `acis_set_mode(practice)` reads.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Mapping

from config.account_doctrine import rulebook_hash
from core.data.ctrader.link import AuthRefused
from core.data.ctrader.schema import PT, AccessRights, HOSTS, enum_value, field
from core.execution.ctrader_symbols import (AttachFatal, VenueSymbolSpec, cross_check, descriptor,
                                            match_symbols, spec_from)


@dataclass(frozen=True)
class AttachReport:
    venue: str
    environment: str
    host: str
    ctid_trader_account_id: int
    verdict: str                                # ATTACHED | HALTED_OPEN_POSITIONS | FATAL
    reason: str
    attached_at: str
    rulebook_key: str
    rulebook_hash: str
    account_class: str | None
    is_live: bool | None = None
    trader_login: int | None = None
    broker_name: str | None = None
    account_type: str | None = None
    deposit_asset: str | None = None
    money_digits: int | None = None
    balance_observed: str | None = None
    symbols: tuple[str, ...] = ()
    open_positions: int = 0
    pending_orders: int = 0

    @property
    def practice_eligible(self) -> bool:
        return (self.verdict == "ATTACHED" and self.environment == "demo"
                and self.is_live is False and self.account_class == "practice")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass(frozen=True)
class Attached:
    report: AttachReport
    specs: Mapping[str, VenueSymbolSpec]
    descriptor: object
    feed_symbols: Mapping[int, tuple[str, int]]         # symbolId → (instrument, digits)


CONNECT_OVERHEAD = 8     # app auth, grant, account auth, trader, assets, symbols ×2, reconcile (§6.5)
ROUND_TRIP = 4           # measured: open 1; close = reconcile ×2 + close 1 (v1.2, GAP-P12D-132 D1)
HISTORY_PER_INSTRUMENT = 2   # the target path's H1 append at each decision + a restart's gap fill (ACIS-04 v1.6 §4b)


def feasible(cfg, execution_cap: int, targeted: int = 0) -> str | None:
    """A9 (§6.5): the day's projected requests fit in budget − reserve, and the orchestrator's own
    cap (ACIS-06 C-EXE-8) sits inside it, so it refuses an open before the adapter must. `targeted`
    instruments each fetch their daily history (the first boot's deeper seed is a one-time query,
    refused inside the reserve, so it can delay a forecast, never an exit)."""
    projected = (CONNECT_OVERHEAD * (1 + cfg.backoff.max_consecutive) + 86400 / cfg.equity_poll_s * 2
                 + 86400 / cfg.reconcile_interval_s + ROUND_TRIP * cfg.max_orders_per_day
                 + HISTORY_PER_INSTRUMENT * targeted)
    room = cfg.daily_request_budget - cfg.close_reserve
    if projected > room:
        return f"projected {projected:.0f} requests a day > {room} (budget − reserve)"
    if execution_cap > room:
        return f"execution.max_venue_requests_per_day {execution_cap} > {room}"
    return None


async def attach(cfg, *, rulebook_key: str, rulebook, instruments: Mapping, session, store,
                 logger, now: datetime, execution_cap: int, targeted: int = 0) -> Attached:
    """A1–A6 and A11 (A7's restart sync belongs to the face, A8 to the feed's first live tick)."""
    base = dict(venue="ctrader", environment=cfg.environment, host=HOSTS[cfg.environment],
                ctid_trader_account_id=cfg.ctid_trader_account_id, attached_at=now.isoformat(),
                rulebook_key=rulebook_key, rulebook_hash=rulebook_hash(rulebook),
                account_class=rulebook.account_class)
    facts: dict = {}

    def refuse(verdict: str, reason: str, *, halted: bool = False) -> Attached:
        report = AttachReport(verdict="HALTED_OPEN_POSITIONS" if halted else "FATAL",
                              reason=f"{verdict}: {reason}", **base, **facts)
        logger.event(verdict, reason=reason)
        return Attached(report, {}, None, {})

    def step(n: int, result: str) -> None:
        logger.event("ATTACH_STEP", n=n, result=result)

    if rulebook.platform != "ctrader":
        return refuse("ATTACH_PLATFORM_MISMATCH", f"rulebook platform is {rulebook.platform!r}")
    if cfg.ctid_trader_account_id == 0:
        return refuse("ATTACH_UNBOUND", "a human commits venue.ctid_trader_account_id")
    infeasible = feasible(cfg, execution_cap, targeted)
    if infeasible:                                       # A9, checked before the venue is contacted
        return refuse("ATTACH_BUDGET_INFEASIBLE", infeasible)
    step(1, "rulebook loaded")
    try:
        grant = await session.start()
    except AuthRefused as exc:
        return refuse(exc.verdict, str(exc))
    facts.update(is_live=grant.is_live, trader_login=grant.trader_login, broker_name=grant.broker)
    step(3, "authorised")

    trader = (await session.request(PT.TRADER_REQ, {}, req_class="query")).payload["trader"]
    assets = {int(a["assetId"]): str(a["name"]) for a in
              (await session.request(PT.ASSET_LIST_REQ, {}, req_class="query")).payload.get("asset", ())}
    facts.update(account_type=str(field(trader, "accountType")),
                 deposit_asset=assets.get(int(trader["depositAssetId"])),
                 money_digits=int(trader.get("moneyDigits", 2)),
                 balance_observed=str(int(trader["balance"])))
    if enum_value(AccessRights, field(trader, "accessRights")) is not AccessRights.FULL_ACCESS:
        return refuse("ATTACH_ACCESS", "the account is not full-access")
    if field(trader, "isLimitedRisk"):
        return refuse("ATTACH_LIMITED_RISK", "limited-risk accounts need guaranteed stops")
    if facts["deposit_asset"] != "USD":
        return refuse("ATTACH_DEPOSIT", f"deposit asset {facts['deposit_asset']!r}, not USD")
    step(4, "trader ok")

    enabled = {k for k, meta in instruments.items() if meta.enabled}
    if enabled - set(cfg.symbol_names):
        return refuse("ATTACH_SYMBOL", f"unmapped: {sorted(enabled - set(cfg.symbol_names))}")
    light = list((await session.request(PT.SYMBOLS_LIST_REQ, {}, req_class="query")).payload.get("symbol", ()))
    try:
        ids = match_symbols(light, {k: cfg.symbol_names[k] for k in sorted(enabled)})
        full = (await session.request(PT.SYMBOL_BY_ID_REQ, {"symbolId": sorted(ids.values())},
                                      req_class="query")).payload.get("symbol", ())
        by_id = {int(sym["symbolId"]): sym for sym in full}
        quote = {int(sym["symbolId"]): assets.get(int(sym.get("quoteAssetId", -1))) for sym in light}
        specs = {k: spec_from(k, cfg.symbol_names[k], by_id[i]) for k, i in ids.items()}
        for k, spec in specs.items():
            cross_check(spec, instruments[k], quote.get(spec.symbol_id), logger)
        desc = descriptor(list(specs.values()), field(trader, "accountType"),
                          frozenset(instruments[k].asset_class for k in specs))
    except AttachFatal as exc:
        return refuse(exc.verdict, exc.reason)
    facts["symbols"] = tuple(sorted(specs))
    step(5, "symbols verified")

    if store.binding() is None:                          # A6: a first attach must find it flat
        res = await session.request(PT.RECONCILE_REQ, {"returnProtectionOrders": True},
                                    req_class="query")
        facts.update(open_positions=len(res.payload.get("position", ())),
                     pending_orders=len(res.payload.get("order", ())))
        if facts["open_positions"] or facts["pending_orders"]:
            return refuse("ATTACH_HALTED_OPEN_POSITIONS", "flatten on the platform or manage it "
                          "until flat; ACIS never trades alongside what it did not open", halted=True)
        store.bind(now, facts["balance_observed"], int(now.timestamp() * 1000), "{}")
    step(6, "flat or restarting")

    report = AttachReport(verdict="ATTACHED", reason="", **base, **facts)
    store.save_report(report.to_json())
    logger.event("ATTACH_VERIFIED", practice_eligible=report.practice_eligible,
                 symbols=list(report.symbols))
    return Attached(report, specs, desc, {s.symbol_id: (k, s.digits) for k, s in specs.items()})
