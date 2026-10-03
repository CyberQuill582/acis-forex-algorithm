"""scripts/r1_gotobi_kill_test.py's look-defining tables (GAP-P12D-159 PC-I-09): the gotobi and control day
sets, and each registered line's legs, times, window and order, pinned so a later edit cannot move a graded
number silently."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("r1_gotobi_kill_test", ROOT / "scripts" / "r1_gotobi_kill_test.py")
g = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = g                       # its dataclass resolves annotations through sys.modules
spec.loader.exec_module(g)

GW_2019 = frozenset(date(2019, 4, 29) + timedelta(days=k) for k in range(8))     # 4-29 .. 5-06


def test_the_day_sets_are_tuesday_to_friday_bank_days_and_disjoint() -> None:
    gotobi, control = g.days_of(GW_2019, "30", date(2019, 4, 1), date(2019, 5, 31))
    assert gotobi == [date(2019, 4, 5), date(2019, 4, 10), date(2019, 4, 19), date(2019, 4, 25), date(2019, 4, 26),
                      date(2019, 5, 10), date(2019, 5, 15), date(2019, 5, 24),
                      date(2019, 5, 30)]                                         # 4-15 and 5-20 are Mondays
    assert not set(gotobi) & set(control)
    assert all(d.weekday() in (1, 2, 3, 4) for d in gotobi + control)
    assert not set(control) & GW_2019 and date(2019, 4, 9) in control
    assert len(gotobi) + len(control) == sum(1 for k in range(61) if (date(2019, 4, 1) + timedelta(days=k)).weekday()
                                             in (1, 2, 3, 4) and date(2019, 4, 1) + timedelta(days=k) not in GW_2019)


def test_each_registered_line_has_its_ruled_legs_times_and_window() -> None:
    v1a, v1b = g.LINES["v1"]["gotobi_v1a_h1_usdjpy"], g.LINES["v1"]["gotobi_v1b_h1h2_usdjpy"]
    assert v1a.legs == (g.H1,) and v1b.legs == (g.H1, g.H2) and v1a.window == (g.START, g.GRADED_FROM, g.END)
    assert (g.H1.entry, g.H1.exit, g.H1.side) == ("entry", "fix", 1.0)
    assert (g.H2.side, g.H2.gate) == (-1.0, ("entry", "nine"))
    assert (g.TIMES["entry"], g.TIMES["fix"]) == (time(3, 0), time(9, 55))
    (v1c,) = g.LINES["exit0954"].values()
    assert v1c.times["fix"] == time(9, 54) and v1c.legs == (g.H1,)
    stage_c, contrast = g.LINES["v2"].items()
    assert stage_c[0] == "gotobi_v1a_h1_usdjpy" and stage_c[1].formula == v1a.formula      # the SAME variant
    assert stage_c[1].window == (date(2024, 1, 2), date(2024, 1, 3), date(2025, 12, 31)) and stage_c[1].changed
    assert contrast[1].contrast and contrast[1].window == v1a.window and contrast[1].legs == (g.H1,)
