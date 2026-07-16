"""Data-layer error taxonomy (ACIS-01 §12)."""

from __future__ import annotations


class DataQualityError(Exception):
    """A tick failed validation — rejected, logged, never coerced (SPEC §3)."""

    def __init__(self, field: str, value: object, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"{field}={value!r}: {reason}")


class FeedAuthError(Exception):
    """Boot-time feed authentication failure — fatal, refuse to start."""
