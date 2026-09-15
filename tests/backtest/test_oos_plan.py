"""The ratified walk-forward plan and the once-only holdout (OOS_VALIDATION.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.backtest.oos_plan import (HOLDOUT_START, HoldoutGuard, HoldoutLockedError,
                                     plan_folds)

UTC = timezone.utc


def test_the_development_plan_is_ten_embargoed_calendar_folds(tmp_path) -> None:
    folds = plan_folds(2014, 2023)
    assert len(folds) == 10
    f0 = folds[0]
    assert (f0.train_start, f0.train_end) == (datetime(2012, 1, 1, tzinfo=UTC), datetime(2014, 1, 1, tzinfo=UTC))
    assert (f0.test_start, f0.test_end) == (datetime(2014, 1, 8, tzinfo=UTC), datetime(2015, 1, 1, tzinfo=UTC))
    assert all(a.test_end <= b.test_start for a, b in zip(folds, folds[1:]))   # no OOS overlap
    assert all(f.test_start - f.train_end == timedelta(days=7) for f in folds)
    assert folds[-1].test_end == HOLDOUT_START
    HoldoutGuard(tmp_path / "marker.json").check_development(folds)


def test_development_may_not_touch_the_holdout(tmp_path) -> None:
    with pytest.raises(HoldoutLockedError):
        HoldoutGuard(tmp_path / "marker.json").check_development(plan_folds(2014, 2024))


def test_training_before_the_data_starts_is_refused() -> None:
    with pytest.raises(ValueError, match="data start"):
        plan_folds(2013, 2014)


def test_a_fold_must_be_ordered() -> None:
    from tests.backtest.walk_forward import Fold
    t = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="train_start < train_end"):
        Fold(0, t, t + timedelta(days=1), t, t + timedelta(days=2))      # test starts before train ends
    with pytest.raises(ValueError, match="tz-aware"):
        Fold(0, datetime(2020, 1, 1), datetime(2020, 2, 1), datetime(2020, 2, 1), datetime(2020, 3, 1))


def test_the_holdout_is_graded_once(tmp_path) -> None:
    guard = HoldoutGuard(tmp_path / "validation" / "holdout_graded.json")
    with pytest.raises(ValueError):
        guard.begin_final(plan_folds(2022, 2023), config_hash="h")      # not the holdout
    with pytest.raises(ValueError):
        guard.begin_final(plan_folds(2024, 2024), config_hash="h")      # malformed: half the holdout
    assert not guard.final_started()                                    # neither burned the grade
    guard.begin_final(plan_folds(2024, 2025), config_hash="h")
    assert guard.final_started()
    with pytest.raises(HoldoutLockedError, match="graded once"):
        HoldoutGuard(tmp_path / "validation" / "holdout_graded.json").begin_final(
            plan_folds(2024, 2025), config_hash="h")
