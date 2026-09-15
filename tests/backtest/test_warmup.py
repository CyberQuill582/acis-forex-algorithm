"""Cold-start warm-up (GAP-P12D-24 F-E3): TSMOM history rebuilt from bars before the train end."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.optimizer.param_types import LabelledBar
from core.regime.regime_types import RegimeType
from tests.backtest.warmup import daily_closes, seed_tsmom
from tests.integration.test_paper_trading_pipeline import flat_portfolio, make_loop

UTC = timezone.utc


def _bar(ts: datetime, close: float) -> LabelledBar:
    return LabelledBar(ts=ts, open=close, high=close, low=close, close=close, spread=0.0001,
                       regime=RegimeType.RANGING_TIGHT)


def test_one_close_per_fx_trading_day_and_nothing_after_the_end() -> None:
    bars = [_bar(datetime(2025, 1, 7, 21, 58, tzinfo=UTC), 1.01),   # Tue 16:58 EST → Tue's day
            _bar(datetime(2025, 1, 7, 21, 59, tzinfo=UTC), 1.02),   # Tue's last bar (closes 17:00)
            _bar(datetime(2025, 1, 7, 22, 0, tzinfo=UTC), 1.03),    # 17:00 EST → Wednesday's day
            _bar(datetime(2025, 1, 8, 10, 0, tzinfo=UTC), 1.04),
            _bar(datetime(2025, 1, 8, 10, 1, tzinfo=UTC), 1.05)]    # closes 10:02, after the end
    closes = daily_closes(bars, end=datetime(2025, 1, 8, 10, 1, 30, tzinfo=UTC), bar_seconds=60)
    assert closes == [(date(2025, 1, 6), 1.02), (date(2025, 1, 7), 1.04)]   # labelled by opening rollover


def test_seeding_gives_tsmom_its_full_history(tmp_path, acis_config, factory) -> None:
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    start = datetime(2013, 1, 7, 12, tzinfo=UTC)
    bars = [_bar(start + timedelta(days=i), 1.0 + 0.001 * i) for i in range(400)]
    closes = daily_closes(bars, end=start + timedelta(days=400), bar_seconds=60)
    seeded = seed_tsmom(loop.agon, "USD_JPY", closes)
    need = acis_config.system.signals.tsmom_min_history_days
    assert seeded == len(closes) >= need
    assert len(loop.agon._daily_bars["USD_JPY"]) >= need
