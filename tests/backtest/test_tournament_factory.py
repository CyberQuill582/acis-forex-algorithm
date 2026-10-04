"""FACTORY's survivors in the tournament (TOURNAMENT): the frozen ECB/CPI/COT series are rewritten in the
looks' own file formats, each book settles only through the inputs it can read, and an owner hypothesis
(human origin, no certifying boundary) registers like any other entry."""

from __future__ import annotations

import importlib.util
from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pytest

from tests.backtest.forward_record import ForwardRecord
from tests.backtest.forward_store import COT, CPI, ECB, InputStore
from tests.backtest.look_claims import Origin
from tests.backtest.tournament_books import BookSeries
from tests.backtest.tournament_factory import cot_view, cpi_view, ecb_view, fxvalue_end, hedgep_end, read_rows
from tests.backtest.tournament_registry import Strategy
from tests.backtest.tournament_rule import rule_line

NOW = datetime(2026, 10, 4, 7, tzinfo=timezone.utc)


def _store(tmp_path) -> InputStore:
    arch = tmp_path / "r1_real"
    (arch / "fx_value").mkdir(parents=True)
    (arch / "cot").mkdir()
    (arch / "macro").mkdir()
    (arch / "fx_value" / "ecb_daily.csv").write_text("date,currency,eur_rate\n2025-12-31,USD,1.1745\n", encoding="utf-8")
    (arch / "fx_value" / "bis_cpi.csv").write_text("month,area,cpi\n2025-12,US,125.5\n", encoding="utf-8")
    (arch / "cot" / "cot_gold.csv").write_text("as_of,open_interest,commercial_long,commercial_short\n"
                                               "2025-12-30,500000,150000,400000\n", encoding="utf-8")
    return InputStore(tmp_path / "store", archive_candles=arch / "candles", archive_macro=arch / "macro",
                      archive_treasury=arch / "treasury", holidays_csv=arch / "h.csv")


def test_the_frozen_series_are_rewritten_in_each_looks_own_file_format(tmp_path) -> None:
    s = _store(tmp_path)
    rows = read_rows(raw_ecb=[("2026-01-02", "USD", 1.1801)], raw_cpi=[("2026-01", "US", 126.0)],
                     raw_cot=[("2026-01-06", 510000, 151000, 401000)])
    for sid, through in ((ECB, date(2026, 1, 2)), (CPI, date(2026, 1, 1)), (COT, date(2026, 1, 6))):
        s.freeze_series(sid, rows[sid], through, NOW)
    assert ecb_view(s).read_text(encoding="utf-8").splitlines() == [
        "date,currency,eur_rate", "2025-12-31,USD,1.1745", "2026-01-02,USD,1.1801"]
    assert cpi_view(s).read_text(encoding="utf-8").splitlines()[1:] == ["2025-12,US,125.5", "2026-01,US,126.0"]
    assert cot_view(s).read_text(encoding="utf-8").splitlines() == [
        "as_of,open_interest,commercial_long,commercial_short", "2025-12-30,500000,150000,400000",
        "2026-01-06,510000,151000,401000"]


class _Through:
    def __init__(self, **t) -> None:
        self.t = t

    def through(self, sid):
        return self.t[sid]


def test_fxvalue_settles_through_the_month_its_ranks_inputs_allow() -> None:
    assert fxvalue_end(_Through(ecb_exr=date(2026, 9, 30), bis_cpi=date(2026, 5, 1)), date(2026, 10, 4)) == date(2026, 10, 31)
    assert fxvalue_end(_Through(ecb_exr=date(2026, 9, 29), bis_cpi=date(2026, 5, 1)), date(2026, 10, 4)) == date(2026, 9, 30)
    assert fxvalue_end(_Through(ecb_exr=date(2026, 10, 20), bis_cpi=date(2026, 4, 1)), date(2026, 10, 21)) == date(2026, 9, 30)


@pytest.mark.skipif(importlib.util.find_spec("tests.backtest.hedgep") is None, reason="HEDGEP's module is on main")
def test_hedgep_settles_through_the_day_before_its_next_report_could_be_read() -> None:
    assert hedgep_end(_Through(cot_gold=date(2026, 9, 29)), date(2026, 10, 4)) == date(2026, 10, 8)   # Fri 10-09


def test_an_owner_hypothesis_registers_with_no_boundary_and_starts_after_it_is_written(tmp_path) -> None:
    book = lambda store, cfg, fs, today: BookSeries((), np.zeros(0), today - timedelta(days=1))   # noqa: E731
    mine = Strategy("OWNER-h1", "owner_h1", "U", (), "rsim_17ny", ("EUR_USD",), "my rule", Origin("human"),
                    date(2026, 10, 7), (time(17, 0), "America/New_York"), 0.0126, 0.0, "ab" * 32, {}, book)
    e = mine.entry()
    assert e["certifying_boundary"] is None and e["origin"]["kind"] == "human"
    rec = ForwardRecord(tmp_path / "rec")
    rec.append(rule_line(), NOW)
    rec.append(e, NOW)
    assert rec.state().entries["OWNER-h1"]["spec_hash"] == e["spec_hash"]
