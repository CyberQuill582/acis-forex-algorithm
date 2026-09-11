"""Dukascopy `.bi5` decoding (tests/backtest/bi5.py) — pinned to REAL Dukascopy bytes.

The fixture is the public-feed hour EUR/USD 2025-12-31 00:00 UTC (4,013 bytes,
sha256 0d70b051a2a8dd9f…). On 2026-09-11 this decoder's output was compared tick-by-tick
with dukascopy-node's decode of the same hour: 740 ticks, identical timestamps, prices
and volumes. The expected values below are that verified output."""

from __future__ import annotations

import lzma
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.backtest.bi5 import RECORD, Bi5Error, decode

UTC = timezone.utc
FIXTURE = Path(__file__).parent / "fixtures" / "EURUSD_2025-12-31_00h_ticks.bi5"
HOUR = datetime(2025, 12, 31, 0, tzinfo=UTC)


def _bi5(*records) -> bytes:
    return lzma.compress(b"".join(RECORD.pack(*r) for r in records), format=lzma.FORMAT_ALONE)


def test_real_dukascopy_hour_decodes_to_the_verified_ticks() -> None:
    ticks = list(decode(FIXTURE.read_bytes(), "EUR_USD", HOUR))
    assert len(ticks) == 740
    assert ticks[0].ts == datetime(2025, 12, 31, 0, 0, 0, 164000, tzinfo=UTC)
    assert (ticks[0].ask, ticks[0].bid) == (1.17459, 1.17455)
    assert ticks[0].ask_volume == pytest.approx(0.12) and ticks[0].bid_volume == pytest.approx(0.9)
    assert ticks[-1].ts == datetime(2025, 12, 31, 0, 59, 40, 754000, tzinfo=UTC)
    assert (ticks[-1].ask, ticks[-1].bid) == (1.17474, 1.1747)
    assert all(a.ts <= b.ts for a, b in zip(ticks, ticks[1:]))


def test_jpy_scale_and_daily_offsets() -> None:
    day = datetime(2020, 6, 1, tzinfo=UTC)
    t = list(decode(_bi5((3_600_000, 107_523, 107_520, 1.0, 2.0)), "USD_JPY", day))[0]
    assert (t.ask, t.bid, t.ts) == (107.523, 107.52, datetime(2020, 6, 1, 1, tzinfo=UTC))


def test_empty_file_is_no_ticks() -> None:
    assert list(decode(b"", "EUR_USD", HOUR)) == []


@pytest.mark.parametrize("raw", [
    b"not an lzma stream",                                   # bad LZMA
    lzma.compress(b"x" * 21, format=lzma.FORMAT_ALONE),      # torn record (21 ≠ k·20)
])
def test_untrustworthy_files_raise(raw) -> None:
    with pytest.raises(Bi5Error):
        list(decode(raw, "EUR_USD", HOUR))


@pytest.mark.parametrize("instrument, wrong_scale, raw_price", [
    ("EUR_USD", 1_000, 117_459),       # FX read with the JPY scale → 117.46
    ("USD_JPY", 100_000, 107_520),     # JPY read with the FX scale → 1.08
    ("XAU_USD", 100, 1_600_000),       # gold read 10× too coarse → 16 000
])
def test_a_wrong_point_scale_fails_loudly_not_silently(monkeypatch, instrument, wrong_scale,
                                                       raw_price) -> None:
    """Dukascopy: a wrong scale 'will produce wrong prices with no error raised' — the
    PLAUSIBLE envelope turns that silent corruption into an error."""
    from tests.backtest import bi5
    monkeypatch.setitem(bi5.SYMBOLS, instrument, (bi5.SYMBOLS[instrument][0], wrong_scale))
    with pytest.raises(Bi5Error, match="point scale"):
        list(decode(_bi5((0, raw_price, raw_price - 5, 1.0, 1.0)), instrument, HOUR))
