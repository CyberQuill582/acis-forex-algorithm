"""Asset-class law (SPEC §3.7, ACIS-01 C-DATA-7).

Everything instrument-specific is declared data (config/instruments.yaml);
this module gives it behaviour: per-instrument market calendars and session
tagging. This is the ONLY session logic in the system (C1, generalised).
"""

from __future__ import annotations

from datetime import datetime, time

from config.schemas import ExchangeCalendar, FxCalendar, Session
from core.data.fx_clock import last_local, next_local, to_local

SESSION_CLOSED = "closed"
SESSION_OVERLAP = "overlap"
SESSION_EXCHANGE = "exchange"


def _hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _in_session(ts: datetime, s: Session) -> bool:
    if s.close_zone is None:
        return _hhmm(s.open) <= to_local(ts, s.zone).time() < _hhmm(s.close)
    opened = last_local(ts, s.zone, s.open)             # crosses centres (and midnight)
    return ts < next_local(opened, s.close_zone, s.close)


class MarketCalendar:
    """Session tagging for one declared calendar (fx or exchange type)."""

    def __init__(self, name: str, cfg: FxCalendar | ExchangeCalendar) -> None:
        self.name = name
        self._cfg = cfg

    def session_at(self, ts: datetime) -> str:
        if ts.tzinfo is None:
            raise ValueError("session_at requires a tz-aware timestamp")
        if isinstance(self._cfg, FxCalendar):
            return self._fx_session(ts)
        return self._exchange_session(ts)

    # -- fx: Sydney/Tokyo/London/NY windows, weekend + daily break (ACIS-01 §6) -- #
    # Every window is read in its own centre's local time (GAP-P12D-10).

    def _fx_session(self, ts: datetime) -> str:
        close, reopen = self._cfg.week_close, self._cfg.week_open
        wk = to_local(ts, close.zone)
        wd, t = wk.isoweekday(), wk.time()  # 1=Mon .. 7=Sun, in the week-close zone
        if wd == 6:  # Saturday
            return SESSION_CLOSED
        if wd == 5 and t >= _hhmm(close.at):  # Friday after close
            return SESSION_CLOSED
        if wd == 7 and to_local(ts, reopen.zone).time() < _hhmm(reopen.at):  # Sunday pre-open
            return SESSION_CLOSED
        brk = self._cfg.daily_break
        if brk and _hhmm(brk.open) <= to_local(ts, brk.zone).time() < _hhmm(brk.close):
            return SESSION_CLOSED                     # a declared daily break (spot metals)
        active = [name for name, s in self._cfg.sessions.items() if _in_session(ts, s)]
        if not active:
            return SESSION_CLOSED
        if len(active) > 1:
            return SESSION_OVERLAP
        return active[0]

    # -- exchange: weekday sessions, holidays, half-days (glitch class §13) -- #

    def _exchange_session(self, ts: datetime) -> str:
        local = to_local(ts, self._cfg.zone)          # days/holidays/hours are local
        d = local.date()
        if local.isoweekday() not in self._cfg.days or d in self._cfg.holidays:
            return SESSION_CLOSED
        close = self._cfg.half_days.get(d, self._cfg.close)
        # A declared early close IS the session end, not a feed outage.
        if _hhmm(self._cfg.open) <= local.time() < _hhmm(close):
            return SESSION_EXCHANGE
        return SESSION_CLOSED


def build_calendars(
    calendars_cfg: dict[str, FxCalendar | ExchangeCalendar],
) -> dict[str, MarketCalendar]:
    return {name: MarketCalendar(name, cfg) for name, cfg in calendars_cfg.items()}
