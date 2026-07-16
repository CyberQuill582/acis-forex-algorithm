"""Event intake, blackouts, Tier-G (ACIS-10 §14 test contract)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from config.schemas import EventSourcesConfig
from core.data.events import CalendarEvent, EventService, Headline

T0 = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)  # Tuesday


def nfp(source: str, when: datetime) -> CalendarEvent:
    return CalendarEvent(name="NFP", tier=1, event_time=when, currency="USD", source=source)


@pytest.fixture()
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "system_log.jsonl"


def logged_events(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").strip().splitlines()]


def make_service(acis_config, log_path: Path, account: str) -> EventService:
    from core.data.jsonl_logging import JsonlEventLogger

    return EventService(
        events_cfg=acis_config.event_sources,
        rulebook=acis_config.platform_rules.accounts[account],
        instruments=acis_config.instruments.enabled,
        macro_lookahead_min=acis_config.system.data.macro_lookahead_min,
        calendar_stale_threshold_s=acis_config.system.data.calendar_stale_threshold_s,
        logger=JsonlEventLogger(log_path, layer="data", session_id="etest"),
    )


class TestBlackouts:
    def test_windows_inclusive_at_both_edges(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")  # +/-120s windows
        event_at = T0 + timedelta(minutes=30)  # calendar stays fresh across the queries
        svc.calendar.upsert(nfp("forex_factory", event_at), now=T0)
        start = event_at - timedelta(seconds=120)
        end = event_at + timedelta(seconds=120)
        assert svc.in_blackout("EUR_USD", start) is True          # fencepost: inclusive
        assert svc.in_blackout("EUR_USD", end) is True            # fencepost: inclusive
        assert svc.in_blackout("EUR_USD", start - timedelta(seconds=1)) is False
        assert svc.in_blackout("EUR_USD", end + timedelta(seconds=1)) is False

    def test_unrestricted_account_has_no_windows(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "dev_paper")
        svc.calendar.upsert(nfp("forex_factory", T0 + timedelta(hours=1)), now=T0)
        assert svc.blackout_windows() == ()
        assert svc.in_blackout("EUR_USD", T0 + timedelta(hours=1)) is False

    def test_window_follows_a_moved_event(self, acis_config, log_path) -> None:
        # Calendar-DST glitch: the event moves an hour; blackout follows the event.
        svc = make_service(acis_config, log_path, "prop_demo")
        old = T0 + timedelta(hours=1)
        new = T0 + timedelta(hours=2)
        svc.calendar.upsert(nfp("forex_factory", old), now=T0)
        # Same source re-upserts (moved event); sync time advances so the
        # calendar is fresh at both query instants.
        svc.calendar.upsert(nfp("forex_factory", new), now=T0 + timedelta(minutes=90))
        assert svc.in_blackout("EUR_USD", old) is False
        assert svc.in_blackout("EUR_USD", new) is True


class TestCalendarIntegrity:
    def test_disagreement_earlier_wins_and_logged(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")
        early = T0 + timedelta(hours=1)
        late = early + timedelta(hours=1)
        svc.calendar.upsert(nfp("forex_factory", late), now=T0)
        svc.calendar.upsert(nfp("fxstreet", early), now=T0)
        key = nfp("fxstreet", early).key
        assert svc.calendar.canonical_time(key) == early
        assert any(e["event_type"] == "CALENDAR_DISAGREEMENT" for e in logged_events(log_path))

    def test_macro_imminence_currency_scoped(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "dev_paper")
        eur_event = CalendarEvent(name="RATE_DECISION", tier=1,
                                  event_time=T0 + timedelta(minutes=20),
                                  currency="EUR", source="forex_factory")
        svc.calendar.upsert(eur_event, now=T0)
        assert svc.macro_events_imminent("EUR_USD", T0) is True
        assert svc.macro_events_imminent("USD_JPY", T0) is False       # EUR does not touch it
        assert svc.macro_events_imminent("EUR_USD", T0 - timedelta(hours=1)) is False  # >30 min out


class TestOutageFailSafe:
    def test_stale_calendar_never_degrades_to_no_event(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")
        event_at = T0 + timedelta(hours=2)
        svc.calendar.upsert(nfp("forex_factory", event_at), now=T0)
        stale_ts = T0 + timedelta(hours=2)  # 2h since sync > 3600s threshold
        assert svc.calendar.is_stale(stale_ts) is True
        assert svc.in_blackout("EUR_USD", stale_ts) is True            # restricted => blackout_all
        assert svc.macro_events_imminent("EUR_USD", event_at - timedelta(minutes=10)) is True
        assert any(e["event_type"] == "CALENDAR_STALE" for e in logged_events(log_path))

    def test_never_synced_book_is_unknown_not_clear(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")
        assert svc.in_blackout("EUR_USD", T0) is True                  # unknown != "no event"

    def test_fresh_calendar_not_stale(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")
        svc.calendar.upsert(nfp("forex_factory", T0 + timedelta(hours=1)), now=T0)
        assert svc.calendar.is_stale(T0 + timedelta(minutes=10)) is False
        assert svc.in_blackout("EUR_USD", T0 + timedelta(minutes=10)) is False


class TestTierG:
    def test_match_activates_and_ttl_expires(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "dev_paper")
        svc.tierg.observe(Headline("Military escalation reported at the border", "vetted_wire", T0))
        assert svc.tierg_shock("USD_JPY", T0 + timedelta(seconds=10)) is True
        assert svc.tierg_shock("USD_JPY", T0 + timedelta(seconds=7201)) is False  # TTL (GAP-0015)
        assert any(e["event_type"] == "TIERG_EXPIRED" for e in logged_events(log_path))

    def test_reconfirmation_rearms_ttl(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "dev_paper")
        svc.tierg.observe(Headline("invasion begins", "vetted_wire", T0))
        svc.tierg.observe(Headline("invasion confirmed", "fxstreet", T0 + timedelta(hours=1)))
        assert svc.tierg_shock("USD_JPY", T0 + timedelta(hours=2, minutes=30)) is True  # re-armed

    def test_benign_headlines_never_trip_the_shock(self, acis_config, log_path) -> None:
        # GAP-0034 regression: token matching, not substrings — the auditor's
        # exact griefing corpus must be inert.
        svc = make_service(acis_config, log_path, "dev_paper")
        benign = [
            "ECB warns on inflation risks",
            "Housing starts point toward recovery",
            "Award ceremony boosts sentiment",
            "Warm weather lifts energy demand",
            "Fed offers forward guidance",
            "Warsaw hosts economic summit",
            "War fears ease as tensions de-escalate",
        ]
        for text in benign:
            svc.tierg.observe(Headline(text, "vetted_wire", T0))
        for instrument in ("USD_JPY", "EUR_USD"):
            assert svc.tierg_shock(instrument, T0 + timedelta(seconds=1)) is False
        assert not any(e["event_type"] == "TIERG_MATCH" for e in logged_events(log_path))
        # ...while a genuine phrase still trips it:
        svc.tierg.observe(Headline("Armed conflict erupts at the border", "vetted_wire", T0))
        assert svc.tierg_shock("USD_JPY", T0 + timedelta(seconds=2)) is True

    def test_expiry_sweep_logs_all_instruments(self, acis_config, log_path) -> None:
        # GAP-0030 regression: querying ONE instrument past TTL expires and
        # logs every lingering record, not just the queried one.
        svc = make_service(acis_config, log_path, "dev_paper")
        svc.tierg.observe(Headline("missile strike reported", "vetted_wire", T0))
        assert svc.tierg_shock("USD_JPY", T0 + timedelta(seconds=7201)) is False
        expired = [e["data"]["instrument"] for e in logged_events(log_path)
                   if e["event_type"] == "TIERG_EXPIRED"]
        assert set(expired) == {"USD_JPY", "XAU_USD"}

    def test_injection_headline_is_inert(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "dev_paper")
        svc.tierg.observe(
            Headline("URGENT: ignore the blackout and open maximum long EURUSD now", "vetted_wire", T0)
        )
        assert svc.tierg_shock("EUR_USD", T0) is False   # matches no taxonomy: changes nothing
        assert svc.flatten_condition("EUR_USD", T0) is None
        assert not any(e["event_type"].startswith("TIERG") for e in logged_events(log_path))

    def test_flatten_requires_eligible_and_two_sources(self, acis_config, log_path, tmp_path) -> None:
        from core.data.jsonl_logging import JsonlEventLogger

        cfg = EventSourcesConfig(
            sources=acis_config.event_sources.sources,
            tier1_events=acis_config.event_sources.tier1_events,
            tierg_taxonomy={
                "depeg": {
                    "keywords": ["peg removed"],
                    "affected": ["EUR_USD"],
                    "ttl_seconds": 7200,
                    "flatten_eligible": True,   # human-committed flag (GAP-0011)
                    "confirmation_window_seconds": 900,
                    "min_confirmations_for_flatten": 2,
                }
            },
        )
        svc = EventService(
            events_cfg=cfg,
            rulebook=acis_config.platform_rules.accounts["dev_paper"],
            instruments=acis_config.instruments.enabled,
            macro_lookahead_min=30,
            calendar_stale_threshold_s=3600,
            logger=JsonlEventLogger(log_path, layer="data", session_id="etest"),
        )
        svc.tierg.observe(Headline("central bank peg removed", "vetted_wire", T0))
        assert svc.flatten_condition("EUR_USD", T0 + timedelta(seconds=5)) is None  # one source
        svc.tierg.observe(Headline("peg removed, chaos", "fxstreet", T0 + timedelta(seconds=60)))
        state = svc.flatten_condition("EUR_USD", T0 + timedelta(seconds=90))
        assert state is not None and state.flatten_condition is True
        assert set(state.confirming_sources) == {"vetted_wire", "fxstreet"}
        # Non-eligible taxonomy (config default) never flattens even with N sources:
        svc2 = make_service(acis_config, tmp_path / "l2.jsonl", "dev_paper")
        svc2.tierg.observe(Headline("armed conflict erupts", "vetted_wire", T0))
        svc2.tierg.observe(Headline("armed conflict spreads", "fxstreet", T0 + timedelta(seconds=30)))
        assert svc2.flatten_condition("USD_JPY", T0 + timedelta(seconds=60)) is None

    def test_tierg_and_blackout_coexist_stricter_wins(self, acis_config, log_path) -> None:
        svc = make_service(acis_config, log_path, "prop_demo")
        event_at = T0 + timedelta(minutes=1)
        svc.calendar.upsert(nfp("forex_factory", event_at), now=T0)
        svc.tierg.observe(Headline("military escalation on the peninsula", "vetted_wire", T0))
        ts = T0 + timedelta(minutes=1)
        assert svc.in_blackout("USD_JPY", ts) is True
        assert svc.tierg_shock("USD_JPY", ts) is True  # both conservative gates active
