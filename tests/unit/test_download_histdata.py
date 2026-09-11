"""Offline tests of the HistData downloader's verification (scripts/download_histdata.py).
Every zip must be fully proven before it counts; these pin the rejection classes and
the fixed-EST -> UTC conversion. (Previously checked only ad hoc in a session — now
committed, per the ledger closure law.)"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import download_histdata as h  # noqa: E402

GOOD = ["20120102 170000123,0.83010,0.83030,0", "20120102 170000456,0.83011,0.83029,0",
        "20120131 235959999,0.83500,0.83520,0"]


def _zip(tmp: Path, name: str, rows, member="DAT_ASCII_EURGBP_T_201201.csv", report=None) -> Path:
    p = tmp / name
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, "\n".join(rows) + "\n")
        if report:
            z.writestr("HISTDATA_COM_ASCII_EURGBP_T201201.txt", report)
    return p


def test_good_month_parses_with_est_to_utc_and_gap_report(tmp_path) -> None:
    r = h.verify("eurgbp", 2012, 1, _zip(tmp_path, "g.zip", GOOD, report="Gap of 62s\nGap of 900s\n"))
    assert r["rows"] == 3
    assert r["first_utc"] == "2012-01-02T22:00:00.123000+00:00"   # 17:00 EST (fixed) = 22:00 UTC
    assert r["last_utc"] == "2012-02-01T04:59:59.999000+00:00"
    assert (r["gap_reports"], r["max_gap_s"]) == (2, 900)


@pytest.mark.parametrize("name, rows, member", [
    ("wrong-month", GOOD + ["20120201 000000000,0.8,0.81,0"], "DAT_ASCII_EURGBP_T_201201.csv"),
    ("bad-timestamp", ["2012-01-02 17:00,0.8,0.81,0"], "DAT_ASCII_EURGBP_T_201201.csv"),
    ("empty", [], "DAT_ASCII_EURGBP_T_201201.csv"),
    ("wrong-member", GOOD, "DAT_ASCII_EURUSD_T_201201.csv"),
])
def test_untrustworthy_zips_are_rejected(tmp_path, name, rows, member) -> None:
    with pytest.raises(ValueError):
        h.verify("eurgbp", 2012, 1, _zip(tmp_path, f"{name}.zip", rows, member))


def test_anomalies_are_counted_not_hidden(tmp_path) -> None:
    rows = ["20120102 170000123,0.83,0.82,0",       # crossed
            "20120102 170000100,0.83,0.84,0",       # out of order
            "20120102 170000100,0.83,0.84,0"]       # duplicate timestamp
    r = h.verify("eurgbp", 2012, 1, _zip(tmp_path, "a.zip", rows))
    assert (r["crossed"], r["out_of_order"], r["duplicate_ts"]) == (1, 1, 1)


def test_plan_is_newest_month_first_all_instruments() -> None:
    plan = h.build_plan()
    assert len(plan) == 8 * 14 * 12
    assert plan[0] == ("eurusd", 2025, 12) and plan[-1] == ("xauusd", 2012, 1)
