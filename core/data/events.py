"""Event & news intake — EventPicture, blackouts, Tier-G (SPEC §3.5–3.6, ACIS-10).

Deterministic data plumbing inside the LLM boundary. The untrusted-input law is
structural: headline text is only ever MATCHED against config keywords — no
string from a feed reaches control flow, a tool call, or an eval of any kind.
Tier-G output is only ever conservative (shock-asymmetry law).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping

from config.schemas import AccountRulebook, EventSourcesConfig, InstrumentSpec
from core.data.errors import DataQualityError
from core.data.jsonl_logging import JsonlEventLogger


def _aware_utc(ts: datetime, name: str) -> datetime:
    if not isinstance(ts, datetime) or ts.tzinfo is None:
        raise ValueError(f"{name} must be a tz-aware datetime")
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class CalendarEvent:
    name: str          # e.g. "NFP" — Tier-1 iff listed in event_sources.tier1_events
    tier: int          # 1 | 2
    event_time: datetime
    currency: str      # the currency the release concerns, e.g. "USD"
    source: str        # trusted source name (event_sources.yaml)

    @property
    def key(self) -> tuple[str, str, str]:
        # One logical event across sources: same name+currency+UTC date (C-EVT-1).
        return (self.name, self.currency, self.event_time.date().isoformat())


@dataclass(frozen=True)
class Headline:
    text: str
    source: str
    published_at: datetime


@dataclass(frozen=True)
class BlackoutWindow:
    instrument: str
    start: datetime  # inclusive (fencepost glitch class)
    end: datetime    # inclusive
    event_key: tuple[str, str, str]


@dataclass(frozen=True)
class TierGState:
    taxonomy_class: str
    instrument: str
    active_until: datetime
    confirming_sources: tuple[str, ...]
    flatten_condition: bool


class CalendarBook:
    """Scheduled events across trusted sources; disagreement -> earlier wins."""

    def __init__(self, stale_threshold_s: int, logger: JsonlEventLogger) -> None:
        self._times: dict[tuple, dict[str, datetime]] = {}  # key -> source -> time
        self._meta: dict[tuple, CalendarEvent] = {}
        self._stale_threshold = timedelta(seconds=stale_threshold_s)
        self._log = logger
        self.last_sync: datetime | None = None

    def upsert(self, ev: CalendarEvent, now: datetime) -> None:
        event_time = _aware_utc(ev.event_time, "event_time")
        if ev.tier not in (1, 2):
            raise DataQualityError("tier", ev.tier, "must be 1 or 2")
        by_source = self._times.setdefault(ev.key, {})
        by_source[ev.source] = event_time  # same-source re-upsert MOVES the event
        self._meta[ev.key] = ev
        if len(set(by_source.values())) > 1:
            self._log.event(
                "CALENDAR_DISAGREEMENT",
                key=list(ev.key),
                times={s: t.isoformat() for s, t in by_source.items()},
            )
        self.last_sync = _aware_utc(now, "now")

    def canonical_time(self, key: tuple) -> datetime:
        return min(self._times[key].values())  # C-EVT-1: earlier time wins

    def events(self, tier: int | None = None) -> list[tuple[tuple, datetime, str]]:
        out = []
        for key, meta in self._meta.items():
            if tier is None or meta.tier == tier:
                out.append((key, self.canonical_time(key), meta.currency))
        return out

    def is_stale(self, now: datetime) -> bool:
        # Never synced == unknown == stale. Unknown never degrades to "no event".
        if self.last_sync is None:
            return True
        return (_aware_utc(now, "now") - self.last_sync) > self._stale_threshold


@dataclass
class _TierGRecord:
    active_until: datetime
    first_seen: datetime
    confirmations: dict[str, datetime] = field(default_factory=dict)  # source -> last match


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens — matching is token-sequence based (GAP-0034):
    'war' cannot match 'warns'/'Warsaw'/'award', and 'de-escalation' tokenizes
    to ['de','escalation'] so hyphenated negations never match a bare phrase."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _contains_phrase(text_tokens: list[str], phrase: str) -> bool:
    kw = _tokens(phrase)
    n = len(kw)
    if n == 0:
        return False
    return any(text_tokens[i:i + n] == kw for i in range(len(text_tokens) - n + 1))


class TierGClassifier:
    """Deterministic keyword taxonomy (§3.6). TTL-bounded (GAP-0015);
    flatten condition requires flatten_eligible + >=2 distinct sources (GAP-0011);
    token-sequence matching, never raw substrings (GAP-0034)."""

    def __init__(self, cfg: EventSourcesConfig, logger: JsonlEventLogger) -> None:
        self._taxonomy = cfg.tierg_taxonomy
        self._log = logger
        self._state: dict[tuple[str, str], _TierGRecord] = {}  # (class, instrument)

    def observe(self, headline: Headline) -> None:
        published = _aware_utc(headline.published_at, "published_at")
        text_tokens = _tokens(headline.text)
        for cls, entry in self._taxonomy.items():
            if not any(_contains_phrase(text_tokens, kw) for kw in entry.keywords):
                continue  # untrusted text that matches nothing changes nothing (C-EVT-6)
            for instrument in entry.affected:
                rec = self._state.get((cls, instrument))
                if rec is None:
                    rec = _TierGRecord(active_until=published, first_seen=published)
                    self._state[(cls, instrument)] = rec
                rec.active_until = published + timedelta(seconds=entry.ttl_seconds)  # re-arm
                rec.confirmations[headline.source] = published
                self._log.event("TIERG_MATCH", taxonomy_class=cls, instrument=instrument,
                                source=headline.source)
                if self._flatten_ok(cls, rec, published):
                    self._log.event("TIERG_FLATTEN_CONDITION", taxonomy_class=cls,
                                    instrument=instrument,
                                    sources=sorted(rec.confirmations))

    def _flatten_ok(self, cls: str, rec: _TierGRecord, at: datetime) -> bool:
        entry = self._taxonomy[cls]
        if not entry.flatten_eligible:
            return False
        window = timedelta(seconds=entry.confirmation_window_seconds)
        recent = [s for s, t in rec.confirmations.items() if at - t <= window]
        return len(recent) >= entry.min_confirmations_for_flatten

    def _expire(self, key: tuple[str, str], ts: datetime) -> _TierGRecord | None:
        rec = self._state.get(key)
        if rec is None:
            return None
        if ts > rec.active_until:
            del self._state[key]  # bounded by construction (GAP-0015)
            self._log.event("TIERG_EXPIRED", taxonomy_class=key[0], instrument=key[1])
            return None
        return rec

    def _sweep(self, ts: datetime) -> None:
        """GAP-0030: expire (and log) ALL lingering records, not only the
        queried instrument's — the audit trail must match the state."""
        for key in list(self._state):
            self._expire(key, ts)

    def shock(self, instrument: str, ts: datetime) -> bool:
        ts = _aware_utc(ts, "ts")
        self._sweep(ts)
        return any(
            inst == instrument and ts >= rec.first_seen
            for (cls, inst), rec in self._state.items()
        )

    def flatten_condition(self, instrument: str, ts: datetime) -> TierGState | None:
        ts = _aware_utc(ts, "ts")
        self._sweep(ts)
        for (cls, inst) in list(self._state):
            if inst != instrument:
                continue
            rec = self._state.get((cls, inst))
            if rec is not None and self._flatten_ok(cls, rec, ts):
                return TierGState(
                    taxonomy_class=cls,
                    instrument=instrument,
                    active_until=rec.active_until,
                    confirming_sources=tuple(sorted(rec.confirmations)),
                    flatten_condition=True,
                )
        return None


