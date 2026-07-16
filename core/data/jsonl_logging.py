"""Structured JSONL logging (SPEC §11) via structlog.

Every record is one JSON line with exactly the mandated envelope:
``{timestamp, event_type, layer, data, session_id}``. No print statements.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, TextIO

import structlog


def _envelope(logger: Any, method_name: str, event_dict: dict) -> dict:
    return {
        "timestamp": event_dict.pop("timestamp"),
        "event_type": event_dict.pop("event"),
        "layer": event_dict.pop("layer"),
        "session_id": event_dict.pop("session_id"),
        "data": {k: v for k, v in event_dict.items() if k != "level"},
    }


class JsonlEventLogger:
    """A bound, file-backed JSONL event logger for one stream (e.g. system_log)."""

    def __init__(self, stream: str | Path | TextIO, layer: str, session_id: str) -> None:
        if isinstance(stream, (str, Path)):
            Path(stream).parent.mkdir(parents=True, exist_ok=True)
            self._fh: TextIO = open(stream, "a", encoding="utf-8")
            self._owns_fh = True
        else:
            self._fh = stream
            self._owns_fh = False
        logger = structlog.wrap_logger(
            structlog.WriteLogger(self._fh),
            processors=[
                structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
                _envelope,
                structlog.processors.JSONRenderer(),
            ],
        )
        self._log = logger.bind(layer=layer, session_id=session_id)

    def event(self, event_type: str, **data: Any) -> None:
        self._log.msg(event_type, **data)
        if isinstance(self._fh, io.TextIOBase):
            self._fh.flush()

    def close(self) -> None:
        if self._owns_fh:
            self._fh.close()
