"""scripts/download_macro.py's live mode for the runtime's rates (R1.6, R6-1): the requests span the asked
window, the research window is unchanged, and a series older than its freshness date is rejected, not saved.
The network fetch itself was run from the Linux server on 2026-10-02 (deploy/README.md)."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

from core.data.rates import stale_days

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("download_macro", ROOT / "scripts" / "download_macro.py")
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def test_the_live_window_reaches_today_and_the_research_window_is_untouched() -> None:
    live = dm.series(date(2023, 6, 20), date(2026, 10, 2))
    assert "endDate=2026-10-02" in live["usd_effr"][0] and "startPeriod=2023-06-20" in live["eur_dfr"][0]
    assert "endDate=2025-12-31" in dm.SERIES["usd_effr"][0]                  # the frozen research set
    assert set(live) == set(dm.SERIES)


def test_a_series_older_than_its_freshness_date_is_rejected() -> None:
    rows = [(date(2026, 9, 1), 3.9), (date(2026, 9, 18), 3.88)]
    assert dm.validate("usd_effr", rows, -1, 10, None, ends_by=date(2026, 9, 22)) is not None
    assert dm.validate("usd_effr", rows, -1, 10, None, ends_by=date(2026, 9, 15)) is None


def test_a_weekly_source_is_held_to_its_own_freshness_limit_in_live_mode() -> None:
    """PR16E-03 (GAP-P12D-146): the downloader judges each series by the engine's own limit, so BIS's
    weekly AUD release is not rejected early in the week while a daily series still is."""
    tue = date(2026, 10, 6)
    due = lambda sid: tue - timedelta(days=stale_days(sid, 10, 21))                 # noqa: E731 (main's rule)
    assert (due("bis_policy"), due("chf_saron"), due("usd_effr")) == (date(2026, 9, 15),) * 2 + (date(2026, 9, 26),)
    aud = [(date(2026, 9, 1), "AU", 3.6), (date(2026, 9, 18), "AU", 3.6)]          # 18 days old on the Tuesday
    assert dm.validate("bis_policy", aud, -1.5, 10, None, due("bis_policy"),
                       areas=dm.LIVE_BIS_AREAS) is None
    usd = [(date(2026, 9, 1), 3.9), (date(2026, 9, 25), 3.88)]                      # 11 days old
    assert dm.validate("usd_effr", usd, -1, 10, None, due("usd_effr")) is not None


def test_the_live_window_starts_at_the_research_start_so_it_covers_any_cache() -> None:
    live = dm.live_series(date(2027, 6, 30))                               # R16I-01: never a rolling window
    assert "spx_yahoo" not in live and all(v[4] is not None for v in live.values())
    assert "startDate=2011-01-01" in live["usd_effr"][0] and "endDate=2027-06-30" in live["usd_effr"][0]


def test_live_mode_validates_only_the_bis_areas_the_engine_reads() -> None:
    rows = [(date(2026, 9, 1), "AU", 3.6), (date(2026, 9, 24), "AU", 3.6)]
    assert dm.validate("bis_policy", rows, -1.5, 10, None, ends_by=date(2026, 9, 20), areas=dm.LIVE_BIS_AREAS) is None
    assert dm.validate("bis_policy", rows, -1.5, 10, None, ends_by=date(2026, 9, 20)) is not None   # all 7 wanted
