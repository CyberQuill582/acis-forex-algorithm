"""Phase-4 integration: evolve -> stage -> stall -> restart -> promote -> NVMA gate
(ACIS-03 §14 integration contract, jointly with ACIS-02)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.optimizer.param_library import ParamLibrary
from core.optimizer.qiea import QIEA
from core.regime.nvma import NVMA
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import T0, TEST_COSTS, CapturingLogger, opt_cfg, zigzag_history
from tests.unit.test_nvma import fill_window, mk_state, series_strong_trend

BOUNDARY_0 = datetime(2026, 7, 6, 22, 0, tzinfo=timezone.utc)


class FakeGate:
    def __init__(self, count: int) -> None:
        self.count = count

    def open_position_count(self) -> int:
        return self.count


@pytest.fixture()
def regime_cfg(acis_config):
    return acis_config.system.regime


def make_nvma(cfg, lib: ParamLibrary) -> NVMA:
    return NVMA(
        cfg=cfg,
        session_median=lambda inst, sess, kind: 0.0002 if kind == "spread" else 10.0,
        tierg_shock=lambda inst, ts: False,
        has_params_for=lib.has_active,  # the real phase-4 wiring (ACIS-03 §7.5)
    )


def test_full_promotion_cycle_with_stall_restart_and_nvma_gate(tmp_path, acis_config) -> None:
    cfg = acis_config.system.regime
    log = CapturingLogger()
    gate = FakeGate(1)
    db = tmp_path / "params.db"
    boundaries = acis_config.system.session_boundaries_utc
    lib = ParamLibrary(db, boundaries, acis_config.system.param_stall_alert_boundaries, gate, log)
    nvma = make_nvma(cfg, lib)

    # 1. Strong trend, but no evolved params for the regime => tradeable=False (ACIS-02).
    window = fill_window(cfg, series_strong_trend(cfg.max_lookback))
    ctx = nvma.classify(mk_state(), window)
    assert ctx.regime is RegimeType.STRONG_TREND_UP
    assert ctx.tradeable is False

    # 2. QIEA evolves offline and stages — active stays empty (write-only-to-pending).
    qiea = QIEA(opt_cfg(), TEST_COSTS, log)
    champion = qiea.evolve(RegimeType.STRONG_TREND_UP, zigzag_history(500), seed=42, now=T0)
    assert champion is not None
    lib.stage(champion, now=BOUNDARY_0 - timedelta(hours=2))
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None

    # 3. Open position across 3 boundaries: zero promotions, stall counted + surfaced.
    for day in range(3):
        assert lib.on_boundary(BOUNDARY_0 + timedelta(days=day)) == []
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None
    snap = lib.pending_snapshot()[0]
    assert snap["boundaries_skipped"] == 3 and snap["stalled"] is True

    # 4. Restart mid-pending: the stall state survives (transaction/restart safety).
    lib.close()
    lib2 = ParamLibrary(db, boundaries, acis_config.system.param_stall_alert_boundaries, gate, log)
    entry = lib2.get_pending(RegimeType.STRONG_TREND_UP)[0]
    assert entry.boundaries_skipped == 3
    assert entry.params == champion

    # 5. Flat at the 4th boundary: exactly one promotion; store postconditions hold.
    gate.count = 0
    promoted = lib2.on_boundary(BOUNDARY_0 + timedelta(days=3))
    assert promoted == [RegimeType.STRONG_TREND_UP.value]
    assert lib2.get_pending() == []
    active = lib2.get_active(RegimeType.STRONG_TREND_UP)
    assert active is not None and active.params == champion
    assert len(log.events("PARAM_PROMOTED")) == 1

    # 6. The same NVMA condition is now tradeable — the regime gate opened via promotion.
    nvma2 = make_nvma(cfg, lib2)
    ctx2 = nvma2.classify(mk_state(), window)
    assert ctx2.regime is RegimeType.STRONG_TREND_UP
    assert ctx2.tradeable is True
    lib2.close()
