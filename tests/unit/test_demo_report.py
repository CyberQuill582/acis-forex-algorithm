"""The demo's forward-record report (scripts/demo_report.py): refusal counts and the uncapped shadow
book's daily USD P&L, read from the engine's own logs."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.governor.target import banded_target, optimum_units

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_report", ROOT / "scripts" / "demo_report.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)


def _write(path: Path, events: list[tuple[str, dict]]) -> None:
    path.write_text("".join(json.dumps({"timestamp": "2026-10-16T21:02:00+00:00", "event_type": k, "data": d}) + "\n"
                            for k, d in events), encoding="utf-8")


def test_refusals_and_the_shadow_books_daily_pnl(tmp_path) -> None:
    decided = lambda inst, day, shadow, close, q=1.0: ("TARGET_DECIDED", {"instrument": inst, "day": day,   # noqa: E731
                                                                          "reason": "target", "shadow": shadow,
                                                                          "close": close, "q": q, "boot": False})
    _write(tmp_path / "target_log.jsonl", [
        decided("EUR_USD", "2026-10-15", 1000.0, 1.10), decided("USD_JPY", "2026-10-15", -500.0, 150.0, 0.0067),
        decided("EUR_USD", "2026-10-16", 800.0, 1.11), decided("USD_JPY", "2026-10-16", -500.0, 149.0, 0.0067),
        ("TARGET_DECIDED", {"instrument": "GBP_USD", "day": "2026-10-16", "reason": "no_target:stale_rates"}),
        ("TARGET_SLOT_SKIPPED", {"instrument": "EUR_USD", "reason": "busy"}),
        ("TARGET_EXECUTED", {"instrument": "EUR_USD", "reason": "open"})])
    _write(tmp_path / "governor_log.jsonl", [("TARGET_ENTRY_ZERO", {"instrument": "USD_JPY", "reason": "wide_spread"})])
    r = dr.refusals(tmp_path, None)
    assert r["decided"] == {"target": 4, "no_target:stale_rates": 1}
    assert r["slot_skipped"] == {"busy": 1} and r["entry_zero"] == {"wide_spread": 1} and r["executed"] == {"open": 1}
    book = dr.shadow_book(tmp_path, None)
    want = 1000.0 * (1.11 - 1.10) * 1.0 + (-500.0) * (149.0 - 150.0) * 0.0067   # +10 + 3.35
    assert book["days"] == 1 and book["daily_usd"]["2026-10-16"] == pytest.approx(want)


def test_the_shadow_position_is_the_banded_sizers_optimum() -> None:
    """From flat with no band and a fine lot grid, the banded target IS the continuous optimum."""
    kw = dict(cash_vol=125.0, weight=1 / 13, idm=1.5)
    units = optimum_units(8.0, 0.006, 1.10, 1.0, **kw)
    target = banded_target(0.0, 8.0, 0.006, 1.10, 1.0, buffer=0.0, step=Decimal("0.01"), minimum=Decimal("0.01"), **kw)
    assert float(target) == pytest.approx(units, abs=0.01) and optimum_units(float("nan"), 0.006, 1.1, 1.0, **kw) == 0.0
