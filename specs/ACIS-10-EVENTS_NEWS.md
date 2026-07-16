# ACIS-10 — Event & News Intake, Blackouts, Tier-G — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-EVENTS-010` |
| **Version** | 1.0 (LOCKED) |
| **Layer / DIR** | Layer 1 · `[DIR:core/data]` (`events.py`) + `[DIR:config]` (`account_doctrine.py`) |
| **Consumes** | calendar/headline fixtures or feeds (external, trusted per `event_sources.yaml`), `platform_rules.yaml`, `instruments.yaml` |
| **Emits** | `EventPicture` (frozen), `macro_events_imminent` inputs to ACIS-01, blackout verdicts to the Governor (via config/data flow), Tier-G flags to NVMA, flatten conditions to the Risk Monitor |
| **Depends On** | `../ACIS_SPEC.md` §3.5–3.6, §9, §9.5, §12, §13 · ACIS-01 |
| **Corrections applied** | C12 (Tier-G + shock asymmetry), GAP-0011 (flatten: flatten_eligible + ≥2 confirmations), GAP-0015 (TTL lifecycle), GAP-0016 (dampen-only clamp lives in config schema), C11 (§9.5 stricter-of composition) |

## 1. Executive purpose & scope
Turn trusted calendars and vetted headlines into a deterministic, timestamped **EventPicture**, compute per-instrument **blackout windows** from the active account's rulebook, and classify **Tier-G** geopolitical shocks — all data plumbing inside the LLM boundary (§0): keyword/taxonomy matching only, no judgment, no network reasoning in the loop. **Untrusted-input law is structural here:** headline text is only ever *matched against config keywords*; no string from a feed reaches control flow, a tool call, or an eval of any kind.

**IS:** calendar book with multi-source cross-check; blackout computation (inclusive fenceposts) per account rulebook; `macro_events_imminent`; calendar-outage fail-safe; Tier-G classifier with TTL lifecycle, re-confirmation, and the ratified flatten condition; §9.5 stricter-of doctrine composition (`config/account_doctrine.py`). Phase-2 gate runs on **fixture** calendars/headlines; live source adapters join later behind `event_sources.yaml`.
**IS NOT:** no fetching in the fast loop; no direction or sizing from any headline (shock-asymmetry law — Tier-G output is only ever conservative flags); no LLM; no blackout invented here (windows come only from the rulebook); Risk-Monitor flatten *execution* is phase 9 — this layer only computes and logs the condition.

## 2. Boot/entry contract & inputs
`core/data/events.py::EventService(cfg, rulebook, instruments, logger, now_fn)`. Inputs: `EventSourcesConfig` (sources, `tier1_events`, `tierg_taxonomy` — human-committed), the active `AccountRulebook` (§9.5, fatal if absent — enforced at config load), instrument specs (currency mapping: an event affects an instrument iff the event currency ∈ {base_ccy, quote_ccy}), `system.data.macro_lookahead_min`, `calendar_stale_threshold_s` (config, required). Boot fatal: empty `tier1_events`; unknown instrument in any taxonomy `affected` list.

## 3. Layer architecture & responsibility
Part of layer 1 (data). May import `core.data.*` + `config` only (layer law). Three units: **CalendarBook** (scheduled events, cross-check, staleness), **TierGClassifier** (headline → taxonomy matches, TTL state), **EventService** (facade: EventPicture, blackout/macro/flatten queries). `config/account_doctrine.py` is pure config composition (no core imports).

## 4. Output contract
```python
@dataclass(frozen=True) class CalendarEvent: event_key, name, tier, event_time, currency, source
@dataclass(frozen=True) class Headline:      text, source, published_at
@dataclass(frozen=True) class BlackoutWindow: instrument, start, end, event_key   # INCLUSIVE edges
@dataclass(frozen=True) class TierGState:    taxonomy_class, instrument, active_until, confirmations, flatten_condition
@dataclass(frozen=True) class EventPicture:  as_of, upcoming, blackouts, tierg, calendar_stale, blackout_all
```
Queries (all pure, UTC, deterministic): `macro_events_imminent(instrument, ts) -> bool` · `in_blackout(instrument, ts) -> bool` (inclusive: `start <= ts <= end`; `blackout_all` short-circuits True on restricted accounts during calendar outage) · `tierg_shock(instrument, ts) -> bool` · `flatten_condition(instrument, ts) -> TierGState | None` · `picture(ts) -> EventPicture`.

