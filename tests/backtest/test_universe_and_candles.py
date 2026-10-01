"""The R1 research universe (R1-D5) and the hourly-candle decoder (R1.5)."""

from __future__ import annotations

import hashlib
import lzma
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.backtest.candles import CandleError, decode_month
from tests.backtest.universe import BY_NAME, EXPLORED, HELD_OUT, UNIVERSE

FIXTURE = Path(__file__).parent / "fixtures" / "EURUSD_2025-12_BID_candles_hour_1.bi5"


def test_the_universe_is_the_ratified_thirty() -> None:
    classes = {}
    for i in UNIVERSE:
        classes[i.asset_class] = classes.get(i.asset_class, 0) + 1
    assert len(UNIVERSE) == 30 and classes == {"fx": 16, "metal": 3, "index": 8, "energy": 3}
    assert all(i.first <= "2013-12" for i in UNIVERSE)                      # history from <= 2013
    assert len(EXPLORED) == 23


def _spelling(i) -> str:
    if i.asset_class in ("fx", "metal"):
        return i.name.replace("_", "/")
    return {"UKOIL": "UKOIL", "NATGAS": "NATGAS", "USOIL": "USOIL"}.get(i.name, i.name)


def test_the_held_out_seven_are_the_salted_draw() -> None:
    """OOS_VALIDATION.md: sort each class by sha256("ACIS-R1-holdout-2026-09-25|" + symbol), hold out
    the first k (FX 3, metal 1, index 2, energy 1), the 8 on-disk instruments forced explored."""
    on_disk = {"EUR_USD", "GBP_USD", "AUD_USD", "USD_CHF", "USD_CAD", "EUR_GBP", "USD_JPY", "XAU_USD"}
    drawn = set()
    for cls, k in (("fx", 3), ("metal", 1), ("index", 2), ("energy", 1)):
        pool = [i for i in UNIVERSE if i.asset_class == cls and i.name not in on_disk]
        pool.sort(key=lambda i: hashlib.sha256(f"ACIS-R1-holdout-2026-09-25|{_spelling(i)}".encode()).hexdigest())
        drawn |= {i.name for i in pool[:k]}
    assert drawn == HELD_OUT == {"AUD_NZD", "NZD_USD", "CAD_JPY", "XCU_USD", "GER40", "US100", "USOIL"}


def test_a_real_archive_month_decodes_every_hour_in_order() -> None:
    c = decode_month(FIXTURE.read_bytes(), "EUR_USD", 2025, 12)
    assert len(c) == 31 * 24 and c[0].ts == datetime(2025, 12, 1, tzinfo=timezone.utc)
    assert (c[0].open, c[0].close, c[0].low, c[0].high) == (1.16011, 1.16031, 1.15975, 1.1607)
    assert all(x.low <= min(x.open, x.close) <= max(x.open, x.close) <= x.high for x in c)


def _month(rows) -> bytes:
    return lzma.compress(b"".join(struct.pack(">IIIIIf", *r) for r in rows), format=lzma.FORMAT_ALONE)


def test_a_wrong_scale_a_missing_hour_or_disordered_ohlc_is_refused() -> None:
    hours = 30 * 24                                                           # November
    good = [(k * 3600, 116000, 116010, 115990, 116020, 1.0) for k in range(hours)]
    assert len(decode_month(_month(good), "EUR_USD", 2025, 11)) == hours
    with pytest.raises(CandleError, match="scale"):
        decode_month(_month([(s, o * 10, c * 10, l * 10, h * 10, v) for s, o, c, l, h, v in good]), "EUR_USD", 2025, 11)
    with pytest.raises(CandleError, match="hourly candles"):
        decode_month(_month(good[:-1]), "EUR_USD", 2025, 11)
    with pytest.raises(CandleError, match="out of order"):
        decode_month(_month([good[0][:3] + (116020, 115990, 1.0)] + good[1:]), "EUR_USD", 2025, 11)
    with pytest.raises(CandleError, match="LZMA"):
        decode_month(b"not lzma", "EUR_USD", 2025, 11)
    assert BY_NAME["US500"].scale == 1000 and BY_NAME["XCU_USD"].scale == 10_000
