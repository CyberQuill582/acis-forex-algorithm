"""R1.6's forecast (ACIS-04 v1.6 §4b): the `Forecast` contract, the excess-return price, and D1 at the
last decision equal to what RSIM grades on the same prices (parity, B0(d))."""

from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pytest

from core.data.errors import DataQualityError
from core.signals import rules
from core.signals.forecast import D1_FAMILY, Forecast, d1_forecast, excess_prices
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.rsim import panel
from tests.backtest.rsim_lab import carver_pct_vol, lab_market

NOW = datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 2)


def test_a_forecast_validates_its_contract() -> None:
    ok = dict(instrument="EUR_USD", value=12.0, family_ids=(D1_FAMILY,), decision_day=DAY, decided_at=NOW,
              price_basis=1.16, pct_vol=0.004, inputs_hash="a" * 64)
    Forecast(**ok)
    for bad in (dict(value=20.5), dict(value=float("nan")), dict(family_ids=()), dict(price_basis=0.0),
                dict(pct_vol=0.0), dict(decided_at=NOW.replace(tzinfo=None)), dict(inputs_hash="x")):
        with pytest.raises(DataQualityError):
            Forecast(**{**ok, **bad})


def test_the_excess_price_compounds_each_move_with_its_rollover() -> None:
    assert excess_prices([1.0, 1.1, 1.1], [0.0, 0.0, 0.01]) == pytest.approx([1.0, 1.1, 1.111])
    with pytest.raises(DataQualityError):
        excess_prices([1.0, 0.0], [0.0, 0.0])


def test_d1_at_the_last_decision_equals_what_rsim_grades_and_warm_up_gives_none() -> None:
    m = lab_market(generate(LabSpec(n_inst=2, days=700, seed=9, effect=Effect(trend_sharpe=1.0))))
    price = m.price[:, 0]
    closes = list(price)                                   # zero carry: the excess price is the close path
    f = d1_forecast("LAB0", closes, [0.0] * len(closes), decision_day=DAY, decided_at=NOW)
    assert f is not None and f.family_ids == (D1_FAMILY,)
    assert f.value == pytest.approx(panel(m, rules.d1)[-1, 0])
    assert f.pct_vol == pytest.approx(carver_pct_vol(m)[-1, 0])
    assert f.inputs_hash == d1_forecast("LAB0", closes, [0.0] * len(closes), decision_day=DAY, decided_at=NOW).inputs_hash
    assert d1_forecast("LAB0", closes[:260], [0.0] * 260, decision_day=DAY, decided_at=NOW) is None   # RSIM's warm-up
    assert d1_forecast("LAB0", closes[:261], [0.0] * 261, decision_day=DAY, decided_at=NOW) is not None
    assert not np.isnan(f.value)
