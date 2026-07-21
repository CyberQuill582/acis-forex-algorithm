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
    train_end: datetime          # == test_start (exclusive boundary)
    test_start: datetime
    test_end: datetime


def generate_folds(*, period_start: datetime, period_end: datetime,
                   train_window: timedelta, test_window: timedelta,
                   step: timedelta) -> list[Fold]:
    """Rolling folds across [period_start, period_end). Each fold trains on
    `train_window` then tests the following `test_window`; the window advances by
    `step`. Only folds whose test window fits inside the period are emitted."""
    if train_window <= timedelta(0) or test_window <= timedelta(0) or step <= timedelta(0):
        raise ValueError("walk-forward windows and step must be positive")
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
        test_start = train_end
        test_end = test_start + test_window
        if test_end > period_end:
            break
        folds.append(Fold(i, train_start, train_end, test_start, test_end))
        train_start = train_start + step
        i += 1
    return folds
