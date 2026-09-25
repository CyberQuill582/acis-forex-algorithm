"""The §7.5 attach protocol, the phase-8 contract half (ACIS-06 §7.5, GAP-0018). Moved out of
core/execution/venue.py (legibility budget, GAP-P12M-01). Invariants:
  * the descriptor's symbol map must cover the enabled universe (the §13 suffix problem
    dies here, once);
  * flat-or-decide: an account holding open positions at attach HALTS for a human
    decision, never caught-and-continued by any agent path.
"""

from __future__ import annotations

from core.data.errors import DataQualityError
from core.execution.venue import BrokerPosition, ExecutionFace


class AttachHalt(Exception):
    """GAP-0018 flat-or-decide: the account holds open positions at attach —
    a HUMAN must decide (flatten via platform, or manage manually until flat).
    Never caught-and-continued by any agent path."""

    def __init__(self, positions: tuple[BrokerPosition, ...]) -> None:
        self.positions = positions
        super().__init__(
            f"attach halted: {len(positions)} open position(s) on the account — "
            "human decision required (flatten first, or manage manually until flat)")


async def verify_attach(face: ExecutionFace, enabled_symbols: set[str],
                        logger) -> None:
    """§7.5 attach protocol, the phase-8 contract half: (1) the capability
    descriptor's symbol map must cover the enabled universe (the §13 suffix
    problem dies here, once); (2) flat-or-decide (GAP-0018). Rulebook loading
    is the §9.5 config layer's job and precedes this call; paper-always mode
    start follows it."""
    missing = enabled_symbols - set(face.descriptor.symbol_map)
    if missing:
        raise DataQualityError("symbol_map", sorted(missing),
                               "descriptor must map every enabled instrument")
    positions = await face.open_positions()
    if positions:
        logger.event("ATTACH_HALTED_OPEN_POSITIONS", venue=face.name,
                     count=len(positions))
        raise AttachHalt(positions)
    logger.event("ATTACH_VERIFIED", venue=face.name,
                 symbols=sorted(enabled_symbols))
