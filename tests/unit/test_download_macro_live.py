"""scripts/download_macro.py's live mode for the runtime's rates (R1.6, R6-1): the requests span the asked
window, the research window is unchanged, and a series older than its freshness date is rejected, not saved.
The network fetch itself was run from the Linux server on 2026-10-02 (deploy/README.md)."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

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
