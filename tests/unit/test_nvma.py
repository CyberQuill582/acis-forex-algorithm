"""NVMA classification + veto provability (ACIS-02 §14, postcondition style)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from core.data.normaliser import MarketState, deep_freeze
from core.regime.nvma import NVMA, NVMAEngine, RegimeInputWindow
from core.regime.regime_types import RegimeType, VolClass

T0 = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)


def mk_state(mid=1.1, spread=0.0002, session="london", macro=False, velocity=10.0,
             stale=False, instrument="EUR_USD", ts=T0) -> MarketState:
    bid, ask = mid - spread / 2.0, mid + spread / 2.0
    return MarketState(
        timestamp=ts, instrument=instrument, bid=bid, ask=ask, spread=ask - bid,
        mid=(bid + ask) / 2.0, volume=1.0,
        order_book_depth=deep_freeze({"bids": (), "asks": ()}),
        tick_velocity=velocity, session=session, macro_events_imminent=macro,
        ingest_ts=ts, is_stale=stale, raw=deep_freeze({}),
    )


def fill_window(cfg, mids, spread=0.0002, velocity=10.0) -> RegimeInputWindow:
    window = RegimeInputWindow(maxlen=cfg.max_lookback)
    window.mids.extend(mids[-cfg.max_lookback:])
    window.spreads.extend([spread] * len(window.mids))
    window.velocities.extend([velocity] * len(window.mids))
    return window


def make_nvma(cfg, *, med_spread=0.0002, med_velocity=10.0, tierg=False, has_params=True) -> NVMA:
    return NVMA(
        cfg=cfg,
        session_median=lambda inst, sess, kind: med_spread if kind == "spread" else med_velocity,
        tierg_shock=lambda inst, ts: tierg,
        has_params_for=lambda regime: has_params,
    )


@pytest.fixture()
def cfg(acis_config):
    return acis_config.system.regime


# ---------------- synthetic fixture generators (one per regime) ---------------- #

def series_strong_trend(n, sign=+1):
    return [1.1 + sign * i * 1e-4 + ((-1) ** i) * 1e-6 for i in range(n)]


def series_weak_trend(n, sign=+1):
    mids, level = [], 1.1
    for i in range(n):
        level += sign * (8e-4 if i % 2 == 0 else -5e-4)
        mids.append(level)
    return mids


def series_mean_reverting(n):
    return [1.1 + (2e-4 if i % 2 == 0 else -2e-4) for i in range(n)]


def series_squeeze(n):
    mids = []
    for i in range(n):
        amplitude = 2e-4 * (1.0 - 0.95 * i / n)  # strictly contracting range
        mids.append(1.1 + (amplitude if i % 2 == 0 else -amplitude))
    return mids


def series_post_breakout(n):
    quiet = [1.1 + (0.3e-4 if i % 2 == 0 else -0.3e-4) for i in range(n - 30)]
    burst_base = quiet[-1]
    burst = [burst_base + (4e-4 if i % 2 == 0 else -4e-4) for i in range(30)]
    return quiet + burst


def series_ranging(n, late_scale):
    # GAP-0070 re-tune: the old zigzag+reflecting-walk was anti-persistent
    # (repaired-estimator H ~0.26-0.34 < the 0.35 mean-rev gate) — a genuinely
    # RANGING series must walk, not oscillate. Walk-dominated Gaussian steps
    # with a late volatility scale; per-branch seeds empirically tuned against
    # the REAL classifier (phase-3 precedent): late_scale<1 -> seed 19
    # (RANGING_TIGHT: H .457, adx 8.8, bb .16, conf .75); >=1 -> seed 8
    # (RANGING_WIDE: H .401, adx 17.7, bb .90, conf .60). Deterministic.
    rng = random.Random(19 if late_scale < 1.0 else 8)
    mids, x = [], 0.0
    for i in range(n):
        scale = 1.0 if i < n * 0.6 else late_scale
        x += rng.gauss(0, 1.5e-4) * scale
        mids.append(1.1 + x)
    return mids


class TestTwelveRegimes:
    def test_strong_trend_up_and_down(self, cfg) -> None:
        nvma = make_nvma(cfg)
        n = cfg.max_lookback
        up = nvma.classify(mk_state(), fill_window(cfg, series_strong_trend(n, +1)))
        assert up.regime is RegimeType.STRONG_TREND_UP and up.trend_direction == 1
        assert up.tradeable is True
        down = nvma.classify(mk_state(), fill_window(cfg, series_strong_trend(n, -1)))
        assert down.regime is RegimeType.STRONG_TREND_DOWN and down.trend_direction == -1

    def test_weak_trend_up_and_down(self, cfg) -> None:
        nvma = make_nvma(cfg)
        n = cfg.max_lookback
        up = nvma.classify(mk_state(), fill_window(cfg, series_weak_trend(n, +1)))
        assert up.regime is RegimeType.WEAK_TREND_UP and up.trend_direction == 1
        down = nvma.classify(mk_state(), fill_window(cfg, series_weak_trend(n, -1)))
        assert down.regime is RegimeType.WEAK_TREND_DOWN and down.trend_direction == -1

    def test_mean_reverting(self, cfg) -> None:
        nvma = make_nvma(cfg)
        ctx = nvma.classify(mk_state(), fill_window(cfg, series_mean_reverting(cfg.max_lookback)))
        assert ctx.regime is RegimeType.MEAN_REVERTING
        assert ctx.inputs_snapshot["hurst"] < cfg.hurst_meanrev

    def test_breakout_imminent_on_squeeze(self, cfg) -> None:
        nvma = make_nvma(cfg)
        ctx = nvma.classify(mk_state(), fill_window(cfg, series_squeeze(cfg.max_lookback)))
        assert ctx.regime is RegimeType.BREAKOUT_IMMINENT
        assert ctx.inputs_snapshot["bb_pct"] <= cfg.bb_squeeze_pct

    def test_post_breakout_on_release(self, cfg) -> None:
        nvma = make_nvma(cfg)
        ctx = nvma.classify(mk_state(), fill_window(cfg, series_post_breakout(cfg.max_lookback)))
        assert ctx.regime is RegimeType.POST_BREAKOUT
        assert ctx.volatility_class in (VolClass.HIGH, VolClass.EXTREME)

    def test_ranging_tight_and_wide(self, cfg) -> None:
        nvma = make_nvma(cfg)
        tight = nvma.classify(mk_state(), fill_window(cfg, series_ranging(cfg.max_lookback, 0.45)))
        assert tight.regime is RegimeType.RANGING_TIGHT
        wide = nvma.classify(mk_state(), fill_window(cfg, series_ranging(cfg.max_lookback, 1.15)))
        assert wide.regime is RegimeType.RANGING_WIDE

    def test_macro_event_from_flag_and_from_tierg(self, cfg) -> None:
        n = cfg.max_lookback
        by_flag = make_nvma(cfg).classify(
            mk_state(macro=True), fill_window(cfg, series_strong_trend(n)))
        assert by_flag.regime is RegimeType.MACRO_EVENT and by_flag.tradeable is False
        by_tierg = make_nvma(cfg, tierg=True).classify(
            mk_state(), fill_window(cfg, series_strong_trend(n)))
        assert by_tierg.regime is RegimeType.MACRO_EVENT and by_tierg.tradeable is False

    def test_illiquid_on_spread_blowout_and_closed_session(self, cfg) -> None:
        # GAP-0028: the ILLIQUID baseline is the SESSION median (one baseline
        # with the veto rules), sigma from window dispersion.
        nvma = make_nvma(cfg)  # session median spread 0.0002; window spreads constant
        window = fill_window(cfg, series_strong_trend(cfg.max_lookback))
        blowout = nvma.classify(mk_state(spread=0.005), window)
        assert blowout.regime is RegimeType.ILLIQUID and blowout.tradeable is False
        assert blowout.inputs_snapshot["session_median_spread"] == 0.0002
        closed = make_nvma(cfg).classify(
            mk_state(session="closed"), fill_window(cfg, series_strong_trend(cfg.max_lookback)))
        assert closed.regime is RegimeType.ILLIQUID and closed.tradeable is False

    def test_unclassified_when_window_short(self, cfg) -> None:
        nvma = make_nvma(cfg)
        window = fill_window(cfg, series_strong_trend(50))
        ctx = nvma.classify(mk_state(), window)
        assert ctx.regime is RegimeType.UNCLASSIFIED and ctx.tradeable is False
        assert "REGIME_WARMING" in ctx.inputs_snapshot["veto_reasons"]

    def test_unclassified_on_nan_indicator(self, cfg) -> None:
        nvma = make_nvma(cfg)
        flat = [1.1] * cfg.max_lookback  # zero variance => Hurst undefined
        ctx = nvma.classify(mk_state(), fill_window(cfg, flat))
        assert ctx.regime is RegimeType.UNCLASSIFIED and ctx.tradeable is False
        assert "INDICATOR_NAN" in ctx.inputs_snapshot["veto_reasons"]


class TestVetoes:
    def test_median_warmup_vetoes(self, cfg) -> None:
        nvma = make_nvma(cfg, med_spread=None)  # session median not warm (C-REG-2)
        ctx = nvma.classify(mk_state(), fill_window(cfg, series_strong_trend(cfg.max_lookback)))
        assert ctx.tradeable is False and ctx.regime is RegimeType.UNCLASSIFIED

    def test_stale_state_vetoes_but_still_classifies(self, cfg) -> None:
        nvma = make_nvma(cfg)
        ctx = nvma.classify(mk_state(stale=True),
                            fill_window(cfg, series_strong_trend(cfg.max_lookback)))
        assert ctx.regime is RegimeType.STRONG_TREND_UP
        assert ctx.tradeable is False
        assert "STALE_STATE" in ctx.inputs_snapshot["veto_reasons"]

    def test_spread_veto_strictly_beyond_3x_median(self, cfg) -> None:
        window = RegimeInputWindow(maxlen=cfg.max_lookback)
        mids = series_strong_trend(cfg.max_lookback)
        window.mids.extend(mids)
        window.spreads.extend([0.0004 if i % 2 == 0 else 0.0008 for i in range(len(mids))])
        window.velocities.extend([10.0] * len(mids))
        nvma = make_nvma(cfg)  # session median spread = 0.0002 => veto above 0.0006
        at_limit = nvma.classify(mk_state(spread=0.0006), window)
        assert "SPREAD_VETO" not in at_limit.inputs_snapshot["veto_reasons"]
        beyond = nvma.classify(mk_state(spread=0.00065), window)
        assert "SPREAD_VETO" in beyond.inputs_snapshot["veto_reasons"]
        assert beyond.tradeable is False

    def test_dead_market_veto_below_half_median_velocity(self, cfg) -> None:
        nvma = make_nvma(cfg)  # median velocity 10 => veto strictly below 5
        window = fill_window(cfg, series_strong_trend(cfg.max_lookback))
        alive = nvma.classify(mk_state(velocity=5.0), window)
        assert "DEAD_MARKET" not in alive.inputs_snapshot["veto_reasons"]
        dead = nvma.classify(mk_state(velocity=4.9), window)
        assert "DEAD_MARKET" in dead.inputs_snapshot["veto_reasons"]
        assert dead.tradeable is False

    def test_no_params_for_regime_vetoes(self, cfg) -> None:
        nvma = make_nvma(cfg, has_params=False)
        ctx = nvma.classify(mk_state(), fill_window(cfg, series_strong_trend(cfg.max_lookback)))
        assert ctx.regime is RegimeType.STRONG_TREND_UP
        assert ctx.tradeable is False
        assert "NO_PARAMS_FOR_REGIME" in ctx.inputs_snapshot["veto_reasons"]


class TestDeterminismAndShift:
    def test_identical_inputs_identical_pure_fields_same_classifier(self, cfg) -> None:
        # C-REG-5 scoped per GAP-0032: on the SAME classifier, the pure fields
        # are functions of (state, window, config); stability/half-life are
        # declared historical aggregates and are exempted BY DOCUMENTATION,
        # not by test omission.
        mids = series_strong_trend(cfg.max_lookback)
        nvma = make_nvma(cfg)
        pure = lambda c: (c.regime, c.trend_direction, c.volatility_class,  # noqa: E731
                          c.liquidity_state, c.tradeable, c.confidence,
                          dict(c.inputs_snapshot))
        a = nvma.classify(mk_state(), fill_window(cfg, mids))
        b = nvma.classify(mk_state(), fill_window(cfg, mids))
        assert pure(a) == pure(b)

    def test_warmup_never_dilutes_stability(self, cfg) -> None:
        # GAP-0031: gate-states are not recorded; the first classifiable
        # regime after 20 UNCLASSIFIED warm-ups reports full stability.
        nvma = make_nvma(cfg)
        short = fill_window(cfg, series_strong_trend(50))
        for _ in range(20):
            warming = nvma.classify(mk_state(), short)
            assert warming.regime is RegimeType.UNCLASSIFIED
            assert warming.regime_stability_score == 0.0
        clean = nvma.classify(mk_state(), fill_window(cfg, series_strong_trend(cfg.max_lookback)))
        assert clean.regime is RegimeType.STRONG_TREND_UP
        assert clean.regime_stability_score == 1.0

    def test_engine_logs_shift_and_notifies_param_library(self, cfg, tmp_path) -> None:
        import json

        from core.data.jsonl_logging import JsonlEventLogger

        log_path = tmp_path / "regime_log.jsonl"
        notified: list[tuple[str, RegimeType]] = []
        engine = NVMAEngine(
            make_nvma(cfg), cfg,
            JsonlEventLogger(log_path, layer="regime", session_id="rtest"),
            notify_shift=lambda inst, regime: notified.append((inst, regime)),
        )
        for mid in series_strong_trend(cfg.max_lookback):
            engine.observe(mk_state(mid=mid))
        first = engine.classify(mk_state())
        assert first.regime is RegimeType.STRONG_TREND_UP
        shifted = engine.classify(mk_state(macro=True, ts=T0 + timedelta(minutes=2)))
        assert shifted.regime is RegimeType.MACRO_EVENT
        assert notified == [("EUR_USD", RegimeType.MACRO_EVENT)]
        events = [json.loads(l) for l in log_path.read_text().strip().splitlines()]
        shifts = [e for e in events if e["event_type"] == "REGIME_SHIFT"]
        assert len(shifts) == 1
        assert shifts[0]["data"]["from_regime"] == "STRONG_TREND_UP"
        assert engine.regime_store["EUR_USD"].regime is RegimeType.MACRO_EVENT