class EventService:
    """Facade: blackout / macro-imminence / Tier-G queries (all pure, UTC)."""

    def __init__(
        self,
        events_cfg: EventSourcesConfig,
        rulebook: AccountRulebook,
        instruments: Mapping[str, InstrumentSpec],
        macro_lookahead_min: int,
        calendar_stale_threshold_s: int,
        logger: JsonlEventLogger,
    ) -> None:
        self._rulebook = rulebook
        self._instruments = dict(instruments)
        self._lookahead = timedelta(minutes=macro_lookahead_min)
        self.calendar = CalendarBook(calendar_stale_threshold_s, logger)
        self.tierg = TierGClassifier(events_cfg, logger)
        self._log = logger
        self._stale_logged = False

    def _affected(self, currency: str) -> list[str]:
        return [
            sym for sym, spec in self._instruments.items()
            if currency in (spec.base_ccy, spec.quote_ccy)
        ]

    # -- blackouts (C-EVT-2): only what the rulebook declares, edges inclusive -- #

    def blackout_windows(self) -> tuple[BlackoutWindow, ...]:
        news = self._rulebook.news
        if not news.restricted:
            return ()
        out = []
        for key, when, currency in self.calendar.events(tier=1):
            for instrument in self._affected(currency):
                out.append(
                    BlackoutWindow(
                        instrument=instrument,
                        start=when - timedelta(seconds=news.window_before_s),
                        end=when + timedelta(seconds=news.window_after_s),
                        event_key=key,
                    )
                )
        return tuple(out)

    def in_blackout(self, instrument: str, ts: datetime) -> bool:
        ts = _aware_utc(ts, "ts")
        if self._rulebook.news.restricted and self.calendar.is_stale(ts):
            self._note_stale(ts)
            return True  # C-EVT-3: outage fail-safe on rule-restricted accounts
        return any(
            w.start <= ts <= w.end  # inclusive fenceposts, provably (test contract)
            for w in self.blackout_windows()
            if w.instrument == instrument
        )

    # -- macro imminence + outage fail-safe (C-EVT-3) -- #

    def macro_events_imminent(self, instrument: str, ts: datetime) -> bool:
        ts = _aware_utc(ts, "ts")
        stale = self.calendar.is_stale(ts)
        if stale:
            self._note_stale(ts)
        for _, when, currency in self.calendar.events(tier=1):
            if instrument not in self._affected(currency):
                continue
            if stale:
                # Unknown-event risk: conservative +/- lookahead around every
                # Tier-1 hour known from the last good sync.
                if abs(when - ts) <= self._lookahead:
                    return True
            elif timedelta(0) <= (when - ts) <= self._lookahead:
                return True
        return False

    def _note_stale(self, ts: datetime) -> None:
        if not self._stale_logged:
            self._log.event("CALENDAR_STALE", at=ts.isoformat())
            self._stale_logged = True

    # -- Tier-G passthroughs (NVMA + Risk Monitor consumers) -- #

    def tierg_shock(self, instrument: str, ts: datetime) -> bool:
        return self.tierg.shock(instrument, ts)

    def flatten_condition(self, instrument: str, ts: datetime) -> TierGState | None:
        return self.tierg.flatten_condition(instrument, ts)
