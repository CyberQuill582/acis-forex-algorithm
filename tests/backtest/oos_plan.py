"""The ratified walk-forward plan and the locked holdout (OOS_VALIDATION.md, owner-ratified 2026-07-21).

Invariants:
  * Folds are calendar years. The fold testing year Y trains on the `train_years` before
    1 January Y and tests from `embargo` after that date to the end of Y (the 7-day embargo
    is longer than the 48 h max hold, GAP-SP12E-03). Test years never overlap, so the
    concatenated out-of-sample record counts each day once.
  * The development plan tests 2014–2023. No development fold may train on or test a day
    of the locked holdout, 2024-01-01 → 2026-01-01.
  * The holdout is graded ONCE: the final run writes a marker (exclusive create) before it
    starts, and a second final run is refused. No code path deletes the marker.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from tests.backtest.walk_forward import Fold

UTC = timezone.utc
DATA_START = datetime(2012, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_END = datetime(2026, 1, 1, tzinfo=UTC)
TRAIN_YEARS = 2
EMBARGO = timedelta(days=7)


class HoldoutLockedError(Exception):
    """A run would touch the locked holdout, or grade it a second time."""


def plan_folds(first_test_year: int, last_test_year: int, *, train_years: int = TRAIN_YEARS,
               embargo: timedelta = EMBARGO) -> list[Fold]:
    if last_test_year < first_test_year:
        raise ValueError("last_test_year must be >= first_test_year")
    folds = []
    for i, year in enumerate(range(first_test_year, last_test_year + 1)):
        jan1 = datetime(year, 1, 1, tzinfo=UTC)
        folds.append(Fold(i, datetime(year - train_years, 1, 1, tzinfo=UTC), jan1,
                          jan1 + embargo, datetime(year + 1, 1, 1, tzinfo=UTC)))
    if folds[0].train_start < DATA_START:
        raise ValueError(f"fold 0 would train from {folds[0].train_start.date()}, before the "
                         f"data start {DATA_START.date()}")
    return folds


class HoldoutGuard:
    def __init__(self, marker: Path) -> None:
        self._marker = Path(marker)

    def final_started(self) -> bool:
        return self._marker.exists()

    def check_development(self, folds: Sequence[Fold]) -> None:
        for f in folds:
            if f.test_end > HOLDOUT_START or f.train_end > HOLDOUT_START:
                raise HoldoutLockedError(
                    f"fold {f.index} reaches into the locked holdout ({HOLDOUT_START.date()} → "
                    f"{HOLDOUT_END.date()}); it is graded once, by the final run only")

    def begin_final(self, folds: Sequence[Fold], *, config_hash: str) -> None:
        if not folds or any(f.test_start < HOLDOUT_START or f.test_end > HOLDOUT_END for f in folds):
            raise ValueError("the final run must test only inside the holdout window")
        self._marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._marker.open("x", encoding="utf-8") as f:
                json.dump({"started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                           "config_hash": config_hash,
                           "folds": [[x.test_start.isoformat(), x.test_end.isoformat()] for x in folds]},
                          f)
        except FileExistsError:
            raise HoldoutLockedError(f"the holdout was already graded (marker {self._marker}); "
                                     "it is graded once") from None
