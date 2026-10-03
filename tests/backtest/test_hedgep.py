"""HEDGEP's signal (GAP-P12D-158; Kang, Rouwenhorst & Tang 2020): a CFTC report is read only from its release
day, the CFTC's own 2026 schedule reproduces, shutdown reports are never read, and the z-score reads no later
report."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from tests.backtest import hedgep

# The CFTC's published 2026 release schedule (cftc.gov, Release Schedule, read 2026-10-04): as-of Tuesday -> release.
CFTC_2026 = {date(2025, 12, 30): date(2026, 1, 5), date(2026, 1, 20): date(2026, 1, 23),
             date(2026, 2, 17): date(2026, 2, 20), date(2026, 5, 26): date(2026, 5, 29),
             date(2026, 6, 16): date(2026, 6, 22), date(2026, 6, 30): date(2026, 7, 6),
             date(2026, 9, 8): date(2026, 9, 11), date(2026, 10, 13): date(2026, 10, 16),
             date(2026, 11, 10): date(2026, 11, 16), date(2026, 11, 24): date(2026, 11, 30),
             date(2026, 12, 22): date(2026, 12, 28)}


def test_release_reproduces_the_cftcs_2026_schedule_and_never_reads_a_shutdown_report() -> None:
    assert {a: hedgep.release(a) for a in CFTC_2026} == CFTC_2026
    assert hedgep.release(date(2013, 10, 8)) is None and hedgep.release(date(2019, 1, 15)) is None
    assert hedgep.release(date(2018, 12, 4)) == date(2018, 12, 10)                  # the Bush day of mourning


def _reports(n: int, q: list[float] | None = None) -> list[tuple[date, int, int, int]]:
    out, net, d = [], 0, date(2015, 1, 6)
    for k in range(n):
        net += int(1000 * (q[k] if q else np.sin(k)))
        out.append((d, 100_000, 50_000 + max(net, -50_000) if net > 0 else 50_000, 50_000 - min(net, 0)))
        d += timedelta(days=7)
    return out


def test_z_reads_only_the_q_values_up_to_its_report_and_starts_after_26() -> None:
    r = _reports(80)
    z = hedgep.zscores(r)
    assert np.isnan(z[hedgep.MIN_WINDOW - 2][2]) and np.isfinite(z[hedgep.MIN_WINDOW - 1][2])
    later = r[:60] + [(r[60][0], 100_000, 99_000, 1_000)] + r[61:]
    assert [x[2] for x in hedgep.zscores(later)[:59]] == pytest.approx([x[2] for x in z[:59]], nan_ok=True)


def test_the_panel_holds_the_latest_released_report_and_goes_flat_when_it_is_stale() -> None:
    r = _reports(60)
    days = [r[40][0] + timedelta(days=k) for k in range(0, 10) if (r[40][0] + timedelta(days=k)).weekday() < 5]
    f = hedgep.panel(days, r)
    z = {d: zz for d, _, zz in hedgep.zscores(r)}
    tue, fri = r[40][0], r[40][0] + timedelta(days=3)
    assert f[days.index(tue)] == pytest.approx(10 * np.clip(z[r[39][0]], -2, 2))   # Tuesday: last week's report
    assert f[days.index(fri)] == pytest.approx(10 * np.clip(z[tue], -2, 2))        # released Friday 15:30
    stale = hedgep.panel([r[-1][0] + timedelta(days=20)], r)
    assert np.isnan(stale).all()