## 5–7. Schemas, algorithms, core logic
- **Cross-check (C-EVT-1):** Tier-1 events keyed `(name, currency, event_time.date())`; two trusted sources disagreeing on time ⇒ canonical time = **earlier**, log `CALENDAR_DISAGREEMENT{key, times}`. A later `upsert` from the same source moves the event (calendar-DST glitch): windows follow the **event**, never the wall clock.
- **Blackouts (C-EVT-2):** only if `rulebook.news.restricted`; for each Tier-1 event and each affected enabled instrument: `[event_time - window_before_s, event_time + window_after_s]`, edges inclusive (fencepost glitch). Unrestricted account ⇒ zero windows, news regimes tradeable like any other (platform-rules law §3.5).
- **Macro imminence:** Tier-1 event affecting the instrument within `macro_lookahead_min` of `ts` (before the event only).
- **Outage fail-safe (C-EVT-3):** `calendar_stale = now - last_sync > calendar_stale_threshold_s`. While stale: `macro_events_imminent` is True during any UTC hour that contained a Tier-1 event in the last good sync (±lookahead), for its affected instruments; on restricted accounts `blackout_all = True` for the whole stale period. **Unknown never degrades to "no event."**
- **Tier-G (C-EVT-4, §3.6):** case-insensitive **token-sequence phrase matching** against `tierg_taxonomy` (GAP-0034: word-boundary tokens, never raw substrings — "war" cannot match "warns"/"Warsaw"/"award", "de-escalation" cannot match a bare phrase; short ambiguous single-word keywords are forbidden in the taxonomy in favour of multi-word phrases); a match activates `(class, instrument)` for `ttl_seconds` from the headline's `published_at`; re-match re-arms; expiry logs `TIERG_EXPIRED` and clears. Confirmations: distinct **sources** matching the same class within `confirmation_window_seconds`. `flatten_condition` is non-None iff the taxonomy entry is `flatten_eligible` **and** confirmations ≥ `min_confirmations_for_flatten` (≥2 by schema) **and** the flag is active. Matches only ever *raise* conservatism (shock asymmetry); nothing here sizes, signals, or halts.
- **Doctrine composition (C-EVT-5, §9.5):** `config/account_doctrine.py::EffectiveDoctrine.compose(guardrails, rulebook)`: taper fractions = `min(engine, account_override)` (schema already forbids looser-than-ratified); constraint set = engine limits (ACIS semantics) ∪ platform `drawdown_rules` (each kept under its own declared measurement semantics — never merged numerically); news/min-hold/weekend/lot-cap/consistency carried through verbatim. Pure function, unit-tested, consumed later by Governor (downward config) and Risk Monitor (platform series, phase 9).

## 8. State & cadence
CalendarBook/TierG state mutate only via `upsert`/`observe` calls (medium cadence, out of the fast loop); all queries are pure reads on immutable snapshots. Time enters via injected `now_fn` — no wall-clock reads inside logic (testable, deterministic).

## 9–10. Persistence & logging
Events log to `system_log` JSONL (§11 envelope): `CALENDAR_DISAGREEMENT`, `CALENDAR_STALE`, `TIERG_MATCH{class, instrument, source}`, `TIERG_EXPIRED`, `TIERG_FLATTEN_CONDITION`. No DB tables in phase 2 (EventPicture is derived state; fixtures are config/test data) — lean-build law; a calendar store lands only if a live source adapter needs replay.

## 11. Interface/MCP
Feeds `acis://events/picture` (phase 10). No tools. Headline/calendar text exposed to any out-of-band LLM stays under the §12 untrusted-input law.

## 12. Error taxonomy
Unknown instrument in taxonomy config → fatal at boot (ConfigError). Malformed fixture event (naive ts, unknown tier) → `DataQualityError`, event rejected + logged, book unchanged. Query with naive `ts` → `ValueError`.

## 13. Logic-flaw registry
C-EVT-1 disagreement=earlier · C-EVT-2 inclusive fenceposts · C-EVT-3 outage fail-safe never "no event" · C-EVT-4 TTL + ≥2-source flatten (GAP-0011/0015) · C-EVT-5 stricter-of composition (GAP-0010 floor via schema) · C-EVT-6 injection text is inert (a headline saying "ignore the blackout" matches nothing and changes nothing — test).

## 14. Test contract (unit, postcondition style)
Blackout windows from fixture calendar+restricted rulebook incl. **exact-edge inclusivity both ends**; unrestricted ⇒ none; macro imminence for affected/unaffected instruments; disagreement→earlier+logged; event moved an hour ⇒ window follows; stale calendar ⇒ macro True in known hours + `blackout_all` on restricted account; Tier-G match/TTL expiry/re-arm; flatten only when eligible + ≥2 distinct sources in window (1 source ⇒ None); injection headline inert; doctrine composition stricter-of + both rule sets present; Tier-G active during a blackout coexists (stricter outcome, no interference).

## 15. Integration gate
NVMA (ACIS-02) consumes `tierg_shock` + `macro_events_imminent`; the Governor (ACIS-05) consumes `in_blackout` as a hard override; Risk Monitor (ACIS-07) consumes `flatten_condition`. Phase-2 done-when: all §14 tests green in the full run; ACIS-01's factory can take `EventService.macro_events_imminent` as its `macro_imminent` callable unchanged.

## Changelog
- **1.1 (LOCKED, 2026-07-15)** — Phases 2–3 subordinate-audit triage: matching precision fixed to token-sequence phrases with a benign-headline regression contract (GAP-0034); Tier-G expiry sweeps ALL lingering records on any query so the audit trail matches state (GAP-0030).
- **1.0 (LOCKED, 2026-07-15)** — Authored for the phase-2 build against master v2.6 (§3.5–3.6, §9.5, ratified GAP-0011/0015 semantics, C-EVT-1..6).
