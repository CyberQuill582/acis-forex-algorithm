"""Walk-forward fold generation (ACIS-09 §5/§6, master §13).

Rolling `(train, test)` folds: QIEA evolves on `train`, freezes, the engine
trades `test`; the concatenated `test` folds are the graded out-of-sample record.
A single split (one fold) can NEVER pass (C-BT-2) — walk-forward is mandatory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator


@dataclass(frozen=True)
class Fold:
    index: int
    train_start: datetime
    train_end: datetime          # exclusive; test_start = train_end + embargo
    test_start: datetime
    test_end: datetime

    def __post_init__(self) -> None:
        """GAP-P12D-24 (F-I4): a fold is ordered or it does not exist."""
        stamps = (self.train_start, self.train_end, self.test_start, self.test_end)
        if any(t.tzinfo is None for t in stamps):
            raise ValueError("fold dates must be tz-aware")
        if not (self.train_start < self.train_end <= self.test_start < self.test_end):
            raise ValueError(f"fold {self.index}: need train_start < train_end <= test_start < test_end")


def generate_folds(*, period_start: datetime, period_end: datetime,
                   train_window: timedelta, test_window: timedelta,
                   step: timedelta, embargo: timedelta) -> list[Fold]:
    """Rolling folds across [period_start, period_end). Each fold trains on
    `train_window`, skips `embargo`, then tests the following `test_window`; the window
    advances by `step`. Only folds whose test window fits inside the period are emitted.

    GAP-SP12E-03 (López de Prado's purge/embargo): a trade opened near the end of training
    can run into the test window, so its outcome leaks test prices into what training saw.
    The embargo must be at least the maximum holding time; `require_embargo` checks that on
    the real data inside the harness."""
    if train_window <= timedelta(0) or test_window <= timedelta(0) or step <= timedelta(0):
        raise ValueError("walk-forward windows and step must be positive")
    if embargo < timedelta(0):
        raise ValueError("embargo must be >= 0")
    # GAP-P11E-06: standard walk-forward uses NON-OVERLAPPING test windows; a
    # step smaller than the test window would replay overlapping OOS periods and
    # double-count them in the concatenated record.
    if step < test_window:
        raise ValueError(
            "walk_forward_step must be >= test_window (non-overlapping OOS folds)")
    folds: list[Fold] = []
    train_start = period_start
    i = 0
    while True:
        train_end = train_start + train_window
        test_start = train_end + embargo
        test_end = test_start + test_window
        if test_end > period_end:
            break
        folds.append(Fold(i, train_start, train_end, test_start, test_end))
        train_start = train_start + step
        i += 1
    return folds


def require_embargo(index: int, last_train: datetime, first_test: datetime,
                    max_hold_s: float) -> None:
    """Refuse a fold whose real train→test data gap is shorter than the maximum hold."""
    gap = (first_test - last_train).total_seconds()
    if gap < max_hold_s:
        raise ValueError(f"fold {index}: train→test gap {gap:.0f} s is shorter than the "
                         f"{max_hold_s:.0f} s max hold — an embargo is required (GAP-SP12E-03)")
